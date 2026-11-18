# 07A 离线评测报告

- 生成时间：2026-11-18T09:34:02+00:00；评测版本：07a-eval-v1
- 数据版本：industrial_log_60；gold 版本：team_gold_v2_industrial
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
| rule | 60 | 60 | 60 | 0 | 307 | 421 | 275 | 87 | 49 | 无 |
| rule+v1 | 60 | 60 | 60 | 0 | 307 | 421 | 275 | 87 | 49 | 有 |
| rule+v2 | 60 | 60 | 60 | 0 | 307 | 421 | 275 | 87 | 49 | 有 |

## 主要指标（值 [95% CI]（分子/分母））

| 指标 | rule | rule+v1 | rule+v2 |
|---|---|---|---|
| false_support_strict | 0.317 [0.17, 0.48]（13/41） | 0.317 [0.17, 0.48]（13/41） | 0.317 [0.17, 0.48]（13/41） |
| false_support_broad | 0.235 [0.16, 0.32]（27/115） | 0.235 [0.16, 0.32]（27/115） | 0.235 [0.16, 0.32]（27/115） |
| insufficient_as_err | 0.000 [0.00, 0.00]（0/73） | 0.000 [0.00, 0.00]（0/73） | 0.000 [0.00, 0.00]（0/73） |
| gap_precision | 0.204 [0.09, 0.33]（10/49） | 0.204 [0.09, 0.33]（10/49） | 0.204 [0.09, 0.33]（10/49） |
| gap_recall | 0.115 [0.05, 0.20]（10/87） | 0.115 [0.05, 0.20]（10/87） | 0.115 [0.05, 0.20]（10/87） |
| gap_f1 | 0.147 [0.06, 0.24]（20/136） | 0.147 [0.06, 0.24]（20/136） | 0.147 [0.06, 0.24]（20/136） |
| requery_param_value_hit | 0.065 [0.00, 0.17]（6/93） | 0.065 [0.00, 0.17]（6/93） | 0.065 [0.00, 0.17]（6/93） |
| requery_param_key_hit | 0.065 [0.00, 0.17]（6/93） | 0.065 [0.00, 0.17]（6/93） | 0.065 [0.00, 0.17]（6/93） |
| requery_action_exists | 0.257 [0.09, 0.43]（9/35） | 0.257 [0.09, 0.43]（9/35） | 0.257 [0.09, 0.43]（9/35） |
| status_accuracy | 0.375 [0.31, 0.43]（103/275） | 0.375 [0.31, 0.43]（103/275） | 0.375 [0.31, 0.43]（103/275） |
| status_macro_f1 | 0.206 [0.15, 0.30]（1.029299/5） | 0.206 [0.15, 0.30]（1.029299/5） | 0.206 [0.15, 0.30]（1.029299/5） |
| status_kappa | 0.076 [0.00, 0.14]（0.051412/0.676866） | 0.076 [0.00, 0.14]（0.051412/0.676866） | 0.076 [0.00, 0.14]（0.051412/0.676866） |
| extraction_coverage | 0.896 [0.86, 0.93]（275/307） | 0.896 [0.86, 0.93]（275/307） | 0.896 [0.86, 0.93]（275/307） |
| extraction_extra_rate | 0.347 [0.29, 0.40]（146/421） | 0.347 [0.29, 0.40]（146/421） | 0.347 [0.29, 0.40]（146/421） |
| severe_recall | null（0/0） | 0.154 [0.00, 0.36]（2/13） | 0.538 [0.23, 0.82]（7/13） |
| severe_false_alarm | null（0/0） | 0.043 [0.00, 0.11]（2/47） | 0.064 [0.00, 0.15]（3/47） |
| calibration_ece | null（0/0） | 0.105 [0.05, 0.17]（30.925397/294） | 0.319 [0.24, 0.40]（93.6693/294） |


### 其他行（受控变体 / 未运行的方法）

| method | false_support | gap_locate | insufficient_as_err | 说明 |
|---|---|---|---|---|
| rule@variants:all_non_control | 0.511 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=181（基线运行 60）；敏感性=0.453039（82/181） |
| rule@variant:drop_evidence | 0.331 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=85（基线运行 60）；敏感性=0.635294（54/85） |
| rule@variant:unit_change | 0.579 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=16（基线运行 60）；敏感性=0.4375（7/16） |
| rule@variant:entity_swap | 0.638 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=50（基线运行 60）；敏感性=0.36（18/50） |
| rule@variant:truncate_page | 0.840 | null | null | 受控变体（人工注入，需求§6）；false_support=注入后目标结论仍为 SUPPORT 的比例（目标=基线 SUPPORT 且其引用事件被破坏），gap_locate/insufficient_as_err 不适用（变体无 gold）；drop_evidence 若存在冗余证据，仍为 SUPPORT 未必是错误，需人工复核；n_variants=30（基线运行 60）；敏感性=0.1（3/30） |
| rule@variant:control_noop | null | null | null | 对照组（control_noop：重排 JSON 键，期望结论与缺口不变）；n_variants=60；稳定性=1.0；三项 08B 指标不适用 |
| hybrid | null | null | null | 未运行 |

