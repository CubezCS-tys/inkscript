"""The gold set's numbers: what KIND of errors does the reading actually have, and how many?

    python tally.py out/*.gold.json

Prints, over every marked page: the error classes in order of size, the share of words right, and the split
that decides the next build — look-alike errors (a checker can catch these) against structural ones (dropped,
merged, split, invented: a checker cannot pose the hypothesis, only a coverage test can).

This is the measurement that milestone 1 waits on. `docs/roadmap.md` item 1 assumes the errors are mostly
look-alikes; if they are not, the checker is the wrong build and this says so before the code is written.
"""
from __future__ import annotations
import json, sys, glob
from collections import Counter

LOOKALIKE = {"dots", "hamza", "ta", "ya", "lookalike"}
NOT_A_READING_ERROR = {"style", "boxwrong"}   # the reading is right; something else is wrong
STRUCTURAL = {"merged", "split", "invented", "wrong"}
LABEL = {"correct": "correct", "dots": "dots", "hamza": "hamza أ ا إ", "ta": "ة / ه", "ya": "ى / ي",
         "lookalike": "other look-alike", "wrong": "wrong word", "merged": "merged", "split": "split",
         "invented": "invented", "style": "the book's style", "boxwrong": "ink isn't this word",
         "unsure": "unsure"}


def main(paths: list[str]) -> int:
    files = [f for p in paths for f in sorted(glob.glob(p))]
    if not files:
        sys.exit("no gold files; pass out/*.gold.json")
    total = Counter(); pages = []; missed = 0
    for f in files:
        d = json.load(open(f)); c = Counter(w["cls"] for w in d["words"])
        total += c; missed += d.get("missed_words", 0)
        pages.append((d["stem"], d["page"], sum(c.values()), c))

    n = sum(total.values())
    print(f"{len(files)} pages, {n} words marked, {missed} words of ink with no reading at all\n")
    for stem, page, m, c in pages:
        bad = sum(v for k, v in c.items() if k != "correct" and k not in NOT_A_READING_ERROR)
        print(f"  {stem} p{page}: {m} words, {m - bad} right ({100 * (m - bad) / max(1, m):.1f}%), {bad} wrong")
    print()
    for k, v in total.most_common():
        if v:
            print(f"  {LABEL.get(k, k):<20} {v:>6}  {100 * v / max(1, n):5.2f}%")

    look = sum(total[k] for k in LOOKALIKE); struct = sum(total[k] for k in STRUCTURAL)
    errs = look + struct + total["unsure"]
    print(f"\n  errors {errs} of {n} words ({100 * errs / max(1, n):.2f}%)")
    if errs:
        print(f"    look-alike (a checker can pose the hypothesis): {look} ({100 * look / errs:.0f}% of errors)")
        print(f"    structural (only a coverage test finds these):  {struct + missed} ({100 * (struct + missed) / (errs + missed):.0f}%)")
        print(f"    unsure from the ink alone:                      {total['unsure']}")
    if total["boxwrong"]:
        print(f"\n  {total['boxwrong']} words whose READING is right but whose box covers the wrong ink.")
        print("  A boxing fault, not a recognition one — it belongs to the layout, and it is why some")
        print("  contradictions are not errors at all (experiments/12_gold/README.md).")
    if total["style"]:
        print(f"\n  {total['style']} words where the BOOK departs from standard Arabic and is not wrong.")
        print("  A checker must learn each book's own practice or it will 'correct' these at scale.")
    print("\n  The baseline any checker must beat is 'change nothing':"
          f" {100 * (n - errs) / max(1, n):.2f}% of words already right.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:] or ["out/*.gold.json"]))
