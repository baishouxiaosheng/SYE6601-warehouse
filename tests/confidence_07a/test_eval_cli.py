"""评测命令行（eval/cli.py 与 __main__ 分派）：用 5 个验收场景的 01A 夹具 + 试点 gold 子集，离线运行。"""
import contextlib
import csv
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from confidence_07a.__main__ import main as top_main
from confidence_07a.eval import cli
from confidence_07a.eval.report import validate_experiment_metrics

from ._sc_support import ACCEPTANCE_CASES, FIXTURES

ROOT = Path(__file__).resolve().parents[2]
PILOT_GOLD = ROOT / "gold" / "pilot_gold_v0.json"
RUN_IDS = ",".join(f"{c}-r1" for c in ACCEPTANCE_CASES)


def _quiet(fn, *args):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        rc = fn(*args)
    return rc, out.getvalue(), err.getvalue()


class TestEvalCli(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.tmp = Path(tempfile.mkdtemp(prefix="07a_cli_"))
        cls.pred = cls.tmp / "output"
        cls.pred.mkdir()
        for c in ACCEPTANCE_CASES:
            for kind in ("graph", "plan", "scorecard"):
                shutil.copy(FIXTURES / f"{c}_{kind}.json", cls.pred / f"{c}_{kind}.json")
        cls.log = FIXTURES / "logs_5cases.json"
        cls.out = cls.tmp / "eval"
        cls.rc, cls.stdout, cls.stderr = _quiet(top_main, [
            "eval", "--gold", str(PILOT_GOLD), "--log", str(cls.log), "--pred", f"rule={cls.pred}",
            "--run-ids", RUN_IDS, "--placeholder", "llm_only", "--placeholder", "hybrid",
            "--gold-version", "pilot_gold_v0", "--out", str(cls.out)])

    @classmethod
    def tearDownClass(cls):
        shutil.rmtree(cls.tmp, ignore_errors=True)

    def _doc(self, d=None):
        with open((d or self.out) / "experiment_metrics.full.json", "r", encoding="utf-8") as fh:
            return json.load(fh)

    def test_08b_file_is_row_list(self):
        with open(self.out / "experiment_metrics.json", "r", encoding="utf-8") as fh:
            rows = json.load(fh)
        self.assertIsInstance(rows, list)
        self.assertEqual(rows, self._doc()["rows"])
        for r in rows:
            for k in ("method", "false_support", "gap_locate", "insufficient_as_err", "note"):
                self.assertIn(k, r)

    def test_outputs_exist_and_schema(self):
        self.assertEqual(self.rc, 0, self.stderr)
        for name in ("experiment_metrics.json", "experiment_metrics.full.json", "report.md", "per_claim.csv", "per_run.csv", "evals.json"):
            self.assertTrue((self.out / name).is_file(), name)
        doc = self._doc()
        self.assertEqual(validate_experiment_metrics(doc), [])
        methods = [r["method"] for r in doc["rows"]]
        self.assertEqual(methods, ["rule", "rule+v1", "rule+v2", "llm_only", "hybrid"])

    def test_placeholders_are_null(self):
        rows = {r["method"]: r for r in self._doc()["rows"]}
        for m in ("llm_only", "hybrid"):
            self.assertIsNone(rows[m]["false_support"])
            self.assertIsNone(rows[m]["gap_locate"])
            self.assertIsNone(rows[m]["insufficient_as_err"])
            self.assertIn("未运行", rows[m]["note"])

    def test_ind053_false_support_exposed(self):
        """需求 §6 验收：IND-053“吊装18吨没有问题”上游判 SUPPORT，评测应把它计入 FSR，而不是在评分层修正。"""
        rows = {r["method"]: r for r in self._doc()["rows"]}
        fs = rows["rule"]["metrics"]["false_support_strict"]
        self.assertGreaterEqual(fs["numerator"], 1)
        self.assertGreater(fs["denominator"], 0)
        with open(self.out / "per_claim.csv", "r", encoding="utf-8", newline="") as fh:
            pc = [r for r in csv.DictReader(fh) if r["method"] == "rule"]
        hit = [r for r in pc if r["run_id"] == "IND-053-r1" and r["false_support"] == "True"]
        self.assertTrue(any("18吨" in r["answer_span"] for r in hit))

    def test_scorecard_rows_differ_only_at_run_level(self):
        rows = {r["method"]: r for r in self._doc()["rows"]}
        for m in ("false_support_strict", "gap_f1", "status_accuracy"):
            self.assertEqual(rows["rule+v1"]["metrics"][m]["value"], rows["rule+v2"]["metrics"][m]["value"])
        self.assertIsNone(rows["rule"]["metrics"]["severe_recall"]["value"])
        self.assertIsNotNone(rows["rule+v2"]["metrics"]["severe_recall"]["denominator"])
        md = (self.out / "report.md").read_text(encoding="utf-8")
        self.assertIn("成绩单层对照", md)
        self.assertIn("给上游的问题清单", md)

    def test_report_subcommand_rebuilds(self):
        out2 = self.tmp / "report2"
        rc, _, err = _quiet(top_main, ["report", "--evals", str(self.out / "evals.json"), "--out", str(out2),
                                       "--placeholder", "llm_only"])
        self.assertEqual(rc, 0, err)
        doc = self._doc(out2)
        self.assertEqual([r["method"] for r in doc["rows"]], ["rule", "rule+v1", "rule+v2", "llm_only"])
        self.assertEqual(doc["gold_version"], "pilot_gold_v0")

    def test_report_with_variants_json(self):
        fake_variants = {
            "variants_version": "t", "engine_settings": {"mode": "rule", "env": {}}, "n_base_runs": 1, "method": "rule",
            "specs": [], "base_failures": {},
            "rows": [{"variant_id": "a~control_noop~all", "base_run_id": "IND-053-r1", "kind": "control_noop",
                      "engine_ok": True, "applicable": True, "effect_observed": True},
                     {"variant_id": "a~drop_evidence~c2", "base_run_id": "IND-053-r1", "kind": "drop_evidence",
                      "engine_ok": True, "applicable": True, "effect_observed": True,
                      "n_target_claims": 1, "n_target_changed": 1, "n_target_missing": 0}],
        }
        vp = self.tmp / "variants.json"
        vp.write_text(json.dumps(fake_variants, ensure_ascii=False), encoding="utf-8")
        out3 = self.tmp / "report3"
        rc, _, err = _quiet(cli.main, ["report", "--evals", str(self.out / "evals.json"), "--variants", str(vp),
                                       "--out", str(out3)])
        self.assertEqual(rc, 0, err)
        rows = {r["method"]: r for r in self._doc(out3)["rows"]}
        self.assertEqual(rows["rule@variant:drop_evidence"]["false_support"], 0.0)
        self.assertIsNone(rows["rule@variant:control_noop"]["false_support"])
        self.assertIn("受控变体结果", (out3 / "report.md").read_text(encoding="utf-8"))

    def test_missing_sources_and_bad_dir(self):
        rc, _, err = _quiet(cli.main, ["eval", "--gold", str(PILOT_GOLD), "--out", str(self.tmp / "x")])
        self.assertEqual(rc, 2)
        with self.assertRaises(ValueError):
            cli.load_method_dir(str(self.tmp), None, "rule")

    def test_variants_requires_engine(self):
        with self.assertRaises(SystemExit):
            _quiet(cli.main, ["variants", "--log", str(self.log), "--out", str(self.tmp / "v")])

    def test_crosscheck_dispatch_is_off_by_default(self):
        out = self.tmp / "cc"
        rc, _, err = _quiet(top_main, ["crosscheck", "--case-notes", "does-not-matter.md", "--v2-dir", str(self.tmp),
                                       "--out", str(out)])
        self.assertEqual(rc, 3)
        self.assertFalse(out.exists())

    def test_llm_judge_dispatch_dry_run(self):
        rc, out, _ = _quiet(top_main, ["llm-judge", "--log", str(self.log), "--run-ids", "IND-053-r1", "--dry-run"])
        self.assertEqual(rc, 0)
        self.assertIn("[dry-run]", out)


if __name__ == "__main__":
    unittest.main()
