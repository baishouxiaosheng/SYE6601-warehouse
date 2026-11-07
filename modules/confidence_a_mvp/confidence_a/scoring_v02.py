"""Hard gates first, then a provisional design score. No model judge and no gold."""

from .contracts import ContractError, validate
from .contracts_v02 import (
    CAUSES, CHECK_NAMES, LEVEL_CODES, LEVELS, POLICY_V02_SCHEMA, SCORECARD_V02_SCHEMA,
    SCORING_VERSION, VERSION_V02, validate_snapshot_v02,
)

DEFAULT_POLICY_V02 = {
    "schema_version": VERSION_V02,
    "policy_version": "graph-risk-demo-0.2",
    "status": "PROVISIONAL",
    "suppress_display_score_on_hard_gate": True,
    "description": "演示约定：硬门槛失败时不展示设计分。设计分是五类计数的等权合并，不是概率，也不是已确认业务规则。",
}

SEMANTICS = "该等级反映已声明范围内的证据与过程质量，不能证明图完整，不能证明已发现全部规则，也不是答案正确概率。"
REF_KEYS = (
    "claim_ids", "obligation_ids", "evidence_ids", "relation_ids",
    "clause_ids", "baseline_ids", "change_ids",
)
BUILD_RISKS = {
    "NO_BASELINE_CHECKLIST", "BASELINE_INCOMPLETE", "BASELINE_OPTIONAL_INCOMPLETE",
    "NO_IDENTIFIED_CLAIMS", "UNMAPPED_CLAIM", "UNMAPPED_CLAIM_NON_IMPACT",
    "CRITICAL_UNEXPANDED", "UNEXPANDED_UNEXPLAINED", "CLAUSE_RESERVED",
    "CRITICAL_RELATION_UNRESOLVED", "CRITICAL_RELATION_UNREVIEWED",
    "RELATION_UNEXPLAINED", "RELATION_RESERVED",
    "SCOPE_UNCLEAR", "SCOPE_UNCLEAR_NON_IMPACT", "STRUCTURE_EXPANSION_OPEN",
}
OPEN_REVIEW = {"proposed", "unresolved"}
KIND_ZH = {"added": "新增", "revised": "修订", "invalidated": "失效"}
TYPE_ZH = {
    "claim": "主张", "obligation": "条件", "relation": "关系", "evidence": "证据", "clause": "条款",
}


def refs(**kwargs):
    data = {key: [] for key in REF_KEYS}
    for key, value in kwargs.items():
        data[key] = list(value)
    return data


def primary_cause(reason_codes):
    for cause in CAUSES:
        if cause in reason_codes:
            return cause
    return None


def ratio(label, numerator, denominator, **extra):
    return {"label": label, "numerator": numerator, "denominator": denominator,
            "value": None if denominator == 0 else numerator / denominator, **extra}


def review_item(code, blocking, priority, reason, cause=None, repair=None, **ref_lists):
    return {
        "code": code, "blocking": blocking, "priority": priority, "reason": reason, "cause": cause,
        "repair_action": None if repair is None else dict(repair),
        "refs": refs(**ref_lists),
    }


def blocking_flags(obligation):
    return (
        obligation["criticality"] == "critical"
        or obligation["required_for_decision"]
        or obligation["must_verify"]
        or obligation["applicability"] == "UNDETERMINED"
    )


