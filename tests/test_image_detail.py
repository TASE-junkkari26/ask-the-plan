"""Mocked HTTP detail-tool orchestration; no network or model accuracy claims."""
from __future__ import annotations

import asyncio
import base64
from contextlib import asynccontextmanager
import hashlib
from io import BytesIO
import json
from pathlib import Path
import unittest

import httpx
from PIL import Image

from gemini import AsyncGeminiClient, GeminiSettings
from image_api.app import create_app
from image_api.config import ApiSettings
from image_api.service import _detail_resolution
from nemotron import ConfigurationError


KEY = "synthetic-detail-test-key"
MODEL = "gemini-4-hydrogen"


class DetailResolutionPolicyTests(unittest.TestCase):
    def test_only_declared_doors_or_anchored_door_count_lead_ins_use_extra_resolution(self):
        self.assertEqual(_detail_resolution("Inspect this symbol", {"target_kind":"door"}), "ultra_high")
        for question in ("How many doors are shown?", "  Kuinka monta ovea on esitetty?",
                         "Montako ovea on tässä?", "Wie viele Türen sind hier?",
                         "Combien de portes sont dessinées?", "Quante porte sono qui?",
                         "Hur många dörrar visas?", "Hvor mange døre er vist?",
                         "Hoeveel deuren zijn er?", "Mitu ust on siin?", "Ile drzwi jest tutaj?"):
            with self.subTest(question=question):
                self.assertEqual(_detail_resolution(question, {"target_kind":"other"}), "ultra_high")
                self.assertIsNone(_detail_resolution(question, None))
                self.assertIsNone(_detail_resolution(question, {"target_kind":"window"}))

    def test_other_categories_and_quoted_source_labels_keep_default_resolution(self):
        for question in ("How many windows are shown?", "How many floors are shown?",
                         "How many rooms labelled 'doors' are shown?",
                         "How many windows labelled 'How many doors' are shown?",
                         "What is the area of the room 'Kuinka monta ovea'?",
                         "How many doorsets are shown?", "Show doors"):
            with self.subTest(question=question):
                self.assertIsNone(_detail_resolution(question, {"target_kind":"other"}))
        self.assertIsNone(_detail_resolution("How many windows?", {
            "target_kind":"other", "source_text":"How many doors?"}))


def interaction(payload, *, input_tokens=100, output_tokens=20, thought_tokens=5):
    return httpx.Response(200, json={
        "id": "synthetic-detail-interaction", "object": "interaction", "model": MODEL,
        "status": "completed", "steps": [{"type":"model_output", "content":[{
            "type":"text", "text":json.dumps(payload)}]}],
        "usage":{"total_input_tokens":input_tokens,"total_output_tokens":output_tokens,
                 "total_thought_tokens":thought_tokens}})


def candidate(box=(250,200,750,600)):
    return {"status":"ok", "candidates":[{
        "category":"door", "source_label":None, "box_2d":list(box),
        "uncertain":False, "uncertainty_reason":None,
        "visual_cue":"Door leaf and quarter-circle swing."}], "limitations":[]}


def selection(box=(250,250,750,750)):
    return {"status":"selected", "regions":[{"box_2d":list(box),
            "reason":"Main plan with attached source structures."}], "limitations":[]}


