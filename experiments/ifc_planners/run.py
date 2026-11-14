"""Paired IFC planner evaluation; default execution is credential-free replay."""
from __future__ import annotations

import argparse
import asyncio
from collections import Counter
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import platform
import subprocess
from time import perf_counter
import ifcopenshell

from contracts import models as m
from ifc_api.service import IfcService
from ifc_engine.catalog import POLICIES, property_key
from image_api.errors import ApiError
from .cases import CASES, Case
from .fixtures import GROUPS, VERSION, Fixture, build_fixture

PROVIDERS = ("replay", "nemotron", "nemotron-thinking", "gemini-low", "gemini-high")
SOURCE_MODULES = (
    "ifc_api/service.py", "ifc_api/providers.py", "ifc_api/discovery.py", "ifc_api/config.py", "ifc_api/answers.py",
    "gemini/client.py", "gemini/config.py", "ifc_engine/engine.py", "ifc_engine/ingest.py",
    "ifc_engine/spatial.py", "ifc_engine/exterior.py", "ifc_engine/catalog.py", "ifc_engine/units.py",
    "contracts/models.py", "contracts/validation.py", "nemotron/client.py",
    "experiments/ifc_planners/run.py", "experiments/ifc_planners/fixtures.py",
    "experiments/ifc_planners/cases.py", "experiments/ifc_planners/references.py",
)


def _provider_diagnostics(error):
    """Persist recognized machine diagnostics only, never provider text/bodies."""
    from gemini.client import PROVIDER_ERROR_CODES
    diagnostics = {}
    status = getattr(error, "provider_status_code", None)
    if type(status) is int and 100 <= status <= 599:
        diagnostics["upstream_status"] = status
    code = getattr(error, "provider_code", None)
    if isinstance(code, str) and code in PROVIDER_ERROR_CODES:
        diagnostics["provider_code"] = code
    validation = getattr(error, "plan_validation_errors", None)
    if isinstance(validation, list):
        from ifc_api.service import PlanProposal
        schema = PlanProposal.model_json_schema()
        fields = set(schema["properties"]) | {"select", "traverse", "aggregate", "rank", "project", "spatial_query"}
        for definition in schema.get("$defs", {}).values():
            fields.update(definition.get("properties", {}))
        accepted = []
        for item in validation[:12]:
            if not isinstance(item, str) or len(item) > 500 or item.count(":") != 1:
                continue
            location, category = item.split(":")
            if category not in {"missing", "value_error", "literal_error", "extra_forbidden", "union_tag_invalid", "union_tag_not_found", "json_invalid", "int_type", "string_type", "bool_type", "list_type", "dict_type", "too_long", "too_short"}:
                continue
            if all(part in fields or part == "*" or part.isdecimal() for part in location.split(".") if part):
                accepted.append(item)
        if accepted:
            diagnostics["plan_validation_errors"] = accepted
    return diagnostics


def _json(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False)


def replay_proposal(case: Case, model, fixture: Fixture) -> dict:
    """Build a query intention, never a reference count or final answer."""
    base = {"status": "ready", "interpretation": "Execute the source-bound " + case.family + " query.",
            "explicitly_requests_entire_model": case.whole_model,
            "steps": [], "output_step_id": None, "outputs": {}}
    nonanswers = {"missing-fire-rating": ("missing_information", "No fire-rating property was extracted."),
                  "unsupported-route": ("unsupported_operation", "Navigable route measurement is unavailable.")}
    if case.replay in nonanswers:
        base["status"], base["interpretation"] = nonanswers[case.replay]
        return base
    rooms = case.replay in {"outdoor-rooms", "connections", "neighbors"}
    select = {"kind": "select", "concept_ids": ["concept:space" if rooms else "concept:door"],
              "count_policy": POLICIES["all_matches"].model_dump()}
    if case.replay in {"internal", "external-flags"}:
        select["where"] = {"kind": "compare", "field": {"kind": "property", "key": property_key("Pset_DoorCommon", "IsExternal")},
                           "operator": "eq", "value": {"kind": "boolean", "value": case.replay == "external-flags"}}
    if case.replay in {"connections", "neighbors"}:
        select["where"] = {"kind": "compare", "field": {"kind": "entity_id", "key": "entity_id"}, "operator": "eq",
                           "value": {"kind": "references", "entity_ids": [model.by_step[fixture.steps["room-b"]]]}}
    steps = [{"id": "objects", "operation": select}]
    if case.replay in {"exterior", "classification", "boundary"}:
        steps.append({"id": "resolved", "operation": {"kind": "spatial_query", "input_step_id": "objects",
                      "relation": "exterior_doors", "exterior_basis": "combined" if case.replay == "exterior" else case.replay}})
    elif rooms:
        relation = {"outdoor-rooms": "outdoor_access", "connections": "door_connections", "neighbors": "boundary_neighbors"}[case.replay]
        steps.append({"id": "resolved", "operation": {"kind": "spatial_query", "input_step_id": "objects", "relation": relation}})
    if case.replay not in {"connections", "neighbors"}:
        steps.append({"id": "answer", "operation": {"kind": "aggregate", "input_step_id": steps[-1]["id"], "method": "count"}})
    base["steps"], base["output_step_id"] = steps, steps[-1]["id"]
    return base


