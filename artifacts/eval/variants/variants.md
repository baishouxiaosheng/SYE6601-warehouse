# 受控变体实验

## 受控变体结果

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

