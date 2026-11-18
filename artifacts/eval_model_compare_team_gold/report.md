# 07A 离线评测报告

- 生成时间：2026-11-18T09:34:34+00:00；评测版本：07a-eval-v1
- 数据版本：monitor_log_60；gold 版本：industrial_gold_v2
- 分数含义：分数与指标基于现有日志的证据审核结果，不是正确概率；校准表仅为描述性统计。

## 注意事项（必读）

- 试点 gold 由 AI 起草、尚未经人工复核（review_status=DRAFT 时），只能用于检验流水线，不能作为结论。
- 样本量小（n 见各指标分母），置信区间很宽，不支持方法间显著性结论。
- 所有分数不是正确概率；校准表与 ECE 仅描述性。
- 模型对照：n=33 条运行（模型结果 ∩ gold industrial_gold_v2.json）；模型 qwen/qwen3.8-27b；token 输入 53553 / 输出 360405；平均延迟 78.9s；混合方案未运行（用户决定不跑完）
- 结论级指标只在已对齐结论上计算；未对齐（漏抽）的 gold 结论数见 excluded_unaligned 与抽取覆盖率。
- 置信区间为按运行聚类的百分位 bootstrap；分母为 0 的指标输出 null，不输出 0。

## 样本量

| 方法 | gold 运行 | 其中 DRAFT | 有预测 | 无预测 | gold 结论 | 预测结论 | 已对齐 | gold 缺口 | 预测缺口 | 成绩单 |
|---|---|---|---|---|---|---|---|---|---|---|
| rule+v2 | 33 | 33 | 33 | 0 | 195 | 269 | 175 | 54 | 34 | 有 |
| llm_only+v2 | 33 | 33 | 33 | 0 | 195 | 295 | 191 | 54 | 74 | 有 |

## 主要指标（值 [95% CI]（分子/分母））

| 指标 | rule+v2 | llm_only+v2 |
|---|---|---|
| false_support_strict | 0.118 [0.00, 0.31]（2/17） | 0.050 [0.00, 0.22]（1/20） |
| false_support_broad | 0.177 [0.08, 0.30]（11/62） | 0.222 [0.10, 0.36]（16/72） |
| insufficient_as_err | 0.000 [0.00, 0.00]（0/44） | 0.020 [0.00, 0.07]（1/51） |
| gap_precision | 0.176 [0.07, 0.29]（6/34） | 0.284 [0.19, 0.39]（21/74） |
| gap_recall | 0.111 [0.04, 0.18]（6/54） | 0.389 [0.27, 0.51]（21/54） |
| gap_f1 | 0.136 [0.05, 0.22]（12/88） | 0.328 [0.23, 0.43]（42/128） |
| requery_param_value_hit | 0.054 [0.00, 0.18]（4/74） | 0.554 [0.18, 0.66]（41/74） |
| requery_param_key_hit | 0.054 [0.00, 0.18]（4/74） | 0.554 [0.18, 0.66]（41/74） |
| requery_action_exists | 0.286 [0.08, 0.48]（8/28） | 0.857 [0.61, 1.00]（24/28） |
| status_accuracy | 0.371 [0.30, 0.44]（65/175） | 0.785 [0.72, 0.85]（150/191） |
| status_macro_f1 | 0.231 [0.14, 0.35]（1.155292/5） | 0.680 [0.50, 0.79]（3.401849/5） |
| status_kappa | 0.086 [-0.02, 0.17]（0.059233/0.687804） | 0.614 [0.47, 0.73]（0.341794/0.556454） |
| extraction_coverage | 0.897 [0.86, 0.94]（175/195） | 0.979 [0.96, 0.99]（191/195） |
| extraction_extra_rate | 0.349 [0.27, 0.42]（94/269） | 0.353 [0.29, 0.41]（104/295） |
| severe_recall | 0.667 [0.00, 1.00]（2/3） | 1.000 [1.00, 1.00]（3/3） |
| severe_false_alarm | 0.067 [0.00, 0.17]（2/30） | 0.267 [0.12, 0.43]（8/30） |
| calibration_ece | 0.396 [0.30, 0.52]（72.0513/182） | 0.064 [0.03, 0.15]（11.6815/182） |


