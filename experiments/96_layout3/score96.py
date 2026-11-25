"""Experiment 96, goals 1, 2 and 4 on experiment 92's 457 test pages, scored ONCE with the frozen choices, by
experiment 94's score94.py conventions (its functions imported, unchanged).

    python score96.py   -> out/score96.json, out/lines96.jsonl

Typing: the new layout model (out/gpu/pred96_lay.json) against experiment 94's fine reference, with experiment 94's
model on the same lines (94_layout2/out/lines94.jsonl) as the baseline.  Author/affiliation exact on the 102 byline
lines and on the 98 lines the stage-2 hand check called clear.  Per-class recall change (classes with >= 50 lines).
Goal 4: coarse typing with table and verse merged.
Order: the line finder's own boxes (experiment 94's, cut94.own_boxes) typed by the new model, direction from the
frozen reader's text on our cuts (as score94), ordered by ORDER (frozen on dev); also the column rule and experiment
94's rules on the same boxes for comparison.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from statistics import mean

from common96 import E, E92, FINE, O94, OUT, TO_COARSE, assert_not_locked, iou, page_is_rtl

sys.path.insert(0, str(E / "94_layout2"))
from cut94 import own_boxes  # noqa: E402
from order94 import order_page  # noqa: E402
from score94 import lay_label, succ_tau  # noqa: E402
from order96 import order_cols  # noqa: E402

ORDER = "FROZEN_LATER"


def main():
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
    refs = [json.loads(l) for l in open(O94 / "ref94.jsonl", encoding="utf-8")]
    assert_not_locked(list(pages))
    PL = json.load(open(OUT / "gpu/pred96_lay.json"))
    PN = json.load(open(O94 / "pred94_line.json"))
    old = {(d["key"], d["i"]): d for d in map(json.loads, open(O94 / "lines94.jsonl", encoding="utf-8"))}
    rd = {}
    for l in open(O94 / "read/ln94.jsonl", encoding="utf-8"):
        d = json.loads(l)
        rd[d["key"]] = d["pred"]
    meth = {"rules94": lambda b, l, rtl, H, W: order_page(b, l, rtl, H=H, rules=("atom",)),
            "cols": lambda b, l, rtl, H, W: order_cols(b, l, rtl, H=H, W=W)}
    if (OUT / "next96.pt").exists():
        from next96 import order_learned
        meth["learned"] = order_learned
    rows = []
    for ref in refs:
        k = ref["key"]
        if k not in PL or k not in PN:
            continue
        pg = pages[k]
        W, H = ref["W"], ref["H"]
        L = [x for x in ref["lines"] if x["box"]]
        res = {}
        for x in L:
            o = old.get((k, x["i"]), {})
            f = lay_label(PL[k], W, H, x["box"])
            res[x["i"]] = dict(key=k, i=x["i"], type=x["type"], coarse=x["coarse"], fine=x["fine"], rank=x["rank"],
                               layout=pg["layout"], era=pg["era"], lay_fine=f, lay_coarse=TO_COARSE.get(f, "none"),
                               lay94_fine=o.get("lay_fine"), lay94_coarse=o.get("lay_coarse"),
                               ours94_rank=o.get("ours_rank"))
        own = own_boxes(PN[k], W, H)
        ob = [b for b, _, _ in own]
        ol = [lay_label(PL[k], W, H, b) for b in ob]
        texts = [rd.get(f"{k}_ln{j:03d}", "") for j in range(len(own))]
        rtl = page_is_rtl(texts) if any(texts) else page_is_rtl([x["text"] for x in L])
        for m, fn in meth.items():
            rk = {j: r for r, j in enumerate(fn(ob, ol, rtl, H, W))}
            for x in L:
                best = max(range(len(ob)), key=lambda j: iou(ob[j], x["box"]), default=None)
                if best is not None and iou(ob[best], x["box"]) >= 0.3:
                    res[x["i"]][f"{m}_rank"] = rk[best]
        for r in res.values():
            r["rtl"] = rtl
        rows += list(res.values())
    with open(OUT / "lines96.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    out = dict(pages=len({r["key"] for r in rows}), lines=len(rows), order_frozen=ORDER)
    T = [r for r in rows if r["coarse"] not in (None, "other")]
    ty = {}
    for m, f in (("ours96", "lay_coarse"), ("ours94", "lay94_coarse")):
        d = dict(all=round(sum(r[f] == r["coarse"] for r in T) / len(T), 4), n=len(T))
        mg = lambda v: "table" if v == "verse" else v  # noqa: E731
        d["table_verse_merged"] = round(sum(mg(r[f]) == mg(r["coarse"]) for r in T) / len(T), 4)
        for lab in sorted({r["coarse"] for r in T}):
            G = [r for r in T if r["coarse"] == lab]
            said = [r for r in T if r[f] == lab]
            d[f"recall:{lab}"] = (round(sum(r[f] == lab for r in G) / len(G), 4), len(G))
            d[f"precision:{lab}"] = (round(sum(r["coarse"] == lab for r in said) / max(1, len(said)), 4), len(said))
        d["confusions"] = Counter(f"{r['coarse']}->{r[f]}" for r in T if r[f] != r["coarse"]).most_common(12)
        ty[m] = d
    TF = [r for r in rows if r["fine"] not in (None, "other")]
    fine = {}
    for m, f in (("ours96", "lay_fine"), ("ours94", "lay94_fine")):
        d = dict(all=round(sum(r[f] == r["fine"] for r in TF) / len(TF), 4))
        for lab in FINE:
            G = [r for r in TF if r["fine"] == lab]
            if G:
                d[f"recall:{lab}"] = (round(sum(r[f] == lab for r in G) / len(G), 4), len(G))
        AA = [r for r in rows if r["fine"] in ("author", "affiliation")]
        d["author_affiliation_exact"] = (round(sum(r[f] == r["fine"] for r in AA) / len(AA), 4), len(AA))
        allb = json.load(open(O94 / "byline94_all.json"))
        hand = json.load(open(O94 / "byline94_hand.json"))
        bad = set(hand["clearly_wrong"])
        mixed = set(hand["mixed_name_and_affiliation_in_one_line"])
        idx = {(b["key"], b["i"]): n for n, b in enumerate(allb)}
        for tag, drop in (("hand_clear98", bad), ("hand_clear_unmixed", bad | mixed)):
            S = [r for r in AA if idx.get((r["key"], r["i"])) is not None and idx[(r["key"], r["i"])] not in drop]
            d[tag] = (round(sum(r[f] == r["fine"] for r in S) / max(1, len(S)), 4), len(S))
        d["author_affiliation_as_byline"] = round(sum(r[f] in ("author", "affiliation") for r in AA) / len(AA), 4)
        fine[m] = d
    fine["recall_change_points"] = {lab: round(100 * (fine["ours96"][f"recall:{lab}"][0] - fine["ours94"][f"recall:{lab}"][0]), 2)
                                    for lab in FINE if f"recall:{lab}" in fine["ours96"]
                                    and fine["ours96"][f"recall:{lab}"][1] >= 50}
    fine["confusions96"] = Counter(f"{r['fine']}->{r['lay_fine']}" for r in TF if r["lay_fine"] != r["fine"]).most_common(20)
    ty["fine"] = fine
    out["typing"] = ty
    by = defaultdict(list)
    for r in rows:
        if r["rank"] is not None:
            by[r["key"]].append(r)
    order = {}
    for m in list(meth) + ["ours94"]:
        f = f"{m}_rank"
        acc = defaultdict(lambda: [0, 0])
        for k, L in by.items():
            pg = pages[k]
            ok, n, _ = succ_tau(L, f)
            for g in ["all", pg["layout"], pg["era"]] + ([] if L[0]["rtl"] else ["latin"]):
                acc[g][0] += ok
                acc[g][1] += n
        order[m] = {g: dict(successor_kept=round(a / max(1, b), 4), steps=b) for g, (a, b) in sorted(acc.items())}
    out["order"] = order
    json.dump(out, open(OUT / "score96.json", "w"), ensure_ascii=False, indent=1)
    print("TYPING", {m: (ty[m]["all"], ty[m]["table_verse_merged"], ty[m].get("precision:list")) for m in ("ours96", "ours94")})
    print("FINE", {m: (fine[m]["all"], fine[m]["author_affiliation_exact"], fine[m]["hand_clear98"],
                       fine[m]["hand_clear_unmixed"]) for m in ("ours96", "ours94")})
    print("RECALL CHANGE", fine["recall_change_points"])
    for m, d in order.items():
        print("ORDER", m, {g: d[g]["successor_kept"] for g in ("all", "single", "two-col", "table", "footnotes", "latin") if g in d})


if __name__ == "__main__":
    main()
