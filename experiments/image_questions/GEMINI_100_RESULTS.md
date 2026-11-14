# Gemini Hydrogen: 100-image count evaluation

14 November 2026, Europe/Helsinki. **79 of 100 candidate counts exactly matched
the supplied references.** All 100 production API requests completed with HTTP
200, and all returned `gemini-4-hydrogen`. The 79 matches also had status `ok`;
neither of the two `partial` responses matched.

This measures **candidate-list count agreement**, not final-answer accuracy or
correct localization. The current image endpoint explicitly returns candidate
regions rather than a final answer, calculation or verified inventory. The
stratified development sample is not a corpus-wide or held-out accuracy estimate.

## Sample and method

- Fixed seed `20261114`; 100 different source files and 100 different submitted
  image hashes; one supplied count question per image, across 29 families.
- 60 CubiCasa PNGs, 30 Swiss PDF pages, seven IFC-derived floor-plan PDF pages,
  and three Opening Design technical sheets. All 40 PDFs have one page.
- Question-family round-robin sampling within each source, followed by random
  draws within a family. Sampling did not inspect answer values or condition on
  expected counts. Source allocations are deliberate, not dataset-frequency weights.
- Whole-model IFC questions were excluded: the selected IFC-derived PDF
  questions explicitly concern the shown floor/view. No IFC file was analyzed.
- Eight question languages: English 54, Finnish 26, German 11, French five, and
  Italian, Polish, Romanian and Danish one each. These small language groups do
  not support language-performance conclusions.
- CubiCasa styles: six colorful, ten high-quality and 44 architectural PNGs.
  Raster images retain their native upright dimensions on white. PDF.js uses
  the frontend's full-page scale/pixel policy, with Node canvas; this does not
  establish byte-identical browser font rasterization.
- Existing production HTTP route, Gemini prompt/schema and `original` full-source
  preprocessing; OCR off; Hydrogen with low thinking and 65,536 output-token
  budget. No crops, repair calls, fallback models or retries.
- Six concurrent requests on an isolated local Uvicorn server. Only its admission
  limit changed; the running workbench's server and settings were left intact.
- Exact instructions/questions/schema, image hashes and provider replies/usage
  were saved before candidate validation. Selected references were accessed for
  scoring only after all baseline responses were saved. No reference values
  entered inference. Image hashes/dimensions and shared contracts were checked;
  all 100 API results also match their recorded provider question/image hash.

Production revision: `9db07ec5287e6c349b35f8d6af57a1add779bbcf`.
The new experiment runner is also captured by content hash and a source snapshot.
Dataset `questions.jsonl` SHA-256:
`0e6322c74561a63f42bac35f5c1be8a2c6a37516b14a81e66ab88b74950a6d1f`.

## Results

| Source | Images | Exact count matches | Rate |
|---|---:|---:|---:|
| CubiCasa floor plans | 60 | 50 | 83.3% |
| Swiss floor plans | 30 | 24 | 80.0% |
| IFC-derived floor-plan images | 7 | 3 | 42.9% |
| Opening Design technical sheets | 3 | 2 | 66.7% |
| **Total** | **100** | **79** | **79.0%** |

Thirteen references are zero-valued: 12 matched an empty `ok` candidate list.
Among 87 positive-valued references, 67 matched (77.0%). An empty list is still
not a verified physical-object zero. There were no unscorable references.

Twenty-one cases mismatched: 13 undercounts and eight overcounts relative to
references. Nineteen mismatches reported status `ok`; two reported `partial`.
The model marked candidates uncertain in five responses, all mismatches in this
sample, but it did not flag the other 16 mismatches with candidate uncertainty.
An `ok` status or absence of uncertainty cannot establish correctness.

The most relevant weak direct-count families were windows (3/9 matches) and doors
(4/8). Balconies were 7/7, sinks/washbasins 6/6, and separate WC rooms 5/5. These
are small family samples; the full 29-family breakdown is in the run report.