### 其他行（受控变体 / 未运行的方法）

| method | false_support | gap_locate | insufficient_as_err | 说明 |
|---|---|---|---|---|
| hybrid | null | null | null | 未运行：用户决定不跑完；01A hybrid 需要密钥 |

08B 兼容字段映射：`false_support` = `false_support_strict`，`gap_locate` = `gap_f1`，`insufficient_as_err` = `insufficient_as_err`。

## 方法 `rule+v2` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 37 | 0 | 76 | 0 | 0 |
| REFUTE | 2 | 2 | 13 | 0 | 0 |
| UNKNOWN | 8 | 0 | 25 | 0 | 0 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 1 | 0 | 9 | 0 | 1 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 43 | 0.0288 | 0.627907 |
| 1 | [0.2, 0.4] | 95 | 0.273161 | 0.705263 |
| 2 | [0.4, 0.6] | 28 | 0.498571 | 0.642857 |
| 3 | [0.6, 0.8] | 16 | 0.6375 | 0.5625 |
| 4 | [0.8, 1.0] | 0 | None | None |

ECE：0.396 [0.30, 0.52]（72.0513/182）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| INSUFFICIENT | 4 | 9 | 0 |
| QUALIFIED | 5 | 15 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=33，合计=0.118544s，均值=0.003592s，中位数=0.003467s；模型调用：0.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-001-r1 | g7 | CLM-009 | UNKNOWN | SUPPORT | 目前仅凭远程数据无法确定具体原因 |
| IND-005-r1 | g3 | CLM-004 | MISSING_RULE | SUPPORT | 共(60×15+32×8)=1156只 |
| IND-018-r1 | g4 | CLM-005 | UNKNOWN | SUPPORT | 从11:30开始离线 |
| IND-021-r1 | g2 | CLM-002 | UNKNOWN | SUPPORT | 振动值在 2.0～2.4 mm/s 之间 |
| IND-022-r1 | g2 | CLM-002 | UNKNOWN | SUPPORT | 良率 98.2% |
| IND-022-r1 | g3 | CLM-003 | UNKNOWN | SUPPORT | 产线利用率 97.7% |
| IND-022-r1 | g4 | CLM-004 | UNKNOWN | SUPPORT | 仅有30分钟换模停机 |
| IND-025-r1 | g4 | CLM-005 | REFUTE | SUPPORT | 该批次判定合格，可以放行 |
| IND-026-r1 | g1 | CLM-001 | UNKNOWN | SUPPORT | 冷却系统运行正常 |
| IND-032-r1 | g3 | CLM-009 | REFUTE | SUPPORT | 当前 THD 3.8% 低于 5% 限值 |
| IND-033-r1 | g4 | CLM-006 | UNKNOWN | SUPPORT | 超过 98℃ 的降速搅拌警戒线 |

## 方法 `llm_only+v2` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 106 | 2 | 4 | 1 | 6 |
| REFUTE | 1 | 17 | 2 | 0 | 0 |
| UNKNOWN | 10 | 1 | 19 | 0 | 8 |
| CONFLICT | 0 | 0 | 0 | 1 | 0 |
| MISSING_RULE | 5 | 0 | 1 | 0 | 7 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 6 | 0.0 | 0.0 |
| 1 | [0.2, 0.4] | 8 | 0.2222 | 0.125 |
| 2 | [0.4, 0.6] | 37 | 0.526284 | 0.648649 |
| 3 | [0.6, 0.8] | 80 | 0.677759 | 0.6875 |
| 4 | [0.8, 1.0] | 51 | 0.913669 | 0.803922 |

