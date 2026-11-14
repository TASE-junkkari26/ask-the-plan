"""Offline panel-tool checks, not model layout-accuracy evaluation."""
from dataclasses import replace
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from gemini.client import GeminiReply, GeminiUsage, GeminiError
from image_api.errors import ApiError
from image_api.images import PreparedImage
from image_api.region_proposal import GeminiRegionProposer


class RegionProposalTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.image = PreparedImage(Path("synthetic.png"), "a"*64, "b"*64, 2000, 1000)

    def client(self, value):
        return SimpleNamespace(settings=SimpleNamespace(model="gemini-4-hydrogen"),
            generate_candidates=AsyncMock(return_value=GeminiReply(text=json.dumps(value),
                model="gemini-4-hydrogen", usage=GeminiUsage(prompt_tokens=5, completion_tokens=8))))

    async def test_normalized_yx_maps_to_source_with_padding_and_usage(self):
        client = self.client({"status":"selected", "regions":[{"box_2d":[100,200,800,900], "reason":"Main plan"}], "limitations":[]})
        result = await GeminiRegionProposer(client).propose(self.image, "show doors")
        self.assertEqual(result.regions[0].source_box, (372,86,1828,814))
        self.assertEqual(result.status, "selected")
        self.assertEqual(result.prompt_tokens, 5)
        self.assertEqual(result.completion_tokens, 8)
        self.assertEqual(result.source_sha256, self.image.sha256)
        call = client.generate_candidates.call_args
        self.assertEqual(call.args, ("show doors",))
        self.assertEqual(call.kwargs["image"], self.image.path)
        self.assertIn("not object boxes", call.kwargs["system"])

    async def test_full_source_overview_uses_original_pixel_frame(self):
        client = self.client({"status":"selected", "regions":[{"box_2d":[0,0,1000,1000], "reason":"Entire plan"}], "limitations":[]})
        result = await GeminiRegionProposer(client).propose(replace(self.image, inference_width=1000, inference_height=500), "doors")
        self.assertEqual(result.regions[0].source_box, (0,0,2000,1000))

    async def test_multiple_relevant_panels_remain_separate(self):
        client = self.client({"status":"selected", "regions":[
            {"box_2d":[0,0,1000,400],"reason":"Floor A"},
            {"box_2d":[0,600,1000,1000],"reason":"Floor B"}], "limitations":[]})
        result = await GeminiRegionProposer(client, padding_fraction=0).propose(self.image, "doors on this page")
        self.assertEqual([r.source_box for r in result.regions], [(0,0,800,1000),(1200,0,2000,1000)])

    async def test_ambiguous_layout_keeps_whole_source(self):
        client = self.client({"status":"ambiguous", "regions":[], "limitations":["Several floors cannot be distinguished."]})
        result = await GeminiRegionProposer(client).propose(self.image, "doors")
        self.assertEqual(result.status, "full_source")
        self.assertEqual(result.regions[0].source_box, (0,0,2000,1000))
        self.assertIn("Several floors", result.limitations[0])

    async def test_invalid_boxes_do_not_drop_scope(self):
        for box in ([800,100,200,300], [0,-1,500,500], [0,0,500,1001], [True,0,500,500]):
            with self.subTest(box=box):
                client = self.client({"status":"selected", "regions":[{"box_2d":box,"reason":"Plan"}], "limitations":[]})
                result = await GeminiRegionProposer(client).propose(self.image, "doors")
                self.assertEqual(result.status, "full_source")
                self.assertTrue(result.limitations)

    async def test_too_many_panels_fall_back_instead_of_truncating(self):
        client = self.client({"status":"selected", "regions":[{"box_2d":[0,i,500,i+1], "reason":"Plan"} for i in range(5)], "limitations":[]})
        result = await GeminiRegionProposer(client).propose(self.image, "doors")
        self.assertEqual(result.status, "full_source")

    async def test_provider_failure_remains_error(self):
        client = self.client({})
        client.generate_candidates.side_effect = GeminiError("private body", status_code=429, retryable=True)
        with self.assertRaises(ApiError) as caught:
            await GeminiRegionProposer(client).propose(self.image, "doors")
        self.assertEqual(caught.exception.status_code, 503)
        self.assertNotIn("private", str(caught.exception))

    async def test_invalid_question_never_calls_provider(self):
        client = self.client({})
        with self.assertRaises(ApiError):
            await GeminiRegionProposer(client).propose(self.image, " ")
        client.generate_candidates.assert_not_called()


if __name__ == "__main__":
    unittest.main()
