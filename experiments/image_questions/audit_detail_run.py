"""Audit completed detailed-run identity, saved call pixels and serialization."""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime
import json
from pathlib import Path

from contracts.models import ImageCandidateResponse
from .benchmark import digest, write_json
from .benchmark_detail import protected_files


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def audit(run):
    manifest = read(run/"cases.json")
    plan = read(run/"comparison-plan.json")
    if not (run/"run-complete.json").exists():
        raise ValueError("Finish all responses before auditing the run")
    cases = {case["id"]: case for case in manifest["cases"]}
    baseline = Path(plan["baseline"])
    if protected_files(baseline) != plan["baseline_hashes"]:
        raise ValueError("Protected baseline files changed")
    if digest(run/"cases.json") != digest(baseline/"cases.json"):
        raise ValueError("Case manifest changed")
    call_counts, returned_models = Counter(), Counter()
    prior_case_end = None
    used_calls = set()
    for case in manifest["cases"]:
        target = run/case["id"]
        outcome = read(target/"outcome.json")
        started, ended = map(datetime.fromisoformat, (outcome["started_at"],outcome["completed_at"]))
        if prior_case_end is not None and started < prior_case_end:
            raise ValueError("Case requests overlapped")
        prior_case_end = ended
        source = read(target/"source.json")
        if digest(target/"input.png") != source["input_sha256"] or digest(target/"input.png") != digest(baseline/case["id"]/"input.png"):
            raise ValueError("Input byte identity changed")
        if outcome["http_status"] == 200:
            body = ImageCandidateResponse.model_validate(read(target/"api-response.json"))
            if body.image.sha256 != source["input_sha256"] or (body.image.width,body.image.height) != (source["width"],source["height"]):
                raise ValueError("Public response source binding mismatch")
            used_calls.update((case["id"],region.inference_sha256) for region in body.detail.regions)
    prior_call_end = None
    provider_inputs = set()
    incomplete = []
    for folder in sorted((run/"provider").iterdir()):
        request, timing = read(folder/"request.json"), read(folder/"timing.json")
        case_id = request["case_id"]
        if case_id not in cases or request["question"] != cases[case_id]["question"]:
            raise ValueError("Provider question/case binding mismatch")
        if digest(folder/"input.png") != request["image_sha256"]:
            raise ValueError("Provider image hash mismatch")
        if request["settings"]["model"] != "gemini-4-hydrogen" or request["settings"]["thinking_level"] != "low" or request["store"] is not False or request["retries"] != 0:
            raise ValueError("Provider configuration differs")
        started, ended = map(datetime.fromisoformat,(request["started_at"],timing["completed_at"]))
        if prior_call_end is not None and started < prior_call_end:
            raise ValueError("Provider calls overlapped")
        prior_call_end = ended
        call_counts[case_id] += 1
        provider_inputs.add((case_id,request["image_sha256"]))
        if (folder/"response.json").exists():
            reply = read(folder/"response.json")
            returned_models[reply["model"]] += 1
            usage = reply.get("usage")
            if usage is None or usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None:
                incomplete.append(folder.name)
    if not used_calls <= provider_inputs:
        raise ValueError("Public crop hashes do not match saved provider images")
    for case in manifest["cases"]:
        outcome = read(run/case["id"]/"outcome.json")
        if outcome["http_status"] == 200 and outcome["provider_calls"] != call_counts[case["id"]]:
            raise ValueError("Public call count mismatch")
    result = {"cases":len(cases),"byte_identical_inputs":len(cases),"baseline_unchanged":True,
        "case_requests_serial":True,"provider_calls_serial":True,"provider_attempts":sum(call_counts.values()),
        "provider_calls_by_case":dict(call_counts),"public_crop_hash_bindings_checked":len(used_calls),
        "returned_models":dict(returned_models),"replies_missing_complete_usage":incomplete}
    write_json(run/"audit.json",result)
    print(json.dumps({key:value for key,value in result.items() if key!="provider_calls_by_case"},indent=2))
    return result


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir",type=Path,required=True)
    audit(parser.parse_args().run_dir)
