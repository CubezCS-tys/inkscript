"""Experiment 69, step 3d: experiment 66's judged fixes on the chosen pages - what each run did with each.
    judged69.py TAG [TAG ...]   -> out/judged.json + a table
Outcome per judged fix: FIX (the run makes the saved fix's change), AZ (keeps Azure's word), OTHER (changes it
otherwise), with and without experiment 66's guard (TAG+g)."""
import json
import sys
from collections import Counter, defaultdict

import common69 as C
from score69 import norm


def main(tags):
    U = list(C.jlines(C.UNITS))
    out, tab = [], defaultdict(Counter)
    for u in U:
        j = u.get("judged")
        if not j or j["lab"] not in "GBM":
            continue
        az, fx = norm(u["azure"]), norm(u["outs"]["saved"])
        rec = dict(sid=j["sid"], lab=j["lab"], uid=u["uid"], poor=u["poor"], azure=u["azure"], fix=u["outs"]["saved"])
        for t in tags:
            for g in ("", "+g"):
                c = t + g
                if c not in u["outs"]:
                    continue
                v = norm(u["outs"][c])
                o = "FIX" if v == fx else "AZ" if v == az else "OTHER"
                rec[c] = o
                tab[(j["lab"], c)][o] += 1
        out.append(rec)
    C.jdump(C.OUT / "judged.json", out)
    for lab in "BMG":
        for t in tags:
            for g in ("", "+g"):
                c = t + g
                if (lab, c) in tab:
                    print(lab, f"{c:10s}", dict(tab[(lab, c)]))


if __name__ == "__main__":
    main(sys.argv[1:])
