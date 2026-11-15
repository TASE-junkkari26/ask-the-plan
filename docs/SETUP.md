# Local setup

Run commands from the repository root. Use Node.js **22.12+** (24 LTS is the
tested frontend baseline), Python **3.10+**, and an IfcOpenShell wheel for your
Python version and platform. Reuse installed dependencies on later launches.
Create native virtual environments and `node_modules` separately on each OS.

## Install once

Windows PowerShell uses `npm.cmd` to avoid the blocked `npm.ps1` wrapper.

```powershell
py -m venv .venv
.\.venv\Scripts\python.exe -m pip install -e ".[api,preprocess,vision]"
npm.cmd run setup:frontend
if (-not (Test-Path -LiteralPath .env)) { Copy-Item -LiteralPath .env.example -Destination .env }
```

Linux uses the matching native environment.

```sh
python3 -m venv .venv
.venv/bin/python -m pip install -e '.[api,preprocess,vision]'
npm run setup:frontend
test -f .env || cp .env.example .env
```

Virtual-environment activation is optional because the commands name its Python
executable. Debian/Ubuntu installations may also need `python3-venv`.
`setup:frontend` installs from `frontend/package-lock.json` with dependency
scripts disabled. The root package forwards commands into `frontend/`.

The `vision` extra enables the local OpenCV window checks. Tesseract OCR is a
separate optional installation described in [the preprocessor guide](DRAWING_PREPROCESSOR.md).

## Configure providers

Edit existing entries in the root `.env`. The drawing workbench uses Detailed
scan, which requires Gemini.

```dotenv
IMAGE_API_PROVIDER=gemini
GEMINI_API_KEY=
```

Fill the key locally. The default Gemini image profile is Hydrogen with low
thinking. Optional capability routing is configured with
`IMAGE_API_ROUTING_MODE=off|shadow|auto`; the default is `off`. The
[image API guide](../image_api/README.md#choose-the-image-provider) describes the
supported profiles and routing limits.

IFC and native PDF tool planning share the `IFC_API_PROVIDER` setting,
independently of the image analyzer. Its default is Nemotron, using the Verda
credential.

```dotenv
IFC_API_PROVIDER=nemotron
VERDA_INFERENCE_KEY=
```

To use Gemini Hydrogen for both planning paths, update the IFC selector.

```dotenv
IFC_API_PROVIDER=gemini
IFC_GEMINI_THINKING_LEVEL=high
```

That option uses the existing `GEMINI_API_KEY`, allowing both visual analysis and
language planning with one provider credential. The planner reasoning level is
independent of the image profile. Supported IFC grammar and direct native PDF
literal lookups can finish with zero model requests. Other native PDF questions
can send bounded extracted text spans to this planner to select source cells and
operations. Source extraction and arithmetic run locally. See [IFC planner settings](IFC_QUESTIONS.md#choose-the-ifc-planner)
for model, budget and discovery behavior.

Keep credentials in backend environment variables or the ignored `.env` file.
Existing process environment variables take precedence over file values.
Restart the Python backend after changing settings.

## Start the app

Open two terminals at the repository root and leave both running.

**Terminal 1 runs the backend.** It includes drawing analysis, DXF rendering,
source sessions and IFC extraction/query execution.

Windows PowerShell

```powershell
.\.venv\Scripts\python.exe -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

Linux

```sh
.venv/bin/python -m uvicorn image_api.app:app --host 127.0.0.1 --port 8000
```

**Terminal 2 runs the frontend.**

Windows PowerShell

```powershell
npm.cmd run dev
```

Linux

```sh
npm run dev
```

Open the Local URL printed by Vite, normally <http://127.0.0.1:5173/>. Import a
drawing or IFC model and ask a question. Vite proxies `/api` to port 8000.
The API documentation is available at <http://127.0.0.1:8000/docs>.

The IFC engine runs inside the backend. Browser IFC conversion and inspection
remain local until a question uploads the original to the local API. Image/PDF
questions upload the selected displayed page when asked. DXF import uploads the
original to the local backend to render the selected layout. Source sessions are
temporary, and browser imports are cleared on refresh.

For subsequent launches, repeat the two server commands. Stop each server with
Ctrl+C in its terminal.

## Use the IFC CLI

The same engine is available independently of the HTTP service.

```powershell
.\.venv\Scripts\python.exe -m ifc_engine --help
.\.venv\Scripts\python.exe -m ifc_engine inspect path/to/building.ifc
.\.venv\Scripts\python.exe -m ifc_engine count path/to/building.ifc door
```

On Linux, replace the executable with `.venv/bin/python`. These are command
templates. Use an actual source file from your local data. See [the IFC engine
guide](IFC_ENGINE.md) for property discovery, source-bound plans, quantities,
geometry methods and cache settings.

## Connection checks and troubleshooting

- `http://127.0.0.1:8000/health` checks image-provider configuration and returns
  200 when configured, or 503 for a missing/invalid setup. Provider reachability
  and IFC readiness require their own checks.
- If a question fails with an HTTP/proxy error, verify both servers are running.
  See [frontend connection troubleshooting](../image_api/README.md#troubleshoot-the-frontend-connection).
- A short live Verda check is available with
  `.\.venv\Scripts\python.exe -m nemotron check` on Windows or
  `.venv/bin/python -m nemotron check` on Linux. It makes a model request.
- If Node was installed after opening a terminal, restart the parent terminal.
  Keep the normal PowerShell execution policy and use `npm.cmd`.
- Drawing assets are downloaded separately from [the challenge brief](../dataset/task.md).
  Adjust dataset commands to the extracted root containing `questions.jsonl`
  and `data/`.

## Development checks

Install the optional test dependencies with the configured Python.

```powershell
.\.venv\Scripts\python.exe -m pip install -e ".[test]"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
npm.cmd run test:frontend
npm.cmd run build
.\.venv\Scripts\python.exe scripts/check_docs.py
```

On Linux, use `.venv/bin/python` and `npm`. Contract regeneration commands are
in [the repository checks](../README.md#checks-and-generated-contracts).
[The verification record](VERIFICATION.md) records actual runs, platforms and
skipped checks.
