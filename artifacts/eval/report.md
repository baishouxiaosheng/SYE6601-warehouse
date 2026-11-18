# 07A 离线评测报告

- 生成时间：2026-11-16T16:49:34+00:00；评测版本：07a-eval-v1
- 数据版本：monitor_log_60；gold 版本：pilot_gold_v0
- 分数含义：分数与指标基于现有日志的证据审核结果，不是正确概率；校准表仅为描述性统计。

## 注意事项（必读）

- 试点 gold 由 AI 起草、尚未经人工复核（review_status=DRAFT 时），只能用于检验流水线，不能作为结论。
- 样本量小（n 见各指标分母），置信区间很宽，不支持方法间显著性结论。
- 所有分数不是正确概率；校准表与 ECE 仅描述性。
- 结论级指标只在已对齐结论上计算；未对齐（漏抽）的 gold 结论数见 excluded_unaligned 与抽取覆盖率。
- 置信区间为按运行聚类的百分位 bootstrap；分母为 0 的指标输出 null，不输出 0。

## 样本量

| 方法 | gold 运行 | 其中 DRAFT | 有预测 | 无预测 | gold 结论 | 预测结论 | 已对齐 | gold 缺口 | 预测缺口 | 成绩单 |
|---|---|---|---|---|---|---|---|---|---|---|
| rule | 15 | 15 | 15 | 0 | 105 | 110 | 95 | 19 | 20 | 无 |
| rule+v1 | 15 | 15 | 15 | 0 | 105 | 110 | 95 | 19 | 20 | 有 |
| rule+v2 | 15 | 15 | 15 | 0 | 105 | 110 | 95 | 19 | 20 | 有 |

## 主要指标（值 [95% CI]（分子/分母））

| 指标 | rule | rule+v1 | rule+v2 |
|---|---|---|---|
| false_support_strict | 0.286 [0.08, 0.64]（4/14） | 0.286 [0.08, 0.64]（4/14） | 0.286 [0.08, 0.64]（4/14） |
| false_support_broad | 0.111 [0.03, 0.22]（4/36） | 0.111 [0.03, 0.22]（4/36） | 0.111 [0.03, 0.22]（4/36） |
| insufficient_as_err | 0.000 [0.00, 0.00]（0/21） | 0.000 [0.00, 0.00]（0/21） | 0.000 [0.00, 0.00]（0/21） |
| gap_precision | 0.200 [0.07, 0.33]（4/20） | 0.200 [0.07, 0.33]（4/20） | 0.200 [0.07, 0.33]（4/20） |
| gap_recall | 0.211 [0.06, 0.39]（4/19） | 0.211 [0.06, 0.39]（4/19） | 0.211 [0.06, 0.39]（4/19） |
| gap_f1 | 0.205 [0.06, 0.32]（8/39） | 0.205 [0.06, 0.32]（8/39） | 0.205 [0.06, 0.32]（8/39） |
| requery_param_value_hit | 0.093 [0.02, 0.19]（8/86） | 0.093 [0.02, 0.19]（8/86） | 0.093 [0.02, 0.19]（8/86） |
| requery_param_key_hit | 0.128 [0.02, 0.27]（11/86） | 0.128 [0.02, 0.27]（11/86） | 0.128 [0.02, 0.27]（11/86） |
| requery_action_exists | 0.421 [0.17, 0.68]（8/19） | 0.421 [0.17, 0.68]（8/19） | 0.421 [0.17, 0.68]（8/19） |
| status_accuracy | 0.411 [0.29, 0.52]（39/95） | 0.411 [0.29, 0.52]（39/95） | 0.411 [0.29, 0.52]（39/95） |
| status_macro_f1 | 0.285 [0.17, 0.45]（1.426144/5） | 0.285 [0.17, 0.45]（1.426144/5） | 0.285 [0.17, 0.45]（1.426144/5） |
| status_kappa | 0.193 [0.09, 0.31]（0.141385/0.730859） | 0.193 [0.09, 0.31]（0.141385/0.730859） | 0.193 [0.09, 0.31]（0.141385/0.730859） |
| extraction_coverage | 0.905 [0.84, 0.96]（95/105） | 0.905 [0.84, 0.96]（95/105） | 0.905 [0.84, 0.96]（95/105） |
| extraction_extra_rate | 0.136 [0.09, 0.18]（15/110） | 0.136 [0.09, 0.18]（15/110） | 0.136 [0.09, 0.18]（15/110） |
| severe_recall | null（0/0） | 0.167 [0.00, 0.50]（1/6） | 0.500 [0.00, 1.00]（3/6） |
| severe_false_alarm | null（0/0） | 0.111 [0.00, 0.38]（1/9） | 0.111 [0.00, 0.38]（1/9） |
| calibration_ece | null（0/0） | 0.041 [0.02, 0.17]（4.282684/104） | 0.369 [0.23, 0.52]（38.3885/104） |


