# Image candidate API implementation plan

Date: 14 November 2026. Status: implementation delivered in this directory;
see [usage and integration](README.md) and the [verification record](../docs/VERIFICATION.md).
This document retains the design and implementation sequence. Nemotron identification is accepted for this work based
on the team's experimentation. Another model-selection or accuracy experiment
is not a prerequisite.

Follow-up: the imported-file UI is now connected to this service. The initial
frontend separation described below records the API implementation's original
boundary; see [current integration behavior](../frontend/README.md#backend-integration-boundary)
for the subsequent image/page snapshot, candidate overlay, and export work.

## Goal and boundary

Build a small internal HTTP API in `image_api/`. It accepts exactly one image
and one question, asks Nemotron to locate relevant candidates, validates the
returned regions, and returns those candidates for the UI to highlight.

For "How many windows are in this floorplan?", request individual window
candidates. Return the candidates, their locations, and any uncertainty. Do not
ask the model for a total, calculate a final count, or generate a final answer
in this version. A short visual cue attached to a candidate describes what was
detected; it is not an answer to the original question.

Scope is always the submitted image. A request for information about unseen
floors or a whole building must not silently expand that scope. Candidate IDs
identify detections within one response, not verified physical building objects.
The number of rendered marks must not become an authoritative construction count.

Start with bounding boxes for localization. Here, "segment candidates" means
separate localized object proposals; pixel masks, exact object outlines, area
measurement, and calibrated geometry are outside this first implementation.

The first integration cases are the supplied raster window and door question
families, documented in the [question classification](../docs/QUESTION_CLASSIFICATION.md).
The service may return other question-relevant visible candidates, but that does
not advertise support for all dataset families or IFC/property queries. Preserve
original labels and identifiers such as `121.A` separately from normalized
categories. Never load supplied reference answers into the request pipeline.

## Reuse and ownership

- Reuse [AsyncNemotronClient](../nemotron/client.py) and the existing backend
  settings loader. Keep the supplied Verda deployment and local `.env` behavior.
- Reuse the normalized `0..1000` box convention and object-instance instructions
  from the [door-labeling pilot](../experiments/door_labeling/README.md), adapting
  the target to the question. Do not import its experiment runner or evaluation
  code into the service.
- Define shared public wire types in [contracts/models.py](../contracts/models.py).
  Reuse `BoxShape`; add stricter two-dimensional, positive-area, image-bound
  checks for candidate responses. Keep model-only proposal parsing private to
  `image_api/`.
- Leave frontend components and `ifc_engine/` unchanged. The UI team owns the
  browser call and overlay integration. This endpoint returns a candidate
  response, not the existing final-answer `QueryResult`.

Proposed files, to be created during implementation:

```text
image_api/
  PLAN.md          implementation plan (this file)
  README.md        installation, startup, API examples, coordinate contract
  __init__.py
  app.py           app factory, HTTP routes, CORS, client lifecycle, safe errors
  config.py        API limits and local server settings
  images.py        decoding, orientation, dimensions, hashes, temporary files
  service.py       prompt construction, inference, proposal validation/mapping
  prompt.txt       versioned candidate-extraction instructions
tests/
  test_image_api.py
  test_image_api_lifecycle.py
  test_image_candidate_contracts.py
```

Shared changes will be limited to package dependencies/discovery, public contract
definitions and exports, generated types, and integration documentation. Inspect
the current diff before editing these files because the UI team also uses them.

## HTTP interface

Use FastAPI with Uvicorn, Pydantic, `python-multipart`, and Pillow. Add the new
dependencies as an `api` extra in the existing Python project and include
`image_api*` in package discovery. Keep the existing Nemotron transport.
FastAPI documents [file and form uploads](https://fastapi.tiangolo.com/tutorial/request-forms-and-files/),
[client lifecycle management](https://fastapi.tiangolo.com/advanced/events/), and
[CORS configuration](https://fastapi.tiangolo.com/tutorial/cors/).

| Route | Behavior |
| --- | --- |
| `GET /health` | Local service/configuration status; never calls the provider or returns secrets. |
| `POST /api/v1/candidates` | Multipart form with exactly one `image` file and one nonblank `question`; returns one JSON response. |
| `/docs` | Generated API documentation and a manual request form for teammates. |

Proposed request limits: PNG/JPEG/WebP only; 20 MiB uploaded image; 40 megapixels
after decoding; question length 1–4,000 characters after trimming. Enforce bounded
request/multipart reads, not just the declared content length. Reject repeated
image/question fields, corrupt images, animation, and unsupported formats with
clear errors before inference. PDF/SVG callers must supply one rasterized view.

Example browser integration to document once implemented:

```typescript
const form = new FormData();
form.append('image', imageFile);
form.append('question', question);
const response = await fetch(`${apiBaseUrl}/api/v1/candidates`, {
  method: 'POST',
  body: form,
  signal: abortController.signal,
});
// Check response.ok, then parse the generated response/error type.
// The browser sets the multipart Content-Type and boundary.
```

Default development address: `127.0.0.1:8000`. Allow the local Vite origins
`http://127.0.0.1:5173` and `http://localhost:5173`, with an explicit configurable
origin list for teammates' setups. Keep the provider key exclusively on the
backend. A frontend API base URL is public configuration, never a credential.

## Response contract and coordinates

Add public `ImageCandidate`, `ImageCandidateResponse`, and `ImageCandidateError`
models, with schema versions following the existing `Contract` convention.
Generate JSON Schemas and TypeScript from Python; do not hand-maintain a second
wire schema. Extend the existing export/generation lists for the new roots.

The response will contain:

- `schema_version`, server-generated `request_id`, and `scope: "submitted_image"`.
- `image`: SHA-256 of submitted bytes, SHA-256 of the inference image, display
  width/height, and `coordinate_system: "display_pixels_top_left"`.
- `status`: `ok`, `partial`, `unreadable`, or `unsupported`.
- `inventory_completeness: "unverified"`: no model response establishes an
  exhaustive inventory.
- `candidates`: IDs, normalized category, nullable literal `source_label`, box
  geometry, `uncertain`, nullable `uncertainty_reason`, and a short `visual_cue`.
- `limitations`: readable explanations for ambiguity, unreadable areas, or scope
  restrictions. `partial`/`unreadable`/`unsupported` require an explanation.
- `provenance`: requested/returned model IDs and prompt version.
- `metrics`: elapsed milliseconds and provider token usage when available;
  missing usage stays null. No invented currency estimate.

All coordinates are finite floats in the EXIF-oriented image's display pixel
frame: origin at the top left, X rightward, Y downward. Apply EXIF orientation
before inference and strip its metadata in the temporary image. Return the
resulting width/height; the UI must display that same orientation. Do not crop
or resize in version one. Reject a prepared inference image above the existing
client's 20 MiB limit rather than silently changing its coordinate frame.

The model receives actual image dimensions and returns normalized boxes over
the entire image, using the pilot's `0..1000` axes. Convert to pixels once on the
backend: `x_px = x_1000 * width / 1000`, and similarly for Y. Require
`0 <= xmin < xmax <= width` and `0 <= ymin < ymax <= height`. Reject invalid
geometry rather than silently clipping or repairing it.

Illustrative candidate fragment, not a real detection or complete response:

```json
{
  "id": "candidate-001",
  "category": "window",
  "source_label": null,
  "geometry": {
    "kind": "box",
    "minimum": [200.0, 300.0],
    "maximum": [280.0, 330.0]
  },
  "uncertain": false,
  "uncertainty_reason": null,
  "visual_cue": "Parallel window lines within the exterior wall."
}
```

Assign candidate IDs on the server, unique within a response and stable for its
lifetime. Preserve model order. Return uncertain candidates explicitly; do not
silently remove overlapping boxes using an arbitrary overlap threshold. Reject
exact duplicate category/geometry records as invalid model output. Overlap alone
does not prove two proposals represent the same object.

An `ok` response with `candidates: []` means the completed request found no
candidates. It does not establish a physical-object count of zero. `partial`
keeps usable candidates and explains limitations; `unreadable` and `unsupported`
return empty lists with reasons. Request failures use HTTP errors, never a
successful empty detection response. No numeric confidence score is required.

## Inference and request lifecycle

1. Validate the multipart request, decode the image, apply orientation, and
   compute image identities. Use temporary files because the current client
   accepts image paths; never trust the uploaded filename as a path.
2. Build a versioned system instruction plus the original question. Ask for
   visible instances relevant to the question, boxes, literal labels, observable
   cues, and limitations. Treat both question and image text as input data;
   preserve the output schema and image-only scope.
3. Describe the intended object grain. For doors, one fitted doorway is one
   candidate, including double-leaf doors; exclude unfitted passages and cabinet
   doors. For windows, group the visible window assembly rather than individual
   line strokes. Keep ambiguous membership visible.
4. Call the existing async client's `ask` with JSON-object output and the
   proposal schema in the system instruction. Use `completion_text` and Pydantic
   validation to retain finish-reason checks, returned model ID, and token usage.
   Do not execute model-generated tools or code.
5. Validate proposal structure and geometry, map boxes to display pixels, assign
   IDs, validate the public response, and return it to the caller.
6. Close uploads and remove owned temporary files on success, failure, timeout,
   or cancellation. Do not persist user images, prompts, or raw model output by
   default. Log request IDs, timing, and sanitized error categories only.

Reuse one async client per application lifecycle. Proposed API defaults are two
in-flight inference requests, a 180-second total deadline, and an 8,192-token
output budget. Expose these as API settings. Disable provider SDK retries for
this endpoint so a request makes one inference attempt; leave CLI defaults
unchanged. Reject excess concurrent work with a retryable busy response rather
than building a job queue. Cancel local inference on client disconnect where
supported; cancellation does not guarantee the provider stops processing.

Bound the proposal list to 100 items initially. Require `partial` with a
limitation when that limit is reached. A truncated completion or invalid JSON
is an error, not a partial successful list. Do not add automatic repair requests,
tiling, a database, caching, streaming, or background jobs to the first version.

## Error handling

Use a versioned error envelope with `request_id`, `code`, safe `message`, and
`retryable`. Normalize framework validation errors into the same envelope.

| HTTP status | Meaning |
| --- | --- |
| 413 | Upload, decoded pixel count, or prepared-image size exceeds a documented limit. |
| 415 | Unsupported media/format. |
| 422 | Missing/repeated input, blank question, corrupt image, or unsupported animation. |
| 429 | Service concurrency limit; caller can try again later. |
| 502 | Provider failure or invalid/truncated/schema-invalid model output. |
| 503 | Missing backend configuration or provider temporarily unavailable/rate limited. |
| 504 | Total inference deadline exceeded. |

Do not return provider response bodies, credentials, host filesystem paths,
image payloads, or raw Pydantic input dumps. Keep provider authentication errors
distinct internally from user request errors; the browser does not authenticate
to Verda.

## Implementation order and checks

1. **Contracts and example:** add the public models, invariants, schema exports,
   generated TypeScript, and clearly synthetic success/empty/partial/error
   examples. This gives the UI team a stable integration target first.
2. **Candidate service:** implement bounded image preparation and the existing
   client's JSON request/validation path, independent of HTTP routing.
3. **HTTP adapter:** add multipart handling, lifecycle-managed client, limits,
   CORS, health/docs routes, and uniform errors. Keep real UI components intact.
4. **Meaningful offline checks:** use mocked provider responses and small image
   fixtures to cover input rejection before inference, normalized-to-pixel
   mapping, EXIF orientation, invalid/duplicate boxes, uncertain/empty/partial
   results, truncation, provider errors, deadlines, cleanup, and concurrent calls
   retaining their own image/question/IDs. Check CORS and error envelopes.
5. **Integration smoke check:** use one existing development floorplan and a
   question to confirm the real HTTP-to-Nemotron path and inspect returned boxes.
   This checks wiring, not a new model-selection study or broad accuracy claim.
6. **Handoff:** document Linux and Windows installation/startup, curl and browser
   examples, response semantics, limits, and overlay mapping. Update root README,
   Nemotron guide, and schema guide to distinguish the implemented service from
   the still-independent frontend and IFC executor.

Planned startup after implementation, from the repository root:

```bash
.venv/bin/python -m pip install -e '.[api,test]'
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Use `.venv\Scripts\python.exe` for the corresponding Windows commands. The
existing `.env` supplies `VERDA_INFERENCE_KEY`; never overwrite it during setup.
API-specific settings must have their own documented defaults.

Run the new API tests plus existing Nemotron and contract regression checks.
Regenerate/check JSON Schemas and TypeScript using the repository commands; run
the frontend build when generated frontend files change. Check Markdown links
with `python scripts/check_docs.py`. Record actual platforms, results, and skipped
checks honestly. Do not commit, publish, or deploy as part of this implementation.

## UI handoff and completion

The UI submits the exact image/page currently displayed and keeps its own source
revision/selection state. For PDFs, upload a rasterized page, not the original
PDF file. Abort requests or discard stale results when the source changes; bind
responses to the submitted image hash and request ID.

The current [frontend adapter boundary](../frontend/README.md#backend-integration-boundary)
and [MarkLayer](../frontend/src/components/MarkLayer.tsx) use bounds
`[x, y, width, height]`. Convert a candidate's minimum/maximum to
`[xmin, ymin, xmax - xmin, ymax - ymin]`. Account for the imported image's fit
offsets/scaling into the current fixed 1100 by 780 demo frame, then apply the
same pan/zoom/rotation as the image. Alternatively, use the returned image
dimensions as an SVG viewBox. Never draw raw image coordinates directly into an
unrelated demo frame. Highlight uncertainty and keep candidate identity separate
from canonical entity identity.

This iteration is complete when another developer can start the service, submit
one image and one question, and receive typed, image-bound candidate boxes with
honest status/error handling, without modifying the model client or knowing the
provider key. Actual frontend integration remains the UI team's work. A final
answer/counting service can later consume reviewed candidates and explicit
coverage/counting policies; it is not part of this candidate endpoint.
