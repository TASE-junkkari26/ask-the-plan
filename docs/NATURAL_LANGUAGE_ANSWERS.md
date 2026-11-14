# Source-bound natural-language answers

Implemented 15 November 2026 from the [answer plan](NATURAL_LANGUAGE_ANSWERS_PLAN.md).
This guide describes runtime behavior. The plan's full-family completion checklist
remains the acceptance target, not a statement of achieved accuracy.

## Runtime and evidence

The workbench registers the original drawing and displayed PNG with
`POST /api/v1/sources`, then submits `AnswerRequest` to `POST /api/v1/answers`.
IFC requests reuse `/api/ifc/models` handles. Existing candidate, detail, DXF and
IFC question endpoints remain available. Asking adds no answer-writing call.

`AnswerResponse` binds the question hash, original/display hashes, revision,
page/layout, rotation, PDF.js viewport transform and crop bounds. Each requested
part has an outcome, optional executable plan, `QueryResult` and evidence context.
Deterministic sentences reference claims and anchors. Semantic validation
regenerates their text and rejects changed values, qualifications or snapshots.
Fixed templates cover English, Finnish, German, French, Italian, Swedish,
Spanish, Danish, Dutch, Estonian, Polish and Romanian. Source strings stay literal.

The optional NDJSON response sends the actual analyzer `handoff` followed by one
terminal `result` or `error` using `AnswerStreamEvent`. The candidate stream's
original wire contract remains unchanged. Temporary source sessions use bounded
storage and worker leases; cancellation stops owned workers before cleanup.
Original downloads are attachments; display resources are PNGs.

## Implemented paths

| Path | Behavior and evidence | Boundary |
| --- | --- | --- |
| IFC execution | Whole-model properties, quantities, inventories and bounded native spatial queries; explicit question filters remain in plans | Existing engine coverage and net/gross definitions remain authoritative |
| IFC compound outputs | Shared planning/discovery budget, independent dependency closures, per-part results | Failed independent parts stay visible; failed prerequisites block dependent outputs |
| IFC scalar arithmetic | Decimal add/subtract/multiply/divide, dimensions, conversions and ratios/percent | Unknown inputs, incompatible bases, currency conversion and zero division fail; rounded results are estimated |
| Visual observations | Existing selected analyzer/detail tools and candidate anchors | Nonempty scans are partial estimated observations; empty scans do not prove zero; candidates do not prove lower bounds |
| Native PDF lookup | Server-owned Node/PDF.js worker, original spans and mapped display anchors | Repeated literal identifiers require clarification; strings remain source quotations |
| Native PDF schedules | Anchored headers/panel extents, row/cell identity, filters, imperial units, row multiplication and sums/extrema | Aggregates remain partial until independent semantic table/assembly coverage is established |
| Calibrated geometry library | Validated polygons, holes and union/difference with source calibration | Callable library; automatic drawing-to-room extraction remains unimplemented |

The fixed PDF worker needs the installed frontend `pdfjs-dist` dependency and
Node 22.12+. Follow the [startup instructions](../README.md). It runs with
execution/output bounds and registered paths; browser spans are not native facts.

## Budgets and presentation

The common request owns a default 180-second deadline and at most 15 external
attempts. IFC retains three planner/discovery calls and six source inspections
across its outputs. Detail scans retain nine provider attempts by default; the
existing tool's explicit maximum remains twelve, plus routing. Native arithmetic
and wording use zero external calls. Failures and unknown usage stay in the ledger.
Question-wide token/spend limits still need measured live baselines.

The answer panel shows every part and qualification above the existing evidence
interfaces. Links select drawing regions or original IFC objects. Structured
values, members and calculations paginate without truncating export. DXF exports
also retain the preview's layout/status/warnings/unit metadata in `source_preview`;
those metadata do not calibrate pixels or establish native CAD counts.

## Acceptance gaps

The full dataset is available under the ignored `dataset/junction-dataset/`
directory. Its classifier reconciles 127,044 rows and 234 families. The
[answer experiments](../experiments/answers/README.md) separate offline manifests,
source audits, saved outputs and scoring. Runtime services do not import QA.

All-family completion has **not** been established. Remaining work includes
evaluated visual omission/false-positive protocols and larger inventories;
complete schedule/type-diagram associations; automatic Swiss room/unit membership
and geometry extraction; provenance-backed drawing-to-IFC links; row-wise IFC
derived columns; required route, orientation, MEP and compliance executors; and
measured live family/language/latency/cost outcomes. An unsupported answerable
family remains an implementation gap.

See [verification](VERIFICATION.md) for actual checks and limits. Schema checks,
synthetic UI tests and native extraction success are not model-answer accuracy
or proof of complete inventories.
