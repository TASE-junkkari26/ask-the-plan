"""Answer-blind random raster evaluation with concurrent cases and provider calls.

Plan freezes a fresh uniform random sample of distinct non-IFC image questions.
Run uses an isolated HTTP server, saves every attempt, and never reads answers.
Score uses the existing count-list proxy only after every attempt completes.
"""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from contextlib import asynccontextmanager
from contextvars import ContextVar
from dataclasses import asdict
from datetime import datetime
from importlib.metadata import version
import json
from pathlib import Path
import platform
import random
import shutil
import subprocess
import sys
import threading
import time

import httpx

from gemini import AsyncGeminiClient, GeminiError
from gemini.config import GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.detail import DetailOptions
from scripts.classify_questions import classify
from .benchmark import digest, language, now, prepare, score, write_json, PRICING

CASE_ID = ContextVar("benchmark_case_id", default=None)
PACKAGES = ("image_api", "gemini", "nemotron", "contracts", "drawing_preprocessor", "ifc_api", "ifc_engine", "dxf_api", "experiments/image_questions", "scripts")


def snapshot(repo: Path, run_dir: Path):
    """Copy source-only packages, without credentials or mutable build output."""
    hashes = {}
    for package in PACKAGES:
        source = repo/package
        if not source.exists():
            continue
        for path in source.rglob("*"):
            if not path.is_file() or path.suffix not in {".py", ".txt", ".json", ".mjs"} or "__pycache__" in path.parts:
                continue
            relative = path.relative_to(repo)
            target = run_dir/"code"/relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(path, target)
            hashes[relative.as_posix()] = digest(path)
    write_json(run_dir/"source-snapshot.json", {"created_at":now(), "git_revision":subprocess.check_output(["git","rev-parse","HEAD"],cwd=repo,text=True).strip(), "source_hashes":hashes})


def plan(repo: Path, dataset: Path, run_dir: Path, seed: int = 20261115, count: int = 30):
    taxonomy=json.loads((repo/"scripts/question_classification_taxonomy.json").read_text(encoding="utf-8"))
    rows, questions_hash, _ = classify(dataset,taxonomy)
    eligible=[]
    for item in rows:
        if item.answer_type!="count" or item.source=="ifc_models" or Path(item.path).suffix.lower() not in {".png", ".pdf"} or not (dataset/item.path).is_file():
            continue
        row={"line":item.line,"path":item.path,"question":item.question,"type":item.answer_type,"source":item.source,"family":item.family,"template":item.template,"scope":item.scope or "selected drawing","page":1}
        row["language"]=language(row)
        eligible.append(row)
    random.Random(seed).shuffle(eligible)
    selected=[]
    used=set()
    for row in eligible:
        if row["path"] in used:
            continue
        selected.append({"id":f"Q{len(selected)+1:03d}",**row})
        used.add(row["path"])
        if len(selected)==count:
            break
    if len(selected)!=count:
        raise ValueError("Insufficient eligible distinct images")
    run_dir.mkdir(parents=True,exist_ok=False)
    write_json(run_dir/"cases.json",{"seed":seed,"created_at":now(),"dataset_questions_sha256":questions_hash,"cases":selected,"selection":"Uniform shuffled non-IFC PNG/PDF count-question rows, retaining the first question for each distinct image until the requested sample size. Reference answer fields excluded; no selection by prior outcomes."})
    snapshot(repo,run_dir)
    print(json.dumps({"run_dir":str(run_dir),"cases":len(selected),"sources":{source:sum(c["source"]==source for c in selected) for source in sorted({c["source"] for c in selected})},"families":len({c["family"] for c in selected}),"pdfs":sum(c["path"].endswith(".pdf") for c in selected)}),flush=True)


