"""Template scorecard text. It restates recorded fields and does not judge them."""

from .contracts import VERSION, ContractError
from .contracts_v02 import VERSION_V02


def _line(text):
    return " ".join(str(text).split())


def _refs(item):
    parts = []
    for key, label in (
        ("claim_ids", "主张"), ("obligation_ids", "条件"), ("evidence_ids", "证据"),
        ("relation_ids", "关系"), ("clause_ids", "条款"), ("baseline_ids", "必查"),
        ("change_ids", "结构变化"),
    ):
        if item["refs"].get(key):
            parts.append(label + " " + ", ".join(item["refs"][key]))
    return "；".join(parts)


def render_scorecard_v02(card):
    lines = [
        "# 证据与过程成绩单",
        "",
        f"- 任务 `{card['task_id']}` / 运行 `{card['run_id']}`",
        f"- 图版本 `{card['graph_version']}` / 答案版本 `{card['answer_version']}` / 评分版本 `{card['scoring_version']}`",
        f"- 版本一致：{'是' if card['version_consistent'] else '否'}",
        f"- 业务结果：`{card['recommendation']}`；流程状态：`{card['workflow_status']}`",
        f"- 等级：**{card['level']}**（`{card['level_code']}`）",
        f"- 设计分：{'不展示' if card['display_score_suppressed'] else card['score']}；原始设计分：{card['raw_design_score']}",
        f"- 可展示确定建议：{'是' if card['may_present_definitive_decision'] else '否'}",
        "",
        card["score_semantics"],
        "",
        "## 等级原因",
    ]
    lines.extend(f"- {_line(reason)}" for reason in card["level_reasons"])
    lines.extend(["", "## 分项"])
    for key, dim in card["dimensions"].items():
        lines.append(
            f"- {dim['label']}（{key}）：{dim['numerator']}/{dim['denominator']}"
        )
    lines.extend(["", "## 建链风险"])
    if card["graph_build_risks"]:
        for risk in card["graph_build_risks"]:
            lines.append(f"- `{risk['code']}` {_line(risk['reason'])}")
    else:
        lines.append("- 本次输入没有记录到建链风险。这不证明图完整。")
    lines.extend(["", "## 残留缺口"])
    if card["residual_gaps"]:
        for gap in card["residual_gaps"]:
            prune = f"；剪枝：{gap['prune_source']} {_line(gap['prune_reason'])}" if gap["pruned"] else ""
            lines.append(f"- `{gap['obligation_id']}` {gap['status']} {_line(gap['reason'])}{prune}")
    else:
        lines.append("- 没有仍为 UNKNOWN 或 CONFLICT 的已识别条件。")
    lines.extend(["", "## 保留项"])
    if card["reservations"]:
        for item in card["reservations"]:
            lines.append(f"- `{item['code']}` {_line(item['reason'])}")
    else:
        lines.append("- 无。")
    lines.extend(["", "## 补证与结构变化"])
    if card["repair_actions"]:
        for action in card["repair_actions"]:
            lines.append(f"- `{action['action_id']}` {_line(action['summary'])}（目标来源 {action['target_source']}）")
    else:
        lines.append("- 上游未提供补证动作。评分器不编造工具。")
    if card["advice_change_notes"]:
        lines.extend(f"- {_line(note)}" for note in card["advice_change_notes"])
    lines.extend(["", f"## 停止原因", "", _line(card["stop_reason"] or "核查中，上游未给停止原因。"), "", "## 优先复核顺序"])
    if card["human_review_order"]:
        for item in card["human_review_order"]:
            where = _refs(item)
            suffix = f"（{where}）" if where else ""
            lines.append(f"{item['order']}. `{item['code']}` {_line(item['reason'])}{suffix}")
    else:
        lines.append("- 硬门槛和保留项都没有需要排序的记录。")
    scope = card["scope_declaration"]
    lines.extend([
        "", "## 范围声明", "",
        f"- `{scope['scope_id']}` {scope['status']}：{_line(scope['statement'])}",
        "- 已知限制：" + "；".join(_line(item) for item in scope["known_limits"]),
        "", "## 固定声明",
    ])
    lines.extend(f"- {_line(note)}" for note in card["notes"])
    lines.append("")
    return "\n".join(lines)


def render_scorecard_v01(card):
    lines = [
        "# 证据评分卡（0.1）",
        "",
        f"- 任务 `{card['task_id']}` / 运行 `{card['run_id']}` / 快照 `{card['snapshot_id']}`",
        f"- Checker 结论：`{card['checker_decision']}`；流程：`{card['process_state']}`",
        f"- 展示分：{card['score']}；原始分：{card['raw_score']}；门槛通过：{'是' if card['gate_passed'] else '否'}",
        f"- 可展示确定结论：{'是' if card['may_present_definitive_decision'] else '否'}",
        "",
        card["score_semantics"],
        "",
        "## 阻断",
    ]
    if card["blockers"]:
        lines.extend(f"- `{item['code']}` {_line(item['reason'])}" for item in card["blockers"])
    else:
        lines.append("- 无。")
    lines.append("")
    return "\n".join(lines)


def render_scorecard_markdown(card):
    if not isinstance(card, dict):
        raise ContractError("scorecard: expected object")
    version = card.get("schema_version")
    if version == VERSION_V02:
        return render_scorecard_v02(card)
    if version == VERSION:
        return render_scorecard_v01(card)
    raise ContractError(f"scorecard.schema_version: unsupported {version!r}")
