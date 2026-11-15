# IFC implementation verification — 15 November 2026

This is a development record, not a dataset-wide accuracy claim. The acceptance
inventory remains [1,188 direct IFC rows, 198 families and 40 source paths](IFC_QUESTION_COVERAGE.md).
The 2,694 paired-PDF rows remain a separate scope-sensitive cohort.
Post-merge checks are recorded separately in the
[origin-first integration verification](VERIFICATION.md#origin-first-ifc-integration-15-november-2026).

## Implemented and exercised

- Typed scalar arithmetic and table calculations, including percentages and
  consecutive storey elevations, retain calculation inputs, units and source
  evidence. Unknown inputs and zero denominators cannot become exact totals.
- Native occurrence context preserves type, storey and building identity;
  material facts preserve ordered layers and literal material names. Multiple
  native types remain explicit rather than selecting an arbitrary first type.
- Large sources use deferred property materialization with per-question work
  limits. Request-only facts and proof anchors are cleared between questions;
  complete native property vocabulary is distinct from materialized values.
- Counts and supported exact quantity grammar can execute with zero model
  requests. Other questions retain the shared ceiling of three model requests,
  six inspections and one deadline. No supplied QA answers enter runtime logic.
- Geometry measurements retain source hashes, native objects, representations,
  frames, method, tolerance and quality. A represented room footprint remains
  distinct from an author's stored room-area computation.
- Port connectivity uses recorded native connections and owner relationships.
  Geometry or system membership alone cannot establish a connected port graph.
- Material quantities prefer explicitly recorded homogeneous net quantities or
  require a verified uniform layered prism. Unknown hosts remain unresolved;
  a known subset cannot become a complete insulation total.
- Enclosed area extracts genuine bounded projected regions with requested wall
  support and explicit closure objects. It adds no hulls or artificial gap fill.
- Model-only context aliases shorten entity references and replace repeated
  metadata proof UUIDs with native locators. Public facts, anchors and canonical
  IDs remain unchanged; only aliases actually exposed during this question can
  resolve. Gemini filters travel as JSON strings and pass the complete typed
  validator after decoding, replacing opaque native filter objects.
- The route evidence panel shows the source XY path projection and source-world
  XYZ coordinates. Its displayed distance includes stair rises. Full coordinates
  remain in the export, and source frame/partial qualifications remain explicit.
- Native cancellation drains active source work before releasing its scope gate
  or deleting the file. Idle large sessions retire before replacement parsing.
  Large HTTP responses use gzip; evidence exports retain their full contents.

## Actual source observations

The following artifacts are generated under ignored `build/` or `/tmp`; they
are local development evidence and are not shipped as immutable benchmarks.

| Check | Observation | Qualification |
| --- | --- | --- |
| All 292 direct quantitative room/floor-area rows | All answered within the supplied 2% tolerance, zero external requests | Estimated represented-space footprints; source membership remains a separate review. Code changed during the run. `build/ifc-fast-area-292-api/report.json`. |
| Duplex A102 | 27.660089 m² represented footprint, versus 30.14164525 m² authored Revit room area | Values have different computation bases; the dataset reference agrees with the footprint. |
| Real Firefox import/question/export | Duplex rendered; A102 footprint and subsequent door count used deterministic zero-inference plans; evidence export and retained answer while typing worked | One browser/model flow, not every question or GPU. `build/ifc-native-area-browser/report.json`. |
| Real Firefox route panel | Native farthest-route grammar, zero planner requests; 8 source path points, 19.6451906868 m physical length and matching XYZ/export | Partial modeled path; six path objects marked. Source hash and zero browser errors verified. `build/ifc-route-browser/report.json`. |
| Largest supplied plumbing model, about 212 MiB | Production ASGI upload/question/delete completed normally in about 82 s; peak RSS about 3,151 MiB | Fixed plan, zero external requests; complete response was about 89 MB before subsequent gzip integration. `/tmp/ifc-network-api-profile-summary.json`. |
| Formerly rejected RWTH multiple-type model | Opened; native spaces 59, doors 70 and windows 47 were counted | Ambiguous type semantics still produce an unresolved outcome. |
| Town inner enclosure | 58,464.97919038182 m², estimated, source/result validation passed | Inner-face projected region with one supported region and explicit gate/tower closures; not a manual centerline land-area measurement. `/tmp/ifc-town-enclosure-engine-proof.json`. |
| Duplex literal insulation assignments | Known allocation subset 7.7735434 m³; four matching hosts unresolved | Correctly partial. Cannot claim a complete insulation requirement. `build/ifc-material-quantities-smoke.json`. |
| Initial planner-context size | Duplex 79,715→64,498 bytes; clinic 107,301→85,263 bytes | About 19–21% less JSON payload; excludes system/schema text and is not a token or billing measurement. `build/ifc-planning-context-size.json`. |

The material-factor scan of the inspected actual models found no native density,
conductivity or embodied-carbon factors sufficient for the corresponding
calculations. Literal material specifications remain available. This does not
justify inserting generic defaults or claiming every dataset source lacks them.
See `build/ifc-material-source-factors.json`.

## Regression checks and platform

The complete offline Python suite passed **613 tests** in 54.6 seconds after
material/enclosure/context changes, before subsequent route and named-room guard
integration. A separate 64-test API/provider/context batch passed, including
compact inspection aliases followed by canonical public evidence export.

Reported platform: Linux, Python 3.14.10, IfcOpenShell 0.9.0.post1, Shapely 2.2.0.
The working backend environment is separate from the absent checkout `.venv`.
Async/socket/thread checks ran outside the restricted sandbox with provider
keys blanked. Restricted-sandbox event-loop shutdown hangs were reproduced
independently; an unrestricted production ASGI profile exited normally.

Frontend checks passed again after the route panel: **18 test files** and the
production build (21.14 seconds), using Node 26. Firefox 160 verified both source
flows above. The build retained existing optional Three WebGPU export and
chunk-size warnings. All 12 generated contracts and Markdown links are current.
The later complete 658-test Python run passed 657 and exposed one obsolete
catalog expectation that routes were unsupported; that assertion was updated
to match the implemented capability. A final suite run remains necessary after
in-progress geometry helpers settle.

## Live planner findings and unfinished acceptance work

Recorded live development runs used explicit cumulative request caps. Reports
retain usage, latency, status, source hashes and predictions before reference
grading. `build/ifc-live-hard-families-r3` used 17 requests across seven questions,
with 1,125,901 reported prompt tokens. It returned one answered, one partial,
one missing-information and four clarification outcomes. Text accuracy remains
ungraded. These statuses must not be counted as seven supported questions.

That run exposed two defects: opaque predicate objects repeatedly failed the
local discriminator check, and an adjacency proposal omitted its named-room
filter and selected all spaces. A finite nested decoder was rejected by Gemini
in both follow-up requests (`build/ifc-live-typed-predicates-r4`), without returned
usage or an answer. Filters now travel as JSON strings and face full local typed
validation. The narrow source-identity guard rejects an ignored uniquely named
room before execution and permits bounded repair. These checks do not prove
all live interpretation failures are resolved.

The JSON-filter follow-up (`build/ifc-live-json-filters-r5`) returned answered
results for both selected cases with three external requests, 129,757 reported
prompt tokens and 7,253 completion tokens (including 6,091 thought tokens):

- Line 85527 used original `PSet_Revit_Dimensions.Volume` and typed
  `Pset_WallCommon.LoadBearing`, preserving the recorded modeled basis. It
  returned 31.4836525 m³ load-bearing and 591.8392666 m³ other walls, with
  5.0509377% load-bearing. Their sum, 623.3229192 m³, and percentage agree with
  the rounded reference values read after predictions were persisted.
- Line 85633 bound only room `1B07` and returned `1BC2` (`CORRIDOR`). A separate
  direct IfcOpenShell inspection confirmed native door `#1339` has physical
  room boundaries for exactly `1B07` and `1BC2`; the supplied reference agrees.

These two targeted source reviews do not grade the remaining text cohort. Both
questions also have source-bound deterministic grammar paths exercised
separately with zero inference, along with type inventories and the corrected
named-room adjacency query. Those grammar results do not replace the forced
external-planner checks above.

Automatic approval review initially rejected follow-up Gemini checks pending
specific authorization to send IFC-derived context to that external destination.
The user subsequently authorized the two checks with a six-request cumulative
cap. The first rejected command sent no request. Two schema-rejected calls,
three successful follow-up calls, and one final same-case schema check used
all six requests. The final line-85633 check returned `1BC2` again with the
current route/tie/compound-part schema, using one request and 42,994 reported
input tokens (`build/ifc-live-final-schema-85633`). Offline source work continues
independently.

Native walking routes now retain explicit paths through source openings and
stair lines. Actual clinic estimates are 18.2045 m from `1E12` and 8.1573 m from
`1E23`; a sampled Duplex maximum is about 19.6452 m, while an unconnected roof
room remains unresolved. These are partial potential routes; actual clear width
and certified emergency-exit status remain unknown. See [route methods and bounds](IFC_ROUTE_PLAN.md).

The broad offline production sweep exposed an initial-discovery bug: valid
questions longer than the search tool's 200-character limit returned an internal
error. Initial search now uses a bounded whole-token prefix and exposes its
truncation; the complete original question still reaches the planner. A token
that alone exceeds the tool limit skips initial search with unknown match count,
preserving the distinction from zero. Targeted long-question checks pass.

Required remaining work includes orientation/standing-height semantics,
all requested parts of compound questions,
all 198 direct families and 40 upload paths, translated/paraphrased variants,
view/empty/hidden-floor/revision scope cases, paired-PDF scope, and independent
source review of free-text/numeric multipart answers. Source absence must be
established from extraction coverage, not inferred from a top-k search or a
planner's non-answer. Existing reference disagreements need source adjudication.

The evaluator deliberately keeps `all_questions_supported=false` while those
acceptance checks are incomplete. See [evaluation procedure](../experiments/ifc_dataset/README.md)
and [required family inventory](IFC_QUESTION_COVERAGE.md#completion-and-evaluation-gates).

## Source-backed implementation probes, 15 November 2026

The [generated inventory](IFC_QUESTION_COVERAGE.md) records the starting capability audit; it is not a current
pass/fail classification for every family. The reusable evaluator in
[`experiments/ifc_dataset`](../experiments/ifc_dataset/README.md) now runs the
production upload/question API, persists predictions before importing references,
and supports a hard zero-external-call budget for native grammar checks.

Observed local Linux results, using IfcOpenShell and the production executor:

- All 292 supplied Duplex/Clinic quantitative room/floor-area rows answered using
  estimated modeled IfcSpace footprints: 287 individual rooms and five floor
  sums. All agreed numerically within the dataset's 2% tolerance, reported as
  `numeric_agreement_estimated`. This does not independently grade room
  membership or semantic interpretation. Runtime code changed during that sweep,
  so it is development evidence rather than a frozen benchmark.
- Line 85521 produced source elevation differences between consecutive storeys,
  grouped by native building identity. Arithmetic stays in the engine; repeated
  elevations or incompatible source units remain executor outcomes.
- Lines 85540, 85633, 85634 and 85759 executed native room topology with zero
  external calls. For 85633/85634 only the explicitly named room `1B07` is the
  subject: its recorded door connection and its boundary neighbors stay distinct.
  Shared-wall candidates without geometric verification remain partial in
  regression fixtures; missing boundaries cannot establish physical zero.
- Lines 85522/85523 produced occurrence counts by native type ID/name; distinct
  types with the same source name remain separate. Line 85527 grouped literal
  source-stored wall `Volume` by boolean `Pset_WallCommon.LoadBearing` and computed
  percentages from those sums. The generic stored quantity retains `modeled`
  basis; it is not relabeled net volume. Missing quantities/classifications
  prevent a complete percentage.

The consecutive-height and seven Bench probes above remain `ungraded_text`;
valid source anchors and a successful executor status do not establish that every
free-text requirement was answered correctly. Their ignored local records live
under `build/ifc-fast-height-api-smoke`, `build/ifc-fast-topology-api-smoke` and
`build/ifc-fast-inventory-volume-api-smoke`; the area sweep is
`build/ifc-fast-area-292-api`. Every run records the source hashes and actual plans.

Model-facing context now uses scope-local native STEP aliases only in typed
operational entity-reference slots. Decoding requires the alias to have appeared
in the question's catalog/discovery rounds. Original text/native GUIDs/property
keys and public proof UUIDs remain literal. Bounded initial payload measurements
on the fixture, Duplex and Clinic catalogs reduced UTF-8 JSON bytes by 21.78%,
19.09% and 20.54% respectively; these are payload-size measurements, not token
or model-quality benchmarks. The named-room intent guard rejects an output that
ignores a unique explicit source room, including an unfiltered all-room query or
an OR branch that can leak other rooms. It is a narrow binding check rather than
a general proof of natural-language correctness.

The broader native-only production run subsequently recorded **all 1,188 direct
rows across all 198 families and successfully opened all 40 source paths**.
No provider configuration/client was loaded; external calls and unattempted
rows were both zero. It produced 356 answered and seven partial native results
across 22 families. The remaining outcomes were 818 explicit external-planning
budget blocks and seven initial-discovery failures caused by questions longer
than the tool's 200-character search limit. All seven failures were then rerun
on their actual sources after bounded initial-query handling: none returned an
internal error, and each reached the expected zero-call planning-budget block.
The complete question remains intact. All four supplied route/width questions
also ran locally in that follow-up and returned qualified partial route results,
including source XYZ points and distinct nominal/geometric/unknown clear widths.

That broad run again obtained 292 estimated-area agreements and 12 exact count
agreements; 64 counts initially needed planning. A separate 64-row count rerun
then obtained **50 further exact numerical agreements** using only source-derived
model identities and conservative German/English grammar. Across these
development runs, **62 of 76 direct count rows** therefore agree at zero external
calls. The remaining 14 `Medical-Dental Clinic` display titles are not established
by the literal native project/building/file identities and remain unresolved;
they are not silently rebound to a different model. Alias checks preserve
discipline/version/variant constraints, including a real native `IFC2SB`
application record for the boundary-enriched source. They contain no QA-title
mapping.

The largest successfully opened source was 326.8 MiB (17,055 extracted objects,
83.05 seconds); the largest object inventory was the 211.8 MiB plumbing source
(71,991 objects, 68.73 seconds). These measurements exercise backend upload and
native extraction, not large-model browser rendering. Reviewable ignored local
reports are `build/ifc-native-all-1188/SUMMARY.md`,
`build/ifc-native-fixes-routes-11/SUMMARY.md` and
`build/ifc-native-count-aliases-64/SUMMARY.md`. Runtime code changed during these
runs, so they remain development evidence rather than a frozen benchmark.
Bench text/source-membership accuracy is still explicitly ungraded.
