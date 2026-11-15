# Supplied IFC question evaluation

This evaluator runs the production `POST /api/ifc/models` and
`POST /api/ifc/questions` routes in-process using an ASGI transport. Upload parsing,
hash checks, extraction, source sessions, planner validation/repair, exact scope,
engine execution, errors and evidence responses use application code. The ASGI
transport needs no listening server. Live mode uses the configured external
planner; replay injects fixed typed proposals and opens no provider connection.
Native-only mode exercises production deterministic planning with no provider
configuration, credentials or transport.

The [coverage inventory](../../docs/IFC_QUESTION_COVERAGE.md) distinguishes **1,188
direct IFC questions across 40 paths and 198 families** from **2,694 questions
whose referenced source is an IFC-derived PDF**. This evaluator selects the direct
IFC rows only. It does not silently replace a PDF with a whole-model question.

## Inspect task inputs

Use the configured Python environment with the project's API/test extras:

```sh
python -m experiments.ifc_dataset --list --line 85521 --line 85643
python -m experiments.ifc_dataset --list --one-per-family
python -m experiments.ifc_dataset --list --model dental_clinic_mep.ifc
```

`--line`, `--family` and `--model` can be repeated. Families match the exact
reviewed taxonomy; a model accepts an exact relative path or basename. Multiple
selector kinds intersect, and records retain original line order. `--limit N`
and `--one-per-family` select deterministic subsets. Unknown selectors fail.
Listing reads only task inputs for output and makes no inference call.

## Bounded live run

The backend `.env` supplies provider credentials and model settings; secrets are
never printed or persisted. Explicitly opt into inference:

```sh
python -m experiments.ifc_dataset --live --provider gemini --line 85521 --output build/ifc-live-heights --max-calls 3
```

Both `gemini` and `nemotron` use their production IFC adapters. Gemini defaults
to high IFC thinking; choose `--thinking-level low|medium|high|xhigh` explicitly
for comparisons. The independent image provider is disabled in this process.
Only the question and production bounded source catalog/discovery go to the
planner, never reference answers or raw source-file uploads to a model service.
Normal live evaluation retains the configured production deterministic grammar
path. Use `--disable-fast-plans` when measuring the external planner alone; the
fixed-plan replay always disables grammar shortcuts so its intended proposal is
actually exercised.

Bounds apply together:

| Option | Default | Meaning |
| --- | ---: | --- |
| `--max-calls` | 12 | Cumulative planner request starts across all cases and resumed attempts; zero permits only deterministic production answers. |
| `--max-model-requests` | 3 | Per-question production planning/discovery/repair cap; at most 3. |
| `--max-inspections` | 6 | Per-question bounded source-action cap; at most 6. |
| `--deadline-seconds` | 180 | Question/upload deadline, also bounded by remaining run time. |
| `--run-deadline-seconds` | 1800 | Overall active attempt deadline; at most one day. |

SDK inference retries are disabled. Budget exhaustion retains the selected-row
denominator and lists not-attempted lines. A started call is durably recorded
before transport, so interruption cannot reset the cumulative request budget.
When deterministic production grammar is enabled, cases continue within the run
deadline after the external-call cap is consumed: native answers remain free,
and questions requiring the model receive an explicit budget error before any
remote request. Use `--live --max-calls 0` for that
native-only production audit; live provider configuration is still validated.
Usage and time remain unknown for a call interrupted before a response; a request
start is a conservative accounting event, not proof that a provider billed it.
There is no automatic provider fallback.

Source discovery supports finite pages (`offset` 0–1,000, `limit` at most 20).
Follow the returned cursor, which uses the records actually retained after the
response-size budget. Facets provide independent per-property `next_offset`
values; continue each property with a single-property request. Every requested
page consumes the existing inspection budget. Explicit `unpageable`/omitted
values or a remaining cursor mean discovery is incomplete, not a zero inventory.

To audit native production coverage without loading any provider configuration
or client, use the explicit native-only mode. It enforces zero external calls,
retains errors for questions that need external planning, and keeps every
selected row in the report denominator:

```sh
python -m experiments.ifc_dataset --native-only --output build/ifc-native-all --run-deadline-seconds 7200
```

Render a completed run's model/family coverage, errors and grading as Markdown:

```sh
python -m experiments.ifc_dataset.summarize build/ifc-native-all --write build/ifc-native-all/SUMMARY.md
```

## Resume without repeating recorded calls

```sh
python -m experiments.ifc_dataset --live --provider gemini --line 85521 --output build/ifc-live-heights --max-calls 3 --resume
```

Every recorded outcome is reused, including errors and non-answers. Source,
question-file hash, selected rows, actual code hashes, provider/model/transport
configuration, IFC settings, scope and replay inputs must still match. A changed
implementation requires a fresh output directory; select only the cases that
need a new measurement. To continue a budget-limited run, explicitly increase
the cumulative `--max-calls` while preserving the remaining configuration.

