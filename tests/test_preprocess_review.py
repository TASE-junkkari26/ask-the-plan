"""Deterministic, source-preserving samples and safe offline review artifacts."""
from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from html.parser import HTMLParser
import importlib.util
import io
import json
from pathlib import Path
import shutil
import subprocess
from types import SimpleNamespace
import tempfile
import unittest
from unittest.mock import patch

from PIL import Image, ImageDraw

from contracts.models import PreparedDrawing
from drawing_preprocessor.core import PreparationError, load_manifest
from drawing_preprocessor.review import _SCRIPT, create_review, render_review


class GalleryParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.cards = []
        self.scripts = []
        self.json_text = ""
        self.in_sample = False
        self.svg_views = []
        self.controls = set()
        self.asset_links = []
        self.images = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "article":
            self.cards.append(attrs)
        if tag == "script":
            self.scripts.append(attrs)
            self.in_sample = attrs.get("id") == "sample-data"
        if tag == "svg":
            self.svg_views.append(attrs.get("viewbox"))
        if tag == "img":
            self.images.append(attrs)
        if "id" in attrs:
            self.controls.add(attrs["id"])
        for name in ("href", "src"):
            if name in attrs:
                self.asset_links.append(attrs[name])

    def handle_endtag(self, tag):
        if tag == "script":
            self.in_sample = False

    def handle_data(self, data):
        if self.in_sample:
            self.json_text += data


