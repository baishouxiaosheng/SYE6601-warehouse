"""Synthetic 0.2 scoring inputs. They exercise the contract; they are not a gold set."""

from copy import deepcopy

CHECKS_OK = {name: True for name in (
    "source_allowed", "scope_valid", "version_valid", "time_valid", "query_sufficient")}
CHECKS_NONE = {name: None for name in CHECKS_OK}


def evidence(evidence_id, source_type):
    return {
        "evidence_id": evidence_id, "source_type": source_type,
        "citation": f"demo://v2/{evidence_id}（合成引用，无真实业务凭证）",
    }


def obligation(obligation_id, statement, evidence_id, status="SUPPORT", criticality="critical",
               required=True, must_verify=False, reason_codes=None, reason=None, checks=None,
               evidence_ids=None, prune=None, repair_action=None):
    if status in ("SUPPORT", "REFUTE"):
        reason_codes = [] if reason_codes is None else reason_codes
        checks = CHECKS_OK if checks is None else checks
        evidence_ids = [evidence_id] if evidence_ids is None else evidence_ids
        if reason is None:
            reason = "证据链 B 声明该条件已判定。" if status == "SUPPORT" else "证据链 B 声明该命题被有效证据反驳。"
    else:
        reason_codes = ["NOT_QUERIED"] if reason_codes is None else reason_codes
        checks = CHECKS_NONE if checks is None else checks
        evidence_ids = [] if evidence_ids is None else evidence_ids
        reason = reason or "证据链 B 声明该条件尚未判定。"
    return {
        "obligation_id": obligation_id, "rule_id": "DEMO-RULE-V2", "statement": statement,
        "applicability": "APPLICABLE",
        "applicability_reason": "演示用上游适用性说明，不是正式业务规则。",
        "criticality": criticality, "required_for_decision": required, "must_verify": must_verify,
        "status": status, "checks": dict(checks), "evidence_ids": list(evidence_ids),
        "reason_codes": list(reason_codes), "reason": reason, "prune": prune, "repair_action": repair_action,
    }


def claim(claim_id, statement, obligation_ids, evidence_ids, mapped=True, affects_answer=True, reason=None):
    return {
        "claim_id": claim_id, "statement": statement, "mapped": mapped,
        "obligation_ids": list(obligation_ids), "evidence_ids": list(evidence_ids),
        "affects_answer": affects_answer,
        "reason": reason or "主张已映射到上游给出的条件检查。",
    }


def baseline(check_id, statement, obligation_ids, built=True, status="COMPLETE", required=True,
             reason_codes=None, reason=None, repair_action=None):
    return {
        "check_id": check_id, "statement": statement, "required": required, "built": built,
        "status": status, "obligation_ids": list(obligation_ids),
        "reason_codes": list(reason_codes or []),
        "reason": reason or "独立必查确认该项已建入并完成。",
        "repair_action": repair_action,
    }


def relation(relation_id, subject_id, object_id, review_status="accepted", critical=True,
             relation_type="supports", reason=None, prune=None):
    return {
        "relation_id": relation_id, "relation_type": relation_type, "review_status": review_status,
        "critical": critical, "subject_id": subject_id, "object_id": object_id,
        "reason": reason or "证据链 B 已给出该关系的审核状态。",
        "prune": prune, "repair_action": None,
    }


def scope(status="declared", affects_answer=False, reason=None):
    return {
        "scope_id": "V2-SCOPE",
        "statement": "演示范围只覆盖已声明的客户故障补偿资格，不是全量政策发现。",
        "covers": ["stated-compensation-eligibility"],
        "known_limits": ["未在已见材料中出现的隐含政策不在本图范围内。"],
        "affects_answer": affects_answer, "status": status,
        "reason": reason or "上游声明本范围已经明确，没有影响本次答案的范围不明。",
    }


def envelope(task_id, run_id, graph_version, answer_version, recommendation, workflow_status,
             stop_reason, obligations, evidence_rows, claims, baselines, relations=None,
             clauses=None, changes=None, scope_declaration=None):
    return {
        "schema_version": "0.2-draft",
        "task_id": task_id, "run_id": run_id, "graph_version": graph_version,
        "answer_version": answer_version, "rules_version": "demo-only-not-01a",
        "synthetic_demo": True, "recommendation": recommendation, "workflow_status": workflow_status,
        "stop_reason": stop_reason,
        "answer_binding": {
            "task_id": task_id, "run_id": run_id, "graph_version": graph_version,
            "answer_version": answer_version,
        },
        "baseline_checks": baselines, "claims": claims, "obligations": obligations,
        "clauses": clauses or [], "relations": relations or [], "changes": changes or [],
        "scope_declaration": scope_declaration or scope(), "evidence": evidence_rows,
    }


