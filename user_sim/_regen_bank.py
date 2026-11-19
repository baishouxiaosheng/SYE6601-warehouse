"""用真实模型重建离线备用题库（需要 USER_SIM_API_KEY）。

    python -m user_sim._regen_bank --per 7

每个 领域 × 画像 生成 --per 道题，只保留通过校验的 llm 结果（generator 内部已校验），
同一场景卡不重复。生成失败的格子用模板题（_fallback._build）补齐。输出覆盖
user_sim/data/fallback_questions.json，每条带 source=llm|template、reviewed=false。
"""
from __future__ import annotations

import argparse
import json
import sys

from . import generator
from ._fallback import _build
from .catalog import DATA
from .personas import PERSONA_IDS

INTENT_ORDER = ["status", "value", "decision", "diagnosis", "compliance", "aggregate", "progress"]


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--per", type=int, default=7)
    ap.add_argument("--max-tries", type=int, default=4, help="每道题最多尝试次数")
    a = ap.parse_args(argv)
    templates = _build()
    bank = []
    for domain in generator.DOMAINS:
        for persona in PERSONA_IDS:
            got, used = [], set()
            for i in range(a.per):
                intent = INTENT_ORDER[i % len(INTENT_ORDER)]
                for _ in range(a.max_tries):
                    q = generator.generate_question(domain, persona, intent)
                    if q["generator"]["mode"] != "llm":
                        q = generator.generate_question(domain, persona)  # 放宽意图再试
                    if q["generator"]["mode"] == "llm" and q["scenario_id"] not in used:
                        used.add(q["scenario_id"])
                        got.append({"scenario_id": q["scenario_id"], "domain": domain, "persona": persona,
                                    "reviewed": False, "source": "llm", "model": q["generator"]["model"],
                                    "user_question": q["user_question"], "intent": q["intent"],
                                    "mentioned_entities": [], "self_check": "真实模型生成并通过校验。"})
                        break
            fill = [dict(t, source="template") for t in templates
                    if t["domain"] == domain and t["persona"] == persona and t["scenario_id"] not in used]
            got += fill[: max(0, a.per - len(got))]
            bank += got
            print(f"{domain} {persona}: llm {sum(x['source'] == 'llm' for x in got)} / {len(got)}", file=sys.stderr)
    (DATA / "fallback_questions.json").write_text(json.dumps(bank, ensure_ascii=False, indent=1) + "\n",
                                                  encoding="utf-8", newline="\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
