# Offline answer coverage and evaluation

15 November 2026. These tools describe development coverage and score **saved**
answers. The answer service does not import this package, the question classifier,
the ledger or reference QA. No model calls, answer-accuracy result or challenge
completion is established by generating these artifacts.

The full dataset is available locally. Its saved classification was checked
against all **127,044 rows, 6,789 question texts and 234 families**. The
[family ledger](family_ledger.json) retains every family, actual source paths,
project/language examples, prerequisites, available primitives and open gaps.
All family outcomes remain `unverified_family_coverage`; no family is declared
complete from its schema, a parser observation or a synthetic test.

## Generate the reference-free manifest and ledger

From the repository root:

```sh
.venv/bin/python scripts/classify_questions.py --check --report-date 2026-11-14
.venv/bin/python scripts/build_answer_ledger.py --audit
.venv/bin/python scripts/build_answer_ledger.py --check
```

On Windows use the configured `.venv\Scripts\python.exe`. The classifier reads
only question/path/type fields; its JSONL byte digest includes the entire source
file but reference-answer fields never enter cases, routing or source audits.
The generated manifest lives in ignored `build/answers/manifest.json` (about
102 MB), alongside any private saved outputs. It contains **127,044 cases and
8,102 registered assets**, including same-drawing companions and named IFC
floor-render prerequisites. All registered assets were available when generated.
Source hashes cover their original bytes. The tracked ledger and
[structural source audit](source_audit.json) are derived metadata, not a runtime
answer lookup.

Grouping keeps translations, a source's alternate formats, Swiss site/building
floors, named IFC floor renders, conservatively named building disciplines and
byte-identical assets together. Additional provenance-backed evaluation links
can be supplied with `--links links.json`, where each entry has `source`,
`target` and `provenance`. These links authorize **offline grouping only**.
They do not register linked sources with the running app.

There are **5,847 conservative leakage groups** in this generation. Split labels
are deterministic proposals, not proof of fresh held-out data. Historical model
experiments and any source used to guide fixes remain development material even
if a proposed hash bucket says `held_out`. Freeze the manifest hash and record
actual development exposure before declaring a split. Unknown relationships
between nonidentical renamed assets remain a grouping limitation. `--skip-hashes`
is for exploration and explicitly leaves duplicate-byte grouping unverified.

## Structural prerequisite observations

The audit selected 54 IFC originals and 16 project-diverse PDFs, prioritizing
IFC-Bench and the three Opening Design sources. **63 sources were inspected;
seven IFCs exceeded the 64 MiB per-file limit and remain uninspected.** Each
subprocess has a 20-second deadline. IFC inspection uses IfcOpenShell native
record classes, property/quantity names, unit metadata, recorded north and port
record counts; it does not generate geometry or infer service connectivity.
PDF.js reports page count and native text availability on **page 0 only**.

The ledger links these structural observations to 214 families; 20 families
remain available but uninspected by this sample. Question-specific source
sufficiency is unverified for every family. Text enumeration does not establish
tables, label membership or complete depicted-object counts. A missing property
name in a bounded catalog, a large-file skip and an uninspected source never
establish missing source information. Parser failures and capped work stay open.
These are automatic metadata checks, **not `agent_reviewed` source labels**.

## Score frozen outputs separately

Save one JSONL record per attempted manifest case:

```text
{"case_id":"qa:...","answer":{...saved AnswerResponse...},"phase":"warm_question"}
{"case_id":"qa:...","error":{"code":"deadline_expired"}}
```

`case_id` is an offline wrapper. It is never passed to the runtime planner.
Optional `phase` can label `cold_import`, `warm_question` or `cache_hit`; record
the actual measurement boundary. Then run:

```sh
.venv/bin/python -m experiments.answers.evaluate \
  --manifest build/answers/manifest.json \
  --outputs build/answers/outputs.jsonl \
  --references dataset/junction-dataset/questions.jsonl \
  --report build/answers/evaluation.json
```

The scorer requires saved nonempty outputs before opening references. It records
manifest/output/reference hashes, rejects changed reference bytes or question
bindings, and keeps unattempted cases in all-coverage denominators. Counts must
match exactly; quantities use the dataset's 2% relative tolerance after unit and
dimension checks. A zero reference requires zero. Numeric claims in references
stored as `text` are scored numerically too. Original reference answers are
never modified.

Raw reference agreement is separate from a strict numeric-and-structural pass.
Partial or estimated answers cannot count as exact successes merely because a
number agrees. Wrong source hashes, root calculation/value mismatches, invented
anchors, incomplete exact numeric coverage, missing count grain and clearly
mismatched net/gross bases fail the structural check. These checks do not prove
source localization, omissions, question interpretation or free-prose entailment.
Descriptive clauses, multiple free-text numeric associations and text-valued
numeric outputs require source review. They do not receive an automatic strict
pass from an unordered bag of matching numbers.

The report includes row-weighted results, family/project macro rates, attempted
coverage, every missing/unsupported/partial/failed/disputed outcome, known calls,
nullable usage/cost counters and latency summaries. Currency totals stay
separate. All-case denominators include `not_run`; attempted-only denominators
are reported separately. Structural pass rates are not an end-to-end accuracy
claim. No full-corpus answer run has been performed by this tooling change.

Optional `--disputes disputes.json` accepts a case-ID mapping whose entries include
`reason`, `source_sha256` and `evidence_locator`. It records source-backed disputes
separately and preserves raw reference agreement. A dispute is not silently
converted into a correct answer.

## Checks

```sh
.venv/bin/python -m unittest tests.test_answer_evaluation -v
```

Synthetic tests cover reference separation, duplicate/link/project grouping,
portable safe paths, honest audit skips, numeric-in-text scoring, exact counts,
2% quantities and units, false evidence, partial answers, reference disputes,
unknown usage, frozen hashes and complete report denominators. These checks
exercise the harness, not model accuracy or the full question-family executors.
