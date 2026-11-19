# 用户模拟 Agent（user_sim）设计规范 v1

负责人：07A（本仓库 `user_sim/`）。用途：课堂演示时点一次按钮，自动生成一条“现场人员 / 理赔人员会问的真实问题”，交给整合方的问答与证据链流水线。

## 1. 边界

| 做 | 不做 |
|---|---|
| 生成**问题**，以及和日志同格式的上下文 `visible_context` | 不生成 AI 回答，不生成 trace，不调任何业务工具 |
| 问题落地到日志 / LoopB 里**真实存在**的对象（设备、产线、批次、保单、赔案） | 不编造数据里没有的设备号、保单号 |
| 用 4 种用户画像制造多样性 | 不使用《案例说明 md》（需求 §2 禁止） |
| 给出“建议查询的工具和对象”作为提示，供下游参考 | 不预设答案，问题文本里不能泄露答案或数值结论 |
| 联网失败时退回离线备用题库，保证课堂演示不卡 | 不把密钥写进任何文件、日志、输出 |

## 2. 领域与数据来源

| 领域 | 日志（仓库内） | 上下文字段（与日志一致） |
|---|---|---|
| 工业 `industrial` | `111/工业智能体模拟监控日志_60条(1).json` | `site`、`workshop`、`received_at` |
| 保险 `insurance` | `111/保险智能体日志集_INS-A03至A62_合并.json` | `claim_id`、`policy_id`（可缺）、`received_at` |

LoopB 数据包（`--loopb-root`，可选，不在仓库内）只用来补充实体：`databases/<domain>/*.json` 里 `family == "SOURCE"` 记录的 `lookup` 键值和 `provenance.observed_task_context`。`SIM01`–`SIM09` 等合成兄弟环境的实体名（带 `SIMxx-` 前缀）**不用**，课堂上不好看。

## 3. 场景卡（scenario card）

离线构建一次，提交到仓库：`user_sim/data/scenarios.json`。由 `python -m user_sim.catalog --out user_sim/data/scenarios.json [--loopb-root PATH]` 生成，只用标准库。

每条原始运行生成一张卡：

```json
{
  "scenario_id": "IND-053",
  "domain": "industrial",
  "context": {"site": "北方石化园区", "workshop": "安装工段"},
  "entities": [{"id": "CRANE-02", "kind": "asset", "label": "桥式起重机"}],
  "topic": "吊装作业放行",
  "intent_hints": ["decision", "status"],
  "tools": ["safety.equipment_inspection", "ops.lift_plan", "safety.permit_check"],
  "risk": "high",
  "style_ref": "今天要吊装一个18吨的设备，行车检验过了吗？可以吊吗？"
}
```

字段来源规则：

- `context`：原日志的 `visible_context`，去掉 `received_at`（生成时重新给当前时间）。
- `entities`：从 trace 里 `tool_call.arguments` 的值中取出**标识符样式**的字符串（含字母+数字、或形如 `CLM-…`、`PL-…`、`BT-…`、`Line-D`），以及 LoopB SOURCE 记录的 `lookup` 值；`kind` 由参数名推断（`asset_id/asset_tag/equipment_id→asset`，`line_id→line`，`batch_id/lot→batch`，`material/sku/part→material`，`policy_id→policy`，`claim_id→claim`，其余 `other`）；`label` 取同一 result 里的 `description/name/model` 字段（没有就空）。参数名为 `display_name`/`name`/`equipment_name` 的中文值（如 IND-001 的“三号锅炉”）作为 `kind=asset` 的实体，`id` 与 `label` 都用该中文名。时间、数量、`query`/`collection` 这类参数值不算实体。每卡最多 8 个，去重。
- `topic`：用规则从原问题和工具名生成 2–8 个字的中文主题（如“库存余量”“排放数据”“吊装放行”“理赔责任”“续保状态”）；规则写成关键词表，放在 `catalog.py`。
- `intent_hints`：从原问题按关键词判定，可多个：`status`（状态/正常吗/怎么样）、`value`（多少/几/数值）、`decision`（能不能/可以/可否/放行/开机/赔吗）、`diagnosis`（为什么/原因/怎么回事）、`compliance`（合规/超标/有效期/证书/资质）、`aggregate`（合计/总共/累计/够不够）、`progress`（进度/出来了吗/到哪一步）。
- `risk`：问题或工具名命中 `confidence_07a/policy/scorecard_policy.v2.json` 的 `high_risk.lexicon` 即 `high`，否则 `normal`。直接读这个文件，保持与成绩单口径一致。
- `style_ref`：原问题，**只作风格参考和防抄袭比对**，不作为输出。

## 4. 用户画像（`user_sim/personas.py`，已写好，不要改语义）

