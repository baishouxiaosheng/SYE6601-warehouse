"""离线评测指标（spec §5.2）。

入口：evaluate(pred_runs, gold_runs, method, scorecards=None, seed=0) -> dict

设计要点：
- 先对每个 gold 运行计算一组“可加计数”（Counter），所有比例指标都由计数之和算出；
  因此按运行聚类的 bootstrap 只需对运行重抽样后重新求和，所有指标共用同一组重抽样索引（可复现）。
- 每个比例输出 {numerator, denominator, value, reason, ci95}；分母为 0 时 value=null 并给 reason，不输出 0。
- 结论级指标（FSR/IAE/混淆矩阵）只在“已对齐”的 gold 结论上计算；未对齐的 gold 结论计入 excluded_unaligned
  并由抽取覆盖率单独反映（避免“少抽结论即可降低 FSR”的投机需要同时看覆盖率）。
- 分数含义：基于现有日志的证据审核结果，不是正确概率；校准表仅描述性。
"""
from __future__ import annotations

import datetime as _dt
import json
import math
import random
import statistics
import unicodedata
from collections import Counter
from typing import Any, Dict, List, Mapping, Optional, Sequence, Tuple

from ..model import (
    ASSERTING_EXPRESSIONS,
    MISSING_RULE,
    REFUTE,
    STATUSES,
    SUPPORT,
    UNKNOWN,
    CONFLICT,
    ActionView,
    GapView,
    RunView,
)
from .align import align_claims
from .config import load_eval_config
from .gold import gold_key, gold_runs as _gold_runs

EVAL_VERSION = "07a-eval-v1"
SCORE_SEMANTICS = "分数与指标基于现有日志的证据审核结果，不是正确概率；校准表仅为描述性统计。"
CAVEATS = [
    "试点 gold 由 AI 起草、尚未经人工复核（review_status=DRAFT 时），只能用于检验流水线，不能作为结论。",
    "样本量小（n 见各指标分母），置信区间很宽，不支持方法间显著性结论。",
    "所有分数不是正确概率；校准表与 ECE 仅描述性。",
]

BROAD_ERR = (REFUTE, UNKNOWN, MISSING_RULE, CONFLICT)
INSUFFICIENT = (UNKNOWN, MISSING_RULE)

# 指标字典：名称 -> 中文定义（报告与文档共用）
METRIC_DEFS: Dict[str, str] = {
    "false_support_strict": "FSR（严格）= #(gold=REFUTE ∧ pred=SUPPORT) / #(gold=REFUTE)，仅已对齐结论",
    "false_support_broad": "FSR（广义）= #(gold∈{REFUTE,UNKNOWN,MISSING_RULE,CONFLICT} ∧ pred=SUPPORT) / #(gold∈该集合)，仅已对齐结论",
    "insufficient_as_err": "IAE = #(gold∈{UNKNOWN,MISSING_RULE} ∧ pred=REFUTE) / #(gold∈{UNKNOWN,MISSING_RULE})，仅已对齐结论",
    "gap_precision": "缺口定位精确率 = 命中缺口数 / 预测缺口数",
    "gap_recall": "缺口定位召回率 = 命中缺口数 / gold 缺口数",
    "gap_f1": "缺口定位 F1 = 2×命中 / (预测缺口数 + gold 缺口数)",
    "requery_param_value_hit": "补查参数定位（键+值）= 在相关动作中键存在且值一致的关键参数数 / gold 关键参数总数",
    "requery_param_key_hit": "补查参数定位（仅键）= 在相关动作中出现的关键参数键数 / gold 关键参数总数",
    "requery_action_exists": "动作存在率 = 有至少一个相关补查动作的 gold 缺口数 / 带 required_params 的 gold 缺口数",
    "status_accuracy": "五态准确率 = 混淆矩阵对角线 / 已对齐结论数",
    "status_macro_f1": "五态 macro-F1 = Σ各类F1 / 出现过的类别数（gold 或 pred 中出现）",
    "status_kappa": "Cohen's κ = (p_o − p_e) / (1 − p_e)",
    "extraction_coverage": "结论抽取覆盖率 = 已对齐 gold 结论数 / gold 结论数",
    "extraction_extra_rate": "多抽率 = 未对齐的预测结论数 / 预测结论数",
    "severe_recall": "严重问题召回 = #(gold 有 severe 结论 ∧ high_risk_alert) / #(gold 有 severe 结论的运行)",
    "severe_false_alarm": "严重问题误报率 = #(gold 无 severe ∧ high_risk_alert) / #(gold 无 severe 的运行)",
    "calibration_ece": "ECE = Σ_b |Σconf_b − Σcorrect_b| / N；样本=gold 断言类结论，conf=所在运行 support_score，correct=gold_status==SUPPORT",
}

