"""Experiment 89, task 2: the TITLE test - article titles on the first page of experiment 81's held-out documents.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python title89.py select     -> out/titles/titles89.jsonl
    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python title89.py cut        -> out/titles/titles89-0.tar
                                                         (48 px, readers) + out/titles/crops/<key>.png (96 px, judge)
    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python title89.py sheet      -> out/look/titles89_sheet*.png

Owner's rule (2026-11-05): display-face ARTICLE TITLES count toward the reader's finish line; mastheads and running
headers do not (they go to layout).

Which documents: experiment 81's own frame - experiment 76's inventory rows of the 26 held-out journals of split76.json
with Azure and PDF on disk, not duplicates (144 articles; 84 of them journal 0097).  Page 1 of each.

Which lines are titles:
  - where experiment 41's Argon labels exist for the document (22 documents): the page-1 lines Argon types "title"
    (Argon's line id p:i is Azure's nonempty line i, as build81.argon_lines reads it);
  - elsewhere, by position and size on page 1 (TITLE RULE below, fixed on the 22 Argon documents before the others were
    looked at):  lines in reading order from the top; noise (fewer than 3 Arabic letters), page numbers and
    running-header / masthead lines (in the top 8% of the page and smaller than body text, or whose text recurs on the
    top lines of pages 2-3, or that contain the journal's own name) are skipped; the title is the first group of
    lines whose height is at least 1.2x the page's median line height (the group may continue with lines of at
    least 1.0x as long as each is <= 75 characters), ending at a byline (بقلم, د., دكتور, الأستاذ, إعداد, ترجمة ...),
    a body-sized line, or after 4 lines; it must start in the top 60% of the page.
Every chosen line is then LOOKED AT on a contact sheet (sheet); lines that are not an article title are listed in
out/titles/not_titles.json by key, with the reason, and left out of the test.
"""
from __future__ import annotations

import io
import json
import re
import statistics
import sys
import tarfile
from collections import Counter
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import (azure_pages, clean_label, cut_line, encode, fixpath, nonempty_lines,  # noqa: E402
                      render_page, test_codes)

OUT = HERE / "out/titles"
INV = E / "76_finetune_pilot/out/inventory76.jsonl"
ARGON = E / "41_azure_structure/out/argon/labels"
AR = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")
BYLINE = re.compile(r"^\s*(بقلم|للاستاذ|للأستاذ|الاستاذ|الأستاذ|أ\s*\.|ا\s*\.|د\s*\.|دكتور|الدكتور|إعداد|اعداد|ترجمة|"
                    r"تأليف)")


def era(y) -> str:
    y = int(str(y)[:4])
    return "2000+" if y >= 2000 else "1950-1999" if y >= 1950 else "pre-1950"


def docs():
    held = test_codes()
    inv = [json.loads(l) for l in open(INV, encoding="utf-8")]
    return [r for r in inv if r["jcode"] in held and r.get("azure_ok") and r.get("pdf_ok") and not r.get("dup")]


def argon_types(stem: str) -> dict[int, str]:
    f = ARGON / f"{stem}.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    out = {}
    for x in d["lines"]:
        if x["page"] == 1:
            out.setdefault(int(re.match(r"\d+", x["id"].split(":")[1]).group()), x["type"])
    return out


def argon_text(stem: str) -> dict[int, str]:
    """Argon's page-1 text per Azure line (as build81.argon_lines)."""
    f = ARGON / f"{stem}.json"
    if not f.exists():
        return {}
    d = json.loads(f.read_text(encoding="utf-8"))
    out: dict[int, list[str]] = {}
    for x in sorted((x for x in d["lines"] if x["page"] == 1), key=lambda x: x["id"]):
        out.setdefault(int(re.match(r"\d+", x["id"].split(":")[1]).group()), []).append(x["text"])
    return {k: clean_label(" ".join(v)) for k, v in out.items()}


def geom(pg):
    L = nonempty_lines(pg)
    for l in L:
        p = l["poly"] or [0] * 8
        ys = p[1::2]
        l["hh"], l["y"] = max(ys) - min(ys), min(ys) / pg["height"]
    return L


def rule_titles(pages, journal: str) -> list[int]:
    """TITLE RULE (module docstring) on page 1; returns Azure line numbers."""
    L = geom(pages[0])
    if not L:
        return []
    med = statistics.median(l["hh"] for l in L) or 1.0
    later = [clean_label(l["text"]) for pg in pages[1:3] for l in sorted(geom(pg), key=lambda z: z["y"])[:3]]
    jn = clean_label(journal or "")
    out, started, base = [], False, None
    for l in sorted(L, key=lambda z: z["y"]):
        t = clean_label(l["text"])
        rel = l["hh"] / med
        if len(AR.findall(t)) < 3:
            continue
        header = ((l["y"] < 0.08 and rel < 1.0) or any(SequenceMatcher(None, t, x).ratio() > 0.8 for x in later)
                  or (len(jn) >= 6 and jn in t))
        if header and not started:
            continue
        if not started:
            if l["y"] > 0.6:
                break
            if rel >= 1.2 and not BYLINE.match(t):
                started, base = True, rel
                out.append(l["i"])
                continue
            if rel < 1.2 and len(t) > 25:          # body text before any large line: no title on this page
                break
            continue
        if BYLINE.match(t) or rel < 1.0 or len(t) > 75 or len(out) >= 4 or header:
            break
        out.append(l["i"])
    return out


