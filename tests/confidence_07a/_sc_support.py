"""成绩单测试公共支撑：夹具路径、手工 RunView 构造、极简 draft-07 校验器（标准库）。

夹具 fixtures/egraph_v1/ 只包含：01A rule 模式对 5 个验收案例的原始产物（graph/plan/v1 scorecard）、
工业日志中这 5 条记录、以及 02B 对这 5 条的 local_review 摘取。均由工业日志 JSON 派生。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List, Optional

from confidence_07a.adapters.egraph_v1 import load_run_from_files
from confidence_07a.model import CheckView, ClaimView, EvidenceRef, GapView, GoalView, RunView

FIXTURES = Path(__file__).resolve().parent / "fixtures" / "egraph_v1"
PACKAGE_DIR = Path(__file__).resolve().parents[2] / "confidence_07a"
SCHEMA_PATH = PACKAGE_DIR / "schemas" / "scorecard.v2.schema.json"
ACCEPTANCE_CASES = ("IND-002", "IND-024", "IND-030", "IND-043", "IND-053")


def read_json(path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def fixture_logs() -> Dict[str, dict]:
    return {r["run_id"]: r for r in read_json(FIXTURES / "logs_5cases.json")}


def fixture_run(case_id: str, with_log: bool = True) -> RunView:
    log = fixture_logs().get(f"{case_id}-r1") if with_log else None
    return load_run_from_files(FIXTURES / f"{case_id}_graph.json", FIXTURES / f"{case_id}_plan.json", log_record=log)


def make_run(
    claims: List[dict],
    goals: Optional[List[dict]] = None,
    gaps: Optional[List[dict]] = None,
    checks: Optional[List[dict]] = None,
    answer_text: str = "",
    run_id: str = "T-001-r1",
) -> RunView:
    """手工构造 RunView。claims 元素：{id, text, status, strength?, goals?, gaps?, checks?, expression?, verdict_reason?}"""
    goals = goals if goals is not None else [{"id": "GOAL-001", "text": "测试目标"}]
    gap_objs = [
        GapView(gap_id=g["id"], gap_type=g.get("type", "MISSING_EVIDENCE"), affected_claims=g.get("claims", []),
                criticality=g.get("criticality", "MEDIUM"), description=g.get("description", "测试缺口"))
        for g in (gaps or [])
    ]
    check_objs = [
        CheckView(check_id=c["id"], kind=c.get("kind", "value_match"), verdict=c.get("verdict", "SUPPORT"),
                  affected_claims=c.get("claims", []), evidence_ref=c.get("evidence_ref"),
                  locator=c.get("locator", "trace[c1].result.x"), detail=c.get("detail", "测试检查"),
                  raw={"event_id": "c1"})
        for c in (checks or [])
    ]
    claim_objs = []
    for c in claims:
        cid = c["id"]
        claim_objs.append(
            ClaimView(
                claim_id=cid,
                text=c["text"],
                status=c["status"],
                upstream_strength=c.get("strength", "assertion"),
                expression=c.get("expression"),
                related_goals=list(c.get("goals", [])),
                linkage_method="upstream" if c.get("goals") else "none",
                check_ids=list(c.get("checks", [])) or [x.check_id for x in check_objs if cid in x.affected_claims],
                gap_ids=[g.gap_id for g in gap_objs if cid in g.affected_claims],
                verdict_reason=c.get("verdict_reason"),
                review_status="proposed",
            )
        )
    return RunView(
        run_id=run_id,
        case_id=run_id.rsplit("-r", 1)[0],
        question="测试问题",
        answer_text=answer_text,
        goals=[GoalView(goal_id=g["id"], text=g["text"]) for g in goals],
        claims=claim_objs,
        evidence={"MAT-001": EvidenceRef(evidence_id="MAT-001", run_id=run_id, event_id="c1",
                                         json_path="trace[c1].result", has_edges=True, raw={"node_type": "evidence"})},
        checks=check_objs,
        gaps=gap_objs,
        upstream_versions={"graph_version": "test-graph-v1", "plan_version": None},
        source={"method": "test", "adapter": "hand_built"},
    )


# --------------------------------------------------------------------------
# 极简 JSON Schema draft-07 子集校验（不依赖 jsonschema）
# 支持：type(含数组)/required/properties/items/enum/minimum/maximum/minLength/pattern/$ref(#/definitions)/allOf
# --------------------------------------------------------------------------

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def validate(instance: Any, schema: dict, root: Optional[dict] = None, path: str = "$") -> List[str]:
    root = root or schema
    errs: List[str] = []
    if "$ref" in schema:
        ref = schema["$ref"]
        if not ref.startswith("#/definitions/"):
            return [f"{path}: 不支持的 $ref {ref}"]
        return validate(instance, root["definitions"][ref.split("/")[-1]], root, path)
    for sub in schema.get("allOf", []):
        errs += validate(instance, sub, root, path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            return errs + [f"{path}: 类型应为 {types}，实际 {type(instance).__name__}"]
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} 不在枚举 {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, str):
        if "minLength" in schema and len(instance) < schema["minLength"]:
            errs.append(f"{path}: 长度 < {schema['minLength']}")
        if "pattern" in schema and not re.search(schema["pattern"], instance):
            errs.append(f"{path}: 不匹配 {schema['pattern']}")
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                errs.append(f"{path}: 缺少必填 {k}")
        for k, sub in (schema.get("properties") or {}).items():
            if k in instance:
                errs += validate(instance[k], sub, root, f"{path}.{k}")
    if isinstance(instance, list) and "items" in schema:
        for i, item in enumerate(instance):
            errs += validate(item, schema["items"], root, f"{path}[{i}]")
    return errs