_ZERO_REASON: Dict[str, str] = {
    "false_support_strict": "分母为0：已对齐结论中没有 gold=REFUTE",
    "false_support_broad": "分母为0：已对齐结论中没有 gold 非 SUPPORT",
    "insufficient_as_err": "分母为0：已对齐结论中没有 gold∈{UNKNOWN,MISSING_RULE}",
    "gap_precision": "分母为0：预测没有缺口",
    "gap_recall": "分母为0：gold 没有缺口",
    "gap_f1": "分母为0：预测与 gold 均无缺口",
    "requery_param_value_hit": "分母为0：gold 未标注 required_params",
    "requery_param_key_hit": "分母为0：gold 未标注 required_params",
    "requery_action_exists": "分母为0：没有带 required_params 的 gold 缺口",
    "status_accuracy": "分母为0：没有已对齐结论",
    "status_macro_f1": "分母为0：没有已对齐结论",
    "status_kappa": "分母为0：没有已对齐结论，或期望一致率 p_e=1（只出现单一类别）",
    "extraction_coverage": "分母为0：gold 没有结论",
    "extraction_extra_rate": "分母为0：预测没有结论",
    "severe_recall": "分母为0：有成绩单的运行中没有 gold severe 运行",
    "severe_false_alarm": "分母为0：有成绩单的运行中没有 gold 非 severe 运行",
    "calibration_ece": "分母为0：没有可用 support_score 的 gold 断言结论",
}


# ---------------------------------------------------------------------------
# 小工具
# ---------------------------------------------------------------------------

def make_ratio(num: float, den: float, reason_if_zero: str) -> Dict[str, Any]:
    """统一比例格式。分母为 0 -> value=None + reason。"""
    if not den or abs(den) < 1e-12:
        return {"numerator": num, "denominator": den, "value": None, "reason": reason_if_zero, "ci95": None}
    return {"numerator": num, "denominator": den, "value": round(num / den, 6), "reason": None, "ci95": None}


def _variant_info(run: Optional[RunView]) -> Tuple[Optional[str], Optional[str]]:
    """从 run.source 读取变体信息：variant_id / variant_kind，或 variant={variant_id, kind} / variant="<id>"。"""
    if run is None:
        return None, None
    src = run.source or {}
    vid = src.get("variant_id")
    kind = src.get("variant_kind")
    v = src.get("variant")
    if isinstance(v, dict):
        vid = vid or v.get("variant_id")
        kind = kind or v.get("kind")
    elif isinstance(v, str) and v:
        vid = vid or v
    return (str(vid) if vid else None), (str(kind) if kind else None)


def run_key(run: RunView) -> Tuple[str, Optional[str]]:
    return (run.run_id, _variant_info(run)[0])


def _key_str(key: Tuple[str, Optional[str]]) -> str:
    return key[0] if not key[1] else f"{key[0]}#{key[1]}"


def _lookup_scorecard(scorecards: Optional[Mapping[str, Dict[str, Any]]], key: Tuple[str, Optional[str]]) -> Optional[Dict[str, Any]]:
    """成绩单按 run_id 索引；变体用 "run_id#variant_id"。"""
    if not scorecards:
        return None
    if key[1]:
        return scorecards.get(_key_str(key))
    return scorecards.get(key[0])


def alert_of(sc: Optional[Mapping[str, Any]]) -> Tuple[Optional[bool], str]:
    """成绩单的高风险告警。v2: high_risk_alert；v1 基线回退：severity_flags 中存在 severity=HIGH。"""
    if not sc:
        return None, "no_scorecard"
    if "high_risk_alert" in sc:
        return bool(sc.get("high_risk_alert")), "high_risk_alert"
    flags = sc.get("severity_flags")
    if isinstance(flags, list):
        return any(isinstance(f, dict) and str(f.get("severity", "")).upper() == "HIGH" for f in flags), "v1_severity_flags_high"
    return None, "unavailable"


def support_score_of(sc: Optional[Mapping[str, Any]]) -> Tuple[Optional[float], str]:
    """成绩单的证据支持度：v2 support_score / dimensions.support.value；v1 dimensions.evidence_support.score。"""
    if not sc:
        return None, "no_scorecard"
    v = sc.get("support_score")
    if isinstance(v, (int, float)) and not isinstance(v, bool):
        return float(v), "support_score"
    dims = sc.get("dimensions") or {}
    sup = dims.get("support") if isinstance(dims, dict) else None
    if isinstance(sup, dict) and isinstance(sup.get("value"), (int, float)):
        return float(sup["value"]), "dimensions.support.value"
    ev = dims.get("evidence_support") if isinstance(dims, dict) else None
    if isinstance(ev, dict) and isinstance(ev.get("score"), (int, float)):
        return float(ev["score"]), "v1.dimensions.evidence_support.score"
    return None, "unavailable"


