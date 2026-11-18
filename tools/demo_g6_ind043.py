"""G6 补证前后演示（IND-043，D 线昨日产量）。

**本演示使用的夜班数据是合成数据（SYNTHETIC），不是日志中的真实返回。**
默认读取 LoopB（04B）统一交付的种子记录 `SIM-D-20261113-NIGHT`
（approved_seed/databases/industrial/shift_outputs.json），保证 01A/07A/08B 三处数值一致；
未提供该文件时才退回 07A 自带的同值占位数据。
它只用于演示“补证 → 01A 重算 → 07A 成绩单前后对比”的链路是否打通，
不能作为任何准确率或业务结论的依据。

做法：
1. 把 01A 引擎副本目录插入 sys.path（不依赖 cwd），用
   ``load_settings({"mode": "rule"}, env={})`` 装配纯规则配置（不读 .env、不调模型）；
2. 对 IND-043 运行 analyze_run 得到补证前产物；
3. 追加一条合成的夜班查询事件（Line-D，2026-11-12 22:00 ~ 2026-11-13 06:00，
   business_date=2026-11-13），调用 recompute_with_updates 得到补证后产物；
4. 两次产物分别经 egraph_v1 适配器 → score_run → diff_scorecards，写出 json/md。

用法（在 deliverable/ 下）：
  python -I tools/demo_g6_ind043.py --eg-root <01A 引擎副本> --log <工业日志 JSON> \
      --loopb-shift-file <LoopB>/approved_seed/databases/industrial/shift_outputs.json --out artifacts/demo_g6
"""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

FALLBACK_NIGHT_SHIFT = {  # 仅在未提供 LoopB 文件时使用
    "id": "u1",
    "event": "tool_call",
    "type": "database_query",
    "tool": "production.daily_output",
    "arguments": {
        "line_id": "Line-D",
        "date_from": "2026-11-12T22:00:00+08:00",
        "date_to": "2026-11-13T06:00:00+08:00",
    },
    "result": {
        "line_id": "Line-D",
        "query_period": "2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00",
        "total_units": 1650,
        "shifts": [
            {
                "shift": "夜班",
                "start_at": "2026-11-12T22:00:00+08:00",
                "end_at": "2026-11-13T06:00:00+08:00",
                "business_date": "2026-11-13",
                "units": 1650,
            }
        ],
        "attribution_rule": "本厂日报按业务日期统计：白班、中班归属开始当天；22:00至次日06:00的夜班归属结束当天。",
        "note": "SYNTHETIC：07A 演示用合成数据，非真实系统返回。",
    },
    "synthetic": True,
    "synthetic_note": "SYNTHETIC — 由 07A 构造，用于 G6 补证前后演示；数值 1650 为假设值。",
    "provenance": {"kind": "SYNTHETIC", "source": "07A fallback（未提供 LoopB 文件）"},
}

LOOPB_RECORD_ID = "SIM-D-20261113-NIGHT"
ATTRIBUTION_RULE = "本厂日报按业务日期统计：白班、中班归属开始当天；22:00至次日06:00的夜班归属结束当天。"


def build_update_from_loopb(path: Path, record_id: str = LOOPB_RECORD_ID) -> dict:
    """把 LoopB 种子库中的夜班记录包装成 01A 能识别的 tool_call 事件，并保留来源信息。"""
    raw = path.read_bytes()
    doc = json.loads(raw.decode("utf-8"))
    recs = doc.get("records") if isinstance(doc, dict) else doc
    rec = next((r for r in recs or [] if isinstance(r, dict) and r.get("record_id") == record_id), None)
    if rec is None:
        raise SystemExit(f"LoopB 文件中没有记录 {record_id}: {path}")
    data, lookup, prov = rec.get("data") or {}, rec.get("lookup") or {}, rec.get("provenance") or {}
    line_id = lookup.get("line_id") or "Line-D"
    shift = {k: data.get(k) for k in ("shift", "start_at", "end_at", "business_date", "units")}
    return {
        "id": "u1",
        "event": "tool_call",
        "type": "database_query",
        "tool": "production.daily_output",
        "arguments": {"line_id": line_id, "date_from": data.get("start_at"), "date_to": data.get("end_at")},
        "result": {
            "line_id": line_id,
            "query_period": f"{data.get('start_at')} ~ {data.get('end_at')}",
            "total_units": data.get("units"),
            "shifts": [shift],
            "attribution_rule": ATTRIBUTION_RULE,
            "note": f"SYNTHETIC：来自 LoopB 种子记录 {record_id}，非真实系统返回。",
        },
        "synthetic": prov.get("kind") == "SYNTHETIC",
        "synthetic_note": prov.get("note"),
        "provenance": {
            "source": "LoopB approved_seed",
            "file": path.name,
            "database_id": doc.get("database_id") if isinstance(doc, dict) else None,
            "dataset_version": doc.get("dataset_version") if isinstance(doc, dict) else None,
            "record_id": record_id,
            "file_sha256": hashlib.sha256(raw).hexdigest(),
            **prov,
        },
    }


