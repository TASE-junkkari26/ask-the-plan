# Capped Gemini IFC validation — 15 November 2026

**Authorized by the user; execution pending final checks.** This selects 12 remaining
representative families, not a dataset-wide accuracy run. The prior permission
covered two cases and six external requests, all now spent; see the
[authorization and live-run record](IFC_IMPLEMENTATION_VERIFICATION.md#live-planner-findings-and-unfinished-acceptance-work).
The user separately approved the additional export and maximum **24 external
request starts** described here on 15 November 2026. That cap includes errors,
discovery, repair and resumed attempts.

Selection used literal task inputs, current source/executor code and existing
source audits. No supplied reference-answer values were looked up to prepare
this batch. Input `questions.jsonl` SHA-256:
`0e6322c74561a63f42bac35f5c1be8a2c6a37516b14a81e66ab88b74950a6d1f`.
The selection is exactly 12 rows, 12 reviewed families and eight source paths.
Already exercised live cases 85527 and 85633 are excluded.

## Cases and source review

Paths below are relative to `dataset/junction-dataset/`. Each item names the
complete literal question and the native evidence to inspect after its prediction
is saved. No numeric answer target is supplied to the planner.

1. **85531 — Volume / Insulation**  
   Source: `data/ifc_bench/4351_arc.ifc`  
   “What is the total volume of insulation material needed for exterior walls that have insulation material in their structure?”  
   Check exhaustive wall membership and typed `IsExternal` values; use literal
   material names discovered in native assignments. Inspect occurrence/type
   overrides, ordered layers, declared units and `material_quantity` allocation
   proof. Layer allocation needs a verified uniform prism with compatible actual
   and specified thickness/offset. Unresolved hosts prevent a complete total;
   any supported subtotal must remain an explicit lower bound. A source-proved
   nonmatching assignment is distinct from unknown material coverage.

2. **85535 — Property / Door fire ratings or rating availability**  
   Source: `data/ifc_bench/4351_arc.ifc`  
   “Which door types have fire rating information?”  
   Resolve used native type IDs from door occurrences, rather than counting type
   definitions or merging identical type names. Inspect original fire-rating
   properties and type/occurrence provenance; an occurrence override does not
   establish its type's rating. Preserve literal ratings and distinguish present,
   explicit-null, absent and unresolved properties. A search sample is not the
   full used-type inventory.

3. **85547 — Area / Exterior facade surface**  
   Source: `data/ifc_bench/4351_arc.ifc`  
   “What is the total surface area of the facade?”  
   Check exterior occurrence selection and the requested area basis before
   accepting a total. Inspect units, geometry method, retained openings and
   unresolved objects. The supported `net_opaque_face` method measures one
   verified opaque wall face; it does not establish complete gross facade or
   glazing area. Do not substitute footprint or the sum of all mesh faces. A
   qualified subset/clarification is preferable to an unsupported complete total.

4. **85553 — Inventory / MEP systems and components by category, space or level**  
   Source: `data/ifc_bench/4351_arc.ifc`  
   “What are the specific MEP system names and their corresponding types present in the building?”  
   Inspect exhaustive native system occurrences, literal names and recorded
   class/`PredefinedType`/type properties. Keep system instances, type definitions
   and assigned components distinct. Missing modeled systems or type fields must
   be supported by source/extraction coverage; they do not establish that the
   physical building lacks MEP systems. Do not infer a system type from its name.

5. **85561 — Inventory / Rooms and spaces with areas, optionally heights or functional groups**  
   Source: `data/ifc_bench/ac20_arc.ifc`  
   “What is the space distribution by level with areas and primary space functions with percentages?”  
   Review every requested part: native space membership, effective storey ID,
   source-recorded function, area basis and percentage denominator. Preserve
   literal function labels and explicit unclassified rooms; do not infer room
   functions from names. Authored room areas and represented footprints cannot
   be mixed silently. Each ratio needs its source-derived numerator/denominator
   and units. If the available operations cannot join all required quantities
   and groups, name those parts in `unanswered_parts` rather than invent a join.

6. **85691 — Inventory / Slab types, quantities and thicknesses**  
   Source: `data/ifc_bench/digital_hub_arc.ifc`  
   “Could you provide a breakdown of all slab types in the building with their quantities and percentages, and include any available thickness information?”  
   Check occurrence counts grouped by native type ID, including missing or
   ambiguous type assignments. Percentages must use an explicit complete
   occurrence denominator. Inspect thickness properties/layer inputs with their
   original units and specified-versus-measured basis; preserve conflicting or
   unavailable thickness values. Counts, percentages and available thicknesses
   must each be returned or explicitly marked unanswered.

7. **85789 — Derived / Structural embodied carbon**  
   Source: `data/ifc_bench/duplex_arc.ifc`  
   “What is the estimated embodied carbon of the structural elements, including a detailed breakdown by material type, the methodology and assumptions used in the calculation?”  
   Check the source-grounded structural selection, material assignments and
   compatible quantity bases. A carbon result needs native factor values,
   provenance and compatible units, plus density if its calculation requires
   volume-to-mass conversion. Existing source audits identify missing factors;
   verify actual field/assignment coverage rather than accepting top-k absence.
   Never insert Gemini's generic material factors or defaults. An explicit
   missing-information/unsupported outcome is valid evidence of a limitation;
   it is not successful carbon calculation. Do not add an unasked count as filler.

8. **85801 — Property / Wall materials and construction layers**  
   Source: `data/ifc_bench/duplex_arc.ifc`  
   “Could you provide a detailed breakdown of the external wall construction, including all layers, their materials, and thickness measurements?”  
   Inspect source-backed external membership and effective native material
   assignment per used wall/type, including occurrence overrides. Retain ordered
   layers, original material names, thickness units and assignment anchors.
   Specified layer thickness is not automatically measured body thickness;
   missing layers/materials and multiple conflicting types remain explicit.

9. **85825 — Spatial / Highest-ground buildings and location**  
   Source: `data/ifc_bench/ettenheim_gis_city.ifc`  
   “Which building(s) stand on the highest ground elevation, and in which part of the town are they located?”  
   Check native `ElevationOfTerrain`, its units, complete building membership
   and all equal highest values (`include_ties`). Missing elevations cannot be
   ignored when claiming a global maximum. Town-part identification separately
   needs source address/district data or an established georeferenced spatial
   basis; mesh minimum Z, local XY direction and a building name are insufficient
   substitutes. A valid highest-building output may be retained with the town
   part explicitly unanswered and the overall response partial.

10. **86080 — Ranking / Door widths, extrema, top-k or statistics**  
    Source: `data/ifc_bench/hitos_arc.ifc`  
    “Could you please provide the names and widths of the five largest types of door (by width) used in the building? Could you also provide the average door width and the range of door widths?”  
    Review used native type identity, source width properties and converted
    units. Conflicting occurrence widths do not establish one type width.
    Inspect the cutoff/tie policy and all tied rows, rather than an arbitrary
    five-record truncation. Check mean membership/denominator and minimum/maximum
    calculation inputs separately; state whether statistics count occurrences
    or distinct types. Missing widths cannot silently disappear from a claimed
    complete average. Cover all three requested results or name the omissions.

11. **86261 — Connectivity / Plumbing network ports and integration**  
    Source: `data/ifc_bench/sixty5_plumbing.ifc`  
    “Could you provide a comprehensive analysis of the plumbing distribution network connectivity, including the connectivity rate and network integration metrics?”  
    Check exhaustive native distribution ports plus a separately selected
    physical component denominator. Inspect `has_port`/`port_connected_to`
    anchors, deduplicated undirected edges, cut connections, owner coverage and
    the graph-content hash. Keep the induced port graph and owner-component
    graph distinct; do not invent internal flow through a component. Include
    portless selected components in the stated integration denominator. Preserve
    zero-denominator unknown ratios and any scope/work-budget non-answer.
    The existing large-source audit exercises native execution, not this live
    interpretation. Its substantial evidence response remains local.

12. **86379 — Count / Doors** (`type=count`)  
    Source: `data/ifc_models/bsc-clinic_clinic-architectural.ifc`  
    “How many doors are there in the model 'Medical-Dental Clinic - architectural'?”  
    Resolve the descriptive title against current source metadata before
    accepting a count. Its native identity remains `UNKNOWN` in the conservative
    grammar; the selected upload/hash stays authoritative and cannot be switched.
    If bounded inspection cannot justify the alias, request clarification.
    Otherwise require the complete native door-occurrence set, counting grain,
    exclusions and source anchors. A clarification is recorded as unanswered for
    numeric grading, not converted into zero or an unrelated model's total.

## Exact proposed command and bounds

From the repository root, using the configured backend Python environment:

```sh
python -m experiments.ifc_dataset \
  --live --provider gemini --disable-fast-plans \
  --line 85531 --line 85535 --line 85547 --line 85553 \
  --line 85561 --line 85691 --line 85789 --line 85801 \
  --line 85825 --line 86080 --line 86261 --line 86379 \
  --scope model --thinking-level high \
  --max-calls 24 --max-model-requests 2 --max-inspections 6 \
  --deadline-seconds 300 --run-deadline-seconds 3600 \
  --output build/ifc-live-next12-20261115-review01
```

The proposed output directory did not exist when this plan was prepared.
Use only the approved cumulative cap. The evaluator groups source
uploads and parses models sequentially. Whole-model evaluation is explicit;
question-defined room/floor restrictions remain in the plan. This does not alter
the interactive viewer's captured-view default. Disabling optional native
grammar exercises Gemini planning; mandatory source/scope guards still apply and
can legitimately return a zero-call clarification.

The **24-start cumulative global cap** covers all 12 rows, discovery rounds,
schema repair, errors and resumed attempts. Each question permits at most two
model requests and six local discovery actions under one 300-second deadline;
the active attempt stops after 3,600 seconds. Reaching any limit must retain the
selected-row denominator and record unresolved/unattempted rows. No extra repair
allowance, SDK transport retry, Nemotron fallback, alternate model or alternate
destination is authorized by this proposal.

Source `search`/`properties` pages accept integer `offset` 0–1,000 and at most 20
records. Follow the returned `next_offset`, which advances by records actually
retained after the 24,000-character response budget, rather than assuming a full
20-record page. Facets have independent per-property cursors and `next_offsets`;
continue each property separately. Pages consume the same six-action budget.
Keep query, property/concept filters and captured source/scope unchanged while
following a cursor. `unpageable`, unknown `matching_total`, omitted source facts
or an exhausted action/offset budget prevent claiming complete discovery.
Oversized values are never clipped into invented identifiers or silently skipped.

The external destination is the configured Gemini model through the
[existing backend transport](../gemini/client.py) at
`https://generativelanguage.googleapis.com/v1beta/interactions`. Export is the
literal question, instructions/schema and bounded IFC-derived catalog/discovery
metadata: source labels, identifiers/native locators, selected property/material
values, units and available source location metadata. Original IFC bytes stay
in the local production API/executor; no raw IFC upload, image, reference answer,
credential or `.env` content is sent to Gemini. Unrelated image transports remain
disabled. Requested/returned model IDs and actual usage must be recorded.

**Estimated monetary cost is unknown:** no applicable tariff was supplied.
Twenty-four request starts bound attempts, not dollars or a guaranteed token
total. Preserve missing usage as unknown; do not infer zero billing from a
rejected or interrupted request.

## Persistence, resume and assessment

Use the [production evaluator](../experiments/ifc_dataset/README.md), which records
source/code/library hashes, exact scope, plans, results, anchors/calculation
inputs, usage and timing. Atomic per-row predictions must be saved before
reference import/grading. Source assets and supplied QA stay read-only. Do not
change runtime code, sources or settings during the batch; a changed-code flag
prevents presenting it as a frozen measurement.

To resume an unchanged, safely interrupted run, repeat the exact command with
`--resume` appended and retain `--max-calls 24`. Recorded predictions, including
errors and non-answers, are reused. Never reset the cap by selecting a fresh
directory, increasing the cap or rerunning a saved case. If a call start lacks a
saved prediction, stop for review: its outcome/billing is unknown and it remains
spent. Do not automatically replay it. Changed source/code/settings identity also
requires review, rather than bypassing the evaluator's resume check.

After predictions are durable, grade the one quantitative count only if it is
complete and exact. The other 11 rows remain `ungraded_text` for accuracy:
independently inspect every requested part against native facts/calculations,
scope, units, membership and complete-versus-partial coverage. An explanation,
schema pass, successful status or keyword match is not correctness. Confirm
source absence independently before accepting a missing-information finding;
`unanswered_parts` records an unhandled request, not proof of source absence.

Produce a reviewable summary without more inference:

```sh
python -m experiments.ifc_dataset.summarize \
  build/ifc-live-next12-20261115-review01 \
  --write build/ifc-live-next12-20261115-review01/SUMMARY.md
```

Review all 12 outcomes, failed/partial/unanswered parts, code-change flags and
the cumulative call ledger before proposing any further run. This plan makes
no execution or accuracy claim.
