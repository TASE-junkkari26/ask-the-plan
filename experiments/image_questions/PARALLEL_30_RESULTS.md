# Parallel random 30-question integration evaluation

The integrated decision/detail pipeline matched **26/30** known reference counts,
compared with **25/30** before integration, on the exact same questions and PNG
bytes. One case improved and none regressed. Both runs completed every HTTP
request with 10 concurrent questions and up to 12 actual provider calls.

This is candidate-list count agreement, not verified localization or a final
answer score. Equal counts can conceal different false positives and omissions.
The one additional match came from Hydrogen, so this small result does not
establish that routing or Carbon caused an accuracy improvement.

## Selection and execution

- Seed `20261115`; 30 fresh random count questions on distinct source images.
- Eligible rows: existing non-IFC PNG/PDF sources with count questions.
- Shuffle all eligible rows, retain the first question for each distinct image
  until 30 are selected. Selection does not use reference values or prior results.
- Resulting sample: 24 CubiCasa and 6 Swiss Dwellings images, 12 question families;
  six PDF pages rendered with the existing frontend PDF.js scale policy.
- Cases, source hashes, canonical PNGs, native input pixels and inference code
  were frozen before inference. References were read only after every response
  was saved. No retries or alternative-answer selection were used.
- Current Hydrogen-low detailed tool, `mode=tiles,max_calls=9`; the only test-time
  changes were admission/call concurrency and request attribution for recording.
- Source/crop hashes, code snapshot hashes and provider-to-case attribution passed
  audit. Actual peaks were 10 concurrent cases and 12 concurrent provider calls.
- Owned isolated loopback server on port 8016 stopped after the run. The user's
  frontend/backend preview was left running.

## Pre-integration results

| Measure | Result |
|---|---:|
| Count matches | 25/30 |
| Strict `ok` count matches | 23/30 |
| CubiCasa | 19/24 |
| Swiss Dwellings | 6/6 |
| HTTP 200 | 30/30 |
| Status | 28 ok, 2 partial |
| Actual Gemini attempts/replies | 45/45 |
| Replies with complete usage | 45/45 |
| Input tokens | 116,074 |
| Output tokens including thinking | 30,292 |
| Nominal standard cost | $0.401301 |
| Median case response | 5.96 s |
| p95 case response | 11.49 s |
| Total inference wall time | 25.42 s |

The sample happened to contain no window questions and no opening-design source.
It cannot establish correctness for those families, IFC, DXF, area computation or
schedule arithmetic. It is a development measurement on a small random sample.

## Paired integrated result

The integrated run used automatic Decisions routing with the production three
second routing deadline. Native detail extraction, source identity, membership
checks and source-bound reconciliation remained enabled. Its manifest and every
input PNG were byte-identical to the pre run. Frozen-code, frame, request
attribution and concurrency audits passed again.

| Measure | Before | Integrated |
|---|---:|---:|
| Exact count matches | 25/30 | 26/30 |
| Strict `ok` matches | 23/30 | 24/30 |
| HTTP 200 | 30/30 | 30/30 |
| Actual provider attempts | 45 | 75 |
| Complete provider replies/usage | 45 | 74 |
| Known nominal cost | $0.401301 | $0.406261 |
| Median case response | 5.96 s | 7.01 s |
| p95 case response | 11.49 s | 14.02 s |
| Inference wall time | 25.42 s | 40.47 s |

The integrated run made 30 Decisions attempts, 43 Hydrogen calls and two Carbon
calls. Routing selected normal for 29 cases. Q022 selected strong after its
Decisions call was cancelled at approximately three seconds; that case was
already correct before integration and remained correct. No case was semantically
recommended for strong analysis in this sample. This run proves the live
Carbon fallback path worked, not that difficulty-based escalation is calibrated.

Q028's WC fixture count changed from four to the correct three under Hydrogen.
With stochastic model calls and one paired repetition, this can be ordinary run
variation. All other match/nonmatch outcomes stayed the same.