def fork(repo: Path, source: Path, run_dir: Path, ids=None):
    if not (source/"run-complete.json").is_file():
        raise ValueError("Prior run must be complete before forking")
    run_dir.mkdir(parents=True,exist_ok=False)
    manifest=json.loads((source/"cases.json").read_text(encoding="utf-8"))
    if ids is not None:
        if not ids or len(ids)!=len(set(ids)) or not set(ids)<={c["id"] for c in manifest["cases"]}:
            raise ValueError("Supply unique existing IDs for an explicit targeted subset")
        manifest={**manifest,"cases":[c for c in manifest["cases"] if c["id"] in ids],"selection":"Explicit frozen targeted development subset chosen after prior scoring. Reference answer fields excluded; not a representative random sample."}
        write_json(run_dir/"cases.json",manifest)
    else:
        shutil.copyfile(source/"cases.json",run_dir/"cases.json")
    for case in manifest["cases"]:
        target=run_dir/case["id"]
        target.mkdir()
        for name in ("input.png","source.json","SOURCE_LICENSE.md","pdf-render.json"):
            if (source/case["id"]/name).exists():
                shutil.copyfile(source/case["id"]/name,target/name)
    write_json(run_dir/"comparison-plan.json",{"previous":source.resolve().as_posix(),"manifest_sha256":digest(run_dir/"cases.json"),"previous_manifest_sha256":digest(source/"cases.json"),"input_sha256":{c["id"]:digest(source/c["id"]/"input.png") for c in manifest["cases"]},"created_at":now()})
    snapshot(repo,run_dir)


class CaseContextMiddleware:
    def __init__(self,app):
        self.app=app

    async def __call__(self,scope,receive,send):
        value=dict(scope.get("headers",[])).get(b"x-benchmark-case",b"").decode("ascii") or None
        token=CASE_ID.set(value)
        try:
            await self.app(scope,receive,send)
        finally:
            CASE_ID.reset(token)


class ParallelRecorder(AsyncGeminiClient):
    def __init__(self,run_dir,provider_workers,*,settings=None,registry=None):
        super().__init__(settings)
        self.run_dir=run_dir
        self.registry=registry if registry is not None else {"number":0,"slots":asyncio.Semaphore(provider_workers)}

    async def generate_candidates(self,question,*,system,image,schema):
        async with self.registry["slots"]:
            self.registry["number"]+=1
            target=self.run_dir/"provider"/f"P{self.registry['number']:04d}"
            target.mkdir(parents=True,exist_ok=False)
            shutil.copyfile(image,target/"input.png")
            write_json(target/"request.json",{"case_id":CASE_ID.get(),"transport":"interactions","question":question,"system":system,"schema":schema,"image_sha256":digest(image),"image_bytes":image.stat().st_size,"started_at":now(),"settings":self.settings.model_dump(mode="json",exclude={"api_key"}),"store":False,"retries":0})
            started=time.perf_counter()
            try:
                reply=await super().generate_candidates(question,system=system,image=image,schema=schema)
                write_json(target/"response.json",asdict(reply))
                return reply
            except GeminiError as exc:
                write_json(target/"error.json",{"code":exc.code,"provider_code":exc.provider_code,"http_status":exc.status_code,"retryable":exc.retryable})
                raise
            except asyncio.CancelledError:
                write_json(target/"error.json",{"code":"cancelled","usage_unknown":True})
                raise
            finally:
                write_json(target/"timing.json",{"elapsed_ms":(time.perf_counter()-started)*1000,"completed_at":now()})


def decisions_recorder(run_dir,registry,settings):
    # Keep the pre-routing snapshot runnable without importing a newer client.
    from gemini.decisions import AsyncDecisionsClient
    class RecordingDecisionsClient(AsyncDecisionsClient):
        async def decide(self,question,*,image,questions,context=""):
            async with registry["slots"]:
                registry["number"]+=1
                target=run_dir/"provider"/f"P{registry['number']:04d}"
                target.mkdir(parents=True,exist_ok=False)
                shutil.copyfile(image,target/"input.png")
                write_json(target/"request.json",{"case_id":CASE_ID.get(),"transport":"decisions","question":question,"system":context,"schema":questions,"image_sha256":digest(image),"image_bytes":image.stat().st_size,"started_at":now(),"settings":self.settings.model_dump(mode="json",exclude={"api_key"}),"store":False,"retries":0})
                started=time.perf_counter()
                try:
                    reply=await super().decide(question,image=image,questions=questions,context=context)
                    write_json(target/"response.json",asdict(reply))
                    return reply
                except GeminiError as exc:
                    write_json(target/"error.json",{"code":exc.code,"provider_code":exc.provider_code,"http_status":exc.status_code,"retryable":exc.retryable})
                    raise
                except asyncio.CancelledError:
                    write_json(target/"error.json",{"code":"cancelled","usage_unknown":True})
                    raise
                finally:
                    write_json(target/"timing.json",{"elapsed_ms":(time.perf_counter()-started)*1000,"completed_at":now()})
    return RecordingDecisionsClient(settings)


