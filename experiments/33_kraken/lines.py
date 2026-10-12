"""Lines of a born-digital page with their exact text, rebuilt from the PDF's own glyphs.

Why rebuild: a typeset PDF stores Arabic runs, numbers and punctuation in the order its producer wrote them, and
MuPDF's lines mix them (`يراعي2».` for `يراعي».2`). Ligature glyphs (لا, لم) often extract with their letters
reversed (`سالمة` for `سلامة`, `املحترف` for `المحترف`). So:

1. glyphs come from `rawdict` (real fonts only: Azure's invisible `Dummy` layer and junk-encoded fonts are left out);
2. a glyph's combining marks join it; a zero-width glyph is the first part of a ligature and joins the next glyph;
3. a line is every glyph whose box overlaps the line band vertically, split where a gap is wider than 2.5 em
   (columns, a page number beside a running head);
4. glyph groups are put in reading order right to left by position, then runs of Latin and numbers are turned back
   left to right (a small inverse of the Unicode bidi rules: a neutral joins two such neighbours only when it is
   inside a Latin run or a single . , : / - between digits);
5. two variants per document, chosen by agreement with Azure's words on the same lines (Azure decides *only* which
   of two deterministic decodings a document's fonts need, never the text of a line): ligature letters as stored or
   reversed; brackets as stored or mirrored.
"""
from __future__ import annotations
import re, unicodedata
import pymupdf

GOOD = re.compile(r"[؀-ۿﭐ-﷿ﹰ-﻿A-Za-z0-9]")
MIRROR = str.maketrans("()[]{}<>«»", ")(][}{><»«")


def cls(ch: str) -> str:
    if ch.isspace():
        return "W"
    b = unicodedata.bidirectional(ch)
    if b in ("R", "AL"):
        return "R"
    if b == "L":
        return "L"
    if b in ("EN", "AN"):
        return "N"
    return "P"


def born_digital(page) -> bool:
    """The pipeline's rule (src/inkscript/pdf/native.py born_digital/text_words), copied so this venv needs no inkscript:
    real fonts carry readable words, at least half as many as Azure's Dummy layer."""
    real = dummy = chars = goodc = 0
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                if sp["font"] == "Dummy":
                    dummy += len(sp["text"].split())
                else:
                    real += len(sp["text"].split())
                    t = sp["text"].replace(" ", ""); chars += len(t); goodc += len(GOOD.findall(t))
    if chars and goodc < 0.5 * chars:
        real = 0
    return real > 0 and real >= 0.5 * dummy


def junk_font_names(page) -> set:
    """Base names of the page's non-Dummy fonts whose text is mostly symbols (no usable encoding)."""
    seen, ok = {}, {}
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                t = sp["text"].replace(" ", "")
                seen[sp["font"]] = seen.get(sp["font"], 0) + len(t); ok[sp["font"]] = ok.get(sp["font"], 0) + len(GOOD.findall(t))
    return {f for f in seen if f != "Dummy" and seen[f] >= 5 and ok[f] < 0.9 * seen[f]}


def page_glyphs(page) -> tuple[list, bool]:
    """Glyph groups of the real fonts: dict(s=str, x0, x1, y0, y1, size, font, bold). Second value: page has junk."""
    junk = junk_font_names(page)
    out = []
    for b in page.get_text("rawdict", flags=pymupdf.TEXT_PRESERVE_WHITESPACE)["blocks"]:
        for l in b.get("lines", []):
            if abs(l["dir"][1]) > 0.02 or l["dir"][0] < 0:
                continue                                               # rotated text is left out
            for sp in l["spans"]:
                if sp["font"] == "Dummy" or sp["font"] in junk:
                    continue
                bold = bool(sp["flags"] & 16) or "bold" in sp["font"].lower()
                pend = []
                for c in sp["chars"]:
                    ch = c["c"]; x0, y0, x1, y1 = c["bbox"]
                    if unicodedata.category(ch) in ("Mn", "Me") and out and not pend and out[-1].get("_span") is sp and not out[-1]["s"].isspace() \
                            and out[-1]["x0"] - 0.5 <= (x0 + x1) / 2 <= out[-1]["x1"] + 0.5:
                        out[-1]["s"] += ch; continue                    # a mark goes with its letter
                    if unicodedata.category(ch) in ("Mn", "Me") and not pend:
                        out.append(dict(s=ch, lig=False, x0=x0, x1=x1, y0=y0, y1=y1, size=sp["size"], font=sp["font"],
                                        bold=bold, _span=None)); continue   # placed on its letter later (attach_marks)
                    if x1 - x0 < 0.05 and not ch.isspace():
                        pend.append(ch); continue                       # first part of a ligature: joins the next glyph
                    g = dict(s="".join(pend) + ch, lig=len(pend) > 0, x0=x0, x1=x1, y0=y0, y1=y1, size=sp["size"],
                             font=sp["font"], bold=bold, _span=sp)
                    pend = []
                    out.append(g)
                if pend and out and out[-1].get("_span") is sp:
                    out[-1]["s"] += "".join(pend)
    for g in out:
        g.pop("_span", None)
    return out, bool(junk)


