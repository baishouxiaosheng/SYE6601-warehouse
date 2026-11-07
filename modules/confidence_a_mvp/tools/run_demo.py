"""One command: tests then produce fresh outputs, without editing input fixtures."""

import json
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from confidence_a import evaluate_runs, render_scorecard_markdown, score_snapshot


def main():
    result = subprocess.run([sys.executable, "-m", "unittest", "discover", "-s", "tests", "-v"], cwd=ROOT)
    if result.returncode:
        return result.returncode
    out = ROOT / "outputs"
    out.mkdir(exist_ok=True)
    for source in sorted((ROOT / "examples").glob("*.snapshot.json")):
        card = score_snapshot(json.loads(source.read_text(encoding="utf-8")))
        (out / source.name.replace("snapshot", "scorecard")).write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"{source.stem}: score={card['score']}, raw={card['raw_score']}, gate={card['gate_passed']}")
    for source in sorted((ROOT / "examples" / "v2").glob("*.input.json")):
        card = score_snapshot(json.loads(source.read_text(encoding="utf-8")))
        (out / source.name.replace(".input.json", ".scorecard.json")).write_text(
            json.dumps(card, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        (out / source.name.replace(".input.json", ".md")).write_text(
            render_scorecard_markdown(card), encoding="utf-8")
        print(f"{source.stem}: level={card['level']}, score={card['score']}, gate={card['gate_passed']}, "
              f"versions={card['graph_version']}/{card['answer_version']}")
    for name in ("runs.demo.json", "runs.v2.json"):
        report = evaluate_runs(json.loads((ROOT / "examples" / name).read_text(encoding="utf-8")))
        (out / name.replace("runs", "metrics")).write_text(
            json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print("Demo only; outputs are not measured results. Written to:", out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
