# Gemini Hydrogen image candidates: implementation plan

Date: 14 November 2026. Status: **implemented; offline, browser, and live smoke checks passed**.
Branch: `feature/gemini-hydrogen`, based on `origin/main` at `2b31bee`.

## Goal and boundary

Add Gemini 4 Hydrogen with low thinking to the existing image/question flow:
import a drawing, submit its displayed image or PDF page and a question, and
review the returned candidate boxes in the current UI. Use one whole-image
inference request. Candidates remain unverified proposals, not final answers,
proven counts, or segmentation masks.

The IFC engine and its Nemotron planner are outside this change. Leave
`ifc_engine/`, `ifc_api/`, IFC contracts, and the IFC viewer unchanged. Keep their
existing Nemotron configuration, prompts, routing, and behavior. The cancelled
cropping/multiple-pass experiment is not part of this branch or implementation.

This targets the supplied raster door/window question families described in
[project scope](../docs/PROJECT_SCOPE.md) and the
[dataset findings](../dataset/FULL_DATASET_FINDINGS.md). Preserve literal labels,
uncertainty, selected-image scope, and the distinction between no detections and
a physical zero. No reference answers enter runtime prompts or model training.

## Feasibility and official documentation

Google lists `gemini-4-hydrogen` as a stable model with image input, structured
output, and `low` thinking. Its default is `high`, so every request must explicitly
set `low`. The implementation record below verifies one live image request;
account-wide quota and general drawing accuracy remain unmeasured.
[Model documentation](https://aistudio.google.com/docs/models/gemini-4-hydrogen),
[Hydrogen changes and thinking levels](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen).

Official sources checked on the date above:

| Topic | Documentation and implementation consequence |
| --- | --- |
| API and request lifecycle | [Interactions overview](https://aistudio.google.com/docs/interactions-overview) recommends Interactions for new integrations. Set `store=false` for this independent, single-turn task. |
| REST wire format | [Create interaction reference](https://aistudio.google.com/api-reference/interactions-api/create-interaction) defines requests, completion status, model-output steps, and usage. Use the documented `/v1beta/interactions` route; keep API version explicit. |
| Authentication | [API keys](https://aistudio.google.com/docs/api-key) documents the `x-goog-api-key` header. Read `GEMINI_API_KEY` explicitly from backend configuration. |
| Image input and boxes | [Image understanding](https://aistudio.google.com/docs/image-understanding) documents inline base64 images, a 20 MB total inline-request limit, and normalized boxes in `[ymin, xmin, ymax, xmax]` order. |
| JSON constraints | [Structured output](https://aistudio.google.com/docs/structured-output) documents `response_format` and a JSON Schema subset. Local validation remains necessary, including lengths and cross-field rules. |
| Reasoning and usage | [Thinking](https://aistudio.google.com/docs/thinking) documents `thinking_level`, summaries, and separate output/thought token counters. Low thinking is not disabled thinking. |
| Limits and failures | [Rate limits](https://aistudio.google.com/docs/rate-limits), [API errors](https://aistudio.google.com/docs/api-errors), and [troubleshooting](https://aistudio.google.com/docs/troubleshooting) cover account-specific quotas and error handling. |
| Cost | [Hydrogen pricing](https://aistudio.google.com/docs/pricing#gemini-4-hydrogen): standard paid rates currently list $1.50 per million input tokens and $7.50 per million output tokens, including thinking. Record actual usage; do not assume free-tier capacity or cost parity with Verda. |

The reference advertises stable `v1` too, but its version-specific page was not
retrievable during this research. The concrete request below follows Google's
accessible REST examples, including their `Api-Revision: 2026-05-20` header.
Do not silently switch API versions or use an OpenAI-compatible endpoint.

## Integration points identified before implementation

- [app.py](app.py) owns the shared FastAPI server. Its lifespan currently creates
  one `AsyncNemotronClient` used by both `CandidateService` and `IfcService`.
  This is the important boundary: replacing that shared client with Gemini
  would also affect IFC. Keep the IFC client in place and create a separate
  Gemini client for image candidates.
- [service.py](service.py) contains the private proposal schema, Nemotron call,
  validation, pixel conversion, and public response construction. Add a small
  image-provider interface here rather than a second HTTP endpoint or app.
- [images.py](images.py) and [preprocessing.py](preprocessing.py) already handle
  orientation, canonical PNG bytes, hashes, and full-source preprocessing.
  Reuse them. Preserve default `original` mode and existing optional `overview`
  behavior; do not revive automatic region selection or multiple calls.
- [candidateApi.ts](../frontend/src/lib/candidateApi.ts) already posts the
  selected snapshot and validates its response identity. The
  [candidate overlay](../frontend/src/components/CandidateLayer.tsx) and
  [review panel](../frontend/src/components/CandidatePanel.tsx) can display the
  existing [response contract](../contracts/models.py) from either provider.

## Intended design

### 1. Separate backend configuration and client ownership

Add a small backend-only `gemini/` package with configuration, an asynchronous
HTTP client, response extraction, and safe errors. Reuse the project's existing
`httpx` dependency for the native REST request; a new SDK is unnecessary for
this limited operation. Include the new package in `pyproject.toml` discovery.

Add `IMAGE_API_PROVIDER=nemotron|gemini`, defaulting to `nemotron` so existing
checkouts retain their behavior. Selecting Gemini affects only
`POST /api/v1/candidates`. Keep Nemotron available as an explicit image-provider
choice, with no automatic fallback between providers.

Backend settings to document in `.env.example`:

```dotenv
# Image candidates only; IFC continues to use the existing VERDA_* settings.
IMAGE_API_PROVIDER=gemini
GEMINI_API_KEY=
GEMINI_MODEL=gemini-4-hydrogen
GEMINI_THINKING_LEVEL=low
GEMINI_MAX_OUTPUT_TOKENS=65536
GEMINI_TIMEOUT_SECONDS=120
```

The user's existing `.env` already has the key. Preserve it and all `VERDA_*`
values. Model and thinking values above are defaults, with this implementation
targeting that exact combination. Use process-over-file precedence, root-relative
`.env` discovery, and non-mutating/non-interpolating loading as in the existing
configuration. Never use browser settings, `VITE_*`, or credentials in URLs.

Keep Nemotron client creation and `IfcService(nemotron_client)` behavior intact
in the shared server. Gemini has its own client lifetime and configuration-error
handling. A missing Gemini key must not disable configured IFC queries; a
missing Verda key must not prevent configured Gemini image analysis. Close each
owned client once at shutdown. Preserve existing dependency injection for IFC
and Nemotron tests; add a separate image-provider injection point.

`/health` continues to report whether image analysis is configured and makes no
inference call. Document that it does not establish IFC readiness or provider
availability. Do not redesign IFC health or routes as part of this work.

### 2. Make one bounded native request

Send the already-prepared PNG and the user's question to:

```text
POST https://generativelanguage.googleapis.com/v1beta/interactions
x-goog-api-key: <backend credential>
Api-Revision: 2026-05-20
Content-Type: application/json
```

Illustrative body; placeholders below are not an executable fixture:

```json
{
  "model": "gemini-4-hydrogen",
  "system_instruction": "<versioned candidate instructions>",
  "input": [
    {"type": "text", "text": "<question>"},
    {"type": "image", "mime_type": "image/png", "data": "<base64 PNG>"}
  ],
  "generation_config": {
    "thinking_level": "low",
    "thinking_summaries": "none",
    "max_output_tokens": 65536
  },
  "response_format": {
    "type": "text",
    "mime_type": "application/json",
    "schema": {"<placeholder>": "<private proposal schema>"}
  },
  "store": false
}
```

Keep requests synchronous at the provider protocol level and asynchronous in
the Python server. No streaming, background execution, continuation, tools,
Files API, retries, or JSON-repair requests. Retain the current total deadline,
concurrency gate, disconnect cancellation, and temporary-image cleanup. Use a
bounded HTTP timeout within that deadline and do not follow credential-bearing
redirects.

Hydrogen's output cap includes reasoning and final output. Start with Google's
documented 65,536 synchronous ceiling and explicit low thinking, independently
of Nemotron's existing 8,192-token setting. This is a ceiling, not an expected
per-request allocation. Measure actual usage before reducing it; truncated JSON
must remain an error. See the
[Hydrogen output-limit guidance](https://aistudio.google.com/docs/whats-new-gemini-4-hydrogen#setting-output-token-limits).

Check the actual serialized request size, including base64, prompt, and schema,
before sending. Google's 20 MB request limit differs from the current 20 MiB
image-file limit. Use a conservative 20,000,000-byte ceiling and return a clear
413 for an oversized prepared request. Do not silently resize or upload a file
through a second API. Test sizes after PNG conversion, not only original upload
size. Retain current pixel/body limits as additional checks.

### 3. Normalize Gemini proposals into the existing contract

Use a private Gemini schema for `status`, `candidates`, and `limitations`, with
the same categories, literal labels, cues, uncertainty, and 100-candidate limit
as the existing API. Use native structured output as well as local Pydantic
validation. Build the provider schema from the private model; any simplification
for supported schema keywords must leave the local validator strict.

Use a distinctly named Gemini box field, `box_2d`, in Google's documented
`[ymin, xmin, ymax, xmax]` order. Normalize it once into the service's internal
`[xmin, ymin, xmax, ymax]` order. Convert against the full display dimensions:

```text
x_min = xmin / 1000 * display_width
y_min = ymin / 1000 * display_height
x_max = xmax / 1000 * display_width
y_max = ymax / 1000 * display_height
```

For a 1200×800 display image, `[100, 200, 400, 500]` must become minimum
`[240, 80]`, maximum `[600, 320]`. Test this with an overview of different pixel
dimensions as well. Reject nonfinite, reversed, zero-area, and out-of-range
boxes; do not hide malformed coordinates by clamping them.

Create a separate versioned Gemini prompt (`gemini-candidate-v1`) so the
Nemotron prompt and coordinate instructions remain stable. Preserve current
object grain: one fitted doorway, including a double-leaf door, is one door
instance; two separate adjacent doorways are two candidates. Describe ambiguous
grouping explicitly. This maintains the current API semantics and does not
promise accurate counting. Preserve visible source labels without translation.

Accept only completed interactions with usable text from `model_output` steps.
Do not parse thought summaries as candidate JSON or assume the SDK-only
`output_text` convenience property exists in REST responses. Missing text,
incomplete results, refusals, and invalid schemas must never become successful
empty lists. Reuse validation and public-envelope construction through a small
normalized provider result; do not duplicate HTTP or coordinate code.

Preserve public hashes, display dimensions, preprocessing provenance, candidate
IDs, and `inventory_completeness: unverified`. Report the requested and actual
returned model and the Gemini prompt version. No public contract change is
expected, and generated schemas/TypeScript should remain unchanged.

Map prompt usage from `total_input_tokens`. Define Gemini `completion_tokens`
as `total_output_tokens + total_thought_tokens` so the existing metric includes
all generated tokens. If needed usage fields are missing, report null rather
than inventing zeros. Record the separate counters in local evaluation results
for cost analysis; do not expose reasoning text. This mapping follows Google's
[thinking-token accounting](https://aistudio.google.com/docs/thinking#pricing).

### 4. Preserve useful errors and the current UI

Keep the existing safe error envelope. Distinguish configuration/access failures
from rate limits or temporary unavailability; handle HTTP 402 as a billing/setup
failure, not something automatic retries can fix. Map incomplete or invalid
model results to `invalid_model_output`. Preserve timeout/cancellation behavior.
Expose concise messages and retryability without raw provider bodies, keys, or
image payloads. Google documents the relevant
[error codes](https://aistudio.google.com/docs/api-errors).

Keep the multipart endpoint and candidate response unchanged. The current UI
should render Gemini boxes without a new page or provider selector. Change only
image-flow wording that incorrectly hardcodes Nemotron, if present; preserve
IFC wording and controls. Continue checking source hash and dimensions and
clearing stale results when the source/page changes.

## Implementation order and verification

1. **Configuration and transport.** Add the Gemini package and tests using
   `httpx.MockTransport`. Assert exact model/low thinking, image MIME/base64,
   schema declaration, stateless behavior, byte limits, safe errors, and one
   request without fallback. Cover missing keys and environment precedence.
2. **Candidate adaptation.** Introduce the minimal image-provider interface,
   separate prompt/schema, normalized boxes, usage conversion, and shared public
   response construction. Test valid/empty/partial/unreadable/unsupported,
   duplicate boxes, uncertain candidates, malformed JSON, incomplete interactions,
   missing text, and distinct model-output/thought blocks.
3. **App integration with IFC isolation.** Select the image provider in the
   existing server and manage its client separately. Add integration tests proving
   that image requests use Gemini while IFC queries still call the original
   Nemotron planner, including configuration failures and shutdown. Do not edit
   IFC implementation files or relax their existing tests.
4. **Frontend handoff and docs.** Reuse candidate overlays and snapshot checks.
   Document planned settings as implemented only after they work. Update the
   image API guide, relevant root setup text, and `.env.example`; leave IFC setup
   commands and credentials intact. Include the new prompt as package data.
5. **Offline regression checks.** Run image API/provider/configuration/geometry
   and lifecycle tests, preprocessing tests, and existing IFC API/engine tests
   because they share the server. Run contract export checks, frontend tests/build,
   and `scripts/check_docs.py`. Any pre-existing failures must be reported
   separately; they do not authorize unrelated IFC changes.
6. **Measured live verification.** After offline checks, use one deliberately
   selected drawing for the initial Gemini image request. Confirm low thinking,
   schema acceptance, actual model, latency/usage, and overlay alignment. Verify
   through the UI with the same image snapshot. A key or successful HTTP request
   alone does not establish localization accuracy.

For quality evaluation, compare whole-image Gemini-low proposals to existing
Nemotron observations on a small, fixed set from the supplied door/window
families. Include adjacent and double-leaf doors, and the user's
`dataset/junction-dataset-preview/data/cubicasa5k/colorful-11960.png` as a
development example. Confirm its actual dimensions rather than assuming the
screenshot resolution. Review object locations and grain, false positives,
missed objects, and merged/separated instances. Use precision/recall only where
reviewed localization labels exist; raw candidate totals are not that evidence.
Record latency, actual token usage, and dated cost estimates. Keep raw outputs
and overlays in ignored experiment storage, without credentials or changes to
dataset assets/reference answers. Keep any quality claim limited to tested cases.

## Done when

- Selecting `IMAGE_API_PROVIDER=gemini` uses exactly one Hydrogen-low request
  for the selected drawing/page and displays validated candidate boxes in the UI.
- Existing Nemotron image mode still works when explicitly selected.
- IFC imports, queries, evidence, and Nemotron planning retain their current
  behavior; no IFC implementation files have changed.
- Existing contracts, hashes, coordinate frames, limits, cancellation, and safe
  errors remain intact; integration tests protect the new provider boundary.
- Setup and measured results distinguish implemented behavior from hoped-for
  accuracy. Implementation results follow; they are not a general accuracy claim.

## Implementation and verification record

Completed on 14 November 2026 on Linux, Python 3.12.3 and Node 24.22.3.
The image API now selects a separate Gemini client; IFC continues to receive
the original Nemotron client. No files under `ifc_engine/`, `ifc_api/`,
`nemotron/`, shared contracts, or the IFC viewer were changed. Local `.env` now
selects Gemini; the user supplied the key. Existing Verda settings were preserved.

The native structured-output schema keeps object structure and four-coordinate
boxes but leaves inventory and numeric bounds to the strict local validators
and prompt. The original full Pydantic schema received HTTP 400 in the first
approved request. Google documents decoder-state complexity from nested bounded
arrays as a possible cause. The simplified schema succeeded on the second
separately approved request, with the same model and drawing. The first error's
machine code was not retained, so its exact cause is not established.
See [Google's schema guidance](https://aistudio.google.com/docs/structured-output#simplifying-complex-schemas).
Subsequent errors retain only recognized machine codes for backend diagnostics;
provider messages/bodies remain excluded from public errors and logs.

Validation completed:

- Full Python suite: **312 tests and 285 subtests passed**. The restricted
  sandbox prevented some asyncio worker completions from waking the event loop;
  the credential-free suite passed outside that restriction. No test weakening
  or application workaround was introduced.
- Frontend: all 16 test files passed; TypeScript and production build passed.
  The build emits dependency export and large-chunk warnings. IFC dependencies
  and implementation were left intact.
- Contract export check: all 12 generated contracts current. Markdown checker:
  zero errors, with optional absent corpus links skipped. Whitespace check passed.
- An isolated wheel build succeeded, and inspection confirmed the Gemini module
  and both provider prompts are included, with no `.env` packaged.
- Firefox 142.0 on the production build: imported the actual drawing, submitted
  a question, rendered the candidate review/overlay and model provenance, and
  checked exact source coordinates using a synthetic provider response. No live
  inference was made during that browser test. Artifacts are local/ignored under
  `experiments/runs/gemini-smoke/browser-synthetic/`.
- Firefox replay of the saved live result rendered all five actual proposals,
  preserving their labels, cues, uncertainty, and status. Every DOM overlay's
  source coordinates matched the saved live response within `1e-6`. This used
  zero additional external requests; its report and screenshot are under
  `experiments/runs/gemini-smoke/browser-live-replay/`. Temporary browser profiles
  and owned servers were cleaned up after both browser tests.

Live smoke result, saved under the ignored directory
`experiments/runs/gemini-smoke/live-20261114T165625Z/`:

| Observation | Result |
| --- | --- |
| Input | `colorful-11960.png`, 240×161 pixels, original full-image preparation |
| Question | Locate visible doorways with fitted doors; retain uncertain candidates |
| Model/configuration | Requested and returned `gemini-4-hydrogen`; explicit low thinking |
| HTTP/API outcome | 200, valid `ok` candidate response, five door proposals |
| Inference-stage elapsed time | 5,011 ms for this request |
| Token usage | 2,182 input, 475 final output, 509 thinking; 984 completion tokens in the public response |
| External requests | Two total, each separately approved: one rejected request and one successful request; no retries |

The saved `response.json`, `report.json`, and `candidate-overlay.png` support
inspection. Five proposals are not an exhaustive door count: manual inspection
suggests an additional unmarked door-like symbol at the left edge. No reviewed
localization benchmark or precision/recall result is claimed. A broader fixed-set
quality comparison remains evaluation work, not a prerequisite for using this
provider integration.