async def submit(run_dir,cases,port,deadline,case_workers,options,endpoint):
    slots=asyncio.Semaphore(case_workers)
    completed=0
    async with httpx.AsyncClient(base_url=f"http://127.0.0.1:{port}",timeout=deadline+30,trust_env=False) as client:
        async def one(case):
            nonlocal completed
            async with slots:
                target=run_dir/case["id"]
                started=time.perf_counter()
                outcome={"id":case["id"],"started_at":now()}
                try:
                    response=await client.post(endpoint,data={"question":case["question"],"options":json.dumps(options)},headers={"x-benchmark-case":case["id"]},files={"image":("display.png",(target/"input.png").read_bytes(),"image/png")})
                    body=response.json()
                    write_json(target/"api-response.json",body)
                    outcome.update(http_status=response.status_code,status=body.get("status",body.get("code")),candidate_count=len(body["candidates"]) if "candidates" in body else None,metrics=body.get("metrics"),request_id=body.get("request_id"),provider_calls=body.get("detail",{}).get("provider_calls"))
                except (httpx.HTTPError,ValueError) as exc:
                    outcome.update(http_status=None,status="client_error",error_type=type(exc).__name__,candidate_count=None,metrics=None)
                outcome.update(elapsed_ms=(time.perf_counter()-started)*1000,completed_at=now())
                write_json(target/"outcome.json",outcome)
                with (run_dir/"results.jsonl").open("a",encoding="utf-8") as stream:
                    stream.write(json.dumps(outcome,ensure_ascii=False)+"\n")
                completed+=1
                write_json(run_dir/"progress.json",{"completed":completed,"total":len(cases),"last_id":case["id"],"updated_at":now()})
                print(f"{completed:03d}/{len(cases)} {case['id']} {case['source']} HTTP={outcome['http_status']} status={outcome['status']} count={outcome['candidate_count']} calls={outcome.get('provider_calls')} seconds={outcome['elapsed_ms']/1000:.1f}",flush=True)
        await asyncio.gather(*(one(c) for c in cases))