class RecordingPlanner:
    """Record bounded request identities/usage, without credentials or raw prompts."""
    def __init__(self, provider):
        self.provider = provider
        self.calls = []

    def __getattr__(self, name):
        return getattr(self.provider, name)

    async def generate(self, payload: str, *, system: str, schema: dict):
        call = {"input_sha256": hashlib.sha256(payload.encode()).hexdigest(),
                "system_sha256": hashlib.sha256(system.encode()).hexdigest(),
                "schema_sha256": hashlib.sha256(_json(schema).encode()).hexdigest(),
                "input_chars": len(payload)}
        started = perf_counter()
        try:
            reply = await self.provider.generate(payload, system=system, schema=schema)
            usage = getattr(reply, "usage", None)
            call.update({"returned_model": reply.model,
                         "prompt_tokens": getattr(usage, "prompt_tokens", None),
                         "completion_tokens": getattr(usage, "completion_tokens", None),
                         "thinking_tokens": getattr(usage, "thought_tokens", None)})
            return reply
        except Exception as exc:
            call["error_category"] = type(exc).__name__
            if isinstance(exc, ApiError):
                call.update(_provider_diagnostics(exc))
            raise
        finally:
            call["elapsed_ms"] = (perf_counter() - started) * 1000
            self.calls.append(call)


class ReplayPlanner:
    """Provider-shaped fixture replay; never opens a socket or loads settings files."""
    name = "offline_replay"

    def __init__(self, state):
        from ifc_api.config import IfcSettings
        self.state = state
        self.settings = IfcSettings()

    @property
    def provenance(self):
        return {"provider": self.name, "requested_model": "fixture-plan-replay"}

    async def generate(self, payload, *, system, schema):
        from ifc_api.providers import PlannerReply
        return PlannerReply(_json(self.state["proposal"]), "fixture-plan-replay")

    async def close(self):
        pass


async def _provider(name, replay_state):
    """Only explicit live modes load credentials or construct network transports."""
    from ifc_api.config import IfcSettings
    from ifc_api.providers import GeminiPlanner, NemotronPlanner
    from nemotron import AsyncNemotronClient, NemotronSettings

    if name == "replay":
        planner = ReplayPlanner(replay_state)
        return planner, planner.close
    if name.startswith("nemotron"):
        values = NemotronSettings.from_env().model_copy(update={"max_retries": 0})
        if name == "nemotron-thinking":
            values = values.model_copy(update={"enable_thinking": True})
        client = AsyncNemotronClient(values)
        return NemotronPlanner(client, IfcSettings.from_env().model_copy(update={"provider": "nemotron"})), client.close
    from gemini import AsyncGeminiClient, GeminiSettings
    client = AsyncGeminiClient(GeminiSettings.from_env())
    settings = IfcSettings.from_env().model_copy(update={"provider": "gemini", "gemini_thinking_level": name.split("-")[1]})
    return GeminiPlanner(client, settings), client.close