08B 兼容字段映射：`false_support` = `false_support_strict`，`gap_locate` = `gap_f1`，`insufficient_as_err` = `insufficient_as_err`。

## 方法 `rule` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 56 | 0 | 104 | 0 | 0 |
| REFUTE | 13 | 2 | 26 | 0 | 0 |
| UNKNOWN | 13 | 0 | 44 | 0 | 2 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 1 | 0 | 12 | 0 | 1 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.174524s，均值=0.002909s，中位数=0.002697s；模型调用：0.0

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
| IND-034-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-035-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 涂膜厚度检测结果：膜厚 45-55 μm |
| IND-036-r1 | g5 | CLM-007 | UNKNOWN | SUPPORT | 消防器材已到位 |
| IND-036-r1 | g6 | CLM-008 | REFUTE | SUPPORT | 可以进行动火作业 |
| IND-037-r1 | g3 | CLM-006 | REFUTE | SUPPORT | 可以进入有限空间作业 |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | COD 已超标 |
| IND-040-r1 | g1 | CLM-001 | UNKNOWN | SUPPORT | 上游 FAB-02 产线运行正常 |
| IND-040-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 增加约 10-15% 的供料速率，以匹配下游 ASM-B 的消耗需求 |
| IND-041-r1 | g4 | CLM-004 | UNKNOWN | SUPPORT | P-201很可能也存在类似的密封腐蚀问题 |
| IND-047-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 有两家替代供应商可以联系 |
| IND-048-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 库房位置在A-03-12货架 |
| IND-052-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 添加剂配方已经确认完毕 |
| IND-052-r1 | g3 | CLM-003 | REFUTE | SUPPORT | 添加剂B用量1.8kg，均已完成确认 |
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题，可以正常作业 |
| IND-055-r1 | g1 | CLM-002 | UNKNOWN | SUPPORT | 空气质量正常，VOC和PM2.5均在标准范围内 |
| IND-057-r1 | g3 | CLM-005 | UNKNOWN | SUPPORT | 建议ROB-03也尽快安排关节检查，参照ROB-01的维护周期执行 |

## 方法 `rule+v1` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 56 | 0 | 104 | 0 | 0 |
| REFUTE | 13 | 2 | 26 | 0 | 0 |
| UNKNOWN | 13 | 0 | 44 | 0 | 2 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 1 | 0 | 12 | 0 | 1 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 0 | None | None |
| 1 | [0.2, 0.4] | 13 | 0.339744 | 0.153846 |
| 2 | [0.4, 0.6] | 68 | 0.522584 | 0.647059 |
| 3 | [0.6, 0.8] | 179 | 0.667795 | 0.608939 |
| 4 | [0.8, 1.0] | 34 | 0.838503 | 0.558824 |

ECE：0.105 [0.05, 0.17]（30.925397/294）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| B | 7 | 5 | 0 |
| C | 13 | 10 | 0 |
| D | 5 | 9 | 0 |
| E | 1 | 10 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.174524s，均值=0.002909s，中位数=0.002697s；模型调用：0.0

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
| IND-034-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-035-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 涂膜厚度检测结果：膜厚 45-55 μm |
| IND-036-r1 | g5 | CLM-007 | UNKNOWN | SUPPORT | 消防器材已到位 |
| IND-036-r1 | g6 | CLM-008 | REFUTE | SUPPORT | 可以进行动火作业 |
| IND-037-r1 | g3 | CLM-006 | REFUTE | SUPPORT | 可以进入有限空间作业 |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | COD 已超标 |
| IND-040-r1 | g1 | CLM-001 | UNKNOWN | SUPPORT | 上游 FAB-02 产线运行正常 |
| IND-040-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 增加约 10-15% 的供料速率，以匹配下游 ASM-B 的消耗需求 |
| IND-041-r1 | g4 | CLM-004 | UNKNOWN | SUPPORT | P-201很可能也存在类似的密封腐蚀问题 |
| IND-047-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 有两家替代供应商可以联系 |
| IND-048-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 库房位置在A-03-12货架 |
| IND-052-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 添加剂配方已经确认完毕 |
| IND-052-r1 | g3 | CLM-003 | REFUTE | SUPPORT | 添加剂B用量1.8kg，均已完成确认 |
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题，可以正常作业 |
| IND-055-r1 | g1 | CLM-002 | UNKNOWN | SUPPORT | 空气质量正常，VOC和PM2.5均在标准范围内 |
| IND-057-r1 | g3 | CLM-005 | UNKNOWN | SUPPORT | 建议ROB-03也尽快安排关节检查，参照ROB-01的维护周期执行 |

