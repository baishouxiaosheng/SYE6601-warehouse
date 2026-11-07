"""Scoring projection for dynamic graph construction. Schema 0.2-draft.

This module consumes declarations from evidence-chain B and Loop. It does not
recompute four-states, and it does not accept offline gold counts.
"""

from .contracts import (
    BOOL, CHECKS, IDS, RUN_SCHEMA, TEXT, ContractError, arr, check_run_semantics, obj,
    unique_index, validate,
)

VERSION_V02 = "0.2-draft"
SCORING_VERSION = "graph-risk-0.2.0"
LEVELS = ("证据不足", "附保留说明", "已建模范围内证据充分")
LEVEL_CODES = ("INSUFFICIENT_EVIDENCE", "WITH_RESERVATIONS", "SUFFICIENT_WITHIN_SCOPE")
RECOMMENDATIONS = ["eligible", "ineligible", "undetermined"]
WORKFLOWS = ["checking", "needs_clarification", "escalated", "completed"]
OBLIGATION_STATES = ["SUPPORT", "REFUTE", "UNKNOWN", "CONFLICT"]
CAUSES = ["ACCESS_DENIED", "PAGINATION_INCOMPLETE", "BUDGET_STOP"]
CAUSE = {"enum": CAUSES + [None]}
RELATION_TYPES = [
    "depends_on", "supports", "refutes", "applies_to", "exception_of", "overrides", "derived_from",
]
REVIEW_STATUSES = ["proposed", "accepted", "rejected", "unresolved"]
INT = {"type": "integer", "minimum": 0}
UNIT = {"type": ["number", "null"], "minimum": 0, "maximum": 1}
CHECK_NAMES = ("source_allowed", "scope_valid", "version_valid", "time_valid", "query_sufficient")


def ids(minimum=0):
    return {**arr(TEXT, minimum), "uniqueItems": True}


def nullable(schema):
    copied = dict(schema)
    kind = copied.get("type", "object")
    if isinstance(kind, str):
        copied["type"] = [kind, "null"]
    return copied


PRUNE = obj({
    "record_id": TEXT,
    "source": {"enum": ["loop", "checker_b"]},
    "reason": TEXT,
})
REPAIR = obj({"action_id": TEXT, "summary": TEXT, "target_source": TEXT})
REFS = obj({
    "claim_ids": IDS, "obligation_ids": IDS, "evidence_ids": IDS, "relation_ids": IDS,
    "clause_ids": IDS, "baseline_ids": IDS, "change_ids": IDS,
})

