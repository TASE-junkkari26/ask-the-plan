# Image candidate API

An internal Python HTTP service for locating question-relevant objects in one
image using Nemotron or an allowlisted Gemini profile. It returns unreviewed
candidate boxes, literal labels, visual cues, and uncertainty. It does not return a final answer
or object count. The React frontend uses this endpoint for imported 2D drawings;
IFC viewing and the CPU executor also connect through the separate
[IFC question API](../docs/IFC_QUESTIONS.md) on this same server.
The application opens on file import; synthetic QA sources remain offline
fixtures. IFC files are not sent to this image endpoint.

The first integration targets are the supplied raster window/door question
families. Other question-relevant candidates may be returned, but no general
dataset coverage is claimed. See the [implementation plan](PLAN.md) and
[Nemotron guide](../docs/nvidia_info.md).

The [Gemini Hydrogen implementation plan](GEMINI_PLAN.md) records the provider
boundary and protocol research. The image provider is selected on the backend;
IFC planning continues to use its existing Nemotron integration.

The [Gemini Decisions plan](DECISIONS_PLAN.md) records the experimental router:
familiar tasks use Hydrogen-low and difficult, unfamiliar or uncertain cases go
directly to Carbon-medium. Selective preprocessing follows in a later stage. It incorporates the new
[tooling/routing research](../docs/TOOLING_AND_ROUTING_PLAN.md) and
[100-image report](../experiments/image_questions/GEMINI_100_RESULTS.md), keeping
that capability-first order. Review tasks use one Astra-6 Max subagent each;
the UI explains recorded decisions and evidence limits, including failures,
in an expandable panel. Routing is off by default pending dataset evaluation.

## Experimental capability routing

Keep `GEMINI_API_KEY` on the backend. Set `IMAGE_API_PROVIDER=gemini` and choose:

| Setting | Behavior |
| --- | --- |
| `IMAGE_API_ROUTING_MODE=off` | Default; one explicitly configured image provider/profile. |
| `IMAGE_API_ROUTING_MODE=shadow` | Decisions recommends a route; the configured baseline analyzer still runs once. |
| `IMAGE_API_ROUTING_MODE=auto` | Selects Hydrogen-low for supported cases meeting the overall-fit threshold, otherwise Carbon-medium directly. No weak-model retry. |

`GEMINI_MODEL=gemini-4-hydrogen` with `GEMINI_THINKING_LEVEL=low` remains the
manual default; `gemini-4-carbon` accepts `low` or `medium`. Auto mode defaults
to Carbon medium; set `IMAGE_API_ROUTING_STRONG_THINKING_LEVEL=low` for lower
thinking. High thinking is outside the application allowlist. Profile selection
preserves the configured output-token and timeout limits.
Carbon model access is required for the strong route. If it is unavailable,
return a traced error rather than silently using Hydrogen.

Routing requires `IMAGE_API_PREPROCESS_MODE=original` or `off`, preserving the
canonical whole raster. It rejects `overview` and more than two concurrent
requests. No crops, OCR or source-tool loop is selected by this initial version.
One decision attempt and one analyzer attempt are allowed, without retries.
Router errors/timeouts recommend Carbon; shadow mode records that recommendation
while retaining the baseline. The total deadline includes preparation/routing;
five seconds are reserved for finalization before another call can run.

`IMAGE_API_ROUTING_THRESHOLD=0.6` is the provisional default. Only the overall
`normal_fit=supported` probability must meet it. Explicit `needs_strong` or
`uncertain`, or an overall fit below the threshold, selects Carbon directly.
Document type, operation, target, counting grain and scope labels are diagnostic:
low confidence in one of those labels does not independently invoke Carbon.

Ordinary readable drawings, room/fixture/object discovery, labels, schedules and
printed quantity regions can use Hydrogen. Several readable panels, a room filter,
a non-count task or another ordinary object category do not automatically make
a task difficult. Both analyzers retain the same submitted-image and candidate-only
boundaries; Carbon does not add missing sources, calibration or execution tools.
Policy `capability-routing-v2` replaces v1's 90%-on-every-label gate and narrow
door/window/fixture vetoes. Its threshold is still a heuristic, not calibrated
accuracy. Explicit environment overrides remain honored; remove an old `0.9`
override or set `IMAGE_API_ROUTING_THRESHOLD=0.6` to use the new default. Restart
the backend after changing settings. Use `shadow` to evaluate routing on your sources.

