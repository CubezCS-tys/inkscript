"""Experiment 94: pictures of what still fails (for looking at; never sent anywhere).

    python look94.py KEY [KEY ...]   -> out/look/<key>.jpg  three panels:
        1. Argon: fine types (colour) + Argon's reading order (red path)
        2. ours: the layout model's fine type of each Azure line (colour; a cross = wrong vs Argon) + our order over
           our own boxes (red path)
        3. line finder: own boxes (blue, direction class as a letter u/c/f/a), Azure lines no own box covers
           (thick red), Azure lines (thin grey)
    python look94.py worst N        -> the N pages with most typing errors and the N with most order steps lost
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict

import cv2
import numpy as np

from common94 import E92, FINE, OUT, area, inter
from common92 import render_gray
from cut94 import own_boxes
from score94 import RULES, lay_label  # noqa: F401
from order94 import order_page

COL = {"title": (0, 0, 200), "author": (0, 120, 255), "affiliation": (0, 200, 255), "abstract": (120, 60, 0),
       "heading": (0, 0, 120), "body": (0, 150, 0), "list": (200, 120, 0), "footnote": (0, 140, 255),
       "reference": (120, 0, 0), "table": (180, 0, 180), "caption": (0, 180, 180), "page_number": (90, 90, 90),
       "header": (150, 150, 150), "equation": (40, 80, 160), "verse": (200, 0, 120), "other": (60, 60, 60),
       None: (200, 200, 200), "none": (0, 0, 0)}


def panel(g, s, title):
    im = cv2.cvtColor(g, cv2.COLOR_GRAY2BGR)
    cv2.putText(im, title, (10, 28), 0, 0.8, (255, 0, 0), 2)
    return im


def draw(key, rows_by, PL, PN, own_meta):
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
    p = pages[key]
    L = rows_by[key]
    g = render_gray(p["pdf"], p["page"], dpi=100)
    ref = next(json.loads(l) for l in open(OUT / "ref94.jsonl", encoding="utf-8") if l.startswith(f'{{"key": "{key}"'))
    W, H = ref["W"], ref["H"]
    s = g.shape[1] / W
    P = lambda b: ((int(b[0] * s), int(b[1] * s)), (int(b[2] * s), int(b[3] * s)))  # noqa: E731
    c = lambda b: (int((b[0] + b[2]) / 2 * s), int((b[1] + b[3]) / 2 * s))  # noqa: E731
    a = panel(g, s, "Argon: fine types + order")
    for r in L:
        cv2.rectangle(a, *P(r["box"]), COL.get(r["fine"], (0, 0, 0)), 2)
    seq = sorted([r for r in L if r["rank"] is not None], key=lambda r: r["rank"])
    for x, y in zip(seq, seq[1:]):
        cv2.line(a, c(x["box"]), c(y["box"]), (0, 0, 255), 1)
    b = panel(g, s, "ours: layout model types + our order")
    for r in L:
        cv2.rectangle(b, *P(r["box"]), COL.get(r["lay_fine"], (0, 0, 0)), 2)
        if r["fine"] not in (None, "other") and r["lay_fine"] != r["fine"]:
            (x0, y0), (x1, y1) = P(r["box"])
            cv2.line(b, (x0, y0), (x1, y1), (0, 0, 255), 1)
    own = own_boxes(PN[key], W, H)
    ob = [o for o, _, _ in own]
    ol = [lay_label(PL[key], W, H, o) for o in ob]
    o = order_page(ob, ol, L[0]["rtl_ours"], H=H, rules=RULES)
    for x, y in zip(o, o[1:]):
        cv2.line(b, c(ob[x]), c(ob[y]), (0, 0, 255), 1)
    d = panel(g, s, "line finder: own boxes, missed Azure lines")
    for r in L:
        cv2.rectangle(d, *P(r["box"]), (180, 180, 180), 1)
        cov = max((inter(q, r["box"]) / max(1e-9, area(r["box"])) for q in ob), default=0)
        if cov < 0.3:
            cv2.rectangle(d, *P(r["box"]), (0, 0, 255), 3)
    for q, cl, _ in own:
        cv2.rectangle(d, *P(q), (255, 80, 0), 1)
        if cl:
            cv2.putText(d, "ucfa"[cl], P(q)[0], 0, 0.5, (255, 0, 0), 1)
    leg = np.full((40, a.shape[1] * 3, 3), 255, np.uint8)
    x = 5
    for k in FINE:
        cv2.rectangle(leg, (x, 10), (x + 14, 24), COL[k], -1)
        cv2.putText(leg, k, (x + 18, 23), 0, 0.45, (0, 0, 0), 1)
        x += 18 + 9 * len(k) + 12
    im = np.vstack([np.hstack([a, b, d]), leg])
    (OUT / "look").mkdir(exist_ok=True)
    cv2.imwrite(str(OUT / "look" / f"{key}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 85])
    return OUT / "look" / f"{key}.jpg"


def main(args):
    rows_by = defaultdict(list)
    for l in open(OUT / "lines94.jsonl", encoding="utf-8"):
        r = json.loads(l)
        rows_by[r["key"]].append(r)
    PL = json.load(open(OUT / "pred94_lay.json"))
    PN = json.load(open(OUT / "pred94_line.json"))
    if args[0] == "worst":
        n = int(args[1])
        typ = sorted(rows_by, key=lambda k: -sum(r["fine"] not in (None, "other") and r["lay_fine"] != r["fine"]
                                                 for r in rows_by[k]))[:n]
        def lost(k):
            S = sorted([r for r in rows_by[k] if r["rank"] is not None and r.get("ours_rank") is not None],
                       key=lambda r: r["rank"])
            ps = sorted(S, key=lambda r: r["ours_rank"])
            nxt = {ps[j]["i"]: ps[j + 1]["i"] for j in range(len(ps) - 1)}
            return sum(nxt.get(x["i"]) != y["i"] for x, y in zip(S, S[1:]))
        order = sorted(rows_by, key=lambda k: -lost(k))[:n]
        keys = list(dict.fromkeys(typ + order))
        print("typing:", typ)
        print("order:", order)
    else:
        keys = args
    for k in keys:
        print(draw(k, rows_by, PL, PN, None))


if __name__ == "__main__":
    main(sys.argv[1:])
