"""用户模拟 Agent：自动生成课堂演示用的用户问题。规范见 docs/user-sim/SPEC.md。"""
from .errors import UserSimError
from .generator import generate_question, to_log_record

__version__ = "0.1.0"
PROMPT_VERSION = "user-sim-prompt-v1"
__all__ = ["generate_question", "to_log_record", "UserSimError", "__version__", "PROMPT_VERSION"]
