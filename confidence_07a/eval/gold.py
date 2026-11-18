"""gold.v1 标注：读取、校验、模板生成（spec §5.1）。

约束：gold 只能依据日志 JSON 独立标注（source="json_only"），不得使用《案例说明 md》。
本模块不读取任何案例说明文件。
"""
from __future__ import annotations

import datetime as _dt
import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Mapping, Optional, Tuple, Union

from .schema_check import load_schema, validate

GOLD_SCHEMA_NAME = "gold.v1.schema.json"


def _as_doc(obj: Any) -> Dict[str, Any]:
    """接受 {runs:[...]} / {records:[...]} / 纯数组 / 单条运行，统一成文档对象。"""
    if isinstance(obj, list):
        return {"schema": "gold.v1", "runs": obj}
    if isinstance(obj, dict):
        if "runs" in obj:
            return obj
        for k in ("records", "items"):
            if isinstance(obj.get(k), list):
                doc = dict(obj)
                doc["runs"] = doc.pop(k)
                return doc
        if "run_id" in obj and "claims" in obj:
            return {"schema": "gold.v1", "runs": [obj]}
    raise ValueError("无法识别的 gold 格式：需要 {runs:[...]} 或运行数组")


def load_gold(path_or_obj: Union[str, Path, Dict[str, Any], List[Any]]) -> Dict[str, Any]:
    """读取 gold 文件（utf-8）或已解析对象，返回文档对象（含 runs 列表）。"""
    if isinstance(path_or_obj, (str, Path)):
        with open(Path(path_or_obj), "r", encoding="utf-8") as fh:
            return _as_doc(json.load(fh))
    return _as_doc(path_or_obj)


def gold_runs(doc_or_runs: Any) -> List[Dict[str, Any]]:
    """取出运行级标注列表。"""
    if isinstance(doc_or_runs, list):
        return doc_or_runs
    return list(_as_doc(doc_or_runs)["runs"])


def gold_key(run: Mapping[str, Any]) -> Tuple[str, Optional[str]]:
    """(run_id, variant_id)：变体保持原 run_id，以 variant_id 区分。"""
    return (str(run.get("run_id")), run.get("variant_id") or None)


def _trace_ids(log_record: Mapping[str, Any]) -> set:
    return {str(e.get("id")) for e in (log_record.get("trace") or []) if isinstance(e, dict)}


