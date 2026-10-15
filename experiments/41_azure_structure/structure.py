"""Experiment 41: "Azure's text, Gemini's structure" on whole articles (exp 40 approach B, strict fix rule v5, carried
to whole articles with exp 40 E's chunking).

For each article (out/sample.json), chunks of <= 10 pages go to Gemini with every page image of the chunk and Azure's
lines of those pages, numbered "P:N" (page P of the article, line N in Azure's order) with boxes in 0-1000 page
coordinates. Gemini returns STRUCTURE ONLY, as line ids: blocks in reading order per page with types (heading levels,
footnotes with their marker and id, calls linking markers to footnotes, verse in half-lines, list items, references,
captions, tables as rows of cells with spans, equations as LaTeX, furniture, figures with a box), page-break
continuations, and the article's metadata. The HTML is assembled here from Azure's own text; Gemini's words enter only
as
  * `fixes`   a misreading of Azure's (the letters on the page are not Azure's letters): applied, logged (D21 / B v5);
  * `sic`     a suspected MISPRINT in the print itself: never applied; a D30 span.sic flag with data-corr;
  * `math`    a formula Azure garbled inside a line: rendered as inline LaTeX;
  * `missed`  printed text no Azure line covers: inserted with data-added;
  * equation LaTeX, a figure's description, metadata strings (which must be copied from Azure's text: checked).
Every Azure line must be used exactly once (or called noise); drops and duplicates are counted exactly.

Chunk context (exp 40 E): a later chunk also gets the article's page 1 image (context only), the outline so far and
the last block of the previous chunk, so heading levels stay consistent and a block cut by the chunk boundary can be
marked continued. A WINDOW of a long article (sample page +-2) gets page 1's image AND its lines as context, so the
metadata can still be given as Azure's text.

Outputs (out/<run>/, run = argon | flash | flash_med | argon_r2 ...):
  raw/<stem>_cAAA-BBB.json   Gemini's answer + call info (saved the moment it arrives: a rerun resumes)
  docs/<stem>.html           the article: metadata JSON, then <section class="page" data-page=N> per page
  article/<stem>.html        the flowing article (furniture out, page breaks joined)
  book/<stem>.json           bookkeeping: lines used / dropped / duplicated, fixes, flags, failures
  labels/<stem>.json         training labels: every Azure line with its block, type, order, cell, footnote link

    .venv/bin/python structure.py estimate [--stems ...]
    .venv/bin/python structure.py run --run argon [--stems S ...] [--threads 4]
    .venv/bin/python structure.py assemble --run argon          (no calls)
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import time
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import OUT, gemini, spent, _price  # noqa: E402

RUNS = {
    "argon": dict(model="gemini-4-argon", thinking="low"),
    "flash": dict(model="gemini-3.8-flash", thinking="low"),
    "flash_med": dict(model="gemini-3.8-flash", thinking="medium"),
    "argon_r2": dict(model="gemini-4-argon", thinking="low", nonce=" "),     # identical call, run again (noise)
    "flash_r2": dict(model="gemini-3.8-flash", thinking="low", nonce=" "),
}
CHUNK = 10
IMG_SIDE = 2400
PAGES = OUT / "pages"
AR = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LA = re.compile(r"[A-Za-zÀ-ɏ]")
COARSE = {"title": "heading", "heading": "heading", "byline": "heading", "paragraph": "body", "quote": "body",
          "abstract": "body", "keywords": "body", "list_item": "list", "reference": "references",
          "footnote": "footnote", "verse": "verse", "table": "table", "equation": "equation", "caption": "caption",
          "figure": "other", "header": "furniture", "footer": "furniture", "other": "other"}


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def sample() -> list[dict]:
    return jl(OUT / "sample.json")["articles"]


def art_of(stem: str) -> dict:
    return next(a for a in sample() if a["stem"] == stem)


# ------------------------------------------------------------------------------------------------ inputs

_az = {}


def azure(a: dict) -> dict:
    if a["stem"] not in _az:
        r = jl(a["azure"])
        _az[a["stem"]] = r.get("analyzeResult", r)
    return _az[a["stem"]]


def page_lines(a: dict, p: int) -> tuple[list[dict], int, int]:
    """Azure's non-empty lines of article page p: id "p:n", text, px box (300 dpi), b box (0-1000)."""
    pg = azure(a)["pages"][p - 1]
    s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
    W, H = int(round(pg["width"] * s)), int(round(pg["height"] * s))
    out = []
    for ln in pg.get("lines", []):
        t = (ln.get("content") or "").strip()
        if not t:
            continue
        xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
        px = [min(xs) * s, min(ys) * s, max(xs) * s, max(ys) * s]
        out.append(dict(id=f"{p}:{len(out) + 1}", page=p, text=t, px=[round(v, 1) for v in px],
                        b=[round(px[0] * 1000 / W), round(px[1] * 1000 / H), round(px[2] * 1000 / W),
                           round(px[3] * 1000 / H)]))
    return out, W, H


def page_image(a: dict, p: int) -> Path:
    """out/pages/<stem>_pNNN.jpg: colour render of the PDF page at 300 dpi (the frame of Azure's boxes)."""
    f = PAGES / f"{a['stem']}_p{p:03d}.jpg"
    if not f.exists():
        import pymupdf
        PAGES.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(a["pdf"]) as d:
            d[p - 1].get_pixmap(dpi=300, alpha=False).save(str(f), jpg_quality=88)
    return f


def send_jpeg(a: dict, p: int) -> bytes:
    import cv2
    img = cv2.imread(str(page_image(a, p)), cv2.IMREAD_COLOR)
    h, w = img.shape[:2]
    s = min(1.0, IMG_SIDE / max(h, w))
    if s < 1:
        img = cv2.resize(img, (int(w * s), int(h * s)), interpolation=cv2.INTER_AREA)
    return cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 88])[1].tobytes()


