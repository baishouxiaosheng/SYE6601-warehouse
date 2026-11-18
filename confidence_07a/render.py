"""成绩单 / 对比结果 -> Markdown（中文）。纯函数，输出确定。"""
from __future__ import annotations

from typing import Any, Dict, List, Optional


def _cell(x: Any, limit: int = 80) -> str:
    if x is None:
        return "—"
    s = str(x).replace("|", "\\|").replace("\n", " ")
    return s if len(s) <= limit else s[: limit - 1] + "…"


def _frac(d: Dict[str, Any]) -> str:
    v = d.get("value")
    num, den = d.get("numerator"), d.get("denominator")
    if v is None:
        return f"{_cell(num)}/{_cell(den)} = null（{d.get('reason', '分母为 0')}）"
    return f"{num}/{den} = {v:.4f}"


def _loc(item: Dict[str, Any]) -> str:
    parts = []
    if item.get("evidence_id"):
        parts.append(item["evidence_id"])
    if item.get("event_id"):
        parts.append(f"事件 {item['event_id']}")
    if item.get("json_path"):
        parts.append(f"`{item['json_path']}`")
    if item.get("check_id"):
        parts.append(f"{item['check_id']}({item.get('kind')}:{item.get('verdict')})")
    return " ".join(parts) or "—"


