"""预测结论 <-> gold 结论对齐（spec §5.1）。

步骤：
1. 显式映射：gold claim 填了 `pred_claim_id` 且该 ID 存在于预测运行中 -> 直接配对（score=1.0, method="explicit"）。
   ID 不存在时记 warning 并回落到相似度对齐。
2. 相似度：answer_span 与预测结论文本（ClaimView.text，及 raw.meta.source_span 若有）
   归一化后用 difflib.SequenceMatcher.ratio；较短串完整包含于较长串时给保底分 contain_floor。
3. 数值实体一致：双方都含数值且集合不相交 -> 不可对齐；部分相交 -> 分数乘 (0.5 + 0.5*Jaccard)。
4. 贪心一对一：候选按 (分数降序, gold 顺序, pred 顺序) 排序依次配对，阈值以下不配。
未配对 gold = 漏抽（missed_gold），未配对预测 = 多抽（extra_pred）。
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from dataclasses import dataclass, field
from typing import Any, Dict, Iterable, List, Optional, Sequence, Set, Tuple

from ..model import ClaimView
from .config import load_eval_config

_PUNCT_RE = re.compile(r"[\s，。、；：！？,.;:!?\"'“”‘’（）()\[\]【】《》<>~～·…—\-]+")
_NUM_RE = re.compile(r"\d+(?:\.\d+)?")


def normalize_text(text: Optional[str]) -> str:
    """NFKC（全角转半角）、小写、去千分位逗号、去空白与标点。"""
    if not text:
        return ""
    t = unicodedata.normalize("NFKC", str(text)).lower()
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    return _PUNCT_RE.sub("", t)


def extract_numbers(text: Optional[str]) -> Set[str]:
    """抽取数值实体（规范化为最简十进制字符串，21,500 -> 21500，2.50 -> 2.5）。"""
    if not text:
        return set()
    t = unicodedata.normalize("NFKC", str(text))
    t = re.sub(r"(?<=\d),(?=\d{3})", "", t)
    out: Set[str] = set()
    for m in _NUM_RE.findall(t):
        s = m
        if "." in s:
            s = s.rstrip("0").rstrip(".")
        s = s.lstrip("0") or "0"
        if s.startswith("."):
            s = "0" + s
        out.add(s)
    return out


def similarity(a: str, b: str, cfg: Optional[Dict[str, Any]] = None) -> float:
    """两段原文的字符相似度（0-1），含包含关系保底分。不考虑数值。"""
    acfg = (cfg or load_eval_config())["alignment"]
    na, nb = normalize_text(a), normalize_text(b)
    if not na or not nb:
        return 0.0
    ratio = difflib.SequenceMatcher(None, na, nb, autojunk=False).ratio()
    short, long_ = (na, nb) if len(na) <= len(nb) else (nb, na)
    if len(short) >= int(acfg.get("min_contain_len", 6)) and short in long_:
        ratio = max(ratio, float(acfg.get("contain_floor", 0.8)))
    return ratio


def numeric_agreement(a: str, b: str) -> Tuple[bool, float]:
    """返回 (是否相容, Jaccard)。任一方无数值 -> (True, 1.0)。"""
    na, nb = extract_numbers(a), extract_numbers(b)
    if not na or not nb:
        return True, 1.0
    inter = na & nb
    if not inter:
        return False, 0.0
    return True, len(inter) / len(na | nb)


def pair_score(gold_text: str, pred_texts: Iterable[str], cfg: Optional[Dict[str, Any]] = None) -> Tuple[float, str]:
    """gold 片段与一个预测结论（可能多份文本）的最终分数和原因。"""
    cfg = cfg or load_eval_config()
    must = bool(cfg["alignment"].get("numeric_must_overlap", True))
    best, why = 0.0, "no_text"
    for pt in pred_texts:
        if not pt:
            continue
        sim = similarity(gold_text, pt, cfg)
        ok, jac = numeric_agreement(gold_text, pt)
        if not ok and must:
            score, reason = 0.0, "numeric_mismatch"
        else:
            score = sim * (0.5 + 0.5 * jac) if jac < 1.0 else sim
            reason = "similarity"
        if score > best or why == "no_text":
            best, why = score, reason
    return best, why


def pred_texts_of(claim: ClaimView) -> List[str]:
    """预测结论可用于对齐的文本：text + 上游 meta.source_span（若适配器保留了 raw）。"""
    texts = [claim.text]
    raw = claim.raw or {}
    meta = raw.get("meta") if isinstance(raw.get("meta"), dict) else {}
    for t in (raw.get("source_span"), meta.get("source_span"), raw.get("content")):
        if isinstance(t, str) and t and t not in texts:
            texts.append(t)
    return texts


@dataclass
class AlignedPair:
    gold_claim_id: str
    pred_claim_id: str
    score: float
    method: str  # explicit / similarity


@dataclass
class Alignment:
    pairs: List[AlignedPair] = field(default_factory=list)
    missed_gold: List[str] = field(default_factory=list)
    extra_pred: List[str] = field(default_factory=list)
    warnings: List[str] = field(default_factory=list)
    # gold_claim_id -> 最高未达标分及原因（便于人工复核阈值）
    best_rejected: Dict[str, Dict[str, Any]] = field(default_factory=dict)

    def gold_to_pred(self) -> Dict[str, str]:
        return {p.gold_claim_id: p.pred_claim_id for p in self.pairs}

    def pred_to_gold(self) -> Dict[str, str]:
        return {p.pred_claim_id: p.gold_claim_id for p in self.pairs}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "pairs": [p.__dict__.copy() for p in self.pairs],
            "missed_gold": list(self.missed_gold),
            "extra_pred": list(self.extra_pred),
            "warnings": list(self.warnings),
            "best_rejected": dict(self.best_rejected),
        }


def align_claims(
    gold_claims: Sequence[Dict[str, Any]],
    pred_claims: Sequence[ClaimView],
    cfg: Optional[Dict[str, Any]] = None,
) -> Alignment:
    """对齐一个运行内的 gold 结论与预测结论（一对一）。"""
    cfg = cfg or load_eval_config()
    threshold = float(cfg["alignment"].get("threshold", 0.5))
    res = Alignment()
    pred_ids = [c.claim_id for c in pred_claims]
    pred_by_id = {c.claim_id: c for c in pred_claims}
    used_gold: Set[str] = set()
    used_pred: Set[str] = set()
    if len(set(pred_ids)) != len(pred_ids):
        res.warnings.append("预测结论 claim_id 有重复，按首次出现处理")

    # 1) 显式映射
    for g in gold_claims:
        gid = g.get("gold_claim_id")
        pid = g.get("pred_claim_id")
        if not pid:
            continue
        if pid not in pred_by_id:
            res.warnings.append(f"{gid}: pred_claim_id={pid} 不在预测结论中，回落到相似度对齐")
            continue
        if pid in used_pred:
            res.warnings.append(f"{gid}: pred_claim_id={pid} 已被其他 gold 结论显式占用，回落到相似度对齐")
            continue
        res.pairs.append(AlignedPair(gid, pid, 1.0, "explicit"))
        used_gold.add(gid)
        used_pred.add(pid)

    # 2) 相似度候选
    cands: List[Tuple[float, int, int, str, str]] = []
    for gi, g in enumerate(gold_claims):
        gid = g.get("gold_claim_id")
        if gid in used_gold:
            continue
        span = g.get("answer_span") or ""
        best = {"score": 0.0, "pred_claim_id": None, "reason": "no_candidate"}
        for pi, c in enumerate(pred_claims):
            if c.claim_id in used_pred:
                continue
            score, reason = pair_score(span, pred_texts_of(c), cfg)
            if score >= threshold:
                cands.append((score, gi, pi, gid, c.claim_id))
            if score > best["score"] or best["pred_claim_id"] is None:
                best = {"score": round(score, 4), "pred_claim_id": c.claim_id, "reason": reason}
        res.best_rejected[gid] = best
    cands.sort(key=lambda x: (-x[0], x[1], x[2]))
    for score, _gi, _pi, gid, pid in cands:
        if gid in used_gold or pid in used_pred:
            continue
        res.pairs.append(AlignedPair(gid, pid, round(score, 4), "similarity"))
        used_gold.add(gid)
        used_pred.add(pid)
        res.best_rejected.pop(gid, None)

    for g in gold_claims:
        gid = g.get("gold_claim_id")
        if gid not in used_gold:
            res.missed_gold.append(gid)
        else:
            res.best_rejected.pop(gid, None)
    seen: Set[str] = set()
    for pid in pred_ids:
        if pid not in used_pred and pid not in seen:
            res.extra_pred.append(pid)
        seen.add(pid)
    # 输出顺序按 gold 顺序，便于阅读
    order = {g.get("gold_claim_id"): i for i, g in enumerate(gold_claims)}
    res.pairs.sort(key=lambda p: order.get(p.gold_claim_id, 0))
    return res
