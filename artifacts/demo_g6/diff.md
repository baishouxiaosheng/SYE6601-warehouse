# 补证前后成绩单对比 · IND-043-r1

> 本成绩单的分数是“基于现有日志的证据审核结果”，不是回答正确的概率；未经独立标注数据校准前不得解读为正确率。等级只覆盖已建模条件，不能证明证据图完整或已发现全部适用规则。

- 等级：证据不足（INSUFFICIENT） → 附保留说明（QUALIFIED）
- 严重问题告警：False → False

| 维度 | 补证前 | 补证后 | 变化 |
|---|---|---|---|
| support | 0.0（0/4） | 0.25（1/4） | 0.25 |
| coverage | 1.0（1/1） | 1.0（1/1） | 0.0 |
| uncertainty | 0.0（0.0/4） | 0.25（1.0/4） | 0.25 |

## 结论状态迁移
| 结论 | 原文 | 补证前 | 补证后 | 不确定性判定 | 阻断项 |
|---|---|---|---|---|---|
| CLM-001→CLM-001 | D线昨天（11月13日）的产量为4200件 | UNKNOWN | **SUPPORT** | OVERCLAIM→APPROPRIATE | ['B2', 'B4']→[] |
| CLM-002→CLM-002 | 其中白班1800件 | UNKNOWN | UNKNOWN | OVERCLAIM→OVERCLAIM | []→[] |
| CLM-003→CLM-003 | 中班2400件 | UNKNOWN | UNKNOWN | OVERCLAIM→OVERCLAIM | []→[] |
| CLM-004→CLM-004 | 生产运行正常 | UNKNOWN | UNKNOWN | OVERCLAIM→OVERCLAIM | []→[] |

- 新增缺口：无
- 已关闭缺口：GAP-001 目标时段存在未覆盖区间：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00…
- 新增阻断项：无
- 消除阻断项：B2 D线昨天（11月13日）的产量为4200件；B4 D线昨天（11月13日）的产量为4200件

## 解释
- 等级由 证据不足（INSUFFICIENT）变为 附保留说明（QUALIFIED）。
- 结论“D线昨天（11月13日）的产量为4200件”状态 UNKNOWN → SUPPORT。
- 缺口 GAP-001（MISSING_EVIDENCE：目标时段存在未覆盖区间：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00）在补证后不再出现。
- 阻断项 B2（D线昨天（11月13日）的产量为4200件）已消除。
- 阻断项 B4（D线昨天（11月13日）的产量为4200件）已消除。

- 版本：补证前 {'graph_version': 'IND-043-evidence-graph-v1', 'plan_version': 'IND-043-supplementary-plan-v1', 'answer_version': None, 'answer_sha256': '29cfe8b610b6ddcf', 'proposal_status': 'proposed'}；补证后 {'graph_version': 'IND-043-evidence-graph-v1', 'plan_version': 'IND-043-supplementary-plan-v1', 'answer_version': None, 'answer_sha256': '29cfe8b610b6ddcf', 'proposal_status': 'proposed'}

## 数据声明

- 补证事件 u1 是 **SYNTHETIC 合成数据**（夜班 1650 件），来源：LoopB 种子记录 SIM-D-20261113-NIGHT（作者 Zhang Jimuqing，文件 sha256 764b6c246bc6…）。只用于演示 G6 链路，不代表真实产量，也不能用于评估准确率。
- 01A 上游 changes：[{"kind": "claim_status", "claim": "CLM-001", "content": "D线昨天（11月13日）的产量为4200件", "before": "UNKNOWN", "after": "SUPPORT", "reason": "补证后证据增强"}, {"kind": "gap_resolved", "gap": "GAP-001", "description": "目标时段存在未覆盖区间：2026-11-12T22:00:00+08:00 ~ 2026-11-13T06:00:00+08:00", "before": "OPEN", "after": "RESOLVED"}]

## 演示旁注：上游重算问题（不影响成绩单计算）

- 补证后按 business_date=2026-11-13 汇总三个班次为 5850 件，与回答的 4200 件不一致；但 01A 重算只检查了时间窗覆盖（CHK time_window_coverage=SUPPORT），把该结论判为 SUPPORT。07A 不重判状态，成绩单如实反映上游结果；此问题已列入给上游（01A）的问题清单。
- 结论：本演示证明 G6 链路（补证 → 重算 → 前后成绩单 → 差异解释）已打通；但“等级升为附保留说明”是建立在上游错误的 SUPPORT 之上的，不能解读为回答变得可信。
