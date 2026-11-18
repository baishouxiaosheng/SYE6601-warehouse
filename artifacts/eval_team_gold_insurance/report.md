# 07A 离线评测报告

- 生成时间：2026-11-18T09:34:04+00:00；评测版本：07a-eval-v1
- 数据版本：insurance_log_60；gold 版本：team_gold_v2_insurance
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
| rule | 60 | 60 | 60 | 0 | 444 | 889 | 352 | 99 | 37 | 无 |
| rule+v1 | 60 | 60 | 60 | 0 | 444 | 889 | 352 | 99 | 37 | 有 |
| rule+v2 | 60 | 60 | 60 | 0 | 444 | 889 | 352 | 99 | 37 | 有 |

## 主要指标（值 [95% CI]（分子/分母））

| 指标 | rule | rule+v1 | rule+v2 |
|---|---|---|---|
| false_support_strict | 0.019 [0.00, 0.07]（1/52） | 0.019 [0.00, 0.07]（1/52） | 0.019 [0.00, 0.07]（1/52） |
| false_support_broad | 0.024 [0.00, 0.05]（3/125） | 0.024 [0.00, 0.05]（3/125） | 0.024 [0.00, 0.05]（3/125） |
| insufficient_as_err | 0.000 [0.00, 0.00]（0/65） | 0.000 [0.00, 0.00]（0/65） | 0.000 [0.00, 0.00]（0/65） |
| gap_precision | 0.135 [0.04, 0.26]（5/37） | 0.135 [0.04, 0.26]（5/37） | 0.135 [0.04, 0.26]（5/37） |
| gap_recall | 0.051 [0.01, 0.10]（5/99） | 0.051 [0.01, 0.10]（5/99） | 0.051 [0.01, 0.10]（5/99） |
| gap_f1 | 0.074 [0.02, 0.14]（10/136） | 0.074 [0.02, 0.14]（10/136） | 0.074 [0.02, 0.14]（10/136） |
| requery_param_value_hit | 0.000 [0.00, 0.00]（0/113） | 0.000 [0.00, 0.00]（0/113） | 0.000 [0.00, 0.00]（0/113） |
| requery_param_key_hit | 0.000 [0.00, 0.00]（0/113） | 0.000 [0.00, 0.00]（0/113） | 0.000 [0.00, 0.00]（0/113） |
| requery_action_exists | 0.066 [0.00, 0.15]（4/61） | 0.066 [0.00, 0.15]（4/61） | 0.066 [0.00, 0.15]（4/61） |
| status_accuracy | 0.352 [0.30, 0.40]（124/352） | 0.352 [0.30, 0.40]（124/352） | 0.352 [0.30, 0.40]（124/352） |
| status_macro_f1 | 0.158 [0.14, 0.18]（0.791021/5） | 0.158 [0.14, 0.18]（0.791021/5） | 0.158 [0.14, 0.18]（0.791021/5） |
| status_kappa | 0.127 [0.09, 0.16]（0.094145/0.741873） | 0.127 [0.09, 0.16]（0.094145/0.741873） | 0.127 [0.09, 0.16]（0.094145/0.741873） |
| extraction_coverage | 0.793 [0.75, 0.84]（352/444） | 0.793 [0.75, 0.84]（352/444） | 0.793 [0.75, 0.84]（352/444） |
| extraction_extra_rate | 0.604 [0.55, 0.65]（537/889） | 0.604 [0.55, 0.65]（537/889） | 0.604 [0.55, 0.65]（537/889） |
| severe_recall | null（0/0） | 0.000 [0.00, 0.00]（0/10） | 0.100 [0.00, 0.33]（1/10） |
| severe_false_alarm | null（0/0） | 0.000 [0.00, 0.00]（0/50） | 0.060 [0.00, 0.13]（3/50） |
| calibration_ece | null（0/0） | 0.067 [0.02, 0.13]（28.109823/422） | 0.474 [0.41, 0.54]（199.9742/422） |


### 其他行（受控变体 / 未运行的方法）

| method | false_support | gap_locate | insufficient_as_err | 说明 |
|---|---|---|---|---|
| llm_only | null | null | null | 未运行 |
| hybrid | null | null | null | 未运行 |

08B 兼容字段映射：`false_support` = `false_support_strict`，`gap_locate` = `gap_f1`，`insufficient_as_err` = `insufficient_as_err`。

