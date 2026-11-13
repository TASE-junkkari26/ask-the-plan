# Full dataset compared with the preview

Investigated 13 November 2026. The full extraction is `junction-dataset/`. The original files were left unchanged. Results are recorded in [full_dataset_audit.json](full_dataset_audit.json) and [full_dataset_quality.json](full_dataset_quality.json). The pre-existing `full_dataset_comparison.json` was read and left unchanged; its basic counts agree with this audit.

**The full dataset is structurally similar: the same nine sources, the same seven asset formats, identical README, and the same five JSONL fields and five observed answer types.** CubiCasa still has exactly the same 12 question categories, each in English and Finnish. The main additions are scale, more models/projects, and broader BIM tasks.

| Measure | Preview | Full |
|---|---:|---:|
| Asset files, excluding licence documents | 910 | 16,891 |
| Asset bytes | 722,493,648 | 12,225,645,628 |
| Same-directory filename-stem groups | 770 | 14,550 |
| Question-answer rows | 7,990 | 127,044 |
| Directly referenced asset paths | 320 | 5,939 |
| Missing referenced paths | 0 | 0 |
| Missing/null or empty answers | 0 | 0 |
| Identical duplicate JSONL rows | 0 | 0 |
| Conflicting answers for identical path and question | 0 | 0 |

All full JSONL rows parse successfully. No non-finite numeric answers or negative numeric answers were found. No Unicode replacement characters were found in the JSONL string fields. These checks do not establish the correctness of every reference answer.

## Sources and coverage

| Source | Full files | Full questions | Referenced files | Change that matters |
|---|---:|---:|---:|---|
| CubiCasa | 4,787 | 85,514 | 4,787 | Same 12 count tasks; sparse per-category coverage remains |
| Swiss Dwellings | 3,120 | 37,584 | 1,040 | 1,040 plans, each in PDF/DXF/PNG; same task families |
| IFC models | 1,247 | 3,062 | 84 | 533 IFCs, 500 PNGs, and 107 PDF/SVG pairs; broader model domains |
| IFC-Bench | 30 | 820 | 25 | More architectural, engineering-system, structural, and town-scale questions |
| Opening Design | 1,006 | 64 | 3 | Many more assets, exactly the same question set |
| Europeana | 1,085 | 0 | 0 | More unlabelled drawings |
| Finna | 1,800 | 0 | 0 | More unlabelled drawings |
| HABS | 1,506 | 0 | 0 | More unlabelled drawings |
| Wikimedia | 2,310 | 0 | 0 | More unlabelled drawings |

CubiCasa and Swiss Dwellings account for 96.89% of the question rows. File coverage is not the same as class coverage or independent-example coverage: formats and translations repeat the same underlying information. Counting alternate extensions with the same filename stem raises question coverage from 5,939 to 8,088 files.

| Format | Preview | Full |
|---|---:|---:|
| PNG | 306 | 6,327 |
| JPEG | 374 | 6,566 |
| PDF | 122 | 1,825 |
| DXF | 66 | 1,049 |
| DWG | 18 | 271 |
| IFC | 14 | 611 |
| SVG | 10 | 242 |

The answer-type distribution is 111,763 count, 14,243 area, 836 text, 138 volume, and 64 length. There are still no `other` rows. IFC-Bench contributes 820 of the text rows, including numeric and multi-part answers encoded as text.

## New or expanded task domains

- **Electrical and lighting:** light-fixture counts now appear in the quantitative IFC-model questions. For example, the clinic electrical model has a reference count of 1,120 lights. IFC-Bench also asks for switches, distribution boards, circuits, cable/conduit components, and electrical properties.
- **Heating, plumbing, and ventilation:** component counts, pipe lengths, system types, radiators, valves, air terminals, ducts, and related properties. A mechanical-only model should not be expected to contain the architectural rooms, doors, or walls.
- **Structural and material questions:** concrete/insulation quantities, load-bearing properties, material compositions, and dimensions. Some requested information is absent or only estimated in the references.
- **Town-scale geometry:** `ifc_bench/ettenheim_gis_city.ifc` has questions about buildings, gates, fountains, roads, distances, and the area inside a town wall. Its reference says residential interiors are not modeled.
- **Infrastructure assets and IFC 4.3:** a Chesapeake Bay Bridge-Tunnel model is present, including a light-fixture question. Two distributed files declare `IFC4X3_ADD2`, alongside 71 `IFC2X3` and 538 `IFC4` files. Include this schema in parser compatibility checks.

These are broader domains rather than new file formats. The basic CubiCasa category vocabulary has not expanded.

## Problems and implementation traps

### 1. Class coverage is still incomplete

CubiCasa has 4,787 images, but only 3,519 have door-count questions, 2,960 bedroom-count questions, and 1,462 balcony-count questions. That leaves 1,268, 1,827, and 3,325 missing per-image task labels respectively. Windows and storeys have questions for every image. Explicit zero answers also exist, so an absent question must continue to mean unknown, not zero.