def _revision():
    try:
        return subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True,
                              cwd=Path(__file__).resolve().parents[2], timeout=5).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def source_fingerprint(root: Path | None = None):
    """Identify the code actually present, including uncommitted adapter changes."""
    root = root if root is not None else Path(__file__).resolve().parents[2]
    hashes, missing = {}, []
    for relative in SOURCE_MODULES:
        path = root / relative
        if not path.is_file():
            missing.append(relative)
            continue
        digest = hashlib.sha256()
        with path.open("rb") as stream:
            for block in iter(lambda: stream.read(65536), b""):
                digest.update(block)
        hashes[relative] = digest.hexdigest()
    return {"sha256": hashlib.sha256(_json(hashes).encode()).hexdigest(),
            "files": hashes, "missing_files": missing}


def _safe_config(provider):
    # Copy explicit harmless scalars only; never serialize a credential settings object.
    output = {"adapter": getattr(provider, "name", type(provider).__name__)}
    settings = getattr(provider, "settings", None)
    for key in ("provider", "max_tokens", "deadline_seconds", "max_model_requests", "max_inspections",
                "gemini_thinking_level", "gemini_max_output_tokens"):
        value = getattr(settings, key, None)
        if value is None or isinstance(value, (str, int, float, bool)):
            output[key] = value
    client_settings = getattr(getattr(provider, "client", None), "settings", None)
    for key in ("model", "enable_thinking"):
        value = getattr(client_settings, key, None)
        if value is None or isinstance(value, (str, int, float, bool)):
            output[key] = value
    return output


def _request(case, fixture, model_id):
    return m.IfcQuestionRequest(model_id=model_id, source_sha256=fixture.sha256,
        question=case.question, scope=case.scope,
        visible_step_ids=[fixture.steps[key] for key in case.view_keys] if case.scope == "view" else None,
        view_label="Synthetic selected inventory" if case.scope == "view" else None)


def _score(prediction, case, fixture, reference):
    response = prediction.get("response")
    result = response["result"] if response else None
    status = result["status"] if result else "api_error"
    claims = result["claims"] if result else []
    counts = [claim["value"]["value"] for claim in claims if claim["value"]["kind"] == "count"]
    actual = {element["step_id"] for element in response["included_elements"] if element["step_id"] is not None} if response else set()
    expected = {fixture.steps[key] for key in reference.included} if reference.included is not None else None
    related = set()
    by_entity = {element["entity_id"]: element["step_id"] for element in response["included_elements"]} if response else {}
    for claim in claims:
        if claim["value"]["kind"] == "table":
            for row in claim["value"]["rows"]:
                related.update(by_entity.get(identifier) for identifier in row.get("related", {}).get("entity_ids", []))
    expected_related = {fixture.steps[key] for key in reference.related} if reference.related is not None else None
    anchor_steps = {int(anchor["selector"]["value"]) for anchor in response["anchors"]
                    if anchor["selector"]["kind"] == "step_id" and anchor["selector"]["value"].isdigit()} if response else set()
    required = {fixture.steps[key] for key in reference.anchor_keys}
    scope_match = response is not None and response["scope"] == case.scope and response["source_sha256"] == fixture.sha256
    if scope_match and response["plan"] is not None:
        exact = response["plan"]["scope"]["exact_entity_ids"]
        if case.scope == "view":
            scope_match = exact is not None and len(exact) == len(case.view_keys)
            # The executed output must never include an object outside the view.
            scope_match = scope_match and actual <= {fixture.steps[key] for key in case.view_keys}
        else:
            scope_match = exact is None
    checks = {"status": status == reference.status, "scope": scope_match,
              "count": reference.count is None or counts == [reference.count],
              "membership": expected is None or actual == expected,
              "related_membership": expected_related is None or related == expected_related,
              "quality": reference.quality is None or bool(claims) and all(c["quality"] == reference.quality for c in claims),
              "required_source_anchors": required <= anchor_steps,
              "nonanswer_has_no_claim": reference.status in {"answered", "partial"} or not claims}
    return {"provider": prediction["provider"], "case_id": case.id, "group": case.group, "split": case.split,
            "family": case.family, "status": status, "expected_status": reference.status,
            "passed": all(checks.values()), "checks": checks,
            "actual_counts": counts, "expected_count": reference.count,
            "actual_step_ids": sorted(actual), "expected_step_ids": sorted(expected) if expected is not None else None,
            "missed_step_ids": sorted(expected - actual) if expected is not None else None,
            "false_step_ids": sorted(actual - expected) if expected is not None else None,
            "missing_anchor_step_ids": sorted(required - anchor_steps),
            "evidence_check": "structural fixture identity/anchor checks; no independent visual/source-truth score",
            "elapsed_ms": prediction["elapsed_ms"], "calls": prediction["calls"]}


