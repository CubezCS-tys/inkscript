"""Azure's reading of one document, as the enrich step sees it: pages, paragraphs, lines and words in reading
order, every word with a stable id, its box in scan pixels and the text our PDF carries for it.

    doc = load(azure_json, shapes_json=None, gemini_pages=())

Coordinates are pixels of the 300-dpi scan (y down), the frame of shapes.json and of `inkscript correct`.

Offsets: Azure counts *text elements* (a letter and its harakat are one) when `stringIndexType` is
`textElements`; slicing `content` needs code points. `text_elements` converts (experiment 20: every word of
215 documents re-reads correctly at its converted offset). The raw offset is kept too (`aoff`), because the
build's shapes.json placements carry the raw one.
"""
from __future__ import annotations

import bisect
import json
import re
import statistics
import unicodedata
from collections import Counter
from pathlib import Path

from ..text import URDU_PERSIAN_ONLY, fold_letters
from .quran import norm, noalef

DPI = 300
ARABIC = re.compile(r"[ء-ي]")
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
LETTERISH = re.compile(r"[\w؀-ۿ]")


def text_elements(s: str) -> list[int]:
    """Code-point start of each text element (grapheme cluster), plus len(s) at the end: a base character and
    the combining marks (Mn/Me/Mc), ZWJ/ZWNJ and variation selectors after it; CR LF is one element."""
    starts, i, n = [], 0, len(s)
    while i < n:
        starts.append(i)
        if s[i] == "\r" and i + 1 < n and s[i + 1] == "\n":
            i += 2
            continue
        i += 1
        while i < n and (unicodedata.category(s[i]) in ("Mn", "Me", "Mc") or s[i] in "‌‍︎️"):
            i += 1
    starts.append(n)
    return starts


def _scale(unit: str) -> float:
    return DPI if unit == "inch" else (DPI / 72.0 if unit == "point" else 1.0)


def is_real(text: str) -> bool:
    """A word with a letter or digit; punctuation alone is not assessed (experiment 19's rule)."""
    return bool(norm(text)) or any(c.isalnum() for c in text)


_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


def same_reading(a: str, b: str) -> bool:
    """Two readers' texts for one word agree: the Quran matching key for words with letters, the digits for
    numbers (punctuation and tatweel ignored)."""
    na, nb = norm(a), norm(b)
    if na or nb:
        return na == nb
    da, db = (re.sub(r"[^0-9A-Za-z]", "", t.translate(_DIGITS)) for t in (a, b))
    return da == db


