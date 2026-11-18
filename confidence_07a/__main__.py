"""命令行：python -m confidence_07a {score,score-dir,diff,eval,variants,report,crosscheck,llm-judge}

- score      单个 01A graph(+plan) → 成绩单 json/md
- score-dir  01A output/ 目录或 06B 结果目录 → 逐运行成绩单 + summary.csv
- diff       两份成绩单 → 对比 json/md
- eval / variants / report / crosscheck / llm-judge  离线评测入口（由 confidence_07a.eval.cli 实现，延迟导入）

所有读写均为 utf-8；不读取任何 .env；不调用模型。
"""
from __future__ import annotations

import argparse
import csv
import json
import sys
from pathlib import Path
from typing import Dict, List, Optional

from .adapters import egraph_v1
from .adapters.b_review import load_b_review, overlay_b_review
from .logs import load_logs
from .render import render_diff_md, render_scorecard_md
from .scorecard import diff_scorecards, load_policy, score_run


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def _read_json(path) -> dict:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


SUMMARY_FIELDS = [
    "run_id", "case_id", "method", "grade", "high_risk_alert",
    "support_score", "coverage_score", "uncertainty_score", "overall", "overall_display",
    "n_claims", "n_goals", "n_blockers", "n_severe", "n_qualifications", "blocker_codes", "severe_claims",
    "v1_grade", "v1_overall", "v1_evidence_support", "v1_question_coverage", "v1_uncertainty_accuracy",
]


def summary_row(card: dict, v1: Optional[dict] = None) -> Dict[str, object]:
    v1 = v1 or {}
    v1d = v1.get("dimensions") or {}
    return {
        "run_id": card["run_id"],
        "case_id": card["case_id"],
        "method": (card.get("source") or {}).get("method"),
        "grade": card["grade"],
        "high_risk_alert": int(bool(card["high_risk_alert"])),
        "support_score": card["support_score"],
        "coverage_score": card["coverage_score"],
        "uncertainty_score": card["uncertainty_score"],
        "overall": card["overall"],
        "overall_display": int(bool(card["overall_display"])),
        "n_claims": len(card["claims"]),
        "n_goals": len(card["goals"]),
        "n_blockers": len(card["blockers"]),
        "n_severe": len(card["severe_issues"]),
        "n_qualifications": len(card["qualifications"]),
        "blocker_codes": " ".join(sorted({b["code"] for b in card["blockers"]})),
        "severe_claims": " ".join(s["claim_id"] for s in card["severe_issues"]),
        "v1_grade": v1.get("grade"),
        "v1_overall": v1.get("overall"),
        "v1_evidence_support": (v1d.get("evidence_support") or {}).get("score"),
        "v1_question_coverage": (v1d.get("question_coverage") or {}).get("score"),
        "v1_uncertainty_accuracy": (v1d.get("uncertainty_accuracy") or {}).get("score"),
    }


