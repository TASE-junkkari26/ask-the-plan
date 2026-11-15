"""Concurrent deletion cannot slip between source lookup and active ownership."""
from __future__ import annotations

import asyncio
import hashlib
from pathlib import Path
import tempfile
import threading
import unittest

from contracts import models as m
from ifc_api.config import IfcSettings
from ifc_api.service import IfcService
from tests.test_ifc_api import proposal
from tests.test_ifc_discovery import ScriptedPlanner
from tests.test_ifc_engine import sample_model


class NativeSourceReservationRaceTests(unittest.IsolatedAsyncioTestCase):
    async def test_delete_waits_for_lookup_reservation_and_native_work_keeps_source(self):
        directory = tempfile.TemporaryDirectory()
        self.addCleanup(directory.cleanup)
        path = Path(directory.name) / "source.ifc"
        sample_model(path)
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        service = IfcService(None, planner=ScriptedPlanner([proposal("door")]),
            settings=IfcSettings(fast_plans=False))
        self.addCleanup(service.close)
        description = service._load(path, digest, path.stat().st_size, directory)
        model = service._model(description.model_id, digest)
        original_lookup, original_catalog = service._model, service._catalog
        lookup_returning, delete_attempted, delete_finished = (threading.Event() for _ in range(3))
        native_entered, native_release = threading.Event(), threading.Event()
        observations, delete_errors = {}, []

        def delete_source():
            try:
                if not lookup_returning.wait(5):
                    raise AssertionError("The source lookup did not reach the race barrier")
                delete_attempted.set()
                service.delete(model.model_id)
            except BaseException as error:
                delete_errors.append(type(error).__name__)
            finally:
                delete_finished.set()

        def paused_lookup(*args):
            selected = original_lookup(*args)
            lookup_returning.set()
            if not delete_attempted.wait(2):
                raise AssertionError("Concurrent deletion was not attempted")
            # The question must already hold its reservation lock while this
            # completed lookup is about to return. With the old split locks,
            # deletion finishes here and removes the original source file.
            observations["deleted_before_reservation"] = delete_finished.wait(2)
            return selected

        def held_native_work(*args):
            if not delete_finished.wait(2):
                raise AssertionError("Deletion did not finish after active ownership was acquired")
            observations["source_alive_during_native"] = path.is_file()
            observations["retired_during_native"] = model.retired
            observations["active_during_native"] = model.active
            native_entered.set()
            if not native_release.wait(5):
                raise AssertionError("The native source phase was not released")
            return original_catalog(*args)

        service._model = paused_lookup
        service._catalog = held_native_work
        deleter = threading.Thread(target=delete_source, name="owned-ifc-delete-race")
        deleter.start()
        request = m.IfcQuestionRequest(model_id=model.model_id, source_sha256=digest,
            question="How many doors are there?", scope="model")
        question = asyncio.create_task(service.question(request, "request:delete-race"))
        try:
            self.assertTrue(await asyncio.to_thread(native_entered.wait, 8), "Native work never reached its barrier")
            self.assertEqual(delete_errors, [])
            self.assertFalse(observations["deleted_before_reservation"],
                "Deletion slipped between model lookup and its active source reservation")
            self.assertTrue(observations["retired_during_native"])
            self.assertEqual(observations["active_during_native"], 1)
            self.assertTrue(observations["source_alive_during_native"])
            self.assertTrue(path.exists(), "A retired source is still owned by in-flight native work")
            self.assertFalse(question.done())
            native_release.set()
            response = await asyncio.wait_for(question, 5)
            self.assertEqual(response.result.status, "answered")
            self.assertEqual(model.active, 0)
            self.assertFalse(path.exists(), "The source must be removed after the final native owner releases it")
        finally:
            native_release.set()
            if not question.done():
                question.cancel()
            await asyncio.gather(question, return_exceptions=True)
            await asyncio.to_thread(deleter.join, 3)
            self.assertFalse(deleter.is_alive(), "The owned deletion thread must be cleaned up")


if __name__ == "__main__":
    unittest.main()
