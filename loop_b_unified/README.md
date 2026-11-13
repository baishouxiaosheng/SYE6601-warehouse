# Loop B 统一入口

当前仓库目录是根目录下的 `loop_b_unified/`，不是 `modules/loop_b_unified/`。
本修订依据 main 提交 04da37d906ff359317033b56c970d69cd902721b（2026-11-13）。
PR #7 已合并；无需重新打开 PR #6，也不要重新上传旧版 loop_b_mock。

## 在 PyCharm 运行

打开整个项目或 loop_b_unified 文件夹。右键 run_raw_demo.py 运行独立演示，
结果保存在本模块 raw_outputs/本次编号/。右键 test_raw_evidence.py 运行原有31项开发检查。
无需模型密钥，仅用 Python 标准库。根 main.py 当前仍是示例文件，不是本模块入口。

## Loop A 从仓库根目录调用

```python
from loop_b_unified import create_provider, make_review_packet

provider = create_provider(log_path="outputs/calls.jsonl")
task = {
    "task_id": "TASK-001", "run_id": "RUN-001",
    "customer_id": "C-DEMO", "incident_id": "I-DEMO",
    "event_time": "2026-10-01T00:00:00Z"
}
receipt = provider("CRM_CONTRACT_DB", task)
```

每次运行创建一个 provider；由 Loop A 选择工具和传回下一页游标。
正式工单沿用 PR5：可注入 `pr5_ticket_provider`；内置 vendor 固定副本用于独立演示。
在模块文件夹内仍可使用 `from provider_setup import create_provider`，兼容现有演示。

## 文件和职责

- provider_setup.py：构建查询入口；raw_evidence.py：原文、引用、分页、异常和日志。
- review_handoff.py：接收 Loop A 的停止快照，整理人工复核包。
- runtime_data/：冻结合成材料；vendor/pr5_dynamic/：保留来源与许可的 PR5 固定副本。
- tool_registry.json：五个当前支持的来源；examples/raw/：历史开发样例。
- UNIFIED_HANDOFF.md：详细接口；INTERFACE_ALIGNMENT.md：对照新规则的差异和待确认项。
- check_team_interfaces.py：只核对接口，不调用模型，不输出补偿结论。

本模块不建图、不计算四态、不改变补偿规则、不选择重试或停止。
原31项检查和历史13例模拟对接（12例结论一致）都不是正式团队验收。
维护 planned/excluded 语义待确认；现有材料也不足以计算新规则要求的维护扣除分钟数。

## 核对最新规则

在仓库根目录运行：

```text
python loop_b_unified/check_team_interfaces.py --team-root .
```

报告保存到 raw_outputs/interface_alignment.json。退出码0表示核对程序执行成功，
不表示待确认接口已解决。加 --strict 时，有未解决项会返回退出码1。
开发核对报告不应整份输入业务模型。

## 完整流程对接

run_raw_integration.py 需要包含 dynamic_evidence/controller.py 的团队项目，
用 --team-root 指定。当前核对的 main 没有该目录；不能宣称已在此 main 跑通完整流程。
请 Loop A／组长确认正式控制器位置和终止快照。

## 更新 GitHub

在基于最新 main 的工作分支，从仓库根目录上传本修订增量包里的整个 loop_b_unified 文件夹。
应出现 loop_b_unified/README.md，不能出现 modules/loop_b_unified 或双层 loop_b_unified。
增量包仅含本次修改，不必再上传全部旧文件。合并后以本 README 为当前入口说明。
