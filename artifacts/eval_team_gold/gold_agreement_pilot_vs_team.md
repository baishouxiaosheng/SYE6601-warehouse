# 标注一致性：pilot_gold_v0.json vs industrial_gold_v2.json

- 重合运行 15 条；对齐结论 78 对；A 未对齐 27，B 未对齐 4（拆分粒度不同）
- 五态一致率 **0.833**（65/78）；Cohen's kappa **0.740**

| run_id | 原文片段 | A | B |
|---|---|---|---|
| IND-002-r1 | 冷媒压力680kPa | SUPPORT | MISSING_RULE |
| IND-005-r1 | 明天WO-28510和WO-28511共需M12×50共(60×15+32×8) | SUPPORT | MISSING_RULE |
| IND-005-r1 | 明天共需(45×15+24×8)=867只 | SUPPORT | MISSING_RULE |
| IND-005-r1 | 系统提示部分工单的领料预留尚未录入，实际可用量可能比计算值低 | SUPPORT | UNKNOWN |
| IND-015-r1 | 目前还在校准有效期内 | SUPPORT | UNKNOWN |
| IND-019-r1 | 完整的质检报告暂时出不了 | SUPPORT | UNKNOWN |
| IND-027-r1 | 14:05:12 变频器 VFD-102 发生重启事件 | SUPPORT | REFUTE |
| IND-027-r1 | 根本原因为变频器异常重启引起喘振 | REFUTE | UNKNOWN |
| IND-027-r1 | 建议检查 VFD-102 重启原因，确认变频器控制回路稳定性后恢复运行 | REFUTE | MISSING_RULE |
| IND-034-r1 | 安全阀整定压力 2.75 MPa | SUPPORT | REFUTE |
| IND-046-r1 | 镀层厚度、附着力和表面粗糙度三项指标全部达标 | SUPPORT | UNKNOWN |
| IND-053-r1 | 证书有效期至2027年5月 | SUPPORT | UNKNOWN |
| IND-058-r1 | 可以在恢复生产后逐步进行，不影响正常产出 | MISSING_RULE | REFUTE |
