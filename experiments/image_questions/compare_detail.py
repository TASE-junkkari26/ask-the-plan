"""Compare completed, identically sampled candidate-count benchmark runs.

Reads saved evaluations only after completion guards; never accesses source QA
or performs inference. Count agreement is not localization accuracy.
"""
from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import statistics


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def completed(run):
    cases = read(run / "cases.json")["cases"]
    if not (run / "run-complete.json").is_file() or any(
            not (run / case["id"] / "outcome.json").is_file() for case in cases):
        raise ValueError("Both runs must finish every case before comparison")
    return cases


def group_rows(pairs, field):
    rows = {}
    for value in sorted({old[field] for old, _ in pairs}):
        group = [(old, new) for old, new in pairs if old[field] == value]
        rows[value] = {
            "cases": len(group),
            "baseline_matches": sum(bool(old["exact_count_match"]) for old, _ in group),
            "detail_matches": sum(bool(new["exact_count_match"]) for _, new in group),
            "improved": sum(not old["exact_count_match"] and new["exact_count_match"] for old, new in group),
            "regressed": sum(old["exact_count_match"] and not new["exact_count_match"] for old, new in group),
        }
        rows[value]["net_change"] = rows[value]["detail_matches"] - rows[value]["baseline_matches"]
    return rows