The CubiCasa folder still contains PNGs without the upstream polygon annotation SVGs. More images and count answers do not turn this into a complete instance-detection training set.

### 2. Stairs and other assemblies require parent/child reasoning

The strongest concrete example is Molio:

- The IFC contains **579 `IfcStair` occurrence records**.
- Their name prefixes are 275 `RISER`, 274 `TREAD`, and 30 `[L]AF`.
- **564 occurrences are aggregated children** of other objects.
- **15 are top-level stair assemblies**, directly associated with spatial containers.
- The whole-model stair reference answer is **15** (full JSONL line 87309).

Following `IfcRelAggregates` and spatial-containment records reconciles this answer exactly. Simply counting every object of class `IfcStair`, or merely dropping names beginning with RISER/TREAD, does not produce the intended answer. This is a granularity problem rather than evidence that the reference answer is wrong. It matters for walls, stairs, and other assemblies with separately rendered parts.

### 3. An SVG class attribute can contain multiple tokens

Many full-dataset SVG groups use values such as `class="cut IfcDoor"`. Exact string matching against `IfcDoor` incorrectly reports zero. Split the class attribute on whitespace, or use an equivalent class selector.

After accounting for this, a screen of **195 English per-floor count questions** against corresponding SVG object groups gives **181 matching raw counts and 14 differences**. The remaining differences concern Molio walls/stairs and TU Wien walls/stairs. These are candidates for assembly/rendering investigation, not 14 proven incorrect answers. For example, a top-level stair assembly may have no shape of its own while its children are drawn under other classes. The complete list is in `full_dataset_quality.json`.

All 107 IFC-derived SVGs parsed successfully, have object groups with GUIDs, and have no repeated GUIDs within an individual SVG.

### 4. The 500 ResBIM IFCs have no explicit room spaces

All **500** `resbim-*_model.ifc` files lack `IfcSpace` records. Most contain wall, door, and window geometry, so this does not make all of them empty or unusable. It means room-count/room-area questions cannot be solved by enumerating stored spaces in these models; rooms would need to be inferred geometrically or obtained elsewhere.

`resbim-388_model.ifc` remains an empty building hierarchy without product-definition shapes. No full-dataset question rows reference any ResBIM model. The 500 paired PNGs and IFCs should therefore not be mistaken for 500 fully labelled QA examples.

### 5. Whole-model questions can still point to one floor PDF

The Esplanades question asking for 211 doors across the model now points to the **first-floor** PDF (line 86667). The equivalent preview question pointed to the fourth-floor PDF. Its scope is still the entire IFC, not the single visible sheet. Resolve the source model and the scope from the question.

All preview question/answer records are present in the full collection when path is ignored, but **866 preview rows have different paths**, all from `ifc_models`. Do not use a preview/full merge as extra independent data, and do not assume paths are stable question IDs.

### 6. Exact model duplicates occur across source folders

SHA-256 checks found **eight pairs of byte-identical IFC files** across `ifc_bench` and `ifc_models`, including Molio, FZK-Haus, the institute, Smiley West, and four DigitalHub discipline files. Keep duplicate files and the same project in the same evaluation partition. Source-folder separation alone does not prevent leakage.

### 7. A reference answer disagrees with distributed file metadata

At full JSONL line **85820**, the Ettenheim answer says the model uses **IFC2X_FINAL**. The distributed file's `FILE_SCHEMA` declares **IFC2X3**. This is a concrete metadata discrepancy to retain for manual review or organizer clarification; it should not become a reason to invent an incorrect schema when answering from the file.

More generally, a keyword screen of text references finds 108 answers mentioning unavailable information and 54 mentioning estimates, approximations, or assumptions. These are heuristic counts and can overlap. Distinguish missing-information responses and estimates from exact quantity tasks.

## Improvements over the preview

The missing FZK-Haus source IFC is now present. Its related IFC-Bench copy is byte-identical. Many more rendered plans and associated source models are available, making model/floor resolution easier. The same ResBIM empty model and intentionally bad/test IFC exports remain; two Opening Design files are explicitly in a folder named `bad IFC models - for autopsy only`.

## What this means for the team

The existing library choices still fit the supplied formats. Prioritize the heavily represented CubiCasa/Swiss count and area tasks, then add IFC queries with explicit spatial scope and parent/child handling. Use model GUIDs and SVG object groups for evidence, while retaining enough IFC hierarchy to trace parts back to assemblies. Keep ResBIM room inference, mechanical systems, and town/infrastructure reasoning as explicit capabilities rather than assuming every IFC is a conventional complete building.

This audit examined all question records, IFC entity inventories, selected IFC relationship graphs, and IFC-derived SVG metadata. It did not formally validate every IFC against its schema, calculate every model's geometry, or visually verify every reference answer. The raw class-count differences are therefore review candidates, not a blanket assertion of bad ground truth.

Reproduce the main structural audit with `python dataset_audit.py junction-dataset --output full_dataset_audit.json`. Additional comparison, assembly, duplicate-file, and SVG results are preserved in [full_dataset_quality.json](full_dataset_quality.json).
