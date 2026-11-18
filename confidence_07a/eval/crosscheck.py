"""外部对照（spec §0：默认关闭、单独隔离、需团队确认）。

**外部对照，不参与评分与标注；需团队确认是否允许。**

- 只有显式传入 `--allow-case-notes`（或 API 参数 allow_case_notes=True）才会读取《案例说明 md》。
- 解析器只抽取每条运行的**运行级类别标签**（正确且充分 / 证据不足时如实说明 / 存在错误），
  不复制案例说明中的任何逐案文字（问题概述、机制、解释等一律丢弃）。
- 输出只与 07A 成绩单（v2 grade / high_risk_alert，可选 v1 grade）做分布对照，写入独立目录；
  成绩单、gold、评测指标均不读取本模块的输出。
"""
from __future__ import annotations

import argparse
import datetime as _dt
import json
import re
import sys
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional, Sequence

BANNER = "外部对照，不参与评分与标注；需团队确认是否允许"
CATEGORIES = ("正确且充分", "证据不足时如实说明", "存在错误")
_LABEL_MAP = [
    (re.compile(r"正确且充分"), "正确且充分"),
    (re.compile(r"证据不足"), "证据不足时如实说明"),
    (re.compile(r"问题样本|存在(?:幻觉|错误)|错误"), "存在错误"),
]
_ROW_RE = re.compile(r"^\|\s*(IND-\d{3})\s*\|[^|]*\|\s*([^|]+?)\s*\|")
_LIST_RE = re.compile(r"^-\s*(正确且充分[^：:]*|证据不足[^：:]*|存在[^：:]*)[：:].*?（(.*?)）")
_RANGE_RE = re.compile(r"IND-(\d{3})\s*至\s*IND-(\d{3})")
_ID_RE = re.compile(r"IND-(\d{3})")


class CaseNotesNotAllowed(PermissionError):
    pass


def _label(text: str) -> Optional[str]:
    for rx, lab in _LABEL_MAP:
        if rx.search(text):
            return lab
    return None


def parse_case_categories(md_text: str) -> Dict[str, Any]:
    """从案例说明 md 抽取 case_id -> 类别标签。

    主来源：“全60条索引”表格的“表现类别”列（第 3 列）；辅助来源：“数量与表现分布”列表。
    两者不一致时以表格为准并记录 disagreements（只记 case_id 与两个标签）。
    """
    table: Dict[str, str] = {}
    listing: Dict[str, str] = {}
    for line in md_text.splitlines():
        m = _ROW_RE.match(line.strip())
        if m:
            lab = _label(m.group(2))
            if lab:
                table.setdefault(m.group(1), lab)
            continue
        m = _LIST_RE.match(line.strip())
        if m:
            lab = _label(m.group(1))
            body = m.group(2)
            ids = set()
            for a, b in _RANGE_RE.findall(body):
                ids |= {f"IND-{i:03d}" for i in range(int(a), int(b) + 1)}
            ids |= {f"IND-{x}" for x in _ID_RE.findall(body)}
            for cid in ids:
                if lab:
                    listing.setdefault(cid, lab)
    cats = dict(table)
    for cid, lab in listing.items():
        cats.setdefault(cid, lab)
    dis = [{"case_id": c, "table": table[c], "listing": listing[c]}
           for c in sorted(set(table) & set(listing)) if table[c] != listing[c]]
    return {"categories": dict(sorted(cats.items())), "n_table": len(table), "n_listing": len(listing),
            "disagreements": dis}


def load_case_categories(md_path, allow_case_notes: bool = False) -> Dict[str, Any]:
    if not allow_case_notes:
        raise CaseNotesNotAllowed("外部对照默认关闭：需显式传入 --allow-case-notes（并经团队确认）才读取案例说明")
    with open(md_path, "r", encoding="utf-8") as fh:
        return parse_case_categories(fh.read())


def _read_cards(d: Path) -> Dict[str, Dict[str, Any]]:
    out = {}
    for p in sorted(d.glob("*.json")):
        try:
            with open(p, "r", encoding="utf-8") as fh:
                c = json.load(fh)
        except (OSError, json.JSONDecodeError):
            continue
        if isinstance(c, dict) and c.get("case_id"):
            out[str(c["case_id"])] = c
    return out


