"""受控变体（eval/variants.py）：生成、应用、比较、汇总；引擎用假实现注入（离线、无 01A 依赖）。"""
import copy
import json
import unittest

from confidence_07a.eval.report import build_experiment_metrics, validate_experiment_metrics
from confidence_07a.eval.variants import (
    KINDS,
    VariantSpec,
    apply_variant,
    compare_variant,
    format_trace_path,
    generate_variants,
    injected_false_support,
    match_claims_by_text,
    parse_trace_path,
    render_variants_md,
    run_variants_experiment,
    summarize_variant_rows,
    variant_csv_rows,
    variant_metric_rows,
)
from confidence_07a.model import ClaimView, EvidenceRef, GapView, RunView

from ._sc_support import fixture_logs, fixture_run


def _by_kind(specs, kind, event=None):
    return [s for s in specs if s.kind == kind and (event is None or s.target_event_id == event)]


class TestPaths(unittest.TestCase):
    def test_parse_and_format(self):
        p = parse_trace_path("trace[c2].result.shifts[0].business_date")
        self.assertEqual(p, ("c2", ["result", "shifts", 0, "business_date"]))
        self.assertEqual(format_trace_path(*p), "trace[c2].result.shifts[0].business_date")
        self.assertIsNone(parse_trace_path("result.x"))
        self.assertIsNone(parse_trace_path(None))


class TestGenerateApplyIND053(unittest.TestCase):
    """IND-053（需求 §6 验收场景：吊装 18 吨 vs 限重 15 吨）。"""

    @classmethod
    def setUpClass(cls):
        cls.rec = fixture_logs()["IND-053-r1"]
        cls.base = fixture_run("IND-053")
        cls.specs = generate_variants(cls.rec, cls.base)

    def test_all_kinds_and_ids(self):
        kinds = {s.kind for s in self.specs}
        self.assertEqual(kinds, set(KINDS) - {"truncate_page"})  # IND-053 没有记录列表
        for s in self.specs:
            self.assertEqual(s.base_run_id, "IND-053-r1")
            self.assertTrue(s.variant_id.startswith("IND-053-r1~" + s.kind))
            self.assertIsInstance(s.expected_effect, dict)
        self.assertEqual(len({s.variant_id for s in self.specs}), len(self.specs))

    def test_targets_are_support_claims_only(self):
        for s in self.specs:
            if s.kind == "control_noop":
                continue
            for cid in s.target_claim_ids_base:
                self.assertEqual(self.base.claim(cid).status, "SUPPORT")
            self.assertEqual(s.expected_effect.get("must_not_be"), "SUPPORT")
            self.assertIn("pred", s.target_sources)

    def test_drop_evidence(self):
        s = _by_kind(self.specs, "drop_evidence", "c2")[0]
        self.assertEqual(s.json_path, "trace[c2]")
        self.assertEqual(s.target_claim_ids_base, ["CLM-004"])
        out = apply_variant(self.rec, s)
        self.assertEqual(out["run_id"], "IND-053-r1")  # 01A 校验要求 run_id 不变
        self.assertNotIn("c2", [e.get("id") for e in out["trace"]])
        self.assertIn("c2", [e.get("id") for e in self.rec["trace"]])  # 原记录未被修改

    def test_unit_change_renames_key_without_conversion(self):
        s = _by_kind(self.specs, "unit_change", "c2")[0]
        self.assertEqual(s.json_path, "trace[c2].result.load_weight_tons")
        self.assertEqual(s.before, {"key": "load_weight_tons", "value": 18})
        self.assertEqual(s.after, {"key": "load_weight_kg", "value": 18})
        out = apply_variant(self.rec, s)
        res = [e for e in out["trace"] if e.get("id") == "c2"][0]["result"]
        self.assertEqual(res["load_weight_kg"], 18)
        self.assertNotIn("load_weight_tons", res)
        orig_keys = list([e for e in self.rec["trace"] if e.get("id") == "c2"][0]["result"].keys())
        self.assertEqual(list(res.keys()), [k if k != "load_weight_tons" else "load_weight_kg" for k in orig_keys])

    def test_entity_swap_changes_result_not_arguments(self):
        s = _by_kind(self.specs, "entity_swap", "c1")[0]
        self.assertEqual((s.before, s.after), ("CRANE-02", "CRANE-03"))
        self.assertEqual(s.target_claim_ids_base, ["CLM-001"])  # 只有原文提到 CRANE-02 的结论
        out = apply_variant(self.rec, s)
        ev = [e for e in out["trace"] if e.get("id") == "c1"][0]
        self.assertEqual(ev["result"]["equipment_id"], "CRANE-03")
        self.assertEqual(ev["arguments"]["equipment_id"], "CRANE-02")

    def test_control_noop_reverses_keys_only(self):
        s = _by_kind(self.specs, "control_noop")[0]
        self.assertEqual(s.expected_effect, {"unchanged": True})
        out = apply_variant(self.rec, s)
        self.assertEqual(out["trace"], self.rec["trace"])  # dict 相等与键序无关
        self.assertEqual(list(out["trace"][1].keys()), list(reversed(list(self.rec["trace"][1].keys()))))

    def test_unknown_kind_rejected(self):
        with self.assertRaises(ValueError):
            generate_variants(self.rec, self.base, kinds=["bogus"])

    def test_gold_locators_add_targets(self):
        gold = {"run_id": "IND-053-r1", "claims": [{
            "gold_claim_id": "g3", "answer_span": "今天吊装18吨设备没有问题", "gold_status": "REFUTE",
            "evidence_locators": [{"event_id": "c3", "json_path": "trace[c3].result.permit_status"}]}]}
        specs = generate_variants(self.rec, self.base, gold, kinds=["drop_evidence"])
        c3 = _by_kind(specs, "drop_evidence", "c3")
        self.assertEqual(len(c3), 1)
        self.assertEqual(c3[0].target_sources, ["gold"])
        self.assertEqual(c3[0].gold_claim_ids, ["g3"])
        self.assertEqual(c3[0].target_claim_ids_base, ["CLM-004"])

    def test_spec_roundtrip(self):
        s = self.specs[0]
        self.assertEqual(VariantSpec.from_dict(json.loads(json.dumps(s.to_dict(), ensure_ascii=False))), s)