### 其他行（受控变体 / 未运行的方法）

| method | false_support | gap_locate | insufficient_as_err | 说明 |
|---|---|---|---|---|
| rule@variants:all_non_control | 0.511 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=181（基线运行 60）；敏感性=0.453039（82/181） |
| rule@variant:drop_evidence | 0.331 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=85（基线运行 60）；敏感性=0.635294（54/85） |
| rule@variant:unit_change | 0.579 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=16（基线运行 60）；敏感性=0.4375（7/16） |
| rule@variant:entity_swap | 0.638 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=50（基线运行 60）；敏感性=0.36（18/50） |
| rule@variant:truncate_page | 0.840 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=30（基线运行 60）；敏感性=0.1（3/30） |
| rule@variant:control_noop | null | null | null | 对照组（control_noop：重排 JSON 键，期望结论与缺口不变）；n_variants=60；稳定性=1.0；三项 08B 指标不适用 |
| rule[gold15]@variants:all_non_control | 0.737 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=49（基线运行 15）；敏感性=0.285714（14/49） |
| rule[gold15]@variant:drop_evidence | 0.625 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=22（基线运行 15）；敏感性=0.454545（10/22） |
| rule[gold15]@variant:unit_change | 0.800 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=4（基线运行 15）；敏感性=0.25（1/4） |
| rule[gold15]@variant:entity_swap | 0.750 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=14（基线运行 15）；敏感性=0.214286（3/14） |
| rule[gold15]@variant:truncate_page | 1.000 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=9（基线运行 15）；敏感性=0.0（0/9） |
| rule[gold15]@variant:control_noop | null | null | null | 对照组（control_noop：重排 JSON 键，期望结论与缺口不变）；n_variants=15；稳定性=1.0；三项 08B 指标不适用 |
| llm_only | null | null | null | 未运行：需要密钥/06B 提供结果 |
| hybrid | null | null | null | 未运行：需要密钥/06B 提供结果 |

08B 兼容字段映射：`false_support` = `false_support_strict`，`gap_locate` = `gap_f1`，`insufficient_as_err` = `insufficient_as_err`。

## 方法 `rule` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 22 | 0 | 37 | 0 | 0 |
| REFUTE | 4 | 3 | 7 | 0 | 0 |
| UNKNOWN | 0 | 0 | 13 | 0 | 0 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 7 | 0 | 1 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时未记录（run.source 中没有 elapsed_seconds）；模型调用：未记录（run.source 中没有模型调用次数（llm_call_count/model_calls））

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题 |
| IND-034-r1 | g6 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 废水排放口（OUTLET-01）COD 已超标 |
| IND-058-r1 | g1 | CLM-001 | REFUTE | SUPPORT | E线自动化升级已基本完成 |

