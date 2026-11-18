"""评测测试用的手算小数据集（直接构造 RunView，不依赖适配器）。

文本取自工业日志中 IND-053 / IND-043 / IND-024 的回答风格，状态为手工设定，
仅用于验证公式，不代表对真实案例的标注。

手算结果（见 test_eval_metrics.py）：
  FSR严格 1/2，FSR广义 1/4，IAE 1/2，准确率 3/6，macro-F1 1.5/3，κ=0.25，
  抽取覆盖 6/7，多抽 1/7，缺口 P=2/3 R=2/3 F1=4/6，参数(值) 3/7，参数(键) 4/7，动作存在 1/2，
  严重召回 1/1，误报 1/1，ECE=2.5/6。
"""
from confidence_07a.model import ActionView, ClaimView, GapView, RunView


def gold_claim(gid, span, status, expression="DEFINITE", pred=None, high=False, severe=False):
    d = {
        "gold_claim_id": gid,
        "answer_span": span,
        "expression": expression,
        "gold_status": status,
        "is_high_risk": high,
        "severe": severe,
        "evidence_locators": [{"event_id": "c1", "json_path": "trace[c1].result"}],
        "rationale": "测试",
    }
    if pred:
        d["pred_claim_id"] = pred
    return d


def gold_run(run_id, claims, gaps=None, has_error=True, honest=False, variant_id=None):
    d = {
        "run_id": run_id,
        "case_id": run_id.rsplit("-r", 1)[0],
        "annotator": "test",
        "annotated_at": "2026-11-17",
        "source": "json_only",
        "review_status": "DRAFT",
        "goals": [{"gold_goal_id": "G1", "text": "问题"}],
        "claims": claims,
        "gaps": gaps or [],
        "run_level": {"answer_has_error": has_error, "answer_honest_about_limits": honest},
    }
    if variant_id:
        d["variant_id"] = variant_id
    return d


def build_dataset():
    gold_a = gold_run("IND-901-r1", [
        gold_claim("g1", "今天吊装18吨设备没有问题", "REFUTE", pred="P1", high=True, severe=True),
        gold_claim("g2", "吊装许可已审批", "UNKNOWN", pred="P2"),
        gold_claim("g3", "设备载荷为18吨", "SUPPORT", pred="P3"),
        gold_claim("g4", "目前无法确定能否开机作业", "MISSING_RULE", expression="DECLARED_UNKNOWN"),
    ], gaps=[
        {"gold_gap_id": "GG1", "affects_claims": ["g1"], "gap_type": "CONFLICT", "missing_info": "许可",
         "required_params": {"tool": "permit.get", "args": {"permit_id": "PTW-1", "date": "2026-11-13"},
                             "success_field": "status"}},
        {"gold_gap_id": "GG2", "affects_claims": ["g4"], "gap_type": "MISSING_RULE", "missing_info": "放行规则",
         "required_params": None},
    ])
    gold_b = gold_run("IND-902-r1", [
        gold_claim("g1", "压力为21500 MPa", "REFUTE", pred="Q1"),
        gold_claim("g2", "全天产量4200件", "UNKNOWN", expression="HEDGED", pred="Q2"),
        gold_claim("g3", "白班1800件", "SUPPORT", expression="SCOPED_PARTIAL", pred="Q3"),
    ], gaps=[
        {"gold_gap_id": "GB1", "affects_claims": ["g2"], "gap_type": "INCOMPLETE_RESULT", "missing_info": "夜班",
         "required_params": {"tool": "production.daily_output",
                             "args": {"line_id": "Line-D", "business_date": "2026-11-13"}}},
    ], has_error=False)

    run_a = RunView(
        run_id="IND-901-r1", case_id="IND-901", question="能吊装吗", answer_text="...",
        claims=[
            ClaimView("P1", "今天吊装18吨设备没有问题", "SUPPORT"),
            ClaimView("P2", "吊装许可已审批", "REFUTE"),
            ClaimView("P3", "设备载荷为18吨", "SUPPORT"),
            ClaimView("P4", "天气晴朗适合户外作业", "UNKNOWN"),
        ],
        gaps=[
            GapView("PG1", "CONFLICT", affected_claims=["P1"]),
            GapView("PG2", "MISSING_EVIDENCE", affected_claims=["P2"]),
        ],
        actions=[
            ActionView("AC1", "requery", gap_ids=["PG1"], tool="permit.get",
                       known_arguments={"permit_id": "PTW-2"},
                       pending_arguments={"date": "业务日期 2026-11-13"},
                       success_criterion="返回 status=APPROVED"),
        ],
        source={"method": "rule", "elapsed_seconds": 0.01},
    )
    run_b = RunView(
        run_id="IND-902-r1", case_id="IND-902", question="产量", answer_text="...",
        claims=[
            ClaimView("Q1", "压力为21500 MPa", "REFUTE"),
            ClaimView("Q2", "全天产量4200件", "UNKNOWN"),
            ClaimView("Q3", "白班1800件", "UNKNOWN"),
        ],
        gaps=[GapView("QG1", "LIMITED_SCOPE", affected_claims=["Q2"])],
        actions=[ActionView("AC9", "recompute", target_claims=["Q3"], tool="production.daily_output",
                            known_arguments={"line_id": "Line-D"})],
        source={"method": "rule", "elapsed_seconds": 0.03},
    )
    scorecards = {
        "IND-901-r1": {"high_risk_alert": True, "support_score": 0.5, "grade": "INSUFFICIENT"},
        "IND-902-r1": {"high_risk_alert": True, "support_score": 1.0, "grade": "QUALIFIED"},
    }
    return [run_a, run_b], [gold_a, gold_b], scorecards
