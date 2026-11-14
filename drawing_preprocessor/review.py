"""Portable, human-reviewed samples of raster preparation outputs.

Sampling is balanced across source folders rather than estimating corpus-wide
accuracy. No reference QA is consulted and no assessment is filled in by a model.
"""
from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import asdict
import hashlib
from html import escape
import json
from pathlib import Path
import random
import shutil
import sys
from urllib.parse import quote

from .core import PIPELINE_VERSION, PreparationError, PreprocessConfig, load_manifest, prepare_drawing


def _json(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"


def _sha(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _url(relative: str) -> str:
    return quote(relative, safe="/")


def _select(data_root: Path, output_root: Path, count: int, seed: int) -> list[dict]:
    strata: dict[str, list[Path]] = defaultdict(list)
    for path in data_root.rglob("*"):
        if path.suffix.lower() not in {".png", ".jpg", ".jpeg"} or not path.is_file():
            continue
        resolved = path.resolve()
        if not resolved.is_relative_to(data_root) or resolved.is_relative_to(output_root):
            continue
        parts = path.relative_to(data_root).parts
        strata[parts[0] if len(parts) > 1 else "root"].append(path)
    rng = random.Random(seed)
    pools: dict[str, deque[Path]] = {}
    for name in sorted(strata):
        paths = sorted(strata[name], key=lambda p: p.relative_to(data_root).as_posix())
        rng.shuffle(paths)
        pools[name] = deque(paths)
    names = list(pools)
    rng.shuffle(names)
    selected: list[dict] = []
    seen: set[str] = set()
    while len(selected) < count and names:
        remaining = []
        for name in names:
            pool = pools[name]
            while pool:
                path = pool.popleft()
                relative = path.relative_to(data_root).as_posix()
                try:
                    sha = _sha(path)
                except OSError as exc:
                    selected.append({"source": relative, "collection": name, "source_sha256": None,
                                     "selection_error": f"Source could not be read ({type(exc).__name__})."})
                    break
                if sha in seen:
                    continue
                seen.add(sha)
                selected.append({"source": relative, "collection": name, "source_sha256": sha})
                break
            if pool:
                remaining.append(name)
            if len(selected) >= count:
                break
        names = remaining
    return selected


def _license_catalogs(data_root: Path, output_root: Path, samples: list[dict]) -> tuple[dict[str, str], list[str]]:
    catalogs: dict[str, str] = {}
    warnings: list[str] = []
    for collection in sorted({sample["collection"] for sample in samples}):
        source = data_root / "LICENSE.md" if collection == "root" else data_root / collection / "LICENSE.md"
        if not source.is_file() or not source.resolve().is_relative_to(data_root):
            continue
        name = "licenses/" + hashlib.sha256(collection.encode("utf-8")).hexdigest()[:16] + ".md"
        target = output_root / name
        try:
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, target)
            catalogs[collection] = name
        except OSError as exc:
            warnings.append(f"Attribution catalog for {collection} could not be copied ({type(exc).__name__}).")
    return catalogs, warnings


def _image(uri: str, description: str, *, css_class: str = "", width: int | None = None,
           height: int | None = None) -> str:
    dimensions = f' width="{width}" height="{height}"' if width is not None and height is not None else ""
    return (f'<a href="{_url(uri)}" target="_blank" rel="noopener">'
            f'<img class="{css_class}" loading="lazy"{dimensions} src="{_url(uri)}" '
            f'alt="{escape(description, quote=True)}"></a>')


def _card(sample: dict, prepared: dict | None) -> str:
    index = sample["index"]
    source = escape(sample["source"])
    license_uri = sample.get("license_catalog_uri")
    license_link = (f'<a href="{_url(license_uri)}" target="_blank" rel="noopener">Source attribution catalog</a>'
                    if license_uri else '<span>Attribution catalog was not found; consult the original dataset before sharing.</span>')
    header = (f'<article id="sample-{index}" data-id="{index}" data-status="pending">'
              f'<header><h2>{index}. {source}</h2><span class="collection">{escape(sample["collection"])}</span></header>'
              f'<p class="provenance">Source SHA-256: <code>{sample.get("source_sha256") or "unavailable"}</code><br>{license_link}</p>')
    controls = (f'<div class="review-controls"><strong>Human review:</strong> '
                f'<button type="button" data-status="pass" aria-pressed="false">Pass</button> '
                f'<button type="button" data-status="problem" aria-pressed="false">Problem</button> '
                f'<button type="button" data-status="uncertain" aria-pressed="false">Uncertain</button> '
                f'<button type="button" data-status="pending" aria-pressed="false">Reset</button>'
                f'<label>Notes<textarea rows="2" maxlength="5000" placeholder="Missing notes/legend, clipped drawing, bad OCR, wrong box…"></textarea></label></div>')
    if prepared is None:
        return header + f'<p class="error">Preparation failed: {escape(sample["error"])}</p>' + controls + '</article>'

    artifact_root = sample["artifact_root"]
    regions = prepared["regions"]
    full = next(region for region in regions if region["role"] == "full_source")
    ocr = prepared["ocr"]
    width, height = prepared["source_width"], prepared["source_height"]
    rects = []
    words = []
    for span in ocr["spans"]:
        left, top, right, bottom = span["bbox"]
        confidence = "unknown" if span["confidence"] is None else f'{span["confidence"]:.3f}'
        rects.append(f'<rect x="{left}" y="{top}" width="{right-left}" height="{bottom-top}"><title>{escape(span["text"])} · engine confidence {confidence}</title></rect>')
        words.append(f'<li><code>{escape(span["text"])}</code> — {escape(str(span["bbox"]))}; engine confidence {confidence}</li>')
    overview_uri = artifact_root + "/" + full["overview_uri"]
    source_uri = artifact_root + "/" + prepared["source_image_uri"]
    original_uri = artifact_root + "/" + prepared["original_uri"]
    full_preview = (f'<figure><figcaption>Uncropped source · {width} × {height} source pixels</figcaption>'
                    f'<label class="toggle"><input type="checkbox" data-overlay> Show OCR word boxes</label>'
                    f'<div class="source-stack"><a href="{_url(source_uri)}" target="_blank" rel="noopener">'
                    f'<img loading="lazy" width="{full["overview_width"]}" height="{full["overview_height"]}" '
                    f'src="{_url(overview_uri)}" alt="Uncropped source overview"></a>'
                    f'<svg class="ocr-overlay" viewBox="0 0 {width} {height}" preserveAspectRatio="none" aria-label="OCR boxes in original source pixels">'
                    + "".join(rects) + '</svg></div><p class="image-error" hidden></p>'
                    f'<a href="{_url(original_uri)}" target="_blank" rel="noopener">Original bytes</a> · '
                    f'<a href="{_url(source_uri)}" target="_blank" rel="noopener">Source PNG in declared pixel orientation</a></figure>')
    layout_scale = min(1.0, 1400 / max(width, height))
    layout_preview = ('<figure><figcaption>Layout proposals · all boxes are heuristic</figcaption>'
                      + _image(artifact_root + '/layout.png', 'Candidate region boxes over the source',
                               width=max(1, round(width * layout_scale)), height=max(1, round(height * layout_scale)))
                      + '<p class="image-error" hidden></p></figure>')
    candidates = []
    for region in regions:
        if region["role"] == "full_source":
            continue
        uri = artifact_root + "/" + region["overview_uri"]
        full_uri = artifact_root + "/" + region["image_uri"]
        candidates.append('<figure><figcaption>' + escape(region["role"]) + ' · source box '
                          + escape(str(region["source_bbox"])) + '</figcaption>'
                          + _image(uri, region["role"] + ' overview', width=region["overview_width"], height=region["overview_height"])
                          + '<p class="image-error" hidden></p>'
                          + f'<a href="{_url(full_uri)}" target="_blank" rel="noopener">Full-resolution candidate</a>'
                          + '<p>' + escape(region["reason"]) + '</p></figure>')
    warnings = '<ul>' + ''.join('<li>' + escape(w) + '</li>' for w in prepared["warnings"]) + '</ul>'
    body = (f'<p><strong>OCR: {escape(ocr["status"])}</strong> · engine {escape(str(ocr["engine"] or "none"))} '
            f'{escape(str(ocr["version"] or ""))} · {len(ocr["spans"])} returned words · '
            f'<a href="{_url(sample["manifest_uri"])}">Prepared manifest</a></p>'
            '<div class="previews">' + full_preview + layout_preview + '</div>'
            '<h3>Candidate crops</h3><div class="candidates">'
            + (''.join(candidates) if candidates else '<p>No separate crop proposed; retain the full-source view.</p>')
            + '</div><details><summary>Warnings</summary>' + warnings + '</details>'
            + f'<details><summary>Raw OCR words ({len(words)})</summary><ol class="words">'
            + ''.join(words) + '</ol></details>')
    return header + body + controls + '</article>'


_STYLE = """
:root{font-family:system-ui,sans-serif;color:#202020;background:#f4f4f2;font-size:15px}
body{margin:0}main{max-width:1400px;margin:auto;padding:20px}h1{font-size:26px}h2{font-size:18px;overflow-wrap:anywhere}
h3{font-size:16px}.top{position:sticky;top:0;z-index:2;padding:12px 20px;background:#fff;border-bottom:1px solid #bbb;display:flex;gap:14px;align-items:center;flex-wrap:wrap}
button,select,textarea{font:inherit}button,select{background:#fff;border:1px solid #999;border-radius:3px;padding:6px 10px;cursor:pointer}
button[aria-pressed=true]{outline:2px solid #1a5f9d;background:#e6eff7}button:focus-visible,select:focus-visible,textarea:focus-visible{outline:3px solid #1a5f9d}
article{background:#fff;margin:20px 0;padding:18px;border:1px solid #ccc;border-radius:4px;scroll-margin-top:90px}
article[data-status=pass]{border-left:5px solid #36783e}article[data-status=problem]{border-left:5px solid #b83024}article[data-status=uncertain]{border-left:5px solid #9b7014}
header{display:flex;align-items:center;gap:14px;justify-content:space-between}.collection{color:#555}.provenance{font-size:12px;overflow-wrap:anywhere}
.previews{display:grid;grid-template-columns:1fr 1fr;gap:18px}.candidates{display:flex;gap:16px;overflow-x:auto;padding-bottom:12px}
figure{margin:0;min-width:0}figcaption{font-size:13px;margin:5px 0}.previews img{width:100%;height:auto;display:block;max-height:none}
.candidates figure{flex:0 0 320px;border:1px solid #ddd;padding:8px}.candidates img{display:block;max-width:100%;max-height:500px;width:auto;height:auto;margin:auto}
.candidates p{font-size:12px}.source-stack{position:relative}.source-stack img{width:100%;height:auto;display:block}
.ocr-overlay{position:absolute;inset:0;width:100%;height:100%;pointer-events:none;display:none}.source-stack.show-ocr .ocr-overlay{display:block}
.ocr-overlay rect{stroke:#d52616;stroke-width:1;vector-effect:non-scaling-stroke;fill:none}.toggle{display:block;font-size:13px;margin-bottom:6px}
.review-controls{border-top:1px solid #ddd;padding-top:12px;margin-top:16px}.review-controls label{display:block;margin-top:10px}textarea{display:block;box-sizing:border-box;width:100%;padding:8px}
details{margin:10px 0}summary{cursor:pointer}.words{max-height:350px;overflow:auto}.error,#storage-warning{color:#9f231b}a{color:#175b91}code{font-family:ui-monospace,monospace}
.image-error,#image-warning{padding:10px;background:#fff0e9;border:1px solid #b86036;color:#822d12}.load-failed{min-height:120px}.import-message{padding:8px;border:1px solid #aaa}.import-message.error{border-color:#9f231b}
@media(max-width:800px){.previews{grid-template-columns:1fr}main{padding:10px}.top{position:static}header{display:block}}
"""


_SCRIPT = """
const sample = JSON.parse(document.getElementById('sample-data').textContent);
const key = 'drawing-preprocessor-review:' + sample.review_id;
const allowed = new Set(['pending','pass','problem','uncertain']);
let saved = {};
try { saved = JSON.parse(localStorage.getItem(key) || '{}'); if (!saved || typeof saved !== 'object' || Array.isArray(saved)) saved = {}; }
catch (_) { document.getElementById('storage-warning').hidden = false; }
const cards = [...document.querySelectorAll('article[data-id]')];
function refresh() {
  const counts = {pending:0,pass:0,problem:0,uncertain:0};
  const filter = document.getElementById('filter').value;
  for (const card of cards) {
    const item = saved[card.dataset.id] || {};
    const status = allowed.has(item.status) ? item.status : 'pending';
    card.dataset.status = status; counts[status]++;
    card.hidden = filter !== 'all' && status !== filter;
    card.querySelectorAll('button[data-status]').forEach(b => b.setAttribute('aria-pressed', String(b.dataset.status === status)));
  }
  document.getElementById('progress').textContent = `${cards.length-counts.pending}/${cards.length} reviewed · ${counts.pass} pass · ${counts.problem} problem · ${counts.uncertain} uncertain`;
}
function persist() {
  try { localStorage.setItem(key, JSON.stringify(saved)); }
  catch (_) { document.getElementById('storage-warning').hidden = false; }
  refresh();
}
function syncNotes() {
  for (const card of cards) {
    const item = saved[card.dataset.id] || {};
    card.querySelector('textarea').value = typeof item.notes === 'string' ? item.notes : '';
  }
}
for (const card of cards) {
  const id = card.dataset.id;
  if (!saved[id] || typeof saved[id] !== 'object') saved[id] = {status:'pending',notes:''};
  const notes = card.querySelector('textarea');
  notes.value = typeof saved[id].notes === 'string' ? saved[id].notes : '';
  notes.addEventListener('input', () => { saved[id].notes = notes.value; persist(); });
  card.querySelectorAll('button[data-status]').forEach(button => button.addEventListener('click', () => {
    saved[id].status = button.dataset.status; persist();
  }));
  const toggle = card.querySelector('input[data-overlay]');
  if (toggle) toggle.addEventListener('change', () => card.querySelector('.source-stack').classList.toggle('show-ocr',toggle.checked));
}
document.getElementById('filter').addEventListener('change',refresh);
const importInput = document.getElementById('import-file');
document.getElementById('import').addEventListener('click',() => importInput.click());
importInput.addEventListener('change',async () => {
  const message = document.getElementById('import-message');
  const file = importInput.files[0];
  if (!file) return;
  try {
    if (file.size > 5*1024*1024) throw new Error('Review JSON is larger than 5 MiB.');
    const incoming = JSON.parse(await file.text());
    if (!incoming || typeof incoming !== 'object' || incoming.review_id !== sample.review_id)
      throw new Error('The review ID does not match this gallery. Existing ratings were kept.');
    if (!Array.isArray(incoming.human_review) || incoming.human_review.length !== sample.samples.length)
      throw new Error('The review does not contain exactly this gallery’s sample entries.');
    const expected = new Map(sample.samples.map(item => [item.index,item]));
    const seen = new Set();
    for (const item of incoming.human_review) {
      if (!item || !Number.isInteger(item.index) || seen.has(item.index) || !expected.has(item.index))
        throw new Error('Invalid, duplicate, or unknown sample index in the review.');
      const original = expected.get(item.index);
      if (item.source_sha256 !== original.source_sha256 || item.source !== original.source)
        throw new Error(`Source/hash mismatch at sample ${item.index}. Existing ratings were kept.`);
      if (!allowed.has(item.status) || typeof item.notes !== 'string' || item.notes.length > 5000)
        throw new Error(`Invalid rating or notes at sample ${item.index}.`);
      seen.add(item.index);
    }
    const next = {...saved};
    let imported = 0, conflicts = 0;
    for (const item of incoming.human_review) {
      const id = String(item.index), current = saved[id] || {status:'pending',notes:''};
      if (item.status === 'pending' && !item.notes) continue;
      const currentStatus = allowed.has(current.status) ? current.status : 'pending';
      const currentNotes = typeof current.notes === 'string' ? current.notes : '';
      if ((currentStatus !== 'pending' || currentNotes) && (currentStatus !== item.status || currentNotes !== item.notes)) {
        conflicts++; continue;
      }
      next[id] = {status:item.status,notes:item.notes}; imported++;
    }
    saved = next; persist(); syncNotes();
    message.textContent = `Imported ${imported} ratings/notes. ${conflicts} conflicting existing entries were kept. The imported file was not changed.`;
    message.className = 'import-message';
  } catch (error) {
    message.textContent = 'Import rejected: ' + error.message;
    message.className = 'import-message error';
  } finally {
    message.hidden = false; importInput.value = '';
  }
});
document.getElementById('export').addEventListener('click', () => {
  const result = {...sample, exported_at_utc:new Date().toISOString(), human_review:sample.samples.map(item => ({
    index:item.index,source:item.source,source_sha256:item.source_sha256,
    status:allowed.has(saved[String(item.index)]?.status) ? saved[String(item.index)].status : 'pending',
    notes:typeof saved[String(item.index)]?.notes === 'string' ? saved[String(item.index)].notes : ''
  }))};
  const url = URL.createObjectURL(new Blob([JSON.stringify(result,null,2)],{type:'application/json'}));
  const a = document.createElement('a'); a.href=url; a.download=sample.review_id+'.json'; a.click();
  setTimeout(() => URL.revokeObjectURL(url),1000);
});
function imageFailed(image) {
  image.classList.add('load-failed');
  const detail = image.closest('figure')?.querySelector('.image-error');
  if (detail) {
    detail.textContent = 'This image could not load. Open the gallery through the supplied localhost HTTP URL; if already using HTTP, check that the server serves this gallery’s prepared artifacts.';
    detail.hidden = false;
  }
  document.getElementById('image-warning').hidden = false;
}
for (const image of document.querySelectorAll('img')) {
  image.addEventListener('error',() => imageFailed(image));
  if (image.complete && image.naturalWidth === 0) imageFailed(image);
}
if (location.protocol === 'file:') document.getElementById('file-hint').hidden = false;
refresh();
"""


def create_review(dataset_root: Path, output_root: Path, *, count: int = 50, seed: int = 42,
                  config: PreprocessConfig | None = None) -> Path:
    """Prepare a deterministic stratified sample and return its local HTML index.

    The root may contain ``data/`` or be that directory itself. Byte-identical
    images are sampled once. Per-file preparation failures remain review cards;
    a sample shortage is reported in the manifest rather than duplicated.
    """
    if type(count) is not int or not 1 <= count <= 200:
        raise PreparationError("Review count must be an integer between 1 and 200.")
    if type(seed) is not int:
        raise PreparationError("Review seed must be an integer.")
    config = config or PreprocessConfig()
    dataset_root, output_root = Path(dataset_root).resolve(), Path(output_root).resolve()
    data_root = dataset_root / "data" if (dataset_root / "data").is_dir() else dataset_root
    if not data_root.is_dir():
        raise PreparationError("Review dataset root must be a directory containing raster sources.")
    if output_root == data_root or data_root.is_relative_to(output_root):
        raise PreparationError("Review output cannot contain or replace the dataset root.")
    output_root.mkdir(parents=True, exist_ok=True)
    samples = _select(data_root, output_root, count, seed)
    if not samples:
        raise PreparationError("No PNG/JPEG sources were found for review.")
    catalogs, license_warnings = _license_catalogs(data_root, output_root, samples)
    identity = hashlib.sha256(_json({"seed": seed, "pipeline": PIPELINE_VERSION,
                                    "config": asdict(config), "samples": samples}).encode("utf-8")).hexdigest()[:24]
    manifest = {
        "review_schema_version": "0.1.0", "review_id": "review-" + identity,
        "pipeline_version": PIPELINE_VERSION, "seed": seed, "requested_count": count,
        "selected_count": len(samples), "dataset_root_name": dataset_root.name,
        "selection": "Seeded shuffle within source folders; balanced round-robin strata; exact-byte deduplication. Not a corpus-frequency sample.",
        "config": asdict(config), "samples": samples,
        "warnings": license_warnings + ([f"Only {len(samples)} unique/readable-selection candidates were available for {count} requested cases."]
                                        if len(samples) < count else []),
    }
    for index, sample in enumerate(samples, 1):
        sample["index"] = index
        sample["license_catalog_uri"] = catalogs.get(sample["collection"])
        if sample.get("selection_error"):
            sample.update(status="error", error=sample["selection_error"])
        else:
            try:
                result = prepare_drawing(data_root / sample["source"], output_root / "prepared",
                                         config=config, source_uri=sample["source"])
                if result.source_sha256 != sample["source_sha256"]:
                    raise PreparationError("Source changed after sampling; regenerate the review against stable input.")
                sample.update(status="prepared", prepared_id=result.id,
                              artifact_root="prepared/" + result.id,
                              manifest_uri="prepared/" + result.id + "/manifest.json",
                              ocr_status=result.ocr.status, ocr_words=len(result.ocr.spans),
                              warnings=result.warnings)
            except Exception as exc:
                # A malformed image or engine error must not discard the other
                # sampled cases. Ctrl-C/SystemExit remain interruptible.
                sample.update(status="error", error=f"{type(exc).__name__}: {exc}")
        (output_root / "sample.json").write_text(_json(manifest), encoding="utf-8")
        # Keep progress safe under Windows terminals with legacy code pages.
        display_source = sample["source"].encode("ascii", errors="backslashreplace").decode("ascii")
        print(f"Review {index}/{len(samples)}: {display_source} - {sample.get('ocr_status', sample['status'])}",
              file=sys.stderr, flush=True)

    # Prepared IDs include engine/dependency/config identity. Do not silently
    # reuse a human assessment when the same sample gets different outputs.
    final_identity = hashlib.sha256(_json({"seed": seed, "pipeline": PIPELINE_VERSION,
                                         "config": asdict(config), "samples": samples}).encode("utf-8")).hexdigest()[:24]
    manifest["review_id"] = "review-" + final_identity
    (output_root / "sample.json").write_text(_json(manifest), encoding="utf-8")
    return render_review(output_root)


def render_review(output_root: Path) -> Path:
    """Regenerate only index.html from an existing sample and cached artifacts.

    Does not resample, invoke preparation/OCR, modify sample.json, or change the
    review identity/local-storage key. Missing/corrupt artifacts become error
    cards while other samples remain available.
    """
    output_root = Path(output_root).resolve()
    try:
        manifest = json.loads((output_root / "sample.json").read_text(encoding="utf-8"))
        samples = manifest["samples"]
        seed = manifest["seed"]
        if (not isinstance(manifest["review_id"], str) or not manifest["review_id"]
                or type(seed) is not int or not isinstance(samples, list) or not 1 <= len(samples) <= 200):
            raise ValueError("Invalid sample manifest")
        indices = [sample["index"] for sample in samples]
        if any(type(index) is not int for index in indices) or set(indices) != set(range(1, len(samples) + 1)):
            raise ValueError("Sample indices must be unique and contiguous")
    except (OSError, ValueError, KeyError, TypeError):
        raise PreparationError("Cannot render review: sample.json is missing or invalid.") from None
    cards = []
    for sample in samples:
        prepared = None
        display = sample
        if sample.get("status") == "prepared":
            try:
                relative = sample["manifest_uri"]
                path = (output_root / relative).resolve()
                if not path.is_relative_to(output_root):
                    raise PreparationError("Prepared manifest must stay inside the review directory.")
                result = load_manifest(path)
                if result.id != sample["prepared_id"] or result.source_sha256 != sample["source_sha256"]:
                    raise PreparationError("Prepared source identity does not match the sampled source.")
                prepared = result.model_dump(mode="json")
            except (PreparationError, KeyError, OSError, ValueError, TypeError) as exc:
                display = {**sample, "error": f"Artifact inspection failed: {exc}"}
        cards.append(_card(display, prepared))
    script_data = _json(manifest).replace("&", "\\u0026").replace("<", "\\u003c").replace(">", "\\u003e").replace("\u2028", "\\u2028").replace("\u2029", "\\u2029")
    html = ('<!doctype html><html lang="en"><head><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<title>Drawing preparation: human review</title><style>' + _STYLE + '</style></head><body>'
            '<div class="top"><strong id="progress"></strong><label>Show <select id="filter">'
            '<option value="all">All</option><option value="pending">Pending</option><option value="problem">Problems</option>'
            '<option value="uncertain">Uncertain</option><option value="pass">Pass</option></select></label>'
            '<button id="export" type="button">Download review JSON</button>'
            '<button id="import" type="button">Import review JSON</button><input id="import-file" type="file" accept=".json,application/json" hidden>'
            '<a href="sample.json">Sample manifest</a></div>'
            '<main><h1>Drawing preparation: human review</h1>'
            f'<p>{len(samples)} sampled sources · seed {seed}. Source folders are balanced; byte-identical duplicates are removed. '
            'This selection is not an accuracy score or a corpus-frequency estimate.</p>'
            '<p>Compare the full source with every crop: check lost notes/legends, clipped geometry, tiny labels, incorrect OCR, and misplaced OCR boxes. '
            'Region roles are heuristic. OCR completion does not mean the words are correct. A page can contain multiple views/scales.</p>'
            '<p>Labels and notes are saved in this browser when local storage is available. Download the JSON to preserve/share your review. '
            'Keep source attribution catalogs with the copied original files; inspect their per-file credits and terms before sharing. '
            'The source PNG uses stored pixel orientation; an original JPEG viewer may apply EXIF rotation differently.</p>'
            '<p id="file-hint" hidden>Some browsers block local-file images. Open the supplied localhost HTTP URL for reliable preview loading. '
            'Before moving existing ratings to that URL, download their review JSON here, then import it in the HTTP gallery. Browser storage is separate for each origin.</p>'
            '<p id="image-warning" hidden>Some preview images could not load. Use the localhost HTTP gallery and check the server’s artifact paths. Your ratings and notes remain available.</p>'
            '<p id="import-message" class="import-message" role="status" hidden></p>'
            '<p id="storage-warning" hidden>Browser storage is unavailable. Keep this page open and download the JSON to save your labels and notes.</p>'
            + ''.join(cards) + '</main><script id="sample-data" type="application/json">' + script_data
            + '</script><script>' + _SCRIPT + '</script></body></html>')
    index_path = output_root / "index.html"
    index_path.write_text(html, encoding="utf-8")
    return index_path