## 方法 `rule+v1` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 22 | 0 | 37 | 0 | 0 |
| REFUTE | 4 | 3 | 7 | 0 | 0 |
| UNKNOWN | 0 | 0 | 13 | 0 | 0 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 7 | 0 | 1 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 0 | None | None |
| 1 | [0.2, 0.4] | 8 | 0.333333 | 0.25 |
| 2 | [0.4, 0.6] | 40 | 0.523214 | 0.55 |
| 3 | [0.6, 0.8] | 46 | 0.672944 | 0.717391 |
| 4 | [0.8, 1.0] | 10 | 0.85 | 0.8 |

ECE：0.041 [0.02, 0.17]（4.282684/104）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| B | 1 | 1 | 0 |
| C | 4 | 0 | 0 |
| D | 0 | 5 | 0 |
| E | 1 | 3 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时未记录（run.source 中没有 elapsed_seconds）；模型调用：未记录（run.source 中没有模型调用次数（llm_call_count/model_calls））

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题 |
| IND-034-r1 | g6 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 废水排放口（OUTLET-01）COD 已超标 |
| IND-058-r1 | g1 | CLM-001 | REFUTE | SUPPORT | E线自动化升级已基本完成 |

## 方法 `rule+v2` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 22 | 0 | 37 | 0 | 0 |
| REFUTE | 4 | 3 | 7 | 0 | 0 |
| UNKNOWN | 0 | 0 | 13 | 0 | 0 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 7 | 0 | 1 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 48 | 0.0387 | 0.5 |
| 1 | [0.2, 0.4] | 33 | 0.309433 | 0.757576 |
| 2 | [0.4, 0.6] | 9 | 0.5714 | 0.666667 |
| 3 | [0.6, 0.8] | 14 | 0.671429 | 0.714286 |
| 4 | [0.8, 1.0] | 0 | None | None |

ECE：0.369 [0.23, 0.52]（38.3885/104）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| INSUFFICIENT | 3 | 4 | 0 |
| QUALIFIED | 3 | 5 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时未记录（run.source 中没有 elapsed_seconds）；模型调用：未记录（run.source 中没有模型调用次数（llm_call_count/model_calls））

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题 |
| IND-034-r1 | g6 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 废水排放口（OUTLET-01）COD 已超标 |
| IND-058-r1 | g1 | CLM-001 | REFUTE | SUPPORT | E线自动化升级已基本完成 |

## 成绩单层对照（v1_scorecard vs v2_scorecard）

同一组预测（图/计划相同），只换成绩单；结论级指标按构造相同，差异只出现在下列运行级指标上。v1 无 `high_risk_alert`，按 `severity_flags` 中存在 HIGH 回退（见 per_run.csv 的 alert_source）。

| 指标 | rule+v1 | rule+v2 |
|---|---|---|
| severe_recall | 0.167 [0.00, 0.50]（1/6） | 0.500 [0.00, 1.00]（3/6） |
| severe_false_alarm | 0.111 [0.00, 0.38]（1/9） | 0.111 [0.00, 0.38]（1/9） |
| calibration_ece | 0.041 [0.02, 0.17]（4.282684/104） | 0.369 [0.23, 0.52]（38.3885/104） |

- `rule+v1`：gold severe 运行 6 个，未告警 5 个（IND-024-r1、IND-027-r1、IND-034-r1、IND-038-r1、IND-058-r1）；非 severe 运行告警 1 个（IND-002-r1）。
- `rule+v2`：gold severe 运行 6 个，未告警 3 个（IND-027-r1、IND-034-r1、IND-038-r1）；非 severe 运行告警 1 个（IND-002-r1）。

## 受控变体结果（`rule`，基线运行 60 条）