def write_summary_csv(path: Path, rows: List[Dict[str, object]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=SUMMARY_FIELDS)
        w.writeheader()
        for r in rows:
            w.writerow({k: ("" if r.get(k) is None else r.get(k)) for k in SUMMARY_FIELDS})


def _maybe_overlay(run, breviews: Dict[str, dict], policy: dict):
    if not breviews:
        return run
    return overlay_b_review(run, breviews.get(run.run_id), policy)


def cmd_score(a) -> int:
    policy = load_policy(a.policy)
    rec = None
    if a.log:
        graph = _read_json(a.graph)
        rec = load_logs(a.log).get(str(graph.get("run_id")))
    run = egraph_v1.load_run_from_files(a.graph, a.plan, log_record=rec, method=a.method)
    if a.b_review:
        run = _maybe_overlay(run, load_b_review(a.b_review), policy)
    card = score_run(run, policy)
    out_json = Path(a.out_json) if a.out_json else None
    if out_json:
        _write_json(out_json, card)
    if a.out_md:
        _write_text(Path(a.out_md), render_scorecard_md(card))
    if not out_json and not a.out_md:
        sys.stdout.write(json.dumps(card, ensure_ascii=False, indent=2) + "\n")
    else:
        print(f"{card['run_id']}: {card['grade']} alert={card['high_risk_alert']}")
    return 0


def cmd_score_dir(a) -> int:
    policy = load_policy(a.policy)
    kind = egraph_v1.detect_dir_kind(a.input)
    if kind == "01a_output":
        runs = egraph_v1.iter_output_dir(a.input, a.log, method=a.method or "rule")
    elif kind == "06b_results":
        runs = egraph_v1.iter_06b_dir(a.input, a.log, method=a.method)
    else:
        print(f"无法识别目录类型：{a.input}", file=sys.stderr)
        return 2
    breviews = load_b_review(a.b_review) if a.b_review else {}
    out = Path(a.out)
    rows = []
    n = 0
    for run in runs:
        run = _maybe_overlay(run, breviews, policy)
        card = score_run(run, policy)
        _write_json(out / f"{run.run_id}.json", card)
        if not a.no_md:
            _write_text(out / f"{run.run_id}.md", render_scorecard_md(card))
        v1 = None
        if kind == "01a_output":
            p = Path(a.input) / f"{run.case_id}_scorecard.json"
            if p.exists():
                v1 = egraph_v1.load_v1_scorecard(p)
        else:
            files = (run.source.get("files") or {}).get("result")
            if files:
                v1 = egraph_v1.load_v1_scorecard(Path(a.input) / files)
        rows.append(summary_row(card, v1))
        n += 1
    write_summary_csv(out / "summary.csv", rows)
    print(f"已写出 {n} 份成绩单到 {out}（目录类型 {kind}）")
    return 0


def cmd_diff(a) -> int:
    d = diff_scorecards(_read_json(a.before), _read_json(a.after))
    if a.out_json:
        _write_json(Path(a.out_json), d)
    if a.out_md:
        _write_text(Path(a.out_md), render_diff_md(d))
    if not a.out_json and not a.out_md:
        sys.stdout.write(json.dumps(d, ensure_ascii=False, indent=2) + "\n")
    else:
        print(f"{d['run_id']}: {d['grade']['before']} -> {d['grade']['after']}")
    return 0


EVAL_SUBCOMMANDS = ("eval", "variants", "report", "crosscheck", "llm-judge")


def cmd_eval_stub(name: str, rest: List[str]) -> int:
    """eval/variants/report 由 confidence_07a.eval 实现；这里只做延迟分派。"""
    try:
        from .eval import cli as eval_cli  # type: ignore
    except ImportError as exc:
        print(f"子命令 {name} 需要 confidence_07a.eval.cli（尚未提供）：{exc}", file=sys.stderr)
        return 2
    main = getattr(eval_cli, "main", None)
    if main is None:
        print("confidence_07a.eval.cli 缺少 main(argv)", file=sys.stderr)
        return 2
    return int(main([name] + list(rest)) or 0)


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="python -m confidence_07a", description="07A 置信度成绩单 v2")
    sub = p.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("score", help="单个 01A graph(+plan) → 成绩单")
    s.add_argument("--graph", required=True)
    s.add_argument("--plan")
    s.add_argument("--log", help="工业日志 JSON（提供回答原文与字段指针）")
    s.add_argument("--b-review", help="02B industrial_results.json（可选覆盖层）")
    s.add_argument("--policy")
    s.add_argument("--method", default="rule")
    s.add_argument("--out-json")
    s.add_argument("--out-md")
    s.set_defaults(func=cmd_score)

    d = sub.add_parser("score-dir", help="01A output/ 或 06B 结果目录 → 逐运行成绩单 + summary.csv")
    d.add_argument("--input", required=True)
    d.add_argument("--log")
    d.add_argument("--b-review")
    d.add_argument("--policy")
    d.add_argument("--method")
    d.add_argument("--out", required=True)
    d.add_argument("--no-md", action="store_true")
    d.set_defaults(func=cmd_score_dir)

    f = sub.add_parser("diff", help="两份成绩单 → 对比")
    f.add_argument("--before", required=True)
    f.add_argument("--after", required=True)
    f.add_argument("--out-json")
    f.add_argument("--out-md")
    f.set_defaults(func=cmd_diff)

    for name in EVAL_SUBCOMMANDS:
        e = sub.add_parser(name, help=f"离线评测：{name}（confidence_07a.eval 提供）", add_help=False)
        e.set_defaults(func=None, stub=name)
    return p


def main(argv: Optional[List[str]] = None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv and argv[0] in EVAL_SUBCOMMANDS:
        return cmd_eval_stub(argv[0], argv[1:])
    args = build_parser().parse_args(argv)
    return int(args.func(args) or 0)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
        sys.stderr.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
