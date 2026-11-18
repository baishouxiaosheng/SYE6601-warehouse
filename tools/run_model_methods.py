"""07A：用真实模型跑“纯模型（llm_only）”和“混合（hybrid，01A 引擎）”两种方案，结果写成 06B 同形目录。

密钥处理：
- 只从环境变量 CONFIDENCE_07A_LLM_API_KEY 读取；没有就在终端里用 getpass 提示输入（不回显、不落盘）。
- 不读取任何 .env 文件；结果文件里只写 base_url / model 等公开配置，不写密钥。
- 01A 引擎通过 load_settings({"mode": "hybrid"}, env=<仅含本脚本传入的键>) 构造，因此不会读取 01A 目录下的 .env。

用法（在 deliverable/ 下）：
  python -I tools/run_model_methods.py --log LOG.json --engine EG_DIR --out-root OUT \
      --gold gold/pilot_gold_v0.json --methods llm_only,hybrid --model qwen/qwen3.8-27b
  加 --all 跑全部 60 条；--max-calls 限制总调用数（防止意外花费）。
"""
from __future__ import annotations

import argparse
import getpass
import json
import os
import sys
import time
from pathlib import Path
from typing import Any, Dict, List

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))

from confidence_07a.eval import runner as _runner  # noqa: E402
from confidence_07a.eval.baselines import llm_judge  # noqa: E402

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1"


