"""受控变体（spec §5.4，需求 §6“受控变体检查结果是否随证据变化”）。

从工业日志 JSON 生成五类变体，跑 01A rule 引擎，比较基线与变体的结论状态与成绩单：

| kind | 操作 | expected_effect |
|---|---|---|
| drop_evidence | 删除目标工具事件（trace 中整条移除） | 目标结论 must_not_be SUPPORT |
| unit_change   | 目标字段单位改写不换算（键名后缀 _kpa→_mpa / 单位字段 / 带单位字符串） | 目标结论 must_not_be SUPPORT |
| entity_swap   | 目标事件返回中的设备/产线等 ID 替换为另一个 ID（参数不变） | 目标结论 must_not_be SUPPORT |
| truncate_page | 目标事件返回中的列表截掉后半并置 has_more=true | 目标结论 must_not_be SUPPORT，或出现新增 INCOMPLETE_RESULT 缺口 |
| control_noop  | 重排整条记录 trace 中所有 JSON 键（逆序） | unchanged：结论状态与缺口类型均不变 |

目标选择（每个基线运行）：
- pred 来源（自洽敏感性）：基线预测中 SUPPORT 结论引用的工具事件（证据节点 event_id + check locator）；
- gold 来源（可选）：gold 结论 evidence_locators 中的事件；期望结论 = 与这些 gold 结论对齐、且基线为 SUPPORT 的预测结论。
期望只针对“基线为 SUPPORT”的结论（否则 must_not_be SUPPORT 恒真，不计入）。

结论匹配：基线与变体之间按归一化后的结论文本匹配（结论 ID 可能漂移）；同文本多条按出现顺序一一配对。

变体 run_id 保持不变（01A 校验要求 case_id-r1），以 variant_id 区分。
不调用模型；不读取 .env；运行 01A 引擎一律 load_settings({"mode": "rule"}, env={})（见 runner.run_engine_rule）。
"""
from __future__ import annotations

import copy
import json
import random
import re
from collections import Counter, OrderedDict
from dataclasses import asdict, dataclass, field
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple

from ..model import SUPPORT, RunView
from .align import align_claims, normalize_text

KINDS = ("drop_evidence", "unit_change", "entity_swap", "truncate_page", "control_noop")
NON_CONTROL_KINDS = KINDS[:-1]
VARIANTS_VERSION = "07a-variants-v1"

GRADE_RANK_V2 = {"INSUFFICIENT": 0, "QUALIFIED": 1, "SUFFICIENT_IN_SCOPE": 2}
GRADE_RANK_V1 = {"E": 0, "D": 1, "C": 2, "B": 3, "A": 4}

_TRACE_PATH_RE = re.compile(r"^trace\[([^\]]+)\]((?:\.[^.\[\]]+|\[\d+\])*)$")
_TOKEN_RE = re.compile(r"\.([^.\[\]]+)|\[(\d+)\]")
_ID_RE = re.compile(r"^[A-Z][A-Z0-9]*(?:-[A-Z0-9]+)+$")

# 键名单位后缀改写（不换算数值）：old -> new
UNIT_SUFFIX_SWAP = OrderedDict([
    ("kpa", "mpa"), ("mpa", "kpa"), ("pa", "kpa"), ("bar", "mpa"),
    ("c", "f"), ("degc", "degf"),
    ("kwh", "mwh"), ("mwh", "kwh"),
    ("tons", "kg"), ("ton", "kg"), ("t", "kg"), ("kg", "g"),
    ("m3", "l"), ("l", "m3"), ("mm", "m"), ("m", "mm"),
    ("hours", "minutes"), ("minutes", "hours"), ("seconds", "minutes"), ("s", "ms"), ("days", "hours"),
    ("ppm", "pct"), ("percent", "ppm"), ("pct", "ppm"), ("hz", "khz"),
])
# 单位字符串改写（单位字段 / “数值+单位”字符串）
UNIT_TEXT_SWAP = OrderedDict([
    ("kPa", "MPa"), ("MPa", "kPa"), ("℃", "℉"), ("°C", "°F"), ("kWh", "MWh"), ("MWh", "kWh"),
    ("吨", "千克"), ("kg", "g"), ("m³", "L"), ("m3", "L"), ("mm", "m"), ("小时", "分钟"), ("min", "h"), ("ppm", "%"),
])
_UNIT_STR_RE = re.compile(r"^\s*(-?[\d.,]+)\s*(" + "|".join(re.escape(u) for u in UNIT_TEXT_SWAP) + r")\s*$")


# ---------------------------------------------------------------------------
# 数据结构
# ---------------------------------------------------------------------------

@dataclass
class VariantSpec:
    variant_id: str
    base_run_id: str
    kind: str
    target_event_id: Optional[str]
    json_path: Optional[str]
    before: Any = None
    after: Any = None
    expected_effect: Dict[str, Any] = field(default_factory=dict)
    target_sources: List[str] = field(default_factory=list)      # pred / gold
    target_claim_ids_base: List[str] = field(default_factory=list)
    gold_claim_ids: List[str] = field(default_factory=list)
    note: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)

    @staticmethod
    def from_dict(d: Mapping[str, Any]) -> "VariantSpec":
        keys = VariantSpec.__dataclass_fields__.keys()  # type: ignore[attr-defined]
        return VariantSpec(**{k: d[k] for k in keys if k in d})


# ---------------------------------------------------------------------------
# JSON 路径工具
# ---------------------------------------------------------------------------

def parse_trace_path(path: Optional[str]) -> Optional[Tuple[str, List[Any]]]:
    """``trace[c2].result.shifts[0].x`` -> ("c2", ["result", "shifts", 0, "x"])；无法解析返回 None。"""
    if not path:
        return None
    m = _TRACE_PATH_RE.match(str(path).strip())
    if not m:
        return None
    toks: List[Any] = []
    for k, i in _TOKEN_RE.findall(m.group(2)):
        toks.append(int(i) if i else k)
    return m.group(1), toks


def format_trace_path(event_id: str, toks: Sequence[Any]) -> str:
    s = f"trace[{event_id}]"
    for t in toks:
        s += f"[{t}]" if isinstance(t, int) else f".{t}"
    return s