OBLIGATION = obj({
    "obligation_id": TEXT, "rule_id": TEXT, "statement": TEXT,
    "applicability": {"enum": ["APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"]},
    "applicability_reason": TEXT,
    "criticality": {"enum": ["critical", "non_critical"]},
    "required_for_decision": BOOL, "must_verify": BOOL,
    "status": {"enum": OBLIGATION_STATES + [None]},
    "checks": CHECKS, "evidence_ids": IDS, "reason_codes": IDS, "reason": TEXT,
    "prune": nullable(PRUNE), "repair_action": nullable(REPAIR),
})
CLAIM = obj({
    "claim_id": TEXT, "statement": TEXT, "mapped": BOOL,
    "obligation_ids": IDS, "evidence_ids": IDS, "affects_answer": BOOL, "reason": TEXT,
})
BASELINE = obj({
    "check_id": TEXT, "statement": TEXT, "required": BOOL, "built": BOOL,
    "status": {"enum": ["COMPLETE", "INCOMPLETE", "UNKNOWN", "NOT_APPLICABLE"]},
    "obligation_ids": IDS, "reason_codes": IDS, "reason": TEXT,
    "repair_action": nullable(REPAIR),
})
CLAUSE = obj({
    "clause_id": TEXT, "statement": TEXT, "source_evidence_id": TEXT,
    "expanded": BOOL, "critical": BOOL, "reason_codes": IDS, "reason": TEXT,
    "prune": nullable(PRUNE), "repair_action": nullable(REPAIR),
})
RELATION = obj({
    "relation_id": TEXT,
    "relation_type": {"enum": RELATION_TYPES},
    "review_status": {"enum": REVIEW_STATUSES},
    "critical": BOOL, "subject_id": TEXT, "object_id": TEXT, "reason": TEXT,
    "prune": nullable(PRUNE), "repair_action": nullable(REPAIR),
})
CHANGE = obj({
    "change_id": TEXT,
    "kind": {"enum": ["added", "revised", "invalidated"]},
    "object_type": {"enum": ["claim", "obligation", "relation", "evidence", "clause"]},
    "object_id": TEXT, "statement": TEXT, "trigger_evidence_ids": IDS,
    "from_graph_version": TEXT, "to_graph_version": TEXT, "affected_claim_ids": IDS,
    "from_recommendation": {"enum": RECOMMENDATIONS + [None]},
    "to_recommendation": {"enum": RECOMMENDATIONS + [None]},
    "explanation": TEXT,
})
SCOPE = obj({
    "scope_id": TEXT, "statement": TEXT, "covers": ids(1), "known_limits": arr(TEXT, 1),
    "affects_answer": BOOL, "status": {"enum": ["declared", "unclear"]}, "reason": TEXT,
})
BINDING = obj({
    "task_id": TEXT, "run_id": TEXT, "graph_version": TEXT, "answer_version": TEXT,
})

SNAPSHOT_V02_SCHEMA = obj({
    "schema_version": {"const": VERSION_V02},
    "task_id": TEXT, "run_id": TEXT, "graph_version": TEXT, "answer_version": TEXT,
    "rules_version": TEXT, "synthetic_demo": BOOL,
    "recommendation": {"enum": RECOMMENDATIONS},
    "workflow_status": {"enum": WORKFLOWS},
    "stop_reason": {"type": ["string", "null"]},
    "answer_binding": BINDING,
    "baseline_checks": arr(BASELINE),
    "claims": arr(CLAIM),
    "obligations": arr(OBLIGATION),
    "clauses": arr(CLAUSE),
    "relations": arr(RELATION),
    "changes": arr(CHANGE),
    "scope_declaration": SCOPE,
    "evidence": arr(obj({"evidence_id": TEXT, "source_type": TEXT, "citation": TEXT})),
})

POLICY_V02_SCHEMA = obj({
    "schema_version": {"const": VERSION_V02},
    "policy_version": TEXT,
    "status": {"enum": ["PROVISIONAL", "TEAM_CONFIRMED"]},
    "suppress_display_score_on_hard_gate": BOOL,
    "description": TEXT,
})

GRAPH_QUALITY = obj({
    "critical_conditions_recognized": INT,
    "critical_conditions_annotated": INT,
    "accepted_relations": INT,
    "accepted_wrong_relations": INT,
    "critical_gaps_present": INT,
    "critical_gaps_reported": INT,
    "structure_stages_expected": INT,
    "structure_stages_succeeded": INT,
    "path_applicable": BOOL,
    "answer_version": TEXT,
    "scorecard_answer_version": TEXT,
    "graph_version": TEXT,
    "scorecard_graph_version": TEXT,
})
_RUN_V02_PROPS = dict(RUN_SCHEMA["properties"])
_RUN_V02_PROPS["graph_quality"] = GRAPH_QUALITY
RUN_V02_SCHEMA = obj(_RUN_V02_PROPS)
RUNS_V02_SCHEMA = obj({"schema_version": {"const": VERSION_V02}, "records": arr(RUN_V02_SCHEMA)})

