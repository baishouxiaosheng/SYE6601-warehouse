"""方法运行器（spec §5.3）。

- run_engine_rule：离线调用 01A 引擎 rule 模式（插入 engine_path 到 sys.path；
  load_settings({"mode": "rule"}, env={})，显式 env={} 使引擎不读取 .env 与进程环境变量；NullLLM，不调用模型）。
- load_results_dir：读取 06B 格式结果目录（每 run 取文件名时间戳最大者，可只保留 passed=true）。
- run_methods：按 method -> 结果来源 的映射得到各方法的 RunView 列表（及 v1 成绩单），供 evaluate 使用。

需要密钥的方法（hybrid/llm_only）只能以“已有结果目录”的形式接入，本模块不执行。
RunView 转换使用 adapters.egraph_v1（由其他成员实现，此处延迟导入）。
"""
from __future__ import annotations

import copy
import glob
import json
import os
import re
import sys
import time
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Union

from ..model import RunView

_RESULT_NAME_RE = re.compile(r"^(?P<run_id>.+?)_(?P<ts>\d+)\.json$")


# ---------------------------------------------------------------------------
# 01A 引擎（rule 模式）
# ---------------------------------------------------------------------------

def _import_engine(engine_path: Union[str, Path]):
    """从 engine_path 导入 01A 引擎模块；确保 config/egraph 包来自该目录。"""
    root = Path(engine_path).resolve()
    if not (root / "egraph" / "pipeline.py").is_file():
        raise FileNotFoundError(f"找不到 01A 引擎：{root / 'egraph' / 'pipeline.py'}")
    # 清掉可能来自其他目录的同名包，避免误导入
    for name in list(sys.modules):
        if name in ("config", "egraph") or name.startswith(("config.", "egraph.")):
            mod = sys.modules[name]
            f = getattr(mod, "__file__", None)
            if f is None or not Path(f).resolve().is_relative_to(root):
                del sys.modules[name]
    if str(root) not in sys.path:
        sys.path.insert(0, str(root))
    import importlib

    settings_mod = importlib.import_module("config.settings")
    pipeline_mod = importlib.import_module("egraph.pipeline")
    loader_mod = importlib.import_module("egraph.loader")
    client_mod = importlib.import_module("egraph.llm.client")
    for m in (settings_mod, pipeline_mod):
        if not Path(m.__file__).resolve().is_relative_to(root):
            raise ImportError(f"导入了其他目录的模块：{m.__file__}")
    return settings_mod, pipeline_mod, loader_mod, client_mod


def _iter_log_records(logs: Union[str, Path, Mapping[str, Any], Sequence[Mapping[str, Any]]]) -> List[Dict[str, Any]]:
    if isinstance(logs, (str, Path)):
        with open(Path(logs), "r", encoding="utf-8") as fh:
            data = json.load(fh)
    else:
        data = logs
    if isinstance(data, Mapping):
        if "run_id" in data and "trace" in data:
            return [dict(data)]
        return [dict(v) for v in data.values()]
    return [dict(x) for x in data]


def run_engine_rule(
    engine_path: Union[str, Path],
    logs: Union[str, Path, Mapping[str, Any], Sequence[Mapping[str, Any]]],
    run_ids: Optional[Iterable[str]] = None,
    validate: bool = True,
) -> Dict[str, Dict[str, Any]]:
    """以 rule 模式运行 01A 引擎，返回 run_id -> 结果记录（与 06B 记录同形）：

    {case_id, run_id, method:"rule", execution_kind, model_called:false, passed, error_type?, error?,
     elapsed_seconds, output:{case_id, graph, plan, scorecard}}

    同一 run_id 的受控变体请分别调用（返回键相同）。不修改传入日志（深拷贝）。
    """
    settings_mod, pipeline_mod, loader_mod, client_mod = _import_engine(engine_path)
    settings = settings_mod.load_settings({"mode": "rule"}, env={})
    wanted = set(run_ids) if run_ids is not None else None
    out: Dict[str, Dict[str, Any]] = {}
    for i, rec in enumerate(_iter_log_records(logs)):
        rid = str(rec.get("run_id"))
        if wanted is not None and rid not in wanted:
            continue
        item: Dict[str, Any] = {
            "case_id": rec.get("case_id"),
            "run_id": rid,
            "method": "rule",
            "execution_kind": "07a_runner_rule_mode",
            "model_called": False,
            "llm_call_count": 0,
            "passed": False,
        }
        t0 = time.perf_counter()
        try:
            copied = json.loads(json.dumps(rec, ensure_ascii=False))
            artifact = pipeline_mod.analyze_run(
                loader_mod.normalize_record(copied, i),
                settings,
                llm=client_mod.NullLLM("07A runner 强制规则模式"),
                validate=validate,
            )
            item["output"] = artifact.to_dict()
            item["schema_errors"] = list(getattr(artifact, "schema_errors", []) or [])
            item["passed"] = not item["schema_errors"]
        except Exception as exc:  # noqa: BLE001 —— 批量验收需记录失败原因而不中断
            item["error_type"] = type(exc).__name__
            item["error"] = str(exc)[:500]
        item["elapsed_seconds"] = round(time.perf_counter() - t0, 6)
        out[rid] = item
    return out


# ---------------------------------------------------------------------------
# 06B 结果目录
# ---------------------------------------------------------------------------