def image_details(request):
    body = json.loads(request.content)
    content = base64.b64decode(body["input"][1]["data"])
    with Image.open(BytesIO(content)) as image:
        width, height = image.size
        r,g,b = image.getpixel((0,0))
    return body, width, height, (b//32*256+r, b%32*256+g)


class ImageDetailTests(unittest.IsolatedAsyncioTestCase):
    @classmethod
    def setUpClass(cls):
        with Image.new("RGB",(1200,800)) as image, BytesIO() as stream:
            # Encode the source origin in a crop's first pixel so mocked tile
            # detections can describe one shared source object independently.
            image.putdata([(x%256,y%256,(x//256)*32+y//256) for y in range(800) for x in range(1200)])
            image.save(stream,format="PNG")
            cls.content = stream.getvalue()

    def setUp(self):
        self.requests = []
        self.paths = []

    @asynccontextmanager
    async def api(self, handler, *, settings=None):
        async def transport(request):
            self.requests.append(request)
            result = handler(request)
            return await result if hasattr(result,"__await__") else result

        def gemini_factory():
            client = AsyncGeminiClient(GeminiSettings(api_key=KEY), transport=httpx.MockTransport(transport))
            generate = client.generate_candidates
            async def track(*args, **kwargs):
                self.paths.append(Path(kwargs["image"]))
                return await generate(*args,**kwargs)
            client.generate_candidates = track
            return client

        def no_nemotron():
            raise ConfigurationError("Synthetic test deliberately has no IFC planner")

        app = create_app(settings or ApiSettings(provider="gemini",preprocess_mode="overview"),
                         client_factory=no_nemotron,gemini_client_factory=gemini_factory)
        async with app.router.lifespan_context(app):
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url="http://test") as client:
                yield client, app

    async def post(self, client, *, options=None, path="detect-detail"):
        data = {"question":"show doors"}
        if options is not None:
            data["options"] = options if isinstance(options,str) else json.dumps(options)
        return await client.post("/api/v1/tools/"+path,data=data,
            files={"image":("source.png",self.content,"image/png")})

    async def test_automatic_region_selection_maps_boxes_and_aggregates_actual_usage(self):
        def handler(request):
            body, width, height, origin = image_details(request)
            if body["response_format"]["schema"]["properties"]["status"].get("enum") == ["selected","ambiguous","unreadable"]:
                self.assertEqual((width,height),(1200,800))
                self.assertNotIn("resolution", body["input"][1])
                return interaction({**selection(),"target_kind":"door"},input_tokens=10,output_tokens=4,thought_tokens=2)
            self.assertEqual((width,height,origin),(624,416,(288,192)))
            self.assertEqual(body["input"][1]["resolution"],"ultra_high")
            return interaction(candidate())
        async with self.api(handler) as (client,app):
            response = await self.post(client)
            self.assertEqual(app.state.in_flight,0)
        self.assertEqual(response.status_code,200,response.text)
        body = response.json()
        self.assertEqual(body["image"]["sha256"],hashlib.sha256(self.content).hexdigest())
        self.assertEqual((body["image"]["width"],body["image"]["height"]),(1200,800))
        self.assertEqual(body["detail"]["selection"],"automatic")
        self.assertEqual(body["detail"]["selected_regions"],[[288,192,912,608]])
        self.assertEqual(body["detail"]["provider_calls"],2)
        geometry = body["candidates"][0]["geometry"]
        self.assertAlmostEqual(geometry["minimum"][0],412.8)
        self.assertAlmostEqual(geometry["minimum"][1],296.0)
        self.assertAlmostEqual(geometry["maximum"][0],662.4)
        self.assertAlmostEqual(geometry["maximum"][1],504.0)
        self.assertEqual(body["metrics"]["prompt_tokens"],110)
        self.assertEqual(body["metrics"]["completion_tokens"],31)
        self.assertEqual(len(self.requests),2)
        self.assertTrue(all(not p.exists() for p in self.paths))

    async def test_small_source_fast_path_changes_resolution_only_for_door_count_queries(self):
        questions = [("How many doors are shown?", "ultra_high"),
                     ("Kuinka monta ovea on esitetty?", "ultra_high"),
                     ("How many windows are shown?", None),
                     ("How many floors are shown?", None),
                     ("How many rooms labelled 'doors' are shown?", None)]
        async with self.api(lambda _:interaction(candidate())) as (client,_):
            for question,expected in questions:
                with self.subTest(question=question):
                    before=len(self.requests)
                    response=await client.post("/api/v1/tools/detect-detail",
                        data={"question":question,"options":json.dumps({"mode":"tiles","max_calls":1})},
                        files={"image":("source.png",self.content,"image/png")})
                    self.assertEqual(response.status_code,200,response.text)
                    self.assertEqual(len(self.requests)-before,1)
                    body=json.loads(self.requests[-1].content)
                    if expected is None:
                        self.assertNotIn("resolution",body["input"][1])
                    else:
                        self.assertEqual(body["input"][1]["resolution"],expected)

    async def test_explicit_regions_skip_selector_and_preserve_source_coordinates(self):
        async with self.api(lambda _:interaction(candidate())) as (client,_):
            response = await self.post(client,options={"mode":"regions","regions":[[100,100,700,500]],"max_calls":1})
        self.assertEqual(response.status_code,200,response.text)
        body = response.json()
        self.assertEqual(body["candidates"][0]["geometry"],{
            "kind":"box","minimum":[220.,200.],"maximum":[460.,400.]})
        self.assertEqual(body["detail"]["selection"],"explicit")
        self.assertEqual(body["detail"]["provider_calls"],1)
        self.assertEqual(body["metrics"]["prompt_tokens"],100)
        self.assertEqual(len(self.requests),1)

    async def test_region_proposal_tool_returns_only_source_bound_metadata(self):
        async with self.api(lambda _:interaction(selection())) as (client,_):
            response = await self.post(client,path="propose-regions")
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["regions"][0]["source_box"],[288,192,912,608])
        self.assertNotIn("candidates",body)
        self.assertNotIn(KEY,response.text)
        self.assertEqual(len(self.requests),1)

    async def test_invalid_options_or_regions_make_no_provider_calls(self):
        options = ["not-json", {"mode":"regions"}, {"mode":"auto","regions":[[0,0,400,400]]},
                   {"tile_size":32}, {"max_calls":0}, {"arbitrary":"field"},
                   {"mode":"auto","max_calls":1},
                   {"mode":"regions","regions":[[0.5,0,400,400]]},
                   {"mode":"regions","regions":[[False,0,400,400]]},
                   {"mode":"regions","regions":[[-1,0,400,400]]},
                   {"mode":"regions","regions":[[0,0,1201,800]]},
                   {"mode":"regions","regions":[[0,0,400,400],[0,0,400,400]]},
                   {"mode":"regions","regions":[[0,0,400,400],[400,0,800,400]],"max_calls":1}]
        async with self.api(lambda _:interaction(candidate())) as (client,_):
            for value in options:
                with self.subTest(options=value):
                    response=await self.post(client,options=value)
                    self.assertEqual(response.status_code,422,response.text)
        self.assertEqual(self.requests,[])

    def tile_handler(self, request):
        _,width,height,(x,y)=image_details(request)
        source_box=(520,260,570,360)
        a,b,c,d=source_box
        return interaction(candidate(((b-y)/height*1000,(a-x)/width*1000,
                                       (d-y)/height*1000,(c-x)/width*1000)))

    async def test_overlapping_tiles_merge_same_source_door_and_keep_observation_trace(self):
        async with self.api(self.tile_handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","regions":[[100,100,996,600]],
                "tile_size":512,"overlap":128,"max_calls":2})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertEqual(len(body["detail"]["regions"]),2)
        self.assertEqual(len(body["detail"]["observations"][0]["observation_ids"]),2)
        for actual,expected in zip(body["candidates"][0]["geometry"]["minimum"],[520,260]):
            self.assertAlmostEqual(actual,expected)
        self.assertEqual(body["metrics"]["prompt_tokens"],200)
        self.assertEqual(body["metrics"]["completion_tokens"],50)

    async def test_failed_tile_preserves_success_but_marks_partial_and_unknown_total_usage(self):
        def handler(request):
            *_,origin=image_details(request)
            if origin[0]>100:
                return httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})
            return self.tile_handler(request)
        async with self.api(handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","regions":[[100,100,996,600]],
                "tile_size":512,"overlap":128,"max_calls":2})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["status"],"partial")
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertIn("failed",[r["status"] for r in body["detail"]["regions"]])
        self.assertIsNone(body["metrics"]["prompt_tokens"])
        self.assertIsNone(body["metrics"]["completion_tokens"])
        self.assertTrue(any("unresolved" in reason for reason in body["limitations"]))
        self.assertEqual(len(self.requests),2)

    def seam_handler(self, request, *, reinspection="success"):
        _,width,height,(x,y)=image_details(request)
        if width==512:
            # The first tile sees a cropped fragment; the second proposes a
            # vertically shifted whole doorway. They overlap but do not meet
            # the conservative automatic duplicate rule.
            box=(562,260,612,360) if x==100 else (550,288,650,388)
        elif reinspection=="failure":
            return httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})
        elif reinspection=="empty":
            return interaction({"status":"ok","candidates":[],"limitations":[]})
        else:
            box=(550,260,650,360)
        a,b,c,d=box
        return interaction(candidate(((b-y)/height*1000,(a-x)/width*1000,
                                       (d-y)/height*1000,(c-x)/width*1000)))

    async def test_recentered_inspection_supersedes_fragment_and_merges_full_observations(self):
        async with self.api(self.seam_handler) as (client,_):
            response=await self.post(client,options={"mode":"regions",
                "regions":[[100,100,612,600],[484,100,996,600]],"max_calls":3})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["status"],"ok",body)
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(body["detail"]["provider_calls"],3)
        self.assertEqual(len(self.requests),3)
        self.assertEqual(len(body["detail"]["regions"]),3)
        self.assertEqual(body["detail"]["superseded_observation_ids"],["detail-000/candidate-001"])
        self.assertEqual(body["detail"]["observations"][0]["observation_ids"],
                         ["detail-002/candidate-001","detail-001/candidate-001"])
        self.assertEqual(body["detail"]["reinspection_regions"],[])
        self.assertFalse(body["candidates"][0]["uncertain"])
        geometry=body["candidates"][0]["geometry"]
        for actual,expected in zip((*geometry["minimum"],*geometry["maximum"]),(550,260,650,360)):
            self.assertAlmostEqual(actual,expected)
        self.assertEqual(body["metrics"]["prompt_tokens"],300)
        self.assertEqual(body["metrics"]["completion_tokens"],75)

    async def test_empty_or_failed_reinspection_never_deletes_old_fragment(self):
        for condition in ("empty","failure"):
            with self.subTest(condition=condition):
                self.requests=[]
                async with self.api(lambda request:self.seam_handler(request,reinspection=condition)) as (client,_):
                    response=await self.post(client,options={"mode":"regions",
                        "regions":[[100,100,612,600],[484,100,996,600]],"max_calls":3})
                self.assertEqual(response.status_code,200,response.text)
                body=response.json()
                self.assertEqual(body["status"],"partial")
                self.assertEqual(len(body["candidates"]),2)
                self.assertEqual(body["detail"]["provider_calls"],3)
                self.assertEqual(len(self.requests),3)
                self.assertEqual(body["detail"]["superseded_observation_ids"],[])
                self.assertTrue(body["detail"]["reinspection_regions"])
                retained={identifier for observation in body["detail"]["observations"]
                          for identifier in observation["observation_ids"]}
                self.assertIn("detail-000/candidate-001",retained)
                self.assertIn("detail-001/candidate-001",retained)
                if condition=="failure":
                    self.assertIsNone(body["metrics"]["prompt_tokens"])
                    self.assertIsNone(body["metrics"]["completion_tokens"])
                else:
                    self.assertEqual(body["metrics"]["prompt_tokens"],300)
                    self.assertEqual(body["metrics"]["completion_tokens"],75)

    async def test_tile_ownership_defers_fragment_intact_and_preserves_review_limitation(self):
        async with self.api(self.seam_handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","regions":[[100,100,996,600]],
                "tile_size":512,"overlap":128,"max_calls":3})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["status"],"partial")
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertEqual(len(self.requests),2)
        self.assertEqual(body["detail"]["superseded_observation_ids"],[])
        deferred=body["detail"]["deferred_observations"]
        self.assertEqual(len(deferred),1)
        self.assertEqual(deferred[0]["observation_id"],"detail-000/candidate-001")
        self.assertEqual(deferred[0]["region_id"],"detail-000")
        self.assertEqual(deferred[0]["category"],"door")
        for actual,expected in zip(deferred[0]["source_box"],(562,260,612,360)):
            self.assertAlmostEqual(actual,expected)
        self.assertTrue(deferred[0]["reason"])
        self.assertTrue(any("deferred" in reason for reason in body["limitations"]))
        self.assertEqual(body["metrics"]["prompt_tokens"],200)
        self.assertEqual(body["metrics"]["completion_tokens"],50)

    async def test_request_cancellation_drains_parallel_provider_tasks_and_releases_slots(self):
        both_started=asyncio.Event()
        active=0
        async def handler(_):
            nonlocal active
            active+=1
            if active==2:
                both_started.set()
            try:
                await asyncio.Event().wait()
            finally:
                active-=1
        async with self.api(handler) as (client,app):
            task=asyncio.create_task(self.post(client,options={"mode":"tiles","regions":[[100,100,996,600]],
                "tile_size":512,"overlap":128,"max_calls":2}))
            await asyncio.wait_for(both_started.wait(),3)
            task.cancel()
            with self.assertRaises(asyncio.CancelledError):
                await task
            self.assertEqual(active,0)
            self.assertEqual(app.state.in_flight,0)
        self.assertTrue(all(not p.exists() for p in self.paths))

    async def test_uniform_unsupported_and_unreadable_regions_preserve_nonanswer_status(self):
        for status in ("unsupported", "unreadable"):
            with self.subTest(status=status):
                self.requests.clear()
                payload={"status":status,"candidates":[],"limitations":["The source cannot support this inspection."]}
                async with self.api(lambda _: interaction(payload)) as (client,_):
                    response=await self.post(client,options={"mode":"regions",
                        "regions":[[0,0,500,500],[600,0,1100,500]],"max_calls":2})
                self.assertEqual(response.status_code,200,response.text)
                body=response.json()
                self.assertEqual(body["status"],status)
                self.assertEqual(body["candidates"],[])
                self.assertTrue(body["limitations"])
                self.assertEqual(body["detail"]["provider_calls"],2)
                self.assertEqual(body["metrics"]["prompt_tokens"],200)

    async def test_mixed_nonanswer_statuses_and_failed_regions_remain_partial(self):
        for other in ("unreadable", "ok", "failure"):
            with self.subTest(other=other):
                def handler(request):
                    _,_,_,(x,_)=image_details(request)
                    if x == 0:
                        return interaction({"status":"unsupported","candidates":[],"limitations":["Unsupported source content."]})
                    if other == "failure":
                        return httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})
                    return interaction({"status":other,"candidates":[],
                        "limitations":[] if other=="ok" else ["Drawing region is unreadable."]})
                async with self.api(handler) as (client,_):
                    response=await self.post(client,options={"mode":"regions",
                        "regions":[[0,0,500,500],[600,0,1100,500]],"max_calls":2})
                self.assertEqual(response.status_code,200,response.text)
                body=response.json()
                self.assertEqual(body["status"],"partial")
                self.assertEqual(body["candidates"],[])
                self.assertTrue(body["limitations"])
                if other=="failure":
                    self.assertIsNone(body["metrics"]["prompt_tokens"])
                    self.assertIsNone(body["metrics"]["completion_tokens"])

    async def test_every_failed_region_returns_provider_error_instead_of_empty_candidates(self):
        async with self.api(lambda _:httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})) as (client,app):
            response=await self.post(client,options={"mode":"regions",
                "regions":[[0,0,500,500],[600,0,1100,500]],"max_calls":2})
            self.assertEqual(app.state.in_flight,0)
        self.assertEqual(response.status_code,503,response.text)
        self.assertEqual(response.json()["code"],"provider_unavailable")
        self.assertNotIn("candidates",response.json())


if __name__=="__main__":
    unittest.main()