def crosscheck(categories: Mapping[str, str], v2_cards: Mapping[str, Mapping[str, Any]],
               v1_cards: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Dict[str, Any]:
    """类别 × v2 grade / high_risk_alert（× v1 grade）列联表。只输出 case_id 与标签。"""
    rows = []
    for cid in sorted(set(categories) & set(v2_cards)):
        c2 = v2_cards[cid]
        rows.append({"case_id": cid, "category": categories[cid], "v2_grade": c2.get("grade"),
                     "v2_high_risk_alert": bool(c2.get("high_risk_alert")),
                     "v1_grade": (v1_cards or {}).get(cid, {}).get("grade") if v1_cards else None})
    tab_grade: Dict[str, Counter] = {k: Counter() for k in CATEGORIES}
    tab_alert: Dict[str, Counter] = {k: Counter() for k in CATEGORIES}
    tab_v1: Dict[str, Counter] = {k: Counter() for k in CATEGORIES}
    for r in rows:
        tab_grade[r["category"]][r["v2_grade"]] += 1
        tab_alert[r["category"]]["alert" if r["v2_high_risk_alert"] else "no_alert"] += 1
        if r["v1_grade"]:
            tab_v1[r["category"]][r["v1_grade"]] += 1

    def ratio(num, den):
        return {"numerator": num, "denominator": den, "value": round(num / den, 6) if den else None,
                "reason": None if den else "该类别没有运行"}

    err = [r for r in rows if r["category"] == "存在错误"]
    ok = [r for r in rows if r["category"] != "存在错误"]
    summary = {
        "error_runs_alert_rate": ratio(sum(r["v2_high_risk_alert"] for r in err), len(err)),
        "error_runs_insufficient_rate": ratio(sum(r["v2_grade"] == "INSUFFICIENT" for r in err), len(err)),
        "non_error_runs_alert_rate": ratio(sum(r["v2_high_risk_alert"] for r in ok), len(ok)),
        "non_error_runs_insufficient_rate": ratio(sum(r["v2_grade"] == "INSUFFICIENT" for r in ok), len(ok)),
    }
    return {
        "banner": BANNER,
        "n_runs": len(rows),
        "category_counts": dict(Counter(r["category"] for r in rows)),
        "category_x_v2_grade": {k: dict(v) for k, v in tab_grade.items()},
        "category_x_v2_alert": {k: dict(v) for k, v in tab_alert.items()},
        "category_x_v1_grade": {k: dict(v) for k, v in tab_v1.items()} if v1_cards else None,
        "summary": summary,
        "per_run": rows,
    }


def render_md(res: Mapping[str, Any], meta: Mapping[str, Any]) -> str:
    L = [f"# 外部对照（可选）", "", f"> **{BANNER}**", "",
         "- 来源：《案例说明 md》中每条运行的表现类别标签（仅标签；未复制任何逐案文字）。",
         "- 用途：只用于观察 07A v2 成绩单等级/高风险告警的分布与案例说明作者自报类别是否大体一致；"
         "不作为 gold，不进入 experiment_metrics.json，也不影响任何评分。",
         "- 注意：案例说明是数据生成方的自述，其“存在错误”类别按生成规划划分（IND-021~060），不等于逐结论人工核验。",
         f"- 生成时间：{meta.get('generated_at')}；成绩单目录：{meta.get('v2_dir')}", ""]
    L += ["## 类别 × v2 等级（运行数）", "", "| 类别 | INSUFFICIENT | QUALIFIED | SUFFICIENT_IN_SCOPE | 合计 |", "|---|---|---|---|---|"]
    for k in CATEGORIES:
        c = res["category_x_v2_grade"][k]
        L.append(f"| {k} | {c.get('INSUFFICIENT', 0)} | {c.get('QUALIFIED', 0)} | {c.get('SUFFICIENT_IN_SCOPE', 0)} | {sum(c.values())} |")
    L += ["", "## 类别 × v2 high_risk_alert（运行数）", "", "| 类别 | 告警 | 未告警 |", "|---|---|---|"]
    for k in CATEGORIES:
        c = res["category_x_v2_alert"][k]
        L.append(f"| {k} | {c.get('alert', 0)} | {c.get('no_alert', 0)} |")
    if res.get("category_x_v1_grade"):
        L += ["", "## 类别 × v1 等级（01A 基线，运行数）", "", "| 类别 | A | B | C | D | E |", "|---|---|---|---|---|---|"]
        for k in CATEGORIES:
            c = res["category_x_v1_grade"][k]
            L.append(f"| {k} | " + " | ".join(str(c.get(g, 0)) for g in "ABCDE") + " |")
    L += ["", "## 汇总比例", ""]
    for k, v in res["summary"].items():
        L.append(f"- `{k}`：{v['value']}（{v['numerator']}/{v['denominator']}）")
    L += ["", "解读提示：v2 等级是“现有日志证据审核结果”，不是“回答对错”；“证据不足时如实说明”的运行被判 INSUFFICIENT 属预期"
          "（证据确实不足），而“存在错误”运行未告警、甚至 SUFFICIENT_IN_SCOPE，才是需要回到上游（01A/02B）检查的信号。", ""]
    return "\n".join(L)


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m confidence_07a.eval.crosscheck", description=BANNER)
    ap.add_argument("--case-notes", required=True, help="《案例说明 md》路径")
    ap.add_argument("--v2-dir", required=True, help="v2 成绩单目录（<run_id>.json）")
    ap.add_argument("--v1-dir", help="可选：01A output/ 目录（读取 <case>_scorecard.json）")
    ap.add_argument("--out", required=True)
    ap.add_argument("--allow-case-notes", action="store_true", help="显式允许读取案例说明（默认关闭，需团队确认）")
    a = ap.parse_args(list(argv) if argv is not None else None)
    if not a.allow_case_notes:
        print(f"{BANNER}。默认关闭：未传入 --allow-case-notes，不读取案例说明。", file=sys.stderr)
        return 3
    parsed = load_case_categories(a.case_notes, allow_case_notes=True)
    v2 = _read_cards(Path(a.v2_dir))
    v1 = None
    if a.v1_dir:
        v1 = {}
        for p in sorted(Path(a.v1_dir).glob("*_scorecard.json")):
            with open(p, "r", encoding="utf-8") as fh:
                c = json.load(fh)
            v1[str(c.get("case_id") or p.name.split("_")[0])] = c
    res = crosscheck(parsed["categories"], v2, v1)
    res["parser"] = {"n_table": parsed["n_table"], "n_listing": parsed["n_listing"], "disagreements": parsed["disagreements"]}
    meta = {"generated_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"), "v2_dir": a.v2_dir}
    res["generated_at"] = meta["generated_at"]
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    with open(out / "crosscheck.json", "w", encoding="utf-8") as fh:
        json.dump(res, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(out / "crosscheck.md", "w", encoding="utf-8") as fh:
        fh.write(render_md(res, meta))
    print(f"{BANNER}；已写出 {out}（{res['n_runs']} 条运行）")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