## 方法 `rule` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 72 | 0 | 155 | 0 | 0 |
| REFUTE | 1 | 0 | 51 | 0 | 0 |
| UNKNOWN | 2 | 0 | 52 | 0 | 0 |
| CONFLICT | 0 | 0 | 8 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 11 | 0 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.231066s，均值=0.003851s，中位数=0.003777s；模型调用：0.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| a3b4c5d6-4545-4a45-e545-f5f6f7f8f9a0 | g4 | CLM-008 | REFUTE | SUPPORT | 等待期后因疾病身故按身故保险金 50 万元给付 |
| b4c5d6e7-4646-4b46-f646-a6a7a8a9b0b1 | g7 | CLM-013 | UNKNOWN | SUPPORT | 索赔提出时已不在保险期间内 |
| d2e3f4a5-6060-4d60-b060-c0c1d2e3f4a5 | g7 | CLM-001 | UNKNOWN | SUPPORT | 保单 ACC-260901-7788 有效 |

## 方法 `rule+v1` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 72 | 0 | 155 | 0 | 0 |
| REFUTE | 1 | 0 | 51 | 0 | 0 |
| UNKNOWN | 2 | 0 | 52 | 0 | 0 |
| CONFLICT | 0 | 0 | 8 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 11 | 0 | 0 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 0 | None | None |
| 1 | [0.2, 0.4] | 0 | None | None |
| 2 | [0.4, 0.6] | 289 | 0.546072 | 0.622837 |
| 3 | [0.6, 0.8] | 128 | 0.673765 | 0.710938 |
| 4 | [0.8, 1.0] | 5 | 0.833333 | 0.6 |

ECE：0.067 [0.02, 0.13]（28.109823/422）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| B | 1 | 2 | 0 |
| C | 3 | 2 | 0 |
| D | 1 | 8 | 0 |
| E | 23 | 20 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.231066s，均值=0.003851s，中位数=0.003777s；模型调用：0.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| a3b4c5d6-4545-4a45-e545-f5f6f7f8f9a0 | g4 | CLM-008 | REFUTE | SUPPORT | 等待期后因疾病身故按身故保险金 50 万元给付 |
| b4c5d6e7-4646-4b46-f646-a6a7a8a9b0b1 | g7 | CLM-013 | UNKNOWN | SUPPORT | 索赔提出时已不在保险期间内 |
| d2e3f4a5-6060-4d60-b060-c0c1d2e3f4a5 | g7 | CLM-001 | UNKNOWN | SUPPORT | 保单 ACC-260901-7788 有效 |

## 方法 `rule+v2` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 72 | 0 | 155 | 0 | 0 |
| REFUTE | 1 | 0 | 51 | 0 | 0 |
| UNKNOWN | 2 | 0 | 52 | 0 | 0 |
| CONFLICT | 0 | 0 | 8 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 11 | 0 | 0 |

### 校准表（描述性，样本小；support_score 不是正确概率）

| 分箱 | 区间 | gold 断言结论数 | 平均 support_score | gold 为 SUPPORT 比例 |
|---|---|---|---|---|
| 0 | [0.0, 0.2] | 289 | 0.092715 | 0.622837 |
| 1 | [0.2, 0.4] | 82 | 0.276428 | 0.658537 |
| 2 | [0.4, 0.6] | 46 | 0.476035 | 0.804348 |
| 3 | [0.6, 0.8] | 5 | 0.6667 | 0.6 |
| 4 | [0.8, 1.0] | 0 | None | None |

ECE：0.474 [0.41, 0.54]（199.9742/422）

### 等级 × gold answer_has_error（运行数）

| 等级 | 有错误 | 无错误 | 未标 |
|---|---|---|---|
| INSUFFICIENT | 6 | 9 | 0 |
| QUALIFIED | 22 | 23 | 0 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=60，合计=0.231066s，均值=0.003851s，中位数=0.003777s；模型调用：0.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| a3b4c5d6-4545-4a45-e545-f5f6f7f8f9a0 | g4 | CLM-008 | REFUTE | SUPPORT | 等待期后因疾病身故按身故保险金 50 万元给付 |
| b4c5d6e7-4646-4b46-f646-a6a7a8a9b0b1 | g7 | CLM-013 | UNKNOWN | SUPPORT | 索赔提出时已不在保险期间内 |
| d2e3f4a5-6060-4d60-b060-c0c1d2e3f4a5 | g7 | CLM-001 | UNKNOWN | SUPPORT | 保单 ACC-260901-7788 有效 |

