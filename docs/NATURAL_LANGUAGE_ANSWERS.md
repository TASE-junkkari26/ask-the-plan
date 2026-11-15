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
Counting instructions stay attached to their question; separate requested
outputs retain separate parts. Literal quoted identifiers are not split.
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
| Visual observations | Existing selected analyzer/detail tools, candidate counts and bounded visual identifications with literal labels and source anchors | Partial estimated observations; visual size/ranking is unverified, empty scans do not prove zero, and candidates do not prove lower bounds or measurements |
| Native PDF lookup | Server-owned Node/PDF.js worker, original spans and mapped display anchors | Repeated literal identifiers require clarification; strings remain source quotations |
| Native PDF schedules | Anchored headers/panel extents, row/cell identity, filters, imperial units, row multiplication and sums/extrema | Aggregates remain partial until independent semantic table/assembly coverage is established |
| Calibrated geometry library | Validated polygons, holes and union/difference with source calibration | Callable library; automatic drawing-to-room extraction remains unimplemented |

The fixed PDF worker needs the installed frontend `pdfjs-dist` dependency and
Node 22.12+. Follow the [startup instructions](../README.md). It runs with
execution/output bounds and registered paths; browser spans are not native facts.

Native PDF tool planning reuses the planner selected by `IFC_API_PROVIDER`.
Direct literal lookup can finish locally. Other supported native questions make
one bounded proposal call per part with extracted source spans to select lookup
anchors or schedule headers, filters and operations. The host validates the
proposal, reads the native values and executes arithmetic locally. This planner
choice is independent of `IMAGE_API_PROVIDER`, which selects visual analysis.

## Budgets and presentation

The common request owns a default 180-second deadline and at most 15 external
attempts. IFC retains three planner/discovery calls and six source inspections
across its outputs. Detail scans retain nine provider attempts by default; the
existing tool's explicit maximum remains twelve, plus routing. Native arithmetic
and wording use zero external calls. Failures and unknown usage stay in the ledger.
Question-wide token/spend limits still need measured live baselines.

The drawing UI always requests Detailed scan. The common answer coordinator uses
the same automatic panel selection and native tile mode as the existing detail
client, including door reading resolution and bounded optional OpenCV window
checks. Native PDF answers can finish before visual analysis is needed.

The answer panel leads with concise answers and their qualifications. Source
buttons select drawing regions or original IFC objects. Technical issues, scope,
members, calculations, usage and source identity stay in collapsed details;
the export retains the complete response. Known call costs use the same recorded
model/timestamp tariffs as the candidate panel, while unpriced or unreported
calls retain an unknown total. Structured values, members and calculations
paginate without truncating export. DXF exports
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
and geometry extraction; provenance-backed drawing-to-IFC links; orientation and
compliance executors; and measured live family/language/latency/cost outcomes.
The [IFC engine](IFC_ENGINE.md) now includes row-wise table calculations, modeled
walking routes and recorded port-network metrics. These bounded operations still
need broader source/family validation, including their partial and estimated
outcomes. An unsupported answerable family remains an implementation gap.

See [verification](VERIFICATION.md) for actual checks and limits. Schema checks,
synthetic UI tests and native extraction success are not model-answer accuracy
or proof of complete inventories.

## Concise answer presentation check — 15 November 2026

Windows, Python 3.14.10 and Node 24.22.3: 106 focused backend tests and 145 frontend
tests passed. Checks cover estimated visual identifications, refusal to invent
measurements or promote candidates to exact/lower-bound facts, counting-rule
preservation, cost-ledger unknowns, and concise presentation without discarding
source evidence. Component server rendering checked a saved response with more
than 20 members: details start closed, source controls remain available, and
member/source data are retained. Production build passed with existing SDK/chunk
warnings; local Markdown links and diff whitespace passed.

The backend was restarted and frontend/proxy/module health checked. No paid
inference or new model-accuracy evaluation was performed. Computer Use ended
before browser verification because URL policy enforcement is unavailable for
the current Windows browser; no interactive browser/layout pass is claimed.
