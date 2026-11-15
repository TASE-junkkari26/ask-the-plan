# Mixed-source 250-question evaluation

This development run exercises the production source registration and common
answer routes with live configured providers. The category report gives peers
the results and limitations without downloading the dataset. [Results](RESULTS.md)

## Sample

Seed `20261115` selects 250 supplied question rows across 83 semantic families
and 207 source assets. Fixed category allocations cover 75 CubiCasa PNG
questions, 75 Swiss PDF questions, 25 IFC-derived floor/view PDF questions,
25 Opening Design PDF questions, 25 quantitative IFC questions and 25 IFC-Bench
questions. Families cycle in a shuffled order. Rows are shuffled within each
family, with preference for previously unused sources. This deliberately gives
the smaller categories more coverage than their share of the full dataset.

IFC-derived PDF selection requires the dataset classifier's explicit floor/view
scope. Original question wording and source identifiers are preserved.
The supplied question file has PNG, PDF and IFC question rows. DXF import has
separate implementation and regression checks.

## Execution and scoring

The runner uses the same Python application, upload parsing, temporary sessions,
planner validation, deterministic engine and evidence contracts as the app.
HTTP requests use an in-process ASGI transport. Live inference uses the backend
configuration. The first phase admitted four concurrent questions, with three
drawing workers and one serialized IFC worker. After 218 outcomes were saved,
the user requested more parallelism. The remaining 32 drawing questions used
up to eight drawing workers, with an admission setting of nine. Questions on
the same source retain their order.

Drawing questions register the original source and a displayed PNG, then request
Detailed scan through `/api/v1/answers`. PDF rendering uses the installed PDF.js,
the frontend's full-page pixel limits and Node canvas. Rotation, viewport
transform, source bounds and display hashes are retained. IFC originals are
parsed locally. The independently configured planner receives bounded native
IFC or PDF catalogs and the question.

All selected outputs are saved before the separate scoring step opens reference
answers. Count agreement requires exact numeric equality. Quantities use the
existing scorer's dimension/unit checks and 2% relative tolerance. The report
keeps qualified visual observations, exact numeric-and-structural passes,
non-answers and execution errors visible. Text questions require source review.
Automatic evidence checks verify response bindings and internal references.
Object membership, source localization and descriptive correctness require
additional human review.

## Reproduce

Use the configured Python environment, frontend dependencies and original
challenge dataset. The live step submits public source snapshots and questions
to the configured providers and can incur inference charges.

```powershell
$evaluationRun = 'build/review-250-my-run'
.\.venv\Scripts\python.exe -m experiments.review_250.run plan --run-dir $evaluationRun --seed 20261115
node experiments/review_250/render_pdfs.mjs $evaluationRun dataset/junction-dataset
.\.venv\Scripts\python.exe -u -m experiments.review_250.run run --run-dir $evaluationRun --workers 4
.\.venv\Scripts\python.exe -m experiments.review_250.run score --run-dir $evaluationRun
```

On Linux use `.venv/bin/python`. Run directories contain the input-only sample,
original and display hashes, runtime settings/code hashes, PDF render metadata,
compressed full predictions and scored outcomes. They remain under ignored
`build/`. Repeating the live command reuses recorded outcomes when code,
configuration and displayed snapshots still match. An interrupted started
question receives an explicit unknown-usage outcome on ordinary resume.

The recorded run used an explicit concurrency handoff after stopping its owned
worker process. The following continuation preserves completed outputs, records
the new worker phase and retries unfinished started questions while retaining
their previous attempt markers.

```powershell
.\.venv\Scripts\python.exe -u -m experiments.review_250.run run --run-dir $evaluationRun --workers 9 --change-concurrency --retry-interrupted
```

Question inputs, source/display hashes, providers and production runtime code
must still match across that handoff. Three interrupted questions in the
recorded run were retried with unknown prior usage. Call and cost totals retain
that uncertainty. [Concurrency and results](RESULTS.md)

The source datasets retain their supplied licenses and attributions. The sample
includes CubiCasa5K, Swiss Dwellings/Archilyse, OpeningDesign and the model-specific
IFC licenses supplied by the organizer.