def group_lines(glyphs: list) -> list[list]:
    """Glyphs into visual lines (vertical overlap, then split at gaps over 2.5 em)."""
    gl = sorted((g for g in glyphs if not g["s"].isspace()), key=lambda g: (g["y0"] + g["y1"]) / 2)
    bands = []
    for g in gl:
        h = g["y1"] - g["y0"]; yc = (g["y0"] + g["y1"]) / 2
        for bd in reversed(bands[-4:]):
            ov = min(bd["y1"], g["y1"]) - max(bd["y0"], g["y0"])
            if ov > 0.55 * min(h, bd["h"]) and abs(yc - bd["yc"]) < 0.45 * max(h, bd["h"]):
                bd["g"].append(g); break
        else:
            bands.append(dict(y0=g["y0"], y1=g["y1"], h=h, yc=yc, g=[g]))
    spaces = [g for g in glyphs if g["s"].isspace()]
    lines = []
    for bd in bands:
        gs = sorted(bd["g"], key=lambda g: -(g["x0"] + g["x1"]) / 2)
        em = sorted(g["size"] for g in gs)[len(gs) // 2]
        cur = [gs[0]]
        for a, b in zip(gs, gs[1:]):
            if a["x0"] - b["x1"] > 2.5 * em:
                lines.append(cur); cur = []
            cur.append(b)
        lines.append(cur)
    out = []
    for ln in lines:
        x0 = min(g["x0"] for g in ln); x1 = max(g["x1"] for g in ln)
        ys = sorted((g["y0"] + g["y1"]) / 2 for g in ln); yc = ys[len(ys) // 2]
        hs = sorted(g["y1"] - g["y0"] for g in ln); h = hs[len(hs) // 2]
        sp = [s for s in spaces if x0 - 1 < (s["x0"] + s["x1"]) / 2 < x1 + 1 and abs((s["y0"] + s["y1"]) / 2 - yc) < 0.35 * h]
        out.append(ln + sp)
    return out


def attach_marks(line: list) -> list:
    """A glyph that is only combining marks (a vowel drawn as its own glyph) joins the letter it sits on."""
    ismark = lambda g: g["s"] and all(unicodedata.category(c) in ("Mn", "Me") for c in g["s"])
    bases = [dict(g) for g in line if not ismark(g)]
    letters = [g for g in bases if not g["s"].isspace()]
    for m in (g for g in line if ismark(g)):
        if not letters:
            continue
        cx = (m["x0"] + m["x1"]) / 2
        b = min(letters, key=lambda g: 0 if g["x0"] <= cx <= g["x1"] else min(abs(cx - g["x0"]), abs(cx - g["x1"])) + 1)
        b["s"] += m["s"]
    # a space glyph drawn inside a letter (some producers emit one with every separately placed vowel) is no space
    keep = []
    for g in bases:
        if g["s"].isspace():
            w = max(g["x1"] - g["x0"], 0.01)
            if any(min(g["x1"], b["x1"]) - max(g["x0"], b["x0"]) > 0.9 * w for b in letters):
                continue
        keep.append(g)
    return keep


def logical(line: list, lig_reverse: bool, mirror: bool) -> str:
    """Reading-order text of one visual line. Base direction right to left, unless Latin letters outnumber Arabic."""
    line = attach_marks(line)
    nl = sum(cls(c) == "L" for g in line for c in g["s"]); nr = sum(cls(c) == "R" for g in line for c in g["s"])
    rtl = nr >= nl
    sgn = -1 if rtl else 1
    gs = sorted(line, key=lambda g: (sgn * (g["x0"] + g["x1"]) / 2, g["s"].isspace()))
    if not gs:
        return ""
    em = sorted(g["size"] for g in gs)[len(gs) // 2]
    toks = []                                                           # (class, string) in base-direction order
    prev = None
    for g in gs:
        s = g["s"]
        if g.get("lig") and lig_reverse:
            base = [c for c in s if unicodedata.category(c) not in ("Mn", "Me")]
            marks = [c for c in s if unicodedata.category(c) in ("Mn", "Me")]
            s = "".join(reversed(base)) + "".join(marks)
        if s.isspace():
            toks.append(("W", " ")); prev = g; continue
        gap = 0 if prev is None else (prev["x0"] - g["x1"]) if rtl else (g["x0"] - prev["x1"])
        if prev is not None and not prev["s"].isspace() and gap > 0.25 * em:
            toks.append(("W", " "))                                     # a gap with no space glyph
        c = next((cls(ch) for ch in s if cls(ch) in "RLN"), "P")
        toks.append((c, s)); prev = g
    # runs against the base direction (Latin/numbers in an Arabic line, Arabic in a Latin line) are turned back
    inner = "LN" if rtl else "R"
    n = len(toks); i = 0; res = []
    while i < n:
        if toks[i][0] not in inner:
            res.append(toks[i]); i += 1; continue
        j = i; last = i
        while j + 1 < n:
            k = j + 1
            if toks[k][0] in inner:
                j = k; last = k; continue
            m = k
            while m < n and toks[m][0] in "WP":
                m += 1
            if m >= n or toks[m][0] not in inner:
                break
            seg = toks[k:m]; a, b = toks[last][0], toks[m][0]
            single_sep = len(seg) == 1 and seg[0][1] in ".,:/-،"
            if not rtl or "L" in (a, b) or (a == "N" and b == "N" and single_sep):
                j = m; last = m; continue
            break
        res.extend(reversed(toks[i:last + 1])); i = last + 1
    s = "".join(t for _, t in res)
    s = re.sub(r"\s+", " ", s).strip()
    if mirror and rtl:                                                  # brackets of the Arabic text drawn mirrored
        s = s.translate(MIRROR)
    return s


def page_lines(page, variants=((False, False), (True, False), (False, True), (True, True))) -> tuple[list, bool]:
    """Lines of one page: dict(bbox=(x0,y0,x1,y1) in points, text={variant: str}, size, bold, nlig)."""
    try:
        gl, junk = page_glyphs(page)
    except Exception:
        return [], True                                                 # MuPDF cannot read this page's text
    out = []
    for ln in group_lines(gl):
        ink = [g for g in ln if not g["s"].isspace()]
        if not ink:
            continue
        sizes = sorted(g["size"] for g in ink)
        out.append(dict(bbox=(min(g["x0"] for g in ink), min(g["y0"] for g in ink), max(g["x1"] for g in ink), max(g["y1"] for g in ink)),
                        text={v: logical(ln, *v) for v in variants}, size=sizes[len(sizes) // 2],
                        bold=sum(g["bold"] for g in ink) > 0.6 * len(ink), nlig=sum(g.get("lig", False) for g in ink),
                        fonts=sorted({g["font"] for g in ink})))
    return out, junk


def azure_words(az_page, page) -> list:
    """Azure's words on a page in PDF points, in Azure's order: dict(t, x0, y0, x1, y1, conf, line)."""
    sx = page.rect.width / az_page["width"]; sy = page.rect.height / az_page["height"]
    out = []
    for w in az_page.get("words", []):
        p = w["polygon"]; xs = p[0::2]; ys = p[1::2]
        out.append(dict(t=w["content"], x0=min(xs) * sx, x1=max(xs) * sx, y0=min(ys) * sy, y1=max(ys) * sy, conf=w.get("confidence", 1)))
    return out


def assign_azure(lines: list, words: list) -> None:
    """Each Azure word goes to the gold line that holds its centre (most vertical overlap wins); sets line['azure']."""
    for ln in lines:
        ln["azure_w"] = []
    for k, w in enumerate(words):
        cx = (w["x0"] + w["x1"]) / 2; cy = (w["y0"] + w["y1"]) / 2
        best, bo = None, 0
        for ln in lines:
            x0, y0, x1, y1 = ln["bbox"]
            if not (x0 - 2 <= cx <= x1 + 2 and y0 - 1 <= cy <= y1 + 1):
                continue
            ov = min(y1, w["y1"]) - max(y0, w["y0"])
            if ov > bo:
                best, bo = ln, ov
        if best is not None:
            best["azure_w"].append(k)
    for ln in lines:
        ln["azure"] = " ".join(words[k]["t"] for k in ln["azure_w"])
        ln["azure_conf"] = min((words[k]["conf"] for k in ln["azure_w"]), default=None)
        del ln["azure_w"]