class TestTruncateCandidates(unittest.TestCase):
    def _setup(self):
        rec = {"run_id": "T-1-r1", "case_id": "T-1", "ai_answer": "批次合格", "trace": [
            {"id": "c1", "event": "tool_call", "tool": "x.list", "arguments": {"line": "L1"},
             "result": {"normal_range_c": [60, 90], "tags": ["a", "b", "c"],
                        "batches": [{"id": 1}, {"id": 2}, {"id": 3}, {"id": 4}]}}]}
        ev = EvidenceRef("MAT-1", "T-1-r1", event_id="c1", json_path="trace[c1].result")
        base = RunView("T-1-r1", "T-1", "q", "批次合格", claims=[ClaimView("C1", "批次合格", "SUPPORT", evidence_ids=["MAT-1"])],
                       evidence={"MAT-1": ev})
        return rec, base

    def test_only_record_lists_are_truncated(self):
        rec, base = self._setup()
        specs = generate_variants(rec, base, kinds=["truncate_page"])
        self.assertEqual(len(specs), 1)
        s = specs[0]
        self.assertEqual(s.json_path, "trace[c1].result.batches")
        self.assertEqual(s.after, {"len": 2, "has_more": True})
        self.assertEqual(s.expected_effect.get("or_new_gap_type"), "INCOMPLETE_RESULT")
        out = apply_variant(rec, s)
        res = out["trace"][0]["result"]
        self.assertEqual(len(res["batches"]), 2)
        self.assertTrue(res["has_more"])
        self.assertEqual(res["normal_range_c"], [60, 90])


