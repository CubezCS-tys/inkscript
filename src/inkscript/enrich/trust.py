"""The trust mark on every word (experiment 22): can a reader trust the unmarked text?

    marks = assess(doc, quotes, scan_pdf)        # {word idx: Mark}

Every word with a letter or digit gets exactly one mark (punctuation alone is not assessed, as in
experiment 19):

  verified  a second, independent source agrees with the reading: the word is part of a Quran quotation and
            equals the verse after normalisation, or (page 1) Gemini's reading, which the PDF carries, equals
            Azure's. A verified word is never flagged: a verse agreeing outweighs a low confidence.
  flagged   at least one free signal says the reading may be wrong; check it on the ink. Reasons below.
  agreed    no signal raised a doubt. Not checked by a second source.
  corrected the reading was corrected from an exact source after a judge on the ink accepted it (experiment 27,
            enrich/corrections.py; set by `overlay`, not by `assess`)

Reasons (the default rule of experiment 22, chosen on 2,971 judged words from 139 random scanned documents:
flags 7.6% of words, about 21 on an average page, catches 51 of 62 judged errors and leaves 0.43% of
unflagged words wrong; 0.0% after 2000, 1.0% before). Since experiment 27 (`refine`), a word flagged for its
confidence alone is not flagged when it is a common word (read confidently in >= 5 corpus documents) and
Azure's confidence is >= 0.6: on the product's own reading of the judged words, flags 7.5% -> 5.0%, errors
caught 50 -> 50 of 61, 1 flag in 8.9 -> 1 in 7.4 a real error.

  conf      Azure's confidence < 0.8 (refined as above)
  speck     a speck or stray mark: a small box alone (or nearly) on its line, or a box far too narrow for its
            letters, unless Azure is very sure (>= 0.98); a box under 0.3 of the document's word height always
  ornament  display type, calligraphy, a stamp or white-on-black: a very large (> 2.5x) or very dense
            (> 33% ink) box, nearly alone on its line, confidence < 0.95
  latin     a Latin word on an Arabic page, confidence < 0.95
  persian   a Persian/Urdu letter left in the text the PDF carries (search typed in Arabic misses it)
  quran     part of a Quran quotation and differs from the verse by dots or letters (on the ink, an Azure
            misreading 20 times in 24, experiment 20)
  gemini    page 1: Gemini's reading (the one the PDF carries) differs from Azure's

Page and block marks (experiment 30, `regions`): where Azure's reading is less reliable as a whole — a handwritten
page, decorative lettering, vowelled text — a flag on most words says nothing about any one of them (60% of words
flagged on the most vowelled documents of experiment 28, 68-91% on handwritten pages). There the block carries the
mark (ALTO TextBlock TAGREFS region.*, PAGECLASS handwritten, JATS custom-meta reading-*, a page note in the trust
PDF) and a word keeps its own flag only when something points at it (`in_region`): a Quran difference, Gemini's
other reading, a Persian letter, a speck, a Latin word, or a confidence under half its block's median and in the
block's lowest tenth. On experiment 19's judged words: in marked blocks 35 -> 11 of 102 words flagged, 3 of their 8
errors still flagged word by word and all 8 inside a marked block; on all judged words flagged 5.0% -> 4.3%.
"""
from __future__ import annotations

import gzip
import re
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path
from statistics import median

import numpy as np

from .document import ARABIC, LATIN, is_real, same_reading

HARAKAT = re.compile(r"[ً-ْ]")
PERSIAN = re.compile(r"[ٹڈڑںھہےۓگکپچژیۀ]")
CONF = 0.8

REASONS = {   # id -> (short label for notes, full description for the XML headers)
    "conf": ("Azure is unsure of this word", "Azure's own confidence for the word is below 0.8 (below 0.6, or not a common word, since experiment 27)."),
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
              "wrong 0.42% of the time (experiment 27; 0.43% under experiment 22's rule, 95% interval 0.05-0.97%). "
              "In a block marked vowelled, handwritten or decorative (its TextBlock's region.* tag) it means only that "
              "nothing points at this word in particular: the block's mark covers it (experiment 30).",
    "flagged": "At least one signal says the reading may be wrong; check it on the ink. On the measured sample about "
               "1 flagged word in 7 is wrong (experiment 27).",
    "corrected": "The reading was corrected from an exact source (a Quran verse) after a judge looking at the scan's ink "
                 "picked the source's word over Azure's, blind; the earlier reading is kept as an ALTERNATIVE "
                 "(experiment 27, <stem>.corrections.json).",
}