def _norm_scalar(v: Any) -> Any:
    """参数值归一化：数值 -> float；ISO 时间 -> UTC datetime；字符串 -> NFKC 小写去空白。"""
    if isinstance(v, bool):
        return v
    if isinstance(v, (int, float)):
        return float(v)
    if isinstance(v, str):
        s = unicodedata.normalize("NFKC", v).strip()
        try:
            return float(s.replace(",", ""))
        except ValueError:
            pass
        if len(s) >= 10 and s[4:5] == "-" and s[7:8] == "-":
            try:
                d = _dt.datetime.fromisoformat(s.replace("Z", "+00:00"))
                if d.tzinfo is not None:
                    return d.astimezone(_dt.timezone.utc).replace(tzinfo=None).isoformat()
                return d.isoformat()
            except ValueError:
                pass
        return "".join(s.lower().split())
    if isinstance(v, (list, tuple)):
        return json.dumps([_norm_scalar(x) for x in v], ensure_ascii=False, sort_keys=True)
    if isinstance(v, dict):
        return json.dumps({k: _norm_scalar(x) for k, x in v.items()}, ensure_ascii=False, sort_keys=True)
    return v


def values_equal(a: Any, b: Any) -> bool:
    return _norm_scalar(a) == _norm_scalar(b)


def _text_contains(hay: Any, needle: Any) -> bool:
    if hay is None or needle is None:
        return False
    h = hay if isinstance(hay, str) else json.dumps(hay, ensure_ascii=False)
    h = "".join(unicodedata.normalize("NFKC", h).lower().split())
    n = needle if isinstance(needle, str) else json.dumps(needle, ensure_ascii=False)
    n = "".join(unicodedata.normalize("NFKC", n).lower().split())
    return bool(n) and n in h


def type_compatible(a: str, b: str, cfg: Dict[str, Any]) -> bool:
    if a == b:
        return True
    for grp in cfg["gaps"].get("compatible_groups", []):
        if a in grp and b in grp:
            return True
    return False


# ---------------------------------------------------------------------------
# 缺口与补查参数
# ---------------------------------------------------------------------------

def match_gaps(
    gold_gaps: Sequence[Dict[str, Any]],
    pred_gaps: Sequence[GapView],
    g2p: Mapping[str, str],
    cfg: Dict[str, Any],
) -> List[Tuple[str, Optional[str]]]:
    """gold 缺口 -> 预测缺口 一对一贪心匹配。

    匹配条件：类型相容，且
      - gold 缺口有 affects_claims：其已对齐的预测结论集合与预测缺口 affected_claims
        有交集（claim_match=overlap）或相等（exact）；gold 结论都没对齐时无法匹配；
      - gold 缺口 affects_claims 为空：仅按类型匹配。
    同一 gold 缺口有多个候选时，优先类型完全相同、交集更大、预测顺序靠前者。
    """
    mode = cfg["gaps"].get("claim_match", "overlap")
    used: set = set()
    out: List[Tuple[str, Optional[str]]] = []
    for g in gold_gaps:
        affects = list(g.get("affects_claims") or [])
        g_aff = {g2p[c] for c in affects if c in g2p}
        best = None
        for pi, p in enumerate(pred_gaps):
            if pi in used or not type_compatible(g.get("gap_type"), p.gap_type, cfg):
                continue
            p_aff = set(p.affected_claims or [])
            if affects:
                if not g_aff:
                    continue
                inter = g_aff & p_aff
                if mode == "exact":
                    if g_aff != p_aff:
                        continue
                elif not inter:
                    continue
            else:
                inter = set()
            rank = (0 if p.gap_type == g.get("gap_type") else 1, -len(inter), pi)
            if best is None or rank < best[0]:
                best = (rank, pi)
        if best is None:
            out.append((g.get("gold_gap_id"), None))
        else:
            used.add(best[1])
            out.append((g.get("gold_gap_id"), pred_gaps[best[1]].gap_id))
    return out


def gold_param_keys(required_params: Optional[Mapping[str, Any]]) -> List[Tuple[str, str, Any]]:
    """把 gold.required_params 展开为关键参数列表 [(kind, key, gold_value)]。"""
    rp = required_params or {}
    keys: List[Tuple[str, str, Any]] = []
    if rp.get("tool"):
        keys.append(("tool", "tool", rp["tool"]))
    for k, v in (rp.get("args") or {}).items():
        keys.append(("arg", str(k), v))
    sf = rp.get("success_field")
    if isinstance(sf, str) and sf:
        keys.append(("success", sf, None))
    elif isinstance(sf, dict):
        for k, v in sf.items():
            keys.append(("success", str(k), v))
    return keys


