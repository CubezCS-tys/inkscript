"""What Chrome's engine (pdfium, the pinned pypdfium2 5.12.1) reads out of a re-typeset PDF, against what it should.

    words_found, order = read_back(pdf, expected_pages)       per page or whole document
    gaps = justification(pdf, dpi=150)                        word gaps in justified lines, from the rendered ink

Tokens are compared after the viewer's `norm` (no vowel marks or punctuation, one alef, Western digits).
"words found" = the share of expected tokens present in pdfium's text (multiset); "order" = the share of expected
tokens pdfium gives in the expected order (longest matching blocks, difflib, no junk heuristic).
"""
from __future__ import annotations

import re
from collections import Counter
from difflib import SequenceMatcher

import numpy as np

from inkscript.viewer.outputs import norm


def tokens(s: str) -> list[str]:
    s = s.replace("￾", " ").replace("­", "")
    return [k for k in (norm(t) for t in s.split()) if k]


def pdf_pages_text(pdf) -> list[str]:
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(str(pdf))
    out = []
    for i in range(len(d)):
        tp = d[i].get_textpage()
        out.append(tp.get_text_range())
        tp.close()
    d.close()
    return out


def compare(expected: list[str], got: list[str]) -> dict:
    if not expected:
        return dict(expected=0, found=0, in_order=0, extra=len(got))
    ce, cg = Counter(expected), Counter(got)
    found = sum(min(v, cg[k]) for k, v in ce.items())
    sm = SequenceMatcher(None, expected, got, autojunk=False)
    in_order = sum(b.size for b in sm.get_matching_blocks())
    extra = sum(max(0, v - ce[k]) for k, v in cg.items())
    return dict(expected=len(expected), found=found, in_order=in_order, extra=extra)


def read_back(pdf, expected_pages: list[list[str]] | None = None, expected_doc: list[str] | None = None) -> dict:
    pages = pdf_pages_text(pdf)
    tot = Counter()
    if expected_pages is not None:
        for exp, txt in zip(expected_pages, pages):
            for k, v in compare(exp, tokens(txt)).items():
                tot[k] += v
    if expected_doc is not None:
        got = [t for p in pages for t in tokens(p)]
        tot.update(compare(expected_doc, got))
    d = dict(tot)
    d["found_pct"] = round(100 * d.get("found", 0) / max(1, d.get("expected", 0)), 2)
    d["order_pct"] = round(100 * d.get("in_order", 0) / max(1, d.get("expected", 0)), 2)
    return d


def justification(pdf, dpi: int = 150, pages: list[int] | None = None) -> dict:
    """Word gaps in full-width lines, measured on the rendered page: text lines from the horizontal ink profile,
    gaps = white runs at least a quarter of the line's height wide (Arabic letters that do not join leave
    smaller ones). Returns the median and 90th percentile gap in line heights, and the share of lines with a gap
    wider than one line height (a river)."""
    import pymupdf
    gaps, rivers, lines = [], 0, 0
    with pymupdf.open(str(pdf)) as d:
        for i, page in enumerate(d):
            if pages and i + 1 not in pages:
                continue
            pix = page.get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
            a = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w) < 128
            rows = a.any(axis=1)
            # text lines: runs of rows with ink
            y, H = 0, len(rows)
            bands = []
            while y < H:
                if rows[y]:
                    y0 = y
                    while y < H and rows[y]:
                        y += 1
                    bands.append((y0, y))
                else:
                    y += 1
            widths = []
            for y0, y1 in bands:
                cols = np.where(a[y0:y1].any(axis=0))[0]
                if len(cols):
                    widths.append((y0, y1, cols[0], cols[-1]))
            if not widths:
                continue
            full = np.percentile([c1 - c0 for _, _, c0, c1 in widths], 75)
            for y0, y1, c0, c1 in widths:
                h = y1 - y0
                if h < 6 or (c1 - c0) < 0.97 * full:
                    continue
                prof = a[y0:y1, c0:c1 + 1].any(axis=0)
                runs, x = [], 0
                while x < len(prof):
                    if not prof[x]:
                        x0 = x
                        while x < len(prof) and not prof[x]:
                            x += 1
                        runs.append(x - x0)
                    else:
                        x += 1
                g = [r / h for r in runs if r >= 0.25 * h]
                if len(g) < 2:
                    continue
                lines += 1
                gaps += g
                rivers += max(g) > 1.0
    if not gaps:
        return dict(lines=0)
    return dict(lines=lines, gap_median=round(float(np.median(gaps)), 3),
                gap_p90=round(float(np.percentile(gaps, 90)), 3), river_lines_pct=round(100 * rivers / lines, 1))
