"""experiment_metrics.json 结构与 schema 一致性；report.md / csv 产出。"""
import copy
import csv
import json
import os
import tempfile
import unittest

from confidence_07a.eval.metrics import evaluate
from confidence_07a.eval.report import build_experiment_metrics, validate_experiment_metrics, write_report
from confidence_07a.eval.schema_check import load_schema, validate
from confidence_07a.model import ClaimView, RunView
from tests.confidence_07a._eval_fixtures import build_dataset, gold_claim, gold_run

FAST = {"bootstrap": {"n_resamples": 100}}


class TestReport(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runs, golds, scs = build_dataset()
        ev_rule = evaluate(runs, golds, "rule", scorecards=scs, config=FAST)
        # 第二个方法：只有一个运行的结论，全部 SUPPORT -> 无 REFUTE 已对齐 => false_support 为 null
        g = gold_run("IND-901-r1", [gold_claim("g1", "设备载荷为18吨", "SUPPORT", pred="P3")])
        r = RunView("IND-901-r1", "IND-901", "q", "a", claims=[ClaimView("P3", "设备载荷为18吨", "SUPPORT")])
        ev_null = evaluate([r], [g], "llm_only", config=FAST)
        cls.evals = [ev_rule, ev_null]

    def test_schema_conformance(self):
        doc = build_experiment_metrics(self.evals, data_version="logs60", gold_version="pilot_v0")
        self.assertEqual(validate_experiment_metrics(doc), [])
        row = doc["rows"][0]
        self.assertEqual(row["method"], "rule")
        self.assertAlmostEqual(row["false_support"], 0.5)
        self.assertAlmostEqual(row["gap_locate"], 2 / 3, places=5)
        self.assertAlmostEqual(row["insufficient_as_err"], 0.5)
        self.assertIsInstance(row["note"], str)
        self.assertIsNone(doc["rows"][1]["false_support"])
        self.assertIsNone(doc["rows"][1]["insufficient_as_err"])

    def test_schema_rejects_bad(self):
        doc = build_experiment_metrics(self.evals)
        bad = copy.deepcopy(doc)
        bad["rows"][0]["false_support"] = 1.5
        del bad["rows"][1]["note"]
        bad["rows"][0]["metrics"]["gap_f1"]["ci95"] = [0.1]
        errs = validate_experiment_metrics(bad)
        self.assertTrue(any("maximum" in e for e in errs))
        self.assertTrue(any("note" in e for e in errs))
        self.assertTrue(any("gap_f1" in e for e in errs))
        bad2 = copy.deepcopy(doc)
        bad2["schema"] = "v0"
        self.assertTrue(validate_experiment_metrics(bad2))

    def test_gold_schema_is_valid_json_and_loads(self):
        s = load_schema("gold.v1.schema.json")
        self.assertIn("run", s["definitions"])
        self.assertTrue(validate({"runs": [{}]}, s))  # 空运行应报缺字段

    def test_write_files(self):
        with tempfile.TemporaryDirectory() as td:
            paths = write_report(self.evals, td, data_version="logs60", gold_version="pilot_v0",
                                 extra_notes=["测试附注"])
            for k in ("experiment_metrics", "report", "per_claim", "per_run"):
                self.assertTrue(os.path.isfile(paths[k]), k)
            with open(paths["experiment_metrics"], "r", encoding="utf-8") as fh:
                doc = json.load(fh)
            self.assertEqual(validate_experiment_metrics(doc), [])
            self.assertIsNone(doc["rows"][1]["false_support"])
            with open(paths["report"], "r", encoding="utf-8") as fh:
                md = fh.read()
            for needle in ("AI 起草", "不是正确概率", "样本量", "混淆矩阵", "测试附注", "IND-901-r1"):
                self.assertIn(needle, md)
            with open(paths["per_claim"], "r", encoding="utf-8", newline="") as fh:
                rows = list(csv.DictReader(fh))
            self.assertEqual(len(rows), 8 + 1)
            self.assertIn("gold_status", rows[0])
            with open(paths["per_run"], "r", encoding="utf-8", newline="") as fh:
                prow = list(csv.DictReader(fh))
            self.assertEqual(len(prow), 3)


if __name__ == "__main__":
    unittest.main()
