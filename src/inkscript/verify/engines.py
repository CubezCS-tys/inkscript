"""Checks against real PDF engines. pdfium is what Chrome uses; MuPDF and
poppler are the other two common extractors. Numbers from here are the ones
worth quoting."""
from __future__ import annotations
import re, statistics, unicodedata
from pathlib import Path

from ..text import norm

def pdfium_words(pdf: Path, report: dict, azure_dir: Path) -> dict:
    """pdfium (Chrome's engine): every page's line count vs Azure's, and how
    many of the words placed come back out intact, vowel marks included."""
    import pypdfium2 as pdfium
    N = lambda s: unicodedata.normalize("NFKC", s)
    def edge(t):
        while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
        while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
        return t
    doc = pdfium.PdfDocument(str(pdf))
    v = []
    for pinfo in report["pages"]:
        pn = pinfo["page"]
        if pn > len(doc) or not pinfo.get("glyphs"):
            continue
        t = N(doc[pn - 1].get_textpage().get_text_range())
        got = {edge(x) for x in re.sub(r"[\u200e\u200f\u202a-\u202e]", "", t).split()}
        want = [edge(x) for t in pinfo["placed"] for x in N(t).split() if norm(x)]   # what the layer holds, Gemini's or Azure's
        want = [x for x in want if x]
        hit = sum(1 for x in want if x in got)
        nl = len([l for l in t.replace("\r\n", "\n").split("\n") if l.strip()])
        v.append(dict(page=pn, lines_pdfium=nl, lines_layer=pinfo["lines"], words=len(want), intact=hit))
    return v


def pdfium_order(pdf: Path) -> tuple[int, int]:
    """(reading-order inversions, lines) across all pages in pdfium: a line whose
    median baseline sits above the previous line's by more than half a line."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf)); inv = nl = 0
    for pn in range(len(doc)):
        tp = doc[pn].get_textpage(); t = tp.get_text_range(); lines, cur = [], []
        for k, c in enumerate(t):
            if c in "\r\n":
                if cur: lines.append(cur); cur = []
                continue
            if c.strip(): cur.append(tp.get_charbox(k))
        if cur: lines.append(cur)
        base = [statistics.median(b[1] for b in L) for L in lines]
        h = [statistics.median(b[3] - b[1] for b in L) for L in lines]
        inv += sum(1 for i in range(len(base) - 1) if base[i + 1] > base[i] + 0.5 * h[i]); nl += len(lines)
    return inv, nl