@dataclass
class Mark:
    mark: str                                   # verified | agreed | flagged | corrected
    why: list[str] = field(default_factory=list)
    verse: str | None = None                    # the verse's word(s), for a Quran difference
    other: str | None = None                    # the other reader's text (Azure's, where the PDF carries Gemini's)
    source: str | None = None                   # a correction's source ("quran 11:106")
    region: list[str] = field(default_factory=list)   # its block's marks (experiment 30): vowelled, handwritten...


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


LEXICON = Path(__file__).resolve().parents[1] / "data" / "lexicon" / "confident-words.tsv.gz"
LEX_DOCS, LEX_CONF = 5, 0.6


@lru_cache(maxsize=1)
def lexicon() -> dict[str, int]:
    """Quran matching key -> number of documents (of 400: experiments 19 and 16) in which Azure read the word with
    confidence >= 0.95; keys seen in at least 5 documents (experiment 27, `lexicon.py ship`)."""
    if not LEXICON.exists():
        return {}
    out = {}
    for line in gzip.decompress(LEXICON.read_bytes()).decode("utf-8").splitlines():
        if line and not line.startswith("#"):
            k, n = line.split("\t")
            out[k] = int(n)
    return out


def refine(why: list[str], s: dict, ctx: dict, lex: dict | None = None,
           min_docs: int = LEX_DOCS, min_conf: float = LEX_CONF) -> list[str]:
    """Experiment 27: a flag raised by Azure's confidence alone is dropped when the word is a common one — read
    with confidence >= 0.95 in at least 5 documents of the corpus — and Azure's confidence is at least 0.6. On
    experiment 19's judged words: flags 7.5% -> 5.0% of words, judged errors caught 50 -> 50 of 61, 1 flag in
    8.9 -> 7.4 a real error, unflagged words wrong 0.43% -> 0.42%. ctx: {"key": the word's matching key}."""
    if why != ["conf"] or s["conf"] is None or s["conf"] < min_conf:
        return why
    lex = lexicon() if lex is None else lex
    return [] if lex.get(ctx.get("key") or "", 0) >= min_docs else why


HW_WORD, HW_PAGE, HW_BLOCK = 0.9, 0.5, 0.6     # experiment 30: Azure's handwriting confidence; page / block share
VOWEL_BLOCK, VOWEL_MIN = 0.3, 3                 # a third of a block's Arabic words vowelled; at least 3 of them


def regions(doc: dict) -> dict:
    """Page- and block-level marks (experiment 30): where Azure's reading is less reliable as a whole, so that a
    flag on most words would say nothing about any one of them.

      handwritten  a page of at least 10 words of which half or more sit in a span Azure styles as handwritten with
                   confidence >= 0.9 (on the 205 documents of experiment 28: the 9 manuscript pages of 0679, median
                   word confidence 0.22-0.76; printed pages reach 0.07 at most); every block on it carries the mark
      decorative   on a printed page, a block of 3+ words 60% of which Azure styles as handwritten (>= 0.9), not
                   vowelled: looked at, a script or display typeface (running heads, headings, a byline), a
                   handwritten note or tick, a screenshot; Azure's reading of such lettering is weaker
      vowelled     a block whose Arabic words carry vowel marks in a third or more of them (at least 3 Arabic words;
                   a smaller block takes its page's share): Azure's confidence drops on vowel marks (conf < 0.8 on
                   4.7% of words in unvowelled blocks, 23-70% in blocks a third to fully vowelled)

    -> dict(pages={page: "handwritten"}, blocks={para idx: ["handwritten" | "decorative", "vowelled"]})"""
    W = doc["words"]
    by_page = {}
    for w in W:
        by_page.setdefault(w["page"], []).append(w)
    pages = {}
    page_vowels = {}
    for pn, ws in by_page.items():
        if len(ws) >= 10 and sum(w.get("hw", 0.0) >= HW_WORD for w in ws) >= HW_PAGE * len(ws):
            pages[pn] = "handwritten"
        ar = [w for w in ws if ARABIC.search(w["text"])]
        page_vowels[pn] = sum(bool(HARAKAT.search(w["text"])) for w in ar) / len(ar) if ar else 0.0
    blocks = {}
    for p in doc["paras"]:
        ws = [W[k] for k in p["words"]]
        if not ws:
            continue
        marks = []
        pn = ws[0]["page"]
        ar = [w for w in ws if ARABIC.search(w["text"])]
        share = (sum(bool(HARAKAT.search(w["text"])) for w in ar) / len(ar)) if len(ar) >= VOWEL_MIN \
            else page_vowels.get(pn, 0.0)
        if pn in pages:
            marks.append("handwritten")
        elif len(ws) >= 3 and sum(w.get("hw", 0.0) >= HW_WORD for w in ws) >= HW_BLOCK * len(ws) \
                and share < VOWEL_BLOCK:            # vowelled print is styled handwritten too (0412's verse)
            marks.append("decorative")
        if share >= VOWEL_BLOCK and ar:
            marks.append("vowelled")
        if marks:
            blocks[p["idx"]] = marks
    return dict(pages=pages, blocks=blocks)


