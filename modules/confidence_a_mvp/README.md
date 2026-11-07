# 07A 评分与指标

本模块根据上游已经声明的证据和过程记录输出成绩单，并根据离线评测记录汇总指标。它不决定是否补偿，不重新判断四态，不读取评测 gold，也不调用模型给答案打分。

当前有两个契约：

- `0.1-draft`：已合并的义务快照。等权查明比例，阻断时展示分默认不超过 49。
- `0.2-draft`：动态建链投影。先硬门槛，再给出「证据不足 / 附保留说明 / 已建模范围内证据充分」。

0.1 快照仍然可以评分。它们不会被自动升级成 0.2，因为升级必须由证据链 B 和 Loop 补上必查、主张映射、关系审核、剪枝和范围声明。

等级和设计分表示**已声明范围内的证据与过程质量**。它们不证明图完整，不证明发现了全部规则，也不是答案正确概率。没有「完全可靠」这一档。

业务规则和若干展示开关仍待确认，见 [待团队确认](docs/03_待团队确认.md)。

## 先运行

Python 3.10 或以上，标准库即可。在本目录执行：

```sh
python tools/run_demo.py
```

测试通过后，`outputs/` 里会有 0.1 成绩单、0.2 成绩单、Markdown 模板和两份演示指标。这些数字只验证公式。

也可以分开运行：

```sh
python -m unittest discover -s tests -v
python -m confidence_a score examples/v2/01_missing_baseline.input.json --policy policy.graph.demo.json --output outputs/missing_baseline.json
python -m confidence_a score examples/v2/06_dyn01_before_ticket.input.json --output outputs/dyn01_before.json
python -m confidence_a score examples/v2/07_dyn01_after_ticket.input.json --output outputs/dyn01_after.json
python -m confidence_a render outputs/dyn01_before.json --output outputs/dyn01_before.md
python -m confidence_a metrics examples/runs.v2.json --output outputs/metrics.v2.json
```

输入错误返回 2，不写新文件。不要把上一次成功的文件当成这一次的结果。

## 0.2 反例

| 样例 | 预期 |
|---|---|
| [漏建客户合同必查](examples/v2/01_missing_baseline.input.json) | 其他节点可以全部通过，仍然是证据不足，不能满分 |
| [条款已发现但未展开](examples/v2/02_unexpanded_clause.input.json) | 未展开，不称条件已齐 |
| [关键 403，另有辅助证据](examples/v2/03_critical_access_denied.input.json) | 辅助证据不能抵消 403 |
| [证据充分的否定建议](examples/v2/04_ineligible_sufficient.input.json) | ineligible 可以是已建模范围内证据充分 |
| [非关键剪枝](examples/v2/05_pruned_reservation.input.json) | 附保留说明，不自动升级 |
| [DYN-01 工单未取](examples/v2/06_dyn01_before_ticket.input.json) | 新的 24 小时条件是关键缺口 |
| [DYN-01 工单已取](examples/v2/07_dyn01_after_ticket.input.json) | 按 B 的新状态重算，版本与取回前不同 |
| [分页未完](examples/v2/11_critical_pagination.input.json) | 未完成分页阻断否定建议 |

0.1 的三个样例仍是：建议补偿 100、有证据地不建议补偿 100、关键合同未知时原始 80 展示 49。

## 接口

```python
from confidence_a import ContractError, adapt_v01_to_v02, evaluate_runs, score_snapshot

try:
    card = score_snapshot(snapshot)
except ContractError as error:
    show_contract_error(str(error))
else:
    show_scorecard(card)

report = evaluate_runs(run_payload)
```

- 评分逻辑：[docs/00_评分逻辑.md](docs/00_评分逻辑.md)
- 接口：[docs/01_接口草案.md](docs/01_接口草案.md)
- 指标：[docs/02_指标口径.md](docs/02_指标口径.md)
- 待确认：[docs/03_待团队确认.md](docs/03_待团队确认.md)
- 演示命令：[docs/04_联调与群消息.md](docs/04_联调与群消息.md)
- 复核记录表：[docs/05_复核体验记录.md](docs/05_复核体验记录.md)

修改契约后运行 `python tools/make_examples.py`，再跑测试。生成器会覆盖本模块的演示输入、成绩单和 schema。

## 目录

```text
confidence_a/     0.1 与 0.2 的评分、契约、指标、模板
docs/             口径、接口、指标、待确认、复核表
examples/         0.1 样例；examples/v2 为建链反例
schemas/          与程序同源的 JSON Schema
tests/            0.1 回归与 0.2 反例
policy.demo.json          0.1 演示参数
policy.graph.demo.json    0.2 演示参数
outputs/          本地运行产物，不纳入 Git
```
