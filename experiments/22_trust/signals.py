"""Free signals for every Azure word of a document: what could tell a reader "check this word"?

    doc_signals(json_path, pdf_path, quotes, year, pages=None) -> {(page, pi): {...}}

(page, pi) is the word's page and its index in Azure's page word list, the key of experiment 19's ids (doc:page:pi).

Signals (all free: Azure's JSON, the scan, the Quran check, the catalogue year):

  conf        Azure's word confidence.
  quran       the word lies in a Quran quotation (experiment 20's check) and differs from the verse by dots or letters
              ("dots"/"letters"/"other"); "match" when it equals the verse (a second source agrees).
  ink_*       what is inside the word's box on the 300-dpi scan (the page's Otsu split, inside the box padded by 2 px):
                ink      share of dark pixels in the box
                cc       connected ink components (8-connected, larger than 3 px)
  h_rel       the word's box height / the document's median word height (Arabic lines)
  w_rel       box width per character / the document's median width per character: Azure turning a speck into
              "tour" gives a 10-px-wide box for four letters
  line_n      words in the word's Azure line
  edge        the box centre lies in the outer 5% of the page (margins: specks, stamps, scanner marks)
  latin       a Latin letter; arabic_page: the page is mostly Arabic
  persian     a Persian/Urdu code point the build does NOT fold (src/inkscript/text.py folds only ک and ی)
  folded      a ک or ی the build folds (so not an error in our PDF)
  salla       the ﷺ ligature character itself, or a vowelled word right after محمد/النبي/الرسول/رسول الله with
              confidence < 0.3 (Azure reads the ligature as a vowelled made-up word: وَله، معَّم)
  supnum      a word ending in shadda or tanwin right before a comma/stop, or a bracketed number in a small box:
              where a superscript note number sits
  hamza_doc   the document's print omits the hamza (bare ان/الى/اذا outnumber أن/إلى/إذا in Azure's own reading)
  hamza       the word carries a hamza on/under an alef (أ إ آ)
"""
from __future__ import annotations
import bisect
import json
import re
import sys
from collections import Counter
from pathlib import Path
from statistics import median

import numpy as np

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))
from inkscript.text import fold_letters  # noqa: E402

LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
ARABIC = re.compile(r"[ء-ي]")
DIGIT = re.compile(r"[0-9٠-٩۰-۹]")
HARAKAT = re.compile(r"[ً-ْ]")
PERSIAN = re.compile(r"[ٹڈڑںھہےۓگکپچژیۀ]")
LETTERISH = re.compile(r"[\w؀-ۿ]")
HAMZA_ALEF = re.compile(r"[أإآ]")
BARE = {"ان", "الى", "اذا", "انه", "او", "اما", "اي", "ايضا", "اكثر", "الا"}
HAMZ = {"أن", "إن", "إلى", "إذا", "أنه", "إنه", "أو", "أما", "إما", "أي", "أيضا", "أكثر", "ألا", "إلا"}
PROPHET = re.compile(r"(محمد|النبي|الرسول|رسول|الله)[،,.]?$")
SUPEND = re.compile(r"[ًٌٍّ][،,.:؛]?$")


def scale(page):
    u = page.get("unit", "inch")
    return 300.0 if u == "inch" else (300.0 / 72 if u == "point" else 1.0)


def plain(t):
    return HARAKAT.sub("", t).replace("ـ", "")


def hamza_print(pages) -> dict:
    """Does the print omit the hamza? Counts Azure's own spellings of common function words."""
    c = Counter()
    for pg in pages:
        for w in pg.get("words", []):
            t = re.sub(r"[^\w]", "", plain(w.get("content", "")))
            if t in BARE: c["bare"] += 1
            elif t in HAMZ: c["hamza"] += 1
    n = c["bare"] + c["hamza"]
    return {"bare": c["bare"], "hamza": c["hamza"], "bare_share": c["bare"] / n if n else None,
            "omits": n >= 20 and c["bare"] / n >= 0.5}


_pages = {}


def page_gray(pdf, pn):
    key = (str(pdf), pn)
    if key not in _pages:
        import pymupdf
        if len(_pages) > 2: _pages.clear()
        d = pymupdf.open(str(pdf)); pix = d[pn - 1].get_pixmap(dpi=300, colorspace=pymupdf.csGRAY)
        g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w).copy()
        import cv2
        t, _ = cv2.threshold(g[::4, ::4], 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)   # page-level split
        _pages[key] = (g, t)
    return _pages[key]


