"""01A egraph v1 产物（graph/plan/scorecard JSON）-> RunView 适配器。

字段映射以 survey/01_evidence_graph_01A.md 为准（01A `egraph/models.py:91-168`、
`graph.py`、`plan.py`）。本适配器只做“搬运 + 关联”，不改写任何结论状态：
claim.status 直接取 01A 节点的 ``evidence_status``。

如果 01A 字段改名，只需要改本文件里的 ``_F`` 映射与对应取值函数。
"""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple

from ..model import (
    STATUSES,
    UNKNOWN,
    ActionView,
    CheckView,
    ClaimView,
    EvidenceRef,
    GapView,
    GoalView,
    RunView,
)

ADAPTER_NAME = "egraph_v1"
ADAPTER_VERSION = "1.0.0"

# 01A 字段名集中在这里，上游改名时只改这一处
_F = {
    "node_type": "type",
    "claim_type": "claim",
    "obligation_type": "obligation",
    "evidence_types": ("evidence", "rule", "fact"),
    "status": "evidence_status",
    "strength": "assertion_strength",
    "goal_link_edge_types": ("supports", "addresses"),
    "evidence_edge_types": ("supports", "refutes", "checks", "uses", "derived_from"),
    "premise_edge_types": ("depends_on", "requires", "derived_from"),
}

# 严重度排序：推荐类结论按前提状态取“最差”时使用（只聚合上游状态，不重判）
_WORST_ORDER = ("REFUTE", "CONFLICT", "MISSING_RULE", "UNKNOWN", "SUPPORT")

_TRACE_RE = re.compile(r"^trace\[([^\]]+)\]")


