# Callable drawing detail tools

These tools supply operations to an external coordinator. The frontend's
**Detailed scan** explicitly chooses automatic panel selection and overlapping
native tiles. Switching it off uses the original full-image detector.

Revision 2 improves observation identity, bounds repeated work and uses cached
preprocessor overviews for layout while preserving native detection pixels.
See [targeted raster results](../experiments/image_questions/RASTER_IDENTITY_RESULTS.md)
for development tests and limits. IFC extraction/planning is outside this work.

## HTTP interface

`GET /api/v1/tools` lists endpoints and the detail-options JSON schema. Both POST
tools take multipart `image` and `question`. Gemini image-provider configuration
is required. Existing upload limits, admission slots and deadlines apply.

| Operation | Endpoint | Result |
|---|---|---|
| Select drawing panels | `POST /api/v1/tools/propose-regions` | Padded original-pixel rectangles, reasons, limitations and usage |
| Detect on native detail | `POST /api/v1/tools/detect-detail` | Original-frame `ImageCandidateResponse` with detail provenance |

The detail endpoint accepts optional multipart text field `options`, containing
a JSON object. Omit it for automatic panel selection followed by one detection
per panel. Available modes:

```json
{"mode":"auto","max_calls":9}
```

```json
{"mode":"regions","regions":[[100,200,1800,1400]],"max_calls":3}
```

```json
{"mode":"tiles","tile_size":1400,"overlap":200,"max_calls":9,"reinspect_edges":true}
```

`auto` selects all relevant panels and detects within them. `regions` uses the
caller's rectangles without layout inference. `tiles` covers supplied regions
with overlapping native tiles; when rectangles are omitted it first proposes
panels. Bounds are half-open integer `[left, top, right, bottom]`.

In tile mode, a source that already fits one native pass skips layout inference.
Larger sources use the cached full-page overview plus explicitly unverified local
layout hints. Detection always uses native pixels. The model returns typed
`target_kind`: floors, rooms and schedule rows retain complete panels rather
than being split into independently counted fragments. The caller can explicitly
supply this grain when already established by its coordinator.

Native tiling allows 20% edge slack, bounded at 2400 pixels, so a 1428-pixel table
is not analyzed twice through almost identical 1400-pixel crops. Seams are evenly
spaced. Reinspection of an identical source rectangle/image is skipped; identical
pixel patterns at different source positions remain distinct objects.

Small images can still contain tiny symbols or multiple views. A coordinator can
request a finer explicit grid, such as `tile_size=320,overlap=64`. Tile edge is
128-2400 and overlap must be below half the edge. Coverage must still fit the call
budget. This is a selectable tool parameter, not the external decision tree.

The default budget of nine includes selection, detection and recentered checks.
Limits are four selected panels and 12 detail calls. The app shares a bounded
provider semaphore across detail requests, configured by `IMAGE_API_MAX_CONCURRENT`
(default 2, maximum 32); the direct Python helper defaults to two without a supplied semaphore. Invalid bounds, repeated regions and budgets too small for
complete coverage are rejected. Pixels are not downsampled to fit more tiles.
Ambiguous panel proposals retain the full source with a limitation.

## Evidence and reconciliation

Each crop retains native pixels and maps its detections to the original frame
through one exact translation. The response binds to the submitted source hash
and dimensions; actual crop bounds/hashes appear separately. The displayed image
remains the source snapshot.

Full observations merge conservatively by geometry, category and literal label.
Coordinates come from a real observation and are never averaged. Adjacent
doorways and conflicting labels remain separate; unresolved overlaps stay
uncertain/partial.

Category aliases depend on the declared counting grain. Literal source labels
remain unchanged; comparison-only whitespace normalization and stable row IDs
help link observations. Strong spatial evidence can group near-identical O/0
readings as an explicitly uncertain hypothesis; both readings remain in
`detail.observations[].source_labels`. Genuine conflicting IDs and distant
repeated labels remain separate. Fixed anchors avoid transitive cluster collapse.

