"""Credential-free IFC upload/planner/executor/evidence integration checks.

The source is a generated IFC and all Nemotron HTTP replies are mocked. These
checks verify deterministic computation and wire behavior, not model accuracy.
"""
from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from decimal import Decimal
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import httpx
import ifcopenshell.guid

from contracts import models as m
from contracts.validation import validate_plan, validate_result
from ifc_engine.catalog import attribute_key, POLICIES
from image_api.app import create_app
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, ConfigurationError, NemotronSettings
from tests.test_ifc_engine import sample_model


KEY = "synthetic-ifc-api-credential"


def completion(payload, *, content=None, status=200, finish="stop"):
    if status != 200:
        return httpx.Response(status, json={"error": {"message": "private " + KEY}})
    return httpx.Response(200, json={"id": "synthetic-ifc", "object": "chat.completion", "created": 1,
        "model": "synthetic-planner", "choices": [{"index": 0, "finish_reason": finish,
            "message": {"role": "assistant", "content": content if content is not None else json.dumps(payload)}}],
        "usage": {"prompt_tokens": 123, "completion_tokens": 45, "total_tokens": 168}})


def proposal(target="window", operation=None):
    steps = [{"id": "objects", "operation": {"kind": "select", "concept_ids": ["concept:" + target],
              "count_policy": POLICIES["all_matches"].model_dump()}}]
    steps.append({"id": "answer", "operation": operation or {"kind": "aggregate", "input_step_id": "objects", "method": "count"}})
    return {"status": "ready", "interpretation": "Count modeled window occurrences in the selected scope.",
            "explicitly_requests_entire_model": False, "steps": steps, "output_step_id": "answer"}


class IfcApiTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        cls.directory = tempfile.TemporaryDirectory()
        cls.path = Path(cls.directory.name) / "source.ifc"
        source, doors, rooms, stairs, ground, upper = sample_model(cls.path)
        cls.windows = [source.create_entity("IfcWindow", GlobalId=ifcopenshell.guid.new(), Name=name,
            OverallWidth=width, OverallHeight=1500.) for name, width in [("121.A", 900.), ("121.B", 1200.), ("121.C", 1000.)]]
        source.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
                            RelatingStructure=ground, RelatedElements=cls.windows[:2])
        source.create_entity("IfcRelContainedInSpatialStructure", GlobalId=ifcopenshell.guid.new(),
                            RelatingStructure=upper, RelatedElements=cls.windows[2:])
        source.write(str(cls.path))
        cls.content = cls.path.read_bytes()
        cls.sha = hashlib.sha256(cls.content).hexdigest()
        cls.window_steps = [item.id() for item in cls.windows]
        cls.window_guids = [item.GlobalId for item in cls.windows]
        cls.door_steps = [item.id() for item in doors]
        cls.ground_step = ground.id()

    @classmethod
    def tearDownClass(cls):
        cls.directory.cleanup()

    def setUp(self):
        self.provider_requests = []
        self.reply = proposal()

    @asynccontextmanager
    async def api(self, handler=None, *, configured=True):
        async def transport(request):
            self.provider_requests.append(json.loads(request.content))
            value = handler(request) if handler else completion(self.reply)
            return await value if hasattr(value, "__await__") else value
        provider = httpx.AsyncClient(transport=httpx.MockTransport(transport))
        sdk = AsyncNemotronClient(NemotronSettings(api_key=KEY, model="synthetic-planner", max_retries=0), http_client=provider)
        def factory():
            if not configured:
                raise ConfigurationError("synthetic unconfigured")
            return sdk
        app = create_app(ApiSettings(), client_factory=factory)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                yield client, app
        await provider.aclose()

    async def upload(self, client, **options):
        response = await client.post("/api/ifc/models", data={"source_sha256": options.get("sha", self.sha)},
            files={"file": ("original.ifc", options.get("content", self.content), "application/x-step")})
        self.assertEqual(response.status_code, options.get("status", 200), response.text)
        return response.json()

    async def question(self, client, model, **options):
        value = {"model_id": model["model_id"], "source_sha256": model["source_sha256"],
                 "question": "How many windows?", "scope": "view", "visible_step_ids": self.window_steps[:2],
                 "view_label": "Ground"}
        value.update(options)
        return await client.post("/api/ifc/questions", json=value)

    async def test_view_count_and_native_highlight_identities_are_exact(self):
        async with self.api() as (client, app):
            model = await self.upload(client)
            response = await self.question(client, model)
            self.assertEqual(response.status_code, 200, response.text)
            answer = m.IfcQuestionResponse.model_validate(response.json())
            self.assertEqual(answer.result.claims[0].value.value, 2)
            self.assertEqual(answer.result.claims[0].count_policy.grain, "occurrence")
            self.assertEqual({e.step_id for e in answer.included_elements}, set(self.window_steps[:2]))
            self.assertEqual({e.guid for e in answer.included_elements}, set(self.window_guids[:2]))
            self.assertEqual({e.name for e in answer.included_elements}, {"121.A", "121.B"})
            self.assertEqual(answer.scope_label, "Ground")
            self.assertEqual(answer.source_sha256, self.sha)
            self.assertEqual(answer.result.metrics.model_input_tokens, 123)
            self.assertEqual(answer.assets[0].sha256, self.sha)
            self.assertTrue(answer.assets[0].uri.startswith("ifc-session://"))
            self.assertEqual({c.id for c in answer.coverage}, set(answer.result.claims[0].coverage_ids))
            model_state = app.state.ifc_service._model(model["model_id"], self.sha)
            validate_plan(answer.plan, model_state.engine.bundle, model_state.engine.capabilities)
            validate_result(answer.result, model_state.engine.bundle, answer.plan)
            self.assertEqual(len(answer.plan.scope.exact_entity_ids), 2)
            self.assertTrue(all(a.selector.kind in {"step_id", "ifc_guid"} for a in answer.anchors))
            self.assertNotIn(KEY, response.text)

    async def test_explicit_model_scope_counts_all_windows(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, scope="model", visible_step_ids=None)
            self.assertEqual(response.status_code, 200, response.text)
            body = response.json()
            self.assertEqual(body["result"]["claims"][0]["value"]["value"], 3)
            self.assertEqual(len(body["included_elements"]), 3)
            self.assertEqual(body["scope_label"], "Entire model")
            self.assertIsNone(body["plan"]["scope"]["exact_entity_ids"])

    async def test_empty_view_is_zero_and_not_unrestricted(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, visible_step_ids=[])
            body = response.json()
            self.assertEqual(body["result"]["status"], "answered", response.text)
            self.assertEqual(body["result"]["claims"][0]["value"]["value"], 0)
            self.assertEqual(body["included_elements"], [])
            self.assertEqual(body["plan"]["scope"]["exact_entity_ids"], [])

    async def test_exact_view_does_not_expand_spatial_descendants(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, visible_step_ids=[self.ground_step])
            self.assertEqual(response.json()["result"]["claims"][0]["value"]["value"], 0)

    async def test_unknown_visible_object_is_incomplete_not_zero(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, visible_step_ids=[999999])
            body = response.json()
            self.assertEqual(body["result"]["status"], "incomplete_coverage")
            self.assertEqual(body["result"]["claims"], [])

    async def test_model_wording_does_not_silently_broaden_view(self):
        self.reply["explicitly_requests_entire_model"] = True
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, question="How many windows in the entire model?")
            self.assertEqual(response.json()["result"]["status"], "needs_clarification")
            self.assertFalse(response.json()["result"]["claims"])

    async def test_window_width_rank_highlights_only_the_final_member(self):
        self.reply = proposal(operation={"kind": "rank", "input_step_id": "objects",
            "field": {"kind": "property", "key": attribute_key("OverallWidth")}, "direction": "descending", "limit": 1})
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model)
            body = response.json()
            self.assertEqual(body["result"]["status"], "answered", response.text)
            self.assertEqual([e["step_id"] for e in body["included_elements"]], [self.window_steps[1]])
            self.assertEqual([e["step_id"] for e in body["excluded_elements"]], [self.window_steps[0]])
            self.assertTrue(any(f["property_key"] == attribute_key("OverallWidth") for f in body["facts"]))

    async def test_stored_width_sum_retains_units_and_fact_inputs(self):
        self.reply = proposal(operation={"kind": "aggregate", "input_step_id": "objects", "method": "sum",
            "field": {"kind": "property", "key": attribute_key("OverallWidth")}, "output_unit_id": "unit:m"})
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model)
            body = response.json()
            value = body["result"]["claims"][0]["value"]
            self.assertEqual(Decimal(value["magnitude"]), Decimal("2.1"))
            self.assertEqual(value["unit_id"], "unit:m")
            self.assertEqual(len([f for f in body["facts"] if f["property_key"] == attribute_key("OverallWidth")]), 2)
            self.assertTrue(any(n["operation"] == "convert_unit" for n in body["result"]["calculations"]))

    async def test_missing_filter_value_cannot_be_an_exact_count(self):
        self.reply = proposal("door")
        self.reply["steps"][0]["operation"]["where"] = {"kind": "compare", "field": {"kind": "property", "key": attribute_key("OverallWidth")},
            "operator": "gt", "value": {"kind": "quantity", "magnitude": "1", "unit_id": "unit:m", "quantity_kind": "length", "basis": "modeled", "unit_resolution": "derived"}}
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, visible_step_ids=self.door_steps)
            self.assertEqual(response.json()["result"]["status"], "missing_information", response.text)
            self.assertFalse(response.json()["result"]["claims"])

    async def test_invalid_plan_identifier_cannot_return_a_successful_answer(self):
        self.reply["steps"][0]["operation"]["concept_ids"] = ["concept:invented-source-category"]
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model)
            self.assertEqual(response.status_code, 200, response.text)
            self.assertEqual(response.json()["result"]["status"], "execution_error")
            self.assertFalse(response.json()["result"]["claims"])

    async def test_unsupported_planner_outcome_is_honest(self):
        self.reply = {"status": "unsupported_operation", "interpretation": "Shortest egress paths require geometry not implemented by this engine.",
                      "explicitly_requests_entire_model": False, "steps": [], "output_step_id": None}
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model)
            self.assertEqual(response.json()["result"]["status"], "unsupported_operation")
            self.assertIsNone(response.json()["plan"])
            self.assertEqual(response.json()["included_elements"], [])

    async def test_source_mismatch_rejected_before_planning(self):
        async with self.api() as (client, _):
            await self.upload(client, sha="0" * 64, status=409)
            model = await self.upload(client)
            response = await self.question(client, model, source_sha256="0" * 64)
            self.assertEqual(response.status_code, 409)
            self.assertEqual(self.provider_requests, [])

    async def test_non_ifc_source_is_rejected(self):
        content = b"not IFC data"
        async with self.api() as (client, _):
            await self.upload(client, content=content, sha=hashlib.sha256(content).hexdigest(), status=422)

    async def test_duplicate_upload_reuses_extracted_session(self):
        async with self.api() as (client, _):
            first = await self.upload(client)
            with patch("ifc_api.service.IfcQueryEngine.open", side_effect=AssertionError("must reuse")):
                second = await self.upload(client)
            self.assertEqual(first["model_id"], second["model_id"])

    async def test_deleted_and_expired_models_require_reupload(self):
        async with self.api() as (client, app):
            first = await self.upload(client)
            response = await client.delete("/api/ifc/models/" + first["model_id"])
            self.assertEqual(response.status_code, 204)
            response = await self.question(client, first)
            self.assertEqual(response.status_code, 410)
            second = await self.upload(client)
            app.state.ifc_service.ttl_seconds = -1
            response = await self.question(client, second)
            self.assertEqual(response.status_code, 410)
            self.assertEqual(self.provider_requests, [])

    async def test_upload_works_without_credentials_questions_report_setup(self):
        async with self.api(configured=False) as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model)
            self.assertEqual(response.status_code, 503)
            self.assertEqual(response.json()["code"], "not_configured")

    async def test_view_requires_unique_explicit_step_ids(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            for ids in [None, [1, 1], [0], [-1], [True]]:
                with self.subTest(ids=ids):
                    response = await self.question(client, model, visible_step_ids=ids)
                    self.assertEqual(response.status_code, 422, response.text)
            self.assertEqual(self.provider_requests, [])

    async def test_planner_receives_only_catalog_and_relevant_source_identity(self):
        async with self.api() as (client, _):
            model = await self.upload(client)
            response = await self.question(client, model, question="What is the width of window 121.A?")
            self.assertEqual(response.status_code, 200, response.text)
            wire = self.provider_requests[0]
            self.assertEqual(wire["response_format"], {"type": "json_object"})
            self.assertEqual(wire["temperature"], 0)
            prompt = json.loads(wire["messages"][-1]["content"])
            self.assertEqual(prompt["question"], "What is the width of window 121.A?")
            self.assertEqual(prompt["scope"], "view")
            matching = prompt["catalog"]["matching_elements"]
            self.assertTrue(any(e["name"] == "121.A" and e["step_id"] == self.window_steps[0] for e in matching))
            self.assertNotIn("ISO-10303", wire["messages"][-1]["content"])
            self.assertNotIn(str(self.path), wire["messages"][-1]["content"])
            self.assertNotIn("questions.jsonl", json.dumps(wire))

    async def test_malformed_and_truncated_provider_output_has_no_answer_or_secrets(self):
        for text, finish in [("private " + KEY, "stop"), (json.dumps(proposal()), "length")]:
            with self.subTest(finish=finish):
                async with self.api(lambda r: completion(None, content=text, finish=finish)) as (client, _):
                    model = await self.upload(client)
                    response = await self.question(client, model)
                    self.assertEqual(response.status_code, 502)
                    self.assertNotIn(KEY, response.text)
                    self.assertNotIn("private", response.text)
                    self.assertNotIn("claims", response.text)

    async def test_provider_errors_are_safe(self):
        for status in [401, 429, 500]:
            with self.subTest(status=status):
                async with self.api(lambda r: completion(None, status=status)) as (client, _):
                    model = await self.upload(client)
                    response = await self.question(client, model)
                    self.assertEqual(response.status_code, 503)
                    self.assertNotIn(KEY, response.text)
                    self.assertNotIn("private", response.text)

    async def test_busy_and_planning_timeout_release_the_gate(self):
        entered, release = asyncio.Event(), asyncio.Event()
        async def pending(request):
            entered.set()
            await release.wait()
            return completion(self.reply)
        async with self.api(pending) as (client, app):
            model = await self.upload(client)
            # The SDK lazily initializes request codecs on its first call.
            app.state.ifc_service.deadline_seconds = 0.5
            first = asyncio.create_task(self.question(client, model))
            await asyncio.wait_for(entered.wait(), 3)
            second = await self.question(client, model)
            self.assertEqual(second.status_code, 429)
            timed_out = await first
            self.assertEqual(timed_out.status_code, 504)
            self.assertFalse(app.state.ifc_service._gate.locked())
            release.set()
            third = await self.question(client, model)
            self.assertEqual(third.status_code, 200, third.text)


class ExactScopeEngineTests(unittest.TestCase):
    def test_exact_membership_replays_without_descendant_expansion(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.ifc"
            sample_model(path)
            from ifc_engine.engine import IfcQueryEngine
            engine = IfcQueryEngine.open(path)
            plan = engine.plan("door")
            plan.scope.exact_entity_ids = [engine.resolve_entity("Ground")]
            self.assertEqual(engine.execute(plan).claims[0].value.value, 0)
            plan.scope.exact_entity_ids = []
            self.assertEqual(engine.execute(plan).claims[0].value.value, 0)
            plan.scope.exact_entity_ids = [engine.resolve_entity("D1")]
            self.assertEqual(engine.execute(plan).claims[0].value.value, 1)
            plan.scope.exact_entity_ids = None
            self.assertEqual(engine.execute(plan).claims[0].value.value, 3)

    def test_exact_scope_prevents_traversal_reintroducing_hidden_objects(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.ifc"
            sample_model(path)
            from ifc_engine.engine import IfcQueryEngine
            engine = IfcQueryEngine.open(path)
            plan = engine.plan("storey")
            plan.scope.exact_entity_ids = [engine.resolve_entity("Ground")]
            plan.steps[-1] = m.PlanStep(id="answer", operation=m.TraverseOperation(
                kind="traverse", input_step_id="objects", predicate="contains", direction="outgoing"))
            result = engine.execute(plan)
            self.assertEqual(result.status, "answered", result.model_dump_json())
            self.assertEqual(result.claims[0].value.entity_ids, [])
            validate_result(result, engine.bundle, plan)
