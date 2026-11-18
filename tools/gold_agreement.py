"""两份 gold 在重合运行上的一致性（标注可靠性）：按回答原文片段对齐结论，比较五态，给出一致率与 Cohen's kappa。
用法：python -I tools/gold_agreement.py GOLD_A GOLD_B --out OUT.md"""
import argparse, difflib, json, sys
from collections import Counter
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from confidence_07a.eval.gold import gold_runs, load_gold  # noqa: E402

ap = argparse.ArgumentParser(); ap.add_argument("a"); ap.add_argument("b"); ap.add_argument("--out", required=True)
ap.add_argument("--threshold", type=float, default=0.6)
x = ap.parse_args()
A = {r["run_id"]: r for r in gold_runs(load_gold(x.a))}
B = {r["run_id"]: r for r in gold_runs(load_gold(x.b))}
pairs, unA, unB, rows = [], 0, 0, []
for rid in sorted(set(A) & set(B)):
    ca, cb = list(A[rid]["claims"]), list(B[rid]["claims"])
    used = set()
    for c in ca:
        best, bj = 0.0, None
        for j, d in enumerate(cb):
            if j in used:
                continue
            s1, s2 = c["answer_span"], d["answer_span"]
            sc = 1.0 if (s1 in s2 or s2 in s1) else difflib.SequenceMatcher(None, s1, s2).ratio()
            if sc > best:
                best, bj = sc, j
        if bj is not None and best >= x.threshold:
            used.add(bj); d = cb[bj]
            pairs.append((c["gold_status"], d["gold_status"]))
            if c["gold_status"] != d["gold_status"]:
                rows.append((rid, c["answer_span"][:40], c["gold_status"], d["gold_status"]))
        else:
            unA += 1
    unB += len(cb) - len(used)
n = len(pairs); agree = sum(a == b for a, b in pairs)
ca, cb = Counter(a for a, _ in pairs), Counter(b for _, b in pairs)
pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n) if n else 0
po = agree / n if n else 0
kappa = (po - pe) / (1 - pe) if n and pe < 1 else None
L = [f"# 标注一致性：{Path(x.a).name} vs {Path(x.b).name}", "",
     f"- 重合运行 {len(set(A) & set(B))} 条；对齐结论 {n} 对；A 未对齐 {unA}，B 未对齐 {unB}（拆分粒度不同）",
     f"- 五态一致率 **{po:.3f}**（{agree}/{n}）；Cohen's kappa **{kappa:.3f}**" if kappa is not None else "- 无可比较结论", "",
     "| run_id | 原文片段 | A | B |", "|---|---|---|---|"]
L += [f"| {r} | {s} | {a} | {b} |" for r, s, a, b in rows]
Path(x.out).parent.mkdir(parents=True, exist_ok=True)
Path(x.out).write_text("\n".join(L) + "\n", encoding="utf-8")
print(f"pairs={n} agree={po:.3f} kappa={kappa} unA={unA} unB={unB} disagreements={len(rows)}")