def param_hit(
    kind: str, key: str, gold_value: Any, actions: Sequence[ActionView], value_anywhere: bool = False
) -> Tuple[bool, bool]:
    """返回 (key_hit, value_hit)。

    tool：相关动作的 tool 与 gold 相等（键、值同判）。
    arg：键出现在 known_arguments 或 pending_arguments -> key_hit；
         known_arguments[k] 与 gold 值相等，或 pending_arguments[k] 文本包含 gold 值 -> value_hit；
         gold 值为 null 表示只要求识别出该键，value_hit=key_hit。
    success：success_criterion 文本包含字段名 -> key_hit；同时包含 gold 值 -> value_hit。
    value_anywhere（arg）：键名不同但 gold 值（规范化后长度>=4）出现在相关动作任一 known/pending 值文本中，
         也算 key_hit 与 value_hit（上游常用中文键名，如 01A 的 pending_arguments{"查询窗口": "..."}）。
    """
    key_hit = value_hit = False
    for a in actions:
        if kind == "tool":
            if a.tool and values_equal(a.tool, gold_value):
                return True, True
            continue
        if kind == "arg":
            known = a.known_arguments or {}
            pending = a.pending_arguments or {}
            if key in known or key in pending:
                key_hit = True
                if gold_value is None:
                    value_hit = True
                elif key in known and values_equal(known[key], gold_value):
                    value_hit = True
                elif key in pending and (values_equal(pending[key], gold_value) or _text_contains(pending[key], gold_value)):
                    value_hit = True
            if value_anywhere and not value_hit and gold_value is not None:
                needle = gold_value if isinstance(gold_value, str) else json.dumps(gold_value, ensure_ascii=False)
                if len("".join(needle.split())) >= 4 and any(
                    _text_contains(v, gold_value) for v in list(known.values()) + list(pending.values())
                ):
                    key_hit = value_hit = True
        elif kind == "success":
            crit = a.success_criterion or ""
            if _text_contains(crit, key):
                key_hit = True
                if gold_value is None or _text_contains(crit, gold_value):
                    value_hit = True
    return key_hit, value_hit


# ---------------------------------------------------------------------------
# 逐运行计数
# ---------------------------------------------------------------------------

