"""01A v1 成绩单 vs 07A v2 成绩单对比（只读，输出 Markdown）。

用法（在 deliverable/ 下）：
  python -I tools/compare_v1_v2.py --v1-dir <01A output 目录> --v2-dir artifacts/scorecards_v2/rule \
      --out artifacts/scorecards_v2/v1_vs_v2.md
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from typing import Dict, List, Optional


def _read(p: Path) -> dict:
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _mean(xs: List[Optional[float]]) -> str:
    v = [x for x in xs if x is not None]
    return f"{sum(v) / len(v):.3f}（n={len(v)}）" if v else "null"


V1_ORDER = ["A", "B", "C", "D", "E"]
V2_ORDER = ["INSUFFICIENT", "QUALIFIED", "SUFFICIENT_IN_SCOPE"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--v1-dir", required=True)
    ap.add_argument("--v2-dir", required=True)
    ap.add_argument("--out", required=True)
    a = ap.parse_args(argv)
    v1_dir, v2_dir = Path(a.v1_dir), Path(a.v2_dir)

    rows = []
    for p in sorted(v2_dir.glob("*.json")):
        v2 = _read(p)
        if v2.get("scorecard_version") != "07a-scorecard-v2":
            continue
        v1p = v1_dir / f"{v2['case_id']}_scorecard.json"
        if not v1p.exists():
            continue
        v1 = _read(v1p)
        d1 = v1.get("dimensions") or {}
        rows.append(
            {
                "case": v2["case_id"],
                "v1_grade": v1.get("grade"),
                "v1_overall": v1.get("overall"),
                "v1_sup": (d1.get("evidence_support") or {}).get("score"),
                "v1_cov": (d1.get("question_coverage") or {}).get("score"),
                "v1_unc": (d1.get("uncertainty_accuracy") or {}).get("score"),
                "v1_flags": v1.get("severity_flags") or [],
                "v2_grade": v2["grade"],
                "v2_alert": v2["high_risk_alert"],
                "v2_overall": v2["overall"],
                "v2_sup": v2["support_score"],
                "v2_cov": v2["coverage_score"],
                "v2_unc": v2["uncertainty_score"],
                "v2_blockers": sorted({b["code"] for b in v2["blockers"]}),
                "v2_severe": [s["claim_id"] + "「" + s["text"][:18] + "」" for s in v2["severe_issues"]],
                "v2_unc_cells": (v2["dimensions"]["uncertainty"].get("breakdown") or {}).get("cells") or {},
                "n_claims": len(v2["claims"]),
                "n_unchecked": len(v2["build_risks"]["claims_without_checks"]),
            }
        )
    n = len(rows)
    L: List[str] = []
    L.append("# 01A v1 成绩单 vs 07A v2 成绩单（工业 60 条，rule 模式）")
    L.append("")
    L.append("> 两版分数都只是“基于现有日志的证据审核结果”，不是正确概率；v2 的权重/阈值为 PROVISIONAL。"
             "结论状态两版相同（都来自 01A），差异只来自评分口径。")
    L.append("")
    L.append(f"- 样本：{n} 条运行；v1 来源 01A `output/<case>_scorecard.json`，v2 来源 `artifacts/scorecards_v2/rule/`。")
    L.append("")

    L.append("## 1. 等级分布")
    c1 = Counter(r["v1_grade"] for r in rows)
    c2 = Counter(r["v2_grade"] for r in rows)
    L.append("| v1 等级 | " + " | ".join(V1_ORDER) + " |")
    L.append("|---|" + "---|" * len(V1_ORDER))
    L.append("| 运行数 | " + " | ".join(str(c1.get(g, 0)) for g in V1_ORDER) + " |")
    L.append("")
    L.append("| v2 等级 | " + " | ".join(V2_ORDER) + " | high_risk_alert |")
    L.append("|---|" + "---|" * (len(V2_ORDER) + 1))
    L.append("| 运行数 | " + " | ".join(str(c2.get(g, 0)) for g in V2_ORDER) + f" | {sum(1 for r in rows if r['v2_alert'])} |")
    L.append("")
    L.append("交叉表（行 v1，列 v2）：")
    L.append("")
    L.append("| v1 \\ v2 | " + " | ".join(V2_ORDER) + " |")
    L.append("|---|" + "---|" * len(V2_ORDER))
    for g1 in V1_ORDER:
        L.append(f"| {g1} | " + " | ".join(
            str(sum(1 for r in rows if r["v1_grade"] == g1 and r["v2_grade"] == g2)) for g2 in V2_ORDER) + " |")
    L.append("")

    L.append("## 2. 维度均值")
    L.append("| 维度 | v1 均值 | v2 均值 | 口径差异 |")
    L.append("|---|---|---|---|")
    L.append(f"| 证据支持度 | {_mean([r['v1_sup'] for r in rows])} | {_mean([r['v2_sup'] for r in rows])} | v1 UNKNOWN 记 0.5、MISSING_RULE 记 0.2，分母为全部结论；v2 UNKNOWN 记 0，分母只含作出断言的结论 |")
    L.append(f"| 问题回应覆盖度 | {_mean([r['v1_cov'] for r in rows])} | {_mean([r['v2_cov'] for r in rows])} | v2 增加“明确声明无法确定”也算回应；对无上游关联的目标做词面兜底并标记 |")
    L.append(f"| 不确定性表达准确性 | {_mean([r['v1_unc'] for r in rows])} | {_mean([r['v2_unc'] for r in rows])} | v1 只看是否含 hedge 词；v2 按 措辞×状态 矩阵，如实声明无法确定得满分 |")
    L.append(f"| 综合分（参考） | {_mean([r['v1_overall'] for r in rows])} | {_mean([r['v2_overall'] for r in rows])} | v2 有阻断项时 overall_display=false，不对外显示 |")
    L.append("")

    v1_high = sum(1 for r in rows for f in r["v1_flags"] if f.get("severity") == "HIGH")
    v1_any = sum(len(r["v1_flags"]) for r in rows)
    L.append("## 3. 严重问题标记")
    L.append(f"- v1 severity_flags：{v1_any} 个（HIGH {v1_high}），分布在 {sum(1 for r in rows if r['v1_flags'])} 条运行。")
    L.append(f"- v2 severe_issues：{sum(len(r['v2_severe']) for r in rows)} 个，high_risk_alert=true 的运行 {sum(1 for r in rows if r['v2_alert'])} 条。")
    L.append("")
    L.append("| 运行 | v1 标记 | v2 严重问题 |")
    L.append("|---|---|---|")
    for r in rows:
        if r["v1_flags"] or r["v2_severe"]:
            v1s = "; ".join(f"{f.get('claim')}:{f.get('status')}/{f.get('severity')}" for f in r["v1_flags"]) or "—"
            L.append(f"| {r['case']} | {v1s} | {'; '.join(r['v2_severe']) or '—'} |")
    L.append("")

    # 分歧：v1 高等级但 v2 证据不足；或 v1 低等级但 v2 只附保留
    def rank1(g):
        return V1_ORDER.index(g) if g in V1_ORDER else 9

    L.append("## 4. v1 与 v2 分歧最大的运行")
    L.append("定义：(a) v1 为 A/B 但 v2 为 INSUFFICIENT；(b) v1 为 D/E 但 v2 不是 INSUFFICIENT；"
             "另按 |v1 综合分 − v2 综合分| 列出前 10。")
    L.append("")
    a_rows = [r for r in rows if rank1(r["v1_grade"]) <= 1 and r["v2_grade"] == "INSUFFICIENT"]
    b_rows = [r for r in rows if rank1(r["v1_grade"]) >= 3 and r["v2_grade"] != "INSUFFICIENT"]
    L.append(f"(a) v1 高 / v2 证据不足：{len(a_rows)} 条")
    L.append("")
    L.append("| 运行 | v1 | v2 | v2 阻断项 | v2 严重问题 |")
    L.append("|---|---|---|---|---|")
    for r in a_rows:
        L.append(f"| {r['case']} | {r['v1_grade']} ({r['v1_overall']:.3f}) | {r['v2_grade']} | {' '.join(r['v2_blockers'])} | {'; '.join(r['v2_severe']) or '—'} |")
    L.append("")
    L.append(f"(b) v1 低 / v2 未阻断：{len(b_rows)} 条")
    L.append("")
    L.append("| 运行 | v1 | v1 不确定性 | v2 | v2 不确定性 | 说明 |")
    L.append("|---|---|---|---|---|---|")
    for r in b_rows:
        L.append(f"| {r['case']} | {r['v1_grade']} ({r['v1_overall']:.3f}) | {r['v1_unc']:.3f} | {r['v2_grade']} | {r['v2_unc']} | "
                 f"无阻断：没有高风险主结论被反驳/过度断言，也没有 HIGH 缺口落在确定结论上 |")
    L.append("")
    diffs = sorted(
        (r for r in rows if r["v1_overall"] is not None and r["v2_overall"] is not None),
        key=lambda r: (-abs(r["v1_overall"] - r["v2_overall"]), r["case"]),
    )[:10]
    L.append("| 运行 | v1 综合 | v2 综合（计算值） | 差 | v1 支持/覆盖/不确定 | v2 支持/覆盖/不确定 | v2 等级 |")
    L.append("|---|---|---|---|---|---|---|")
    for r in diffs:
        L.append(
            f"| {r['case']} | {r['v1_overall']:.3f} | {r['v2_overall']:.3f} | {r['v2_overall'] - r['v1_overall']:+.3f} | "
            f"{r['v1_sup']:.2f}/{r['v1_cov']:.2f}/{r['v1_unc']:.2f} | {r['v2_sup']}/{r['v2_cov']}/{r['v2_unc']} | {r['v2_grade']} |"
        )
    L.append("")

    cells = Counter()
    for r in rows:
        cells.update(r["v2_unc_cells"])
    L.append("## 5. v2 措辞×状态 分布（全部结论）")
    L.append("| 单元格 | 结论数 |")
    L.append("|---|---|")
    for k, v in sorted(cells.items(), key=lambda kv: (-kv[1], kv[0])):
        L.append(f"| {k} | {v} |")
    L.append("")
    tot = sum(r["n_claims"] for r in rows)
    unchk = sum(r["n_unchecked"] for r in rows)
    L.append("## 6. 解读与局限")
    L.append("- v2 总体更严格：UNKNOWN 不再给 0.5 分，且“先判门槛再汇总”，高风险主结论被反驳或在证据不足时被写成确定结论会直接判为证据不足，不会被其他正确细节的平均分掩盖。")
    L.append(f"- v2 的不确定性维度把“如实声明无法确定”计为满分，修正了 v1 将其判为过于含糊而扣分的问题；但 01A rule 模式下 {unchk}/{tot} 条结论没有任何 check 命中（多数因此默认为 UNKNOWN），这部分在 v2 中仍按 DEFINITE×UNKNOWN 计为过度断言，"
             "breakdown.checked_only 给出排除这些结论后的参考值。")
    L.append("- 两版都无法发现上游判错：例如 IND-053 “今天吊装18吨设备没有问题”被 01A 判为 SUPPORT（只核对了数值 18），v1/v2 都按 SUPPORT 计分；v2 仍因“可以正常作业”被 REFUTE 而触发严重问题。需要独立 gold 标注后用评测指标（错误结论被判支持比例）暴露。")
    L.append("- 等级线、权重、高风险词典均为 PROVISIONAL，尚未用独立评估数据校准。")
    L.append("")
    with open(a.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write("\n".join(L))
    print(f"写出 {a.out}（{n} 条）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
