"""Experiment 96, goal 2 development on DEV pages only (the training pool's validation documents, never the test):
reading-order candidates against Argon's order, successor kept / Kendall tau by layout.

    python orderdev96.py cache            -> out/dev96_pages.pkl  every validation page with >= 5 ranked lines:
                                             Azure boxes, texts, Argon fine types and ranks, layout (build92.layout_of)
    python orderdev96.py score [BOXES]    -> out/orderdev96[_own].json
        BOXES = azure (default): Azure's boxes with Argon's types (oracle, as experiment 94's orderdev94);
                own: the line finder's boxes typed by a layout model (pred json given by env PRED_LINE, PRED_LAY),
                Azure lines take the rank of the own box they overlap most (IoU >= 0.3), as score94 does.
Methods: rules94 = experiment 94's frozen rules (XY-cut + table/verse atoms); cols = order96.order_cols;
learned = next96.order_learned (if out/next96.pt exists).  Pages: "dev600" = experiment 94's 600 order-dev pages
(seed 94 shuffle, first 600 usable), "all" = every usable validation page.
"""
from __future__ import annotations

import json
import os
import pickle
import random
import sys
from collections import defaultdict

from common96 import E, O94, OUT, FINE, TO_COARSE, azure_lines, assert_not_locked, inventory_azure, iou, kendall_tau, page_is_rtl

sys.path.insert(0, str(E / "92_layout"))
sys.path.insert(0, str(E / "94_layout2"))
from build92 import layout_of  # noqa: E402
from order94 import order_page  # noqa: E402
from order96 import order_cols  # noqa: E402


