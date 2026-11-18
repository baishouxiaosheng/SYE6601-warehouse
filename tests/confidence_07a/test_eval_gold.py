"""gold.v1 读取、校验与模板生成。"""
import copy
import json
import os
import tempfile
import unittest

from confidence_07a.eval.gold import build_gold_template, gold_runs, load_gold, validate_gold
from tests.confidence_07a._eval_fixtures import build_dataset

LOG = {
    "case_id": "IND-901", "run_id": "IND-901-r1", "user_question": "能吊装吗？",
    "visible_context": {}, "ai_answer": "可以吊装。",
    "trace": [{"id": "c1", "event": "tool_call", "tool": "x", "arguments": {}, "result": {}}],
}


class TestGold(unittest.TestCase):
    def setUp(self):
        _, golds, _ = build_dataset()
        self.doc = {"schema": "gold.v1", "gold_version": "t", "runs": golds}

    def test_valid(self):
        errors, warnings = validate_gold(self.doc)
        self.assertEqual(errors, [])
        self.assertTrue(any("DRAFT" in w for w in warnings))

    def test_enum_and_required(self):
        doc = copy.deepcopy(self.doc)
        doc["runs"][0]["claims"][0]["gold_status"] = "TRUE"
        del doc["runs"][0]["claims"][1]["severe"]
        doc["runs"][0]["source"] = "case_md"
        errors, _ = validate_gold(doc)
        joined = "\n".join(errors)
        self.assertIn("TRUE", joined)
        self.assertIn("severe", joined)
        self.assertIn("source", joined)

    def test_reference_errors(self):
        doc = copy.deepcopy(self.doc)
        doc["runs"][0]["gaps"][0]["affects_claims"] = ["nope"]
        doc["runs"][0]["claims"].append(copy.deepcopy(doc["runs"][0]["claims"][0]))
        doc["runs"].append(copy.deepcopy(doc["runs"][1]))
        errors, _ = validate_gold(doc)
        joined = "\n".join(errors)
        self.assertIn("nope", joined)
        self.assertIn("gold_claim_id 重复", joined)
        self.assertIn("运行重复", joined)

    def test_locators_checked_against_logs(self):
        doc = copy.deepcopy(self.doc)
        doc["runs"] = doc["runs"][:1]
        doc["runs"][0]["claims"][0]["evidence_locators"] = [{"event_id": "c9", "json_path": "result.x"}]
        errors, warnings = validate_gold(doc, logs={"IND-901-r1": LOG})
        self.assertTrue(any("c9" in e for e in errors))
        self.assertTrue(any("trace[" in w for w in warnings))

    def test_load_variants(self):
        runs = self.doc["runs"]
        self.assertEqual(len(gold_runs(load_gold(runs))), 2)
        self.assertEqual(len(gold_runs(load_gold({"records": runs}))), 2)
        self.assertEqual(len(gold_runs(load_gold(runs[0]))), 1)
        with tempfile.TemporaryDirectory() as td:
            p = os.path.join(td, "g.json")
            with open(p, "w", encoding="utf-8") as fh:
                json.dump(self.doc, fh, ensure_ascii=False)
            self.assertEqual(load_gold(p)["gold_version"], "t")
        with self.assertRaises(ValueError):
            load_gold({"foo": 1})

    def test_template(self):
        tpl = build_gold_template({"IND-901-r1": LOG}, annotator="me")
        errors, _ = validate_gold(tpl, logs={"IND-901-r1": LOG})
        self.assertEqual(errors, [])
        run = tpl["runs"][0]
        self.assertEqual(run["claims"], [])
        self.assertEqual(run["_answer_text"], "可以吊装。")
        self.assertEqual(run["_trace_event_ids"], ["c1"])
        self.assertEqual(run["review_status"], "DRAFT")
        self.assertEqual(build_gold_template([LOG], run_ids=["other"])["runs"], [])


if __name__ == "__main__":
    unittest.main()