def chunks(a: dict) -> list[tuple[int, int]]:
    first, last = a["first"], a["last"]
    n = last - first + 1
    k = -(-n // CHUNK)
    size = -(-n // k)
    out, x = [], first
    while x <= last:
        y = min(last, x + size - 1)
        out.append((x, y))
        x = y + 1
    return out


def line_table(lines) -> str:
    return "\n".join(f"{l['id']} [{','.join(map(str, l['b']))}] {l['text']}" for l in lines)


# ------------------------------------------------------------------------------------------------ prompt

PROMPT = """You are restructuring a scanned Arabic journal article (it may contain French or English) into a clean,
faithful digital edition. A trusted OCR engine (Azure) has already read every page; its lines are listed below, page
by page. Each row: line id "P:N" (P = page number in the article, N = Azure's line number on that page), the line's
box [x0,y0,x1,y1] in 0-1000 coordinates of its page (x from the LEFT edge, y from the top), then the text exactly as
Azure read it. Azure's order is not always the reading order.
{images_note}
{context}
AZURE'S LINES:
{lines}

YOUR JOB: give the structure of pages {first}-{last}, built ONLY from these line ids. Azure's text IS the text of the
edition; you never retype it. Return one JSON object:

{{
 "metadata": {metadata_spec},
 "pages": [ {{"page": {first}, "blocks": [ ... in true reading order ... ]}}, ... one entry per page {first}..{last} ],
 "splits": [ {{"line": "3:12", "parts": ["first part", "second part"]}} ],
 "noise": ["3:40"],
 "fixes": [ {{"line": "3:7", "from": "exact substring of Azure's text", "to": "what the ink shows", "why": "short"}} ],
 "sic": [ {{"line": "3:9", "text": "exact printed substring", "corr": "the intended word", "why": "short"}} ],
 "math": [ {{"line": "3:9", "from": "exact substring of Azure's text", "latex": "LaTeX of that formula"}} ],
 "missed": [ {{"after": "3:15", "type": "paragraph", "text": "printed text that no Azure line covers"}} ]
}}

BLOCKS. Each block: {{"type": T, "lines": ["3:1", "3:2", ...]}} with its lines in reading order. Reading order is the
right-hand column before the left-hand column for Arabic, top to bottom; page furniture first or last as printed. T:
  title                 the article's main title (once in the article)
  heading               a section heading; add "level": 2 for main sections, 3 for sub-sections, 4 below that.
                        Headings that look the same in print get the same level throughout the article.
  byline                author names, affiliations, dates and places under the title or signed at the end
  abstract, keywords    an abstract paragraph / a keywords line (any language)
  paragraph             body text; one block per printed paragraph (a new block where a paragraph starts)
  list_item             one item of a numbered or bulleted list; add "list": "ol" or "ul"
  reference             one entry of a bibliography / reference list
  footnote              one footnote; add "marker": the marker as printed (e.g. "(1)", "*") and "id": "fn-P-M"
                        (P = the page the footnote is printed on, M = the marker's digits or symbol)
  verse                 one line of poetry: instead of "lines" give "hemistichs": [["3:10"], ["3:11"]], the right
                        half-line first; one Azure line holding both halves is cut with "splits". Free verse: one
                        verse block per printed line with a single hemistich.
  quote                 a Quran verse or quotation set apart from the paragraph
  table                 instead of "lines" give "rows": [[{{"lines": ["3:20"], "th": true, "colspan": 1, "rowspan": 1}},
                        ...], ...]; cells in printed order (right to left for an Arabic table); an empty cell is
                        {{"lines": []}}; the caption is its own "caption" block
  equation              a displayed formula: "lines" (Azure's garbled text of it) plus "latex"
  caption               the caption of a table or figure
  figure                a picture, chart or drawing: "box": [x0,y0,x1,y1] on its page (0-1000), "lines": any
                        text printed inside it, "description": a few words saying what it shows
  header, footer        running head, page number, journal name, issue line: page furniture
  other                 anything else
Optional on any block: "lang": "ar" | "fr" | "en".
FOOTNOTE CALLS: on EVERY block of any type (paragraph, verse, list item, table, quote, heading, even a footnote) whose
text holds footnote call markers, list each one: "calls": [{{"line": "3:5", "marker": "(1)", "fn": "fn-3-1"}}] (marker
exactly as it appears in Azure's line text, after your fix if you fixed it; "fn" = the id of the footnote it points
to). Every footnote should be called from somewhere.
PAGE BREAKS: when a block (paragraph, list item, footnote, table, verse group, quote) continues from the previous
page, give its first block on the new page "continued": true. A table whose header row is repeated on the new page
keeps that row (it is printed).

RULES
- Use EVERY line id of pages {first}-{last} exactly once across all blocks (a line in "noise" is not used): never drop
  a line, never repeat one. "noise" is only for marks that are not printed text (specks, ornaments read as letters).
- "splits" only when one Azure line holds text of two different blocks (two columns run together, both half-lines of a
  verse, a heading glued to a paragraph, a table row read as one line). The parts must be Azure's text cut into
  pieces, unchanged; then use "3:12a", "3:12b", ... instead of "3:12".
- FIXES ARE FOR AZURE'S MISREADINGS ONLY. This edition is a faithful transcription, not a corrected one: a fix must
  restore what the INK shows, letter by letter, where Azure's letters are not the printed letters (a dot missed or
  invented, a letter shape mistaken for another, a digit misread, a word cut short, a printed vowel mark lost, a
  footnote marker read as a symbol) and you can see it plainly. "from" must be an exact substring of that line.
  Never correct the author's or printer's spelling, typos, grammar, missing hamza, alif maqsura vs ya, ta marbuta vs
  ha, old or Quranic orthography, names, dialect, word spacing or punctuation. Most pages need no fix at all.
- "sic" is for a MISPRINT IN THE PRINT ITSELF, where Azure read the ink correctly but the printed word is plainly a
  printer's error (a letter dropped or doubled, two words run together by mistake). The text stays as printed; you only
  propose the intended reading. Old spelling, Quranic orthography, missing hamzas, ى for ي, ه for ة, names and dialect
  are NOT misprints. Use it rarely, only when certain.
- "math": formulas Azure turned into garbage inside a running line (displayed formulas are equation blocks).
- "missed": only printed text that no Azure line covers.
- Return only the JSON object."""

META_FULL = """{{"title": "...", "subtitle": "...", "authors": [{{"name": "...", "affiliation": "...", "email": "..."}}],
   "abstract": {{"ar": ["1:20", "1:21"], "en": ["1:30"]}}, "keywords": {{"ar": "...", "en": "..."}},
   "journal": "...", "volume": "...", "issue": "...", "year": "...", "pages_printed": "45-62", "language": "ar"}}
   (every string copied exactly from Azure's lines, as printed; abstracts as lists of line ids; null for what is not
   printed in these pages; journal, volume, issue, year may come from a running head)"""
META_NONE = "null   (already given for this article: write null)"

IMG_WHOLE = "The page images are attached in order: Image k is page {first}+k-1 of the article."
IMG_CTX = ("Image 1 is the article's FIRST page, for context only (title, authors, journal, heading style); then "
           "Image k+1 is page {first}+k-1.")

CTX_LINES = """CONTEXT ONLY - the article's page 1 lines (use them for the metadata; never put them in blocks):
{lines}
"""

STATE = """THE PREVIOUS PART of this article (pages before {first}) is already done. Keep its conventions:
* outline so far (keep these heading levels for headings that look the same): {outline}
* it ended with this {btype} block (if page {first} begins by continuing it, mark that first block "continued": true):
  <<<{last}>>>
"""


def make_prompt(a: dict, ci: int, x: int, y: int, state: dict | None) -> tuple[str, list[bytes], int]:
    lines = []
    for p in range(x, y + 1):
        ls, _, _ = page_lines(a, p)
        lines.append(f"=== PAGE {p} ===\n" + line_table(ls))
    ctx_img = x > 1
    imgs = ([send_jpeg(a, 1)] if ctx_img else []) + [send_jpeg(a, p) for p in range(x, y + 1)]
    context = ""
    want_meta = ci == 0
    if want_meta and x > 1:                      # a window: page 1's lines as context for the metadata
        ls, _, _ = page_lines(a, 1)
        context += CTX_LINES.format(lines=line_table(ls))
    if state:
        context += STATE.format(first=x, **state)
    p = PROMPT.format(images_note=(IMG_CTX if ctx_img else IMG_WHOLE).format(first=x), context=context,
                      lines="\n".join(lines), first=x, last=y, metadata_spec=META_FULL if want_meta else META_NONE)
    return p, imgs, len(imgs)


# ------------------------------------------------------------------------------------------------ run

def raw_file(run: str, stem: str, x: int, y: int) -> Path:
    return OUT / run / "raw" / f"{stem}_c{x:03d}-{y:03d}.json"


def est_tokens(prompt: str, nimg: int) -> int:
    return 1150 * nimg + int(len(prompt) / 2.6) + 300


def state_of(ans: dict, prev_outline: list) -> dict:
    outline = list(prev_outline)
    last_b = None
    for pg in ans.get("pages") or []:
        for b in pg.get("blocks") or []:
            if isinstance(b, dict):
                if b.get("type") in ("title", "heading"):
                    outline.append(dict(level=1 if b["type"] == "title" else b.get("level", 2), lines=b.get("lines")))
                if b.get("type") not in ("header", "footer"):
                    last_b = b
    return dict(outline=outline, last_block=last_b)


def run_article(run: str, a: dict, call=True) -> list[dict]:
    """Run an article's chunks in order (state carried); a rerun resumes from what is saved."""
    cfg = RUNS[run]
    recs, outline, last_b, last_text = [], [], None, ""
    for ci, (x, y) in enumerate(chunks(a)):
        rf = raw_file(run, a["stem"], x, y)
        if rf.exists():
            rec = jl(rf)
        elif not call:
            break
        else:
            state = None
            if ci > 0:
                ot = []
                for o in outline[-25:]:
                    ot.append(dict(level=o["level"], text=" ".join(lines_text(a, o.get("lines") or []))[:120]))
                state = dict(outline=json.dumps(ot, ensure_ascii=False),
                             btype=(last_b or {}).get("type", "?"), last=last_text[-500:])
            prompt, imgs, nimg = make_prompt(a, ci, x, y, state)
            prompt += cfg.get("nonce", "")
            n = y - x + 1
            info = {}
            t0 = time.time()
            ans, usd = gemini(prompt, images=imgs, tag=f"{run}_{a['stem']}_c{x:03d}-{y:03d}", model=cfg["model"],
                              max_out=min(65000, 3000 * n + 6000), thinking=cfg["thinking"], json_out=True,
                              est_in=est_tokens(prompt, nimg), info=info)
            rec = dict(stem=a["stem"], first=x, last=y, pages=n, usd=usd, wall=round(time.time() - t0, 1),
                       **{k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs", "cached", "error")})
            if ans is None:
                rec["failed"] = True
                rf.parent.mkdir(parents=True, exist_ok=True)
                (rf.parent / (rf.stem + ".failed.json")).write_text(json.dumps(rec, indent=1))
                print(f"  {run} {a['stem']} c{x}-{y}: FAILED {info.get('finish') or info.get('error') or 'refused'}",
                      flush=True)
                recs.append(rec)
                return recs
            if isinstance(ans, list):
                ans = {"pages": ans}
            rec["answer"] = ans
            rf.parent.mkdir(parents=True, exist_ok=True)
            rf.write_text(json.dumps(rec, ensure_ascii=False, indent=1), encoding="utf-8")
            print(f"  {run} {a['stem']} c{x}-{y}: {n} p, in {rec['tin']} out {rec['tout']} (think {rec['think']}) "
                  f"${usd:.4f} {rec['secs'] or 0:.0f}s   [total ${spent():.3f}]", flush=True)
        recs.append(rec)
        st = state_of(rec["answer"], outline)
        outline, last_b = st["outline"], st["last_block"]
        if last_b:
            ids = last_b.get("lines") or [i for h in (last_b.get("hemistichs") or []) for i in (h or [])] or \
                  [i for r in (last_b.get("rows") or []) for c in r if isinstance(c, dict) for i in c.get("lines") or []]
            last_text = " ".join(lines_text(a, ids))
    return recs


def lines_text(a, ids) -> list[str]:
    out = []
    for i in ids or []:
        i = str(i)
        m = re.match(r"(\d+):(\d+)", i)
        if not m:
            continue
        ls, _, _ = page_lines(a, int(m.group(1)))
        k = int(m.group(2)) - 1
        if 0 <= k < len(ls):
            out.append(ls[k]["text"])
    return out


# ------------------------------------------------------------------------------------------------ assembly

def is_rtl(t: str) -> bool:
    return len(AR.findall(t)) >= len(LA.findall(t))


def union(bs):
    bs = [b for b in bs if b]
    if not bs:
        return None
    return [min(b[0] for b in bs), min(b[1] for b in bs), max(b[2] for b in bs), max(b[3] for b in bs)]


def nows(s):
    return re.sub(r"\s+", "", s or "")


def fn_norm(fid: str) -> str:
    t = str(fid or "").translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))
    return re.sub(r"\s+", "", t)


class Store:
    """All Azure lines of the article's pages after splits; fixes applied (apply=True); sic / math / calls kept as
    decorations to render."""

    def __init__(self, a, pages, answers, apply=True):
        self.lines, self.orig = {}, []
        self.dims = {}
        for p in pages:
            ls, W, H = page_lines(a, p)
            self.dims[p] = (W, H)
            for l in ls:
                self.lines[l["id"]] = dict(l)
                self.orig.append(l["id"])
        self.issues, self.applied, self.rejected = [], [], []
        self.sic, self.sic_rejected, self.math = {}, [], {}
        for ans in answers:
            for s in ans.get("splits") or []:
                if not isinstance(s, dict):
                    continue
                lid, parts = str(s.get("line")), [p for p in (s.get("parts") or []) if isinstance(p, str)]
                same = lid in self.lines and (nows("".join(parts)) == nows(self.lines[lid]["text"]) or
                                              sorted(" ".join(parts).split()) == sorted(self.lines[lid]["text"].split()))
                if same and not self.lines[lid].get("split") and len(parts) >= 2:
                    if nows("".join(parts)) != nows(self.lines[lid]["text"]):
                        self.issues.append(dict(kind="split_reordered", line=lid))      # Azure's words, other order
                    base = self.lines[lid]
                    tot, acc = sum(len(nows(p)) for p in parts) or 1, 0
                    rtl = is_rtl(base["text"])
                    for k, p in enumerate(parts):
                        f0, f1 = acc / tot, (acc + len(nows(p))) / tot
                        acc += len(nows(p))
                        bb, pp = base["b"], base["px"]

                        def cut(b):
                            w = b[2] - b[0]
                            return ([round(b[2] - f1 * w, 1), b[1], round(b[2] - f0 * w, 1), b[3]] if rtl else
                                    [round(b[0] + f0 * w, 1), b[1], round(b[0] + f1 * w, 1), b[3]])
                        nid = f"{lid}{'abcdefghijklmnop'[k]}"
                        self.lines[nid] = dict(base, id=nid, text=p.strip(), split_of=lid, b=cut(bb), px=cut(pp))
                    base["split"] = True
                else:
                    self.issues.append(dict(kind="bad_split", item=s))
        if not apply:
            return
        for ans in answers:
            for f in ans.get("fixes") or []:
                if not isinstance(f, dict):
                    continue
                L = self.get(f.get("line"), f.get("from"))
                if L is None or not f.get("from") or f["from"] not in L["text"] or f.get("from") == f.get("to"):
                    self.rejected.append(f)
                    continue
                L.setdefault("azure_text", L["text"])
                L["text"] = L["text"].replace(f["from"], f.get("to") or "", 1)
                self.applied.append(dict(f, at=L["id"], page=L["page"]))
            for s in ans.get("sic") or []:
                if not isinstance(s, dict):
                    continue
                L = self.get(s.get("line"), s.get("text"))
                if L is None or not s.get("text") or s["text"] not in L["text"] or not s.get("corr") or \
                        s.get("corr") == s.get("text"):
                    self.sic_rejected.append(s)
                    continue
                self.sic.setdefault(L["id"], []).append(dict(s, at=L["id"], page=L["page"]))
            for m in ans.get("math") or []:
                if not isinstance(m, dict):
                    continue
                L = self.get(m.get("line"), m.get("from"))
                if L is None or not m.get("from") or m["from"] not in L["text"] or not m.get("latex"):
                    self.rejected.append(dict(m, kind="math"))
                    continue
                self.math.setdefault(L["id"], []).append(m)

    def get(self, lid, sub=None):
        lid = str(lid)
        L = self.lines.get(lid)
        if L is not None and L.get("split") and sub:
            parts = [x for x in self.lines.values() if x.get("split_of") == lid and sub in x["text"]]
            return parts[0] if parts else None
        return L

    def text_html(self, lid, calls=(), source="model"):
        L = self.lines[lid]
        t = L["text"]
        reps, k = {}, 0
        for m in self.math.get(lid, []):
            if m["from"] in t:
                ph = f"\ue000{k}\ue001"
                k += 1
                t = t.replace(m["from"], ph, 1)
                reps[ph] = f'<span class="math">\\({html.escape(m["latex"])}\\)</span>'
        for s in self.sic.get(lid, []):
            if s["text"] in t:
                ph = f"\ue000{k}\ue001"
                k += 1
                t = t.replace(s["text"], ph, 1)
                reps[ph] = (f'<span class="sic" data-corr="{html.escape(s["corr"])}" '
                            f'data-why="{html.escape(s.get("why") or "")}" data-source="{source}">'
                            f'{html.escape(s["text"])}</span>')
        for c in calls:
            mk = c.get("marker")
            if mk and mk in t:
                ph = f"\ue000{k}\ue001"
                k += 1
                t = t.replace(mk, ph, 1)
                reps[ph] = f'<sup><a href="#{html.escape(fn_norm(c.get("fn")))}">{html.escape(mk)}</a></sup>'
                c["_placed"] = True
        t = html.escape(t)
        for ph, r in reps.items():
            t = t.replace(ph, r)
        return t


def bbox_attr(b):
    return f' data-bbox="{round(b[0])},{round(b[1])},{round(b[2])},{round(b[3])}"' if b else ""


def ids_of_block(b) -> list[str]:
    if not isinstance(b, dict):
        return []
    if b.get("type") == "table":
        out = []
        for r in b.get("rows") or []:
            for c in (r if isinstance(r, list) else []):
                c = c if isinstance(c, dict) else {"lines": [c]}
                out += [str(i) for i in c.get("lines") or []]
        return out + [str(i) for i in b.get("lines") or []]
    if b.get("type") == "verse" and b.get("hemistichs"):
        return [str(i) for h in b["hemistichs"] for i in (h if isinstance(h, list) else [h])]
    return [str(i) for i in b.get("lines") or []]


def assemble(run: str, a: dict, apply=True) -> dict | None:
    """Build docs/, article/, book/, labels/ for one article from its saved chunk answers."""
    recs = []
    for x, y in chunks(a):
        rf = raw_file(run, a["stem"], x, y)
        if not rf.exists():
            ff = rf.parent / (rf.stem + ".failed.json")
            recs.append({**(jl(ff) if ff.exists() else {}), "first": x, "last": y, "failed": True})
            continue
        recs.append(jl(rf))
    ok = [r for r in recs if not r.get("failed")]
    if not ok:
        return None
    pages = list(range(a["first"], a["last"] + 1))
    answers = [r["answer"] for r in ok]
    S = Store(a, pages, answers, apply)
    lost_pages = [p for r in recs if r.get("failed") for p in range(r["first"], r["last"] + 1)]
    src = RUNS[run]["model"].replace("gemini-", "").split("-")[-1]      # argon / flash

    used = Counter()
    misplaced = []
    blocks_out = []                                   # flat: dict(page, type, ids, html, ...)
    fn_ids, calls_all = {}, []
    missed_after = {}
    if apply:
        for ans in answers:
            for m in ans.get("missed") or []:
                if isinstance(m, dict) and (m.get("text") or "").strip():
                    missed_after.setdefault(str(m.get("after")), []).append(m)

    def take(ids, page):
        res = []
        for i in ids or []:
            i = str(i).strip()
            if i in S.lines and not S.lines[i].get("split"):
                res.append(i)
            elif i in S.lines:
                res.extend(k for k in S.lines if S.lines[k].get("split_of") == i)
            else:
                S.issues.append(dict(kind="unknown_id", id=i, page=page))
                continue
        for i in res:
            used[i] += 1
            if S.lines[i]["page"] != page:
                misplaced.append(i)
        return res

    page_blocks = {p: [] for p in pages}
    for ans in answers:
        for pg in ans.get("pages") or []:
            if not isinstance(pg, dict):
                continue
            try:
                p = int(pg.get("page"))
            except Exception:
                continue
            if p not in page_blocks:
                S.issues.append(dict(kind="page_out_of_range", page=p))
                continue
            page_blocks[p].extend(b for b in (pg.get("blocks") or []) if isinstance(b, dict))

    order = 0
    for p in pages:
        for blk in page_blocks[p]:
            T = (blk.get("type") or "paragraph").lower()
            if T not in COARSE:
                S.issues.append(dict(kind="unknown_type", type=T, page=p))
                T = "other"
            rec = dict(page=p, type=T, level=blk.get("level"), continued=bool(blk.get("continued")),
                       lang=blk.get("lang"), n=len(blocks_out) + 1,
                       list=blk.get("list"))
            if T == "verse":
                hs = blk.get("hemistichs") or ([blk["lines"]] if blk.get("lines") else [])
                rec["hemistichs"] = [take(h if isinstance(h, list) else [h], p) for h in hs]
                rec["ids"] = [i for h in rec["hemistichs"] for i in h]
            elif T == "table":
                rows = []
                for r in blk.get("rows") or []:
                    row = []
                    for c in (r if isinstance(r, list) else []):
                        c = c if isinstance(c, dict) else {"lines": [c]}
                        sp = {k: int(c[k]) for k in ("colspan", "rowspan")
                              if str(c.get(k, 1)).isdigit() and int(c.get(k, 1)) > 1}
                        row.append(dict(ids=take(c.get("lines"), p), th=bool(c.get("th")), **sp))
                    rows.append(row)
                for i in take(blk.get("lines"), p):
                    rows.append([dict(ids=[i], th=False)])
                # cell order from Azure's boxes: an Arabic table's cells run right to left (decreasing x), a Latin
                # table's left to right. The models give the same table in either order from one call to the next
                # (exp 41: identical calls, same cells, TEDS 0.3), so the order is set here, deterministically.
                rtl_t = is_rtl(" ".join(S.lines[i]["text"] for r in rows for c in r for i in c["ids"]))
                for r in rows:
                    xs = [(sum(S.lines[i]["b"][0] + S.lines[i]["b"][2] for i in c["ids"]) / (2 * len(c["ids"])))
                          for c in r if c["ids"]]
                    if len(xs) >= 2:
                        inc = sum(1 for u, v in zip(xs, xs[1:]) if v > u)
                        dec = sum(1 for u, v in zip(xs, xs[1:]) if v < u)
                        if (rtl_t and inc > dec) or (not rtl_t and dec > inc):
                            r.reverse()
                            S.issues.append(dict(kind="table_row_reversed", page=p))
                rec["rows"] = rows
                rec["ids"] = [i for r in rows for c in r for i in c["ids"]]
            else:
                rec["ids"] = take(blk.get("lines"), p)
            if T == "equation":
                rec["latex"] = (blk.get("latex") or "").strip()
            if T == "figure":
                bx = blk.get("box")
                rec["fig_box"] = [float(v) for v in bx][:4] if isinstance(bx, list) and len(bx) == 4 and \
                    all(isinstance(v, (int, float)) for v in bx) else None
                rec["description"] = blk.get("description")
            if T == "footnote":
                rec["marker"] = blk.get("marker")
                fid = fn_norm(blk.get("id") or f"fn-{p}-{blk.get('marker')}")
                rec["fn_id"] = fid
                if not rec["continued"]:
                    fn_ids.setdefault(fid, rec["n"])
            rec["calls"] = [dict(c) for c in (blk.get("calls") or []) if isinstance(c, dict)]
            for c in rec["calls"]:
                c["page"] = p
                c["block"] = rec["n"]
                calls_all.append(c)
            if not rec["ids"] and not (T == "equation" and rec.get("latex")) and not (T == "figure" and rec.get("fig_box")):
                continue
            rec["order"] = order
            order += 1
            blocks_out.append(rec)

    # ---- HTML per block
    def join(ids, calls=()):
        cs = {}
        for c in calls:
            cs.setdefault(str(c.get("line")), []).append(c)
        out = []
        for i in ids:
            L = S.lines[i]
            out.append(S.text_html(i, cs.get(i, []) + cs.get(L.get("split_of") or "\0", []), src))
        return " ".join(out)

    def box_of(ids, rec):
        if rec.get("fig_box"):
            return rec["fig_box"]
        return union([S.lines[i]["b"] for i in ids if S.lines[i]["page"] == rec["page"]])

    def attrs(rec, ids):
        t = " ".join(S.lines[i]["text"] for i in ids)
        lang = rec.get("lang") or ("ar" if is_rtl(t) else ("fr" if re.search(r"[éèàçêùâô]", t) else "en"))
        d = "rtl" if lang == "ar" else "ltr"
        ex = f' data-n="{rec["n"]}" data-type="{rec["type"]}"'
        if rec["continued"]:
            ex += ' data-continued="prev"'
        return f'{ex}{bbox_attr(box_of(ids, rec))} dir="{d}" lang="{lang}" data-lines="{" ".join(ids)}"'

    for rec in blocks_out:
        T, ids = rec["type"], rec["ids"]
        if T == "verse":
            spans = "".join(f'<span class="hemistich"{bbox_attr(union([S.lines[i]["b"] for i in h]))}>{join(h)}</span>'
                            for h in rec["hemistichs"] if h)
            cls = "verse free" if len([h for h in rec["hemistichs"] if h]) == 1 else "verse"
            rec["html"] = f'<div class="{cls}"{attrs(rec, ids)}>{spans}</div>'
        elif T == "table":
            trs = []
            for r in rec["rows"]:
                cells = []
                for c in r:
                    tg = "th" if c["th"] else "td"
                    sp = "".join(f' {k}="{c[k]}"' for k in ("colspan", "rowspan") if k in c)
                    cells.append(f"<{tg}{sp}{bbox_attr(union([S.lines[i]['b'] for i in c['ids']]))}>"
                                 f"{join(c['ids'], rec['calls'])}</{tg}>")
                trs.append("<tr>" + "".join(cells) + "</tr>")
            rec["html"] = f'<table{attrs(rec, ids)}>' + "".join(trs) + "</table>"
        elif T == "equation":
            if rec.get("latex"):
                rec["html"] = (f'<div class="equation"{attrs(rec, ids)}><span class="math">\\[{html.escape(rec["latex"])}'
                               f'\\]</span></div>')
            else:
                rec["html"] = f'<div class="equation"{attrs(rec, ids)}>{join(ids)}</div>'
        else:
            tag, cls = {"title": ("h1", ""), "heading": (f"h{min(6, max(2, int(rec['level'] or 2)))}"
                                                         if str(rec.get("level") or 2).isdigit() else "h2", ""),
                        "byline": ("p", ' class="byline"'), "abstract": ("p", ' class="abstract"'),
                        "keywords": ("p", ' class="keywords"'), "list_item": ("li", ""), "reference": ("li", ""),
                        "footnote": ("aside", ' class="footnote"'), "quote": ("blockquote", ""),
                        "caption": ("p", ' class="caption"'), "figure": ("figure", ""),
                        "header": ("header", ' class="furniture"'), "footer": ("footer", ' class="furniture"'),
                        "other": ("div", ' class="other"')}.get(T, ("p", ""))
            if T == "footnote" and not rec["continued"]:
                cls += f' id="{html.escape(rec["fn_id"])}"'
            inner = join(ids, rec["calls"])
            if T == "figure":
                d = html.escape(rec.get("description") or "")
                inner = (f'<figcaption>{inner}</figcaption>' if ids else "")
                cls += f' data-description="{d}"'
            rec["html"] = f"<{tag}{cls}{attrs(rec, ids)}>{inner}</{tag}>"
        for i in ids:
            for m in missed_after.pop(i, []) + missed_after.pop(S.lines[i].get("split_of") or "\0", []):
                t = m["text"].strip()
                rec.setdefault("missed_html", []).append(
                    f'<p dir="{"rtl" if is_rtl(t) else "ltr"}" data-added="{src}">{html.escape(t)}</p>')
                rec.setdefault("missed", []).append(m)
    leftover_missed = [m for ms in missed_after.values() for m in ms]

    # list wrapping per page
    def page_html(p):
        out, open_l = [], None
        for rec in [r for r in blocks_out if r["page"] == p]:
            want = {"list_item": rec.get("list") if rec.get("list") in ("ol", "ul") else "ol",
                    "reference": "references"}.get(rec["type"])
            if want != open_l:
                if open_l:
                    out.append("</ul>" if open_l == "ul" else "</ol>")
                if want:
                    out.append('<ol class="references">' if want == "references" else f"<{want}>")
                open_l = want
            out.append(rec["html"])
            out.extend(rec.get("missed_html", []))
        if open_l:
            out.append("</ul>" if open_l == "ul" else "</ol>")
        return "\n".join(out)

    # ---- metadata
    meta = {}
    for ans in answers[:1]:
        m = ans.get("metadata")
        if isinstance(m, dict):
            meta = m
    meta_out, meta_check = resolve_meta(S, meta, a)

    # ---- bookkeeping on Azure's ORIGINAL lines
    noise = {str(x) for ans in answers for x in (ans.get("noise") or [])}
    base_used, nparts = Counter(), Counter()
    for i, n in used.items():
        base_used[S.lines[i].get("split_of") or i] += n
    for i in S.lines:
        if S.lines[i].get("split_of"):
            nparts[S.lines[i]["split_of"]] += 1
    live = [i for i in S.orig if S.lines[i]["page"] not in lost_pages]
    dropped = [i for i in live if base_used[i] == 0 and i not in noise]
    dup = [i for i in live if base_used[i] > max(1, nparts.get(i, 1))]
    fn_targets = set(fn_ids)
    resolved = [c for c in calls_all if fn_norm(c.get("fn")) in fn_targets]
    called = {fn_norm(c.get("fn")) for c in calls_all}
    book = dict(stem=a["stem"], run=run, pages=len(pages), chunks=len(recs), chunks_failed=sum(1 for r in recs if r.get("failed")),
                failed=[{k: r.get(k) for k in ("first", "last", "finish", "error")} for r in recs if r.get("failed")],
                lost_pages=lost_pages, lines=len(live), used=sum(1 for i in live if base_used[i] > 0),
                dropped=dropped, duplicated=dup, noise=sorted(noise), misplaced=sorted(set(misplaced)),
                dropped_chars=sum(len(S.lines[i]["text"]) for i in dropped),
                chars=sum(len(S.lines[i]["text"]) for i in live),
                splits=sum(1 for i in S.orig if S.lines[i].get("split")),
                fixes_applied=S.applied, fixes_rejected=S.rejected,
                sic=[s for v in S.sic.values() for s in v], sic_rejected=S.sic_rejected,
                math=sum(len(v) for v in S.math.values()),
                missed=[m for r in blocks_out for m in r.get("missed", [])] + leftover_missed,
                issues=S.issues[:50], n_issues=len(S.issues), blocks=len(blocks_out),
                types=dict(Counter(r["type"] for r in blocks_out)),
                footnotes=len(fn_ids), calls=len(calls_all), calls_resolved=len(resolved),
                calls_placed=sum(1 for r in blocks_out for c in r["calls"] if c.get("_placed")),
                footnotes_uncalled=sorted(fn_targets - called),
                continued=sum(1 for r in blocks_out if r["continued"]),
                figures=sum(1 for r in blocks_out if r["type"] == "figure"),
                tables=sum(1 for r in blocks_out if r["type"] == "table"),
                equations=sum(1 for r in blocks_out if r["type"] == "equation"),
                meta_check=meta_check,
                usd=round(sum(r.get("usd") or 0 for r in recs), 5),
                secs=round(sum(r.get("secs") or 0 for r in recs), 1),
                tin=sum(r.get("tin") or 0 for r in recs), tout=sum(r.get("tout") or 0 for r in recs),
                think=sum(r.get("think") or 0 for r in recs))

    d = OUT / run
    if apply:
        doc = [f'<script type="application/json" id="article-meta">{json.dumps(meta_out, ensure_ascii=False)}</script>']
        for p in pages:
            W, H = S.dims[p]
            doc.append(f'<section class="page" data-page="{p}" data-width="{W}" data-height="{H}">\n{page_html(p)}\n'
                       f'</section>')
        for sub in ("docs", "article", "book", "labels"):
            (d / sub).mkdir(parents=True, exist_ok=True)
        (d / "docs" / f"{a['stem']}.html").write_text("\n".join(doc) + "\n", encoding="utf-8")
        (d / "article" / f"{a['stem']}.html").write_text(article_view(meta_out, blocks_out, pages), encoding="utf-8")
        (d / "book" / f"{a['stem']}.json").write_text(json.dumps(book, ensure_ascii=False, indent=1), encoding="utf-8")
        (d / "labels" / f"{a['stem']}.json").write_text(json.dumps(labels(a, S, blocks_out, meta_out, fn_ids, run),
                                                                   ensure_ascii=False), encoding="utf-8")
    return book


def resolve_meta(S: Store, meta: dict, a: dict) -> tuple[dict, dict]:
    """Abstract line ids -> Azure's text; every metadata string checked against the article's Azure text (as fixed)."""
    allt = " ".join(L["text"] for L in S.lines.values() if not L.get("split"))
    hay = nows(allt)
    if a["first"] > 1:                          # a window: page 1 was context
        ls, _, _ = page_lines(a, 1)
        hay += nows(" ".join(l["text"] for l in ls))
    chk = dict(strings=0, verbatim=0, not_verbatim=[])

    def check(v, what):
        if isinstance(v, str) and v.strip():
            chk["strings"] += 1
            if nows(v) in hay:
                chk["verbatim"] += 1
            else:
                chk["not_verbatim"].append(dict(field=what, text=v[:200]))
    out = {}
    for k, v in (meta or {}).items():
        if k == "abstract" and isinstance(v, dict):
            out[k] = {}
            for lang, ids in v.items():
                if isinstance(ids, list):
                    txt = []
                    for i in ids:
                        L = S.lines.get(str(i))
                        if L is None and a["first"] > 1 and str(i).startswith("1:"):
                            txt += lines_text(a, [i])
                        elif L is not None:
                            txt.append(L["text"] if not L.get("split") else
                                       " ".join(x["text"] for x in S.lines.values() if x.get("split_of") == str(i)))
                    out[k][lang] = " ".join(txt)
                elif isinstance(ids, str):
                    out[k][lang] = ids
                    check(ids, f"abstract.{lang}")
        elif k == "authors" and isinstance(v, list):
            out[k] = v
            for au in v:
                if isinstance(au, dict):
                    for f in ("name", "affiliation", "email"):
                        check(au.get(f), f"authors.{f}")
                else:
                    check(au, "authors")
        elif k == "keywords" and isinstance(v, dict):
            out[k] = v
            for lang, t in v.items():
                if isinstance(t, list):
                    for x in t:
                        check(x, f"keywords.{lang}")
                else:
                    check(t, f"keywords.{lang}")
        else:
            out[k] = v
            if k not in ("language",):
                check(v, k)
    return out, chk


def labels(a, S, blocks_out, meta, fn_ids, run) -> dict:
    """Training labels: every Azure line (after splits) with its block and role, plus the blocks themselves."""
    rows = []
    for rec in blocks_out:
        role = {}
        if rec["type"] == "verse":
            for k, h in enumerate(rec["hemistichs"]):
                for i in h:
                    role[i] = dict(hemistich=k)
        if rec["type"] == "table":
            for r, row in enumerate(rec["rows"]):
                for c, cell in enumerate(row):
                    for i in cell["ids"]:
                        role[i] = dict(row=r, col=c, th=cell["th"], colspan=cell.get("colspan", 1),
                                       rowspan=cell.get("rowspan", 1))
        for k, i in enumerate(rec["ids"]):
            L = S.lines[i]
            rows.append(dict(id=i, page=L["page"], text=L["text"], azure_text=L.get("azure_text"), box=L["px"],
                             block=rec["n"], type=rec["type"], label=COARSE[rec["type"]], level=rec.get("level"),
                             order=rec["order"], k=k, **role.get(i, {})))
    blocks = []
    for rec in blocks_out:
        b = {k: rec.get(k) for k in ("n", "page", "type", "level", "continued", "lang", "ids", "order", "latex",
                                     "fig_box", "description", "marker", "fn_id") if rec.get(k) not in (None, [], "")}
        b["label"] = COARSE[rec["type"]]
        if rec["type"] == "table":
            b["rows"] = rec["rows"]
        if rec["type"] == "verse":
            b["hemistichs"] = rec["hemistichs"]
        if rec["calls"]:
            b["calls"] = [{k: c.get(k) for k in ("line", "marker", "fn")} for c in rec["calls"]]
        blocks.append(b)
    pages = {p: dict(width=S.dims[p][0], height=S.dims[p][1]) for p in S.dims}
    return dict(stem=a["stem"], run=run, model=RUNS[run]["model"], first=a["first"], last=a["last"], pages=pages,
                metadata=meta, lines=rows, blocks=blocks, footnotes=fn_ids,
                note="boxes in pixels of the page rendered at 300 dpi (Azure's frame); text = Azure's after fixes")


CSS_ARTICLE = """body{margin:0;background:#fff;color:#111;font-family:'Scheherazade New',serif;font-size:20px;line-height:1.7}
.sheet{max-width:820px;margin:0 auto;padding:24px 20px}
h1{font-size:1.6em} h2{font-size:1.3em} h3{font-size:1.12em} h4{font-size:1em}
.verse{display:grid;grid-template-columns:1fr 1fr;gap:0 3em;margin:.1em 0}.verse .hemistich{text-align:center}
.verse.free{display:block}
aside.footnote{font-size:.85em;color:#333;border-top:1px solid #ddd}
table{border-collapse:collapse;margin:.5em 0;font-size:.9em} td,th{border:1px solid #999;padding:2px 6px}
.equation{direction:ltr;text-align:center}.pb{font:11px sans-serif;color:#999}
.sic{text-decoration:underline wavy #c80}.byline{color:#555}[data-added]{background:#fff3c4}
.meta{font:13px sans-serif;background:#f6f6f6;padding:8px;direction:rtl}"""


def article_view(meta, blocks_out, pages) -> str:
    out, prev = [], None
    for rec in blocks_out:
        if rec["type"] in ("header", "footer"):
            continue
        h = rec["html"]
        if rec["continued"] and prev is not None and prev["type"] == rec["type"] and rec["type"] in \
                ("paragraph", "footnote", "quote", "list_item", "abstract"):
            inner = re.sub(r"^<[^>]+>|</[^>]+>$", "", h)
            out[-1] = re.sub(r"(</[a-z0-9]+>)$", f' <span class="pb">[{rec["page"]}]</span> {inner}\\1', out[-1])
        else:
            out.append(h)
        prev = rec
    m = meta or {}
    head = f'<div class="meta">{html.escape(json.dumps(m, ensure_ascii=False)[:3000])}</div>'
    return (f'<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>{CSS_ARTICLE}</style>'
            f'</head><body><div class="sheet">{head}\n' + "\n".join(out) + "</div></body></html>\n")


# ------------------------------------------------------------------------------------------------ estimate

def estimate(stems=None, runs=("argon", "flash"), calib=None) -> dict:
    """Worst case and expected cost of running the given articles with the given runs (no calls)."""
    tot = {}
    for run in runs:
        pin, pout = _price(RUNS[run]["model"])
        e_usd = w_usd = 0.0
        npg = 0
        for a in sample():
            if stems and a["stem"] not in stems:
                continue
            for ci, (x, y) in enumerate(chunks(a)):
                if raw_file(run, a["stem"], x, y).exists():
                    continue
                n = y - x + 1
                npg += n
                lines = sum(len(page_lines(a, p)[0]) for p in range(x, y + 1))
                chars = sum(len(l["text"]) + 26 for p in range(x, y + 1) for l in page_lines(a, p)[0])
                tin = 1150 * (n + (x > 1)) + int((chars + len(PROMPT)) / 2.6)
                c = (calib or {}).get(run, {})
                tout = c.get("out_per_line", 9.0) * lines + c.get("out_per_page", 150) * n
                tin = tin * c.get("in_factor", 1.0)
                e_usd += tin / 1e6 * pin + tout / 1e6 * pout
                w_usd += tin / 1e6 * pin + min(65000, 3000 * n + 6000) / 1e6 * pout
        tot[run] = dict(pages=npg, expected=round(e_usd, 3), worst=round(w_usd, 3))
    return tot


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["estimate", "run", "assemble"])
    ap.add_argument("--run", default="argon", choices=list(RUNS))
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--threads", type=int, default=4)
    ap.add_argument("--max-usd", type=float, default=None, help="stop starting new articles past this total spend")
    a = ap.parse_args()
    arts = [x for x in sample() if not a.stems or x["stem"] in a.stems]
    if a.cmd == "estimate":
        calib = None
        cf = OUT / "calibration.json"
        if cf.exists():
            calib = jl(cf)
        print(json.dumps(estimate(a.stems, calib=calib), indent=1), f"spent ${spent():.3f}")
        return
    if a.cmd == "run":
        print(f"{a.run}: {len(arts)} articles; spent so far ${spent():.3f}", flush=True)

        def one(x):
            if a.max_usd is not None and spent() > a.max_usd:
                print(f"  skip {x['stem']}: spend ${spent():.3f} past --max-usd", flush=True)
                return
            try:
                run_article(a.run, x)
                assemble(a.run, x)
            except Exception as e:                      # one article's bug must not stop the batch
                import traceback
                traceback.print_exc()
                print(f"  {x['stem']}: ERROR {type(e).__name__} {e}", flush=True)
        with ThreadPoolExecutor(min(4, a.threads)) as ex:
            list(ex.map(one, arts))
        print(f"spent ${spent():.3f}")
    for x in arts:
        b = assemble(a.run, x)
        if b:
            print(f"  {x['stem']:24} p{b['pages']:>2} lines {b['used']}/{b['lines']} drop {len(b['dropped'])} dup "
                  f"{len(b['duplicated'])} fix {len(b['fixes_applied'])}(-{len(b['fixes_rejected'])}) sic {len(b['sic'])} "
                  f"fn {b['calls_resolved']}/{b['calls']} cont {b['continued']} fail {b['chunks_failed']} "
                  f"issues {b['n_issues']} ${b['usd']:.3f}")


if __name__ == "__main__":
    main()