def sufficient_graph(task_id, contract_status="SUPPORT", contract_reason=None):
    rows = [
        ("CONTRACT", "CRM_CONTRACT_DB", "适用的客户专属合同允许本次事故补偿"),
        ("DURATION", "MONITORING_SYSTEM", "本次事故的有效时长达到适用阈值"),
    ]
    evidence_rows, obligations = [], []
    for key, source, statement in rows:
        evidence_rows.append(evidence(f"{task_id}-E-{key}", source))
        status = contract_status if key == "CONTRACT" else "SUPPORT"
        obligations.append(obligation(
            f"{task_id}-O-{key}", statement, f"{task_id}-E-{key}", status=status,
            reason=contract_reason if key == "CONTRACT" else None,
        ))
    claim_row = claim(
        f"{task_id}-C-ELIGIBLE", "本次故障满足已建模补偿条件",
        [row["obligation_id"] for row in obligations],
        [row["evidence_id"] for row in evidence_rows],
    )
    baseline_row = baseline(
        f"{task_id}-B-CONTRACT", "核对适用的客户专属合同", [f"{task_id}-O-CONTRACT"],
    )
    relation_row = relation(
        f"{task_id}-R-CONTRACT", f"{task_id}-E-CONTRACT", f"{task_id}-O-CONTRACT",
    )
    return evidence_rows, obligations, [claim_row], [baseline_row], [relation_row]


def sufficient_eligible():
    task = "V2-ELIGIBLE"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "DECLARED_CHECKS_CLOSED", obligations, evidence_rows, claims, baselines, relations,
    )


def sufficient_ineligible():
    task = "V2-INELIGIBLE"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(
        task, "REFUTE", "合同条款表明本次不具备补偿资格。",
    )
    claims[0]["statement"] = "本次故障不具备已建模补偿资格"
    claims[0]["reason"] = "否定建议已映射到被反驳的合同条件，以及其他已判定条件。"
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "ineligible", "completed",
        "DECLARED_CHECKS_CLOSED", obligations, evidence_rows, claims, baselines, relations,
    )


def missing_baseline():
    task = "V2-MISSING-BASELINE"
    evidence_rows = [
        evidence(f"{task}-E-DURATION", "MONITORING_SYSTEM"),
        evidence(f"{task}-E-PLAN", "PLAN_DB"),
    ]
    obligations = [
        obligation(f"{task}-O-DURATION", "本次事故的有效时长达到适用阈值", f"{task}-E-DURATION"),
        obligation(f"{task}-O-PLAN", "本次事故对应套餐在适用范围内", f"{task}-E-PLAN"),
    ]
    claims = [claim(
        f"{task}-C-ELIGIBLE", "除合同以外的已建条件均已通过",
        [row["obligation_id"] for row in obligations],
        [row["evidence_id"] for row in evidence_rows],
        reason="模型只映射了自己建出的节点。",
    )]
    baselines = [baseline(
        f"{task}-B-CONTRACT", "核对适用的客户专属合同", [], built=False, status="INCOMPLETE",
        reason_codes=["MISSING_FROM_GRAPH"],
        reason="独立必查指出应建客户专属合同义务，但图中没有该节点。其余已通过节点不能填补。",
    )]
    relations = [relation(f"{task}-R-DURATION", f"{task}-E-DURATION", f"{task}-O-DURATION")]
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "UPSTREAM_DECLARED_COMPLETE", obligations, evidence_rows, claims, baselines, relations,
    )


