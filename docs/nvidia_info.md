# Verda Nemotron integration

Implemented 14 November 2026 in [nemotron/](../nemotron/). The backend adapter
supports synchronous/asynchronous Chat Completions, local PNG/JPEG/WebP images,
JSON-object output with Pydantic validation, tool-call transport, bounded retries,
and request timeouts. A CLI sends a connection check or a text/image request.

The frontend and IFC CLI remain independent. This adapter does not implement a
question planner, object detector, annotation batch job, or drawing-analysis API.
Model predictions and syntactically valid JSON do not establish source truth,
correct localization, or a complete object inventory.

## One local setup step

In the prepared checkout, dependencies are installed in `.venv` and the local
ignored **`.env` already exists**. Paste the inference key after:

```dotenv
VERDA_INFERENCE_KEY=
```

No model/URL changes or shell exports are needed. For a fresh clone, install the
project with `python -m pip install -e ".[test]"` in a virtual environment and copy
[.env.example](../.env.example) to `.env` first. See [README](../README.md) for
platform-specific installation commands. Never put the key in frontend code,
`VITE_*`, command-line arguments, screenshots, or committed files.

Settings load when a client is created, not at import time. In an editable
checkout, `.env` resolves from the repository root even when the working directory
differs. A regular wheel installation uses the current directory's `.env`.
Existing process environment values take precedence over file values. Loading
does not mutate `os.environ` or expand dollar sequences in keys. Explicitly select
a different file with `python -m nemotron --env-file PATH check`.

## Defaults

| Setting | Default | Meaning |
|---|---|---|
| `VERDA_INFERENCE_KEY` | Empty; required | Verda inference credential, sent as a Bearer token |
| `VERDA_BASE_URL` | `https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1` | Supplied Junction deployment's OpenAI-compatible base URL |
| `VERDA_MODEL` | `nemotron-3.5-super-vl` | Supplied deployment's model ID |
| `VERDA_TIMEOUT_SECONDS` | `120` | Per-attempt timeout, up to 600 seconds; connection timeout is at most 10 seconds |
| `VERDA_MAX_RETRIES` | `2` | Retries after the initial attempt, bounded to 0-5 |
| `VERDA_MAX_TOKENS` | `2048` | Output-token budget, sent as `max_tokens` |
| `VERDA_TEMPERATURE` | `0.2` | Sampling temperature, 0-2 |
| `VERDA_ENABLE_THINKING` | `false` | Sends `chat_template_kwargs.enable_thinking`; `true` enables it, `auto` omits the parameter |

The model supports reasoning mode in its documented chat template. Thinking is
disabled by default to preserve the output budget for short answers and JSON.
These are configurable request defaults, not measured accuracy/cost claims.

The SDK retries connection failures, timeouts, HTTP 408/409/429 and server errors.
Authentication errors do not retry. Timeouts apply to each attempt, so a retried
request can take longer than `VERDA_TIMEOUT_SECONDS`. Reuse a client within a batch
and bound concurrency at the worker level. Never retry indefinitely.

Verda's general inference documentation now uses `https://inference.verda.com/v1`.
This project deliberately defaults to the separately supplied hackathon deployment;
it does not silently switch endpoints or substitute the NVIDIA-hosted model ID.

## CLI usage

Run from the repository root. Windows PowerShell:

```powershell
.\.venv\Scripts\python.exe -m nemotron check
.\.venv\Scripts\python.exe -m nemotron ask "Reply with a short greeting."
.\.venv\Scripts\python.exe -m nemotron ask "Describe the door symbols; retain any uncertainty." --image "dataset/junction-dataset/data/cubicasa5k/colorful-10052.png"
.\.venv\Scripts\python.exe -m nemotron ask 'Return a JSON object with a greeting field.' --json-mode
```

On Linux, replace `.\.venv\Scripts\python.exe` with `.venv/bin/python`.
After installation, `nemotron check` also works when the virtual environment's
scripts directory is on PATH. `--image` may be repeated. Images are embedded as
data URLs with media types detected from their headers; the application does not
host them at public URLs. Each image has a 20 MiB client limit. Render PDFs to
page images before sending them. Inference requests send supplied image pixels
and prompts to Verda.