def _run(claims, gaps=None):
    return RunView("T-2-r1", "T-2", "q", "a", claims=[ClaimView(c, t, s) for c, t, s in claims], gaps=gaps or [])


class TestCompareAndSummarize(unittest.TestCase):
    def setUp(self):
        self.base = _run([("C1", "压力2.5MPa", "SUPPORT"), ("C2", "可以开机", "UNKNOWN")])
        self.spec = VariantSpec("T-2-r1~drop_evidence~c1", "T-2-r1", "drop_evidence", "c1", "trace[c1]",
                                expected_effect={"must_not_be": "SUPPORT"}, target_sources=["pred"],
                                target_claim_ids_base=["C1"])
        self.ctrl = VariantSpec("T-2-r1~control_noop~all", "T-2-r1", "control_noop", None, "trace[*]",
                                expected_effect={"unchanged": True}, target_sources=["control"])

    def test_match_by_text_ignores_ids(self):
        var = _run([("X9", "可以开机", "UNKNOWN"), ("X8", "压力2.5MPa", "UNKNOWN")])
        self.assertEqual(match_claims_by_text(self.base, var), {"C1": "X8", "C2": "X9"})

    def test_effect_observed_and_missing(self):
        changed = compare_variant(self.spec, self.base, _run([("A", "压力2.5MPa", "UNKNOWN"), ("B", "可以开机", "UNKNOWN")]))
        self.assertTrue(changed["effect_observed"])
        self.assertEqual(changed["n_collateral_changed"], 0)
        same = compare_variant(self.spec, self.base, self.base)
        self.assertFalse(same["effect_observed"])
        missing = compare_variant(self.spec, self.base, _run([("B", "可以开机", "UNKNOWN")]))
        self.assertFalse(missing["effect_observed"])
        self.assertEqual(missing["n_target_missing"], 1)
        err = compare_variant(self.spec, self.base, None, error="boom")
        self.assertFalse(err["engine_ok"])

    def test_truncate_satisfied_by_new_gap(self):
        spec = VariantSpec("v", "T-2-r1", "truncate_page", "c1", "trace[c1].result.rows",
                           expected_effect={"must_not_be": "SUPPORT", "or_new_gap_type": "INCOMPLETE_RESULT"},
                           target_claim_ids_base=["C1"])
        var = _run([("C1", "压力2.5MPa", "SUPPORT"), ("C2", "可以开机", "UNKNOWN")],
                   gaps=[GapView("G1", "INCOMPLETE_RESULT")])
        r = compare_variant(spec, self.base, var)
        self.assertFalse(r["effect_by_claims"])
        self.assertTrue(r["effect_by_new_gap"])
        self.assertTrue(r["effect_observed"])

    def test_control_and_summary(self):
        rows = [compare_variant(self.ctrl, self.base, copy.deepcopy(self.base)),
                compare_variant(self.spec, self.base, _run([("A", "压力2.5MPa", "UNKNOWN"), ("B", "可以开机", "UNKNOWN")])),
                compare_variant(self.spec, self.base, self.base)]
        rows[2]["base_run_id"] = "T-3-r1"
        s = summarize_variant_rows(rows, seed=0)
        self.assertEqual(s["control"]["stability"]["value"], 1.0)
        self.assertEqual(s["by_kind"]["drop_evidence"]["sensitivity"]["numerator"], 1)
        self.assertEqual(s["by_kind"]["drop_evidence"]["sensitivity"]["denominator"], 2)
        self.assertIsNone(s["by_kind"]["unit_change"]["sensitivity"]["value"])  # 分母 0 -> null，不输出 0
        self.assertIsNotNone(s["by_kind"]["unit_change"]["sensitivity"]["reason"])
        ifs = injected_false_support(rows)
        self.assertEqual((ifs["numerator"], ifs["denominator"]), (1, 2))