def _block_conf(doc: dict, reg: dict, para: int) -> tuple:
    """(n, median, lower quartile, lowest tenth) of Azure's confidences in a block, cached in reg."""
    cache = reg.setdefault("_conf", {})
    if para not in cache:
        W = doc["words"]
        confs = sorted(W[k]["conf"] for k in doc["paras"][para]["words"] if W[k]["conf"] is not None)
        q = (lambda f: confs[min(len(confs) - 1, int(f * len(confs)))]) if confs else (lambda f: None)
        cache[para] = (len(confs), q(0.5), q(0.25), q(0.1))
    return cache[para]


def context(doc: dict, reg: dict, w: dict) -> dict:
    """What the block-level rule looks at for one word: its block's marks and how sure Azure is of the block."""
    n, med, q25, q10 = _block_conf(doc, reg, w["para"])
    return dict(marks=reg["blocks"].get(w["para"], []), page_mark=reg["pages"].get(w["page"]), block_n=n,
                block_med=med, block_q25=q25, block_q10=q10, vowelled=bool(HARAKAT.search(w["text"])))


SPECIFIC = ("quran", "gemini", "persian", "speck", "latin")
REL_CONF = 0.5


def in_region(why: list[str], s: dict, ctx: dict, rel: float = REL_CONF, specific=SPECIFIC,
              tail: bool = True) -> list[str]:
    """Experiment 30: inside a block marked vowelled or handwritten the mark speaks for the block; a word keeps its
    own flag only for something that points at that word — a Quran difference, Gemini's other reading, a Persian
    letter, a speck (not on a handwritten page), a Latin word — or a confidence far below its own block's: under
    half the block's median and among the block's lowest tenth."""
    if not ctx.get("marks"):
        return why
    if "handwritten" in ctx["marks"]:          # a pen's strokes give small, narrow boxes everywhere: not specific
        specific = tuple(r for r in specific if r != "speck")
    keep = [r for r in why if r in specific]
    med, q10 = ctx.get("block_med"), ctx.get("block_q10")
    if "conf" in why and s["conf"] is not None and med is not None and s["conf"] < min(CONF, rel * med) \
            and (not tail or q10 is None or s["conf"] <= q10):
        keep.insert(0, "conf")
    return keep


def assess(doc: dict, quotes: list[dict], scan_pdf=None) -> dict[int, Mark]:
    """One mark per word that has a letter or digit; the page and block marks (regions) go into doc["regions"]."""
    sig = signals(doc, quotes, scan_pdf)
    reg = doc["regions"] = regions(doc)
    marks = {}
    for w in doc["words"]:
        if not is_real(w["text"]):
            continue
        s = sig[w["idx"]]
        why = refine(reasons(s), s, dict(key=w["n"]))
        verified = s["quran"][0] == "match"
        other = None
        if "gemini" in w:                       # page 1: two readers
            if same_reading(w["gemini"], w["text"]):
                verified = True
            else:
                why.append("gemini")
                other = w["text"]
        ctx = context(doc, reg, w)
        why = in_region(why, s, ctx)
        if verified and "gemini" not in why:
            marks[w["idx"]] = Mark("verified", region=ctx["marks"])
        elif why:
            marks[w["idx"]] = Mark("flagged", why, verse=s["quran"][1], other=other, region=ctx["marks"])
        else:
            marks[w["idx"]] = Mark("agreed", region=ctx["marks"])
    return marks