def _write_json(path: Path, obj) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        json.dump(obj, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--eg-root", required=True, help="01A 引擎副本根目录（无 .env）")
    ap.add_argument("--log", required=True, help="工业日志 JSON")
    ap.add_argument("--out", required=True)
    ap.add_argument("--case", default="IND-043")
    ap.add_argument("--loopb-shift-file", default=None,
                    help="LoopB approved_seed/databases/industrial/shift_outputs.json；不提供时用 07A 占位数据")
    a = ap.parse_args(argv)

    eg_root = str(Path(a.eg_root).resolve())
    for p in (eg_root, str(ROOT)):
        if p not in sys.path:
            sys.path.insert(0, p)

    from config.settings import load_settings  # 01A
    from egraph.loader import load_runs, select_runs  # 01A
    from egraph.pipeline import analyze_run, recompute_with_updates  # 01A

    from confidence_07a.adapters.egraph_v1 import load_run_from_artifacts
    from confidence_07a.render import render_diff_md, render_scorecard_md
    from confidence_07a.scorecard import diff_scorecards, load_policy, score_run

    settings = load_settings({"mode": "rule"}, env={})
    assert settings.mode == "rule"
    runs = select_runs(load_runs(Path(a.log)), [a.case])
    if not runs:
        print(f"日志中没有 {a.case}", file=sys.stderr)
        return 2
    record = runs[0]
    before = analyze_run(record, settings)
    update = build_update_from_loopb(Path(a.loopb_shift_file)) if a.loopb_shift_file else FALLBACK_NIGHT_SHIFT
    pv = update.get("provenance") or {}
    src_zh = (f"LoopB 种子记录 {pv.get('record_id')}（作者 {pv.get('author')}，"
              f"文件 sha256 {str(pv.get('file_sha256'))[:12]}…）") if a.loopb_shift_file else "07A 占位数据"
    after = recompute_with_updates(before, settings, [update])

    out = Path(a.out)
    policy = load_policy()
    b_graph, b_plan = before.graph.to_dict(), before.plan.to_dict()
    a_graph, a_plan = after.graph.to_dict(), after.plan.to_dict()
    run_b = load_run_from_artifacts(b_graph, b_plan, log_record=record.raw, method="rule")
    run_a = load_run_from_artifacts(a_graph, a_plan, log_record=after.run.raw, method="rule")
    run_a.notes.append(f"补证后运行：trace 追加了 1 条 SYNTHETIC 夜班事件 u1，来源 {src_zh}（合成数据，仅演示）。")
    card_b = score_run(run_b, policy)
    card_a = score_run(run_a, policy)
    diff = diff_scorecards(card_b, card_a)
    diff["synthetic_update"] = {
        "is_synthetic": True,
        "event": update,
        "upstream_graph_changes": a_graph.get("changes"),
        "upstream_v1_grade": {"before": before.scorecard.grade, "after": after.scorecard.grade},
    }

    # 演示层旁注（不进入成绩单、不改写状态）：按 business_date 汇总班次产量，与回答数值对照，
    # 用于“给上游的问题清单”。
    target_date = "2026-11-13"
    seen = set()
    total = 0
    for ev in after.run.raw.get("trace") or []:
        res = ev.get("result") if isinstance(ev, dict) else None
        for sh in (res or {}).get("shifts") or []:
            key = (sh.get("shift"), sh.get("start_at"))
            if sh.get("business_date") == target_date and key not in seen:
                seen.add(key)
                total += int(sh.get("units") or 0)
    clm = next((c for c in card_a["claims"] if "4200" in c["text"]), None)
    observation = {
        "business_date": target_date,
        "shift_units_sum_after_update": total,
        "claim_text": clm["text"] if clm else None,
        "claim_status_after_by_01A": clm["status"] if clm else None,
        "note_zh": (
            f"补证后按 business_date={target_date} 汇总三个班次为 {total} 件，与回答的 4200 件不一致；"
            "但 01A 重算只检查了时间窗覆盖（CHK time_window_coverage=SUPPORT），把该结论判为 SUPPORT。"
            "07A 不重判状态，成绩单如实反映上游结果；此问题已列入给上游（01A）的问题清单。"
        ),
    }
    diff["demo_observation"] = observation

    _write_json(out / "synthetic_update_IND-043.json", {a.case: [update]})
    _write_json(out / "before_graph.json", b_graph)
    _write_json(out / "before_plan.json", b_plan)
    _write_json(out / "after_graph.json", a_graph)
    _write_json(out / "after_plan.json", a_plan)
    _write_json(out / "scorecard_before.json", card_b)
    _write_json(out / "scorecard_after.json", card_a)
    _write_text(out / "scorecard_before.md", render_scorecard_md(card_b))
    _write_text(out / "scorecard_after.md", render_scorecard_md(card_a))
    _write_json(out / "diff.json", diff)
    md = render_diff_md(diff)
    md += (
        "\n## 数据声明\n\n- 补证事件 u1 是 **SYNTHETIC 合成数据**（夜班 "
        f"{update['result'].get('total_units')} 件），来源：{src_zh}。只用于演示 G6 链路，"
        "不代表真实产量，也不能用于评估准确率。\n"
        f"- 01A 上游 changes：{json.dumps(a_graph.get('changes'), ensure_ascii=False)}\n"
        "\n## 演示旁注：上游重算问题（不影响成绩单计算）\n\n"
        f"- {observation['note_zh']}\n"
        "- 结论：本演示证明 G6 链路（补证 → 重算 → 前后成绩单 → 差异解释）已打通；"
        "但“等级升为附保留说明”是建立在上游错误的 SUPPORT 之上的，不能解读为回答变得可信。\n"
    )
    _write_text(out / "diff.md", md)
    print(json.dumps({"grade": diff["grade"], "transitions": diff["transition_summary"],
                      "explanation": diff["explanation_zh"]}, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
