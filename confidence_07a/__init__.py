"""confidence_07a —— 置信度组 A：成绩单 v2（在线）与离线评测。

分数含义：基于现有日志的证据审核结果，不是正确概率。
"""
from __future__ import annotations

__version__ = "2.1.0"

from .scorecard import diff_scorecards, load_policy, score_run  # noqa: E402,F401


def evaluate(*args, **kwargs):
    """离线评测入口（延迟导入 confidence_07a.eval.metrics.evaluate）。"""
    from .eval.metrics import evaluate as _evaluate

    return _evaluate(*args, **kwargs)


__all__ = ["score_run", "diff_scorecards", "load_policy", "evaluate", "__version__"]
