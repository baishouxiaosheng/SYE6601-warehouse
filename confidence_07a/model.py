"""07A 归一化数据模型。

所有适配器（01A egraph v1、02B b_review、日后其他上游）都先转成 RunView，
评分（scorecard.py）与评测（eval/）只依赖本文件，不直接依赖上游 JSON 字段名。
上游字段改名时，只需改 adapters/ 下对应适配器。
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Dict, List, Optional

# 上游结论五态（沿用 01A egraph 枚举，不改名）
SUPPORT = "SUPPORT"
REFUTE = "REFUTE"
UNKNOWN = "UNKNOWN"
CONFLICT = "CONFLICT"
MISSING_RULE = "MISSING_RULE"
STATUSES = (SUPPORT, REFUTE, UNKNOWN, CONFLICT, MISSING_RULE)
STATUS_ZH = {
    SUPPORT: "已支持",
    REFUTE: "与证据矛盾",
    UNKNOWN: "证据不足",
    CONFLICT: "来源冲突",
    MISSING_RULE: "缺适用规则",
}
UNRESOLVED_STATUSES = (UNKNOWN, CONFLICT, MISSING_RULE)

# 回答措辞强度（07A 自行判定）
DEFINITE = "DEFINITE"
HEDGED = "HEDGED"
DECLARED_UNKNOWN = "DECLARED_UNKNOWN"
SCOPED_PARTIAL = "SCOPED_PARTIAL"
EXPRESSIONS = (DEFINITE, HEDGED, DECLARED_UNKNOWN, SCOPED_PARTIAL)
ASSERTING_EXPRESSIONS = (DEFINITE, HEDGED, SCOPED_PARTIAL)

# 缺口类型（沿用 01A）
GAP_TYPES = (
    "MISSING_EVIDENCE",
    "MISSING_RULE",
    "MISSING_DEPENDENCY",
    "INCOMPLETE_RESULT",
    "CONFLICT",
    "LIMITED_SCOPE",
)


@dataclass
class EvidenceRef:
    """一条可回溯到原始日志字段的证据。"""
    evidence_id: str                      # 上游证据节点 ID，如 MAT-001
    run_id: str
    event_id: Optional[str] = None        # trace 事件 ID，如 c1
    tool: Optional[str] = None
    arguments: Dict[str, Any] = field(default_factory=dict)
    json_path: Optional[str] = None       # 如 trace[c1].result.pressure_kpa
    excerpt: Optional[str] = None
    value: Any = None
    unit: Optional[str] = None
    has_edges: Optional[bool] = None      # 图中是否有边连到它（可追溯性）
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GoalView:
    goal_id: str
    text: str
    question_type: Optional[str] = None
    upstream_answered: Optional[bool] = None   # 上游给的，仅参考
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CheckView:
    check_id: str
    kind: Optional[str] = None
    status: Optional[str] = None          # satisfied / violated / unknown / not_applicable
    verdict: Optional[str] = None         # 五态之一
    category: Optional[str] = None
    affected_claims: List[str] = field(default_factory=list)
    evidence_ref: Optional[str] = None
    locator: Optional[str] = None
    expected: Any = None
    actual: Any = None
    detail: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ClaimView:
    claim_id: str
    text: str
    status: str                            # 五态之一（来自上游，不重判）
    upstream_strength: Optional[str] = None  # 01A assertion_strength: reading/assertion/inference/approval/negative_finding/recommendation
    expression: Optional[str] = None       # 07A 判定的措辞强度（适配器可留空，由 expression.py 补）
    related_goals: List[str] = field(default_factory=list)
    linkage_method: str = "upstream"       # upstream / lexical_fallback / none
    evidence_ids: List[str] = field(default_factory=list)   # 支持/反驳它的证据
    check_ids: List[str] = field(default_factory=list)
    gap_ids: List[str] = field(default_factory=list)
    action_ids: List[str] = field(default_factory=list)
    scope_limited: Optional[bool] = None
    value: Any = None
    unit: Optional[str] = None
    verdict_reason: Optional[str] = None
    review_status: Optional[str] = None    # proposed / verified / rejected / unresolved
    status_source: str = "01A"             # 状态来自谁：01A / 02B
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class GapView:
    gap_id: str
    gap_type: str
    affected_claims: List[str] = field(default_factory=list)
    criticality: Optional[str] = None      # HIGH / MEDIUM / LOW
    description: Optional[str] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ActionView:
    action_id: str
    action_type: str                       # recompute / refetch_page / requery / alt_source / rule_lookup / manual_confirm
    gap_ids: List[str] = field(default_factory=list)
    target_claims: List[str] = field(default_factory=list)
    tool: Optional[str] = None
    known_arguments: Dict[str, Any] = field(default_factory=dict)
    pending_arguments: Dict[str, Any] = field(default_factory=dict)
    success_criterion: Optional[str] = None
    executability: Optional[str] = None    # executable / needs_confirmation / manual
    priority: Optional[int] = None
    raw: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RunView:
    run_id: str
    case_id: str
    question: str
    answer_text: str
    goals: List[GoalView] = field(default_factory=list)
    claims: List[ClaimView] = field(default_factory=list)
    evidence: Dict[str, EvidenceRef] = field(default_factory=dict)
    checks: List[CheckView] = field(default_factory=list)
    gaps: List[GapView] = field(default_factory=list)
    actions: List[ActionView] = field(default_factory=list)
    scope: Dict[str, Any] = field(default_factory=dict)
    upstream_versions: Dict[str, Optional[str]] = field(default_factory=dict)
    source: Dict[str, Any] = field(default_factory=dict)      # {method, engine, adapter, files...}
    build_risks: Dict[str, Any] = field(default_factory=dict) # 适配器发现的建链风险原始计数
    notes: List[str] = field(default_factory=list)

    def claim(self, claim_id: str) -> Optional[ClaimView]:
        for c in self.claims:
            if c.claim_id == claim_id:
                return c
        return None

    def to_dict(self) -> Dict[str, Any]:
        return asdict(self)
