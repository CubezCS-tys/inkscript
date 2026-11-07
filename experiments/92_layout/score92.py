"""Experiment 92, step 3: (a) block typing and grouping, (b) reading order, against Argon's structure.

    python3 score92.py   -> out/score92.json (+ printed tables); out/lines92.jsonl (one row per Azure line, every
                            method's label / block / rank, for the pictures and the gap analysis)

Unit: Azure's non-empty lines that Argon placed in a block (reference type = Argon's block type, coarse = experiment
39's eleven labels; "other" lines are left out of typing, as experiment 39 did).

Methods
- azure:  prebuilt-read gives paragraphs and, on some pages, a 'title' role; nothing else.  Label = heading for a
          title paragraph, else body.  Block = Azure paragraph.  Order = Azure's own line order.
- azure_xy: Azure's line boxes, our XY-cut order (no Azure order used), right to left unless the page's Latin letters
          outnumber its Arabic ones (then left to right); azure_xyrtl / r1rtl / r2rtl: always right to left.
- yolo r1 / r2: experiment 39's layout model.  Typing exactly as experiment 39 scored it (score_yolo.py: an Azure line
          takes the class of the predicted box covering >= 40% of it, the largest overlap x confidence; none ->
          "none").  Its OWN lines: boxes with conf >= 0.25, class-agnostic de-duplication (IoU > 0.5, higher
          confidence kept), ordered by our XY-cut, grouped into blocks (below); an Azure line takes the block and rank
          of the own line it overlaps most (IoU >= 0.3; else it is missing from (b) and the grouping).
- rivers: experiment 39's white-space blocks (no types).  An Azure line takes the block covering most of it; order =
          XY-cut over the blocks, then top to bottom, right to left inside a block.
Grouping of own lines (no model): consecutive lines in our order are one block when they have the same class, the
gap between them is < 0.8 median line height, they overlap horizontally by > 50% of the narrower one, and the
second does not start a paragraph (its right edge indented > 1 line height from the first's, or the first ends
> 2 line heights short of the second's left edge; mirrored on a left-to-right page).
Grouping is scored on consecutive pairs of Argon's order: a "break" is a pair in two Argon blocks; precision / recall /
F1 of predicted breaks.  Order: Kendall tau-b per page between Argon's rank and the method's rank, over the lines
both place; and "successor kept": the share of Argon's line-to-next-line steps that the method also takes (strict:
one line out of place breaks two steps).
"""
from __future__ import annotations

import json
from collections import Counter, defaultdict
from statistics import mean, median

from common92 import (LABELS, OUT, area, assert_not_locked, azure_paragraph_of, inter, iou, kendall_tau, page_is_rtl,
                      xycut_order)

CONF = 0.25


def own_lines(pred: dict, W: float, H: float):
    """De-duplicated own line boxes in page units: [(box, label, conf)]."""
    B = sorted(((b[0] * W, b[1] * H, b[2] * W, b[3] * H), LABELS[c], s)
               for b, c, s in zip(pred["boxes"], pred["cls"], pred["conf"]) if s >= CONF)
    B.sort(key=lambda x: -x[2])
    keep = []
    for b in B:
        if all(iou(b[0], k[0]) <= 0.5 for k in keep):
            keep.append(b)
    return keep


