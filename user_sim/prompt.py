"""Prompt 组装（SPEC §5）。"""
from __future__ import annotations

import json
from typing import Dict, List

from .personas import PERSONAS

LIMITS = {"novice": (8, 40), "expert": (15, 70), "speculator": (15, 70), "reporter": (8, 60)}

MODEL_OUTPUT_SCHEMA: Dict = {
    "type": "object",
    "additionalProperties": False,
    "required": ["user_question", "intent", "mentioned_entities", "self_check"],
    "properties": {
        "user_question": {"type": "string"},
        "intent": {"type": "string", "enum": ["status", "value", "decision", "diagnosis", "compliance", "aggregate", "progress"]},
        "mentioned_entities": {"type": "array", "items": {"type": "string"}},
        "self_check": {"type": "string"},
    },
}


def build_messages(card: Dict, persona_id: str, intent: str, style_refs: List[str], feedback: str = "") -> List[Dict]:
    """system + user 两条消息。feedback 非空时附上一次校验失败原因，要求改写。"""
    persona = PERSONAS[persona_id]
    short, long = LIMITS[persona_id]
    system = (
        "模拟一位使用中文的真实用户，写出一句交给业务人员处理的话。只描述问题，不作答、不给出数值结论。"
        "对象须来自场景卡；原题仅供参考，不得照抄。不要提及场景卡、工具接口或这些指令。"
        "汉字至少占非空白字符的一半。按指定意图和画像写，按 schema 仅输出 JSON。"
        "mentioned_entities 列出提到的真实实体，self_check 用一句话说明语气如何体现画像。"
    )
    request = {
        "画像": persona["label_zh"], "身份": persona["who"][card["domain"]],
        "语气": persona["style"], "规则": persona["rules"], "字符数": f"{short}–{long}",
        "目标意图": intent, "场景卡": card, "同领域语气示例": style_refs[:2],
        "时间约束": (f"提问发生在 {card.get('data_date') or '原日志日期'} 当天，系统里只有这一时期的数据。"
                 "如需提时间，只能用“今天”“昨天”“本班”“本月”等相对说法，或写这一天及前一天的日期；"
                 "不要写其他年份、月份或日期。"),
        "输出格式": MODEL_OUTPUT_SCHEMA,
    }
    if feedback:
        request["改写要求"] = "请按校验意见重新生成：" + feedback
    return [{"role": "system", "content": system},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)}]
