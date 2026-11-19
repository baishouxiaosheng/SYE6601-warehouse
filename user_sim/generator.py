"""主流程（SPEC §5、§7、§8）。"""
from __future__ import annotations

import logging
import os
import random
import time
from collections import deque
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from functools import lru_cache
from threading import Lock
from typing import Dict, Optional
from uuid import uuid4

from . import client
from .errors import UserSimError
from .personas import PERSONAS, persona_label
from .prompt import MODEL_OUTPUT_SCHEMA, build_messages
from .validate import _answer_numbers, validate_output

DOMAINS = ("industrial", "insurance")
INTENTS = MODEL_OUTPUT_SCHEMA["properties"]["intent"]["enum"]
_RECENT = {domain: deque(maxlen=5) for domain in DOMAINS}
_LOCK = Lock()
_LOG = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _catalog():
    from .catalog import load_scenarios
    return {c["scenario_id"]: c for c in load_scenarios()}


@lru_cache(maxsize=1)
def _numbers():
    from .catalog import REPO, _logs
    return {row["case_id"]: _answer_numbers(row) for _, row in _logs(REPO)}


@lru_cache(maxsize=1)
def _bank():
    from .catalog import DATA, _read
    return _read(DATA / "fallback_questions.json")


def _pick(rows, domain, rng, seed, *, remember=True):
    if seed is not None:
        return rng.choice(rows)
    with _LOCK:
        recent = _RECENT[domain]
        fresh = [r for r in rows if r["scenario_id"] not in recent]
        row = rng.choice(fresh or rows)
        if remember:
            recent.append(row["scenario_id"])
    return row


def _record(card, out, persona, metadata):
    from . import PROMPT_VERSION
    now = datetime.now(timezone(timedelta(hours=8)))
    stamp = now.isoformat(timespec="seconds")
    received = stamp
    if card.get("data_date"):
        # 问题里的“今天/昨天”要与数据时期一致：取原日志日期 + 当前时刻
        received = card["data_date"] + stamp[10:]
    prefix = "IND" if card["domain"] == "industrial" else "INS"
    case_id = f"SIM-{prefix}-{now:%Y%m%d-%H%M%S}-{uuid4().hex[:12]}"
    return {
        "schema": "sim-question.v1", "case_id": case_id, "run_id": case_id + "-r1",
        "domain": card["domain"], "user_question": out["user_question"].strip(),
        "visible_context": {**card["context"], "received_at": received},
        "persona": {"id": persona, "label_zh": persona_label(persona)},
        "intent": out["intent"], "scenario_id": card["scenario_id"],
        "grounding": {"entities": deepcopy(card["entities"]), "suggested_tools": list(card["tools"]),
                      "risk": card["risk"]},
        "generator": {**metadata, "prompt_version": PROMPT_VERSION}, "created_at": stamp,
    }


def generate_question(domain: str = "industrial", persona: Optional[str] = None, intent: Optional[str] = None,
                      seed: Optional[int] = None, *, offline: bool = False, transport=None, env=None) -> Dict:
    """生成一条 sim-question.v1 记录；任何错误都不抛出，退回离线备用题。"""
    if domain not in DOMAINS or (persona is not None and persona not in PERSONAS):
        raise ValueError("领域或画像无效")
    if intent is not None and intent not in INTENTS:
        raise ValueError("意图无效")
    if seed is not None and type(seed) is not int:
        raise ValueError("seed 须为整数")
    if type(offline) is not bool:
        raise ValueError("offline 须为布尔值")
    rng = random.Random(seed)
    persona = persona or rng.choices(list(PERSONAS), weights=[p["weight"] for p in PERSONAS.values()])[0]
    source = os.environ if env is None else env
    catalog = _catalog()
    usage = {"prompt_tokens": 0, "completion_tokens": 0}
    meta = {"mode": "offline_fallback", "model": "", "quantization": "", "provider": "",
            "seed": seed, "attempts": 0, "latency_s": 0.0, "usage": usage, "note": ""}
    if offline:
        meta["note"] = "已指定离线模式"
    elif not client.get_api_key(source):
        meta["note"] = "未配置密钥"
    else:
        cards = [c for c in catalog.values() if c["domain"] == domain]
        feasible = [c for c in cards if c["entities"] or persona in {"novice", "reporter"}]
        preferred = [c for c in feasible if intent in c["intent_hints"]]
        card = _pick(preferred or feasible, domain, rng, seed, remember=False)
        target = intent or rng.choice(card["intent_hints"] or ["status"])
        refs = [c["style_ref"] for c in cards]
        others = [ref for ref in refs if ref != card["style_ref"]]
        examples = rng.sample(others, min(2, len(others)))
        feedback = ""
        for attempt in (1, 2):
            meta["attempts"] = attempt
            messages = build_messages(card, persona, target, examples, feedback)
            started = time.monotonic()
            try:
                reply = client.chat_json(messages, schema=MODEL_OUTPUT_SCHEMA, seed=seed,
                                         transport=transport, env=source)
            except client._InvalidOutput as exc:
                feedback = str(exc)
                continue
            except UserSimError as exc:
                meta["note"] = str(exc)
                break
            finally:
                meta["latency_s"] = round(meta["latency_s"] + time.monotonic() - started, 3)
            out = reply["content"]
            for k in usage:
                usage[k] += reply["usage"][k]
            errors = validate_output(out, card, persona, refs, _numbers()[card["scenario_id"]])
            if intent is not None and out.get("intent") != intent:
                errors.append("请使用指定的目标意图")
            if not errors:
                key = client.get_api_key(source)
                meta.update(mode="llm", provider=reply["provider"],
                            model=client.redact(source.get("USER_SIM_MODEL", client.DEFAULT_MODEL), key),
                            quantization=client.redact(source.get("USER_SIM_QUANT", client.DEFAULT_QUANT), key))
                if seed is None:
                    with _LOCK:
                        _RECENT[domain].append(card["scenario_id"])
                _LOG.debug("画像自检 %s", out["self_check"])
                return _record(card, out, persona, meta)
            feedback = "；".join(errors)
        else:
            meta["note"] = "两次校验未通过：" + feedback

    bank = [q for q in _bank() if q["domain"] == domain]
    pool = ([q for q in bank if q["persona"] == persona and (intent is None or q["intent"] == intent)]
            or [q for q in bank if q["persona"] == persona] or bank)
    if not pool:
        raise UserSimError(f"离线备用题库里没有 {domain} 领域的题目")
    choice = _pick(pool, domain, rng, seed)
    return _record(catalog[choice["scenario_id"]], choice, persona, meta)


def to_log_record(q: Dict) -> Dict:
    """转成日志同格式：{case_id, run_id, user_question, visible_context, trace: [], ai_answer: ""}。"""
    return {"case_id": q["case_id"], "run_id": q["run_id"], "user_question": q["user_question"],
            "visible_context": dict(q["visible_context"]), "trace": [], "ai_answer": ""}
