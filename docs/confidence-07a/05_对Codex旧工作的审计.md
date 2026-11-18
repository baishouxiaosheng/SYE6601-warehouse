# 05 对 Codex 旧工作的审计

版本：2026-11-17。依据：`_claude_work/survey/04_repo_and_codex_audit.md`（对本地仓库只读执行 git 命令和 GitHub 公共 API 的结果）和 Codex 旧对话记录。
目的：说清楚之前 Codex 替 07A 做的东西，哪些继续用、哪些是错的、哪些因为项目转向已经过时。

> 安全提醒：旧对话记录文件里有一行用户当时粘贴的明文密钥。该文件**不要**放进仓库，也不要分享。若密钥还没撤销，请尽快在服务商处撤销并换新。本文不复制任何密钥。

## 1. 背景：项目转向了

| 时间 | 方向 | 07A 当时做了什么 |
|---|---|---|
| 10 月底 ~ 11 月初 | 企业客户故障**补偿**判断（合同、403、DYN-01） | PR #1 评分模块 → PR #4 建链风险 vNext → PR #5/#8 动态补偿 harness |
| 11 月中（本地） | Codex 自行转到“客服回答监督”（物流例子） | 未推送的 `answer_supervision.py` |
| 11-15/16 起 | **工业智能体动态证据图**（本交付） | 新包 `confidence_07a/` |

所以旧代码的大部分**业务语义**已经不适用；能留下的是一些**做法**。

## 2. 做对了、值得保留的（在新包里重写，不直接 import 旧代码）

| 做法 | 旧位置 | 新包里怎么体现 |
|---|---|---|
| 比例统一输出 `{分子, 分母, 值}`，分母为 0 时值为 null，不写 0 | `modules/confidence_a_mvp/confidence_a/metrics.py` 的 `ratio()` | 成绩单三维度和全部评测指标 |
| 门槛（能不能放行）和展示分分开 | 旧 `scoring.py` 的 `gate_passed` | `blockers` + `overall_display=false` |
| 明确声明“分数不是概率、未校准” | 旧 notes、文档 | 每份成绩单的 `score_semantics` |
| 失败的运行留在分母里，不悄悄丢掉 | 旧 `metrics.py` | `runner` 的 `failures` 记为漏抽 |
| 方法分组，不混算 | 旧 `metrics.py` | `experiment_metrics.json` 每方法一行 |
| 引用必须能追到原始工具返回 | `answer_supervision.py`（未推送） | 逐结论 `main_basis` 带 `run_id + 事件 ID + json_path + 指针` |
| “完整的空结果”和“没查完”分开 | `answer_supervision.py` | 阻断项 B5（分页/超时/筛选未生效） |
| 同一 run 和版本的身份校验 | `dynamic_evidence/report.py` 的 IDENTITY | 适配器检查 run_id 一致；成绩单记录 `upstream_versions` |
| 读密钥只走环境变量 | `dynamic_evidence/models.py` | 新包不调用模型，也不读 `.env` |
| “模型提案、代码发布”的分层 | `dynamic_evidence/graph.py` | 与需求 G5 一致；新包评分全部由代码完成 |

## 3. 做错了或有风险的

1. **硬编码演示参数 49**：旧评分“有阻断时最高 49 分”。文档写了“待确认”，但测试把 49 写死，群消息稿也写了“100/100/49”，容易被组员当成标准。新包取消了这个上限：有阻断就直接不显示综合分。
2. **SUPPORT 和 REFUTE 都算“好”**：旧评分对象是“义务”，查明了就算好。新方向评分对象是回答里的结论，“与证据矛盾”说明回答错了，不能算好。
3. **越界实现别人的模块**：`dynamic_evidence/` 写了建链（01A）、审核（02B）、调度（03A）、工具适配（04B）、金标（05A）、基线（06B）、界面（08B）全链路，而 07A 自己的成绩单只有 48 行。后果：
   - 04B 反过来内嵌了 Codex 的合成数据（`loop_b_unified/vendor/pr5_dynamic/`）；
   - 为了集成，改了 04B 的 `loop_b_unified/provider_setup.py` 和根 `README.md`、`.gitignore`，造成 PR #8 冲突；
   - `docs/dynamic-evidence/integration.md` 替其他组员写了“需要交付什么”，容易引起分工摩擦。
