"""评测输出：experiment_metrics.json（08B 格式）、report.md（中文）、per_claim.csv、per_run.csv。"""
from __future__ import annotations

import csv
import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from ..model import STATUSES
from .metrics import CAVEATS, EVAL_VERSION, METRIC_DEFS, SCORE_SEMANTICS
from .schema_check import load_schema, validate

SCHEMA_NAME = "experiment_metrics.v1.schema.json"

# 08B 三个兼容字段 -> 内部指标名
METRIC_MAPPING = {
    "false_support": "false_support_strict",
    "gap_locate": "gap_f1",
    "insufficient_as_err": "insufficient_as_err",
}

PER_CLAIM_FIELDS = [
    "method", "run_id", "variant_id", "gold_claim_id", "pred_claim_id", "align_method", "align_score",
    "gold_status", "pred_status", "gold_expression", "pred_expression", "is_high_risk", "severe",
    "false_support", "insufficient_as_err", "run_support_score", "answer_span", "pred_text",
]
PER_RUN_FIELDS = [
    "method", "run_id", "case_id", "variant_id", "variant_kind", "stratum", "pred_available", "gold_review_status",
    "n_gold_claims", "n_pred_claims", "n_aligned", "n_missed_gold", "n_extra_pred",
    "n_gold_gaps", "n_pred_gaps", "gap_tp", "param_total", "param_value_hit", "param_key_hit",
    "gold_severe", "high_risk_alert", "alert_source", "grade", "support_score", "support_score_source",
    "answer_has_error", "answer_honest_about_limits", "elapsed_seconds", "model_calls",
]


def _now() -> str:
    return _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds")


def _strip_metric(r: Dict[str, Any]) -> Dict[str, Any]:
    keep = ("numerator", "denominator", "value", "reason", "ci95", "definition", "excluded_unaligned", "ci_valid_resamples")
    return {k: r[k] for k in keep if k in r}


def _note(ev: Dict[str, Any]) -> str:
    n = ev["n"]
    m = ev["metrics"]
    parts = [
        f"n_runs={n['gold_runs']}",
        f"gold结论={n['gold_claims']}",
        f"已对齐={n['aligned_claims']}",
        f"FSR分母={m['false_support_strict']['denominator']}",
        f"IAE分母={m['insufficient_as_err']['denominator']}",
        "gap_locate=缺口定位F1",
    ]
    if n.get("gold_runs_draft"):
        parts.append(f"gold 有 {n['gold_runs_draft']} 个 DRAFT 运行（AI 起草未复核）")
    if n.get("pred_runs_missing"):
        parts.append(f"{n['pred_runs_missing']} 个运行无预测")
    parts.append("样本小；不是概率")
    return "；".join(parts)


