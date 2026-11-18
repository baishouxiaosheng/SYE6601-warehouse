"""Schema 合规、确定性、渲染、CLI（score / score-dir / diff / eval 桩）。"""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from confidence_07a.__main__ import main as cli_main
from confidence_07a.render import render_diff_md, render_scorecard_md
from confidence_07a.scorecard import diff_scorecards, load_policy, policy_sha256, score_run

from ._sc_support import ACCEPTANCE_CASES, FIXTURES, SCHEMA_PATH, fixture_run, make_run, read_json, validate


def _dump(obj) -> str:
    return json.dumps(obj, ensure_ascii=False, sort_keys=True)


class SchemaTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.schema = read_json(SCHEMA_PATH)

    def test_schema_is_draft07(self):
        self.assertEqual(self.schema["$schema"], "http://json-schema.org/draft-07/schema#")

    def test_real_scorecards_valid(self):
        for case in ACCEPTANCE_CASES:
            with self.subTest(case=case):
                card = score_run(fixture_run(case))
                self.assertEqual(validate(card, self.schema), [])

    def test_edge_scorecards_valid(self):
        for run in (make_run([], goals=[]), make_run([{"id": "CLM-001", "text": "可以开机", "status": "MISSING_RULE", "strength": "approval"}])):
            self.assertEqual(validate(score_run(run), self.schema), [])

    def test_validator_catches_errors(self):
        card = score_run(fixture_run("IND-043"))
        bad = json.loads(json.dumps(card))
        bad["grade"] = "A"
        bad["support_score"] = 1.5
        del bad["scope_note"]
        bad["claims"][0]["status"] = "MAYBE"
        errs = validate(bad, self.schema)
        self.assertTrue(any("grade" in e for e in errs))
        self.assertTrue(any("support_score" in e for e in errs))
        self.assertTrue(any("scope_note" in e for e in errs))
        self.assertTrue(any("claims[0].status" in e for e in errs))


class DeterminismTest(unittest.TestCase):
    def test_same_input_same_output(self):
        for case in ACCEPTANCE_CASES:
            a = _dump(score_run(fixture_run(case)))
            b = _dump(score_run(fixture_run(case)))
            self.assertEqual(a, b, case)

    def test_policy_hash_stable_and_sensitive(self):
        p = load_policy()
        self.assertEqual(policy_sha256(p), policy_sha256(load_policy()))
        q = json.loads(json.dumps(p))
        q["weights"]["support"] = 0.6
        self.assertNotEqual(policy_sha256(p), policy_sha256(q))
        self.assertEqual(score_run(fixture_run("IND-002"), p)["policy_sha256"], policy_sha256(p))

    def test_policy_is_provisional_and_versioned(self):
        p = load_policy()
        self.assertEqual(p["status"], "PROVISIONAL")
        for k in ("version", "weights", "expression_matrix", "high_risk", "expression", "grades", "gates"):
            self.assertIn(k, p)
        for k in ("declared_unknown_lexicon", "scoped_partial_lexicon", "hedge_lexicon"):
            self.assertTrue(p["expression"][k])


class RenderTest(unittest.TestCase):
    def test_markdown_contains_required_sections(self):
        card = score_run(fixture_run("IND-053"))
        md = render_scorecard_md(card)
        for s in ("证据不足", "严重 SEVERE_CONTRADICTION", "三个维度", "逐结论", "缺口", "补证计划",
                  "建链风险", "不是回答正确的概率", "trace[c1].result.restriction", "/5 = 0.6000"):
            self.assertIn(s, md)
        d = diff_scorecards(card, card)
        md2 = render_diff_md(d)
        self.assertIn("等级", md2)
        self.assertIn("补证未改变任何结论状态", md2)


class CliTest(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="sc07a_cli_"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def run_cli(self, argv):
        buf, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(buf), contextlib.redirect_stderr(err):
            try:
                code = cli_main(argv)
            except SystemExit as exc:  # argparse 报错
                code = exc.code
        return code, buf.getvalue(), err.getvalue()

    def test_score_score_dir_and_diff(self):
        out_dir = self.tmp / "output"
        out_dir.mkdir()
        for case in ("IND-024", "IND-043"):
            for k in ("graph", "plan", "scorecard"):
                shutil.copy(FIXTURES / f"{case}_{k}.json", out_dir / f"{case}_{k}.json")
        logs = str(FIXTURES / "logs_5cases.json")

        code, _, _ = self.run_cli(["score", "--graph", str(out_dir / "IND-043_graph.json"), "--log", logs,
                                   "--out-json", str(self.tmp / "s.json"), "--out-md", str(self.tmp / "s.md")])
        self.assertEqual(code, 0)
        card = read_json(self.tmp / "s.json")
        self.assertEqual(card["run_id"], "IND-043-r1")
        self.assertTrue((self.tmp / "s.md").read_text(encoding="utf-8").startswith("# 置信度成绩单 v2"))

        code, _, _ = self.run_cli(["score-dir", "--input", str(out_dir), "--log", logs, "--out", str(self.tmp / "sc"),
                                   "--b-review", str(FIXTURES / "b_review_local_5cases.json")])
        self.assertEqual(code, 0)
        with open(self.tmp / "sc" / "summary.csv", "r", encoding="utf-8") as fh:
            lines = fh.read().splitlines()
        self.assertEqual(len(lines), 3)
        self.assertTrue(lines[0].startswith("run_id,case_id,method,grade,high_risk_alert"))
        self.assertIn("IND-024-r1,IND-024,rule,INSUFFICIENT,1", lines[1])
        self.assertIn(",E,", lines[1])  # v1 基线等级
        c24 = read_json(self.tmp / "sc" / "IND-024-r1.json")
        self.assertEqual(c24["source"]["b_review"]["matched_claims"], ["CLM-001"])

        code, _, _ = self.run_cli(["diff", "--before", str(self.tmp / "s.json"), "--after", str(self.tmp / "sc" / "IND-043-r1.json"),
                                   "--out-json", str(self.tmp / "d.json"), "--out-md", str(self.tmp / "d.md")])
        self.assertEqual(code, 0)
        d = read_json(self.tmp / "d.json")
        self.assertFalse(d["grade"]["changed"])
        self.assertEqual(d["warnings"], [])

    def test_eval_stub_dispatch_or_message(self):
        code, _, err = self.run_cli(["eval", "--help-not-real"])
        self.assertIn(code, (0, 1, 2))


if __name__ == "__main__":
    unittest.main()
