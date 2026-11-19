"""输出校验（SPEC §7.3）。"""
from __future__ import annotations

import re
import unicodedata
from functools import lru_cache
from typing import Dict, List

from .prompt import LIMITS, MODEL_OUTPUT_SCHEMA

HAN = re.compile(r"[\u3400-\u9fff\U00020000-\U0002FA1F]")
TOKEN = re.compile(r"(?<![A-Za-z0-9_-])[A-Za-z][A-Za-z0-9]*(?:[_.-][A-Za-z0-9]+)*(?![A-Za-z0-9_-])")
TOOL = re.compile(r"[A-Za-z_]\w*\.[A-Za-z_][A-Za-z_0-9]*", re.ASCII)
UNITS = (
    "亿元 万美元 万元 美元 泰铢 元 万 千瓦时 元/kWh 元/月 ℃ °C 摄氏度 度 分贝 "
    "mg/m3 mg/L μg/m3 mm/s L/min kWh kvar kPa MPa Pa kW kV Hz ppm dB kg mm cm μm "
    "CNY THB HRC m3 L A V % 立方米 毫米 米 公斤 吨 亩 片/小时 件 只 支 片 个 条 位 "
    "人 名 起 层 批 台 份 笔 次 岁 周岁 级 倍 年 个月 月 日 天 周 小时 分钟 秒"
).split()


def _normalize(text):
    return re.sub(r"(?<=\d),(?=\d{3}(?:\D|$))", "", unicodedata.normalize("NFKC", text))


_UNIT_PATTERN = "|".join(re.escape(_normalize(u)) for u in sorted(UNITS, key=len, reverse=True))
_MEASUREMENT = re.compile(r"(?<![A-Za-z0-9.])([+-]?\d+(?:\.\d+)?)\s*(" + _UNIT_PATTERN + r")(?![A-Za-z])")


def _measurements(text):
    return {value + unit for value, unit in _MEASUREMENT.findall(_normalize(text))}


def _answer_numbers(row):
    return sorted(_measurements(row["ai_answer"]) - _measurements(row["user_question"]))


@lru_cache(maxsize=4096)
def _bigrams(text):
    return frozenset(zip(text, text[1:]))


def _date_errors(question, data_date):
    """显式日期只能落在原数据日期当天或前一天（年份、月份必须一致）。"""
    if len(data_date) < 10:
        return []
    year, month, day = int(data_date[:4]), int(data_date[5:7]), int(data_date[8:10])
    for y in re.findall(r"(\d{4})\s*年", question) + re.findall(r"(\d{4})-\d{1,2}-\d{1,2}", question):
        if int(y) != year:
            return [f"日期须在数据时期内（{data_date}），不要写其他年份"]
    pairs = re.findall(r"(\d{1,2})\s*月\s*(\d{1,2})\s*[日号]", question)
    pairs += re.findall(r"\d{4}-(\d{1,2})-(\d{1,2})", question)
    for m, d in pairs:
        if int(m) != month or int(d) not in (day, day - 1):
            return [f"日期须为数据当天或前一天（{data_date}），可改用“今天”“昨天”"]
    return []


def _looks_like_id(token):
    return (any(c.isdigit() for c in token) or token.lower().startswith("line-") or
            re.fullmatch(r"[A-Z]{2,}-[A-Z]+", token) is not None)


def validate_output(out: Dict, card: Dict, persona_id: str, style_refs_all: List[str], answer_numbers: List[str]) -> List[str]:
    """返回错误列表（中文，空列表表示通过）。"""
    if not isinstance(out, dict) or set(out) != set(MODEL_OUTPUT_SCHEMA["required"]):
        return ["模型输出须为含四个指定字段的 JSON 对象"]
    question = out["user_question"]
    mentions = out["mentioned_entities"]
    if (not isinstance(question, str) or not isinstance(out["self_check"], str)
            or not isinstance(mentions, list) or not all(isinstance(s, str) for s in mentions)):
        return ["问题、自检须为字符串，实体须为字符串数组"]
    errors = []
    if out["intent"] not in MODEL_OUTPUT_SCHEMA["properties"]["intent"]["enum"]:
        errors.append("意图不在枚举中")
    short, long = LIMITS[persona_id]
    question = question.strip()
    if not short <= len(question) <= long:
        errors.append(f"该画像的问题须在 {short} 至 {long} 字符内")
    compact = "".join(question.split())
    # 编号、型号（CRANE-02、PL-260201-9923、PLC）和数字不计入分母：资深画像本来就会带很多编号。
    # 这条规则只为挡住整句英文，所以要求剩余的拉丁字母不超过汉字数的一半，且至少 4 个汉字。
    words = [t for t in TOKEN.findall(compact) if not _looks_like_id(t) and not t.isupper()]
    han = len(HAN.findall(compact))
    if han < 4 or sum(len(w) for w in words) * 2 > han:
        errors.append("问题须以中文为主")

    errors += _date_errors(question, card.get("data_date") or "")

    names = {e[k] for e in card["entities"] for k in ("id", "label") if e[k]}
    if persona_id in {"expert", "speculator"} and not any(name in question for name in names):
        errors.append("请在问题里提及卡上的实体编号或名称")
    valid_ids = {t for name in names for t in TOKEN.findall(name)}
    if any(_looks_like_id(t) and t not in valid_ids
           for s in [question, *mentions] for t in TOKEN.findall(s)):
        errors.append("出现了场景卡以外的编号")
    if _measurements(question) & {n for s in answer_numbers for n in _measurements(s)}:
        errors.append("问题包含原回答的数值结论")
    grams = _bigrams(question)
    for ref in style_refs_all:
        other = _bigrams(ref)
        union = grams | other
        if union and len(grams & other) / len(union) >= 0.6:
            errors.append("与同领域原题过于相似，请换一种问法")
            break
    if persona_id == "reporter" and question.count("？") + question.count("?") > 1:
        errors.append("现象描述最多带一个问句")
    if persona_id == "novice" and (TOOL.search(question) or any(t in question for t in card["tools"])):
        errors.append("新人问题里不能出现工具名")
    return errors