def _percentile(values, fraction):
    return sorted(values)[max(0, math.ceil(len(values) * fraction) - 1)] if values else None


def summarize_scores(scores):
    summaries = {}
    for name in sorted({score["provider"] for score in scores}):
        rows = [score for score in scores if score["provider"] == name]
        calls = [call for row in rows for call in row["calls"]]
        token_totals = {}
        for key in ("prompt_tokens", "completion_tokens", "thinking_tokens"):
            counters = [call.get(key) for call in calls]
            token_totals[key] = {"reported_total": sum(value for value in counters if value is not None),
                                 "unreported_calls": sum(value is None for value in counters)}
        summaries[name] = {"cases": len(rows), "passed": sum(row["passed"] for row in rows),
            "statuses": dict(Counter(row["status"] for row in rows)),
            "answered_or_partial": sum(row["status"] in {"answered", "partial"} for row in rows),
            "abstained_or_failed": sum(row["status"] not in {"answered", "partial"} for row in rows),
            "count_cases": sum(row["expected_count"] is not None for row in rows),
            "numeric_count_agreements": sum(row["expected_count"] is not None and row["checks"]["count"] for row in rows),
            "missed_instances": sum(len(row["missed_step_ids"] or []) for row in rows),
            "false_instances": sum(len(row["false_step_ids"] or []) for row in rows),
            "membership_unscored_cases": sum(row["expected_step_ids"] is None for row in rows),
            "p50_ms": _percentile([row["elapsed_ms"] for row in rows], .5),
            "p95_ms": _percentile([row["elapsed_ms"] for row in rows], .95),
            "planner_requests": len(calls), "external_inference_requests": 0 if name == "replay" else len(calls),
            "usage": token_totals, "cost_estimate": None,
            "by_family": {family: {"cases": sum(row["family"] == family for row in rows),
                                     "passed": sum(row["family"] == family and row["passed"] for row in rows)}
                          for family in sorted({row["family"] for row in rows})}}
    return summaries


def paired_scores(scores, providers):
    """Compare matched cases, keeping input equality separate from outcome quality."""
    if len(providers) < 2:
        return []
    baseline = providers[0]
    indexed = {(row["provider"], row["case_id"]): row for row in scores}
    comparisons = []
    for candidate in providers[1:]:
        pairs = []
        for case_id in sorted({row["case_id"] for row in scores}):
            left, right = indexed.get((baseline, case_id)), indexed.get((candidate, case_id))
            if left is None or right is None:
                continue
            pairs.append({"case_id": case_id, "baseline_passed": left["passed"], "candidate_passed": right["passed"],
                "same_initial_catalog": bool(left["calls"] and right["calls"]) and
                    left["calls"][0]["input_sha256"] == right["calls"][0]["input_sha256"],
                "elapsed_delta_ms": right["elapsed_ms"] - left["elapsed_ms"]})
        comparisons.append({"baseline": baseline, "candidate": candidate, "paired_cases": len(pairs),
            "candidate_only_passed": sum(not row["baseline_passed"] and row["candidate_passed"] for row in pairs),
            "baseline_only_passed": sum(row["baseline_passed"] and not row["candidate_passed"] for row in pairs),
            "both_passed": sum(row["baseline_passed"] and row["candidate_passed"] for row in pairs),
            "both_failed": sum(not row["baseline_passed"] and not row["candidate_passed"] for row in pairs),
            "cases": pairs})
    return comparisons


