# 07A 离线评测报告

- 生成时间：2026-11-16T16:49:25+00:00；评测版本：07a-eval-v1
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
| rule_live | 15 | 15 | 15 | 0 | 105 | 110 | 95 | 19 | 20 | 无 |

## 主要指标（值 [95% CI]（分子/分母））

| 指标 | rule_live |
|---|---|
| false_support_strict | 0.286 [0.08, 0.64]（4/14） |
| false_support_broad | 0.111 [0.03, 0.22]（4/36） |
| insufficient_as_err | 0.000 [0.00, 0.00]（0/21） |
| gap_precision | 0.200 [0.07, 0.33]（4/20） |
| gap_recall | 0.211 [0.06, 0.39]（4/19） |
| gap_f1 | 0.205 [0.06, 0.32]（8/39） |
| requery_param_value_hit | 0.093 [0.02, 0.19]（8/86） |
| requery_param_key_hit | 0.128 [0.02, 0.27]（11/86） |
| requery_action_exists | 0.421 [0.17, 0.68]（8/19） |
| status_accuracy | 0.411 [0.29, 0.52]（39/95） |
| status_macro_f1 | 0.285 [0.17, 0.45]（1.426144/5） |
| status_kappa | 0.193 [0.09, 0.31]（0.141385/0.730859） |
| extraction_coverage | 0.905 [0.84, 0.96]（95/105） |
| extraction_extra_rate | 0.136 [0.09, 0.18]（15/110） |
| severe_recall | null（0/0） |
| severe_false_alarm | null（0/0） |
| calibration_ece | null（0/0） |

08B 兼容字段映射：`false_support` = `false_support_strict`，`gap_locate` = `gap_f1`，`insufficient_as_err` = `insufficient_as_err`。

## 方法 `rule_live` 明细

### 五态混淆矩阵（行 = gold，列 = 预测，仅已对齐结论）

| gold \ pred | SUPPORT | REFUTE | UNKNOWN | CONFLICT | MISSING_RULE |
|---|---|---|---|---|---|
| SUPPORT | 22 | 0 | 37 | 0 | 0 |
| REFUTE | 4 | 3 | 7 | 0 | 0 |
| UNKNOWN | 0 | 0 | 13 | 0 | 0 |
| CONFLICT | 0 | 0 | 1 | 0 | 0 |
| MISSING_RULE | 0 | 0 | 7 | 0 | 1 |

分层：run.source 中没有变体信息，未分层（全部视为自然运行）

成本：耗时 n=15，合计=0.044778s，均值=0.002985s，中位数=0.002882s；模型调用：0.0

### 被判为支持的非支持结论（需上游复核）

| run_id | gold_claim_id | pred_claim_id | gold | pred | 原文片段 |
|---|---|---|---|---|---|
| IND-053-r1 | g3 | CLM-004 | REFUTE | SUPPORT | 今天吊装18吨设备没有问题 |
| IND-034-r1 | g6 | CLM-007 | REFUTE | SUPPORT | 安全操作压力上限为 2.5 MPa |
| IND-038-r1 | g1 | CLM-001 | REFUTE | SUPPORT | 废水排放口（OUTLET-01）COD 已超标 |
| IND-058-r1 | g1 | CLM-001 | REFUTE | SUPPORT | E线自动化升级已基本完成 |

## 给上游的问题清单（自动生成，方法 `rule_live`）

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
