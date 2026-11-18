"""成绩单 v2 规则：措辞×状态矩阵每一格、硬门槛 B1–B5、等级、严重问题、零分母、综合分显示。"""
import itertools
import unittest

from confidence_07a.model import EXPRESSIONS, STATUSES
from confidence_07a.scorecard import load_policy, ratio, score_run

from ._sc_support import make_run

# 规范 §4.1 的默认矩阵（policy 必须与之一致；SCOPED_PARTIAL×{CONFLICT,MISSING_RULE} 规范未写，按 ×UNKNOWN 处理）
SPEC_MATRIX = {
    "DEFINITE": {"SUPPORT": (1.0, "APPROPRIATE"), "REFUTE": (0.0, "WRONG"), "UNKNOWN": (0.0, "OVERCLAIM"),
                 "CONFLICT": (0.0, "OVERCLAIM"), "MISSING_RULE": (0.0, "OVERCLAIM")},
    "HEDGED": {"SUPPORT": (0.5, "UNDERCLAIM"), "REFUTE": (0.0, "WRONG"), "UNKNOWN": (1.0, "APPROPRIATE"),
               "CONFLICT": (1.0, "APPROPRIATE"), "MISSING_RULE": (1.0, "APPROPRIATE")},
    "DECLARED_UNKNOWN": {"SUPPORT": (0.5, "UNDERCLAIM"), "REFUTE": (0.5, "UNDERCLAIM"), "UNKNOWN": (1.0, "APPROPRIATE"),
                         "CONFLICT": (1.0, "APPROPRIATE"), "MISSING_RULE": (1.0, "APPROPRIATE")},
    "SCOPED_PARTIAL": {"SUPPORT": (1.0, "APPROPRIATE"), "REFUTE": (0.0, "WRONG"), "UNKNOWN": (0.5, "OVERCLAIM"),
                       "CONFLICT": (0.5, "OVERCLAIM"), "MISSING_RULE": (0.5, "OVERCLAIM")},
}


def one(text, status, **kw):
    d = {"id": "CLM-001", "text": text, "status": status}
    d.update(kw)
    return d


class MatrixTest(unittest.TestCase):
    def test_every_cell(self):
        policy = load_policy()
        for expr, status in itertools.product(EXPRESSIONS, STATUSES):
            with self.subTest(expr=expr, status=status):
                run = make_run([one("设备读数为 10 单位", status, expression=expr)])
                row = score_run(run, policy)["claims"][0]
                score, judgement = SPEC_MATRIX[expr][status]
                self.assertEqual(row["uncertainty"]["score"], score)
                self.assertEqual(row["uncertainty"]["judgement"], judgement)
                self.assertEqual(row["uncertainty"]["cell"], f"{expr}×{status}")
                self.assertEqual(policy["expression_matrix"][expr][status]["score"], score)

    def test_declared_unknown_gap_confirmed_special_cell(self):
        reason = "图中确实存在证据缺口，该结论关于“现有证据不足”的表述本身得到支持"
        run = make_run([one("目前无法确定具体原因", "SUPPORT", verdict_reason=reason)])
        row = score_run(run)["claims"][0]
        self.assertEqual(row["expression"], "DECLARED_UNKNOWN")
        self.assertEqual(row["uncertainty"]["score"], 1.0)
        self.assertEqual(row["uncertainty"]["judgement"], "APPROPRIATE")
        run2 = make_run([one("目前无法确定具体原因", "SUPPORT", verdict_reason="现有证据条件全部满足")])
        self.assertEqual(score_run(run2)["claims"][0]["uncertainty"]["judgement"], "UNDERCLAIM")


