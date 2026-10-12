"""Experiment 38, step 7: blind Gemini judges -> out/judge_sides.jsonl, out/judge_objects.jsonl.

    /home/yassine/inkscript/.venv/bin/python judge.py sides|objects [--limit N]

sides    one call per page (Gemini 3.1 Pro): Image 1 the scan, Images 2 and 3 the old (experiment 35) and the new
         (experiment 38) layout-faithful rebuilds of that page, in an order drawn per page from a seeded coin (the
         judge is never told which is which). It says which is closer to the original and why, aspect by aspect.
objects  one call per table and per formula (Gemini 3.1 Pro): the crop of the scan and the candidates, anonymised
         and shuffled: tables - dots.mocr's own HTML and the new table (Azure's words in dots' grid); formulas -
         dots.mocr's LaTeX and the checked LaTeX. Each graded 1-5 against the crop.
"""
from __future__ import annotations

import json
import random
import sys

import cv2

from common import OUT, gemini, jpeg, pages

MODEL = "gemini-3.1-pro-preview"
SIDES = """Image 1 is a scanned page of an Arabic journal. Images 2 and 3 are two digital rebuilds of that same page,
made by two different systems, A (Image 2) and B (Image 3). Compare each rebuild with the original scan, as a reader
would, and say which one is closer to the original. Look at:
- text: is all the printed text there, in the right places, nothing invented or garbled, page number as printed;
- layout: columns, the reading order of blocks, alignment, relative text sizes;
- headings: set apart as on the scan (size, bold where the scan is bold, and not bold where it is not);
- tables: present, with their rows, columns and rules;
- pictures, charts and logos: present where the scan has them;
- formulas: present and readable;
- lists and bullets, footnotes;
- Latin (English/French) text: readable in the right order.
Ignore the scan's paper colour, stains and the typeface itself (a rebuild uses its own font).
For each aspect say which is better: "A", "B", "same", or "n/a" when the page has nothing of that kind.
Then the overall winner ("A", "B" or "tie"), a grade 1-5 for each rebuild's closeness to the original, and at most
three short sentences on the main differences."""
SIDES_SCHEMA = {"type": "object", "properties": {
    **{k: {"type": "string", "enum": ["A", "B", "same", "n/a"]} for k in
       ("text", "layout", "headings", "tables", "pictures", "formulas", "lists_notes", "latin")},
    "winner": {"type": "string", "enum": ["A", "B", "tie"]}, "grade_A": {"type": "integer"},
    "grade_B": {"type": "integer"}, "why": {"type": "string"}},
    "required": ["text", "layout", "headings", "tables", "pictures", "formulas", "lists_notes", "latin", "winner",
                 "grade_A", "grade_B", "why"]}
ASPECTS = ("text", "layout", "headings", "tables", "pictures", "formulas", "lists_notes", "latin")

OBJ = {"table": """Image 1 is a crop of a scanned Arabic journal page holding one table. Below are {n} transcriptions
of it as HTML, labelled {labels}, made by different systems. Judge each against the image only:
- structure_ok: rows, columns and merged cells match the printed table;
- cells_wrong: cells whose text differs from the print (a wrong digit, letter or word counts);
- cells_missing / cells_extra: printed cells left out / cells not printed;
- grade 1 (unusable) to 5 (exact); note: at most 15 words on the worst problem.
Arabic-Indic and Western digits count as the same digit. A candidate may list each row's cells from right to left
(the Arabic reading order) or from left to right: do not count the direction as an error.
{cands}""",
       "formula": """Image 1 is a crop of a scanned Arabic journal page holding one displayed formula (Arabic words may
appear in it). Below are {n} transcriptions of it as LaTeX, labelled {labels}, made by different systems. Judge each
against the image only, as it would render (the formula's printed number may be left out of a candidate; do not
count that):
- structure_ok: fractions, sub/superscripts, roots, sums, matrices and the order of terms match;
- cells_wrong: symbols, digits or words that differ; cells_missing / cells_extra: left out / not printed;
- grade 1 (unusable) to 5 (exact); note: at most 15 words on the worst problem.
Arabic-Indic and Western digits count as the same digit.
{cands}"""}
OBJ_SCHEMA = {"type": "object", "properties": {"candidates": {"type": "array", "items": {"type": "object", "properties": {
    "label": {"type": "string"}, "structure_ok": {"type": "boolean"}, "cells_wrong": {"type": "integer"},
    "cells_missing": {"type": "integer"}, "cells_extra": {"type": "integer"}, "grade": {"type": "integer"},
    "note": {"type": "string"}}, "required": ["label", "structure_ok", "cells_wrong", "cells_missing", "cells_extra",
                                              "grade", "note"]}}}, "required": ["candidates"]}


