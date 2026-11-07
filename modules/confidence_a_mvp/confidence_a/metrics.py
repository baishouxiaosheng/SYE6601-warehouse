"""Small offline evaluator. Assessments must be independent of online scores."""

from collections import defaultdict
from statistics import mean

from .contracts import DEFINITE, VERSION, ContractError, validate_runs


def ratio(numerator, denominator):
    return {"numerator": numerator, "denominator": denominator,
            "value": numerator / denominator if denominator else None}


def summarize(rows):
    n = len(rows)
    asserted = [r for r in rows if r["actual_decision"] in DEFINITE]

    def correct(r):
        a = r["assessment"]
        return (r["run_status"] == "COMPLETED"
                and r["actual_decision"] == a["reference_decision"]
                and r["actual_escalated"] == a["expected_escalated"])

    automatic_success = sum(correct(r) and r["assessment"]["assertion_supported"] is True
                            and r["assessment"]["process_compliant"] for r in asserted)
    costs = {}
    for key in ("tool_calls", "cost_units", "latency_ms"):
        values = [r[key] for r in rows if r[key] is not None]
        costs[key] = {"mean": mean(values) if values else None,
                      "measured_count": len(values), "missing_count": n - len(values)}
    return {
        "n_runs": n, "run_ids": [r["run_id"] for r in rows],
        "terminal_accuracy": ratio(sum(correct(r) for r in rows), n),
        "assertion_accuracy": ratio(sum(correct(r) for r in asserted), len(asserted)),
        "unsupported_answer_rate": ratio(sum(r["assessment"]["assertion_supported"] is False
                                             for r in asserted), len(asserted)),
        "automatic_coverage": ratio(len(asserted), n),
        "automatic_success_rate": ratio(automatic_success, n),
        "escalation_rate": ratio(sum(r["actual_escalated"] for r in rows), n),
        "proper_escalations": sum(correct(r) and r["actual_escalated"]
                                  and r["assessment"]["process_compliant"] for r in rows),
        "failed_runs": sum(r["run_status"] == "FAILED" for r in rows), "costs": costs,
    }


GROUP_FIELDS = ("method", "comparison_group", "dataset_version", "rules_version", "permissions_id",
                 "execution_mode", "fault_origin", "synthetic_demo", "cost_unit", "rubric_version")


def _group(records):
    groups = defaultdict(list)
    for row in records:
        groups[tuple(row["assessment"][k] if k == "rubric_version" else row[k] for k in GROUP_FIELDS)].append(row)
    return groups


def evaluate_runs_v01(payload):
    validate_runs(payload)
    # No mixing demo/real, different tools, rule versions, fault origins or methods.
    return {"schema_version": VERSION, "n_records": len(payload["records"]),
            "groups": [{"scope": dict(zip(GROUP_FIELDS, key)), **summarize(rows)}
                       for key, rows in sorted(_group(payload["records"]).items())],
            "notes": ["支持性标签必须由独立评审基于本次运行证据产生，不能读取评分卡。",
                      "失败运行保留在分母；缺测成本保留 null，均值只基于已测值。",
                      "此版本不自动输出方法间增益；比较前需配对相同案例及实验条件。",
                      "合成样例只验证接口，不是实验成绩。"]}


def graph_metrics(rows):
    quality = [row["graph_quality"] for row in rows]
    applicable = [item for item in quality if item["path_applicable"]]
    consistent = sum(
        item["answer_version"] == item["scorecard_answer_version"]
        and item["graph_version"] == item["scorecard_graph_version"]
        for item in quality
    )
    return {
        "critical_omission_rate": ratio(
            sum(item["critical_conditions_annotated"] - item["critical_conditions_recognized"] for item in quality),
            sum(item["critical_conditions_annotated"] for item in quality)),
        "accepted_wrong_relation_rate": ratio(
            sum(item["accepted_wrong_relations"] for item in quality),
            sum(item["accepted_relations"] for item in quality)),
        "critical_gap_miss_rate": ratio(
            sum(item["critical_gaps_present"] - item["critical_gaps_reported"] for item in quality),
            sum(item["critical_gaps_present"] for item in quality)),
        "structure_expansion_path_success": ratio(
            sum(item["structure_stages_succeeded"] == item["structure_stages_expected"] for item in applicable),
            len(applicable)),
        "structure_expansion_stage_success": ratio(
            sum(item["structure_stages_succeeded"] for item in applicable),
            sum(item["structure_stages_expected"] for item in applicable)),
        "answer_scorecard_version_consistency": ratio(consistent, len(rows)),
    }


def evaluate_runs_v02(payload):
    from .contracts_v02 import VERSION_V02, validate_runs_v02
    validate_runs_v02(payload)
    return {
        "schema_version": VERSION_V02, "n_records": len(payload["records"]),
        "measurement_status": "NOT_A_MEASURED_RESULT",
        "target_status": {
            "status": "PROPOSED_NOT_MEASURED",
            "items": [
                {"name": "relative_improvement", "proposed_target": "+30%", "measured": None},
                {"name": "unsupported_answer_rate", "proposed_target": "<5%", "measured": None},
                {"name": "query_reduction", "proposed_target": "-50%", "measured": None},
            ],
        },
        "groups": [{"scope": dict(zip(GROUP_FIELDS, key)), **summarize(rows), **graph_metrics(rows)}
                   for key, rows in sorted(_group(payload["records"]).items())],
        "notes": [
            "图质量计数只来自离线评测记录，线上单例评分不得读取这些 gold。",
            "自然错误与注入故障按 fault_origin 分开，不合并成一个成绩。",
            "关键条件漏建率、错误接纳关系、关键缺口漏报、结构扩展路径和版本一致性的分母仍待与 06 冻结。",
            "+30%、<5%、-50% 只是拟验证目标，本报告不声称已经测得。",
            "合成样例只验证公式，不是实验成绩。",
        ],
    }


def evaluate_runs(payload):
    from .contracts_v02 import VERSION_V02
    if not isinstance(payload, dict):
        raise ContractError("runs: expected object")
    version = payload.get("schema_version")
    if version == VERSION:
        return evaluate_runs_v01(payload)
    if version == VERSION_V02:
        return evaluate_runs_v02(payload)
    raise ContractError(
        f"runs.schema_version: expected {VERSION!r} or {VERSION_V02!r}, got {version!r}."
    )