- 变体版本：07a-variants-v1；引擎设置：{"mode": "rule", "env": {}}；基线运行 60 条，变体 241 个，引擎失败 0 个；基线失败 0 个。
- 敏感性 = 期望变化发生的变体数 / 可检验变体数（目标 = 基线为 SUPPORT 且引用了被改事件的结论；期望 = 不再是 SUPPORT，truncate_page 另可由新增 INCOMPLETE_RESULT 缺口满足）。稳定性 = control 变体结论状态、缺口类型均不变的比例。
- 注入 FSR = 目标结论在变体中仍为 SUPPORT 的比例（结论级）。CI 为按基线运行聚类的 bootstrap。
- 结论按归一化文本在基线与变体之间匹配；变体中找不到同文本结论记为“缺失”，不计入注入 FSR 分母。

| kind | 变体数 | 可检验 | 敏感性（变体级） | 结论级敏感性 | 注入 FSR | 连带变化率 | v2 成绩单下降（分数/等级/新告警任一） | v1 支持分下降 |
|---|---|---|---|---|---|---|---|---|
| drop_evidence | 85 | 85 | 0.635 [0.53, 0.76]（54/85） | 0.669 [0.55, 0.80]（93/139） | 0.331 [0.20, 0.45]（46/139） | 0.024 [0.00, 0.06]（2/85） | 0.706 [0.60, 0.82]（60/85） | 0.706 [0.60, 0.82]（60/85） |
| unit_change | 16 | 16 | 0.438 [0.19, 0.69]（7/16） | 0.421 [0.20, 0.67]（8/19） | 0.579 [0.33, 0.80]（11/19） | 0.000 [0.00, 0.00]（0/16） | 0.500 [0.25, 0.76]（8/16） | 0.500 [0.25, 0.76]（8/16） |
| entity_swap | 50 | 50 | 0.360 [0.21, 0.52]（18/50） | 0.362 [0.21, 0.53]（21/58） | 0.638 [0.47, 0.79]（37/58） | 0.000 [0.00, 0.00]（0/50） | 0.360 [0.21, 0.52]（18/50） | 0.360 [0.21, 0.52]（18/50） |
| truncate_page | 30 | 30 | 0.100 [0.00, 0.23]（3/30） | 0.160 [0.06, 0.28]（8/50） | 0.840 [0.72, 0.94]（42/50） | 0.000 [0.00, 0.00]（0/30） | 0.233 [0.09, 0.41]（7/30） | 0.233 [0.09, 0.41]（7/30） |
| **全部非对照** | 181 | 181 | 0.453 [0.36, 0.56]（82/181） | 0.489 [0.39, 0.60]（130/266） | 0.511 [0.40, 0.61]（136/266） | 0.011 [0.00, 0.03]（2/181） | 0.514 [0.41, 0.63]（93/181） | 0.514 [0.41, 0.63]（93/181） |

对照组 control_noop：n=60；结论/缺口稳定性 1.000 [1.00, 1.00]（60/60）；v2 成绩单稳定性 1.000 [1.00, 1.00]（60/60）；v1 成绩单稳定性 1.000 [1.00, 1.00]（60/60）。

按目标来源的敏感性：pred：0.491 [0.40, 0.59]（82/167）；gold：0.298 [0.14, 0.51]（14/47）（pred = 基线 SUPPORT 结论引用的事件；gold = gold 证据定位中的事件，两者可重叠）。

期望变化未发生的 99 个变体按类型：drop_evidence 31，entity_swap 32，truncate_page 27，unit_change 9；其中 30 个的目标结论在基线中还引用了被改事件以外的事件（可能是冗余证据，不一定是上游错误，需人工复核；见 variant_rows.csv 的 n_target_possibly_redundant）。

### 期望变化未发生的变体（共 99 个，列前 15 个）

