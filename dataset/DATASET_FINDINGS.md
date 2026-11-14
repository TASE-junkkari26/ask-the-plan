# What the Stoa dataset is asking us to build

Investigated 13 November 2026. This is a historical audit of the extracted
**preview**, not the full archive or a current implementation status report. See
[full dataset findings](FULL_DATASET_FINDINGS.md) for the later full-corpus audit
and [README](../README.md) for the application now present in this repository.

Project scope clarification, 14 November: the supplied dataset's question
families define hackathon acceptance. A system that works for that set is
sufficient; unknown question classes are not an evaluation requirement. See
[project scope](../docs/PROJECT_SCOPE.md). Historical observations below about
missing annotations do not expand that boundary.

**The requested product answers a natural-language question using a construction drawing or BIM model, returns the answer with the right scope and units, and shows the supporting objects or source region.** Object detection, room classification, OCR, and geometry extraction are possible implementation components. The brief does not prescribe a fixed set of classes to predict.

Evidence: [task.md](task.md), especially its challenge and judging sections. The
four criteria are answer accuracy, visualization that enables human verification,
creativity, and low inference cost, each weighted 25%. Training a model is not a
stated requirement. [Compute notes](compute.md) record the reported credit grants;
they do not change Stoa's task into a classification competition.

Later clarification reported on 14 November: the organizer expects questions to
mostly concern what is shown. Default the UI to that drawing/view while retaining
the explicit broader scope of the existing reference rows discussed below.

## What is actually present

There are **910 asset files**, excluding the nine licence documents, taking 722,493,648 bytes. There are **7,990 question-answer rows** referencing **320 distinct paths**. Every row has all five documented fields; every answer is populated; every referenced path exists. There are no identical duplicate rows or conflicting answers for an identical `(path, question)`.

| Source | Asset files | Files referenced by questions | Question rows | Tasks represented |
|---|---:|---:|---:|---|
| cubicasa5k | 241 | 241 | 4,270 | Counts of objects, room categories, and storeys |
| swiss_dwellings | 195 | 65 | 2,358 | Object/room/apartment counts; room, apartment, and floor areas |
| ifc_models | 10 | 6 | 1,049 | Whole-model and per-floor counts, areas, lengths, volumes |
| ifc_bench | 5 | 5 | 249 | BIM information retrieval, aggregation, spatial reasoning, missing information |
| opening_design | 78 | 3 | 64 | Door/finish schedules, dimensions, materials, room areas, restroom fixtures |
| europeana | 61 | 0 | 0 | Drawings without supplied question-answer rows |
| finna | 96 | 0 | 0 | Drawings without supplied question-answer rows |
| habs | 92 | 0 | 0 | Drawings without supplied question-answer rows |
| wikimedia | 132 | 0 | 0 | Drawings without supplied question-answer rows |
| **Total** | **910** | **320** | **7,990** | |

The raw file count includes format alternatives. All 65 Swiss plans have PDF, DXF, and PNG versions, but questions point to the PDF. Three IFC-derived plans have both PDF and SVG. Seven Wikimedia drawings also have format alternatives. Grouping by directory and filename stem gives 770 groups; this is not a count of independent buildings. Counting equivalent extensions as covered raises coverage from 320 to 453 files.

The README's approximately 14,000 drawings and 120,000 questions describe the broader dataset, not this local extraction. The README itself says questions cover only roughly 40% of drawings. The full archive has not been inspected here, so its exact coverage and possible additional annotations remain unverified.

## What `type` and the answers mean

Each record has `{path, question, answer, unit, type}`. `type` describes the answer format or measurement:

| Answer type | Preview rows | Example task |
|---|---:|---|
| count | 6,076 | Count doors, windows, apartments, or toilets |
| area | 1,599 | Return a room's area or sum net floor areas |
| volume | 34 | Sum net wall/slab volumes |
| length | 16 | Sum wall lengths |
| text | 265 | Retrieve a door specification or describe BIM properties |
| other | 0 | Allowed by the README, absent in this preview |

The documented numeric scoring rule is exact counts and measurements within 2%; text answers are free-form. No executable scorer or text grading procedure is supplied. These rules are distinct from the four hackathon judging criteria.

