"""Keep the imported Nemotron evaluation independent of the UI image provider."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

import httpx

from experiments.image_questions import run
from image_api.config import ApiSettings
from nemotron import AsyncNemotronClient, NemotronSettings
from tests.test_image_api import completion, image_bytes


class ImageQuestionExperimentTests(unittest.IsolatedAsyncioTestCase):
    async def test_gemini_workbench_setting_keeps_baseline_calls_and_metadata_on_nemotron(self):
        settings = ApiSettings(provider="gemini", preprocess_mode="off")
        model_settings = NemotronSettings(api_key="synthetic-evaluation-key", max_retries=0)
        requests = []

        def respond(request):
            requests.append(request)
            return completion()

        provider_http = httpx.AsyncClient(transport=httpx.MockTransport(respond))
        provider = AsyncNemotronClient(model_settings, http_client=provider_http)
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "cases.json").write_text('{"cases": []}', encoding="utf-8")
            with patch.object(run.ApiSettings, "from_env", return_value=settings), \
                    patch.object(run.NemotronSettings, "from_env", return_value=model_settings), \
                    patch.object(run, "RecordingClient", return_value=provider), \
                    patch("image_api.app.AsyncGeminiClient") as gemini:
                # Empty fixtures exercise the environment manifest without a dataset
                # or reference answers. Both runner entry points use recording_app.
                run.prepare(root, root)
                environment = json.loads((root / "environment.json").read_text())
                self.assertEqual(environment["api_settings"]["provider"], "nemotron")
                self.assertEqual(environment["api_settings"]["preprocess_mode"], "off")
                self.assertNotIn("api_key", environment["model_settings"])
                app = run.recording_app(root)
                async with app.router.lifespan_context(app):
                    async with httpx.AsyncClient(transport=httpx.ASGITransport(app), base_url="http://test") as client:
                        response = await client.post("/api/v1/candidates", data={"question": "Locate windows."},
                            files={"image": ("plan.png", image_bytes(), "image/png")})
                self.assertEqual(response.status_code, 200, response.text)
                self.assertEqual(response.json()["provenance"]["prompt_version"], "candidate-v2")
                self.assertEqual(len(requests), 1)
                self.assertEqual(json.loads(requests[0].content)["model"], model_settings.model)
                gemini.assert_not_called()
        self.assertTrue(provider_http.is_closed)


if __name__ == "__main__":
    unittest.main()