| id | 名称 | 特点 |
|---|---|---|
| `novice` | 完全不懂的新人 | 口语、模糊、可能用错术语，不写编号，常问“这个要紧吗” |
| `expert` | 资深工程师 / 核赔 | 精确：带编号、单位、时间窗，可能一次问两件相关的事 |
| `speculator` | 懂系统、会猜的人 | 提到系统或数据源，自带一个假设（可能是错的），要求核实 |
| `reporter` | 只会描述现象的人 | 只说看到/听到/遇到了什么，不直接提问，句尾可能是“你看看” |

默认按权重随机：novice 0.25、expert 0.25、speculator 0.25、reporter 0.25；`persona` 参数可指定。

## 5. 生成流程

```
选场景卡（domain 内随机，可用 seed 复现；跳过最近 5 次用过的）
  → 选画像、选意图（从 intent_hints 里挑一个，没有就 status）
  → 组装 prompt（system + 画像规则 + 场景卡 + 2 条同领域 style_ref 做风格示例 + 输出 JSON schema）
  → 调 OpenRouter（structured outputs）
  → 校验（§7），不通过把错误写回去重试 1 次
  → 仍不通过：退回离线备用题（§8），generator.mode = "offline_fallback"
```

## 6. 模型调用

- 端点：`https://openrouter.ai/api/v1/chat/completions`（可用 `USER_SIM_BASE_URL` 覆盖）。
- 模型：`qwen/qwen3.8-27b`；provider 路由 `{"quantizations": ["fp4"], "allow_fallbacks": true}`（fp4 提供方：Darkbloom、ModelRun、Nebius）。`USER_SIM_MODEL`、`USER_SIM_QUANT` 可覆盖。
- `response_format`：`{"type": "json_schema", "json_schema": {"name": "sim_question", "strict": true, "schema": <§7 的模型输出 schema>}}`。
- `temperature` 0.9，`top_p` 0.95，`max_tokens` 600，`seed` 透传。
- 推理：默认**关闭** `reasoning: {"enabled": false}`。2026-11-19 实测：`effort: low` 时 600 token 常全部用于推理、`content` 为空；关闭后单次约 1.5 秒，问题质量足够。`USER_SIM_REASONING=low|medium` 可重新打开，此时 `max_tokens` 自动提到 2000。
- 密钥：只读环境变量 `USER_SIM_API_KEY`，没有再读 `OPENROUTER_API_KEY`；都没有时 `mode` 直接走离线，并在输出 `generator.note` 里写“未配置密钥”。**不读 .env，不打印、不记录、不写入密钥**；异常信息里出现密钥时要替换为 `***`。
- 请求头：`HTTP-Referer: https://github.com/forest1119/SYE6601-warehouse`、`X-Title: SYE6601 user-sim`。
- 只用标准库 `urllib`；超时 30 秒；网络/HTTP 错误统一转成 `UserSimError`，不抛到 UI。
- 记录 `usage`（prompt/completion tokens）、`latency_s`、`provider`（响应里的 `provider` 字段）。

## 7. 输出格式

### 7.1 模型输出（structured outputs 的 schema）

```json
{"user_question": "string", "intent": "status|value|decision|diagnosis|compliance|aggregate|progress",
 "mentioned_entities": ["string"], "self_check": "string"}
```

`self_check` 是模型一句话自述“为什么这像该画像会问的话”，只记日志、不展示。

### 7.2 对外输出（`user_sim/schemas/sim_question.v1.schema.json`）

```json
{
  "schema": "sim-question.v1",
  "case_id": "SIM-IND-20261119-153012-7f3a",
  "run_id": "SIM-IND-20261119-153012-7f3a-r1",
  "domain": "industrial",
  "user_question": "三号锅炉那边一直在报警，声音挺大的，你帮我看看。",
  "visible_context": {"site": "华东一厂", "workshop": "动力车间", "received_at": "2026-11-19T15:30:12+08:00"},
  "persona": {"id": "reporter", "label_zh": "只会描述现象的人"},
  "intent": "diagnosis",
  "scenario_id": "IND-001",
  "grounding": {"entities": [{"id": "三号锅炉", "kind": "asset", "label": ""}], "suggested_tools": ["ops.alarm_history"], "risk": "normal"},
  "generator": {"mode": "llm", "model": "qwen/qwen3.8-27b", "quantization": "fp4", "provider": "Nebius",
                "prompt_version": "user-sim-prompt-v1", "seed": 7, "attempts": 1, "latency_s": 4.2,
                "usage": {"prompt_tokens": 900, "completion_tokens": 80}, "note": ""},
  "created_at": "2026-11-19T15:30:12+08:00"
}
```

- `case_id` 前缀：工业 `SIM-IND-`，保险 `SIM-INS-`；保证不和真实 `IND-xxx` / `INS-Axx` 冲突。
- `received_at` 用当前时间（Asia/Shanghai，ISO 8601 带 `+08:00`）。
- 保险领域：`visible_context` 带场景卡的 `claim_id`、`policy_id`，与日志一致。
- `to_log_record(q)` 返回下游直接可用的日志记录：`{case_id, run_id, user_question, visible_context, trace: [], ai_answer: ""}`。