def collect_reviews(snapshot):
    items = []
    required = [row for row in snapshot["baseline_checks"] if row["required"]]
    if not required:
        items.append(review_item(
            "NO_BASELINE_CHECKLIST", True, 5,
            "上游没有声明任何必查项。空清单不能当成已覆盖。",
        ))
    for row in snapshot["baseline_checks"]:
        covered = row["status"] in ("COMPLETE", "NOT_APPLICABLE")
        if covered:
            continue
        cause = primary_cause(row["reason_codes"])
        if row["required"]:
            code, priority, blocking = "BASELINE_INCOMPLETE", 10, True
            prefix = "必查未建入图，按未完成计。" if not row["built"] else "必查未完成。"
        else:
            code, priority, blocking = "BASELINE_OPTIONAL_INCOMPLETE", 80, False
            prefix = "非必查清单项未完成，只作保留。"
        codes = "、".join(row["reason_codes"]) if row["reason_codes"] else "无"
        items.append(review_item(
            code, blocking, priority, f"{prefix}原因码：{codes}。{row['reason']}", cause, row["repair_action"],
            baseline_ids=[row["check_id"]], obligation_ids=row["obligation_ids"],
        ))

    if not snapshot["claims"]:
        items.append(review_item(
            "NO_IDENTIFIED_CLAIMS", True, 6,
            "上游没有声明答案主张，无法计算主张覆盖。",
        ))
    for claim in snapshot["claims"]:
        if claim["mapped"]:
            continue
        if claim["affects_answer"]:
            items.append(review_item(
                "UNMAPPED_CLAIM", True, 60,
                "影响答案的主张没有可追溯检查。" + claim["reason"],
                claim_ids=[claim["claim_id"]], evidence_ids=claim["evidence_ids"],
            ))
        else:
            items.append(review_item(
                "UNMAPPED_CLAIM_NON_IMPACT", False, 90,
                "不影响答案的未映射主张按上游说明保留。" + claim["reason"],
                claim_ids=[claim["claim_id"]], evidence_ids=claim["evidence_ids"],
            ))

    included = [row for row in snapshot["obligations"] if row["applicability"] != "NOT_APPLICABLE"]
    if not included:
        items.append(review_item(
            "NO_RECOGNIZED_CONDITIONS", True, 7,
            "没有进入分母的已识别条件，不能给出已建模范围内充分。",
        ))
    for row in included:
        status = row["status"]
        if row["applicability"] == "UNDETERMINED":
            items.append(review_item(
                "APPLICABILITY_UNDETERMINED", True, 25,
                "条件适用性未定，不能移出分母。" + row["reason"],
                primary_cause(row["reason_codes"]), row["repair_action"],
                obligation_ids=[row["obligation_id"]], evidence_ids=row["evidence_ids"],
            ))
            continue
        if status not in ("UNKNOWN", "CONFLICT"):
            continue
        cause = primary_cause(row["reason_codes"])
        if blocking_flags(row):
            items.append(review_item(
                "CRITICAL_OBLIGATION_UNRESOLVED", True, 20,
                f"关键或必查条件为 {status}。" + row["reason"],
                cause, row["repair_action"],
                obligation_ids=[row["obligation_id"]], evidence_ids=row["evidence_ids"],
            ))
        elif row["prune"] is not None:
            items.append(review_item(
                "PRUNED_RESIDUAL", False, 100,
                f"非关键残留已由 {row['prune']['source']} 记录为不影响本次结论。" + row["prune"]["reason"],
                cause, row["repair_action"],
                obligation_ids=[row["obligation_id"]], evidence_ids=row["evidence_ids"],
            ))
        else:
            items.append(review_item(
                "UNPRUNED_RESIDUAL", True, 70,
                "非关键缺口没有 Loop 或证据链 B 的不影响说明，评分器不自行认定无关。" + row["reason"],
                cause, row["repair_action"],
                obligation_ids=[row["obligation_id"]], evidence_ids=row["evidence_ids"],
            ))

    for row in snapshot["clauses"]:
        if row["expanded"]:
            continue
        cause = primary_cause(row["reason_codes"])
        if row["critical"]:
            items.append(review_item(
                "CRITICAL_UNEXPANDED", True, 40,
                "关键条款已发现但未展开，不能称为条件已齐。" + row["reason"],
                cause, row["repair_action"],
                clause_ids=[row["clause_id"]], evidence_ids=[row["source_evidence_id"]],
            ))
        elif row["prune"] is not None:
            items.append(review_item(
                "CLAUSE_RESERVED", False, 100,
                f"非关键未展开条款按 {row['prune']['source']} 的记录保留。" + row["prune"]["reason"],
                cause, row["repair_action"],
                clause_ids=[row["clause_id"]], evidence_ids=[row["source_evidence_id"]],
            ))
        else:
            items.append(review_item(
                "UNEXPANDED_UNEXPLAINED", True, 72,
                "未展开条款没有不影响说明，不能记为已完成。" + row["reason"],
                cause, row["repair_action"],
                clause_ids=[row["clause_id"]], evidence_ids=[row["source_evidence_id"]],
            ))

    for row in snapshot["relations"]:
        if row["review_status"] not in OPEN_REVIEW:
            continue
        if row["critical"] and row["review_status"] == "unresolved":
            code, priority = "CRITICAL_RELATION_UNRESOLVED", 30
        elif row["critical"]:
            code, priority = "CRITICAL_RELATION_UNREVIEWED", 31
        elif row["prune"] is not None:
            code, priority = "RELATION_RESERVED", 100
        else:
            code, priority = "RELATION_UNEXPLAINED", 71
        blocking = code not in ("RELATION_RESERVED",)
        if code == "RELATION_RESERVED":
            reason = f"非关键关系按 {row['prune']['source']} 的记录保留。" + row["prune"]["reason"]
        elif row["review_status"] == "proposed":
            reason = "关键或未说明的候选关系尚未审核，不能当成已接纳。" + row["reason"]
        else:
            reason = "语义关系未决，不能用其他已通过节点抵消。" + row["reason"]
        items.append(review_item(
            code, blocking, priority, reason, None, row["repair_action"],
            relation_ids=[row["relation_id"]],
        ))

    scope = snapshot["scope_declaration"]
    if scope["status"] == "unclear" and scope["affects_answer"]:
        items.append(review_item(
            "SCOPE_UNCLEAR", True, 50,
            f"影响答案的范围不明（{scope['scope_id']}）。" + scope["reason"],
        ))
    elif scope["status"] == "unclear":
        items.append(review_item(
            "SCOPE_UNCLEAR_NON_IMPACT", False, 95,
            f"范围仍不明（{scope['scope_id']}），但上游说明不影响本次答案。" + scope["reason"],
        ))

    open_obligations = {
        row["obligation_id"]: row for row in snapshot["obligations"]
        if row["status"] in ("UNKNOWN", "CONFLICT")
    }
    open_clauses = {row["clause_id"]: row for row in snapshot["clauses"] if not row["expanded"]}
    for change in snapshot["changes"]:
        target = open_obligations.get(change["object_id"]) or open_clauses.get(change["object_id"])
        if target is None:
            continue
        if "obligation_id" in target:
            blocking = blocking_flags(target) or target["prune"] is None
            cause = primary_cause(target["reason_codes"])
            ref = {"obligation_ids": [target["obligation_id"]]}
        else:
            blocking = target["critical"] or target["prune"] is None
            cause = primary_cause(target["reason_codes"])
            ref = {"clause_ids": [target["clause_id"]]}
        items.append(review_item(
            "STRUCTURE_EXPANSION_OPEN", blocking, 15,
            "结构增量仍指向未关闭对象。" + change["explanation"],
            cause, None, change_ids=[change["change_id"]], **ref,
        ))
    return items