def load_results_dir(
    results_dir: Union[str, Path],
    only_passed: bool = True,
    batch_prefix: Optional[str] = None,
) -> Dict[str, Dict[str, Any]]:
    """读取 06B 格式目录 `{run_id}_{time_ns}.json`：同一 run_id 取时间戳最大者。

    only_passed：只保留 passed=true（失败记录仍返回在 `_failed` 键下，便于报告处理失败原因）。
    batch_prefix：只取文件名时间戳以该前缀开头的批次。
    返回 run_id -> 记录（附 `_path`）；若有失败记录，另有键 "_failed" -> {run_id: 记录}。
    """
    best: Dict[str, tuple] = {}
    for p in sorted(Path(results_dir).glob("*.json")):
        m = _RESULT_NAME_RE.match(p.name)
        if not m:
            continue
        ts = m.group("ts")
        if batch_prefix and not ts.startswith(batch_prefix):
            continue
        rid = m.group("run_id")
        if rid not in best or int(ts) > int(best[rid][0]):
            best[rid] = (ts, p)
    out: Dict[str, Dict[str, Any]] = {}
    failed: Dict[str, Dict[str, Any]] = {}
    for rid in sorted(best):
        p = best[rid][1]
        with open(p, "r", encoding="utf-8") as fh:
            rec = json.load(fh)
        rec["_path"] = str(p)
        if only_passed and rec.get("passed") is False:
            failed[rid] = rec
            continue
        out[rid] = rec
    if failed:
        out["_failed"] = failed  # type: ignore[assignment]
    return out


# ---------------------------------------------------------------------------
# 编排
# ---------------------------------------------------------------------------

def _adapters():
    from ..adapters import egraph_v1  # 延迟导入：由其他成员实现

    return egraph_v1


def records_to_runs(
    records: Mapping[str, Dict[str, Any]],
    method: str,
    logs_by_run: Optional[Mapping[str, Dict[str, Any]]] = None,
    converter: Optional[Callable[..., RunView]] = None,
) -> Dict[str, Any]:
    """06B/runner 记录 -> RunView 列表 + v1 成绩单。

    converter(graph, plan, log_record, method) -> RunView，默认 adapters.egraph_v1.load_run_from_artifacts。
    elapsed_seconds / 变体字段写入 run.source（若适配器未写）。
    """
    if converter is None:
        converter = _adapters().load_run_from_artifacts
    runs: List[RunView] = []
    v1: Dict[str, Dict[str, Any]] = {}
    failures: Dict[str, str] = {}
    for rid, rec in records.items():
        if rid == "_failed":
            for frid, frec in rec.items():
                failures[frid] = f"{frec.get('error_type') or 'failed'}"
            continue
        out = rec.get("output") or {}
        if not out.get("graph"):
            failures[rid] = f"{rec.get('error_type') or 'no_output'}: {rec.get('error') or ''}".strip()
            continue
        log_rec = (logs_by_run or {}).get(rid)
        run = converter(out.get("graph"), out.get("plan"), log_rec, method)
        src = run.source if isinstance(run.source, dict) else {}
        src.setdefault("method", method)
        if rec.get("elapsed_seconds") is not None:
            src.setdefault("elapsed_seconds", rec.get("elapsed_seconds"))
        for k in ("variant_id", "variant_kind", "llm_call_count", "model_calls", "batch_id"):
            if rec.get(k) is not None:
                src.setdefault(k, rec.get(k))
        if rec.get("_path"):
            src.setdefault("result_path", rec["_path"])
        run.source = src
        runs.append(run)
        if out.get("scorecard"):
            key = rid if not src.get("variant_id") else f"{rid}#{src['variant_id']}"
            v1[key] = out["scorecard"]
    return {"runs": runs, "v1_scorecards": v1, "failures": failures}


def run_methods(
    sources: Mapping[str, Any],
    logs: Union[None, str, Path, Mapping[str, Any], Sequence[Mapping[str, Any]]] = None,
    converter: Optional[Callable[..., RunView]] = None,
) -> Dict[str, Dict[str, Any]]:
    """按 method -> 来源 生成各方法的预测。

    来源可以是：
      - 目录路径（str/Path）：06B 格式结果目录；
      - {"results_dir": 路径, "only_passed"?, "batch_prefix"?}；
      - {"engine": 01A 引擎路径, "run_ids"?: [...]}：离线 rule 模式现跑（需 logs）；
      - {"records": run_id -> 记录}：已加载的记录；
      - list[RunView]：直接使用。
    返回 method -> {"runs": [RunView], "v1_scorecards": {run_id: dict}, "failures": {run_id: 原因}}。
    """
    logs_by_run: Optional[Dict[str, Dict[str, Any]]] = None
    if logs is not None:
        logs_by_run = {str(r.get("run_id")): r for r in _iter_log_records(logs)}
    result: Dict[str, Dict[str, Any]] = {}
    for method, src in sources.items():
        if isinstance(src, list):
            result[method] = {"runs": list(src), "v1_scorecards": {}, "failures": {}}
            continue
        if isinstance(src, (str, Path)):
            records = load_results_dir(src)
        elif isinstance(src, Mapping) and "results_dir" in src:
            records = load_results_dir(src["results_dir"], src.get("only_passed", True), src.get("batch_prefix"))
        elif isinstance(src, Mapping) and "engine" in src:
            if logs is None:
                raise ValueError(f"{method}: engine 来源需要提供 logs")
            records = run_engine_rule(src["engine"], logs, src.get("run_ids"))
        elif isinstance(src, Mapping) and "records" in src:
            records = src["records"]
        else:
            raise ValueError(f"{method}: 无法识别的来源 {type(src).__name__}")
        result[method] = records_to_runs(records, method, logs_by_run, converter)
    return result