def unexpanded_clause():
    task = "V2-UNEXPANDED"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    clauses = [{
        "clause_id": f"{task}-L-TICKET",
        "statement": "已发现工单时限条款，但当前规则表达解释不了它。",
        "source_evidence_id": f"{task}-E-CONTRACT", "expanded": False, "critical": True,
        "reason_codes": ["UNEXPANDED"],
        "reason": "条款已经定位，语义尚未展开，不能称为条件已齐。",
        "prune": None,
        "repair_action": {
            "action_id": f"{task}-REPAIR-CLAUSE",
            "summary": "把该条款交给建链适配，展开为可校验条件或标成无法表达。",
            "target_source": "CONTRACT_TEXT",
        },
    }]
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "CLAUSE_FOUND_BUT_UNEXPANDED", obligations, evidence_rows, claims, baselines, relations,
        clauses=clauses,
    )


def _tool_blocked(task, reason_code, reason, recommendation):
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    obligations[0].update(
        status="UNKNOWN", checks=dict(CHECKS_NONE), evidence_ids=[], reason_codes=[reason_code], reason=reason,
    )
    baselines[0].update(status="INCOMPLETE", reason_codes=[reason_code], reason=reason)
    for index in range(1, 5):
        evidence_rows.append(evidence(f"{task}-E-AUX-{index}", "AUXILIARY_NOTE"))
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", recommendation, "escalated",
        reason_code, obligations, evidence_rows, claims, baselines, relations,
    )


def critical_access_denied():
    return _tool_blocked(
        "V2-ACCESS-DENIED", "ACCESS_DENIED",
        "客户合同来源返回 403。辅助材料再多也不能代替这份关键来源。", "eligible",
    )


def critical_pagination():
    return _tool_blocked(
        "V2-PAGINATION", "PAGINATION_INCOMPLETE",
        "维护记录只返回了第一页。辅助证据不能把未完成分页当成查询充分。", "ineligible",
    )


def pruned_reservation():
    task = "V2-PRUNED"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    obligations.append(obligation(
        f"{task}-O-NOTE", "备注字段是否填写", f"{task}-E-NOTE", status="UNKNOWN",
        criticality="non_critical", required=False, reason_codes=["NOT_QUERIED"],
        reason="备注字段没有取值。",
        prune={
            "record_id": f"{task}-PRUNE-1", "source": "loop",
            "reason": "Loop 依赖分析记录该备注不影响本次补偿结论，且不是程序必查。",
        },
    ))
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "NONCRITICAL_PRUNED", obligations, evidence_rows, claims, baselines, relations,
    )


def _dyn_change(change_id, kind, graph_from, graph_to, recommendation_from, recommendation_to,
                statement, explanation, evidence_ids):
    return {
        "change_id": change_id, "kind": kind, "object_type": "obligation",
        "object_id": "DYN-O-TICKET-24H", "statement": statement,
        "trigger_evidence_ids": evidence_ids, "from_graph_version": graph_from,
        "to_graph_version": graph_to, "affected_claim_ids": ["DYN-C-ELIGIBLE"],
        "from_recommendation": recommendation_from, "to_recommendation": recommendation_to,
        "explanation": explanation,
    }


def dyn01_before_ticket():
    evidence_rows = [
        evidence("DYN-E-CONTRACT", "CRM_CONTRACT_DB"),
        evidence("DYN-E-DURATION", "MONITORING_SYSTEM"),
    ]
    obligations = [
        obligation("DYN-O-CONTRACT", "已核对客户专属合同", "DYN-E-CONTRACT"),
        obligation("DYN-O-DURATION", "本次事故的有效时长达到适用阈值", "DYN-E-DURATION"),
        obligation(
            "DYN-O-TICKET-24H", "故障后 24 小时内提交工单", "DYN-E-TICKET", status="UNKNOWN",
            reason_codes=["NOT_QUERIED"],
            reason="合同返回后才出现该条件。工单尚未取得，不能沿用补合同之前的建议。",
            repair_action={
                "action_id": "DYN-REPAIR-TICKET",
                "summary": "查询该故障后 24 小时内的工单提交记录。",
                "target_source": "TICKET_SYSTEM",
            },
        ),
    ]
    claims = [claim(
        "DYN-C-ELIGIBLE", "补偿主张取决于合同、时长，以及新出现的 24 小时工单条件。",
        [row["obligation_id"] for row in obligations], ["DYN-E-CONTRACT", "DYN-E-DURATION"],
        reason="新条件已经映射到主张，但工单证据还未回来。",
    )]
    baselines = [baseline("DYN-B-CONTRACT", "核对适用的客户专属合同", ["DYN-O-CONTRACT"])]
    relations = [relation("DYN-R-CONTRACT", "DYN-E-CONTRACT", "DYN-O-CONTRACT")]
    changes = [_dyn_change(
        "DYN01-CHG-TICKET-ADDED", "added", "dyn01-graph-0", "dyn01-graph-1", "eligible", "undetermined",
        "合同原文新增条件：故障后 24 小时内提交工单。初始图没有为该案例预写这个节点。",
        "专属合同返回后出现新的 24 小时工单依赖；工单未取得，建议不能维持。",
        ["DYN-E-CONTRACT"],
    )]
    return envelope(
        "DYN-01", "DYN-01-RUN", "dyn01-graph-1", "dyn01-answer-1", "undetermined", "checking",
        "AWAITING_TICKET_EVIDENCE", obligations, evidence_rows, claims, baselines, relations,
        changes=changes,
    )


