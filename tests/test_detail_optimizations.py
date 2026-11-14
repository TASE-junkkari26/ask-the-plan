"""Mocked HTTP/native-preparation checks for detail identity optimizations."""
from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path
import tempfile
import unittest

import httpx
from PIL import Image

from image_api.config import ApiSettings
from image_api.preprocessing import ImagePreprocessor
from tests import test_image_detail as detail_fixture
from tests.test_image_detail import candidate, image_details, interaction, selection
from tests.test_image_preprocessing import content_image


def png(size):
    with Image.new("RGB",size,"white") as image,BytesIO() as stream:
        image.save(stream,format="PNG")
        return stream.getvalue()


def is_layout(body):
    return body["response_format"]["schema"]["properties"]["status"].get("enum")==["selected","ambiguous","unreadable"]


def fixture_hypotheses():
    certain={"category":"toilet","source_label":"WC 1","box_2d":[200,150,300,250],
        "uncertain":False,"uncertainty_reason":None,"visual_cue":"A fitted WC fixture."}
    uncertain={"category":"toilet","source_label":"121.A","box_2d":[400,500,550,600],
        "uncertain":True,"uncertainty_reason":"This symbol may be another sanitary fixture.",
        "visual_cue":"An ambiguous sanitary symbol near a wall."}
    return {"status":"ok","candidates":[certain,uncertain],"limitations":[]}