def select():
    OUT.mkdir(parents=True, exist_ok=True)
    rows, calib = [], Counter()
    for r in docs():
        pages = azure_pages(fixpath(r["azure"]))
        if not pages:
            continue
        L = {l["i"]: l for l in nonempty_lines(pages[0])}
        at = argon_types(r["stem"])
        atx = argon_text(r["stem"])
        rule = rule_titles(pages, r.get("journal", ""))
        if at:
            arg = [i for i, t in sorted(at.items()) if t == "title"]
            calib["argon_titles"] += len(arg)
            calib["rule_on_argon_docs"] += len(rule)
            calib["rule_and_argon"] += len(set(rule) & set(arg))
            chosen, src = arg, "argon"
        else:
            chosen, src = rule, "rule"
        for i in chosen:
            if i not in L:
                continue
            key = f"{r['stem']}_p001_l{i:03d}"
            rows.append(dict(key=key, stem=r["stem"], page=1, i=i, jcode=r["jcode"], year=str(r["year"])[:4],
                             era=era(r["year"]), src=src, azure=clean_label(L[i]["text"]), argon=atx.get(i),
                             azure_raw=L[i]["text"], azure_json=str(fixpath(r["azure"])), pdf=str(fixpath(r["pdf"]))))
    with open(OUT / "titles89.jsonl", "w", encoding="utf-8") as f:
        for x in rows:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    st = dict(lines=len(rows), docs=len({x["stem"] for x in rows}), by_src=Counter(x["src"] for x in rows),
              by_era=Counter(x["era"] for x in rows), by_journal=Counter(x["jcode"] for x in rows), calib=calib,
              rule_precision_on_argon=calib["rule_and_argon"] / max(1, calib["rule_on_argon_docs"]),
              rule_recall_on_argon=calib["rule_and_argon"] / max(1, calib["argon_titles"]))
    (OUT / "select89.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False, indent=1))


def cut():
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(1)
    rows = [json.loads(l) for l in open(OUT / "titles89.jsonl", encoding="utf-8")]
    (OUT / "crops").mkdir(parents=True, exist_ok=True)
    tar = tarfile.open(OUT / "titles89-0.tar.part", "w")
    by = {}
    for x in rows:
        by.setdefault(x["stem"], []).append(x)
    n = 0
    for stem, xs in sorted(by.items()):
        pg = azure_pages(xs[0]["azure_json"])[0]
        L = {l["i"]: l for l in nonempty_lines(pg)}
        doc = pdfium.PdfDocument(xs[0]["pdf"])
        for dpi, H in ((250, 48), (300, 96)):
            img = render_page(doc, 0, dpi=dpi)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            for x in xs:
                c, _ = cut_line(img, L[x["i"]]["poly"], sx, sy, H=H, test=True)
                if c is None:
                    continue
                if H == 48:
                    for name, data in ((x["key"] + ".jpg", encode(c)), (x["key"] + ".txt", x["azure"].encode())):
                        ti = tarfile.TarInfo(name)
                        ti.size = len(data)
                        tar.addfile(ti, io.BytesIO(data))
                    n += 1
                else:
                    cv2.imwrite(str(OUT / "crops" / f"{x['key']}.png"), c)
        doc.close()
    tar.close()
    (OUT / "titles89-0.tar.part").rename(OUT / "titles89-0.tar")
    print("cut", n, "lines;", len(list((OUT / "crops").glob("*.png"))), "judge crops")


def sheet():
    """Contact sheets of the 96-px crops with key and Azure text, 40 a sheet, to look at every chosen line."""
    import cv2
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    rows = [json.loads(l) for l in open(OUT / "titles89.jsonl", encoding="utf-8")]
    look = HERE / "out/look"
    look.mkdir(parents=True, exist_ok=True)
    font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 14)
    for s in range(0, len(rows), 40):
        part = rows[s:s + 40]
        W, Hh = 1400, 120
        canvas = Image.new("L", (W, Hh * len(part)), 255)
        d = ImageDraw.Draw(canvas)
        for k, x in enumerate(part):
            f = OUT / "crops" / f"{x['key']}.png"
            if f.exists():
                im = cv2.imread(str(f), cv2.IMREAD_GRAYSCALE)
                sc = min(1.0, (W - 300) / im.shape[1], 96 / im.shape[0])
                im = cv2.resize(im, (max(1, int(im.shape[1] * sc)), max(1, int(im.shape[0] * sc))))
                canvas.paste(Image.fromarray(im), (300, k * Hh + 4))
            d.text((4, k * Hh + 8), f"{s + k} {x['key']}", font=font, fill=0)
            d.text((4, k * Hh + 30), f"{x['src']} {x['era']}", font=font, fill=0)
            d.line([(0, k * Hh + Hh - 1), (W, k * Hh + Hh - 1)], fill=180)
        canvas.save(look / f"titles89_sheet{s // 40:02d}.png")
    print("sheets:", (len(rows) + 39) // 40)


if __name__ == "__main__":
    {"select": select, "cut": cut, "sheet": sheet}[sys.argv[1]]()
