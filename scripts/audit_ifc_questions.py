"""Exhaustive, analysis-only IFC task inventory; never a runtime answer lookup.

Uses the reviewed question taxonomy and original source paths, never reference
answers. The optional JSON manifest retains every original line/question/scope
for reproducible evaluations without bundling supplied answers into the app.
"""
from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import asdict
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_QUESTION_SHA256 = "0e6322c74561a63f42bac35f5c1be8a2c6a37516b14a81e66ab88b74950a6d1f"
sys.path.insert(0, str(ROOT))
from scripts.classify_questions import classify


def inventory(dataset: Path) -> dict:
    taxonomy = json.loads((ROOT / "scripts/question_classification_taxonomy.json").read_text())
    classified, digest, _ = classify(dataset, taxonomy)
    if digest != EXPECTED_QUESTION_SHA256:
        raise ValueError("This reviewed inventory requires the full question-file revision stated in the report; review changed inputs before generating new scope claims.")
    rows = []
    for row in classified:
        if row.source not in {"ifc_models", "ifc_bench"}:
            continue
        path = Path(row.path)
        direct = path.suffix.casefold() == ".ifc"
        model = path if direct else path.with_name(path.stem.split("_plan-", 1)[0] + ".ifc")
        if not direct and "_plan-" not in path.stem:
            raise ValueError(f"Unreviewed IFC-derived representation naming: {row.path}")
        if not (dataset / model).is_file():
            raise ValueError(f"Missing paired source: {model}")
        if not (dataset / path).is_file():
            raise ValueError(f"Missing referenced asset: {path}")
        record = asdict(row)
        record.update(model_path=model.as_posix(), direct_ifc=direct,
                      scope=row.scope or "question-defined; preserve the literal question restrictions")
        rows.append(record)
    models = sorted({row["model_path"] for row in rows})
    return {"dataset_sha256": digest, "rows": rows, "model_paths": models}


def requirements(family: str) -> str:
    """Reviewed tool classes, not assertions that a family is implemented."""
    tags = set()
    prefix = family.split(" / ", 1)[0]
    if prefix in {"Count", "Compound", "Inventory"}:
        tags.add("C")
    if prefix in {"Area", "Volume", "Length", "Property", "Ranking", "Compound", "Inventory", "Derived"}:
        tags.add("Q")
    if prefix in {"Inventory", "Compound", "Spatial", "Volume"}:
        tags.add("J")
    if prefix in {"Derived", "Connectivity"}:
        tags.add("A")
    if prefix == "Connectivity":
        tags.add("N")
    if prefix == "Overview" or family == "Property / Model software and IFC standards":
        tags.add("M")
    if prefix == "Spatial" or family in {
        "Area / Building footprint", "Area / Exterior facade surface",
        "Area / Town enclosed by inner wall", "Length / Skirting boards",
        "Property / Steel beams spanning a specified room", "Property / Ceiling GUID",
    }:
        tags.add("G")
    if family in {
        "Property / Building level heights and elevations", "Volume / Insulation",
        "Area / Interior wall painting", "Area / Duct cross-sections and distribution",
        "Area / Glazed windows", "Count / Stair steps", "Count / Roof vapor barriers",
    }:
        tags.add("A")
    if any(word in family.lower() for word in ["layer", "insulation", "material", "thickness"]):
        tags.add("X")
    if prefix in {"Compliance", "Sustainability"} or family in {
        "Derived / Structural embodied carbon", "Derived / Door cost by type or total",
        "Derived / Window total cost", "Property / Roof material lifespan",
        "Property / Maintenance requirements or schedules", "Property / Wall acoustic rating",
        "Property / Waiting-area capacities", "Property / Ventilation requirements",
    }:
        tags.add("E")
    return ", ".join(sorted(tags)) or "Q"