ECE：0.064 [0.03, 0.15]（11.6815/182）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| INSUFFICIENT | 9 | 15 | 0 |
| QUALIFIED | 0 | 9 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=33，合计=2604.033s，均值=78.910091s，中位数=70.781s；模型调用：33.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-001-r1 | g7 | C8 | UNKNOWN | SUPPORT | 目前仅凭远程数据无法确定具体原因 |
| IND-002-r1 | g6 | C6 | MISSING_RULE | SUPPORT | 冷媒压力680kPa在正常范围 |
| IND-002-r1 | g8 | C9 | MISSING_RULE | SUPPORT | 可以开机 |
| IND-005-r1 | g3 | C4 | MISSING_RULE | SUPPORT | 共(60×15+32×8)=1156只 |
| IND-005-r1 | g5 | C8 | MISSING_RULE | SUPPORT | 明天共需(45×15+24×8)=867只 |
| IND-005-r1 | g6 | C9 | UNKNOWN | SUPPORT | 实际可用量可能比计算值低 |
| IND-009-r1 | g6 | C5 | UNKNOWN | SUPPORT | 有效期到12月1日 |
| IND-011-r1 | g6 | C7 | UNKNOWN | SUPPORT | 没法远程判断异响的具体原因 |
| IND-013-r1 | g5 | C5 | UNKNOWN | SUPPORT | 目前是有条件放行 |
| IND-015-r1 | g3 | C4 | UNKNOWN | SUPPORT | 目前还在校准有效期内 |
| IND-022-r1 | g2 | C2 | UNKNOWN | SUPPORT | 良率 98.2% |
| IND-022-r1 | g3 | C3 | UNKNOWN | SUPPORT | 产线利用率 97.7% |
| IND-022-r1 | g4 | C4 | UNKNOWN | SUPPORT | 仅有30分钟换模停机 |
| IND-032-r1 | g3 | C9 | REFUTE | SUPPORT | 当前 THD 3.8% 低于 5% 限值 |
| IND-033-r1 | g4 | C6 | UNKNOWN | SUPPORT | 超过 98℃ 的降速搅拌警戒线 |
| IND-033-r1 | g6 | C4 | MISSING_RULE | SUPPORT | 当前温度 102℃ 已超过建议上限 95℃ |

## 成绩单层对照（v1_scorecard vs v2_scorecard）

同一组预测（图/计划相同），只换成绩单；结论级指标按构造相同，差异只出现在下列运行级指标上。v1 无 `high_risk_alert`，按 `severity_flags` 中存在 HIGH 回退（见 per_run.csv 的 alert_source）。

| 指标 | rule+v2 | llm_only+v2 |
|---|---|---|
| severe_recall | 0.667 [0.00, 1.00]（2/3） | 1.000 [1.00, 1.00]（3/3） |
| severe_false_alarm | 0.067 [0.00, 0.17]（2/30） | 0.267 [0.12, 0.43]（8/30） |
| calibration_ece | 0.396 [0.30, 0.52]（72.0513/182） | 0.064 [0.03, 0.15]（11.6815/182） |

- `rule+v2`：gold severe 运行 3 个，未告警 1 个（IND-023-r1）；非 severe 运行告警 2 个（IND-002-r1、IND-004-r1）。
- `llm_only+v2`：gold severe 运行 3 个，未告警 0 个；非 severe 运行告警 8 个（IND-002-r1、IND-003-r1、IND-004-r1、IND-011-r1、IND-021-r1、IND-026-r1、IND-027-r1、IND-033-r1）。

## 给上游的问题清单（自动生成，方法 `rule+v2`）

### 未被抽取（未对齐）的高风险 gold 结论