def render_scorecard_md(card: Dict[str, Any]) -> str:
    L: List[str] = []
    L.append(f"# 置信度成绩单 v2 · {card.get('run_id')}")
    L.append("")
    L.append(f"> {card.get('score_semantics')}")
    L.append("")
    L.append(f"- 问题：{card.get('question') or '—'}")
    L.append(f"- **等级：{card.get('grade_label_zh')}（{card.get('grade')}）**")
    L.append(f"- 严重问题告警（high_risk_alert）：{'是' if card.get('high_risk_alert') else '否'}")
    if card.get("overall_display"):
        L.append(f"- 综合分（加权，PROVISIONAL）：{card.get('overall')}")
    else:
        L.append(f"- 综合分：不显示（存在阻断项或无可计算维度；计算值 {card.get('overall')} 仅供调试）")
    uv = card.get("upstream_versions") or {}
    L.append(
        f"- 评分规则版本：{card.get('policy_version')}（{card.get('policy_status')}，sha256 {str(card.get('policy_sha256'))[:12]}…）；"
        f"上游：graph={uv.get('graph_version')} plan={uv.get('plan_version')} answer_sha256={uv.get('answer_sha256')}"
    )
    L.append("")

    L.append("## 阻断项与严重问题")
    sev = card.get("severe_issues") or []
    if sev:
        for s in sev:
            L.append(f"- **严重 {s['code']}** {s['claim_id']}「{_cell(s['text'])}」：{s['reason_zh']}；"
                     f"措辞 {s['expression']}，状态 {s['status']}；高风险依据 {', '.join(s['high_risk_basis'])}")
    else:
        L.append("- 无严重问题。")
    blk = card.get("blockers") or []
    if blk:
        for b in blk:
            L.append(f"- 阻断 {b['code']}{'（严重）' if b.get('severe') else ''} {b['claim_id']}「{_cell(b['text'])}」：{b['reason_zh']}（{_cell(b.get('detail'), 120)}）")
    else:
        L.append("- 无阻断项。")
    L.append("")

    L.append("## 保留项")
    q = card.get("qualifications") or []
    if q:
        for x in q:
            who = x.get("claim_id") or x.get("goal_id") or x.get("gap_id") or "运行级"
            L.append(f"- {x['code']} [{who}] {x['reason_zh']}：{_cell(x.get('detail'), 120)}")
    else:
        L.append("- 无。")
    L.append("")

    L.append("## 三个维度（分子/分母）")
    L.append("| 维度 | 分子/分母 = 值 | 权重 | 分项 |")
    L.append("|---|---|---|---|")
    names = {"support": "证据支持度", "coverage": "问题回应覆盖度", "uncertainty": "不确定性表达准确性"}
    for k, d in (card.get("dimensions") or {}).items():
        bd = d.get("breakdown") or {}
        if k == "uncertainty":
            bd_s = f"判定 {bd.get('judgements')}；未检查默认UNKNOWN {bd.get('unchecked_default_unknown')}；仅已检查结论 {_frac(bd.get('checked_only') or {})}"
        else:
            bd_s = ", ".join(f"{a}={b}" for a, b in bd.items())
        L.append(f"| {names.get(k, k)} | {_frac(d)} | {d.get('weight')} | {_cell(bd_s, 200)} |")
    L.append("")
    for k, d in (card.get("dimensions") or {}).items():
        L.append(f"- {names.get(k, k)}口径：{d.get('rule')}")
    L.append("")

    L.append("## 逐结论")
    L.append("| 复核序 | 结论 | 原文 | 措辞 | 状态 | 不确定性判定 | 高风险 | 主要依据（事件/字段） | 缺失或冲突 | 目标 | 补证动作 |")
    L.append("|---|---|---|---|---|---|---|---|---|---|---|")
    seq = card.get("review_sequence") or []
    for c in card.get("claims") or []:
        order = seq.index(c["claim_id"]) + 1 if c["claim_id"] in seq else ""
        basis = "; ".join(_loc(b) for b in c.get("main_basis") or []) or "—"
        miss = "; ".join(
            (f"{m['gap_id']}({m['gap_type']},{m.get('criticality')})" if m.get("gap_id") else _loc(m))
            for m in c.get("missing_or_conflicting") or []
        ) or "—"
        hr = ("严重 " if c.get("severe") else "") + ("是：" + ",".join(c["high_risk_basis"]) if c.get("is_high_risk") else "否")
        acts = ", ".join(f"{a['action_id']}({a['action_type']}/{a.get('executability')})" for a in c.get("actions") or []) or "—"
        goals = ",".join(c.get("affected_goals") or []) or "—"
        if c.get("linkage_method") == "lexical_fallback":
            goals += "（词面兜底）"
        L.append(
            f"| {order} | {c['claim_id']} | {_cell(c['text'], 40)} | {c['expression_zh']} | {c['status_zh']}（{c['status']}，来源 {c['status_source']}） | "
            f"{c['uncertainty']['judgement']}（{c['uncertainty']['score']}） | {_cell(hr, 60)} | {_cell(basis, 160)} | {_cell(miss, 120)} | {goals} | {_cell(acts, 80)} |"
        )
    L.append("")

    L.append("## 用户目标")
    for g in card.get("goals") or []:
        L.append(f"- {g['goal_id']}「{g['text']}」：{g['coverage_state_zh']}（{g['coverage_state']}），关联 {g['linked_claims'] or '无'}，关联方式 {g['linkage_method']}")
    L.append("")

    L.append("## 缺口")
    gaps = card.get("gaps") or []
    if gaps:
        for g in gaps:
            L.append(f"- {g['gap_id']} {g['gap_type']} / {g.get('criticality')}：{g.get('description')}；影响 {g['affected_claims']}")
    else:
        L.append("- 上游未给出缺口。")
    L.append("")

    sup = card.get("supplement") or {}
    L.append("## 补证计划")
    L.append(f"共 {sup.get('plan_action_count')} 个动作：可执行 {sup.get('executable')}，需确认 {sup.get('needs_confirmation')}，需人工 {sup.get('manual')}。")
    for a in sup.get("actions") or []:
        L.append(
            f"- {a['action_id']} {a['action_type']}（{a.get('executability')}，工具 {a.get('tool') or '未指定'}）→ 结论 {a['target_claims']}；"
            f"已知参数 {a.get('known_arguments')}；待确认 {a.get('pending_arguments')}；成功判据：{_cell(a.get('success_criterion'), 120)}"
        )
    L.append("")

    br = card.get("build_risks") or {}
    L.append("## 建链风险与范围声明")
    um = br.get("unmapped_sentences") or {}
    L.append(f"- 回答中未映射到任何结论的句子：{um.get('count')} {um.get('items') or ''}")
    L.append(f"- 无关联结论的目标：{br.get('goals_without_claims')}；词面兜底关联：{br.get('lexical_fallback_links')}")
    L.append(f"- 无边证据节点：{br.get('orphan_evidence')}")
    L.append(f"- 没有任何 check 命中的结论：{br.get('claims_without_checks')}（其中默认 UNKNOWN：{br.get('unchecked_default_unknown')}）")
    L.append(f"- 审核状态：{br.get('review_status')}")
    if br.get("recommendations_unscored"):
        L.append(f"- 未计分的推荐类结论：{[r.get('id') for r in br['recommendations_unscored']]}")
    if br.get("gap_missing_condition_not_node"):
        L.append(f"- missing_condition 不是节点 ID 的缺口：{br['gap_missing_condition_not_node']}")
    L.append(f"- {br.get('scope_statement')}")
    L.append(f"- 范围说明：{card.get('scope_note')}")
    if card.get("notes"):
        L.append("")
        L.append("## 备注")
        for n in card["notes"]:
            L.append(f"- {n}")
    L.append("")
    return "\n".join(L)


