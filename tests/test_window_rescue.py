"""Bounded source-frame CV/model integration; all provider responses are synthetic."""
import json
import unittest
from unittest.mock import patch

import httpx

from tests import test_image_detail as fixture
from tests.test_image_detail import image_details, interaction


def windows(boxes, width, height, origin):
    x0,y0=origin
    return {"status":"ok","limitations":[],"candidates":[{
        "category":"window","source_label":None,"uncertain":False,"uncertainty_reason":None,
        "visual_cue":"A fitted window frame.",
        "box_2d":[(b-y0)/height*1000,(a-x0)/width*1000,(d-y0)/height*1000,(c-x0)/width*1000]
    } for a,b,c,d in boxes]}


class WindowRescueTests(unittest.IsolatedAsyncioTestCase):
    api=fixture.ImageDetailTests.api
    content=None

    @classmethod
    def setUpClass(cls):
        fixture.ImageDetailTests.setUpClass()
        cls.content=fixture.ImageDetailTests.content

    def setUp(self):
        self.requests=[]
        self.paths=[]

    async def post(self,client,question="How many windows are shown?",**options):
        return await client.post("/api/v1/tools/detect-detail",
            data={"question":question,"options":json.dumps({"mode":"tiles","opencv_windows":True,
                "max_calls":3,"verify_membership":False,"reinspect_edges":False,**options})},
            files={"image":("source.png",self.content,"image/png")})

    async def test_native_crop_maps_to_source_and_records_real_call_without_escalation(self):
        def provider(request):
            body,width,height,origin=image_details(request)
            self.assertEqual(body["model"],"gemini-4-hydrogen")
            self.assertNotIn("resolution",body["input"][1])
            box=(100,100,180,200) if origin==(0,0) else (700,200,800,300)
            return interaction(windows([box],width,height,origin))
        with patch("image_api.detail.propose_window_regions",return_value=((600,100,1000,500),)) as cv:
            async with self.api(provider) as (client,_):
                response=await self.post(client)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result["detail"]["provider_calls"],2)
        self.assertEqual(len(result["candidates"]),2)
        self.assertEqual(result["candidates"][1]["geometry"],{"kind":"box","minimum":[700.,200.],"maximum":[800.,300.]})
        self.assertTrue(result["detail"]["regions"][1]["id"].startswith("cv-window-"))
        self.assertEqual(len(self.requests),2)
        self.assertEqual(len(cv.call_args.kwargs["existing_boxes"]),1)
        context=json.loads(json.loads(self.requests[1].content)["system_instruction"].split("Host crop context:\n")[1])
        self.assertEqual(context["source_crop_box"],[600,100,1000,500])
        self.assertEqual(context["target_kind"],"window")

    async def test_repeat_observation_merges_and_empty_rescue_never_deletes_original(self):
        for empty in (False,True):
            self.requests=[]
            def provider(request):
                _,width,height,origin=image_details(request)
                boxes=[] if empty and origin!=(0,0) else [(200,200,300,350)]
                return interaction(windows(boxes,width,height,origin))
            with patch("image_api.detail.propose_window_regions",return_value=((100,100,500,500),)):
                async with self.api(provider) as (client,_):
                    response=await self.post(client)
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(response.json()["candidates"]),1)
            self.assertEqual(response.json()["detail"]["provider_calls"],2)

    async def test_failed_rescue_preserves_source_candidate_and_reports_unknown_usage(self):
        def provider(request):
            _,width,height,origin=image_details(request)
            if origin!=(0,0):
                return httpx.Response(503,json={"error":{"message":"synthetic unavailable"}})
            return interaction(windows([(100,100,180,200)],width,height,origin))
        with patch("image_api.detail.propose_window_regions",return_value=((600,100,1000,500),)):
            async with self.api(provider) as (client,_):
                response=await self.post(client)
        result=response.json()
        self.assertEqual(response.status_code,200,response.text)
        self.assertEqual(len(result["candidates"]),1)
        self.assertEqual(result["status"],"partial")
        self.assertEqual(result["detail"]["provider_calls"],2)
        self.assertIsNone(result["metrics"]["prompt_tokens"])

    async def test_nonwindow_disabled_and_exhausted_budget_do_no_cv_or_extra_inference(self):
        for question,options in [("How many doors are shown?",{}),
                                 ("How many rooms labelled 'windows'?",{}),
                                 ("How many windows?",{"opencv_windows":False}),
                                 ("How many windows?",{"max_calls":1})]:
            self.requests=[]
            def provider(request):
                _,width,height,origin=image_details(request)
                return interaction(windows([(100,100,180,200)],width,height,origin))
            with patch("image_api.detail.propose_window_regions") as cv:
                async with self.api(provider) as (client,_):
                    response=await self.post(client,question,**options)
                cv.assert_not_called()
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(self.requests),1)

    async def test_only_two_extra_calls_fit_the_remaining_budget_and_ids_are_unique(self):
        def provider(request):
            _,width,height,origin=image_details(request)
            return interaction(windows([],width,height,origin))
        with patch("image_api.detail.propose_window_regions",return_value=((300,0,600,400),(700,200,1100,600))):
            async with self.api(provider) as (client,_):
                response=await self.post(client,max_calls=3)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(result["detail"]["provider_calls"],3)
        ids=[r["id"] for r in result["detail"]["regions"]]
        self.assertEqual(len(ids),len(set(ids)))

    async def test_clipped_rescue_remains_evidence_without_new_candidate_or_followup_calls(self):
        def provider(request):
            _,width,height,origin=image_details(request)
            box=(100,100,180,200) if origin==(0,0) else (600,150,620,250)
            return interaction(windows([box],width,height,origin))
        with patch("image_api.detail.propose_window_regions",return_value=((600,100,1000,500),)):
            async with self.api(provider) as (client,_):
                response=await self.post(client,max_calls=9,verify_membership=True,reinspect_edges=True)
        self.assertEqual(response.status_code,200,response.text)
        result=response.json()
        self.assertEqual(len(result["candidates"]),1)
        self.assertEqual(result["detail"]["provider_calls"],2)
        self.assertEqual(len(result["detail"]["deferred_observations"]),1)
        self.assertIn("not an established",result["detail"]["deferred_observations"][0]["reason"])

    async def test_cpu_contradiction_requires_model_rejection_and_checks_at_most_one(self):
        for verdict,remaining in (("rejected",1),("supported",2),("ambiguous",2)):
            self.requests=[]
            def provider(request):
                body,width,height,origin=image_details(request)
                if "verdict" in body["response_format"]["schema"]["properties"]:
                    return interaction({"verdict":verdict,"reason":"Visible source linework checked."})
                return interaction(windows([(100,100,180,200),(600,200,680,300)],width,height,origin))
            with patch("image_api.detail.find_solid_window_boxes",return_value=(0,1)):
                async with self.api(provider) as (client,_):
                    response=await self.post(client,opencv_windows=False,opencv_window_checks=True,
                                             verify_membership=True,reinspect_edges=True,max_calls=6)
            result=response.json()
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(result["candidates"]),remaining)
            self.assertEqual(result["detail"]["provider_calls"],2)
            self.assertEqual(len(result["detail"]["membership_checks"]),1)
            self.assertEqual(result["detail"]["membership_checks"][0]["verdict"],verdict)

    async def test_disabled_cpu_quality_or_nonwindow_task_keeps_initial_request(self):
        for question,enabled in (("How many doors?",True),("How many windows?",False)):
            self.requests=[]
            def provider(request):
                _,width,height,origin=image_details(request)
                return interaction(windows([(100,100,180,200)],width,height,origin))
            with patch("image_api.detail.find_solid_window_boxes") as check:
                async with self.api(provider) as (client,_):
                    response=await self.post(client,question,opencv_windows=False,
                        opencv_window_checks=enabled,verify_membership=True)
                check.assert_not_called()
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(len(self.requests),1)
