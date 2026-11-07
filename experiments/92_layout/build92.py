"""Experiment 92, step 1: the layout test set.

    python3 build92.py pool     -> out/pool92.jsonl   every held-out page with Argon structure (flags, no selection)
    python3 build92.py select   -> out/pages92.jsonl  the test pages + out/ref92.jsonl (per page: Azure lines with
                                   Argon's type, block and reading rank)

Pool: articles of experiment 81's 26 held-out journals (experiment 76's split76.json) that Argon answered (experiment
76's inventory: v2_55, v33_300, v33_300b, j0097), first copy of each article.  A page is usable when Argon gave it
blocks, it has >= 5 non-empty Azure lines and Argon placed >= 80% of them.  Excluded: locked journals / documents
(both guards, asserted), and every DOCUMENT one of whose pages trained or validated experiment 39's layout model
(round 1 or 2), so the model is tested on documents it never saw.
Layout of a page (from Argon's types and Azure's boxes): table (a table block of >= 4 lines) > two columns (>= 4
narrow body lines in each half of the text area, overlapping in height) > footnotes (a footnote block) > single.
Selection (seed 92): every pool page that experiment 81 also tested (its judged lines give truth for the reader
test), then fill each era x layout cell towards a target, at most 12 pages a document and 140 pages of journal 0097.
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict

from common92 import (ARGON_SETS, E, INV, OUT, argon_pages, assert_not_locked, azure_lines, era_of, fixpath,
                      heldout_codes, is_locked_any)

Y39 = E / "39_ink_geometry/out/train"
TARGET = 460


def yolo_seen_docs() -> set[str]:
    seen = set()
    for y in ("yolo", "yolo2"):
        for split in ("train", "val"):
            d = Y39 / y / "images" / split
            if d.exists():
                seen |= {f.name.rsplit("_p", 1)[0] for f in d.glob("*.jpg")}
    return seen


def layout_of(blocks, lines, W) -> tuple[str, dict]:
    by_i = {ln["i"]: ln for ln in lines}
    typ = {}
    for b in blocks:
        for i in b["ids"]:
            typ.setdefault(i, b["coarse"])
    has_table = any(b["coarse"] == "table" and len(b["ids"]) >= 4 for b in blocks)
    has_fn = any(b["type"] == "footnote" for b in blocks)
    body = [by_i[i] for i, t in typ.items() if t in ("body", "list", "references", "footnote") and i in by_i
            and by_i[i]["box"]]
    two = False
    if body:
        x0 = min(l["box"][0] for l in body)
        x1 = max(l["box"][2] for l in body)
        tw, mid = x1 - x0, (x0 + x1) / 2
        nar = [l for l in body if l["box"][2] - l["box"][0] < 0.55 * tw]
        R = [l for l in nar if l["box"][0] > mid - 0.05 * tw]
        L = [l for l in nar if l["box"][2] < mid + 0.05 * tw]
        if len(R) >= 4 and len(L) >= 4:
            ry = (min(l["box"][1] for l in R), max(l["box"][3] for l in R))
            ly = (min(l["box"][1] for l in L), max(l["box"][3] for l in L))
            two = min(ry[1], ly[1]) - max(ry[0], ly[0]) > 0
    lay = "table" if has_table else "two-col" if two else "footnotes" if has_fn else "single"
    return lay, dict(table=has_table, two_col=two, footnotes=has_fn)


def pool():
    S = heldout_codes()
    seen_docs = yolo_seen_docs()
    raw = dict(ARGON_SETS)
    done, rows = set(), []
    for l in open(INV, encoding="utf-8"):
        a = json.loads(l)
        if a["jcode"] not in S or not a["answered"] or a["stem"] in done or a["set"] not in raw:
            continue
        if is_locked_any(a["stem"]):
            continue
        done.add(a["stem"])
        az, pdf = fixpath(a["azure"]), fixpath(a["pdf"])
        if not (az.exists() and pdf.exists()):
            continue
        AP = argon_pages(raw[a["set"]], a["stem"])
        for p, blocks in sorted(AP.items()):
            try:
                lines, W, H = azure_lines(str(az), p)
            except IndexError:
                continue
            placed = {i for b in blocks for i in b["ids"]}
            n = len(lines)
            if n < 5 or len(placed & {x["i"] for x in lines}) < 0.8 * n:
                continue
            lay, fl = layout_of(blocks, lines, W)
            rows.append(dict(stem=a["stem"], page=p, key=f"{a['stem']}_p{p:03d}", jcode=a["jcode"], year=a["year"],
                             era=era_of(a["year"]), set=a["set"], azure=str(az), pdf=str(pdf), lines=n,
                             layout=lay, **fl, yolo_seen=a["stem"] in seen_docs))
        print(a["set"], a["stem"], len(rows), flush=True)
    assert_not_locked([r["key"] for r in rows])
    with open(OUT / "pool92.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows), "pool pages;", Counter((r["era"], r["layout"]) for r in rows if not r["yolo_seen"]))


def select():
    P = [json.loads(l) for l in open(OUT / "pool92.jsonl", encoding="utf-8")]
    P = [r for r in P if not r["yolo_seen"] and r["era"] != "unknown"]
    in81 = {(json.loads(l)["stem"], json.loads(l)["page"]) for l in open(E / "81_heldout_scale/out/pages81.jsonl")}
    rnd = random.Random(92)
    rnd.shuffle(P)
    chosen, per_doc, n97 = [], Counter(), 0

    def take(r):
        nonlocal n97
        if per_doc[r["stem"]] >= 12 or (r["jcode"] == "0097" and n97 >= 140):
            return False
        chosen.append(r)
        per_doc[r["stem"]] += 1
        n97 += r["jcode"] == "0097"
        r["in81"] = (r["stem"], r["page"]) in in81
        return True

    for r in P:
        if (r["stem"], r["page"]) in in81:
            take(r)
    cells = defaultdict(list)
    for r in P:
        if r not in chosen:
            cells[(r["era"], r["layout"])].append(r)
    # round robin over the cells, rarest first, until the target
    while len(chosen) < TARGET and any(cells.values()):
        for c in sorted(cells, key=lambda c: len(cells[c])):
            while cells[c]:
                r = cells[c].pop()
                if take(r):
                    break
            if len(chosen) >= TARGET:
                break
    for r in chosen:
        r.setdefault("in81", (r["stem"], r["page"]) in in81)
    assert_not_locked([r["key"] for r in chosen])
    chosen.sort(key=lambda r: r["key"])
    with open(OUT / "pages92.jsonl", "w", encoding="utf-8") as f:
        for r in chosen:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    # reference: every Azure line with Argon's type, block and rank
    raw = dict(ARGON_SETS)
    with open(OUT / "ref92.jsonl", "w", encoding="utf-8") as f:
        for r in chosen:
            blocks = argon_pages(raw[r["set"]], r["stem"])[r["page"]]
            lines, W, H = azure_lines(r["azure"], r["page"])
            info, rank = {}, 0
            for bi, b in enumerate(blocks):
                for i in b["ids"]:
                    if i not in info:
                        info[i] = dict(type=b["type"], coarse=b["coarse"], block=bi, rank=rank)
                        rank += 1
            out = [dict(i=ln["i"], text=ln["text"], poly=ln["poly"], box=ln["box"], span=ln["span"],
                        **info.get(ln["i"], dict(type=None, coarse=None, block=None, rank=None))) for ln in lines]
            f.write(json.dumps(dict(key=r["key"], W=W, H=H, lines=out), ensure_ascii=False) + "\n")
    print(len(chosen), "pages;", sum(r["in81"] for r in chosen), "also in experiment 81")
    print(Counter((r["era"], r["layout"]) for r in chosen))
    print(Counter(r["jcode"] for r in chosen))


if __name__ == "__main__":
    {"pool": pool, "select": select}[sys.argv[1]]()
