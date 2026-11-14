"""Small live evaluation of the unchanged production candidate HTTP route.

Inputs contain questions, never answers. Provider responses are recorded before
API parsing so transport/schema failures remain distinguishable from visual errors.
The recording subclass changes no request parameters or production logic.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import platform
import shutil
import subprocess
import sys
import threading
import time

import httpx
from PIL import Image, ImageOps

from image_api.app import create_app
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, NemotronError, NemotronSettings


def write_json(path: Path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


def digest(path: Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def experiment_settings() -> ApiSettings:
    # This experiment records a Nemotron baseline, independently of the UI choice.
    return ApiSettings.from_env().model_copy(update={"provider": "nemotron"})


def recording_app(run_dir: Path):
    return create_app(experiment_settings(), client_factory=lambda: RecordingClient(run_dir))


class RecordingClient(AsyncNemotronClient):
    def __init__(self, run_dir: Path):
        super().__init__(NemotronSettings.from_env().model_copy(update={"max_retries": 0}))
        self.run_dir = run_dir
        self.number = 0

    async def ask(self, prompt, *, system=None, images=(), **options):
        self.number += 1
        target = self.run_dir / "provider" / f"{self.number:02}"
        target.mkdir(parents=True, exist_ok=False)
        write_json(target / "request.json", {
            "question": prompt, "system": system, "options": options,
            "images": [{"sha256": digest(Path(p)), "bytes": Path(p).stat().st_size} for p in images],
        })
        started = time.perf_counter()
        try:
            response = await super().ask(prompt, system=system, images=images, **options)
            write_json(target / "response.json", response.model_dump(mode="json"))
            return response
        except NemotronError as exc:
            write_json(target / "error.json", {"message": str(exc),
                       "status_code": exc.status_code, "retryable": exc.retryable})
            raise
        finally:
            write_json(target / "timing.json", {"elapsed_seconds": time.perf_counter() - started})


def prepare(run_dir: Path, dataset: Path):
    cases = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))["cases"]
    for item in cases:
        target = run_dir / item["id"]
        target.mkdir(parents=True, exist_ok=True)
        source = dataset / item["path"]
        if source.suffix.lower() != ".pdf":
            with Image.open(source) as opened:
                rgba = ImageOps.exif_transpose(opened).convert("RGBA")
                white = Image.new("RGBA", rgba.size, "white")
                white.alpha_composite(rgba)
                white.convert("RGB").save(target / "input.png")
        with Image.open(target / "input.png") as image:
            size = image.size
        shutil.copyfile(dataset / "data" / Path(item["path"]).parts[1] / "LICENSE.md", target / "SOURCE_LICENSE.md")
        write_json(target / "source.json", {
            **item, "source_sha256": digest(source), "input_sha256": digest(target / "input.png"),
            "width": size[0], "height": size[1],
        })
    settings = NemotronSettings.from_env()
    write_json(run_dir / "environment.json", {
        "git_revision": subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip(),
        "python": sys.version, "platform": platform.platform(),
        "api_settings": experiment_settings().model_dump(mode="json"),
        "model_settings": settings.model_dump(mode="json", exclude={"api_key"}),
        "effective_retries": 0, "concurrency": 1,
        "production_prompt_sha256": digest(Path("image_api/prompt.txt")),
        "runner_sha256": digest(Path(__file__)),
        "transport": "Real loopback HTTP to uvicorn, real Verda provider; recording client only",
    })


def evaluate(run_dir: Path, dataset: Path, port: int):
    # Refuse reuse rather than accidentally overwrite or resubmit an existing run.
    if (run_dir / "provider").exists():
        raise SystemExit("Provider artifacts already exist; use a fresh run directory.")
    prepare(run_dir, dataset)
    cases = json.loads((run_dir / "cases.json").read_text(encoding="utf-8"))["cases"]
    import uvicorn
    app = recording_app(run_dir)
    server = uvicorn.Server(uvicorn.Config(app, host="127.0.0.1", port=port, log_level="warning"))
    thread = threading.Thread(target=server.run, daemon=True)
    thread.start()
    try:
        try:
            with httpx.Client(base_url=f"http://127.0.0.1:{port}", timeout=195, trust_env=False) as client:
                for _ in range(60):
                    if not thread.is_alive():
                        raise RuntimeError("Owned API server stopped")
                    try:
                        health = client.get("/health")
                        health.raise_for_status()
                        break
                    except httpx.ConnectError:
                        time.sleep(0.25)
                else:
                    raise RuntimeError("Owned API did not start")
                results = []
                for item in cases:
                    target = run_dir / item["id"]
                    started = time.perf_counter()
                    print(f"Submitting {item['id']}: {item['question']}", flush=True)
                    response = client.post("/api/v1/candidates", data={"question": item["question"]},
                        files={"image": ("display.png", (target / "input.png").read_bytes(), "image/png")})
                    body = response.json()
                    write_json(target / "api-response.json", body)
                    result = {"id": item["id"], "http_status": response.status_code,
                              "elapsed_seconds": time.perf_counter() - started,
                              "status": body.get("status", body.get("code")),
                              "candidate_count": len(body.get("candidates", [])),
                              "metrics": body.get("metrics")}
                    results.append(result)
                    write_json(run_dir / "results.json", results)
                    print(json.dumps(result), flush=True)
                    if response.status_code in {401, 403, 503}:
                        raise RuntimeError("Provider unavailable; stopping live sample")
        finally:
            server.should_exit = True
    finally:
        server.should_exit = True
        thread.join(timeout=30)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=["serve", "run"])
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--dataset", type=Path, default=Path("dataset/junction-dataset"))
    parser.add_argument("--port", type=int, default=8011)
    args = parser.parse_args()
    if args.command == "serve":
        import uvicorn
        app = recording_app(args.run_dir)
        uvicorn.run(app, host="127.0.0.1", port=args.port, log_level="warning")
    else:
        evaluate(args.run_dir, args.dataset, args.port)


if __name__ == "__main__":
    main()