4. **方向漂移三次**，最后一次（客服回答监督）不是团队确认的方向。
5. **评测数据不独立**：自建 63 例合成矩阵和金标，金标与被测代码同人同库。
6. **密钥**：用户的密钥没有进入任何仓库或提交（已核实）；但团队的 SiliconFlow 密钥被 06B 写死在仓库文件里（见 `06_对接需求与群消息.md`），这不是 Codex 造成的，但 Codex 发现后只在对话里提了一句，没有形成正式提醒。
7. **自称有 CI 但已消失**：PR #1 说加了 3.10/3.12 自动测试，那个 workflow 随旧 main 一起没了。

## 4. 转向后已经过时的

- 义务（obligation）作为分母；
- 补偿 / 不补偿 / 转人工三类终局；
- DYN-01、合同 24 小时工单条款；
- 63 例合成矩阵和 `evaluate.GOLD`；
- 与 Loop B provider 的耦合；
- 06B `tests/handoff.md` 里“SUPPORT/REFUTE→高、UNKNOWN→中、CONFLICT→低”的置信度映射（REFUTE 不等于高置信，在新方向下作废）；
- 02B 的 `score_bridge_v02.py` 对 PR #4 版本的依赖（PR #4 已不在 main 上）。

## 5. 旧 PR 和本地分支的状态

| 对象 | 状态 | 建议 |
|---|---|---|
| PR #1（`modules/confidence_a_mvp`，0.1 MVP） | GitHub 显示已合并，但**不在当前 upstream/main 历史里** | 视为历史归档，不恢复 |
| PR #4（Cursor 生成的 vNext） | 同上 | 同上；告知 02B 其 `score_bridge_v02` 依赖已失效 |
| PR #5（动态补偿 harness 旧版） | 同上；后来被重提为 PR #8 | — |
| PR #8（`dynamic_evidence/*` + 文档 + CI） | **在当前 main 上**，是 Codex 唯一留存的代码 | 短期不动（04B 的 vendor 和现有 CI 依赖它）。新 PR 中声明“补偿时代遗留，07A 不再维护”；是否删除由 PM 统一决定，**不要在 07A 的 PR 里删** |
| main 被重写 | `upstream/main` 根提交为 `8bff1dd`（10-26），与旧 main 无共同祖先 | 提 PR 前一定要基于最新 `upstream/main`，并在提交前再 fetch 一次 |
| “49 上限” | 只存在于旧分支和 vendored 0.1 版本 | 新包已取消；会上说明作废 |
| harness 代做他人角色 | `dynamic_evidence/` 在 main 上 | 不再扩展；新包只做 07A 的事 |
| 本地提交 `2456120`（分支 `feat/dyn01-reviewed-snapshots`） | 未推送。`reviewed_snapshots.py` 把 `DYN-01` 和版本 `[1,2,3]` 写死 | **不推送**。如需留档，本地另存 patch 后放弃 |
| 未提交改动（`reviewed_snapshots.py` 一行） | 未提交 | 丢弃 |
| 未追踪的 `answer_supervision.py` 及其测试、文档 | 未追踪；例子是物流客服，与工业方向不符 | **不推送**。其中“引用追到回执”“完整性检查”的思路已在新包中重写 |

## 6. 这次具体改了什么

| 方面 | 旧（Codex） | 新（`confidence_07a`） |
|---|---|---|
| 位置 | `modules/confidence_a_mvp/`、`dynamic_evidence/report.py` | 新顶层包 `confidence_07a/`，不碰其他目录 |
| 评分对象 | 补偿义务 | 回答中的原子结论 + 用户目标 |
| 维度 | 基础必查 / 已映射主张 / 条件已判定 / 关系审核 | 需求 §5 的三维：证据支持度、问题回应覆盖度、不确定性表达准确性 |
| 等级 | 0–100 分 + 49 上限 | 三档等级（证据不足 / 附保留说明 / 已建模范围内证据充分），先判门槛 |
| 严重问题 | 无 | 高风险主结论被反驳或过度断言 → `high_risk_alert` |
| 状态来源 | 自己的 harness 判 | 只读上游，不重判 |
| 评测 | 63 例合成 + 自建金标 | 独立 gold（只依据 JSON）、FSR/IAE/缺口/参数、bootstrap 置信区间、校准表 |
| 方法对照 | 普通 prompt / 固定全查（补偿） | 纯规则 / 纯模型 / 混合 + v1/v2 成绩单对照 |
| 模型调用 | 有（OpenRouter） | 无；不读 `.env` |
| 测试 | 依赖 Loop B、在线测试 | 全部离线 unittest，Windows 默认编码下也通过（数量见 `07_测试与自审记录.md`） |