def dyn01_after_ticket():
    before = dyn01_before_ticket()
    after = deepcopy(before)
    after.update(graph_version="dyn01-graph-2", answer_version="dyn01-answer-2",
                 recommendation="eligible", workflow_status="completed",
                 stop_reason="TICKET_CONDITION_RESOLVED")
    after["answer_binding"].update(graph_version="dyn01-graph-2", answer_version="dyn01-answer-2")
    after["evidence"].append(evidence("DYN-E-TICKET", "TICKET_SYSTEM"))
    ticket = after["obligations"][2]
    ticket.update(status="SUPPORT", checks=dict(CHECKS_OK), evidence_ids=["DYN-E-TICKET"],
                  reason_codes=[], repair_action=None,
                  reason="工单记录显示故障后 24 小时内已提交。该新条件由 UNKNOWN 改为 SUPPORT。")
    after["claims"][0]["evidence_ids"] = ["DYN-E-CONTRACT", "DYN-E-DURATION", "DYN-E-TICKET"]
    after["changes"].append(_dyn_change(
        "DYN01-CHG-TICKET-RESOLVED", "revised", "dyn01-graph-1", "dyn01-graph-2",
        "undetermined", "eligible",
        "工单证据表明故障后 24 小时内已提交工单，该新条件由 UNKNOWN 改为 SUPPORT。",
        "新的 24 小时工单条件已查明并支持资格主张，建议由未确定改为可补偿。",
        ["DYN-E-TICKET"],
    ))
    return after


def scope_unclear():
    task = "V2-SCOPE-UNCLEAR"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "needs_clarification",
        "SCOPE_UNCLEAR", obligations, evidence_rows, claims, baselines, relations,
        scope_declaration=scope(
            "unclear", True, "事件时间不足以判断适用哪一版合同，而且这个不明会影响答案。",
        ),
    )


def unresolved_relation():
    task = "V2-RELATION"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    relations.append(relation(
        f"{task}-R-OPEN", f"{task}-C-ELIGIBLE", f"{task}-O-DURATION",
        review_status="unresolved", relation_type="depends_on",
        reason="时长阈值与补偿主张的依赖仍未审核。字段类型正确也不能当作已接纳。",
    ))
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "RELATION_UNRESOLVED", obligations, evidence_rows, claims, baselines, relations,
    )


def unmapped_claim():
    task = "V2-UNMAPPED"
    evidence_rows, obligations, claims, baselines, relations = sufficient_graph(task)
    claims.append(claim(
        f"{task}-C-AMOUNT", "另外补偿 500 元", [], [], mapped=False, affects_answer=True,
        reason="金额主张没有对应的义务检查。",
    ))
    return envelope(
        task, f"{task}-RUN", f"{task}-GRAPH", f"{task}-ANSWER", "eligible", "completed",
        "UNMAPPED_AMOUNT_CLAIM", obligations, evidence_rows, claims, baselines, relations,
    )


def all_cases():
    return [
        ("01_missing_baseline", missing_baseline()),
        ("02_unexpanded_clause", unexpanded_clause()),
        ("03_critical_access_denied", critical_access_denied()),
        ("04_ineligible_sufficient", sufficient_ineligible()),
        ("05_pruned_reservation", pruned_reservation()),
        ("06_dyn01_before_ticket", dyn01_before_ticket()),
        ("07_dyn01_after_ticket", dyn01_after_ticket()),
        ("08_scope_unclear", scope_unclear()),
        ("09_unresolved_relation", unresolved_relation()),
        ("10_unmapped_claim", unmapped_claim()),
        ("11_critical_pagination", critical_pagination()),
        ("12_sufficient_eligible", sufficient_eligible()),
    ]


