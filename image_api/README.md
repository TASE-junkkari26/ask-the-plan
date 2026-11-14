# Image candidate API

An internal Python HTTP service for locating question-relevant objects in one
image using the existing Nemotron client. It returns unreviewed candidate boxes,
literal labels, visual cues, and uncertainty. It does not return a final answer
or object count. The React frontend uses this endpoint for imported 2D drawings;
local IFC inspection and the IFC executor retain their separate behavior.
The application opens on file import; synthetic QA sources remain offline
fixtures. IFC files are not sent to this image endpoint.

The first integration targets are the supplied raster window/door question
families. Other question-relevant candidates may be returned, but no general
dataset coverage is claimed. See the [implementation plan](PLAN.md) and
[Nemotron guide](../docs/nvidia_info.md).

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

Reuse an existing environment when already installed. Set `VERDA_INFERENCE_KEY`
in the existing root `.env`; never overwrite that file during setup. The backend
loads it using the [existing configuration rules](../docs/nvidia_info.md#local-setup).
No key goes into browser code or the HTTP request.

Open <http://127.0.0.1:8000/docs> for the upload form/OpenAPI documentation.
`GET /health` returns 200 when configured and 503 when backend configuration is
missing/invalid. Health and documentation requests never spend inference calls;
health does not test current provider availability. Stop the server with Ctrl+C.

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
formats. Submitting sends the snapshot and question to Nemotron; importing alone
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

## Limits, settings and errors

API settings load from the root `.env` with process environment taking
precedence. Optional settings (defaults shown):

| Variable | Default |
| --- | --- |
| `IMAGE_API_MAX_IMAGE_BYTES` | `20971520` (20 MiB, also the maximum accepted setting) |
| `IMAGE_API_MAX_BODY_BYTES` | `23068672` (22 MiB, including multipart overhead) |
| `IMAGE_API_MAX_PIXELS` | `40000000` (decoded image pixels) |
| `IMAGE_API_MAX_QUESTION_CHARS` | `4000` (may be lowered) |
| `IMAGE_API_MAX_CONCURRENT` | `2` (per worker process) |
| `IMAGE_API_DEADLINE_SECONDS` | `180` |
| `IMAGE_API_MAX_TOKENS` | `8192` (overrides the client's output default here) |
| `IMAGE_API_ORIGINS` | `http://127.0.0.1:5173,http://localhost:5173` |
| `IMAGE_API_PREPROCESS_MODE` | `original` (`original`, `overview`, or `off`) |
| `IMAGE_API_PREPROCESS_OVERVIEW_LONG_EDGE` | `1600` |
| `IMAGE_API_PREPROCESS_CACHE_ENTRIES` | `8` (per backend process) |

The prepared PNG must also fit the configured image byte limit. A compact JPEG
can exceed this limit after decoding/re-encoding; the API reports an error
rather than silently shrinking it. The body cap applies even without a truthful
Content-Length. Local multipart parsing also bounds field/file multiplicity.

One inference attempt is made per accepted request; SDK retries are disabled for
this endpoint, with no change to CLI defaults. The deadline covers body receipt,
preparation and inference. Preparation runs in a worker thread; a timed-out
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
| 413 | Multipart body, upload, decoded pixel count, or prepared PNG exceeds a limit. |
| 415 | Wrong request content type or unsupported actual image format. |
| 422 | Missing/repeated/extra fields, invalid question, corrupt or animated image. |
| 429 | All local request slots are busy; retry later. |
| 499 | Client disconnected while awaiting inference. |
| 500 | Internal preparation/service failure. |
| 502 | Provider failure or invalid/truncated model candidates. |
| 503 | Missing backend settings, provider configuration/access problem, or transient provider unavailability/rate limit. |
| 504 | Total request deadline exceeded. |

Scope restrictions and candidate relevance are model-proposed and remain subject
to the same uncertainty as other model observations. This local internal service
does not add deployment authentication, persistence, a job queue, pixel masks,
physical measurements, or a final-answer planner.

## Verification

From the root, with no key or live calls required:

```bash
.venv/bin/python -m unittest tests.test_image_api tests.test_image_candidate_contracts tests.test_nemotron tests.test_contracts -v
.venv/bin/python -m contracts.export --check
npm --prefix frontend run generate:contracts
npm run build
.venv/bin/python scripts/check_docs.py
```

Use the Windows interpreter path and `npm.cmd` on Windows. See the
[verification record](../docs/VERIFICATION.md) for actual results and live-check
boundaries; synthetic fixtures and mocked provider tests are not accuracy tests.
