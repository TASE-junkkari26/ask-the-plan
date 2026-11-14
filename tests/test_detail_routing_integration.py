"""Offline route-to-detail integration; mocks do not establish drawing accuracy."""

from __future__ import annotations



import asyncio
from contextlib import asynccontextmanager
import inspect

import base64

import hashlib

from io import BytesIO

import json

from pathlib import Path

import unittest



import httpx

from PIL import Image



from contracts.models import ImageCandidateResponse

from gemini import AsyncGeminiClient, GeminiSettings

from gemini.decisions import AsyncDecisionsClient

from gemini.decisions_config import DecisionsSettings

from image_api.app import create_app

from image_api.config import ApiSettings

from nemotron import ConfigurationError

from tests.test_decision_routing import answers

from tests.test_image_api import image_bytes



KEY = "synthetic-detail-routing-key"





def reply(body, payload):

    return httpx.Response(200, json={"model":body["model"],"status":"completed",

        "steps":[{"type":"model_output","content":[{"type":"text","text":json.dumps(payload)}]}],

        "usage":{"total_input_tokens":100,"total_output_tokens":20,"total_thought_tokens":5}})





def candidate():

    return {"status":"ok","candidates":[{"category":"window","source_label":"121.A",

        "box_2d":[300,300,600,600],"uncertain":False,"uncertainty_reason":None,

        "visual_cue":"Framed opening with parallel glazing lines."}],"limitations":[]}