def metric_record(run_id, method, fault_origin, supported, calls, quality, reason):
    return {
        "case_id": "DEMO-V2-CASE", "task_id": "DEMO-V2-TASK", "run_id": run_id, "method": method,
        "comparison_group": "demo-v2-identical-environment", "dataset_version": "demo-0.2",
        "rules_version": "demo-only-not-01a", "permissions_id": "demo-permissions",
        "execution_mode": "SIMULATED", "fault_origin": fault_origin, "synthetic_demo": True,
        "run_status": "COMPLETED", "actual_decision": "DO_NOT_RECOMMEND", "actual_escalated": False,
        "tool_calls": calls, "cost_units": float(calls), "latency_ms": None, "cost_unit": "demo_unit",
        "assessment": {
            "assessment_id": f"ASSESS-{run_id}", "assessor": "handwritten-fixture-not-experiment",
            "rubric_version": "demo-rubric-0.2", "evidence_snapshot_id": f"SNAP-{run_id}",
            "reference_decision": "DO_NOT_RECOMMEND", "expected_escalated": False,
            "assertion_supported": supported, "process_compliant": supported, "reason": reason,
        },
        "graph_quality": quality,
    }


def metric_runs():
    natural = metric_record(
        "V2-METRIC-NATURAL", "dynamic", "NATURAL", True, 3,
        {"critical_conditions_recognized": 2, "critical_conditions_annotated": 2,
         "accepted_relations": 3, "accepted_wrong_relations": 0,
         "critical_gaps_present": 1, "critical_gaps_reported": 1,
         "structure_stages_expected": 2, "structure_stages_succeeded": 2, "path_applicable": True,
         "answer_version": "a-natural", "scorecard_answer_version": "a-natural",
         "graph_version": "g-natural", "scorecard_graph_version": "g-natural"},
        "手写演示：自然分层，离线计数完整且版本一致。",
    )
    injected = metric_record(
        "V2-METRIC-INJECTED", "dynamic", "INJECTED", False, 2,
        {"critical_conditions_recognized": 1, "critical_conditions_annotated": 2,
         "accepted_relations": 4, "accepted_wrong_relations": 1,
         "critical_gaps_present": 2, "critical_gaps_reported": 1,
         "structure_stages_expected": 2, "structure_stages_succeeded": 1, "path_applicable": True,
         "answer_version": "a-injected", "scorecard_answer_version": "a-injected",
         "graph_version": "g-injected", "scorecard_graph_version": "g-injected"},
        "手写演示：注入故障。漏建、错误关系和缺口漏报只存在于离线计数。",
    )
    fixed = metric_record(
        "V2-METRIC-FIXED", "fixed_full", "INJECTED", True, 6,
        {"critical_conditions_recognized": 2, "critical_conditions_annotated": 2,
         "accepted_relations": 0, "accepted_wrong_relations": 0,
         "critical_gaps_present": 0, "critical_gaps_reported": 0,
         "structure_stages_expected": 0, "structure_stages_succeeded": 0, "path_applicable": False,
         "answer_version": "a-fixed", "scorecard_answer_version": "a-fixed",
         "graph_version": "g-fixed", "scorecard_graph_version": "g-fixed"},
        "手写演示：固定全查没有结构扩展路径，分母不把 0 阶段算成功。",
    )
    mismatch = metric_record(
        "V2-METRIC-MISMATCH", "prompt_mock", "NATURAL", False, 1,
        {"critical_conditions_recognized": 0, "critical_conditions_annotated": 1,
         "accepted_relations": 1, "accepted_wrong_relations": 1,
         "critical_gaps_present": 1, "critical_gaps_reported": 0,
         "structure_stages_expected": 1, "structure_stages_succeeded": 1, "path_applicable": True,
         "answer_version": "a-answer", "scorecard_answer_version": "a-scorecard",
         "graph_version": "g-answer", "scorecard_graph_version": "g-scorecard"},
        "手写演示：答案版本与成绩单版本不一致。",
    )
    return {"schema_version": "0.2-draft", "records": [natural, injected, fixed, mismatch]}
