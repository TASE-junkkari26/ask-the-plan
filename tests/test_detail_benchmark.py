"""Offline reproducibility and serialization checks for the detailed rerun.

Synthetic files and httpx.MockTransport only; no source QA or live calls.
"""
from __future__ import annotations

import asyncio
import hashlib
from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
from PIL import Image

from experiments.image_questions.benchmark_detail import SerialRecorder, plan, protected_files, run as run_benchmark
from experiments.image_questions.audit_detail_run import audit
from experiments.image_questions.compare_detail import compare
from gemini import AsyncGeminiClient, GeminiError, GeminiSettings
from tests.test_gemini import interaction


KEY = "synthetic-serial-benchmark-key"
SCHEMA = {"type": "object", "properties": {"status": {"type": "string"}}, "required": ["status"]}


def png(color="white"):
    with Image.new("RGB", (4, 3), color) as image, BytesIO() as stream:
        image.save(stream, format="PNG")
        return stream.getvalue()


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def synthetic_baseline(root, count=100):
    root.mkdir()
    cases = [{"id": f"Q{i:03d}", "line": i, "path": f"data/synthetic/{i}.png",
              "question": "Montako ovea tässä pohjassa on?", "source": "synthetic",
              "family": "Count / Doors", "language": "fi", "page": 1}
             for i in range(1, count+1)]
    save(root / "cases.json", {"seed": 20261114, "cases": cases,
                              "dataset_questions_sha256": "a"*64})
    save(root / "run-complete.json", {"cases": count})
    for name in ("evaluation.json", "results.csv", "REPORT.md"):
        (root / name).write_text("Synthetic protected content\n", encoding="utf-8")
    content = png()
    sha = hashlib.sha256(content).hexdigest()
    for case in cases:
        folder = root / case["id"]
        folder.mkdir()
        (folder / "input.png").write_bytes(content)
        save(folder / "source.json", {**case, "input_sha256": sha,
                                      "source_sha256": "b"*64, "width": 4, "height": 3})
        (folder / "SOURCE_LICENSE.md").write_text("Synthetic fixture only.\n", encoding="utf-8")
        save(folder / "api-response.json", {"synthetic": True})
        save(folder / "outcome.json", {"synthetic": True})
    return cases


