"""Experiment 69: append judgments to out/labels69.tsv by sheet row number.
    lab69.py ORDER_FILE  'K<TAB>truth<TAB>why' lines on stdin   (truth: AZ, AZM, U, or the printed text)"""
import json, sys
import common69 as C
order = json.load(open(C.OUT / sys.argv[1]))
with open(C.OUT / "labels69.tsv", "a", encoding="utf-8") as f:
    for ln in sys.stdin:
        if not ln.strip():
            continue
        k, truth, why = (ln.rstrip("\n").split("|", 2) + [""])[:3]
        f.write(f"{order[int(k) - 1]}\t{truth.strip()}\t{why.strip()}\n")
