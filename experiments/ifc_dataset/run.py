"""Bounded supplied-dataset evaluation through the production IFC HTTP routes."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
import hashlib
import importlib
from importlib.metadata import PackageNotFoundError, version
import json
import math
import os
from pathlib import Path
import platform
import re
import subprocess
from time import perf_counter

import httpx

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.providers import PlannerReply
from image_api.errors import ApiError
from nemotron import ConfigurationError
from .questions import ROOT, Task, load_tasks, select_tasks


def encoded(value) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def hash_file(path: Path) -> str:
    result = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            result.update(block)
    return result.hexdigest()


def runtime_versions() -> dict:
    versions = {"python": platform.python_version()}
    for name in ("ifcopenshell", "pydantic", "fastapi", "starlette", "httpx", "numpy"):
        try:
            versions[name] = version(name)
        except PackageNotFoundError:
            versions[name] = None
    return versions


def code_fingerprint(root: Path = ROOT) -> dict:
    """Capture current runtime/evaluator code, including uncommitted changes."""
    files = {}
    for package in ("ifc_api", "ifc_engine", "contracts", "gemini", "nemotron", "image_api", "experiments/ifc_dataset"):
        for path in sorted((root / package).rglob("*.py")):
            files[path.relative_to(root).as_posix()] = hash_file(path)
    files["scripts/question_classification_taxonomy.json"] = hash_file(root / "scripts/question_classification_taxonomy.json")
    files["scripts/classify_questions.py"] = hash_file(root / "scripts/classify_questions.py")
    try:
        revision = subprocess.run(["git", "rev-parse", "HEAD"], cwd=root, capture_output=True,
                                  text=True, check=True, timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        revision = None
    return {"sha256": digest(encoded(files).encode()), "files": files, "git_revision": revision}


def atomic_json(path: Path, value):
    temporary = path.with_name(path.name + ".tmp")
    with temporary.open("w", encoding="utf-8") as stream:
        stream.write(encoded(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    temporary.replace(path)


def append_json(path: Path, value):
    with path.open("a", encoding="utf-8") as stream:
        stream.write(encoded(value) + "\n")
        stream.flush()
        os.fsync(stream.fileno())


def safe_error(status: int, value=None) -> dict:
    code = value.get("code") if isinstance(value, dict) else None
    return {"status": status, "code": code if isinstance(code, str) and re.fullmatch(r"[a-z][a-z0-9_]{0,63}", code) else "api_error"}


@dataclass
class Budget:
    maximum: int
    expires: float
    spent: int = 0

    def remaining(self):
        return self.maximum - self.spent


class ReplayPlanner:
    """Replay caller-supplied typed intentions, never reference answers."""
    name = "offline_replay"
    provenance = {"provider": "offline_replay", "requested_model": "fixed-plan-replay"}

    def __init__(self, plans: dict):
        from ifc_api.service import PlanProposal
        self.plans = {}
        self.line, self.offset = None, 0
        for key, value in plans.items():
            sequence = value if isinstance(value, list) else [value]
            if not sequence:
                raise ValueError("Replay proposal sequences cannot be empty.")
            self.plans[int(key)] = [PlanProposal.model_validate(proposal).model_dump(mode="json") for proposal in sequence]

    def select(self, line: int):
        self.line, self.offset = line, 0

    async def generate(self, payload, *, system, schema):
        proposals = self.plans[self.line]
        if self.offset >= len(proposals):
            raise ApiError(502, "replay_exhausted", "The fixed proposal sequence was exhausted.")
        proposal = proposals[self.offset]
        self.offset += 1
        return PlannerReply(encoded(proposal), "fixed-plan-replay")


class NoTransportPlanner:
    """Native audit sentinel: never loads provider settings or owns a socket."""
    name = "native_only"
    provenance = {"provider": "none", "requested_model": "native-only"}

    async def generate(self, payload, *, system, schema):
        raise AssertionError("Native-only evaluation cannot submit an inference request.")


class RecordingPlanner:
    """A cumulative request budget and durable, credential-free call ledger."""
    def __init__(self, provider, budget: Budget, ledger: Path, mode: str):
        self.provider, self.budget, self.ledger, self.mode = provider, budget, ledger, mode
        self.line = None
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.provider, name)

    async def generate(self, payload, *, system, schema):
        if self.budget.remaining() <= 0:
            raise ApiError(429, "evaluation_call_budget", "The evaluation request budget is exhausted.")
        if perf_counter() >= self.budget.expires:
            raise ApiError(504, "evaluation_deadline", "The evaluation run deadline is exhausted.")
        self.budget.spent += 1
        call = {"call_id": self.budget.spent, "line": self.line, "mode": self.mode,
                "input_sha256": digest(payload.encode()), "input_chars": len(payload),
                "system_sha256": digest(system.encode()), "schema_sha256": digest(encoded(schema).encode())}
        # A started call remains spent after interruption, so resuming cannot
        # silently bypass the maximum with an unrecorded paid request.
        append_json(self.ledger, {**call, "stage": "started"})
        started = perf_counter()
        try:
            reply = await self.provider.generate(payload, system=system, schema=schema)
            usage = getattr(reply, "usage", None)
            call.update(returned_model=reply.model,
                        prompt_tokens=getattr(usage, "prompt_tokens", None),
                        completion_tokens=getattr(usage, "completion_tokens", None),
                        thought_tokens=getattr(usage, "thought_tokens", None))
            return reply
        except asyncio.CancelledError:
            call["error_category"] = "cancelled"
            raise
        except Exception as error:
            call["error_category"] = "provider_error" if isinstance(error, ApiError) else "internal_error"
            if isinstance(error, ApiError):
                call["error"] = safe_error(error.status_code, {"code": error.code})
                upstream_status = getattr(error, "provider_status_code", None)
                if type(upstream_status) is int and 100 <= upstream_status <= 599:
                    call["upstream_status"] = upstream_status
                from gemini.client import PROVIDER_ERROR_CODES
                upstream_code = getattr(error, "provider_code", None)
                if isinstance(upstream_code, str) and upstream_code in PROVIDER_ERROR_CODES:
                    call["provider_code"] = upstream_code
            raise
        finally:
            call["elapsed_ms"] = (perf_counter() - started) * 1000
            self.calls.append(call)
            append_json(self.ledger, {**call, "stage": "finished"})


def evidence_checks(prediction: dict) -> dict:
    response, request = prediction.get("response"), prediction["request"]
    if not response:
        return {"response_present": False, "source_membership_accuracy": "ungraded",
                "all_question_parts": "ungraded"}
    result, plan = response["result"], response.get("plan")
    facts = {fact["id"] for fact in response.get("facts", [])}
    anchors = {anchor["id"] for anchor in response.get("anchors", [])}
    calculations = {node["id"] for node in result.get("calculations", [])}
    sets = {value["id"] for value in result.get("entity_sets", [])}
    elements = [element for key in ("included_elements", "excluded_elements", "unresolved_elements")
                for element in response.get(key, [])]
    visible = set(request.get("visible_step_ids") or [])
    bindings = [binding for claim in result.get("claims", []) for binding in claim.get("evidence", [])]
    claimed = result["status"] in {"answered", "partial"}
    checks = {
        "response_present": True,
        "source_question_scope_binding": all(response.get(key) == request.get(key) for key in
                                             ("model_id", "source_sha256", "question", "scope")),
        "view_elements_within_scope": request["scope"] == "model" or all(e["step_id"] in visible for e in elements),
        "view_inventory_size_preserved": request["scope"] == "model" or plan is None or
            len(plan["scope"].get("exact_entity_ids") or []) == len(visible),
        "claim_bindings_resolve": all(binding.get("calculation_id") in calculations
                                      and set(binding.get("fact_ids", [])) <= facts
                                      and set(binding.get("anchor_ids", [])) <= anchors
                                      and set(binding.get("entity_set_ids", [])) <= sets for binding in bindings),
        "claims_have_evidence": not claimed or bool(bindings),
        "nonanswer_has_no_claims": claimed or not result.get("claims"),
        "source_membership_accuracy": "ungraded",
        "all_question_parts": "ungraded",
    }
    return checks


def summarize(tasks, predictions, scores, budget, mode):
    calls = [call for prediction in predictions for call in prediction.get("calls", [])]
    durations = sorted(prediction["elapsed_ms"] for prediction in predictions)
    summary = {
        "selected_rows": len(tasks), "selected_families": len({task.family for task in tasks}),
        "selected_models": len({task.path for task in tasks}), "recorded_predictions": len(predictions),
        "not_attempted_rows": len(tasks) - len(predictions),
        "statuses": dict(Counter(p.get("response", {}).get("result", {}).get("status", "api_error") for p in predictions)),
        "grading": dict(Counter(score["grading"]["status"] for score in scores)),
        "planner_requests_recorded": len(calls), "cumulative_started_calls": budget.spent,
        "started_calls_without_prediction": max(0, budget.spent - len(calls)),
        "external_inference_requests": budget.spent if mode == "live" else 0,
        "p50_ms": durations[max(0, math.ceil(len(durations) * .5) - 1)] if durations else None,
        "p95_ms": durations[max(0, math.ceil(len(durations) * .95) - 1)] if durations else None,
        "usage": {name: {"reported_total": sum(call[name] for call in calls if call.get(name) is not None),
                         "unreported_calls": sum(call.get(name) is None for call in calls) + max(0, budget.spent - len(calls))}
                  for name in ("prompt_tokens", "completion_tokens", "thought_tokens")},
        "cost_estimate": None, "source_membership_accuracy": "ungraded",
        "free_text_accuracy": "ungraded", "all_questions_supported": False,
    }
    summary["by_family"] = {family: {
        "selected": sum(task.family == family for task in tasks),
        "recorded": sum(p["task"]["family"] == family for p in predictions),
        "grading": dict(Counter(score["grading"]["status"] for score in scores if score["family"] == family)),
    } for family in sorted({task.family for task in tasks})}
    return summary


def _unconfigured():
    raise ConfigurationError("The evaluator disables unrelated image transports.")


def _native_settings(provider):
    if provider == "gemini":
        from gemini import GeminiSettings
        return GeminiSettings.from_env()
    from nemotron import NemotronSettings
    return NemotronSettings.from_env().model_copy(update={"max_retries": 0})


def _safe_native_settings(settings):
    result = {name: getattr(settings, name) for name in ("model", "timeout_seconds", "max_retries", "temperature", "enable_thinking")
              if hasattr(settings, name)}
    if hasattr(settings, "base_url"):
        result["endpoint_sha256"] = digest(settings.base_url.encode())
    return result


async def _live_planner(provider: str, settings: IfcSettings, native_settings):
    from ifc_api.providers import GeminiPlanner, NemotronPlanner
    if provider == "gemini":
        from gemini import AsyncGeminiClient
        client = AsyncGeminiClient(native_settings)
        planner = GeminiPlanner(client, settings)
    elif provider == "nemotron":
        from nemotron import AsyncNemotronClient
        client = AsyncNemotronClient(native_settings)
        planner = NemotronPlanner(client, settings)
    else:
        raise ValueError("Choose Gemini or Nemotron for live execution.")
    return planner, client


async def evaluate(dataset: Path, output: Path, *, lines=(), families=(), models=(), limit=None,
                   one_per_family=False, provider="gemini", live=False, replay_plans: Path | None = None,
                   resume=False, max_calls=12, deadline_seconds=180, run_deadline_seconds=1800,
                   max_model_requests=3, max_inspections=6, thinking_level="high",
                   scope="model", visible_step_ids: dict[str, list[int]] | None = None,
                   fast_plans: bool | None = None, native_only=False):
    if sum(bool(value) for value in (live, replay_plans, native_only)) != 1:
        raise ValueError("Choose exactly one of --native-only, explicit --live or --replay-plans FILE.")
    if native_only:
        if fast_plans is False:
            raise ValueError("Native-only evaluation requires deterministic production planning.")
        max_calls, fast_plans = 0, True
    if provider not in {"gemini", "nemotron"}:
        raise ValueError("Choose Gemini or Nemotron.")
    if type(max_calls) is not int or max_calls < 0 or not 0 < run_deadline_seconds <= 86400:
        raise ValueError("Use a nonnegative request budget and a positive run deadline of at most one day.")
    if scope not in {"model", "view"}:
        raise ValueError("Choose model or view scope.")
    tasks, dataset_sha = load_tasks(dataset)
    tasks = select_tasks(tasks, lines=lines, families=families, models=models, limit=limit, one_per_family=one_per_family)
    if scope == "view":
        if visible_step_ids is None or {task.path for task in tasks} - visible_step_ids.keys():
            raise ValueError("View mode requires an explicit STEP-ID inventory for every selected model.")
        for ids in visible_step_ids.values():
            if not isinstance(ids, list) or any(type(value) is not int or value <= 0 for value in ids) or len(ids) != len(set(ids)):
                raise ValueError("View inventories require distinct positive STEP IDs; an empty list is valid.")
    else:
        visible_step_ids = None
    # Replay has no key loading; live configuration remains independent of the
    # image provider. All bounds are validated rather than model_copy bypassed.
    base = IfcSettings.from_env().model_dump() if live else IfcSettings().model_dump()
    settings = IfcSettings.model_validate({**base, "provider": provider, "deadline_seconds": deadline_seconds,
        "max_model_requests": max_model_requests, "max_inspections": max_inspections,
        "gemini_thinking_level": thinking_level,
        "fast_plans": False if replay_plans else base["fast_plans"] if fast_plans is None else fast_plans})
    native_settings = _native_settings(provider) if live else None
    replay = None
    if replay_plans:
        replay = ReplayPlanner(json.loads(replay_plans.read_text(encoding="utf-8")))
        if {task.line for task in tasks} - replay.plans.keys():
            raise ValueError("Every selected row needs a fixed replay proposal.")
    sources = {}
    dataset = dataset.resolve()
    for task in tasks:
        if task.path in sources:
            continue
        path = (dataset / task.path).resolve(strict=True)
        if not path.is_relative_to(dataset):
            raise ValueError("Source IFC paths must stay within the dataset.")
        sources[task.path] = {"sha256": hash_file(path), "bytes": path.stat().st_size}
    code = code_fingerprint()
    mode = "native_only" if native_only else "live" if live else "fixed_plan_replay"
    identity = {"format_version": 1, "dataset_sha256": dataset_sha, "tasks": [task.as_dict() for task in tasks],
                "sources": sources, "code": code, "mode": mode, "provider": "none" if native_only else provider if live else "offline_replay",
                "runtime_versions": runtime_versions(),
                "settings": settings.model_dump(mode="json"), "scope": scope, "visible_step_ids": visible_step_ids,
                "transport_settings": _safe_native_settings(native_settings) if native_settings else None,
                "replay_sha256": hash_file(replay_plans) if replay_plans else None}
    manifest_file, predictions_dir = output / "manifest.json", output / "predictions"
    if output.exists():
        if not resume:
            raise FileExistsError("Output exists; use --resume or a fresh output directory.")
        saved = json.loads(manifest_file.read_text())
        if saved["identity"] != identity:
            raise ValueError("Resume identity differs (questions/source/code/provider/settings/scope/replay); choose a fresh output.")
    else:
        output.mkdir(parents=True)
        predictions_dir.mkdir()
        atomic_json(manifest_file, {"identity": identity, "created_at": datetime.now(timezone.utc).isoformat(),
            "python": platform.python_version(),
            "interpretation": "Fixed plans test execution only; numeric agreement is not independent source-membership verification; text accuracy stays ungraded."})
    existing = {}
    for path in sorted(predictions_dir.glob("line-*.json")):
        prediction = json.loads(path.read_text())
        if prediction["line"] not in {task.line for task in tasks}:
            raise ValueError("Unexpected prediction identity in output.")
        existing[prediction["line"]] = prediction
    ledger = output / "calls.jsonl"
    spent = 0
    if ledger.is_file():
        started = [json.loads(raw) for raw in ledger.read_text().splitlines() if raw.strip()]
        ids = [call["call_id"] for call in started if call["stage"] == "started"]
        if len(ids) != len(set(ids)) or (ids and sorted(ids) != list(range(1, max(ids) + 1))):
            raise ValueError("Call ledger has inconsistent identities; do not replay paid requests automatically.")
        spent = len(ids)
    budget = Budget(max_calls, perf_counter() + run_deadline_seconds, spent)
    append_json(output / "attempts.jsonl", {"started_at": datetime.now(timezone.utc).isoformat(),
        "max_calls_cumulative": max_calls, "run_deadline_seconds": run_deadline_seconds,
        "reused_predictions": len(existing), "previous_started_calls": spent})
    client_owner = None
    if len(existing) < len(tasks) and (budget.remaining() > 0 or settings.fast_plans):
        inner = NoTransportPlanner() if native_only else replay
        if live:
            inner, client_owner = await _live_planner(provider, settings, native_settings)
        recording = RecordingPlanner(inner, budget, ledger, mode)
        # This is the actual application and its HTTP multipart/question routes.
        # Only the planner is injected; source upload, extraction, validation,
        # scope enforcement, execution, errors and evidence stay in production.
        from image_api.app import create_app
        from image_api.config import ApiSettings
        app = create_app(ApiSettings(provider="nemotron", preprocess_mode="off"),
                         client_factory=_unconfigured, gemini_client_factory=_unconfigured,
                         ifc_gemini_client_factory=_unconfigured, ifc_settings=settings,
                         ifc_planner_factory=lambda: recording)
        grouped = defaultdict(list)
        for task in tasks:
            if task.line not in existing:
                grouped[task.path].append(task)
        try:
            async with app.router.lifespan_context(app):
                async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://evaluation") as client:
                    for source_path, group in grouped.items():
                        if (budget.remaining() <= 0 and not settings.fast_plans) or perf_counter() >= budget.expires:
                            break
                        upload_started = perf_counter()
                        upload, upload_error = None, None
                        try:
                            with (dataset / source_path).open("rb") as stream:
                                uploaded = await asyncio.wait_for(client.post("/api/ifc/models",
                                    data={"source_sha256": sources[source_path]["sha256"]},
                                    files={"file": (Path(source_path).name, stream, "application/x-step")}),
                                    timeout=max(.001, min(deadline_seconds, budget.expires - perf_counter())))
                            if uploaded.status_code == 200:
                                upload = m.IfcModelResponse.model_validate(uploaded.json()).model_dump(mode="json")
                            else:
                                upload_error = safe_error(uploaded.status_code, uploaded.json())
                        except asyncio.TimeoutError:
                            upload_error = {"status": 504, "code": "upload_deadline"}
                        except Exception:
                            upload_error = {"status": 500, "code": "upload_internal_error"}
                        upload_ms = (perf_counter() - upload_started) * 1000
                        if upload and upload["source_sha256"] != sources[source_path]["sha256"]:
                            raise ValueError("Production upload returned an inconsistent source revision.")
                        for task in group:
                            if (budget.remaining() <= 0 and not settings.fast_plans) or perf_counter() >= budget.expires:
                                break
                            request = {"model_id": upload["model_id"] if upload else "unavailable",
                                "source_sha256": sources[source_path]["sha256"], "question": task.question,
                                "scope": scope, "visible_step_ids": visible_step_ids[task.path] if scope == "view" else None,
                                "view_label": "Explicit evaluation inventory" if scope == "view" else None}
                            prediction = {"line": task.line, "task": task.as_dict(), "source": sources[source_path],
                                "request": request, "upload": upload, "upload_ms": upload_ms,
                                "code_sha256": code["sha256"], "mode": mode, "provider": identity["provider"]}
                            recording.line = task.line
                            if replay:
                                replay.select(task.line)
                            offset, started = len(recording.calls), perf_counter()
                            if upload is None:
                                prediction["error"] = upload_error
                            else:
                                try:
                                    response = await asyncio.wait_for(client.post("/api/ifc/questions", json=request),
                                        timeout=max(.001, min(deadline_seconds + 1, budget.expires - perf_counter())))
                                    if response.status_code == 200:
                                        prediction["response"] = m.IfcQuestionResponse.model_validate(response.json()).model_dump(mode="json")
                                    else:
                                        prediction["error"] = safe_error(response.status_code, response.json())
                                except asyncio.TimeoutError:
                                    prediction["error"] = {"status": 504, "code": "evaluation_deadline"}
                                except Exception:
                                    prediction["error"] = {"status": 500, "code": "evaluation_internal_error"}
                            prediction.update(elapsed_ms=(perf_counter() - started) * 1000,
                                              calls=recording.calls[offset:])
                            prediction["evidence_checks"] = evidence_checks(prediction)
                            atomic_json(predictions_dir / f"line-{task.line:08d}.json", prediction)
                            append_json(output / "predictions.jsonl", prediction)
                            existing[task.line] = prediction
        finally:
            if client_owner is not None:
                await client_owner.close()
    predictions = [existing[task.line] for task in tasks if task.line in existing]
    # Rebuild the convenience index from atomically saved records. A truncated
    # streaming line from interruption never causes a completed call to rerun.
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for prediction in predictions:
            stream.write(encoded(prediction) + "\n")
        stream.flush()
        os.fsync(stream.fileno())
    # Only now may evaluation code load supplied answer values.
    if hash_file(dataset / "questions.jsonl") != dataset_sha:
        raise ValueError("Question file changed during evaluation; predictions were saved but cannot be graded against another revision.")
    references = importlib.import_module("experiments.ifc_dataset.references")
    truth = references.load_references(dataset, {prediction["line"] for prediction in predictions})
    scores = [{"line": p["line"], "family": p["task"]["family"],
               "grading": references.numeric_grade(p, truth[p["line"]]),
               "evidence_checks": p["evidence_checks"]} for p in predictions]
    report = {"summary": summarize(tasks, predictions, scores, budget, mode), "scores": scores,
              "not_attempted_lines": [task.line for task in tasks if task.line not in existing],
              "code_changed_during_run": code_fingerprint()["sha256"] != code["sha256"],
              "completed_at": datetime.now(timezone.utc).isoformat()}
    atomic_json(output / "report.json", report)
    return report


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, default=ROOT / "dataset/junction-dataset")
    parser.add_argument("--output", type=Path)
    parser.add_argument("--line", type=int, action="append", default=[])
    parser.add_argument("--family", action="append", default=[])
    parser.add_argument("--model", action="append", default=[])
    parser.add_argument("--limit", type=int)
    parser.add_argument("--one-per-family", action="store_true")
    parser.add_argument("--provider", choices=["gemini", "nemotron"], default="gemini")
    parser.add_argument("--live", action="store_true")
    parser.add_argument("--native-only", action="store_true", help="Exercise production deterministic planning with zero calls and no provider configuration/transport.")
    parser.add_argument("--replay-plans", type=Path)
    parser.add_argument("--resume", action="store_true")
    parser.add_argument("--max-calls", type=int, default=12)
    parser.add_argument("--deadline-seconds", type=float, default=180)
    parser.add_argument("--run-deadline-seconds", type=float, default=1800)
    parser.add_argument("--max-model-requests", type=int, default=3)
    parser.add_argument("--max-inspections", type=int, default=6)
    parser.add_argument("--thinking-level", choices=["low", "medium", "high", "xhigh"], default="high")
    parser.add_argument("--disable-fast-plans", action="store_true", help="Force external planning for a live adapter comparison; replay always disables deterministic grammar.")
    parser.add_argument("--scope", choices=["model", "view"], default="model")
    parser.add_argument("--view-ids", type=Path, help="JSON mapping exact model paths to lists of visible STEP IDs.")
    parser.add_argument("--list", action="store_true", help="Print selected task inputs/families without inference or references.")
    args = parser.parse_args(argv)
    if args.list:
        tasks, sha = load_tasks(args.dataset)
        selected = select_tasks(tasks, lines=args.line, families=args.family, models=args.model,
                                limit=args.limit, one_per_family=args.one_per_family)
        print(encoded({"dataset_sha256": sha, "rows": [task.as_dict() for task in selected]}))
        return 0
    output = args.output or ROOT / "build" / ("ifc-dataset-" + datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    try:
        report = asyncio.run(evaluate(args.dataset, output, lines=args.line, families=args.family, models=args.model,
            limit=args.limit, one_per_family=args.one_per_family, provider=args.provider, live=args.live,
            replay_plans=args.replay_plans, resume=args.resume, max_calls=args.max_calls,
            deadline_seconds=args.deadline_seconds, run_deadline_seconds=args.run_deadline_seconds,
            max_model_requests=args.max_model_requests, max_inspections=args.max_inspections,
            thinking_level=args.thinking_level, scope=args.scope,
            visible_step_ids=json.loads(args.view_ids.read_text()) if args.view_ids else None,
            fast_plans=False if args.disable_fast_plans else None, native_only=args.native_only))
    except (ConfigurationError, ValueError, FileExistsError, FileNotFoundError):
        print("Evaluation setup failed. Check explicit live/replay selection, selectors, bounds, source paths, backend configuration and resume identity; private settings were not printed.")
        return 2
    print(encoded({"output": str(output), "summary": report["summary"]}))
    bad = report["summary"]["not_attempted_rows"] or report["summary"]["statuses"].get("api_error", 0)
    bad = bad or any(score["grading"]["status"] not in {"numeric_agreement", "numeric_agreement_estimated", "ungraded_text", "ungraded_scope_variant"}
                     for score in report["scores"])
    bad = bad or any(value is False for score in report["scores"] for value in score["evidence_checks"].values())
    bad = bad or report["code_changed_during_run"]
    return 1 if bad else 0


if __name__ == "__main__":
    raise SystemExit(main())
