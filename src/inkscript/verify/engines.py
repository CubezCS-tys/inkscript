"""Checks against real PDF engines. pdfium is what Chrome uses; MuPDF and
poppler are the other two common extractors. Numbers from here are the ones
worth quoting."""
from __future__ import annotations
import re, statistics, unicodedata
from pathlib import Path

from ..text import norm, ARABIC

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
    doc.close()
    return v


def pdfium_lines(pdf: Path, report: dict) -> list[dict]:
    """Word ORDER, line by line: how many of the layer's lines (three or more
    Arabic words) pdfium gives back as a line with the words in reading
    order, and how many come back reversed. The words-intact check cannot
    see this; pdfium build 7999 reversed every line and passed it."""
    import pypdfium2 as pdfium
    N = lambda s: unicodedata.normalize("NFKC", s)
    def edge(t):
        while t and unicodedata.category(t[0])[0] in "PSZ": t = t[1:]
        while t and unicodedata.category(t[-1])[0] in "PSZ": t = t[:-1]
        return t
    def key(line):
        return tuple(x for x in (edge(w) for w in N(line).split()) if x and ARABIC.search(x))
    doc = pdfium.PdfDocument(str(pdf))
    v = []
    for pinfo in report["pages"]:
        pn = pinfo["page"]
        if pn > len(doc) or not pinfo.get("glyphs") or "runs" not in pinfo:
            continue
        t = re.sub(r"[\u200e\u200f\u202a-\u202e]", "", doc[pn - 1].get_textpage().get_text_range()).replace("\r\n", "\n")
        got = [key(l) for l in t.split("\n")]
        def within(k):                                  # the run's words, contiguous, inside one pdfium line
            n = len(k)
            return any(l[i:i + n] == k for l in got if len(l) >= n for i in range(len(l) - n + 1))
        want = [k for k in (key(r) for r in pinfo["runs"]) if len(k) >= 3]
        ok = sum(1 for k in want if within(k)); rev = sum(1 for k in want if not within(k) and within(k[::-1]))
        v.append(dict(page=pn, lines=len(want), in_order=ok, reversed=rev))
    doc.close()
    return v


def pdfium_order(pdf: Path, skip: set[int] | None = None) -> tuple[int, int]:
    """(reading-order inversions, lines) across all pages in pdfium: a line whose
    median baseline sits above the previous line's by more than half a line.
    `skip` names pages (1-based) to leave out — sideways pages, whose lines
    run down the page and cannot be judged by baseline."""
    import pypdfium2 as pdfium
    doc = pdfium.PdfDocument(str(pdf)); inv = nl = 0
    for pn in range(len(doc)):
        if skip and pn + 1 in skip:
            continue
        tp = doc[pn].get_textpage(); t = tp.get_text_range(); lines, cur = [], []
        for k, c in enumerate(t):
            if c in "\r\n":
                if cur: lines.append(cur); cur = []
                continue
            if c.strip(): cur.append(tp.get_charbox(k))
        if cur: lines.append(cur)
        base = [statistics.median(b[1] for b in L) for L in lines]
        h = [statistics.median(b[3] - b[1] for b in L) for L in lines]
        xr = [(min(b[0] for b in L), max(b[2] for b in L)) for L in lines]
        # A jump back up the page is an inversion only within a column: two
        # consecutive lines that do not overlap horizontally are a column
        # change (right column finished, left column begins), not an error.
        def same_col(i, j):
            o = min(xr[i][1], xr[j][1]) - max(xr[i][0], xr[j][0])
            return o > 0.3 * min(xr[i][1] - xr[i][0], xr[j][1] - xr[j][0])
        inv += sum(1 for i in range(len(base) - 1) if base[i + 1] > base[i] + 0.5 * h[i] and same_col(i, i + 1)); nl += len(lines)
    doc.close()
    return inv, nl


def pages_missing_image(pdf: Path, scan: Path) -> list[int]:
    """Pages (1-based) whose output renders with less than half the ink of
    the scan page: the page image was lost (a writer defect seen once with
    inherited /Resources). Rendered at 30 dpi, so cheap."""
    import fitz, numpy as np
    src, out = fitz.open(str(scan)), fitz.open(str(pdf))
    lost = []
    for pn in range(min(src.page_count, out.page_count)):
        a = np.frombuffer(src[pn].get_pixmap(dpi=30, colorspace=fitz.csGRAY).samples, np.uint8)
        b = np.frombuffer(out[pn].get_pixmap(dpi=30, colorspace=fitz.csGRAY).samples, np.uint8)
        ia, ib = int((a < 128).sum()), int((b < 128).sum())
        if ia > 100 and ib < 0.5 * ia:
            lost.append(pn + 1)
    src.close(); out.close()
    return lost
