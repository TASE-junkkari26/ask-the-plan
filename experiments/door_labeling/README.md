# Nemotron door-labeling pilot

Question: can the configured Nemotron VL endpoint produce useful door-instance
boxes from a raster floor plan, without being told the reference count?

The first input is `dataset/junction-dataset/data/cubicasa5k/colorful-10052.png`.
It is a clear colored plan with a double-leaf door and several single-leaf doors.
This is one development example, not a held-out accuracy benchmark.

See [the first run's findings](RESULTS.md) for the result and visual review.

After installing the optional dependencies described in [Experiments](../README.md),
run from the repository root:

```powershell
.\.venv\Scripts\python.exe -m experiments.door_labeling --evaluate-reference
```

This sends **one inference request**, with automatic retries disabled. The prompt
asks for a list of logical door instances and normalized `xyxy` coordinates over
the entire image. The count is calculated from that list. The source is uploaded
unmodified; no crop/resize transformation is applied in this first baseline.

Each timestamped directory under `experiments/runs/door-labeling/` contains:

- `input.png`, source credit and licence: exact input and attribution.
- `request.json`: source hash, code revision/runner hash, dimensions, settings,
  exact instructions and response schema. Credentials and image payloads are excluded.
- `response.json`: returned text, model, finish reason, token usage and elapsed time.
- `predictions.json`: validated normalized boxes plus original-image pixel boxes.
- `annotated.png` and `proposal-crops.jpg`: original-coordinate overlays and context crops.
- `reference-check.json`, if requested: count comparison performed only after
  saving the prediction. It does not verify localization.
- `summary.json`, or `error.json` if the request/validation fails.
- `cost-estimate.json` and `README.md`: token-cost arithmetic, dated reference
  rates/source, effective project cost, and a visible result/overlay summary.
- `runner-source.py.txt`: the exact runner source matching the recorded hash.

All boxes start as **unreviewed proposals**. Inspect each crop for the door leaf,
missed doors, duplicate leaves, open passages and cabinet/window false positives.
Keep human corrections separate from raw predictions. A correct total can hide a
miss and a false positive; schema-valid coordinates can still be inaccurate.

The pilot is restricted to CubiCasa PNG inputs so that its attribution is correct.
The original images and reference answers remain unchanged. The derived overlay
and crops retain CC BY-NC-SA 4.0 attribution and are used for this non-commercial
challenge experiment. Only [the first example run](../runs/door-labeling/20261113T234605960384Z/README.md)
is checked in; all future run directories are ignored.

The price snapshot in [pricing.json](pricing.json) uses Together's public
OpenRouter listing for the same named Nemotron model. It is an API-equivalent
estimate rather than a tariff for the custom Verda endpoint. All reported prompt
tokens, including image tokens, use the uncached input rate; completion tokens
use the output rate. Discounts, taxes and separate image charges are excluded.
The project's effective access cost is recorded separately as zero, as reported
by the owner, without claiming verification against a billing account.

To recompute the report from saved usage without calling the model:

```powershell
.\.venv\Scripts\python.exe -m experiments.door_labeling.reporting experiments/runs/door-labeling/20261113T234605960384Z
```
