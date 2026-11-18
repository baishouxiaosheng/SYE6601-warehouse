"""适配器：01A egraph v1 真实产物、06B 结果包装、02B 覆盖层。"""
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from confidence_07a.adapters import egraph_v1
from confidence_07a.adapters.b_review import load_b_review, overlay_b_review
from confidence_07a.logs import load_logs
from confidence_07a.model import STATUSES
from confidence_07a.scorecard import load_policy, score_run

from ._sc_support import ACCEPTANCE_CASES, FIXTURES, fixture_logs, fixture_run, read_json


class EgraphAdapterTest(unittest.TestCase):
    def test_statuses_copied_verbatim(self):
        for case in ACCEPTANCE_CASES:
            with self.subTest(case=case):
                graph = read_json(FIXTURES / f"{case}_graph.json")
                upstream = {n["id"]: n["evidence_status"] for n in graph["nodes"] if n["type"] == "claim"}
                run = fixture_run(case)
                got = {c.claim_id: c.status for c in run.claims if c.claim_id.startswith("CLM-")}
                self.assertEqual(got, upstream)
                self.assertTrue(all(c.status in STATUSES for c in run.claims))
                self.assertTrue(all(c.status_source == "01A" for c in run.claims))

    def test_ind043_fields(self):
        run = fixture_run("IND-043")
        self.assertEqual(run.run_id, "IND-043-r1")
        self.assertEqual(run.case_id, "IND-043")
        self.assertIn("4200", run.answer_text)
        self.assertEqual(run.upstream_versions["graph_version"], "IND-043-evidence-graph-v1")
        self.assertEqual(run.upstream_versions["plan_version"], "IND-043-supplementary-plan-v1")
        c1 = run.claim("CLM-001")
        self.assertEqual(c1.related_goals, ["GOAL-001"])
        self.assertEqual(c1.gap_ids, ["GAP-001"])
        self.assertEqual(c1.action_ids, ["ACT-001"])
        self.assertEqual(c1.check_ids, ["CHK-001"])
        self.assertEqual(run.claim("CLM-002").check_ids, [])
        # 两个 MAT 证据节点没有任何边（survey 已记录）
        self.assertEqual(run.build_risks["orphan_evidence"], ["MAT-001", "MAT-002"])
        self.assertEqual(run.build_risks["gap_missing_condition_not_node"], ["GAP-001"])
        ev = run.evidence["MAT-001"]
        self.assertEqual((ev.event_id, ev.json_path, ev.raw["pointer"]), ("c1", "trace[c1].result", "/trace/1/result"))
        rule = run.evidence["RULE-001"]
        self.assertEqual(rule.raw["pointer"], "/trace/1/result/attribution_rule")

    def test_locator_pointer_conversion(self):
        rec = {"trace": [{"id": "s1"}, {"id": "c1"}, {"id": "c2"}]}
        self.assertEqual(egraph_v1.locator_to_pointer("trace[c2].result.shifts[0].units", rec), "/trace/2/result/shifts/0/units")
        self.assertIsNone(egraph_v1.locator_to_pointer("trace[c9].result", rec))
        self.assertIsNone(egraph_v1.locator_to_pointer("trace[c1].result", None))

    def test_obligations_not_scored_without_premise(self):
        run = fixture_run("IND-024")
        ids = [c.claim_id for c in run.claims]
        self.assertFalse(any(i.startswith("OBL-") for i in ids))
        recs = [r["id"] for r in run.build_risks["recommendations_unscored"]]
        self.assertEqual(recs, ["OBL-005", "OBL-008"])

    def test_without_log_answer_is_empty_and_noted(self):
        run = fixture_run("IND-002", with_log=False)
        self.assertEqual(run.answer_text, "")
        self.assertTrue(run.notes)
        card = score_run(run)
        self.assertIsNone(card["build_risks"]["unmapped_sentences"]["count"])

    def test_run_id_mismatch_raises(self):
        graph = read_json(FIXTURES / "IND-002_graph.json")
        with self.assertRaises(ValueError):
            egraph_v1.load_run_from_artifacts(graph, None, log_record={"run_id": "IND-999-r1"})

    def test_iter_output_dir_and_06b_wrapper(self):
        tmp = Path(tempfile.mkdtemp(prefix="sc07a_"))
        try:
            out = tmp / "output"
            out.mkdir()
            for case in ("IND-043", "IND-053"):
                for k in ("graph", "plan", "scorecard"):
                    shutil.copy(FIXTURES / f"{case}_{k}.json", out / f"{case}_{k}.json")
            self.assertEqual(egraph_v1.detect_dir_kind(out), "01a_output")
            runs = list(egraph_v1.iter_output_dir(out, FIXTURES / "logs_5cases.json"))
            self.assertEqual([r.run_id for r in runs], ["IND-043-r1", "IND-053-r1"])
            self.assertTrue(all(r.answer_text for r in runs))

            res = tmp / "res"
            res.mkdir()
            payload = {
                "case_id": "IND-043", "run_id": "IND-043-r1", "execution_kind": "actual_project_rule_mode",
                "model_called": False, "elapsed_seconds": 0.01, "passed": True,
                "output": {k: read_json(FIXTURES / f"IND-043_{k}.json") for k in ("graph", "plan", "scorecard")},
            }
            older = dict(payload, elapsed_seconds=9.9)
            for name, body in (("IND-043-r1_100.json", older), ("IND-043-r1_200.json", payload)):
                with open(res / name, "w", encoding="utf-8") as fh:
                    json.dump(body, fh, ensure_ascii=False)
            self.assertEqual(egraph_v1.detect_dir_kind(res), "06b_results")
            self.assertEqual([p.name for p in egraph_v1.latest_06b_files(res)], ["IND-043-r1_200.json"])
            r06 = list(egraph_v1.iter_06b_dir(res, FIXTURES / "logs_5cases.json"))
            self.assertEqual(len(r06), 1)
            self.assertEqual(r06[0].source["method"], "rule")
            self.assertEqual(r06[0].source["elapsed_seconds"], 0.01)
            v1 = egraph_v1.load_v1_scorecard(res / "IND-043-r1_200.json")
            self.assertEqual(v1["scorecard_version"], "IND-043-scorecard-v1")
            # 06B 与 01A 输出目录得到的成绩单一致（除来源字段外）
            a = score_run(runs[0])
            b = score_run(r06[0])
            for k in ("grade", "support_score", "coverage_score", "uncertainty_score", "blockers", "claims"):
                self.assertEqual(a[k], b[k], k)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_load_logs_shapes(self):
        tmp = Path(tempfile.mkdtemp(prefix="sc07a_"))
        try:
            recs = read_json(FIXTURES / "logs_5cases.json")
            with open(tmp / "a.json", "w", encoding="utf-8") as fh:
                json.dump({"runs": recs[:2]}, fh, ensure_ascii=False)
            with open(tmp / "b.json", "w", encoding="utf-8") as fh:
                json.dump(recs[2], fh, ensure_ascii=False)
            logs = load_logs(tmp)
            self.assertEqual(sorted(logs), sorted(r["run_id"] for r in recs[:3]))
            self.assertEqual(len(load_logs(FIXTURES / "logs_5cases.json")), 5)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)


class BReviewOverlayTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()
        cls.br = load_b_review(FIXTURES / "b_review_local_5cases.json")

    def test_real_02b_matches_and_agrees(self):
        expected = {
            "IND-002-r1": ["CLM-001", "CLM-006", "CLM-007"],
            "IND-024-r1": ["CLM-001"],
            "IND-030-r1": ["CLM-001"],
            "IND-043-r1": ["CLM-001"],
            "IND-053-r1": ["CLM-005"],
        }
        for case in ACCEPTANCE_CASES:
            with self.subTest(case=case):
                run = fixture_run(case)
                over = overlay_b_review(run, self.br[run.run_id], self.policy)
                self.assertEqual(over.source["b_review"]["matched_claims"], expected[run.run_id])
                # 02B 与 01A 在这 5 条上没有状态分歧（IND-002 的 UNKNOWN+MISSING_RULE 缺口映射为 MISSING_RULE）
                self.assertEqual(over.build_risks["b_review_applied"], [])
                for cid in expected[run.run_id]:
                    self.assertEqual(over.claim(cid).status_source, "02B")
                    self.assertEqual(over.claim(cid).status, run.claim(cid).status)
                # 入参未被修改
                self.assertTrue(all(c.status_source == "01A" for c in run.claims))

    def test_fact_checks_recorded_not_applied(self):
        run = fixture_run("IND-043")
        over = overlay_b_review(run, self.br["IND-043-r1"], self.policy)
        um = over.build_risks["b_review_unmatched"]
        self.assertEqual([u["check_id"] for u in um], ["check:fact:subtotal"])
        self.assertTrue(any("check:fact:subtotal" in n for n in over.notes))

    def test_conservative_override_only_on_clear_match(self):
        run = fixture_run("IND-053")
        lr = {
            "run_id": "IND-053-r1",
            "nodes": [
                {"id": "claim:x", "type": "claim", "answer_excerpt": "今天吊装18吨设备没有问题"},
                {"id": "claim:amb", "type": "claim", "answer_excerpt": "检验"},
            ],
            "checks": [
                {"id": "check:claim:x", "target": "claim:x", "state": "REFUTE", "reason": "18>15"},
                {"id": "check:claim:amb", "target": "claim:amb", "state": "REFUTE", "reason": "模糊"},
            ],
            "gaps": [],
        }
        over = overlay_b_review(run, lr, self.policy)
        c4 = over.claim("CLM-004")
        self.assertEqual((c4.status, c4.status_source, c4.raw["status_01A"]), ("REFUTE", "02B", "SUPPORT"))
        self.assertEqual(over.build_risks["b_review_applied"], [{"claim_id": "CLM-004", "from": "SUPPORT", "to": "REFUTE"}])
        # “检验”太短/多条候选 → 不覆盖
        self.assertEqual([u["check_id"] for u in over.build_risks["b_review_unmatched"]], ["check:claim:amb"])
        self.assertEqual(over.claim("CLM-001").status_source, "01A")

    def test_run_id_mismatch_is_noop(self):
        run = fixture_run("IND-053")
        over = overlay_b_review(run, dict(self.br["IND-043-r1"]), self.policy)
        self.assertTrue(all(c.status_source == "01A" for c in over.claims))
        self.assertTrue(any("不一致" in n for n in over.notes))


if __name__ == "__main__":
    unittest.main()