## 方法 `rule+v2` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 56 | 0 | 104 | 0 | 0 |
| REFUTE | 13 | 2 | 26 | 0 | 0 |
| UNKNOWN | 13 | 0 | 44 | 0 | 2 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 1 | 0 | 12 | 0 | 1 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 78 | 0.032974 | 0.551282 |
| 1 | [0.2, 0.4] | 128 | 0.277893 | 0.632812 |
| 2 | [0.4, 0.6] | 50 | 0.507768 | 0.58 |
| 3 | [0.6, 0.8] | 38 | 0.663158 | 0.552632 |
| 4 | [0.8, 1.0] | 0 | None | None |

ECE：0.319 [0.24, 0.40]（93.6693/294）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| INSUFFICIENT | 13 | 12 | 0 |
| QUALIFIED | 13 | 22 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.174524s，均值=0.002909s，中位数=0.002697s；模型调用：0.0

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
| IND-034-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-035-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 涂膜厚度检测结果：膜厚 45-55 μm |
| IND-036-r1 | g5 | CLM-007 | UNKNOWN | SUPPORT | 消防器材已到位 |
| IND-036-r1 | g6 | CLM-008 | REFUTE | SUPPORT | 可以进行动火作业 |
| IND-037-r1 | g3 | CLM-006 | REFUTE | SUPPORT | 可以进入有限空间作业 |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | COD 已超标 |
| IND-040-r1 | g1 | CLM-001 | UNKNOWN | SUPPORT | 上游 FAB-02 产线运行正常 |
| IND-040-r1 | g4 | CLM-007 | REFUTE | SUPPORT | 增加约 10-15% 的供料速率，以匹配下游 ASM-B 的消耗需求 |
| IND-041-r1 | g4 | CLM-004 | UNKNOWN | SUPPORT | P-201很可能也存在类似的密封腐蚀问题 |
| IND-047-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 有两家替代供应商可以联系 |
| IND-048-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 库房位置在A-03-12货架 |
| IND-052-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 添加剂配方已经确认完毕 |
| IND-052-r1 | g3 | CLM-003 | REFUTE | SUPPORT | 添加剂B用量1.8kg，均已完成确认 |
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题，可以正常作业 |
| IND-055-r1 | g1 | CLM-002 | UNKNOWN | SUPPORT | 空气质量正常，VOC和PM2.5均在标准范围内 |
| IND-057-r1 | g3 | CLM-005 | UNKNOWN | SUPPORT | 建议ROB-03也尽快安排关节检查，参照ROB-01的维护周期执行 |

## 成绩单层对照（v1_scorecard vs v2_scorecard）

同一组预测（图/计划相同），只换成绩单；结论级指标按构造相同，差异只出现在下列运行级指标上。v1 无 `high_risk_alert`，按 `severity_flags` 中存在 HIGH 回退（见 per_run.csv 的 alert_source）。

| 指标 | rule+v1 | rule+v2 |
|---|---|---|
| severe_recall | 0.154 [0.00, 0.36]（2/13） | 0.538 [0.23, 0.82]（7/13） |
| severe_false_alarm | 0.043 [0.00, 0.11]（2/47） | 0.064 [0.00, 0.15]（3/47） |
| calibration_ece | 0.105 [0.05, 0.17]（30.925397/294） | 0.319 [0.24, 0.40]（93.6693/294） |

- `rule+v1`：gold severe 运行 13 个，未告警 11 个（IND-023-r1、IND-024-r1、IND-036-r1、IND-037-r1、IND-040-r1、IND-045-r1、IND-051-r1、IND-052-r1、IND-054-r1、IND-056-r1、IND-058-r1）；非 severe 运行告警 2 个（IND-002-r1、IND-055-r1）。
- `rule+v2`：gold severe 运行 13 个，未告警 6 个（IND-023-r1、IND-036-r1、IND-040-r1、IND-045-r1、IND-054-r1、IND-056-r1）；非 severe 运行告警 3 个（IND-002-r1、IND-004-r1、IND-055-r1）。

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

## 给上游的问题清单（自动生成，方法 `rule`）

### 未被抽取（未对齐）的高风险 gold 结论

| run_id | gold_claim_id | gold | 最高相似度 | 原文片段 |
|---|---|---|---|---|
| IND-003-r1 | g5 | UNKNOWN | 0.0909 | 需要现场停机检查后才能确认 |
| IND-013-r1 | g2 | UNKNOWN | 0.3333 | 合格放行 |
| IND-024-r1 | g5 | REFUTE | 0.069 | 请立即停机检查 |
| IND-024-r1 | g7 | REFUTE | 0.0625 | 建议立即启动紧急停机程序 |
| IND-024-r1 | g8 | MISSING_RULE | 0.0 | 排查传感器或安全阀 |
| IND-042-r1 | g3 | UNKNOWN | 0.0645 | 建议明天上午进行试运行后恢复生产 |
| IND-051-r1 | g3 | REFUTE | 0.1935 | 请按180℃设定固化温度即可 |

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