## 成绩单层对照（v1_scorecard vs v2_scorecard）

同一组预测（图/计划相同），只换成绩单；结论级指标按构造相同，差异只出现在下列运行级指标上。v1 无 `high_risk_alert`，按 `severity_flags` 中存在 HIGH 回退（见 per_run.csv 的 alert_source）。

| 指标 | rule+v1 | rule+v2 |
|---|---|---|
| severe_recall | 0.000 [0.00, 0.00]（0/10） | 0.100 [0.00, 0.33]（1/10） |
| severe_false_alarm | 0.000 [0.00, 0.00]（0/50） | 0.060 [0.00, 0.13]（3/50） |
| calibration_ece | 0.067 [0.02, 0.13]（28.109823/422） | 0.474 [0.41, 0.54]（199.9742/422） |

- `rule+v1`：gold severe 运行 10 个，未告警 10 个（b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d、9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d、c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f、6f7a8b9c-0d1e-4f2a-3b4c-5d6e7f8a9b0c、d4e5f6a7-4444-4d4e-1f4a-4b4c4d4e4f50、c9d0e1f2-4141-4c41-a141-b1b2b3b4b5b6、e1f2a3b4-4343-4e43-c343-d3d4d5d6d7d8、a3b4c5d6-4545-4a45-e545-f5f6f7f8f9a0、d6e7f8a9-5454-4d54-b454-c4c5c6c7c8c9、b0c1d2e3-5858-4b58-f858-a8a9b0c1d2e3）；非 severe 运行告警 0 个。
- `rule+v2`：gold severe 运行 10 个，未告警 9 个（b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d、9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d、c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f、d4e5f6a7-4444-4d4e-1f4a-4b4c4d4e4f50、c9d0e1f2-4141-4c41-a141-b1b2b3b4b5b6、e1f2a3b4-4343-4e43-c343-d3d4d5d6d7d8、a3b4c5d6-4545-4a45-e545-f5f6f7f8f9a0、d6e7f8a9-5454-4d54-b454-c4c5c6c7c8c9、b0c1d2e3-5858-4b58-f858-a8a9b0c1d2e3）；非 severe 运行告警 3 个（b8c9d0e1-8888-4b8c-5d8e-8f9091929394、c5d6e7f8-4747-4c47-a747-b7b8b9c0c1c2、c5d6e7f8-5353-4c53-a353-b3b4b5b6b7b8）。

## 给上游的问题清单（自动生成，方法 `rule`）

### 未被抽取（未对齐）的高风险 gold 结论

