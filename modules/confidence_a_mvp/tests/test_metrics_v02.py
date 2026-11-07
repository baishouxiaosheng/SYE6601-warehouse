import json
import unittest
from copy import deepcopy
from pathlib import Path

from confidence_a import ContractError, evaluate_runs
from confidence_a.demo_fixtures import metric_runs

ROOT = Path(__file__).resolve().parents[1]


class GraphMetricTests(unittest.TestCase):
    def test_rates_are_stratified_and_targets_are_not_measured(self):
        report = evaluate_runs(metric_runs())
        self.assertEqual(report["measurement_status"], "NOT_A_MEASURED_RESULT")
        self.assertEqual(report["target_status"]["status"], "PROPOSED_NOT_MEASURED")
        self.assertTrue(all(item["measured"] is None for item in report["target_status"]["items"]))
        self.assertIn("拟验证", "\n".join(report["notes"]))
        groups = {(group["scope"]["method"], group["scope"]["fault_origin"]): group for group in report["groups"]}
        self.assertEqual(len(groups), 4)
        natural = groups[("dynamic", "NATURAL")]
        injected = groups[("dynamic", "INJECTED")]
        fixed = groups[("fixed_full", "INJECTED")]
        mismatch = groups[("prompt_mock", "NATURAL")]
        self.assertEqual(natural["critical_omission_rate"], {"numerator": 0, "denominator": 2, "value": 0})
        self.assertEqual(injected["critical_omission_rate"]["numerator"], 1)
        self.assertEqual(injected["critical_omission_rate"]["denominator"], 2)
        self.assertEqual(injected["accepted_wrong_relation_rate"], {"numerator": 1, "denominator": 4, "value": 0.25})
        self.assertEqual(injected["critical_gap_miss_rate"], {"numerator": 1, "denominator": 2, "value": 0.5})
        self.assertEqual(injected["structure_expansion_path_success"], {"numerator": 0, "denominator": 1, "value": 0})
        self.assertEqual(injected["structure_expansion_stage_success"], {"numerator": 1, "denominator": 2, "value": 0.5})
        self.assertEqual(natural["structure_expansion_path_success"]["value"], 1)
        self.assertIsNone(fixed["structure_expansion_path_success"]["value"])
        self.assertEqual(fixed["structure_expansion_path_success"]["denominator"], 0)
        self.assertIsNone(fixed["accepted_wrong_relation_rate"]["value"])
        self.assertEqual(mismatch["answer_scorecard_version_consistency"]["value"], 0)
        self.assertEqual(natural["answer_scorecard_version_consistency"]["value"], 1)
        self.assertEqual(natural["terminal_accuracy"]["value"], 1)
        self.assertEqual(injected["unsupported_answer_rate"]["value"], 1)

    def test_legacy_metrics_do_not_gain_gold_fields(self):
        payload = json.loads((ROOT / "examples/runs.demo.json").read_text(encoding="utf-8"))
        report = evaluate_runs(payload)
        self.assertNotIn("critical_omission_rate", report)
        self.assertNotIn("critical_omission_rate", report["groups"][0])
        self.assertEqual(report["schema_version"], "0.1-draft")

    def test_saved_v2_metrics_match_the_formula(self):
        payload = json.loads((ROOT / "examples/runs.v2.json").read_text(encoding="utf-8"))
        self.assertEqual(evaluate_runs(payload), json.loads((ROOT / "examples/metrics.v2.json").read_text(encoding="utf-8")))

    def test_gold_counts_cannot_exceed_their_denominators(self):
        data = metric_runs()
        data["records"][0]["graph_quality"]["critical_conditions_recognized"] = 9
        with self.assertRaises(ContractError):
            evaluate_runs(data)

    def test_natural_and_injected_stay_split_when_otherwise_identical(self):
        data = metric_runs()
        copied = deepcopy(data["records"][0])
        copied["run_id"] = "V2-METRIC-NATURAL-COPY"
        copied["fault_origin"] = "INJECTED"
        copied["assessment"] = deepcopy(copied["assessment"])
        copied["assessment"]["assessment_id"] = "ASSESS-COPY"
        data["records"] = [data["records"][0], copied]
        self.assertEqual(len(evaluate_runs(data)["groups"]), 2)


if __name__ == "__main__":
    unittest.main()
