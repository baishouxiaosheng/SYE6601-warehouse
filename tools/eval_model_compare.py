"""07A：纯规则 vs 纯模型（llm_only）小样本对照。

只在“有模型结果 ∩ 试点 gold”的运行上比较，两种方法用同一组运行，避免样本不一致。
用法（deliverable/ 下）：
  python -I tools/eval_model_compare.py --log LOG.json --gold gold/pilot_gold_v0.json \
      --rule-dir RULE_OUTPUT_DIR_OR_06B_RESULTS --llm-dir artifacts/model_runs/llm_only --out artifacts/eval_model_compare
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from confidence_07a.eval import cli as _cli  # noqa: E402
from confidence_07a.eval.baselines import llm_judge  # noqa: E402
from confidence_07a.eval.gold import gold_runs, load_gold  # noqa: E402
from confidence_07a.eval.metrics import evaluate  # noqa: E402
from confidence_07a.eval.runner import load_results_dir, run_methods  # noqa: E402


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--log", required=True)
    ap.add_argument("--gold", required=True)
    ap.add_argument("--engine", required=True, help="01A 引擎目录（离线 rule 模式现跑，env={}）")
    ap.add_argument("--llm-dir", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--seed", type=int, default=0)
    a = ap.parse_args(argv)

    llm_records = load_results_dir(a.llm_dir)
    llm_ids = {k for k in llm_records if k != "_failed"}
    gold = [g for g in gold_runs(load_gold(a.gold)) if str(g["run_id"]) in llm_ids]
    ids = [g["run_id"] for g in gold]
    print(f"对照运行（模型结果 ∩ gold）：{len(ids)} 条 {ids}")

    res = run_methods(
        {"rule": {"engine": a.engine, "run_ids": ids}},
        logs=a.log,
    )
    res.update(run_methods({"llm_only": {"records": {k: v for k, v in llm_records.items() if k in set(ids)}}},
                           logs=a.log, converter=llm_judge.converter))

    evals = []
    for name in ("rule", "llm_only"):
        runs = res[name]["runs"]
        evals.append(evaluate(runs, gold, f"{name}+v2", scorecards=_cli.v2_scorecards(runs, None), seed=a.seed))
        for rid, why in (res[name].get("failures") or {}).items():
            print(f"[{name}] 处理失败 {rid}: {why}", file=sys.stderr)

    # 成本（仅模型方法）
    usage = {"prompt_tokens": 0, "completion_tokens": 0, "latency_seconds": 0.0, "n": 0}
    for k in ids:
        r = llm_records[k]
        u = r.get("usage") or {}
        usage["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        usage["completion_tokens"] += int(u.get("completion_tokens") or 0)
        usage["latency_seconds"] += float(r.get("latency_seconds") or 0)
        usage["n"] += 1
    note = (f"模型对照：n={len(ids)} 条运行（模型结果 ∩ gold {Path(a.gold).name}）；模型 "
            f"{(next(iter(llm_records.values())).get('llm_config') or {}).get('model')}；"
            f"token 输入 {usage['prompt_tokens']} / 输出 {usage['completion_tokens']}；"
            f"平均延迟 {usage['latency_seconds'] / max(usage['n'], 1):.1f}s；混合方案未运行（用户决定不跑完）")
    out = Path(a.out)
    _cli._write_json(out / "evals.json", {"schema": "07a-evals.v1", "run_ids": ids, "usage": usage, "evals": evals})
    paths = _cli._compose_report(evals, out, "monitor_log_60", Path(a.gold).stem, None,
                                 ["hybrid"], "未运行：用户决定不跑完；01A hybrid 需要密钥", extra_notes=[note])
    for e in evals:
        m = e["metrics"]
        print(f"{e['method']}: FSR={m['false_support_strict']['value']} broadFSR={m['false_support_broad']['value']} "
              f"IAE={m['insufficient_as_err']['value']} gapF1={m['gap_f1']['value']} acc={m['status_accuracy']['value']} "
              f"param={m['requery_param_value_hit']['value']} severe_recall={m['severe_recall']['value']} "
              f"extract_cov={m['extraction_coverage']['value']}")
    print(note)
    print("已写出：" + "，".join(paths.values()))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