| run_id | gold_claim_id | gold | 最高相似度 | 原文片段 |
|---|---|---|---|---|
| f47ac10b-58cc-4372-a567-0e02b2c3d479 | g6 | UNKNOWN | 0.125 | 本次应付赔款 2,144 元 |
| a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d | g5 | UNKNOWN | 0.0 | 预计赔付 6,300 元 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g6 | SUPPORT | 0.1176 | 每次事故免赔额 5,000 元 |
| 4d5e6f7a-8b9c-4d0e-1f2a-3b4c5d6e7f8a | g8 | SUPPORT | 0.1875 | 建议转核赔部门确认既往症认定后决定是否赔付 |
| 5e6f7a8b-9c0d-4e1f-2a3b-4c5d6e7f8a9b | g4 | SUPPORT | 0.2222 | 已结案赔付 32,000 元 |
| 6f7a8b9c-0d1e-4f2a-3b4c-5d6e7f8a9b0c | g4 | REFUTE | 0.2857 | 每月领取年金 86,563 元 |
| 6f7a8b9c-0d1e-4f2a-3b4c-5d6e7f8a9b0c | g7 | CONFLICT | 0.2963 | 保证期内合计给付约 1,038,750 元 |
| 7a8b9c0d-1e2f-4a3b-4c5d-6e7f8a9b0c1d | g2 | REFUTE | 0.0 | 信用限额 1,500 万元 |
| 7a8b9c0d-1e2f-4a3b-4c5d-6e7f8a9b0c1d | g6 | REFUTE | 0.4667 | 预计可赔付 (850,000 × 80% − 10,000) = 670,000 元 |
| 7a8b9c0d-1e2f-4a3b-4c5d-6e7f8a9b0c1d | g7 | UNKNOWN | 0.1667 | 等待期届满后即可正式受理理赔申请 |
| 8b9c0d1e-2f3a-4b4c-5d6e-7f8a9b0c1d2e | g2 | REFUTE | 0.1538 | 保险金额 1,500 万元 |
| 8b9c0d1e-2f3a-4b4c-5d6e-7f8a9b0c1d2e | g7 | REFUTE | 0.0 | 预计可赔付 (920,000 − 50,000) = 870,000 元 |
| b2c3d4e5-2222-4b2c-9d2e-2f2a2b2c2d2e | g1 | SUPPORT | 0.2353 | 每人医疗费用限额 10,000 元 |
| b2c3d4e5-2222-4b2c-9d2e-2f2a2b2c2d2e | g5 | UNKNOWN | 0.0 | 预计可赔付 9,500 元 |
| c3d4e5f6-3333-4c3d-0e3f-3a3b3c3d3e3f | g3 | SUPPORT | 0.1667 | 每次事故免赔额 2,000 元 |
| d4e5f6a7-4444-4d4e-1f4a-4b4c4d4e4f50 | g3 | REFUTE | 0.2308 | 本次赔付 3,000 万元 |
| d4e5f6a7-4444-4d4e-1f4a-4b4c4d4e4f50 | g6 | REFUTE | 0.0833 | 赔付 8,000 万元 |
| e5f6a7b8-5555-4e5f-2a5b-5c5d5e5f6061 | g2 | REFUTE | 0.4667 | 数据恢复费用 350,000 元、营业中断损失 480,000 元（停机 3 天）、第三方索赔 1,200,000 元，合计 2,030,000 元 |
| e5f6a7b8-5555-4e5f-2a5b-5c5d5e5f6061 | g3 | CONFLICT | 0.0 | 一个免赔额 20,000 元 |
| e5f6a7b8-5555-4e5f-2a5b-5c5d5e5f6061 | g7 | CONFLICT | 0.0 | 扣除免赔额后可赔付 (2,030,000 − 20,000) = 2,010,000 元 |
| f6a7b8c9-6666-4f6a-3b6c-6d6e6f707172 | g6 | REFUTE | 0.0556 | 本次赔付 (800,000 − 100,000) = 700,000 元 |
| a7b8c9d0-7777-4a7b-4c7d-7e7f80818283 | g7 | SUPPORT | 0.2128 | 建议等环保局出具正式调查结论后再做理赔判断 |
| b8c9d0e1-8888-4b8c-5d8e-8f9091929394 | g1 | REFUTE | 0.1111 | 保额 5,000 万元 |
| a1b2c3d4-3333-4a33-8333-3e3f3a3b3c3d | g5 | SUPPORT | 0.48 | 本次赔付 (9,800 − 500) = 9,300 元 |
| c3d4e5f6-3555-4c35-a555-5a5b5c5d5e5f | g7 | UNKNOWN | 0.3333 | 如已上牌，正常赔付 22,320 元 |
| d4e5f6a7-3666-4d36-b666-6b6c6d6e6f70 | g3 | CONFLICT | 0.1818 | 第三者财产损失限额 2,000 元 |
| d4e5f6a7-3666-4d36-b666-6b6c6d6e6f70 | g4 | CONFLICT | 0.4 | 交强险赔付 2,000 元 |
| d4e5f6a7-3666-4d36-b666-6b6c6d6e6f70 | g8 | SUPPORT | 0.25 | 合计赔付 59,500 元 |
| e5f6a7b8-3777-4e37-c777-7c7d7e7f8081 | g7 | SUPPORT | 0.48 | 本次赔付 (34,000 − 500) = 33,500 元 |
| f6a7b8c9-3838-4f38-d838-8e8f8a8b8c8d | g6 | SUPPORT | 0.48 | 假设残值 2 万元，则赔付 = 290,000 − 20,000 − 500 = 269,500 元 |
| a7b8c9d0-3939-4a39-e939-9f9a9b9c9d9e | g5 | UNKNOWN | 0.0 | 预计赔付约 40,500 元 |
| b8c9d0e1-4040-4b40-f040-a0a1a2a3a4a5 | g4 | SUPPORT | 0.16 | 一年利息约 18,480 元 |
| e1f2a3b4-4343-4e43-c343-d3d4d5d6d7d8 | g2 | REFUTE | 0.381 | 一切险保额 5,000 万元 |
| e1f2a3b4-4343-4e43-c343-d3d4d5d6d7d8 | g7 | REFUTE | 0.0 | 预计可赔付 (1,850,000 − 50,000) = 1,800,000 元 |
| c5d6e7f8-4747-4c47-a747-b7b8b9c0c1c2 | g4 | CONFLICT | 0.1053 | 本次赔付 80,000 元 |
| a7b8c9d0-5151-4a51-e151-f1f2f3f4f5f6 | g2 | SUPPORT | 0.1176 | 累计已赔 127,000 元 |
| a7b8c9d0-5151-4a51-e151-f1f2f3f4f5f6 | g3 | CONFLICT | 0.1176 | 剩余保额 1,873,000 元 |
| d6e7f8a9-5454-4d54-b454-c4c5c6c7c8c9 | g7 | REFUTE | 0.0571 | 可赔付 1,500,000 元 |
| e7f8a9b0-5555-4e55-c555-d5d6d7d8d9e0 | g1 | REFUTE | 0.1429 | 每次事故限额 2,000 万元，年度累计限额 5,000 万元 |
| e7f8a9b0-5555-4e55-c555-d5d6d7d8d9e0 | g5 | REFUTE | 0.2353 | 累计限额剩余约 3,870 万元 |

