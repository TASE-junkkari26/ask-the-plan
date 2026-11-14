"""Opt-in, local image/crop ablation using the production candidate provider.

The JSON spec supplies source-pixel crops and optional manually reviewed boxes.
References never enter the model request. This bypasses HTTP/browser code, keeps
the production prompt/normalization, and records each single inference attempt.
No production configuration is changed. Outputs contain the submitted drawing;
keep private runs under experiments/runs (ignored by Git).
"""
from __future__ import annotations

import argparse
import asyncio
import base64
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import re
import time

import httpx
from PIL import Image

from gemini import AsyncGeminiClient, GeminiSettings
from image_api.config import ApiSettings
from image_api.errors import ApiError
from image_api.images import prepare_image
from image_api.service import CandidateService, GeminiCandidateProvider


def save(path, value):
    Path(path).write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class DiagnosticTransport(httpx.AsyncBaseTransport):
    def __init__(self, directory, resolution):
        self.directory, self.resolution = directory, resolution
        self.inner = httpx.AsyncHTTPTransport(retries=0)

    async def handle_async_request(self, request):
        body = json.loads(request.content)
        if self.resolution:
            body["input"][1]["resolution"] = self.resolution
        encoded = json.dumps(body, ensure_ascii=False, separators=(",", ":")).encode()
        # Preserve exact prompt/schema/settings, without credentials or base64.
        image_part = body["input"][1]
        image_part["sha256"] = hashlib.sha256(base64.b64decode(image_part.pop("data"))).hexdigest()
        save(self.directory / "request.json", body)
        headers = dict(request.headers)
        headers.pop("content-length", None)
        return await self.inner.handle_async_request(httpx.Request(
            request.method, request.url, content=encoded, headers=headers,
            extensions=request.extensions))

    async def aclose(self):
        await self.inner.aclose()


class RecordingClient(AsyncGeminiClient):
    def __init__(self, directory, resolution):
        self.directory = directory
        super().__init__(GeminiSettings.from_env(), transport=DiagnosticTransport(directory, resolution))

    async def generate_candidates(self, *args, **kwargs):
        result = await super().generate_candidates(*args, **kwargs)
        save(self.directory / "provider-reply.json", asdict(result))
        return result


async def run_case(source, case, directory, question):
    directory.mkdir(parents=True, exist_ok=False)
    x0, y0, x1, y1 = case["crop"]
    if not (0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height):
        raise ValueError("Crop must lie within the upright source image")
    source.crop(case["crop"]).save(directory / "input.png")
    settings = ApiSettings(provider="gemini", preprocess_mode="off")
    prepared = prepare_image((directory / "input.png").read_bytes(), settings, directory)
    save(directory / "source.json", {"crop": case["crop"], "width": prepared.width,
         "height": prepared.height, "inference_sha256": prepared.inference_sha256,
         "pixel_transform": {"scale": [1, 1], "translation": [x0, y0]}})
    started = time.perf_counter()
    try:
        async with RecordingClient(directory, case.get("resolution")) as client:
            response = await CandidateService(None, settings, provider=GeminiCandidateProvider(client)).extract(
                prepared, question, case["id"])
        body = response.model_dump(mode="json")
        save(directory / "response.json", body)
        mapped = []
        for candidate in body["candidates"]:
            a, b = candidate["geometry"]["minimum"]
            c, d = candidate["geometry"]["maximum"]
            mapped.append({**candidate, "source_box": [a+x0, b+y0, c+x0, d+y0]})
        save(directory / "mapped-candidates.json", mapped)
        summary = {"id": case["id"], "status": body["status"], "candidates": len(mapped),
                   "seconds": time.perf_counter()-started, "metrics": body["metrics"],
                   "uncertain": sum(c["uncertain"] for c in mapped)}
    except ApiError as exc:
        summary = {"id": case["id"], "error": exc.code, "http_status": exc.status_code,
                   "seconds": time.perf_counter()-started}
    save(directory / "outcome.json", summary)
    print(json.dumps(summary), flush=True)
    return summary


async def main(args):
    spec = json.loads(args.spec.read_text(encoding="utf-8"))
    cases = spec.get("cases", [])
    if not isinstance(spec.get("question"), str) or not spec["question"].strip():
        raise ValueError("A nonblank question is required")
    if not isinstance(cases, list) or not 1 <= len(cases) <= 32:
        raise ValueError("Supply between 1 and 32 cases")
    ids = set()
    for case in cases:
        case_id = case.get("id", "")
        if not isinstance(case_id, str) or not re.fullmatch(r"[a-z0-9][a-z0-9_-]{0,79}", case_id) or case_id in ids:
            raise ValueError("Case IDs must be unique, simple lowercase directory names")
        ids.add(case_id)
        crop = case.get("crop")
        if not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop):
            raise ValueError("Crops must contain four integer source-pixel coordinates")
        if case.get("resolution") not in {None, "low", "medium", "high", "ultra_high"}:
            raise ValueError("Unsupported diagnostic image resolution")
    args.output.mkdir(parents=True, exist_ok=False)
    save(args.output / "spec.json", spec)
    save(args.output / "environment.json", {
        "source_filename": args.source.name,
        "source_sha256": hashlib.sha256(args.source.read_bytes()).hexdigest(),
        "runner_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "method": "Production preparation/provider/service, without HTTP/browser or artifact cache. Manual crops; original pixels.",
        "case_order": [c["id"] for c in spec["cases"]],
        "production_hashes": {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in (
            "gemini/client.py", "image_api/service.py", "image_api/gemini_prompt.txt", "image_api/images.py")}})
    semaphore = asyncio.Semaphore(2)
    canonical_dir = args.output / "canonical-source"
    canonical_dir.mkdir()
    prepared = prepare_image(args.source.read_bytes(), ApiSettings(provider="gemini"), canonical_dir)
    with Image.open(prepared.path) as source:
        # Validate every crop before making any paid inference requests.
        for case in cases:
            x0, y0, x1, y1 = case["crop"]
            if not (0 <= x0 < x1 <= source.width and 0 <= y0 < y1 <= source.height):
                raise ValueError("Crop must lie within the upright source image")
        async def one(case):
            async with semaphore:
                return await run_case(source, case, args.output/case["id"], spec["question"])
        results = await asyncio.gather(*(one(case) for case in cases))
    save(args.output / "summary.json", results)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--spec", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--run", action="store_true", help="Explicitly allow paid inference calls")
    args = parser.parse_args()
    if not args.run:
        parser.error("Pass --run to perform the specified inference attempts")
    asyncio.run(main(args))
