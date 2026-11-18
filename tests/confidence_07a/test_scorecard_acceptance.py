"""需求 §6 五个验收场景（IND-002/024/030/043/053）在成绩单层的期望行为。

期望来自需求文档本身（§5、§6），不来自案例说明。成绩单不重判状态：以下断言都是
“给定上游（01A rule 模式）状态，v2 成绩单应如何汇总”。上游判错之处如实记录在断言注释中。
"""
import copy
import unittest

from confidence_07a.scorecard import diff_scorecards, load_policy, score_run

from ._sc_support import fixture_run


def rows(card):
    return {r["claim_id"]: r for r in card["claims"]}


def blocker_codes(card, claim_id):
    return sorted(b["code"] for b in card["blockers"] if b["claim_id"] == claim_id)


class AcceptanceTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.policy = load_policy()
        cls.cards = {c: score_run(fixture_run(c), cls.policy) for c in ("IND-002", "IND-024", "IND-030", "IND-043", "IND-053")}

    # ---------------- IND-002 回答覆盖 ----------------
    def test_ind002_separate_evaluation_and_release_rule(self):
        card = self.cards["IND-002"]
        r = rows(card)
        # “保养已完成”与“系统显示可启动”分别评价，均为已支持
        self.assertEqual(r["CLM-001"]["status"], "SUPPORT")
        self.assertEqual(r["CLM-006"]["status"], "SUPPORT")
        self.assertEqual(r["CLM-006"]["uncertainty"]["judgement"], "APPROPRIATE")
        # “可以开机”缺适用放行规则：保留 MISSING_RULE 缺口，且以确定措辞给出 → 严重过度断言
        self.assertEqual(r["CLM-007"]["status"], "MISSING_RULE")
        gap_types = [m.get("gap_type") for m in r["CLM-007"]["missing_or_conflicting"] if m.get("gap_id")]
        self.assertIn("MISSING_RULE", gap_types)
        self.assertEqual(r["CLM-007"]["severe_code"], "SEVERE_OVERCLAIM")
        self.assertIn("B2", blocker_codes(card, "CLM-007"))
        self.assertTrue(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        self.assertEqual(card["review_sequence"][0], "CLM-007")
        # 补证动作可回到规则检索
        self.assertIn("rule_lookup", [a["action_type"] for a in r["CLM-007"]["actions"]])

    # ---------------- IND-024 单位矛盾 ----------------
    def test_ind024_unit_error_is_severe_contradiction(self):
        card = self.cards["IND-024"]
        r = rows(card)
        c1 = r["CLM-001"]
        self.assertEqual(c1["status"], "REFUTE")
        self.assertEqual(c1["severe_code"], "SEVERE_CONTRADICTION")  # v1 只给了 MEDIUM
        self.assertIn("lexicon:压力", c1["high_risk_basis"])
        # 依据可回到原始字段 trace[c1].result.system_pressure_kpa
        unit_chk = [b for b in c1["main_basis"] if b.get("kind") == "unit_consistency"][0]
        self.assertEqual(unit_chk["json_path"], "trace[c1].result.system_pressure_kpa")
        self.assertEqual(unit_chk["event_id"], "c1")
        self.assertEqual(unit_chk["pointer"], "/trace/0/result/system_pressure_kpa")
        self.assertEqual(unit_chk["verdict"], "REFUTE")
        # 非主结论的 REFUTE（“已严重超出最大工作压力”）阻断但不重复计严重
        self.assertEqual(blocker_codes(card, "CLM-002"), ["B3"])
        self.assertTrue(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        self.assertEqual(card["support_score"], 0.0)
        self.assertFalse(card["overall_display"])
        # “正常吗”这一目标没有被上游关联到任何结论 → 未回应
        self.assertEqual({g["goal_id"]: g["coverage_state"] for g in card["goals"]}["GOAL-002"], "NOT_ADDRESSED")

    # ---------------- IND-030 检索不完整 ----------------
    def test_ind030_incomplete_search_blocks_definite_negative(self):
        card = self.cards["IND-030"]
        c1 = rows(card)["CLM-001"]
        # 回答写“库房中未找到”（全库确定断言），上游 UNKNOWN + 分页/筛选缺口
        self.assertEqual(c1["expression"], "DEFINITE")
        self.assertEqual(c1["status"], "UNKNOWN")
        self.assertEqual(c1["uncertainty"]["judgement"], "OVERCLAIM")
        self.assertEqual(blocker_codes(card, "CLM-001"), ["B2", "B4", "B5"])
        # 非安全类：阻断但不告警
        self.assertFalse(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        # 补证计划包含翻页动作，且参数为第 2 页
        acts = {a["action_id"]: a for a in card["supplement"]["actions"]}
        self.assertEqual(acts["ACT-001"]["action_type"], "refetch_page")
        self.assertEqual(acts["ACT-001"]["known_arguments"].get("page"), 2)
        self.assertEqual(acts["ACT-001"]["executability"], "executable")

    def test_ind030_scoped_wording_would_be_kept(self):
        # 若回答改为“当前页面未发现”（限定范围的部分结论），同样的上游状态不再触发 B2/B4/B5
        run = fixture_run("IND-030")
        run.claim("CLM-001").text = "当前页面未发现 M8 钛合金螺栓"
        card = score_run(run, self.policy)
        c1 = rows(card)["CLM-001"]
        self.assertEqual(c1["expression"], "SCOPED_PARTIAL")
        self.assertEqual(blocker_codes(card, "CLM-001"), [])
        self.assertEqual(c1["uncertainty"]["score"], 0.5)

    # ---------------- IND-043 时段遗漏 ----------------
    def test_ind043_missing_night_shift(self):
        card = self.cards["IND-043"]
        r = rows(card)
        c1 = r["CLM-001"]
        self.assertEqual(c1["status"], "UNKNOWN")
        self.assertEqual(blocker_codes(card, "CLM-001"), ["B2", "B4"])
        self.assertFalse(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        # 上游问题如实保留：白班/中班小计没有任何 check 命中，默认 UNKNOWN
        self.assertEqual(r["CLM-002"]["status"], "UNKNOWN")
        self.assertFalse(r["CLM-002"]["checked"])
        self.assertIn("CLM-002", card["build_risks"]["unchecked_default_unknown"])
        self.assertEqual(card["build_risks"]["orphan_evidence"], ["MAT-001", "MAT-002"])
        # 补查动作存在，但上游未给出工具与 business_date（需确认）
        act = card["supplement"]["actions"][0]
        self.assertEqual(act["action_type"], "requery")
        self.assertEqual(act["executability"], "needs_confirmation")
        self.assertIsNone(act["tool"])

    def test_ind043_supplement_diff(self):
        # 模拟上游补证后状态变为 SUPPORT、缺口关闭（G6）：等级与阻断项随之变化，diff 给出解释
        before = self.cards["IND-043"]
        run = fixture_run("IND-043")
        run.claim("CLM-001").status = "SUPPORT"
        run.claim("CLM-001").gap_ids = []
        run.gaps = []
        after = score_run(run, self.policy)
        d = diff_scorecards(before, after)
        self.assertEqual(d["grade"]["before"], "INSUFFICIENT")
        self.assertNotEqual(d["grade"]["after"], "INSUFFICIENT")
        self.assertEqual(d["transition_summary"], {"UNKNOWN→SUPPORT": 1})
        self.assertEqual(len(d["gaps_closed"]), 1)
        self.assertEqual(sorted(b["code"] for b in d["blockers_removed"]), ["B2", "B4"])
        self.assertTrue(any("UNKNOWN → SUPPORT" in e for e in d["explanation_zh"]))
        self.assertEqual(d["dimensions"]["support"]["delta"], 0.25)

    # ---------------- IND-053 审批与限制 ----------------
    def test_ind053_upstream_rule_mode(self):
        card = self.cards["IND-053"]
        r = rows(card)
        # “可以正常作业”被上游判 REFUTE（载荷 18t > 限重 15t），且缺可用审批 → 严重矛盾
        c5 = r["CLM-005"]
        self.assertEqual(c5["status"], "REFUTE")
        self.assertEqual(c5["severe_code"], "SEVERE_CONTRADICTION")
        self.assertIn("approval_type", c5["high_risk_basis"])
        gap_types = sorted(m["gap_type"] for m in c5["missing_or_conflicting"] if m.get("gap_id"))
        self.assertEqual(gap_types, ["CONFLICT", "MISSING_RULE"])
        locs = {b.get("json_path") for b in c5["main_basis"]} | {b.get("json_path") for b in c5["missing_or_conflicting"]}
        self.assertIn("trace[c1].result.restriction", locs)
        self.assertIn("trace[c3].result.permit_status", locs)
        self.assertTrue(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")
        # 上游错误如实反映：“今天吊装18吨设备没有问题”被 01A 判为 SUPPORT（只核对了数值 18），
        # v2 不重判，因此该条不被标记；这一错误需由评测指标（错误结论被判支持比例）暴露。
        self.assertEqual(r["CLM-004"]["status"], "SUPPORT")
        self.assertFalse(r["CLM-004"]["severe"])
        self.assertEqual(r["CLM-004"]["blocker_codes"], [])

    def test_ind053_hand_built_refute_on_18t_claim(self):
        # 若上游正确地把 18 吨结论判为 REFUTE：它是 GOAL-001 的主回应、含“吊装”，走严重矛盾路径
        run = fixture_run("IND-053")
        run.claim("CLM-004").status = "REFUTE"
        card = score_run(run, self.policy)
        c4 = rows(card)["CLM-004"]
        self.assertEqual(c4["severe_code"], "SEVERE_CONTRADICTION")
        self.assertIn("lexicon:吊装", c4["high_risk_basis"])
        self.assertEqual(sorted(s["claim_id"] for s in card["severe_issues"]), ["CLM-004", "CLM-005"])
        self.assertEqual(card["goals"][0]["coverage_state"], "ADDRESSED_UNSUPPORTED")

    def test_ind053_hand_built_permit_pending(self):
        # 若上游把“可以正常作业”判为 MISSING_RULE（许可待审批、无判定规则）：确定措辞 → 严重过度断言
        run = fixture_run("IND-053")
        run.claim("CLM-005").status = "MISSING_RULE"
        card = score_run(run, self.policy)
        c5 = rows(card)["CLM-005"]
        self.assertEqual(c5["severe_code"], "SEVERE_OVERCLAIM")
        self.assertTrue(card["high_risk_alert"])
        self.assertEqual(card["grade"], "INSUFFICIENT")

    def test_status_never_rewritten(self):
        for case, card in self.cards.items():
            run = fixture_run(case)
            up = {c.claim_id: c.status for c in run.claims}
            self.assertEqual({r["claim_id"]: r["status"] for r in card["claims"]}, up, case)

    def test_inputs_not_mutated(self):
        run = fixture_run("IND-053")
        snap = copy.deepcopy(run.to_dict())
        score_run(run, self.policy)
        self.assertEqual(run.to_dict(), snap)


if __name__ == "__main__":
    unittest.main()
