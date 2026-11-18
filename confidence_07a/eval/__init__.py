"""07A 离线评测（spec §5）。仅标准库；不调用模型；不读取 .env。"""
from .align import Alignment, AlignedPair, align_claims
from .config import load_eval_config
from .gold import build_gold_template, gold_runs, load_gold, validate_gold
from .metrics import EVAL_VERSION, METRIC_DEFS, bootstrap_ci, evaluate
from .report import build_experiment_metrics, validate_experiment_metrics, write_report
from .runner import load_results_dir, records_to_runs, run_engine_rule, run_methods

__all__ = [
    "Alignment", "AlignedPair", "align_claims",
    "load_eval_config",
    "build_gold_template", "gold_runs", "load_gold", "validate_gold",
    "EVAL_VERSION", "METRIC_DEFS", "bootstrap_ci", "evaluate",
    "build_experiment_metrics", "validate_experiment_metrics", "write_report",
    "load_results_dir", "records_to_runs", "run_engine_rule", "run_methods",
]
