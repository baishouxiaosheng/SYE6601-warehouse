import json
import unittest
from copy import deepcopy

from confidence_a import ContractError, adapt_v01_to_v02, render_scorecard_markdown, score_snapshot
from confidence_a.demo_fixtures import (
    critical_access_denied, critical_pagination, dyn01_after_ticket, dyn01_before_ticket,
    missing_baseline, pruned_reservation, scope_unclear, sufficient_eligible, sufficient_ineligible,
    unexpanded_clause, unmapped_claim, unresolved_relation,
)
from confidence_a.scoring import DEFAULT_POLICY
from confidence_a.scoring_v02 import DEFAULT_POLICY_V02


def dumped(card):
    return json.dumps(card, ensure_ascii=False)


class GraphScoringTests(unittest.TestCase):
    def test_legacy_snapshot_still_scores_and_does_not_auto_upgrade(self):
        from pathlib import Path
        data = json.loads(Path(__file__).resolve().parents[1].joinpath(
            "examples/03_contract_unknown.snapshot.json").read_text(encoding="utf-8"))
        card = score_snapshot(data)
        self.assertEqual(card["schema_version"], "0.1-draft")
        self.assertEqual(card["score"], 49)
        with self.assertRaises(ContractError):
            adapt_v01_to_v02(data)

    def test_unknown_version_fails_clearly(self):
        data = sufficient_eligible()
        data["schema_version"] = "future-version"
        with self.assertRaises(ContractError) as caught:
            score_snapshot(data)
        self.assertIn("0.2-draft", str(caught.exception))

    def test_missing_baseline_blocks_even_when_built_nodes_pass(self):
        card = score_snapshot(missing_baseline())
        self.assertEqual(card["level"], "证据不足")
        self.assertIsNone(card["score"])
        self.assertLess(card["raw_design_score"], 100)
        self.assertFalse(card["gate_passed"])
        self.assertFalse(card["may_present_definitive_decision"])
        self.assertTrue(card["upstream_recommendation_blocked"])
        self.assertEqual(card["recommendation"], "eligible")
        self.assertEqual(card["dimensions"]["baseline_coverage"]["numerator"], 0)
        self.assertGreater(card["dimensions"]["recognized_conditions"]["value"], 0.99)
        self.assertIn("BASELINE_INCOMPLETE", dumped(card["graph_build_risks"]))
        self.assertIn("MISSING_FROM_GRAPH", dumped(card))

    def test_negative_advice_is_blocked_by_the_same_gate(self):
        data = missing_baseline()
        data["recommendation"] = "ineligible"
        card = score_snapshot(data)
        self.assertEqual(card["level"], "证据不足")
        self.assertFalse(card["may_present_definitive_decision"])
        self.assertTrue(card["upstream_recommendation_blocked"])
        self.assertIn("否定建议", dumped(card["notes"]))

    def test_unexpanded_clause_is_not_complete(self):
        card = score_snapshot(unexpanded_clause())
        self.assertEqual(card["level"], "证据不足")
        self.assertFalse(card["gate_passed"])
        self.assertGreater(card["dimensions"]["expansion_and_semantics"]["unexpanded_count"], 0)
        self.assertLess(card["dimensions"]["expansion_and_semantics"]["value"], 1)
        self.assertIn("CRITICAL_UNEXPANDED", dumped(card["graph_build_risks"]))
        self.assertNotIn("已建模范围内证据充分", card["level"])

    def test_auxiliary_evidence_cannot_cancel_403_or_pagination(self):
        for builder, cause in ((critical_access_denied, "ACCESS_DENIED"),
                               (critical_pagination, "PAGINATION_INCOMPLETE")):
            with self.subTest(cause=cause):
                original = builder()
                extra = deepcopy(original)
                extra["evidence"].append({
                    "evidence_id": "EXTRA-EVIDENCE", "source_type": "AUXILIARY_NOTE",
                    "citation": "demo://v2/extra",
                })
                first, second = score_snapshot(original), score_snapshot(extra)
                self.assertEqual(first["level"], "证据不足")
                self.assertIsNone(first["score"])
                self.assertEqual(first["raw_design_score"], second["raw_design_score"])
                self.assertEqual(first["gate_passed"], second["gate_passed"])
                self.assertFalse(first["may_present_definitive_decision"])
                self.assertTrue(any(gap["cause"] == cause for gap in first["residual_gaps"]))
                self.assertTrue(any(risk["code"] == "TOOL_LIMIT" and risk["cause"] == cause
                                    for risk in first["graph_build_risks"]))

    def test_budget_stop_on_a_critical_gap_still_blocks(self):
        data = critical_access_denied()
        data["obligations"][0]["reason_codes"] = ["BUDGET_STOP"]
        data["obligations"][0]["reason"] = "预算耗尽，关键合同仍未取得。"
        data["baseline_checks"][0]["reason_codes"] = ["BUDGET_STOP"]
        data["baseline_checks"][0]["reason"] = data["obligations"][0]["reason"]
        data["stop_reason"] = "BUDGET_STOP"
        card = score_snapshot(data)
        self.assertEqual(card["level"], "证据不足")
        self.assertEqual(card["stop_reason"], "BUDGET_STOP")
        self.assertIsNone(card["score"])
        self.assertTrue(any(gap["cause"] == "BUDGET_STOP" for gap in card["residual_gaps"]))

    def test_pagination_blocks_ungrounded_negative_advice(self):
        card = score_snapshot(critical_pagination())
        self.assertEqual(card["recommendation"], "ineligible")
        self.assertTrue(card["upstream_recommendation_blocked"])
        self.assertEqual(card["level"], "证据不足")

    def test_ineligibility_can_be_sufficient_inside_scope(self):
        card = score_snapshot(sufficient_ineligible())
        self.assertEqual(card["level"], "已建模范围内证据充分")
        self.assertEqual(card["recommendation"], "ineligible")
        self.assertTrue(card["gate_passed"])
        self.assertTrue(card["may_present_definitive_decision"])
        self.assertEqual(card["score"], 100)
        self.assertNotIn("完全可靠", dumped(card))

    def test_pruned_noncritical_gap_is_reserved_and_not_escalated(self):
        card = score_snapshot(pruned_reservation())
        self.assertEqual(card["level"], "附保留说明")
        self.assertEqual(card["workflow_status"], "completed")
        self.assertNotEqual(card["workflow_status"], "escalated")
        self.assertTrue(card["may_present_definitive_decision"])
        self.assertFalse(card["display_score_suppressed"])
        self.assertTrue(any(item["code"] == "PRUNED_RESIDUAL" and "loop" in item["reason"]
                            for item in card["reservations"]))
        self.assertTrue(any(gap["pruned"] and gap["prune_source"] == "loop" for gap in card["residual_gaps"]))

    def test_unpruned_noncritical_gap_is_not_treated_as_irrelevant(self):
        data = pruned_reservation()
        data["obligations"][-1]["prune"] = None
        card = score_snapshot(data)
        self.assertEqual(card["level"], "证据不足")
        self.assertEqual(card["workflow_status"], "completed")
        self.assertIn("UNPRUNED_RESIDUAL", dumped(card["level_reasons"]))

    def test_dyn01_ticket_gap_then_rescore_keeps_versions_consistent(self):
        before = score_snapshot(dyn01_before_ticket())
        after = score_snapshot(dyn01_after_ticket())
        self.assertEqual(before["level"], "证据不足")
        self.assertFalse(before["may_present_definitive_decision"])
        self.assertEqual(before["graph_version"], "dyn01-graph-1")
        self.assertEqual(before["answer_version"], "dyn01-answer-1")
        self.assertTrue(before["version_consistent"])
        self.assertTrue(any(gap["obligation_id"] == "DYN-O-TICKET-24H" for gap in before["residual_gaps"]))
        self.assertIn("STRUCTURE_EXPANSION_OPEN", dumped(before["graph_build_risks"]))
        before_notes = "\n".join(before["advice_change_notes"])
        self.assertIn("24 小时", before_notes)
        self.assertIn("UNKNOWN", before_notes)
        self.assertIn("eligible → undetermined", before_notes)
        self.assertTrue(any(row["action_id"] == "DYN-REPAIR-TICKET" for row in before["repair_actions"]))

        self.assertEqual(after["level"], "已建模范围内证据充分")
        self.assertEqual(after["score"], 100)
        self.assertEqual(after["recommendation"], "eligible")
        self.assertTrue(after["may_present_definitive_decision"])
        self.assertEqual(after["graph_version"], "dyn01-graph-2")
        self.assertEqual(after["answer_version"], "dyn01-answer-2")
        self.assertNotEqual(before["graph_version"], after["graph_version"])
        self.assertNotEqual(before["answer_version"], after["answer_version"])
        after_notes = "\n".join(after["advice_change_notes"])
        self.assertIn("24 小时", after_notes)
        self.assertIn("undetermined → eligible", after_notes)
        self.assertIn("SUPPORT", after_notes)
        self.assertFalse(any(gap["obligation_id"] == "DYN-O-TICKET-24H" for gap in after["residual_gaps"]))

    def test_dyn01_negative_recommendation_is_blocked_before_ticket(self):
        data = dyn01_before_ticket()
        data["recommendation"] = "ineligible"
        card = score_snapshot(data)
        self.assertEqual(card["level"], "证据不足")
        self.assertTrue(card["upstream_recommendation_blocked"])

    def test_scope_unresolved_relation_and_unmapped_claim_block(self):
        expectations = (
            (scope_unclear, "SCOPE_UNCLEAR"),
            (unresolved_relation, "CRITICAL_RELATION_UNRESOLVED"),
            (unmapped_claim, "UNMAPPED_CLAIM"),
        )
        for builder, code in expectations:
            with self.subTest(code=code):
                card = score_snapshot(builder())
                self.assertEqual(card["level"], "证据不足")
                self.assertIsNone(card["score"])
                self.assertIn(code, dumped(card["graph_build_risks"]))
                self.assertFalse(card["may_present_definitive_decision"])

    def test_version_mismatch_and_gold_field_are_rejected(self):
        mismatch = sufficient_eligible()
        mismatch["answer_binding"]["answer_version"] = "other-answer"
        with self.assertRaises(ContractError) as caught:
            score_snapshot(mismatch)
        self.assertIn("answer_version", str(caught.exception))
        gold = sufficient_eligible()
        gold["critical_conditions_annotated"] = 1
        with self.assertRaises(ContractError):
            score_snapshot(gold)

    def test_v01_policy_is_not_silently_applied(self):
        with self.assertRaises(ContractError):
            score_snapshot(sufficient_eligible(), DEFAULT_POLICY)

    def test_display_cap_cannot_turn_a_hard_gate_into_sufficient(self):
        policy = deepcopy(DEFAULT_POLICY_V02)
        policy["suppress_display_score_on_hard_gate"] = False
        card = score_snapshot(missing_baseline(), policy)
        self.assertEqual(card["level"], "证据不足")
        self.assertFalse(card["may_present_definitive_decision"])
        self.assertLess(card["score"], 100)
        self.assertFalse(card["display_score_suppressed"])

    def test_critical_prune_is_rejected(self):
        data = dyn01_before_ticket()
        data["obligations"][2]["prune"] = {
            "record_id": "BAD", "source": "loop", "reason": "不能剪掉关键工单条件。",
        }
        with self.assertRaises(ContractError):
            score_snapshot(data)

    def test_deterministic_and_template_restates_recorded_reason(self):
        data = dyn01_before_ticket()
        before = deepcopy(data)
        first, second = score_snapshot(data), score_snapshot(data)
        self.assertEqual(first, second)
        self.assertEqual(data, before)
        text = render_scorecard_markdown(first)
        self.assertIn("证据不足", text)
        self.assertIn("dyn01-graph-1", text)
        self.assertIn("dyn01-answer-1", text)
        self.assertIn("24 小时", text)
        self.assertNotIn("完全可靠", text)


if __name__ == "__main__":
    unittest.main()
