"""Exact-input, serial Detailed scan rerun of a saved candidate benchmark.

Copy the answer-free baseline manifest and prepared PNGs, run, then score.
All case requests and all provider calls are serialized. No retries or fallback.
"""
from __future__ import annotations

import argparse
import asyncio
from dataclasses import asdict
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time

import httpx

from gemini import AsyncGeminiClient, GeminiError
from gemini.config import GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.detail import DetailOptions
from .benchmark import ROOT, PRICING, digest, now, score, write_json


OPTIONS = {"mode": "tiles", "max_calls": 9}


def protected_files(baseline):
    names = ["cases.json", "evaluation.json", "results.csv", "REPORT.md"]
    manifest = json.loads((baseline / "cases.json").read_text(encoding="utf-8"))
    for case in manifest["cases"]:
        names.extend(f"{case['id']}/{name}" for name in (
            "input.png", "source.json", "api-response.json", "outcome.json"))
    return {name: digest(baseline / name) for name in names}


def plan(baseline: Path, run_dir: Path):
    manifest = json.loads((baseline / "cases.json").read_text(encoding="utf-8"))
    if not (baseline / "run-complete.json").is_file() or len(manifest["cases"]) != 100:
        raise ValueError("The saved baseline must contain a completed 100-case run")
    run_dir.mkdir(parents=True, exist_ok=False)
    shutil.copyfile(baseline / "cases.json", run_dir / "cases.json")
    for case in manifest["cases"]:
        target = run_dir / case["id"]
        target.mkdir()
        for name in ("input.png", "source.json", "SOURCE_LICENSE.md"):
            shutil.copyfile(baseline / case["id"] / name, target / name)
        source = json.loads((target / "source.json").read_text(encoding="utf-8"))
        if digest(target / "input.png") != source["input_sha256"]:
            raise ValueError("Saved baseline image does not match its recorded hash")
    write_json(run_dir / "comparison-plan.json", {
        "baseline": baseline.resolve().as_posix(), "baseline_hashes": protected_files(baseline),
        "options": OPTIONS, "case_concurrency": 1, "provider_concurrency": 1,
        "created_at": now(), "selection": "Exact copied baseline cases/questions/display PNG bytes; no resampling or rerendering."})
    print(f"Copied the exact 100 cases and input PNG bytes into {run_dir}.", flush=True)


class SerialRecorder(AsyncGeminiClient):
    def __init__(self, run_dir, context):
        super().__init__()
        self.run_dir, self.context = run_dir, context
        self.number = 0
        self.serial = asyncio.Semaphore(1)

    async def generate_candidates(self, question, *, system, image, schema):
        async with self.serial:
            self.number += 1
            target = self.run_dir / "provider" / f"P{self.number:04d}"
            target.mkdir(parents=True, exist_ok=False)
            shutil.copyfile(image, target / "input.png")
            write_json(target / "request.json", {
                "case_id": self.context["case_id"], "question": question, "system": system,
                "schema": schema, "image_sha256": digest(image),
                "image_bytes": image.stat().st_size, "started_at": now(),
                "settings": self.settings.model_dump(mode="json", exclude={"api_key"}),
                "store": False, "retries": 0})
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
                write_json(target / "timing.json", {"elapsed_ms": (time.perf_counter()-started)*1000,
                    "completed_at": now()})


async def submit(run_dir, cases, port, deadline, context):
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}", timeout=deadline+30, trust_env=False) as client:
        for number, case in enumerate(cases, 1):
            context["case_id"] = case["id"]
            target = run_dir / case["id"]
            started = time.perf_counter()
            outcome = {"id": case["id"], "started_at": now()}
            try:
                response = await client.post("/api/v1/tools/detect-detail",
                    data={"question": case["question"], "options": json.dumps(OPTIONS)},
                    files={"image": ("display.png", (target/"input.png").read_bytes(), "image/png")})
                body = response.json()
                write_json(target / "api-response.json", body)
                outcome.update(http_status=response.status_code, status=body.get("status", body.get("code")),
                    candidate_count=len(body["candidates"]) if "candidates" in body else None,
                    metrics=body.get("metrics"), request_id=body.get("request_id"),
                    provider_calls=body.get("detail", {}).get("provider_calls"),
                    deferred_observations=len(body.get("detail", {}).get("deferred_observations", [])))
            except (httpx.HTTPError, ValueError) as exc:
                outcome.update(http_status=None, status="client_error", error_type=type(exc).__name__,
                    candidate_count=None, metrics=None)
            outcome.update(elapsed_ms=(time.perf_counter()-started)*1000, completed_at=now())
            write_json(target / "outcome.json", outcome)
            with (run_dir/"results.jsonl").open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(outcome, ensure_ascii=False)+"\n")
            write_json(run_dir/"progress.json", {"completed": number, "total": len(cases),
                "last_id": case["id"], "updated_at": now()})
            print(f"{number:03d}/{len(cases)} {case['id']} {case['source']} HTTP={outcome['http_status']} "
                  f"status={outcome['status']} candidates={outcome['candidate_count']} "
                  f"calls={outcome.get('provider_calls')} seconds={outcome['elapsed_ms']/1000:.1f}", flush=True)


