"""Render a persisted IFC evaluation as a reviewable coverage summary."""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
import json
from pathlib import Path


def _cell(value):
    return str(value).replace("|", "\\|").replace("\n", " ")


def render(output: Path) -> str:
    identity = json.loads((output / "manifest.json").read_text())["identity"]
    report = json.loads((output / "report.json").read_text())
    records = [json.loads(path.read_text()) for path in sorted((output / "predictions").glob("line-*.json"))]
    selected = identity["tasks"]
    models, families = defaultdict(list), defaultdict(list)
    for task in selected:
        models[task["path"]].append(task)
        families[task["family"]].append(task)
    by_model, by_family = defaultdict(list), defaultdict(list)
    errors, internal = Counter(), []
    native = []
    for record in records:
        by_model[record["task"]["path"]].append(record)
        by_family[record["task"]["family"]].append(record)
        if "error" in record:
            errors[record["error"]["code"]] += 1
            if record["error"]["code"] in {"internal_error", "evaluation_internal_error", "upload_internal_error"}:
                internal.append(record)
        elif record["response"].get("planning", {}).get("provider") == "deterministic":
            native.append(record)
    native_lines = {record["line"] for record in native}
    native_families = {record["task"]["family"] for record in native}
    all_native_families = {family for family, tasks in families.items() if all(task["line"] in native_lines for task in tasks)}
    successful_models = {record["task"]["path"] for record in records if record.get("upload")}
    summary = report["summary"]
    rows = ["# IFC source coverage run", "",
            f"Mode: `{identity['mode']}`. Selected {len(selected)} rows, {len(families)} families and {len(models)} source paths; recorded {len(records)} predictions.", "",
            f"Successfully opened {len(successful_models)} source paths. Native planning produced {len(native)} responses across {len(native_families)} families; all selected rows compiled natively in {len(all_native_families)} families.", "",
            f"External inference requests: {summary['external_inference_requests']}; cumulative call starts: {summary['cumulative_started_calls']}. Unattempted rows: {summary['not_attempted_rows']}.", "",
            f"Runtime source files changed during run: `{str(report['code_changed_during_run']).lower()}`.", "",
            "Native compilation and source/evidence consistency do not independently establish answer accuracy. Bench free text and source membership remain ungraded. Complete estimated quantities use the documented 2% numeric tolerance; lower/upper/partial results cannot pass as exact totals.", "",
            "## Outcomes", "", "| Outcome | Rows |", "| --- | ---: |"]
    rows += [f"| {_cell(key)} | {value} |" for key, value in sorted(summary["statuses"].items())]
    rows += ["", "## Numeric/text grading", "", "| Grading | Rows |", "| --- | ---: |"]
    rows += [f"| {_cell(key)} | {value} |" for key, value in sorted(summary["grading"].items())]
    rows += ["", "## API errors", "", "| Safe error code | Rows |", "| --- | ---: |"]
    rows += [f"| `{_cell(key)}` | {value} |" for key, value in sorted(errors.items())]
    rows += ["", "## Sources", "", "| Source path | Selected | Recorded | Opened | Native | Answered | Other API errors |", "| --- | ---: | ---: | --- | ---: | ---: | ---: |"]
    for path, tasks in models.items():
        values = by_model[path]
        native_count = sum(record["line"] in native_lines for record in values)
        answered = sum(record.get("response", {}).get("result", {}).get("status") == "answered" for record in values)
        other_errors = sum("error" in record and record["error"]["code"] != "evaluation_call_budget" for record in values)
        opened = "yes" if path in successful_models else "failed" if values else "unattempted"
        rows.append(f"| {_cell(path)} | {len(tasks)} | {len(values)} | {opened} | {native_count} | {answered} | {other_errors} |")
    rows += ["", "## Native family coverage", "", "| Family | Selected | Native responses | Answered |", "| --- | ---: | ---: | ---: |"]
    for family in sorted(native_families):
        values = by_family[family]
        native_count = sum(record["line"] in native_lines for record in values)
        answered = sum(record["line"] in native_lines and record.get("response", {}).get("result", {}).get("status") == "answered" for record in values)
        rows.append(f"| {_cell(family)} | {len(families[family])} | {native_count} | {answered} |")
    if internal:
        rows += ["", "## Unexpected internal errors", "", "| Line | Question characters | Source path | Safe code |", "| ---: | ---: | --- | --- |"]
        for record in sorted(internal, key=lambda value: value["line"]):
            rows.append(f"| {record['line']} | {len(record['task']['question'])} | {_cell(record['task']['path'])} | `{record['error']['code']}` |")
    rows += ["", "Full selected rows/source hashes/code hashes are in `manifest.json`; exact predictions/plans/proofs are atomic per-row files in `predictions/`; grading and unattempted lines are in `report.json`.", ""]
    return "\n".join(rows)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--write", type=Path)
    args = parser.parse_args(argv)
    content = render(args.output)
    if args.write:
        args.write.write_text(content, encoding="utf-8")
    else:
        print(content, end="")


if __name__ == "__main__":
    main()
