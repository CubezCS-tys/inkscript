"""Experiment 90: which locked lines are mastheads / running headers (excluded from the reader's criteria by the
owner's decision of 2026-11-05: layout's job, Plan m34), from Azure's JSON and geometry only, fixed before any
reader's reading of the locked lines was looked at.

    python3 masthead90.py      -> out/masthead90.json  {key: reason} for every masthead line of out/lines90.jsonl

Rule.  A page's BAND lines are the lines whose polygon lies in the top 12% or the bottom 10% of the page (Azure's
page height).  A band line's key is its text folded (inkscript.gold.text.folded), with digits, punctuation and spaces
removed; keys under 4 letters are ignored (page numbers, dates alone are not in the Arabic frame anyway).  The POOL of
a page is every page of every fetched document of its issue (the stem's first 12 characters: "0123-045-006"), plus,
for the locked journals, every page of the journal's fetched documents.  A band line is a masthead / running header
when a band line with a similar key (rapidfuzz ratio >= 70) is on at least 40% of the pages of its issue pool (and
at least 3 pages), or on at least 25% of its journal pool (at least 5 pages): the same text at the top or bottom of
most pages.  Alternating headers (journal name on odd pages, article title on even pages) each reach about 50%.
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict
from pathlib import Path

from rapidfuzz import fuzz

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
SRC = OUT / "src"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E.parent / "src"))
from common77 import azure_pages, nonempty_lines  # noqa: E402
from inkscript.gold.text import folded  # noqa: E402

TOP, BOT, SIM = 0.12, 0.10, 70
NONL = re.compile(r"[\W\d_]+")


def key_of(t: str) -> str:
    return NONL.sub("", folded(t or ""))


def band_lines(stem: str):
    """[(page, i, key)] for the band lines of every page of a fetched document; and the page count."""
    out, pages = [], 0
    for p, pg in enumerate(azure_pages(SRC / f"{stem}.json"), 1):
        L = nonempty_lines(pg)
        if not L:
            continue
        pages += 1
        H = pg["height"]
        for ln in L:
            if not ln["poly"]:
                continue
            ys = ln["poly"][1::2]
            if max(ys) / H <= TOP or min(ys) / H >= 1 - BOT:
                k = key_of(ln["text"])
                if len(k) >= 4:
                    out.append((p, ln["i"], k))
    return out, pages


def repeated(items, pool_pages: dict, need_share: float, need_min: int):
    """items: [(stem, page, i, key)] of one pool -> set of (stem, page, i) whose key recurs on enough pages."""
    n_pages = sum(pool_pages.values())
    need = max(need_min, need_share * n_pages)
    if n_pages < need_min:
        return set()
    keys = [x[3] for x in items]
    hit = set()
    for a, (st, p, i, k) in enumerate(items):
        pages = {(st, p)}
        for b, k2 in enumerate(keys):
            if (items[b][0], items[b][1]) not in pages and fuzz.ratio(k, k2) >= SIM:
                pages.add((items[b][0], items[b][1]))
        if len(pages) >= need:
            hit.add((st, p, i))
    return hit


def main():
    lines = [json.loads(l) for l in open(OUT / "lines90.jsonl", encoding="utf-8")]
    stems = sorted({r["stem"] for r in lines})
    sets = {r["stem"]: r["set"] for r in lines}
    B, NP = {}, {}
    for s in stems:
        B[s], NP[s] = band_lines(s)
    issue, journal = defaultdict(list), defaultdict(list)
    for s in stems:
        issue[s[:12]].append(s)
        if sets[s] == "journals":
            journal[s[:4]].append(s)
    hits = {}
    for name, pools, share, mn in (("issue", issue, 0.40, 3), ("journal", journal, 0.25, 5)):
        for g, S in pools.items():
            items = [(s, p, i, k) for s in S for p, i, k in B[s]]
            for st, p, i in repeated(items, {s: NP[s] for s in S}, share, mn):
                hits.setdefault(f"{st}_p{p:03d}_l{i:03d}", f"repeated band line ({name} pool)")
    keys = {r["key"] for r in lines}
    res = {k: v for k, v in hits.items() if k in keys}
    (OUT / "masthead90.json").write_text(json.dumps(res, ensure_ascii=False, indent=0))
    ar = [r for r in lines if r["arabic_share"] is not None and r["arabic_share"] >= 0.5]
    print("masthead lines among the cut lines:", len(res), "of", len(lines), "; Arabic frame:",
          sum(r["key"] in res for r in ar), "of", len(ar))
    by = defaultdict(int)
    for r in ar:
        if r["key"] in res:
            by[r["era"]] += 1
    print(dict(by))


if __name__ == "__main__":
    main()
