"""极简 JSON Schema 校验器（仅标准库；支持本项目 schema 用到的子集）。

支持关键字：type(含数组形式)、required、properties、additionalProperties(bool/schema)、
items、enum、const、minimum、maximum、minItems、maxItems、anyOf、oneOf、$ref(#/definitions/..)、pattern。
不支持的关键字静默忽略。返回错误字符串列表（空列表 = 通过）。
"""
from __future__ import annotations

import json
import re
from pathlib import Path
from typing import Any, Dict, List

SCHEMA_DIR = Path(__file__).resolve().parent.parent / "schemas"

_TYPES = {
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
}


def load_schema(name: str) -> Dict[str, Any]:
    """按文件名读取 confidence_07a/schemas/ 下的 schema。"""
    with open(SCHEMA_DIR / name, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _resolve(root: Dict[str, Any], ref: str) -> Dict[str, Any]:
    if not ref.startswith("#/"):
        raise ValueError(f"只支持本地 $ref：{ref}")
    node: Any = root
    for part in ref[2:].split("/"):
        node = node[part]
    return node


def validate(instance: Any, schema: Dict[str, Any], root: Dict[str, Any] | None = None, path: str = "$") -> List[str]:
    root = root if root is not None else schema
    errs: List[str] = []
    if "$ref" in schema:
        return validate(instance, _resolve(root, schema["$ref"]), root, path)
    t = schema.get("type")
    if t is not None:
        types = t if isinstance(t, list) else [t]
        if not any(_TYPES[x](instance) for x in types):
            return [f"{path}: 类型应为 {types}，实际 {type(instance).__name__}"]
    if "const" in schema and instance != schema["const"]:
        errs.append(f"{path}: 应等于 {schema['const']!r}")
    if "enum" in schema and instance not in schema["enum"]:
        errs.append(f"{path}: {instance!r} 不在枚举 {schema['enum']}")
    if isinstance(instance, (int, float)) and not isinstance(instance, bool):
        if "minimum" in schema and instance < schema["minimum"]:
            errs.append(f"{path}: {instance} < minimum {schema['minimum']}")
        if "maximum" in schema and instance > schema["maximum"]:
            errs.append(f"{path}: {instance} > maximum {schema['maximum']}")
    if isinstance(instance, str) and "pattern" in schema:
        if not re.search(schema["pattern"], instance):
            errs.append(f"{path}: 不匹配 pattern {schema['pattern']}")
    if isinstance(instance, dict):
        for k in schema.get("required", []):
            if k not in instance:
                errs.append(f"{path}: 缺少必填字段 {k}")
        props = schema.get("properties", {})
        addl = schema.get("additionalProperties", True)
        for k, v in instance.items():
            if k in props:
                errs.extend(validate(v, props[k], root, f"{path}.{k}"))
            elif addl is False:
                errs.append(f"{path}: 不允许的字段 {k}")
            elif isinstance(addl, dict):
                errs.extend(validate(v, addl, root, f"{path}.{k}"))
    if isinstance(instance, list):
        if "minItems" in schema and len(instance) < schema["minItems"]:
            errs.append(f"{path}: 元素数 < {schema['minItems']}")
        if "maxItems" in schema and len(instance) > schema["maxItems"]:
            errs.append(f"{path}: 元素数 > {schema['maxItems']}")
        if isinstance(schema.get("items"), dict):
            for i, v in enumerate(instance):
                errs.extend(validate(v, schema["items"], root, f"{path}[{i}]"))
    if "anyOf" in schema:
        if not any(not validate(instance, s, root, path) for s in schema["anyOf"]):
            errs.append(f"{path}: 不满足 anyOf 任一分支")
    if "oneOf" in schema:
        n = sum(1 for s in schema["oneOf"] if not validate(instance, s, root, path))
        if n != 1:
            errs.append(f"{path}: oneOf 命中 {n} 个分支（应为 1）")
    return errs
