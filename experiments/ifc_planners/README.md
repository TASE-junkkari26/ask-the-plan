# IFC planner comparison

Compare production IFC planning/execution using 24 questions on six deterministic
synthetic IFC models. The questions exercise supplied task families: door and
property-filtered counts, distinct exterior doors versus outdoor-access rooms,
native adjacency/connectivity, missing information, conflicts, and exact selected
view versus explicit whole-model scope. English/Finnish paraphrases share the
same model group and split.

This is a bounded regression/comparison tool. The synthetic cases are authored
development fixtures, not independent evidence of supplied-corpus accuracy.
Development/test labels preserve project grouping; viewing and tuning against
all cases does not constitute a held-out model-quality experiment.

## Offline replay

From the repository root, use the configured Python environment with the project
API/test dependencies installed:

```sh
python -m experiments.ifc_planners
```

The default `replay` provider opens no network transport and loads no credentials
or local `.env`. It submits fixed typed query intentions through the same planner
validation, source scope, CPU executor and evidence response path. It does not
interpret the natural-language question. A passing replay validates those fixed
plans and fixture outcomes; it is not a language-model accuracy score.

Runs are written to a fresh ignored directory under
`experiments/runs/ifc-planners/`. An existing output directory is rejected. Choose
another output location or a smaller set with:

```sh
python -m experiments.ifc_planners --output build/ifc-replay-new --cases classified-outside topology-doors partial-combined
```

## Explicit live comparison

Live mode sends the synthetic model's bounded metadata catalog and question to
the selected external provider. It never loads the challenge dataset, and it
does not send raw IFC geometry. It can spend inference calls and provider quota.
Configure backend keys using the [existing setup](../../docs/nvidia_info.md#local-setup),
then explicitly select providers and enable live execution:

```sh
python -m experiments.ifc_planners --live --providers nemotron nemotron-thinking gemini-low gemini-high
```

Provider names select these configurations:

| Name | Configuration |
| --- | --- |
| `replay` | Fixed typed-plan replay; zero external inference. |
| `nemotron` | Current configured Nemotron model/thinking settings, SDK retries disabled. |
| `nemotron-thinking` | Same deployment with thinking explicitly enabled, SDK retries disabled. |
| `gemini-low` | Configured Hydrogen model, IFC thinking level explicitly low. |
| `gemini-high` | Configured Hydrogen model, IFC thinking level explicitly high. |

Both live providers use the same production discovery, proposal validation,
scope, executor and evidence path. Request and inspection budgets follow
`IFC_API_*` settings; Gemini output limits follow `IFC_GEMINI_MAX_OUTPUT_TOKENS`.
The thinking-enabled Nemotron comparison may need a larger `IFC_API_MAX_TOKENS`
budget to leave room for both reasoning and the final structured plan. Record
actual usage and truncation rather than assuming equal output caps imply equal
reasoning effort. No automatic provider fallback is used.

## Artifacts and interpretation

- `sources/`: reproducible IFC4 files with fixed GUIDs, timestamps and source
  hashes. One model covers each of complete classifications, native topology,
  absent information, multiple floors, partial classifications, and conflicting
  classification/boundary evidence.
- `manifest.json`: questions, task family, source hash, exact scope, grouped split,
  fixture version, interpreter/library versions and Git revision, plus SHA-256
  fingerprints of 20 explicit runtime/evaluator source modules. These identify
  uncommitted planner/schema changes without copying code or reading `.env`.
  Replay intention
  names are evaluator metadata; they are not included in planner requests.
- `predictions.jsonl`: validated result/evidence responses or safe error categories,
  saved and flushed before reference values are imported and compared. It includes
  request scope/hash and per-call model IDs, prompt/schema identities, actual
  token usage when reported, and timing. Credentials and raw prompts are omitted.
  Failures may retain recognized upstream HTTP status and allowlisted machine
  codes for backend diagnosis; provider messages and bodies remain excluded.
- `report.json`: safe configuration fields, all case outcomes, checks and summary
  denominators, by-family results, missed/false instances, required source-anchor
  checks, nearest-rank p50/p95, and reported/missing usage counters. Cost remains
  null without an explicit applicable tariff; missing usage remains unreported.
  Paired comparisons align case IDs with the first requested provider as baseline,
  report wins/regressions, and check that the initial catalog hashes match.

The evaluator checks status, exact counts, door/room membership, related-room
identities, selected scope, lower-bound quality and fixture boundary/fill anchors.
A matching count with incorrect objects fails. Non-answers and provider errors
remain in the total case denominator. Reference values live only in the evaluator
[reference module](references.py), imported after prediction artifacts are saved;
production planning does not import it.

These evidence checks establish declared fixture identities and relationship
anchors, not independent visual correctness or physical building completeness.
The small-run latency percentiles do not establish production performance.
Compare real source-backed quality separately before promoting a provider, as
described in the [assessment](../../docs/GEMINI_IFC_ASSESSMENT.md). Visual inputs
and geometric inference remain a separate experiment.

Run the evaluator regressions with:

```sh
python -m unittest tests.test_ifc_planner_evaluation -v
```

The CLI exits zero when all selected comparisons pass their fixture checks, and
one when any case fails. API errors are recorded without provider response bodies.
Offline checks for this implementation use no live inference.
