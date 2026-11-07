import argparse
import json
import sys
from pathlib import Path

from .contracts import ContractError, exported_schemas
from .metrics import evaluate_runs
from .render import render_scorecard_markdown
from .scoring import score_snapshot


def read_json(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8")


def main():
    parser = argparse.ArgumentParser(description="07A 证据评分 MVP")
    subs = parser.add_subparsers(dest="command", required=True)
    score = subs.add_parser("score")
    score.add_argument("input")
    score.add_argument("--policy")
    score.add_argument("--output", required=True)
    metrics = subs.add_parser("metrics")
    metrics.add_argument("input")
    metrics.add_argument("--output", required=True)
    schemas = subs.add_parser("schemas")
    schemas.add_argument("--output-dir", default="schemas")
    render = subs.add_parser("render")
    render.add_argument("input")
    render.add_argument("--output", required=True)
    args = parser.parse_args()
    try:
        if args.command == "schemas":
            for name, schema in exported_schemas().items():
                write_json(Path(args.output_dir) / f"{name}.schema.json", schema)
            return 0
        source = Path(args.input).resolve()
        target = Path(args.output).resolve()
        policy = Path(args.policy).resolve() if args.command == "score" and args.policy else None
        if source == target or policy == target:
            raise ContractError("输出路径不能覆盖输入或策略文件")
        payload = read_json(source)
        if args.command == "render":
            target.write_text(render_scorecard_markdown(payload), encoding="utf-8")
            print(f"Written: {target}")
            return 0
        result = (score_snapshot(payload, read_json(args.policy) if args.policy else None)
                  if args.command == "score" else evaluate_runs(payload))
        write_json(target, result)
        print(f"Written: {target}")
        return 0
    except (ContractError, ValueError, OSError) as error:
        print(f"Input error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