def _run_stats(
    g: Dict[str, Any],
    run: Optional[RunView],
    sc: Optional[Dict[str, Any]],
    has_scorecards: bool,
    method: str,
    cfg: Dict[str, Any],
) -> Tuple[Counter, List[Dict[str, Any]], Dict[str, Any], Dict[str, Any], List[str]]:
    c: Counter = Counter()
    warnings: List[str] = []
    key = gold_key(g)
    ks = _key_str(key)
    gclaims = [x for x in g.get("claims") or [] if isinstance(x, dict)]
    pclaims = list(run.claims) if run else []
    al = align_claims(gclaims, pclaims, cfg)
    warnings.extend(f"{ks}: {w}" for w in al.warnings)
    g2p = al.gold_to_pred()
    p2g = al.pred_to_gold()
    pred_by_id: Dict[str, Any] = {}
    for pc in pclaims:
        pred_by_id.setdefault(pc.claim_id, pc)
    score_by_gold = {p.gold_claim_id: (p.score, p.method) for p in al.pairs}

    c["cl.gold"] += len(gclaims)
    c["cl.pred"] += len(pclaims)
    c["cl.extra"] += len(al.extra_pred)

    rows: List[Dict[str, Any]] = []
    for gc in gclaims:
        gid = gc.get("gold_claim_id")
        gs = gc.get("gold_status")
        pid = g2p.get(gid)
        pc = pred_by_id.get(pid) if pid else None
        ps = pc.status if pc else None
        aligned = pc is not None and ps in STATUSES
        if pc is not None and ps not in STATUSES:
            warnings.append(f"{ks}: 预测结论 {pid} 状态 {ps!r} 不是五态之一，按未对齐处理")
        if aligned:
            c["cl.aligned"] += 1
            c[f"cm.{gs}.{ps}"] += 1
        for name, cond_gold, cond_pred in (
            ("fs_strict", gs == REFUTE, ps == SUPPORT),
            ("fs_broad", gs in BROAD_ERR, ps == SUPPORT),
            ("iae", gs in INSUFFICIENT, ps == REFUTE),
        ):
            if cond_gold:
                if aligned:
                    c[f"{name}.den"] += 1
                    c[f"{name}.num"] += int(bool(cond_pred))
                else:
                    c[f"{name}.excl"] += 1
        sc_val, _ = support_score_of(sc)
        rows.append({
            "method": method,
            "run_id": key[0],
            "variant_id": key[1],
            "gold_claim_id": gid,
            "pred_claim_id": pid if aligned else None,
            "align_method": score_by_gold.get(gid, (None, None))[1] if aligned else None,
            "align_score": score_by_gold.get(gid, (None, None))[0] if aligned else al.best_rejected.get(gid, {}).get("score"),
            "gold_status": gs,
            "pred_status": ps if aligned else None,
            "gold_expression": gc.get("expression"),
            "pred_expression": getattr(pc, "expression", None) if pc else None,
            "is_high_risk": bool(gc.get("is_high_risk")),
            "severe": bool(gc.get("severe")),
            "false_support": (gs in BROAD_ERR and ps == SUPPORT) if aligned else None,
            "insufficient_as_err": (gs in INSUFFICIENT and ps == REFUTE) if aligned else None,
            "answer_span": gc.get("answer_span"),
            "pred_text": pc.text if pc else None,
            "run_support_score": sc_val,
        })
    for pid in al.extra_pred:
        pc = pred_by_id.get(pid)
        rows.append({
            "method": method, "run_id": key[0], "variant_id": key[1],
            "gold_claim_id": None, "pred_claim_id": pid, "align_method": "extra_pred", "align_score": None,
            "gold_status": None, "pred_status": pc.status if pc else None,
            "gold_expression": None, "pred_expression": getattr(pc, "expression", None) if pc else None,
            "is_high_risk": None, "severe": None, "false_support": None, "insufficient_as_err": None,
            "answer_span": None, "pred_text": pc.text if pc else None, "run_support_score": None,
        })

    # 缺口定位
    ggaps = [x for x in g.get("gaps") or [] if isinstance(x, dict)]
    pgaps = list(run.gaps) if run else []
    gap_pairs = match_gaps(ggaps, pgaps, g2p, cfg)
    tp = sum(1 for _, p in gap_pairs if p)
    c["gap.tp"] += tp
    c["gap.gold"] += len(ggaps)
    c["gap.pred"] += len(pgaps)

    # 补查参数
    actions = list(run.actions) if run else []
    gap_match = dict(gap_pairs)
    par_tot = par_key = par_val = 0
    value_anywhere = bool(cfg.get("params", {}).get("match_value_anywhere", True))
    for gg in ggaps:
        keys = gold_param_keys(gg.get("required_params"))
        if not keys:
            continue
        g_aff = {g2p[x] for x in gg.get("affects_claims") or [] if x in g2p}
        pgid = gap_match.get(gg.get("gold_gap_id"))
        related = [a for a in actions if (pgid and pgid in (a.gap_ids or [])) or (g_aff & set(a.target_claims or []))]
        c["act.den"] += 1
        c["act.num"] += int(bool(related))
        for kind, k, v in keys:
            kh, vh = param_hit(kind, k, v, related, value_anywhere)
            par_tot += 1
            par_key += int(kh)
            par_val += int(vh)
    c["par.tot"] += par_tot
    c["par.key"] += par_key
    c["par.val"] += par_val

    # 运行级严重问题
    gold_severe = any(bool(x.get("severe")) for x in gclaims)
    alert, alert_how = alert_of(sc)
    if has_scorecards and alert is not None:
        if gold_severe:
            c["sev.pos"] += 1
            c["sev.tp"] += int(alert)
        else:
            c["sev.neg"] += 1
            c["sev.fp"] += int(alert)

    # 校准（gold 断言类结论，conf=运行 support_score）
    s, s_how = support_score_of(sc)
    nb = int(cfg["calibration"].get("n_bins", 5))
    if s is not None:
        s_clip = min(max(s, 0.0), 1.0)
        b = min(int(s_clip * nb), nb - 1)
        for gc in gclaims:
            if gc.get("expression") in ASSERTING_EXPRESSIONS:
                c[f"cal.{b}.n"] += 1
                c[f"cal.{b}.conf"] += s_clip
                c[f"cal.{b}.correct"] += int(gc.get("gold_status") == SUPPORT)

    src = run.source if run else {}
    elapsed = src.get("elapsed_seconds") if isinstance(src, dict) else None
    calls = None
    if isinstance(src, dict):
        for k in ("llm_call_count", "model_calls", "model_call_count"):
            if isinstance(src.get(k), (int, float)):
                calls = src.get(k)
                break
    vid, vkind = _variant_info(run)
    per_run = {
        "method": method,
        "run_id": key[0],
        "case_id": g.get("case_id"),
        "variant_id": key[1],
        "variant_kind": vkind,
        "stratum": "variant" if key[1] else "natural",
        "pred_available": run is not None,
        "gold_review_status": g.get("review_status"),
        "n_gold_claims": len(gclaims),
        "n_pred_claims": len(pclaims),
        "n_aligned": c["cl.aligned"],
        "n_missed_gold": len(gclaims) - c["cl.aligned"],
        "n_extra_pred": len(al.extra_pred),
        "n_gold_gaps": len(ggaps),
        "n_pred_gaps": len(pgaps),
        "gap_tp": tp,
        "param_total": par_tot,
        "param_value_hit": par_val,
        "param_key_hit": par_key,
        "gold_severe": gold_severe,
        "high_risk_alert": alert,
        "alert_source": alert_how,
        "grade": (sc or {}).get("grade"),
        "support_score": s,
        "support_score_source": s_how,
        "answer_has_error": (g.get("run_level") or {}).get("answer_has_error"),
        "answer_honest_about_limits": (g.get("run_level") or {}).get("answer_honest_about_limits"),
        "elapsed_seconds": elapsed,
        "model_calls": calls,
    }
    align_info = al.to_dict()
    align_info["gap_pairs"] = [{"gold_gap_id": a, "pred_gap_id": b} for a, b in gap_pairs]
    return c, rows, per_run, align_info, warnings