class DetailedRoutingIntegrationTests(unittest.IsolatedAsyncioTestCase):

    @asynccontextmanager

    async def api(self, *, fit="supported", mode="auto", handler=None, strong=True,
                  decision_handler=None, **settings):

        self.calls, self.paths = [], []

        async def decide(request):

            self.calls.append(("routing",json.loads(request.content)))

            if decision_handler is not None:
                result = decision_handler(request)
                return await result if inspect.isawaitable(result) else result

            return httpx.Response(200,json={"answers":answers(normal_fit=fit),

                "usage":{"total_input_tokens":10,"total_output_tokens":0}})

        async def analyze(request):

            body=json.loads(request.content)

            self.calls.append(("analysis",body))

            if handler is not None:

                result=handler(body)
                return await result if inspect.isawaitable(result) else result

            return reply(body,candidate())

        def sdk(profile):

            client=AsyncGeminiClient(GeminiSettings(api_key=KEY).profile(profile),

                transport=httpx.MockTransport(analyze))

            generate=client.generate_candidates

            async def track(*args,**kwargs):

                self.paths.append(Path(kwargs["image"]))

                return await generate(*args,**kwargs)

            client.generate_candidates=track

            return client

        def unavailable():

            raise ConfigurationError("Synthetic unavailable provider")

        app=create_app(ApiSettings(provider="gemini",routing_mode=mode,preprocess_mode="off",max_concurrent=12, **settings),

            client_factory=unavailable,gemini_client_factory=lambda:sdk("normal"),

            strong_client_factory=(lambda:sdk("strong")) if strong else unavailable,

            decisions_client_factory=lambda:AsyncDecisionsClient(DecisionsSettings(api_key=KEY),

                transport=httpx.MockTransport(decide)))

        async with app.router.lifespan_context(app):

            async with httpx.AsyncClient(transport=httpx.ASGITransport(app),base_url="http://test") as http:

                yield http,app

        self.assertTrue(all(not path.exists() for path in self.paths))



    async def post(self,http,*,options=None,size=(1200,800),stream=False):

        return await http.post("/api/v1/tools/detect-detail",

            data={"question":"Find windows","options":json.dumps(options or {

                "mode":"regions","regions":[[100,50,600,450]],"max_calls":1})},

            files={"image":("drawing.png",image_bytes(size),"image/png")},

            headers={"Accept":"application/x-ndjson"} if stream else {})



    async def test_strong_analyzer_receives_native_crop_and_real_source_bound_ledger(self):

        async with self.api(fit="needs_strong") as (http,app):

            response=await self.post(http)

            self.assertEqual(app.state.in_flight,0)

        self.assertEqual(response.status_code,200,response.text)

        body=response.json()

        ImageCandidateResponse.model_validate(body)

        self.assertEqual(body["decision_trace"]["selected_profile"],"strong")

        self.assertEqual(body["detail"]["provider_calls"],1)

        self.assertEqual(body["provenance"]["requested_model"],"gemini-4-carbon")

        calls=body["decision_trace"]["calls"]

        self.assertEqual(len(calls),2)

        crop_call=calls[1]

        self.assertEqual(crop_call["requested_model"],"gemini-4-carbon")

        self.assertEqual(crop_call["source_box"],[100,50,600,450])

        self.assertEqual((crop_call["input_width"],crop_call["input_height"]),(500,400))

        self.assertNotEqual(crop_call["input_sha256"],body["image"]["inference_sha256"])

        self.assertEqual([kind for kind,_ in self.calls],["routing","analysis"])

        model_input=self.calls[-1][1]

        self.assertEqual(model_input["input"][0]["text"],"Find windows")

        with Image.open(BytesIO(base64.b64decode(model_input["input"][1]["data"]))) as image:

            self.assertEqual(image.size,(500,400))



    async def test_auto_selection_keeps_cheap_layout_then_selected_frontier_detection(self):

        def handler(body):

            schema=body["response_format"]["schema"]

            if schema["properties"]["status"].get("enum")==["selected","ambiguous","unreadable"]:

                return reply(body,{"status":"selected","target_kind":"window",

                    "regions":[{"box_2d":[100,100,900,900],"reason":"Complete main drawing."}],"limitations":[]})

            return reply(body,candidate())

        async with self.api(fit="needs_strong",handler=handler) as (http,_):

            response=await self.post(http,options={"mode":"auto","max_calls":3})

        self.assertEqual(response.status_code,200,response.text)

        body=response.json()

        ImageCandidateResponse.model_validate(body)

        calls=body["decision_trace"]["calls"]

        self.assertEqual([c["purpose"] for c in calls],["routing","region_proposal","analysis"])

        self.assertEqual([c["requested_model"] for c in calls],

            ["gemini-decision-1","gemini-4-hydrogen","gemini-4-carbon"])

        self.assertEqual(body["detail"]["provider_calls"],2)

        self.assertEqual(len([kind for kind,_ in self.calls if kind=="routing"]),1)



    async def test_stream_sends_actual_model_handoff_and_detailed_result(self):

        async with self.api(fit="needs_strong") as (http,_):

            response=await self.post(http,stream=True)

        self.assertEqual(response.status_code,200,response.text)

        self.assertEqual(response.headers["content-type"].split(";")[0],"application/x-ndjson")

        frames=[json.loads(line) for line in response.text.splitlines()]

        self.assertEqual([frame["type"] for frame in frames],["handoff","result"])

        self.assertEqual(frames[0]["progress"]["requested_model"],"gemini-4-carbon")

        self.assertEqual(frames[1]["result"]["detail"]["provider_calls"],1)

        self.assertEqual(frames[0]["progress"]["image"],frames[1]["result"]["image"])



    async def test_routing_off_still_returns_actual_detail_cost_ledger_without_decisions(self):

        async with self.api(mode="off") as (http,_):

            response=await self.post(http)

        self.assertEqual(response.status_code,200,response.text)

        body=response.json()

        ImageCandidateResponse.model_validate(body)

        trace=body["decision_trace"]

        self.assertEqual((trace["mode"],trace["selected_profile"]),("off","manual"))

        self.assertEqual(len(trace["calls"]),1)

        self.assertEqual([kind for kind,_ in self.calls],["analysis"])

        self.assertEqual(trace["calls"][0]["prompt_tokens"],100)

        self.assertEqual(trace["calls"][0]["completion_tokens"],25)



    async def test_unavailable_strong_fails_before_detail_calls_and_keeps_route(self):

        async with self.api(fit="needs_strong",strong=False) as (http,app):

            response=await self.post(http)

            self.assertEqual(app.state.in_flight,0)

        self.assertEqual(response.status_code,503,response.text)

        self.assertEqual(response.json()["code"],"strong_unavailable")

        self.assertEqual(response.json()["decision_trace"]["selected_profile"],"strong")

        self.assertEqual([kind for kind,_ in self.calls],["routing"])



    async def test_failed_crop_does_not_become_a_billed_aggregate_or_silent_normal_retry(self):

        async with self.api(fit="needs_strong",handler=lambda _:httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})) as (http,_):

            response=await self.post(http)

        self.assertEqual(response.status_code,503,response.text)

        calls=response.json()["decision_trace"]["calls"]

        self.assertEqual(len(calls),2)

        self.assertEqual(calls[-1]["requested_model"],"gemini-4-carbon")

        self.assertEqual(calls[-1]["outcome"],"failed")

        self.assertIsNone(calls[-1]["prompt_tokens"])

        self.assertEqual([kind for kind,_ in self.calls],["routing","analysis"])


    async def test_multiple_tiles_share_one_route_and_use_configured_parallelism(self):
        active=0
        peak=0
        async def handler(body):
            nonlocal active,peak
            active+=1
            peak=max(peak,active)
            try:
                await asyncio.sleep(.025)
                return reply(body,candidate())
            finally:
                active-=1
        async with self.api(handler=handler) as (http,_):
            response=await self.post(http,options={"mode":"tiles","regions":[[0,0,1200,800]],
                "tile_size":600,"overlap":100,"max_calls":9,"reinspect_edges":False,"verify_membership":False})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        ImageCandidateResponse.model_validate(body)
        self.assertEqual(body["detail"]["provider_calls"],4)
        self.assertEqual(len(body["decision_trace"]["calls"]),5)
        self.assertEqual(len([kind for kind,_ in self.calls if kind=="routing"]),1)
        self.assertGreater(peak,2)
        self.assertLessEqual(peak,12)
        self.assertEqual(active,0)

    async def test_stream_disconnect_drains_detail_workers_and_releases_admission(self):
        started=asyncio.Event()
        cancelled=asyncio.Event()
        async def handler(body):
            started.set()
            try:
                await asyncio.Future()
            finally:
                cancelled.set()
        async with self.api(handler=handler) as (_,app):
            request=httpx.Request("POST","http://test/api/v1/tools/detect-detail",
                data={"question":"Find windows","options":json.dumps({"mode":"regions",
                    "regions":[[100,50,600,450]],"max_calls":1})},
                files={"image":("drawing.png",image_bytes((1200,800)),"image/png")},
                headers={"Accept":"application/x-ndjson"})
            incoming=asyncio.Queue()
            outgoing=asyncio.Queue()
            incoming.put_nowait({"type":"http.request","body":request.read(),"more_body":False})
            scope={"type":"http","asgi":{"version":"3.0","spec_version":"2.0"},
                "http_version":"1.1","method":"POST","scheme":"http",
                "path":"/api/v1/tools/detect-detail","raw_path":b"/api/v1/tools/detect-detail",
                "query_string":b"","headers":[(name.lower(),value) for name,value in request.headers.raw],
                "client":("127.0.0.1",1234),"server":("test",80)}
            task=asyncio.create_task(app(scope,incoming.get,outgoing.put))
            try:
                start=await asyncio.wait_for(outgoing.get(),3)
                self.assertEqual(start["type"],"http.response.start")
                frame=await asyncio.wait_for(outgoing.get(),3)
                self.assertEqual(json.loads(frame["body"])["type"],"handoff")
                await asyncio.wait_for(started.wait(),3)
                incoming.put_nowait({"type":"http.disconnect"})
                await asyncio.wait_for(task,3)
                self.assertTrue(cancelled.is_set())
                self.assertEqual(app.state.in_flight,0)
                self.assertTrue(all(not path.exists() for path in self.paths))
            finally:
                task.cancel()
                await asyncio.gather(task,return_exceptions=True)

    async def test_detail_handoff_and_crop_ledger_follow_hydrogen_first_gate(self):
        for fit, probability, expected in (
            ("uncertain", .99, "gemini-4-hydrogen"),
            ("needs_strong", .799, "gemini-4-hydrogen"),
            ("needs_strong", .8, "gemini-4-carbon"),
        ):
            with self.subTest(fit=fit, probability=probability):
                def decide(_):
                    values = answers(normal_fit=fit)
                    values["normal_fit"]["probabilities"] = {
                        "supported": 1 - probability, "needs_strong": probability if fit == "needs_strong" else 0,
                        "uncertain": probability if fit == "uncertain" else 0,
                    }
                    values["normal_fit"]["confidence"] = probability
                    return httpx.Response(200, json={"answers": values})

                async with self.api(decision_handler=decide) as (http, _):
                    response = await self.post(http, stream=True)
                self.assertEqual(response.status_code, 200, response.text)
                frames = [json.loads(line) for line in response.text.splitlines()]
                self.assertEqual([frame["type"] for frame in frames], ["handoff", "result"])
                body = frames[-1]["result"]
                ImageCandidateResponse.model_validate(body)
                self.assertEqual(frames[0]["progress"]["requested_model"], expected)
                self.assertEqual(body["provenance"]["requested_model"], expected)
                self.assertEqual(body["decision_trace"]["policy_version"], "capability-routing-v4")
                calls = body["decision_trace"]["calls"]
                self.assertEqual([call["purpose"] for call in calls], ["routing", "analysis"])
                self.assertEqual(calls[-1]["requested_model"], expected)
                self.assertEqual(calls[-1]["source_box"], [100, 50, 600, 450])
                crop = base64.b64decode(self.calls[-1][1]["input"][1]["data"])
                self.assertEqual(calls[-1]["input_sha256"], hashlib.sha256(crop).hexdigest())
                self.assertEqual([kind for kind, _ in self.calls], ["routing", "analysis"])

    async def test_detail_routing_failure_and_timeout_use_one_hydrogen_attempt(self):
        for failure in ("timeout", "provider_error"):
            with self.subTest(failure=failure):
                cancelled = asyncio.Event()

                async def decide(_):
                    if failure == "provider_error":
                        return httpx.Response(503, json={"error": {"message": KEY}})
                    try:
                        await asyncio.Future()
                    finally:
                        cancelled.set()

                async with self.api(decision_handler=decide, routing_timeout_seconds=.02) as (http, _):
                    response = await self.post(http, stream=True)
                self.assertEqual(response.status_code, 200, response.text)
                frames = [json.loads(line) for line in response.text.splitlines()]
                self.assertEqual([frame["type"] for frame in frames], ["handoff", "result"])
                body = frames[-1]["result"]
                ImageCandidateResponse.model_validate(body)
                trace = body["decision_trace"]
                self.assertEqual(trace["selected_profile"], "normal")
                self.assertEqual(trace["assessments"], {})
                self.assertEqual(trace["nodes"][0]["state"], "failed")
                self.assertEqual(trace["nodes"][1]["reason_code"], "routing_fallback_normal")
                self.assertEqual(frames[0]["progress"]["requested_model"], "gemini-4-hydrogen")
                self.assertEqual(trace["calls"][-1]["source_box"], [100, 50, 600, 450])
                self.assertEqual(trace["calls"][-1]["requested_model"], "gemini-4-hydrogen")
                self.assertEqual([kind for kind, _ in self.calls], ["routing", "analysis"])
                self.assertNotIn(KEY, response.text)
                if failure == "timeout":
                    self.assertTrue(cancelled.is_set())

    async def test_detail_preparation_mode_has_its_own_cached_decision(self):
        async with self.api() as (http, _):
            first = await self.post(http)
            cached = await self.post(http)
            tiled = await self.post(http, options={"mode": "tiles", "regions": [[100, 50, 600, 450]],
                "max_calls": 1, "reinspect_edges": False, "verify_membership": False})
        for response in (first, cached, tiled):
            self.assertEqual(response.status_code, 200, response.text)
        self.assertEqual(cached.json()["decision_trace"]["nodes"][0]["state"], "reused")
        self.assertEqual(tiled.json()["decision_trace"]["nodes"][0]["state"], "evaluated")
        decisions = [body for kind, body in self.calls if kind == "routing"]
        self.assertEqual(len(decisions), 2)
        self.assertIn("Requested preparation: regions", decisions[0]["input"][0]["text"])
        self.assertIn("Requested preparation: tiles", decisions[1]["input"][0]["text"])
        self.assertEqual([kind for kind, _ in self.calls], ["routing", "analysis", "analysis", "routing", "analysis"])
