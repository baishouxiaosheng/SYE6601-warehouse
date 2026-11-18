# confidence_07a —— 置信度组 A（07A）模块

> **分数含义**：本模块输出的所有分数，都是“基于现有日志的证据审核结果”，**不是回答正确的概率**。
> 等级只覆盖上游已经建模的条件，不能证明证据图完整，也不能证明已发现全部适用规则。
> 权重、阈值、等级线、词典目前都是 **PROVISIONAL（暂定，待团队确认）**，没有用独立标注数据校准过。

## 1. 07A 在新方向里做什么

项目已经从“故障补偿”转到“工业智能体动态证据图”（需求说明 2026-11-16 版）。07A 负责两件事：

| 部分 | 做什么 | 读什么 | 产出什么 |
|---|---|---|---|
| 在线成绩单（scorecard v2） | 把上游对一次运行的审核结果，按代码规则汇总成可追溯的成绩单 | 01A 的 graph/plan JSON（或 06B 结果文件），可选叠加 02B 局部检查，可选日志原文 | 每个 run 一份 `<run_id>.json` + `.md`，目录汇总 `summary.csv` |
| 离线评测（eval） | 用独立标注（gold）对照多种方法的结果，计算需求 §6 的指标 | 各方法的逐运行结果 + gold | `experiment_metrics.json`（08B 可直接读）、`report.md`、`per_claim.csv`、`per_run.csv` |

07A **不做**的事：

- 不重新判断结论的五态。状态一律来自上游（01A 的 `evidence_status`，或明确匹配上的 02B 检查）。上游判错由评测指标暴露，并写进给上游的问题清单。
- 不调用模型打分。所有分数由代码计算。
- 在线成绩单不读 gold，也不读《案例说明 md》。
- 不读取任何 `.env`，不需要密钥。
- 不修改其他成员的代码。01A 自带的 `egraph/scorecard.py`（v1）保留为对照基线。

## 2. 快速开始

在 `deliverable/`（将来是仓库根目录）下运行。只需要 Python ≥ 3.10，无第三方依赖。

```bash
# 0) 跑 07A 测试（无网络、无密钥；在仓库里不要用 -s tests，以免收进 06B 的在线测试）
python -m unittest discover -s tests/confidence_07a -t .

# 1) 给单个运行打分（01A 输出的 graph + plan；--log 提供回答原文和字段指针）
python -m confidence_07a score \
    --graph <01A output>/IND-043_graph.json --plan <01A output>/IND-043_plan.json \
    --log "111/工业智能体模拟监控日志_60条(1).json" \
    --out-json s.json --out-md s.md
#    可选：--b-review <02B results/industrial_results.json> 叠加 02B 局部检查
#    可选：--policy <自定义 policy JSON>

# 2) 给整个目录打分（自动识别 01A output/ 目录或 06B results/evidence_rule/ 目录）
python -m confidence_07a score-dir \
    --input <01A output 或 06B results/evidence_rule> \
    --log "111/工业智能体模拟监控日志_60条(1).json" \
    --out artifacts/scorecards_v2/rule

# 3) 补证前后对比
python -m confidence_07a diff --before before.json --after after.json --out-json d.json --out-md d.md

# 4) 离线评测 / 受控变体 / 报告（由 confidence_07a/eval/cli.py 提供；参数以 --help 为准）
python -m confidence_07a eval --help
python -m confidence_07a variants --help
python -m confidence_07a report --help
```

- 如果要用 `python -I`（隔离模式），把 `python -m confidence_07a` 换成 `python -I tools/run_cli.py`。
- `eval/variants/report` 三个子命令分派到 `confidence_07a/eval/cli.py`。该文件不存在时，命令返回 2 并给出提示。实验命令和结果见 `docs/confidence-07a/03_评测与指标.md` §实验结果。
- 需要现跑 01A 引擎时，代码固定使用 `load_settings({"mode":"rule"}, env={})`，不会读 `.env`，也不会调模型。

