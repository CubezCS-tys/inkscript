"""Every Azure word of a document, with the stratum it belongs to (where it sits on the page, what it is).

Azure's `prebuilt-read` gives no roles (no title, footnote, heading), so place is read from geometry, per document:
the *size* of a line is the median height of its words' boxes, compared with the document's median line size.

Strata are exclusive, assigned in this priority (a word gets the first that applies):

  sideways   the page is turned (Azure page angle beyond 45 degrees)
  latin      the word has a Latin letter
  number     the word has a digit (Western, Arabic-Indic or Persian)
  vowelled   the word carries a short-vowel mark (harakat, shadda, sukun, tanwin)
  p1_title   page 1, a line in the top 30% of the page or a line 1.2x the document's size or larger
  p1_body    the rest of page 1
  header     another page, a line in the top 7% of the page (running head, folio line)
  heading    another page, a line 1.3x the document's size or larger
  footnote   another page, a line 0.82x the document's size or smaller, in the bottom half
  body       everything else

Checked by eye on contact sheets: the geometry is rough. "footnote" holds real footnotes but also table cells,
captions and scanner watermarks; "heading" holds headings but also signatures and the odd body line in a bigger face.
The labels in the report say so.

The encoding check (`encoding_slip`) is code, not ink: Persian/Urdu code points that look like Arabic letters
(ی ک ۀ ہ ھ ے) break search for the word even when the reading is right.
"""
import json, re
from pathlib import Path
from statistics import median

LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
DIGIT = re.compile(r"[0-9٠-٩۰-۹]")
HARAKAT = re.compile(r"[ً-ْ]")
ARABIC = re.compile(r"[ء-ي]")
SLIP = re.compile(r"[یکۀہھے]")
STRATA = ["body", "p1_title", "p1_body", "heading", "header", "footnote", "number", "vowelled", "latin", "sideways"]
LABEL = {"body": "body text", "p1_title": "page 1: title & author area", "p1_body": "page 1: body", "heading": "large print (headings)",
         "header": "top strip (running heads)", "footnote": "small print, lower half", "number": "numbers & dates",
         "vowelled": "vowelled words", "latin": "Latin script", "sideways": "sideways pages"}


def scale(page):
    u = page.get("unit", "inch")
    return 300.0 if u == "inch" else (300.0 / 72 if u == "point" else 1.0)


def words_of(json_path, skip_pages=()):
    """All words of the document: dict(page, i, text, conf, box (px at 300 dpi, axis-aligned), poly, stratum, size)."""
    j = json.load(open(json_path)); ar = j.get("analyzeResult", j)
    out = []; line_sizes = []; per_page = []
    for pg in ar["pages"]:
        pn = pg["pageNumber"]
        if pn in skip_pages: continue
        s = scale(pg); W, H = pg["width"] * s, pg["height"] * s
        ws = pg.get("words", []); offs = [(w.get("span") or {}).get("offset", -1) for w in ws]
        boxes = []
        for w in ws:
            p = [v * s for v in w["polygon"]]; xs, ys = p[0::2], p[1::2]
            boxes.append((min(xs), min(ys), max(xs), max(ys)))
        # words of each line, through spans
        line_of = [-1] * len(ws); lines = pg.get("lines", [])
        import bisect
        order = sorted(range(len(ws)), key=lambda k: offs[k]); so = [offs[k] for k in order]
        for li, ln in enumerate(lines):
            for sp in ln.get("spans", []):
                a, b = sp["offset"], sp["offset"] + sp["length"]
                for t in range(bisect.bisect_left(so, a), bisect.bisect_left(so, b)): line_of[order[t]] = li
        lsize = {}; lyc = {}
        for li in range(len(lines)):
            mem = [k for k in range(len(ws)) if line_of[k] == li]
            if not mem: continue
            angle = abs(pg.get("angle") or 0); sideways = angle > 45
            hs = [(boxes[k][2] - boxes[k][0]) if sideways else (boxes[k][3] - boxes[k][1]) for k in mem]
            lsize[li] = median(hs); lyc[li] = median([(boxes[k][1] + boxes[k][3]) / 2 for k in mem]) / H
            if ARABIC.search(" ".join(ws[k]["content"] for k in mem)): line_sizes.append(lsize[li])
        per_page.append((pn, pg, ws, boxes, line_of, lsize, lyc))
    med = median(line_sizes) if line_sizes else 1.0
    for pn, pg, ws, boxes, line_of, lsize, lyc in per_page:
        sideways = abs(pg.get("angle") or 0) > 45
        for k, w in enumerate(ws):
            t = w.get("content", ""); li = line_of[k]
            size = lsize.get(li, med) / med; yc = lyc.get(li, 0.5)
            if sideways: st = "sideways"
            elif LATIN.search(t): st = "latin"
            elif DIGIT.search(t): st = "number"
            elif HARAKAT.search(t): st = "vowelled"
            elif pn == 1: st = "p1_title" if (yc < 0.30 or size >= 1.2) else "p1_body"
            elif yc < 0.07: st = "header"
            elif size >= 1.3: st = "heading"
            elif size <= 0.82 and yc > 0.5: st = "footnote"
            else: st = "body"
            out.append(dict(page=pn, i=k, text=t, conf=w.get("confidence"), box=[int(round(v)) for v in boxes[k]],
                            stratum=st, size=round(size, 2), yc=round(yc, 3), angle=pg.get("angle") or 0,
                            slip=bool(SLIP.search(t))))
    return out