def render_diff_md(diff: Dict[str, Any]) -> str:
    L: List[str] = []
    L.append(f"# 补证前后成绩单对比 · {diff.get('run_id')}")
    L.append("")
    if diff.get("score_semantics"):
        L.append(f"> {diff['score_semantics']}")
        L.append("")
    for w in diff.get("warnings") or []:
        L.append(f"- 警告：{w}")
    g = diff.get("grade") or {}
    L.append(f"- 等级：{g.get('before_zh')}（{g.get('before')}） → {g.get('after_zh')}（{g.get('after')}）")
    h = diff.get("high_risk_alert") or {}
    L.append(f"- 严重问题告警：{h.get('before')} → {h.get('after')}")
    L.append("")
    L.append("| 维度 | 补证前 | 补证后 | 变化 |")
    L.append("|---|---|---|---|")
    for k, d in (diff.get("dimensions") or {}).items():
        L.append(f"| {k} | {d['before']}（{d['before_fraction'][0]}/{d['before_fraction'][1]}） | {d['after']}（{d['after_fraction'][0]}/{d['after_fraction'][1]}） | {d['delta']} |")
    L.append("")
    L.append("## 结论状态迁移")
    L.append("| 结论 | 原文 | 补证前 | 补证后 | 不确定性判定 | 阻断项 |")
    L.append("|---|---|---|---|---|---|")
    for t in diff.get("claim_transitions") or []:
        mark = "**" if t["changed"] else ""
        L.append(
            f"| {t['claim_id_before']}→{t['claim_id_after']} | {_cell(t['text'], 40)} | {t['status_before']} | {mark}{t['status_after']}{mark} | "
            f"{t['judgement_before']}→{t['judgement_after']} | {t['blockers_before']}→{t['blockers_after']} |"
        )
    L.append("")
    for title, key in (("新增缺口", "gaps_added"), ("已关闭缺口", "gaps_closed"),
                       ("新增阻断项", "blockers_added"), ("消除阻断项", "blockers_removed")):
        items = diff.get(key) or []
        L.append(f"- {title}：" + ("；".join(f"{x.get('gap_id') or x.get('code')} {_cell(x.get('description') or x.get('text'), 60)}" for x in items) or "无"))
    L.append("")
    L.append("## 解释")
    for e in diff.get("explanation_zh") or []:
        L.append(f"- {e}")
    v = diff.get("versions") or {}
    L.append("")
    L.append(f"- 版本：补证前 {((v.get('before') or {}).get('upstream_versions'))}；补证后 {((v.get('after') or {}).get('upstream_versions'))}")
    L.append("")
    return "\n".join(L)