def compare(baseline, detail):
    old_cases, new_cases = completed(baseline), completed(detail)
    keys = ("id", "line", "path", "question", "source", "family", "language", "page")
    if len(old_cases) != len(new_cases) or any(
            any(old.get(key) != new.get(key) for key in keys)
            for old, new in zip(old_cases, new_cases)):
        raise ValueError("Case identities/order differ")
    for case in old_cases:
        old_source = read(baseline / case["id"] / "source.json")
        new_source = read(detail / case["id"] / "source.json")
        if any(old_source[key] != new_source[key] for key in
               ("input_sha256", "source_sha256", "width", "height")):
            raise ValueError(f"Source identity/frame differs: {case['id']}")

    old_eval, new_eval = read(baseline / "evaluation.json"), read(detail / "evaluation.json")
    old_rows = {row["id"]: row for row in old_eval["cases"]}
    new_rows = {row["id"]: row for row in new_eval["cases"]}
    if set(old_rows) != set(new_rows) or set(old_rows) != {case["id"] for case in old_cases}:
        raise ValueError("Saved evaluations do not cover the same cases")
    pairs = [(old_rows[case["id"]], new_rows[case["id"]]) for case in old_cases]
    if any(old["reference_count"] != new["reference_count"] for old, new in pairs):
        raise ValueError("Reference counts differ between saved evaluations")
    changed = []
    for old, new in pairs:
        if old["exact_count_match"] != new["exact_count_match"]:
            changed.append({key: new[key] for key in ("id", "source", "family", "question", "reference_count")}
                           | {"transition": "improved" if new["exact_count_match"] else "regressed",
                              "baseline_count": old["predicted_candidate_count"],
                              "detail_count": new["predicted_candidate_count"],
                              "baseline_status": old["status"], "detail_status": new["status"],
                              "detail_http_status": new["http_status"]})

    traces, failures = [], []
    for case in new_cases:
        outcome = new_rows[case["id"]]
        response_path = detail / case["id"] / "api-response.json"
        body = read(response_path) if response_path.is_file() else {}
        if body.get("detail"):
            trace = body["detail"]
            traces.append({"id": case["id"], "calls": trace["provider_calls"],
                           "regions": len(trace["regions"]),
                           "deferred": len(trace.get("deferred_observations", [])),
                           "superseded": len(trace.get("superseded_observation_ids", [])),
                           "pending_reinspection": len(trace.get("reinspection_regions", []))})
        if outcome["http_status"] != 200:
            failures.append({"id": case["id"], "source": case["source"],
                             "http_status": outcome["http_status"], "status": outcome["status"]})

    by_source, by_family = group_rows(pairs, "source"), group_rows(pairs, "family")
    summary = {
        "cases": len(pairs), "same_case_order_and_source_frames": True,
        "baseline_matches": sum(bool(old["exact_count_match"]) for old, _ in pairs),
        "detail_matches": sum(bool(new["exact_count_match"]) for _, new in pairs),
        "improved": sum(item["transition"] == "improved" for item in changed),
        "regressed": sum(item["transition"] == "regressed" for item in changed),
        "both_correct": sum(old["exact_count_match"] and new["exact_count_match"] for old, new in pairs),
        "both_wrong": sum(not old["exact_count_match"] and not new["exact_count_match"] for old, new in pairs),
        "strict_ok_matches": {"baseline": old_eval["summary"]["strict_ok_matches"],
                              "detail": new_eval["summary"]["strict_ok_matches"]},
        "by_source": by_source, "by_family": by_family, "by_language": group_rows(pairs, "language"),
        "status_counts": {"baseline": dict(Counter(old["status"] for old, _ in pairs)),
                          "detail": dict(Counter(new["status"] for _, new in pairs))},
        "failures": failures,
        "budget_failures": [row for row in failures if row["status"] in {"call_budget", "invalid_regions"}],
        "traces": traces,
        "trace_totals": {"successful_responses_with_trace": len(traces),
                         "calls_in_successful_response_traces": sum(t["calls"] for t in traces),
                         "deferred_observations": sum(t["deferred"] for t in traces),
                         "responses_with_deferred": sum(t["deferred"] > 0 for t in traces),
                         "pending_reinspection_regions": sum(t["pending_reinspection"] for t in traces)},
        "latency_seconds": {"baseline": old_eval["summary"]["latency_seconds"],
                            "detail": new_eval["summary"]["latency_seconds"]},
        "provider_attempts": {"baseline": old_eval["summary"]["provider_attempts"],
                              "detail": new_eval["summary"]["provider_attempts"]},
        "returned_models": {"baseline": dict(Counter(old.get("returned_model") for old, _ in pairs)),
                            "detail": dict(Counter(new.get("returned_model") for _, new in pairs))},
        "estimated_standard_cost_usd": {"baseline": old_eval["summary"]["estimated_standard_cost_usd"],
                                        "detail": new_eval["summary"]["estimated_standard_cost_usd"]},
        "measurement": "Paired exact candidate-list count agreement; partial results count, abstentions/errors never become zero. No localization/final-answer accuracy is measured.",
        "latency_caveat": "The baseline admitted six parallel cases; this detailed rerun is serial. Per-case timing is descriptive and wall time is not a controlled concurrency comparison.",
    }
    for arm, key in (("baseline", "baseline_matches"), ("detail", "detail_matches")):
        count = summary[key]
        summary.setdefault("estimated_cost_per_matching_case_usd", {})[arm] = (
            summary["estimated_standard_cost_usd"][arm]/count if count else None)
    summary["macro_family_match_rate"] = {
        arm: statistics.mean(row[f"{arm}_matches"]/row["cases"] for row in by_family.values())
        for arm in ("baseline", "detail")}
    output = {"summary": summary, "changed_cases": changed}
    (detail / "comparison.json").write_text(json.dumps(output, ensure_ascii=False, indent=2), encoding="utf-8")

    report = ["# Same 100 cases: detailed scan comparison", "", summary["measurement"], "",
              f"Baseline **{summary['baseline_matches']}/{len(pairs)}**; detailed scan **{summary['detail_matches']}/{len(pairs)}**.",
              f"Improved: {summary['improved']}; regressed: {summary['regressed']}; both correct: {summary['both_correct']}; both wrong: {summary['both_wrong']}.", "",
              "| Source | Cases | Baseline | Detail | Improved | Regressed |", "|---|---:|---:|---:|---:|---:|"]
    for source, row in by_source.items():
        report.append(f"| {source} | {row['cases']} | {row['baseline_matches']} | {row['detail_matches']} | {row['improved']} | {row['regressed']} |")
    report += ["", "## Changed cases", "", "| ID | Transition | Family | Reference | Baseline count | Detail count | Detail status |", "|---|---|---|---:|---:|---:|---|"]
    for row in changed:
        report.append(f"| {row['id']} | {row['transition']} | {row['family']} | {row['reference_count']} | {row['baseline_count']} | {row['detail_count']} | {row['detail_status']} |")
    report += ["", "## Operational comparison", "", "```json", json.dumps({key: summary[key] for key in (
        "strict_ok_matches", "status_counts", "provider_attempts", "estimated_standard_cost_usd",
        "estimated_cost_per_matching_case_usd", "latency_seconds", "trace_totals", "failures")}, indent=2),
        "```", "", summary["latency_caveat"], "",
        "All cases remain in the denominator. API budgets/failures are not retried or removed. Strict `ok` agreement is separate because detailed scan deliberately marks deferred seams partial.",
        "Cost sums saved provider replies across selection, detection and reinspection; unsuccessful calls may have unreported charges. This is a development sample, not a held-out accuracy estimate."]
    (detail / "COMPARISON.md").write_text("\n".join(report)+"\n", encoding="utf-8")
    print(json.dumps({key: summary[key] for key in ("cases", "baseline_matches", "detail_matches", "improved", "regressed", "estimated_standard_cost_usd")}, indent=2))
    return output


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--baseline", type=Path, required=True)
    parser.add_argument("--detail", type=Path, required=True)
    args = parser.parse_args()
    compare(args.baseline, args.detail)
