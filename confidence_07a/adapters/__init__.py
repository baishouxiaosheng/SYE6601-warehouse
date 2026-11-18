"""上游产物适配器：统一转成 confidence_07a.model.RunView。

- egraph_v1：01A 证据图引擎 graph/plan(/v1 scorecard) JSON，及 06B 结果文件
- b_review：02B 局部检查覆盖层（可选，保守匹配）
"""
from .egraph_v1 import (  # noqa: F401
    detect_dir_kind,
    iter_06b_dir,
    iter_output_dir,
    latest_06b_files,
    load_run_from_06b_result,
    load_run_from_artifacts,
    load_run_from_files,
    load_v1_scorecard,
)
