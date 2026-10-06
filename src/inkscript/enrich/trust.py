"""The trust mark on every word (experiment 22): can a reader trust the unmarked text?

    marks = assess(doc, quotes, scan_pdf)        # {word idx: Mark}

Every word with a letter or digit gets exactly one mark (punctuation alone is not assessed, as in
experiment 19):

  verified  a second, independent source agrees with the reading: the word is part of a Quran quotation and
            equals the verse after normalisation, or (page 1) Gemini's reading, which the PDF carries, equals
            Azure's. A verified word is never flagged: a verse agreeing outweighs a low confidence.
  flagged   at least one free signal says the reading may be wrong; check it on the ink. Reasons below.
  agreed    no signal raised a doubt. Not checked by a second source.

Reasons (the default rule of experiment 22, chosen on 2,971 judged words from 139 random scanned documents:
flags 7.6% of words, about 21 on an average page, catches 51 of 62 judged errors and leaves 0.43% of
unflagged words wrong; 0.0% after 2000, 1.0% before):

  conf      Azure's confidence < 0.8
  speck     a speck or stray mark: a small box alone (or nearly) on its line, or a box far too narrow for its
            letters, unless Azure is very sure (>= 0.98); a box under 0.3 of the document's word height always
  ornament  display type, calligraphy, a stamp or white-on-black: a very large (> 2.5x) or very dense
            (> 33% ink) box, nearly alone on its line, confidence < 0.95
  latin     a Latin word on an Arabic page, confidence < 0.95
  persian   a Persian/Urdu letter left in the text the PDF carries (search typed in Arabic misses it)
  quran     part of a Quran quotation and differs from the verse by dots or letters (on the ink, an Azure
            misreading 20 times in 24, experiment 20)
  gemini    page 1: Gemini's reading (the one the PDF carries) differs from Azure's
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from statistics import median

import numpy as np

from .document import ARABIC, LATIN, is_real, same_reading

HARAKAT = re.compile(r"[ً-ْ]")
PERSIAN = re.compile(r"[ٹڈڑںھہےۓگکپچژیۀ]")
CONF = 0.8

REASONS = {   # id -> (short label for notes, full description for the XML headers)
    "conf": ("Azure is unsure of this word", "Azure's own confidence for the word is below 0.8."),
    "speck": ("a speck or stray mark read as a word",
              "A speck or stray mark: the box is small and alone (or nearly) on its line, or far too narrow for "
              "the letters Azure gives it."),
    "ornament": ("ornament, stamp or display type",
                 "Display type, calligraphy, a stamp or white-on-black: a very large or very dense box, nearly "
                 "alone on its line, with confidence below 0.95."),
    "latin": ("Latin word on an Arabic page",
              "A Latin word on an Arabic page with confidence below 0.95 (transliteration, formulas, specks read "
              "as Latin)."),
    "persian": ("Persian letter in an Arabic word",
                "A Persian/Urdu letter the build does not fold to Arabic (a search typed in Arabic misses it)."),
    "quran": ("differs from the Quran verse",
              "Part of a Quran quotation and differs from the verse by dots or letters (an Azure misreading 20 "
              "times in 24 on the ink, experiment 20; otherwise the author's wording)."),
    "gemini": ("Gemini reads it differently", "On page 1, Gemini's reading (which the PDF carries) differs from "
               "Azure's."),
}
MARKS = {
    "verified": "A second, independent source agrees with the reading: the word is part of a Quran quotation and "
                "equals the verse after normalisation, or Gemini's page-1 reading (which the PDF carries) is the same.",
    "agreed": "No free signal raised a doubt. Not checked by a second source; on the measured sample such words are "
              "wrong 0.43% of the time (95% interval 0.05-0.97%).",
    "flagged": "At least one signal says the reading may be wrong; check it on the ink. On the measured sample about "
               "1 flagged word in 7 is wrong.",
}


@dataclass
class Mark:
    mark: str                                   # verified | agreed | flagged
    why: list[str] = field(default_factory=list)
    verse: str | None = None                    # the verse's word(s), for a Quran difference
    other: str | None = None                    # the other reader's text (Azure's, where the PDF carries Gemini's)


def _ink(scan_pdf, doc) -> dict[int, float]:
    """Share of dark pixels inside each word's box on the 300-dpi scan (page-level Otsu split, box padded 2 px).
    Pages are rendered one at a time and dropped."""
    import cv2
    import pymupdf
    out = {}
    by_page = {}
    for w in doc["words"]:
        by_page.setdefault(w["page"], []).append(w)
    src = pymupdf.open(str(scan_pdf))
    try:
        for pn, ws in by_page.items():
            if pn > src.page_count:
                continue
            pix = src[pn - 1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
            g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
            t, _ = cv2.threshold(np.ascontiguousarray(g[::4, ::4]), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
            H, W = g.shape
            for w in ws:
                x0, y0, x1, y1 = (int(round(v)) for v in w["box"])
                x0, y0, x1, y1 = max(0, x0 - 2), max(0, y0 - 2), min(W, x1 + 2), min(H, y1 + 2)
                out[w["idx"]] = float((g[y0:y1, x0:x1] <= t).mean()) if x1 - x0 >= 2 and y1 - y0 >= 2 else 0.0
            del g, pix
    finally:
        src.close()
    return out


def signals(doc: dict, quotes: list[dict], scan_pdf=None) -> dict[int, dict]:
    """The free signals of experiment 22 for every word (those the default rule uses)."""
    words = doc["words"]
    hs, wpc = [], []
    for w in words:
        if ARABIC.search(w["text"]):
            hs.append(w["box"][3] - w["box"][1])
            wpc.append((w["box"][2] - w["box"][0]) / (len(HARAKAT.sub("", w["text"]).replace("ـ", "")) or 1))
    mh, mw = (median(hs) if hs else 30.0), (median(wpc) if wpc else 15.0)
    qmark = {}
    for qt in quotes:
        for o in qt["ops"]:
            for i in o["doc"]:
                if o["kind"] in ("exact", "spelling", "split", "joined"):
                    qmark.setdefault(i, ("match", None))
                elif o["kind"] in ("dots", "letters", "other"):
                    qmark[i] = (o["kind"], " ".join(x["v"] for x in o["q"]))
    ink = _ink(scan_pdf, doc) if scan_pdf else {}
    out = {}
    for w in words:
        t = w["text"]
        n = len(HARAKAT.sub("", t).replace("ـ", "")) or 1
        page = doc["pages"][w["page"]]
        line_n = len(doc["lines"][w["page"]][w["line"]])
        out[w["idx"]] = dict(conf=w["conf"], h_rel=(w["box"][3] - w["box"][1]) / mh,
                             w_rel=(w["box"][2] - w["box"][0]) / n / mw, line_n=line_n,
                             latin=bool(LATIN.search(t)), arabic_page=page["arabic"],
                             persian=bool(PERSIAN.search(w["out"])),
                             ink=ink.get(w["idx"], 0.0), quran=qmark.get(w["idx"], (None, None)))
    return out


def reasons(s: dict) -> list[str]:
    """The default rule: which reasons flag this word (empty: not flagged)."""
    conf = s["conf"] if s["conf"] is not None else 1.0
    why = []
    if s["conf"] is not None and s["conf"] < CONF:
        why.append("conf")
    small = (s["h_rel"] < 0.65 and s["line_n"] <= 2) or s["w_rel"] < 0.4
    if (small and conf < 0.98) or s["h_rel"] < 0.3:
        why.append("speck")
    if (s["h_rel"] > 2.5 or s["ink"] > 0.33) and s["line_n"] <= 3 and conf < 0.95:
        why.append("ornament")
    if s["latin"] and s["arabic_page"] and conf < 0.95:
        why.append("latin")
    if s["persian"]:
        why.append("persian")
    if s["quran"][0] in ("dots", "letters", "other"):
        why.append("quran")
    return why


def assess(doc: dict, quotes: list[dict], scan_pdf=None) -> dict[int, Mark]:
    """One mark per word that has a letter or digit."""
    sig = signals(doc, quotes, scan_pdf)
    marks = {}
    for w in doc["words"]:
        if not is_real(w["text"]):
            continue
        s = sig[w["idx"]]
        why = reasons(s)
        verified = s["quran"][0] == "match"
        other = None
        if "gemini" in w:                       # page 1: two readers
            if same_reading(w["gemini"], w["text"]):
                verified = True
            else:
                why.append("gemini")
                other = w["text"]
        if verified and "gemini" not in why:
            marks[w["idx"]] = Mark("verified")
        elif why:
            marks[w["idx"]] = Mark("flagged", why, verse=s["quran"][1], other=other)
        else:
            marks[w["idx"]] = Mark("agreed")
    return marks


def summary(marks: dict[int, Mark]) -> dict:
    from collections import Counter
    c = Counter(m.mark for m in marks.values())
    return dict(words=len(marks), verified=c["verified"], agreed=c["agreed"], flagged=c["flagged"],
                why=dict(Counter(r for m in marks.values() for r in m.why).most_common()))