# ---------------------------------------------------------------------------
# 由计数求指标
# ---------------------------------------------------------------------------

def _confusion(c: Mapping[str, float]) -> List[List[int]]:
    return [[int(c.get(f"cm.{g}.{p}", 0)) for p in STATUSES] for g in STATUSES]


def _raw_metrics(c: Mapping[str, float], has_scorecards: bool, nb: int) -> Dict[str, Tuple[float, float]]:
    """返回 名称 -> (numerator, denominator)。"""
    m: Dict[str, Tuple[float, float]] = {}
    m["false_support_strict"] = (c.get("fs_strict.num", 0), c.get("fs_strict.den", 0))
    m["false_support_broad"] = (c.get("fs_broad.num", 0), c.get("fs_broad.den", 0))
    m["insufficient_as_err"] = (c.get("iae.num", 0), c.get("iae.den", 0))
    tp, gp, gg = c.get("gap.tp", 0), c.get("gap.pred", 0), c.get("gap.gold", 0)
    m["gap_precision"] = (tp, gp)
    m["gap_recall"] = (tp, gg)
    m["gap_f1"] = (2 * tp, gp + gg)
    m["requery_param_value_hit"] = (c.get("par.val", 0), c.get("par.tot", 0))
    m["requery_param_key_hit"] = (c.get("par.key", 0), c.get("par.tot", 0))
    m["requery_action_exists"] = (c.get("act.num", 0), c.get("act.den", 0))

    cm = _confusion(c)
    n = sum(sum(r) for r in cm)
    diag = sum(cm[i][i] for i in range(len(STATUSES)))
    m["status_accuracy"] = (diag, n)
    f1_sum, k = 0.0, 0
    for i in range(len(STATUSES)):
        g_cnt = sum(cm[i])
        p_cnt = sum(cm[r][i] for r in range(len(STATUSES)))
        if g_cnt == 0 and p_cnt == 0:
            continue
        k += 1
        t = cm[i][i]
        f1_sum += (2 * t / (g_cnt + p_cnt)) if (g_cnt + p_cnt) else 0.0
    m["status_macro_f1"] = (f1_sum, k)
    if n:
        po = diag / n
        pe = sum((sum(cm[i]) / n) * (sum(cm[r][i] for r in range(len(STATUSES))) / n) for i in range(len(STATUSES)))
        den = 1 - pe
        m["status_kappa"] = (po - pe, den if abs(den) > 1e-12 else 0)
    else:
        m["status_kappa"] = (0, 0)
    m["extraction_coverage"] = (c.get("cl.aligned", 0), c.get("cl.gold", 0))
    m["extraction_extra_rate"] = (c.get("cl.extra", 0), c.get("cl.pred", 0))
    m["severe_recall"] = (c.get("sev.tp", 0), c.get("sev.pos", 0))
    m["severe_false_alarm"] = (c.get("sev.fp", 0), c.get("sev.neg", 0))
    num = 0.0
    tot = 0
    for b in range(nb):
        nbn = c.get(f"cal.{b}.n", 0)
        if nbn:
            num += abs(c.get(f"cal.{b}.conf", 0) - c.get(f"cal.{b}.correct", 0))
            tot += nbn
    m["calibration_ece"] = (num, tot)
    return m


def _metrics_from_counter(c: Mapping[str, float], has_scorecards: bool, nb: int) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}
    for name, (num, den) in _raw_metrics(c, has_scorecards, nb).items():
        reason = _ZERO_REASON[name]
        if name in ("severe_recall", "severe_false_alarm", "calibration_ece") and not has_scorecards:
            reason = "未提供成绩单（scorecards=None），无法计算"
        r = make_ratio(_clean(num), _clean(den), reason)
        if r["value"] is not None:
            r["value"] = round(num / den, 6)  # 用未舍入的分子分母求值
        r["definition"] = METRIC_DEFS[name]
        out[name] = r
    for name, key in (("false_support_strict", "fs_strict"), ("false_support_broad", "fs_broad"), ("insufficient_as_err", "iae")):
        out[name]["excluded_unaligned"] = int(c.get(f"{key}.excl", 0))
    return out


def _clean(x: float) -> Any:
    if isinstance(x, float) and x.is_integer():
        return int(x)
    if isinstance(x, float):
        return round(x, 6)
    return x


def _quantile(sorted_vals: List[float], q: float) -> float:
    if len(sorted_vals) == 1:
        return sorted_vals[0]
    pos = q * (len(sorted_vals) - 1)
    lo = math.floor(pos)
    hi = min(lo + 1, len(sorted_vals) - 1)
    return sorted_vals[lo] + (sorted_vals[hi] - sorted_vals[lo]) * (pos - lo)


