"""Does the offline replay of today's cutter reproduce experiment 21's build-time plans (= today's src)?"""
import sys, pickle
from pathlib import Path
HERE = Path(__file__).resolve().parent; E21 = HERE.parent / "21_better_boxes"
from replay import replay, DOCS

for doc in sys.argv[1:]:
    old = pickle.load(open(E21 / f"out/plans/new_{doc}.pkl", "rb"))
    kept, _ = replay(doc, set(DOCS[doc]["pages"]))
    idx = {(p["page"], tuple(p["units"]), tuple(p["off"])): p["cuts"] for p in old}
    same = diff = miss = 0
    for r, p in kept:
        k = (r["page"], tuple(p["units"]), tuple(p["off"]))
        if k not in idx: miss += 1
        elif list(idx[k]) == list(p["cuts"]): same += 1
        else: diff += 1
    print(doc, f"21 plans {len(old)}, replayed {len(kept)}: same cuts {same}, different {diff}, unmatched {miss}", flush=True)