Successful output contains answer text, returned model ID, finish reason, token
usage when the provider supplies it, and elapsed milliseconds. It excludes the
key, raw provider error bodies, image payloads, and separate reasoning content.
Exit codes: 0 success, 1 request/response error, 2 configuration error, 130 cancelled.
`check` makes **one short text request**; it does not verify image grounding or
structured-output support. Missing credentials fail before a network request.

## Python usage

```python
from nemotron import NemotronClient, completion_text

with NemotronClient() as client:
    reply = client.ask("Read the literal labels.", images=["drawing.png"])
    print(completion_text(reply))
    print(reply.usage)
```

Require locally validated JSON using any Pydantic response model:

```python
from pydantic import BaseModel, ConfigDict
from nemotron import NemotronClient

class DoorProposal(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # Original image pixels, top-left origin. Locations still need verification.
    boxes_xyxy: list[tuple[float, float, float, float]]
    uncertain: bool

with NemotronClient() as client:
    proposals = client.ask_json(
        "Propose boxes around door symbols. Keep uncertainty explicit.",
        DoorProposal,
        images=["drawing.png"],
    )
```

`ask_json` sends the response schema in the system instruction, requests JSON-object
mode, and validates the result locally. It rejects malformed/schema-invalid or
truncated answers. It does not claim server-enforced strict JSON Schema or correct
geometry. `chat(messages, response_format=..., tools=..., tool_choice=...)` exposes
the underlying Chat Completions response for advanced callers. Tool calls are
returned for application validation; this module never executes them.

```python
from nemotron import AsyncNemotronClient, completion_text

async def inspect_image(path):
    async with AsyncNemotronClient() as client:
        reply = await client.ask("Describe the symbols.", images=[path])
        return completion_text(reply)
```

`AsyncNemotronClient` also provides `chat` and `ask_json` with the same arguments.
For concurrent jobs, reuse a client and add a semaphore/queue in the worker. Keep
source/crop hashes and transforms with saved outputs; those belong to the future
ingestion/annotation pipeline, not to an unverified model claim.

## Verification and troubleshooting

Credential-free tests:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_nemotron -v
```

The 24 Windows Python 3.14 tests passed with OpenAI SDK 2.54.0, httpx 0.28.1 and
python-dotenv 1.2.4. They exercise serialized text/image/JSON/tool requests,
environment precedence, credential redaction, async calls, timeout handling,
transient retries, authentication failures, malformed provider responses, and
truncated/invalid output. These mocked HTTP tests do not establish blueprint accuracy.

Separate authenticated checks passed on 14 November 2026 after the key was added:

- The `check` command returned `OK` from `nemotron-3.5-super-vl` in 884 ms, with
  21 prompt tokens and 2 completion tokens (23 total; zero reasoning tokens).
- An async image/JSON request correctly identified a generated 32 by 32 red PNG
  and reported no text, returning locally validated JSON in 6348 ms.

These checks establish working authentication, text completion, image input,
JSON-object mode, and both client paths for those small requests. They do not
measure blueprint localization/count accuracy, sustained throughput, or general
schema adherence. The service may impose its own quotas or limits.

| Outcome | Action |
|---|---|
| Missing key / configuration exit 2 | Fill `VERDA_INFERENCE_KEY` in the checkout's `.env`; check for an overriding shell variable |
| HTTP 401 / 403 | Verify that the inference credential is valid for this deployment |
| HTTP 404 | Verify deployment availability, base URL and deployment-specific model ID |
| HTTP 400 | Inspect endpoint support for the requested image/JSON/thinking mode; `VERDA_ENABLE_THINKING=auto` omits the optional template parameter |
| HTTP 429 | Reduce concurrent requests and check provider quota; retries are already bounded |
| Token-limit/empty-answer error | Shorten input or increase the output budget; keep thinking disabled for short extraction requests |

Protocol sources checked during implementation: [Verda OpenAI compatibility](https://docs.verda.com/inference/openai-compatibility/),
[OpenAI SDK](https://github.com/openai/openai-python), and
[NVIDIA Nemotron model card](https://build.nvidia.com/nvidia/nemotron-3.5-super-vl-120b-a12b/modelcard).
See [the stack recommendation](TECH_STACK_RECOMMENDATION.md) for the planned
interpreter boundary and [compute notes](../dataset/compute.md) for reported grants.