def ink_of(gray_thr, box):
    gray, thr = gray_thr
    import cv2
    H, W = gray.shape; x0, y0, x1, y1 = box
    p = 2; x0, y0, x1, y1 = max(0, x0 - p), max(0, y0 - p), min(W, x1 + p), min(H, y1 + p)
    if x1 - x0 < 2 or y1 - y0 < 2: return {"ink": 0.0, "cc": 0}
    g = gray[y0:y1, x0:x1]
    m = (g <= thr).astype(np.uint8)        # Otsu: above the split is paper (a binary scan gives a split of 0)
    n, lab, st, _ = cv2.connectedComponentsWithStats(m, connectivity=8)
    cc = int(sum(1 for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > 3))
    return {"ink": float(m.mean()), "cc": cc}


def doc_signals(json_path, pdf_path=None, quotes=(), year=None, pages=None, words_idx=None) -> dict:
    """Signals for every word (or only words on `pages`). `quotes`: experiment 20's quotation records for this
    document, whose word indices are content-order indices (docs.load_doc idx); `words_idx` maps idx -> (page, pi)."""
    j = json.load(open(json_path)); ar = j.get("analyzeResult", j)
    hp = hamza_print(ar["pages"])
    qmark = {}
    for qt in quotes or ():
        for o in qt["ops"]:
            for i in o["doc"]:
                key = words_idx.get(i) if words_idx else None
                if key is None: continue
                if o["kind"] in ("exact", "spelling", "split", "joined"):
                    qmark.setdefault(key, ("match", None))
                elif o["kind"] in ("dots", "letters", "other"):
                    qmark[key] = (o["kind"], " ".join(x["v"] for x in o["q"]))
    # document-level sizes (Arabic words)
    hs, wpc = [], []
    for pg in ar["pages"]:
        s = scale(pg)
        for w in pg.get("words", []):
            t = w.get("content", "")
            if not ARABIC.search(t) or not w.get("polygon"): continue
            p = [v * s for v in w["polygon"]]; xs, ys = p[0::2], p[1::2]
            hs.append(max(ys) - min(ys)); n = len(plain(t)) or 1; wpc.append((max(xs) - min(xs)) / n)
    mh = median(hs) if hs else 30.0; mw = median(wpc) if wpc else 15.0
    out = {}
    for pg in ar["pages"]:
        pn = pg["pageNumber"]
        if pages is not None and pn not in pages: continue
        s = scale(pg); W, H = pg["width"] * s, pg["height"] * s
        ws = pg.get("words", [])
        offs = [(w.get("span") or {}).get("offset", -1) for w in ws]
        order = sorted(range(len(ws)), key=lambda k: offs[k]); so = [offs[k] for k in order]
        line_of = [-1] * len(ws)
        for li, ln in enumerate(pg.get("lines", [])):
            for sp in ln.get("spans", []):
                a, b = sp["offset"], sp["offset"] + sp["length"]
                for t in range(bisect.bisect_left(so, a), bisect.bisect_left(so, b)): line_of[order[t]] = li
        line_n = Counter(line_of)
        txt_all = " ".join(w.get("content", "") for w in ws)
        arabic_page = len(ARABIC.findall(txt_all)) > len(LATIN.findall(txt_all))
        gray = page_gray(pdf_path, pn) if pdf_path else None
        prev_txt = ""
        for k in order:
            w = ws[k]; t = w.get("content", "")
            if not w.get("polygon"): continue
            p = [v * s for v in w["polygon"]]; xs, ys = p[0::2], p[1::2]
            box = [int(round(min(xs))), int(round(min(ys))), int(round(max(xs))), int(round(max(ys)))]
            n = len(plain(t)) or 1
            cx, cy = (box[0] + box[2]) / 2 / W, (box[1] + box[3]) / 2 / H
            conf = w.get("confidence")
            d = dict(page=pn, pi=k, text=t, conf=conf, box=box,
                     h_rel=(box[3] - box[1]) / mh, w_rel=(box[2] - box[0]) / n / mw,
                     line_n=line_n[line_of[k]] if line_of[k] >= 0 else 1,
                     edge=min(cx, 1 - cx) < 0.05 or min(cy, 1 - cy) < 0.04,
                     latin=bool(LATIN.search(t)), arabic_page=arabic_page,
                     digit=bool(DIGIT.search(t)), vowelled=bool(HARAKAT.search(t)),
                     persian=bool(PERSIAN.search(fold_letters(t))), folded=fold_letters(t) != t,
                     salla=("ﷺ" in t) or (bool(HARAKAT.search(t)) and (conf or 1) < 0.3 and bool(PROPHET.search(plain(prev_txt)))),
                     supnum=bool(SUPEND.search(t)) and len(plain(t)) >= 3,
                     hamza=bool(HAMZA_ALEF.search(t)), hamza_doc=hp["omits"],
                     year=int(year) if year and str(year)[:4].isdigit() else None,
                     real=bool(LETTERISH.search(t)))
            q = qmark.get((pn, k))
            d["quran"], d["quran_verse"] = q if q else (None, None)
            if gray is not None:
                d.update(ink_of(gray, box))
            out[(pn, k)] = d
            prev_txt = t
    return out, hp