def run(run_dir, dataset, port):
    if (run_dir/"run-started.json").exists() or (run_dir/"provider").exists():
        raise ValueError("Refusing to repeat/overwrite a started run")
    plan_data = json.loads((run_dir/"comparison-plan.json").read_text(encoding="utf-8"))
    manifest = json.loads((run_dir/"cases.json").read_text(encoding="utf-8"))
    baseline = Path(plan_data["baseline"])
    if protected_files(baseline) != plan_data["baseline_hashes"]:
        raise ValueError("Baseline changed after planning")
    if digest(dataset/"questions.jsonl") != manifest["dataset_questions_sha256"]:
        raise ValueError("Reference dataset differs from the baseline dataset")
    for case in manifest["cases"]:
        source = json.loads((run_dir/case["id"]/"source.json").read_text(encoding="utf-8"))
        if digest(run_dir/case["id"]/"input.png") != source["input_sha256"]:
            raise ValueError("Input bytes changed after planning")
    settings = ApiSettings.from_env()
    if settings.provider != "gemini":
        raise ValueError("Current image provider must be Gemini")
    settings = settings.model_copy(update={"max_concurrent": 1})
    DetailOptions.model_validate(OPTIONS)
    source_files = [*Path("image_api").glob("*.py"), *Path("image_api").glob("*.txt"),
        *Path("gemini").glob("*.py"), Path("contracts/models.py"),
        Path("experiments/image_questions/benchmark_detail.py"), Path("experiments/image_questions/benchmark.py")]
    hashes = {}
    for path in source_files:
        target = run_dir/"code"/path
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, target)
        hashes[path.as_posix()] = digest(path)
    write_json(run_dir/"environment.json", {
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT, text=True).strip(),
        "python": sys.version, "platform": platform.platform(),
        "packages": {name: version(name) for name in ("httpx","fastapi","uvicorn","pydantic","Pillow","numpy")},
        "api_settings": settings.model_dump(mode="json"),
        "gemini_settings": GeminiSettings.from_env().model_dump(mode="json", exclude={"api_key"}),
        "source_hashes": hashes, "options": OPTIONS, "concurrency": 1, "provider_concurrency": 1,
        "retries": 0, "pricing": PRICING,
        "pipeline": "Current Detailed scan HTTP tool; exact baseline input bytes; one case and one provider call at a time. Recording/serialization wrapper only; no model/prompt/crop/reconciliation changes."})
    write_json(run_dir/"run-started.json", {"started_at": now(), "cases": len(manifest["cases"])})
    import uvicorn
    context = {"case_id": None}
    app = create_app(settings, gemini_client_factory=lambda: SerialRecorder(run_dir, context))
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    started = time.perf_counter()
    try:
        with httpx.Client(timeout=5, trust_env=False) as client:
            for _ in range(60):
                if not thread.is_alive():
                    raise RuntimeError("Owned benchmark server stopped")
                try:
                    client.get(f"http://127.0.0.1:{port}/health").raise_for_status()
                    break
                except httpx.ConnectError:
                    time.sleep(.25)
            else:
                raise RuntimeError("Owned benchmark server did not start")
        asyncio.run(submit(run_dir, manifest["cases"], port, settings.deadline_seconds, context))
        if protected_files(baseline) != plan_data["baseline_hashes"]:
            raise ValueError("Protected baseline files changed during the rerun")
        write_json(run_dir/"run-complete.json", {"completed_at": now(), "cases": len(manifest["cases"]),
            "wall_seconds": time.perf_counter()-started, "baseline_unchanged": True})
    finally:
        server.should_exit = True
        thread.join(timeout=30)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["plan","run","score"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--baseline", type=Path)
    parser.add_argument("--dataset", type=Path, default=ROOT/"dataset/junction-dataset")
    parser.add_argument("--port", type=int, default=8014)
    args = parser.parse_args()
    if args.command == "plan":
        if not args.baseline:
            parser.error("plan requires --baseline")
        plan(args.baseline, args.run_dir)
    elif args.command == "run":
        run(args.run_dir, args.dataset, args.port)
    else:
        score(args.run_dir, args.dataset)
