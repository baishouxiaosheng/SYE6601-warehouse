"""纯模型基线 llm_only（spec §5.3；需求 §6“比较纯规则、纯模型和混合方案”）。

给定一条工业日志记录，请 OpenAI 兼容的 chat/completions 端点：
  1) 把 ai_answer 拆成原子结论；2) 只依据 trace 给每条结论标五态之一；3) 给出证据定位 trace[事件].result.字段；
  4) 列出缺口与补查动作。
模型输出被转换为 RunView（`parsed_to_run_view`），也可以写成 06B 同形结果记录，再经
`runner.run_methods({"llm_only": {"results_dir": DIR}}, logs, converter=converter)` 进入评测。

注意：
- 这是**对照基线**，不是评分裁判；07A 成绩单不调用模型。
- 配置只来自环境变量 CONFIDENCE_07A_LLM_BASE_URL / CONFIDENCE_07A_LLM_API_KEY / CONFIDENCE_07A_LLM_MODEL；
  不读取任何 .env 文件，不在代码中写入密钥，输出与日志中不记录密钥。
- 仅用标准库 urllib；每次调用记录 token 用量与延迟。
- `--dry-run` 只打印提示词，不发网络请求、不需要密钥。
- 提示词只包含日志记录本身（问题、可见上下文、trace、回答），不包含任何案例说明或 gold。

命令行：
  python -m confidence_07a.eval.baselines.llm_judge --log LOG.json --run-ids IND-002-r1 --dry-run
  python -m confidence_07a.eval.baselines.llm_judge --log LOG.json --all --out results/llm_only
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import http.client
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, List, Mapping, Optional, Sequence, Tuple

from ...model import (
    EXPRESSIONS,
    GAP_TYPES,
    STATUSES,
    UNKNOWN,
    ActionView,
    ClaimView,
    EvidenceRef,
    GapView,
    GoalView,
    RunView,
)

JUDGE_VERSION = "07a-llm-judge-v1"
ENV_BASE_URL = "CONFIDENCE_07A_LLM_BASE_URL"
ENV_API_KEY = "CONFIDENCE_07A_LLM_API_KEY"
ENV_MODEL = "CONFIDENCE_07A_LLM_MODEL"

# transport(url, headers, body_bytes, timeout) -> (http_status, response_bytes)
Transport = Callable[[str, Dict[str, str], bytes, float], Tuple[int, bytes]]

SYSTEM_PROMPT = """你是工业智能体回答的证据审核员。只能依据给定监控日志中的工具返回（trace）判断，不得使用常识或经验补充厂内规则。

任务：
1. 把“AI 回答”拆成可独立核验的原子结论（读数、计算、状态、推断、预测、审批/许可、操作建议分别拆开）。每条结论的 text 必须是回答原文中的连续片段。
2. 列出用户问题中的待回答目标 goals。
3. 对每条结论给出证据状态 status（只能取以下五个值之一）：
   - SUPPORT：适用字段直接给出，或可由字段复算得出；
   - REFUTE：适用字段与结论矛盾（数值/单位/阈值/状态/时序等）；
   - UNKNOWN：缺少读数或证据（未查、只查了部分页/部分时段、抽样外推等）；
   - CONFLICT：两个来源不一致且日志中没有可引用的优先规则；
   - MISSING_RULE：需要一条判断依据（正常区间、放行/审批条件等），但日志中没有该规则或阈值。
4. 给出结论的措辞强度 expression：DEFINITE / HEDGED / DECLARED_UNKNOWN / SCOPED_PARTIAL。
5. 每条结论给出证据定位 evidence：[{"event_id": "c1", "json_path": "trace[c1].result.字段"}]；没有依据则为空列表。
6. 对非 SUPPORT、非 REFUTE 的结论给出缺口 gaps（type 取 MISSING_EVIDENCE / MISSING_RULE / MISSING_DEPENDENCY / INCOMPLETE_RESULT / CONFLICT / LIMITED_SCOPE）与补查动作 actions（工具名、已知参数、待定参数、成功判据）。

