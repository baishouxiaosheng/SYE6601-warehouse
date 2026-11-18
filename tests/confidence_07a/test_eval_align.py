"""结论对齐：显式映射、相似度、重复、数值不一致、阈值。"""
import unittest

from confidence_07a.eval.align import align_claims, extract_numbers, normalize_text, similarity
from confidence_07a.eval.config import load_eval_config
from confidence_07a.model import ClaimView


def g(gid, span, pred=None):
    d = {"gold_claim_id": gid, "answer_span": span}
    if pred:
        d["pred_claim_id"] = pred
    return d


class TestNormalize(unittest.TestCase):
    def test_normalize_text(self):
        self.assertEqual(normalize_text("压力 21,500 ＭＰａ。"), "压力21500mpa")
        self.assertEqual(normalize_text(None), "")

    def test_extract_numbers(self):
        self.assertEqual(extract_numbers("21,500 kPa 即 21.50 MPa"), {"21500", "21.5"})
        self.assertEqual(extract_numbers("Line-D 夜班"), set())
        self.assertEqual(extract_numbers("０８号"), {"8"})


class TestAlign(unittest.TestCase):
    def test_explicit_first(self):
        gold = [g("g1", "完全不同的文本", pred="C2")]
        pred = [ClaimView("C1", "完全不同的文本", "SUPPORT"), ClaimView("C2", "别的", "UNKNOWN")]
        al = align_claims(gold, pred)
        self.assertEqual([(p.gold_claim_id, p.pred_claim_id, p.method) for p in al.pairs], [("g1", "C2", "explicit")])
        self.assertEqual(al.extra_pred, ["C1"])

    def test_explicit_invalid_falls_back(self):
        gold = [g("g1", "白班产量1800件", pred="NOPE")]
        pred = [ClaimView("C1", "白班产量1800件", "SUPPORT")]
        al = align_claims(gold, pred)
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})
        self.assertEqual(al.pairs[0].method, "similarity")
        self.assertTrue(any("NOPE" in w for w in al.warnings))

    def test_similarity_and_containment(self):
        gold = [g("g1", "D线昨天（11月13日）的产量为4200件")]
        pred = [ClaimView("C1", "D线昨天的产量为4200件", "UNKNOWN"),
                ClaimView("C2", "生产运行正常", "UNKNOWN")]
        al = align_claims(gold, pred)
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})
        self.assertEqual(al.extra_pred, ["C2"])
        # 包含关系保底分
        self.assertGreaterEqual(similarity("今天吊装18吨设备没有问题，可以正常作业", "今天吊装18吨设备没有问题"), 0.8)

    def test_uses_source_span_from_raw(self):
        gold = [g("g1", "CRANE-02已通过定期检验")]
        pred = [ClaimView("C1", "定检状态：通过", "SUPPORT", raw={"meta": {"source_span": "CRANE-02已通过定期检验"}})]
        self.assertEqual(align_claims(gold, pred).gold_to_pred(), {"g1": "C1"})

    def test_numeric_mismatch_blocks(self):
        gold = [g("g1", "白班产量1800件")]
        pred = [ClaimView("C1", "白班产量1900件", "SUPPORT")]
        al = align_claims(gold, pred)
        self.assertEqual(al.pairs, [])
        self.assertEqual(al.missed_gold, ["g1"])
        self.assertEqual(al.extra_pred, ["C1"])
        self.assertEqual(al.best_rejected["g1"]["reason"], "numeric_mismatch")

    def test_numeric_same_number_different_unit_aligns(self):
        # 单位错误（kPa vs MPa）属于结论内容问题，应对齐后由状态体现
        al = align_claims([g("g1", "系统压力为21,500 MPa")], [ClaimView("C1", "系统压力为21500 kPa", "REFUTE")])
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})

    def test_partial_numeric_overlap_prefers_better(self):
        gold = [g("g1", "白班1800件中班2400件")]
        pred = [ClaimView("C1", "白班1800件中班2500件", "SUPPORT"),
                ClaimView("C2", "白班1800件中班2400件", "SUPPORT")]
        self.assertEqual(align_claims(gold, pred).gold_to_pred(), {"g1": "C2"})

    def test_duplicate_gold_spans(self):
        gold = [g("g1", "许可待审批"), g("g2", "许可待审批")]
        pred = [ClaimView("C1", "许可待审批", "UNKNOWN")]
        al = align_claims(gold, pred)
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})  # 平分时按 gold 顺序
        self.assertEqual(al.missed_gold, ["g2"])

    def test_duplicate_pred_texts(self):
        gold = [g("g1", "许可待审批")]
        pred = [ClaimView("C1", "许可待审批", "UNKNOWN"), ClaimView("C2", "许可待审批", "UNKNOWN")]
        al = align_claims(gold, pred)
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})
        self.assertEqual(al.extra_pred, ["C2"])

    def test_explicit_conflict_same_pred(self):
        gold = [g("g1", "许可待审批", pred="C1"), g("g2", "许可待审批", pred="C1")]
        pred = [ClaimView("C1", "许可待审批", "UNKNOWN")]
        al = align_claims(gold, pred)
        self.assertEqual(al.gold_to_pred(), {"g1": "C1"})
        self.assertEqual(al.missed_gold, ["g2"])
        self.assertTrue(al.warnings)

    def test_greedy_global_best(self):
        # g1 与 C1、C2 都像，但 g2 只像 C2；全局按分数贪心，g2-C2 完全相同先配
        gold = [g("g1", "压力表读数正常范围内"), g("g2", "压力表读数正常")]
        pred = [ClaimView("C1", "压力表读数在正常范围内", "SUPPORT"), ClaimView("C2", "压力表读数正常", "SUPPORT")]
        self.assertEqual(align_claims(gold, pred).gold_to_pred(), {"g2": "C2", "g1": "C1"})

    def test_threshold_from_config(self):
        gold = [g("g1", "D线昨天产量为4200件")]
        pred = [ClaimView("C1", "D线产量4200件", "UNKNOWN")]
        self.assertEqual(len(align_claims(gold, pred).pairs), 1)
        strict = load_eval_config({"alignment": {"threshold": 0.99}})
        self.assertEqual(len(align_claims(gold, pred, strict).pairs), 0)

    def test_empty_inputs(self):
        al = align_claims([], [])
        self.assertEqual((al.pairs, al.missed_gold, al.extra_pred), ([], [], []))
        al = align_claims([g("g1", "")], [ClaimView("C1", "x", "SUPPORT")])
        self.assertEqual(al.missed_gold, ["g1"])


if __name__ == "__main__":
    unittest.main()
