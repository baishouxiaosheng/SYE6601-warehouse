# 新规则与 Loop B 接口核对（2026-11-13）

核对基线：main 04da37d906ff359317033b56c970d69cd902721b；
base_rules_registry.json、GraphProposal_Schema.json 和 Loop B 当前实现。
本文件是工程核对，不是业务签认或测试标准答案。

## 已直接修正

- 说明统一为根目录 loop_b_unified；旧上传和删除指引改为当前状态。
- 增加包入口，可在仓库根目录导入 create_provider 和 make_review_packet；原 PyCharm 演示方式保留。
- 增加只读核对程序，区分名称匹配、待确认对应、未实现来源。

## 来源名称

| 新规则要求 | 当前工具 | 状态与负责人 |
| --- | --- | --- |
| CRM_CONTRACT_DB | 同名 | 名称匹配；不代表全部业务字段已满足 |
| MAINTENANCE_CALENDAR | 同名 | 名称匹配；维护计算口径和材料还缺 |
| MONITORING_SYSTEM | INCIDENT_DB | 仅为候选对应，证据链组与 Loop A 确认后才能路由 |
| TICKET_SYSTEM | TICKET_DB | 仅为候选对应，确认后仍委托 PR5 工单实现 |
| FINANCE_ZONE_DB | 无 | 需要身份原始材料、返回格式和测试案例，再由 Loop B 补工具 |
| KA_CLIENT_DB | 无 | 同上，不从客户编号猜身份 |
| TRIAL_ACCOUNTS_DB | 无 | 同上，不从场景标签造身份 |
| SANDBOX_LOGS | 无 | 需要原始沙盒记录及范围说明 |

POLICY_DB 是已有通用政策来源，新规则 target_source 中未直接列出不等于应删除。
本次不启用 MONITORING_SYSTEM/TICKET_SYSTEM 别名，不补造四个缺失来源的数据。

## 请求、引用与快照

| 检查项 | 实际情况 | 需要谁处理 |
| --- | --- | --- |
| 任务参数 | GraphProposal仅强制 task_id/run_id/question；工具另需 customer_id/incident_id/event_time | Loop A 查询前补全；缺值不能替换成演示客户 |
| 客户类型、套餐 | 新规则使用 customer_tier/plan_type；现有冻结材料未提供完整身份与套餐证明 | 规则／数据负责人签认材料，再由 Loop B 提供原始查询 |
| 来源与记录 | 工具 source_id 是文档ID，source_type 是工具来源，record_id 是记录ID | 建链器保留含义，不把来源枚举当文档ID |
| 原文定位 | 工具 locator 为含 start/end/unit 的对象；GraphProposal source_locator.locator 为字符串 | 证据链组确认编码或修改提案格式；本次不丢弃偏移或伪造字符串 |
| 四态 | SUCCESS/FORBIDDEN/TIMEOUT/ERROR是工具状态，不是支持／反驳等四态 | Checker负责证据四态，Loop B保持原回执 |
| 图与版本 | 提案 graph_version 是字符串；人工包接收审核后的整数 graph_version/answer_version | Loop A提供终止快照及版本对应；不能简单把提案强转成快照 |
| 免责节点 | 注册表 node_type 有 exemption；提案 type 枚举没有 exemption | 证据链组确认如何表示，Loop B不改建图语义 |
| 停止与升级 | 提案没有 stop_reason/recommendation/workflow_status 等终止信息 | Loop A传入make_review_packet，不能从工具日志猜 |

## 维护和阈值

新VIP表达式是 incident_minutes - planned_maintenance_minutes >= 30；
现有PR5材料有90分钟专属合同例子，而新注册表写30分钟。
这可能是不同合同或规则版本，不能直接覆盖原文。
请规则负责人明确每个案例的政策、专属合同、有效期、覆盖优先级和预期结果。

现有 planned 表示计划维护事实，不等于 excluded（免责结论），也不提供足够的
维护区间、与故障重叠区间和扣除分钟数。规则负责人决定扣除口径；数据负责人
提供故障/维护起止时间及适用范围；Loop B返回原始记录，Checker负责验证和计算。
工单提交时刻继续复用PR5；提交间隔由审核层结合故障时间算，不由工具直接给补偿结论。

## 联调还需要

1. Loop A／组长给出当前控制器正式位置。核对的main不含dynamic_evidence目录，完整集成暂缺依赖。
2. Loop A给一份真实调用请求和审核后的终止快照，保留task/run/call编号与版本对应。
3. 证据链组确认来源名称、引用格式、身份材料以及维护与合同阈值口径。
4. 测试组提供独立标准答案，确认先测哪些来源与案例。历史13例模拟一致性不是正式验收。

核对程序只读仓库配置，既不修改规则也不把待确认对应自动启用。