class TestExperimentWithFakeEngine(unittest.TestCase):
    """假引擎：c2 存在且 load_weight_tons==18、equipment 与 c1 参数一致时，结论“吊装18吨没有问题”为 SUPPORT。"""

    @staticmethod
    def fake_engine(engine_path, records):
        out = {}
        for rec in records:
            out[str(rec["run_id"])] = {"run_id": rec["run_id"], "passed": True, "elapsed_seconds": 0.0,
                                       "output": {"graph": copy.deepcopy(rec), "plan": None}}
        return out

    @staticmethod
    def converter(graph, plan, log_record, method):
        ev = {e.get("id"): e for e in graph.get("trace") or []}
        c2 = ev.get("c2")
        ok = bool(c2) and (c2.get("result") or {}).get("load_weight_tons") == 18
        evid = {}
        claims = [ClaimView("CLM-001", "今天吊装18吨设备没有问题", "SUPPORT" if ok else "UNKNOWN",
                            evidence_ids=["MAT-1"] if c2 else [])]
        if c2:
            evid["MAT-1"] = EvidenceRef("MAT-1", graph["run_id"], event_id="c2", json_path="trace[c2].result.load_weight_tons")
        return RunView(graph["run_id"], graph["case_id"], graph.get("user_question", ""), graph.get("ai_answer", ""),
                       claims=claims, evidence=evid, source={"method": method})

    def test_end_to_end(self):
        rec = fixture_logs()["IND-053-r1"]
        res = run_variants_experiment("unused", [rec], engine_fn=self.fake_engine, converter=self.converter, seed=0)
        self.assertEqual(res["base_failures"], {})
        self.assertEqual(res["engine_settings"], {"mode": "rule", "env": {}})
        rows = {r["variant_id"]: r for r in res["rows"]}
        self.assertTrue(rows["IND-053-r1~drop_evidence~c2"]["effect_observed"])
        self.assertTrue(rows["IND-053-r1~unit_change~c2"]["effect_observed"])
        self.assertFalse(rows["IND-053-r1~entity_swap~c2"]["effect_observed"])  # 假引擎不查对象一致性
        self.assertTrue(rows["IND-053-r1~control_noop~all"]["effect_observed"])
        self.assertIn("v2_grade_base", rows["IND-053-r1~drop_evidence~c2"])
        s = res["summary"]
        self.assertEqual(s["control"]["stability"]["value"], 1.0)
        self.assertEqual(s["overall"]["sensitivity"]["numerator"], 2)
        # experiment_metrics 行与 schema
        vrows = variant_metric_rows(res)
        names = [r["method"] for r in vrows]
        self.assertIn("rule@variant:drop_evidence", names)
        self.assertIn("rule@variant:control_noop", names)
        ctrl = [r for r in vrows if r["method"] == "rule@variant:control_noop"][0]
        self.assertIsNone(ctrl["false_support"])
        doc = build_experiment_metrics([], "t", "t", extra_rows=vrows)
        self.assertEqual(validate_experiment_metrics(doc), [])
        md = render_variants_md(res)
        self.assertIn("control_noop", md)
        csv_rows = variant_csv_rows(res["rows"])
        self.assertIn("CLM-001:SUPPORT->", csv_rows[0]["target_transitions"] + csv_rows[1]["target_transitions"])
        json.dumps(res, ensure_ascii=False)  # 可序列化

    def test_base_failure_recorded(self):
        def broken(engine_path, records):
            return {str(r["run_id"]): {"run_id": r["run_id"], "passed": False, "error_type": "Boom", "error": "x"} for r in records}

        rec = fixture_logs()["IND-053-r1"]
        res = run_variants_experiment("unused", [rec], engine_fn=broken, converter=self.converter)
        self.assertIn("IND-053-r1", res["base_failures"])
        self.assertEqual(res["rows"], [])


if __name__ == "__main__":
    unittest.main()
