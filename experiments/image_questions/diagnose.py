"""Six bounded, post-baseline diagnostics; not held-out accuracy measurements."""
from __future__ import annotations

import argparse
import asyncio
import json
from pathlib import Path
import shutil
from tempfile import TemporaryDirectory
import time

from PIL import Image

from image_api.config import ApiSettings
from image_api.preprocessing import ImagePreprocessor
from image_api.service import CandidateService
from nemotron import completion_text
from .run import RecordingClient, digest, write_json


DIRECT_SYSTEM = """Answer the user's construction drawing question using only the attached image.
Preserve literal identifiers and units. Count logical instances according to the question,
not strokes or symbols in a legend. Do not invent unreadable text or dimensions.
If the source cannot support an answer, say insufficient_evidence.
Return only a JSON object with status (answered or insufficient_evidence), answer
(number, string, or null), unit (string or null), observations (a list of short,
specific visible evidence statements), and limitations (a list of strings).
Do not give hidden reasoning; observations should describe only visible evidence."""

DIAGNOSTICS = [
    ("D01", "Q02", "direct", None, 1),
    ("D02", "Q03", "direct", None, 1),
    ("D03", "Q03", "candidate", (210, 165, 335, 275), 4),
    ("D04", "Q07", "candidate", (140, 110, 1030, 740), 1),
    ("D05", "Q08", "direct", None, 1),
    ("D06", "Q08", "direct", (140, 110, 1030, 740), 1),
]


async def run(base: Path):
    cases = {c["id"]: c for c in json.loads((base / "cases.json").read_text(encoding="utf-8"))["cases"]}
    root = base / "diagnostics"
    root.mkdir(exist_ok=False)
    settings = ApiSettings.from_env()
    results = []
    for name, question_id, mode, box, scale in DIAGNOSTICS:
        target = root / name
        target.mkdir()
        source = base / question_id / "input.png"
        with Image.open(source) as opened:
            selected = opened.crop(box) if box else opened.copy()
            if scale != 1:
                selected = selected.resize((selected.width * scale, selected.height * scale), Image.Resampling.LANCZOS)
            selected.save(target / "input.png")
        shutil.copyfile(base / question_id / "SOURCE_LICENSE.md", target / "SOURCE_LICENSE.md")
        write_json(target / "method.json", {
            "question_id": question_id, "mode": mode, "question": cases[question_id]["question"],
            "source_sha256": digest(source), "crop_pixels": box, "scale": scale,
            "input_sha256": digest(target / "input.png"),
            "crop_selection": "Manually chosen after baseline failure; exploratory, not an automated crop selector.",
        })
        client = RecordingClient(target)
        started = time.perf_counter()
        print(f"Submitting {name}: {mode}, {question_id}, crop={box}", flush=True)
        try:
            if mode == "direct":
                reply = await client.ask(cases[question_id]["question"], system=DIRECT_SYSTEM,
                    images=[target / "input.png"], max_tokens=2048, response_format={"type": "json_object"})
                result = json.loads(completion_text(reply))
                write_json(target / "answer.json", result)
            else:
                preprocessor = ImagePreprocessor(settings)
                try:
                    with TemporaryDirectory(prefix="image-evaluation-") as tmp:
                        prepared = preprocessor.prepare((target / "input.png").read_bytes(), Path(tmp))
                        reply = await CandidateService(client, settings).extract(prepared, cases[question_id]["question"], name)
                        result = reply.model_dump(mode="json")
                        write_json(target / "api-response.json", result)
                finally:
                    preprocessor.close()
            summary = {"id": name, "question_id": question_id, "mode": mode,
                       "elapsed_seconds": time.perf_counter() - started, "status": result["status"],
                       "answer": result.get("answer"),
                       "candidate_count": len(result["candidates"]) if "candidates" in result else None}
            results.append(summary)
            write_json(root / "results.json", results)
            print(json.dumps(summary), flush=True)
        finally:
            await client.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_dir", type=Path)
    args = parser.parse_args()
    asyncio.run(run(args.run_dir))