def finalize_review(items):
    ordered = sorted(items, key=lambda item: (item["priority"], item["code"], _ref_sort(item)))
    finalized = []
    for index, item in enumerate(ordered, start=1):
        finalized.append({**item, "order": index, "refs": dict(item["refs"])})
    return finalized


def _ref_sort(item):
    return tuple(tuple(item["refs"][key]) for key in REF_KEYS)


def dimensions(snapshot):
    required = [row for row in snapshot["baseline_checks"] if row["required"]]
    baseline_num = sum(row["status"] in ("COMPLETE", "NOT_APPLICABLE") for row in required)
    mapped = sum(claim["mapped"] for claim in snapshot["claims"])
    included = [row for row in snapshot["obligations"] if row["applicability"] != "NOT_APPLICABLE"]
    resolved = sum(row["status"] in ("SUPPORT", "REFUTE") for row in included)
    expanded = sum(clause["expanded"] for clause in snapshot["clauses"])
    critical_relations = [row for row in snapshot["relations"] if row["critical"]]
    resolved_relations = sum(row["review_status"] in ("accepted", "rejected") for row in critical_relations)
    unresolved_relations = len(critical_relations) - resolved_relations
    check_rows = {}
    passed_total = 0
    for name in CHECK_NAMES:
        passed = sum(row["checks"][name] is True for row in included)
        check_rows[name] = {"passed": passed, "denominator": len(included)}
        passed_total += passed
    return {
        "baseline_coverage": ratio("基础必查覆盖", baseline_num, len(required)),
        "claim_coverage": ratio("答案主张覆盖", mapped, len(snapshot["claims"])),
        "recognized_conditions": ratio("已识别条件证据完成", resolved, len(included)),
        "expansion_and_semantics": ratio(
            "材料展开与语义审核",
            expanded + resolved_relations,
            len(snapshot["clauses"]) + len(critical_relations),
            unexpanded_count=len(snapshot["clauses"]) - expanded,
            critical_unresolved_count=unresolved_relations,
        ),
        "source_and_query": ratio(
            "来源适用与查询完整", passed_total, len(CHECK_NAMES) * len(included), checks=check_rows,
        ),
    }


