"""Experiment 35: the stratified sample of pages the vision judge looks at (and the report shows).

    PYTHONPATH=src .venv/bin/python experiments/35_edition/sample.py [--n 36]   -> out/sample.json

Strata, from the master files only (seeded, reproducible): a page 1 (title, authors), a page with footnotes,
a multi-column page (two content blocks side by side), a table-like page (many short blocks in a grid), a page
with a Quran quotation, a page with a section heading, a plain body page; spread over the decades. Born-digital
pages are left out (their "scan" is the publisher's own PDF). The hand-made test masters are added on top.
"""
from __future__ import annotations

import argparse
import json
import random
import re
from pathlib import Path

from inkscript.edition.model import load

MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")
OUT = Path("/home/yassine/inkscript/experiments/35_edition/out")


def overlap(a, b):
    return max(0.0, min(a[1] + a[3], b[1] + b[3]) - max(a[1], b[1]))


def page_traits(ed, n) -> set:
    p = ed.pages[n]
    content = [b for b in p.blocks if b.kind not in ("furniture", "stray") and b.words]
    t = set()
    if n == 1:
        t.add("first")
    if any(b.kind == "fn" for b in content):
        t.add("footnotes")
    if any(b.kind == "heading" for b in content):
        t.add("heading")
    body = [b for b in content if b.kind in ("p", "fn", "heading") and b.box[3] > 3 * 40]
    for i, a in enumerate(body):
        for b in body[i + 1:]:
            if overlap(a.box, b.box) > 0.5 * min(a.box[3], b.box[3]) and \
                    (a.box[0] + a.box[2] < b.box[0] + 10 or b.box[0] + b.box[2] < a.box[0] + 10):
                t.add("columns")
    small = [b for b in content if len(b.words) <= 6]        # a grid: >= 3 rows of >= 3 short blocks side by side
    rows = 0
    for i, a in enumerate(small):
        side = [b for b in small if b is not a and overlap(a.box, b.box) > 0.5 * min(a.box[3], b.box[3])]
        if len(side) >= 2 and all(b.box[1] >= a.box[1] - 5 for b in side if b.box[1] < a.box[1] + 5):
            rows += 1
    if rows >= 4:
        t.add("table")
    return t


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=36)
    ap.add_argument("--seed", type=int, default=35)
    a = ap.parse_args()
    rnd = random.Random(a.seed)
    pool = {k: [] for k in ("first", "footnotes", "columns", "table", "quran", "heading", "plain")}
    for j in sorted(MERGED.glob("*.jats.xml")):
        ed = load(j, pdf_path=Path("/nonexistent"))         # page sizes are not needed here
        quran_pages = set()
        for node in ed.body:
            if any(r["t"] == "quran" for r in node.inl):
                quran_pages.update(ed.blocks[b].page for b in node.blocks if b in ed.blocks)
        year = ed.front.get("year") or ""
        dec = (year[:3] + "0s") if re.match(r"^\d{4}$", year) and ed.front.get("calendar") == "gregorian" else "?"
        for n, p in ed.pages.items():
            if p.born or p.handwritten or not any(b.words for b in p.blocks):
                continue
            tr = page_traits(ed, n)
            if n in quran_pages:
                tr.add("quran")
            row = dict(id=ed.stem, page=n, traits=sorted(tr), decade=dec, journal=ed.front.get("journal_id"))
            for k in tr:
                pool[k].append(row)
            if not tr - {"heading"}:
                pool["plain"].append(row)
    want = {"first": 6, "footnotes": 6, "columns": 6, "table": 5, "quran": 4, "heading": 4, "plain": 5}
    picked, seen_docs = [], set()
    for k, m in want.items():
        cands = pool[k][:]
        rnd.shuffle(cands)
        cands.sort(key=lambda r: r["id"] in seen_docs)             # a new document first
        for r in cands:
            if sum(1 for p in picked if p["stratum"] == k) >= m:
                break
            if any(p["id"] == r["id"] and p["page"] == r["page"] for p in picked):
                continue
            picked.append(dict(r, stratum=k))
            seen_docs.add(r["id"])
    picked = picked[:a.n]
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "sample.json").write_text(json.dumps(dict(seed=a.seed, pool={k: len(v) for k, v in pool.items()},
                                                     pages=picked), ensure_ascii=False, indent=1))
    print({k: len(v) for k, v in pool.items()})
    for p in picked:
        print(p["stratum"], p["id"], p["page"], p["decade"], ",".join(p["traits"]))


if __name__ == "__main__":
    main()
