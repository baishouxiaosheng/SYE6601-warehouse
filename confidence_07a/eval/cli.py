"""离线评测命令行（由 `python -m confidence_07a {eval,variants,report,crosscheck,llm-judge}` 分派）。

- eval        预测（01A output/ 或 06B 结果目录，或离线现跑 01A rule）× gold → evals.json + 四个报告文件；
              默认对每个方法输出三行：<m>（只看图/计划）、<m>+v1（01A v1 成绩单）、<m>+v2（07A v2 成绩单）。
- variants    受控变体（eval/variants.py）：生成 → 现跑 01A rule 引擎 → 敏感性/稳定性 → variants.json/csv/md。
- report      从 evals.json（+ variants.json + 占位方法）重新生成 experiment_metrics.json / report.md / csv。
- crosscheck  外部对照（默认关闭，需 --allow-case-notes；见 eval/crosscheck.py）。
- llm-judge   纯模型基线入口（需环境变量；--dry-run 不联网；见 eval/baselines/llm_judge.py）。

约束：仅标准库；所有读写 utf-8；不读取 .env；01A 引擎固定 load_settings({"mode": "rule"}, env={})；本命令不调用模型
（llm-judge 非 dry-run 时除外，且只读环境变量）。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence, Tuple

DEFAULT_PLACEHOLDER_NOTE = "未运行：需要密钥/06B 提供结果"


# ---------------------------------------------------------------------------
# IO
# ---------------------------------------------------------------------------

def _read_json(path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _write_json(path: Path, obj: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2, default=str)
        fh.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _write_csv(path: Path, fields: Sequence[str], rows: Sequence[Dict[str, Any]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=list(fields), extrasaction="ignore")
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in fields})


def _parse_pred(spec: str) -> Tuple[str, str]:
    if "=" not in spec:
        raise argparse.ArgumentTypeError(f"--pred 需要 NAME=PATH 形式：{spec}")
    name, path = spec.split("=", 1)
    return name.strip(), path.strip()


# ---------------------------------------------------------------------------
# 预测加载
# ---------------------------------------------------------------------------

def load_method_dir(path: str, log_path: Optional[str], method: str) -> Dict[str, Any]:
    """01A output/ 或 06B 结果目录 -> {"runs", "v1_scorecards", "failures", "dir_kind"}。"""
    from ..adapters import egraph_v1
    from .runner import load_results_dir, records_to_runs

    kind = egraph_v1.detect_dir_kind(path)
    if kind == "01a_output":
        runs = list(egraph_v1.iter_output_dir(path, log_path, method=method))
        v1: Dict[str, Dict[str, Any]] = {}
        for r in runs:
            p = Path(path) / f"{r.case_id}_scorecard.json"
            if p.is_file():
                v1[r.run_id] = egraph_v1.load_v1_scorecard(p)
        return {"runs": runs, "v1_scorecards": v1, "failures": {}, "dir_kind": kind}
    if kind == "06b_results":
        logs = None
        if log_path:
            from ..logs import load_logs

            logs = load_logs(log_path)
        res = records_to_runs(load_results_dir(path), method, logs)
        res["dir_kind"] = kind
        return res
    raise ValueError(f"无法识别的预测目录（既不是 01A output/ 也不是 06B 结果目录）：{path}")


def load_engine_live(engine: str, log_path: str, method: str, run_ids: Optional[Sequence[str]] = None) -> Dict[str, Any]:
    from ..logs import load_logs
    from .runner import records_to_runs, run_engine_rule

    logs = load_logs(log_path)
    recs = run_engine_rule(engine, list(logs.values()), run_ids)
    res = records_to_runs(recs, method, logs)
    res["dir_kind"] = "engine_live_rule"
    return res


def v2_scorecards(runs, policy_path: Optional[str] = None) -> Dict[str, Dict[str, Any]]:
    from ..scorecard import load_policy, score_run

    pol = load_policy(policy_path)
    out = {}
    for r in runs:
        vid = (r.source or {}).get("variant_id")
        out[r.run_id if not vid else f"{r.run_id}#{vid}"] = score_run(r, pol)
    return out


# ---------------------------------------------------------------------------
# 额外的报告片段
# ---------------------------------------------------------------------------

def placeholder_rows(names: Sequence[str], note: str = DEFAULT_PLACEHOLDER_NOTE) -> List[Dict[str, Any]]:
    return [{"method": n, "false_support": None, "gap_locate": None, "insufficient_as_err": None,
             "note": note, "status": "not_run"} for n in names]


def _fmt(m: Optional[Dict[str, Any]]) -> str:
    if not m:
        return "—"
    if m.get("value") is None:
        return f"null（{m.get('numerator')}/{m.get('denominator')}）"
    ci = m.get("ci95")
    cis = f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else ""
    return f"{m['value']:.3f}{cis}（{m['numerator']}/{m['denominator']}）"


SCORECARD_METRICS = ("severe_recall", "severe_false_alarm", "calibration_ece")


def scorecard_comparison_md(evals: Sequence[Dict[str, Any]]) -> Optional[str]:
    """成绩单层对照（v1 vs v2）：只比较运行级严重问题召回/误报、校准与等级列联表。"""
    sc = [e for e in evals if e["n"].get("scorecards_provided")]
    if len(sc) < 1:
        return None
    L = ["## 成绩单层对照（v1_scorecard vs v2_scorecard）", "",
         "同一组预测（图/计划相同），只换成绩单；结论级指标按构造相同，差异只出现在下列运行级指标上。"
         "v1 无 `high_risk_alert`，按 `severity_flags` 中存在 HIGH 回退（见 per_run.csv 的 alert_source）。", "",
         "| 指标 | " + " | ".join(e["method"] for e in sc) + " |", "|---|" + "---|" * len(sc)]
    for m in SCORECARD_METRICS:
        L.append(f"| {m} | " + " | ".join(_fmt(e["metrics"].get(m)) for e in sc) + " |")
    L.append("")
    for e in sc:
        rows = e["per_run"]
        sev = [r for r in rows if r.get("gold_severe")]
        miss = [r["run_id"] for r in sev if r.get("high_risk_alert") is False]
        fa = [r["run_id"] for r in rows if not r.get("gold_severe") and r.get("high_risk_alert")]
        L.append(f"- `{e['method']}`：gold severe 运行 {len(sev)} 个，未告警 {len(miss)} 个"
                 f"{('（' + '、'.join(miss) + '）') if miss else ''}；非 severe 运行告警 {len(fa)} 个"
                 f"{('（' + '、'.join(fa) + '）') if fa else ''}。")
    L.append("")
    return "\n".join(L)


def upstream_issue_md(evals: Sequence[Dict[str, Any]], max_rows: int = 40) -> Optional[str]:
    """给上游的问题清单（自动部分）：IAE 结论、漏抽的高风险 gold 结论、未定位的 gold 缺口所在运行。"""
    base = next((e for e in evals if not e["n"].get("scorecards_provided")), evals[0] if evals else None)
    if base is None:
        return None
    L = [f"## 给上游的问题清单（自动生成，方法 `{base['method']}`）", ""]
    iae = [r for r in base["per_claim"] if r.get("insufficient_as_err")]
    if iae:
        L += ["### 证据不足被判为 REFUTE（IAE）", "", "| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |", "|---|---|---|---|---|---|"]
        for r in iae[:max_rows]:
            L.append(f"| {r['run_id']} | {r['gold_claim_id']} | {r['pred_claim_id']} | {r['gold_status']} | {r['pred_status']} | "
                     f"{str(r.get('answer_span') or '').replace('|', '/')} |")
        L.append("")
    missed = [r for r in base["per_claim"] if r.get("gold_claim_id") and not r.get("pred_claim_id") and r.get("is_high_risk")]
    if missed:
        L += ["### 未被抽取（未对齐）的高风险 gold 结论", "", "| run_id | gold_claim_id | gold | 最高相似度 | 原文片段 |", "|---|---|---|---|---|"]
        for r in missed[:max_rows]:
            L.append(f"| {r['run_id']} | {r['gold_claim_id']} | {r['gold_status']} | {r.get('align_score')} | "
                     f"{str(r.get('answer_span') or '').replace('|', '/')} |")
        L.append("")
    mis = [r for r in base["per_claim"] if r.get("pred_claim_id") and r.get("gold_status") and r.get("pred_status")
           and r["gold_status"] != r["pred_status"] and not r.get("false_support") and not r.get("insufficient_as_err")]
    if mis:
        L += ["### 其他五态不一致（已对齐）", "", "| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |", "|---|---|---|---|---|---|"]
        for r in mis[:max_rows]:
            L.append(f"| {r['run_id']} | {r['gold_claim_id']} | {r['pred_claim_id']} | {r['gold_status']} | {r['pred_status']} | "
                     f"{str(r.get('answer_span') or '').replace('|', '/')} |")
        L.append("")
    return "\n".join(L) if len(L) > 2 else None


def _compose_report(evals, out: Path, data_version, gold_version, variants_result=None,
                    placeholders: Sequence[str] = (), placeholder_note: str = DEFAULT_PLACEHOLDER_NOTE,
                    generated_at: Optional[str] = None, extra_notes: Sequence[str] = ()) -> Dict[str, str]:
    from .report import write_report
    from .variants import render_variants_md, variant_metric_rows

    extra_rows: List[Dict[str, Any]] = []
    sections: List[str] = []
    s = scorecard_comparison_md(evals)
    if s:
        sections.append(s)
    vlist = variants_result if isinstance(variants_result, list) else ([variants_result] if variants_result else [])
    for vr in vlist:
        base_method = (vr.get("method") or "rule")
        extra_rows += variant_metric_rows(vr, method=base_method, seed=int(vr.get("seed") or 0))
        sections.append(render_variants_md(vr, title=f"受控变体结果（`{base_method}`，基线运行 {vr.get('n_base_runs')} 条）"))
    extra_rows += placeholder_rows(placeholders, placeholder_note)
    u = upstream_issue_md(evals)
    if u:
        sections.append(u)
    return write_report(evals, out, data_version=data_version, gold_version=gold_version,
                        extra_notes=list(extra_notes), generated_at=generated_at,
                        extra_rows=extra_rows, extra_sections=sections)


# ---------------------------------------------------------------------------
# 子命令
# ---------------------------------------------------------------------------

def cmd_eval(a) -> int:
    from .gold import gold_runs, load_gold
    from .metrics import evaluate

    gold = gold_runs(load_gold(a.gold))
    if a.run_ids:
        want = {x.strip() for x in a.run_ids.split(",") if x.strip()}
        gold = [g for g in gold if str(g.get("run_id")) in want]
    sources: List[Tuple[str, Dict[str, Any]]] = []
    for spec in a.pred or []:
        name, path = _parse_pred(spec)
        sources.append((name, load_method_dir(path, a.log, name)))
    if a.engine:
        if not a.log:
            print("--engine 需要 --log", file=sys.stderr)
            return 2
        sources.append((a.engine_method, load_engine_live(a.engine, a.log, a.engine_method,
                                                          [g["run_id"] for g in gold])))
    if not sources:
        print("至少需要一个 --pred NAME=PATH 或 --engine", file=sys.stderr)
        return 2
    modes = [m.strip() for m in a.scorecards.split(",") if m.strip()] if a.scorecards else []
    evals = []
    for name, res in sources:
        runs = res["runs"]
        if "none" in modes or not modes:
            evals.append(evaluate(runs, gold, name, scorecards=None, seed=a.seed, config=a.config))
        if "v1" in modes:
            evals.append(evaluate(runs, gold, f"{name}+v1", scorecards=res["v1_scorecards"], seed=a.seed, config=a.config))
        if "v2" in modes:
            evals.append(evaluate(runs, gold, f"{name}+v2", scorecards=v2_scorecards(runs, a.policy), seed=a.seed, config=a.config))
        for rid, why in (res.get("failures") or {}).items():
            print(f"[{name}] 处理失败 {rid}: {why}", file=sys.stderr)
    out = Path(a.out)
    _write_json(out / "evals.json", {"schema": "07a-evals.v1", "data_version": a.data_version,
                                     "gold_version": a.gold_version, "evals": evals})
    variants_result = [_read_json(p) for p in a.variants or []]
    paths = _compose_report(evals, out, a.data_version, a.gold_version, variants_result,
                            a.placeholder or [], a.placeholder_note)
    for e in evals:
        m = e["metrics"]
        print(f"{e['method']}: FSR={m['false_support_strict']['value']} IAE={m['insufficient_as_err']['value']} "
              f"gapF1={m['gap_f1']['value']} severe_recall={m['severe_recall']['value']}")
    print("已写出：" + "，".join(paths.values()))
    return 0


def cmd_report(a) -> int:
    doc = _read_json(a.evals)
    evals = doc["evals"] if isinstance(doc, dict) else doc
    variants_result = [_read_json(p) for p in a.variants or []]
    paths = _compose_report(evals, Path(a.out), a.data_version or doc.get("data_version"),
                            a.gold_version or doc.get("gold_version"), variants_result,
                            a.placeholder or [], a.placeholder_note)
    print("已写出：" + "，".join(paths.values()))
    return 0


def cmd_variants(a) -> int:
    from ..logs import load_logs
    from ..scorecard import load_policy
    from .gold import gold_runs, load_gold
    from .variants import KINDS, VARIANT_CSV_FIELDS, render_variants_md, run_variants_experiment, variant_csv_rows

    logs = load_logs(a.log)
    gold = gold_runs(load_gold(a.gold)) if a.gold else []
    if a.run_ids:
        run_ids = [x.strip() for x in a.run_ids.split(",") if x.strip()]
    elif a.gold_only:
        if not gold:
            print("--gold-only 需要 --gold", file=sys.stderr)
            return 2
        run_ids = [str(g["run_id"]) for g in gold if not g.get("variant_id")]
    else:
        run_ids = sorted(logs)
    kinds = [k.strip() for k in a.kinds.split(",")] if a.kinds else list(KINDS)
    res = run_variants_experiment(a.engine, list(logs.values()), run_ids=run_ids, gold_runs=gold, kinds=kinds,
                                  policy=load_policy(a.policy), seed=a.seed)
    res["method"] = a.method
    res["seed"] = a.seed
    res["inputs"] = {"log": Path(a.log).name, "gold": Path(a.gold).name if a.gold else None,
                     "run_selection": "run_ids" if a.run_ids else ("gold_only" if a.gold_only else "all")}
    out = Path(a.out)
    _write_json(out / "variants.json", res)
    _write_csv(out / "variant_rows.csv", VARIANT_CSV_FIELDS, variant_csv_rows(res["rows"]))
    _write_text(out / "variants.md", "# 受控变体实验\n\n" + render_variants_md(res) + "\n")
    s = res["summary"]
    print(f"变体 {s['n_variants']} 个（引擎失败 {s['n_engine_error']}）；敏感性={s['overall']['sensitivity']['value']}；"
          f"稳定性={s['control']['stability']['value']}；已写出 {out}")
    return 0


def cmd_crosscheck(rest: Sequence[str]) -> int:
    from .crosscheck import main as cc_main

    return int(cc_main(list(rest)) or 0)


def cmd_llm_judge(rest: Sequence[str]) -> int:
    from .baselines.llm_judge import main as lj_main

    return int(lj_main(list(rest)) or 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m confidence_07a", description="07A 离线评测")
    sub = p.add_subparsers(dest="cmd", required=True)

    e = sub.add_parser("eval", help="预测 × gold → 指标与报告")
    e.add_argument("--gold", required=True, help="gold.v1 JSON")
    e.add_argument("--log", help="工业日志 JSON（提供回答原文；--engine 时必需）")
    e.add_argument("--pred", action="append", help="NAME=PATH：01A output/ 或 06B 结果目录，可重复")
    e.add_argument("--engine", help="01A 引擎目录（离线现跑 rule 模式，env={}）")
    e.add_argument("--engine-method", default="rule_live")
    e.add_argument("--scorecards", default="none,v1,v2", help="逗号分隔：none,v1,v2（默认三者都输出）")
    e.add_argument("--policy", help="v2 成绩单 policy JSON")
    e.add_argument("--config", help="评测配置 JSON（默认 eval_config.v1.json）")
    e.add_argument("--run-ids", help="只评测这些运行（逗号分隔）")
    e.add_argument("--variants", action="append", help="variants.json（把变体行并入 experiment_metrics 与报告），可重复")
    e.add_argument("--placeholder", action="append", help="未运行方法的占位行（如 llm_only、hybrid），可重复")
    e.add_argument("--placeholder-note", default=DEFAULT_PLACEHOLDER_NOTE)
    e.add_argument("--data-version", default="monitor_log_60")
    e.add_argument("--gold-version")
    e.add_argument("--seed", type=int, default=0)
    e.add_argument("--out", required=True)
    e.set_defaults(func=cmd_eval)

    v = sub.add_parser("variants", help="受控变体：生成 → 跑 01A rule → 敏感性/稳定性")
    v.add_argument("--log", required=True)
    v.add_argument("--engine", required=True, help="01A 引擎目录")
    v.add_argument("--gold", help="gold.v1（提供 gold 证据定位作为额外目标）")
    g = v.add_mutually_exclusive_group()
    g.add_argument("--run-ids", help="逗号分隔")
    g.add_argument("--gold-only", action="store_true", help="只跑 gold 中的运行")
    v.add_argument("--kinds", help="逗号分隔，默认全部五类")
    v.add_argument("--policy")
    v.add_argument("--method", default="rule", help="写入结果与 experiment_metrics 行名的方法标签（如 rule、rule[gold15]）")
    v.add_argument("--seed", type=int, default=0)
    v.add_argument("--out", required=True)
    v.set_defaults(func=cmd_variants)

    r = sub.add_parser("report", help="从 evals.json 重新生成报告")
    r.add_argument("--evals", required=True)
    r.add_argument("--variants", action="append", help="variants.json，可重复")
    r.add_argument("--placeholder", action="append")
    r.add_argument("--placeholder-note", default=DEFAULT_PLACEHOLDER_NOTE)
    r.add_argument("--data-version")
    r.add_argument("--gold-version")
    r.add_argument("--out", required=True)
    r.set_defaults(func=cmd_report)

    sub.add_parser("crosscheck", help="外部对照（默认关闭；参数见 crosscheck --help）", add_help=False)
    sub.add_parser("llm-judge", help="纯模型基线入口（参数见 llm-judge --help）", add_help=False)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] == "crosscheck":
        return cmd_crosscheck(argv[1:])
    if argv and argv[0] == "llm-judge":
        return cmd_llm_judge(argv[1:])
    a = build_parser().parse_args(argv)
    return int(a.func(a) or 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