def run(repo:Path,run_dir:Path,dataset:Path,port:int,case_workers:int=10,provider_workers:int=12,endpoint:str="/api/v1/tools/detect-detail",routing_mode:str="off",routing_timeout:float=3,analyzer_model=None,routing_threshold=None):
    if (run_dir/"run-started.json").exists() or (run_dir/"provider").exists():
        raise ValueError("Refusing to repeat/overwrite a started run")
    manifest=json.loads((run_dir/"cases.json").read_text(encoding="utf-8"))
    if digest(dataset/"questions.jsonl")!=manifest["dataset_questions_sha256"]:
        raise ValueError("Dataset identity changed")
    if not all((run_dir/c["id"]/"input.png").is_file() for c in manifest["cases"]):
        prepare(run_dir,dataset,manifest["cases"])
    for case in manifest["cases"]:
        source=json.loads((run_dir/case["id"]/"source.json").read_text(encoding="utf-8"))
        if digest(run_dir/case["id"]/"input.png")!=source["input_sha256"]:
            raise ValueError("Frozen input changed")
    overrides={"max_concurrent":max(case_workers,provider_workers),"routing_mode":routing_mode,"routing_timeout_seconds":routing_timeout}
    if routing_threshold is not None:
        if not .5<=routing_threshold<=1:
            raise ValueError("Routing threshold must be within .5..1")
        overrides["routing_threshold"]=routing_threshold
    settings=ApiSettings.from_env().model_copy(update=overrides)
    if settings.provider!="gemini":
        raise ValueError("Image provider must be Gemini")
    options=DetailOptions(mode="tiles",max_calls=9).model_dump(mode="json")
    environment={"snapshot":json.loads((run_dir/"source-snapshot.json").read_text(encoding="utf-8")),"python":sys.version,"platform":platform.platform(),"packages":{name:version(name) for name in ("httpx","fastapi","uvicorn","pydantic","Pillow","numpy")},"api_settings":settings.model_dump(mode="json"),"gemini_settings":GeminiSettings.from_env().model_dump(mode="json",exclude={"api_key"}),"case_concurrency":case_workers,"provider_concurrency":provider_workers,"endpoint":endpoint,"options":options,"retries":0,"pricing":PRICING,"pipeline":"Current detailed HTTP route from frozen source snapshot. Admission/call concurrency changes and request attribution only; no prompt/detection/reconciliation changes."}
    import uvicorn
    registry={"number":0,"slots":asyncio.Semaphore(provider_workers)}
    model_settings=GeminiSettings.from_env()
    if analyzer_model is not None:
        if routing_mode!="off":
            raise ValueError("Manual analyzer comparison requires routing off")
        model_settings=model_settings.profile("strong" if analyzer_model=="carbon" else "normal",thinking_level="medium")
    if routing_mode!="off":
        from gemini.decisions_config import DecisionsSettings
        model_settings=model_settings.profile("normal")
        factories={"strong_client_factory":lambda:ParallelRecorder(run_dir,provider_workers,settings=model_settings.profile("strong",thinking_level=settings.routing_strong_thinking_level),registry=registry),
                   "decisions_client_factory":lambda:decisions_recorder(run_dir,registry,DecisionsSettings(api_key=model_settings.api_key,timeout_seconds=settings.routing_timeout_seconds))}
    else:
        factories={}
    environment["gemini_settings"]=model_settings.model_dump(mode="json",exclude={"api_key"})
    environment["analyzer_model_override"]=analyzer_model
    write_json(run_dir/"environment.json",environment)
    write_json(run_dir/"run-started.json",{"started_at":now(),"cases":len(manifest["cases"])})
    app=create_app(settings,gemini_client_factory=lambda:ParallelRecorder(run_dir,provider_workers,settings=model_settings,registry=registry),**factories)
    app.add_middleware(CaseContextMiddleware)
    original_lifespan=app.router.lifespan_context
    @asynccontextmanager
    async def lifespan(app):
        async with original_lifespan(app):
            if not hasattr(app.state,"detail_slots") and getattr(app.state,"detail_tools",None) is not None:
                app.state.detail_tools._slots=asyncio.Semaphore(provider_workers)
            yield
    app.router.lifespan_context=lifespan
    server=uvicorn.Server(uvicorn.Config(app,host="127.0.0.1",port=port,log_level="warning"))
    thread=threading.Thread(target=server.run,daemon=True)
    thread.start()
    started=time.perf_counter()
    try:
        with httpx.Client(timeout=5,trust_env=False) as client:
            for _ in range(60):
                if not thread.is_alive():
                    raise RuntimeError("Owned benchmark server stopped")
                try:
                    client.get(f"http://127.0.0.1:{port}/health").raise_for_status()
                    break
                except httpx.ConnectError:
                    time.sleep(.25)
            else:
                raise RuntimeError("Owned benchmark server did not start")
        asyncio.run(submit(run_dir,manifest["cases"],port,settings.deadline_seconds,case_workers,options,endpoint))
        write_json(run_dir/"run-complete.json",{"completed_at":now(),"cases":len(manifest["cases"]),"wall_seconds":time.perf_counter()-started})
    finally:
        server.should_exit=True
        thread.join(timeout=30)


def _peak(intervals):
    events=[(start,1) for start,end in intervals]+[(end,-1) for start,end in intervals]
    active=peak=0
    for _,delta in sorted(events):
        active+=delta
        peak=max(peak,active)
    return peak


