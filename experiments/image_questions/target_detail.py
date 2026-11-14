"""Frozen targeted raster development evaluation with stable-correct controls.

Plan selects from completed runs; inference sees only copied images/questions.
Cases and actual provider calls run serially. Score reads answers after completion.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from importlib.metadata import version
import json
from pathlib import Path
import platform
import shutil
import statistics
import subprocess
import sys
import threading
import time

import httpx

from contracts.models import ImageCandidateResponse
from gemini.config import GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.detail import DetailOptions
from .benchmark import ROOT, PRICING, compare_count, digest, now, write_json
from .benchmark_detail import SerialRecorder, protected_files


CONTROL_IDS = ("Q003", "Q011", "Q040", "Q065", "Q079", "Q100")


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def complete(run):
    cases = read(run/"cases.json")["cases"]
    if not (run/"run-complete.json").is_file() or any(not (run/c["id"]/"outcome.json").is_file() for c in cases):
        raise ValueError("Prior runs must be complete")
    return cases


def select_cases(baseline, previous, ids=None):
    cases, prior_cases = complete(baseline), complete(previous)
    if cases != prior_cases:
        raise ValueError("Prior case identities differ")
    old = {r["id"]:r for r in read(baseline/"evaluation.json")["cases"]}
    latest = {r["id"]:r for r in read(previous/"evaluation.json")["cases"]}
    eligible = {c["id"]:c for c in cases if c["source"] != "ifc_models"}
    if ids is None:
        chosen = {i for i,c in eligible.items() if not latest[i]["exact_count_match"]}
        chosen.update(i for i in CONTROL_IDS if i in eligible and old[i]["exact_count_match"] and latest[i]["exact_count_match"])
    else:
        if len(ids) != len(set(ids)) or not ids:
            raise ValueError("Supply unique case IDs")
        chosen = set(ids)
        if not chosen <= eligible.keys():
            raise ValueError("Unknown or IFC case IDs are not eligible")
    selected = [c for c in cases if c["id"] in chosen]
    groups = {c["id"]:("regression" if old[c["id"]]["exact_count_match"] and not latest[c["id"]]["exact_count_match"]
        else "failure" if not latest[c["id"]]["exact_count_match"] else "control") for c in selected}
    return selected, groups


def plan(baseline, previous, run_dir, ids=None, options=None):
    selected, groups = select_cases(baseline, previous, ids)
    options = options or {"mode":"tiles", "max_calls":9}
    DetailOptions.model_validate(options)
    run_dir.mkdir(parents=True, exist_ok=False)
    source_manifest = read(previous/"cases.json")
    write_json(run_dir/"cases.json", {**source_manifest,"cases":selected,
        "selection":"Frozen targeted raster development failures and stable-correct controls; not a representative/held-out sample."})
    for case in selected:
        target = run_dir/case["id"]
        target.mkdir()
        for name in ("input.png","source.json","SOURCE_LICENSE.md"):
            shutil.copyfile(previous/case["id"]/name,target/name)
        if digest(target/"input.png") != read(target/"source.json")["input_sha256"]:
            raise ValueError("Copied input hash mismatch")
    write_json(run_dir/"target-plan.json", {"created_at":now(),
        "baseline":baseline.resolve().as_posix(),"previous":previous.resolve().as_posix(),
        "baseline_hashes":protected_files(baseline),"previous_hashes":protected_files(previous),
        "groups":groups,"options":options,"case_concurrency":1,"provider_concurrency":1,
        "selection_rule":"Latest failed non-IFC cases plus six fixed diverse stable controls, or an explicit frozen subset. No expected values enter inference."})
    print(json.dumps({"cases":len(selected),"ids":[c["id"] for c in selected],"groups":dict(Counter(groups.values())),"run_dir":str(run_dir)}),flush=True)


def check_protected(plan_data):
    for key in ("baseline","previous"):
        if protected_files(Path(plan_data[key])) != plan_data[key+"_hashes"]:
            raise ValueError(f"Protected {key} run changed")


async def submit(run_dir,cases,port,deadline,context,options):
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",timeout=deadline+30,trust_env=False) as client:
        for number,case in enumerate(cases,1):
            context["case_id"]=case["id"]
            target=run_dir/case["id"]
            started=time.perf_counter()
            outcome={"id":case["id"],"started_at":now()}
            try:
                response=await client.post("/api/v1/tools/detect-detail",
                    data={"question":case["question"],"options":json.dumps(options)},
                    files={"image":("display.png",(target/"input.png").read_bytes(),"image/png")})
                body=response.json()
                write_json(target/"api-response.json",body)
                outcome.update(http_status=response.status_code,status=body.get("status",body.get("code")),
                    candidate_count=len(body["candidates"]) if "candidates" in body else None,
                    metrics=body.get("metrics"),request_id=body.get("request_id"),
                    provider_calls=body.get("detail",{}).get("provider_calls"))
            except (httpx.HTTPError,ValueError) as exc:
                outcome.update(http_status=None,status="client_error",error_type=type(exc).__name__,candidate_count=None,metrics=None)
            outcome.update(elapsed_ms=(time.perf_counter()-started)*1000,completed_at=now())
            write_json(target/"outcome.json",outcome)
            with (run_dir/"results.jsonl").open("a",encoding="utf-8") as stream:
                stream.write(json.dumps(outcome,ensure_ascii=False)+"\n")
            write_json(run_dir/"progress.json",{"completed":number,"total":len(cases),"last_id":case["id"],"updated_at":now()})
            print(f"{number:03d}/{len(cases)} {case['id']} HTTP={outcome['http_status']} status={outcome['status']} count={outcome['candidate_count']} calls={outcome.get('provider_calls')} seconds={outcome['elapsed_ms']/1000:.1f}",flush=True)


def run(run_dir,dataset,port):
    if (run_dir/"run-started.json").exists() or (run_dir/"provider").exists():
        raise ValueError("Refusing to repeat/overwrite a started targeted run")
    plan_data,manifest=read(run_dir/"target-plan.json"),read(run_dir/"cases.json")
    check_protected(plan_data)
    if digest(dataset/"questions.jsonl") != manifest["dataset_questions_sha256"]:
        raise ValueError("Dataset identity changed")
    for case in manifest["cases"]:
        source=read(run_dir/case["id"]/"source.json")
        if digest(run_dir/case["id"]/"input.png") != source["input_sha256"]:
            raise ValueError("Input hash changed after planning")
    settings=ApiSettings.from_env()
    if settings.provider!="gemini":
        raise ValueError("Current image provider must be Gemini")
    settings=settings.model_copy(update={"max_concurrent":1})
    options=DetailOptions.model_validate(plan_data["options"]).model_dump(mode="json")
    hashes={}
    for path in [*Path("image_api").glob("*.py"),*Path("image_api").glob("*.txt"),
                 *Path("gemini").glob("*.py"),Path("contracts/models.py"),Path(__file__).relative_to(ROOT)]:
        target=run_dir/"code"/path
        target.parent.mkdir(parents=True,exist_ok=True)
        shutil.copyfile(path,target)
        hashes[path.as_posix()]=digest(path)
    write_json(run_dir/"environment.json",{"git_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=ROOT,text=True).strip(),
        "python":sys.version,"platform":platform.platform(),
        "packages":{name:version(name) for name in ("httpx","fastapi","uvicorn","pydantic","Pillow","numpy")},
        "source_hashes":hashes,"options":options,"api_settings":settings.model_dump(mode="json"),
        "gemini_settings":GeminiSettings.from_env().model_dump(mode="json",exclude={"api_key"}),
        "case_concurrency":1,"provider_concurrency":1,"retries":0,"pricing":PRICING})
    write_json(run_dir/"run-started.json",{"started_at":now(),"cases":len(manifest["cases"])})
    import uvicorn
    context={"case_id":None}
    app=create_app(settings,gemini_client_factory=lambda:SerialRecorder(run_dir,context))
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_level="warning"))
    thread=threading.Thread(target=server.run,daemon=True)
    thread.start()
    started=time.perf_counter()
    try:
        with httpx.Client(timeout=5,trust_env=False) as client:
            for _ in range(60):
                if not thread.is_alive():
                    raise RuntimeError("Owned targeted server stopped")
                try:
                    client.get(f"http://127.0.0.1:{port}/health").raise_for_status()
                    break
                except httpx.ConnectError:
                    time.sleep(.25)
            else:
                raise RuntimeError("Owned targeted server did not start")
        asyncio.run(submit(run_dir,manifest["cases"],port,settings.deadline_seconds,context,options))
        check_protected(plan_data)
        write_json(run_dir/"run-complete.json",{"completed_at":now(),"cases":len(manifest["cases"]),"wall_seconds":time.perf_counter()-started,"prior_runs_unchanged":True})
    finally:
        server.should_exit=True
        thread.join(timeout=30)


def score(run_dir,dataset):
    manifest,plan_data=read(run_dir/"cases.json"),read(run_dir/"target-plan.json")
    if not (run_dir/"run-complete.json").is_file() or any(not (run_dir/c["id"]/"outcome.json").exists() for c in manifest["cases"]):
        raise ValueError("Save every targeted response before reading references")
    check_protected(plan_data)
    if digest(dataset/"questions.jsonl") != manifest["dataset_questions_sha256"]:
        raise ValueError("Dataset identity changed")
    wanted={c["line"] for c in manifest["cases"]}
    with (dataset/"questions.jsonl").open(encoding="utf-8-sig") as stream:
        refs={number:json.loads(line) for number,line in enumerate(stream,1) if number in wanted}
    priors={key:{r["id"]:r for r in read(Path(plan_data[key])/"evaluation.json")["cases"]} for key in ("baseline","previous")}
    rows=[]
    for case in manifest["cases"]:
        reference=refs[case["line"]]
        if any(reference[k]!=case[k] for k in ("path","question")) or reference["type"]!="count":
            raise ValueError("Reference identity mismatch")
        target=run_dir/case["id"]
        outcome=read(target/"outcome.json")
        body=read(target/"api-response.json") if (target/"api-response.json").is_file() else {}
        if outcome["http_status"]==200:
            response=ImageCandidateResponse.model_validate(body)
            source=read(target/"source.json")
            if response.image.sha256!=source["input_sha256"] or (response.image.width,response.image.height)!=(source["width"],source["height"]):
                raise ValueError("Response/source frame mismatch")
        comparison=compare_count(body if outcome["http_status"]==200 else {},reference["answer"])
        rows.append({**case,**outcome,**comparison,"group":plan_data["groups"][case["id"]],
            "baseline_count":priors["baseline"][case["id"]]["predicted_candidate_count"],
            "baseline_match":priors["baseline"][case["id"]]["exact_count_match"],
            "previous_count":priors["previous"][case["id"]]["predicted_candidate_count"],
            "previous_match":priors["previous"][case["id"]]["exact_count_match"],
            "strict_ok_match":comparison["exact_count_match"] and body.get("status")=="ok"})
    replies=[read(p) for p in sorted((run_dir/"provider").glob("*/response.json"))]
    usages=[r["usage"] for r in replies if r.get("usage") is not None]
    inputs=sum(u.get("prompt_tokens") or 0 for u in usages)
    outputs=sum(u.get("completion_tokens") or 0 for u in usages)
    times=sorted(r["elapsed_ms"]/1000 for r in rows)
    summary={"cases":len(rows),"baseline_matches":sum(r["baseline_match"] for r in rows),
        "previous_matches":sum(r["previous_match"] for r in rows),"exact_count_matches":sum(r["exact_count_match"] for r in rows),
        "strict_ok_matches":sum(r["strict_ok_match"] for r in rows),
        "repaired_since_previous":sum(not r["previous_match"] and r["exact_count_match"] for r in rows),
        "regressed_since_previous":sum(r["previous_match"] and not r["exact_count_match"] for r in rows),
        "group_results":{g:{"cases":sum(r["group"]==g for r in rows),"matches":sum(r["group"]==g and r["exact_count_match"] for r in rows)} for g in sorted({r["group"] for r in rows})},
        "http_counts":dict(Counter(str(r["http_status"]) for r in rows)),"status_counts":dict(Counter(r["status"] for r in rows)),
        "provider_attempts":len(list((run_dir/"provider").glob("*/request.json"))),"completed_replies":len(replies),
        "complete_usage_replies":sum(u.get("prompt_tokens") is not None and u.get("completion_tokens") is not None for u in usages),
        "input_tokens":inputs,"output_tokens_including_thinking":outputs,
        "estimated_standard_cost_usd":(inputs*PRICING["input_per_million"]+outputs*PRICING["output_per_million"])/1e6,
        "latency_seconds":{"median":statistics.median(times),"p95":times[max(0,int(len(times)*.95)-1)]},
        "measurement":"Targeted development count agreement only; references excluded from inference, partial matches count, all attempts retained; not held-out accuracy or localization accuracy."}
    write_json(run_dir/"evaluation.json",{"summary":summary,"cases":rows})
    report=["# Targeted raster development evaluation","",summary["measurement"],"",
        f"Original: {summary['baseline_matches']}/{len(rows)}; previous detailed: {summary['previous_matches']}/{len(rows)}; revised detailed: **{summary['exact_count_matches']}/{len(rows)}**.","",
        "| ID | Group | Reference | Original | Previous | Revised | Match | Calls | Status |",
        "|---|---|---:|---:|---:|---:|---|---:|---|"]
    for r in rows:
        report.append(f"| {r['id']} | {r['group']} | {r['reference_count']} | {r['baseline_count']} | {r['previous_count']} | {r['predicted_candidate_count']} | {r['exact_count_match']} | {r.get('provider_calls')} | {r['status']} |")
    report += ["","```json",json.dumps(summary,indent=2),"```",""]
    (run_dir/"REPORT.md").write_text("\n".join(report),encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
    return {"summary":summary,"cases":rows}


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["plan","run","score"])
    parser.add_argument("--baseline",type=Path)
    parser.add_argument("--previous",type=Path)
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--ids",help="Comma-separated frozen subset; IFC IDs rejected")
    parser.add_argument("--options",default='{"mode":"tiles","max_calls":9}')
    parser.add_argument("--dataset",type=Path,default=ROOT/"dataset/junction-dataset")
    parser.add_argument("--port",type=int,default=8015)
    args=parser.parse_args()
    if args.command=="plan":
        if args.baseline is None or args.previous is None:
            parser.error("plan requires --baseline and --previous")
        plan(args.baseline,args.previous,args.run_dir,args.ids.split(",") if args.ids else None,json.loads(args.options))
    elif args.command=="run":
        run(args.run_dir,args.dataset,args.port)
    else:
        score(args.run_dir,args.dataset)