def group_blocks(boxes, labels, order, rtl: bool = True) -> list[int]:
    """Block id per box (index), from consecutive boxes in reading order."""
    if not boxes:
        return []
    hs = sorted(b[3] - b[1] for b in boxes)
    mh = hs[len(hs) // 2]
    blk = [0] * len(boxes)
    cur = 0
    for a, b in zip(order, order[1:]):
        A, Bx = boxes[a], boxes[b]
        same = labels[a] == labels[b]
        gap = Bx[1] - A[3]
        ov = min(A[2], Bx[2]) - max(A[0], Bx[0])
        narrow = min(A[2] - A[0], Bx[2] - Bx[0])
        para = ((A[2] - Bx[2] > mh) or (A[0] - Bx[0] > 2 * mh)) if rtl else ((Bx[0] - A[0] > mh) or (Bx[2] - A[2] > 2 * mh))
        if not (same and -0.5 * mh < gap < 0.8 * mh and ov > 0.5 * narrow and not para):
            cur += 1
        blk[b] = cur
    blk[order[0]] = 0 if order else 0
    return blk


def yolo_label(pred, W, H, box):
    a = max(1e-9, area(box))
    cand = [(inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a * s, LABELS[c])
            for b, c, s in zip(pred["boxes"], pred["cls"], pred["conf"])
            if inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a >= 0.4]
    return max(cand)[1] if cand else "none"


def main():
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(OUT / "pages92.jsonl", encoding="utf-8")}
    refs = [json.loads(l) for l in open(OUT / "ref92.jsonl", encoding="utf-8")]
    assert_not_locked(list(pages))
    Y = {m: json.load(open(OUT / f"yolo92_{m}.json")) for m in ("r1", "r2")}
    R = json.load(open(OUT / "rivers92.json"))
    rows = []
    for ref in refs:
        k = ref["key"]
        pg = pages[k]
        if any(k not in Y[m] for m in Y) or k not in R:
            continue
        W, H = ref["W"], ref["H"]
        L = [x for x in ref["lines"] if x["box"]]
        para = azure_paragraph_of(pg["azure"], pg["page"], L)
        res = {x["i"]: dict(key=k, i=x["i"], text=x["text"], box=x["box"], type=x["type"], coarse=x["coarse"],
                            block=x["block"], rank=x["rank"], layout=pg["layout"], era=pg["era"], jcode=pg["jcode"],
                            rtl=None)
               for x in L}
        # azure
        for x in L:
            pi, role = para.get(x["i"], (None, None))
            r = res[x["i"]]
            r["azure_label"] = "heading" if role in ("title", "sectionHeading") else "furniture" if role in (
                "pageHeader", "pageFooter", "pageNumber") else "footnote" if role == "footnote" else "body"
            r["azure_block"] = pi if pi is not None else f"x{x['i']}"
            r["azure_rank"] = x["i"]
        rtl = page_is_rtl([x["text"] for x in L])
        for nm, d in (("azure_xy", rtl), ("azure_xyrtl", True)):
            for rk, j in enumerate(xycut_order([x["box"] for x in L], d)):
                res[L[j]["i"]][f"{nm}_rank"] = rk
        # yolo
        for m in Y:
            p = Y[m][k]
            own = own_lines(p, W, H)
            ob = [b for b, _, _ in own]
            ol = [c for _, c, _ in own]
            oo = xycut_order(ob, rtl)
            rank = {j: rk for rk, j in enumerate(oo)}
            rank_rtl = {j: rk for rk, j in enumerate(xycut_order(ob, True))}
            blk = group_blocks(ob, ol, oo, rtl)
            for x in L:
                r = res[x["i"]]
                r[f"{m}_label"] = yolo_label(p, W, H, x["box"])
                best = max(range(len(ob)), key=lambda j: iou(ob[j], x["box"]), default=None)
                if best is not None and iou(ob[best], x["box"]) >= 0.3:
                    r[f"{m}_rank"] = rank[best]
                    r[f"{m}rtl_rank"] = rank_rtl[best]
                    r[f"{m}_block"] = blk[best]
                    r[f"{m}_own"] = best
                    r[f"{m}_own_label"] = ol[best]
        # rivers
        rv = R[k]
        sx, sy = W / rv["W"], H / rv["H"]
        rb = [(x * sx, y * sy, (x + w) * sx, (y + h) * sy) for x, y, w, h in rv["blocks"]]
        bo = {j: rk for rk, j in enumerate(xycut_order(rb, rtl))}
        inblk = defaultdict(list)
        for x in L:
            best = max(range(len(rb)), key=lambda j: inter(rb[j], x["box"]), default=None)
            if best is not None and inter(rb[best], x["box"]) > 0.3 * area(x["box"]):
                res[x["i"]]["rivers_block"] = best
                inblk[best].append(x)
        rk = 0
        for j in sorted(inblk, key=lambda j: bo[j]):
            for x in sorted(inblk[j], key=lambda x: ((x["box"][1] + x["box"][3]) / 2, -x["box"][2] if rtl else x["box"][0])):
                res[x["i"]]["rivers_rank"] = rk
                rk += 1
        for r in res.values():
            r["rtl"] = rtl
        rows += list(res.values())
    with open(OUT / "lines92.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = dict(conf=CONF, pages=len({r["key"] for r in rows}), lines=len(rows))

    # (a) typing
    T = [r for r in rows if r["coarse"] not in (None, "other")]
    ty = {}
    for m in ("azure", "r1", "r2"):
        f = f"{m}_label"
        d = dict(all=round(sum(r[f] == r["coarse"] for r in T) / len(T), 4), n=len(T))
        for g in ("layout", "era"):
            for v in sorted({r[g] for r in T}):
                G = [r for r in T if r[g] == v]
                d[f"{g}:{v}"] = (round(sum(r[f] == r["coarse"] for r in G) / len(G), 4), len(G))
        for lab in LABELS:
            G = [r for r in T if r["coarse"] == lab]
            said = [r for r in T if r[f] == lab]
            if G:
                d[f"recall:{lab}"] = (round(sum(r[f] == lab for r in G) / len(G), 4), len(G))
                d[f"precision:{lab}"] = (round(sum(r["coarse"] == lab for r in said) / max(1, len(said)), 4), len(said))
        for t in sorted({r["type"] for r in T}):
            G = [r for r in T if r["type"] == t]
            d[f"fine:{t}"] = (round(sum(r[f] == r["coarse"] for r in G) / len(G), 4), len(G))
        d["confusions"] = Counter(f"{r['coarse']}->{r[f]}" for r in T if r[f] != r["coarse"]).most_common(15)
        ty[m] = d
    out["typing"] = ty

    # (a) grouping, (b) order
    by = defaultdict(list)
    for r in rows:
        if r["rank"] is not None:
            by[r["key"]].append(r)
    grp, order = {}, {}
    for m in ("azure", "r1", "r2", "rivers"):
        tp = fp = fn = 0
        exact = tot = 0
        for k, L in by.items():
            L = sorted(L, key=lambda r: r["rank"])
            for a, b in zip(L, L[1:]):
                if f"{m}_block" not in a or f"{m}_block" not in b:
                    if a["block"] != b["block"]:
                        fn += 1
                    continue
                rb, pb = a["block"] != b["block"], a[f"{m}_block"] != b[f"{m}_block"]
                tp += rb and pb
                fp += pb and not rb
                fn += rb and not pb
            ref_b = defaultdict(set)
            pr_b = defaultdict(set)
            for r in L:
                ref_b[r["block"]].add(r["i"])
                if f"{m}_block" in r:
                    pr_b[r[f"{m}_block"]].add(r["i"])
            ps = {frozenset(s) for s in pr_b.values()}
            exact += sum(frozenset(s) in ps for s in ref_b.values())
            tot += len(ref_b)
        P, Rr = tp / max(1, tp + fp), tp / max(1, tp + fn)
        grp[m] = dict(precision=round(P, 4), recall=round(Rr, 4), f1=round(2 * P * Rr / max(1e-9, P + Rr), 4),
                      exact_blocks=round(exact / max(1, tot), 4), ref_blocks=tot)
    out["grouping"] = grp
    for m in ("azure", "azure_xy", "azure_xyrtl", "r1", "r1rtl", "r2", "r2rtl", "rivers"):
        f = f"{m}_rank"
        taus = defaultdict(list)
        succ = defaultdict(lambda: [0, 0])
        cover = []
        for k, L in by.items():
            S = [r for r in L if f in r]
            cover.append(len(S) / len(L))
            t = kendall_tau([r[f] for r in S], [r["rank"] for r in S])
            if len(S) >= 2:
                rs = sorted(S, key=lambda r: r["rank"])
                ps = sorted(S, key=lambda r: r[f])
                nxt = {ps[j]["i"]: ps[j + 1]["i"] for j in range(len(ps) - 1)}
                ok = sum(nxt.get(a["i"]) == b["i"] for a, b in zip(rs, rs[1:]))
                for g in ("all", pages[k]["layout"], pages[k]["era"]):
                    succ[g][0] += ok
                    succ[g][1] += len(rs) - 1
                if pages[k]["two_col"] and pages[k]["footnotes"]:
                    succ["two-col+footnotes"][0] += ok
                    succ["two-col+footnotes"][1] += len(rs) - 1
            if t is not None:
                taus["all"].append(t)
                taus[pages[k]["layout"]].append(t)
                taus[pages[k]["era"]].append(t)
                if pages[k]["two_col"] and pages[k]["footnotes"]:
                    taus["two-col+footnotes"].append(t)
        order[m] = {g: dict(mean=round(mean(v), 4), median=round(median(v), 4),
                            pages_ge_0_95=round(sum(x >= 0.95 for x in v) / len(v), 4), n=len(v))
                    for g, v in sorted(taus.items())}
        for g, (a, b) in succ.items():
            order[m].setdefault(g, {})["successor_kept"] = round(a / max(1, b), 4)
        order[m]["line_coverage"] = round(mean(cover), 4)
    out["order"] = order
    json.dump(out, open(OUT / "score92.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("pages", "lines")}))
    for m, d in ty.items():
        print("TYPING", m, d["all"], {k: v for k, v in d.items() if k.startswith(("layout", "recall"))})
    print("GROUPING", json.dumps(grp))
    for m, d in order.items():
        print("ORDER", m, json.dumps(d))


if __name__ == "__main__":
    main()