def audit(run_dir:Path):
    read=lambda path:json.loads(path.read_text(encoding="utf-8"))
    manifest=read(run_dir/"cases.json")
    cases={c["id"]:c for c in manifest["cases"]}
    environment=read(run_dir/"environment.json")
    for case in cases.values():
        if any(key in case for key in ("answer","reference_count","exact_count_match","baseline_count")):
            raise ValueError("Answer fields leaked into frozen inference manifest")
        source=read(run_dir/case["id"]/"source.json")
        if digest(run_dir/case["id"]/"input.png")!=source["input_sha256"]:
            raise ValueError("Submitted image changed")
    snapshot_data=read(run_dir/"source-snapshot.json")
    for name,sha in snapshot_data["source_hashes"].items():
        if digest(run_dir/"code"/name)!=sha:
            raise ValueError("Frozen code changed")
    if (run_dir/"comparison-plan.json").is_file():
        comparison=read(run_dir/"comparison-plan.json")
        previous=Path(comparison["previous"])
        if digest(run_dir/"cases.json")!=comparison["manifest_sha256"] or digest(previous/"cases.json")!=comparison.get("previous_manifest_sha256",comparison["manifest_sha256"]):
            raise ValueError("Paired manifest changed")
        prior_cases={c["id"]:c for c in read(previous/"cases.json")["cases"]}
        if any(prior_cases.get(id)!=case for id,case in cases.items()):
            raise ValueError("Paired case identity changed")
        for id,sha in comparison["input_sha256"].items():
            if digest(run_dir/id/"input.png")!=sha or digest(previous/id/"input.png")!=sha:
                raise ValueError("Paired input changed")
    intervals=[]
    case_calls=Counter()
    models=Counter()
    for path in sorted((run_dir/"provider").glob("*/request.json")):
        request=read(path)
        target=path.parent
        if request["case_id"] not in cases or digest(target/"input.png")!=request["image_sha256"]:
            raise ValueError("Provider request attribution/hash invalid")
        if request["retries"]!=0 or request["store"] is not False or "api_key" in request["settings"]:
            raise ValueError("Unsafe provider metadata")
        if (target/"response.json").is_file()==(target/"error.json").is_file():
            raise ValueError("Provider attempt lacks exactly one saved result/error")
        timing=read(target/"timing.json")
        intervals.append((datetime.fromisoformat(request["started_at"]),datetime.fromisoformat(timing["completed_at"])))
        case_calls[request["case_id"]]+=1
        models[request["settings"]["model"]]+=1
    case_intervals=[]
    for id in cases:
        outcome=read(run_dir/id/"outcome.json")
        case_intervals.append((datetime.fromisoformat(outcome["started_at"]),datetime.fromisoformat(outcome["completed_at"])))
    provider_peak,case_peak=_peak(intervals),_peak(case_intervals)
    if provider_peak>environment["provider_concurrency"] or case_peak>environment["case_concurrency"]:
        raise ValueError("Recorded concurrency exceeds bound")
    result={"source_frames_and_hashes_unchanged":True,"frozen_code_unchanged":True,"answer_fields_absent":True,"provider_case_attribution_complete":True,"case_peak_concurrency":case_peak,"provider_peak_concurrency":provider_peak,"provider_attempts":sum(case_calls.values()),"attempts_by_model":dict(models),"calls_by_case":dict(case_calls)}
    write_json(run_dir/"audit.json",result)
    return result


