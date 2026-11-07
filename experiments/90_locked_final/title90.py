"""Experiment 90: the TITLE lines of the locked documents, by experiment 89's title method (title89.rule_titles,
imported unchanged; no Argon labels exist for locked material, so the rule alone), on page 1 of every locked document
with pages in the test.

    python3 title90.py select   -> out/titles90.jsonl, out/pages90_titles.jsonl (page 1 where page 1 is not already a
                                   test page: only its title lines are cut), out/title90.json (all title keys)
    python3 title90.py sheet    -> out/look/titles90_sheet*.png (the judge crops, to look at every chosen line)
    python3 title90.py drop     -> applies out/not_titles90.json (keys looked at and found not to be an article title,
                                   as experiment 89 does), rewriting out/title90.json

Fixed before any reader's reading of a locked line was looked at.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "89_final_reader"))
from common77 import azure_pages, clean_label, nonempty_lines  # noqa: E402
from title89 import rule_titles  # noqa: E402


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if Path(p).exists() else []


def select():
    names = {j["code"]: j["name"] for j in json.loads((E / "84_display_fonts/LOCKED_TEST.json").read_text())["journals"]}
    P = jl(OUT / "pages90_journals.jsonl") + jl(OUT / "pages90_old.jsonl")
    main = {(p["stem"], p["page"]) for p in P}
    docs = {}
    for p in P:
        docs.setdefault(p["stem"], p)
    rows, extra = [], []
    for stem, p in sorted(docs.items()):
        pages = azure_pages(OUT / "src" / f"{stem}.json")
        if not pages:
            continue
        L = {l["i"]: l for l in nonempty_lines(pages[0])}
        T = [i for i in rule_titles(pages, names.get(stem[:4], "")) if i in L]
        for i in T:
            rows.append(dict(key=f"{stem}_p001_l{i:03d}", stem=stem, page=1, i=i, jcode=stem[:4], era=p["era"],
                             set=p["set"], in_main=(stem, 1) in main, azure=clean_label(L[i]["text"])))
        if T and (stem, 1) not in main:
            extra.append(dict(stem=stem, page=1, jcode=p["jcode"], year=p["year"], era=p["era"], lines=len(T),
                              set="titles", only=T))
    with open(OUT / "titles90.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(OUT / "pages90_titles.jsonl", "w", encoding="utf-8") as f:
        for r in extra:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    (OUT / "title90.json").write_text(json.dumps(sorted(r["key"] for r in rows)))
    from collections import Counter
    print(len(rows), "title lines in", len({r["stem"] for r in rows}), "documents;", sum(r["in_main"] for r in rows),
          "on test pages;", len(extra), "extra page-1 pages;", Counter(r["era"] for r in rows))


def sheet():
    import cv2
    from PIL import Image, ImageDraw, ImageFont
    rows = jl(OUT / "titles90.jsonl")
    look = OUT / "look"
    look.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    crops = OUT / "judge/crops"
    for s in range(0, len(rows), 40):
        part = rows[s:s + 40]
        W, Hh = 1400, 110
        canvas = Image.new("L", (W, Hh * len(part)), 255)
        d = ImageDraw.Draw(canvas)
        for k, x in enumerate(part):
            f = crops / f"{x['key']}.png"
            if f.exists():
                im = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                sc = min(1.0, (W - 330) / im.shape[1], 96 / im.shape[0])
                im = cv2.resize(im, (max(1, int(im.shape[1] * sc)), max(1, int(im.shape[0] * sc))))
                canvas.paste(Image.fromarray(im), (330, k * Hh + 4))
            d.text((4, k * Hh + 8), f"{s + k} {x['key']}", font=font, fill=0)
            d.text((4, k * Hh + 30), f"{x['set']} {x['era']}", font=font, fill=0)
            d.line([(0, k * Hh + Hh - 1), (W, k * Hh + Hh - 1)], fill=180)
        canvas.save(look / f"titles90_sheet{s // 40:02d}.png")
    print("sheets:", (len(rows) + 39) // 40)


def drop():
    bad = json.loads((OUT / "not_titles90.json").read_text()) if (OUT / "not_titles90.json").exists() else {}
    rows = [r for r in jl(OUT / "titles90.jsonl") if r["key"] not in bad]
    (OUT / "title90.json").write_text(json.dumps(sorted(r["key"] for r in rows)))
    print(len(rows), "title lines kept;", len(bad), "dropped after looking")


if __name__ == "__main__":
    {"select": select, "sheet": sheet, "drop": drop}[sys.argv[1]]()
