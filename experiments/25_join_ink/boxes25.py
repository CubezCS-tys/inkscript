"""Letter boxes (what Chrome highlights) of experiment 18's sample words under a variant, from the replayed plans:
experiment 21's cells.word_boxes (each letter's stretch of the path in page x, retiled as type3 writes the advances).
For variant 'today' this must reproduce experiment 21's boxes read back from the built PDFs (boxes_new.json).

    ../../.venv/bin/python boxes25.py VARIANT      -> out/boxes_<variant>.json {word id: [[x0, x1], ...]}
"""
import sys, json
from common import *


def boxes(variant):
    out = {}
    for wid, (s, w) in words().items():
        load(variant, w["doc"]); b, m = C.word_boxes(w, C.cells_orig, variant); out[wid] = [list(map(float, c)) for c in b]
    return out


if __name__ == "__main__":
    v = sys.argv[1]; B = boxes(v); json.dump(B, open(HERE / f"out/boxes_{v}.json", "w"))
    N = json.load(open(E21 / "out/boxes_new.json")); same = diff = 0; dl = []
    for wid, cells in B.items():
        if wid not in N: continue
        d = max(abs(a - c) for x, y in zip(cells, N[wid]["cells"]) for a, c in zip(x, y))
        if d <= 1.0: same += 1
        else: diff += 1; dl.append((wid, round(d, 1)))
    print(f"{v}: {len(B)} words; vs 21's PDF boxes: same {same}, different {diff} {dl[:12]}")
