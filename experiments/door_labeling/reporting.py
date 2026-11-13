"""Add a dated token-cost estimate and browsable report to a saved run."""
from __future__ import annotations

import argparse
from decimal import Decimal
import json
from pathlib import Path
from typing import Any

PRICING_FILE = Path(__file__).with_name("pricing.json")
MILLION = Decimal(1_000_000)
USD_PRECISION = Decimal("0.00000001")


def price_snapshot() -> dict[str, Any]:
    return json.loads(PRICING_FILE.read_text(encoding="utf-8"))


def usd(value: Decimal) -> str:
    return format(value.quantize(USD_PRECISION), "f")


def estimate_cost(usage: dict[str, Any] | None) -> dict[str, Any]:
    snapshot = price_snapshot()
    result = {
        "status": "unavailable", "currency": "USD", "price_snapshot": snapshot,
        "effective_project_cost_usd": snapshot["effective_project_cost_usd"],
        "nominal_input_cost_usd": None, "nominal_output_cost_usd": None,
        "nominal_total_cost_usd": None,
    }
    if not usage or usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None:
        result["reason"] = "Provider token usage is unavailable; a nominal zero cost is not inferred."
        return result
    prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
    if any(not isinstance(value, int) or isinstance(value, bool) or value < 0 for value in (prompt, completion)):
        raise ValueError("Token counts must be non-negative integers.")
    input_rate = Decimal(snapshot["input_usd_per_million_tokens"])
    output_rate = Decimal(snapshot["output_usd_per_million_tokens"])
    input_cost = Decimal(prompt) * input_rate / MILLION
    output_cost = Decimal(completion) * output_rate / MILLION
    return {
        **result, "status": "estimated_at_reference_tariff",
        "prompt_tokens": prompt, "completion_tokens": completion,
        "nominal_input_cost_usd": usd(input_cost),
        "nominal_output_cost_usd": usd(output_cost),
        "nominal_total_cost_usd": usd(input_cost + output_cost),
        "nominal_cost_per_1000_equal_usage_requests_usd": usd((input_cost + output_cost) * 1000),
        "formula": "prompt_tokens / 1000000 * input_rate + completion_tokens / 1000000 * output_rate",
    }


def write_report(directory: Path) -> dict[str, Any]:
    response = json.loads((directory / "response.json").read_text(encoding="utf-8"))
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    cost = estimate_cost(response.get("usage"))
    summary["cost_estimate"] = cost
    for name, value in (("cost-estimate.json", cost), ("summary.json", summary)):
        (directory / name).write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rate = cost["price_snapshot"]
    nominal = f"USD {cost['nominal_total_cost_usd']}" if cost["nominal_total_cost_usd"] is not None else "Unavailable (missing usage)"
    reference_link = " · [Reference count comparison](reference-check.json)" if (directory / "reference-check.json").is_file() else ""
    text = f"""# Door-labeling run

| Measurement | Result |
|---|---|
| Returned door proposals | {summary['door_proposals']} |
| Inference elapsed | {response['elapsed_ms']} ms |
| Prompt / completion tokens | {(response.get('usage') or {}).get('prompt_tokens', 'unknown')} / {(response.get('usage') or {}).get('completion_tokens', 'unknown')} |
| Nominal API-equivalent cost | **{nominal}** |
| Effective project cost | **USD {cost['effective_project_cost_usd']}** (owner-reported free access) |
| Reference provider | {rate['reference_provider']} |
| Price snapshot checked | {rate['source_checked_on']} |

The published reference rates are USD {rate['input_usd_per_million_tokens']} per
million uncached input tokens and USD {rate['output_usd_per_million_tokens']} per
million output tokens. [Published model/provider prices]({rate['source_url']}).
This is a comparison tariff for the same named model, not a quote for the custom
Verda deployment or a measurement of GPU hardware cost. No billing account was
queried. All prompt tokens are priced as uncached; discounts, separate image
charges and taxes are excluded. Reasoning tokens are already part of completion
usage and are not counted twice.

The arithmetic, rate snapshot and assumptions are in [cost-estimate.json](cost-estimate.json).
The nominal estimate is computed from saved usage without another model request.

## Inspect the proposals

![Original drawing with model-proposed door boxes](annotated.png)

[Context crops](proposal-crops.jpg) · [Raw predictions](predictions.json) ·
[Request and source metadata](request.json) · [Model response and usage](response.json){reference_link}

Boxes are provisional model annotations. Count agreement does not validate their
extents or subtypes. See the separate review when available and the
[experiment findings](../../../door_labeling/RESULTS.md).

Source attribution: [ATTRIBUTION.txt](ATTRIBUTION.txt), [SOURCE_LICENSE.md](SOURCE_LICENSE.md).
The original source is retained as [input.png](input.png). The source and derived
overlay/crops retain CC BY-NC-SA 4.0 attribution for this non-commercial example.
The exact original runner, when present, is retained in `runner-source.py.txt` and
matches the hash recorded in `request.json`.
"""
    if (directory / "review.json").is_file():
        text += "\n[Separate assistant visual review](review.json). Raw predictions were not modified.\n"
    (directory / "README.md").write_text(text, encoding="utf-8")
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("run_directory", type=Path)
    args = parser.parse_args()
    summary = write_report(args.run_directory)
    print(json.dumps(summary["cost_estimate"], indent=2))


if __name__ == "__main__":
    main()
