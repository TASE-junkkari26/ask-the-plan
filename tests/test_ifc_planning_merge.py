"""Discovery and proposal repair share one captured scope and bounded budget."""
from __future__ import annotations

from copy import deepcopy
import hashlib
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.providers import PlannerReply
from ifc_api.service import IfcService
from tests.test_ifc_discovery import ScriptedPlanner, inspect_request
from tests.test_ifc_engine import sample_model


class PlanningMergeTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.directory = tempfile.TemporaryDirectory()
        self.path = Path(self.directory.name) / "source.ifc"
        _, doors, *_ = sample_model(self.path)
        self.sha = hashlib.sha256(self.path.read_bytes()).hexdigest()
        self.service = IfcService(None, settings=IfcSettings(fast_plans=False))
        description = self.service._load(self.path, self.sha, self.path.stat().st_size)
        self.model = self.service._model(description.model_id, self.sha)
        self.request = m.IfcQuestionRequest(model_id=self.model.model_id, source_sha256=self.sha,
            question="How many doors are in this view?", scope="view", visible_step_ids=[doors[0].id()])
        plan = self.model.engine.plan("door")
        self.ready = {"status": "ready", "interpretation": "Count door occurrences in the captured view.",
            "explicitly_requests_entire_model": False,
            "steps": [step.model_dump(mode="json") for step in plan.steps],
            "output_step_id": next(iter(plan.outputs.values()))}
        self.invalid = deepcopy(self.ready)
        self.invalid["steps"].append({"id": "invalid", "operation": {
            "kind": "traverse", "input_step_id": self.invalid["output_step_id"],
            "predicate": "contains", "direction": "outgoing"}})
        self.invalid["output_step_id"] = "invalid"

    def tearDown(self):
        self.service.close()
        self.directory.cleanup()

    async def test_discovery_then_preflight_repair_reuses_scope_and_accounts_for_all_calls(self):
        planner = ScriptedPlanner([inspect_request(action="search", query="doors"), self.invalid, self.ready])
        self.service.planner = planner
        with patch.object(self.model.engine, "execute", wraps=self.model.engine.execute) as execute:
            response = await self.service.question(self.request, "request:merged-planning")
        self.assertEqual(response.result.status, "answered")
        self.assertEqual(response.result.claims[0].value.value, 1)
        self.assertEqual(execute.call_count, 1)
        self.assertEqual(response.planning.model_requests, 3)
        self.assertEqual(response.planning.inspection_count, 1)
        self.assertEqual(response.planning.prompt_tokens, 60)
        self.assertEqual(response.result.metrics.model_output_tokens, 30)
        self.assertEqual([call["budget"]["model_requests_remaining"] for call in planner.calls], [3, 2, 1])
        self.assertEqual(planner.calls[0]["catalog"], planner.calls[2]["catalog"])
        self.assertEqual(planner.calls[0]["scope_fingerprint"], planner.calls[2]["scope_fingerprint"])
        self.assertEqual(len(planner.calls[2]["inspection_history"]), 1)
        self.assertIn("plan_repair", planner.calls[2])
        self.assertEqual(response.plan.scope.exact_entity_ids, [self.model.by_step[self.request.visible_step_ids[0]]])

    async def test_repair_does_not_reset_model_request_budget_after_discovery(self):
        planner = ScriptedPlanner([inspect_request(action="search", query="doors"), self.invalid, self.ready])
        self.service.planner = planner
        self.service.settings = IfcSettings(max_model_requests=2, fast_plans=False)
        with patch.object(self.model.engine, "execute", wraps=self.model.engine.execute) as execute:
            response = await self.service.question(self.request, "request:shared-limit")
        self.assertEqual(response.result.status, "needs_clarification")
        self.assertFalse(response.result.claims)
        self.assertEqual(execute.call_count, 0)
        self.assertEqual(len(planner.calls), 2)
        self.assertEqual(response.planning.model_requests, 2)
        self.assertEqual(response.planning.inspection_count, 1)

    async def test_unreported_usage_stays_unknown_across_repair(self):
        class MissingUsagePlanner(ScriptedPlanner):
            async def generate(self, payload, *, system, schema):
                reply = await super().generate(payload, system=system, schema=schema)
                return PlannerReply(text=reply.text, model=reply.model,
                    usage=None if len(self.calls) == 1 else reply.usage)

        planner = MissingUsagePlanner([self.invalid, self.ready])
        self.service.planner = planner
        response = await self.service.question(self.request, "request:unknown-usage")
        self.assertEqual(response.result.status, "answered")
        self.assertEqual(response.planning.model_requests, 2)
        self.assertIsNone(response.planning.prompt_tokens)
        self.assertIsNone(response.planning.completion_tokens)
        self.assertIsNone(response.result.metrics.model_input_tokens)
        self.assertIsNone(response.result.metrics.model_output_tokens)

    async def test_invalid_schema_diagnostics_do_not_echo_provider_field_names(self):
        secret = "private-provider-field-value"
        invalid = {**self.ready, secret: secret}
        planner = ScriptedPlanner([invalid, invalid])
        self.service.planner = planner
        response = await self.service.question(self.request, "request:sanitized-repair")
        self.assertEqual(response.result.status, "needs_clarification")
        self.assertNotIn(secret, response.model_dump_json())
        self.assertNotIn(secret, planner.calls[1]["plan_repair"]["reason"])
        self.assertEqual(response.planning.model_requests, 2)


if __name__ == "__main__":
    unittest.main()