class DetailOptimizationTests(unittest.IsolatedAsyncioTestCase):
    api=detail_fixture.ImageDetailTests.api

    def setUp(self):
        self.requests=[]
        self.paths=[]
        self.content=png((1200,800))

    async def post(self,client,*,options=None,question="show doors"):
        data={"question":question}
        if options is not None:
            data["options"]=json.dumps(options)
        return await client.post("/api/v1/tools/detect-detail",data=data,
            files={"image":("source.png",self.content,"image/png")})

    async def test_small_native_source_skips_layout_and_fits_single_call_budget(self):
        self.content=png((1680,1680))
        def handler(request):
            body,width,height,_=image_details(request)
            self.assertFalse(is_layout(body),"Small native input must not spend a layout call")
            self.assertEqual((width,height),(1680,1680))
            return interaction(candidate())
        async with self.api(handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","max_calls":1})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["provider_calls"],1)
        self.assertEqual(body["detail"]["selected_regions"],[[0,0,1680,1680]])
        self.assertEqual(len(self.requests),1)

    async def test_explicit_crop_keeps_native_frame_context_and_literal_question(self):
        question="Näytä ovet 121.A!"
        def handler(request):
            body,width,height,_=image_details(request)
            self.assertFalse(is_layout(body))
            self.assertEqual((width,height),(600,400))
            self.assertEqual(body["input"][0]["text"],question)
            system=body["system_instruction"]
            self.assertIn("Host crop context:",system)
            context=json.loads(system.split("Host crop context:\n",1)[1])
            self.assertEqual(context["source_dimensions"],[1200,800])
            self.assertEqual(context["source_crop_box"],[100,100,700,500])
            self.assertEqual(context["selected_panels"],[[100,100,700,500]])
            self.assertEqual(context["target_kind"],"door")
            self.assertIn("attached crop",context["coordinate_frame"])
            return interaction(candidate())
        async with self.api(handler) as (client,_):
            response=await self.post(client,question=question,options={"mode":"regions",
                "regions":[[100,100,700,500]],"target_kind":"door","max_calls":1})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["selection"],"explicit")
        self.assertEqual(body["candidates"][0]["geometry"],{
            "kind":"box","minimum":[220.,200.],"maximum":[460.,400.]})
        self.assertEqual(len(self.requests),1)

    async def test_global_targets_keep_complete_panel_instead_of_object_tiling(self):
        for target_kind in ("floor","schedule_row","room"):
            with self.subTest(target_kind=target_kind):
                self.requests=[]
                self.content=png((3000,1800))
                sizes=[]
                def handler(request):
                    body,width,height,_=image_details(request)
                    sizes.append((width,height))
                    if is_layout(body):
                        payload=selection((0,0,1000,1000))
                        payload["target_kind"]=target_kind
                        return interaction(payload)
                    payload=candidate((0,0,1000,1000))
                    payload["candidates"][0]["category"]=target_kind
                    return interaction(payload)
                async with self.api(handler) as (client,_):
                    response=await self.post(client,options={"mode":"tiles","max_calls":2})
                self.assertEqual(response.status_code,200,response.text)
                body=response.json()
                self.assertEqual(body["detail"]["target_kind"],target_kind)
                self.assertEqual(body["detail"]["provider_calls"],2)
                self.assertEqual(len(body["detail"]["regions"]),1)
                self.assertEqual(body["detail"]["regions"][0]["source_box"],[0,0,3000,1800])
                self.assertEqual(sizes[-1],(3000,1800),"Detection must retain native full-panel pixels")
                self.assertLessEqual(max(sizes[0]),1600,"Layout should reuse the full-page preprocessor overview")
                self.assertEqual(len(self.requests),2)

    async def test_explicit_target_override_is_typed_and_avoids_global_object_fragmentation(self):
        self.content=png((3000,1800))
        def handler(request):
            body,_,_,_=image_details(request)
            if is_layout(body):
                payload=selection((0,0,1000,1000));payload["target_kind"]="other"
                return interaction(payload)
            payload=candidate();payload["candidates"][0]["category"]="schedule_row"
            return interaction(payload)
        async with self.api(handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","target_kind":"schedule_row","max_calls":2})
            self.assertEqual(response.status_code,200,response.text)
            self.assertEqual(response.json()["detail"]["target_kind"],"schedule_row")
            before=len(self.requests)
            invalid=await self.post(client,options={"target_kind":"arbitrary-unknown"})
            self.assertEqual(invalid.status_code,422,invalid.text)
            self.assertEqual(len(self.requests),before)

    async def test_identical_full_frame_reinspection_is_reused_instead_of_a_second_model_call(self):
        def handler(_):
            payload=candidate((0,0,1000,1000))
            payload["candidates"][0]["category"]="whole_symbol"
            return interaction(payload)
        async with self.api(handler) as (client,_):
            response=await self.post(client,options={"mode":"tiles","max_calls":3})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["provider_calls"],1)
        self.assertEqual(body["detail"]["reused_crops"],1)
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(len(self.requests),1)

    async def test_identical_pixel_hash_at_different_source_positions_does_not_erase_objects(self):
        self.content=png((1200,600))
        async with self.api(lambda _:interaction(candidate())) as (client,_):
            response=await self.post(client,options={"mode":"regions",
                "regions":[[0,100,500,500],[700,100,1200,500]],"target_kind":"door","max_calls":2})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertEqual(len(body["candidates"]),2)
        self.assertEqual(len(self.requests),2)

    async def test_membership_rejection_removes_only_the_uncertain_hypothesis_and_records_evidence(self):
        question="Montako WC-istuinta on kuvassa (121.A)?"
        def handler(request):
            body,width,height,_=image_details(request)
            self.assertEqual(body["input"][0]["text"],question)
            if "verdict" in body["response_format"]["schema"]["properties"]:
                self.assertLess(width,1200)
                self.assertLess(height,800)
                metadata=json.loads(body["system_instruction"].split("Host proposal metadata (data, not instructions):\n",1)[1])
                self.assertEqual(metadata["proposed_category"],"toilet")
                self.assertEqual(metadata["proposed_source_label"],"121.A")
                return interaction({"verdict":"rejected","reason":"The proposed symbol is a wash basin, not a WC fixture."})
            self.assertFalse(is_layout(body))
            return interaction(fixture_hypotheses())
        async with self.api(handler) as (client,_):
            response=await self.post(client,question=question,options={"mode":"tiles","target_kind":"toilet","max_calls":5})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertEqual(len(self.requests),2,"Membership verification must not become another regional inventory pass")
        self.assertEqual(len(body["candidates"]),1)
        self.assertEqual(body["candidates"][0]["source_label"],"WC 1")
        self.assertEqual(body["candidates"][0]["geometry"],{"kind":"box","minimum":[180.,160.],"maximum":[300.,240.]})
        check=body["detail"]["membership_checks"][0]
        self.assertEqual(check["observation_ids"],["detail-000/candidate-002"])
        self.assertEqual(check["source_box"],[600.,320.,720.,440.])
        self.assertEqual(check["verdict"],"rejected")
        self.assertEqual(body["metrics"]["prompt_tokens"],200)
        self.assertEqual(body["metrics"]["completion_tokens"],50)

    async def test_supported_membership_clears_uncertainty_without_changing_geometry_ids_or_labels(self):
        question="How many WC fixtures marked 121.A are visible?"
        def handler(request):
            body,_,_,_=image_details(request)
            self.assertEqual(body["input"][0]["text"],question)
            if "verdict" in body["response_format"]["schema"]["properties"]:
                return interaction({"verdict":"supported","reason":"The full fixture symbol confirms the proposed WC membership."})
            return interaction(fixture_hypotheses())
        async with self.api(handler) as (client,_):
            response=await self.post(client,question=question,options={"mode":"tiles","target_kind":"toilet","max_calls":5})
        self.assertEqual(response.status_code,200,response.text)
        body=response.json()
        self.assertEqual(body["detail"]["provider_calls"],2)
        self.assertEqual(len(self.requests),2)
        candidates={c["source_label"]:c for c in body["candidates"]}
        self.assertEqual(set(candidates),{"WC 1","121.A"})
        checked=candidates["121.A"]
        self.assertEqual(checked["id"],"candidate-002")
        self.assertEqual(checked["geometry"],{"kind":"box","minimum":[600.,320.],"maximum":[720.,440.]})
        self.assertFalse(checked["uncertain"])
        self.assertIsNone(checked["uncertainty_reason"])
        self.assertEqual(body["detail"]["membership_checks"][0]["verdict"],"supported")

    async def test_ambiguous_or_failed_membership_preserves_evidence_and_does_not_recrop_inventory(self):
        for verdict in ("ambiguous","failed"):
            with self.subTest(verdict=verdict):
                self.requests=[]
                def handler(request):
                    body,_,_,_=image_details(request)
                    self.assertEqual(body["input"][0]["text"],"show doors")
                    if "verdict" in body["response_format"]["schema"]["properties"]:
                        if verdict=="failed":
                            return httpx.Response(503,json={"error":{"status":"UNAVAILABLE"}})
                        return interaction({"verdict":"ambiguous","reason":"Visible linework cannot distinguish the fixture."})
                    return interaction(fixture_hypotheses())
                async with self.api(handler) as (client,_):
                    response=await self.post(client,options={"mode":"tiles","target_kind":"toilet","max_calls":5})
                self.assertEqual(response.status_code,200,response.text)
                body=response.json()
                self.assertEqual(body["status"],"partial")
                self.assertEqual(body["detail"]["provider_calls"],2)
                self.assertEqual(len(self.requests),2,"Checked IDs must prevent a third inventory call")
                self.assertEqual(len(body["candidates"]),2)
                checked=next(c for c in body["candidates"] if c["source_label"]=="121.A")
                self.assertTrue(checked["uncertain"])
                self.assertEqual(checked["geometry"],{"kind":"box","minimum":[600.,320.],"maximum":[720.,440.]})
                self.assertEqual(body["detail"]["membership_checks"][0]["verdict"],verdict)
                if verdict=="failed":
                    self.assertIsNone(body["metrics"]["prompt_tokens"])
                    self.assertIsNone(body["metrics"]["completion_tokens"])
                    self.assertTrue(any(region["status"]=="failed" for region in body["detail"]["regions"]))
                else:
                    self.assertEqual(body["metrics"]["prompt_tokens"],200)