def design_score(dims):
    numerator = sum(dim["numerator"] for dim in dims.values() if dim["denominator"])
    denominator = sum(dim["denominator"] for dim in dims.values() if dim["denominator"])
    if denominator == 0:
        return None
    return round(100 * numerator / denominator, 2)


def advice_notes(snapshot):
    obligations = {row["obligation_id"]: row for row in snapshot["obligations"]}
    clauses = {row["clause_id"]: row for row in snapshot["clauses"]}
    notes = []
    for change in snapshot["changes"]:
        parts = [
            f"结构变化 {change['change_id']}：{KIND_ZH[change['kind']]}{TYPE_ZH[change['object_type']]} {change['object_id']}。",
            change["statement"],
            change["explanation"],
        ]
        if change["from_recommendation"] or change["to_recommendation"]:
            left = change["from_recommendation"] or "未记录"
            right = change["to_recommendation"] or "未记录"
            parts.append(f"上游记录的建议变化：{left} → {right}。")
        obligation = obligations.get(change["object_id"]) if change["object_type"] == "obligation" else None
        if obligation and obligation["status"] in ("UNKNOWN", "CONFLICT"):
            parts.append(f"当前证据链 B 将该条件记为 {obligation['status']}，取得并校验前不能给出确定建议。")
        elif obligation and obligation["status"] in ("SUPPORT", "REFUTE"):
            parts.append(
                f"当前证据链 B 将该条件记为 {obligation['status']}。新条件如何改变建议以上游记录的建议变化为准。"
            )
        clause = clauses.get(change["object_id"]) if change["object_type"] == "clause" else None
        if clause is not None and not clause["expanded"]:
            parts.append("该条款仍未展开，不能记为条件已齐。")
        notes.append("".join(parts))
    return notes


def repair_actions(snapshot):
    found = []
    sources = (
        ("baseline", snapshot["baseline_checks"], "check_id"),
        ("obligation", snapshot["obligations"], "obligation_id"),
        ("clause", snapshot["clauses"], "clause_id"),
        ("relation", snapshot["relations"], "relation_id"),
    )
    for origin, rows, key in sources:
        for row in rows:
            if row["repair_action"] is None:
                continue
            found.append({**row["repair_action"], "origin_code": origin, "origin_id": row[key]})
    return sorted(found, key=lambda row: (row["origin_code"], row["origin_id"], row["action_id"]))