| run_id | gold_claim_id | gold | 最高相似度 | 原文片段 |
|---|---|---|---|---|
| IND-003-r1 | g5 | UNKNOWN | 0.0909 | 需要现场停机检查后才能确认 |
| IND-013-r1 | g2 | UNKNOWN | 0.3333 | 合格放行 |
| IND-024-r1 | g5 | REFUTE | 0.069 | 请立即停机检查 |
| IND-024-r1 | g7 | REFUTE | 0.0625 | 建议立即启动紧急停机程序 |
| IND-024-r1 | g8 | MISSING_RULE | 0.0 | 排查传感器或安全阀 |

### 其他五态不一致（已对齐）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-001-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 近两小时持续上升 |
| IND-001-r1 | g8 | CLM-011 | SUPPORT | UNKNOWN | 建议安排现场检查，优先排查积灰情况，同时检查燃烧器喷嘴和过剩空气系数 |
| IND-002-r1 | g5 | CLM-004 | MISSING_RULE | UNKNOWN | 油温42℃正常 |
| IND-002-r1 | g6 | CLM-005 | MISSING_RULE | UNKNOWN | 冷媒压力680kPa在正常范围 |
| IND-003-r1 | g2 | CLM-003 | SUPPORT | UNKNOWN | 主要集中在3号吸嘴，抛料率5.1% |
| IND-003-r1 | g3 | CLM-006 | SUPPORT | UNKNOWN | 真空度-45kPa，偏离规格-60kPa约25% |
| IND-003-r1 | g6 | CLM-012 | SUPPORT | UNKNOWN | 7号吸嘴可继续观察 |
| IND-003-r1 | g7 | CLM-007 | SUPPORT | UNKNOWN | 7号吸嘴也有轻微偏离 |
| IND-004-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 上午A线两个批次都已检完并放行 |
| IND-004-r1 | g3 | CLM-004 | SUPPORT | UNKNOWN | 质检主管李明已分别于11:00和14:20签字放行 |
| IND-005-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | M12×50不锈钢螺栓库存2400只 |
| IND-005-r1 | g4 | CLM-005 | SUPPORT | UNKNOWN | M12×80库存1800只，已录入预留500只，可用1300只 |
| IND-005-r1 | g5 | CLM-008 | MISSING_RULE | UNKNOWN | 明天共需(45×15+24×8)=867只 |
| IND-006-r1 | g3 | CLM-011 | SUPPORT | UNKNOWN | 10月用电量比9月增加约15% |
| IND-006-r1 | g4 | CLM-014 | SUPPORT | UNKNOWN | 产量也从16,200件增到18,500件（+14.2%） |
| IND-006-r1 | g5 | CLM-017 | SUPPORT | UNKNOWN | 从已有数据看，电费增长与产量增长基本匹配 |
| IND-006-r1 | g7 | CLM-018 | SUPPORT | UNKNOWN | 未见明显异常耗电 |
| IND-007-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 还没有切换 |
| IND-007-r1 | g2 | CLM-003 | SUPPORT | UNKNOWN | 当前使用的是REC-204的R2版本，11月10日启用的 |
| IND-007-r1 | g4 | CLM-005 | SUPPORT | UNKNOWN | 目前状态是待审批，还没指定审批人 |
| IND-008-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 今天系统里有两张动火证 |
| IND-008-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 安全主管刘强7:50审批的，有效期到18:00 |
| IND-008-r1 | g5 | CLM-006 | SUPPORT | UNKNOWN | 7:30提交的，还没批 |
| IND-009-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 排放口COD在线数据正常 |
| IND-009-r1 | g2 | CLM-002 | SUPPORT | UNKNOWN | 最近三次读数分别是42、38、45 mg/L |
| IND-009-r1 | g3 | CLM-004 | SUPPORT | UNKNOWN | 均远低于100 mg/L的限值 |
| IND-009-r1 | g4 | CLM-005 | SUPPORT | UNKNOWN | 仪器11月1日校准过 |
| IND-009-r1 | g5 | CLM-007 | SUPPORT | UNKNOWN | 今早6点自动标定也通过了 |
| IND-010-r1 | g3 | CLM-005 | SUPPORT | UNKNOWN | 供料线于15:12:00确认无料 |
| IND-010-r1 | g5 | CLM-010 | SUPPORT | UNKNOWN | 现有事件关联与物料流记录支持A线此次停机由上游断料引起 |
| IND-011-r1 | g2 | CLM-003 | MISSING_RULE | UNKNOWN | 都在正常范围 |
| IND-011-r1 | g3 | CLM-004 | MISSING_RULE | UNKNOWN | 数据上看没有异常 |
| IND-011-r1 | g4 | CLM-006 | SUPPORT | UNKNOWN | 6月15日巡检报告过一次轻微嗡嗡声，当时判断正常 |
| IND-011-r1 | g5 | CLM-007 | SUPPORT | UNKNOWN | 变压器没装振动传感器 |
| IND-012-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 上午11:30完成了渗碳淬火工艺 |
| IND-012-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 实验室那边也没有这批的送样记录 |
| IND-012-r1 | g4 | CLM-004 | SUPPORT | UNKNOWN | 热处理报告目前还没有，需要先安排送检 |
| IND-013-r1 | g4 | CLM-004 | SUPPORT | UNKNOWN | 盐雾试验只做了48小时，没到规定的72小时 |
| IND-014-r1 | g1 | CLM-002 | SUPPORT | UNKNOWN | 4个SKF 6308轴承，预计今天到货 |
| IND-014-r1 | g2 | CLM-003 | SUPPORT | UNKNOWN | 物流查询超时了 |