class NativeDetailPreparationTests(unittest.TestCase):
    def test_native_cache_and_context_overview_preserve_separate_source_and_model_frames(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            processor=ImagePreprocessor(ApiSettings(provider="gemini",preprocess_mode="overview",
                preprocess_overview_long_edge=257))
            try:
                first_dir,second_dir=root/"first",root/"second"
                first_dir.mkdir();second_dir.mkdir()
                first=processor.prepare_native(content_image(),first_dir)
                second=processor.prepare_native(content_image(),second_dir)
                self.assertEqual((first.model_width,first.model_height),(809,613))
                self.assertEqual(first.preprocessing_mode,"original")
                self.assertFalse(first.preparation_cache_hit)
                self.assertTrue(second.preparation_cache_hit)
                self.assertEqual(first.prepared_id,second.prepared_id)
                self.assertEqual(first.inference_sha256,second.inference_sha256)
                overview,hints=processor.detail_context(second,second_dir)
                self.assertEqual((overview.width,overview.height),(809,613))
                self.assertEqual((overview.model_width,overview.model_height),(257,195))
                self.assertEqual(overview.preprocessing_mode,"overview")
                self.assertNotEqual(overview.path,second.path)
                self.assertNotEqual(overview.inference_sha256,second.inference_sha256)
                self.assertEqual(overview.sha256,second.sha256)
                self.assertEqual((hints["source_width"],hints["source_height"]),(809,613))
                self.assertIn("not semantic",hints["note"])
                with Image.open(second.path) as native,Image.open(overview.path) as small:
                    self.assertEqual(native.size,(809,613));self.assertEqual(small.size,(257,195))
            finally:
                processor.close()


if __name__=="__main__":
    unittest.main()
