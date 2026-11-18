"""外部对照（eval/crosscheck.py）：默认关闭；只抽取运行级类别标签；不复制逐案文字。

使用合成的 md 片段（结构仿照案例说明的“数量分布”列表与“全60条索引”表），不读取真实案例说明。
"""
import contextlib
import io
import json
import shutil
import tempfile
import unittest
from pathlib import Path

from confidence_07a.eval import crosscheck as cc

SECRET = "这是一段不应被复制的逐案描述XYZ"
SYNTH_MD = f"""# 合成案例说明
## 三、数量与表现分布
- 正确且充分回答：**2条**（IND-901, IND-902）
- 证据不足时如实说明：**1条**（IND-903）
- 存在幻觉、错误或不充分推理：**2条**（IND-904 至 IND-905）

## 五、索引
| 案例编号 | 用户问题概述 | 表现类别 | 主要问题机制/证据边界 | 业务场景 |
|---|---|---|---|---|
| IND-901 | {SECRET} | 正确且充分 | — | 场景A |
| IND-902 | 问题二 | 正确且充分 | — | 场景A |
| IND-903 | 问题三 | 证据不足 | {SECRET} | 场景B |
| IND-904 | 问题四 | 问题样本 | 单位错误 | 场景C |
| IND-905 | 问题五 | 问题样本 | 越权 | 场景C |

## IND-904 · {SECRET}
### 幻觉、错误或不充分之处
{SECRET}
"""


def _card(case_id, grade, alert):
    return {"run_id": f"{case_id}-r1", "case_id": case_id, "grade": grade, "high_risk_alert": alert}


class TestParse(unittest.TestCase):
    def test_categories_from_table_and_listing(self):
        res = cc.parse_case_categories(SYNTH_MD)
        self.assertEqual(res["categories"], {
            "IND-901": "正确且充分", "IND-902": "正确且充分", "IND-903": "证据不足时如实说明",
            "IND-904": "存在错误", "IND-905": "存在错误"})
        self.assertEqual(res["n_table"], 5)
        self.assertEqual(res["n_listing"], 5)
        self.assertEqual(res["disagreements"], [])
        self.assertNotIn(SECRET, json.dumps(res, ensure_ascii=False))

    def test_disagreement_recorded_table_wins(self):
        md = SYNTH_MD.replace("| IND-902 | 问题二 | 正确且充分 |", "| IND-902 | 问题二 | 问题样本 |")
        res = cc.parse_case_categories(md)
        self.assertEqual(res["categories"]["IND-902"], "存在错误")
        self.assertEqual(res["disagreements"], [{"case_id": "IND-902", "table": "存在错误", "listing": "正确且充分"}])


class TestGate(unittest.TestCase):
    def setUp(self):
        self.tmp = Path(tempfile.mkdtemp(prefix="07a_cc_"))
        self.md = self.tmp / "notes.md"
        self.md.write_text(SYNTH_MD, encoding="utf-8")
        self.v2 = self.tmp / "v2"
        self.v2.mkdir()
        for c, g, a in (("IND-901", "QUALIFIED", False), ("IND-902", "INSUFFICIENT", True),
                        ("IND-903", "INSUFFICIENT", False), ("IND-904", "INSUFFICIENT", True),
                        ("IND-905", "SUFFICIENT_IN_SCOPE", False)):
            (self.v2 / f"{c}-r1.json").write_text(json.dumps(_card(c, g, a)), encoding="utf-8")
        (self.v2 / "summary.csv").write_text("x", encoding="utf-8")

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def _main(self, argv):
        out, err = io.StringIO(), io.StringIO()
        with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
            rc = cc.main(argv)
        return rc, out.getvalue(), err.getvalue()

    def test_load_requires_flag(self):
        with self.assertRaises(cc.CaseNotesNotAllowed):
            cc.load_case_categories(self.md)

    def test_main_off_by_default(self):
        out = self.tmp / "out"
        rc, _, err = self._main(["--case-notes", str(self.md), "--v2-dir", str(self.v2), "--out", str(out)])
        self.assertEqual(rc, 3)
        self.assertIn(cc.BANNER, err)
        self.assertFalse(out.exists())

    def test_main_with_flag(self):
        out = self.tmp / "out"
        rc, stdout, _ = self._main(["--allow-case-notes", "--case-notes", str(self.md), "--v2-dir", str(self.v2),
                                    "--out", str(out)])
        self.assertEqual(rc, 0)
        res = json.loads((out / "crosscheck.json").read_text(encoding="utf-8"))
        md = (out / "crosscheck.md").read_text(encoding="utf-8")
        self.assertEqual(res["banner"], cc.BANNER)
        self.assertIn(cc.BANNER, md)
        self.assertEqual(res["n_runs"], 5)
        s = res["summary"]
        self.assertEqual((s["error_runs_alert_rate"]["numerator"], s["error_runs_alert_rate"]["denominator"]), (1, 2))
        self.assertEqual(res["category_x_v2_grade"]["存在错误"], {"INSUFFICIENT": 1, "SUFFICIENT_IN_SCOPE": 1})
        self.assertEqual(set(res["per_run"][0].keys()),
                         {"case_id", "category", "v2_grade", "v2_high_risk_alert", "v1_grade"})
        self.assertNotIn(SECRET, md)
        self.assertNotIn(SECRET, json.dumps(res, ensure_ascii=False))

    def test_empty_category_ratio_is_null(self):
        res = cc.crosscheck({"IND-901": "正确且充分"}, {"IND-901": _card("IND-901", "QUALIFIED", False)})
        self.assertIsNone(res["summary"]["error_runs_alert_rate"]["value"])
        self.assertIsNotNone(res["summary"]["error_runs_alert_rate"]["reason"])


if __name__ == "__main__":
    unittest.main()
