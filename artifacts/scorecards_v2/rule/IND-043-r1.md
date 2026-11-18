# 置信度成绩单 v2 · IND-043-r1

> 本成绩单的分数是“基于现有日志的证据审核结果”，不是回答正确的概率；未经独立标注数据校准前不得解读为正确率。等级只覆盖已建模条件，不能证明证据图完整或已发现全部适用规则。

- 问题：D线昨天的产量是多少？
- **等级：证据不足（INSUFFICIENT）**
- 严重问题告警（high_risk_alert）：否
- 综合分：不显示（存在阻断项或无可计算维度；计算值 0.25 仅供调试）
- 评分规则版本：2.1.0（PROVISIONAL，sha256 f6a12bb2d19e…）；上游：graph=IND-043-evidence-graph-v1 plan=IND-043-supplementary-plan-v1 answer_sha256=29cfe8b610b6ddcf

## 阻断项与严重问题
- 无严重问题。
- 阻断 B2 CLM-001「D线昨天（11月13日）的产量为4200件」：高风险主结论以确定措辞表述，但上游状态为证据不足/缺规则/冲突（措辞 DEFINITE，状态 UNKNOWN；高风险依据 ['gap_high:GAP-001', 'sole_goal_main_claim']）
- 阻断 B4 CLM-001「D线昨天（11月13日）的产量为4200件」：HIGH 关键度缺口影响了确定措辞的结论（HIGH 缺口 ['GAP-001']）

## 保留项
- Q6_OVERCLAIM [CLM-002] 确定措辞但证据未支持（非高风险、无 HIGH 缺口，未达阻断）：DEFINITE×UNKNOWN
- Q6_OVERCLAIM [CLM-003] 确定措辞但证据未支持（非高风险、无 HIGH 缺口，未达阻断）：DEFINITE×UNKNOWN
- Q6_OVERCLAIM [CLM-004] 确定措辞但证据未支持（非高风险、无 HIGH 缺口，未达阻断）：DEFINITE×UNKNOWN
- Q5_BUILD_RISK [运行级] 存在建链风险（见 build_risks）：claims_without_checks=3
- Q5_BUILD_RISK [运行级] 存在建链风险（见 build_risks）：orphan_evidence=2

## 三个维度（分子/分母）
| 维度 | 分子/分母 = 值 | 权重 | 分项 |
|---|---|---|---|
| 证据支持度 | 0/4 = 0.0000 | 0.5 | SUPPORT=0, REFUTE=0, UNKNOWN=4, CONFLICT=0, MISSING_RULE=0, excluded_declared_unknown=0 |
| 问题回应覆盖度 | 1/1 = 1.0000 | 0.25 | ADDRESSED_SUPPORTED=0, ADDRESSED_DECLARED_UNKNOWN=0, ADDRESSED_UNSUPPORTED=1, NOT_ADDRESSED=0, lexical_fallback_goals=0 |
| 不确定性表达准确性 | 0.0/4 = 0.0000 | 0.25 | 判定 {'OVERCLAIM': 4}；未检查默认UNKNOWN 3；仅已检查结论 0.0/1 = 0.0000 |

- 证据支持度口径：分母=措辞为 DEFINITE/HEDGED/SCOPED_PARTIAL 的结论数；分子=其中上游状态为 SUPPORT 的条数。UNKNOWN 不给半分。DECLARED_UNKNOWN 不计入。
- 问题回应覆盖度口径：分母=用户目标数；分子=有关联结论（DEFINITE/HEDGED/SCOPED_PARTIAL）或明确声明无法确定（DECLARED_UNKNOWN）的目标数。关联优先用上游 related_goals/covers_goals/边，退化为词面匹配时标 lexical_fallback。
- 不确定性表达准确性口径：对每条结论按 policy.expression_matrix 的 (措辞×状态) 查表得分，分母=全部结论。如实声明无法确定（DECLARED_UNKNOWN×UNKNOWN/MISSING_RULE/CONFLICT）得满分。breakdown.checked_only 仅供参考：排除了“未被任何 check 命中而默认 UNKNOWN”的结论。

## 逐结论
| 复核序 | 结论 | 原文 | 措辞 | 状态 | 不确定性判定 | 高风险 | 主要依据（事件/字段） | 缺失或冲突 | 目标 | 补证动作 |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | CLM-001 | D线昨天（11月13日）的产量为4200件 | 确定断言 | 证据不足（UNKNOWN，来源 01A） | OVERCLAIM（0.0） | 是：gap_high:GAP-001,sole_goal_main_claim | — | CHK-001(time_window_coverage:UNKNOWN); GAP-001(MISSING_EVIDENCE,HIGH) | GOAL-001 | ACT-001(requery/needs_confirmation) |
| 2 | CLM-002 | 其中白班1800件 | 确定断言 | 证据不足（UNKNOWN，来源 01A） | OVERCLAIM（0.0） | 否 | — | — | — | — |
| 3 | CLM-003 | 中班2400件 | 确定断言 | 证据不足（UNKNOWN，来源 01A） | OVERCLAIM（0.0） | 否 | — | — | — | — |
| 4 | CLM-004 | 生产运行正常 | 确定断言 | 证据不足（UNKNOWN，来源 01A） | OVERCLAIM（0.0） | 否 | — | — | — | — |

## 用户目标
- GOAL-001「D线昨天的产量是多少」：已回应但未获支持（ADDRESSED_UNSUPPORTED），关联 ['CLM-001']，关联方式 upstream

## 缺口
- GAP-001 MISSING_EVIDENCE / HIGH：目标时段存在未覆盖区间：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00；影响 ['CLM-001']

## 补证计划
共 1 个动作：可执行 0，需确认 1，需人工 0。
- ACT-001 requery（needs_confirmation，工具 未指定）→ 结论 ['CLM-001']；已知参数 {}；待确认 {'查询条件': '目标时段存在未覆盖区间：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00'}；成功判据：新返回字段能覆盖缺口所涉的对象/时段，且可定位到具体字段路径后复算出结论

## 建链风险与范围声明
- 回答中未映射到任何结论的句子：0 
- 无关联结论的目标：[]；词面兜底关联：0
- 无边证据节点：['MAT-001', 'MAT-002']
- 没有任何 check 命中的结论：['CLM-002', 'CLM-003', 'CLM-004']（其中默认 UNKNOWN：['CLM-002', 'CLM-003', 'CLM-004']）
- 审核状态：{'proposed_nodes': 5, 'unresolved_nodes': 0, 'proposed_edges': 0, 'unresolved_edges': 0, 'proposed_claims': 4}
- missing_condition 不是节点 ID 的缺口：['GAP-001']
- 本成绩单只覆盖已建模条件，不能证明证据图完整或已发现全部适用规则。
- 范围说明：本成绩单只评价上游（01A 建图 / 02B 审核）已建模的结论、证据与缺口；结论状态由上游给出，07A 不重新判断。未被抽取的结论、未被发现的规则与日志外事实不在评价范围内。
