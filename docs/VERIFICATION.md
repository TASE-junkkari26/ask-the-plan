# Sprint-one verification record

Checked 14 November 2026 on Windows, using the existing virtual environment and
frontend dependencies. This records checks performed during the documentation
hardening pass. It does not establish complete hackathon question coverage.

## Environment and commands

Python 3.14.10, IfcOpenShell 0.9.0.post1, Pydantic 2.14.3; Node 24.22.3 and npm
11.19.1. In the table, `python` means `.\.venv\Scripts\python.exe` on Windows or
`.venv/bin/python` on Linux. Commands run from the repository root except the
explicitly marked frontend smoke check. Linux was not rerun in this pass.

| Check | Observed result |
|---|---|
| `python -m unittest discover -s tests -v` | 106 passed, no skips: contracts, IFC, Nemotron mocked HTTP, cost reporting, and 15 documentation-checker regressions. |
| `python -m pip check` | No broken installed requirements. This is not a fresh-install test or dependency lock. |
| `npm.cmd run test:frontend` | 11 logic tests passed. |
| `npm.cmd run build` | TypeScript check and Vite production build passed. |
| `node scripts/smoke-render.mjs` from `frontend/` | Server-rendered initial workspace: eight marks, eight evidence rows, unique SVG IDs. No browser launched. |
| Demo fixture export followed by Pydantic validation | All 28 exported `QueryResult` envelopes passed. No bundle/plan semantic validation is claimed. |
| `python -m contracts.export --check` | All six generated JSON Schemas current. |
| `python scripts/classify_questions.py --report-date 2026-11-14 --check` | Report reproduced: 127,044 rows, 6,789 literal texts, 234 analysis families, no unclassified rows. |
| Preview audit with its default input, writing under `build/docs-audit/` | 910 assets, 7,990 QA rows, no missing/null answers; also passed from a different working directory. |
| `python scripts/check_docs.py` | All maintained Markdown local links/images and supported anchors passed. |
| `git diff --check` | Passed. |

The audit helper now resolves its default preview relative to the script, rather
than an obsolete nested path relative to the caller. The drawing inputs and
tracked audit reports were left unchanged. Create an output directory before
using its `--output` option.

The real-model test read
`dataset/junction-dataset-preview/data/ifc_models/bsc-esplanades_1807-ep-ar-v18.ifc`
and checked 211 model-wide doors and 42 on `4.korrus`. Without that optional file,
this test skips; another extraction layout is not searched automatically. Other
IFC quantities/counts in the [engine guide](IFC_ENGINE.md) remain separately dated
selected observations, not a corpus-wide accuracy score.

The build and server-rendering check initially hit the execution sandbox's
restriction on Vite/esbuild reading ancestor directories. Both passed when rerun
with normal filesystem access. No Vite configuration or execution policy was
changed to work around that environment restriction.

To repeat the demo-envelope check with the configured Python/Node environment:

```sh
python -c "import json, subprocess; from contracts.models import QueryResult; rows = json.loads(subprocess.check_output(['node', '--experimental-strip-types', 'frontend/scripts/export-demo-fixtures.ts'], encoding='utf-8')); [QueryResult.model_validate(row) for row in rows]; print(len(rows), 'envelopes validated')"
```

## Documentation check boundaries

The [offline checker](../scripts/check_docs.py) inventories tracked/non-ignored
Markdown using Git, including nested checked-in experiment reports. Without Git,
it scans maintained documentation directories. It checks inline/reference links,
images, filename case, Markdown headings, explicit HTML anchors, and `#Lx` or
`#Lx-Ly` source-line bounds. Code examples/comments are ignored. Its regressions
cover the previously missed image/report links, code fences, slug collisions,
encoded filenames, and optional-data handling.

Only links into the two named optional dataset roots can be skipped, and only
when that root is absent. If a root is installed, missing files inside it fail.
Distributed archive documentation is excluded from the project-doc inventory.
External URL availability, arbitrary non-Markdown fragment IDs, and every possible
Markdown extension are outside this automated check. Selected publisher pages
cited by the research guides were opened separately; archive downloads and
inference endpoints were not exercised by this pass.

## Remaining verification gaps

- Browser layout, keyboard/touch interactions, file preview/page navigation, and
  exported drawing artifacts still need browser checks on the demo devices.
- The frontend uses prepared results. A real question-to-planner-to-IFC-to-viewer
  flow, HTTP integration, and general raster extraction are not implemented.
- Dataset-wide answer accuracy, evidence localization, multilingual robustness,
  latency distributions, and inference cost have not been benchmarked here.
- No fresh dependency installation, Linux run, live inference request, or billing
  check was performed. The [Nemotron guide](nvidia_info.md) and saved
  [door-labeling experiment](../experiments/door_labeling/RESULTS.md) retain their
  earlier observations and limits.