Python 调用：

```python
from confidence_07a import score_run, diff_scorecards, load_policy
from confidence_07a.adapters.egraph_v1 import load_run_from_files
from confidence_07a.logs import load_logs

logs = load_logs("111/工业智能体模拟监控日志_60条(1).json")
run = load_run_from_files("IND-043_graph.json", "IND-043_plan.json", log_record=logs["IND-043-r1"])
card = score_run(run, load_policy())
print(card["grade"], card["support_score"], card["high_risk_alert"])
```

## 3. 目录说明

```
confidence_07a/
  __init__.py              导出 score_run / diff_scorecards / load_policy / evaluate / __version__
  __main__.py              命令行：score / score-dir / diff / eval / variants / report
  model.py                 统一数据模型 RunView（评分和评测只依赖它）
  logs.py                  读工业日志 JSON（run_id -> 原始记录）
  expression.py            回答措辞分类：DEFINITE / HEDGED / DECLARED_UNKNOWN / SCOPED_PARTIAL
  scorecard.py             成绩单 v2：三维度、阻断项、保留项、严重问题、等级；补证前后 diff
  render.py                成绩单和 diff 转 Markdown
  policy/
    scorecard_policy.v2.json   权重、矩阵、词典、门槛（PROVISIONAL）
  adapters/
    egraph_v1.py           01A graph/plan、06B 结果文件 -> RunView（上游字段改名只改这里）
    b_review.py            02B 局部检查覆盖层（可选，默认不开）
  eval/
    gold.py                gold 读取、校验、空白模板
    align.py               预测结论与 gold 结论对齐
    metrics.py             指标、bootstrap 置信区间、校准表
    report.py              experiment_metrics.json / report.md / csv
    runner.py              离线跑 01A rule 模式；读取已有结果目录
    schema_check.py        标准库 JSON Schema 校验
    eval_config.v1.json    评测参数（PROVISIONAL）
    （cli.py、variants.py 等由并行任务补充）
  schemas/
    scorecard.v2.schema.json / gold.v1.schema.json / experiment_metrics.v1.schema.json
tests/confidence_07a/      unittest；fixtures 只来自工业日志 JSON 和 01A rule 模式输出
docs/confidence-07a/       中文文档（00 总览 ~ 08 PR 说明草稿）
gold/                      gold 模板（60 条）与 AI 起草的试点标注（15 条，DRAFT）
tools/                     run_cli.py（-I 启动器）、demo_g6_ind043.py（补证演示）、compare_v1_v2.py
artifacts/                 已生成的成绩单、G6 演示、评测输出
```

## 4. 哪些是暂定的（PROVISIONAL）

下面这些都**没有经过团队确认**，也没有用独立数据校准。改动方式和影响见 `docs/confidence-07a/04_待团队确认.md`。

| 内容 | 位置 |
|---|---|
| 综合分权重 support 0.5 / coverage 0.25 / uncertainty 0.25 | `policy/scorecard_policy.v2.json` → `weights` |
| 措辞 × 状态 打分矩阵 | 同上 → `expression_matrix` |
| 措辞词典、高风险词典 | 同上 → `expression.*_lexicon`、`high_risk.lexicon` |
| 哪些高风险依据算“严重问题” | 同上 → `high_risk.severe_bases` |
| 阻断项、保留项的触发条件 | 同上 → `gates` |
| 词面兜底关联阈值 0.5 | 同上 → `linkage.min_overlap` |
| 评测对齐阈值、缺口类型相容组、bootstrap 次数 | `eval/eval_config.v1.json` |
| 试点 gold（15 条） | `gold/pilot_gold_v0.json`：**AI 起草，DRAFT，必须由 05A 人工复核或重做** |

## 5. 分数语义声明（每份成绩单都带）

每份成绩单都有 `score_semantics` 和 `scope_note` 两个字段，内容来自 policy：

