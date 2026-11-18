"""07A 置信度成绩单 v2：score_run / diff_scorecards。

硬约束（规范 §0）：
- 不重新判断结论状态：status 一律取 RunView（上游 01A/02B）。
- 不读 gold、不读案例说明、不调用模型；全部由代码与版本化 policy 计算。
- 所有比例输出 {numerator, denominator, value}；分母为 0 时 value=null 并给 reason。
- 输出不含时间戳等易变字段，同一输入 + 同一 policy => 字节级一致。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from .expression import classify_expression, lexicon_hits
from .model import (
    ASSERTING_EXPRESSIONS,
    DECLARED_UNKNOWN,
    DEFINITE,
    EXPRESSIONS,
    HEDGED,
    REFUTE,
    SCOPED_PARTIAL,
    STATUS_ZH,
    STATUSES,
    SUPPORT,
    UNRESOLVED_STATUSES,
    ClaimView,
    RunView,
)

SCORECARD_VERSION = "07a-scorecard-v2"
DEFAULT_POLICY_PATH = Path(__file__).resolve().parent / "policy" / "scorecard_policy.v2.json"

BLOCKER_TEXT = {
    "B1": "高风险主结论与证据矛盾（REFUTE）",
    "B2": "高风险主结论以确定措辞表述，但上游状态为证据不足/缺规则/冲突",
    "B3": "确定措辞的结论与证据矛盾（REFUTE）",
    "B4": "HIGH 关键度缺口影响了确定措辞的结论",
    "B5": "确定措辞的结论依赖不完整的检索结果（分页/超时/筛选未生效等）",
}
SEVERE_CODE = {"B1": "SEVERE_CONTRADICTION", "B2": "SEVERE_OVERCLAIM"}
QUAL_TEXT = {
    "Q1_UNADDRESSED_GOAL": "用户目标未被任何结论回应，也未声明无法确定",
    "Q2_RESIDUAL_UNCERTAINTY": "非确定措辞的结论仍有未解决状态或残留缺口（已如实限定，但证据未补齐）",
    "Q3_OPEN_GAP": "存在未被阻断项覆盖的开放缺口",
    "Q4_LEXICAL_FALLBACK": "目标与结论的关联由词面兜底得出，非上游关联",
    "Q5_BUILD_RISK": "存在建链风险（见 build_risks）",
    "Q6_OVERCLAIM": "确定措辞但证据未支持（非高风险、无 HIGH 缺口，未达阻断）",
    "Q7_UNDERCLAIM": "证据已支持但措辞过度保守",
    "Q8_NO_CLAIMS": "没有可评价的结论",
}
GOAL_STATES = ("ADDRESSED_SUPPORTED", "ADDRESSED_DECLARED_UNKNOWN", "ADDRESSED_UNSUPPORTED", "NOT_ADDRESSED")
GOAL_STATE_ZH = {
    "ADDRESSED_SUPPORTED": "已回应且有支持",
    "ADDRESSED_DECLARED_UNKNOWN": "已如实声明无法确定",
    "ADDRESSED_UNSUPPORTED": "已回应但未获支持",
    "NOT_ADDRESSED": "未回应",
}
EXPRESSION_ZH = {
    DEFINITE: "确定断言",
    HEDGED: "带限定/推测",
    DECLARED_UNKNOWN: "声明无法确定",
    SCOPED_PARTIAL: "限定范围的部分结论",
}


# --------------------------------------------------------------------------
# policy
# --------------------------------------------------------------------------


def load_policy(path=None) -> dict:
    p = Path(path) if path else DEFAULT_POLICY_PATH
    with open(p, "r", encoding="utf-8") as fh:
        return json.load(fh)


def policy_sha256(policy: dict) -> str:
    canon = json.dumps(policy, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()


def _version() -> str:
    try:
        from . import __version__

        return __version__
    except Exception:  # pragma: no cover
        return "unknown"


# --------------------------------------------------------------------------
# 小工具
# --------------------------------------------------------------------------


def _round(x: Optional[float]) -> Optional[float]:
    return None if x is None else round(float(x), 4)


def ratio(numerator: float, denominator: int, zero_reason: str) -> Dict[str, Any]:
    num = numerator if isinstance(numerator, int) else _round(numerator)
    if not denominator:
        return {"numerator": num, "denominator": 0, "value": None, "reason": zero_reason}
    return {"numerator": num, "denominator": int(denominator), "value": _round(numerator / denominator)}


_SPLIT_SENT = re.compile(r"[。！？!?；;\n]+")
_NORM = re.compile(r"[\s，,。．.！!？?；;：:、“”\"'（）()]+")


def _norm(text: str) -> str:
    return _NORM.sub("", text or "")


def _bigrams(text: str, strip: str) -> set:
    t = "".join(ch for ch in (text or "") if ch not in strip)
    return {t[i : i + 2] for i in range(len(t) - 1)} if len(t) >= 2 else ({t} if t else set())


def _overlap(a: str, b: str, strip: str) -> float:
    A, B = _bigrams(a, strip), _bigrams(b, strip)
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def _cat(basis: str) -> str:
    return basis.split(":", 1)[0]


# --------------------------------------------------------------------------
# 逐结论判定
# --------------------------------------------------------------------------


def _expression_for(claim: ClaimView, policy: dict) -> Tuple[str, List[str]]:
    if claim.expression in EXPRESSIONS:
        return claim.expression, ["upstream_expression"]
    expr, hits = classify_expression(claim.text, claim.upstream_strength, policy)
    if claim.scope_limited and expr not in (DECLARED_UNKNOWN, SCOPED_PARTIAL):
        return SCOPED_PARTIAL, ["upstream:scope_limited"]
    return expr, hits


def _matrix_cell(expr: str, status: str, claim: ClaimView, policy: dict) -> Dict[str, Any]:
    special = (policy.get("expression_matrix_special") or {}).get("DECLARED_UNKNOWN_SUPPORT_GAP_CONFIRMED")
    if special and expr == DECLARED_UNKNOWN and status == SUPPORT:
        markers = special.get("upstream_gap_confirmation_markers") or []
        if any(m in (claim.verdict_reason or "") for m in markers):
            return {
                "score": float(special["score"]),
                "judgement": special["judgement"],
                "cell": "DECLARED_UNKNOWN×SUPPORT(gap_confirmed)",
            }
    cell = ((policy.get("expression_matrix") or {}).get(expr) or {}).get(status)
    if not cell:
        raise ValueError(f"policy.expression_matrix 缺少 {expr}×{status}")
    return {"score": float(cell["score"]), "judgement": cell["judgement"], "cell": f"{expr}×{status}"}


def _link_goals(run: RunView, policy: dict) -> Tuple[Dict[str, List[str]], Dict[str, str], Dict[str, List[str]]]:
    """返回 (claim->goals, claim->linkage_method, goal->claims)。"""
    goal_ids = [g.goal_id for g in run.goals]
    c2g: Dict[str, List[str]] = {c.claim_id: [g for g in c.related_goals if g in goal_ids] for c in run.claims}
    method: Dict[str, str] = {c.claim_id: ("upstream" if c2g[c.claim_id] else "none") for c in run.claims}
    for c in run.claims:
        if c.linkage_method == "lexical_fallback" and c2g[c.claim_id]:
            method[c.claim_id] = "lexical_fallback"
    g2c: Dict[str, List[str]] = {g: [c.claim_id for c in run.claims if g in c2g[c.claim_id]] for g in goal_ids}
    cfg = policy.get("linkage") or {}
    if cfg.get("lexical_fallback", True):
        strip = cfg.get("strip_chars", "")
        thr = float(cfg.get("min_overlap", 0.5))
        for g in run.goals:
            if g2c[g.goal_id]:
                continue
            for c in run.claims:
                if _overlap(g.text, c.text, strip) >= thr:
                    c2g[c.claim_id].append(g.goal_id)
                    g2c[g.goal_id].append(c.claim_id)
                    if method[c.claim_id] == "none":
                        method[c.claim_id] = "lexical_fallback"
    return c2g, method, g2c


def _basis_items(claim: ClaimView, run: RunView) -> Tuple[List[dict], List[dict]]:
    """(主要依据, 缺失或冲突)。每项都带 run_id + 事件 ID + json_path 以便回溯。"""
    checks = {c.check_id: c for c in run.checks}
    basis: List[dict] = []
    missing: List[dict] = []
    used_ev = set()
    for cid in claim.check_ids:
        chk = checks.get(cid)
        if not chk:
            continue
        ev = run.evidence.get(chk.evidence_ref) if chk.evidence_ref else None
        item = {
            "check_id": chk.check_id,
            "kind": chk.kind,
            "verdict": chk.verdict,
            "evidence_id": chk.evidence_ref,
            "run_id": run.run_id,
            "event_id": (chk.raw or {}).get("event_id") or (ev.event_id if ev else None),
            "json_path": chk.locator or (ev.json_path if ev else None),
            "pointer": (chk.raw or {}).get("pointer") or ((ev.raw or {}).get("pointer") if ev else None),
            "excerpt": (str(chk.detail)[:200] if chk.detail else None),
        }
        if chk.evidence_ref:
            used_ev.add(chk.evidence_ref)
        if chk.verdict in (SUPPORT, REFUTE):
            basis.append(item)
        else:
            missing.append(item)
    for eid in claim.evidence_ids:
        if eid in used_ev:
            continue
        ev = run.evidence.get(eid)
        if not ev:
            continue
        basis.append(
            {
                "check_id": None,
                "kind": (ev.raw or {}).get("node_type"),
                "verdict": None,
                "evidence_id": eid,
                "run_id": ev.run_id or run.run_id,
                "event_id": ev.event_id,
                "json_path": ev.json_path,
                "pointer": (ev.raw or {}).get("pointer"),
                "excerpt": (str(ev.excerpt)[:200] if ev.excerpt else None),
            }
        )
    return basis, missing


# --------------------------------------------------------------------------
# score_run
# --------------------------------------------------------------------------


def score_run(run: RunView, policy: Optional[dict] = None) -> dict:
    policy = policy or load_policy()
    hr = policy.get("high_risk") or {}
    crit = hr.get("criteria") or {}
    severe_bases = set(hr.get("severe_bases") or [])
    gates = policy.get("gates") or {}
    high_levels = set(gates.get("high_criticality") or ["HIGH"])
    incomplete_gap_types = set(gates.get("incomplete_gap_types") or [])
    incomplete_check_kinds = set(gates.get("incomplete_check_kinds") or [])

    gaps_by_id = {g.gap_id: g for g in run.gaps}
    checks_by_id = {c.check_id: c for c in run.checks}
    actions_by_id = {a.action_id: a for a in run.actions}
    goals_by_id = {g.goal_id: g for g in run.goals}

    c2g, link_method, g2c = _link_goals(run, policy)

    # 唯一主目标的主结论：只有 1 个目标时，按回答顺序第一条关联到它的结论
    sole_main: Optional[str] = None
    if len(run.goals) == 1:
        linked = g2c.get(run.goals[0].goal_id) or []
        upstream_linked = [c for c in linked if link_method.get(c) == "upstream"]
        cand = upstream_linked or linked
        sole_main = cand[0] if cand else None

    lexicon = hr.get("lexicon") or []
    rows: List[Dict[str, Any]] = []
    blockers: List[Dict[str, Any]] = []
    severe: List[Dict[str, Any]] = []
    quals: List[Dict[str, Any]] = []
    gaps_cited_by_blockers = set()

    for c in run.claims:
        expr, expr_hits = _expression_for(c, policy)
        status = c.status if c.status in STATUSES else "UNKNOWN"
        cell = _matrix_cell(expr, status, c, policy)
        goals_of = c2g.get(c.claim_id, [])
        claim_gaps = [gaps_by_id[g] for g in c.gap_ids if g in gaps_by_id]

        basis: List[str] = []
        if crit.get("lexicon", True):
            basis += [f"lexicon:{w}" for w in lexicon_hits(c.text, lexicon)]
        if crit.get("goal_lexicon", True):
            for gid in goals_of:
                g = goals_by_id.get(gid)
                if g:
                    basis += [f"goal_lexicon:{w}" for w in lexicon_hits(g.text, lexicon)]
        if crit.get("approval_type", True) and c.upstream_strength == "approval":
            basis.append("approval_type")
        if crit.get("gap_high", True):
            basis += [f"gap_high:{g.gap_id}" for g in claim_gaps if g.criticality in high_levels]
        if crit.get("sole_goal_main_claim", True) and sole_main == c.claim_id:
            basis.append("sole_goal_main_claim")
        basis = list(dict.fromkeys(basis))
        is_high = bool(basis)
        severe_eligible = any(_cat(b) in severe_bases for b in basis)
        if hr.get("main_claim_requires_goal_link_or_approval", True):
            is_main = bool(goals_of) or c.upstream_strength == "approval"
        else:
            is_main = True

        incomplete_reasons = [f"gap:{g.gap_id}:{g.gap_type}" for g in claim_gaps if g.gap_type in incomplete_gap_types]
        for cid in c.check_ids:
            chk = checks_by_id.get(cid)
            if chk and chk.kind in incomplete_check_kinds and chk.verdict != SUPPORT:
                incomplete_reasons.append(f"check:{chk.check_id}:{chk.kind}")

        codes: List[str] = []
        severe_code: Optional[str] = None
        high_gaps = [g.gap_id for g in claim_gaps if g.criticality in high_levels]

        def add_blocker(code: str, detail: str, gap_ids: Optional[List[str]] = None, is_severe: bool = False):
            codes.append(code)
            blockers.append(
                {
                    "code": code,
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "severe": is_severe,
                    "reason_zh": BLOCKER_TEXT[code],
                    "detail": detail,
                    "gap_ids": gap_ids or [],
                }
            )
            for gid in gap_ids or []:
                gaps_cited_by_blockers.add(gid)

        if is_main and is_high and status == REFUTE:
            add_blocker("B1", f"状态 REFUTE；高风险依据 {basis}", is_severe=severe_eligible)
            if severe_eligible:
                severe_code = SEVERE_CODE["B1"]
        if is_main and is_high and expr == DEFINITE and status in UNRESOLVED_STATUSES:
            add_blocker("B2", f"措辞 DEFINITE，状态 {status}；高风险依据 {basis}", c.gap_ids, is_severe=severe_eligible)
            if severe_eligible and not severe_code:
                severe_code = SEVERE_CODE["B2"]
        if expr == DEFINITE and status == REFUTE and "B1" not in codes:
            add_blocker("B3", "措辞 DEFINITE，状态 REFUTE")
        if expr == DEFINITE and high_gaps:
            add_blocker("B4", f"HIGH 缺口 {high_gaps}", high_gaps)
        if expr == DEFINITE and incomplete_reasons:
            add_blocker(
                "B5",
                f"不完整证据 {incomplete_reasons}",
                [g.gap_id for g in claim_gaps if g.gap_type in incomplete_gap_types],
            )
        if severe_code:
            severe.append(
                {
                    "code": severe_code,
                    "claim_id": c.claim_id,
                    "text": c.text,
                    "status": status,
                    "expression": expr,
                    "high_risk_basis": basis,
                    "reason_zh": (
                        "高风险主结论与证据明确矛盾" if severe_code == "SEVERE_CONTRADICTION"
                        else "高风险主结论在证据不足/缺规则/冲突时被写成确定结论"
                    ),
                }
            )

        # 保留项（逐结论）
        if not codes:
            if expr == DEFINITE and status in UNRESOLVED_STATUSES:
                quals.append({"code": "Q6_OVERCLAIM", "claim_id": c.claim_id, "goal_id": None,
                              "reason_zh": QUAL_TEXT["Q6_OVERCLAIM"], "detail": f"{expr}×{status}"})
            elif expr != DEFINITE and (status != SUPPORT or claim_gaps):
                quals.append({"code": "Q2_RESIDUAL_UNCERTAINTY", "claim_id": c.claim_id, "goal_id": None,
                              "reason_zh": QUAL_TEXT["Q2_RESIDUAL_UNCERTAINTY"],
                              "detail": f"{expr}×{status}；缺口 {c.gap_ids}"})
            if cell["judgement"] == "UNDERCLAIM":
                quals.append({"code": "Q7_UNDERCLAIM", "claim_id": c.claim_id, "goal_id": None,
                              "reason_zh": QUAL_TEXT["Q7_UNDERCLAIM"], "detail": cell["cell"]})

        main_basis, missing = _basis_items(c, run)
        for g in claim_gaps:
            missing.append(
                {
                    "gap_id": g.gap_id,
                    "gap_type": g.gap_type,
                    "criticality": g.criticality,
                    "description": g.description,
                }
            )
        rows.append(
            {
                "claim_id": c.claim_id,
                "text": c.text,
                "expression": expr,
                "expression_zh": EXPRESSION_ZH.get(expr, expr),
                "expression_hits": expr_hits,
                "upstream_strength": c.upstream_strength,
                "status": status,
                "status_zh": STATUS_ZH.get(status, status),
                "status_source": c.status_source,
                "verdict_reason": c.verdict_reason,
                "checked": bool([x for x in c.check_ids if x in checks_by_id]),
                "main_basis": main_basis,
                "missing_or_conflicting": missing,
                "gap_ids": list(c.gap_ids),
                "affected_goals": goals_of,
                "linkage_method": link_method.get(c.claim_id, "none"),
                "actions": [
                    {
                        "action_id": a.action_id,
                        "action_type": a.action_type,
                        "tool": a.tool,
                        "executability": a.executability,
                    }
                    for a in (actions_by_id.get(x) for x in c.action_ids)
                    if a
                ],
                "uncertainty": cell,
                "is_main": is_main,
                "is_high_risk": is_high,
                "high_risk_basis": basis,
                "severe": bool(severe_code),
                "severe_code": severe_code,
                "blocker_codes": codes,
                "review_status": c.review_status,
            }
        )

    row_by_id = {r["claim_id"]: r for r in rows}

    # ---------- 维度 1：证据支持度 ----------
    asserting = [r for r in rows if r["expression"] in ASSERTING_EXPRESSIONS]
    sup_breakdown = {s: sum(1 for r in asserting if r["status"] == s) for s in STATUSES}
    sup_breakdown["excluded_declared_unknown"] = sum(1 for r in rows if r["expression"] == DECLARED_UNKNOWN)
    support = ratio(
        sup_breakdown[SUPPORT], len(asserting), "回答中没有作出断言的结论（分母为 0）"
    )
    support["breakdown"] = sup_breakdown
    support["rule"] = (
        "分母=措辞为 DEFINITE/HEDGED/SCOPED_PARTIAL 的结论数；分子=其中上游状态为 SUPPORT 的条数。"
        "UNKNOWN 不给半分。DECLARED_UNKNOWN 不计入。"
    )

    # ---------- 维度 2：问题回应覆盖度 ----------
    goal_rows: List[Dict[str, Any]] = []
    cov_breakdown = {s: 0 for s in GOAL_STATES}
    lexical_goals: List[str] = []
    for g in run.goals:
        linked = g2c.get(g.goal_id, [])
        lr = [row_by_id[x] for x in linked if x in row_by_id]
        methods = sorted({link_method.get(x, "none") for x in linked})
        if lr and all(m == "lexical_fallback" for m in methods):
            lexical_goals.append(g.goal_id)
        asserting_lr = [r for r in lr if r["expression"] in ASSERTING_EXPRESSIONS]
        if any(r["status"] == SUPPORT for r in asserting_lr):
            state = "ADDRESSED_SUPPORTED"
        elif any(r["expression"] == DECLARED_UNKNOWN for r in lr):
            state = "ADDRESSED_DECLARED_UNKNOWN"
        elif asserting_lr:
            state = "ADDRESSED_UNSUPPORTED"
        else:
            state = "NOT_ADDRESSED"
        cov_breakdown[state] += 1
        goal_rows.append(
            {
                "goal_id": g.goal_id,
                "text": g.text,
                "question_type": g.question_type,
                "coverage_state": state,
                "coverage_state_zh": GOAL_STATE_ZH[state],
                "linked_claims": linked,
                "linkage_method": (
                    "none" if not linked else ("lexical_fallback" if g.goal_id in lexical_goals else "upstream")
                ),
                "upstream_answered": g.upstream_answered,
            }
        )
        if state == "NOT_ADDRESSED":
            quals.append({"code": "Q1_UNADDRESSED_GOAL", "claim_id": None, "goal_id": g.goal_id,
                          "reason_zh": QUAL_TEXT["Q1_UNADDRESSED_GOAL"], "detail": g.text})
        if g.goal_id in lexical_goals:
            quals.append({"code": "Q4_LEXICAL_FALLBACK", "claim_id": None, "goal_id": g.goal_id,
                          "reason_zh": QUAL_TEXT["Q4_LEXICAL_FALLBACK"], "detail": f"关联结论 {linked}"})
    addressed = len(run.goals) - cov_breakdown["NOT_ADDRESSED"]
    coverage = ratio(addressed, len(run.goals), "上游未抽取出任何用户目标（分母为 0）")
    coverage["breakdown"] = dict(cov_breakdown, lexical_fallback_goals=len(lexical_goals))
    coverage["rule"] = (
        "分母=用户目标数；分子=有关联结论（DEFINITE/HEDGED/SCOPED_PARTIAL）或明确声明无法确定"
        "（DECLARED_UNKNOWN）的目标数。关联优先用上游 related_goals/covers_goals/边，退化为词面匹配时标 lexical_fallback。"
    )

    # ---------- 维度 3：不确定性表达准确性 ----------
    unc_num = sum(r["uncertainty"]["score"] for r in rows)
    uncertainty = ratio(unc_num, len(rows), "没有可评价的结论（分母为 0）")
    judg = {}
    cells = {}
    for r in rows:
        judg[r["uncertainty"]["judgement"]] = judg.get(r["uncertainty"]["judgement"], 0) + 1
        cells[r["uncertainty"]["cell"]] = cells.get(r["uncertainty"]["cell"], 0) + 1
    checked_rows = [r for r in rows if r["checked"]]
    unchecked_unknown = [r["claim_id"] for r in rows if not r["checked"] and r["status"] == "UNKNOWN"]
    uncertainty["breakdown"] = {
        "judgements": dict(sorted(judg.items())),
        "cells": dict(sorted(cells.items())),
        "unchecked_default_unknown": len(unchecked_unknown),
        "checked_only": ratio(
            sum(r["uncertainty"]["score"] for r in checked_rows), len(checked_rows),
            "没有任何被 check 命中的结论",
        ),
    }
    uncertainty["rule"] = (
        "对每条结论按 policy.expression_matrix 的 (措辞×状态) 查表得分，分母=全部结论。"
        "如实声明无法确定（DECLARED_UNKNOWN×UNKNOWN/MISSING_RULE/CONFLICT）得满分。"
        "breakdown.checked_only 仅供参考：排除了“未被任何 check 命中而默认 UNKNOWN”的结论。"
    )

    if not rows:
        quals.append({"code": "Q8_NO_CLAIMS", "claim_id": None, "goal_id": None,
                      "reason_zh": QUAL_TEXT["Q8_NO_CLAIMS"], "detail": None})

    # ---------- 开放缺口 ----------
    for g in run.gaps:
        if g.gap_id in gaps_cited_by_blockers:
            continue
        quals.append({"code": "Q3_OPEN_GAP", "claim_id": None, "goal_id": None,
                      "reason_zh": QUAL_TEXT["Q3_OPEN_GAP"],
                      "detail": f"{g.gap_id} {g.gap_type} {g.criticality}：{g.description}", "gap_id": g.gap_id})

    # ---------- 建链风险 ----------
    br = run.build_risks or {}
    rec_texts = [r.get("text", "") for r in br.get("recommendations_unscored") or []]
    if run.answer_text:
        mapped_texts = [_norm(r["text"]) for r in rows] + [_norm(t) for t in rec_texts]
        mapped_texts = [t for t in mapped_texts if t]
        unmapped = []
        for s in _SPLIT_SENT.split(run.answer_text):
            ns = _norm(s)
            if not ns:
                continue
            if not any(t in ns or ns in t for t in mapped_texts):
                unmapped.append(s.strip())
        unmapped_sentences = {"count": len(unmapped), "items": unmapped}
    else:
        unmapped_sentences = {"count": None, "items": [], "reason": "未提供回答原文"}
    goals_without_claims = [g["goal_id"] for g in goal_rows if not g["linked_claims"]]
    claims_without_checks = [r["claim_id"] for r in rows if not r["checked"]]
    lexical_links = sum(1 for r in rows if r["linkage_method"] == "lexical_fallback")
    build_risks = {
        "unmapped_sentences": unmapped_sentences,
        "goals_without_claims": goals_without_claims,
        "goals_lexical_fallback": lexical_goals,
        "lexical_fallback_links": lexical_links,
        "orphan_evidence": list(br.get("orphan_evidence") or []),
        "claims_without_checks": claims_without_checks,
        "unchecked_default_unknown": unchecked_unknown,
        "review_status": {
            k: br.get(k)
            for k in ("proposed_nodes", "unresolved_nodes", "proposed_edges", "unresolved_edges", "proposed_claims")
        },
        "gap_missing_condition_not_node": list(br.get("gap_missing_condition_not_node") or []),
        "dangling_action_gap_refs": list(br.get("dangling_action_gap_refs") or []),
        "recommendations_unscored": list(br.get("recommendations_unscored") or []),
        "b_review_unmatched": list(br.get("b_review_unmatched") or []),
        "scope_statement": "本成绩单只覆盖已建模条件，不能证明证据图完整或已发现全部适用规则。",
    }
    qualifying = set(gates.get("qualifying_build_risks") or [])
    risk_counts = {
        "claims_without_checks": len(claims_without_checks),
        "goals_without_claims": len(goals_without_claims),
        "lexical_fallback_links": lexical_links,
        "unmapped_sentences": unmapped_sentences["count"] or 0,
        "orphan_evidence": len(build_risks["orphan_evidence"]),
    }
    for k in sorted(qualifying):
        if risk_counts.get(k):
            quals.append({"code": "Q5_BUILD_RISK", "claim_id": None, "goal_id": None,
                          "reason_zh": QUAL_TEXT["Q5_BUILD_RISK"], "detail": f"{k}={risk_counts[k]}"})

    # ---------- 等级 ----------
    labels = (policy.get("grades") or {}).get("labels_zh") or {}
    if blockers or severe:
        grade = "INSUFFICIENT"
    elif quals:
        grade = "QUALIFIED"
    else:
        grade = "SUFFICIENT_IN_SCOPE"

    # ---------- 综合分 ----------
    weights = policy.get("weights") or {}
    dims = {"support": support, "coverage": coverage, "uncertainty": uncertainty}
    for k, d in dims.items():
        d["weight"] = weights.get(k)
    num = 0.0
    wsum = 0.0
    for k, d in dims.items():
        if d["value"] is not None and weights.get(k):
            num += d["value"] * float(weights[k])
            wsum += float(weights[k])
    overall_value = _round(num / wsum) if wsum else None
    hide = (policy.get("overall") or {}).get("hide_when_blockers", True)
    overall_display = not (hide and (blockers or severe)) and overall_value is not None

    # ---------- 复核顺序 ----------
    seq: List[str] = []
    for bucket in (
        [s["claim_id"] for s in severe],
        [b["claim_id"] for b in blockers],
        [q["claim_id"] for q in quals if q.get("claim_id")],
    ):
        for cid in bucket:
            if cid not in seq:
                seq.append(cid)

    # ---------- 补证 ----------
    execs = [a.executability for a in run.actions]
    supplement = {
        "plan_action_count": len(run.actions),
        "executable": execs.count("executable"),
        "needs_confirmation": execs.count("needs_confirmation"),
        "manual": execs.count("manual"),
        "actions": [
            {
                "action_id": a.action_id,
                "action_type": a.action_type,
                "tool": a.tool,
                "executability": a.executability,
                "priority": a.priority,
                "gap_ids": list(a.gap_ids),
                "target_claims": list(a.target_claims),
                "known_arguments": a.known_arguments,
                "pending_arguments": a.pending_arguments,
                "success_criterion": a.success_criterion,
            }
            for a in run.actions
        ],
    }

    gaps_out = [
        {
            "gap_id": g.gap_id,
            "gap_type": g.gap_type,
            "criticality": g.criticality,
            "description": g.description,
            "affected_claims": list(g.affected_claims),
            "affected_claim_texts": [row_by_id[x]["text"] for x in g.affected_claims if x in row_by_id],
            "cited_by_blocker": g.gap_id in gaps_cited_by_blockers,
        }
        for g in run.gaps
    ]

    scope_note = policy.get("scope_note") or ""
    return {
        "scorecard_version": SCORECARD_VERSION,
        "rule_version": policy.get("version"),
        "policy_version": policy.get("version"),
        "policy_status": policy.get("status"),
        "policy_sha256": policy_sha256(policy),
        "run_id": run.run_id,
        "case_id": run.case_id,
        "upstream_versions": dict(run.upstream_versions),
        "source": dict(run.source),
        "question": run.question,
        "grade": grade,
        "grade_label_zh": labels.get(grade, grade),
        "high_risk_alert": bool(severe),
        # 08B 的看板把告警当作一句话显示；这里给出可直接展示的中文文本（无严重问题时为空串）
        "high_risk_alert_text": "；".join(
            f"{x.get('claim_id')}「{x.get('text')}」：{x.get('reason_zh')}" for x in severe
        ),
        "support_score": support["value"],
        "coverage_score": coverage["value"],
        "uncertainty_score": uncertainty["value"],
        "overall": overall_value,
        "overall_display": overall_display,
        "blockers": blockers,
        "qualifications": quals,
        "severe_issues": severe,
        "dimensions": dims,
        "review_sequence": seq,
        "claims": rows,
        "goals": goal_rows,
        "gaps": gaps_out,
        "build_risks": build_risks,
        "supplement": supplement,
        "scope_note": scope_note,
        "score_semantics": policy.get("score_semantics") or "",
        "notes": list(run.notes),
        "generated_by": {
            "package": "confidence_07a",
            "package_version": _version(),
            "scorecard_version": SCORECARD_VERSION,
            "adapter": run.source.get("adapter"),
            "model_called": False,
        },
    }


# --------------------------------------------------------------------------
# diff_scorecards
# --------------------------------------------------------------------------


def _claim_key_map(card: dict) -> Dict[str, dict]:
    return {c["claim_id"]: c for c in card.get("claims") or []}


def _match_claims(before: dict, after: dict) -> Tuple[List[Tuple[dict, dict]], List[dict], List[dict]]:
    """先按 claim_id 且原文相同匹配，再按原文匹配。"""
    b_list = list(before.get("claims") or [])
    a_list = list(after.get("claims") or [])
    pairs: List[Tuple[dict, dict]] = []
    used_a = set()
    a_by_id = {c["claim_id"]: c for c in a_list}
    rest_b = []
    for b in b_list:
        a = a_by_id.get(b["claim_id"])
        if a is not None and _norm(a["text"]) == _norm(b["text"]) and a["claim_id"] not in used_a:
            pairs.append((b, a))
            used_a.add(a["claim_id"])
        else:
            rest_b.append(b)
    removed = []
    for b in rest_b:
        cand = [a for a in a_list if a["claim_id"] not in used_a and _norm(a["text"]) == _norm(b["text"])]
        if cand:
            pairs.append((b, cand[0]))
            used_a.add(cand[0]["claim_id"])
        else:
            removed.append(b)
    added = [a for a in a_list if a["claim_id"] not in used_a]
    return pairs, added, removed


def _issue_keys(card: dict, field: str) -> Dict[Tuple[str, str], dict]:
    out = {}
    for x in card.get(field) or []:
        out[(x.get("code"), _norm(x.get("text") or ""))] = x
    return out


def _gap_key(g: dict) -> Tuple[str, str, str]:
    return (
        g.get("gap_type") or "",
        "|".join(sorted(_norm(t) for t in g.get("affected_claim_texts") or [])),
        _norm(g.get("description") or ""),
    )


def diff_scorecards(before: dict, after: dict) -> dict:
    """补证前后成绩单对比（同一 run_id）。"""
    warnings: List[str] = []
    if before.get("run_id") != after.get("run_id"):
        warnings.append(f"run_id 不一致：{before.get('run_id')} vs {after.get('run_id')}")
    dims = {}
    for k in ("support", "coverage", "uncertainty"):
        b = (before.get("dimensions") or {}).get(k) or {}
        a = (after.get("dimensions") or {}).get(k) or {}
        bv, av = b.get("value"), a.get("value")
        dims[k] = {
            "before": bv,
            "after": av,
            "delta": _round(av - bv) if (av is not None and bv is not None) else None,
            "before_fraction": [b.get("numerator"), b.get("denominator")],
            "after_fraction": [a.get("numerator"), a.get("denominator")],
        }
    pairs, added, removed = _match_claims(before, after)
    transitions = []
    summary: Dict[str, int] = {}
    for b, a in pairs:
        t = {
            "claim_id_before": b["claim_id"],
            "claim_id_after": a["claim_id"],
            "text": a["text"],
            "status_before": b["status"],
            "status_after": a["status"],
            "changed": b["status"] != a["status"],
            "judgement_before": (b.get("uncertainty") or {}).get("judgement"),
            "judgement_after": (a.get("uncertainty") or {}).get("judgement"),
            "blockers_before": b.get("blocker_codes") or [],
            "blockers_after": a.get("blocker_codes") or [],
        }
        transitions.append(t)
        if t["changed"]:
            key = f"{b['status']}→{a['status']}"
            summary[key] = summary.get(key, 0) + 1

    def set_diff(field):
        bk, ak = _issue_keys(before, field), _issue_keys(after, field)
        return (
            [ak[k] for k in ak if k not in bk],
            [bk[k] for k in bk if k not in ak],
        )

    blk_new, blk_gone = set_diff("blockers")
    sev_new, sev_gone = set_diff("severe_issues")
    bg = {_gap_key(g): g for g in before.get("gaps") or []}
    ag = {_gap_key(g): g for g in after.get("gaps") or []}
    gaps_new = [ag[k] for k in ag if k not in bg]
    gaps_closed = [bg[k] for k in bg if k not in ag]

    gb, ga = before.get("grade"), after.get("grade")
    expl: List[str] = []
    if gb != ga:
        expl.append(f"等级由 {before.get('grade_label_zh')}（{gb}）变为 {after.get('grade_label_zh')}（{ga}）。")
    else:
        expl.append(f"等级保持 {after.get('grade_label_zh')}（{ga}）。")
    for t in transitions:
        if t["changed"]:
            expl.append(f"结论“{t['text']}”状态 {t['status_before']} → {t['status_after']}。")
    for g in gaps_closed:
        expl.append(f"缺口 {g.get('gap_id')}（{g.get('gap_type')}：{g.get('description')}）在补证后不再出现。")
    for g in gaps_new:
        expl.append(f"补证后新增缺口 {g.get('gap_id')}（{g.get('gap_type')}：{g.get('description')}）。")
    for b in blk_gone:
        expl.append(f"阻断项 {b.get('code')}（{b.get('text')}）已消除。")
    for b in blk_new:
        expl.append(f"新增阻断项 {b.get('code')}（{b.get('text')}）：{b.get('reason_zh')}。")
    if gb == ga and not any(t["changed"] for t in transitions) and not gaps_closed and not blk_gone:
        expl.append("补证未改变任何结论状态；若补证数据与缺口相关，请检查上游是否重算了对应检查。")
    return {
        "diff_version": "07a-scorecard-diff-v1",
        "run_id": after.get("run_id"),
        "case_id": after.get("case_id"),
        "warnings": warnings,
        "versions": {
            "before": {
                "upstream_versions": before.get("upstream_versions"),
                "policy_version": before.get("policy_version"),
                "policy_sha256": before.get("policy_sha256"),
            },
            "after": {
                "upstream_versions": after.get("upstream_versions"),
                "policy_version": after.get("policy_version"),
                "policy_sha256": after.get("policy_sha256"),
            },
        },
        "grade": {"before": gb, "after": ga, "changed": gb != ga,
                  "before_zh": before.get("grade_label_zh"), "after_zh": after.get("grade_label_zh")},
        "high_risk_alert": {"before": before.get("high_risk_alert"), "after": after.get("high_risk_alert")},
        "dimensions": dims,
        "claim_transitions": transitions,
        "transition_summary": dict(sorted(summary.items())),
        "claims_added": [{"claim_id": c["claim_id"], "text": c["text"], "status": c["status"]} for c in added],
        "claims_removed": [{"claim_id": c["claim_id"], "text": c["text"], "status": c["status"]} for c in removed],
        "blockers_added": blk_new,
        "blockers_removed": blk_gone,
        "severe_added": sev_new,
        "severe_removed": sev_gone,
        "gaps_added": gaps_new,
        "gaps_closed": gaps_closed,
        "explanation_zh": expl,
        "score_semantics": after.get("score_semantics") or before.get("score_semantics"),
    }