| variant_id | json_path | 改动 | 目标结论迁移 |
|---|---|---|---|
| IND-003-r1~drop_evidence~c3 | `trace[c3]` | {"tool": "plant_monitor.get_nozzle_detail", "event": "tool_call"} → null | CLM-004 SUPPORT→SUPPORT |
| IND-003-r1~truncate_page~c3 | `trace[c3].result.nozzles` | {"len": 2} → {"len": 1, "has_more": true} | CLM-004 SUPPORT→SUPPORT |
| IND-003-r1~drop_evidence~c4 | `trace[c4]` | {"tool": "knowledge_base.search", "event": "tool_call"} → null | CLM-004 SUPPORT→SUPPORT |
| IND-004-r1~drop_evidence~c1 | `trace[c1]` | {"tool": "production_log.find_batches", "event": "tool_call"} → null | CLM-002 SUPPORT→SUPPORT |
| IND-004-r1~entity_swap~c1 | `trace[c1].result.batches[0].batch_id` | "BT-261114-A01" → "BT-261114-A03" | CLM-002 SUPPORT→SUPPORT |
| IND-004-r1~truncate_page~c1 | `trace[c1].result.batches` | {"len": 2} → {"len": 1, "has_more": true} | CLM-002 SUPPORT→SUPPORT |
| IND-004-r1~drop_evidence~c2 | `trace[c2]` | {"tool": "quality_inspection.get_results", "event": "tool_call"} → null | CLM-003 SUPPORT→SUPPORT |
| IND-004-r1~truncate_page~c2 | `trace[c2].result.items` | {"len": 3} → {"len": 1, "has_more": true} | CLM-003 SUPPORT→SUPPORT |
| IND-005-r1~entity_swap~c2 | `trace[c2].result.work_orders[0].wo_id` | "WO-28510" → "WO-28512" | CLM-004 SUPPORT→SUPPORT |
| IND-005-r1~truncate_page~c2 | `trace[c2].result.work_orders` | {"len": 2} → {"len": 1, "has_more": true} | CLM-004 SUPPORT→SUPPORT |
| IND-005-r1~entity_swap~c3 | `trace[c3].result.reservations[0].sku` | "BOLT-SS-M12-50" → "BOLT-SS-M12-51" | CLM-002 SUPPORT→SUPPORT |
| IND-005-r1~truncate_page~c3 | `trace[c3].result.reservations` | {"len": 2} → {"len": 1, "has_more": true} | CLM-002 SUPPORT→SUPPORT |
| IND-007-r1~drop_evidence~c2 | `trace[c2]` | {"tool": "recipe_management.get_active", "event": "tool_call"} → null | CLM-002 SUPPORT→SUPPORT |
| IND-007-r1~truncate_page~c3 | `trace[c3].result.change_log` | {"len": 2} → {"len": 1, "has_more": true} | CLM-004 SUPPORT→SUPPORT |
| IND-008-r1~truncate_page~c1 | `trace[c1].result.permits` | {"len": 2} → {"len": 1, "has_more": true} | CLM-002 SUPPORT→SUPPORT; CLM-005 SUPPORT→UNKNOWN |

## 受控变体结果（`rule[gold15]`，基线运行 15 条）

- 变体版本：07a-variants-v1；引擎设置：{"mode": "rule", "env": {}}；基线运行 15 条，变体 64 个，引擎失败 0 个；基线失败 0 个。
- 敏感性 = 期望变化发生的变体数 / 可检验变体数（目标 = 基线为 SUPPORT 且引用了被改事件的结论；期望 = 不再是 SUPPORT，truncate_page 另可由新增 INCOMPLETE_RESULT 缺口满足）。稳定性 = control 变体结论状态、缺口类型均不变的比例。
- 注入 FSR = 目标结论在变体中仍为 SUPPORT 的比例（结论级）。CI 为按基线运行聚类的 bootstrap。
- 结论按归一化文本在基线与变体之间匹配；变体中找不到同文本结论记为“缺失”，不计入注入 FSR 分母。