Known cost by model: Hydrogen $0.374475, Carbon $0.024056 and Decisions $0.007730.
The timed-out Decisions attempt has unknown usage and may have an additional
unreported charge; it is retained as a failed/cancelled attempt rather than zero
cost. All 74 completed replies included full token usage, including thinking.

Two remaining shower/bath failures had reported normal-fit probabilities of
0.636 and 0.657, above the current 0.6 threshold. This suggests a useful targeted
frontier comparison before changing routing policy. These are uncalibrated
development observations, not evidence that raising a threshold will improve
general accuracy. Missing proposals can also be confident, so checking only
uncertain existing candidates does not solve the omission problem.

## Targeted Carbon comparisons

After the paired run was scored, a separate diagnostic sent its four remaining
failures and two fixed stable controls to Carbon-medium with the same detailed
options. This was an explicitly targeted development probe; its results do not
replace the random 30-case measurement.

| Post-30 case | Reference | Hydrogen detailed | Carbon-medium detailed |
|---|---:|---:|---:|
| Q003, floor control | 1 | 1 | 1, partial |
| Q011, sinks | 0 | 3 | 3, partial |
| Q022, sink control | 2 | 2 | 2 |
| Q023, showers/baths | 1 | 0 | 1 |
| Q024, doors | 9 | 11 | 11 |
| Q026, showers/baths | 4 | 3 | 3, partial |

Carbon repaired one failure and preserved both controls: **3/6** versus **2/6**.
All six HTTP calls succeeded; 13 Carbon calls returned complete token usage.
Known nominal cost was $0.281916; median case latency 36.44 seconds, total
wall time 119.78 seconds. Carbon helps some interpretation problems, but it did
not repair every missed fixture or door-count mismatch.

A separate two-case probe reused prior targeted-v2 dense opening failures.
Actual source questions were Q004 **windows** and Q086 **doors**; the historical
artifact folder name contains `windows` but does not change either question.
Q004 failed with HTTP 503 after a provider timeout at 120.5 seconds. Q086 failed
with HTTP 504 at the 180-second total deadline. No count was returned in either
case; failures remain failures and do not become predicted zero. There were five
Carbon attempts and three completed replies, costing a known $0.1552 plus unknown
charges for the two failed/cancelled attempts. These results do not support
blindly sending a dense full region to Carbon-medium as a universal repair.

## Posthoc routing-gate trial

The six-case comparison motivated one additional paired 30-case trial at a
**0.7** normal-fit threshold. Only this isolated benchmark setting changed;
runtime prompts, sources, detail options, model profiles and the three-second
router deadline stayed fixed. The threshold was selected after seeing these
development results, so this is not an independent confirmation set.

| Measure | Integrated gate 0.6 | Trial gate 0.7 |
|---|---:|---:|
| Exact count matches | 26/30 | 26/30 |
| Strict `ok` count matches | 24/30 | 21/30 |
| Normal / strong profiles selected | 29 / 1 | 23 / 7 |
| Decisions / Hydrogen / Carbon attempts | 30 / 43 / 2 | 30 / 36 / 10 |
| Known nominal cost | $0.406261 | $0.479534 |
| Unknown-charge attempts | 1 | 1 |
| Median case latency | 7.01 s | 8.88 s |
| Total inference wall time | 40.47 s | 61.34 s |

Q023 improved from zero to one shower/bath. Q017 regressed from the correct zero
to one uncertain sauna proposal. Those effects cancelled in the count score.
The trial escalated six cases because of the higher threshold and one because of
a router timeout. Every HTTP request succeeded and the same source/frame/code
and parallelism audits passed. There were 76 provider attempts, 75 completed
replies with complete usage, and one cancelled Decisions attempt with unknown
usage.

