"""工业监控日志读取（只读、utf-8）。

支持四种形态：单条对象、数组、``{"runs": [...]}``、目录（逐个 *.json）。
返回 ``run_id -> 原始记录``。不做任何字段改写。
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List


def _records_from_payload(payload: Any) -> List[Dict[str, Any]]:
    if isinstance(payload, list):
        return [r for r in payload if isinstance(r, dict)]
    if isinstance(payload, dict):
        if isinstance(payload.get("runs"), list):
            return [r for r in payload["runs"] if isinstance(r, dict)]
        if "run_id" in payload or "case_id" in payload:
            return [payload]
    return []


def _read_json(path: Path) -> Any:
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def load_logs(path) -> Dict[str, Dict[str, Any]]:
    """读取日志，返回 ``{run_id: record}``；缺 run_id 时退化用 ``<case_id>-r1``。"""
    p = Path(path)
    files: Iterable[Path]
    if p.is_dir():
        files = sorted(p.glob("*.json"))
    else:
        files = [p]
    out: Dict[str, Dict[str, Any]] = {}
    for f in files:
        for rec in _records_from_payload(_read_json(f)):
            run_id = rec.get("run_id") or (f"{rec.get('case_id')}-r1" if rec.get("case_id") else None)
            if run_id:
                out[str(run_id)] = rec
    return out


def index_by_case(logs: Dict[str, Dict[str, Any]]) -> Dict[str, Dict[str, Any]]:
    """``case_id -> record``（同一 case 多条时取 run_id 排序后的第一条）。"""
    out: Dict[str, Dict[str, Any]] = {}
    for run_id in sorted(logs):
        rec = logs[run_id]
        cid = rec.get("case_id")
        if cid and cid not in out:
            out[cid] = rec
    return out
