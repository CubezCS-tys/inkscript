#!/usr/bin/env python3
"""Experiment 99 pictures for the owner (out/pictures/), drawn with PIL + raqm (experiment 49's Desk venv, as
KEYER_RULES allows):

  pages_<stem>_pNNN.png  the page three times: answer key | Azure + Gemini pipeline | LiteParse (text layer, LayoutNet
                         on).  Every Azure line is filled with its role's colour; a line whose role the key does not
                         accept is outlined red, thick; each piece (block) gets a thin grey frame round its lines.
  lines_strip.png        12 exam lines: the crop, then truth / Azure / our reader t91 / LiteParse text layer /
                         Tesseract / ocria-nano (as returned, in LiteParse's own order).

    nice -n 19 /home/appuser/inkscript/experiments/49_correction_desk/.venv/bin/python pictures99.py
Picks are seeded (seed 99) within each kind, not chosen by looking at the results.
"""
from __future__ import annotations

import json
import os
import random
import sys

from PIL import Image, ImageDraw, ImageFont

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert99 as V  # noqa: E402
sys.path.insert(0, V.P97)
import score97 as S  # noqa: E402

E = V.E
OUT = f"{E}/out/pictures"
FONT_AR = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
FONT_LA = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
ROLE_COL = {
    "paragraph": (120, 170, 230), "heading": (230, 120, 40), "list-item": (60, 180, 120), "table": (170, 120, 210),
    "ref": (200, 170, 60), "footnote": (230, 110, 170), "endnote": (230, 110, 170), "running-head": (150, 150, 150),
    "page-number": (90, 90, 90), "title": (220, 60, 60), "title-translated": (220, 60, 60), "byline": (40, 160, 170),
    "affiliation": (20, 110, 120), "abstract": (100, 120, 200), "keywords": (100, 90, 160), "front-matter": (140, 100, 60),
    "caption": (240, 200, 0), "figure": (150, 150, 0), "quote": (160, 200, 90), "verse": (160, 200, 90),
    "equation": (0, 0, 0), "other": (200, 200, 200), "(not-text)": (240, 240, 240), "(no-block)": (255, 255, 255),
}


def col(role):
    return ROLE_COL.get(role, (255, 0, 255))


def font(size, ar=True):
    return ImageFont.truetype(FONT_AR if ar else FONT_LA, size)


def role_maps(doc):
    role, piece = S._line_index(doc)
    return role, piece


def draw_panel(img, az, gold, doc, title, sc):
    im = img.copy().convert("RGB")
    ov = Image.new("RGBA", im.size, (0, 0, 0, 0))
    d = ImageDraw.Draw(ov)
    role, piece = role_maps(doc)
    grole, gpiece = role_maps(gold)
    gp = gold.get("pieces") or []
    n_bad = 0
    for ln, (x, y, w, h) in az.items():
        r = role.get(ln, S.NO_BLOCK)
        c = col(r)
        d.rectangle([x * sc, y * sc, (x + w) * sc, (y + h) * sc], fill=c + (110,))
    # piece frames
    pcs = C_pieces(doc)
    for p, lines in pcs.items():
        bx = [az[l] for l in lines if l in az]
        if not bx:
            continue
        x0 = min(b[0] for b in bx); y0 = min(b[1] for b in bx)
        x1 = max(b[0] + b[2] for b in bx); y1 = max(b[1] + b[3] for b in bx)
        d.rectangle([x0 * sc - 3, y0 * sc - 3, x1 * sc + 3, y1 * sc + 3], outline=(60, 60, 60, 200), width=1)
    # differing lines (not on the key panel)
    if doc is not gold:
        for ln, (x, y, w, h) in az.items():
            g = grole.get(ln)
            if g is None or g == S.NOT_TEXT:
                continue
            if ln in gpiece and gp[gpiece[ln]].get("unsure"):
                continue
            p = role.get(ln, S.NO_BLOCK)
            if p not in S.accepted_roles(gp[gpiece[ln]]) if ln in gpiece else p != g:
                n_bad += 1
                d.rectangle([x * sc - 2, y * sc - 2, (x + w) * sc + 2, (y + h) * sc + 2], outline=(220, 0, 0, 255), width=4)
    im = Image.alpha_composite(im.convert("RGBA"), ov).convert("RGB")
    head = Image.new("RGB", (im.width, 64), (255, 255, 255))
    hd = ImageDraw.Draw(head)
    hd.text((10, 8), title + ("" if doc is gold else f"   ({n_bad} lines labelled differently from the key)"),
            fill=(0, 0, 0), font=font(24, False))
    out = Image.new("RGB", (im.width, im.height + 64), (255, 255, 255))
    out.paste(head, (0, 0)); out.paste(im, (0, 64))
    return out, n_bad


