"""python -m user_sim --domain industrial --persona novice --n 1 [--offline] [--seed 7] [--out file.jsonl]"""
import argparse
import json
import sys
from contextlib import nullcontext
from pathlib import Path

from .generator import DOMAINS, INTENTS, generate_question
from .personas import PERSONA_IDS


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="生成课堂演示用的用户问题")
    parser.add_argument("--domain", choices=DOMAINS, default="industrial")
    parser.add_argument("--persona", choices=PERSONA_IDS)
    parser.add_argument("--intent", choices=INTENTS)
    parser.add_argument("--n", type=int, default=1)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--offline", action="store_true")
    parser.add_argument("--out", type=Path)
    args = parser.parse_args(argv)
    if args.n < 1:
        parser.error("--n 须为正整数")
    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        output = args.out.open("w", encoding="utf-8")
    else:
        output = nullcontext(sys.stdout)
    with output as stream:
        for i in range(args.n):
            seed = args.seed + i if args.seed is not None else None
            record = generate_question(args.domain, args.persona, args.intent, seed, offline=args.offline)
            print(json.dumps(record, ensure_ascii=False), file=stream)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
