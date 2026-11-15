"""Real-dataset evaluator regressions use tiny sources and zero external calls."""
from __future__ import annotations

import importlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, patch

from experiments.ifc_dataset.questions import load_tasks, select_tasks
from experiments.ifc_dataset.run import ReplayPlanner, evaluate, evidence_checks
from ifc_engine.catalog import POLICIES
from image_api.errors import ApiError
from tests.test_ifc_engine import sample_model


def proposal(concept="door", *, entire=True):
    return {"status": "ready", "interpretation": "Count the selected source occurrences.",
            "explicitly_requests_entire_model": entire,
            "steps": [{"id": "selected", "operation": {"kind": "select", "concept_ids": ["concept:" + concept],
                       "count_policy": POLICIES["all_matches"].model_dump()}},
                      {"id": "total", "operation": {"kind": "aggregate", "input_step_id": "selected", "method": "count"}}],
            "output_step_id": "total"}


def fixture(root):
    dataset = root / "dataset"
    source = dataset / "data/ifc_models/source.ifc"
    source.parent.mkdir(parents=True)
    sample_model(source)
    bench = dataset / "data/ifc_bench/source.ifc"
    bench.parent.mkdir()
    bench.write_bytes(source.read_bytes())
    questions = [
        {"path": "data/ifc_models/source.ifc", "question": "How many doors are there in the model 'Fixture'?",
         "type": "count", "unit": "count", "answer": 3},
        {"path": "data/ifc_models/source.ifc", "question": "How many stairs are there in the model 'Fixture'?",
         "type": "count", "unit": "count", "answer": 3},
        {"path": "data/ifc_bench/source.ifc", "question": "How many doors are there in this building?",
         "type": "text", "unit": None, "answer": "Three doors; do not use this answer in planning."},
        {"path": "data/ifc_models/source_plan-01-ground.pdf", "question": "How many doors are there on this floor plan?",
         "type": "count", "unit": "count", "answer": 2},
    ]
    (dataset / "questions.jsonl").write_text("\n".join(json.dumps(q) for q in questions) + "\n")
    plans = root / "plans.json"
    plans.write_text(json.dumps({"1": proposal(), "2": proposal("stair"), "3": proposal()}))
    return dataset, plans


class DatasetInputTests(unittest.TestCase):
    def test_direct_ifc_selection_is_exact_and_references_are_not_task_fields(self):
        with tempfile.TemporaryDirectory() as temporary:
            dataset, _ = fixture(Path(temporary))
            tasks, sha = load_tasks(dataset)
        self.assertEqual(len(tasks), 3)
        self.assertEqual(len(sha), 64)
        self.assertEqual([task.line for task in select_tasks(tasks, lines=[2, 1])], [1, 2])
        self.assertEqual([task.line for task in select_tasks(tasks, models=["data/ifc_bench/source.ifc"])], [3])
        self.assertEqual([task.line for task in select_tasks(tasks, families=["Count / Doors"])], [1, 3])
        self.assertEqual([task.line for task in select_tasks(tasks, one_per_family=True)], [1, 2])
        self.assertFalse(any("answer" in task.as_dict() for task in tasks))
        for options in ({"lines": [4]}, {"families": ["Unreviewed"]}, {"models": ["missing.ifc"]}):
            with self.assertRaises(ValueError):
                select_tasks(tasks, **options)

    def test_numeric_quantity_comparison_converts_units_and_keeps_partial_counts_nonexact(self):
        from experiments.ifc_dataset.references import numeric_grade
        from ifc_engine.units import standard_units
        prediction = {"request": {"scope": "model"}, "response": {"units": [standard_units()["unit:mm2"].model_dump()],
            "result": {"status": "answered", "claims": [{"quality": "exact", "value": {
                "kind": "quantity", "magnitude": "19000000", "unit_id": "unit:mm2", "quantity_kind": "area"}}]}}}
        reference = {"type": "area", "unit": "m²", "answer": 19.1}
        self.assertEqual(numeric_grade(prediction, reference)["status"], "numeric_agreement")
        reference["answer"] = 20
        self.assertEqual(numeric_grade(prediction, reference)["status"], "numeric_disagreement")
        prediction["response"]["result"]["status"] = "partial"
        prediction["response"]["result"]["claims"][0]["quality"] = "lower_bound"
        self.assertEqual(numeric_grade(prediction, reference)["status"], "unanswered_or_nonexact")
        prediction["request"]["scope"] = "view"
        self.assertEqual(numeric_grade(prediction, reference)["status"], "ungraded_scope_variant")

    def test_complete_geometry_estimate_has_distinct_two_percent_agreement_but_estimated_counts_do_not_pass(self):
        from experiments.ifc_dataset.references import numeric_grade
        from ifc_engine.units import standard_units
        prediction = {"request": {"scope": "model"}, "response": {"units": [standard_units()["unit:m2"].model_dump()],
            "result": {"status": "answered", "claims": [{"quality": "estimated", "value": {
                "kind": "quantity", "magnitude": "19", "unit_id": "unit:m2", "quantity_kind": "area", "quality": "estimated"}}]}}}
        reference = {"type": "area", "unit": "m²", "answer": 19.1}
        grade = numeric_grade(prediction, reference)
        self.assertEqual(grade["status"], "numeric_agreement_estimated")
        self.assertEqual(grade["quality"], "estimated")
        prediction["response"]["result"]["claims"][0]["value"] = {"kind": "count", "value": 19}
        self.assertEqual(numeric_grade(prediction, {"type": "count", "unit": "count", "answer": 19})["status"], "unanswered_or_nonexact")