def C_pieces(doc):
    out = {}
    for n, p in enumerate(doc.get("pieces") or []):
        out[n] = p.get("lines") or []
    return out


def legend(width, roles):
    roles = [r for r in ROLE_COL if r in roles]
    h = 40 * ((len(roles) + 5) // 6) + 50
    im = Image.new("RGB", (width, h), (255, 255, 255))
    d = ImageDraw.Draw(im)
    for i, r in enumerate(roles):
        x, y = 20 + (i % 6) * (width // 6), 10 + (i // 6) * 40
        d.rectangle([x, y + 4, x + 40, y + 28], fill=col(r), outline=(80, 80, 80))
        d.text((x + 50, y), r, fill=(0, 0, 0), font=font(22, False))
    d.text((20, h - 36), "red frame = line labelled differently from the key (accept-either rulings applied);"
           " grey frame = one piece / block", fill=(160, 0, 0), font=font(20, False))
    return im


def page_pictures(mode="text", n_target=None):
    gold = S.gold_set("PAGE", "final")[0]["files"]
    lock = {a["stem"]: a for a in V.json.load(open(f"{V.P97}/LOCKED_EVAL.json"))["articles"]}
    tab = set(S.gold_set("TAB", "final")[0]["files"])
    by = {"body": [], "two": [], "table": [], "refs": [], "front": []}
    for name, g in sorted(gold.items()):
        if not S._is_eval_file("PAGE", g) or S.file_left_out(g):
            continue
        a = lock[g["stem"]]
        kinds = {k for k, p in a["pages"].items() if p == g["page"]}
        if g.get("columns") == 2 and not kinds & {"front"}:
            by["two"].append(name)
        elif "front" in kinds:
            by["front"].append(name)
        elif "table" in kinds and name in tab:
            by["table"].append(name)
        elif "refs" in kinds:
            by["refs"].append(name)
        elif "body" in kinds and g.get("columns") == 1:
            by["body"].append(name)
    rnd = random.Random(99)
    pick = rnd.sample(by["body"], 2) + rnd.sample(by["two"], 2) + rnd.sample(by["table"], 2) + \
        rnd.sample(by["refs"], 1) + rnd.sample(by["front"], 1)
    made = []
    for name in pick:
        g = gold[name]
        stem, page = g["stem"], int(g["page"])
        pp = V.packet_page(stem, page)
        img = Image.open(pp["image"])
        sc = 900 / img.width
        small = img.resize((900, int(img.height * sc)))
        az = {l["line"]: (l["x"], l["y"], l["w"], l["h"]) for l in pp["azure_lines"]}
        pipe = S.pipeline_page(stem, page)
        lpp = V.json.load(open(f"{E}/out/runs/exam_{mode}/{stem}.json"))["pages"].get(str(page))
        lit = V.pred_page(stem, page, lpp)[0] if lpp else dict(pieces=[])
        panels = [draw_panel(small, az, g, g, "Answer key", sc)[0],
                  draw_panel(small, az, g, pipe, "Azure + Gemini pipeline", sc)[0],
                  draw_panel(small, az, g, lit, "LiteParse (text layer)", sc)[0]]
        W = sum(p.width for p in panels) + 40
        roles = {p.get("role") for d in (g, pipe, lit) for p in d.get("pieces") or []} | {S.NO_BLOCK}
        lg = legend(W, roles)
        H = max(p.height for p in panels)
        out = Image.new("RGB", (W, H + lg.height + 50), (255, 255, 255))
        ImageDraw.Draw(out).text((20, 10), f"{stem}  page {page}  ({', '.join(k for k, v in by.items() if name in v)})",
                                 fill=(0, 0, 0), font=font(26, False))
        x = 10
        for p in panels:
            out.paste(p, (x, 50)); x += p.width + 10
        out.paste(lg, (0, H + 50))
        f = f"{OUT}/pages_{stem}_p{page:03d}.png"
        out.save(f, optimize=True)
        made.append(f)
    return made


def strip():
    recs = {}
    for m in ("text", "tess", "nano"):
        f = f"{E}/out/scores/r1_lines_{m}.jsonl"
        if os.path.exists(f):
            for x in open(f):
                d = json.loads(x)
                recs.setdefault(d["id"], dict(d))[m] = d["liteparse"]
    ids = sorted(k for k, v in recs.items() if v.get("truth"))
    rnd = random.Random(99)
    pick = []
    by = {}
    for k in ids:
        by.setdefault(recs[k]["kind"], []).append(k)
    for kind in sorted(by):
        pick += rnd.sample(by[kind], min(2, len(by[kind])))
    rest = [k for k in ids if k not in pick]
    pick += rnd.sample(rest, 12 - len(pick))
    W = 1700
    rows = []
    for k in pick:
        r = recs[k]
        crop = Image.open(f"{V.P97}/out/reading/crops/{k}.png").convert("RGB")
        s = min(1.0, (W - 20) / crop.width)
        crop = crop.resize((int(crop.width * s), int(crop.height * s)))
        lines = [("truth (settled)", r.get("truth")), ("Azure raw", r.get("azure")), ("our reader t91", r.get("t91")),
                 ("LiteParse text layer", r.get("text")), ("LiteParse Tesseract", r.get("tess")),
                 ("LiteParse ocria-nano", r.get("nano"))]
        h = crop.height + 30 + 44 * len(lines) + 20
        im = Image.new("RGB", (W, h), (255, 255, 255))
        d = ImageDraw.Draw(im)
        d.text((10, 4), f"{k}  ({r['kind']} page)", fill=(80, 80, 80), font=font(18, False))
        im.paste(crop, (W - 10 - crop.width, 28))
        y = crop.height + 34
        for lab, t in lines:
            t = t or "(nothing)"
            same = (t or "") == (r.get("truth") or "")
            d.text((10, y + 6), lab, fill=(0, 120, 0) if same else (170, 0, 0), font=font(20, False))
            ar = any("؀" <= ch <= "ۿ" for ch in t)
            # Naskh has no Latin letters: a line holding Latin is drawn in DejaVu Sans (Arabic and Latin both)
            f = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 24) if any(
                (ch.isascii() and ch.isalpha()) or ch in "\u2010\u2011\u2012\u2013\u2014\u2212" for ch in t) else font(26, True)
            try:
                tw = d.textlength(t, font=f, direction="rtl" if ar else "ltr")
            except Exception:  # noqa: BLE001
                tw = d.textlength(t, font=f)
            x = max(270, W - 10 - tw) if ar else 270
            d.text((x, y), t, fill=(0, 0, 0), font=f, direction="rtl" if ar else "ltr")
            y += 44
        d.line([0, h - 2, W, h - 2], fill=(180, 180, 180), width=2)
        rows.append(im)
    # two sheets of six (one would be too tall to read)
    made = []
    for n in range(2):
        part = rows[6 * n: 6 * n + 6]
        out = Image.new("RGB", (W, sum(r.height for r in part) + 60), (255, 255, 255))
        ImageDraw.Draw(out).text((10, 10), "Twelve exam lines (seed 99, two per page kind, then at random). Green label ="
                                 " same as the truth, red = differs. Texts shown in the order each tool returned them.",
                                 fill=(0, 0, 0), font=font(20, False))
        y = 50
        for r in part:
            out.paste(r, (0, y)); y += r.height
        f = f"{OUT}/lines_strip_{n + 1}.png"
        out.save(f, optimize=True)
        made.append(f)
    return made


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    what = sys.argv[1] if len(sys.argv) > 1 else "all"
    if what in ("all", "pages"):
        print(page_pictures())
    if what in ("all", "lines"):
        print(strip())
