"""Prepare raster sources and inspect regions without an API or model key."""
import argparse
import json
from pathlib import Path

from .core import PreparationError, PreprocessConfig, inspect_region, prepare_drawing
from .tools import inspection_tool_spec


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare", help="Create/cache a prepared raster artifact directory.")
    prepare.add_argument("source", type=Path)
    prepare.add_argument("--output", type=Path, default=Path("build/prepared"))
    prepare.add_argument("--source-uri")
    prepare.add_argument("--overview-long-edge", type=int, default=1600)
    prepare.add_argument("--analysis-long-edge", type=int, default=1200)
    prepare.add_argument("--padding", type=int, default=12)
    prepare.add_argument("--ocr", choices=["none", "tesseract"], default="none")
    prepare.add_argument("--ocr-languages", default="eng")
    prepare.add_argument("--ocr-timeout", type=float, default=30)
    prepare.add_argument("--max-source-pixels", type=int, default=50_000_000)
    crop = commands.add_parser("inspect", help="Crop full-resolution pixels using a manifest view ID.")
    crop.add_argument("manifest", type=Path)
    crop.add_argument("--view-id", required=True)
    crop.add_argument("--bbox", type=float, nargs=4, required=True)
    crop.add_argument("--coordinate-space", choices=["view", "overview"], default="view")
    crop.add_argument("--output-long-edge", type=int)
    review = commands.add_parser("review", help="Prepare a reproducible random image set and local human-review gallery.")
    review.add_argument("dataset_root", type=Path)
    review.add_argument("--output", type=Path, default=Path("build/preprocess-review"))
    review.add_argument("--count", type=int, default=50)
    review.add_argument("--seed", type=int, default=42)
    review.add_argument("--ocr", choices=["none", "tesseract"], default="none")
    review.add_argument("--ocr-languages", default="eng")
    review.add_argument("--ocr-timeout", type=float, default=30)
    review.add_argument("--overview-long-edge", type=int, default=1600)
    serve = commands.add_parser("serve", help="View an existing review gallery over localhost.")
    serve.add_argument("directory", type=Path)
    serve.add_argument("--port", type=int, default=8765)
    commands.add_parser("tool-schema", help="Print the backend function-tool declaration.")
    args = parser.parse_args()
    try:
        if args.command == "prepare":
            config = PreprocessConfig(overview_long_edge=args.overview_long_edge, analysis_long_edge=args.analysis_long_edge,
                                      padding=args.padding, ocr=args.ocr, ocr_languages=args.ocr_languages,
                                      ocr_timeout_seconds=args.ocr_timeout, max_source_pixels=args.max_source_pixels)
            result = prepare_drawing(args.source, args.output, config=config, source_uri=args.source_uri)
            print(json.dumps({"manifest": (args.output / result.id / "manifest.json").as_posix(),
                              "prepared": result.model_dump(mode="json")}, ensure_ascii=False, indent=2))
        elif args.command == "inspect":
            result = inspect_region(args.manifest, args.view_id, args.bbox, coordinate_space=args.coordinate_space,
                                    output_long_edge=args.output_long_edge)
            print(json.dumps(result, ensure_ascii=False, indent=2))
        elif args.command == "review":
            from .review import create_review
            path = create_review(args.dataset_root, args.output, count=args.count, seed=args.seed,
                                 config=PreprocessConfig(ocr=args.ocr, ocr_languages=args.ocr_languages,
                                                         ocr_timeout_seconds=args.ocr_timeout,
                                                         overview_long_edge=args.overview_long_edge))
            print(json.dumps({"review_gallery": path.as_posix()}, indent=2))
        elif args.command == "serve":
            from .server import serve_review
            serve_review(args.directory, port=args.port)
        else:
            print(json.dumps(inspection_tool_spec(), indent=2))
    except (PreparationError, ValueError, OSError) as exc:
        parser.exit(2, f"{exc}\n")


if __name__ == "__main__":
    main()