`unit: null` for text rows is intentional. Some text answers contain numbers or dimensions: for example, the width of door 121.A is returned as `5'-10 3/8"` and marked `text` ([preview questions.jsonl, line 5586](junction-dataset-preview/questions.jsonl#L5586)). Thus `type` is not an object class or a complete intent taxonomy.

## Why questions do not cover every class

**No existing row is missing its answer. What is missing is a row for every possible `(drawing, object category)` combination.** There is no exhaustive annotation contract or explanation of the selection/filtering process in the package. Treat an unasked category as an unknown training/evaluation annotation, not as a negative label or count of zero. This sparsity does not require support for additional question classes.

CubiCasa illustrates this clearly. Its 24 distinct question texts are English/Finnish versions of 12 tasks:

| CubiCasa task/category | Images with that task, out of 241 | Explicit zero answers, counting English rows |
|---|---:|---:|
| Windows | 241 | 1 |
| Storeys shown | 241 | 0 |
| Toilet bowls | 240 | 11 |
| Sinks/washbasins | 239 | 6 |
| Showers and bathtubs combined | 227 | 14 |
| Doors fitted with a door leaf | 176 | 0 |
| Saunas | 165 | 72 |
| Kitchens, including kitchenettes/open/utility kitchens | 161 | 3 |
| Bedrooms | 154 | 26 |
| Separate WC rooms | 112 | 68 |
| Bathrooms/washrooms excluding separate WC rooms | 111 | 8 |
| Balconies | 68 | 39 |

For a concrete counterexample to interpreting missing questions as zero, `data/cubicasa5k/colorful-11397.png` visibly contains swinging doors, yet its ten rows ask only about windows, toilet bowls, sinks, showers/baths, and storeys, each in two languages. There is no door-count answer for that image.

Counting conventions also matter: a double-bowl sink counts as one; an open doorway without a door leaf does not count as a door; separate WC rooms and toilet bowls are different questions. Swiss indoor-area questions explicitly exclude balconies, terraces, shafts, and voids.

The [upstream CubiCasa5K repository](https://github.com/CubiCasa/CubiCasa5k) describes polygon annotations for more than 80 object categories. **The local CubiCasa folder contains PNG images and a licence document, without those SVG polygon annotations.** The supplied JSONL provides aggregate counts, with no bounding boxes, masks, object coordinates, or per-instance class labels. A detector trained on all original categories would need the upstream annotations or another source of instance supervision. We cannot infer why the challenge builder omitted particular per-image questions from this package.

Many rows are translations rather than independent visual examples. Consecutive English/local-language pairs in CubiCasa, Swiss Dwellings, and the bilingual portion of `ifc_models` have matching paths, answers, units, and types. Keep translated questions and alternate formats of the same drawing together when making development/evaluation splits; preferably split by building/project as well.

## What the IFC models are for

An IFC file stores building objects, their types, names/IDs, spatial hierarchy, properties, quantities, and geometry. These models are input documents for the question-answering task. They are also useful for deriving structured answers, retaining evidence IDs, and potentially creating labelled renderings.

### `ifc_models`: quantitative questions and linked drawings

The licence documentation says the PDF/SVG floor plans were rendered from the IFC models using IfcOpenShell. The preview has four IFC files and three PDF/SVG plan pairs. Some questions ask about a whole model; others ask about a specific storey or room.

**A question's `path` is not always a sufficient description of its scope.** Verified example:

- JSONL line 4521 points to `bsc-esplanades_1807-ep-ar-v18_plan-04-4-korrus.pdf` but asks how many doors are in the entire model. Its answer is **211**.
- The corresponding IFC contains exactly **211 `IFCDOOR` occurrence records**.
- The paired fourth-floor SVG contains **42 door object groups** with distinct IFC GUIDs.
- JSONL line 4905 asks specifically about `4.korrus`, with answer **42**.

The Molio example behaves the same way: **119** doors in the model versus **14** on its basement plan. Both model-wide and floor-specific questions point to that basement PDF. Therefore these rows cannot all be scored as questions about only the visible sheet. Resolve the associated IFC and the scope stated in the question. Model-wide quantities should not be expected to be recoverable from one floor image.

The SVG plans preserve `class`, `data-name`, `data-guid`, and object IDs. The Esplanades plan, for example, has classes `IfcSpace`, `IfcDoor`, `IfcWindow`, `IfcWall`, `IfcWallStandardCase`, `IfcStairFlight`, and `IfcRailing`. This provides a direct route from a counted object to highlighted geometry. The floor SVG's 14 `IfcWall` groups plus 146 `IfcWallStandardCase` groups also match the supplied floor wall count of 160. These are counts of model objects, which need not match a person's intuitive count of continuous wall runs.

Not all IFC exports represent classes identically. The clinic's answer of 119 sanitary fixtures is supported by **119 `IfcFlowTerminal` occurrences linked to nine `IfcSanitaryTerminalType` definitions**. Searching only for an `IFCSANITARYTERMINAL` occurrence string would incorrectly find zero. Use the schema, type relationships, and property sets through a parser. [IfcOpenShell's official examples](https://docs.ifcopenshell.org/ifcopenshell-python/code_examples.html) cover type relationships, quantity/property lookup, spatial containers, and unit conversion.

### `ifc_bench`: broader BIM questions

All 249 local questions are stored as `text`, even when they ask for numeric quantities or multi-part summaries. The five models have 48, 64, 51, 35, and 51 questions respectively. Tasks include room/area breakdowns, largest rooms, door types and widths, material quantities, building metadata, and whether specific information exists.

The [upstream IFC-Bench taxonomy](https://huggingface.co/datasets/sylvainHellin/ifc-bench/blob/main/README.md#question-taxonomy) distinguishes direct property retrieval, mathematical aggregation, geometric/spatial computation, and incomplete information. The challenge's JSONL does not retain that `category` column.

Some reference answers explicitly say the information is unavailable; others give estimates and assumptions. For example, line 4399 asks for first-floor live-load capacity and answers that the information is unavailable in the BIM model. Missing model information is a real part of the task: an answer should state the limitation rather than invent a value. Distinguish these rows from exact quantity questions when evaluating results.

### Preview limitations found

- **Missing source model:** the FZK-Haus attic PDF/SVG has 24 questions, including whole-building counts, but `kit-fzk-haus_ac20-fzk-haus.ifc` is absent from the preview. Its SVG shows no doors on the attic floor, while a model-wide question asks for five doors. The existing `ifc_bench/ac20_arc.ifc` is a different office model, not a substitute. This was unverified in the preview review; the later [full audit](FULL_DATASET_FINDINGS.md#improvements-over-the-preview) confirms that source is present in the full archive.
- **Empty model content:** `ifc_models/resbim-388_model.ifc` is only 2,501 bytes. It contains project/site/building/storey and unit/context records, but no building-element or space occurrences. No questions reference it. Do not assume every IFC is a usable complete building.
- **Other IFCs:** five IFC files in `opening_design` are unreferenced by questions. Some are details/test exports, including a file explicitly located under `bad IFC models - for autopsy only`. They should not be assumed to be equivalent training examples of complete buildings.
- **Units:** the inspected Esplanades and Molio files declare millimetre length units and square-metre area units. Inspect the appropriate quantity/project units before summing or comparing to the JSONL's metres, square metres, cubic metres, or square feet.

## A practical interpretation for implementation

Build a shared question-answering interface with format-specific extraction underneath:

1. Parse the question into the requested objects/properties, operation, spatial scope, exclusions, and output unit.
2. Resolve the source and its available representations: IFC with its rendered SVG/PDF; Swiss DXF with its PNG/PDF; or a standalone raster/schedule sheet.
3. Extract structured evidence using IFC properties/geometry, CAD entities, schedule text, or visual detection/OCR as appropriate. One inspected Swiss DXF exposes layers including `ROOM_OUTLINE`, `ROOM_TEXT`, `UNIT_OUTLINE`, `DOOR`, `WINDOW`, `WALL`, and `FIXTURE`. CAD primitives still need grouping; one line or arc is not necessarily one object.
4. Count or calculate using explicit rules, then return the answer, unit, scope, and supporting object IDs or drawing regions. Show uncertainty or absent information where appropriate.

A useful first demonstrator is an IFC-backed answer with highlighted SVG objects, a Swiss count/area question using its structured drawing, and a real Opening Design schedule lookup. This recommendation follows the observed formats and judging criteria; it is not a requirement imposed by the organizer. It exercises counting, geometry, document lookup, and verifiable evidence. Standalone scans can then use an additional vision/OCR path. A detector for the 12 local CubiCasa question categories addresses only one part of this dataset.

The package does not specify the submission schema, exact free-form text grader,
or why particular per-image questions were selected. Those administrative details
do not expand the project scope: implement the families demonstrated by the full
supplied dataset, with correct answers and easily checked evidence. Do not infer
a requirement for unknown evaluation classes from missing package metadata.

## Reproduce the local audit

From the **repository root**, with the preview root containing `questions.jsonl`
and `data/`:

```text
python dataset/dataset_audit.py dataset/junction-dataset-preview --output dataset/dataset_audit.json
```

Adjust the input path if your extraction layout differs. The script uses only
the Python standard library, reads original data without changing it, and writes
the requested report. Running it again replaces that report. It records source
counts, type distributions, sparse CubiCasa coverage, IFC STEP entity inventories,
SVG metadata, and model/floor question examples.

[dataset_audit.json](dataset_audit.json) contains the measured results; [dataset_audit.py](dataset_audit.py) contains the audit. STEP string inspection verifies occurrence inventories, not general IFC geometry correctness. The raw drawings, question file, and licence documents were left unchanged.