def score_parallel(run_dir:Path,dataset:Path):
    audit_data=audit(run_dir)
    score(run_dir,dataset)
    read=lambda path:json.loads(path.read_text(encoding="utf-8"))
    evaluation=read(run_dir/"evaluation.json")
    summary=evaluation["summary"]
    rate_map={"gemini-4-hydrogen":(1.5,7.5),"gemini-4-carbon":(2.,10.),"gemini-decision-1":(.1,0.)}
    costs={}
    unknown=0
    for path in (run_dir/"provider").glob("*/request.json"):
        request=read(path)
        model=request["settings"]["model"]
        reply=read(path.parent/"response.json") if (path.parent/"response.json").is_file() else {}
        usage=reply.get("usage") or {}
        if usage.get("prompt_tokens") is None or usage.get("completion_tokens") is None or model not in rate_map:
            unknown+=1
            continue
        input_rate,output_rate=rate_map[model]
        costs[model]=costs.get(model,0)+(usage["prompt_tokens"]*input_rate+usage["completion_tokens"]*output_rate)/1e6
    profiles=Counter()
    reasons=Counter()
    for case in evaluation["cases"]:
        body=read(run_dir/case["id"]/"api-response.json")
        trace=body.get("decision_trace") or {}
        case["selected_profile"]=trace.get("selected_profile")
        if case["selected_profile"]:
            profiles[case["selected_profile"]]+=1
        for node in trace.get("nodes",[]):
            if node["id"]=="capability":
                reasons[node["reason_code"]]+=1
    summary.update(estimated_standard_cost_usd=sum(costs.values()),cost_by_model_usd=costs,attempts_with_unknown_charge=unknown,
        pricing={"checked_on":"2026-11-14","rates_per_million":{model:{"input":rates[0],"output":rates[1]} for model,rates in rate_map.items()},"basis":"Nominal paid standard rates, including thinking; Carbon pre-2026-12-01. Failed/unknown-usage attempts may incur unreported charges."},
        wall_seconds=read(run_dir/"run-complete.json")["wall_seconds"],audit=audit_data,selected_profiles=dict(profiles),routing_reasons=dict(reasons))
    if (run_dir/"comparison-plan.json").is_file():
        previous=Path(read(run_dir/"comparison-plan.json")["previous"])
        prior={c["id"]:c for c in read(previous/"evaluation.json")["cases"]}
        summary["paired_comparison"]={"previous_matches":sum(prior[c["id"]]["exact_count_match"] for c in evaluation["cases"]),"current_matches":summary["exact_count_matches"],"repaired":sum(not prior[c["id"]]["exact_count_match"] and c["exact_count_match"] for c in evaluation["cases"]),"regressed":sum(prior[c["id"]]["exact_count_match"] and not c["exact_count_match"] for c in evaluation["cases"])}
    write_json(run_dir/"evaluation.json",evaluation)
    selection=read(run_dir/"cases.json").get("selection","")
    sample_kind="Targeted diagnostic" if "targeted" in selection.lower() else "Parallel random"
    report=[f"# {sample_kind} {len(evaluation['cases'])}-question raster evaluation","",summary["measurement"],"",f"Exact agreement: **{summary['exact_count_matches']}/{len(evaluation['cases'])}**; strict ok: **{summary['strict_ok_matches']}**.","", selection,"", "References excluded from inference. Every response was saved before scoring. Paired reruns preserve selected case identities and exact PNG bytes. This measures candidate-list count agreement; it does not establish localization or final-answer correctness.","","```json",json.dumps(summary,indent=2),"```","","| ID | Family | Reference | Predicted | Match | Profile | Status |","|---|---|---:|---:|---|---|---|"]
    report += [f"| {c['id']} | {c['family']} | {c['reference_count']} | {c['predicted_candidate_count']} | {c['exact_count_match']} | {c.get('selected_profile')} | {c['status']} |" for c in evaluation["cases"]]
    (run_dir/"REPORT.md").write_text("\n".join(report)+"\n",encoding="utf-8")
    print(json.dumps(summary,indent=2),flush=True)
    return evaluation


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command",choices=["plan","run","score","fork","audit"])
    parser.add_argument("--repo",type=Path,default=Path.cwd())
    parser.add_argument("--run-dir",type=Path,required=True)
    parser.add_argument("--dataset",type=Path)
    parser.add_argument("--previous",type=Path)
    parser.add_argument("--ids",help="Comma-separated explicit targeted subset for fork")
    parser.add_argument("--seed",type=int,default=20261115)
    parser.add_argument("--count",type=int,default=30)
    parser.add_argument("--port",type=int,default=8016)
    parser.add_argument("--case-workers",type=int,choices=range(1,33),default=10)
    parser.add_argument("--provider-workers",type=int,choices=range(1,33),default=12)
    parser.add_argument("--endpoint",default="/api/v1/tools/detect-detail")
    parser.add_argument("--routing-mode",choices=["off","shadow","auto"],default="off")
    parser.add_argument("--routing-timeout",type=float,default=3)
    parser.add_argument("--routing-threshold",type=float,help="Explicit posthoc experimental gate; never changes backend environment/defaults")
    parser.add_argument("--analyzer-model",choices=["hydrogen","carbon"],help="Explicit manual model comparison; Carbon uses medium thinking, routing must be off")
    args=parser.parse_args()
    repo=args.repo.resolve()
    dataset=(args.dataset or repo/"dataset/junction-dataset").resolve()
    run_dir=args.run_dir.resolve()
    if args.command=="run":
        frozen=run_dir/"code/experiments/image_questions/parallel_detail.py"
        if not frozen.is_file():
            parser.error("run requires the source snapshot created by plan/fork")
        if Path(__file__).resolve()!=frozen.resolve():
            # Start a clean interpreter so no already-imported live package can
            # bleed into the frozen run while other developers integrate code.
            bootstrap="import runpy,sys;sys.path.insert(0,sys.argv.pop(1));runpy.run_module('experiments.image_questions.parallel_detail',run_name='__main__')"
            result=subprocess.run([sys.executable,"-u","-c",bootstrap,str(run_dir/"code"),*sys.argv[1:]],cwd=repo)
            raise SystemExit(result.returncode)
    if args.command=="plan":
        plan(repo,dataset,run_dir,args.seed,args.count)
    elif args.command=="fork":
        if args.previous is None:
            parser.error("fork requires --previous")
        fork(repo,args.previous.resolve(),run_dir,args.ids.split(",") if args.ids else None)
    elif args.command=="run":
        run(repo,run_dir,dataset,args.port,args.case_workers,args.provider_workers,args.endpoint,args.routing_mode,args.routing_timeout,args.analyzer_model,args.routing_threshold)
    elif args.command=="audit":
        print(json.dumps(audit(run_dir),indent=2))
    else:
        score_parallel(run_dir,dataset)