只输出一个 JSON 对象，不要输出其他文字。格式：
{"goals":[{"id":"G1","text":"..."}],
 "claims":[{"id":"C1","text":"<回答原文片段>","status":"SUPPORT","expression":"DEFINITE","goal_ids":["G1"],"high_risk":false,
            "evidence":[{"event_id":"c1","json_path":"trace[c1].result.x"}],"reason":"<依据字段与数值>"}],
 "gaps":[{"id":"GAP1","type":"MISSING_EVIDENCE","affects":["C1"],"criticality":"HIGH","description":"..."}],
 "actions":[{"id":"A1","gap_ids":["GAP1"],"target_claims":["C1"],"tool":"<工具名或null>","arguments":{},"pending_arguments":{},"success_criterion":"..."}]}"""


# ---------------------------------------------------------------------------
# 配置
# ---------------------------------------------------------------------------

@dataclass
class LLMConfig:
    base_url: str
    api_key: str
    model: str
    timeout: float = 120.0
    temperature: float = 0.0
    json_mode: bool = True

    @staticmethod
    def from_env(env: Optional[Mapping[str, str]] = None, **overrides: Any) -> "LLMConfig":
        """只读进程环境变量（或传入的映射）；不读取 .env 文件。缺项抛 RuntimeError（不回显密钥）。"""
        env = os.environ if env is None else env
        vals = {k: (env.get(v) or "").strip() for k, v in
                (("base_url", ENV_BASE_URL), ("api_key", ENV_API_KEY), ("model", ENV_MODEL))}
        missing = [n for n, k in ((ENV_BASE_URL, "base_url"), (ENV_API_KEY, "api_key"), (ENV_MODEL, "model")) if not vals[k]]
        if missing:
            raise RuntimeError("缺少环境变量：" + ", ".join(missing) + "（不会读取 .env 文件）")
        return LLMConfig(**vals, **overrides)

    def public(self) -> Dict[str, Any]:
        """可写入结果的配置（不含密钥）。"""
        return {"base_url": self.base_url, "model": self.model, "temperature": self.temperature,
                "json_mode": self.json_mode, "timeout": self.timeout}

    def endpoint(self) -> str:
        u = self.base_url.rstrip("/")
        return u if u.endswith("/chat/completions") else u + "/chat/completions"


# ---------------------------------------------------------------------------
# 提示词
# ---------------------------------------------------------------------------

def build_messages(record: Mapping[str, Any]) -> List[Dict[str, str]]:
    """只使用日志记录本身的字段。"""
    payload = {
        "run_id": record.get("run_id"),
        "user_question": record.get("user_question"),
        "visible_context": record.get("visible_context"),
        "trace": record.get("trace"),
    }
    user = (
        "监控日志（JSON）：\n" + json.dumps(payload, ensure_ascii=False, indent=1)
        + "\n\nAI 回答：\n" + str(record.get("ai_answer") or "")
        + "\n\n请按系统说明输出 JSON。"
    )
    return [{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": user}]


def render_prompt(record: Mapping[str, Any]) -> str:
    return "\n\n".join(f"### {m['role']}\n{m['content']}" for m in build_messages(record))


# ---------------------------------------------------------------------------
# 传输与调用
# ---------------------------------------------------------------------------

def urllib_transport(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> Tuple[int, bytes]:
    req = urllib.request.Request(url, data=body, headers=headers, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:  # noqa: S310 —— URL 来自用户环境变量
            return int(resp.status), resp.read()
    except urllib.error.HTTPError as exc:
        return int(exc.code), exc.read() or b""
    except (urllib.error.URLError, TimeoutError, OSError, http.client.HTTPException) as exc:
        # 网络层失败（拒绝连接、超时、DNS）：返回 status=0 与 JSON 错误体，由 call_chat 记为失败记录，不中断批量运行
        reason = getattr(exc, "reason", exc)
        msg = f"network error: {type(exc).__name__}: {str(reason)[:200]}"
        return 0, json.dumps({"error": {"message": msg}}, ensure_ascii=False).encode("utf-8")


def call_chat(
    config: LLMConfig,
    messages: List[Dict[str, str]],
    transport: Optional[Transport] = None,
) -> Dict[str, Any]:
    """一次 chat/completions 调用。返回 {content, usage, latency_seconds, http_status, error}。"""
    transport = transport or urllib_transport
    body: Dict[str, Any] = {"model": config.model, "messages": messages, "temperature": config.temperature}
    if config.json_mode:
        body["response_format"] = {"type": "json_object"}
    headers = {"Content-Type": "application/json; charset=utf-8", "Authorization": f"Bearer {config.api_key}"}
    t0 = time.monotonic()
    status, raw = transport(config.endpoint(), headers, json.dumps(body, ensure_ascii=False).encode("utf-8"), config.timeout)
    latency = round(time.monotonic() - t0, 6)
    out: Dict[str, Any] = {"http_status": status, "latency_seconds": latency, "content": None, "usage": None, "error": None}
    try:
        data = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        out["error"] = f"响应不是 JSON：{type(exc).__name__}"
        return out
    if status != 200:
        err = data.get("error") if isinstance(data, dict) else None
        msg = err.get("message") if isinstance(err, dict) else err
        out["error"] = f"HTTP {status}: {str(msg)[:300] if msg else ''}".strip()
        return out
    try:
        out["content"] = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        out["error"] = "响应缺少 choices[0].message.content"
    usage = data.get("usage") if isinstance(data, dict) else None
    if isinstance(usage, dict):
        out["usage"] = {k: usage.get(k) for k in ("prompt_tokens", "completion_tokens", "total_tokens")}
    return out


def parse_json_content(text: Optional[str]) -> Dict[str, Any]:
    """容忍 ```json 围栏与前后多余文字；取第一个 { 到最后一个 }。"""
    if not text:
        raise ValueError("模型输出为空")
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    i, j = t.find("{"), t.rfind("}")
    if i < 0 or j <= i:
        raise ValueError("模型输出中没有 JSON 对象")
    obj = json.loads(t[i: j + 1])
    if not isinstance(obj, dict):
        raise ValueError("模型输出不是 JSON 对象")
    return obj


# ---------------------------------------------------------------------------
# 转换为 RunView
# ---------------------------------------------------------------------------

_TRACE_RE = re.compile(r"^trace\[([^\]]+)\]")


def _resolve(record: Mapping[str, Any], json_path: str) -> Tuple[bool, Any, Optional[str]]:
    """校验 json_path 能否在日志中解析；返回 (ok, value, tool)。"""
    from ..variants import _find_event, _get, parse_trace_path  # 复用路径工具

    p = parse_trace_path(json_path)
    if not p:
        return False, None, None
    ev = _find_event(record, p[0])
    if ev is None:
        return False, None, None
    if not p[1]:
        return True, None, ev.get("tool")
    sentinel = object()
    cur: Any = ev
    for t in p[1]:
        if isinstance(t, int) and isinstance(cur, list) and 0 <= t < len(cur):
            cur = cur[t]
        elif isinstance(t, str) and isinstance(cur, dict) and t in cur:
            cur = cur[t]
        else:
            cur = sentinel
            break
    if cur is sentinel:
        return False, None, ev.get("tool")
    return True, _get(ev, p[1]), ev.get("tool")


def parsed_to_run_view(
    parsed: Mapping[str, Any],
    record: Mapping[str, Any],
    method: str = "llm_only",
    source_extra: Optional[Mapping[str, Any]] = None,
) -> RunView:
    """模型 JSON -> RunView。非法状态记为 UNKNOWN 并写 notes；无法解析的证据定位计入 build_risks。"""
    run_id = str(record.get("run_id") or parsed.get("run_id") or "")
    case_id = str(record.get("case_id") or run_id.rsplit("-r", 1)[0])
    notes: List[str] = []
    goals = [GoalView(goal_id=str(g.get("id") or f"G{i + 1}"), text=str(g.get("text") or ""))
             for i, g in enumerate(parsed.get("goals") or []) if isinstance(g, dict)]
    goal_ids = {g.goal_id for g in goals}
    evidence: Dict[str, EvidenceRef] = {}
    claims: List[ClaimView] = []
    invalid_locators: List[str] = []
    gaps_by_claim: Dict[str, List[str]] = {}
    acts_by_claim: Dict[str, List[str]] = {}

    gaps: List[GapView] = []
    for i, g in enumerate(parsed.get("gaps") or []):
        if not isinstance(g, dict):
            continue
        gid = str(g.get("id") or f"GAP{i + 1}")
        gt = str(g.get("type") or "MISSING_EVIDENCE").upper()
        if gt not in GAP_TYPES:
            notes.append(f"{gid}: 非法缺口类型 {gt}，按 MISSING_EVIDENCE 处理")
            gt = "MISSING_EVIDENCE"
        aff = [str(x) for x in g.get("affects") or g.get("affected_claims") or []]
        crit = str(g.get("criticality") or "").upper() or None
        gaps.append(GapView(gap_id=gid, gap_type=gt, affected_claims=aff,
                            criticality=crit if crit in ("HIGH", "MEDIUM", "LOW") else None,
                            description=g.get("description"), raw=dict(g)))
        for c in aff:
            gaps_by_claim.setdefault(c, []).append(gid)

    actions: List[ActionView] = []
    for i, a in enumerate(parsed.get("actions") or []):
        if not isinstance(a, dict):
            continue
        aid = str(a.get("id") or f"A{i + 1}")
        tc = [str(x) for x in a.get("target_claims") or []]
        gids = [str(x) for x in a.get("gap_ids") or []]
        if not tc:
            tc = sorted({c for g in gaps if g.gap_id in gids for c in g.affected_claims})
        actions.append(ActionView(action_id=aid, action_type="requery", gap_ids=gids, target_claims=tc,
                                  tool=a.get("tool"), known_arguments=dict(a.get("arguments") or {}),
                                  pending_arguments=dict(a.get("pending_arguments") or {}),
                                  success_criterion=a.get("success_criterion"),
                                  executability="needs_confirmation", raw=dict(a)))
        for c in tc:
            acts_by_claim.setdefault(c, []).append(aid)

    n_ev = 0
    for i, c in enumerate(parsed.get("claims") or []):
        if not isinstance(c, dict):
            continue
        cid = str(c.get("id") or f"C{i + 1}")
        status = str(c.get("status") or "").upper()
        if status not in STATUSES:
            notes.append(f"{cid}: 非法状态 {status!r}，按 UNKNOWN 处理")
            status = UNKNOWN
        expr = str(c.get("expression") or "").upper() or None
        if expr not in EXPRESSIONS:
            expr = None  # 交给 07A expression.py 判定
        ev_ids: List[str] = []
        for loc in c.get("evidence") or []:
            if not isinstance(loc, dict):
                continue
            jp = str(loc.get("json_path") or (f"trace[{loc.get('event_id')}].result" if loc.get("event_id") else ""))
            ok, val, tool = _resolve(record, jp)
            if not ok:
                invalid_locators.append(f"{cid}:{jp}")
                continue
            n_ev += 1
            eid = f"EV-{n_ev:03d}"
            m = _TRACE_RE.match(jp)
            evidence[eid] = EvidenceRef(evidence_id=eid, run_id=run_id, event_id=m.group(1) if m else None, tool=tool,
                                        json_path=jp, value=val if not isinstance(val, (dict, list)) else None,
                                        excerpt=json.dumps(val, ensure_ascii=False)[:200] if val is not None else None,
                                        has_edges=True)
            ev_ids.append(eid)
        rg = [str(x) for x in c.get("goal_ids") or [] if str(x) in goal_ids]
        claims.append(ClaimView(
            claim_id=cid, text=str(c.get("text") or ""), status=status, expression=expr,
            related_goals=rg, linkage_method="upstream" if rg else "none", evidence_ids=ev_ids,
            gap_ids=gaps_by_claim.get(cid, []), action_ids=acts_by_claim.get(cid, []),
            verdict_reason=c.get("reason"), status_source="llm_only", raw=dict(c)))
    if invalid_locators:
        notes.append(f"{len(invalid_locators)} 个证据定位无法在日志中解析（模型可能编造字段）")
    src: Dict[str, Any] = {"method": method, "engine": JUDGE_VERSION, "adapter": "llm_judge.parsed_to_run_view"}
    src.update(dict(source_extra or {}))
    return RunView(
        run_id=run_id, case_id=case_id, question=str(record.get("user_question") or ""),
        answer_text=str(record.get("ai_answer") or ""), goals=goals, claims=claims, evidence=evidence,
        gaps=gaps, actions=actions, scope={"declared_by": "llm_only"},
        upstream_versions={"graph_version": JUDGE_VERSION, "plan_version": JUDGE_VERSION},
        source=src, build_risks={"invalid_locators": invalid_locators}, notes=notes)


def judge_record(
    record: Mapping[str, Any],
    config: LLMConfig,
    transport: Optional[Transport] = None,
) -> Dict[str, Any]:
    """对一条日志调用一次模型，返回 06B 同形结果记录（output.graph 内含 llm_judge 原始解析结果）。"""
    t0 = time.monotonic()
    call = call_chat(config, build_messages(record), transport)
    rec: Dict[str, Any] = {
        "case_id": record.get("case_id"), "run_id": record.get("run_id"), "method": "llm_only",
        "execution_kind": "07a_llm_judge", "model_called": True, "passed": False,
        "llm_call_count": 1, "usage": call.get("usage"), "latency_seconds": call.get("latency_seconds"),
        "llm_config": config.public(), "judge_version": JUDGE_VERSION,
    }
    if call.get("error"):
        rec["error_type"] = "LLMCallError"
        rec["error"] = call["error"]
    else:
        try:
            parsed = parse_json_content(call.get("content"))
            rec["output"] = {"graph": {"run_id": record.get("run_id"), "case_id": record.get("case_id"),
                                       "format": JUDGE_VERSION, "llm_judge": parsed}, "plan": None}
            rec["passed"] = True
        except (ValueError, json.JSONDecodeError) as exc:
            rec["error_type"] = "LLMOutputParseError"
            rec["error"] = str(exc)[:300]
            rec["raw_content"] = str(call.get("content") or "")[:2000]
    rec["elapsed_seconds"] = round(time.monotonic() - t0, 6)
    return rec


def converter(graph: Mapping[str, Any], plan: Any, log_record: Optional[Mapping[str, Any]], method: str) -> RunView:
    """runner.records_to_runs / run_methods 的 converter：llm_judge 结果记录 -> RunView。"""
    rec = dict(log_record or {"run_id": graph.get("run_id"), "case_id": graph.get("case_id")})
    return parsed_to_run_view(graph.get("llm_judge") or {}, rec, method=method or "llm_only",
                              source_extra={"adapter": "llm_judge.converter"})


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main(argv: Optional[Sequence[str]] = None, env: Optional[Mapping[str, str]] = None,
         transport: Optional[Transport] = None) -> int:
    ap = argparse.ArgumentParser(prog="python -m confidence_07a.eval.baselines.llm_judge",
                                 description="纯模型基线 llm_only（OpenAI 兼容端点；配置只来自环境变量）")
    ap.add_argument("--log", required=True, help="工业日志 JSON（utf-8）")
    ap.add_argument("--run-ids", help="逗号分隔的 run_id")
    ap.add_argument("--all", action="store_true", help="全部运行")
    ap.add_argument("--out", help="结果目录（06B 同形 {run_id}_{time_ns}.json）")
    ap.add_argument("--dry-run", action="store_true", help="只打印提示词，不调用模型")
    ap.add_argument("--timeout", type=float, default=120.0)
    ap.add_argument("--no-json-mode", action="store_true", help="不发送 response_format（部分端点不支持）")
    a = ap.parse_args(list(argv) if argv is not None else None)

    with open(a.log, "r", encoding="utf-8") as fh:
        data = json.load(fh)
    records = data if isinstance(data, list) else list(data.values())
    if a.run_ids:
        want = [x.strip() for x in a.run_ids.split(",") if x.strip()]
        records = [r for r in records if str(r.get("run_id")) in want]
    elif not a.all and not a.dry_run:
        print("请指定 --run-ids 或 --all", file=sys.stderr)
        return 2
    if not records:
        print("没有匹配的运行", file=sys.stderr)
        return 2

    if a.dry_run:
        for r in records[:1] if not a.run_ids else records:
            sys.stdout.write(render_prompt(r) + "\n")
        sys.stdout.write(f"\n[dry-run] 未调用模型；端点配置读取自环境变量 {ENV_BASE_URL}/{ENV_MODEL}（密钥 {ENV_API_KEY}）。\n")
        return 0

    try:
        cfg = LLMConfig.from_env(env, timeout=a.timeout, json_mode=not a.no_json_mode)
    except RuntimeError as exc:
        print(str(exc), file=sys.stderr)
        return 2
    if not a.out:
        print("非 dry-run 需要 --out", file=sys.stderr)
        return 2
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    tot = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    n_ok = 0
    for r in records:
        rec = judge_record(r, cfg, transport)
        n_ok += int(bool(rec.get("passed")))
        for k in tot:
            tot[k] += int(((rec.get("usage") or {}).get(k)) or 0)
        with open(out / f"{r.get('run_id')}_{time.time_ns()}.json", "w", encoding="utf-8") as fh:
            json.dump(rec, fh, ensure_ascii=False, indent=2)
            fh.write("\n")
    print(f"llm_only：{n_ok}/{len(records)} 成功；token 合计 {tot}；结果目录 {out}")
    return 0


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
    except Exception:
        pass
    sys.exit(main())