def load(azure_json: Path, shapes_json: Path | None = None, gemini_pages=()) -> dict:
    """Azure's reading of a document, with the build's glyph placements attached to their words.

    Each word: idx (reading order in the document), id (p<page>w<nnnn>, nnnn = reading order on the page),
    page, pi (index in Azure's page word list), off/len (code points), aoff (Azure's offset), text (Azure's),
    out (the text our PDF carries: Gemini's on a Gemini page 1, Persian look-alikes folded as the build folds
    them), poly/box (px), conf, line (index into doc["lines"][page]), para (index into doc["paras"]),
    glyphs (indices of shapes.json placements drawn for it), n/k (Quran matching keys)."""
    j = json.loads(Path(azure_json).read_text(encoding="utf-8"))
    ar = j.get("analyzeResult", j)
    content = ar.get("content", "")
    te = text_elements(content) if ar.get("stringIndexType") == "textElements" else None

    def cp(off):
        if te is None or off is None or off < 0:
            return off
        return te[min(off, len(te) - 1)]

    def span(sp):
        o, ln = sp.get("offset", -1), sp.get("length", 0)
        a = cp(o)
        return a, (cp(o + ln) - a if o >= 0 else 0)

    pages, words, lines = {}, [], {}
    for pg in ar.get("pages", []):
        pn = pg.get("pageNumber", len(pages) + 1)
        s = _scale(pg.get("unit", "inch"))
        ws = pg.get("words", [])
        arabic_letters = not any(URDU_PERSIAN_ONLY.search(w.get("content", "")) for w in ws)   # as load_azure folds
        txt = " ".join(w.get("content", "") for w in ws)
        pages[pn] = dict(n=pn, w=(pg.get("width") or 1) * s, h=(pg.get("height") or 1) * s,
                         angle=pg.get("angle") or 0.0, unit=pg.get("unit", "inch"),
                         fold=arabic_letters, arabic=len(ARABIC.findall(txt)) >= len(LATIN.findall(txt)))
        for pi, w in enumerate(ws):
            if not w.get("polygon"):
                continue
            o, ln = span(w.get("span") or {})
            p = [v * s for v in w["polygon"]]
            xs, ys = p[0::2], p[1::2]
            t = w.get("content", "")
            words.append(dict(page=pn, pi=pi, text=t, out=fold_letters(t) if arabic_letters else t,
                              off=o, len=ln, aoff=(w.get("span") or {}).get("offset", -1),
                              poly=p, box=[min(xs), min(ys), max(xs), max(ys)],
                              conf=w.get("confidence"), line=None, para=None, glyphs=[]))
        lines[pn] = []
    words.sort(key=lambda w: (w["off"], w["page"]))
    per_page = Counter()
    for i, w in enumerate(words):
        w["idx"] = i
        per_page[w["page"]] += 1
        w["id"] = f"p{w['page']}w{per_page[w['page']]:04d}"
        w["n"] = norm(w["text"])
        w["k"] = noalef(w["n"])
    offs = [w["off"] for w in words]

    def words_in(a, ln, page=None):
        i0, i1 = bisect.bisect_left(offs, a), bisect.bisect_left(offs, a + ln)
        return [k for k in range(i0, i1) if page is None or words[k]["page"] == page]

    for pg in ar.get("pages", []):
        pn = pg.get("pageNumber")
        for ln_ in pg.get("lines", []):
            members = []
            for sp in ln_.get("spans", []):
                a, n = span(sp)
                members += words_in(a, n, pn)
            if not members:
                continue
            li = len(lines[pn])
            for k in members:
                words[k]["line"] = li
            lines[pn].append(members)
    for w in words:                    # a word no line claims gets a line of its own
        if w["line"] is None:
            w["line"] = len(lines[w["page"]])
            lines[w["page"]].append([w["idx"]])

    paras = []
    for p in ar.get("paragraphs", []):
        regions = [(r.get("pageNumber"), r.get("polygon")) for r in (p.get("boundingRegions") or [])]
        members = []
        for sp in p.get("spans") or []:
            a, n = span(sp)
            members += words_in(a, n)
        members = [k for k in members if words[k]["para"] is None]
        if not members:
            continue
        for k in members:
            words[k]["para"] = len(paras)
        paras.append(dict(idx=len(paras), role=p.get("role"), content=p.get("content", ""), words=members,
                          off=words[members[0]]["off"], regions=regions))
    # words outside every paragraph: one paragraph per run of them, so nothing is lost
    loose = [w["idx"] for w in words if w["para"] is None]
    run = []
    for k in loose + [None]:
        if run and (k is None or k != run[-1] + 1 or words[k]["page"] != words[run[-1]]["page"]):
            for m in run:
                words[m]["para"] = len(paras)
            paras.append(dict(idx=len(paras), role=None, content=" ".join(words[m]["text"] for m in run),
                              words=run, off=words[run[0]]["off"], regions=[]))
            run = []
        if k is not None:
            run.append(k)
    paras.sort(key=lambda p: p["off"])
    for i, p in enumerate(paras):
        p["idx"] = i
        for k in p["words"]:
            words[k]["para"] = i

    # the build's glyphs: shapes.json placements carry their Azure word's raw offset (since 2026-10-06)
    placements = []
    if shapes_json and Path(shapes_json).exists():
        placements = json.loads(Path(shapes_json).read_text(encoding="utf-8")).get("placements", [])
        by_aoff = {(w["page"], w["aoff"]): w for w in words}
        for gi, pl in enumerate(placements):
            w = by_aoff.get((pl.get("page"), pl.get("off")))
            if w is not None:
                w["glyphs"].append(gi)
        for w in words:                # page 1 read by Gemini: the PDF carries Gemini's text for the word
            if w["page"] in gemini_pages and len(w["glyphs"]) == 1:
                w["gemini"] = placements[w["glyphs"][0]]["text"]
                w["out"] = w["gemini"]
    doc = dict(content=content, pages=pages, words=words, lines=lines, paras=paras, placements=placements,
               model=ar.get("modelId"), api=ar.get("apiVersion"), gemini_pages=set(gemini_pages))
    doc["roles"] = roles(doc)
    for p, r in zip(doc["paras"], doc["roles"]):
        p["kind"] = r
    return doc


