"""02B 局部检查（b_review.local_review）覆盖层 —— 可选、保守。

02B 的工业局部检查不使用 01A 的 CLM 编号（见 survey/02_checker_02B.md §1.5），
只能按 02B claim 节点的 ``answer_excerpt`` 与 01A 结论原文对齐。规则：

1. 只处理 02B ``type == "claim"`` 且有 ``answer_excerpt`` 的节点；``fact`` 节点
   不对应回答中的原子结论，只记入 notes。
2. “明确匹配”= 规范化后 excerpt 与某条结论原文相等；或 excerpt 是**恰好一条**结论
   原文的子串，且长度 >= min_excerpt_len、占该结论长度比例 >= min_containment_ratio。
   多条命中、无命中、或同一结论被映射到相互矛盾的 02B 状态，一律不覆盖。
3. 02B 四态里“UNKNOWN + gap MISSING_RULE”等价于 01A 的 MISSING_RULE；若 01A 已是
   MISSING_RULE，不会被降成 UNKNOWN。
4. 覆盖时 ``status_source="02B"``，原 01A 状态保存在 ``raw["status_01A"]``。
   未匹配的 02B 检查写入 ``run.notes`` 与 ``run.build_risks["b_review_unmatched"]``。

本模块不改动 02B 的任何判断，也不重新判定结论。
"""
from __future__ import annotations

import copy
import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..model import MISSING_RULE, STATUSES, UNKNOWN, CheckView, RunView

_PUNCT = re.compile(r"[\s，,。．.！!？?；;：:、“”\"'（）()]+")


def _norm(text: Optional[str]) -> str:
    return _PUNCT.sub("", text or "")


def load_b_review(path_or_obj) -> Dict[str, Dict[str, Any]]:
    """读取 02B 结果，返回 ``run_id -> local_review``。

    接受：industrial_results.json（数组）、单个 bridge 输出 dict、或直接的 local_review dict。
    """
    if isinstance(path_or_obj, (str, Path)):
        with open(path_or_obj, "r", encoding="utf-8") as fh:
            payload = json.load(fh)
    else:
        payload = path_or_obj
    items = payload if isinstance(payload, list) else [payload]
    out: Dict[str, Dict[str, Any]] = {}
    for it in items:
        if not isinstance(it, dict):
            continue
        lr = None
        if isinstance(it.get("b_review"), dict):
            lr = it["b_review"].get("local_review")
        elif "checks" in it and "nodes" in it:
            lr = it
        if isinstance(lr, dict) and lr.get("run_id"):
            out[str(lr["run_id"])] = lr
    return out


def overlay_b_review(run: RunView, local_review: Optional[dict], policy: Optional[dict] = None) -> RunView:
    """返回叠加了 02B 局部检查的新 RunView（不修改入参）。"""
    run = copy.deepcopy(run)
    if not local_review:
        return run
    cfg = ((policy or {}).get("b_review")) or {}
    min_len = int(cfg.get("min_excerpt_len", 4))
    min_ratio = float(cfg.get("min_containment_ratio", 0.3))
    mr_gap_types = set(cfg.get("missing_rule_gap_types", ["MISSING_RULE"]))

    if str(local_review.get("run_id")) != run.run_id:
        run.notes.append(
            f"02B local_review run_id={local_review.get('run_id')} 与本运行 {run.run_id} 不一致，未叠加。"
        )
        return run

    nodes = {n.get("id"): n for n in local_review.get("nodes") or [] if isinstance(n, dict)}
    gaps = [g for g in local_review.get("gaps") or [] if isinstance(g, dict)]
    claim_norm = [(c, _norm(c.text)) for c in run.claims]

    proposals: Dict[str, List[Dict[str, Any]]] = {}
    unmatched: List[Dict[str, Any]] = []
    for chk in local_review.get("checks") or []:
        target = chk.get("target")
        node = nodes.get(target) or {}
        state = chk.get("state")
        rec = {"check_id": chk.get("id"), "target": target, "state": state, "reason": chk.get("reason")}
        if node.get("type") != "claim" or not node.get("answer_excerpt"):
            rec["why"] = "02B 目标不是回答中的原子结论（fact 或无 answer_excerpt）"
            unmatched.append(rec)
            continue
        if state not in STATUSES:
            rec["why"] = "02B 状态不在五态内"
            unmatched.append(rec)
            continue
        ex = _norm(node.get("answer_excerpt"))
        exact = [c for c, t in claim_norm if t and t == ex]
        if len(exact) == 1:
            hit = exact
        else:
            hit = [
                c
                for c, t in claim_norm
                if t and len(ex) >= min_len and ex in t and len(ex) / max(len(t), 1) >= min_ratio
            ]
        if len(hit) != 1:
            rec["why"] = "无明确匹配（0 条或多条候选）" if not hit else f"多条候选：{[c.claim_id for c in hit]}"
            unmatched.append(rec)
            continue
        claim = hit[0]
        # 02B 的 “UNKNOWN + MISSING_RULE 缺口” 等价映射
        eff = state
        if state == UNKNOWN and any(
            target in (g.get("affected_claim_ids") or []) and g.get("gap_type") in mr_gap_types for g in gaps
        ):
            eff = MISSING_RULE
        rec.update({"claim_id": claim.claim_id, "effective_state": eff})
        proposals.setdefault(claim.claim_id, []).append(rec)

    applied: List[Dict[str, Any]] = []
    for claim in run.claims:
        recs = proposals.get(claim.claim_id)
        if not recs:
            continue
        states = {r["effective_state"] for r in recs}
        for r in recs:
            run.checks.append(
                CheckView(
                    check_id="02B:" + str(r["check_id"]),
                    kind="02B_local_check",
                    verdict=r["state"],
                    affected_claims=[claim.claim_id],
                    detail=r.get("reason"),
                    raw={"source": "02B", "target": r["target"], "effective_state": r["effective_state"]},
                )
            )
            claim.check_ids.append("02B:" + str(r["check_id"]))
        if len(states) != 1:
            run.notes.append(f"02B 对 {claim.claim_id} 给出相互矛盾的状态 {sorted(states)}，未覆盖。")
            unmatched.extend(dict(r, why="同一结论的 02B 状态互相矛盾") for r in recs)
            continue
        new = states.pop()
        claim.raw["status_01A"] = claim.status
        claim.raw["b_review_targets"] = [r["target"] for r in recs]
        if new != claim.status:
            applied.append({"claim_id": claim.claim_id, "from": claim.status, "to": new})
            claim.status = new
        claim.status_source = "02B"

    for r in unmatched:
        run.notes.append(f"02B 检查 {r.get('check_id')}（{r.get('state')}）未叠加：{r.get('why')}")
    run.build_risks["b_review_unmatched"] = unmatched
    run.build_risks["b_review_applied"] = applied
    run.source["b_review"] = {
        "analysis_status": local_review.get("analysis_status"),
        "rule_version": local_review.get("rule_version"),
        "matched_claims": sorted(proposals),
        "status_changes": len(applied),
    }
    return run