class DetailPlanTests(unittest.TestCase):
    def test_plan_copies_exact_100_case_and_png_bytes_without_qa(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline, target = root / "baseline", root / "detail"
            cases = synthetic_baseline(baseline)
            before = protected_files(baseline)
            plan(baseline, target)
            self.assertEqual((target / "cases.json").read_bytes(), (baseline / "cases.json").read_bytes())
            self.assertEqual(len(json.loads((target / "cases.json").read_text(encoding="utf-8"))["cases"]), 100)
            for case in cases:
                for name in ("input.png", "source.json", "SOURCE_LICENSE.md"):
                    self.assertEqual((target / case["id"] / name).read_bytes(),
                                     (baseline / case["id"] / name).read_bytes())
            self.assertEqual(before, protected_files(baseline))
            manifest = json.loads((target / "comparison-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["case_concurrency"], 1)
            self.assertEqual(manifest["provider_concurrency"], 1)
            self.assertEqual(manifest["options"], {"mode": "tiles", "max_calls": 9})
            self.assertFalse(any(root.rglob("questions.jsonl")))
            self.assertFalse(any("answer" in case for case in cases))
            with self.assertRaises(FileExistsError):
                plan(baseline, target)

    def test_plan_requires_completed_100_and_checks_saved_input_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            incomplete = root / "incomplete"
            synthetic_baseline(incomplete, count=99)
            with self.assertRaisesRegex(ValueError, "completed 100-case"):
                plan(incomplete, root / "wrong-count")
            baseline = root / "baseline"
            synthetic_baseline(baseline)
            (baseline / "run-complete.json").unlink()
            with self.assertRaisesRegex(ValueError, "completed 100-case"):
                plan(baseline, root / "unfinished")
            save(baseline / "run-complete.json", {"cases": 100})
            (baseline / "Q001" / "input.png").write_bytes(png("black"))
            with self.assertRaisesRegex(ValueError, "recorded hash"):
                plan(baseline, root / "corrupt")

    def test_comparison_stops_before_evaluation_for_unfinished_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            baseline = root / "baseline"
            synthetic_baseline(baseline)
            target = root / "detail"
            target.mkdir()
            (target / "cases.json").write_bytes((baseline / "cases.json").read_bytes())
            # No evaluation or source QA exists in the target. Completion must
            # fail before attempting to parse either run's evaluation artifact.
            with self.assertRaisesRegex(ValueError, "finish every case"):
                compare(baseline, target)
            self.assertFalse((target / "comparison.json").exists())

    def test_audit_stops_before_protected_baseline_for_unfinished_run(self):
        with tempfile.TemporaryDirectory() as temporary:
            run = Path(temporary)
            save(run / "cases.json", {"cases": [{"id": "Q001"}]})
            save(run / "comparison-plan.json", {"baseline": "unavailable-synthetic-baseline"})
            with self.assertRaisesRegex(ValueError, "Finish all responses"):
                audit(run)
            self.assertFalse((run / "audit.json").exists())

    def test_started_or_partially_recorded_run_is_never_reissued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for name in ("run-started.json", "provider"):
                run = root / name.replace(".", "-")
                run.mkdir()
                marker = run / name
                marker.mkdir() if name == "provider" else marker.write_text("{}", encoding="utf-8")
                with self.subTest(marker=name):
                    with self.assertRaisesRegex(ValueError, "repeat/overwrite"):
                        run_benchmark(run, root / "unused-dataset", 8014)


class SerialRecorderTests(unittest.IsolatedAsyncioTestCase):
    def recorder(self, directory, handler):
        original_init = AsyncGeminiClient.__init__

        def injected_init(instance):
            original_init(instance, GeminiSettings(api_key=KEY),
                          transport=httpx.MockTransport(handler))

        with patch.object(AsyncGeminiClient, "__init__", injected_init):
            return SerialRecorder(directory, {"case_id": "Q001"})

    async def test_concurrent_tasks_produce_serial_actual_requests_and_exact_audit_images(self):
        active, maximum = 0, 0
        requests = []

        async def handler(request):
            nonlocal active, maximum
            active += 1
            maximum = max(maximum, active)
            requests.append(request)
            try:
                await asyncio.sleep(.005)
                return httpx.Response(200, json=interaction())
            finally:
                active -= 1

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "source.png"
            content = png()
            image.write_bytes(content)
            async with self.recorder(root, handler) as recorder:
                replies = await asyncio.gather(*(recorder.generate_candidates(
                    f"Question {number}", system="Synthetic system", image=image, schema=SCHEMA)
                    for number in range(5)))
                self.assertEqual(recorder.number, 5)
            self.assertEqual(maximum, 1)
            self.assertEqual(active, 0)
            self.assertEqual(len(requests), 5)
            self.assertEqual(len(replies), 5)
            for number in range(1, 6):
                folder = root / "provider" / f"P{number:04d}"
                self.assertEqual((folder / "input.png").read_bytes(), content)
                request = json.loads((folder / "request.json").read_text(encoding="utf-8"))
                self.assertEqual(request["image_sha256"], hashlib.sha256(content).hexdigest())
                self.assertEqual(request["image_bytes"], len(content))
                self.assertEqual(request["case_id"], "Q001")
                self.assertEqual(request["settings"]["thinking_level"], "low")
                self.assertEqual(request["retries"], 0)
                self.assertFalse(request["store"])
                self.assertNotIn("api_key", request["settings"])
                self.assertTrue((folder / "response.json").is_file())
                self.assertTrue((folder / "timing.json").is_file())
                for path in folder.glob("*.json"):
                    self.assertNotIn(KEY, path.read_text(encoding="utf-8"))

    async def test_provider_error_records_safe_category_and_never_retries(self):
        calls = 0

        def handler(_):
            nonlocal calls
            calls += 1
            return httpx.Response(403, json={"error": {
                "status": "PERMISSION_DENIED", "message": f"Private detail {KEY}"}})

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            image = root / "source.png"
            image.write_bytes(png())
            async with self.recorder(root, handler) as recorder:
                with self.assertRaises(GeminiError):
                    await recorder.generate_candidates("Question", system="Synthetic system",
                                                       image=image, schema=SCHEMA)
            self.assertEqual(calls, 1)
            folder = root / "provider" / "P0001"
            error = json.loads((folder / "error.json").read_text(encoding="utf-8"))
            self.assertEqual(error["http_status"], 403)
            self.assertEqual(error["provider_code"], "PERMISSION_DENIED")
            self.assertFalse((folder / "response.json").exists())
            self.assertTrue((folder / "timing.json").exists())
            for path in folder.glob("*.json"):
                self.assertNotIn(KEY, path.read_text(encoding="utf-8"))
                self.assertNotIn("Private detail", path.read_text(encoding="utf-8"))


if __name__ == "__main__":
    unittest.main()