def escaped(value) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def report(data: dict) -> str:
    rows = data["rows"]
    direct = [row for row in rows if row["direct_ifc"]]
    pdf = [row for row in rows if not row["direct_ifc"]]
    by_model, by_family = defaultdict(list), defaultdict(list)
    for row in rows:
        by_model[row["model_path"]].append(row)
        by_family[row["family"]].append(row)
    output = [
        "# IFC question coverage and acceptance inventory", "",
        "Audit of the supplied full dataset on 14 November 2026. This is a task inventory,",
        "not a claim of completed engine coverage or measured answer accuracy.", "",
        f"Question-file SHA-256: `{data['dataset_sha256']}`.", "",
        "Regenerate with `python scripts/audit_ifc_questions.py`. Add",
        "`--inventory-json build/ifc-question-inventory.json` for every original",
        "line, question, reviewed family, scope and paired source path. The generator",
        "does not read reference answer values or call a model.", "",
        "## Exact denominators", "",
        "| Cohort | Rows | Referenced paths | Distinct question texts |",
        "| --- | ---: | ---: | ---: |",
    ]
    for label, selected in [
        ("IFC-Bench, direct IFC", [r for r in direct if r["source"] == "ifc_bench"]),
        ("Quantitative IFC models, direct IFC", [r for r in direct if r["source"] == "ifc_models"]),
        ("IFC-derived floor PDFs", pdf), ("All direct IFC", direct), ("All IFC-source cohorts", rows),
    ]:
        output.append(f"| {label} | {len(selected):,} | {len({r['path'] for r in selected})} | {len({r['question'] for r in selected}):,} |")
    output += [
        "", f"The direct IFC target contains **{len({r['family'] for r in direct})} reviewed families**.",
        f"Including paired PDFs gives **{len(by_family)} families and {len(by_model)} source-model paths**.",
        "All referenced assets and all 69 PDF-to-IFC pairs exist in this checkout.",
        "The dataset README documents `<model>_plan-<level>.pdf` as a rendering of",
        "`<model>.ifc`; this pairing establishes provenance, not identical view scope.", "",
        "Direct quantitative IFC rows contain **64 whole-model and 304 floor/room rows**.",
        "Their PDFs add **194 whole-model and 2,500 floor/room rows**. A model-wide",
        "question remains model-wide even when its referenced asset is one floor PDF.",
        "The 820 Bench rows have question-specific restrictions rather than a dataset",
        "scope field; retain their exact model/floor/room/object wording. Do not infer",
        "that all Bench questions authorize broadening an interactive current-view request.", "",
        "## Starting implementation and required work", "",
        "The initial audited runtime is commit `80a8ded`. It has source selection,",
        "scalar property projection, exact counts, grouping, ranking, sum/mean/min/max,",
        "native topology, bounded room/boundary geometry, related-object projection,",
        "metadata discovery and source-backed result explanations. Its planner has a",
        "shared cap of three requests, six inspection actions and a deadline. Those",
        "primitives establish an implementation basis; they do not prove every family.", "",
        "| Code | Required reusable work | Starting coverage / acceptance condition |",
        "| --- | --- | --- |",
        "| C | Select/filter/count at stated grain | Existing primitives; source class/type semantics, assemblies, multilingual literals and exact scope need real-case checks. |",
        "| Q | Project scalar quantities/properties; aggregate or rank | Existing primitives; resolve original property keys, units, net/gross basis, missing inputs and all requested outputs. |",
        "| J | Object→storey/type/material/system/room relationships and joined inventories | Native relations and related-object projection exist; joined per-occurrence grouping and incomplete relationships need verification. |",
        "| A | Arithmetic, percentages, ratios, cost products, consecutive-elevation differences | Executor gap at audit start; preserve dimensions and input evidence, reject zero denominators and unsupported assumptions. |",
        "| X | Material layers, layer thicknesses and nested source properties | Material membership exists; composition/ordered layer facts and derived layer quantities need extraction and evidence. |",
        "| G | Geometry, topology, nearest distances and routes | Bounded topology/room containment exists; general quantities, town positions, route distances and widths remain gaps or require explicit missing-source outcomes. |",
        "| N | Distribution-port graph, connectivity and integration metrics | Native port connectivity graph and derived metric definitions need implementation; system membership is insufficient. |",
        "| M | Source metadata and bounded descriptive summaries | Native metadata exists; verify all requested components without inventing history, location or structural performance. |",
        "| E | External factors, rule basis or estimation assumptions | Require explicit sourced inputs, qualified estimates or precise missing-information outcomes; reference defaults are not model facts. |", "",
        "Codes describe the family as a whole and are not per-row success labels.",
        "A missing executor for a known family remains unfinished work. Conversely,",
        "a source-supported finding that the requested fact is absent can be correct;",
        "absence must be established from extraction/source coverage, not guessed by a model.", "",
        "Concrete initial gaps include consecutive storey heights (line 85521),",
        "load-bearing volume percentage (85527), clinical/nonclinical ratio (85616),",
        "net/gross ratio (85643), plumbing and ventilation port metrics (86261, 86292),",
        "nearest town gate (85838), enclosed town area (85839), route lengths (85618,",
        "85770) and source-qualified accessibility rules (85756).", "",
        "## Every source model referenced directly or by a paired floor", "",
        "Rows count question records, including translations and repeated references.",
        "Distinct IFC paths are not independent projects: the prior full-data audit",
        "found eight byte-identical cross-folder model pairs. Keep equivalent models",
        "and their floors together in evaluation partitions.", "",
        "| Source IFC path | Direct IFC rows | Paired PDF rows | PDF paths | First JSONL line |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for path, selected in sorted(by_model.items()):
        output.append(f"| `{path}` | {sum(r['direct_ifc'] for r in selected)} | {sum(not r['direct_ifc'] for r in selected)} | {len({r['path'] for r in selected if not r['direct_ifc']})} | {min(r['line'] for r in selected)} |")
    output += [
        "", "## Every reviewed family", "",
        "The existing [exhaustive wording catalog](QUESTION_CLASSIFICATION.md#exhaustive-wording-and-template-catalog)",
        "retains verbatim examples. The optional JSON inventory retains every original",
        "row and exact path; this table preserves direct IFC versus PDF denominators.", "",
        "| Family | IFC rows | PDF rows | Required work | First JSONL line |",
        "| --- | ---: | ---: | --- | ---: |",
    ]
    for family, selected in sorted(by_family.items()):
        output.append(f"| {escaped(family)} | {sum(r['direct_ifc'] for r in selected)} | {sum(not r['direct_ifc'] for r in selected)} | {requirements(family)} | {min(r['line'] for r in selected)} |")
    output += [
        "", "## Completion and evaluation gates", "",
        "1. Preserve the 1,188 direct-IFC-row denominator and all 198 families. Track",
        "   the 2,694 paired-PDF rows separately; using their source IFC must retain",
        "   the named floor/view and cannot silently expand a user's upload scope.",
        "2. Run production upload/question planning and execution on all 40 directly",
        "   referenced IFC paths. Cover every family and named quantity, including",
        "   rare geometry, network and derived tasks. Unknown unsupported families",
        "   remain in the denominator rather than disappearing from a success report.",
        "3. Save predictions, plans, source hashes, source element/fact/anchor sets,",
        "   calculation inputs, scope, status, units, usage and timing before loading",
        "   evaluation references. No QA lookup belongs in planning or execution.",
        "4. Counts require exact agreement at the stated occurrence/assembly grain.",
        "   Quantities require compatible units/bases and the supplied dataset's 2%",
        "   tolerance. A missing total is not zero; lower bounds cannot pass as exact.",
        "5. Bench `text` includes numerical and multipart tasks. Check every requested",
        "   component against source facts/calculations or an independently supported",
        "   missing-information finding. Structural/evidence checks alone leave text",
        "   accuracy ungraded; keyword matching cannot establish correctness.",
        "6. Check current-view, explicit-empty-view, hidden-floor, whole-model and",
        "   source-revision variants. Add paraphrases/translations within these known",
        "   families and preserve literal identifiers. A result cannot use outside-view",
        "   prerequisite objects without reporting incomplete coverage.",
        "7. Use deterministic cached extraction and bounded tools for computation.",
        "   Start with one planning call; discovery/repair shares a finite budget.",
        "   Resume persisted runs to avoid repeated paid calls and report actual usage,",
        "   latency, errors and non-answers alongside successful results.", "",
        "Known reference disputes need source adjudication. For example, line 85820",
        "reports a legacy schema differing from the distributed IFC file header.",
        "See [dataset findings](../dataset/FULL_DATASET_FINDINGS.md) and",
        "[scope and acceptance](PROJECT_SCOPE.md). This inventory does not validate",
        "all reference answers, classify all missing-input references, or establish",
        "dataset-wide end-to-end accuracy.", "",
        "Implemented behavior, source-backed development probes and their limitations",
        "are recorded separately in [implementation verification](IFC_IMPLEMENTATION_VERIFICATION.md).", "",
    ]
    return "\n".join(output)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset/junction-dataset")
    parser.add_argument("--output", type=Path, default=ROOT / "docs/IFC_QUESTION_COVERAGE.md")
    parser.add_argument("--inventory-json", type=Path)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args()
    data = inventory(args.dataset)
    rendered = report(data)
    if args.check:
        if not args.output.is_file() or args.output.read_text() != rendered:
            print(f"Stale IFC question inventory: {args.output}")
            return 1
    else:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")
    if args.inventory_json:
        args.inventory_json.parent.mkdir(parents=True, exist_ok=True)
        args.inventory_json.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"Inventoried {len(data['rows'])} IFC-source rows, {len(data['model_paths'])} source IFC paths; no inference.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