- 分数是“基于现有日志的证据审核结果”，不是回答正确的概率；未经独立标注数据校准前，不能解读为正确率。
- 等级只有三档：证据不足 / 附保留说明 / 已建模范围内证据充分。没有“完全可靠”。
- 有阻断项时 `overall_display=false`，对外只显示等级和分项，不显示综合分。
- 结论状态由上游给出，07A 不重新判断；未被抽取的结论、未被发现的规则、日志外事实都不在评价范围内。

## 6. 相关文档

| 文档 | 内容 |
|---|---|
| `docs/confidence-07a/00_总览.md` | 新方向的项目架构、各角色接口、07A 的位置 |
| `docs/confidence-07a/01_评分规范.md` | 成绩单 v2 的评分规则 |
| `docs/confidence-07a/02_接口契约.md` | 上游字段映射、输出字段、命令行 |
| `docs/confidence-07a/03_评测与指标.md` | 离线评测、指标字典、实验结果 |
| `docs/confidence-07a/04_待团队确认.md` | 需要团队拍板的事项 |
| `docs/confidence-07a/05_对Codex旧工作的审计.md` | 旧代码哪些保留、哪些作废 |
| `docs/confidence-07a/06_对接需求与群消息.md` | 向各组员要什么、给什么；群消息稿 |
| `docs/confidence-07a/07_测试与自审记录.md` | 测试数量与自审结果 |
| `docs/confidence-07a/08_PR说明草稿.md` | 提 PR 的说明和步骤 |

## 7. 真实模型对照（可选，需要密钥）

```bash
# 纯模型（llm_only）与混合（hybrid，01A 引擎）批量运行；支持断点续跑（已成功的运行自动跳过）
python -I tools/run_model_methods.py --log <工业日志.json> --engine <01A 引擎目录> \
    --out-root artifacts/model_runs --all --methods llm_only,hybrid --model qwen/qwen3.8-27b --max-calls 600
# 密钥：环境变量 CONFIDENCE_07A_LLM_API_KEY；或 --key-file 一次性文本文件（跑完自动删除）；都没有则终端提示输入
# 端点：--base-url（默认 OpenRouter），不读取任何 .env

# 纯规则 vs 纯模型同口径对照（只比较“已有模型结果 ∩ gold”的运行）
python -I tools/eval_model_compare.py --log <工业日志.json> --gold gold/team_v2/industrial_gold_v2.json \
    --engine <01A 引擎目录> --llm-dir artifacts/model_runs/llm_only --out artifacts/eval_model_compare_team_gold

# 两份 gold 的一致性（五态一致率、Cohen's kappa）
python -I tools/gold_agreement.py <gold_A.json> <gold_B.json> --out <报告.md>

# G6 补证前后演示（夜班取 LoopB 种子记录 SIM-D-20261113-NIGHT）
python -I tools/demo_g6_ind043.py --eg-root <01A 引擎目录> --log <工业日志.json> \
    --loopb-shift-file <LoopB>/approved_seed/databases/industrial/shift_outputs.json --out artifacts/demo_g6
```

本次已跑：llm_only 33/60 条（用户决定提前停止），全部在 05A 团队 gold 范围内；hybrid 未跑。结果见 `docs/confidence-07a/03_评测与指标.md` §F2。

## 8. 给 08B 的两个兼容点

- 看板读 **`artifacts/experiment_metrics.json`**：顶层是**行列表**（08B `load_experiment_metrics()` 可直接读），基于 05A 团队 gold，工业/保险按 `domain` 分行。各评测目录里另有带分子分母和置信区间的 `experiment_metrics.full.json`。`artifacts/eval/` 是旧的试点结果，不要再给看板用。
- 成绩单 v2 同时给出布尔 `high_risk_alert` 和可直接展示的中文 `high_risk_alert_text`（无严重问题时为空串）。