class DimensionTest(unittest.TestCase):
    def test_unknown_gets_no_half_credit(self):
        run = make_run([
            one("工单已完成", "SUPPORT", goals=["GOAL-001"]),
            {"id": "CLM-002", "text": "油温42℃正常", "status": "UNKNOWN"},
        ])
        d = score_run(run)["dimensions"]["support"]
        self.assertEqual((d["numerator"], d["denominator"], d["value"]), (1, 2, 0.5))
        self.assertEqual(d["breakdown"]["UNKNOWN"], 1)

    def test_declared_unknown_excluded_from_support_but_counts_for_coverage(self):
        run = make_run([one("目前无法确认是否已经到货", "UNKNOWN", goals=["GOAL-001"])])
        card = score_run(run)
        sup = card["dimensions"]["support"]
        self.assertEqual(sup["denominator"], 0)
        self.assertIsNone(sup["value"])
        self.assertIn("reason", sup)
        self.assertIsNone(card["support_score"])
        self.assertEqual(card["goals"][0]["coverage_state"], "ADDRESSED_DECLARED_UNKNOWN")
        self.assertEqual(card["coverage_score"], 1.0)
        self.assertEqual(card["uncertainty_score"], 1.0)

    def test_zero_denominators_are_null_not_zero(self):
        run = make_run([], goals=[])
        card = score_run(run)
        for k in ("support", "coverage", "uncertainty"):
            d = card["dimensions"][k]
            self.assertEqual(d["denominator"], 0)
            self.assertIsNone(d["value"])
            self.assertTrue(d["reason"])
        self.assertIsNone(card["overall"])
        self.assertFalse(card["overall_display"])
        self.assertIn("Q8_NO_CLAIMS", [q["code"] for q in card["qualifications"]])
        self.assertEqual(ratio(0, 0, "x"), {"numerator": 0, "denominator": 0, "value": None, "reason": "x"})

    def test_coverage_states(self):
        run = make_run(
            [one("产量为4200件", "UNKNOWN", goals=["GOAL-001"])],
            goals=[{"id": "GOAL-001", "text": "产量是多少"}, {"id": "GOAL-002", "text": "正常吗"}],
        )
        card = score_run(run)
        states = {g["goal_id"]: g["coverage_state"] for g in card["goals"]}
        self.assertEqual(states, {"GOAL-001": "ADDRESSED_UNSUPPORTED", "GOAL-002": "NOT_ADDRESSED"})
        self.assertEqual(card["dimensions"]["coverage"]["numerator"], 1)
        self.assertIn("Q1_UNADDRESSED_GOAL", [q["code"] for q in card["qualifications"]])

    def test_lexical_fallback_is_marked(self):
        run = make_run(
            [one("可以正常作业", "SUPPORT", strength="approval")],
            goals=[{"id": "GOAL-002", "text": "可以吊吗"}],
        )
        card = score_run(run)
        self.assertEqual(card["goals"][0]["linkage_method"], "lexical_fallback")
        self.assertEqual(card["claims"][0]["linkage_method"], "lexical_fallback")
        self.assertEqual(card["build_risks"]["lexical_fallback_links"], 1)
        self.assertIn("Q4_LEXICAL_FALLBACK", [q["code"] for q in card["qualifications"]])
        self.assertEqual(card["grade"], "QUALIFIED")

    def test_checked_only_reference_value(self):
        run = make_run(
            [one("读数为 5", "SUPPORT"), {"id": "CLM-002", "text": "趋势稳定", "status": "UNKNOWN"}],
            checks=[{"id": "CHK-001", "claims": ["CLM-001"]}],
        )
        d = score_run(run)["dimensions"]["uncertainty"]
        self.assertEqual(d["value"], 0.5)
        self.assertEqual(d["breakdown"]["unchecked_default_unknown"], 1)
        self.assertEqual(d["breakdown"]["checked_only"]["value"], 1.0)