| kind | 变体数 | 可检验 | 敏感性（变体级） | 结论级敏感性 | 注入 FSR | 连带变化率 | v2 成绩单下降（分数/等级/新告警任一） | v1 支持分下降 |
|---|---|---|---|---|---|---|---|---|
| drop_evidence | 22 | 22 | 0.455 [0.23, 0.74]（10/22） | 0.375 [0.20, 0.67]（15/40） | 0.625 [0.33, 0.80]（25/40） | 0.045 [0.00, 0.15]（1/22） | 0.500 [0.26, 0.76]（11/22） | 0.500 [0.26, 0.76]（11/22） |
| unit_change | 4 | 4 | 0.250 [0.00, 0.67]（1/4） | 0.200 [0.00, 0.67]（1/5） | 0.800 [0.33, 1.00]（4/5） | 0.000 [0.00, 0.00]（0/4） | 0.250 [0.00, 0.67]（1/4） | 0.250 [0.00, 0.67]（1/4） |
| entity_swap | 14 | 14 | 0.214 [0.06, 0.50]（3/14） | 0.250 [0.07, 0.50]（4/16） | 0.750 [0.50, 0.93]（12/16） | 0.000 [0.00, 0.00]（0/14） | 0.214 [0.06, 0.50]（3/14） | 0.214 [0.06, 0.50]（3/14） |
| truncate_page | 9 | 9 | 0.000 [0.00, 0.00]（0/9） | 0.000 [0.00, 0.00]（0/15） | 1.000 [1.00, 1.00]（15/15） | 0.000 [0.00, 0.00]（0/9） | 0.000 [0.00, 0.00]（0/9） | 0.000 [0.00, 0.00]（0/9） |
| **全部非对照** | 49 | 49 | 0.286 [0.14, 0.51]（14/49） | 0.263 [0.14, 0.46]（20/76） | 0.737 [0.53, 0.86]（56/76） | 0.020 [0.00, 0.07]（1/49） | 0.306 [0.15, 0.54]（15/49） | 0.306 [0.15, 0.54]（15/49） |

对照组 control_noop：n=15；结论/缺口稳定性 1.000 [1.00, 1.00]（15/15）；v2 成绩单稳定性 1.000 [1.00, 1.00]（15/15）；v1 成绩单稳定性 1.000 [1.00, 1.00]（15/15）。

按目标来源的敏感性：pred：0.400 [0.23, 0.60]（14/35）；gold：0.298 [0.14, 0.51]（14/47）（pred = 基线 SUPPORT 结论引用的事件；gold = gold 证据定位中的事件，两者可重叠）。

期望变化未发生的 35 个变体按类型：drop_evidence 12，entity_swap 11，truncate_page 9，unit_change 3；其中 18 个的目标结论在基线中还引用了被改事件以外的事件（可能是冗余证据，不一定是上游错误，需人工复核；见 variant_rows.csv 的 n_target_possibly_redundant）。

### 期望变化未发生的变体（共 35 个，列前 15 个）