def condition_refs(snapshot):
    rows = []
    for row in snapshot["obligations"]:
        prune = row["prune"]
        included = row["applicability"] != "NOT_APPLICABLE"
        rows.append({
            "obligation_id": row["obligation_id"], "statement": row["statement"], "status": row["status"],
            "applicability": row["applicability"], "criticality": row["criticality"],
            "required_for_decision": row["required_for_decision"], "must_verify": row["must_verify"],
            "included_in_denominator": included,
            "resolved": included and row["status"] in ("SUPPORT", "REFUTE"),
            "checks": dict(row["checks"]), "evidence_ids": list(row["evidence_ids"]),
            "reason_codes": list(row["reason_codes"]), "reason": row["reason"],
            "applicability_reason": row["applicability_reason"],
            "prune_record_id": None if prune is None else prune["record_id"],
            "prune_source": None if prune is None else prune["source"],
            "prune_reason": None if prune is None else prune["reason"],
        })
    return rows


def residual_gaps(snapshot):
    gaps = []
    for row in snapshot["obligations"]:
        if row["status"] not in ("UNKNOWN", "CONFLICT"):
            continue
        prune = row["prune"]
        gaps.append({
            "obligation_id": row["obligation_id"], "status": row["status"], "criticality": row["criticality"],
            "reason_codes": list(row["reason_codes"]), "reason": row["reason"],
            "cause": primary_cause(row["reason_codes"]), "pruned": prune is not None,
            "prune_source": None if prune is None else prune["source"],
            "prune_reason": None if prune is None else prune["reason"],
            "evidence_ids": list(row["evidence_ids"]),
        })
    return gaps


def as_risk(item, code=None):
    return {
        "code": item["code"] if code is None else code, "blocking": item["blocking"],
        "refs": dict(item["refs"]), "reason": item["reason"], "cause": item["cause"],
    }


def graph_risks(items):
    risks = [as_risk(item) for item in items if item["code"] in BUILD_RISKS]
    for item in items:
        if item["cause"] in CAUSES and item["code"] not in BUILD_RISKS:
            risks.append(as_risk(item, "TOOL_LIMIT"))
    return risks


def copy_change(change):
    return {
        "change_id": change["change_id"], "kind": change["kind"], "object_type": change["object_type"],
        "object_id": change["object_id"], "statement": change["statement"],
        "trigger_evidence_ids": list(change["trigger_evidence_ids"]),
        "from_graph_version": change["from_graph_version"], "to_graph_version": change["to_graph_version"],
        "affected_claim_ids": list(change["affected_claim_ids"]),
        "from_recommendation": change["from_recommendation"], "to_recommendation": change["to_recommendation"],
        "explanation": change["explanation"],
    }


def copy_scope(scope):
    return {**scope, "covers": list(scope["covers"]), "known_limits": list(scope["known_limits"])}