def para_box(doc: dict, p: dict, page: int) -> list[float] | None:
    ws = [doc["words"][k] for k in p["words"] if doc["words"][k]["page"] == page]
    if not ws:
        return None
    return [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
            max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)]


# ---------------------------------------------------------------- paragraph roles

_NUM = re.compile(r"^[\s\d٠-٩۰-۹\-–—()\[\].]+$")
_FOOT = re.compile(r"^\s*[\(\[]?[\d٠-٩۰-۹]{1,3}[\)\]]?\s*[-–.)]?")
_MAST = re.compile(r"مجلة|العدد|السنة|المجلد")
_DIGIT = re.compile(r"[\d٠-٩۰-۹]")


def roles(doc: dict) -> list[str | None]:
    """A role per paragraph: Azure's when it gives one (prebuilt-read almost never does: 11 in 87,500
    paragraphs, experiment 20), otherwise position rules (experiment 20's, unchanged):

      pageNumber      only digits/dashes, in the top or bottom 12% of the page
      pageHeader      also: the journal's masthead, a paragraph in the top 20% of up to 20 words that names
                      مجلة / العدد / السنة / المجلد with a number
      pageHeader      in the top 8%, at most 12 words
      pageFooter      in the bottom 6%, at most 12 words
      footnote        lower half, letters <= 85% of the page's median word height, and either opening with a
                      note number or following a footnote on the same page
      sectionHeading  <= 10 words, letters >= 125% of the median, not ending in a full stop or comma
    None is body text."""
    words = doc["words"]
    hs = {}
    for w in words:
        hs.setdefault(w["page"], []).append(w["box"][3] - w["box"][1])
    med = {p: statistics.median(v) for p, v in hs.items() if v}
    out, prev_foot = [], {}
    for p in doc["paras"]:
        if p["role"]:
            out.append(p["role"])
            continue
        pg = words[p["words"][0]]["page"]
        ws = [words[k] for k in p["words"] if words[k]["page"] == pg]
        H = doc["pages"][pg]["h"]
        x0, y0, x1, y1 = para_box(doc, p, pg)
        h = statistics.median([w["box"][3] - w["box"][1] for w in ws])
        m = med.get(pg, h) or 1
        txt = " ".join(w["text"] for w in ws).strip()
        r = None
        if _NUM.match(txt) and len(txt) <= 9 and (y1 < 0.12 * H or y0 > 0.88 * H):
            r = "pageNumber"
        elif y1 < 0.2 * H and len(ws) <= 20 and _MAST.search(txt) and _DIGIT.search(txt):
            r = "pageHeader"                       # the journal's masthead: name, volume, issue, year
        elif y1 < 0.08 * H and len(ws) <= 12:
            r = "pageHeader"
        elif y0 > 0.94 * H and len(ws) <= 12:
            r = "pageFooter"
        elif y0 > 0.5 * H and h <= 0.85 * m and (_FOOT.match(txt) or prev_foot.get(pg)):
            r = "footnote"
        elif len(ws) <= 10 and h >= 1.25 * m and not txt.endswith((".", "،")):
            r = "sectionHeading"
        prev_foot[pg] = r == "footnote" or bool(prev_foot.get(pg) and r is None and y0 > 0.5 * H and h <= 0.85 * m)
        if prev_foot[pg] and r is None:
            r = "footnote"
        out.append(r)
    return out