## 指标定义

- `false_support_strict`：FSR（严格）= #(gold=REFUTE ∧ pred=SUPPORT) / #(gold=REFUTE)，仅已对齐结论
- `false_support_broad`：FSR（广义）= #(gold∈{REFUTE,UNKNOWN,MISSING_RULE,CONFLICT} ∧ pred=SUPPORT) / #(gold∈该集合)，仅已对齐结论
- `insufficient_as_err`：IAE = #(gold∈{UNKNOWN,MISSING_RULE} ∧ pred=REFUTE) / #(gold∈{UNKNOWN,MISSING_RULE})，仅已对齐结论
- `gap_precision`：缺口定位精确率 = 命中缺口数 / 预测缺口数
- `gap_recall`：缺口定位召回率 = 命中缺口数 / gold 缺口数
- `gap_f1`：缺口定位 F1 = 2×命中 / (预测缺口数 + gold 缺口数)
- `requery_param_value_hit`：补查参数定位（键+值）= 在相关动作中键存在且值一致的关键参数数 / gold 关键参数总数
- `requery_param_key_hit`：补查参数定位（仅键）= 在相关动作中出现的关键参数键数 / gold 关键参数总数
- `requery_action_exists`：动作存在率 = 有至少一个相关补查动作的 gold 缺口数 / 带 required_params 的 gold 缺口数
- `status_accuracy`：五态准确率 = 混淆矩阵对角线 / 已对齐结论数
- `status_macro_f1`：五态 macro-F1 = Σ各类F1 / 出现过的类别数（gold 或 pred 中出现）
- `status_kappa`：Cohen's κ = (p_o − p_e) / (1 − p_e)
- `extraction_coverage`：结论抽取覆盖率 = 已对齐 gold 结论数 / gold 结论数
- `extraction_extra_rate`：多抽率 = 未对齐的预测结论数 / 预测结论数
- `severe_recall`：严重问题召回 = #(gold 有 severe 结论 ∧ high_risk_alert) / #(gold 有 severe 结论的运行)
- `severe_false_alarm`：严重问题误报率 = #(gold 无 severe ∧ high_risk_alert) / #(gold 无 severe 的运行)
- `calibration_ece`：ECE = Σ_b |Σconf_b − Σcorrect_b| / N；样本=gold 断言类结论，conf=所在运行 support_score，correct=gold_status==SUPPORT