def _read_json(path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _uniq(seq) -> List[Any]:
    seen = set()
    out = []
    for x in seq:
        if x is None or x in seen:
            continue
        seen.add(x)
        out.append(x)
    return out


def event_id_from_locator(locator: Optional[str]) -> Optional[str]:
    """``trace[c1].result.x`` -> ``c1``。"""
    if not locator:
        return None
    m = _TRACE_RE.match(str(locator))
    return m.group(1) if m else None


def locator_to_pointer(locator: Optional[str], log_record: Optional[dict]) -> Optional[str]:
    """把 01A locator 转成 RFC6901 风格指针（需要原始日志确定事件下标）。

    ``trace[c1].result.shifts[0].units`` -> ``/trace/1/result/shifts/0/units``。
    无法解析时返回 None（不猜）。
    """
    if not locator or not log_record:
        return None
    m = _TRACE_RE.match(str(locator))
    if not m:
        return None
    event_id = m.group(1)
    trace = log_record.get("trace") or []
    idx = None
    for i, ev in enumerate(trace):
        if isinstance(ev, dict) and str(ev.get("id")) == event_id:
            idx = i
            break
    if idx is None:
        return None
    rest = str(locator)[m.end():]
    parts: List[str] = []
    for tok in re.findall(r"\.([^.\[\]]+)|\[(\d+)\]", rest):
        key = tok[0] if tok[0] else tok[1]
        parts.append(key.replace("~", "~0").replace("/", "~1"))
    return "/trace/%d" % idx + "".join("/" + p for p in parts)


def _sha16(text: str) -> str:
    return hashlib.sha256((text or "").encode("utf-8")).hexdigest()[:16]


def load_run_from_artifacts(
    graph: dict,
    plan: Optional[dict],
    log_record: Optional[dict] = None,
    method: str = "rule",
) -> RunView:
    """把 01A 的 graph/plan dict 转成 RunView。"""
    if not isinstance(graph, dict):
        raise ValueError("graph 必须是 01A graph.json 的 dict")
    plan = plan or {}
    run_id = str(graph.get("run_id") or "")
    case_id = str(graph.get("case_id") or "")
    task = graph.get("task") or {}
    notes: List[str] = []

    if log_record is not None:
        if log_record.get("run_id") and str(log_record.get("run_id")) != run_id:
            raise ValueError(f"日志 run_id {log_record.get('run_id')} 与 graph run_id {run_id} 不一致")
    if plan and plan.get("run_id") and str(plan.get("run_id")) != run_id:
        raise ValueError(f"plan run_id {plan.get('run_id')} 与 graph run_id {run_id} 不一致")

    question = (log_record or {}).get("user_question") or task.get("question") or ""
    answer_text = (log_record or {}).get("ai_answer") or ""
    if not answer_text:
        notes.append("未提供原始日志记录，answer_text 为空；无法统计未映射句子数。")

    nodes: List[dict] = list(graph.get("nodes") or [])
    edges: List[dict] = list(graph.get("edges") or [])
    checks_raw: List[dict] = list(graph.get("checks") or [])
    gaps_raw: List[dict] = list(graph.get("gaps") or [])
    actions_raw: List[dict] = list(plan.get("actions") or [])
    by_id = {n.get("id"): n for n in nodes if n.get("id")}

    # ---------- goals ----------
    goals: List[GoalView] = []
    goal_order: List[str] = []
    for g in graph.get("goals") or []:
        gid = str(g.get("id"))
        goal_order.append(gid)
        goals.append(
            GoalView(
                goal_id=gid,
                text=g.get("text") or "",
                question_type=g.get("question_type"),
                upstream_answered=g.get("answered"),
                raw={"subject": g.get("subject"), "coverage_note": g.get("coverage_note")},
            )
        )
    goal_ids = set(goal_order)

    # ---------- 边索引 ----------
    touched = set()
    in_edges: Dict[str, List[dict]] = {}
    out_edges: Dict[str, List[dict]] = {}
    for e in edges:
        s, t = e.get("source"), e.get("target")
        touched.add(s)
        touched.add(t)
        in_edges.setdefault(t, []).append(e)
        out_edges.setdefault(s, []).append(e)

    # ---------- evidence ----------
    evidence: Dict[str, EvidenceRef] = {}
    for n in nodes:
        if n.get(_F["node_type"]) not in _F["evidence_types"]:
            continue
        nid = n["id"]
        locator = n.get("locator")
        event_id = n.get("record_id") or event_id_from_locator(locator)
        excerpt = n.get("excerpt") or (n.get("content") or "")[:160] or None
        evidence[nid] = EvidenceRef(
            evidence_id=nid,
            run_id=run_id,
            event_id=event_id,
            tool=n.get("tool"),
            arguments=dict(n.get("arguments") or {}),
            json_path=locator,
            excerpt=excerpt,
            value=n.get("value"),
            unit=n.get("unit"),
            has_edges=nid in touched,
            raw={
                "node_type": n.get("type"),
                "review_status": n.get("review_status"),
                "pointer": locator_to_pointer(locator, log_record),
                "meta": n.get("meta") or {},
            },
        )

    # ---------- checks ----------
    checks: List[CheckView] = []
    for c in checks_raw:
        loc = c.get("locator")
        checks.append(
            CheckView(
                check_id=str(c.get("check_id")),
                kind=c.get("kind"),
                status=c.get("status"),
                verdict=c.get("verdict"),
                category=c.get("category"),
                affected_claims=list(c.get("affected_claims") or []),
                evidence_ref=c.get("evidence_ref"),
                locator=loc,
                expected=c.get("expected"),
                actual=c.get("actual"),
                detail=c.get("detail"),
                raw={
                    "description": c.get("description"),
                    "rule_id": c.get("rule_id"),
                    "target_node": c.get("target_node"),
                    "event_id": event_id_from_locator(loc),
                    "pointer": locator_to_pointer(loc, log_record),
                },
            )
        )

    # ---------- gaps ----------
    gaps: List[GapView] = []
    gap_ids_all = set()
    gap_missing_condition_not_node: List[str] = []
    for g in gaps_raw:
        gid = str(g.get("id"))
        gap_ids_all.add(gid)
        mc = g.get("missing_condition")
        if mc and mc not in by_id:
            gap_missing_condition_not_node.append(gid)
        gaps.append(
            GapView(
                gap_id=gid,
                gap_type=str(g.get("type") or ""),
                affected_claims=list(g.get("affected_claims") or []),
                criticality=g.get("criticality"),
                description=g.get("description"),
                raw={
                    "missing_condition": mc,
                    "target_source": g.get("target_source"),
                    "mandatory": g.get("mandatory"),
                },
            )
        )

    # ---------- actions ----------
    actions: List[ActionView] = []
    dangling_action_gaps: List[str] = []
    for a in actions_raw:
        aid = str(a.get("id"))
        for gid in a.get("gap_ids") or []:
            if gid not in gap_ids_all:
                dangling_action_gaps.append(f"{aid}->{gid}")
        actions.append(
            ActionView(
                action_id=aid,
                action_type=str(a.get("action_type") or ""),
                gap_ids=list(a.get("gap_ids") or []),
                target_claims=list(a.get("target_claims") or []),
                tool=a.get("tool"),
                known_arguments=dict(a.get("known_arguments") or {}),
                pending_arguments=dict(a.get("pending_arguments") or {}),
                success_criterion=a.get("success_criterion"),
                executability=a.get("executability"),
                priority=a.get("priority"),
                raw={
                    "expected_outcome": a.get("expected_outcome"),
                    "rationale": a.get("rationale"),
                    "replaces_actions": a.get("replaces_actions"),
                },
            )
        )

    # ---------- claims ----------
    claim_nodes = [n for n in nodes if n.get(_F["node_type"]) == _F["claim_type"]]
    claim_nodes.sort(key=lambda n: ((n.get("meta") or {}).get("order", 10 ** 6), str(n.get("id"))))
    claims: List[ClaimView] = []
    bad_status: List[str] = []
    for n in claim_nodes:
        cid = n["id"]
        meta = n.get("meta") or {}
        related = [g for g in (n.get("related_goals") or []) if g in goal_ids]
        for e in out_edges.get(cid, []):
            if e.get("type") in _F["goal_link_edge_types"] and e.get("target") in goal_ids:
                related.append(e["target"])
        for pos in meta.get("covers_goals") or []:
            if isinstance(pos, int) and 0 <= pos < len(goal_order):
                related.append(goal_order[pos])
        related = _uniq(related)

        ev_ids = []
        for e in in_edges.get(cid, []):
            src = e.get("source")
            if src in evidence and e.get("type") in _F["evidence_edge_types"]:
                ev_ids.append(src)
        chk_ids = [c.check_id for c in checks if cid in c.affected_claims]
        for x in meta.get("checks") or []:
            chk_ids.append(x)
        chk_ids = _uniq(chk_ids)
        for c in checks:
            if c.check_id in chk_ids and c.evidence_ref and c.evidence_ref in evidence:
                ev_ids.append(c.evidence_ref)

        status = n.get(_F["status"])
        if status not in STATUSES:
            bad_status.append(cid)
            notes.append(f"{cid} 上游状态 {status!r} 不在五态内，按 UNKNOWN 记录（未重判）。")
            status = UNKNOWN
        claims.append(
            ClaimView(
                claim_id=cid,
                text=n.get("content") or "",
                status=status,
                upstream_strength=n.get(_F["strength"]),
                related_goals=related,
                linkage_method="upstream" if related else "none",
                evidence_ids=_uniq(ev_ids),
                check_ids=chk_ids,
                gap_ids=[g.gap_id for g in gaps if cid in g.affected_claims],
                action_ids=[a.action_id for a in actions if cid in a.target_claims],
                scope_limited=n.get("scope_limited"),
                value=n.get("value"),
                unit=n.get("unit"),
                verdict_reason=meta.get("verdict_reason"),
                review_status=n.get("review_status"),
                status_source="01A",
                raw={
                    "order": meta.get("order"),
                    "source_span": meta.get("source_span"),
                    "created_by": n.get("created_by"),
                    "entities": meta.get("entities") or [],
                },
            )
        )

    # ---------- 推荐类（01A 改名为 OBL 的结论） ----------
    claim_ids = {c.claim_id for c in claims}
    claim_by_id = {c.claim_id: c for c in claims}
    unscored_recs: List[Dict[str, Any]] = []
    for n in nodes:
        if n.get(_F["node_type"]) != _F["obligation_type"]:
            continue
        oid = n["id"]
        premises = [
            e.get("target")
            for e in out_edges.get(oid, [])
            if e.get("type") in _F["premise_edge_types"] and e.get("target") in claim_ids
        ]
        premises += [
            e.get("source")
            for e in in_edges.get(oid, [])
            if e.get("type") in ("supports", "requires") and e.get("source") in claim_ids
        ]
        premises = _uniq(premises)
        if premises:
            statuses = [claim_by_id[p].status for p in premises]
            worst = next(s for s in _WORST_ORDER if s in statuses)
            claims.append(
                ClaimView(
                    claim_id=oid,
                    text=n.get("content") or "",
                    status=worst,
                    upstream_strength="recommendation",
                    related_goals=_uniq(g for p in premises for g in claim_by_id[p].related_goals),
                    linkage_method="upstream",
                    evidence_ids=[],
                    gap_ids=_uniq(g for p in premises for g in claim_by_id[p].gap_ids),
                    action_ids=[a.action_id for a in actions if oid in a.target_claims],
                    review_status=n.get("review_status"),
                    verdict_reason="推荐类结论：状态取其前提结论中最不利的上游状态（聚合，非重判）",
                    status_source="01A",
                    raw={"premises": premises, "derived_from_claim": (n.get("meta") or {}).get("derived_from_claim")},
                )
            )
        else:
            unscored_recs.append({"id": oid, "text": n.get("content") or ""})

    # ---------- 建链风险（原始计数，scorecard 汇总） ----------
    proposed_nodes = sum(1 for n in nodes if n.get("review_status") == "proposed")
    unresolved_nodes = sum(1 for n in nodes if n.get("review_status") == "unresolved")
    proposed_edges = sum(1 for e in edges if e.get("review_status") == "proposed")
    unresolved_edges = sum(1 for e in edges if e.get("review_status") == "unresolved")
    orphan_ev = sorted(
        eid for eid, ev in evidence.items() if ev.raw.get("node_type") == "evidence" and not ev.has_edges
    )
    build_risks = {
        "orphan_evidence": orphan_ev,
        "proposed_nodes": proposed_nodes,
        "unresolved_nodes": unresolved_nodes,
        "proposed_edges": proposed_edges,
        "unresolved_edges": unresolved_edges,
        "proposed_claims": sum(1 for c in claims if c.review_status == "proposed"),
        "gap_missing_condition_not_node": gap_missing_condition_not_node,
        "dangling_action_gap_refs": dangling_action_gaps,
        "recommendations_unscored": unscored_recs,
        "invalid_upstream_status_claims": bad_status,
    }
    if unscored_recs:
        notes.append(
            f"{len(unscored_recs)} 条推荐类结论（OBL）上游未给出前提关联，未计入评分，只在建链风险中披露。"
        )

    upstream_versions = {
        "graph_version": graph.get("graph_version"),
        "plan_version": plan.get("plan_version") if plan else None,
        "answer_version": (log_record or {}).get("answer_version"),
        "answer_sha256": _sha16(answer_text) if answer_text else None,
        "proposal_status": graph.get("proposal_status"),
    }
    scope = {
        "scope_declaration": graph.get("scope_declaration") or {},
        "limitations": list(graph.get("limitations") or []),
        "paths": len(graph.get("paths") or []),
        "common_necessary_conditions": len(graph.get("common_necessary_conditions") or []),
        "graph_changes": list(graph.get("changes") or []),
    }
    source = {
        "method": method,
        "engine": "01A-egraph",
        "adapter": ADAPTER_NAME,
        "adapter_version": ADAPTER_VERSION,
        "log_record_available": log_record is not None,
    }
    return RunView(
        run_id=run_id,
        case_id=case_id,
        question=question,
        answer_text=answer_text,
        goals=goals,
        claims=claims,
        evidence=evidence,
        checks=checks,
        gaps=gaps,
        actions=actions,
        scope=scope,
        upstream_versions=upstream_versions,
        source=source,
        build_risks=build_risks,
        notes=notes,
    )


def _sibling(path: Path, kind: str) -> Optional[Path]:
    name = path.name
    if name.endswith("_graph.json"):
        cand = path.with_name(name[: -len("_graph.json")] + f"_{kind}.json")
        if cand.exists():
            return cand
    return None


def load_run_from_files(graph_path, plan_path=None, log_record: Optional[dict] = None, method: str = "rule") -> RunView:
    gp = Path(graph_path)
    graph = _read_json(gp)
    pp = Path(plan_path) if plan_path else _sibling(gp, "plan")
    plan = _read_json(pp) if pp else None
    run = load_run_from_artifacts(graph, plan, log_record=log_record, method=method)
    run.source["files"] = {"graph": gp.name, "plan": pp.name if pp else None}
    if plan is None:
        run.notes.append("未找到 plan 文件，补证动作为空。")
    return run


def load_run_from_06b_result(result_path, log_record: Optional[dict] = None, method: Optional[str] = None) -> RunView:
    """读取 06B（industrial_pytest）单个结果文件，其 ``output`` 内含 graph/plan/scorecard。"""
    rp = Path(result_path)
    payload = _read_json(rp)
    out = payload.get("output") or {}
    graph = out.get("graph")
    if not isinstance(graph, dict):
        raise ValueError(f"{rp.name}: 06B 结果缺少 output.graph")
    kind = str(payload.get("execution_kind") or "")
    if method is None:
        method = "rule" if "rule" in kind else (kind or "unknown")
    run = load_run_from_artifacts(graph, out.get("plan"), log_record=log_record, method=method)
    run.source.update(
        {
            "adapter": ADAPTER_NAME + "+06b",
            "files": {"result": rp.name},
            "execution_kind": payload.get("execution_kind"),
            "model_called": payload.get("model_called"),
            "elapsed_seconds": payload.get("elapsed_seconds"),
            "input_sha256": payload.get("input_sha256"),
            "passed": payload.get("passed"),
        }
    )
    return run


def load_v1_scorecard(scorecard_path_or_dict) -> dict:
    """01A v1 成绩单原样返回（基线对照），也接受 06B 结果文件（取 output.scorecard）。"""
    if isinstance(scorecard_path_or_dict, dict):
        d = scorecard_path_or_dict
    else:
        d = _read_json(Path(scorecard_path_or_dict))
    if "output" in d and isinstance(d["output"], dict) and "scorecard" in d["output"]:
        return d["output"]["scorecard"]
    return d


def _logs_or_empty(log_path) -> Dict[str, dict]:
    if not log_path:
        return {}
    from ..logs import load_logs

    return load_logs(log_path)


def iter_output_dir(output_dir, log_path=None, method="rule") -> Iterator[RunView]:
    """遍历 01A ``output/`` 目录（``<case>_graph.json`` + ``<case>_plan.json``）。"""
    logs = _logs_or_empty(log_path)
    for gp in sorted(Path(output_dir).glob("*_graph.json")):
        graph = _read_json(gp)
        rec = logs.get(str(graph.get("run_id")))
        pp = _sibling(gp, "plan")
        plan = _read_json(pp) if pp else None
        run = load_run_from_artifacts(graph, plan, log_record=rec, method=method)
        run.source["files"] = {"graph": gp.name, "plan": pp.name if pp else None}
        yield run


def latest_06b_files(results_dir) -> List[Path]:
    """06B 目录中每个 run 取最新文件（文件名 ``<run_id>_<时间戳>.json``，按时间戳取最大）。"""
    best: Dict[str, Tuple[int, Path]] = {}
    for p in Path(results_dir).glob("*.json"):
        stem = p.stem
        if "_" not in stem:
            continue
        run_id, ts = stem.rsplit("_", 1)
        try:
            t = int(ts)
        except ValueError:
            continue
        if run_id not in best or t > best[run_id][0]:
            best[run_id] = (t, p)
    return [best[k][1] for k in sorted(best)]


def iter_06b_dir(results_dir, log_path=None, method=None) -> Iterator[RunView]:
    logs = _logs_or_empty(log_path)
    for p in latest_06b_files(results_dir):
        run_id = p.stem.rsplit("_", 1)[0]
        yield load_run_from_06b_result(p, log_record=logs.get(run_id), method=method)


def detect_dir_kind(path) -> str:
    """``01a_output`` / ``06b_results`` / ``unknown``。"""
    p = Path(path)
    if any(p.glob("*_graph.json")):
        return "01a_output"
    if latest_06b_files(p):
        return "06b_results"
    return "unknown"