## What the mismatches include

| Case | Supplied task | Reference | Candidates | Observation |
|---|---|---:|---:|---|
| Q004 | CubiCasa `high_quality_architectural-14139.png`, windows | 15 | 10 | Undercount; status `ok`, no limitations. |
| Q086 | Swiss `site925_bldg1957_floor8574.pdf`, fitted doors | 54 | 45 | Dense-plan undercount; status `ok`, no limitations. |
| Q092 | IFC-derived `DG2` floor plan, doors | 11 | 12 | `partial`; glazed terrace openings lack swing arcs, making door/window membership ambiguous. |
| Q093 | IFC-derived `Level 2` floor plan, stairs | 2 | 0 | Empty `ok` result despite a positive supplied reference. |
| Q099 | Cannery Trail A700, total ESDH3066 units from N-wide assemblies | 379 | 6 | Quantity aggregation is not implemented by the candidate endpoint; candidate-list length is the wrong computation for this question. |

Q099 is a derived count requiring multiplication and summation rather than direct
object enumeration. It remains in the preselected 100-case headline result.
The 99 direct-count cases had 79 exact matches (79.8%) and mean absolute count
error 0.515. Across all 100, mean absolute error was 4.24, dominated by Q099's
373-unit difference. The API's 100-region cap also means list length cannot
represent a 379-unit answer, although this response returned only six regions
and did not hit that cap.

No per-case reference was changed or overridden. Mismatch descriptions compare
saved outputs with supplied references; they are not a manual adjudication of
every source object or box. Equal counts can conceal cancelling omissions and
false positives. Alternative models and routing policies were not evaluated.

## Timing and cost

| Measurement | Observed |
|---|---:|
| API round-trip median | 5.79 s |
| API round-trip mean | 7.04 s |
| API round-trip p95 | 15.19 s |
| Live run wall time, six concurrent requests | 125.48 s |
| Reported input tokens | 219,400 |
| Reported output tokens, including thinking | 117,397 |
| Output content / thinking tokens | 50,013 / 67,384 |
| Estimated standard-rate total | $1.2095775 USD |
| Estimated average per request | $0.012095775 USD |

All 100 provider replies reported complete token usage. The estimate uses
[Google's paid standard Hydrogen rates](https://ai.google.dev/gemini-api/docs/pricing#gemini-4-hydrogen),
verified on 14 November 2026: $1.50 per million input tokens and $7.50 per million
output tokens, including thinking. It precedes cache discounts, credits and
taxes and is not an invoice. API timing includes local server preparation and
the model request, but excludes benchmark queue time and pre-rendering; it is
not a browser-measured response time. There were no transport failures, rate-limit
responses, timeouts or candidate-validation failures in this run.

## Reproduction and artifacts

See [the runner instructions](README.md#100-image-gemini-hydrogen-benchmark).
Local artifacts are under the ignored directory
`experiments/runs/gemini-hydrogen-100/20261114T182040Z/`:

- `REPORT.md`: generated full source/family/language and operational summary.
- `results.csv` and `evaluation.json`: every question, reference, candidate count,
  match decision, scope, latency and model identity.
- `cases.json`: answer-free sample with dataset line numbers, exact questions,
  source paths, selection seed and dataset hash.
- `Q001/` through `Q100/`: submitted PNG, source license/hashes, API output and timing.
- `provider/`: exact prompt/schema/image identity, raw provider reply, token usage
  and timing. Credentials, authorization headers and image data URIs are excluded.
- `environment.json` and `code/`: platform/package versions, credential-free
  settings, pricing, pipeline hashes and snapshots. `evaluation.json` separately
  records the scorer hash.

Checked on Windows, Python 3.14.10. Five offline harness tests pass, including
distinct-image sampling, reproducibility, absent/zero separation and abstention
grading. Documentation links and whitespace checks pass. No browser or manual
100-image localization review is claimed. The isolated evaluation server shut
down after the run; production source files and original dataset assets are unchanged.