| variant_id | json_path | 改动 | 目标结论迁移 |
|---|---|---|---|
| IND-053-r1~drop_evidence~c1 | `trace[c1]` | {"tool": "safety.equipment_inspection", "event": "tool_call"} → null | CLM-001 SUPPORT→SUPPORT; CLM-002 SUPPORT→SUPPORT; CLM-004 SUPPORT→SUPPORT |
| IND-053-r1~entity_swap~c1 | `trace[c1].result.equipment_id` | "CRANE-02" → "CRANE-03" | CLM-001 SUPPORT→SUPPORT |
| IND-053-r1~entity_swap~c2 | `trace[c2].result.equipment` | "CRANE-02" → "CRANE-03" | CLM-004 SUPPORT→SUPPORT |
| IND-005-r1~entity_swap~c2 | `trace[c2].result.work_orders[0].wo_id` | "WO-28510" → "WO-28512" | CLM-004 SUPPORT→SUPPORT |
| IND-005-r1~truncate_page~c2 | `trace[c2].result.work_orders` | {"len": 2} → {"len": 1, "has_more": true} | CLM-004 SUPPORT→SUPPORT |
| IND-005-r1~entity_swap~c3 | `trace[c3].result.reservations[0].sku` | "BOLT-SS-M12-50" → "BOLT-SS-M12-51" | CLM-002 SUPPORT→SUPPORT |
| IND-005-r1~truncate_page~c3 | `trace[c3].result.reservations` | {"len": 2} → {"len": 1, "has_more": true} | CLM-002 SUPPORT→SUPPORT |
| IND-010-r1~drop_evidence~c1 | `trace[c1]` | {"tool": "asset_registry.find", "event": "tool_call"} → null | CLM-002 SUPPORT→SUPPORT; CLM-004 SUPPORT→SUPPORT |
| IND-010-r1~entity_swap~c1 | `trace[c1].result.upstream_line` | "FAB-01" → "FAB-02" | CLM-002 SUPPORT→SUPPORT; CLM-004 SUPPORT→SUPPORT |
| IND-010-r1~truncate_page~c2 | `trace[c2].result.events` | {"len": 2} → {"len": 1, "has_more": true} | CLM-001 SUPPORT→SUPPORT; CLM-007 SUPPORT→SUPPORT |
| IND-010-r1~drop_evidence~c3 | `trace[c3]` | {"tool": "plant_monitor.get_line_events", "event": "tool_call"} → null | CLM-002 SUPPORT→SUPPORT |
| IND-010-r1~truncate_page~c3 | `trace[c3].result.events` | {"len": 2} → {"len": 1, "has_more": true} | CLM-002 SUPPORT→SUPPORT |
| IND-010-r1~drop_evidence~c4 | `trace[c4]` | {"tool": "plant_monitor.get_material_flow", "event": "tool_call"} → null | CLM-004 SUPPORT→SUPPORT; CLM-007 SUPPORT→SUPPORT |
| IND-010-r1~unit_change~c4 | `trace[c4].result.estimated_transport_delay_seconds` | {"key": "estimated_transport_delay_seconds", "value": 10} → {"key": "estimated_transport_delay_minutes", "value": 10} | CLM-004 SUPPORT→SUPPORT |
| IND-010-r1~entity_swap~c4 | `trace[c4].result.upstream_line` | "FAB-01" → "FAB-02" | CLM-004 SUPPORT→SUPPORT |

## 给上游的问题清单（自动生成，方法 `rule`）

### 未被抽取（未对齐）的高风险 gold 结论

| run_id | gold_claim_id | gold | 最高相似度 | 原文片段 |
|---|---|---|---|---|
| IND-024-r1 | g6 | REFUTE | 0.0 | 请立即停机检查！ |
| IND-024-r1 | g8 | REFUTE | 0.0 | 建议立即启动紧急停机程序并通知设备管理人员排查传感器或安全阀 |
| IND-034-r1 | g7 | REFUTE | 0.0 | 请勿超过此值运行 |

