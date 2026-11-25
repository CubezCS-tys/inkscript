"""Experiment 94, goal 2 development: the order rules on DEV pages (the training pool's validation documents, never the
test set), Azure's line boxes, Argon's fine types (oracle) and Argon's order as reference.

    python orderdev94.py [N]   -> out/orderdev94.json  successor kept / tau by layout, for each rule set

The test set is scored once, by score94.py, with the rules frozen here.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict

from common94 import OUT, TO_COARSE, azure_lines, assert_not_locked
from order94 import order_page

sys.path.insert(0, str(OUT.parent.parent / "92_layout"))
from build92 import layout_of  # noqa: E402
from common92 import kendall_tau, page_is_rtl, xycut_order  # noqa: E402


def succ(ref_rank: dict, order: list) -> tuple[int, int]:
    """(kept, steps): Argon's line-to-next steps also taken by the order (over items both place)."""
    S = [i for i in order if i in ref_rank]
    rs = sorted(S, key=lambda i: ref_rank[i])
    nxt = {S[j]: S[j + 1] for j in range(len(S) - 1)}
    return sum(nxt.get(a) == b for a, b in zip(rs, rs[1:])), max(0, len(rs) - 1)


VARIANTS = {"xycut92": None, "atom": ("atom",), "atom+foot": ("atom", "foot"), "atom+furn": ("atom", "furn"),
            "furn+foot+atom": ("furn", "foot", "atom"), "cols+atom": ("cols", "atom"),
            "all": ("furn", "foot", "atom", "cols"), "atom_v0.3": ("atom", 0.3), "atom_v0.2": ("atom", 0.2),
            "atom_v0.3_h0.6": ("atom", 0.3, 0.6)}


def main(N=600):
    rows = [json.loads(l) for l in open(OUT / "train94.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["split"] == "val"]
    random.Random(94).shuffle(rows)
    pdfaz = {}
    for l in open(OUT.parent.parent / "76_finetune_pilot/out/inventory76.jsonl", encoding="utf-8"):
        a = json.loads(l)
        pdfaz.setdefault(a["stem"], a["azure"].replace("/home/yassine/", "/home/appuser/"))
    assert_not_locked([r["key"] for r in rows])
    res = defaultdict(lambda: defaultdict(lambda: [0, 0]))
    taus = defaultdict(lambda: defaultdict(list))
    n = 0
    for r in rows:
        L = [x for x in r["lines"] if x["rank"] is not None]
        if len(L) < 5:
            continue
        az, W, H = azure_lines(pdfaz[r["stem"]], r["page"])
        text = {x["i"]: x["text"] for x in az}
        box = {x["i"]: x["box"] for x in az}
        blocks = defaultdict(lambda: dict(ids=[], coarse=None, type=None))
        for x in L:
            b = blocks[x["block"]]
            b["ids"].append(x["i"])
            b["coarse"] = TO_COARSE.get(x["fine"] or "other")
            b["type"] = "footnote" if x["fine"] == "footnote" else x["fine"]
        lay, fl = layout_of(list(blocks.values()), az, W)
        rtl = page_is_rtl([text[x["i"]] for x in L])
        ids = [x["i"] for x in L]
        bx = [box[i] for i in ids]
        lab = [x["fine"] for x in L]
        ref = {k: x["rank"] for k, x in enumerate(L)}
        for v, rules in VARIANTS.items():
            import order94
            order94.XY.update(vmin=0.5, hmin=0.3)
            if rules and len(rules) > 1 and not isinstance(rules[1], str):
                order94.XY.update(vmin=rules[1], hmin=rules[2] if len(rules) > 2 else 0.3)
                rules = rules[:1]
            o = xycut_order(bx, rtl) if rules is None else order_page(bx, lab, rtl, H=H, rules=rules)
            k, s = succ(ref, o)
            pos = {i: p for p, i in enumerate(o)}
            t = kendall_tau([pos[i] for i in range(len(L))], [ref[i] for i in range(len(L))])
            for g in ("all", lay):
                res[v][g][0] += k
                res[v][g][1] += s
                if t is not None:
                    taus[v][g].append(t)
        n += 1
        if n >= N:
            break
    out = {v: {g: dict(kept=round(a / max(1, b), 4), steps=b, tau=round(sum(taus[v][g]) / max(1, len(taus[v][g])), 4),
                       pages=len(taus[v][g]))
               for g, (a, b) in d.items()} for v, d in res.items()}
    json.dump(out, open(OUT / "orderdev94.json", "w"), indent=1)
    for v, d in out.items():
        print(v, {g: (x["kept"], x["pages"]) for g, x in sorted(d.items())})


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 600)