def score_snapshot_v02(snapshot, policy=None):
    validate_snapshot_v02(snapshot)
    policy = DEFAULT_POLICY_V02 if policy is None else policy
    validate(policy, POLICY_V02_SCHEMA, "policy")
    items = finalize_review(collect_reviews(snapshot))
    blockers = [item for item in items if item["blocking"]]
    reservations = [item for item in items if not item["blocking"]]
    dims = dimensions(snapshot)
    raw = design_score(dims)
    suppressed = bool(blockers) and policy["suppress_display_score_on_hard_gate"]
    if blockers:
        level, level_code = LEVELS[0], LEVEL_CODES[0]
        reasons = [f"{item['code']}: {item['reason']}" for item in blockers]
    elif reservations:
        level, level_code = LEVELS[1], LEVEL_CODES[1]
        reasons = [f"{item['code']}: {item['reason']}" for item in reservations]
    else:
        level, level_code = LEVELS[2], LEVEL_CODES[2]
        reasons = ["已声明范围内的硬门槛已通过。等级只描述该范围内的证据与过程质量。"]
    definite = snapshot["recommendation"] in ("eligible", "ineligible")
    may_present = (not blockers) and snapshot["workflow_status"] == "completed" and definite
    if not blockers and snapshot["recommendation"] == "undetermined":
        reasons.append("上游业务结果仍是 undetermined，因此不展示确定建议。")
    notes = [
        SEMANTICS,
        "四态、审核状态、必查覆盖、剪枝理由与结构增量均消费上游声明；评分器不重新判定证据，也不读取评测 gold。",
        "SUPPORT 与 REFUTE 都表示该条件已判定。具备资格的否定证据可以对应已建模范围内证据充分。",
        "硬门槛先于设计分。证据不足时默认不展示总分。",
        "这里的说明是模板，只复述已记录原因。",
    ]
    if blockers:
        notes.append("硬门槛同时阻断无依据的肯定建议和否定建议，不只阻断建议补偿。")
    elif reservations:
        notes.append("保留项来自 Loop 或证据链 B 已记录的说明。评分器不自动升级，也不自行认定无关。")
    card = {
        "schema_version": VERSION_V02,
        "scoring_version": SCORING_VERSION,
        "scoring_policy_version": policy["policy_version"],
        "policy_status": policy["status"],
        "task_id": snapshot["task_id"], "run_id": snapshot["run_id"],
        "graph_version": snapshot["graph_version"], "answer_version": snapshot["answer_version"],
        "rules_version": snapshot["rules_version"], "synthetic_demo": snapshot["synthetic_demo"],
        "version_consistent": True,
        "recommendation": snapshot["recommendation"], "workflow_status": snapshot["workflow_status"],
        "stop_reason": snapshot["stop_reason"],
        "level": level, "level_code": level_code, "level_reasons": reasons,
        "score": None if suppressed else raw, "raw_design_score": raw,
        "display_score_suppressed": suppressed, "score_semantics": SEMANTICS,
        "gate_passed": not blockers, "may_present_definitive_decision": may_present,
        "upstream_recommendation_blocked": bool(blockers) and definite,
        "dimensions": dims,
        "claim_refs": [{
            "claim_id": row["claim_id"], "statement": row["statement"], "mapped": row["mapped"],
            "affects_answer": row["affects_answer"], "obligation_ids": list(row["obligation_ids"]),
            "evidence_ids": list(row["evidence_ids"]), "reason": row["reason"],
        } for row in snapshot["claims"]],
        "condition_refs": condition_refs(snapshot),
        "evidence_refs": [dict(row) for row in snapshot["evidence"]],
        "graph_build_risks": graph_risks(items),
        "residual_gaps": residual_gaps(snapshot),
        "reservations": reservations,
        "repair_actions": repair_actions(snapshot),
        "structure_changes": [copy_change(row) for row in snapshot["changes"]],
        "advice_change_notes": advice_notes(snapshot),
        "human_review_order": items,
        "scope_declaration": copy_scope(snapshot["scope_declaration"]),
        "notes": notes,
    }
    validate(card, SCORECARD_V02_SCHEMA, "scorecard")
    return card


def adapt_v01_to_v02(snapshot):
    """0.1 snapshots stay on their own scorer. Upgrading them would invent coverage."""
    from .contracts import validate_snapshot
    validate_snapshot(snapshot)
    raise ContractError(
        "0.1-draft 快照不能自动升级为 0.2-draft：缺少基础必查清单、主张映射、未展开条款、"
        "关系审核、剪枝记录、结构增量与范围声明。请继续用 schema 0.1-draft 评分，或由证据链 B / Loop "
        "提供这些上游声明。评分器不会把旧快照臆造成已覆盖必查。"
    )
