"""Experiment 94, goals 1 and 2 on experiment 92's 457 test pages, scored as experiment 92's score92.py scored.

    python score94.py [VARIANT]   -> out/score94.json (+ printed), out/lines94.jsonl

Goal 1, typing.  An Azure line takes the class of the layout model's box covering >= 40% of it with the largest
overlap x confidence (score92.yolo_label, unchanged), none -> "none".  Coarse accuracy: the fine class folded to
experiment 39/92's eleven labels (common94.TO_COARSE) against Argon's coarse type, Argon "other" lines left out (as
92).  Fine accuracy: against the fine reference (ref94.jsonl), "other" left out.  Author/affiliation: of lines whose
reference is author or affiliation, the share predicted exactly.  List precision: coarse.
Baseline on the same lines: experiment 39's round-2 model (experiment 92's lines92.jsonl).

Goal 2, reading order (rules frozen on DEV pages by orderdev94.py: experiment 92's XY-cut with tables and verse read
row by row as atoms; direction from the script).
- ours: the line finder's own boxes (conf >= 0.25, de-duplicated; cut94.own_boxes), typed by the layout model,
  direction from the frozen reader's text on our own cuts (Latin letters > Arabic -> left to right).  An Azure line
  takes the rank of the own box it overlaps most (IoU >= 0.3), as experiment 92 did.
- ours_xy92: the same boxes, experiment 92's plain XY-cut (the stage-1 method, for comparison).
- az_rules_ourtypes / az_rules_argontypes: the frozen rules on Azure's boxes (diagnostic).
Successor kept and Kendall tau as score92 (strict: one misplaced line breaks two steps).
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from statistics import mean

from common94 import E92, FINE, OUT, TO_COARSE, area, assert_not_locked, inter, iou, kendall_tau, page_is_rtl, xycut_order
from cut94 import own_boxes
from order94 import order_page

RULES = ("atom",)        # frozen 2026-11-09 from out/orderdev94.json (600 dev pages)


def lay_label(pred, W, H, box):
    a = max(1e-9, area(box))
    cand = [(inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a * s, FINE[c])
            for b, c, s in zip(pred["boxes"], pred["cls"], pred["conf"])
            if inter((b[0] * W, b[1] * H, b[2] * W, b[3] * H), box) / a >= 0.4]
    return max(cand)[1] if cand else "none"


def succ_tau(L, f):
    S = [r for r in L if r.get(f) is not None]
    if len(S) < 2:
        return 0, 0, None
    rs = sorted(S, key=lambda r: r["rank"])
    ps = sorted(S, key=lambda r: r[f])
    nxt = {ps[j]["i"]: ps[j + 1]["i"] for j in range(len(ps) - 1)}
    ok = sum(nxt.get(a["i"]) == b["i"] for a, b in zip(rs, rs[1:]))
    return ok, len(rs) - 1, kendall_tau([r[f] for r in S], [r["rank"] for r in S])


def main(var=""):
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
    refs = [json.loads(l) for l in open(OUT / "ref94.jsonl", encoding="utf-8")]
    assert_not_locked(list(pages))
    PL = json.load(open(OUT / "pred94_lay.json"))
    PN = json.load(open(OUT / "pred94_line.json"))
    r2 = {(d["key"], d["i"]): d.get("r2_label") for d in map(json.loads, open(E92 / "lines92.jsonl", encoding="utf-8"))}
    rd = {}
    rf = OUT / "read" / f"ln94{var}.jsonl"
    if rf.exists():
        for l in open(rf, encoding="utf-8"):
            d = json.loads(l)
            rd[d["key"]] = d["pred"]
    rows = []
    for ref in refs:
        k = ref["key"]
        if k not in PL or k not in PN:
            continue
        pg = pages[k]
        W, H = ref["W"], ref["H"]
        L = [x for x in ref["lines"] if x["box"]]
        res = {x["i"]: dict(key=k, i=x["i"], text=x["text"], box=x["box"], type=x["type"], coarse=x["coarse"],
                            fine=x["fine"], rank=x["rank"], layout=pg["layout"], era=pg["era"], jcode=pg["jcode"],
                            two_col=pg["two_col"], footnotes=pg["footnotes"], r2_label=r2.get((k, x["i"])))
               for x in L}
        for x in L:
            f = lay_label(PL[k], W, H, x["box"])
            res[x["i"]]["lay_fine"] = f
            res[x["i"]]["lay_coarse"] = TO_COARSE.get(f, "none")
        # own boxes, typed, ordered
        own = own_boxes(PN[k], W, H)
        ob = [b for b, _, _ in own]
        ol = [lay_label(PL[k], W, H, b) for b in ob]
        texts = [rd.get(f"{k}_ln{j:03d}", "") for j in range(len(own))]
        rtl = page_is_rtl(texts) if any(texts) else page_is_rtl([x["text"] for x in L])
        o_rules = order_page(ob, ol, rtl, H=H, rules=RULES)
        o_xy = xycut_order(ob, rtl)
        rk_rules = {j: r for r, j in enumerate(o_rules)}
        rk_xy = {j: r for r, j in enumerate(o_xy)}
        for x in L:
            best = max(range(len(ob)), key=lambda j: iou(ob[j], x["box"]), default=None)
            if best is not None and iou(ob[best], x["box"]) >= 0.3:
                res[x["i"]]["ours_rank"] = rk_rules[best]
                res[x["i"]]["ours_xy92_rank"] = rk_xy[best]
        azb = [x["box"] for x in L]
        rtl_az = page_is_rtl([x["text"] for x in L])
        for nm, labs in (("az_rules_ourtypes", [res[x["i"]]["lay_fine"] for x in L]),
                         ("az_rules_argontypes", [x["fine"] for x in L])):
            for r, j in enumerate(order_page(azb, labs, rtl_az, H=H, rules=RULES)):
                res[L[j]["i"]][f"{nm}_rank"] = r
        for r in res.values():
            r["rtl_ours"], r["rtl_azure"] = rtl, rtl_az
        rows += list(res.values())
    with open(OUT / f"lines94{var}.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = dict(pages=len({r["key"] for r in rows}), lines=len(rows), rules=RULES)

    # goal 1
    T = [r for r in rows if r["coarse"] not in (None, "other")]
    ty = {}
    for m, f in (("ours", "lay_coarse"), ("r2_exp39", "r2_label")):
        d = dict(all=round(sum(r[f] == r["coarse"] for r in T) / len(T), 4), n=len(T))
        for g in ("layout", "era"):
            for v in sorted({r[g] for r in T}):
                G = [r for r in T if r[g] == v]
                d[f"{g}:{v}"] = (round(sum(r[f] == r["coarse"] for r in G) / len(G), 4), len(G))
        for lab in sorted({r["coarse"] for r in T}):
            G = [r for r in T if r["coarse"] == lab]
            said = [r for r in T if r[f] == lab]
            d[f"recall:{lab}"] = (round(sum(r[f] == lab for r in G) / len(G), 4), len(G))
            d[f"precision:{lab}"] = (round(sum(r["coarse"] == lab for r in said) / max(1, len(said)), 4), len(said))
        d["confusions"] = Counter(f"{r['coarse']}->{r[f]}" for r in T if r[f] != r["coarse"]).most_common(12)
        ty[m] = d
    TF = [r for r in rows if r["fine"] not in (None, "other")]
    fine = dict(all=round(sum(r["lay_fine"] == r["fine"] for r in TF) / len(TF), 4), n=len(TF))
    for lab in FINE:
        G = [r for r in TF if r["fine"] == lab]
        said = [r for r in TF if r["lay_fine"] == lab]
        if G or said:
            fine[f"recall:{lab}"] = (round(sum(r["lay_fine"] == lab for r in G) / max(1, len(G)), 4), len(G))
            fine[f"precision:{lab}"] = (round(sum(r["fine"] == lab for r in said) / max(1, len(said)), 4), len(said))
    fine["confusions"] = Counter(f"{r['fine']}->{r['lay_fine']}" for r in TF if r["lay_fine"] != r["fine"]).most_common(20)
    AA = [r for r in rows if r["fine"] in ("author", "affiliation")]
    fine["author_affiliation_exact"] = (round(sum(r["lay_fine"] == r["fine"] for r in AA) / max(1, len(AA)), 4), len(AA))
    fine["author_affiliation_as_byline"] = (round(sum(r["lay_fine"] in ("author", "affiliation") for r in AA) / max(1, len(AA)), 4), len(AA))
    ty["fine"] = fine
    out["typing"] = ty

    # goal 2
    by = defaultdict(list)
    for r in rows:
        if r["rank"] is not None:
            by[r["key"]].append(r)
    order = {}
    for m in ("ours", "ours_xy92", "az_rules_ourtypes", "az_rules_argontypes"):
        f = f"{m}_rank"
        acc = defaultdict(lambda: [0, 0])
        taus = defaultdict(list)
        cover = []
        for k, L in by.items():
            pg = pages[k]
            ok, n, t = succ_tau(L, f)
            cover.append(sum(r.get(f) is not None for r in L) / len(L))
            groups = ["all", pg["layout"], pg["era"]] + (["two-col+footnotes"] if pg["two_col"] and pg["footnotes"] else []) \
                + (["latin"] if not L[0]["rtl_azure"] else [])
            for g in groups:
                acc[g][0] += ok
                acc[g][1] += n
                if t is not None:
                    taus[g].append(t)
        order[m] = {g: dict(successor_kept=round(a / max(1, b), 4), steps=b,
                            tau=round(mean(taus[g]), 4) if taus[g] else None, pages=len(taus[g]))
                    for g, (a, b) in sorted(acc.items())}
        order[m]["line_coverage"] = round(mean(cover), 4)
    out["order"] = order
    json.dump(out, open(OUT / f"score94{var}.json", "w"), ensure_ascii=False, indent=1)
    print(json.dumps({k: out[k] for k in ("pages", "lines")}))
    for m in ("ours", "r2_exp39"):
        print("TYPING", m, ty[m]["all"], "list precision", ty[m].get("precision:list"))
    print("FINE", fine["all"], "author/aff", fine["author_affiliation_exact"])
    for m, d in order.items():
        print("ORDER", m, {g: d[g]["successor_kept"] for g in ("all", "single", "two-col", "table", "footnotes") if g in d})


if __name__ == "__main__":
    main(*(sys.argv[1:]))