`IMAGE_API_ROUTING_TIMEOUT_SECONDS=3` bounds Decisions. A bounded session-only
cache (`IMAGE_API_ROUTING_CACHE_ENTRIES=32`, zero disables it) keys on exact
question/scope, image hashes, profiles and policy/criteria versions. Cache hits
reuse routing assessments without billing them as a new call. No source bytes or
reference answers are cached there. Both modes still send the image and question
to the configured Gemini services when an uncached decision is needed.

The expandable **How this was analyzed** panel shows recorded assessments,
probabilities, thresholds, actual route/calls, skipped preparation and failures.
For v2 it explains that only overall fit is thresholded; older v1 traces retain
their original explanation. Policy and criteria changes invalidate cached routes.
Scores are routing estimates, not answer accuracy. Exported candidate JSON retains
the trace; failures retain it in the error state. Total cost estimates sum each
call's timestamp/model/usage and mark missing information as unknown. IFC continues
through its separate Nemotron integration. See [.env.example](../.env.example).

## Live model handoff while loading

The workbench shows **Preparing image…**, then **Choosing analysis model…**.
Immediately before the chosen analyzer is invoked, both loading areas show
**Handing to Gemini 4 Hydrogen…** or **Handing to Gemini 4 Carbon…** (with Finnish
equivalents). This uses the actual dispatch, including cache hits and the
configured baseline in shadow/manual mode; it does not wait for candidate output.
Cancellation, source/page changes and a new request clear the previous model.

The frontend opts into streaming on the same multipart
`POST /api/v1/candidates` with `Accept: application/x-ndjson`. The ordinary JSON
response remains the default for existing callers. A stream contains one
`ImageCandidateStreamEvent` of type `handoff`, followed by a terminal `result`
or `error`, newline-delimited UTF-8. An error before dispatch has no handoff.
Successful streams require the handoff. Each frame has schema version `0.1.0`;
the handoff includes request ID, source identity/dimensions, question hash and
requested model. Terminal responses retain the existing contracts and full trace.
See the [generated event schema](../contracts/jsonschema/ImageCandidateStreamEvent.schema.json).

Upload and image preparation/validation complete before streaming headers, so
their HTTP validation errors remain JSON. After streaming starts, errors travel
as terminal error frames under HTTP 200; consumers must read the terminal frame.
The stream uses `X-Request-ID`, `Cache-Control: no-store` and
`X-Accel-Buffering: no`. Clients reject source/request/question mismatches,
inconsistent handoff/result models, malformed/truncated streams and stale updates.
An older JSON-only backend is accepted without resubmitting or inventing progress.

Streaming adds no provider call or polling request. Deadlines, admission limits
and cancellation still apply. Disconnect cleanup stops owned analysis workers,
awaits asynchronous cancellation cleanup, then removes request files and releases
admission. An unavailable strong profile is reported before any model handoff.

## Install and run

From the repository root on Linux, with Python 3.10+ (tested with 3.12):

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[api,preprocess,test]'
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Windows PowerShell, using a separate native virtual environment:

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api,preprocess,test]"
.\.venv\Scripts\python.exe -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Reuse an existing environment when already installed. Configure the selected
image provider in the existing root `.env`; never overwrite that file during
setup. No key goes into browser code or the HTTP upload request.

Open <http://127.0.0.1:8000/docs> for the upload form/OpenAPI documentation.
`GET /health` returns 200 when configured and 503 when backend configuration is
missing/invalid. Health and documentation requests never spend inference calls;
health checks image configuration, not current provider availability or IFC
readiness. Stop the server with Ctrl+C.

## Choose the image provider

To use Gemini, preserve the key already in your existing `.env` and add the
selector. Set the key only if it is missing:

