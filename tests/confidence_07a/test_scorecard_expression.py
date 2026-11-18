"""措辞强度分类（expression.py）。"""
import unittest

from confidence_07a.expression import classify_expression
from confidence_07a.model import DECLARED_UNKNOWN, DEFINITE, HEDGED, SCOPED_PARTIAL
from confidence_07a.scorecard import load_policy, score_run

from ._sc_support import make_run


class ClassifyExpressionTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()

    def c(self, text, strength=None):
        return classify_expression(text, strength, self.policy)

    def test_definite_reading(self):
        self.assertEqual(self.c("D线昨天（11月13日）的产量为4200件", "reading")[0], DEFINITE)

    def test_hedged(self):
        expr, hits = self.c("可能有一定积灰", "inference")
        self.assertEqual(expr, HEDGED)
        self.assertIn("HEDGED:可能", hits)
        self.assertEqual(self.c("预计今天到货")[0], HEDGED)

    def test_declared_unknown_beats_hedge_and_scope(self):
        expr, hits = self.c("目前仅凭远程数据无法确定具体原因", "negative_finding")
        self.assertEqual(expr, DECLARED_UNKNOWN)
        self.assertTrue(any(h.startswith("DECLARED_UNKNOWN:") for h in hits))
        self.assertEqual(self.c("暂时查不到实时物流状态")[0], DECLARED_UNKNOWN)
        self.assertEqual(self.c("需要现场停机检查后才能确认")[0], DECLARED_UNKNOWN)

    def test_scoped_partial(self):
        self.assertEqual(self.c("当前页面未发现 M8 钛合金螺栓", "negative_finding")[0], SCOPED_PARTIAL)
        self.assertEqual(self.c("已查白班中班合计4200件", "reading")[0], SCOPED_PARTIAL)

    def test_unscoped_negative_finding_is_definite(self):
        # “库房中未找到”是对全库的断言，不是限定范围的部分结论
        self.assertEqual(self.c("库房中未找到 M8 钛合金螺栓", "negative_finding")[0], DEFINITE)

    def test_approval_cannot_be_hedged(self):
        # “基本可以开机”在 approval 类结论上仍视为确定放行
        self.assertEqual(self.c("基本可以开机", "approval")[0], DEFINITE)
        self.assertEqual(self.c("基本可以安排重新启动", "assertion")[0], HEDGED)

    def test_approximation_is_not_hedge(self):
        # 01A 把含“约”的数字标为 inference；约数不等于推测
        self.assertEqual(self.c("本月电费约 31640 万元", "inference")[0], DEFINITE)

    def test_default_without_upstream(self):
        expr, hits = self.c("设备锁定已解除")
        self.assertEqual((expr, hits), (DEFINITE, ["default"]))

    def test_upstream_expression_and_scope_limited_override(self):
        run = make_run([
            {"id": "CLM-001", "text": "产量为4200件", "status": "SUPPORT", "expression": SCOPED_PARTIAL},
            {"id": "CLM-002", "text": "白班1800件", "status": "SUPPORT"},
        ])
        run.claims[1].scope_limited = True
        card = score_run(run)
        rows = {r["claim_id"]: r for r in card["claims"]}
        self.assertEqual(rows["CLM-001"]["expression_hits"], ["upstream_expression"])
        self.assertEqual(rows["CLM-002"]["expression"], SCOPED_PARTIAL)
        self.assertEqual(rows["CLM-002"]["expression_hits"], ["upstream:scope_limited"])


if __name__ == "__main__":
    unittest.main()