### 其他五态不一致（已对齐）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| f47ac10b-58cc-4372-a567-0e02b2c3d479 | g2 | CLM-004 | SUPPORT | UNKNOWN | 生效日 2026 年 1 月 15 日，等待期 30 天，客户 10 月 8 日入院时已远超等待期 |
| f47ac10b-58cc-4372-a567-0e02b2c3d479 | g4 | CLM-006 | SUPPORT | UNKNOWN | 四川大学华西医院（三级甲等公立），符合保单要求的二级及以上公立医院 |
| f47ac10b-58cc-4372-a567-0e02b2c3d479 | g7 | CLM-015 | MISSING_RULE | UNKNOWN | 免赔额不再重复扣除 |
| 7c9e6679-7425-40de-94c0-e315582e7a3b | g2 | CLM-004 | SUPPORT | UNKNOWN | 免疫组化检测尚未完成，最终诊断未出 |
| 7c9e6679-7425-40de-94c0-e315582e7a3b | g3 | CLM-005 | SUPPORT | UNKNOWN | 要求经病理学明确诊断且符合 WHO 恶性肿瘤分类标准 |
| 7c9e6679-7425-40de-94c0-e315582e7a3b | g4 | CLM-006 | SUPPORT | UNKNOWN | 交界性肿瘤和低度恶性肿瘤属于明确除外责任 |
| 7c9e6679-7425-40de-94c0-e315582e7a3b | g5 | CLM-008 | SUPPORT | UNKNOWN | 如果确认为重度恶性肿瘤，在保障范围内 |
| 7c9e6679-7425-40de-94c0-e315582e7a3b | g6 | CLM-012 | SUPPORT | UNKNOWN | 请等医院出具完整病理报告（含免疫组化结果）后，提交给核赔团队继续审核 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g1 | CLM-001 | REFUTE | UNKNOWN | 这笔可以赔 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g3 | CLM-003 | SUPPORT | UNKNOWN | 急性心肌梗死属于保障范围内的重大疾病 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g4 | CLM-004 | SUPPORT | UNKNOWN | 四川省人民医院为三级甲等公立医院 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g5 | CLM-006 | SUPPORT | UNKNOWN | 重疾保额 50 万元 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g6 | CLM-007 | REFUTE | UNKNOWN | 可全额给付 |
| b5d4e3c2-a1f0-4987-8e6d-5c4b3a2f1e0d | g7 | CLM-009 | SUPPORT | UNKNOWN | 请提醒客户准备诊断证明书、心电图报告及心肌酶/肌钙蛋白检测报告提交核赔 |
| 3f2504e0-4f89-41d3-9a0c-0b5e7d8c1f42 | g2 | CLM-006 | SUPPORT | UNKNOWN | 年度免赔额 10,000 元，报销比例 80% |
| 3f2504e0-4f89-41d3-9a0c-0b5e7d8c1f42 | g3 | CLM-007 | SUPPORT | UNKNOWN | 理算引擎计算后剩余部分扣除免赔额，余额 2,680 元按 80% 报销 |
| 9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d | g1 | CLM-001 | REFUTE | UNKNOWN | 这笔可以赔 |
| 9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d | g2 | CLM-003 | REFUTE | UNKNOWN | 被保人张伟确诊肺癌（小细胞癌） |
| 9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d | g3 | CLM-005 | SUPPORT | UNKNOWN | 保额 50 万元 |
| 9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d | g4 | CLM-006 | SUPPORT | UNKNOWN | 医院四川大学华西医院为三级甲等公立医院 |
| 9a1b2c3d-4e5f-4a6b-8c7d-6e5f4a3b2c1d | g5 | CLM-008 | SUPPORT | UNKNOWN | 等待期已过 |
| d8e9f0a1-b2c3-4d4e-5f6a-7b8c9d0e1f2a | g2 | CLM-006 | SUPPORT | UNKNOWN | 重庆西南医院为三级甲等公立医院，符合保单要求 |
| d8e9f0a1-b2c3-4d4e-5f6a-7b8c9d0e1f2a | g3 | CLM-008 | SUPPORT | UNKNOWN | 交警认定对方全责，被保人为乘客 |
| d8e9f0a1-b2c3-4d4e-5f6a-7b8c9d0e1f2a | g6 | CLM-014 | REFUTE | UNKNOWN | 免赔额 100 元 |
| d8e9f0a1-b2c3-4d4e-5f6a-7b8c9d0e1f2a | g8 | CLM-018 | MISSING_RULE | UNKNOWN | 后续医疗费用可在意外医疗保额 10 万元内继续报销 |
| a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d | g2 | CLM-004 | SUPPORT | UNKNOWN | 查勘照片已拍到后备箱变形、后保险杠破损、左尾灯破裂、底盘后部刮擦等主要损伤部位 |
| a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d | g4 | CLM-014 | SUPPORT | UNKNOWN | 修理厂宁波捷达汽车修理厂为二类综合修理厂，符合保单要求 |
| a7b8c9d0-e1f2-4a3b-4c5d-6e7f8a9b0c1d | g6 | CLM-001 | SUPPORT | UNKNOWN | 这笔可以定损 |
| c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f | g2 | CLM-002 | REFUTE | UNKNOWN | 被保人周婷名下有两张定期寿险保单 |
| c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f | g3 | CLM-004 | SUPPORT | UNKNOWN | TERM-240601-4417（守护定期寿险）2024 年 6 月 1 日生效，已过两年自杀免责期，保额 80 万元 |
| c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f | g5 | CLM-008 | SUPPORT | UNKNOWN | 死因心源性猝死属于自然身故 |
| c1d2e3f4-a5b6-4c7d-8e9f-0a1b2c3d4e5f | g6 | CLM-010 | REFUTE | UNKNOWN | 两张保单合计保额 180 万元 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g2 | CLM-004 | SUPPORT | UNKNOWN | 万达广场B1层在保单列明的 5 个经营场所内 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g3 | CLM-006 | SUPPORT | UNKNOWN | 持有有效食品经营许可证（有效期至 2027 年 6 月 30 日），满足扩展条款的承保前提 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g4 | CLM-007 | SUPPORT | UNKNOWN | 卫生部门已确认为沙门氏菌感染导致的食物中毒，12 名顾客受影响 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g5 | CLM-009 | REFUTE | UNKNOWN | 第三者责任险保额 2 亿元 |
| b2c3d4e5-f6a7-4b8c-9d0e-1f2a3b4c5d6e | g8 | CLM-013 | SUPPORT | UNKNOWN | 建议等卫生部门出具最终调查报告后，收集受伤顾客的医疗单据推进核赔 |
| f3a4b5c6-d7e8-4f9a-0b1c-2d3e4f5a6b7c | g2 | CLM-002 | REFUTE | UNKNOWN | 第三者责任保额 2 亿元 |
| f3a4b5c6-d7e8-4f9a-0b1c-2d3e4f5a6b7c | g3 | CLM-004 | SUPPORT | UNKNOWN | 保单附加了地质条件扩展条款和邻近建筑保障条款 |
| f3a4b5c6-d7e8-4f9a-0b1c-2d3e4f5a6b7c | g5 | CLM-006 | SUPPORT | UNKNOWN | 每次事故免赔额 1 万元 |

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
