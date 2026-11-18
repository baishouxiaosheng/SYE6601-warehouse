"""在 `python -I`（隔离模式，不把当前目录加入 sys.path）下运行 confidence_07a CLI 的启动器。

用法：python -I tools/run_cli.py score-dir --input <01A output 目录> --log <日志 JSON> --out <目录>
"""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from confidence_07a.__main__ import main  # noqa: E402

if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass
    sys.exit(main())