Predictions are atomic per-row JSON files. `predictions.jsonl` is a convenience
index reconstructed from those records on resume, so a truncated streaming line
cannot cause a completed request to rerun. Do not run two evaluator processes
against the same output directory simultaneously.

## Zero-provider-call replay

Replay requires a JSON mapping original one-based dataset line numbers to typed
`PlanProposal` objects. A value may instead be a list of proposals for a bounded
inspection/repair sequence. These are query intentions, not answer values:

```json
{
  "86338": {
    "status": "ready",
    "interpretation": "Count native wall occurrences in the authorized model.",
    "explicitly_requests_entire_model": true,
    "steps": [
      {
        "id": "walls",
        "operation": {
          "kind": "select",
          "concept_ids": ["concept:wall"],
          "count_policy": {
            "grain": "occurrence",
            "hierarchy": "all_matches",
            "distinct_by": "canonical_entity_id",
            "rule_key": "ifc.occurrence.v1"
          }
        }
      },
      {
        "id": "total",
        "operation": {"kind": "aggregate", "input_step_id": "walls", "method": "count"}
      }
    ],
    "output_step_id": "total"
  }
}
```

```sh
python -m experiments.ifc_dataset --replay-plans build/ifc-plans.json --line 86338 --output build/ifc-fixed-plan-check
```

Every selected line needs a proposal. Replay loads no provider keys, creates no
external transport and does not interpret the natural-language question. A replay
pass demonstrates those fixed plans' execution/evidence, not planner accuracy.

## Scope variants

The normal run explicitly authorizes the source model with `scope=model` while
the question retains its named floor/room filters. This is a dataset evaluation
choice; the interactive UI still defaults to its captured current-view inventory.

Use `--scope view --view-ids build/view-inventory.json` for scope regressions.
That JSON maps each selected exact model path to its visible STEP IDs. An empty
list is preserved, and duplicate/nonpositive IDs are rejected. Scope variants
are **ungraded against supplied numeric references** because those references
are not bound to an arbitrary custom visible inventory. Source/question/scope
bindings and output membership still receive structural checks.

## Artifacts and scoring limits

- `manifest.json`: literal task inputs, source hashes/sizes, code/module hashes,
  Git revision, Python/library versions, explicit settings, selected scope and
  safe transport configuration.
  It never serializes a credential settings object or `.env` contents.
- `calls.jsonl`: durable request starts/finishes, case identity, prompt/catalog/
  schema hashes, lengths, actual returned model, usage and timing. Safe static
  error categories and allowlisted upstream diagnostics are retained; raw prompts,
  provider bodies, private error messages and credentials are omitted.
- `predictions/line-*.json` and `predictions.jsonl`: full production plans,
  result/evidence responses or safe errors, submitted scope, source hash,
  upload/question timings, call records and structural checks.
- `attempts.jsonl`: each resume attempt's explicit cumulative budget and reused
  predictions.
- `report.json`: selected and recorded denominators, unattempted lines, statuses,
  per-family outcomes, actual/missing token usage, latency, and evaluation results.
  Applicable cost is null without an explicit tariff. A flag records code changes
  observed during a run; do not describe such a run as a frozen implementation.

All selected predictions are saved and flushed **before** the reference-loader
module is imported or supplied answer values are loaded for comparison. Runtime
planning/execution never imports that evaluation module.

Quantitative `count` rows require one exact answered count and exact equality.
`area`, `length` and `volume` require one complete answered compatible quantity,
explicit unit conversion, and the dataset's **2%** relative tolerance. Complete
geometry estimates within tolerance are reported distinctly as
`numeric_agreement_estimated`; they never become exact claims. Zero references
have zero absolute tolerance. Partial/lower-bound/upper-bound answers and estimated
counts cannot pass as exact totals. This is **numeric agreement**, not independent verification of
correct object membership, property meaning, net/gross basis or every question
constraint. Those remain visible review requirements.

All Bench `text` rows, including numeric or multipart questions encoded as text,
remain **`ungraded_text`** for accuracy. The evaluator checks source/question/scope
bindings, output view membership, calculation/fact/anchor/entity-set references
and non-answer shape. It does not treat matching prose, a plausible explanation,
a structured non-answer or green schema checks as proof of answering all parts.
Unsupported known families remain unfinished work. Missing information may be
correct only when independently supported from source/extraction coverage.

The CLI returns 2 for a setup failure, 1 for API errors, structural failures,
unanswered/ungradable numeric cases, numeric disagreement, unattempted rows or
code changes during the run, and 0 when those execution checks pass.
An exit code of 0 with ungraded text does **not** mean full IFC question accuracy
or acceptance completeness. `all_questions_supported` deliberately remains false
until a separate, source-backed review establishes the full requirement set.

Run the offline regressions with:

```sh
python -m unittest tests.test_ifc_dataset_evaluation -v
```
