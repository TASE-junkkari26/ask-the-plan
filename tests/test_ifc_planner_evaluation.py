"""The evaluator must distinguish replay, source evidence and model accuracy."""
from __future__ import annotations

import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from experiments.ifc_planners.cases import CASES
from experiments.ifc_planners.fixtures import GROUPS, build_fixture
from experiments.ifc_planners.references import REFERENCES
from experiments.ifc_planners.run import ReplayPlanner, _provider_diagnostics, _score, evaluate, paired_scores, source_fingerprint
from image_api.errors import ApiError


class FixtureManifestTests(unittest.TestCase):
    def test_sources_have_reproducible_hashes_and_project_grouped_splits(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            first = [build_fixture(root / "first", group) for group in GROUPS]
            second = [build_fixture(root / "second", group) for group in GROUPS]
            self.assertEqual([fixture.sha256 for fixture in first], [fixture.sha256 for fixture in second])
            self.assertEqual(len({fixture.sha256 for fixture in first}), 6)
        self.assertEqual(len(CASES), 24)
        self.assertEqual({case.id for case in CASES}, set(REFERENCES))
        self.assertEqual({case.group for case in CASES}, set(GROUPS))
        for group in GROUPS:
            grouped = [case for case in CASES if case.group == group]
            self.assertEqual(len(grouped), 4)
            self.assertEqual(len({case.split for case in grouped}), 1)

    def test_matching_count_cannot_hide_incorrect_door_membership(self):
        with tempfile.TemporaryDirectory() as temporary:
            fixture = build_fixture(Path(temporary), "classified")
            case = next(case for case in CASES if case.id == "classified-outside")
            prediction = {"provider": "replay", "elapsed_ms": 1., "calls": [], "response": {
                "scope": "model", "source_sha256": fixture.sha256,
                "plan": {"scope": {"exact_entity_ids": None}},
                "included_elements": [{"entity_id": "entry", "step_id": fixture.steps["entry"]},
                                      {"entity_id": "service", "step_id": fixture.steps["service"]}],
                "anchors": [], "result": {"status": "answered", "claims": [
                    {"value": {"kind": "count", "value": 2}, "quality": "exact"}]}}}
            score = _score(prediction, case, fixture, REFERENCES[case.id])
            self.assertTrue(score["checks"]["count"])
            self.assertFalse(score["checks"]["membership"])
            self.assertFalse(score["passed"])
            self.assertEqual(score["missed_step_ids"], [fixture.steps["patio"]])
            self.assertEqual(score["false_step_ids"], [fixture.steps["service"]])

    def test_paired_comparison_uses_case_identity_and_reports_changed_inputs(self):
        def row(provider, case, passed, digest):
            return {"provider": provider, "case_id": case, "passed": passed, "elapsed_ms": 1.,
                    "calls": [{"input_sha256": digest}]}
        scores = [row("baseline", "a", False, "same"), row("candidate", "b", False, "changed"),
                  row("candidate", "a", True, "same"), row("baseline", "b", True, "original")]
        comparison = paired_scores(scores, ("baseline", "candidate"))[0]
        self.assertEqual(comparison["paired_cases"], 2)
        self.assertEqual(comparison["candidate_only_passed"], 1)
        self.assertEqual(comparison["baseline_only_passed"], 1)
        self.assertTrue(comparison["cases"][0]["same_initial_catalog"])
        self.assertFalse(comparison["cases"][1]["same_initial_catalog"])

    def test_machine_diagnostics_reject_unrecognized_text_and_invalid_status(self):
        private = "Bearer private-credential must not be retained"
        self.assertEqual(_provider_diagnostics(ApiError(503, "provider_configuration", private,
                         provider_status_code=private, provider_code=private)), {})
        self.assertEqual(_provider_diagnostics(ApiError(503, "provider_configuration", private,
                         provider_status_code=True, provider_code="INVALID_ARGUMENT")),
                         {"provider_code": "INVALID_ARGUMENT"})

    def test_plan_diagnostics_keep_static_field_locations_without_rejected_values(self):
        error = ApiError(502, "invalid_model_output", "Safe plan error")
        error.plan_validation_errors = ["steps.0.operation.select.count_policy:missing",
            "private-credential:missing", "steps:Bearer private-credential", "interpretation:value_error"]
        self.assertEqual(_provider_diagnostics(error), {"plan_validation_errors": [
            "steps.0.operation.select.count_policy:missing", "interpretation:value_error"]})

    def test_code_fingerprint_tracks_uncommitted_adapter_changes_without_env_files(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            provider = root / "ifc_api" / "providers.py"
            provider.parent.mkdir()
            provider.write_text("native_schema = 'original'\n")
            (root / ".env").write_text("private credential must not be read")
            first = source_fingerprint(root)
            self.assertEqual(list(first["files"]), ["ifc_api/providers.py"])
            provider.write_text("native_schema = 'compact'\n")
            second = source_fingerprint(root)
            self.assertNotEqual(first["sha256"], second["sha256"])
            self.assertNotEqual(first["files"]["ifc_api/providers.py"], second["files"]["ifc_api/providers.py"])
            self.assertNotIn(".env", second["missing_files"])
            self.assertNotIn("private credential", json.dumps(second))


class PlannerEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_default_replays_all_cases_without_credentials_or_network(self):
        payloads = []
        original = ReplayPlanner.generate

        async def capture(provider, payload, **options):
            payloads.append(json.loads(payload))
            return await original(provider, payload, **options)

        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation"
            with patch("nemotron.NemotronSettings.from_env", side_effect=AssertionError("offline must not load credentials")), \
                 patch("gemini.GeminiSettings.from_env", side_effect=AssertionError("offline must not load credentials")), \
                 patch("ifc_api.config.IfcSettings.from_env", side_effect=AssertionError("offline must not load local environment")), \
                 patch("httpx.AsyncClient", side_effect=AssertionError("offline must not open HTTP transport")), \
                 patch.object(ReplayPlanner, "generate", capture):
                report = await evaluate(output)
            self.assertTrue(report["all_passed"], json.dumps([row for row in report["scores"] if not row["passed"]], indent=2))
            summary = report["summary"]["replay"]
            self.assertEqual(summary["cases"], 24)
            self.assertEqual(summary["passed"], 24)
            self.assertEqual(summary["external_inference_requests"], 0)
            self.assertEqual(summary["planner_requests"], 24)
            self.assertEqual(summary["statuses"]["partial"], 2)
            self.assertEqual(summary["statuses"]["missing_information"], 2)
            self.assertEqual(summary["statuses"]["needs_clarification"], 1)
            self.assertEqual(summary["statuses"]["conflicting_evidence"], 1)
            self.assertEqual(summary["usage"]["prompt_tokens"]["unreported_calls"], 24)
            self.assertIsNone(summary["cost_estimate"])
            stored = [json.loads(line) for line in (output / "predictions.jsonl").read_text().splitlines()]
            self.assertEqual(len(stored), 24)
            self.assertTrue(all(row["response"]["planning"]["provider"] == "offline_replay" for row in stored))
            self.assertEqual(json.loads((output / "manifest.json").read_text())["mode"], "offline_replay")
        evaluator_fields = {"reference_value", "expected_count", "expected_status", "leakage_group", "replay", "split"}

        def check_data(value):
            if isinstance(value, dict):
                self.assertFalse(evaluator_fields & value.keys())
                for child in value.values():
                    check_data(child)
            elif isinstance(value, list):
                for child in value:
                    check_data(child)
        self.assertEqual(len(payloads), 24)
        for payload in payloads:
            check_data(payload)

    async def test_live_provider_requires_explicit_opt_in_before_output_creation(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation"
            with self.assertRaisesRegex(ValueError, "--live"):
                await evaluate(output, providers=("gemini-high",))
            self.assertFalse(output.exists())

    async def test_provider_failure_remains_in_denominator_without_leaking_error_body(self):
        async def fail(*args, **kwargs):
            raise ApiError(503, "provider_unavailable", "private provider diagnostic must not be saved",
                           provider_status_code=400, provider_code="INVALID_ARGUMENT")
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation"
            with patch.object(ReplayPlanner, "generate", fail):
                report = await evaluate(output, case_ids=("classified-all",))
            self.assertFalse(report["all_passed"])
            self.assertEqual(report["summary"]["replay"]["cases"], 1)
            self.assertEqual(report["summary"]["replay"]["abstained_or_failed"], 1)
            self.assertEqual(report["summary"]["replay"]["statuses"], {"api_error": 1})
            saved = (output / "predictions.jsonl").read_text()
            self.assertNotIn("private provider diagnostic", saved)
            stored = json.loads(saved)
            self.assertEqual(stored["error"], {"code": "provider_unavailable", "status": 503,
                             "upstream_status": 400, "provider_code": "INVALID_ARGUMENT"})
            self.assertEqual(stored["calls"][0]["upstream_status"], 400)
            self.assertEqual(stored["calls"][0]["provider_code"], "INVALID_ARGUMENT")

    async def test_existing_output_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "evaluation"
            output.mkdir()
            marker = output / "existing.txt"
            marker.write_text("preserve this investigation")
            with self.assertRaises(FileExistsError):
                await evaluate(output, case_ids=("classified-all",))
            self.assertEqual(marker.read_text(), "preserve this investigation")


if __name__ == "__main__":
    unittest.main()