class DatasetEvaluationTests(unittest.IsolatedAsyncioTestCase):
    async def test_native_only_has_no_provider_configuration_or_transport_and_preserves_fallback_rows(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, _ = fixture(root)
            output = root / "evaluation"
            with patch("experiments.ifc_dataset.run._native_settings", side_effect=AssertionError("No provider settings")), \
                 patch("experiments.ifc_dataset.run._live_planner", side_effect=AssertionError("No provider client")), \
                 patch("experiments.ifc_dataset.run.IfcSettings.from_env", side_effect=AssertionError("No environment file")), \
                 patch("experiments.ifc_dataset.run.NoTransportPlanner.generate", side_effect=AssertionError("No inference submission")), \
                 patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("No network")):
                report = await evaluate(dataset, output, native_only=True)
            self.assertEqual(report["summary"]["selected_rows"], 3)
            self.assertEqual(report["summary"]["recorded_predictions"], 3)
            self.assertEqual(report["summary"]["statuses"], {"api_error": 2, "answered": 1})
            self.assertEqual(report["summary"]["external_inference_requests"], 0)
            self.assertEqual(report["summary"]["cumulative_started_calls"], 0)
            manifest = json.loads((output / "manifest.json").read_text())["identity"]
            self.assertEqual(manifest["mode"], "native_only")
            self.assertEqual(manifest["provider"], "none")
            self.assertIsNone(manifest["transport_settings"])

    async def test_zero_call_cap_still_runs_native_production_answers_without_provider_transport(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, _ = fixture(root)
            output = root / "evaluation"
            owner = SimpleNamespace(close=AsyncMock())
            planner = ReplayPlanner({3: proposal()})
            with patch("experiments.ifc_dataset.run._native_settings", return_value=SimpleNamespace(model="test-model", timeout_seconds=120)), \
                 patch("experiments.ifc_dataset.run._live_planner", new=AsyncMock(return_value=(planner, owner))), \
                 patch.object(planner, "generate", side_effect=AssertionError("Native grammar must not call a provider")), \
                 patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("No network")):
                report = await evaluate(dataset, output, live=True, lines=[1, 3], max_calls=0, fast_plans=True)
            self.assertEqual(report["summary"]["statuses"], {"api_error": 1, "answered": 1})
            self.assertEqual(report["summary"]["recorded_predictions"], 2)
            self.assertEqual(report["summary"]["cumulative_started_calls"], 0)
            self.assertEqual(report["summary"]["external_inference_requests"], 0)
            failed = json.loads((output / "predictions/line-00000001.json").read_text())
            self.assertEqual(failed["error"]["code"], "evaluation_call_budget")
            prediction = json.loads((output / "predictions/line-00000003.json").read_text())
            self.assertEqual(prediction["response"]["planning"]["provider"], "deterministic")
            self.assertEqual(prediction["response"]["planning"]["model_requests"], 0)
            self.assertEqual(prediction["response"]["result"]["claims"][0]["value"]["value"], 3)
            owner.close.assert_awaited_once()

    async def test_replay_runs_production_http_and_saves_predictions_before_reference_loading(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            output = root / "evaluation"
            original_import = importlib.import_module
            original_generate = ReplayPlanner.generate
            payloads = []

            def check_import(name, *args):
                if name == "experiments.ifc_dataset.references":
                    saved = [json.loads(raw) for raw in (output / "predictions.jsonl").read_text().splitlines()]
                    self.assertEqual({row["line"] for row in saved}, {1, 2, 3})
                    self.assertEqual(len(list((output / "predictions").glob("*.json"))), 3)
                return original_import(name, *args)

            async def capture(planner, payload, **kwargs):
                payloads.append(payload)
                return await original_generate(planner, payload, **kwargs)

            with patch("experiments.ifc_dataset.run._live_planner", side_effect=AssertionError("No live transport")), \
                 patch("experiments.ifc_dataset.run._native_settings", side_effect=AssertionError("No provider credentials")), \
                 patch("httpx.AsyncHTTPTransport.handle_async_request", side_effect=AssertionError("No network")), \
                 patch.object(importlib, "import_module", side_effect=check_import), \
                 patch.object(ReplayPlanner, "generate", capture):
                report = await evaluate(dataset, output, replay_plans=plans)
            self.assertEqual(report["summary"]["selected_rows"], 3)
            self.assertEqual(report["summary"]["statuses"], {"answered": 3})
            self.assertEqual(report["summary"]["grading"], {"numeric_agreement": 2, "ungraded_text": 1})
            self.assertEqual(report["summary"]["external_inference_requests"], 0)
            self.assertEqual(report["summary"]["cumulative_started_calls"], 3)
            self.assertFalse(report["summary"]["all_questions_supported"])
            self.assertTrue(all(all(v is not False for v in score["evidence_checks"].values()) for score in report["scores"]))
            self.assertTrue(all("do not use this answer" not in payload for payload in payloads))
            self.assertNotIn("GEMINI_API_KEY", (output / "manifest.json").read_text())
            with patch.object(ReplayPlanner, "generate", side_effect=AssertionError("Resume cannot repeat calls")):
                resumed = await evaluate(dataset, output, replay_plans=plans, resume=True)
            self.assertEqual(resumed["summary"]["cumulative_started_calls"], 3)
            self.assertEqual(len((output / "predictions.jsonl").read_text().splitlines()), 3)

    async def test_cumulative_call_cap_and_resume_preserve_unattempted_denominator(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            output = root / "evaluation"
            first = await evaluate(dataset, output, replay_plans=plans, lines=[1, 2], max_calls=1)
            self.assertEqual(first["summary"]["recorded_predictions"], 1)
            self.assertEqual(first["not_attempted_lines"], [2])
            second = await evaluate(dataset, output, replay_plans=plans, lines=[1, 2], max_calls=2, resume=True)
            self.assertEqual(second["summary"]["recorded_predictions"], 2)
            self.assertEqual(second["summary"]["cumulative_started_calls"], 2)
            ledger = [json.loads(raw) for raw in (output / "calls.jsonl").read_text().splitlines()]
            self.assertEqual([row["call_id"] for row in ledger if row["stage"] == "started"], [1, 2])

    async def test_interrupted_started_call_still_consumes_budget_when_prediction_is_missing(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            output = root / "evaluation"
            await evaluate(dataset, output, replay_plans=plans, lines=[1], max_calls=1)
            # Simulate a stop between provider transport and atomic prediction
            # persistence. The durable request-start ledger remains authoritative.
            next((output / "predictions").glob("*.json")).unlink()
            (output / "predictions.jsonl").write_text("")
            report = await evaluate(dataset, output, replay_plans=plans, lines=[1], max_calls=1, resume=True)
            self.assertEqual(report["summary"]["cumulative_started_calls"], 1)
            self.assertEqual(report["summary"]["started_calls_without_prediction"], 1)
            self.assertEqual(report["summary"]["recorded_predictions"], 0)
            self.assertEqual(report["summary"]["not_attempted_rows"], 1)
            self.assertEqual(report["summary"]["usage"]["prompt_tokens"]["unreported_calls"], 1)

    async def test_safe_provider_errors_and_existing_output_are_not_hidden_or_overwritten(self):
        secret = "private-transport-body-or-credential"
        async def fail(*args, **kwargs):
            raise ApiError(503, "provider_unavailable", secret)
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            output = root / "evaluation"
            with patch.object(ReplayPlanner, "generate", fail):
                report = await evaluate(dataset, output, replay_plans=plans, lines=[1])
            self.assertEqual(report["summary"]["statuses"], {"api_error": 1})
            self.assertEqual(report["summary"]["grading"], {"unanswered": 1})
            for artifact in output.rglob("*.json*"):
                self.assertNotIn(secret, artifact.read_text())
            with self.assertRaises(FileExistsError):
                await evaluate(dataset, output, replay_plans=plans, lines=[1])
            with self.assertRaisesRegex(ValueError, "Resume identity"):
                await evaluate(dataset, output, replay_plans=plans, lines=[1], resume=True, scope="view",
                               visible_step_ids={"data/ifc_models/source.ifc": []})

    async def test_view_inventory_stays_empty_and_reference_numeric_grade_is_disabled(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            values = json.loads(plans.read_text())
            values["1"] = proposal(entire=False)
            plans.write_text(json.dumps(values))
            output = root / "evaluation"
            report = await evaluate(dataset, output, replay_plans=plans, lines=[1], scope="view",
                                    visible_step_ids={"data/ifc_models/source.ifc": []})
            self.assertEqual(report["summary"]["grading"], {"ungraded_scope_variant": 1})
            prediction = json.loads(next((output / "predictions").glob("*.json")).read_text())
            self.assertEqual(prediction["request"]["visible_step_ids"], [])
            self.assertEqual(prediction["response"]["result"]["claims"][0]["value"]["value"], 0)
            self.assertTrue(prediction["evidence_checks"]["view_inventory_size_preserved"])
            changed = json.loads(json.dumps(prediction))
            changed["response"]["source_sha256"] = "0" * 64
            self.assertFalse(evidence_checks(changed)["source_question_scope_binding"])

    async def test_explicit_mode_and_complete_replay_inputs_are_required_before_output(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            dataset, plans = fixture(root)
            output = root / "evaluation"
            with self.assertRaisesRegex(ValueError, "--live"):
                await evaluate(dataset, output)
            self.assertFalse(output.exists())
            plans.write_text(json.dumps({"1": proposal()}))
            with self.assertRaisesRegex(ValueError, "Every selected row"):
                await evaluate(dataset, output, replay_plans=plans)
            self.assertFalse(output.exists())


if __name__ == "__main__":
    unittest.main()