def summary(marks: dict[int, Mark]) -> dict:
    from collections import Counter
    c = Counter(m.mark for m in marks.values())
    out = dict(words=len(marks), verified=c["verified"], agreed=c["agreed"], flagged=c["flagged"],
               corrected=c["corrected"], why=dict(Counter(r for m in marks.values() for r in m.why).most_common()))
    reg = Counter(r for m in marks.values() for r in m.region)
    if reg:                                       # words in marked blocks, and how many of them still flagged
        out["in_marked_blocks"] = dict(reg)
        out["flagged_in_marked_blocks"] = sum(1 for m in marks.values() if m.region and m.mark == "flagged")
    return out


REGIONS = {   # id -> (short label for notes, full description for the XML headers)
    "handwritten": ("handwritten page",
                    "A handwritten page (Azure styles half or more of its words as handwritten with confidence >= 0.9): "
                    "Azure's reading of handwriting is unreliable throughout; its words are flagged only for a "
                    "specific reason, so an unflagged word here is not vouched for."),
    "decorative": ("decorative lettering",
                   "On a printed page, a block Azure takes for handwriting: a script or display typeface, calligraphy, "
                   "a handwritten note: Azure's reading is less reliable here; words are flagged only for a specific "
                   "reason."),
    "vowelled": ("vowelled text",
                 "A third or more of the block's Arabic words carry vowel marks: Azure's confidence drops on vowel marks "
                 "(below 0.8 on 23-70% of such words against 5% elsewhere), so its reading is less reliable here as a "
                 "whole and words are flagged only for a specific reason: a Quran difference, Gemini's other reading, a "
                 "Persian letter, a speck, a Latin word, or a confidence under half the block's median and in its "
                 "lowest tenth (experiment 30)."),
}


def region_summary(doc: dict, marks: dict[int, Mark] | None = None) -> dict:
    """{mark: dict(blocks=[para idx], pages=[page], words=n, flagged=n)} for the marks set by assess (doc["regions"])."""
    reg = doc.get("regions") or {}
    out = {}
    for i, ms in sorted((reg.get("blocks") or {}).items()):
        p = doc["paras"][i]
        for m in ms:
            e = out.setdefault(m, dict(blocks=[], pages=[], words=0, flagged=0))
            e["blocks"].append(i)
            e["words"] += len(p["words"])
            if marks:
                e["flagged"] += sum(1 for k in p["words"] if getattr(marks.get(k), "mark", "") == "flagged")
            pg = doc["words"][p["words"][0]]["page"]
            if pg not in e["pages"]:
                e["pages"].append(pg)
    return out


def _pages_text(pages: list[int]) -> str:
    runs, out = [], []
    for p in sorted(pages):
        if runs and p == runs[-1][1] + 1:
            runs[-1][1] = p
        else:
            runs.append([p, p])
    for a, b in runs:
        out.append(str(a) if a == b else f"{a}-{b}")
    return ", ".join(out)


def region_meta(doc: dict, marks: dict[int, Mark], bids: dict | None = None) -> list[tuple[str, str]]:
    """(name, value) for the JATS custom-meta: one per mark present, with its pages and the ids of its blocks."""
    out = []
    hw_pages = sorted((doc.get("regions") or {}).get("pages", {}))
    for m, e in region_summary(doc, marks).items():
        label, desc = REGIONS[m]
        ids = []
        if bids:
            for i in e["blocks"]:
                ids += [b for pg, b in bids.get(i, [])]
        pages = hw_pages if m == "handwritten" and hw_pages else e["pages"]
        out.append((f"reading-{m}", f"{label}: {len(e['blocks'])} block(s), {e['words']} words, {e['flagged']} of them "
                                    f"flagged, on page(s) {_pages_text(pages)}. {desc}"
                    + (f" Blocks: {' '.join(ids)}." if ids else "")))
    return out