def bootstrap_ci(
    counters: Sequence[Mapping[str, float]],
    has_scorecards: bool,
    nb: int,
    n_resamples: int = 1000,
    seed: int = 0,
    ci: float = 0.95,
) -> Dict[str, Dict[str, Any]]:
    """按运行聚类的百分位 bootstrap。所有指标共用同一组重抽样索引。

    返回 名称 -> {ci95:[lo,hi]|None, valid_resamples}。分母为 0 的重抽样被丢弃。
    """
    n = len(counters)
    names = list(METRIC_DEFS)
    if n == 0 or n_resamples <= 0:
        return {k: {"ci95": None, "valid_resamples": 0} for k in names}
    keys = sorted({k for cc in counters for k in cc})
    vecs = [[float(cc.get(k, 0)) for k in keys] for cc in counters]
    rng = random.Random(seed)
    samples: Dict[str, List[float]] = {k: [] for k in names}
    for _ in range(n_resamples):
        tot = [0.0] * len(keys)
        for _j in range(n):
            v = vecs[rng.randrange(n)]
            for i, x in enumerate(v):
                if x:
                    tot[i] += x
        agg = dict(zip(keys, tot))
        for name, (num, den) in _raw_metrics(agg, has_scorecards, nb).items():
            if den and abs(den) > 1e-12:
                samples[name].append(num / den)
    alpha = (1 - ci) / 2
    out: Dict[str, Dict[str, Any]] = {}
    for name in names:
        vals = sorted(samples[name])
        if not vals:
            out[name] = {"ci95": None, "valid_resamples": 0}
        else:
            out[name] = {
                "ci95": [round(_quantile(vals, alpha), 6), round(_quantile(vals, 1 - alpha), 6)],
                "valid_resamples": len(vals),
            }
    return out


def _calibration_table(c: Mapping[str, float], nb: int) -> List[Dict[str, Any]]:
    rows = []
    for b in range(nb):
        n = int(c.get(f"cal.{b}.n", 0))
        rows.append({
            "bin": b,
            "range": [round(b / nb, 4), round((b + 1) / nb, 4)],
            "n_claims": n,
            "mean_support_score": round(c.get(f"cal.{b}.conf", 0) / n, 6) if n else None,
            "gold_support_rate": round(c.get(f"cal.{b}.correct", 0) / n, 6) if n else None,
        })
    return rows


def _summarize(counters: List[Counter], has_sc: bool, cfg: Dict[str, Any], seed: int) -> Dict[str, Any]:
    nb = int(cfg["calibration"].get("n_bins", 5))
    total: Counter = Counter()
    for cc in counters:
        total.update(cc)
    metrics = _metrics_from_counter(total, has_sc, nb)
    bs = bootstrap_ci(
        counters, has_sc, nb,
        n_resamples=int(cfg["bootstrap"].get("n_resamples", 1000)),
        seed=seed, ci=float(cfg["bootstrap"].get("ci", 0.95)),
    )
    for name, r in metrics.items():
        if r["value"] is not None:
            r["ci95"] = bs[name]["ci95"]
            r["ci_valid_resamples"] = bs[name]["valid_resamples"]
    return {"metrics": metrics, "total": total}


def _cost(per_run: List[Dict[str, Any]]) -> Dict[str, Any]:
    el = [float(r["elapsed_seconds"]) for r in per_run if isinstance(r.get("elapsed_seconds"), (int, float))]
    calls = [float(r["model_calls"]) for r in per_run if isinstance(r.get("model_calls"), (int, float))]
    return {
        "elapsed_seconds": {
            "n": len(el),
            "total": round(sum(el), 6) if el else None,
            "mean": round(statistics.mean(el), 6) if el else None,
            "median": round(statistics.median(el), 6) if el else None,
            "reason": None if el else "run.source 中没有 elapsed_seconds",
        },
        "model_calls": {
            "n": len(calls),
            "total": sum(calls) if calls else None,
            "reason": None if calls else "run.source 中没有模型调用次数（llm_call_count/model_calls）",
        },
    }


def _contingency(per_run: List[Dict[str, Any]], field_name: str) -> Dict[str, Dict[str, int]]:
    tab: Dict[str, Dict[str, int]] = {}
    for r in per_run:
        g = str(r.get("grade")) if r.get("grade") is not None else "NO_SCORECARD"
        v = r.get(field_name)
        col = "true" if v is True else ("false" if v is False else "na")
        tab.setdefault(g, {"true": 0, "false": 0, "na": 0})[col] += 1
    return tab


