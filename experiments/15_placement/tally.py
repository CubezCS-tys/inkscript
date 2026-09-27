"""The blind trial's verdict: does the pen path beat equal slicing where a reader can see?

    python tally.py out/*_placement.json

Reports the win/loss/draw split and a sign test over the decided pairs — the share that must be beaten is 50%,
not 0%, because equal slicing is free (docs/decisions.md, D7). "Both wrong" is counted apart: it is the share
of words where letter selection does not work at all, whichever method cut them, which is the honest reading
of milestone 2.
"""
from __future__ import annotations
import glob, json, sys
from collections import Counter
from math import comb


def sign_test(w, l):
    """Two-sided probability of a split this lopsided if the two methods were equally good."""
    n = w + l
    if n == 0:
        return 1.0
    k = min(w, l)
    tail = sum(comb(n, i) for i in range(0, k + 1)) / 2 ** n
    return min(1.0, 2 * tail)


def main(paths):
    files = [f for p in paths for f in sorted(glob.glob(p))]
    if not files:
        sys.exit("no placement files; pass out/*_placement.json")
    tot = Counter(); docs = []
    for f in files:
        d = json.load(open(f))
        c = Counter(w["winner"] for w in d["words"] if w.get("winner"))
        tot += c; docs.append((d["stem"], sum(c.values()), c))

    n = sum(tot.values())
    print(f"{len(files)} document(s), {n} words judged\n")
    for stem, m, c in docs:
        print(f"  {stem}: {m} judged — pen path {c['pen path']}, equal slicing {c['equal slicing']}, "
              f"same {c['same']}, both wrong {c['both_wrong']}")
    if not n:
        return 0
    w, l, s, b = tot["pen path"], tot["equal slicing"], tot["same"], tot["both_wrong"]
    print(f"\n  pen path better     {w:>5}  ({100*w/n:.1f}%)")
    print(f"  equal slicing better{l:>5}  ({100*l/n:.1f}%)")
    print(f"  the same            {s:>5}  ({100*s/n:.1f}%)")
    print(f"  both wrong          {b:>5}  ({100*b/n:.1f}%)")
    dec = w + l
    if dec:
        p = sign_test(w, l)
        print(f"\n  of the {dec} words where one was better, the pen path won {w} ({100*w/dec:.1f}%); "
              f"sign test p = {p:.4f}")
        if p > 0.05:
            print("  Not distinguishable from a coin flip. By D7 that is a fail: a method that does not beat")
            print("  equal slicing is not worth its code.")
        elif w > l:
            print("  The pen path beats the free baseline where a reader can see it.")
        else:
            print("  EQUAL SLICING WINS. Read D7 before defending the cutter.")
    print(f"\n  letter selection visibly wrong either way: {100*b/n:.1f}% of words — the honest ceiling on")
    print("  what letter-level highlighting delivers today, whatever cut is used.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["out/*_placement.json"]))