async def evaluate(output: Path, *, providers=("replay",), live=False, case_ids=None):
    if not providers or any(name not in PROVIDERS for name in providers):
        raise ValueError("Choose supported planner providers.")
    if any(name != "replay" for name in providers) and not live:
        raise ValueError("External inference requires explicit --live.")
    if len(set(providers)) != len(providers):
        raise ValueError("Provider comparisons must not repeat a provider.")
    cases = [case for case in CASES if case_ids is None or case.id in case_ids]
    if not cases or case_ids is not None and set(case_ids) - {case.id for case in CASES}:
        raise ValueError("Choose known evaluation case IDs.")
    output.mkdir(parents=True, exist_ok=False)
    fixtures = {group: build_fixture(output / "sources", group) for group in GROUPS if any(c.group == group for c in cases)}
    manifest = {"fixture_version": VERSION, "code_revision": _revision(), "source_code": source_fingerprint(), "python": platform.python_version(),
        "ifcopenshell": ifcopenshell.version, "mode": "live_comparison" if any(name != "replay" for name in providers) else "offline_replay",
        "synthetic_sources_only": True, "providers": list(providers),
        "cases": [{**asdict(case), "source_sha256": fixtures[case.group].sha256,
                   "source_path": "sources/" + fixtures[case.group].path.name,
                   "leakage_group": case.group} for case in cases]}
    (output / "manifest.json").write_text(_json(manifest) + "\n", encoding="utf-8")
    predictions = []
    configurations = {}
    replay_state = {}
    with (output / "predictions.jsonl").open("w", encoding="utf-8") as stream:
        for name in providers:
            provider, close = await _provider(name, replay_state)
            recording = RecordingPlanner(provider)
            configurations[name] = _safe_config(provider)
            service = IfcService(None, planner=recording, settings=provider.settings, max_models=len(fixtures))
            try:
                descriptions = {group: service._load(f.path, f.sha256, f.path.stat().st_size) for group, f in fixtures.items()}
                for case in cases:
                    fixture, description = fixtures[case.group], descriptions[case.group]
                    model = service._model(description.model_id, fixture.sha256)
                    if name == "replay":
                        replay_state["proposal"] = replay_proposal(case, model, fixture)
                    request = _request(case, fixture, description.model_id)
                    offset, started = len(recording.calls), perf_counter()
                    prediction = {"provider": name, "case_id": case.id, "source_sha256": fixture.sha256,
                                  "request": request.model_dump(mode="json")}
                    try:
                        response = await service.question(request, "evaluation:" + name + ":" + case.id)
                        prediction["response"] = response.model_dump(mode="json")
                    except ApiError as exc:
                        prediction["error"] = {"code": exc.code, "status": exc.status_code,
                                               **_provider_diagnostics(exc)}
                    prediction["elapsed_ms"] = (perf_counter() - started) * 1000
                    prediction["calls"] = recording.calls[offset:]
                    predictions.append(prediction)
                    stream.write(_json(prediction) + "\n")
                    stream.flush()
            finally:
                service.close()
                await close()
    # Reference values are imported only after every prediction has been saved.
    from .references import REFERENCES
    scores = [_score(prediction, next(c for c in cases if c.id == prediction["case_id"]),
                     fixtures[next(c.group for c in cases if c.id == prediction["case_id"])], REFERENCES[prediction["case_id"]])
              for prediction in predictions]
    report = {"mode": manifest["mode"], "synthetic_sources_only": True, "configurations": configurations,
        "cases": len(cases), "summary": summarize_scores(scores), "scores": scores,
        "paired_comparisons": paired_scores(scores, providers),
        "all_passed": all(score["passed"] for score in scores),
        "limitations": ["Replay validates fixed typed plans and engine/evidence behavior; it does not measure natural-language quality.",
                        "Synthetic fixture outcomes do not establish supplied-corpus accuracy or physical building completeness.",
                        "Evidence checks cover declared fixture identities and source anchors; independent human source review remains separate.",
                        "Reported p50/p95 use nearest ranks over this small run, not a production performance benchmark."]}
    (output / "report.json").write_text(_json(report) + "\n", encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=Path("experiments/runs/ifc-planners") / datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ"))
    parser.add_argument("--providers", nargs="+", choices=PROVIDERS, default=["replay"])
    parser.add_argument("--live", action="store_true", help="Allow external inference for the explicitly selected live providers; synthetic sources only.")
    parser.add_argument("--cases", nargs="+", help="Optional case IDs; default is all 24 grouped cases.")
    args = parser.parse_args(argv)
    if any(name != "replay" for name in args.providers) and not args.live:
        parser.error("External inference requires --live; default replay uses no credentials or network.")
    try:
        report = asyncio.run(evaluate(args.output, providers=args.providers, live=args.live, case_ids=args.cases))
    except (ValueError, FileExistsError) as exc:
        parser.error(str(exc))
    print(_json({"output": str(args.output), "all_passed": report["all_passed"], "summary": report["summary"]}))
    return 0 if report["all_passed"] else 1