def validate_gold(doc: Any, logs: Optional[Mapping[str, Mapping[str, Any]]] = None) -> Tuple[List[str], List[str]]:
    """校验 gold 文档。返回 (errors, warnings)。

    errors：违反 gold.v1 schema 或引用不一致（会影响指标计算）。
    warnings：可疑但不阻断（如 severe 但未标高风险、json_path 不以 trace[ 开头、仍为 DRAFT）。
    logs：可选 run_id -> 原始日志记录，用于核对 evidence_locators 的 event_id 存在。
    """
    doc = _as_doc(doc)
    errors = validate(doc, load_schema(GOLD_SCHEMA_NAME))
    warnings: List[str] = []
    seen_runs = set()
    n_draft = 0
    for i, run in enumerate(doc.get("runs") or []):
        if not isinstance(run, dict):
            continue
        key = gold_key(run)
        where = f"runs[{i}]({key[0]}{'/' + key[1] if key[1] else ''})"
        if key in seen_runs:
            errors.append(f"{where}: 运行重复")
        seen_runs.add(key)
        if run.get("review_status") == "DRAFT":
            n_draft += 1
        claim_ids: List[str] = [c.get("gold_claim_id") for c in run.get("claims") or [] if isinstance(c, dict)]
        if len(set(claim_ids)) != len(claim_ids):
            errors.append(f"{where}: gold_claim_id 重复")
        goal_ids = {g.get("gold_goal_id") for g in run.get("goals") or [] if isinstance(g, dict)}
        pred_ids = [c.get("pred_claim_id") for c in run.get("claims") or [] if isinstance(c, dict) and c.get("pred_claim_id")]
        if len(set(pred_ids)) != len(pred_ids):
            warnings.append(f"{where}: 多条 gold 结论显式映射到同一 pred_claim_id，只有第一条生效")
        trace_ids = _trace_ids(logs[key[0]]) if logs and key[0] in logs else None
        if logs is not None and trace_ids is None:
            warnings.append(f"{where}: 日志中找不到该 run_id，无法核对证据定位")
        for c in run.get("claims") or []:
            if not isinstance(c, dict):
                continue
            cid = c.get("gold_claim_id")
            if c.get("severe") and not c.get("is_high_risk"):
                warnings.append(f"{where}.{cid}: severe=true 但 is_high_risk=false")
            if c.get("severe") and c.get("gold_status") == "SUPPORT":
                warnings.append(f"{where}.{cid}: severe=true 但 gold_status=SUPPORT")
            for gid in c.get("goal_ids") or []:
                if gid not in goal_ids:
                    errors.append(f"{where}.{cid}: goal_ids 引用不存在的目标 {gid}")
            for loc in c.get("evidence_locators") or []:
                if not isinstance(loc, dict):
                    continue
                if trace_ids is not None and str(loc.get("event_id")) not in trace_ids:
                    errors.append(f"{where}.{cid}: event_id={loc.get('event_id')} 不在日志 trace 中")
                jp = loc.get("json_path")
                if jp and not str(jp).startswith("trace[") and not str(jp).startswith("ai_answer"):
                    warnings.append(f"{where}.{cid}: json_path={jp} 不以 trace[ 开头")
        for gp in run.get("gaps") or []:
            if not isinstance(gp, dict):
                continue
            for cid in gp.get("affects_claims") or []:
                if cid not in claim_ids:
                    errors.append(f"{where}.{gp.get('gold_gap_id')}: affects_claims 引用不存在的结论 {cid}")
    if n_draft:
        warnings.append(f"{n_draft} 个运行的标注仍为 DRAFT（未人工复核）")
    return errors, warnings


def _iter_logs(logs: Union[Mapping[str, Any], Iterable[Mapping[str, Any]]]) -> Iterable[Mapping[str, Any]]:
    if isinstance(logs, Mapping):
        return list(logs.values())
    return list(logs)


def build_gold_template(
    logs: Union[Mapping[str, Mapping[str, Any]], Iterable[Mapping[str, Any]]],
    run_ids: Optional[Iterable[str]] = None,
    annotator: str = "",
    gold_version: str = "template",
) -> Dict[str, Any]:
    """从日志生成待填写的 gold 模板（每运行一条，结论/缺口为空）。

    只放入日志原文（问题、回答、trace 事件 ID 列表）作为辅助字段（以 _ 开头），
    不预填任何判断，避免把模型或规则输出“泄漏”进 gold。
    """
    wanted = set(run_ids) if run_ids is not None else None
    runs = []
    for rec in _iter_logs(logs):
        rid = str(rec.get("run_id"))
        if wanted is not None and rid not in wanted:
            continue
        runs.append({
            "run_id": rid,
            "case_id": str(rec.get("case_id")),
            "annotator": annotator,
            "annotated_at": None,
            "source": "json_only",
            "review_status": "DRAFT",
            "_question": rec.get("user_question"),
            "_answer_text": rec.get("ai_answer"),
            "_trace_event_ids": [e.get("id") for e in rec.get("trace") or [] if isinstance(e, dict)],
            "goals": [],
            "claims": [],
            "gaps": [],
            "run_level": {"answer_has_error": False, "answer_honest_about_limits": False},
        })
    return {
        "schema": "gold.v1",
        "gold_version": gold_version,
        "created_at": _dt.datetime.now(_dt.timezone.utc).isoformat(timespec="seconds"),
        "notes": "模板：仅依据日志 JSON 标注；_ 开头字段为辅助信息，不参与评测。run_level 默认值需人工改写。",
        "runs": runs,
    }