def _find_event(record: Mapping[str, Any], event_id: str) -> Optional[Dict[str, Any]]:
    for ev in record.get("trace") or []:
        if isinstance(ev, dict) and str(ev.get("id")) == str(event_id):
            return ev
    return None


def _get(obj: Any, toks: Sequence[Any]) -> Any:
    for t in toks:
        if isinstance(t, int) and isinstance(obj, list) and 0 <= t < len(obj):
            obj = obj[t]
        elif isinstance(t, str) and isinstance(obj, dict) and t in obj:
            obj = obj[t]
        else:
            return None
    return obj


def _walk(obj: Any, toks: Tuple[Any, ...] = ()) -> Iterable[Tuple[Tuple[Any, ...], Any]]:
    yield toks, obj
    if isinstance(obj, dict):
        for k, v in obj.items():
            yield from _walk(v, toks + (k,))
    elif isinstance(obj, list):
        for i, v in enumerate(obj):
            yield from _walk(v, toks + (i,))


def _is_prefix(a: Sequence[Any], b: Sequence[Any]) -> bool:
    return len(a) <= len(b) and list(b[: len(a)]) == list(a)


def _num_strings(v: Any) -> List[str]:
    if isinstance(v, bool) or not isinstance(v, (int, float)):
        return []
    out = {str(v)}
    if isinstance(v, float) and v.is_integer():
        out.add(str(int(v)))
    if abs(v) >= 1000 and float(v).is_integer():
        out.add(f"{int(v):,}")
    return sorted(out)


def _text_has_value(text: str, v: Any) -> bool:
    if not text:
        return False
    t = normalize_text(text)
    if isinstance(v, str):
        return bool(v) and normalize_text(v) in t
    for s in _num_strings(v):
        if re.search(r"(?<![\d.])" + re.escape(s.replace(",", "")) + r"(?![\d])", t):
            return True
    return False


# ---------------------------------------------------------------------------
# 引用关系
# ---------------------------------------------------------------------------

def claim_citations(run: RunView) -> Dict[str, Dict[str, set]]:
    """claim_id -> {"events": {event_id}, "paths": {json_path}}（证据节点 + check locator）。"""
    from ..adapters.egraph_v1 import event_id_from_locator

    checks = {c.check_id: c for c in run.checks}
    out: Dict[str, Dict[str, set]] = {}
    for c in run.claims:
        ev, paths = set(), set()
        for eid in c.evidence_ids:
            e = run.evidence.get(eid)
            if e is None:
                continue
            if e.event_id:
                ev.add(str(e.event_id))
            if e.json_path:
                paths.add(str(e.json_path))
        cids = set(c.check_ids) | {k.check_id for k in run.checks if c.claim_id in (k.affected_claims or [])}
        for cid in cids:
            k = checks.get(cid)
            if k is None or not k.locator:
                continue
            for loc in re.split(r"[;,；，\s]+", str(k.locator)):
                eid = event_id_from_locator(loc)
                if eid:
                    ev.add(eid)
                    paths.add(loc)
        out[c.claim_id] = {"events": ev, "paths": paths}
    return out


@dataclass
class _Target:
    event_id: str
    sources: set = field(default_factory=set)
    claim_ids: List[str] = field(default_factory=list)     # 基线 SUPPORT 结论
    paths: set = field(default_factory=set)                # 字段级引用（用于选字段）
    gold_claim_ids: List[str] = field(default_factory=list)


def select_targets(
    record: Mapping[str, Any],
    base_run: Optional[RunView],
    gold_run: Optional[Mapping[str, Any]] = None,
) -> Dict[str, _Target]:
    """返回 event_id -> 目标信息。只取 trace 中存在的 tool_call 事件。"""
    tool_events = {str(e.get("id")) for e in record.get("trace") or []
                   if isinstance(e, dict) and e.get("event", "tool_call") == "tool_call" and "result" in e}
    targets: Dict[str, _Target] = {}

    def tgt(eid: str) -> _Target:
        if eid not in targets:
            targets[eid] = _Target(eid)
        return targets[eid]

    supp = [c for c in (base_run.claims if base_run else []) if c.status == SUPPORT]
    cites = claim_citations(base_run) if base_run else {}
    for c in supp:
        for eid in sorted(cites.get(c.claim_id, {}).get("events", set())):
            if eid not in tool_events:
                continue
            t = tgt(eid)
            t.sources.add("pred")
            if c.claim_id not in t.claim_ids:
                t.claim_ids.append(c.claim_id)
            t.paths |= {p for p in cites[c.claim_id]["paths"] if (parse_trace_path(p) or ("",))[0] == eid}

    if gold_run and base_run:
        al = align_claims(gold_run.get("claims") or [], base_run.claims)
        g2p = {p.gold_claim_id: p.pred_claim_id for p in al.pairs}
        for gc in gold_run.get("claims") or []:
            for loc in gc.get("evidence_locators") or []:
                eid = str(loc.get("event_id") or (parse_trace_path(loc.get("json_path")) or ("",))[0] or "")
                if eid not in tool_events:
                    continue
                t = tgt(eid)
                t.sources.add("gold")
                if gc.get("gold_claim_id") not in t.gold_claim_ids:
                    t.gold_claim_ids.append(gc.get("gold_claim_id"))
                if loc.get("json_path"):
                    t.paths.add(str(loc["json_path"]))
                pid = g2p.get(gc.get("gold_claim_id"))
                pc = base_run.claim(pid) if pid else None
                if pc is not None and pc.status == SUPPORT and pid not in t.claim_ids:
                    t.claim_ids.append(pid)
    return dict(sorted(targets.items(), key=lambda kv: _event_order(record, kv[0])))


def _event_order(record: Mapping[str, Any], eid: str) -> int:
    for i, e in enumerate(record.get("trace") or []):
        if isinstance(e, dict) and str(e.get("id")) == eid:
            return i
    return 10 ** 6


# ---------------------------------------------------------------------------
# 各类变体的候选字段
# ---------------------------------------------------------------------------

def _swap_suffix(key: str) -> Optional[str]:
    low = key.lower()
    for old, new in UNIT_SUFFIX_SWAP.items():
        if low.endswith("_" + old):
            stem = key[: len(key) - len(old)]
            return stem + (new.upper() if key[-len(old):].isupper() else new)
    return None