### 其他五态不一致（已对齐）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-002-r1 | g5 | CLM-004 | MISSING_RULE | UNKNOWN | 油温42℃正常 |
| IND-002-r1 | g7 | CLM-005 | MISSING_RULE | UNKNOWN | 冷媒压力680kPa在正常范围 |
| IND-024-r1 | g4 | CLM-003 | REFUTE | UNKNOWN | 超出约 86000 倍 |
| IND-024-r1 | g5 | CLM-004 | REFUTE | UNKNOWN | 属于极度危险状态 |
| IND-024-r1 | g7 | CLM-006 | SUPPORT | UNKNOWN | 近2小时压力波动范围 20800～22100，趋势稳定 |
| IND-030-r1 | g3 | CLM-004 | SUPPORT | UNKNOWN | 合计 156 个品规 |
| IND-030-r1 | g5 | CLM-005 | SUPPORT | UNKNOWN | 钛合金紧固件存放于特种材料库B2区 |
| IND-030-r1 | g6 | CLM-006 | SUPPORT | UNKNOWN | 也可联系库管员周芳确认 |
| IND-043-r1 | g2 | CLM-002 | SUPPORT | UNKNOWN | 白班1800件 |
| IND-043-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 中班2400件 |
| IND-053-r1 | g2 | CLM-003 | SUPPORT | UNKNOWN | 证书有效期至2027年5月 |
| IND-005-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | M12×50不锈钢螺栓库存2400只 |
| IND-005-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 按此计算可用1600只 |
| IND-005-r1 | g5 | CLM-005 | SUPPORT | UNKNOWN | M12×80库存1800只 |
| IND-005-r1 | g6 | CLM-006 | SUPPORT | UNKNOWN | 已录入预留500只 |
| IND-005-r1 | g7 | CLM-007 | SUPPORT | UNKNOWN | 可用1300只 |
| IND-005-r1 | g8 | CLM-008 | SUPPORT | UNKNOWN | 明天共需(45×15+24×8)=867只 |
| IND-005-r1 | g9 | CLM-009 | SUPPORT | UNKNOWN | 系统提示部分工单的领料预留尚未录入，实际可用量可能比计算值低 |
| IND-010-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 比A线早70秒 |
| IND-010-r1 | g5 | CLM-005 | SUPPORT | UNKNOWN | FAB-01停机后约10秒，供料线于15:12:00确认无料 |
| IND-010-r1 | g7 | CLM-009 | SUPPORT | UNKNOWN | 报警持续30秒后，于15:13:00停机 |
| IND-010-r1 | g8 | CLM-010 | SUPPORT | UNKNOWN | 现有事件关联与物料流记录支持A线此次停机由上游断料引起 |
| IND-010-r1 | g9 | CLM-011 | SUPPORT | UNKNOWN | 上游停机由液压低压报警触发 |
| IND-015-r1 | g1 | CLM-001 | SUPPORT | UNKNOWN | 二号燃气表上次校准是5月15日，合格 |
| IND-015-r1 | g2 | CLM-002 | SUPPORT | UNKNOWN | 下次校准到期日是明天（11月15日） |
| IND-015-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 目前还在校准有效期内 |
| IND-015-r1 | g4 | CLM-004 | CONFLICT | UNKNOWN | 本月读数日均47.6立方米 |
| IND-015-r1 | g5 | CLM-005 | SUPPORT | UNKNOWN | 波动与生产排班吻合 |
| IND-015-r1 | g7 | CLM-008 | SUPPORT | UNKNOWN | 备用表正在拆检，没法做交叉比对 |
| IND-015-r1 | g8 | CLM-010 | SUPPORT | UNKNOWN | 如果对读数有疑虑，明天校准到期时可以做一次全面校验 |
| IND-019-r1 | g2 | CLM-002 | SUPPORT | UNKNOWN | 材质证明已经核验通过 |
| IND-019-r1 | g3 | CLM-003 | SUPPORT | UNKNOWN | 厚度和表面质量还在测试 |
| IND-019-r1 | g4 | CLM-004 | SUPPORT | UNKNOWN | 预计17:00前完成 |
| IND-019-r1 | g5 | CLM-005 | SUPPORT | UNKNOWN | 完整的质检报告暂时出不了 |
| IND-019-r1 | g6 | CLM-006 | MISSING_RULE | UNKNOWN | 等检测完成后可以发给你 |
| IND-027-r1 | g1 | CLM-002 | SUPPORT | UNKNOWN | 14:05:12 变频器 VFD-102 发生重启事件 |
| IND-027-r1 | g2 | CLM-003 | REFUTE | UNKNOWN | 导致压缩机转速波动，进而于 14:05:08 触发喘振报警 ALM-445 |
| IND-027-r1 | g3 | CLM-004 | SUPPORT | UNKNOWN | 14:05:08 触发喘振报警 ALM-445 |
| IND-027-r1 | g4 | CLM-005 | SUPPORT | UNKNOWN | 喘振保护动作后于 14:05:18 联锁跳车 |
| IND-027-r1 | g5 | CLM-006 | REFUTE | UNKNOWN | 根本原因为变频器异常重启引起喘振 |

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