### 7.3 校验（`validate.py`，任何一条不过即重试）

1. JSON 可解析，字段齐全，`intent` 在枚举内。
2. 问题是中文为主（汉字占非空白字符 ≥ 50%），长度：novice 8–40、expert 15–70、speculator 15–70、reporter 8–60 个字符。
3. **落地**：expert、speculator 必须至少提到场景卡里 1 个实体（`id` 或 `label` 子串匹配）；novice、reporter 可以只说中文名称（如“三号锅炉”“那台行车”），但不能出现场景卡之外的“编号样式”字符串（正则 `[A-Z]{1,6}-?\d{2,}` 等），防止编造编号。
4. 不泄露答案：不得包含场景卡原日志 `ai_answer` 里出现的数值结论（取原回答里的数字+单位，如“4200件”“218℃”，命中即失败）。原日志里用户自己问题中的数字不算。
5. 不抄原题：与该领域全部 `style_ref` 的字符 bigram Jaccard 相似度 < 0.6。
6. reporter 画像不能以问号结尾超过一句；novice 不能出现工具名（如 `ops.alarm_history`）。

## 8. 离线备用

- `user_sim/data/fallback_questions.json`：每个领域、每种画像至少 6 条，共 ≥ 48 条，**由我们在有网时用本 agent 生成并人工过目后提交**（第一版先用模板生成占位，标记 `"reviewed": false`）。
- 选择规则：同领域 + 同画像（指定时），随机一条，`generator.mode = "offline_fallback"`，`note` 写明原因（无密钥 / 网络失败 / 校验两次未过）。
- 课堂演示时网络出问题，按钮照样出题，界面标一个小字“离线备用题”。

## 9. 对外接口

| 形式 | 签名 / 用法 | 给谁 |
|---|---|---|
| Python | `from user_sim import generate_question, to_log_record`<br>`generate_question(domain="industrial", persona=None, intent=None, seed=None, *, offline=False, transport=None) -> dict` | 整合方（首选） |
| Streamlit 组件 | `from user_sim.ui import render_user_sim_button`<br>`q = render_user_sim_button(key="user_sim", on_generate=None)`：领域切换（工业/保险）、画像选择（随机/四种）、一个“生成一个用户问题”按钮、问题卡片；结果放进 `st.session_state["user_sim_question"]` 并返回；`on_generate(q)` 回调可直接把问题送进下游 | 08B 看板 / 整合方 UI |
| 命令行 | `python -m user_sim --domain insurance --persona speculator --n 3 --out artifacts/user_sim/questions.jsonl [--offline] [--seed 7]` | 批量出题、演示前预热 |
| HTTP（可选，仅本机） | `python -m user_sim.server --port 8765`，`POST /generate` body 同 Python 参数，返回 §7.2 JSON；只绑定 `127.0.0.1` | 非 Python 的整合方 |
| 演示页 | `streamlit run apps/user_sim_demo.py --server.address localhost` | 课堂单独展示 |

`transport` 参数用于测试注入：`transport(url, headers, body_bytes, timeout) -> (status_code, body_bytes)`，默认用 urllib。

## 10. 测试（`tests/user_sim/`，unittest，离线，不联网）

至少覆盖：

1. 场景卡构建：两个领域都能从仓库日志构建；每卡字段齐全；实体抽取对 IND-053（`CRANE-02`）、IND-043（`Line-D`）、一个保险案例（`policy_id`）正确。
2. 请求构造：模型、fp4 路由、json_schema、reasoning 配置、请求头齐全；请求体和日志里都找不到密钥。
3. 正常生成（mock transport 返回合法 JSON）：输出符合 schema，`case_id` 前缀正确，`to_log_record` 结构正确。
4. 校验：各条规则各至少 1 个失败用例（编造编号、泄露答案数字、抄原题、长度越界、reporter 连续提问、novice 出现工具名）。
5. 重试：第一次校验失败、第二次成功 → `attempts == 2`。
6. 回退：无密钥 / HTTP 500 / 超时 / 两次校验失败 → `mode == "offline_fallback"`，不抛异常，`note` 写明原因。
7. 画像覆盖：seed 固定时可复现；不指定画像跑 200 次（mock），四种画像都出现。
8. 异常里的密钥脱敏。
9. CLI 写出 JSONL；HTTP server 用 `127.0.0.1` 起在随机端口，POST 返回 200 与合法 JSON。

运行：`python -m unittest discover -s tests/user_sim -t .`（不要新增 `tests/__init__.py`）。

## 11. 约束

- 只用标准库（Streamlit 只在 `ui.py` 和 `apps/user_sim_demo.py` 里导入，导入失败给清楚的提示）。
- 所有文件读写显式 `encoding="utf-8"`；Windows GBK 下测试也要通过。
- 不修改仓库里任何已有文件；只新增 `user_sim/`、`tests/user_sim/`、`docs/user-sim/`、`apps/user_sim_demo.py`。
- 不读取、不提交任何 `.env`、密钥文件。