def _unit_candidates(result: Any) -> List[Tuple[Tuple[Any, ...], str, Any, Any]]:
    """[(toks, mode, before, after)]，toks 为相对 event 的路径（以 "result" 开头）。"""
    out = []
    for toks, v in _walk(result, ("result",)):
        if not toks or len(toks) < 2:
            continue
        key = toks[-1]
        if isinstance(key, str) and isinstance(v, (int, float)) and not isinstance(v, bool):
            nk = _swap_suffix(key)
            if nk:
                out.append((toks, "rename_key", {"key": key, "value": v}, {"key": nk, "value": v}))
        if isinstance(key, str) and (key.lower() in ("unit", "units") or key.lower().endswith("_unit")) and isinstance(v, str):
            nv = UNIT_TEXT_SWAP.get(v.strip())
            if nv:
                out.append((toks, "unit_field", v, nv))
        if isinstance(v, str):
            m = _UNIT_STR_RE.match(v)
            if m:
                out.append((toks, "unit_text", v, v.replace(m.group(2), UNIT_TEXT_SWAP[m.group(2)], 1)))
    return out


def _swap_id(value: str, taken: set) -> str:
    m = re.search(r"(\d+)(?!.*\d)", value)
    if m:
        width = len(m.group(1))
        n = int(m.group(1))
        for step in (1, 2, 3, 7, 11):
            cand = value[: m.start()] + str(n + step).zfill(width) + value[m.end():]
            if cand not in taken:
                return cand
    return value + "-X"


# 设备/产线/装置类对象的键名（entity_swap 优先替换这些键上的 ID）
_ENTITY_KEY_RE = re.compile(
    r"(equipment|device|line|asset|machine|unit|tank|pump|compressor|crane|boiler|sensor|station|reactor|"
    r"furnace|kiln|meter|tag|chiller|vessel|motor|valve|conveyor|workshop|area|zone|plant)", re.I)


def _id_candidates(event: Mapping[str, Any]) -> List[Tuple[Tuple[Any, ...], str]]:
    out = []
    for toks, v in _walk(event.get("result"), ("result",)):
        if isinstance(v, str) and _ID_RE.match(v) and re.search(r"\d", v):
            out.append((toks, v))
    return out


def _entity_key(toks: Sequence[Any]) -> bool:
    for t in reversed(list(toks)):
        if isinstance(t, str):
            return bool(_ENTITY_KEY_RE.search(t))
    return False


def _list_candidates(result: Any) -> List[Tuple[Tuple[Any, ...], int]]:
    """可截断的“记录列表”：≥2 个元素且元素都是对象（如 batches / work_orders / shifts）。

    数值区间（如 normal_range_c=[60, 90]）、字符串标签列表不是分页结果，不作为候选。"""
    out = []
    for toks, v in _walk(result, ("result",)):
        if (isinstance(v, list) and len(v) >= 2 and len(toks) >= 2 and isinstance(toks[-1], str)
                and all(isinstance(x, dict) for x in v)):
            out.append((toks, len(v)))
    return out


def _all_strings(record: Mapping[str, Any]) -> set:
    return {v for _, v in _walk(record) if isinstance(v, str)}


def _rank_by_paths(cands: List[Tuple[Any, ...]], cited: Sequence[Tuple[Any, ...]]) -> List[int]:
    """候选下标按“被引用路径命中”优先排序（命中：互为前缀）。"""
    def score(i):
        toks = cands[i]
        hit = any(_is_prefix(c, toks) or _is_prefix(toks, c) for c in cited if len(c) > 1)
        exact = any(list(c) == list(toks) for c in cited)
        return (0 if exact else (1 if hit else 2), len(toks), i)
    return sorted(range(len(cands)), key=score)


# ---------------------------------------------------------------------------
# 生成与应用
# ---------------------------------------------------------------------------

def _vid(run_id: str, kind: str, event_id: Optional[str]) -> str:
    return f"{run_id}~{kind}~{event_id or 'all'}"


def _claims_text(base_run: RunView, ids: Sequence[str]) -> List[str]:
    out = []
    for cid in ids:
        c = base_run.claim(cid)
        if c is not None:
            out.append(c.text)
    return out