class CountingLLM:
    """包住 01A 的 LLMClient：统计调用次数、token、失败，不改变其行为。"""

    def __init__(self, inner: Any, budget: Dict[str, int]) -> None:
        self.inner = inner
        self.budget = budget
        self.calls: List[Dict[str, Any]] = []
        self.name = getattr(inner, "name", "counting")
        self.available = getattr(inner, "available", True)
        # 01A 的 extract_json 内部调用 self.chat；把实例上的 chat 换成计数版本，才能统计到全部调用
        self._orig_chat = getattr(inner, "chat", None)
        if self._orig_chat is not None:
            try:
                inner.chat = self.chat
            except Exception:  # noqa: BLE001
                pass

    def __getattr__(self, item: str) -> Any:
        return getattr(self.inner, item)

    def chat(self, messages, json_mode=None):  # 与 01A LLMClient.chat 同签名
        if self.budget["used"] >= self.budget["max"]:
            raise RuntimeError("07A 预算上限：已达到 --max-calls")
        self.budget["used"] += 1
        t0 = time.monotonic()
        try:
            resp = self._orig_chat(messages, json_mode=json_mode)
        except Exception as exc:  # 01A 会自行回退规则；这里只记录
            self.calls.append({"ok": False, "error": f"{type(exc).__name__}: {str(exc)[:200]}",
                               "latency_seconds": round(time.monotonic() - t0, 3)})
            raise
        usage = dict(getattr(resp, "usage", {}) or {})
        self.calls.append({"ok": True, "latency_seconds": round(time.monotonic() - t0, 3),
                           "usage": {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")},
                           "attempts": getattr(resp, "attempts", None)})
        return resp


def _records(log_path: str, run_ids: List[str] | None) -> List[Dict[str, Any]]:
    with open(log_path, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    recs = data if isinstance(data, list) else list(data.values())
    if run_ids is not None:
        want = set(run_ids)
        recs = [r for r in recs if str(r.get("run_id")) in want]
    return recs


def _write(out_dir: Path, rec: Dict[str, Any]) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    with open(out_dir / f"{rec.get('run_id')}_{time.time_ns()}.json", "w", encoding="utf-8") as fh:
        json.dump(rec, fh, ensure_ascii=False, indent=2)
        fh.write("\n")


def _done_ids(out_dir: Path) -> set:
    """已有 passed=true 结果的 run_id（断点续跑时跳过）。"""
    done = set()
    if out_dir.is_dir():
        for f in out_dir.glob("*.json"):
            try:
                with open(f, "r", encoding="utf-8") as fh:
                    rec = json.load(fh)
                if rec.get("passed"):
                    done.add(str(rec.get("run_id")))
            except (OSError, ValueError):
                pass
    return done


def run_llm_only(records, cfg, out_dir: Path, budget) -> Dict[str, Any]:
    tot = {"runs": 0, "passed": 0, "skipped_done": 0, "prompt_tokens": 0, "completion_tokens": 0, "seconds": 0.0}
    done = _done_ids(out_dir)
    for r in records:
        if str(r.get("run_id")) in done:
            tot["skipped_done"] += 1
            continue
        if budget["used"] >= budget["max"]:
            print("  预算上限，停止 llm_only")
            break
        budget["used"] += 1
        try:
            rec = llm_judge.judge_record(r, cfg)
        except Exception as exc:  # noqa: BLE001 —— 单条失败不中断批量
            rec = {"case_id": r.get("case_id"), "run_id": r.get("run_id"), "method": "llm_only", "passed": False,
                   "error_type": type(exc).__name__, "error": str(exc)[:300], "llm_call_count": 1}
        if not rec.get("passed"):  # 一次格式/网络失败允许重试一次（计入预算）
            if budget["used"] < budget["max"]:
                budget["used"] += 1
                try:
                    retry = llm_judge.judge_record(r, cfg)
                except Exception as exc:  # noqa: BLE001
                    retry = {"case_id": r.get("case_id"), "run_id": r.get("run_id"), "method": "llm_only",
                             "passed": False, "error_type": type(exc).__name__, "error": str(exc)[:300]}
                retry["retry_of_failure"] = rec.get("error")
                retry["llm_call_count"] = 2
                rec = retry
        _write(out_dir, rec)
        u = rec.get("usage") or {}
        tot["runs"] += 1
        tot["passed"] += int(bool(rec.get("passed")))
        tot["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
        tot["completion_tokens"] += int(u.get("completion_tokens") or 0)
        tot["seconds"] += float(rec.get("elapsed_seconds") or 0)
        print(f"  llm_only {r.get('run_id')}: {'OK' if rec.get('passed') else 'FAIL ' + str(rec.get('error'))[:80]}")
    return tot


def run_hybrid(records, engine: str, base_url: str, api_key: str, model: str, out_dir: Path, budget) -> Dict[str, Any]:
    settings_mod, pipeline_mod, loader_mod, client_mod = _runner._import_engine(engine)
    env = {"EG_LLM_BASE_URL": base_url, "EG_LLM_API_KEY": api_key, "EG_LLM_MODEL": model,
           "EG_MODE": "hybrid", "EG_RENDER": "0", "EG_LLM_MAX_RETRIES": "2", "EG_LLM_TIMEOUT": "120"}
    settings = settings_mod.load_settings({"mode": "hybrid"}, env=env)
    tot = {"runs": 0, "passed": 0, "skipped_done": 0, "llm_calls": 0, "llm_failures": 0, "prompt_tokens": 0,
           "completion_tokens": 0, "seconds": 0.0, "runs_with_llm_nodes": 0}
    done = _done_ids(out_dir)
    for i, r in enumerate(records):
        if str(r.get("run_id")) in done:
            tot["skipped_done"] += 1
            continue
        if budget["used"] >= budget["max"]:
            print("  预算上限，停止 hybrid")
            break
        llm = CountingLLM(client_mod.build_llm(settings.llm), budget)
        item: Dict[str, Any] = {"case_id": r.get("case_id"), "run_id": r.get("run_id"), "method": "hybrid",
                                "execution_kind": "07a_runner_hybrid_mode", "model_called": True, "passed": False,
                                "llm_config": {"base_url": base_url, "model": model, "engine_mode": "hybrid"}}
        t0 = time.perf_counter()
        try:
            copied = json.loads(json.dumps(r, ensure_ascii=False))
            art = pipeline_mod.analyze_run(loader_mod.normalize_record(copied, i), settings, llm=llm, validate=True)
            item["output"] = art.to_dict()
            item["schema_errors"] = list(getattr(art, "schema_errors", []) or [])
            item["passed"] = not item["schema_errors"]
        except Exception as exc:  # noqa: BLE001
            item["error_type"] = type(exc).__name__
            item["error"] = str(exc)[:500]
        item["elapsed_seconds"] = round(time.perf_counter() - t0, 3)
        item["llm_calls"] = llm.calls
        item["llm_call_count"] = len(llm.calls)
        nodes = (((item.get("output") or {}).get("graph") or {}).get("nodes")) or []
        item["llm_created_nodes"] = sum(1 for n in nodes if n.get("created_by") == "llm")
        _write(out_dir, item)
        tot["runs"] += 1
        tot["passed"] += int(item["passed"])
        tot["llm_calls"] += len(llm.calls)
        tot["llm_failures"] += sum(1 for c in llm.calls if not c.get("ok"))
        tot["runs_with_llm_nodes"] += int(item["llm_created_nodes"] > 0)
        for c in llm.calls:
            u = c.get("usage") or {}
            tot["prompt_tokens"] += int(u.get("prompt_tokens") or 0)
            tot["completion_tokens"] += int(u.get("completion_tokens") or 0)
        tot["seconds"] += item["elapsed_seconds"]
        print(f"  hybrid {r.get('run_id')}: passed={item['passed']} calls={len(llm.calls)} llm_nodes={item['llm_created_nodes']}")
    return tot


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--log", required=True)
    ap.add_argument("--engine", required=True, help="01A 引擎目录（不读取其中 .env）")
    ap.add_argument("--out-root", required=True)
    ap.add_argument("--gold", help="只跑 gold 中的运行")
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--methods", default="llm_only,hybrid")
    ap.add_argument("--model", default=os.environ.get("CONFIDENCE_07A_LLM_MODEL", "qwen/qwen3.8-27b"))
    ap.add_argument("--base-url", default=os.environ.get("CONFIDENCE_07A_LLM_BASE_URL", DEFAULT_BASE_URL))
    ap.add_argument("--max-calls", type=int, default=400)
    ap.add_argument("--keep-key-file", action="store_true", help="运行结束后不删除密钥文件")
    ap.add_argument("--key-file", help="从文本文件读取密钥（读后立即删除该文件；用于终端无法粘贴的情况）")
    a = ap.parse_args(argv)

    run_ids = None
    if a.gold and not a.all:
        with open(a.gold, "r", encoding="utf-8") as fh:
            g = json.load(fh)
        run_ids = [str(x["run_id"]) for x in (g.get("runs") if isinstance(g, dict) else g)]
    records = _records(a.log, run_ids)
    print(f"运行数 {len(records)}；模型 {a.model}；端点 {a.base_url}；方法 {a.methods}；调用上限 {a.max_calls}")

    key = os.environ.get("CONFIDENCE_07A_LLM_API_KEY", "").strip()
    if not key and a.key_file and Path(a.key_file).exists():
        with open(a.key_file, "r", encoding="utf-8-sig") as fh:
            key = fh.read().strip()
        print(f"已从 {a.key_file} 读取密钥；运行结束后删除该文件（--keep-key-file 可保留以便断点续跑）。")
    if not key:
        key = getpass.getpass("请输入 OpenRouter API Key（输入不显示，回车确认；不会保存）：").strip()
    if not key:
        print("未提供密钥，退出。")
        return 2

    try:
        return _run(a, records, key)
    finally:
        if a.key_file and not a.keep_key_file and Path(a.key_file).exists():
            try:
                os.remove(a.key_file)
                print(f"已删除密钥文件 {a.key_file}。")
            except OSError as exc:
                print(f"警告：未能删除密钥文件 {a.key_file}：{exc}；请手动删除。")


def _run(a, records, key) -> int:
    budget = {"used": 0, "max": a.max_calls}
    out_root = Path(a.out_root)
    summary: Dict[str, Any] = {"model": a.model, "base_url": a.base_url, "n_runs": len(records),
                               "started_at": time.strftime("%Y-%m-%dT%H:%M:%S%z")}
    methods = [m.strip() for m in a.methods.split(",") if m.strip()]
    if "llm_only" in methods:
        cfg = llm_judge.LLMConfig(base_url=a.base_url, api_key=key, model=a.model, timeout=180.0)
        summary["llm_only"] = run_llm_only(records, cfg, out_root / "llm_only", budget)
    if "hybrid" in methods:
        summary["hybrid"] = run_hybrid(records, a.engine, a.base_url, key, a.model, out_root / "hybrid", budget)
    summary["calls_used"] = budget["used"]
    summary["finished_at"] = time.strftime("%Y-%m-%dT%H:%M:%S%z")
    out_root.mkdir(parents=True, exist_ok=True)
    with open(out_root / "run_summary.json", "w", encoding="utf-8") as fh:
        json.dump(summary, fh, ensure_ascii=False, indent=2)
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    print("完成。可以关闭此终端；密钥未写入任何文件。")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
