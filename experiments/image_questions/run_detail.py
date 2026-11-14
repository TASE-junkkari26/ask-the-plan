"""Run the callable production detail tools on an authorized local image."""
import argparse
import asyncio
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import shutil

from PIL import Image, ImageDraw
from gemini import AsyncGeminiClient
from image_api.config import ApiSettings
from image_api.detail import DetailOptions, DetailTools
from image_api.images import prepare_image
from image_api.service import CandidateService, GeminiCandidateProvider


def save(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")


class RecordingClient(AsyncGeminiClient):
    def __init__(self, directory):
        super().__init__()
        self.directory, self.calls = directory, 0

    async def generate_candidates(self, question, *, system, image, schema, resolution=None):
        self.calls += 1
        folder = self.directory / f"call-{self.calls:02d}"
        folder.mkdir()
        shutil.copyfile(image, folder / "input.png")
        save(folder / "request.json", {"question": question, "system": system, "schema": schema, "resolution": resolution,
             "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
             "model": self.settings.model, "thinking": self.settings.thinking_level})
        reply = await super().generate_candidates(question, system=system, image=image, schema=schema, resolution=resolution)
        save(folder / "reply.json", asdict(reply))
        return reply


async def main(args):
    output = args.output
    output.mkdir(parents=True, exist_ok=False)
    image = prepare_image(args.source.read_bytes(), ApiSettings(provider="gemini"), output)
    options = DetailOptions(mode=args.mode, regions=json.loads(args.regions) if args.regions else [])
    save(output / "config.json", {"source_sha256": image.sha256, "question": args.question,
                                  "options": options.model_dump(),
                                  "code_hashes": {str(p): hashlib.sha256(p.read_bytes()).hexdigest()
                                   for p in Path('image_api').glob('*.py')}})
    async with RecordingClient(output) as client:
        service = CandidateService(None, ApiSettings(provider="gemini"), provider=GeminiCandidateProvider(client))
        result = await DetailTools(service, client).extract(image, args.question, "detail-experiment", output, options)
    body = result.model_dump(mode="json")
    save(output / "response.json", body)
    with Image.open(image.path) as source:
        draw = ImageDraw.Draw(source)
        for region in result.detail.selected_regions:
            draw.rectangle(region, outline='#ee8800', width=8)
        for index, candidate in enumerate(result.candidates, 1):
            a, b = candidate.geometry.minimum
            c, d = candidate.geometry.maximum
            draw.rectangle((a,b,c,d), outline='#137d70' if not candidate.uncertain else '#b46500', width=5)
            draw.text((a,b), str(index), fill='#005044', font_size=26)
        source.thumbnail((1800,1400))
        source.save(output / "overlay.png")
    print(json.dumps({"status": result.status, "candidates": len(result.candidates),
          "detail": body['detail'], "metrics": body['metrics'], "limitations": body['limitations']}, indent=2))


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--question', default='show doors')
    parser.add_argument('--mode', choices=['auto','regions','tiles'], default='auto')
    parser.add_argument('--regions', help='Explicit source-pixel boxes as a JSON array')
    parser.add_argument('--run', action='store_true')
    args = parser.parse_args()
    if not args.run:
        parser.error('Pass --run to authorize the specified paid inference calls')
    asyncio.run(main(args))
