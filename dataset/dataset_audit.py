"""Audit an extracted preview/full dataset using only the standard library.

From the repository root:
    python dataset/dataset_audit.py dataset/junction-dataset-preview --output build/preview-audit.json

Create the output directory first. Sources are read only; an existing output is replaced.
IFC entity counts inspect STEP records; they are not a substitute for an IFC parser.
"""

import argparse
from collections import Counter, defaultdict
import hashlib
import json
from pathlib import Path
import re
import xml.etree.ElementTree as ET


def audit(root):
    question_file = root / "questions.jsonl"
    rows = [json.loads(line) for line in question_file.read_text(encoding="utf-8").splitlines() if line.strip()]
    files = sorted(p for p in (root / "data").rglob("*") if p.is_file() and p.name != "LICENSE.md")
    paths = {row["path"] for row in rows}
    file_paths = {p.relative_to(root).as_posix() for p in files}
    format_groups = defaultdict(list)
    for p in files:
        format_groups[p.relative_to(root).with_suffix("").as_posix()].append(p.relative_to(root).as_posix())
    covered_stems = {str(Path(p).with_suffix("")).replace("\\", "/") for p in paths}
    equivalent_paths = {p for stem, members in format_groups.items() if stem in covered_stems for p in members}
    answers_by_question = defaultdict(set)
    for row in rows:
        answers_by_question[(row["path"], row["question"])].add(json.dumps(row["answer"], sort_keys=True))

    sources = {}
    for source in sorted(p.name for p in (root / "data").iterdir() if p.is_dir()):
        source_files = [p for p in files if p.relative_to(root / "data").parts[0] == source]
        source_rows = [row for row in rows if row["path"].split("/")[1] == source]
        sources[source] = {
            "files": len(source_files),
            "extensions": dict(Counter(p.suffix.lower() for p in source_files)),
            "questions": len(source_rows),
            "referenced_files": len({row["path"] for row in source_rows}),
            "answer_types": dict(Counter(row["type"] for row in source_rows)),
            "zero_answers": sum(row["answer"] == 0 for row in source_rows),
        }

    cubi = [row for row in rows if row["path"].startswith("data/cubicasa5k/")]
    cubi_paths = {row["path"] for row in cubi}
    coverage = []
    for prompt in dict.fromkeys(row["question"] for row in cubi if row["question"].startswith("How")):
        matching = [row for row in cubi if row["question"] == prompt]
        coverage.append({
            "question": prompt,
            "files_with_question": len({row["path"] for row in matching}),
            "files_without_question": len(cubi_paths - {row["path"] for row in matching}),
            "explicit_zero_answers": sum(row["answer"] == 0 for row in matching),
            "minimum_answer": min(row["answer"] for row in matching),
            "maximum_answer": max(row["answer"] for row in matching),
        })

    ifc_stats = []
    for p in files:
        if p.suffix.lower() != ".ifc":
            continue
        content = p.read_text(encoding="utf-8", errors="replace")
        entity_counts = Counter(re.findall(r"^\s*#\d+\s*=\s*(IFC\w+)\s*\(", content, re.MULTILINE))
        ifc_stats.append({
            "path": p.relative_to(root).as_posix(),
            "bytes": p.stat().st_size,
            "schema": re.findall(r"FILE_SCHEMA\s*\((.*?)\);", content, re.DOTALL),
            "exact_step_entity_counts": dict(sorted(entity_counts.items())),
        })

    svg_stats = []
    for p in sorted((root / "data/ifc_models").glob("*.svg")):
        elements = list(ET.parse(p).iter())
        product_groups = [e for e in elements if "data-guid" in e.attrib]
        guids = [e.attrib["data-guid"] for e in product_groups]
        svg_stats.append({
            "path": p.relative_to(root).as_posix(),
            "class_counts": dict(Counter(e.attrib.get("class") for e in product_groups)),
            "product_groups": len(product_groups),
            "unique_guids": len(set(guids)),
            "example_object": product_groups[0].attrib if product_groups else None,
        })

    example_path = "data/cubicasa5k/colorful-11397.png"
    scope_examples = []
    for line, row in enumerate(rows, 1):
        if row["path"].startswith("data/ifc_models/") and row["path"].endswith(".pdf"):
            if row["question"].startswith("How many doors"):
                scope_examples.append({"jsonl_line": line, **row})

    return {
        "dataset_root": root.resolve().as_posix(),
        "questions_sha256": hashlib.sha256(question_file.read_bytes()).hexdigest(),
        "files_excluding_license_documents": len(files),
        "bytes_excluding_license_documents": sum(p.stat().st_size for p in files),
        "same_name_format_groups": len(format_groups),
        "questions": len(rows),
        "directly_referenced_files": len(paths),
        "referenced_or_same_name_format_files": len(equivalent_paths),
        "missing_question_paths": sorted(paths - file_paths),
        "missing_or_null_answers": sum(row.get("answer") is None for row in rows),
        "empty_string_answers": sum(row.get("answer") == "" for row in rows),
        "field_occurrences": dict(Counter(key for row in rows for key in row)),
        "answer_types": dict(Counter(row["type"] for row in rows)),
        "duplicate_rows": len(rows) - len({json.dumps(row, sort_keys=True) for row in rows}),
        "conflicting_answers_for_same_path_and_question": sum(len(v) > 1 for v in answers_by_question.values()),
        "sources": sources,
        "cubicasa_question_coverage": coverage,
        "sparse_example": {"path": example_path, "rows": [row for row in cubi if row["path"] == example_path]},
        "ifc_step_inspection": ifc_stats,
        "ifc_rendered_svg_inspection": svg_stats,
        "model_vs_floor_question_examples": scope_examples,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", nargs="?", type=Path, default=Path(__file__).resolve().parent / "junction-dataset-preview",
                        help="Dataset root containing questions.jsonl and data/; defaults to the checkout preview")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = audit(args.dataset)
    serialized = json.dumps(result, ensure_ascii=False, indent=2) + "\n"
    if args.output:
        args.output.write_text(serialized, encoding="utf-8")
        print(json.dumps({"output": str(args.output), "files": result["files_excluding_license_documents"], "questions": result["questions"], "missing_answers": result["missing_or_null_answers"]}))
    else:
        print(serialized)
