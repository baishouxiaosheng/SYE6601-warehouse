# 受控变体实验

## 受控变体结果

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

