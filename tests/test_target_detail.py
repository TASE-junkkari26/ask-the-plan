"""Offline targeted-evaluation selection, source binding and scoring guards."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from experiments.image_questions.target_detail import plan, score, select_cases, run
from tests.test_detail_benchmark import synthetic_baseline, save


def prior_runs(root):
    baseline,previous=root/"baseline",root/"previous"
    cases=synthetic_baseline(baseline)
    synthetic_baseline(previous)
    cases[3]["source"]="ifc_models"
    old,new=[],[]
    for case in cases:
        number=int(case["id"][1:])
        old.append({**case,"exact_count_match":number!=2,"predicted_candidate_count":1})
        new.append({**case,"exact_count_match":number not in (1,2,4),"predicted_candidate_count":2 if number==1 else 1})
    for folder,rows in ((baseline,old),(previous,new)):
        manifest=json.loads((folder/"cases.json").read_text(encoding="utf-8"))
        manifest["cases"]=cases
        save(folder/"cases.json",manifest)
        save(folder/"evaluation.json",{"cases":rows})
    return baseline,previous,cases


class TargetDetailTests(unittest.TestCase):
    def test_default_selection_covers_failures_and_stable_controls_but_excludes_ifc(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline,previous,_=prior_runs(Path(temporary))
            cases,groups=select_cases(baseline,previous)
            self.assertEqual(groups["Q001"],"regression")
            self.assertEqual(groups["Q002"],"failure")
            self.assertEqual(groups["Q003"],"control")
            self.assertEqual(len(cases),8)
            self.assertNotIn("Q004",groups)
            self.assertTrue(all(c["source"]!="ifc_models" for c in cases))
            self.assertTrue(all("answer" not in c for c in cases))

    def test_explicit_subset_is_frozen_in_original_order_with_exact_pixels_and_no_answers(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            baseline,previous,_=prior_runs(root)
            target=root/"target"
            plan(baseline,previous,target,["Q003","Q001"])
            manifest=json.loads((target/"cases.json").read_text(encoding="utf-8"))
            self.assertEqual([c["id"] for c in manifest["cases"]],["Q001","Q003"])
            for case in manifest["cases"]:
                self.assertEqual((target/case["id"]/"input.png").read_bytes(),(previous/case["id"]/"input.png").read_bytes())
                self.assertNotIn("answer",case)
            self.assertFalse((target/"evaluation.json").exists())
            metadata=json.loads((target/"target-plan.json").read_text(encoding="utf-8"))
            self.assertEqual(metadata["provider_concurrency"],1)
            self.assertEqual(metadata["options"],{"mode":"tiles","max_calls":9})
            with self.assertRaises(FileExistsError):
                plan(baseline,previous,target,["Q001"])

    def test_invalid_unknown_ifc_and_duplicate_ids_are_rejected(self):
        with tempfile.TemporaryDirectory() as temporary:
            baseline,previous,_=prior_runs(Path(temporary))
            for ids in ([],["Q004"],["Q999"],["Q001","Q001"]):
                with self.subTest(ids=ids),self.assertRaises(ValueError):
                    select_cases(baseline,previous,ids)

    def test_score_requires_completed_outputs_before_opening_dataset(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            save(root/"cases.json",{"cases":[{"id":"Q001"}]})
            save(root/"target-plan.json",{})
            with self.assertRaisesRegex(ValueError,"Save every targeted response"):
                score(root,root/"missing-dataset")
            self.assertFalse((root/"evaluation.json").exists())

    def test_started_runs_are_not_reissued(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            save(root/"run-started.json",{})
            with self.assertRaisesRegex(ValueError,"repeat/overwrite"):
                run(root,root/"missing-dataset",8015)

    def test_scoring_keeps_nonanswers_distinct_from_zero_and_records_paired_changes(self):
        with tempfile.TemporaryDirectory() as temporary:
            root=Path(temporary)
            baseline,previous,cases=prior_runs(root)
            dataset=root/"dataset"
            dataset.mkdir()
            qa=[{"path":c["path"],"question":c["question"],"type":"count","answer":0 if c["id"]=="Q002" else 1} for c in cases]
            content="\n".join(json.dumps(r,ensure_ascii=False) for r in qa)+"\n"
            (dataset/"questions.jsonl").write_text(content,encoding="utf-8")
            for folder in (baseline,previous):
                manifest=json.loads((folder/"cases.json").read_text(encoding="utf-8"))
                manifest["dataset_questions_sha256"]=hashlib.sha256((dataset/"questions.jsonl").read_bytes()).hexdigest()
                save(folder/"cases.json",manifest)
            target=root/"target"
            plan(baseline,previous,target,["Q001","Q002","Q003"])
            for identifier,status in (("Q001","ok"),("Q002","unsupported"),("Q003","ok")):
                source=json.loads((target/identifier/"source.json").read_text(encoding="utf-8"))
                candidates=[] if status=="unsupported" else [{"id":"candidate-001","category":"door","source_label":None,
                    "geometry":{"kind":"box","minimum":[0.,0.],"maximum":[2.,2.]},"uncertain":False,
                    "uncertainty_reason":None,"visual_cue":"Synthetic fitted doorway."}]
                body={"schema_version":"0.1.0","request_id":identifier,"scope":"submitted_image",
                    "inventory_completeness":"unverified","image":{"sha256":source["input_sha256"],
                    "inference_sha256":source["input_sha256"],"width":4,"height":3},"status":status,
                    "candidates":candidates,"limitations":["Source cannot answer the question"] if not candidates else [],
                    "provenance":{"requested_model":"gemini-4-hydrogen","returned_model":"gemini-4-hydrogen","prompt_version":"synthetic"},
                    "metrics":{"elapsed_ms":1000,"prompt_tokens":10,"completion_tokens":5}}
                save(target/identifier/"api-response.json",body)
                save(target/identifier/"outcome.json",{"id":identifier,"http_status":200,"status":status,"elapsed_ms":1000,"provider_calls":1})
            save(target/"run-complete.json",{"cases":3})
            (target/"provider").mkdir()
            result=score(target,dataset)
            self.assertEqual(result["summary"]["exact_count_matches"],2)
            self.assertEqual(result["summary"]["repaired_since_previous"],1)
            self.assertEqual(result["summary"]["group_results"]["control"],{"cases":1,"matches":1})
            self.assertIsNone(result["cases"][1]["predicted_candidate_count"])
            self.assertFalse(result["cases"][1]["exact_count_match"])
            self.assertTrue((target/"REPORT.md").is_file())


if __name__=="__main__":
    unittest.main()
