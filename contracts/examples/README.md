# Illustrative contract examples

These are synthetic integration examples, not extracted source data or benchmark
answers. The CAD room has a 20 m2 shell and a 1 m2 column hole. Its property stores
19,000,000 mm2 normalized to 19 m2, deliberately exercising squared-unit scaling.
The German label `7.16` remains literal when the question is in Finnish.

- `cad-area.bundle.json`: logical room, CAD and PNG representations, source
  anchors, native and pixel coordinate frames, a view-specific calibration,
  quantities, hierarchy, provenance, and complete scoped coverage.
- `cad-area.request.json`, `cad-area.plan.json`, `cad-area.result.json`: the
  matching multilingual single-room sum with unit normalization and a traceable
  quantity value. The select predicate resolves the literal room identifier
  before aggregation; no implicit singleton projection is required.
- `raster-incomplete.request.json`, `raster-incomplete.result.json`: uses the
  bundle's PNG attachment. An unfinished detector produces an explicit
  `incomplete_coverage` outcome, not an exact zero.
- `missing-property.request.json`, `missing-property.result.json`: uses the
  bundle's room identifiers and shows how to return unavailable information.

The result contracts illustrate response shape, not an implemented executor.
Never infer a physical building inventory from the illustrative fixture's
source-only coverage. Run the contract regression suite from the repository:

```sh
python -m unittest discover -s tests -v
```
