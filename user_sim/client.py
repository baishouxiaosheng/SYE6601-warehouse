"""OpenRouter 调用（SPEC §6）。只用 urllib；密钥只从环境变量读取。"""
from __future__ import annotations

import json
import os
import time
from urllib import request
from typing import Callable, Dict, Optional, Tuple

from .errors import UserSimError


class _InvalidOutput(UserSimError):
    """模型内容无法用于校验，可带反馈再试一次。"""

DEFAULT_BASE_URL = "https://openrouter.ai/api/v1/chat/completions"
DEFAULT_MODEL = "qwen/qwen3.8-27b"
DEFAULT_QUANT = "fp4"
Transport = Callable[[str, Dict[str, str], bytes, float], Tuple[int, bytes]]


def get_api_key(env=None) -> Optional[str]:
    """USER_SIM_API_KEY，其次 OPENROUTER_API_KEY；都没有返回 None。不读 .env。"""
    source = os.environ if env is None else env
    return source.get("USER_SIM_API_KEY") or source.get("OPENROUTER_API_KEY") or None


def redact(text: str, key: Optional[str]) -> str:
    """把 text 里的密钥替换为 ***。"""
    return text.replace(key, "***") if key else text


def build_request(messages, *, schema: Dict, seed=None, reasoning: Optional[Dict] = None, env=None) -> Dict:
    """返回请求体 dict（模型、fp4 路由、json_schema、temperature 等）。不含密钥。"""
    source = os.environ if env is None else env
    body = {
        "messages": messages, "model": source.get("USER_SIM_MODEL", DEFAULT_MODEL),
        "provider": {"quantizations": [source.get("USER_SIM_QUANT", DEFAULT_QUANT)], "allow_fallbacks": True},
        "response_format": {"type": "json_schema", "json_schema": {
            "name": "sim_question", "strict": True, "schema": schema}},
        "temperature": 0.9, "top_p": 0.95, "max_tokens": 600,
    }
    if reasoning is None:
        # 实测（2026-11-19）：qwen3.8-27b 即使 effort=low 也常把 600 token 全用在推理上、content 为空；
        # 关闭推理后单次约 1.5 秒、成功率最高。设 USER_SIM_REASONING=low/medium 可重新打开。
        effort = source.get("USER_SIM_REASONING", "off")
        reasoning = {"enabled": False} if effort == "off" else {"effort": effort, "exclude": True}
    if reasoning:
        body["reasoning"] = reasoning
        if reasoning.get("enabled") is not False:
            body["max_tokens"] = 2000  # 推理打开时给足空间，否则答案会被截断
    if seed is not None:
        body["seed"] = seed
    return body


def urllib_transport(url: str, headers: Dict[str, str], body: bytes, timeout: float) -> Tuple[int, bytes]:
    req = request.Request(url, data=body, method="POST")
    for name, value in headers.items():
        if name.lower() == "authorization":
            req.add_unredirected_header(name, value)
        else:
            req.add_header(name, value)
    with request.urlopen(req, timeout=timeout) as response:
        return response.status, response.read()


def chat_json(messages, *, schema: Dict, seed=None, transport: Optional[Transport] = None, env=None) -> Dict:
    """发请求并返回 {"content": dict, "usage": {...}, "provider": str, "latency_s": float}；失败抛 UserSimError。"""
    source = os.environ if env is None else env
    key = get_api_key(source)
    if not key:
        raise UserSimError("未配置密钥")
    payload = build_request(messages, schema=schema, seed=seed, env=source)
    body = redact(json.dumps(payload, ensure_ascii=False), key).encode("utf-8")
    headers = {
        "Authorization": "Bearer " + key, "Content-Type": "application/json",
        "HTTP-Referer": "https://github.com/forest1119/SYE6601-warehouse",
        "X-Title": "SYE6601 user-sim",
    }
    url = source.get("USER_SIM_BASE_URL", DEFAULT_BASE_URL)
    start = time.monotonic()
    try:
        status, raw = (transport or urllib_transport)(url, headers, body, 30)
    except Exception as exc:
        # Raise outside the handler so even the exception chain omits credentials.
        failure = redact(f"网络请求失败：{type(exc).__name__} {exc}", key)
    else:
        failure = "" if 200 <= status < 300 else f"网络请求失败：HTTP {status}"
    if failure:
        raise UserSimError(failure)
    try:
        response = json.loads(raw.decode("utf-8"))
        content = json.loads(response["choices"][0]["message"]["content"])
        # Decode before sanitising, including JSON-escaped characters from a provider.
        content = json.loads(redact(json.dumps(content, ensure_ascii=False), key))
        provider = response.get("provider")
        usage = response.get("usage") or {}
        counts = {k: usage.get(k, 0) for k in ("prompt_tokens", "completion_tokens")}
        if not all(type(n) is int and n >= 0 for n in counts.values()):
            raise ValueError("usage")
        if not isinstance(content, dict):
            raise ValueError("content")
        return {"content": content, "usage": counts,
                "provider": redact(provider, key) if isinstance(provider, str) else "",
                "latency_s": round(time.monotonic() - start, 3)}
    except (ValueError, TypeError, LookupError, AttributeError):
        pass
    raise _InvalidOutput("响应缺少有效的 JSON 对象或字段")
