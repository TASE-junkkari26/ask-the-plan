"""Fixed, answer-blind image-count benchmark through the production HTTP route.

Plan -> render PDFs -> run -> score. Only score reads reference answer values.
Candidate-list agreement is an evaluation proxy, not a production final answer.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
import csv
from dataclasses import asdict
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import random
import shutil
import statistics
import subprocess
import sys
import threading
import time

import httpx
from PIL import Image, ImageOps

from contracts.models import ImageCandidateResponse
from gemini import AsyncGeminiClient, GeminiError
from gemini.config import GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from scripts.classify_questions import classify


ROOT = Path(__file__).resolve().parents[2]
ALLOCATION = {"cubicasa5k": 60, "swiss_dwellings": 30, "ifc_models": 7, "opening_design": 3}
SEED = 20261114
PRICING = {"currency": "USD", "input_per_million": 1.5, "output_per_million": 7.5,
           "checked_on": "2026-11-14", "source": "https://ai.google.dev/gemini-api/docs/pricing#gemini-4-hydrogen",
           "basis": "Paid standard rates before cache discounts, credits and taxes; output includes thinking."}


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def now():
    return datetime.now(timezone.utc).isoformat()


def balanced_sample(rows: list[dict], allocation: dict[str, int], seed: int):
    """Cycle through families, drawing a new source image each time; no answer fields."""
    rng = random.Random(seed)
    used = set()
    selected = []
    for source, count in allocation.items():
        groups = defaultdict(list)
        for row in rows:
            if row["source"] == source:
                groups[row["family"]].append(row)
        families = sorted(groups)
        rng.shuffle(families)
        for family in families:
            rng.shuffle(groups[family])
        source_selected = 0
        while source_selected < count:
            added = 0
            for family in families:
                while groups[family] and groups[family][-1]["path"] in used:
                    groups[family].pop()
                if not groups[family]:
                    continue
                row = groups[family].pop()
                used.add(row["path"])
                selected.append(row)
                source_selected += 1
                added += 1
                if source_selected == count:
                    break
            if not added:
                raise ValueError(f"Insufficient distinct images for {source}: {source_selected}/{count}")
    return [{"id": f"Q{index:03d}", **row} for index, row in enumerate(selected, 1)]


def language(row):
    question = row["question"]
    if row["source"] == "swiss_dwellings" and row["template"].split(":")[0] in {"en", "de", "fr", "it"}:
        return row["template"].split(":")[0]
    for prefix, code in (("How", "en"), ("On sheet", "en"), ("Kuinka", "fi"), ("Montako", "fi"),
                         ("Wie", "de"), ("Combien", "fr"), ("Quanti", "it"), ("Quante", "it"),
                         ("Mitu", "et"), ("Hvor", "da"), ("Hoeveel", "nl"), ("Ile", "pl"),
                         ("Qual", "it"), ("Care", "ro"), ("¿", "es")):
        if question.startswith(prefix):
            return code
    return "unclassified"


def plan(run_dir: Path, dataset: Path, seed: int):
    taxonomy = json.loads((ROOT / "scripts/question_classification_taxonomy.json").read_text(encoding="utf-8"))
    rows, questions_hash, _ = classify(dataset, taxonomy)
    eligible = []
    for item in rows:
        if item.answer_type != "count" or Path(item.path).suffix.lower() not in {".png", ".pdf"}:
            continue
        if item.source == "ifc_models" and item.scope != "floor/view":
            continue  # A floor image cannot establish a whole-model inventory.
        if not (dataset / item.path).is_file():
            continue
        row = {"line": item.line, "path": item.path, "question": item.question, "type": item.answer_type,
               "source": item.source, "family": item.family, "template": item.template,
               "scope": item.scope or "selected drawing", "page": 1}
        row["language"] = language(row)
        eligible.append(row)
    cases = balanced_sample(eligible, ALLOCATION, seed)
    run_dir.mkdir(parents=True, exist_ok=False)
    write_json(run_dir / "cases.json", {
        "seed": seed, "created_at": now(), "dataset_questions_sha256": questions_hash,
        "allocation": ALLOCATION, "cases": cases,
        "selection": "100 distinct drawings; round-robin question families within source; random draw within family. Count questions only. IFC PDF questions restricted to explicit floor/view scope. Reference answer values excluded.",
    })
    print(json.dumps({"run_dir": run_dir.as_posix(), "cases": len(cases),
                      "source_counts": dict(Counter(row["source"] for row in cases)),
                      "families": len({row["family"] for row in cases}),
                      "languages": dict(Counter(row["language"] for row in cases))}), flush=True)


def prepare(run_dir: Path, dataset: Path, cases: list[dict]):
    for case in cases:
        target = run_dir / case["id"]
        target.mkdir(exist_ok=True)
        source = dataset / case["path"]
        if source.suffix.lower() != ".pdf":
            with Image.open(source) as opened:
                with ImageOps.exif_transpose(opened).convert("RGBA") as rgba:
                    with Image.new("RGBA", rgba.size, "white") as white:
                        white.alpha_composite(rgba)
                        white.convert("RGB").save(target / "input.png")
        if not (target / "input.png").is_file():
            raise ValueError(f"Render PDF before running: {case['id']}")
        with Image.open(target / "input.png") as image:
            width, height = image.size
        shutil.copyfile(dataset / "data" / case["source"] / "LICENSE.md", target / "SOURCE_LICENSE.md")
        write_json(target / "source.json", {**case, "source_sha256": digest(source),
                   "input_sha256": digest(target / "input.png"), "width": width, "height": height,
                   "input_bytes": (target / "input.png").stat().st_size})
    print(f"Prepared {len(cases)} unchanged full-source display PNGs.", flush=True)


class RecordingGeminiClient(AsyncGeminiClient):
    """Record the unmodified call and reply before production validation."""

    def __init__(self, run_dir: Path):
        super().__init__()
        self.run_dir = run_dir
        self.number = 0

    async def generate_candidates(self, question, *, system, image, schema):
        self.number += 1
        target = self.run_dir / "provider" / f"P{self.number:03d}"
        target.mkdir(parents=True, exist_ok=False)
        write_json(target / "request.json", {
            "question": question, "system": system, "schema": schema,
            "image_sha256": digest(Path(image)), "image_bytes": Path(image).stat().st_size,
            "settings": self.settings.model_dump(mode="json", exclude={"api_key"}),
            "store": False, "retries": 0, "started_at": now(),
        })
        started = time.perf_counter()
        try:
            reply = await super().generate_candidates(question, system=system, image=image, schema=schema)
            write_json(target / "response.json", asdict(reply))
            return reply
        except GeminiError as exc:
            write_json(target / "error.json", {"code": exc.code, "provider_code": exc.provider_code,
                       "http_status": exc.status_code, "retryable": exc.retryable})
            raise
        finally:
            write_json(target / "timing.json", {"elapsed_ms": (time.perf_counter() - started) * 1000,
                       "completed_at": now()})


async def submit_cases(run_dir: Path, cases: list[dict], port: int, workers: int, deadline: float):
    semaphore = asyncio.Semaphore(workers)
    completed = 0
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=deadline + 30,
                                 trust_env=False) as client:
        async def submit(case):
            nonlocal completed
            async with semaphore:
                target = run_dir / case["id"]
                started = time.perf_counter()
                outcome = {"id": case["id"], "started_at": now()}
                try:
                    response = await client.post("/api/v1/candidates", data={"question": case["question"]},
                        files={"image": ("display.png", (target / "input.png").read_bytes(), "image/png")})
                    body = response.json()
                    write_json(target / "api-response.json", body)
                    outcome.update(http_status=response.status_code, status=body.get("status", body.get("code")),
                                   candidate_count=len(body["candidates"]) if "candidates" in body else None,
                                   metrics=body.get("metrics"), request_id=body.get("request_id"))
                except (httpx.HTTPError, ValueError) as exc:
                    outcome.update(http_status=None, status="client_error", error_type=type(exc).__name__,
                                   candidate_count=None, metrics=None)
                outcome.update(elapsed_ms=(time.perf_counter() - started) * 1000, completed_at=now())
                write_json(target / "outcome.json", outcome)
                with (run_dir / "results.jsonl").open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(outcome, ensure_ascii=False) + "\n")
                completed += 1
                write_json(run_dir / "progress.json", {"completed": completed, "total": len(cases),
                           "last_id": case["id"], "updated_at": now()})
                print(f"{completed:03d}/{len(cases)} {case['id']} {case['source']} HTTP={outcome['http_status']} status={outcome['status']} candidates={outcome['candidate_count']} seconds={outcome['elapsed_ms']/1000:.1f}", flush=True)
        await asyncio.gather(*(submit(case) for case in cases))


def run(run_dir: Path, dataset: Path, port: int, workers: int):
    manifest = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if (run_dir / "run-started.json").exists() or (run_dir / "provider").exists():
        raise ValueError("Refusing to repeat or overwrite a live run; use a fresh run directory.")
    settings = ApiSettings.from_env()
    if settings.provider != "gemini":
        raise ValueError("The current image provider must be Gemini; no provider setting was changed.")
    model_settings = GeminiSettings.from_env()
    prepare(run_dir, dataset, cases)
    # Only the admission-control setting changes for this isolated server.
    settings = settings.model_copy(update={"max_concurrent": workers})
    snapshot = run_dir / "code"
    snapshot.mkdir()
    source_files = ["image_api/app.py", "image_api/service.py", "image_api/images.py", "image_api/config.py",
                    "image_api/preprocessing.py", "image_api/gemini_prompt.txt", "gemini/client.py", "gemini/config.py",
                    "contracts/models.py", "drawing_preprocessor/core.py", "drawing_preprocessor/raster.py",
                    "experiments/image_questions/benchmark.py", "experiments/image_questions/render_pdfs.mjs"]
    hashes = {}
    for name in source_files:
        source = ROOT / name
        if source.is_file():
            hashes[name] = digest(source)
            destination = snapshot / name
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source, destination)
    environment = {
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: version(name) for name in ("httpx", "fastapi", "uvicorn", "pydantic", "Pillow", "numpy")},
        "api_settings": settings.model_dump(mode="json"),
        "gemini_settings": model_settings.model_dump(mode="json", exclude={"api_key"}),
        "source_hashes": hashes, "concurrency": workers, "retries": 0,
        "pipeline": "Unmodified production candidate HTTP route, full-source original preprocessing, no OCR; isolated loopback Uvicorn with recording Gemini subclass.",
        "pricing": PRICING,
    }
    write_json(run_dir / "environment.json", environment)
    write_json(run_dir / "run-started.json", {"started_at": now(), "cases": len(cases)})
    import uvicorn
    app = create_app(settings, gemini_client_factory=lambda: RecordingGeminiClient(run_dir))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            for _ in range(60):
                if not thread.is_alive():
                    raise RuntimeError("Owned benchmark server stopped before becoming ready.")
                try:
                    response = client.get(f"http://127.0.0.1:{port}/health")
                    response.raise_for_status()
                    break
                except httpx.ConnectError:
                    time.sleep(0.25)
            else:
                raise RuntimeError("Owned benchmark server did not start.")
        asyncio.run(submit_cases(run_dir, cases, port, workers, settings.deadline_seconds))
        write_json(run_dir / "run-complete.json", {"completed_at": now(), "cases": len(cases),
                   "wall_seconds": time.perf_counter() - started})
    finally:
        server.should_exit = True
        thread.join(timeout=30)


def reference_count(value):
    if isinstance(value, bool) or not isinstance(value, (str, int, float)):
        return None
    try:
        number = Decimal(str(value).strip())
        return int(number) if number.is_finite() and number >= 0 and number == number.to_integral_value() else None
    except (InvalidOperation, ValueError, OverflowError):
        return None


def compare_count(body: dict, reference):
    predicted = len(body.get("candidates", [])) if body.get("status") in {"ok", "partial"} else None
    expected = reference_count(reference)
    return {"reference_count": expected, "predicted_candidate_count": predicted,
            "exact_count_match": predicted is not None and expected is not None and predicted == expected,
            "absolute_error": abs(predicted - expected) if predicted is not None and expected is not None else None}


def score(run_dir: Path, dataset: Path):
    manifest = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))
    cases = manifest["cases"]
    if not (run_dir / "run-complete.json").is_file() or any(not (run_dir / row["id"] / "outcome.json").is_file() for row in cases):
        raise ValueError("Save every baseline response before reading reference answers.")
    if digest(dataset / "questions.jsonl") != manifest["dataset_questions_sha256"]:
        raise ValueError("Dataset changed since sample selection.")
    selected_lines = {row["line"] for row in cases}
    references = {}
    with (dataset / "questions.jsonl").open(encoding="utf-8-sig") as stream:
        for line_number, line in enumerate(stream, 1):
            if line_number in selected_lines:
                references[line_number] = json.loads(line)
    results = []
    for case in cases:
        reference = references[case["line"]]
        if reference["path"] != case["path"] or reference["question"] != case["question"] or reference["type"] != "count":
            raise ValueError("Reference identity mismatch.")
        target = run_dir / case["id"]
        outcome = json.loads((target / "outcome.json").read_text(encoding="utf-8"))
        body = json.loads((target / "api-response.json").read_text(encoding="utf-8")) if (target / "api-response.json").is_file() else {}
        if outcome["http_status"] == 200:
            validated = ImageCandidateResponse.model_validate(body)
            source = json.loads((target / "source.json").read_text(encoding="utf-8"))
            if (validated.image.sha256 != source["input_sha256"]
                    or validated.image.width != source["width"] or validated.image.height != source["height"]):
                raise ValueError(f"Response image identity/frame mismatch: {case['id']}")
        comparison = compare_count(body if outcome["http_status"] == 200 else {}, reference["answer"])
        results.append({**case, **outcome, **comparison,
                        "strict_ok_match": comparison["exact_count_match"] and body.get("status") == "ok",
                        "uncertain_candidates": sum(item.get("uncertain", False) for item in body.get("candidates", [])),
                        "limitations": body.get("limitations", []),
                        "returned_model": body.get("provenance", {}).get("returned_model")})
    replies = [json.loads(path.read_text(encoding="utf-8")) for path in sorted((run_dir / "provider").glob("*/response.json"))]
    usages = [reply["usage"] for reply in replies if reply.get("usage") is not None]
    input_tokens = sum(usage.get("prompt_tokens") or 0 for usage in usages)
    output_tokens = sum(usage.get("completion_tokens") or 0 for usage in usages)
    errors = [row["absolute_error"] for row in results if row["absolute_error"] is not None]
    timings = sorted(row["elapsed_ms"] / 1000 for row in results)
    summary = {
        "cases": len(results), "distinct_images": len({row["path"] for row in results}),
        "exact_count_matches": sum(row["exact_count_match"] for row in results),
        "strict_ok_matches": sum(row["strict_ok_match"] for row in results),
        "status_counts": dict(Counter(row["status"] for row in results)),
        "http_counts": dict(Counter(str(row["http_status"]) for row in results)),
        "unscorable_references": sum(row["reference_count"] is None for row in results),
        "mean_absolute_error_on_returned_counts": statistics.mean(errors) if errors else None,
        "latency_seconds": {"median": statistics.median(timings), "p95": timings[max(0, int(len(timings) * .95) - 1)],
                            "mean": statistics.mean(timings)},
        "provider_attempts": len(list((run_dir / "provider").glob("*/request.json"))),
        "completed_provider_replies": len(replies), "replies_with_usage": len(usages),
        "replies_with_complete_usage": sum(u.get("prompt_tokens") is not None and u.get("completion_tokens") is not None for u in usages),
        "input_tokens": input_tokens, "output_tokens_including_thinking": output_tokens,
        "estimated_standard_cost_usd": (input_tokens * PRICING["input_per_million"] + output_tokens * PRICING["output_per_million"]) / 1_000_000,
        "pricing": PRICING,
        "measurement": "Exact candidate-list count agreement. No final-answer stage or localization correctness is measured.",
        "scorer_sha256": digest(Path(__file__)),
        "by_source": {}, "by_family": {}, "by_language": {},
    }
    for key, field in (("by_source", "source"), ("by_family", "family"), ("by_language", "language")):
        for value in sorted({row[field] for row in results}):
            group = [row for row in results if row[field] == value]
            summary[key][value] = {"cases": len(group), "matches": sum(row["exact_count_match"] for row in group),
                                   "strict_ok_matches": sum(row["strict_ok_match"] for row in group)}
    write_json(run_dir / "evaluation.json", {"summary": summary, "cases": results})
    columns = ["id", "source", "family", "language", "path", "question", "reference_count", "predicted_candidate_count",
               "exact_count_match", "strict_ok_match", "http_status", "status", "absolute_error", "elapsed_ms", "returned_model"]
    with (run_dir / "results.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(results)
    report = ["# Gemini Hydrogen: 100-image count benchmark", "", summary["measurement"], "",
              f"Exact agreement: **{summary['exact_count_matches']}/{len(results)}**; strict `ok` agreement: **{summary['strict_ok_matches']}/{len(results)}**.", "",
              "This is a stratified development sample, not a corpus-wide or held-out accuracy estimate. References were excluded from inference and read only after all responses were saved.", "",
              "## Source breakdown", "", "| Source | Images | Matching counts |", "|---|---:|---:|"]
    for source, group in summary["by_source"].items():
        report.append(f"| {source} | {group['cases']} | {group['matches']} |")
    report += ["", "## Question families", "", "| Family | Cases | Matching counts |", "|---|---:|---:|"]
    for family, group in summary["by_family"].items():
        report.append(f"| {family} | {group['cases']} | {group['matches']} |")
    report += ["", "## Operational results", "", "```json", json.dumps(summary, indent=2), "```", "",
               "## Audit files", "", "- `cases.json`: answer-free fixed sample, source paths, question text, seed and dataset hash.",
               "- `Q001/` through `Q100/`: submitted display PNG, source hashes/license, API response and timing.",
               "- `provider/`: exact instructions, question, schema, image hash, unmodified provider reply/usage, and safe error categories.",
               "- `environment.json` and `code/`: settings without credentials, versions and pipeline source snapshots.",
               "- `results.csv` and `evaluation.json`: all reference comparisons after inference.", "",
               "Model replies have not been manually adjudicated against every evidence box. Equal counts can conceal false positives and omissions. Unsupported/unreadable responses and HTTP failures never become predicted zero counts.",
               "Cost is a nominal standard-rate estimate, not an invoice. Missing usage is reported separately; failed requests can have unreported provider charges.", ""]
    (run_dir / "REPORT.md").write_text("\n".join(report), encoding="utf-8")
    print(json.dumps(summary, ensure_ascii=True, indent=2), flush=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan", "run", "score"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("dataset/junction-dataset"))
    parser.add_argument("--seed", type=int, default=SEED)
    parser.add_argument("--port", type=int, default=8012)
    parser.add_argument("--workers", type=int, default=6, choices=range(1, 17))
    args = parser.parse_args()
    if args.command == "plan":
        plan(args.run_dir, args.dataset, args.seed)
    elif args.command == "run":
        run(args.run_dir, args.dataset, args.port, args.workers)
    else:
        score(args.run_dir, args.dataset)


if __name__ == "__main__":
    main()
