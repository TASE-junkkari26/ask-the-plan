# Supplied Nemotron inference configuration

Configuration supplied during the hackathon; documentation reviewed 14 November
2026. This records an integration candidate, not a tested service or installed
application dependency. The current mock frontend and IFC CLI make no model calls.

| Setting | Supplied value |
|---|---|
| Service | Verda/DataCrunch Nemotron endpoint |
| OpenAI-compatible base URL | `https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1` |
| Model ID | `nemotron-3.5-super-vl` |
| Backend environment variable | `VERDA_INFERENCE_KEY` |

Verify authentication, model listing, structured-output behavior, image support,
timeouts, limits, latency, and billing with a bounded experiment before routing
queries to it. Tool/image capabilities and token limits below are supplied
configuration values, not measurements. Keep credentials on the backend; never
put them in browser code, `VITE_*` variables, examples, or logs.

The following OpenCode configuration was supplied as an example. Its keys and
provider package have not been verified against a particular OpenCode release;
check that release's configuration before using it. It is not the application's
backend adapter configuration.

```json
{
  "$schema": "https://opencode.ai/config.json",
  "model": "verda-nemotron/nemotron",
  "providers": {
    "verda-nemotron": {
      "name": "Verda Nemotron 3.5 Super VL",
      "env": ["VERDA_INFERENCE_KEY"],
      "package": "@opencode/ai/providers/openai-compatible",
      "settings": {
        "baseURL": "https://containers.datacrunch.io/nemotron-3-5-super-vl-b300/v1",
        "apiKey": "{env:VERDA_INFERENCE_KEY}"
      },
      "models": {
        "nemotron": {
          "modelID": "nemotron-3.5-super-vl",
          "name": "Nemotron 3.5 Super VL",
          "capabilities": {
            "tools": true,
            "input": ["text", "image"],
            "output": ["text"]
          },
          "compatibility": {
            "maxTokensField": "max_tokens",
            "reasoningField": "reasoning_content"
          },
          "limit": {
            "context": 1048576,
            "output": 32768
          }
        }
      }
    }
  }
}
```

See the [stack recommendation](TECH_STACK_RECOMMENDATION.md) for the proposed
planner boundary and [compute notes](../dataset/compute.md) for reported grants.