PLAIN_DIM = obj({"label": TEXT, "numerator": INT, "denominator": INT, "value": UNIT})
EXP_DIM = obj({**PLAIN_DIM["properties"], "unexpanded_count": INT, "critical_unresolved_count": INT})
SOURCE_DIM = obj({
    **PLAIN_DIM["properties"],
    "checks": obj({name: obj({"passed": INT, "denominator": INT}) for name in CHECK_NAMES}),
})
REVIEW_ITEM = obj({
    "order": {"type": "integer", "minimum": 1}, "priority": INT, "code": TEXT, "blocking": BOOL,
    "refs": REFS, "reason": TEXT, "cause": CAUSE, "repair_action": nullable(REPAIR),
})
RISK = obj({"code": TEXT, "blocking": BOOL, "refs": REFS, "reason": TEXT, "cause": CAUSE})
GAP = obj({
    "obligation_id": TEXT, "status": {"enum": ["UNKNOWN", "CONFLICT"]},
    "criticality": {"enum": ["critical", "non_critical"]},
    "reason_codes": IDS, "reason": TEXT, "cause": CAUSE, "pruned": BOOL,
    "prune_source": {"type": ["string", "null"]}, "prune_reason": {"type": ["string", "null"]},
    "evidence_ids": IDS,
})
REPAIR_OUT = obj({
    "action_id": TEXT, "summary": TEXT, "target_source": TEXT, "origin_code": TEXT, "origin_id": TEXT,
})

SCORECARD_V02_SCHEMA = obj({
    "schema_version": {"const": VERSION_V02},
    "scoring_version": {"const": SCORING_VERSION},
    "scoring_policy_version": TEXT,
    "policy_status": {"enum": ["PROVISIONAL", "TEAM_CONFIRMED"]},
    "task_id": TEXT, "run_id": TEXT, "graph_version": TEXT, "answer_version": TEXT,
    "rules_version": TEXT, "synthetic_demo": BOOL, "version_consistent": {"const": True},
    "recommendation": {"enum": RECOMMENDATIONS},
    "workflow_status": {"enum": WORKFLOWS},
    "stop_reason": {"type": ["string", "null"]},
    "level": {"enum": list(LEVELS)},
    "level_code": {"enum": list(LEVEL_CODES)},
    "level_reasons": arr(TEXT),
    "score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
    "raw_design_score": {"type": ["number", "null"], "minimum": 0, "maximum": 100},
    "display_score_suppressed": BOOL,
    "score_semantics": TEXT,
    "gate_passed": BOOL,
    "may_present_definitive_decision": BOOL,
    "upstream_recommendation_blocked": BOOL,
    "dimensions": obj({
        "baseline_coverage": PLAIN_DIM,
        "claim_coverage": PLAIN_DIM,
        "recognized_conditions": PLAIN_DIM,
        "expansion_and_semantics": EXP_DIM,
        "source_and_query": SOURCE_DIM,
    }),
    "claim_refs": arr(obj({
        "claim_id": TEXT, "statement": TEXT, "mapped": BOOL, "affects_answer": BOOL,
        "obligation_ids": IDS, "evidence_ids": IDS, "reason": TEXT,
    })),
    "condition_refs": arr(obj({
        "obligation_id": TEXT, "statement": TEXT,
        "status": {"enum": OBLIGATION_STATES + [None]},
        "applicability": {"enum": ["APPLICABLE", "NOT_APPLICABLE", "UNDETERMINED"]},
        "criticality": {"enum": ["critical", "non_critical"]},
        "required_for_decision": BOOL, "must_verify": BOOL,
        "included_in_denominator": BOOL, "resolved": BOOL, "checks": CHECKS,
        "evidence_ids": IDS, "reason_codes": IDS, "reason": TEXT, "applicability_reason": TEXT,
        "prune_record_id": {"type": ["string", "null"]},
        "prune_source": {"type": ["string", "null"]},
        "prune_reason": {"type": ["string", "null"]},
    })),
    "evidence_refs": SNAPSHOT_V02_SCHEMA["properties"]["evidence"],
    "graph_build_risks": arr(RISK),
    "residual_gaps": arr(GAP),
    "reservations": arr(REVIEW_ITEM),
    "repair_actions": arr(REPAIR_OUT),
    "structure_changes": arr(CHANGE),
    "advice_change_notes": arr(TEXT),
    "human_review_order": arr(REVIEW_ITEM),
    "scope_declaration": SCOPE,
    "notes": arr(TEXT),
})