In tile mode, clipped fragments are deferred when another successful tile sees
their center farther from its edges. They remain in `detail.deferred_observations`
with source boxes and IDs, and cause a partial result. They are not counted as
additional full detections. This ownership rule does not prove that the
neighboring view found every object.

With budget remaining, clipped or disputed survivors receive recentered
inspection. Fresh certain, nonclipped geometry can supersede a corroborated old
fragment. Empty or failed checks preserve unresolved evidence. Suggested follow-up
rectangles remain in `detail.reinspection_regions`.

`verify_membership` defaults true. An uncertain object proposal can receive one
focused supported/rejected/ambiguous check instead of another regional inventory.
Only an explicit source-supported rejection removes it; uncertainty and provider
failure preserve the proposal. `detail.membership_checks` records source boxes,
verdicts and reasons, displayed in the frontend with rejected-source close-ups.
Checking detected objects does not find objects the detector missed.

The trace records selected bounds, actual crop bounds/hashes/statuses, surviving
candidates' observation and region IDs, deferred/superseded fragments and actual
provider-call count. Token metrics sum selection, detection and reinspection.
An attempt with unknown usage makes the total null. The HTTP response also
exports each actual attempt in `decision_trace.calls`,
with model, timestamp, usage, actual input hash/dimensions and source crop bounds.
The frontend prices these calls separately, preserving unknown usage and mixed
Hydrogen/Carbon rates, and shows total client response time.

Candidates and inventory completeness remain unverified. Physical measurement,
calibration, final-answer planning and multi-provider arbitration remain separate
coordinator operations. The fetched capability router is now integrated with this
endpoint: auto/shadow selects a profile once, Hydrogen proposes panels, and the
selected analyzer handles detections and membership checks. Full-panel targets
retain their context. Explicit tools remain independently callable; the detail
module itself contains no decision tree. See the [routing setup](README.md#experimental-capability-routing).

## Python operations

The host supplies canonical `prepare_image` output and owns the temp directory.
Native tools reject reduced overviews. Tool arguments do not supply arbitrary
filesystem paths.

```python
from image_api.detail import DetailOptions, DetailTools

tools = DetailTools(candidate_service, gemini_client)
selection = await tools.propose_regions(image, question, request_id)
result = await tools.extract(image, question, request_id, owned_temp_directory,
    DetailOptions(mode="tiles", max_calls=9))
```

Independent operations available to the decision system:

- `GeminiRegionProposer.propose`: semantic panel proposals.
- `crop_region`, `tile_boxes`, `tile_regions`: native pixels, complete selected
  coverage, hashes and crop-to-source transformations.
- `reconcile_candidates`: combine observations in one source frame.
- `partition_tile_observations`: defer clipped fragments to successful interior
  views while preserving those records.
- `propose_reinspection_regions`: bounded recentered follow-up rectangles.
- `apply_reinspection`: incorporate new corroborating fragment evidence with
  explicit superseded IDs.
- `GeminiCandidateVerifier.verify`: classify one proposed object's membership
  without generating additional objects.
- `read_source_labels`: optional local OCR anchors from the existing preprocessor.
  It preserves literal words, source frames and recognition status. OCR remains
  off by default: its confidence does not establish correctness, and it can
  miss/misread identifiers even on otherwise clear plans.

Uploads and crops are request-local. Cancellation drains provider tasks and
crop workers before cleanup.

## Verification

```text
python -m unittest tests.test_region_tools tests.test_region_proposal tests.test_image_reconciliation tests.test_image_detail -v
```

The opt-in `experiments/image_questions/run_detail.py` records prompts, schemas,
source hashes, replies, usage and an overlay. It takes `--source`, a new ignored
`--output`, optional `--mode`, `--regions`, `--question`, and requires `--run`.
Use authorized source material. Reference answers never enter these tools.
The [earlier investigation](../experiments/image_questions/LARGE_SCAN_LOCALIZATION.md)
records manually selected crops. Automatic-tool observations are separate and
do not update the original 100-image benchmark.