This sample supports **retaining the existing 0.6 gate**, rather than globally
raising it: 0.7 increased known inference cost by about 18%, increased latency,
and produced no net count improvement. A later change should target a demonstrated
failure mechanism and check correct controls, rather than treating a model's fit
probability as calibrated correctness. No backend policy or default threshold was
changed by these benchmark trials.

## Failures retained

| Case | Question family | Reference | Candidates |
|---|---|---:|---:|
| Q011 | Sinks and washbasins | 0 | 3 |
| Q023 | Showers and bathtubs together | 1 | 0 |
| Q024 | Doors | 9 | 11 |
| Q026 | Showers and bathtubs together | 4 | 3 |
| Q028 | Toilet bowls/WC fixtures | 3 | 4 |

Q011 has a possible reference discrepancy. The source
`high_quality_architectural-675.png` visibly includes a kitchen double basin and
washbasins in `PESUH.` and `WC`; the model proposed those three with source boxes.
Focused membership checks rejected two additional false proposals. This is a
manual observation, not independent ground truth. The supplied zero reference is
unchanged and the case remains scored as a failure.

Q023 illustrates a different issue: a small shower symbol in a dense plan was not
proposed. Membership checking only existing proposals cannot recover omissions.
The remaining cases require source-level review; the score alone does not
establish whether they fail through recognition, counting grain or annotation.

## Reproduce and compare

The reusable harness is [parallel_detail.py](parallel_detail.py). From the repo
root, use the configured Python interpreter (Windows:
`.venv\Scripts\python.exe`).

```text
python -m experiments.image_questions.parallel_detail plan --run-dir experiments/runs/NEW --seed 20261115 --count 30
node experiments/image_questions/render_pdfs.mjs experiments/runs/NEW dataset/junction-dataset
python -m experiments.image_questions.parallel_detail run --run-dir experiments/runs/NEW --port 8016 --case-workers 10 --provider-workers 12
python -m experiments.image_questions.parallel_detail score --run-dir experiments/runs/NEW
```

For a paired rerun, `fork --previous PRE_RUN --run-dir POST_RUN` copies the exact
manifest and PNG bytes, checks the prior run is complete, and snapshots the new
source. Run with `--routing-mode auto` to exercise the Decisions and Carbon
factories. The harness records all models and accounts for mixed provider usage.
The `run` command starts a clean interpreter with the frozen package tree first
on `sys.path`; concurrent edits to live source cannot change its loaded pipeline.
Use `fork --ids Q003,Q011,...` for a clearly labeled targeted subset,
`run --analyzer-model carbon --routing-mode off` for a manual Carbon-medium
comparison, or `run --routing-mode auto --routing-threshold 0.7` for an isolated
gate trial. These options never write the backend environment or runtime policy.

The actual pre run executed the copied `code/` package tree first on `sys.path`,
so concurrent integration edits could not change inference code. Credentials were
read from the backend environment; no `.env` or key was copied into the snapshot.

Local ignored artifacts:

- `experiments/runs/detail-random30-pre-20261115/`
- `experiments/runs/detail-random30-post-20261115/`
- `experiments/runs/detail-carbon-six-20261115/`
- `experiments/runs/detail-carbon-windows-20261115/`
- `experiments/runs/detail-random30-gate070-20261115/`

They contain frozen cases/images, licenses, source/code hashes, every native
provider request and saved reply/error, safe timings, `audit.json`,
`evaluation.json`, `results.csv` and full local reports. Costs exclude
taxes/credits and use the paid standard rates checked on 14 November: Hydrogen
$1.50/$7.50, Carbon $2/$10 and Decisions $0.10/$0 per million input/output tokens.
Output includes thinking. The source assets and supplied reference answers were
not modified. Seven local harness tests cover seeded answer-blind selection,
concurrent attribution, shared provider capacity, cancellation records and code
snapshot auditing, including exact-input targeted forks. Across these five runs,
214 provider attempts produced 210 completed replies; known nominal cost was
$1.724212, plus unknown charges on four failed/cancelled attempts.