```dotenv
IMAGE_API_PROVIDER=gemini
GEMINI_API_KEY=
```

Restart the Python server after changing settings. Images use the native Google
Interactions API with `gemini-4-hydrogen`/low by default, structured JSON output,
and `store=false`. With routing off, one image request makes one provider call;
experimental routing adds at most one Decisions call before one selected analyzer.
No retries or repair requests are enabled. The same current UI displays
the returned candidates and actual model provenance.

The image provider defaults to `nemotron`. To select it explicitly, set
`IMAGE_API_PROVIDER=nemotron` and configure `VERDA_INFERENCE_KEY` using the
[Nemotron configuration rules](../docs/nvidia_info.md#local-setup).

The selector affects `POST /api/v1/candidates` only. IFC queries keep their
existing Nemotron client and `VERDA_*` settings. Gemini configuration failure
does not disable configured IFC queries; missing Verda settings do not disable
configured Gemini image analysis.

Gemini configuration uses the same root `.env` discovery and process-over-file
precedence, without changing `os.environ` or interpolating dollar sequences.
The backend reads `GEMINI_API_KEY` explicitly; `GOOGLE_API_KEY` is not an alias.
Credentials, images, and provider error bodies are omitted from API errors.

| Gemini setting | Default and meaning |
| --- | --- |
| `GEMINI_API_KEY` | Empty; required when Gemini is selected. |
| `GEMINI_MODEL` | `gemini-4-hydrogen` by default; also accepts `gemini-4-carbon`. |
| `GEMINI_THINKING_LEVEL` | `low` for Hydrogen; `low` or `medium` for Carbon. |
| `GEMINI_MAX_OUTPUT_TOKENS` | `65536`; range 1–65536, shared by thinking and final output. |
| `GEMINI_TIMEOUT_SECONDS` | `120`; HTTP network-phase timeout, bounded by the total API deadline. |

Low thinking still uses reasoning tokens. Gemini response `completion_tokens`
includes both final-output and thinking tokens, while `prompt_tokens` reports
input tokens. Missing usage fields remain null. The existing Nemotron
`IMAGE_API_MAX_TOKENS` budget is separate from Gemini's output cap. See the
[official documentation collected in the plan](GEMINI_PLAN.md#feasibility-and-official-documentation)
for protocol, pricing, quota, and structured-output details. One live drawing
request and the browser handoff passed; broader localization accuracy requires
case-specific evaluation. See the
[verification record](GEMINI_PLAN.md#implementation-and-verification-record).

## Request and response

Send exactly two multipart parts to `POST /api/v1/candidates`: an `image` file
and a nonblank `question`. Question wording is preserved after trimming outer
whitespace. Only PNG, JPEG and WebP still images are accepted; formats are checked
from their contents. Render a PDF page/SVG view to a supported image first.

```bash
curl --fail-with-body http://127.0.0.1:8000/api/v1/candidates \
  -F 'image=@path/to/floorplan.png' \
  -F 'question=How many windows are in this floorplan?'
```

Use `curl.exe` in Windows PowerShell and supply a real image path.

The response's `candidates` list contains question-relevant detections, not a
computed count or final answer. Each candidate has a response-local ID, category,
nullable original `source_label`, `geometry`, `uncertain`, nullable
`uncertainty_reason`, and a short observable `visual_cue`. Example box fragment
(synthetic, not model output):

```json
{
  "id": "candidate-001",
  "category": "window",
  "source_label": "121.A",
  "geometry": {"kind": "box", "minimum": [8.0, 8.0], "maximum": [72.0, 32.0]},
  "uncertain": false,
  "uncertainty_reason": null,
  "visual_cue": "Parallel lines within the exterior wall."
}
```

The envelope includes `schema_version`, `request_id`, `scope: "submitted_image"`,
`image`, `status`, `inventory_completeness: "unverified"`, `limitations`,
`provenance` (requested/returned model, prompt version, and optional preprocessing
metadata), and `metrics` (inference-stage elapsed milliseconds, nullable token
usage, and preparation metrics). Image metadata contains
`sha256` of the submitted bytes, `inference_sha256` of the prepared image,
`width`, `height`, and `coordinate_system: "display_pixels_top_left"`.

The public definitions are generated from [Python contracts](../contracts/models.py):
[response schema](../contracts/jsonschema/ImageCandidateResponse.schema.json),
[error schema](../contracts/jsonschema/ImageCandidateError.schema.json), and
[TypeScript response](../frontend/src/contracts/ImageCandidateResponse.ts)/
[error types](../frontend/src/contracts/ImageCandidateError.ts).
Schema validity does not establish detection accuracy or inventory completeness.
Complete synthetic envelopes are saved as [success](examples/success.json),
[empty](examples/empty.json), [partial](examples/partial.json), and
[error](examples/error.json) examples. They are integration fixtures, not live
model observations.

| Status | Interpretation |
| --- | --- |
| `ok` | Extraction finished without a reported limitation; an empty list means no candidates detected, not a proven physical zero. |
| `partial` | Candidate extraction has limitations, explained in `limitations`; usable proposals may still be present. |
| `unreadable` | No candidates; image interpretation failed, with an explanation. |
| `unsupported` | No candidates; the question requires information this image cannot support, with an explanation. |

Uncertain detections remain in the response with reasons. IDs are stable within
one response, not across requests or drawings, and are not canonical building
entity IDs. Up to 100 candidates are supported; reaching that limit requires a
partial result. Invalid boxes, exact duplicate category/geometry records, invalid
JSON, and token-truncated completions produce errors without an automatic repair
request. Overlapping candidates are preserved rather than silently merged.

## UI integration and coordinates

```typescript
import type { ImageCandidateResponse } from './contracts/ImageCandidateResponse';
import type { ImageCandidateError } from './contracts/ImageCandidateError';

const body = new FormData();
body.append('image', imageFile);
body.append('question', question);
const response = await fetch('http://127.0.0.1:8000/api/v1/candidates', {
  method: 'POST', body, signal: abortController.signal,
});
// Let the browser supply Content-Type with its multipart boundary.
if (!response.ok) {
  const error: ImageCandidateError = await response.json();
  throw new Error(error.message);
}
const result: ImageCandidateResponse = await response.json();
// Match this result to the source/request still selected before rendering it.
```

Coordinates use the **entire EXIF-oriented display image**, in pixels: top-left
origin, X right, Y down. The backend applies EXIF orientation, composites
transparency onto white, and strips metadata into a canonical full-size PNG
before optional preprocessing. The default mode sends that PNG without cropping
or resizing. Optional overview mode sends a reduced full-source image and maps
its proposed boxes back to the full display frame. Display the original source
snapshot with that same orientation on white, regardless of inference mode.
Use returned dimensions; model-normalized coordinates have already been mapped
to display pixels by the backend.

For an SVG overlay, use `viewBox="0 0 width height"` with those dimensions and
share the source image's viewport/pan/zoom/rotation. For the existing UI `Mark`
bounds, map `[xmin, ymin]`, `[xmax, ymax]` to
`[xmin, ymin, xmax-xmin, ymax-ymin]` and then apply the image's fit scale and
offsets into the demo's 1100 by 780 frame. Raw pixels cannot be placed directly
in that unrelated frame. Candidate IDs should remain separate from `entityId`.

The React integration rasterizes the selected imported image or PDF page onto
white PNG at the displayed source dimensions, hashes that submitted raster, and
freezes the preview to that same snapshot while analysing/reviewing candidates.
This also supports SVG/GIF/BMP previews without changing the API's accepted
formats. Submitting sends the snapshot and question to the selected image provider; importing alone
does not. Original upload bytes and backend-submitted raster hashes can differ.
Source/page changes abort the request and clear stale results; the client rejects
responses whose submitted hash or dimensions differ from the prepared snapshot.

Run the Python server above and `npm run dev` in separate terminals. Vite proxies
`/api` to `http://127.0.0.1:8000` in development and local preview. Optionally set
the Vite server process's `IMAGE_API_PROXY_TARGET` to a different local backend;
this value is server configuration, not a browser credential. A hosted build
requires its hosting server to forward `/api` to the Python service.

## Raster preprocessing in the candidate path

The [raster preprocessor](../docs/DRAWING_PREPROCESSOR.md) runs after
`prepare_image` has created its upright, bounded, metadata-free PNG. OCR is off
for this integration. Layout artifacts may be cached for later local inspection,
but candidate inference never automatically selects a `drawing_candidate` or
other content crop. Keeping the entire page preserves relationships among
panels, legends, scale bars, and footers.

| Mode | Preparation and inference behavior |
| --- | --- |
| `original` (default) | Prepare/cache raster artifacts, then send the unchanged canonical PNG used before this integration. |
| `overview` | Prepare/cache artifacts, then send only the `full_source` region's overview; reduce to the configured edge without cropping or enlargement. |
| `off` | Skip the raster preprocessor and use the existing canonical PNG path. |

Set these backend options in the existing root `.env` or process environment:

```text
IMAGE_API_PREPROCESS_MODE=original
IMAGE_API_PREPROCESS_OVERVIEW_LONG_EDGE=1600
IMAGE_API_PREPROCESS_CACHE_ENTRIES=8
```

The bounded cache is owned by the backend process, stores derived artifacts in
its own `TemporaryDirectory`, and is removed at backend shutdown. It is a
session-only cache, separate from the standalone CLI's explicit output directory;
persistent upload storage is not enabled. Changing modes does not enable OCR,
tool calling, IFC analysis, or a final-answer planner. Smaller overviews can lose
fine text/symbols, so measure quality and actual provider usage before preferring
overview mode; no accuracy or inference-cost improvement is claimed.

The response keeps the submitted `image.sha256`, full display `width`/`height`,
and original display-pixel box coordinates. `image.inference_sha256` identifies
the actual PNG bytes sent to the model. Optional `provenance.preprocessing`
contains `mode`, `pipeline_version`, `prepared_id`, `input_width`, and
`input_height`; `metrics.preparation_ms` and `metrics.preparation_cache_hit`
report preparation work. Internal cache paths and artifacts are not exposed by
the candidate API. The frontend continues to freeze and display the original
submitted snapshot; it must not substitute an overview PNG for that snapshot.

## Troubleshoot the frontend connection

The frontend needs both servers: `npm run dev` starts Vite only. If the image API
is stopped, Vite can return an empty HTTP 500, which older frontend versions
describe as "The analysis service returned an unreadable response. Check that
the backend is running." This is a connection/response-format error, separate
from an API result with `status: "unreadable"` about the drawing itself.

From the repository root, start the Python service and leave it running in a
separate terminal:

```sh
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

On Windows use `.\.venv\Scripts\python.exe`. If `uvicorn` is missing, install the
`api` extra using the [setup commands](#install-and-run).

Open <http://127.0.0.1:8000/health>. A configured service returns
`{"status":"ok","configured":true}`. If it returns HTTP 503 with
`"configured":false`, check `IMAGE_API_PROVIDER`, its required key
(`GEMINI_API_KEY` or `VERDA_INFERENCE_KEY`), and the other backend settings
in the existing root `.env`, then restart the API. This check makes no inference
request and does not establish provider availability.

To check routing through the running frontend without sending a drawing or
spending an inference call, send an intentionally empty request:

```sh
curl -i -X POST http://127.0.0.1:5173/api/v1/candidates
```

Use `curl.exe` in Windows PowerShell and the actual Vite port if it differs.
A configured API returns HTTP 415 with a JSON message asking for multipart image
and question fields. An empty/plain-text HTTP 500 or a gateway error points to
the backend connection; check the Vite terminal and `IMAGE_API_PROXY_TARGET`.
An HTML page instead of API JSON points to missing `/api` routing. Restart Vite
after changing its proxy environment variable; for hosted builds, configure the
hosting server's `/api` forwarding. Once these checks pass, retry the question.

## Limits, settings and errors

API settings load from the root `.env` with process environment taking
precedence. Optional settings (defaults shown):

| Variable | Default |
| --- | --- |
| `IMAGE_API_PROVIDER` | `nemotron` (`nemotron` or `gemini`; image candidates only) |
| `IMAGE_API_MAX_IMAGE_BYTES` | `20971520` (20 MiB, also the maximum accepted setting) |
| `IMAGE_API_MAX_BODY_BYTES` | `23068672` (22 MiB, including multipart overhead) |
| `IMAGE_API_MAX_PIXELS` | `40000000` (decoded image pixels) |
| `IMAGE_API_MAX_QUESTION_CHARS` | `4000` (may be lowered) |
| `IMAGE_API_MAX_CONCURRENT` | `2` (per worker process) |
| `IMAGE_API_DEADLINE_SECONDS` | `180` |
| `IMAGE_API_MAX_TOKENS` | `8192` (Nemotron image output budget only) |
| `IMAGE_API_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` |
| `IMAGE_API_PREPROCESS_MODE` | `original` (`original`, `overview`, or `off`) |
| `IMAGE_API_PREPROCESS_OVERVIEW_LONG_EDGE` | `1600` |
| `IMAGE_API_PREPROCESS_CACHE_ENTRIES` | `8` (per backend process) |

The prepared PNG must also fit the configured image byte limit. A compact JPEG
can exceed this limit after decoding/re-encoding; the API reports an error
rather than silently shrinking it. The body cap applies even without a truthful
Content-Length. Local multipart parsing also bounds field/file multiplicity.

Gemini additionally bounds the entire serialized inline request to 20,000,000
bytes, including base64 PNG, question, instructions, and schema. A file accepted
under the image limit may therefore still exceed the Gemini limit and receive
413 before inference. The server does not silently resize it or upload it using
a separate Files API request. Its private normalized `[ymin, xmin, ymax, xmax]`
boxes are converted to the same public X/Y display pixels described above.

One analyzer attempt is made per accepted request; routing optionally adds one
decision attempt. SDK retries are disabled for this endpoint, with no change to
CLI defaults. The deadline covers body receipt, preparation, routing and analysis.
Preparation runs in a worker thread; a timed-out
worker finishes its bounded local work and then removes its files. Inference is
cancelled on timeout/disconnect; this does not guarantee the remote provider
stops processing. Request-specific upload/normalization files are cleaned after
their local work finishes. When preprocessing is enabled, derived image artifacts
can remain in the bounded session cache until eviction or backend shutdown.
No persistent upload store or prompt/raw-response storage is enabled.

Errors use `schema_version`, `request_id`, `code`, safe `message`, and `retryable`.
Normal responses expose the correlation ID in `X-Request-ID` too. Provider error
bodies, credentials, image payloads, and local filesystem paths are omitted.

| HTTP | Meaning |
| --- | --- |
| 413 | Multipart body, upload, decoded pixel count, prepared PNG, or Gemini inline request exceeds a limit. |
| 415 | Wrong request content type or unsupported actual image format. |
| 422 | Missing/repeated/extra fields, invalid question, corrupt or animated image. |
| 429 | All local request slots are busy; retry later. |
| 499 | Client disconnected while awaiting inference. |
| 500 | Internal preparation/service failure. |
| 502 | Provider failure or invalid/truncated model candidates. |
| 503 | Missing backend settings, provider configuration/access/billing problem, or transient provider unavailability/rate limit. |
| 504 | Total request deadline exceeded. |

Scope restrictions and candidate relevance are model-proposed and remain subject
to the same uncertainty as other model observations. This local internal service
does not add deployment authentication, persistence, a job queue, pixel masks,
physical measurements, or a final-answer planner.

## Verification

From the root, with no key or live calls required:

```bash
.venv/bin/python -m unittest tests.test_image_api tests.test_image_candidate_contracts tests.test_nemotron tests.test_gemini tests.test_contracts -v
.venv/bin/python -m contracts.export --check
npm --prefix frontend run generate:contracts
npm run build
.venv/bin/python scripts/check_docs.py
```

Use the Windows interpreter path and `npm.cmd` on Windows. See the
[verification record](../docs/VERIFICATION.md) for actual results and live-check
boundaries; synthetic fixtures and mocked provider tests are not accuracy tests.