V02_SCHEMAS = {
    "snapshot_v02": SNAPSHOT_V02_SCHEMA,
    "policy_v02": POLICY_V02_SCHEMA,
    "runs_v02": RUNS_V02_SCHEMA,
    "scorecard_v02": SCORECARD_V02_SCHEMA,
}


def _index(rows, key):
    return unique_index(rows, key, key)


def _must_resolve(id_list, universe, path):
    missing = [item for item in id_list if item not in universe]
    if missing:
        raise ContractError(f"{path}: unknown reference {missing[0]}")


def _reject_prune(record, path):
    if record["prune"] is not None:
        raise ContractError(f"{path}: resolved or blocking item cannot carry a prune record")


def validate_snapshot_v02(snapshot):
    validate(snapshot, SNAPSHOT_V02_SCHEMA, "snapshot")
    binding = snapshot["answer_binding"]
    for key in ("task_id", "run_id", "graph_version", "answer_version"):
        if binding[key] != snapshot[key]:
            raise ContractError(
                f"answer_binding.{key} does not match snapshot.{key}; "
                "refuse to score across inconsistent task/run/graph/answer versions"
            )
    if snapshot["workflow_status"] != "checking" and not snapshot["stop_reason"]:
        raise ContractError("terminal workflow_status requires stop_reason")

    baselines = _index(snapshot["baseline_checks"], "check_id")
    claims = _index(snapshot["claims"], "claim_id")
    obligations = _index(snapshot["obligations"], "obligation_id")
    evidence = _index(snapshot["evidence"], "evidence_id")
    clauses = _index(snapshot["clauses"], "clause_id")
    relations = _index(snapshot["relations"], "relation_id")
    changes = _index(snapshot["changes"], "change_id")
    groups = [baselines, claims, obligations, evidence, clauses, relations, changes]
    seen = {}
    for group in groups:
        overlap = set(seen).intersection(group)
        if overlap:
            raise ContractError(f"duplicate id across collections: {sorted(overlap)[0]}")
        seen.update(group)
    node_ids = set(claims) | set(obligations) | set(evidence) | set(clauses)

    for oid, ob in obligations.items():
        _must_resolve(ob["evidence_ids"], evidence, oid)
        applicability, status = ob["applicability"], ob["status"]
        if applicability == "NOT_APPLICABLE":
            if status is not None:
                raise ContractError(f"{oid}: not-applicable obligation must have null status")
            _reject_prune(ob, oid)
        elif applicability == "UNDETERMINED":
            if status != "UNKNOWN":
                raise ContractError(f"{oid}: undetermined applicability requires UNKNOWN")
            _reject_prune(ob, oid)
        elif status is None:
            raise ContractError(f"{oid}: applicable obligation requires four-state status")
        if status in ("SUPPORT", "REFUTE"):
            if not ob["evidence_ids"] or not all(value is True for value in ob["checks"].values()):
                raise ContractError(f"{oid}: resolved status requires references and validated checks")
            _reject_prune(ob, oid)
        if status in ("UNKNOWN", "CONFLICT") and not ob["reason_codes"]:
            raise ContractError(f"{oid}: unresolved status requires a reason code")
        if status == "CONFLICT" and not ob["evidence_ids"]:
            raise ContractError(f"{oid}: conflict requires evidence references")
        blocking = (
            ob["criticality"] == "critical" or ob["required_for_decision"] or ob["must_verify"]
            or applicability == "UNDETERMINED"
        )
        if status in ("UNKNOWN", "CONFLICT") and blocking and ob["prune"] is not None:
            raise ContractError(f"{oid}: critical, required, or must-verify gap cannot be pruned")

    for bid, row in baselines.items():
        if row["built"] and row["status"] == "COMPLETE" and not row["obligation_ids"]:
            raise ContractError(f"{bid}: complete baseline check must cite the built obligation")
        if row["built"] and not row["obligation_ids"]:
            raise ContractError(f"{bid}: built baseline check requires obligation ids")
        if not row["built"] and row["obligation_ids"]:
            raise ContractError(f"{bid}: missing-from-graph baseline cannot cite obligations")
        if row["status"] == "COMPLETE" and not row["built"]:
            raise ContractError(f"{bid}: missing-from-graph baseline cannot be COMPLETE")
        if row["status"] not in ("COMPLETE", "NOT_APPLICABLE") and not row["reason_codes"]:
            raise ContractError(f"{bid}: incomplete baseline check requires a reason code")
        _must_resolve(row["obligation_ids"], obligations, bid)

    for cid, claim in claims.items():
        _must_resolve(claim["obligation_ids"], obligations, cid)
        _must_resolve(claim["evidence_ids"], evidence, cid)
        if claim["mapped"] and not claim["obligation_ids"]:
            raise ContractError(f"{cid}: mapped claim requires obligation ids")
        if not claim["mapped"] and claim["obligation_ids"]:
            raise ContractError(f"{cid}: unmapped claim cannot cite obligations")

    for cid, clause in clauses.items():
        if clause["source_evidence_id"] not in evidence:
            raise ContractError(f"{cid}: source evidence not found")
        if clause["expanded"]:
            _reject_prune(clause, cid)
        elif not clause["reason_codes"]:
            raise ContractError(f"{cid}: unexpanded clause requires a reason code")
        elif clause["critical"] and clause["prune"] is not None:
            raise ContractError(f"{cid}: critical unexpanded clause cannot be pruned")

    for rid, rel in relations.items():
        for endpoint in (rel["subject_id"], rel["object_id"]):
            if endpoint not in node_ids:
                raise ContractError(f"{rid}: endpoint {endpoint} not in the snapshot")
        open_review = rel["review_status"] in ("proposed", "unresolved")
        if not open_review:
            _reject_prune(rel, rid)
        elif rel["critical"] and rel["prune"] is not None:
            raise ContractError(f"{rid}: critical unresolved relation cannot be pruned")

    collections = {
        "claim": claims, "obligation": obligations, "relation": relations,
        "evidence": evidence, "clause": clauses,
    }
    for cid, change in changes.items():
        _must_resolve(change["trigger_evidence_ids"], evidence, cid)
        _must_resolve(change["affected_claim_ids"], claims, cid)
        if change["kind"] != "invalidated" and change["object_id"] not in collections[change["object_type"]]:
            raise ContractError(f"{cid}: {change['kind']} object is not in the current snapshot")
    return snapshot


def validate_runs_v02(payload):
    validate(payload, RUNS_V02_SCHEMA, "runs")
    unique_index(payload["records"], "run_id", "records")
    for row in payload["records"]:
        check_run_semantics(row)
        quality = row["graph_quality"]
        pairs = (
            ("critical_conditions_recognized", "critical_conditions_annotated", "recognized conditions exceed annotated gold"),
            ("accepted_wrong_relations", "accepted_relations", "wrong relations exceed accepted relations"),
            ("critical_gaps_reported", "critical_gaps_present", "reported critical gaps exceed gold gaps"),
            ("structure_stages_succeeded", "structure_stages_expected", "succeeded stages exceed expected stages"),
        )
        for left, right, message in pairs:
            if quality[left] > quality[right]:
                raise ContractError(f"{row['run_id']}: {message}")
        if quality["path_applicable"]:
            if quality["structure_stages_expected"] < 1:
                raise ContractError(f"{row['run_id']}: applicable structure path needs a positive stage denominator")
        elif quality["structure_stages_expected"] or quality["structure_stages_succeeded"]:
            raise ContractError(f"{row['run_id']}: non-applicable path must have zero stages")
    return payload