def build_experiment_metrics(
    evals: Sequence[Dict[str, Any]],
    data_version: Optional[str] = None,
    gold_version: Optional[str] = None,
    generated_at: Optional[str] = None,
    extra_rows: Optional[Sequence[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """把多个方法的 evaluate() 结果组装为 experiment_metrics.v1。

    extra_rows：附加行（如受控变体行、未运行方法的占位行），须自带 method/三项 08B 字段/note。"""
    rows = []
    for ev in evals:
        m = ev["metrics"]
        row: Dict[str, Any] = {
            "method": ev["method"],
            "false_support": m[METRIC_MAPPING["false_support"]]["value"],
            "gap_locate": m[METRIC_MAPPING["gap_locate"]]["value"],
            "insufficient_as_err": m[METRIC_MAPPING["insufficient_as_err"]]["value"],
            "note": _note(ev),
            "n_runs": ev["n"]["gold_runs"],
            "n_gold_claims": ev["n"]["gold_claims"],
            "n_aligned_claims": ev["n"]["aligned_claims"],
            "gold_runs_draft": ev["n"].get("gold_runs_draft", 0),
            "metric_mapping": dict(METRIC_MAPPING),
            "metrics": {k: _strip_metric(v) for k, v in m.items()},
            "strata": {s: {"n_runs": v["n_runs"], "metrics": {k: _strip_metric(x) for k, x in v["metrics"].items()}}
                       for s, v in (ev.get("strata") or {}).items()},
            "cost": ev.get("cost") or {},
        }
        rows.append(row)
    for r in extra_rows or []:
        rows.append(dict(r))
    return {
        "schema": "experiment_metrics.v1",
        "generated_at": generated_at or _now(),
        "data_version": data_version,
        "gold_version": gold_version,
        "eval_version": EVAL_VERSION,
        "score_semantics": SCORE_SEMANTICS,
        "caveats": list(CAVEATS),
        "rows": rows,
    }


def validate_experiment_metrics(doc: Dict[str, Any]) -> List[str]:
    return validate(doc, load_schema(SCHEMA_NAME))


# ---------------------------------------------------------------------------
# Markdown
# ---------------------------------------------------------------------------

def _fmt(r: Dict[str, Any]) -> str:
    if r.get("value") is None:
        return f"null（{r.get('numerator')}/{r.get('denominator')}）"
    ci = r.get("ci95")
    cis = f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else ""
    return f"{r['value']:.3f}{cis}（{r['numerator']}/{r['denominator']}）"


def _cell(s: Any) -> str:
    return str(s).replace("|", "\\|").replace("\n", " ")


def render_markdown(
    evals: Sequence[Dict[str, Any]],
    doc: Dict[str, Any],
    extra_notes: Optional[Sequence[str]] = None,
    extra_sections: Optional[Sequence[str]] = None,
) -> str:
    L: List[str] = []
    L.append("# 07A 离线评测报告")
    L.append("")
    L.append(f"- 生成时间：{doc['generated_at']}；评测版本：{EVAL_VERSION}")
    L.append(f"- 数据版本：{doc.get('data_version')}；gold 版本：{doc.get('gold_version')}")
    L.append(f"- 分数含义：{SCORE_SEMANTICS}")
    L.append("")
    L.append("## 注意事项（必读）")
    L.append("")
    for c in CAVEATS:
        L.append(f"- {c}")
    for c in extra_notes or []:
        L.append(f"- {c}")
    L.append("- 结论级指标只在已对齐结论上计算；未对齐（漏抽）的 gold 结论数见 excluded_unaligned 与抽取覆盖率。")
    L.append("- 置信区间为按运行聚类的百分位 bootstrap；分母为 0 的指标输出 null，不输出 0。")
    L.append("")
    L.append("## 样本量")
    L.append("")
    L.append("| 方法 | gold 运行 | 其中 DRAFT | 有预测 | 无预测 | gold 结论 | 预测结论 | 已对齐 | gold 缺口 | 预测缺口 | 成绩单 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    for ev in evals:
        n = ev["n"]
        L.append(f"| {ev['method']} | {n['gold_runs']} | {n['gold_runs_draft']} | {n['pred_runs_matched']} | {n['pred_runs_missing']} | "
                 f"{n['gold_claims']} | {n['pred_claims']} | {n['aligned_claims']} | {n['gold_gaps']} | {n['pred_gaps']} | "
                 f"{'有' if n['scorecards_provided'] else '无'} |")
    L.append("")
    L.append("## 主要指标（值 [95% CI]（分子/分母））")
    L.append("")
    methods = [ev["method"] for ev in evals]
    L.append("| 指标 | " + " | ".join(methods) + " |")
    L.append("|---|" + "---|" * len(methods))
    for name in METRIC_DEFS:
        L.append(f"| {name} | " + " | ".join(_fmt(ev["metrics"][name]) for ev in evals) + " |")
    L.append("")
    eval_methods = set(methods)
    others = [r for r in doc.get("rows") or [] if r.get("method") not in eval_methods]
    if others:
        L.append("")
        L.append("### 其他行（受控变体 / 未运行的方法）")
        L.append("")
        L.append("| method | false_support | gap_locate | insufficient_as_err | 说明 |")
        L.append("|---|---|---|---|---|")
        for r in others:
            f3 = ["null" if r.get(k) is None else f"{r[k]:.3f}" for k in ("false_support", "gap_locate", "insufficient_as_err")]
            L.append(f"| {r['method']} | " + " | ".join(f3) + f" | {_cell(r.get('note', ''))} |")
        L.append("")
    L.append("08B 兼容字段映射：" + "，".join(f"`{k}` = `{v}`" for k, v in METRIC_MAPPING.items()) + "。")
    L.append("")
    for ev in evals:
        L.append(f"## 方法 `{ev['method']}` 明细")
        L.append("")
        L.append("### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）")
        L.append("")
        L.append("| gold \\ pred | " + " | ".join(STATUSES) + " |")
        L.append("|---|" + "---|" * len(STATUSES))
        for i, g in enumerate(STATUSES):
            L.append(f"| {g} | " + " | ".join(str(x) for x in ev["confusion"]["matrix"][i]) + " |")
        L.append("")
        if ev["calibration"]["table"]:
            L.append("### 校准表（描述性，样本小；support_score 不是正确概率）")
            L.append("")
            L.append("| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |")
            L.append("|---|---|---|---|---|")
            for r in ev["calibration"]["table"]:
                L.append(f"| {r['bin']} | {r['range']} | {r['n_claims']} | {r['mean_support_score']} | {r['gold_support_rate']} |")
            L.append("")
            L.append(f"ECE：{_fmt(ev['calibration']['ece'])}")
            L.append("")
        rl = ev["run_level"].get("grade_vs_answer_has_error") or {}
        if rl:
            L.append("### 等级 × gold answer_has_error（运行数）")
            L.append("")
            L.append("| 等级 | 有错误 | 无错误 | 未标 |")
            L.append("|---|---|---|---|")
            for g, v in sorted(rl.items()):
                L.append(f"| {g} | {v['true']} | {v['false']} | {v['na']} |")
            L.append("")
        if ev.get("strata"):
            L.append("### 分层（自然运行 vs 受控变体）")
            L.append("")
            L.append("| 层 | 运行数 | FSR严格 | FSR广义 | IAE | 缺口F1 |")
            L.append("|---|---|---|---|---|---|")
            for s, v in ev["strata"].items():
                mm = v["metrics"]
                L.append(f"| {s} | {v['n_runs']} | {_fmt(mm['false_support_strict'])} | {_fmt(mm['false_support_broad'])} | "
                         f"{_fmt(mm['insufficient_as_err'])} | {_fmt(mm['gap_f1'])} |")
            L.append("")
        else:
            L.append(f"分层：{ev.get('strata_note')}")
            L.append("")
        cost = ev["cost"]
        el = cost["elapsed_seconds"]
        if el.get("n"):
            el_txt = f"耗时 n={el['n']}，合计={el['total']}s，均值={el['mean']}s，中位数={el.get('median')}s"
        else:
            el_txt = f"耗时未记录（{el.get('reason') or '无 elapsed_seconds'}）"
        mc = cost["model_calls"]
        mc_txt = f"{mc['total']}" if mc.get("total") is not None else "未记录"
        L.append(f"成本：{el_txt}；模型调用：{mc_txt}{'（' + mc['reason'] + '）' if mc.get('reason') else ''}")
        L.append("")
        fs = [r for r in ev["per_claim"] if r.get("false_support")]
        if fs:
            L.append("### 被判为支持的非支持结论（需上游复核）")
            L.append("")
            L.append("| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |")
            L.append("|---|---|---|---|---|---|")
            for r in fs:
                L.append(f"| {r['run_id']} | {r['gold_claim_id']} | {r['pred_claim_id']} | {r['gold_status']} | {r['pred_status']} | {_cell(r['answer_span'])} |")
            L.append("")
        if ev["warnings"]:
            L.append(f"### 警告（共 {len(ev['warnings'])} 条，最多列 20 条）")
            L.append("")
            for w in ev["warnings"][:20]:
                L.append(f"- {_cell(w)}")
            L.append("")
    for sec in extra_sections or []:
        L.append(sec.rstrip())
        L.append("")
    L.append("## 指标定义")
    L.append("")
    for k, v in METRIC_DEFS.items():
        L.append(f"- `{k}`：{v}")
    L.append("")
    return "\n".join(L)


def _write_csv(path: Path, fields: List[str], rows: Sequence[Dict[str, Any]]) -> None:
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def write_report(
    evals: Sequence[Dict[str, Any]],
    out_dir: str | Path,
    data_version: Optional[str] = None,
    gold_version: Optional[str] = None,
    extra_notes: Optional[Sequence[str]] = None,
    generated_at: Optional[str] = None,
    extra_rows: Optional[Sequence[Dict[str, Any]]] = None,
    extra_sections: Optional[Sequence[str]] = None,
) -> Dict[str, str]:
    """写出四个文件，返回 名称 -> 路径。写之前做 schema 校验，失败抛 ValueError。"""
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    doc = build_experiment_metrics(evals, data_version, gold_version, generated_at, extra_rows)
    errs = validate_experiment_metrics(doc)
    if errs:
        raise ValueError("experiment_metrics 不符合 schema：" + "; ".join(errs[:10]))
    paths = {
        # 完整文档（含元数据、分子分母、CI）；08B 看板读取的是下面的 experiment_metrics.json（顶层为行列表）
        "experiment_metrics": out / "experiment_metrics.full.json",
        "experiment_metrics_08b": out / "experiment_metrics.json",
        "report": out / "report.md",
        "per_claim": out / "per_claim.csv",
        "per_run": out / "per_run.csv",
    }
    with open(paths["experiment_metrics"], "w", encoding="utf-8") as fh:
        json.dump(doc, fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(paths["experiment_metrics_08b"], "w", encoding="utf-8") as fh:
        json.dump(list(doc.get("rows") or []), fh, ensure_ascii=False, indent=2)
        fh.write("\n")
    with open(paths["report"], "w", encoding="utf-8") as fh:
        fh.write(render_markdown(evals, doc, extra_notes, extra_sections))
    _write_csv(paths["per_claim"], PER_CLAIM_FIELDS, [r for ev in evals for r in ev["per_claim"]])
    _write_csv(paths["per_run"], PER_RUN_FIELDS, [r for ev in evals for r in ev["per_run"]])
    return {k: str(v) for k, v in paths.items()}
