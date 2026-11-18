"""evaluate() 指标公式：手算小数据集逐项核对。"""
import copy
import unittest

from confidence_07a.eval.metrics import (
    alert_of,
    bootstrap_ci,
    evaluate,
    match_gaps,
    param_hit,
    support_score_of,
    values_equal,
)
from confidence_07a.eval.config import load_eval_config
from confidence_07a.model import ActionView, ClaimView, GapView, RunView
from tests.confidence_07a._eval_fixtures import build_dataset, gold_claim, gold_run

FAST = {"bootstrap": {"n_resamples": 200}}


class TestHandComputed(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        runs, golds, scs = build_dataset()
        cls.ev = evaluate(runs, golds, "rule", scorecards=scs, seed=0, config=FAST)
        cls.m = cls.ev["metrics"]

    def nd(self, name):
        r = self.m[name]
        return r["numerator"], r["denominator"]

    def test_false_support(self):
        self.assertEqual(self.nd("false_support_strict"), (1, 2))
        self.assertAlmostEqual(self.m["false_support_strict"]["value"], 0.5)
        self.assertEqual(self.nd("false_support_broad"), (1, 4))
        self.assertEqual(self.m["false_support_broad"]["excluded_unaligned"], 1)
        self.assertEqual(self.m["false_support_strict"]["excluded_unaligned"], 0)

    def test_iae(self):
        self.assertEqual(self.nd("insufficient_as_err"), (1, 2))
        self.assertEqual(self.m["insufficient_as_err"]["excluded_unaligned"], 1)

    def test_confusion_accuracy_f1_kappa(self):
        labels = self.ev["confusion"]["labels"]
        mat = self.ev["confusion"]["matrix"]
        cell = lambda g, p: mat[labels.index(g)][labels.index(p)]
        self.assertEqual(cell("REFUTE", "SUPPORT"), 1)
        self.assertEqual(cell("UNKNOWN", "REFUTE"), 1)
        self.assertEqual(cell("SUPPORT", "UNKNOWN"), 1)
        self.assertEqual(sum(map(sum, mat)), 6)
        self.assertEqual(self.nd("status_accuracy"), (3, 6))
        self.assertAlmostEqual(self.m["status_macro_f1"]["value"], 0.5)
        self.assertEqual(self.m["status_macro_f1"]["denominator"], 3)
        self.assertAlmostEqual(self.m["status_kappa"]["value"], 0.25, places=6)

    def test_extraction(self):
        self.assertEqual(self.nd("extraction_coverage"), (6, 7))
        self.assertEqual(self.nd("extraction_extra_rate"), (1, 7))

    def test_gaps(self):
        self.assertEqual(self.nd("gap_precision"), (2, 3))
        self.assertEqual(self.nd("gap_recall"), (2, 3))
        self.assertEqual(self.nd("gap_f1"), (4, 6))
        self.assertAlmostEqual(self.m["gap_f1"]["value"], 2 / 3, places=5)

    def test_requery_params(self):
        self.assertEqual(self.nd("requery_param_value_hit"), (3, 7))
        self.assertEqual(self.nd("requery_param_key_hit"), (4, 7))
        self.assertEqual(self.nd("requery_action_exists"), (1, 2))

    def test_run_level(self):
        self.assertEqual(self.nd("severe_recall"), (1, 1))
        self.assertEqual(self.nd("severe_false_alarm"), (1, 1))
        tab = self.ev["run_level"]["grade_vs_answer_has_error"]
        self.assertEqual(tab["INSUFFICIENT"]["true"], 1)
        self.assertEqual(tab["QUALIFIED"]["false"], 1)

    def test_calibration(self):
        self.assertAlmostEqual(self.m["calibration_ece"]["numerator"], 2.5)
        self.assertEqual(self.m["calibration_ece"]["denominator"], 6)
        self.assertAlmostEqual(self.m["calibration_ece"]["value"], 2.5 / 6, places=5)
        table = self.ev["calibration"]["table"]
        self.assertEqual(table[2]["n_claims"], 3)
        self.assertAlmostEqual(table[2]["gold_support_rate"], 1 / 3, places=5)
        self.assertEqual(table[4]["n_claims"], 3)
        self.assertIsNone(table[0]["mean_support_score"])

    def test_cost_and_counts(self):
        self.assertEqual(self.ev["cost"]["elapsed_seconds"]["n"], 2)
        self.assertAlmostEqual(self.ev["cost"]["elapsed_seconds"]["total"], 0.04)
        self.assertIsNone(self.ev["cost"]["model_calls"]["total"])
        self.assertEqual(self.ev["n"]["gold_runs_draft"], 2)
        self.assertEqual(self.ev["strata"], {})
        self.assertIsNotNone(self.ev["strata_note"])

    def test_ci_present_and_ordered(self):
        for name, r in self.m.items():
            if r["value"] is None:
                self.assertIsNone(r["ci95"], name)
            else:
                lo, hi = r["ci95"]
                self.assertLessEqual(lo, hi, name)

    def test_per_claim_rows(self):
        rows = self.ev["per_claim"]
        self.assertEqual(len(rows), 8)  # 7 gold + 1 extra
        fs = [r for r in rows if r["false_support"]]
        self.assertEqual([(r["run_id"], r["gold_claim_id"]) for r in fs], [("IND-901-r1", "g1")])


class TestNullAndEdge(unittest.TestCase):
    def test_zero_denominators_are_null(self):
        g = gold_run("IND-903-r1", [gold_claim("g1", "白班1800件", "SUPPORT", pred="X1")])
        r = RunView("IND-903-r1", "IND-903", "q", "a", claims=[ClaimView("X1", "白班1800件", "SUPPORT")])
        ev = evaluate([r], [g], "rule", seed=0, config=FAST)
        m = ev["metrics"]
        for name in ("false_support_strict", "false_support_broad", "insufficient_as_err",
                     "gap_precision", "gap_recall", "gap_f1", "requery_param_value_hit",
                     "requery_action_exists", "severe_recall", "calibration_ece"):
            self.assertIsNone(m[name]["value"], name)
            self.assertTrue(m[name]["reason"], name)
            self.assertIsNone(m[name]["ci95"], name)
        self.assertIn("scorecards=None", m["severe_recall"]["reason"])
        # 单一类别 -> p_e = 1 -> κ 为 null
        self.assertIsNone(m["status_kappa"]["value"])
        self.assertEqual(m["status_accuracy"]["value"], 1.0)

    def test_missing_prediction_run(self):
        runs, golds, _ = build_dataset()
        ev = evaluate(runs[:1], golds, "rule", config=FAST)
        self.assertEqual(ev["n"]["pred_runs_missing"], 1)
        self.assertEqual(ev["metrics"]["extraction_coverage"]["numerator"], 3)
        self.assertEqual(ev["metrics"]["extraction_coverage"]["denominator"], 7)
        self.assertTrue(any("没有此运行的预测" in w for w in ev["warnings"]))

    def test_invalid_pred_status_excluded(self):
        g = gold_run("IND-904-r1", [gold_claim("g1", "x设备运行正常", "REFUTE", pred="Z")])
        r = RunView("IND-904-r1", "IND-904", "q", "a", claims=[ClaimView("Z", "x设备运行正常", "WEIRD")])
        ev = evaluate([r], [g], "rule", config=FAST)
        self.assertIsNone(ev["metrics"]["false_support_strict"]["value"])
        self.assertEqual(ev["metrics"]["false_support_strict"]["excluded_unaligned"], 1)

    def test_variant_strata(self):
        runs, golds, _ = build_dataset()
        vrun = copy.deepcopy(runs[1])
        vrun.source = {"variant_id": "V-unit-1", "variant_kind": "unit_change"}
        vgold = copy.deepcopy(golds[1])
        vgold["variant_id"] = "V-unit-1"
        ev = evaluate(runs + [vrun], golds + [vgold], "rule", config=FAST)
        self.assertEqual(set(ev["strata"]), {"natural", "variant", "variant:unit_change"})
        self.assertEqual(ev["strata"]["natural"]["n_runs"], 2)
        self.assertEqual(ev["strata"]["variant"]["n_runs"], 1)
        self.assertEqual(ev["strata"]["variant"]["metrics"]["false_support_strict"]["denominator"], 1)

    def test_v1_scorecard_fallback(self):
        v1 = {"severity_flags": [{"severity": "HIGH"}], "dimensions": {"evidence_support": {"score": 0.4}}}
        self.assertEqual(alert_of(v1), (True, "v1_severity_flags_high"))
        self.assertEqual(support_score_of(v1), (0.4, "v1.dimensions.evidence_support.score"))
        self.assertEqual(alert_of(None)[0], None)
        self.assertEqual(alert_of({"severity_flags": []})[0], False)


class TestGapsAndParams(unittest.TestCase):
    def setUp(self):
        self.cfg = load_eval_config()

    def test_gap_requires_aligned_claim(self):
        gg = [{"gold_gap_id": "A", "affects_claims": ["g1"], "gap_type": "MISSING_RULE"}]
        pg = [GapView("P", "MISSING_RULE", affected_claims=["C1"])]
        self.assertEqual(match_gaps(gg, pg, {}, self.cfg), [("A", None)])
        self.assertEqual(match_gaps(gg, pg, {"g1": "C1"}, self.cfg), [("A", "P")])

    def test_gap_type_incompatible_and_duplicates(self):
        gg = [{"gold_gap_id": "A", "affects_claims": ["g1"], "gap_type": "INCOMPLETE_RESULT"}]
        pg = [GapView("P1", "MISSING_RULE", affected_claims=["C1"]),
              GapView("P2", "INCOMPLETE_RESULT", affected_claims=["C1"]),
              GapView("P3", "INCOMPLETE_RESULT", affected_claims=["C1"])]
        self.assertEqual(match_gaps(gg, pg, {"g1": "C1"}, self.cfg), [("A", "P2")])

    def test_gap_exact_mode(self):
        cfg = load_eval_config({"gaps": {"claim_match": "exact"}})
        gg = [{"gold_gap_id": "A", "affects_claims": ["g1"], "gap_type": "CONFLICT"}]
        pg = [GapView("P", "CONFLICT", affected_claims=["C1", "C2"])]
        self.assertEqual(match_gaps(gg, pg, {"g1": "C1"}, cfg), [("A", None)])
        self.assertEqual(match_gaps(gg, pg, {"g1": "C1"}, self.cfg), [("A", "P")])

    def test_param_value_normalization(self):
        self.assertTrue(values_equal("2026-11-12T22:00:00+08:00", "2026-11-12T14:00:00Z"))
        self.assertTrue(values_equal(15, "15.0"))
        self.assertTrue(values_equal("Line-D", " line-d "))
        self.assertFalse(values_equal("Line-D", "Line-E"))
        a = ActionView("A", "requery", tool="production.daily_output",
                       known_arguments={"line_id": "Line-D"}, pending_arguments={"business_date": None})
        self.assertEqual(param_hit("arg", "line_id", "Line-D", [a]), (True, True))
        self.assertEqual(param_hit("arg", "business_date", "2026-11-13", [a]), (True, False))
        self.assertEqual(param_hit("arg", "page", 2, [a]), (False, False))
        self.assertEqual(param_hit("tool", "tool", "production.daily_output", [a]), (True, True))
        self.assertEqual(param_hit("tool", "tool", "x", []), (False, False))

    def test_param_value_anywhere(self):
        # 01A 风格：中文键名 + 时间窗文本
        a = ActionView("A", "requery", pending_arguments={"查询窗口": "目标时段：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00"})
        self.assertEqual(param_hit("arg", "date_from", "2026-11-12T22:00:00+08:00", [a]), (False, False))
        self.assertEqual(param_hit("arg", "date_from", "2026-11-12T22:00:00+08:00", [a], value_anywhere=True), (True, True))
        # 过短的值不做任意位置匹配，避免误命中
        b = ActionView("B", "requery", known_arguments={"q": "page 2 of 8"})
        self.assertEqual(param_hit("arg", "page", 2, [b], value_anywhere=True), (False, False))


class TestBootstrap(unittest.TestCase):
    def test_deterministic_with_seed(self):
        runs, golds, scs = build_dataset()
        a = evaluate(runs, golds, "rule", scorecards=scs, seed=7, config=FAST)
        b = evaluate(runs, golds, "rule", scorecards=scs, seed=7, config=FAST)
        self.assertEqual({k: v["ci95"] for k, v in a["metrics"].items()},
                         {k: v["ci95"] for k, v in b["metrics"].items()})

    def test_degenerate_and_range(self):
        c = {"fs_strict.num": 1, "fs_strict.den": 2}
        out = bootstrap_ci([c, dict(c), dict(c)], False, 5, n_resamples=100, seed=0)
        self.assertEqual(out["false_support_strict"]["ci95"], [0.5, 0.5])
        self.assertEqual(out["false_support_strict"]["valid_resamples"], 100)
        self.assertIsNone(out["insufficient_as_err"]["ci95"])
        c1 = {"fs_strict.num": 1, "fs_strict.den": 1}
        c0 = {"fs_strict.num": 0, "fs_strict.den": 1}
        out = bootstrap_ci([c1, c0], False, 5, n_resamples=500, seed=1)
        lo, hi = out["false_support_strict"]["ci95"]
        self.assertEqual((lo, hi), (0.0, 1.0))

    def test_resamples_with_zero_den_dropped(self):
        c1 = {"iae.num": 1, "iae.den": 1}
        out = bootstrap_ci([c1, {}], False, 5, n_resamples=400, seed=3)
        self.assertLess(out["insufficient_as_err"]["valid_resamples"], 400)
        self.assertEqual(out["insufficient_as_err"]["ci95"], [1.0, 1.0])


if __name__ == "__main__":
    unittest.main()
