from __future__ import annotations

import asyncio
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
import unittest
from unittest.mock import patch

from gemini import AsyncGeminiClient
from gemini.client import GeminiReply
from gemini.config import GeminiSettings
from experiments.image_questions import parallel_detail as bench


class ParallelPlanningTests(unittest.TestCase):
    def test_targeted_fork_preserves_selected_case_and_input_bytes(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            prior=root/"prior"
            prior.mkdir()
            cases=[{"id":id,"question":"original question","path":f"{id}.png"} for id in ("Q001","Q002")]
            bench.write_json(prior/"cases.json",{"cases":cases})
            bench.write_json(prior/"run-complete.json",{})
            for case in cases:
                target=prior/case["id"]
                target.mkdir()
                (target/"input.png").write_bytes(case["id"].encode())
                bench.write_json(target/"source.json",{"input_sha256":bench.digest(target/"input.png")})
                (target/"SOURCE_LICENSE.md").write_text("original license")
            with patch.object(bench,"snapshot"):
                bench.fork(root,prior,root/"subset",["Q002"])
            manifest=json.loads((root/"subset/cases.json").read_text())
            self.assertEqual(manifest["cases"],[cases[1]])
            self.assertIn("targeted",manifest["selection"])
            self.assertEqual((root/"subset/Q002/input.png").read_bytes(),(prior/"Q002/input.png").read_bytes())
            self.assertFalse((root/"subset/Q001").exists())
            plan=json.loads((root/"subset/comparison-plan.json").read_text())
            self.assertEqual(plan["previous_manifest_sha256"],bench.digest(prior/"cases.json"))
            self.assertEqual(set(plan["input_sha256"]),{"Q002"})

    def test_sample_is_seeded_distinct_and_answer_blind(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"scripts").mkdir()
            (root/"scripts/question_classification_taxonomy.json").write_text("{}")
            dataset=root/"dataset"
            dataset.mkdir()
            rows=[]
            for index,(source,path) in enumerate((("cubicasa5k","one.png"),("cubicasa5k","one.png"),("swiss_dwellings","two.pdf"),("ifc_models","three.pdf")),1):
                (dataset/path).touch()
                rows.append(SimpleNamespace(line=index,source=source,path=path,question=f"How many {index}?",answer_type="count",family="Count / fixture",template="en:test",scope="selected drawing",answer="secret reference"))
            with patch.object(bench,"classify",return_value=(rows,"dataset-hash",None)),patch.object(bench,"snapshot"):
                bench.plan(root,dataset,root/"first",17,2)
                bench.plan(root,dataset,root/"second",17,2)
            first=json.loads((root/"first/cases.json").read_text())
            second=json.loads((root/"second/cases.json").read_text())
            self.assertEqual(first["cases"],second["cases"])
            self.assertEqual(len({c["path"] for c in first["cases"]}),2)
            self.assertTrue(all(c["source"]!="ifc_models" for c in first["cases"]))
            self.assertNotIn("secret reference",json.dumps(first))
            self.assertTrue(all("answer" not in c for c in first["cases"]))

    def test_peak_treats_touching_intervals_as_nonoverlap(self):
        self.assertEqual(bench._peak([(1,2),(2,3),(1.5,2.5)]),2)


class ParallelAttributionTests(unittest.IsolatedAsyncioTestCase):
    async def test_request_context_is_isolated_across_concurrent_requests(self):
        seen=[]
        async def app(scope,receive,send):
            before=bench.CASE_ID.get()
            await asyncio.sleep(.005)
            seen.append((before,bench.CASE_ID.get()))
        middleware=bench.CaseContextMiddleware(app)
        await asyncio.gather(*(middleware({"headers":[(b"x-benchmark-case",id.encode())]},None,None) for id in ("Q001","Q002")))
        self.assertEqual(set(seen),{("Q001","Q001"),("Q002","Q002")})
        self.assertIsNone(bench.CASE_ID.get())

    async def test_shared_recorder_limits_calls_and_keeps_case_identity(self):
        active=peak=0
        async def generate(client,question,*,system,image,schema):
            nonlocal active,peak
            active+=1
            peak=max(peak,active)
            await asyncio.sleep(.01)
            active-=1
            return GeminiReply("{}",client.settings.model)
        settings=GeminiSettings(api_key="test-key")
        with TemporaryDirectory() as directory:
            root=Path(directory)
            image=root/"source.png"
            image.write_bytes(b"fake png; transport mocked")
            registry={"number":0,"slots":asyncio.Semaphore(2)}
            first=bench.ParallelRecorder(root,2,settings=settings,registry=registry)
            second=bench.ParallelRecorder(root,2,settings=settings,registry=registry)
            async def one(index):
                token=bench.CASE_ID.set(f"Q{index:03d}")
                try:
                    return await (first if index%2 else second).generate_candidates("question",system="instructions",image=image,schema={"type":"object"})
                finally:
                    bench.CASE_ID.reset(token)
            try:
                with patch.object(AsyncGeminiClient,"generate_candidates",generate):
                    await asyncio.gather(*(one(i) for i in range(1,7)))
            finally:
                await first.close()
                await second.close()
            requests=[json.loads(p.read_text()) for p in sorted((root/"provider").glob("*/request.json"))]
            self.assertEqual(peak,2)
            self.assertEqual(len(requests),6)
            self.assertEqual({r["case_id"] for r in requests},{f"Q{i:03d}" for i in range(1,7)})
            self.assertTrue(all("api_key" not in r["settings"] for r in requests))

    async def test_cancelled_call_retains_terminal_audit_record(self):
        async def generate(client,*args,**kwargs):
            raise asyncio.CancelledError
        with TemporaryDirectory() as directory:
            root=Path(directory)
            image=root/"source.png"
            image.write_bytes(b"transport mocked")
            client=bench.ParallelRecorder(root,1,settings=GeminiSettings(api_key="test-key"))
            try:
                with patch.object(AsyncGeminiClient,"generate_candidates",generate):
                    with self.assertRaises(asyncio.CancelledError):
                        await client.generate_candidates("question",system="instructions",image=image,schema={"type":"object"})
            finally:
                await client.close()
            target=root/"provider/P0001"
            self.assertEqual(json.loads((target/"error.json").read_text())["code"],"cancelled")
            self.assertTrue((target/"timing.json").is_file())


class ParallelAuditTests(unittest.TestCase):
    def test_audit_rejects_changed_frozen_code(self):
        with TemporaryDirectory() as directory:
            root=Path(directory)
            (root/"code").mkdir()
            (root/"code/pipeline.py").write_text("source")
            bench.write_json(root/"cases.json",{"cases":[]})
            bench.write_json(root/"environment.json",{"provider_concurrency":12,"case_concurrency":10})
            bench.write_json(root/"source-snapshot.json",{"source_hashes":{"pipeline.py":bench.digest(root/"code/pipeline.py")}})
            self.assertTrue(bench.audit(root)["frozen_code_unchanged"])
            (root/"code/pipeline.py").write_text("changed")
            with self.assertRaisesRegex(ValueError,"Frozen code changed"):
                bench.audit(root)


if __name__=="__main__":
    unittest.main()
