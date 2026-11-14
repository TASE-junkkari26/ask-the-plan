# Experiments

Small, reproducible investigations live here. Experiment code, prompts, and
written findings can be versioned. Local run artifacts are written under
`experiments/runs/` and ignored by default. The single checked-in example is
[the first door-labeling run](runs/door-labeling/20261113T234605960384Z/README.md);
future runs stay ignored. Keep original drawing assets and reference answers unchanged.

- [Door labeling with Nemotron](door_labeling/README.md): one-image, zero-shot
  bounding-box proposals, saved model output, overlays, and post-inference review.
- [Live 2D question evaluation](image_questions/README.md): eight production-API
  questions, six diagnostic calls, source-derived PDF/DXF comparisons, and a
  [recommended hybrid direction](image_questions/RESULTS.md). No IFC cases.

Record the source hash, input dimensions, exact instructions/schema, model and
sampling settings, token usage, elapsed time, and code revision. Preserve source
attribution in image artifacts. Save model output before inspecting references;
reference answers are evaluation inputs and must not enter the labeling prompt.
Separate automatic schema checks, count agreement, and manual localization review.
Model proposals remain provisional labels until reviewed.

Door-labeling runs also include a nominal API cost estimate, its dated reference
tariff/source, and the project's effective cost. The nominal estimate uses the
reported token usage; the effective project cost is zero as reported by the owner.

From the repository root, install optional image tooling once:

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[experiments]"
```

Use `.venv/bin/python` on Linux. Credentials are read through the existing
backend [Nemotron client](../docs/nvidia_info.md); never save credentials,
authorization headers, or full base64 request payloads in run artifacts.
