"""Native source ownership survives cancellation and large-session replacement."""
import asyncio
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest
from unittest.mock import patch

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.service import DEFER_PROPERTY_BYTES, IfcService, _explicit_whole_model, _model_title_conflict
from ifc_engine.engine import IfcQueryEngine, QueryError
from tests.test_ifc_discovery import ScriptedPlanner
from tests.test_ifc_api import proposal
from tests.test_ifc_engine import sample_model


class NativeLifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_verified_wrong_model_identity_blocks_a_planner_that_would_count_this_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "duplex.ifc"
            source, *_ = sample_model(path)
            source.by_type("IfcProject")[0].Name = "Duplex Apartment"
            source.write(str(path))
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            planner = ScriptedPlanner([proposal()])
            service = IfcService(None, planner=planner, settings=IfcSettings(fast_plans=False))
            try:
                model = service._load(path, digest, path.stat().st_size, original_name="Duplex_Architectural.ifc")
                request = m.IfcQuestionRequest(model_id=model.model_id, source_sha256=digest,
                    question="How many windows are there in the model 'Different Hospital'?", scope="model")
                response = await service.question(request, "request:wrong-model")
                self.assertEqual(response.result.status, "needs_clarification")
                self.assertEqual(response.result.claims, [])
                self.assertEqual(planner.calls, [])
                self.assertEqual(response.planning.model_requests, 0)
            finally:
                service.close()

    def test_quoted_source_labels_cannot_become_scope_or_model_instructions(self):
        for text in ["Show objects called 'in the entire model' in this view.",
                     "Näytä huone 'koko mallissa' tässä näkymässä."]:
            self.assertFalse(_explicit_whole_model(text))
        self.assertTrue(_explicit_whole_model("Count windows in the entire model named 'Current view'."))
        with patch("ifc_api.model_identity.assess_model", side_effect=AssertionError("No file target exists")):
            self.assertIsNone(_model_title_conflict(None,
                'Show the room named "model \'Different Hospital\'" in this view.', False))

    async def test_source_identity_preflight_error_is_a_source_outcome_and_releases_gate(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.ifc"
            sample_model(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            planner = ScriptedPlanner([proposal()])
            service = IfcService(None, planner=planner, settings=IfcSettings(fast_plans=False))
            try:
                model = service._load(path, digest, path.stat().st_size)
                request = m.IfcQuestionRequest(model_id=model.model_id, source_sha256=digest,
                    question="How many windows are there?", scope="model")
                with patch("ifc_api.service._model_title_conflict", side_effect=QueryError(
                        "incomplete_coverage", "The native metadata check could not complete.")):
                    response = await service.question(request, "request:source-preflight")
                self.assertEqual(response.result.status, "incomplete_coverage")
                self.assertEqual(response.result.claims, [])
                self.assertEqual(planner.calls, [])
                self.assertFalse(service._gate.locked())
                self.assertEqual(service._model(model.model_id, digest).active, 0)
            finally:
                service.close()

    async def test_repeated_cancellation_keeps_discovery_gate_and_source_until_worker_finishes(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "source.ifc"
        sample_model(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        service = IfcService(None, planner=ScriptedPlanner([proposal()]), settings=IfcSettings(fast_plans=False))
        self.addCleanup(service.close)
        description = service._load(path, digest, path.stat().st_size, directory)
        model = service._model(description.model_id, digest)
        entered, release = threading.Event(), threading.Event()

        def catalog(*args):
            entered.set()
            if not release.wait(5):
                raise TimeoutError("Fixture was not released")
            return {}

        service._catalog = catalog
        request = m.IfcQuestionRequest(model_id=model.model_id, source_sha256=digest,
            question="Which modeled windows have a recorded type?", scope="model")
        task = asyncio.create_task(service.question(request, "request:cancel"))
        try:
            self.assertTrue(await asyncio.to_thread(entered.wait, 2))
            task.cancel()
            await asyncio.sleep(0.02)
            task.cancel()
            await asyncio.sleep(0.02)
            self.assertTrue(service._gate.locked())
            self.assertEqual(model.active, 1)
            service.delete(model.model_id)
            self.assertTrue(path.exists(), "Deleting a session cannot remove a worker's live source")
            release.set()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertFalse(service._gate.locked())
            self.assertEqual(model.active, 0)
            self.assertFalse(path.exists())
        finally:
            release.set()
            if not task.done():
                task.cancel()
            await asyncio.gather(task, return_exceptions=True)

    async def test_large_session_replacement_retires_idle_source_before_new_parse(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "first.ifc"
        sample_model(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        service = IfcService(None)
        self.addCleanup(service.close)
        first = service._load(path, digest, path.stat().st_size, directory)
        original = service._model(first.model_id, digest)
        engine = IfcQueryEngine.open(path)

        def load(*args, **kwargs):
            self.assertTrue(original.retired)
            self.assertFalse(path.exists(), "The previous large source is retired before the new native parse")
            return engine

        with patch("ifc_api.service.IfcQueryEngine.open", side_effect=load):
            service._load(path, "b" * 64, DEFER_PROPERTY_BYTES)
        self.assertEqual(len(service._models), 1)

    async def test_original_upload_name_is_a_label_and_cannot_choose_a_backend_path(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "source.ifc"
            sample_model(path)
            digest = hashlib.sha256(path.read_bytes()).hexdigest()
            service = IfcService(None)
            try:
                value = service._load(path, digest, path.stat().st_size,
                    original_name="C:\\private\\..\\Original clinic.ifc")
                model = service._model(value.model_id, digest)
                self.assertEqual(model.engine.bundle.documents[0].title[0].text, "Original clinic.ifc")
                self.assertEqual(model.source_path, path)
                self.assertNotIn("private", model.engine.bundle.assets[0].uri)
            finally:
                service.close()


if __name__ == "__main__":
    unittest.main()
