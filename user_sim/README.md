# 用户模拟 Agent

用工业和保险日志中的真实对象，生成一条符合指定画像的用户问题。返回值带场景来源和建议查询的工具；`visible_context.received_at` 取原日志日期加当前时刻，问题里的“今天/昨天”与数据时期一致。整合方把问题送入自己的问答流水线即可。

## Python 接入

```python
from user_sim import generate_question, to_log_record

q = generate_question("insurance", persona="speculator", seed=7, offline=True)
print(q["user_question"])
record = to_log_record(q)  # 含 case_id、run_id、user_question、visible_context、trace、ai_answer
```

领域可选 `industrial`、`insurance`。画像可选 `novice`、`expert`、`speculator`、`reporter`，省略时等权抽取。`intent` 可指定 `status`、`value`、`decision`、`diagnosis`、`compliance`、`aggregate`、`progress`。完整记录格式见 [JSON Schema](schemas/sim_question.v1.schema.json)。

## 演示与命令

在仓库根目录执行。核心模块仅依赖 Python 标准库，演示页另需 Streamlit。

```sh
python -m user_sim --domain industrial --n 3 --offline
python -m user_sim --domain insurance --persona speculator --n 2 --seed 7 --offline --out artifacts/user_sim/questions.jsonl
streamlit run apps/user_sim_demo.py --server.address localhost
python -m user_sim.server --port 8765
```

Streamlit 看板可调用 `render_user_sim_button(key="user_sim", on_generate=callback)`（从 `user_sim.ui` 导入）。新题写入 `st.session_state["user_sim_question"]`，并触发一次 `callback(q)`。本机 HTTP 接口接受 `POST http://127.0.0.1:8765/generate`，JSON 请求体示例为 `{"domain":"insurance","offline":true}`。

## 模型配置与离线备用

| 环境变量 | 用途或默认值 |
|---|---|
| `USER_SIM_API_KEY`、`OPENROUTER_API_KEY` | 按先后顺序取首个已设置的密钥，仅用于鉴权请求头 |
| `USER_SIM_BASE_URL` | 完整端点，默认 `https://openrouter.ai/api/v1/chat/completions` |
| `USER_SIM_MODEL`、`USER_SIM_QUANT` | 默认 `qwen/qwen3.8-27b`、`fp4` |
| `USER_SIM_REASONING` | 默认 `off`（关闭推理，约 1.5 秒出题）；设为 `low`/`medium` 打开推理，较慢 |

指定离线、缺少密钥、请求失败，或两次模型输出均未通过校验时，从匹配领域及画像的备用库抽题。指定意图时也会匹配意图。`generator.note` 给出原因，页面显示“离线备用题”。两领域共 120 张场景卡，备用库 56 条，每个领域和画像组合各 7 条，由真实模型生成并通过同一套校验（`source: llm`），个别缺口用模板补齐（`source: template`），均标 `reviewed: false`。

## 数据与验收

```sh
python -m user_sim.catalog --out user_sim/data/scenarios.json
USER_SIM_API_KEY=... python -m user_sim._regen_bank --per 7   # 用真实模型重建备用库（会覆盖）
python -m unittest discover -s tests/user_sim -t .
```

构建场景卡时可附加 `--loopb-root PATH`，按可唯一定位的原场景补充 SOURCE 实体。模型生成时还会读取仓库原日志，以校验回答中的数值。自动检查覆盖编号、数字和单位、中文占比、日期是否在数据时期内及原题相似度，题目自然度与业务判断仍需人工复核。

默认抽取会在同进程、同领域内避开最近五张卡，候选用尽时允许重复。显式 `seed` 独立于历史，便于复现选材；批量 CLI 从给定种子逐条加一。时间和记录 ID 每次新建，模型服务的实际措辞和延迟取决于提供方。
