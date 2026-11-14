"""Generate public JSON Schema contracts from the Pydantic source models.

Run from the repository root: ``python -m contracts.export``.
Use ``--check`` in CI to detect stale or missing generated contracts.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

from .models import (
    BenchmarkCase,
    CapabilityManifest,
    ImageCandidateError,
    ImageCandidateResponse,
    IfcModelResponse,
    IfcQuestionRequest,
    IfcQuestionResponse,
    KnowledgeBundle,
    PreparedDrawing,
    QueryPlan,
    QueryResult,
    QuestionRequest,
)


ROOT_MODELS = (
    KnowledgeBundle,
    QuestionRequest,
    QueryPlan,
    QueryResult,
    CapabilityManifest,
    BenchmarkCase,
    ImageCandidateResponse,
    ImageCandidateError,
    PreparedDrawing,
    IfcModelResponse,
    IfcQuestionRequest,
    IfcQuestionResponse,
)
OUTPUT_DIRECTORY = Path(__file__).resolve().parent / "jsonschema"
DRAFT = "https://json-schema.org/draft/2020-12/schema"


def schema_documents() -> dict[str, str]:
    """Return deterministic file contents without touching the filesystem."""
    documents: dict[str, str] = {}
    for model in ROOT_MODELS:
        schema = model.model_json_schema(mode="validation")
        version = schema["properties"]["schema_version"]["const"]
        document = {
            "$schema": DRAFT,
            "$id": f"urn:stoa:contracts:{version}:{model.__name__}",
            "$comment": (
                "Generated from contracts.models; do not edit manually. "
                "JSON Schema checks structure. Pydantic and semantic validators "
                "also enforce local invariants, references, units, scope, and evidence."
            ),
            **schema,
        }
        documents[f"{model.__name__}.schema.json"] = (
            json.dumps(document, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
        )
    return documents


def export_schemas(output_directory: Path = OUTPUT_DIRECTORY) -> list[Path]:
    output_directory.mkdir(parents=True, exist_ok=True)
    paths = []
    for filename, contents in schema_documents().items():
        path = output_directory / filename
        path.write_text(contents, encoding="utf-8", newline="\n")
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Fail if exported schemas are stale or missing.")
    args = parser.parse_args()
    if args.check:
        stale = []
        for filename, contents in schema_documents().items():
            path = OUTPUT_DIRECTORY / filename
            if not path.exists() or path.read_text(encoding="utf-8") != contents:
                stale.append(filename)
        if stale:
            parser.exit(1, "Stale generated contracts: " + ", ".join(stale) + ". Run python -m contracts.export.\n")
        print(f"All {len(ROOT_MODELS)} generated contracts are current.")
    else:
        paths = export_schemas()
        print(f"Exported {len(paths)} contracts to {OUTPUT_DIRECTORY}.")


if __name__ == "__main__":
    main()
