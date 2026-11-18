"""离线评测配置（版本化，状态 PROVISIONAL，待团队确认）。

所有阈值集中在 eval_config.v1.json；本模块给出同值的内置默认，
JSON 缺失或字段缺失时回落到默认值。调用方可传入 dict 或路径覆盖。
"""
from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any, Dict, Optional, Union

CONFIG_PATH = Path(__file__).resolve().parent / "eval_config.v1.json"

DEFAULT_CONFIG: Dict[str, Any] = {
    "config_version": "07a-eval-config-v1",
    "status": "PROVISIONAL",
    "alignment": {
        # 字符相似度（difflib ratio，归一化后）阈值，>= 才可对齐
        "threshold": 0.5,
        # 较短文本完整包含于较长文本且长度 >= min_contain_len 时，相似度至少取 contain_floor
        "contain_floor": 0.8,
        "min_contain_len": 6,
        # 双方都含数值且数值集合不相交 -> 禁止对齐
        "numeric_must_overlap": True,
    },
    "gaps": {
        # overlap：受影响的已对齐结论有交集即可；exact：集合必须相等
        "claim_match": "overlap",
        # 相容缺口类型组（同组视为相容；同类型总是相容）
        "compatible_groups": [
            ["MISSING_EVIDENCE", "MISSING_DEPENDENCY"],
            ["INCOMPLETE_RESULT", "LIMITED_SCOPE"],
        ],
    },
    "params": {
        # 键名不同但 gold 参数值出现在相关动作的参数值文本中，也算命中（见 metrics.param_hit）
        "match_value_anywhere": True,
    },
    "calibration": {"n_bins": 5},
    "bootstrap": {"n_resamples": 1000, "ci": 0.95},
}


def _deep_merge(base: Dict[str, Any], over: Dict[str, Any]) -> Dict[str, Any]:
    out = copy.deepcopy(base)
    for k, v in (over or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def load_eval_config(cfg: Union[None, str, Path, Dict[str, Any]] = None) -> Dict[str, Any]:
    """读取评测配置。cfg 可为 None（读包内 JSON）、路径或 dict（覆盖默认）。"""
    base = copy.deepcopy(DEFAULT_CONFIG)
    if cfg is None:
        if CONFIG_PATH.is_file():
            with open(CONFIG_PATH, "r", encoding="utf-8") as fh:
                base = _deep_merge(base, json.load(fh))
        return base
    if isinstance(cfg, dict):
        return _deep_merge(base, cfg)
    with open(Path(cfg), "r", encoding="utf-8") as fh:
        return _deep_merge(base, json.load(fh))
