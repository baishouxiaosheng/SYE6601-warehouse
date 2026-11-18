"""回答措辞强度分类（规则词典，确定性）。

四类（见规范 §3）：
- DEFINITE          确定断言（含审批/放行/可操作类结论）
- HEDGED            带推测/预计/可能等限定
- DECLARED_UNKNOWN  明确说无法确定/待确认/未查到/需人工
- SCOPED_PARTIAL    明确限定范围的部分结论（“当前页面未发现”“已查白班中班合计”）

判定顺序：policy.expression.precedence（默认 DECLARED_UNKNOWN > SCOPED_PARTIAL > HEDGED）
按词典命中；都未命中时用上游 assertion_strength 映射（upstream_strength_map），
仍无则 DEFINITE。approval 类结论在 approval_blocks_hedge=true 时只可能是
DEFINITE 或 DECLARED_UNKNOWN（“基本可以开机”仍视为确定放行）。
"""
from __future__ import annotations

from typing import Dict, List, Optional, Tuple

from .model import DECLARED_UNKNOWN, DEFINITE, EXPRESSIONS, HEDGED, SCOPED_PARTIAL

_LEXICON_KEYS = {
    DECLARED_UNKNOWN: "declared_unknown_lexicon",
    SCOPED_PARTIAL: "scoped_partial_lexicon",
    HEDGED: "hedge_lexicon",
}


def _expr_cfg(policy: Optional[dict]) -> dict:
    if policy is None:
        from .scorecard import load_policy

        policy = load_policy()
    return policy.get("expression") or {}


def lexicon_hits(text: str, words) -> List[str]:
    t = text or ""
    return [w for w in words if w and w in t]


def classify_expression(
    text: str, upstream_strength: Optional[str] = None, policy: Optional[dict] = None
) -> Tuple[str, List[str]]:
    """返回 (expression, 命中依据列表)。命中依据形如 ``"HEDGED:可能"``、``"upstream:inference"``。"""
    cfg = _expr_cfg(policy)
    precedence = cfg.get("precedence") or [DECLARED_UNKNOWN, SCOPED_PARTIAL, HEDGED]
    is_approval = upstream_strength == "approval"
    for expr in precedence:
        if expr not in _LEXICON_KEYS:
            continue
        if is_approval and cfg.get("approval_blocks_hedge", True) and expr in (HEDGED, SCOPED_PARTIAL):
            continue
        hits = lexicon_hits(text, cfg.get(_LEXICON_KEYS[expr]) or [])
        if hits:
            return expr, [f"{expr}:{h}" for h in hits]
    mapping: Dict[str, str] = cfg.get("upstream_strength_map") or {}
    if upstream_strength and mapping.get(upstream_strength) in EXPRESSIONS:
        return mapping[upstream_strength], [f"upstream:{upstream_strength}"]
    default = cfg.get("default") or DEFINITE
    return default, ["default"]
