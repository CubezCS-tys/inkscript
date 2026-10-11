"""Experiment 35: rebuilt pages with one fault put in on purpose, to calibrate the vision judge.

    PYTHONPATH=src .venv/bin/python experiments/35_edition/planted.py    -> out/planted/*.pdf, out/planted/planted.json

On sampled pages (seeded), the layout-faithful page is rebuilt from a copy of the master with one fault:
  drop      a content block (a paragraph or footnote) is left out;
  swap      the texts of two content blocks trade places (both boxes stay);
  heading   a heading (or the title) is set as body text: body weight and the page's body line height.
Only that page is rebuilt (one-page PDF). The judge is not told which pages carry a fault.
"""
from __future__ import annotations

import copy
import json
import random
import statistics
from pathlib import Path

from inkscript.edition.model import load
from inkscript.edition.printpdf import layout_pdf

OUT = Path("/home/yassine/inkscript/experiments/35_edition/out")
MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")


def first_words(b, n=5):
    return " ".join(w.text for w in b.words[:n])


def plant(ed, n, fault, rnd):
    page = ed.pages[n]
    content = [b for b in page.blocks if b.kind in ("p", "fn") and len(b.words) >= 8]
    if fault == "drop":
        if not content:
            return None
        b = max(content, key=lambda b: len(b.words)) if rnd.random() < 0.5 else rnd.choice(content)
        page.blocks.remove(b)
        return f"left out block {b.id} ({b.kind}, {len(b.words)} words): «{first_words(b)}…»"
    if fault == "swap":
        if len(content) < 2:
            return None
        a, b = rnd.sample(content, 2)
        a.lines, b.lines = b.lines, a.lines         # the texts move, the boxes stay (lines keep their own boxes,
        dy_a = a.box[1] - b.box[1]                  # so move each set of lines into the other block's place)
        dx_a = a.box[0] - b.box[0]
        for ln in a.lines:
            ln.box = (ln.box[0] + dx_a, ln.box[1] + dy_a, ln.box[2], ln.box[3])
            for w in ln.words:
                w.box = (w.box[0] + dx_a, w.box[1] + dy_a, w.box[2], w.box[3])
        for ln in b.lines:
            ln.box = (ln.box[0] - dx_a, ln.box[1] - dy_a, ln.box[2], ln.box[3])
            for w in ln.words:
                w.box = (w.box[0] - dx_a, w.box[1] - dy_a, w.box[2], w.box[3])
        return f"swapped texts of {a.id} «{first_words(b)}…» and {b.id} «{first_words(a)}…»"
    if fault == "heading":
        heads = [b for b in page.blocks if b.kind in ("heading", "title") and b.words]
        body = [ln.box[3] for b in page.blocks if b.kind == "p" for ln in b.lines]
        if not heads or not body:
            return None
        h = max(heads, key=lambda b: max(ln.box[3] for ln in b.lines))
        bh = statistics.median(body)
        for ln in h.lines:
            k = bh / max(1.0, ln.box[3])
            cy = ln.box[1] + ln.box[3] / 2
            ln.box = (ln.box[0], cy - bh / 2, ln.box[2], bh)
            for w in ln.words:
                w.box = (w.box[0], cy - bh / 2, w.box[2], min(w.box[3] * k, bh))
        h.kind, h.role = "p", "body"
        return f"heading {h.id} «{first_words(h)}…» set as body text"
    return None


def main():
    s = json.loads((OUT / "sample.json").read_text())
    rnd = random.Random(3535)
    pages = [p for p in s["pages"] if not p["id"].startswith("test-")]
    rnd.shuffle(pages)
    want = {"drop": 3, "swap": 3, "heading": 3}
    got, rows = {k: 0 for k in want}, []
    (OUT / "planted").mkdir(parents=True, exist_ok=True)
    for p in pages:
        for fault in want:
            if got[fault] >= want[fault] or any(r["id"] == p["id"] for r in rows):
                continue
            ed = load(MERGED / f"{p['id']}.jats.xml")
            ed2 = copy.deepcopy(ed)
            detail = plant(ed2, p["page"], fault, rnd)
            if not detail:
                continue
            ed2.pages = {p["page"]: ed2.pages[p["page"]]}
            out = OUT / "planted" / f"{p['id']}.p{p['page']}.{fault}.pdf"
            st = layout_pdf(ed2, out)
            if not out.exists():
                print("failed", p["id"], fault, st.get("errors"))
                continue
            got[fault] += 1
            rows.append(dict(id=p["id"], page=p["page"], fault=fault, detail=detail, scan=str(MERGED / f"{p['id']}.pdf"),
                             rebuild=str(out), rebuild_page=1))
            print(fault, p["id"], p["page"], detail)
            break
    (OUT / "planted" / "planted.json").write_text(json.dumps(rows, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