class PreprocessReviewTests(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.dataset = self.root / "dataset"
        self.data = self.dataset / "data"
        self.output = self.root / "review"
        for collection in ("alpha", "beta", "gamma"):
            (self.data / collection).mkdir(parents=True)
        for index, (collection, name) in enumerate((("alpha", "one.png"),
                                                  ("alpha", "two.png"),
                                                  ("beta", "three.png")), 1):
            image = Image.new("RGB", (161, 113), "white")
            ImageDraw.Draw(image).rectangle((20 + index, 20, 110, 80), outline=(index, 0, 0), width=3)
            image.save(self.data / collection / name)
        (self.data / "gamma" / "broken.png").write_bytes(b"not a decodable PNG")
        (self.data / "beta" / "duplicate.png").write_bytes((self.data / "alpha" / "one.png").read_bytes())
        (self.data / "alpha" / "LICENSE.md").write_text("Source attribution and per-file credits\n", encoding="utf-8")

    def review(self, **kwargs):
        with redirect_stderr(io.StringIO()):
            index = create_review(self.dataset, self.output, **kwargs)
        text = index.read_text(encoding="utf-8")
        parsed = GalleryParser()
        parsed.feed(text)
        manifest = json.loads((self.output / "sample.json").read_text(encoding="utf-8"))
        return manifest, text, parsed

    def test_seeded_selection_is_repeatable_deduplicated_and_preserves_sources(self):
        before = {path.relative_to(self.data).as_posix(): path.read_bytes()
                  for path in self.data.rglob("*") if path.is_file()}
        first, _, _ = self.review(count=20, seed=7)
        second, _, _ = self.review(count=20, seed=7)
        self.assertEqual(first["review_id"], second["review_id"])
        self.assertEqual(first["samples"], second["samples"])
        self.assertEqual(first["selected_count"], 4)
        self.assertEqual(len({sample["source_sha256"] for sample in first["samples"]}), 4)
        self.assertEqual(before, {path.relative_to(self.data).as_posix(): path.read_bytes()
                                  for path in self.data.rglob("*") if path.is_file()})
        for sample in first["samples"]:
            if sample["status"] == "prepared":
                artifact = json.loads((self.output / sample["manifest_uri"]).read_text(encoding="utf-8"))
                original = self.output / sample["artifact_root"] / artifact["original_uri"]
                self.assertEqual(hashlib.sha256(original.read_bytes()).hexdigest(), sample["source_sha256"])

    def test_prepare_failure_stays_in_sample_and_has_a_pending_review_card(self):
        manifest, html, parsed = self.review(count=20, seed=8)
        self.assertEqual(manifest["requested_count"], 20)
        self.assertEqual(manifest["selected_count"], 4)
        self.assertEqual(len(manifest["samples"]), 4)
        self.assertEqual(sum(sample["status"] == "prepared" for sample in manifest["samples"]), 3)
        self.assertEqual(sum(sample["status"] == "error" for sample in manifest["samples"]), 1)
        self.assertEqual(len(parsed.cards), 4)
        self.assertTrue(all(card["data-status"] == "pending" for card in parsed.cards))
        self.assertIn("Preparation failed:", html)
        self.assertTrue(manifest["warnings"])
        self.assertNotIn("human_review", manifest)

    def test_round_robin_small_sample_uses_distinct_source_folders(self):
        manifest, _, _ = self.review(count=2, seed=42)
        self.assertEqual(manifest["selected_count"], 2)
        self.assertEqual(len({sample["collection"] for sample in manifest["samples"]}), 2)

    def test_generated_outputs_are_excluded_when_review_is_inside_dataset(self):
        self.output = self.data / "generated-review"
        first, _, _ = self.review(count=20, seed=42)
        second, _, _ = self.review(count=20, seed=42)
        self.assertEqual(first["selected_count"], 4)
        self.assertEqual(first["samples"], second["samples"])
        self.assertFalse(any(sample["source"].startswith("generated-review/") for sample in second["samples"]))

    def test_gallery_includes_export_filters_attribution_and_source_coordinate_overlays(self):
        manifest, html, parsed = self.review(count=20, seed=42)
        self.assertTrue({"export", "import", "import-file", "import-message", "filter", "progress",
                         "storage-warning", "image-warning", "file-hint"}.issubset(parsed.controls))
        self.assertIn("localStorage", html)
        self.assertIn("human_review:sample.samples.map", html)
        self.assertIn("Download review JSON", html)
        self.assertEqual(len(parsed.svg_views), 3)
        self.assertTrue(all(view == "0 0 161 113" for view in parsed.svg_views))
        self.assertEqual(json.loads(parsed.json_text), manifest)
        self.assertFalse(any(url.startswith(("http:", "https:", "file:")) for url in parsed.asset_links))
        self.assertTrue(parsed.images)
        self.assertTrue(all(int(image["width"]) > 0 and int(image["height"]) > 0 for image in parsed.images))
        self.assertIn('class="image-error"', html)
        self.assertIn("localhost HTTP", html)
        for sample in manifest["samples"]:
            if sample.get("license_catalog_uri"):
                copied = self.output / sample["license_catalog_uri"]
                self.assertEqual(copied.read_text(encoding="utf-8"), "Source attribution and per-file credits\n")

    def test_untrusted_source_names_and_error_messages_cannot_create_html_scripts(self):
        source = "alpha/</script><script>alert('source')</script>.png"
        selected = [{"source": source, "collection": "alpha", "source_sha256": "a" * 64}]
        with patch("drawing_preprocessor.review._select", return_value=selected), \
                patch("drawing_preprocessor.review.prepare_drawing",
                      side_effect=PreparationError("<script>alert('error')</script>")):
            manifest, html, parsed = self.review(count=1, seed=42)
        self.assertEqual(len(parsed.scripts), 2)
        self.assertEqual(json.loads(parsed.json_text)["samples"][0]["source"], source)
        self.assertIn("&lt;script&gt;alert", html)
        self.assertIn("\\u003c/script\\u003e", html)
        self.assertEqual(manifest["selected_count"], 1)

    def test_untrusted_ocr_text_is_escaped_and_boxes_keep_source_frame(self):
        self.dataset = self.data / "alpha"
        actual_load = load_manifest
        injected = "</script><script>alert('ocr')</script>"

        def with_ocr(*args, **kwargs):
            result = actual_load(*args, **kwargs)
            data = result.model_dump(mode="json")
            data["ocr"] = {"status": "complete", "engine": "test-ocr", "version": "test",
                           "languages": ["eng"], "warnings": [], "spans": [{
                               "id": "word-1", "text": injected, "frame_id": result.source_frame_id,
                               "bbox": [20, 30, 60, 40], "confidence": 0.8, "engine": "test-ocr"}]}
            return PreparedDrawing.model_validate(data)

        with patch("drawing_preprocessor.review.load_manifest", side_effect=with_ocr):
            _, html, parsed = self.review(count=1, seed=1)
        self.assertEqual(len(parsed.scripts), 2)
        self.assertIn("&lt;/script&gt;&lt;script&gt;alert", html)
        self.assertIn('<rect x="20.0" y="30.0" width="40.0" height="10.0">', html)
        self.assertEqual(parsed.svg_views, ["0 0 161 113"])

    def test_rerender_keeps_sample_identity_bytes_and_cached_artifacts_unchanged(self):
        manifest, _, _ = self.review(count=20, seed=42)
        retained = {path.relative_to(self.output).as_posix(): path.read_bytes()
                    for path in self.output.rglob("*") if path.is_file() and path.name != "index.html"}
        (self.output / "index.html").write_text("obsolete page", encoding="utf-8")
        with patch("drawing_preprocessor.review.prepare_drawing", side_effect=AssertionError("must not prepare")):
            index = render_review(self.output)
        after = {path.relative_to(self.output).as_posix(): path.read_bytes()
                 for path in self.output.rglob("*") if path.is_file() and path.name != "index.html"}
        self.assertEqual(retained, after)
        parsed = GalleryParser()
        parsed.feed(index.read_text(encoding="utf-8"))
        self.assertEqual(json.loads(parsed.json_text)["review_id"], manifest["review_id"])
        self.assertIn("import-file", parsed.controls)
        self.assertIn("file-hint", parsed.controls)

    def test_rerender_missing_artifact_retains_sample_and_reports_error_card(self):
        manifest, _, _ = self.review(count=20, seed=42)
        first = next(sample for sample in manifest["samples"] if sample["status"] == "prepared")
        original_sample_bytes = (self.output / "sample.json").read_bytes()
        (self.output / first["artifact_root"] / "source.png").unlink()
        index = render_review(self.output)
        html = index.read_text(encoding="utf-8")
        parsed = GalleryParser()
        parsed.feed(html)
        self.assertEqual(len(parsed.cards), manifest["selected_count"])
        self.assertIn("Artifact inspection failed", html)
        self.assertEqual((self.output / "sample.json").read_bytes(), original_sample_bytes)

    def test_review_rejects_output_that_contains_dataset(self):
        with self.assertRaises(PreparationError):
            create_review(self.dataset, self.root)
        with self.assertRaises(PreparationError):
            create_review(self.dataset, self.data)

    def test_review_rejects_invalid_request_and_empty_dataset(self):
        for count in (0, 201, True):
            with self.subTest(count=count), self.assertRaises(PreparationError):
                create_review(self.dataset, self.output, count=count)
        empty = self.root / "empty"
        empty.mkdir()
        with self.assertRaises(PreparationError):
            create_review(empty, self.output)


class ReviewImportTests(unittest.TestCase):
    @unittest.skipUnless(shutil.which("node"), "Node.js is required to execute gallery import checks")
    def test_import_validates_gallery_and_sources_before_merging_without_overwrite(self):
        sample = {"review_id": "review-test", "samples": [
            {"index": 1, "source": "alpha/a.png", "source_sha256": "a" * 64},
            {"index": 2, "source": "beta/b.png", "source_sha256": "b" * 64},
        ]}
        entries = [{**item, "status": "pass", "notes": "checked"} for item in sample["samples"]]
        existing = {"1": {"status": "pass", "notes": "keep me"},
                    "2": {"status": "pending", "notes": ""}}
        valid = {"review_id": sample["review_id"], "human_review": entries}
        cases = [{"name": "valid", "incoming": valid, "saved": {}},
                 {"name": "wrong gallery", "incoming": {**valid, "review_id": "another-review"}, "saved": existing},
                 {"name": "missing entry", "incoming": {**valid, "human_review": entries[:1]}, "saved": existing},
                 {"name": "duplicate entry", "incoming": {**valid, "human_review": [entries[0], entries[0]]}, "saved": existing}]
        for name, changed in (("unknown entry", {"index": 3}), ("wrong hash", {"source_sha256": "c" * 64}),
                              ("wrong source", {"source": "other.png"}), ("invalid status", {"status": "approved"}),
                              ("invalid notes", {"notes": 42}), ("oversized notes", {"notes": "x" * 5001})):
            cases.append({"name": name, "incoming": {**valid, "human_review": [{**entries[0], **changed}, entries[1]]},
                          "saved": existing})
        cases.append({"name": "conflict", "incoming": {**valid, "human_review": [
            {**entries[0], "status": "problem", "notes": "replace old"},
            {**entries[1], "status": "uncertain", "notes": "new note"}]}, "saved": existing})
        cases.append({"name": "oversized file", "incoming": valid, "saved": existing, "size": 5 * 1024 * 1024 + 1})
        harness = r"""
const vm = require('node:vm');
(async () => {
  let input=''; for await (const chunk of process.stdin) input+=chunk;
  const payload=JSON.parse(input), results=[];
  for (const test of payload.cases) {
    function element(extra={}) { return {dataset:{},value:'',hidden:true,textContent:'',handlers:{},files:[],
      addEventListener(event,fn){this.handlers[event]=fn;},setAttribute(){},click(){},...extra}; }
    const ids={};
    function byId(id) { return ids[id] ||= element(); }
    byId('sample-data').textContent=JSON.stringify(payload.sample); byId('filter').value='all';
    const cards=payload.sample.samples.map(item => {
      const notes=element(), buttons=['pending','pass','problem','uncertain'].map(status => element({dataset:{status}}));
      return element({dataset:{id:String(item.index)},
        querySelector(selector){return selector==='textarea' ? notes : null;},
        querySelectorAll(selector){return selector==='button[data-status]' ? buttons : [];}});
    });
    const key='drawing-preprocessor-review:'+payload.sample.review_id;
    const memory={[key]:JSON.stringify(test.saved)};
    const context=vm.createContext({document:{getElementById:byId,
      querySelectorAll(selector){return selector==='article[data-id]' ? cards : [];}},
      localStorage:{getItem:k=>memory[k]??null,setItem:(k,v)=>{memory[k]=v;}},location:{protocol:'http:'}});
    vm.runInContext(payload.script,context);
    let reads=0;
    byId('import-file').files=[{size:test.size??100,text:async()=>{reads++;return JSON.stringify(test.incoming);}}];
    await byId('import-file').handlers.change();
    results.push({name:test.name,saved:JSON.parse(memory[key]),message:byId('import-message').textContent,
      messageHidden:byId('import-message').hidden,reads});
  }
  process.stdout.write(JSON.stringify(results));
})().catch(error => {process.stderr.write(error.stack);process.exitCode=1;});
"""
        result = subprocess.run([shutil.which("node"), "-e", harness],
                                input=json.dumps({"script": _SCRIPT, "sample": sample, "cases": cases}),
                                text=True, encoding="utf-8", capture_output=True, timeout=20, check=True)
        results = json.loads(result.stdout)
        for case in results:
            with self.subTest(case=case["name"]):
                self.assertFalse(case["messageHidden"])
                if case["name"] == "valid":
                    self.assertEqual(case["saved"]["1"], {"status": "pass", "notes": "checked"})
                    self.assertEqual(case["saved"]["2"], {"status": "pass", "notes": "checked"})
                    self.assertIn("Imported 2", case["message"])
                elif case["name"] == "conflict":
                    self.assertEqual(case["saved"]["1"], existing["1"])
                    self.assertEqual(case["saved"]["2"], {"status": "uncertain", "notes": "new note"})
                    self.assertIn("1 conflicting", case["message"])
                else:
                    self.assertEqual(case["saved"], existing)
                    self.assertIn("Import rejected", case["message"])
                    if case["name"] == "oversized file":
                        self.assertEqual(case["reads"], 0)


class TesseractSetupCheckTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        path = Path(__file__).resolve().parents[1] / "scripts" / "setup_tesseract.py"
        spec = importlib.util.spec_from_file_location("tesseract_setup_under_test", path)
        cls.setup = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(cls.setup)

    def test_nonwindows_check_provides_instructions_without_download_or_install(self):
        output = io.StringIO()
        with patch.object(self.setup, "os", SimpleNamespace(name="posix")), \
                patch.object(self.setup, "_download") as download, \
                patch.object(self.setup, "_install_engine") as install, \
                patch.object(self.setup, "_run") as run, redirect_stdout(output):
            status = self.setup.main(["--check", "--languages", "eng", "fin"])
        self.assertEqual(status, 1)
        self.assertIn("tesseract-ocr-eng tesseract-ocr-fin", output.getvalue())
        self.assertIn("brew install", output.getvalue())
        download.assert_not_called()
        install.assert_not_called()
        run.assert_not_called()

    def test_windows_check_does_not_download_or_install(self):
        with patch.object(self.setup, "os", SimpleNamespace(name="nt")), \
                patch.object(self.setup.platform, "machine", return_value="AMD64"), \
                patch.object(self.setup, "_download") as download, \
                patch.object(self.setup, "_install_engine") as install, \
                patch.object(self.setup, "_check", return_value=True) as check:
            status = self.setup.main(["--check", "--languages", "eng", "eng", "fin"])
        self.assertEqual(status, 0)
        self.assertEqual(check.call_args.args[1], ["eng", "fin"])
        download.assert_not_called()
        install.assert_not_called()


if __name__ == "__main__":
    unittest.main()