def done_ids(path):
    if not path.exists():
        return set()
    return {json.loads(l)["key"] for l in path.read_text(encoding="utf-8").splitlines() if l.strip()}


def sides(limit=0):
    out = OUT / "judge_sides.jsonl"
    have = done_ids(out)
    n = 0
    for meta in pages():
        pid = meta["page_id"]
        sd = OUT / "pages" / pid / "shots"
        if pid in have or not (sd / "old_layout.jpg").exists() or not (sd / "new_layout.jpg").exists():
            continue
        if limit and n >= limit:
            break
        n += 1
        new_first = random.Random("38:" + pid).random() < 0.5
        scan, old, new = (cv2.imread(str(sd / f"{k}.jpg")) for k in ("scan", "old_layout", "new_layout"))
        imgs = [jpeg(scan, 1600), jpeg(new if new_first else old, 1600), jpeg(old if new_first else new, 1600)]
        ans, usd = gemini(SIDES, imgs, f"sides {pid}", model=MODEL, max_out=6000, schema=SIDES_SCHEMA,
                          thinking="low", est_in=3 * 1200 + 600)
        if ans is None:
            continue
        side = {"A": "new" if new_first else "old", "B": "old" if new_first else "new"}
        un = {k: (side.get(v, v)) for k, v in ans.items() if k in ASPECTS + ("winner",)}
        rec = dict(key=pid, new_is=("A" if new_first else "B"), answer=ans, unblinded=un,
                   grade_new=ans["grade_A"] if new_first else ans["grade_B"],
                   grade_old=ans["grade_B"] if new_first else ans["grade_A"], why=ans["why"], usd=usd)
        with open(out, "a", encoding="utf-8") as f:
            f.write(json.dumps(rec, ensure_ascii=False) + "\n")
        print(pid, "winner", un["winner"], "new", rec["grade_new"], "old", rec["grade_old"], flush=True)


def objects(limit=0):
    from measure import table_html
    from master import apply_corrections, corrected_words
    out = OUT / "judge_objects.jsonl"
    have = done_ids(out)
    n = 0
    for meta in pages():
        pid = meta["page_id"]
        pdir = OUT / "pages" / pid
        if not (pdir / "layout.json").exists():
            continue
        L = json.loads((pdir / "layout.json").read_text(encoding="utf-8"))
        F = {f["id"]: f for f in json.loads((pdir / "formulas.json").read_text())} \
            if (pdir / "formulas.json").exists() else {}
        C = json.loads((pdir / "corrections.json").read_text()) if (pdir / "corrections.json").exists() else None
        rep = apply_corrections(L, C)
        for b in L["blocks"]:
            if b["role"] not in ("table", "formula"):
                continue
            key = f"{pid}:{b['id']}"
            if key in have:
                continue
            if limit and n >= limit:
                return
            if b["role"] == "table":
                cands = {"dots": b["html"], "new": table_html(b, rep, corrected_words)}
            else:
                f = F.get(b["id"]) or {}
                cands = {"dots": b.get("tex_dots") or "", "new": f.get("tex") or b.get("tex_dots") or ""}
            if cands["dots"].strip() == cands["new"].strip():
                rec = dict(key=key, kind=b["role"], same=True, cands=cands)
                # identical: one candidate is enough
                cands = {"dots": cands["dots"]}
            else:
                rec = dict(key=key, kind=b["role"], same=False, cands=cands)
            n += 1
            tags = list(cands)
            random.Random("38:" + key).shuffle(tags)
            labels = [chr(65 + i) for i in range(len(tags))]
            txt = "\n\n".join(f"Candidate {l}:\n{cands[t] or '(nothing)'}" for l, t in zip(labels, tags))
            img = cv2.imread(str(pdir / b["crop"]))
            ans, usd = gemini(OBJ[b["role"]].format(n=len(tags), labels=", ".join(labels), cands=txt),
                              [jpeg(img, 1600)], f"object {key}", model=MODEL, max_out=6000, schema=OBJ_SCHEMA,
                              thinking="low")
            if ans is None:
                continue
            g = {}
            for c in ans.get("candidates", []):
                if c.get("label") in labels:
                    g[tags[labels.index(c["label"])]] = c
            if rec["same"]:
                g["new"] = g.get("dots")
            rec.update(grades=g, usd=usd)
            with open(out, "a", encoding="utf-8") as fo:
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
            print(key, {k: (v or {}).get("grade") for k, v in g.items()}, flush=True)


if __name__ == "__main__":
    lim = int(sys.argv[sys.argv.index("--limit") + 1]) if "--limit" in sys.argv else 0
    {"sides": sides, "objects": objects}[sys.argv[1]](lim)