def generate_variants(
    record: Mapping[str, Any],
    base_run: Optional[RunView],
    gold_run: Optional[Mapping[str, Any]] = None,
    kinds: Optional[Sequence[str]] = None,
) -> List[VariantSpec]:
    """为一个基线运行生成变体规格（不修改 record）。"""
    kinds = list(kinds or KINDS)
    bad = [k for k in kinds if k not in KINDS]
    if bad:
        raise ValueError(f"未知变体类型：{bad}")
    rid = str(record.get("run_id"))
    specs: List[VariantSpec] = []
    targets = select_targets(record, base_run, gold_run)
    for eid, t in targets.items():
        ev = _find_event(record, eid)
        if ev is None:
            continue
        cited = [tuple(p[1]) for p in (parse_trace_path(x) for x in t.paths) if p]
        claim_ids = list(t.claim_ids)
        if not claim_ids:
            continue  # 没有基线 SUPPORT 结论可检验
        texts = _claims_text(base_run, claim_ids)
        common = dict(base_run_id=rid, target_event_id=eid, target_sources=sorted(t.sources),
                      gold_claim_ids=list(t.gold_claim_ids))

        if "drop_evidence" in kinds:
            specs.append(VariantSpec(
                variant_id=_vid(rid, "drop_evidence", eid), kind="drop_evidence",
                json_path=f"trace[{eid}]", before={"tool": ev.get("tool"), "event": ev.get("event")}, after=None,
                expected_effect={"claims": texts, "must_not_be": SUPPORT, "match": "all"},
                target_claim_ids_base=claim_ids, **common))

        if "unit_change" in kinds:
            cands = _unit_candidates(ev.get("result"))
            if cands:
                order = _rank_by_paths([c[0] for c in cands], cited)
                chosen = None
                for i in order:
                    toks, mode, before, after = cands[i]
                    val = before["value"] if isinstance(before, dict) else before
                    hit_ids = [cid for cid in claim_ids
                               if any(list(c) == list(toks) for c in cited)
                               and _text_has_value(base_run.claim(cid).text, val if not isinstance(val, str) else re.sub(r"[^\d.,-]", "", val))]
                    if not hit_ids:
                        hit_ids = [cid for cid in claim_ids
                                   if _text_has_value(base_run.claim(cid).text, val if not isinstance(val, str) else re.sub(r"[^\d.,-]", "", val))]
                    if hit_ids:
                        chosen = (toks, mode, before, after, hit_ids)
                        break
                if chosen:
                    toks, mode, before, after, hit_ids = chosen
                    specs.append(VariantSpec(
                        variant_id=_vid(rid, "unit_change", eid), kind="unit_change",
                        json_path=format_trace_path(eid, toks), before=before, after=after,
                        expected_effect={"claims": _claims_text(base_run, hit_ids), "must_not_be": SUPPORT, "match": "all"},
                        target_claim_ids_base=hit_ids, note=mode, **common))

        if "entity_swap" in kinds:
            answer = record.get("ai_answer") or ""
            args_text = json.dumps(ev.get("arguments") or {}, ensure_ascii=False)
            # 只替换“被查询的对象”（出现在工具参数中）或“回答中提到的对象”的 ID，否则结论未必依赖它
            cands = [c for c in _id_candidates(ev) if c[1] in args_text or c[1] in answer]
            if cands:
                def pri(i):
                    toks, v = cands[i]
                    return (0 if _entity_key(toks) else 1, 0 if v in args_text else 1, 0 if v in answer else 1, len(toks), i)
                toks, v = cands[sorted(range(len(cands)), key=pri)[0]]
                nv = _swap_id(v, _all_strings(record))
                # 结论原文提到该 ID 的，只以这些结论为目标（期望最明确）；否则以引用该事件的全部 SUPPORT 结论为目标
                mention = [cid for cid in claim_ids if normalize_text(v) in normalize_text(base_run.claim(cid).text)]
                es_ids = mention or claim_ids
                specs.append(VariantSpec(
                    variant_id=_vid(rid, "entity_swap", eid), kind="entity_swap",
                    json_path=format_trace_path(eid, toks), before=v, after=nv,
                    expected_effect={"claims": _claims_text(base_run, es_ids), "must_not_be": SUPPORT, "match": "all"},
                    target_claim_ids_base=es_ids,
                    note=("替换该事件 result 中所有等于原 ID 的字符串；arguments 不变；目标="
                          + ("原文提到该 ID 的结论" if mention else "引用该事件的全部 SUPPORT 结论")), **common))

        if "truncate_page" in kinds:
            cands = _list_candidates(ev.get("result"))
            if cands:
                # 被引用路径命中者优先，其次最长列表
                def tpri(i):
                    tk = cands[i][0]
                    hit = any(_is_prefix(c, tk) or _is_prefix(tk, c) for c in cited if len(c) > 1)
                    return (0 if hit else 1, -cands[i][1], i)
                toks, n = cands[sorted(range(len(cands)), key=tpri)[0]]
                keep = max(1, n // 2)
                specs.append(VariantSpec(
                    variant_id=_vid(rid, "truncate_page", eid), kind="truncate_page",
                    json_path=format_trace_path(eid, toks), before={"len": n}, after={"len": keep, "has_more": True},
                    expected_effect={"claims": texts, "must_not_be": SUPPORT, "match": "all",
                                     "or_new_gap_type": "INCOMPLETE_RESULT"},
                    target_claim_ids_base=claim_ids, **common))

    if "control_noop" in kinds and base_run is not None:
        specs.append(VariantSpec(
            variant_id=_vid(rid, "control_noop", None), base_run_id=rid, kind="control_noop",
            target_event_id=None, json_path="trace[*]", before="原键序", after="所有对象键逆序",
            expected_effect={"unchanged": True}, target_sources=["control"],
            target_claim_ids_base=[c.claim_id for c in base_run.claims]))
    return specs


def _reverse_keys(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _reverse_keys(obj[k]) for k in reversed(list(obj.keys()))}
    if isinstance(obj, list):
        return [_reverse_keys(x) for x in obj]
    return obj


def apply_variant(record: Mapping[str, Any], spec: VariantSpec) -> Dict[str, Any]:
    """返回修改后的日志记录（深拷贝；run_id 不变）。"""
    rec = copy.deepcopy(dict(record))
    if spec.kind == "control_noop":
        rec["trace"] = [_reverse_keys(e) for e in rec.get("trace") or []]
        return rec
    eid = spec.target_event_id
    ev = _find_event(rec, eid) if eid else None
    if ev is None:
        raise ValueError(f"{spec.variant_id}: 找不到事件 {eid}")
    if spec.kind == "drop_evidence":
        rec["trace"] = [e for e in rec["trace"] if not (isinstance(e, dict) and str(e.get("id")) == str(eid))]
        return rec
    parsed = parse_trace_path(spec.json_path)
    if not parsed:
        raise ValueError(f"{spec.variant_id}: 无法解析 json_path {spec.json_path}")
    toks = parsed[1]
    parent = _get(ev, toks[:-1])
    last = toks[-1]
    if spec.kind == "unit_change":
        if spec.note == "rename_key":
            new_key = spec.after["key"]
            items = list(parent.items())
            parent.clear()
            for k, v in items:
                parent[new_key if k == last else k] = v
        else:
            parent[last] = spec.after
        return rec
    if spec.kind == "entity_swap":
        old, new = spec.before, spec.after

        def repl(o):
            if isinstance(o, dict):
                return {k: repl(v) for k, v in o.items()}
            if isinstance(o, list):
                return [repl(x) for x in o]
            return new if o == old else o

        ev["result"] = repl(ev.get("result"))
        return rec
    if spec.kind == "truncate_page":
        lst = parent[last]
        parent[last] = lst[: spec.after["len"]]
        parent["has_more"] = True
        return rec
    raise ValueError(f"未知变体类型 {spec.kind}")


# ---------------------------------------------------------------------------
# 比较
# ---------------------------------------------------------------------------

def match_claims_by_text(base: RunView, variant: Optional[RunView]) -> Dict[str, Optional[str]]:
    """基线 claim_id -> 变体 claim_id（按归一化文本，多重集按顺序配对）；变体中找不到为 None。"""
    pool: Dict[str, List[str]] = {}
    for c in (variant.claims if variant else []):
        pool.setdefault(normalize_text(c.text), []).append(c.claim_id)
    out: Dict[str, Optional[str]] = {}
    for c in base.claims:
        lst = pool.get(normalize_text(c.text))
        out[c.claim_id] = lst.pop(0) if lst else None
    return out


def _gap_types(run: Optional[RunView]) -> Counter:
    return Counter(g.gap_type for g in (run.gaps if run else []))


def _v1_support(v1: Optional[Mapping[str, Any]]) -> Optional[float]:
    if not v1:
        return None
    return ((v1.get("dimensions") or {}).get("evidence_support") or {}).get("score")


def compare_variant(
    spec: VariantSpec,
    base_run: RunView,
    var_run: Optional[RunView],
    base_cards: Optional[Mapping[str, Any]] = None,
    var_cards: Optional[Mapping[str, Any]] = None,
    error: Optional[str] = None,
) -> Dict[str, Any]:
    """单个变体的结果行。cards = {"v2": dict, "v1": dict}。"""
    row: Dict[str, Any] = {
        "variant_id": spec.variant_id, "base_run_id": spec.base_run_id, "kind": spec.kind,
        "target_event_id": spec.target_event_id, "json_path": spec.json_path,
        "target_sources": "+".join(spec.target_sources), "expected_effect": spec.expected_effect,
        "engine_ok": var_run is not None and not error, "error": error,
    }
    if var_run is None or error:
        row.update({"applicable": True, "effect_observed": None})
        return row
    mapping = match_claims_by_text(base_run, var_run)
    cites_b = claim_citations(base_run)
    cites_v = claim_citations(var_run)
    target_rows = []
    for cid in spec.target_claim_ids_base:
        bc = base_run.claim(cid)
        vid = mapping.get(cid)
        vc = var_run.claim(vid) if vid else None
        b_ev = sorted(cites_b.get(cid, {}).get("events", set()))
        v_ev = sorted(cites_v.get(vid, {}).get("events", set())) if vid else []
        other = [e for e in b_ev if e != spec.target_event_id]
        target_rows.append({"base_claim_id": cid, "variant_claim_id": vid, "text": bc.text if bc else None,
                            "base_status": bc.status if bc else None, "variant_status": vc.status if vc else None,
                            "base_cited_events": b_ev, "variant_cited_events": v_ev,
                            # 基线本就引用了被改事件以外的事件：变体仍为 SUPPORT 可能来自冗余证据，需人工判断
                            "possibly_redundant": bool(other) and (vc is not None and vc.status == SUPPORT)})
    status_changed = []
    for c in base_run.claims:
        vid = mapping.get(c.claim_id)
        vc = var_run.claim(vid) if vid else None
        if vc is None or vc.status != c.status:
            status_changed.append(c.claim_id)
    gt_b, gt_v = _gap_types(base_run), _gap_types(var_run)
    eff = spec.expected_effect or {}
    if eff.get("unchanged"):
        unchanged = (not status_changed and gt_b == gt_v and len(base_run.claims) == len(var_run.claims))
        row.update({"applicable": True, "effect_observed": unchanged,
                    "n_target_claims": 0, "n_target_changed": 0, "n_target_missing": 0})
    else:
        bad = eff.get("must_not_be", SUPPORT)
        changed = [t for t in target_rows if t["variant_status"] is not None and t["variant_status"] != bad]
        missing = [t for t in target_rows if t["variant_status"] is None]
        ok = bool(target_rows) and len(changed) == len(target_rows)
        new_gap = eff.get("or_new_gap_type")
        gap_hit = bool(new_gap) and gt_v.get(new_gap, 0) > gt_b.get(new_gap, 0)
        row.update({"applicable": bool(target_rows), "effect_observed": (ok or gap_hit) if target_rows else None,
                    "effect_by_claims": ok, "effect_by_new_gap": gap_hit if new_gap else None,
                    "n_target_claims": len(target_rows), "n_target_changed": len(changed),
                    "n_target_missing": len(missing)})
    row["target_claims"] = target_rows
    row["n_target_possibly_redundant"] = len([t for t in target_rows if t.get("possibly_redundant")])
    row["n_status_changed_any"] = len(status_changed)
    row["n_collateral_changed"] = len([c for c in status_changed if c not in spec.target_claim_ids_base])
    row["gap_types_base"] = dict(gt_b)
    row["gap_types_variant"] = dict(gt_v)
    # 成绩单层
    for ver, rank in (("v2", GRADE_RANK_V2), ("v1", GRADE_RANK_V1)):
        b = (base_cards or {}).get(ver)
        v = (var_cards or {}).get(ver)
        if not b or not v:
            continue
        if ver == "v2":
            sb, sv = b.get("support_score"), v.get("support_score")
            row["v2_alert_base"], row["v2_alert_variant"] = b.get("high_risk_alert"), v.get("high_risk_alert")
        else:
            sb, sv = _v1_support(b), _v1_support(v)
        gb, gv = b.get("grade"), v.get("grade")
        row[f"{ver}_grade_base"], row[f"{ver}_grade_variant"] = gb, gv
        row[f"{ver}_support_base"], row[f"{ver}_support_variant"] = sb, sv
        row[f"{ver}_support_drop"] = (sv < sb) if (sb is not None and sv is not None) else None
        row[f"{ver}_grade_drop"] = (rank.get(gv, -1) < rank.get(gb, -1)) if (gb in rank and gv in rank) else None
        row[f"{ver}_unchanged"] = (gb == gv and sb == sv)
    return row


# ---------------------------------------------------------------------------
# 汇总
# ---------------------------------------------------------------------------

def _ratio(num: int, den: int, reason: str) -> Dict[str, Any]:
    if not den:
        return {"numerator": num, "denominator": den, "value": None, "reason": reason, "ci95": None}
    return {"numerator": num, "denominator": den, "value": round(num / den, 6), "reason": None, "ci95": None}


def _cluster_ci(rows: List[Dict[str, Any]], num_f: Callable, den_f: Callable, seed: int, n_res: int = 1000):
    by_run: Dict[str, List[Dict[str, Any]]] = {}
    for r in rows:
        by_run.setdefault(r["base_run_id"], []).append(r)
    keys = sorted(by_run)
    if len(keys) < 2:
        return None
    rng = random.Random(seed)
    vals = []
    for _ in range(n_res):
        num = den = 0
        for _k in range(len(keys)):
            for r in by_run[keys[rng.randrange(len(keys))]]:
                num += num_f(r)
                den += den_f(r)
        if den:
            vals.append(num / den)
    if not vals:
        return None
    vals.sort()
    lo = vals[int(0.025 * (len(vals) - 1))]
    hi = vals[int(round(0.975 * (len(vals) - 1)))]
    return [round(lo, 6), round(hi, 6)]


def _metric(rows, num_f, den_f, reason, seed):
    num = sum(num_f(r) for r in rows)
    den = sum(den_f(r) for r in rows)
    m = _ratio(num, den, reason)
    if den:
        m["ci95"] = _cluster_ci(rows, num_f, den_f, seed)
    return m


def summarize_variant_rows(rows: List[Dict[str, Any]], seed: int = 0) -> Dict[str, Any]:
    """敏感性/稳定性（总体与按 kind），以及成绩单层敏感性。比例格式 {numerator, denominator, value, reason, ci95}。"""
    ok = [r for r in rows if r.get("engine_ok")]
    out: Dict[str, Any] = {
        "n_variants": len(rows),
        "n_engine_error": len(rows) - len(ok),
        "by_kind": {},
    }

    def block(rs: List[Dict[str, Any]], control: bool) -> Dict[str, Any]:
        app = [r for r in rs if r.get("applicable")]
        b: Dict[str, Any] = {"n": len(rs), "n_applicable": len(app)}
        if control:
            b["stability"] = _metric(app, lambda r: int(bool(r["effect_observed"])), lambda r: 1,
                                     "没有成功运行的 control 变体", seed)
            for ver in ("v2", "v1"):
                key = f"{ver}_unchanged"
                sub = [r for r in app if r.get(key) is not None]
                b[f"{ver}_scorecard_stability"] = _metric(sub, lambda r, k=key: int(bool(r[k])), lambda r: 1,
                                                          f"没有 {ver} 成绩单可比", seed)
            return b
        b["sensitivity"] = _metric(app, lambda r: int(bool(r["effect_observed"])), lambda r: 1,
                                   "没有可检验的变体（无基线 SUPPORT 目标结论或引擎失败）", seed)
        b["claim_sensitivity"] = _metric(app, lambda r: r.get("n_target_changed", 0), lambda r: r.get("n_target_claims", 0),
                                         "没有目标结论", seed)
        b["target_missing_rate"] = _metric(app, lambda r: r.get("n_target_missing", 0), lambda r: r.get("n_target_claims", 0),
                                           "没有目标结论", seed)
        b["collateral_rate"] = _metric(app, lambda r: int(r.get("n_collateral_changed", 0) > 0), lambda r: 1,
                                       "没有可检验的变体", seed)
        for ver in ("v2", "v1"):
            for what in ("support_drop", "grade_drop"):
                key = f"{ver}_{what}"
                sub = [r for r in app if r.get(key) is not None]
                b[f"{ver}_scorecard_{what}"] = _metric(sub, lambda r, k=key: int(bool(r[k])), lambda r: 1,
                                                        f"没有 {ver} 成绩单可比（或分数为 null）", seed)
            if ver == "v2":
                sub = [r for r in app if r.get("v2_support_drop") is not None or r.get("v2_grade_drop") is not None]
                b["v2_scorecard_any_drop"] = _metric(
                    sub, lambda r: int(bool(r.get("v2_support_drop")) or bool(r.get("v2_grade_drop"))
                                       or (r.get("v2_alert_variant") and not r.get("v2_alert_base"))), lambda r: 1,
                    "没有 v2 成绩单可比", seed)
        return b

    for k in KINDS:
        rs = [r for r in ok if r["kind"] == k]
        out["by_kind"][k] = block(rs, k == "control_noop")
        out["by_kind"][k]["n_engine_error"] = len([r for r in rows if r["kind"] == k and not r.get("engine_ok")])
    out["overall"] = block([r for r in ok if r["kind"] != "control_noop"], False)
    out["control"] = out["by_kind"]["control_noop"]
    by_src: Dict[str, Any] = {}
    for src in ("pred", "gold"):
        rs = [r for r in ok if r["kind"] != "control_noop" and src in str(r.get("target_sources", "")).split("+")]
        by_src[src] = block(rs, False)["sensitivity"]
    out["by_target_source"] = by_src
    return out


# ---------------------------------------------------------------------------
# 运行
# ---------------------------------------------------------------------------

def _score_cards(run: RunView, v1: Optional[Dict[str, Any]], policy: Optional[dict]) -> Dict[str, Any]:
    from ..scorecard import score_run

    return {"v2": score_run(run, policy), "v1": v1}


def run_variants_experiment(
    engine_path: str,
    logs: Sequence[Mapping[str, Any]],
    run_ids: Optional[Iterable[str]] = None,
    gold_runs: Optional[Sequence[Mapping[str, Any]]] = None,
    kinds: Optional[Sequence[str]] = None,
    policy: Optional[dict] = None,
    seed: int = 0,
    engine_fn: Optional[Callable[..., Dict[str, Dict[str, Any]]]] = None,
    converter: Optional[Callable[..., RunView]] = None,
) -> Dict[str, Any]:
    """生成并运行变体，返回 {specs, rows, summary, base_failures}。

    engine_fn(engine_path, [record]) -> {run_id: 06B 同形记录}，默认 runner.run_engine_rule（测试可注入）。
    """
    from .runner import records_to_runs, run_engine_rule

    engine_fn = engine_fn or run_engine_rule
    by_run = {str(r.get("run_id")): dict(r) for r in logs}
    wanted = [rid for rid in (list(run_ids) if run_ids is not None else list(by_run)) if rid in by_run]
    golds = {str(g.get("run_id")): g for g in (gold_runs or []) if not g.get("variant_id")}

    def run_one(rec: Mapping[str, Any], variant_id: Optional[str] = None):
        recs = engine_fn(engine_path, [rec])
        item = recs.get(str(rec.get("run_id")))
        if item is None or not (item.get("output") or {}).get("graph"):
            err = (item or {}).get("error_type") or "no_output"
            return None, None, f"{err}: {(item or {}).get('error') or ''}".strip()
        conv = records_to_runs({str(rec.get("run_id")): item}, "rule", {str(rec.get("run_id")): dict(rec)}, converter)
        run = conv["runs"][0]
        if variant_id:
            run.source["variant_id"] = variant_id
        return run, conv["v1_scorecards"].get(str(rec.get("run_id"))) or (item.get("output") or {}).get("scorecard"), None

    specs: List[VariantSpec] = []
    rows: List[Dict[str, Any]] = []
    base_failures: Dict[str, str] = {}
    for rid in wanted:
        rec = by_run[rid]
        base, base_v1, err = run_one(rec)
        if base is None:
            base_failures[rid] = err or "failed"
            continue
        base_cards = _score_cards(base, base_v1, policy)
        sp = generate_variants(rec, base, golds.get(rid), kinds)
        for s in sp:
            specs.append(s)
            try:
                vrec = apply_variant(rec, s)
            except Exception as exc:  # noqa: BLE001
                rows.append(compare_variant(s, base, None, error=f"apply:{type(exc).__name__}: {exc}"))
                continue
            vrun, v_v1, verr = run_one(vrec, s.variant_id)
            if vrun is None:
                rows.append(compare_variant(s, base, None, error=verr))
                continue
            vrun.source["variant_kind"] = s.kind
            rows.append(compare_variant(s, base, vrun, base_cards, _score_cards(vrun, v_v1, policy)))
    return {
        "variants_version": VARIANTS_VERSION,
        "engine_settings": {"mode": "rule", "env": {}},
        "n_base_runs": len(wanted),
        "specs": [s.to_dict() for s in specs],
        "rows": rows,
        "summary": summarize_variant_rows(rows, seed),
        "base_failures": base_failures,
    }


# ---------------------------------------------------------------------------
# 输出：experiment_metrics 行、Markdown、CSV
# ---------------------------------------------------------------------------

def _still_support(r: Mapping[str, Any]) -> int:
    return int(r.get("n_target_claims", 0)) - int(r.get("n_target_changed", 0)) - int(r.get("n_target_missing", 0))


def _present(r: Mapping[str, Any]) -> int:
    return int(r.get("n_target_claims", 0)) - int(r.get("n_target_missing", 0))


def injected_false_support(rows: Sequence[Mapping[str, Any]], seed: int = 0) -> Dict[str, Any]:
    """人工注入错误下的“错误结论被判为支持”比例：
    目标结论（基线 SUPPORT、其依据被变体破坏）在变体中仍为 SUPPORT 的数 / 目标结论在变体中仍能按文本找到的数。"""
    app = [dict(r) for r in rows if r.get("engine_ok") and r.get("applicable") and r.get("kind") != "control_noop"]
    return _metric(app, _still_support, _present, "没有可检验的目标结论", seed)


VARIANT_ROW_NOTE = (
    "受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），"
    "gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核"
)


def _strip_ratio(m: Mapping[str, Any]) -> Dict[str, Any]:
    return {k: m.get(k) for k in ("numerator", "denominator", "value", "reason", "ci95")}


def variant_metric_rows(result: Mapping[str, Any], method: str = "rule", seed: int = 0) -> List[Dict[str, Any]]:
    """把 run_variants_experiment 的结果转为 experiment_metrics.v1 的行（08B 三字段 + 扩展 metrics）。"""
    rows = list(result.get("rows") or [])
    summ = result.get("summary") or summarize_variant_rows(rows, seed)
    out: List[Dict[str, Any]] = []
    n_base = int(result.get("n_base_runs") or len({r.get("base_run_id") for r in rows}))

    groups = [(f"{method}@variants:all_non_control", [r for r in rows if r.get("kind") != "control_noop"], "overall")]
    groups += [(f"{method}@variant:{k}", [r for r in rows if r.get("kind") == k], k) for k in KINDS]
    for name, rs, key in groups:
        blk = summ["overall"] if key == "overall" else summ["by_kind"].get(key, {})
        metrics: Dict[str, Any] = {}
        if key == "control_noop":
            fs = None
            for mk in ("stability", "v2_scorecard_stability", "v1_scorecard_stability"):
                if mk in blk:
                    metrics[mk] = _strip_ratio(blk[mk])
            note = (f"对照组（control_noop：重排 JSON 键，期望结论与缺口不变）；n_variants={len(rs)}；"
                    f"稳定性={blk.get('stability', {}).get('value')}；三项 08B 指标不适用")
        else:
            ifs = injected_false_support(rs, seed)
            fs = ifs["value"]
            metrics["injected_false_support"] = _strip_ratio(ifs)
            for mk in ("sensitivity", "claim_sensitivity", "target_missing_rate", "collateral_rate",
                       "v2_scorecard_support_drop", "v2_scorecard_grade_drop", "v2_scorecard_any_drop",
                       "v1_scorecard_support_drop", "v1_scorecard_grade_drop"):
                if mk in blk:
                    metrics[mk] = _strip_ratio(blk[mk])
            sens = blk.get("sensitivity") or {}
            note = (f"{VARIANT_ROW_NOTE}；n_variants={len(rs)}（基线运行 {n_base}）；"
                    f"敏感性={sens.get('value')}（{sens.get('numerator')}/{sens.get('denominator')}）")
        out.append({
            "method": name,
            "false_support": fs,
            "gap_locate": None,
            "insufficient_as_err": None,
            "note": note,
            "n_runs": n_base,
            "metrics": metrics,
            "variant_kind": key,
            "n_variants": len(rs),
            "n_engine_error": len([r for r in rs if not r.get("engine_ok")]),
        })
    return out


VARIANT_CSV_FIELDS = [
    "variant_id", "base_run_id", "kind", "target_event_id", "json_path", "target_sources", "engine_ok", "error",
    "applicable", "effect_observed", "effect_by_claims", "effect_by_new_gap", "n_target_claims", "n_target_changed",
    "n_target_missing", "n_target_possibly_redundant", "n_status_changed_any", "n_collateral_changed", "target_transitions",
    "v2_grade_base", "v2_grade_variant", "v2_support_base", "v2_support_variant", "v2_alert_base", "v2_alert_variant",
    "v1_grade_base", "v1_grade_variant", "v1_support_base", "v1_support_variant", "expected_effect",
]


def variant_csv_rows(rows: Sequence[Mapping[str, Any]]) -> List[Dict[str, Any]]:
    out = []
    for r in rows:
        d = dict(r)
        d["target_transitions"] = "; ".join(
            f"{t.get('base_claim_id')}:{t.get('base_status')}->{t.get('variant_status') or 'MISSING'}"
            for t in r.get("target_claims") or [])
        d["expected_effect"] = json.dumps({k: v for k, v in (r.get("expected_effect") or {}).items() if k != "claims"},
                                          ensure_ascii=False)
        out.append(d)
    return out


def _fmt_ratio(m: Optional[Mapping[str, Any]]) -> str:
    if not m:
        return "—"
    if m.get("value") is None:
        return f"null（{m.get('numerator')}/{m.get('denominator')}）"
    ci = m.get("ci95")
    cis = f" [{ci[0]:.2f}, {ci[1]:.2f}]" if ci else ""
    return f"{m['value']:.3f}{cis}（{m['numerator']}/{m['denominator']}）"


def render_variants_md(result: Mapping[str, Any], title: str = "受控变体结果", max_examples: int = 15) -> str:
    """变体汇总的 Markdown 片段（供 report.md 与 variants.md 使用）。"""
    s = result.get("summary") or {}
    rows = list(result.get("rows") or [])
    L = [f"## {title}", "",
         f"- 变体版本：{result.get('variants_version')}；引擎设置：{json.dumps(result.get('engine_settings'), ensure_ascii=False)}；"
         f"基线运行 {result.get('n_base_runs')} 条，变体 {s.get('n_variants')} 个，引擎失败 {s.get('n_engine_error')} 个；"
         f"基线失败 {len(result.get('base_failures') or {})} 个。",
         "- 敏感性 = 期望变化发生的变体数 / 可检验变体数（目标 = 基线为 SUPPORT 且引用了被改事件的结论；期望 = 不再是 SUPPORT，"
         "truncate_page 另可由新增 INCOMPLETE_RESULT 缺口满足）。稳定性 = control 变体结论状态、缺口类型均不变的比例。",
         "- 注入 FSR = 目标结论在变体中仍为 SUPPORT 的比例（结论级）。CI 为按基线运行聚类的 bootstrap。",
         "- 结论按归一化文本在基线与变体之间匹配；变体中找不到同文本结论记为“缺失”，不计入注入 FSR 分母。",
         "",
         "| kind | 变体数 | 可检验 | 敏感性（变体级） | 结论级敏感性 | 注入 FSR | 连带变化率 | v2 成绩单下降（分数/等级/新告警任一） | v1 支持分下降 |",
         "|---|---|---|---|---|---|---|---|---|"]
    for k in NON_CONTROL_KINDS:
        b = (s.get("by_kind") or {}).get(k) or {}
        rs = [r for r in rows if r.get("kind") == k]
        L.append(f"| {k} | {b.get('n', 0)} | {b.get('n_applicable', 0)} | {_fmt_ratio(b.get('sensitivity'))} | "
                 f"{_fmt_ratio(b.get('claim_sensitivity'))} | {_fmt_ratio(injected_false_support(rs))} | "
                 f"{_fmt_ratio(b.get('collateral_rate'))} | {_fmt_ratio(b.get('v2_scorecard_any_drop'))} | "
                 f"{_fmt_ratio(b.get('v1_scorecard_support_drop'))} |")
    ov = s.get("overall") or {}
    L.append(f"| **全部非对照** | {ov.get('n', 0)} | {ov.get('n_applicable', 0)} | {_fmt_ratio(ov.get('sensitivity'))} | "
             f"{_fmt_ratio(ov.get('claim_sensitivity'))} | {_fmt_ratio(injected_false_support(rows))} | "
             f"{_fmt_ratio(ov.get('collateral_rate'))} | {_fmt_ratio(ov.get('v2_scorecard_any_drop'))} | "
             f"{_fmt_ratio(ov.get('v1_scorecard_support_drop'))} |")
    c = s.get("control") or {}
    L += ["", f"对照组 control_noop：n={c.get('n', 0)}；结论/缺口稳定性 {_fmt_ratio(c.get('stability'))}；"
              f"v2 成绩单稳定性 {_fmt_ratio(c.get('v2_scorecard_stability'))}；v1 成绩单稳定性 {_fmt_ratio(c.get('v1_scorecard_stability'))}。", ""]
    bts = s.get("by_target_source") or {}
    if bts:
        L.append("按目标来源的敏感性：" + "；".join(f"{k}：{_fmt_ratio(v)}" for k, v in bts.items())
                 + "（pred = 基线 SUPPORT 结论引用的事件；gold = gold 证据定位中的事件，两者可重叠）。")
        L.append("")
    miss = [r for r in rows if r.get("engine_ok") and r.get("applicable") and r.get("kind") != "control_noop"
            and r.get("effect_observed") is False]
    if miss:
        red = [r for r in miss if r.get("n_target_possibly_redundant")]
        by_k = Counter(r["kind"] for r in miss)
        L.append(f"期望变化未发生的 {len(miss)} 个变体按类型：" + "，".join(f"{k} {n}" for k, n in sorted(by_k.items()))
                 + f"；其中 {len(red)} 个的目标结论在基线中还引用了被改事件以外的事件（可能是冗余证据，"
                   "不一定是上游错误，需人工复核；见 variant_rows.csv 的 n_target_possibly_redundant）。")
        L.append("")
        L += [f"### 期望变化未发生的变体（共 {len(miss)} 个，列前 {min(max_examples, len(miss))} 个）", "",
              "| variant_id | json_path | 改动 | 目标结论迁移 |", "|---|---|---|---|"]
        spec_by = {sp.get("variant_id"): sp for sp in result.get("specs") or []}
        for r in miss[:max_examples]:
            sp = spec_by.get(r["variant_id"], {})
            chg = f"{json.dumps(sp.get('before'), ensure_ascii=False)} → {json.dumps(sp.get('after'), ensure_ascii=False)}"
            tr = "; ".join(f"{t.get('base_claim_id')} {t.get('base_status')}→{t.get('variant_status') or '缺失'}"
                           for t in r.get("target_claims") or [])
            L.append(f"| {r['variant_id']} | `{r.get('json_path')}` | {chg.replace('|', '/')[:120]} | {tr} |")
        L.append("")
    return "\n".join(L)