class GateTest(unittest.TestCase):
    def codes(self, card):
        return sorted({b["code"] for b in card["blockers"]})

    def test_b1_severe_contradiction(self):
        run = make_run([one("液压机系统压力为 21500 MPa", "REFUTE", strength="reading", goals=["GOAL-001"])])
        card = score_run(run)
        self.assertIn("B1", self.codes(card))
        self.assertNotIn("B3", self.codes(card))
        self.assertEqual(card["severe_issues"][0]["code"], "SEVERE_CONTRADICTION")
        self.assertTrue(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        self.assertFalse(card["overall_display"])

    def test_b1_from_gap_high_only_is_blocker_but_not_severe(self):
        run = make_run(
            [one("产量为4200件", "REFUTE", goals=["GOAL-001"])],
            gaps=[{"id": "GAP-001", "claims": ["CLM-001"], "criticality": "HIGH"}],
        )
        card = score_run(run)
        self.assertIn("B1", self.codes(card))
        self.assertFalse(card["high_risk_alert"])
        self.assertEqual(card["severe_issues"], [])
        self.assertEqual(card["grade"], "INSUFFICIENT")

    def test_b2_severe_overclaim_on_approval(self):
        run = make_run([one("可以开机", "MISSING_RULE", strength="approval")])
        card = score_run(run)
        self.assertIn("B2", self.codes(card))
        self.assertEqual(card["severe_issues"][0]["code"], "SEVERE_OVERCLAIM")
        self.assertIn("approval_type", card["severe_issues"][0]["high_risk_basis"])
        self.assertTrue(card["high_risk_alert"])

    def test_b2_needs_definite_and_main(self):
        # 高风险词但措辞带推测 → 不阻断，只是保留项
        run = make_run([one("压力可能偏高", "UNKNOWN", goals=["GOAL-001"])])
        card = score_run(run)
        self.assertEqual(self.codes(card), [])
        self.assertIn("Q2_RESIDUAL_UNCERTAINTY", [q["code"] for q in card["qualifications"]])
        # 高风险词、确定措辞但不是主结论（未关联目标、非审批类）→ 过度断言保留项
        run2 = make_run([one("冷媒压力680kPa在正常范围", "UNKNOWN", strength="reading")])
        card2 = score_run(run2)
        self.assertEqual(self.codes(card2), [])
        self.assertIn("Q6_OVERCLAIM", [q["code"] for q in card2["qualifications"]])
        self.assertEqual(card2["grade"], "QUALIFIED")

    def test_b3_definite_refute_non_high_risk(self):
        run = make_run([one("合计 156 个品规", "REFUTE", strength="reading")])
        card = score_run(run)
        self.assertEqual(self.codes(card), ["B3"])
        self.assertFalse(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")

    def test_b4_high_gap_on_definite(self):
        run = make_run(
            [one("合计 156 个品规", "UNKNOWN")],
            gaps=[{"id": "GAP-001", "claims": ["CLM-001"], "criticality": "HIGH"}],
        )
        self.assertIn("B4", self.codes(score_run(run)))
        # 同一缺口落在带限定措辞的结论上：不阻断
        run2 = make_run(
            [one("合计可能 156 个品规", "UNKNOWN")],
            gaps=[{"id": "GAP-001", "claims": ["CLM-001"], "criticality": "HIGH"}],
        )
        self.assertEqual(self.codes(score_run(run2)), [])

    def test_b5_incomplete_result(self):
        run = make_run(
            [one("合计 156 个品规", "UNKNOWN")],
            gaps=[{"id": "GAP-001", "type": "INCOMPLETE_RESULT", "claims": ["CLM-001"], "criticality": "MEDIUM"}],
        )
        self.assertIn("B5", self.codes(score_run(run)))
        run2 = make_run(
            [one("合计 156 个品规", "UNKNOWN")],
            checks=[{"id": "CHK-001", "kind": "availability", "verdict": "UNKNOWN", "claims": ["CLM-001"]}],
        )
        self.assertEqual(self.codes(score_run(run2)), ["B5"])

    def test_sufficient_in_scope(self):
        run = make_run(
            [one("工单WO-1已完成", "SUPPORT", goals=["GOAL-001"])],
            checks=[{"id": "CHK-001", "claims": ["CLM-001"], "evidence_ref": "MAT-001"}],
            answer_text="工单WO-1已完成。",
        )
        card = score_run(run)
        self.assertEqual(card["grade"], "SUFFICIENT_IN_SCOPE")
        self.assertEqual(card["qualifications"], [])
        self.assertEqual(card["overall"], 1.0)
        self.assertTrue(card["overall_display"])
        self.assertEqual(card["review_sequence"], [])
        basis = card["claims"][0]["main_basis"][0]
        self.assertEqual((basis["run_id"], basis["event_id"], basis["evidence_id"]), ("T-001-r1", "c1", "MAT-001"))

    def test_unmapped_sentence_is_qualification(self):
        run = make_run(
            [one("工单WO-1已完成", "SUPPORT", goals=["GOAL-001"])],
            checks=[{"id": "CHK-001", "claims": ["CLM-001"]}],
            answer_text="工单WO-1已完成。另外设备已经可以投产。",
        )
        card = score_run(run)
        self.assertEqual(card["build_risks"]["unmapped_sentences"]["count"], 1)
        self.assertEqual(card["grade"], "QUALIFIED")

    def test_review_sequence_order(self):
        run = make_run([
            {"id": "CLM-001", "text": "趋势稳定", "status": "UNKNOWN"},
            {"id": "CLM-002", "text": "合计 156 个品规", "status": "REFUTE"},
            {"id": "CLM-003", "text": "可以开机", "status": "MISSING_RULE", "strength": "approval"},
        ])
        card = score_run(run)
        self.assertEqual(card["review_sequence"], ["CLM-003", "CLM-002", "CLM-001"])

    def test_overall_weights_and_08b_fields(self):
        policy = load_policy()
        run = make_run(
            [one("工单WO-1已完成", "SUPPORT", goals=["GOAL-001"]), {"id": "CLM-002", "text": "趋势稳定", "status": "UNKNOWN"}],
            checks=[{"id": "CHK-001", "claims": ["CLM-001", "CLM-002"]}],
        )
        card = score_run(run, policy)
        w = policy["weights"]
        exp = (0.5 * w["support"] + 1.0 * w["coverage"] + 0.5 * w["uncertainty"]) / sum(w.values())
        self.assertAlmostEqual(card["overall"], round(exp, 4))
        for k, t in (("rule_version", str), ("support_score", float), ("coverage_score", float),
                     ("uncertainty_score", float), ("high_risk_alert", bool), ("scope_note", str),
                     ("review_sequence", list)):
            self.assertIsInstance(card[k], t, k)
        self.assertEqual(card["rule_version"], policy["version"])
        self.assertEqual(card["policy_status"], "PROVISIONAL")
        self.assertIn("不是", card["score_semantics"])


if __name__ == "__main__":
    unittest.main()