def evaluate(
    pred_runs: List[RunView],
    gold_runs: List[Dict[str, Any]],
    method: str,
    scorecards: Optional[Dict[str, Dict[str, Any]]] = None,
    seed: int = 0,
    config: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    """计算一个方法在 gold 运行集合上的全部指标（spec §5.2）。

    pred_runs：该方法的预测（RunView）；按 (run_id, source.variant_id) 与 gold 对应。
    gold_runs：gold.v1 运行列表（或整份 gold 文档）。
    scorecards：可选，run_id（变体为 "run_id#variant_id"）-> 成绩单 dict（v2 或 v1）；
                提供时才计算严重问题召回/误报、校准与等级列联表。
    seed：bootstrap 随机种子（结果可复现）。
    """
    cfg = load_eval_config(config)
    golds = _gold_runs(gold_runs)
    warnings: List[str] = []
    pred_index: Dict[Tuple[str, Optional[str]], RunView] = {}
    for r in pred_runs:
        k = run_key(r)
        if k in pred_index:
            warnings.append(f"{_key_str(k)}: 预测运行重复，保留第一条")
            continue
        pred_index[k] = r
    has_sc = scorecards is not None

    counters: List[Counter] = []
    strata_of: List[List[str]] = []
    per_claim: List[Dict[str, Any]] = []
    per_run: List[Dict[str, Any]] = []
    alignment: Dict[str, Any] = {}
    gold_keys = set()
    n_missing_pred = 0
    review_status = Counter()
    for g in golds:
        k = gold_key(g)
        gold_keys.add(k)
        review_status[str(g.get("review_status"))] += 1
        run = pred_index.get(k)
        if run is None:
            n_missing_pred += 1
            warnings.append(f"{_key_str(k)}: 该方法没有此运行的预测（处理失败或未运行），gold 结论全部计为漏抽")
        sc = _lookup_scorecard(scorecards, k)
        c, rows, prow, ainfo, w = _run_stats(g, run, sc, has_sc, method, cfg)
        warnings.extend(w)
        counters.append(c)
        per_claim.extend(rows)
        per_run.append(prow)
        alignment[_key_str(k)] = ainfo
        vkind = prow.get("variant_kind")
        st = ["variant"] if k[1] else ["natural"]
        if k[1]:
            st.append(f"variant:{vkind or 'unknown'}")
        strata_of.append(st)

    summary = _summarize(counters, has_sc, cfg, seed)
    total = summary["total"]
    nb = int(cfg["calibration"].get("n_bins", 5))

    strata: Dict[str, Any] = {}
    if any(k[1] for k in gold_keys):
        names = sorted({s for st in strata_of for s in st})
        for s in names:
            idx = [i for i, st in enumerate(strata_of) if s in st]
            sub = _summarize([counters[i] for i in idx], has_sc, cfg, seed)
            strata[s] = {"n_runs": len(idx), "metrics": sub["metrics"]}

    n_pred_unannotated = sum(1 for k in pred_index if k not in gold_keys)
    result = {
        "eval_version": EVAL_VERSION,
        "method": method,
        "seed": seed,
        "config": cfg,
        "score_semantics": SCORE_SEMANTICS,
        "caveats": list(CAVEATS),
        "n": {
            "gold_runs": len(golds),
            "gold_runs_reviewed": review_status.get("REVIEWED", 0),
            "gold_runs_draft": review_status.get("DRAFT", 0),
            "pred_runs_matched": len(golds) - n_missing_pred,
            "pred_runs_missing": n_missing_pred,
            "pred_runs_unannotated": n_pred_unannotated,
            "gold_claims": int(total.get("cl.gold", 0)),
            "pred_claims": int(total.get("cl.pred", 0)),
            "aligned_claims": int(total.get("cl.aligned", 0)),
            "gold_gaps": int(total.get("gap.gold", 0)),
            "pred_gaps": int(total.get("gap.pred", 0)),
            "scorecards_provided": has_sc,
        },
        "metrics": summary["metrics"],
        "bootstrap": {
            "method": "按运行聚类的百分位 bootstrap",
            "n_resamples": int(cfg["bootstrap"].get("n_resamples", 1000)),
            "seed": seed,
            "clusters": len(counters),
        },
        "confusion": {"labels": list(STATUSES), "rows": "gold", "cols": "pred", "matrix": _confusion(total)},
        "calibration": {
            "table": _calibration_table(total, nb) if has_sc else [],
            "ece": summary["metrics"]["calibration_ece"],
            "note": "样本小，仅描述性；support_score 不是正确概率。",
        },
        "run_level": {
            "grade_vs_answer_has_error": _contingency(per_run, "answer_has_error") if has_sc else {},
            "grade_vs_answer_honest_about_limits": _contingency(per_run, "answer_honest_about_limits") if has_sc else {},
        },
        "cost": _cost(per_run),
        "strata": strata,
        "strata_note": None if strata else "run.source 中没有变体信息，未分层（全部视为自然运行）",
        "per_claim": per_claim,
        "per_run": per_run,
        "alignment": alignment,
        "warnings": warnings,
    }
    return result
