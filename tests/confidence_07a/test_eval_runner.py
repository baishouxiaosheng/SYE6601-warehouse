"""runner：06B 结果目录读取、记录转换编排；01A 引擎调用（仅在设置环境变量时运行）。"""
import json
import os
import tempfile
import unittest

from confidence_07a.eval.runner import load_results_dir, records_to_runs, run_engine_rule, run_methods
from confidence_07a.model import ClaimView, RunView


def fake_converter(graph, plan, log_record, method):
    claims = [ClaimView(n["id"], n["content"], n["evidence_status"]) for n in graph.get("nodes", []) if n.get("type") == "claim"]
    return RunView(graph["run_id"], graph["case_id"], "q", (log_record or {}).get("ai_answer", ""), claims=claims,
                   source={"adapter": "fake"})


def record(run_id, passed=True, elapsed=0.01, status="SUPPORT"):
    return {
        "case_id": run_id[:-3], "run_id": run_id, "passed": passed, "elapsed_seconds": elapsed,
        "output": {
            "graph": {"run_id": run_id, "case_id": run_id[:-3],
                      "nodes": [{"id": "CLM-001", "type": "claim", "content": "x", "evidence_status": status}]},
            "plan": {"actions": []},
            "scorecard": {"rule_version": "1.0.0", "severity_flags": []},
        },
    }


class TestResultsDir(unittest.TestCase):
    def test_latest_and_failed(self):
        with tempfile.TemporaryDirectory() as td:
            def put(name, rec):
                with open(os.path.join(td, name), "w", encoding="utf-8") as fh:
                    json.dump(rec, fh)
            put("IND-001-r1_1794824099642680500.json", record("IND-001-r1", status="UNKNOWN"))
            put("IND-001-r1_1794829480535608600.json", record("IND-001-r1", status="SUPPORT"))
            put("IND-002-r1_1794829480535608601.json", record("IND-002-r1", passed=False))
            put("notes.json", {"x": 1})
            recs = load_results_dir(td)
            self.assertEqual(sorted(k for k in recs if not k.startswith("_")), ["IND-001-r1"])
            self.assertEqual(recs["IND-001-r1"]["output"]["graph"]["nodes"][0]["evidence_status"], "SUPPORT")
            self.assertIn("IND-002-r1", recs["_failed"])
            old = load_results_dir(td, batch_prefix="17948240")
            self.assertEqual(old["IND-001-r1"]["output"]["graph"]["nodes"][0]["evidence_status"], "UNKNOWN")

            res = run_methods({"rule": td}, logs=[{"run_id": "IND-001-r1", "ai_answer": "答"}], converter=fake_converter)
            r = res["rule"]
            self.assertEqual(len(r["runs"]), 1)
            self.assertEqual(r["runs"][0].answer_text, "答")
            self.assertEqual(r["runs"][0].source["elapsed_seconds"], 0.01)
            self.assertEqual(r["runs"][0].source["method"], "rule")
            self.assertIn("IND-001-r1", r["v1_scorecards"])
            self.assertIn("IND-002-r1", r["failures"])


class TestRunMethods(unittest.TestCase):
    def test_list_and_records_sources(self):
        rv = RunView("IND-003-r1", "IND-003", "q", "a")
        recs = {"IND-004-r1": record("IND-004-r1"), "IND-005-r1": {"run_id": "IND-005-r1", "error_type": "KeyError"}}
        recs["IND-004-r1"]["variant_id"] = "V1"
        res = run_methods({"llm_only": [rv], "hybrid": {"records": recs}}, converter=fake_converter)
        self.assertIs(res["llm_only"]["runs"][0], rv)
        self.assertEqual(len(res["hybrid"]["runs"]), 1)
        self.assertEqual(res["hybrid"]["runs"][0].source["variant_id"], "V1")
        self.assertIn("IND-004-r1#V1", res["hybrid"]["v1_scorecards"])
        self.assertIn("KeyError", res["hybrid"]["failures"]["IND-005-r1"])

    def test_bad_source(self):
        with self.assertRaises(ValueError):
            run_methods({"x": 42})
        with self.assertRaises(ValueError):
            run_methods({"rule": {"engine": "nowhere"}})

    def test_engine_missing_path(self):
        with self.assertRaises(FileNotFoundError):
            run_engine_rule(os.path.join(tempfile.gettempdir(), "no_such_engine_07a"), [])


ENGINE = os.environ.get("CONFIDENCE_07A_ENGINE_PATH")
LOGS = os.environ.get("CONFIDENCE_07A_LOG_PATH")


@unittest.skipUnless(ENGINE and LOGS, "未设置 CONFIDENCE_07A_ENGINE_PATH / CONFIDENCE_07A_LOG_PATH，跳过真实引擎测试")
class TestEngineRule(unittest.TestCase):
    def test_rule_mode_runs(self):
        out = run_engine_rule(ENGINE, LOGS, run_ids=["IND-024-r1", "IND-043-r1"])
        self.assertEqual(sorted(out), ["IND-024-r1", "IND-043-r1"])
        for rec in out.values():
            self.assertFalse(rec["model_called"])
            self.assertIn("graph", rec["output"])
            self.assertIn("plan", rec["output"])
            self.assertEqual(rec["output"]["graph"]["run_id"], rec["run_id"])


if __name__ == "__main__":
    unittest.main()
