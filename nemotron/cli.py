"""Small opt-in live check and text/image request CLI; no key argument."""
from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from time import perf_counter

from .client import NemotronClient, NemotronError, completion_text
from .config import ConfigurationError, NemotronSettings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Call the configured Verda Nemotron text/vision endpoint.")
    parser.add_argument("--env-file", type=Path, help="Explicit .env file; defaults to the checkout root.")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("check", help="Send one short text request to check authentication and inference.")
    ask = commands.add_parser("ask", help="Send a prompt, optionally with local images.")
    ask.add_argument("prompt")
    ask.add_argument("--image", action="append", default=[], type=Path, help="Local PNG/JPEG/WebP; repeat for multiple images.")
    ask.add_argument("--system", help="Optional system instruction.")
    ask.add_argument("--max-tokens", type=int, help="Override the output token budget for this request.")
    ask.add_argument("--json-mode", action="store_true", help="Request and validate a JSON object response.")
    args = parser.parse_args(argv)
    try:
        settings = NemotronSettings.from_env(args.env_file)
        started = perf_counter()
        with NemotronClient(settings) as client:
            if args.command == "check":
                completion = client.ask("Reply with exactly OK.", max_tokens=256)
            else:
                system = args.system
                options = {"max_tokens": args.max_tokens}
                if args.json_mode:
                    system = f"{system or ''}\nReturn one JSON object. Return only JSON.".strip()
                    options["response_format"] = {"type": "json_object"}
                completion = client.ask(args.prompt, system=system, images=args.image, **options)
            text = completion_text(completion)
        result = {
            "status": "connected" if args.command == "check" else "completed",
            "model": completion.model, "text": text,
            "finish_reason": completion.choices[0].finish_reason,
            "usage": completion.usage.model_dump(exclude_none=True) if completion.usage else None,
            "latency_ms": round((perf_counter() - started) * 1000),
        }
        if args.command == "ask" and args.json_mode:
            try:
                data = json.loads(text)
            except ValueError:
                raise NemotronError("Nemotron returned invalid JSON in JSON mode.") from None
            if not isinstance(data, dict):
                raise NemotronError("Nemotron returned a non-object JSON value in JSON mode.")
            result["data"] = data
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except ConfigurationError as exc:
        print(f"Nemotron configuration: {exc}", file=sys.stderr)
        return 2
    except NemotronError as exc:
        print(f"Nemotron: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        print("Nemotron request cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