def cache():
    rows = [json.loads(l) for l in open(O94 / "train94.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["split"] == "val"]
    random.Random(94).shuffle(rows)
    az = inventory_azure()
    assert_not_locked([r["key"] for r in rows])
    out, n600 = [], 0
    for r in rows:
        L = [x for x in r["lines"] if x["rank"] is not None]
        if len(L) < 5:
            continue
        A, W, H = azure_lines(az[r["stem"]], r["page"])
        text = {x["i"]: x["text"] for x in A}
        box = {x["i"]: x["box"] for x in A}
        blocks = defaultdict(lambda: dict(ids=[], coarse=None, type=None))
        for x in L:
            b = blocks[x["block"]]
            b["ids"].append(x["i"])
            b["coarse"] = TO_COARSE.get(x["fine"] or "other")
            b["type"] = "footnote" if x["fine"] == "footnote" else x["fine"]
        lay, _ = layout_of(list(blocks.values()), A, W)
        n600 += 1
        out.append(dict(key=r["key"], W=W, H=H, layout=lay, dev600=n600 <= 600,
                        rtl=page_is_rtl([text[x["i"]] for x in L]),
                        lines=[dict(i=x["i"], box=box[x["i"]], text=text[x["i"]], fine=x["fine"], rank=x["rank"])
                               for x in L]))
    pickle.dump(out, open(OUT / "dev96_pages.pkl", "wb"))
    print(len(out), "pages", sum(p["dev600"] for p in out), "in dev600")


def succ(ref_rank, order):
    S = [i for i in order if i in ref_rank]
    rs = sorted(S, key=lambda i: ref_rank[i])
    nxt = {S[j]: S[j + 1] for j in range(len(S) - 1)}
    return sum(nxt.get(a) == b for a, b in zip(rs, rs[1:])), max(0, len(rs) - 1)


def methods():
    M = {"rules94": lambda b, l, rtl, H, W: order_page(b, l, rtl, H=H, rules=("atom",)),
         "cols": lambda b, l, rtl, H, W: order_cols(b, l, rtl, H=H, W=W)}
    if (OUT / "next96.pt").exists():
        from next96 import order_learned
        M["learned"] = lambda b, l, rtl, H, W: order_learned(b, l, rtl, H, W)
    return M


def lay_label(pred, W, H, box):
    from common96 import area, inter
    a = max(1e-9, area(box))
    cand = [(inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a * s, FINE[c])
            for b, c, s in zip(pred["boxes"], pred["cls"], pred["conf"])
            if inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a >= 0.4]
    return max(cand)[1] if cand else "none"


def score(boxes="azure", only=None):
    P = pickle.load(open(OUT / "dev96_pages.pkl", "rb"))
    M = methods()
    if only:
        M = {k: v for k, v in M.items() if k in only.split(",")}
    if boxes == "own":
        sys.path.insert(0, str(E / "94_layout2"))
        from cut94 import own_boxes
        PN = json.load(open(os.environ["PRED_LINE"]))
        PL = json.load(open(os.environ["PRED_LAY"]))
    acc = {m: defaultdict(lambda: [0, 0]) for m in M}
    taus = {m: defaultdict(list) for m in M}
    for p in P:
        L, W, H = p["lines"], p["W"], p["H"]
        groups = ["all", p["layout"]] + (["dev600", f"dev600:{p['layout']}"] if p["dev600"] else []) + \
            ([] if p["rtl"] else ["latin"])
        if boxes == "azure":
            bx, lab, ref = [x["box"] for x in L], [x["fine"] for x in L], {k: x["rank"] for k, x in enumerate(L)}
        else:
            if p["key"] not in PN or p["key"] not in PL:
                continue
            own = own_boxes(PN[p["key"]], W, H)
            bx = [b for b, _, _ in own]
            lab = [lay_label(PL[p["key"]], W, H, b) for b in bx]
            home = {}
            for k, x in enumerate(L):
                j = max(range(len(bx)), key=lambda j: iou(bx[j], x["box"]), default=None)
                if j is not None and iou(bx[j], x["box"]) >= 0.3:
                    home[k] = j
        for m, fn in M.items():
            o = fn(bx, lab, p["rtl"], H, W)
            if boxes == "azure":
                k_, s_ = succ(ref, o)
                pos = {i: q for q, i in enumerate(o)}
                t = kendall_tau([pos[i] for i in range(len(L))], [ref[i] for i in range(len(L))])
            else:      # Azure lines ranked by their own box (score94's succ_tau, strict)
                pos = {i: q for q, i in enumerate(o)}
                S = [(k, pos[home[k]]) for k in range(len(L)) if k in home]
                rs = sorted(S, key=lambda t: L[t[0]]["rank"])
                ps = sorted(S, key=lambda t: t[1])
                nxt = {ps[j][0]: ps[j + 1][0] for j in range(len(ps) - 1)}
                k_ = sum(nxt.get(a[0]) == b[0] for a, b in zip(rs, rs[1:]))
                s_ = max(0, len(rs) - 1)
                t = kendall_tau([q for _, q in S], [L[k]["rank"] for k, _ in S]) if len(S) > 1 else None
            for g in groups:
                acc[m][g][0] += k_
                acc[m][g][1] += s_
                if t is not None:
                    taus[m][g].append(t)
    out = {m: {g: dict(kept=round(a / max(1, b), 4), steps=b, pages=len(taus[m][g]),
                       tau=round(sum(taus[m][g]) / max(1, len(taus[m][g])), 4)) for g, (a, b) in sorted(d.items())}
           for m, d in acc.items()}
    tag = "" if boxes == "azure" else "_own"
    old = json.load(open(OUT / f"orderdev96{tag}.json")) if (OUT / f"orderdev96{tag}.json").exists() else {}
    old.update(out)
    json.dump(old, open(OUT / f"orderdev96{tag}.json", "w"), indent=1)
    for m, d in out.items():
        print(m, {g: (x["kept"], x["pages"]) for g, x in d.items()})


if __name__ == "__main__":
    {"cache": lambda *a: cache(), "score": score}[sys.argv[1]](*sys.argv[2:])
