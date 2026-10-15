"""Experiment 40, approach E ("best"): the integration of what worked in A-D.

Pass 1 - whole document, one call (C's win: metadata, consistent heading levels, page breaks joined, cheaper than
         page by page), with D's strict transcription rules (copy only printed vowel marks; the prompt was worth more
         than any extra pass), high media resolution (ultra_high is refused for PDF parts: 400 INVALID_ARGUMENT), and fixes for what A-D saw go wrong:
           * faint dots: ة / ي stay dotted unless the print clearly has no dots (D's strict prompt over-applied
             "dotless as printed");
           * misprints are copied, not corrected (A, B, D all saw المتعمون -> المتعلمون);
           * lists keep the printed number as text, with list-style:none (no double numbers when rendered; the
             scorer no longer counts printed note numbers as dropped);
           * free verse gets <div class="verse free"> per printed line (C/D: 0732 written as paragraphs);
           * bold as <b>; every figure has a box (cropped into the article view as a picture).
         Documents over 12 pages go in chunks of up to 10 pages; each chunk carries the document's first page as
         context-only (metadata, heading style) and the outline + last block of the previous chunk (state).
         In this experiment one long document (0870, 22 pages) is run whole in chunks; the other long documents
         are run as a window (sample page - 1 .. sample page + 1) with page 1 as context.

Pass 2 - Azure-arbitrated look-again (B's lesson: Azure is a trusted second reader; D's lesson: a zoomed look fixes
         letters, but re-reading every block is expensive and buys little). Every word where Argon's text and
         Azure's words in the same box disagree (letters, ة/ه, ى/ي, hamza, spacing, or vowel marks) becomes a
         question. Each question is a full-resolution crop of the word (Azure's own word box, with its neighbours),
         packed into sheets; one call per page asks which reading the INK shows (A / B / neither + what is printed /
         unclear). Azure's text is never taken without the image agreeing, and Argon's language prior is starved:
         the crop shows a few words, not a sentence to "fix".

Local  - figure crops into the article view; the flowing article (C's article_view); per-page cost files.

    .venv/bin/python best.py plan                 # units, pages, worst-case cost
    .venv/bin/python best.py run [--stems S ...] [--no-p2]
    .venv/bin/python best.py arb-only DIR         # pass 2 on another approach's page HTML (e.g. out/A_oneshot)
Outputs in out/E_best/ (see notes.md there).
"""
from __future__ import annotations

import argparse
import base64
import difflib
import hashlib
import json
import re
import sys
import time
import unicodedata
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import CAP, DOCS, OUT, PAGES, gemini, sample, spent, strip_fences  # noqa: E402
from C_whole_document import article_view, split_answer  # noqa: E402  (read-only reuse)

TAG = "E_best"
ED = OUT / "E_best"
HEADROOM = 0.50
FULL_CHUNKED = {"0870-017-001-003"}        # long documents run whole, in chunks (the archive-scale path)
WHOLE_MAX = 12
CHUNK = 10
P2_MAX_Q = 64
P2_MODE = "blind"          # "blind": transcribe the crop with no readings shown; "choose": A/B with spelling
HARAKAT = re.compile("[ً-ٰٟۖ-ۭ࣓-ࣿ]")
TATWEEL = "ـ"


def subcap() -> tuple[str, float]:
    other = spent() - spent(TAG)
    return (TAG, round(CAP - HEADROOM - other, 4))


# ------------------------------------------------------------------------------------------------ prompts

P1 = """You are given a scanned Arabic journal article: the attached PDF.
{pagemap}
Turn it into ONE semantic HTML document that is a faithful, complete digital edition.{state}

Output exactly this, and nothing else (no commentary, no markdown fences):

1. First, the article's metadata as JSON inside
   <script type="application/json" id="article-meta">{{...}}</script>
   with keys: "title", "subtitle", "authors" (list of {{"name", "affiliation", "email"}}), "abstract" (object, one
   entry per language printed, e.g. {{"ar": "...", "en": "..."}}), "keywords" (object per language, lists),
   "journal", "volume", "issue", "year", "pages_printed", "language",
   "sections" (the outline of the pages you transcribe: list of {{"level": 2, "title": "...", "page": N}}),
   "figures" (list of {{"page": N, "caption": "...", "description": "what the figure shows"}}),
   "tables" (list of {{"page": N, "caption": "..."}}). Copy values exactly as printed; null when not printed
   (a journal name or year read from a running header counts as printed).

2. Then, for every page to transcribe, in order, one
   <section class="page" data-page="N"> ... </section>   (N = the document page number given above)
   holding everything printed on that page, in reading order (Arabic columns right to left: the right column
   first; a paragraph cut at the bottom of a column continues at the top of the next), with these elements:
   - article title: <h1> (the main title only, once per article); main section headings <h2>; sub-headings <h3>;
     headings that look the same in print get the same level throughout the article
   - body paragraph: <p>, one per printed paragraph (not one per line)
   - numbered / bulleted list: <ol style="list-style:none"> (or <ul style="list-style:none">) with one <li> per item;
     each <li> starts with its printed number or bullet copied as text (e.g. <li>١- ...</li>, <li>(أ) ...</li>)
   - bibliography / references: <ol class="references" style="list-style:none"> with one <li> per entry, its
     printed number kept as text
   - footnote: <aside class="footnote" id="fn-N-M">...</aside> where N is the page number and M the marker as
     printed; the aside starts with its printed marker. In the text, the marker is <sup><a href="#fn-N-M">M</a></sup>
     exactly where printed. Every marker links to its footnote; ids are unique in the whole document.
   - classical verse (a line printed as two half-lines): <div class="verse"><span class="hemistich">first half</span>
     <span class="hemistich">second half</span></div>, one div per verse line, the right half first
   - free verse (poem lines printed one per line, not in two halves): <div class="verse free">one printed line</div>,
     one div per printed line
   - table: <table> with <tr>, <th>/<td>, rowspan/colspan as printed; caption in <caption>
   - equation: inline <span class="math">\\(LaTeX\\)</span>; display
     <div class="equation"><span class="math">\\[LaTeX\\]</span></div>
   - figure / picture / chart / photo / map / logo: <figure data-bbox="..."><figcaption>printed caption</figcaption>
     </figure> (text that is part of a drawing stays out of the page text)
   - running header, page number, footer: <header class="furniture">...</header> /
     <footer class="furniture">...</footer> inside the page's section
   - anything else (signatures, place and date, epigraph boxes): <div class="other">
   - words printed in bold inside a paragraph or footnote: <b>...</b>
   Give every block dir="rtl" or dir="ltr", lang ("ar", "fr", "en"), and data-bbox="x0,y0,x1,y1": the block's
   box on ITS page in 0-1000 coordinates (x from the left edge, y from the top), tight around its ink.

3. Page breaks. When a paragraph, list, table, footnote or verse block is cut by a page break, give its last block
   on page N data-continues="next" and its first block on page N+1 data-continued="prev" (no repeated words).

Text rules - copy exactly what is printed, character for character:
* Vowel marks: copy ONLY the marks that are actually printed. Most body text in these journals is printed without
  vowel marks: then write none. Never add a fatha, damma or kasra on a hamza seat (أ إ ؤ) unless you see it
  printed. Quran, verse and some words do carry marks - copy those exactly (shadda, sukun, tanween included).
  Tanween al-fath goes where it is printed (usually on the alef: ـاً).
* Dots: ة and ي are written with their dots even when the dots are faint, broken or touching a neighbour; write
  ه or ى only when the print clearly has no dots there. Hamza forms, alif maqsura, and rare letters (چ پ ڤ گ) as
  printed.
* Misprints: when the printed word is misspelt (a letter missing, doubled, swapped, a wrong dot), copy the misprint.
  Never correct, complete, modernise, translate or summarise. Keep words joined or separated as printed.
* Digits as printed (Arabic-Indic stay Arabic-Indic, Western stay Western); Latin text with its accents; Quran
  quotations with their brackets and marks. No tatweel stretching.
Do not skip any page or any part of a page; the last page matters as much as the first."""

PAGEMAP_WHOLE = "It has {n} page(s); transcribe all of them, document pages 1..{n} (PDF page k = document page k)."
PAGEMAP_PART = ("It is part of a {total}-page article. {ctx}PDF pages {a}..{b} are document pages {first}..{last}: "
                "transcribe exactly those, as sections data-page=\"{first}\" .. data-page=\"{last}\".")
CTX_NOTE = ("PDF page 1 is the article's FIRST page, given for context only (title, authors, journal, heading "
            "style): use it for the metadata, but do NOT write a section for it. ")

STATE = """

The previous part of this article (pages before {first}) has already been transcribed. Keep its conventions:
* outline so far (keep these heading levels for headings that look the same): {outline}
* it ended with this block (if page {first} begins by continuing it, mark that block data-continued="prev"):
  <<<{last}>>>
* footnote ids use the document page number: fn-N-M."""

P2 = """The attached images are sheets of numbered crops cut at full resolution from ONE scanned Arabic journal
page (number in the left margin of each crop). Two OCR readers disagree about the word(s) marked by the red line
under the MIDDLE of each crop; the crop also shows a neighbour word or two so you can find the spot.

These old prints are full of misprints: the printed word is often NOT a real word (a letter missing, doubled or
swapped, a wrong dot). Do not let the meaning guide you. For each question, read the ink shape by shape: count the
teeth and the dots, look for each vowel mark. First spell what the ink shows, letter by letter separated by spaces,
each letter followed by any vowel mark printed on it; then say which reading matches it exactly.
Exactly means: letters and dots as printed (ة vs ه, ي vs ى, hamza forms, joined or separate words), vowel marks only
where printed (a missing or extra fatha/damma/kasra/shadda/sukun/tanween makes a reading wrong), digits as printed.

{questions}

Answer JSON: {{"a": ["1: <letters as spelled> => A", "2: <letters> => B", "3: <letters> => N", "4: => U", ...]}}
one entry per question: A or B = that reading is exactly what is printed; N = neither (your spelling is what is
printed); U = the crop does not show it."""


P2_BLIND = """The attached images are sheets of numbered crops cut at full resolution from ONE scanned Arabic journal
page (number in the left margin of each crop). In each crop a red line is drawn under the word(s) in the middle.

These old prints are full of misprints: the printed word is often NOT a real word (a letter missing, doubled or
swapped, a wrong dot). Do not guess from meaning. For each crop, transcribe ONLY the word(s) above the red line,
exactly as the ink shows them: letter by letter, every dot as printed (ة vs ه, ي vs ى, hamza forms), vowel marks only
where printed, joined or separate words as printed, digits as printed.

{questions}

Answer JSON: {{"a": ["1: <the word(s) exactly as printed>", "2: ...", ...]}}  one entry per crop; write "1: ?" if
the crop does not show the word."""

# ------------------------------------------------------------------------------------------------ documents

def doc_table() -> dict:
    """stem -> {pdf, azure, pages, pids {page: sample pid}}."""
    S = sample()
    out = {}
    for d in S["docs"]:
        out[d["stem"]] = dict(pdf=Path(d["pdf"]), azure=Path(d["azure_json"]), pages=d["pages"], pids={})
    for p in S["pages"]:
        if p["stem"] not in out:
            f = Path(p["source_pdf"])
            import pymupdf
            with pymupdf.open(str(f)) as d:
                n = len(d)
            out[p["stem"]] = dict(pdf=f, azure=f.with_suffix(".json"), pages=n, pids={})
        out[p["stem"]]["pids"][p["page"]] = p["page_id"]
    return out


def pid_of(D: dict, stem: str, k: int) -> str:
    return D["pids"].get(k) or f"{stem}_p{k:03d}"


def plan() -> list[dict]:
    """Units: each a list of chunks run in order (state carried); a chunk = (first, last, context_page1)."""
    T = doc_table()
    units = []
    for stem, D in sorted(T.items()):
        n = D["pages"]
        if n <= WHOLE_MAX:
            units.append(dict(stem=stem, chunks=[(1, n, False)], kind="whole"))
        elif stem in FULL_CHUNKED:
            ch, a = [], 1
            k = -(-n // CHUNK)
            size = -(-n // k)
            while a <= n:
                b = min(n, a + size - 1)
                ch.append((a, b, a > 1))
                a = b + 1
            units.append(dict(stem=stem, chunks=ch, kind="chunked"))
        else:
            for s in sorted(D["pids"]):
                a, b = max(1, s - 1), min(n, s + 1)
                units.append(dict(stem=stem, chunks=[(a, b, a > 1)], kind="window"))
    return units


def chunk_name(stem, a, b):
    return f"{stem}_c{a:03d}-{b:03d}"


def chunk_pdf(stem: str, a: int, b: int, ctx: bool) -> Path:
    D = doc_table()[stem]
    f = ED / "chunks" / f"{chunk_name(stem, a, b)}{'_ctx' if ctx else ''}.pdf"
    if not f.exists():
        import pymupdf
        f.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(D["pdf"])) as d:
            if a == 1 and b == len(d) and not ctx:
                f.write_bytes(Path(D["pdf"]).read_bytes())
                return f
            o = pymupdf.open()
            if ctx:
                o.insert_pdf(d, from_page=0, to_page=0)
            o.insert_pdf(d, from_page=a - 1, to_page=b - 1)
            o.save(str(f), garbage=3, deflate=True)
    return f


def page_image(stem: str, k: int) -> Path:
    D = doc_table()[stem]
    pid = D["pids"].get(k)
    if pid and (PAGES / f"{pid}.jpg").exists():
        return PAGES / f"{pid}.jpg"
    f = ED / "img" / f"{stem}_p{k:03d}.jpg"
    if not f.exists():
        import pymupdf
        f.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(D["pdf"])) as d:
            d[k - 1].get_pixmap(dpi=300, alpha=False).save(str(f), jpg_quality=92)
    return f


_az_cache: dict = {}


def azure_words(stem: str, k: int, W: int, H: int) -> list[dict]:
    """Azure's words of document page k: text, box in the page image's pixels, line index, in Azure's order."""
    f = doc_table()[stem]["azure"]
    if f not in _az_cache:
        a = json.loads(Path(f).read_text(encoding="utf-8"))
        _az_cache[f] = a.get("analyzeResult", a)
    pg = _az_cache[f]["pages"][k - 1]
    sx, sy = W / pg["width"], H / pg["height"]
    spans = []
    for i, ln in enumerate(pg.get("lines", [])):
        for sp in ln.get("spans", []):
            spans.append((sp["offset"], sp["offset"] + sp["length"], i))
    out = []
    for w in pg.get("words", []):
        xs, ys = w["polygon"][0::2], w["polygon"][1::2]
        off = w["span"]["offset"]
        li = next((i for s, e, i in spans if s <= off < e), -1)
        out.append(dict(text=az_norm(w["content"]), box=[min(xs) * sx, min(ys) * sy, max(xs) * sx, max(ys) * sy],
                        line=li))
    return out


# ------------------------------------------------------------------------------------------------ text keys

def az_norm(s: str) -> str:
    s = unicodedata.normalize("NFC", s).replace("ک", "ك")
    return re.sub("ی(?=\\W|$)", "ى", s).replace("ی", "ي")


_DIG = str.maketrans({chr(0x660 + i): str(i) for i in range(10)} | {chr(0x6f0 + i): str(i) for i in range(10)})


def skel(w: str) -> str:
    """Letters only: no vowel marks, tatweel or punctuation; digits folded to one script; Latin lowercased."""
    w = unicodedata.normalize("NFC", w).replace(TATWEEL, "")
    w = HARAKAT.sub("", w)
    w = re.sub(r"[^\w]|_", "", w).translate(_DIG)
    return w.lower()


def marked(w: str) -> str:
    """Letters with their vowel marks (no tatweel, no punctuation), digits folded."""
    w = unicodedata.normalize("NFC", w).replace(TATWEEL, "")
    w = "".join(c for c in w if c.isalnum() or HARAKAT.match(c)).translate(_DIG)
    return w.lower()


def sim(a: str, b: str) -> float:
    return difflib.SequenceMatcher(None, a, b, autojunk=False).ratio() if (a or b) else 1.0


# ------------------------------------------------------------------------------------------------ pass 1

def run_unit(u: dict) -> list[dict]:
    """Run a unit's chunks in order; returns chunk records (cached on disk: a rerun resumes)."""
    stem = u["stem"]
    D = doc_table()[stem]
    recs, prev_meta, prev_last = [], None, None
    rawd = ED / "raw"
    rawd.mkdir(parents=True, exist_ok=True)
    for a, b, ctx in u["chunks"]:
        name = chunk_name(stem, a, b)
        rf, hf = rawd / f"{name}.json", rawd / f"{name}.html"
        if rf.exists() and hf.exists():
            rec = json.loads(rf.read_text())
        else:
            n = b - a + 1
            if a == 1 and b == D["pages"]:
                pm = PAGEMAP_WHOLE.format(n=n)
            else:
                off = 1 if ctx else 0
                pm = PAGEMAP_PART.format(total=D["pages"], ctx=CTX_NOTE if ctx else "", a=1 + off, b=n + off,
                                         first=a, last=b)
            state = ""
            if u["kind"] == "chunked" and prev_meta is not None:
                outline = json.dumps([dict(level=s.get("level"), title=s.get("title"))
                                      for s in (prev_meta.get("sections") or [])][-25:], ensure_ascii=False)
                state = STATE.format(first=a, outline=outline, last=(prev_last or "")[-600:])
            prompt = P1.format(pagemap=pm, state=state)
            pdf = chunk_pdf(stem, a, b, ctx)
            info = {}
            ans, usd = gemini(prompt, pdf=pdf, tag=f"{TAG}_p1_{name}", json_out=False,
                              max_out=min(65000, 4500 * n + 6000), thinking="low", resolution="high",
                              subcap=subcap(), info=info)
            rec = dict(stem=stem, unit=name, first=a, last=b, ctx=ctx, pages=n, usd=usd,
                       **{k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs", "cached", "error")})
            if ans is None:
                rec["failed"] = True
                (rawd / f"{name}.failed.json").write_text(json.dumps(rec, indent=1))
                print(f"  p1 {name}: FAILED {info.get('finish') or info.get('error')}", flush=True)
                return recs
            hf.write_text(strip_fences(ans), encoding="utf-8")
            rf.write_text(json.dumps(rec, indent=1))
            print(f"  p1 {name}: {n} p in {rec['tin']} out {rec['tout']} ${usd:.4f} {rec['secs'] or 0:.0f}s",
                  flush=True)
        recs.append(rec)
        meta, secs = split_answer(hf.read_text(encoding="utf-8"))
        if meta and prev_meta:
            for key in ("sections", "figures", "tables"):
                meta[key] = (prev_meta.get(key) or []) + (meta.get(key) or [])
        prev_meta = meta or prev_meta
        if secs:
            last = re.sub(r"<[^>]+>", " ", secs[max(secs)])
            prev_last = re.sub(r"\s+", " ", last).strip()
    return recs


def unit_pages(u: dict) -> tuple[dict | None, dict[int, str], dict[int, float]]:
    """(metadata, {page: section html}, {page: pass-1 usd share}) from a unit's raw answers."""
    meta, pages, cost = None, {}, {}
    for a, b, ctx in u["chunks"]:
        name = chunk_name(u["stem"], a, b)
        hf, rf = ED / "raw" / f"{name}.html", ED / "raw" / f"{name}.json"
        if not hf.exists():
            continue
        rec = json.loads(rf.read_text())
        m, secs = split_answer(hf.read_text(encoding="utf-8"))
        if m:
            if meta is None:
                meta = m
            else:
                for key in ("sections", "figures", "tables"):
                    meta[key] = (meta.get(key) or []) + (m.get(key) or [])
        keep = {k: s for k, s in secs.items() if a <= k <= b}
        if not keep and secs:          # the model numbered sections 1..n of the PDF: map them back
            ks = sorted(secs)
            off = 1 if ctx else 0
            keep = {a + i: secs[k] for i, k in enumerate(ks[off:]) if a + i <= b}
            keep = {k: re.sub(r'(<section\b[^>]*data-page=")\d+(")', rf"\g<1>{k}\2", s, count=1)
                    for k, s in keep.items()}
        for k, s in keep.items():
            pages[k] = s
            cost[k] = (rec.get("usd") or 0) / max(1, b - a + 1)
    return meta, pages, cost


# ------------------------------------------------------------------------------------------------ pass 2

def _cls(el) -> str:
    return el.get("class") or "" if isinstance(el.tag, str) else ""


def _blocks(el):
    for ch in el:
        if not isinstance(ch.tag, str):
            continue
        if ch.get("data-bbox"):
            yield ch
        else:
            yield from _blocks(ch)


def _tokens(block) -> list[dict]:
    """Word tokens of a block's text nodes, math left out: text, node (element, 'text'|'tail'), start, end."""
    toks = []

    def add(el, which):
        s = getattr(el, which) or ""
        for m in re.finditer(r"\S+", s):
            toks.append(dict(text=m.group(), node=(el, which), start=m.start(), end=m.end()))

    def walk(el):
        if not isinstance(el.tag, str):
            return
        if "math" in _cls(el).split() or el.tag in ("math", "script", "style", "img"):
            return
        add(el, "text")
        for ch in el:
            walk(ch)
            add(ch, "tail")
    walk(block)
    return [t for t in toks if skel(t["text"]) and "\\" not in t["text"] and "$" not in t["text"]]


def _bbox(el, W, H):
    try:
        v = [float(x) for x in re.split(r"[,\s]+", el.get("data-bbox").strip()) if x]
        if len(v) != 4 or v[2] <= v[0] or v[3] <= v[1]:
            return None
        return [v[0] * W / 1000, v[1] * H / 1000, v[2] * W / 1000, v[3] * H / 1000]
    except Exception:
        return None


def disputes_of(sec_el, words: list[dict], W: int, H: int) -> list[dict]:
    """Word disagreements between the edition's blocks and Azure's words inside each block's box."""
    blocks = []
    for bl in _blocks(sec_el):
        bb = _bbox(bl, W, H)
        if bb:
            mx, my = 0.015 * W, 0.012 * H
            blocks.append((bl, [bb[0] - mx, bb[1] - my, bb[2] + mx, bb[3] + my]))
    owner = {}
    for i, w in enumerate(words):
        cx, cy = (w["box"][0] + w["box"][2]) / 2, (w["box"][1] + w["box"][3]) / 2
        best = None
        for j, (_, b) in enumerate(blocks):
            if b[0] <= cx <= b[2] and b[1] <= cy <= b[3]:
                area = (b[2] - b[0]) * (b[3] - b[1])
                if best is None or area < best[0]:
                    best = (area, j)
        if best:
            owner.setdefault(best[1], []).append(i)
    out = []
    for j, (bl, _) in enumerate(blocks):
        toks = _tokens(bl)
        aw = [words[i] for i in owner.get(j, []) if skel(words[i]["text"])]
        if not toks or not aw:
            continue
        gk, ak = [skel(t["text"]) for t in toks], [skel(w["text"]) for w in aw]
        sm = difflib.SequenceMatcher(None, gk, ak, autojunk=False)
        for op, i1, i2, j1, j2 in sm.get_opcodes():
            if op == "equal":
                for d in range(i2 - i1):
                    g, a = toks[i1 + d], aw[j1 + d]
                    if marked(g["text"]) != marked(a["text"]):
                        out.append(dict(kind="marks", g=[i1 + d], a=[a], toks=toks, block=bl))
            elif op == "replace" and (i2 - i1) <= 3 and (j2 - j1) <= 3:
                gs = "".join(gk[i1:i2])
                as_ = "".join(ak[j1:j2])
                if gs == as_:
                    kind = "spacing"
                elif sim(gs, as_) >= 0.5:
                    kind = "letters"
                else:
                    continue
                if len({w["line"] for w in aw[j1:j2]}) > 1:
                    continue                       # the Azure side spans two lines: no single crop shows it
                out.append(dict(kind=kind, g=list(range(i1, i2)), a=aw[j1:j2], toks=toks, block=bl))
    # letters first, then spacing, then marks; cap
    out.sort(key=lambda d: {"letters": 0, "spacing": 1, "marks": 2}[d["kind"]])
    return out[:P2_MAX_Q]


def _crop(img, a_words, W, H):
    import cv2
    x0 = min(w["box"][0] for w in a_words); y0 = min(w["box"][1] for w in a_words)
    x1 = max(w["box"][2] for w in a_words); y1 = max(w["box"][3] for w in a_words)
    h = max(20.0, y1 - y0)
    X0, X1 = int(max(0, x0 - 1.6 * h)), int(min(W, x1 + 1.6 * h))
    Y0, Y1 = int(max(0, y0 - 0.45 * h)), int(min(H, y1 + 0.45 * h))
    c = img[Y0:Y1, X0:X1].copy()
    # a thin mark under the disputed word(s) so the model knows which one is meant
    cv2.line(c, (int(x0 - X0), c.shape[0] - 3), (int(x1 - X0), c.shape[0] - 3), (0, 0, 255), 3)
    s = 120 / max(1, c.shape[0])
    s = min(s, 1300 / max(1, c.shape[1]), 3.0)
    return cv2.resize(c, (max(1, int(c.shape[1] * s)), max(1, int(c.shape[0] * s))), interpolation=cv2.INTER_CUBIC)


def sheets_of(crops: list) -> list[bytes]:
    import cv2
    import numpy as np
    out = []
    for i in range(0, len(crops), 8):
        group = crops[i:i + 8]
        wmax = max(c.shape[1] for c in group) + 90
        rows = []
        for k, c in enumerate(group, i + 1):
            row = np.full((c.shape[0] + 16, wmax, 3), 255, np.uint8)
            row[8:8 + c.shape[0], 90:90 + c.shape[1]] = c
            cv2.putText(row, str(k), (8, row.shape[0] // 2 + 14), cv2.FONT_HERSHEY_SIMPLEX, 1.2, (200, 0, 0), 3)
            cv2.line(row, (0, row.shape[0] - 1), (wmax, row.shape[0] - 1), (180, 180, 180), 1)
            rows.append(row)
        sheet = np.vstack(rows)
        out.append(cv2.imencode(".jpg", sheet, [cv2.IMWRITE_JPEG_QUALITY, 92])[1].tobytes())
    return out


def arbitrate(sec_html: str, img_path: Path, words: list[dict], tag: str, rec_dir: Path) -> tuple[str, dict]:
    """Pass 2 on one page section. Returns (new section html, record)."""
    import cv2
    import lxml.html as LH
    from lxml import etree
    rf = rec_dir / f"{tag.split('_p2_', 1)[-1]}.json"
    wrap = LH.fragment_fromstring(sec_html, create_parent="div")
    sec = wrap.find(".//section")
    sec = sec if sec is not None else wrap
    img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
    H, W = img.shape[:2]
    ds = disputes_of(sec, words, W, H)
    rec = dict(tag=tag, n_disputes=len(ds), usd=0.0, decisions=[])
    if not ds:
        return sec_html, rec
    qs, crops = [], []
    for n, d in enumerate(ds, 1):
        gtxt = " ".join(d["toks"][i]["text"] for i in d["g"])
        atxt = " ".join(w["text"] for w in d["a"])
        flip = int(hashlib.md5(f"{tag}{n}".encode()).hexdigest(), 16) % 2 == 1
        A, B = (atxt, gtxt) if flip else (gtxt, atxt)
        lo, hi = max(0, d["g"][0] - 3), min(len(d["toks"]), d["g"][-1] + 4)
        ctx = " ".join(d["toks"][i]["text"] if i not in d["g"] else "⟦?⟧" for i in range(lo, hi))
        ctx = re.sub(r"(⟦\?⟧ ?)+", "⟦?⟧ ", ctx).strip()
        if P2_MODE == "blind":
            nw = max(len(d["g"]), len(d["a"]))
            qs.append(f"{n}. crop {n}: {nw} word(s) above the line")
        else:
            qs.append(f"{n}. crop {n}: A «{A}»   B «{B}»   context: «{ctx}»")
        d.update(n=n, gtxt=gtxt, atxt=atxt, flip=flip)
        crops.append(_crop(img, d["a"], W, H))
    sheets = sheets_of(crops)
    sd = rec_dir / "sheets"
    sd.mkdir(parents=True, exist_ok=True)
    stem_tag = tag.split("_p2_", 1)[-1]
    for k, s in enumerate(sheets, 1):
        (sd / f"{stem_tag}_s{k}.jpg").write_bytes(s)
    info = {}
    ans, usd = gemini((P2_BLIND if P2_MODE == "blind" else P2).format(questions="\n".join(qs)), images=sheets, tag=tag, json_out=True,
                      max_out=600 + 90 * len(ds), thinking="low", resolution="high", subcap=subcap(), info=info)
    rec.update(usd=usd, tin=info.get("tin"), tout=info.get("tout"), secs=info.get("secs"), sheets=len(sheets))
    if not ans:
        rec["failed"] = True
        return sec_html, rec
    picks = {}
    for s in ans.get("a", []) if isinstance(ans, dict) else []:
        if P2_MODE == "blind":
            m = re.match(r"\s*(\d+)\s*:\s*(.*?)\s*$", str(s), re.S)
            if m:
                t = m.group(2).strip()
                picks[int(m.group(1))] = ("U", "") if t in ("?", "") else ("N", t)
            continue
        m = re.match(r"\s*(\d+)\s*:(.*?)=>\s*([ABNU])\s*$", str(s), re.S)
        if m:
            spelled = re.sub(r"\s+", "", m.group(2))
            picks[int(m.group(1))] = (m.group(3), spelled)
    edits = []                                     # (node, start, end, new text)
    for d in ds:
        p, printed = picks.get(d["n"], ("U", ""))
        # the spelling decides when it matches one reading exactly (the letter-by-letter look is the evidence)
        if printed and marked(printed) == marked(d["atxt"].replace(" ", "")) != marked(d["gtxt"].replace(" ", "")):
            p = "B" if d["flip"] is False else "A"
        elif printed and marked(printed) == marked(d["gtxt"].replace(" ", "")) != marked(d["atxt"].replace(" ", "")):
            p = "A" if d["flip"] is False else "B"
        if P2_MODE == "blind" and p == "N":
            # two of three: Argon's page reading, Azure, and this blind zoomed reading
            from inkscript.gold.text import distance, folded
            key = marked if d["kind"] == "marks" else (lambda x: folded(x).replace(" ", ""))
            pk, gk_, ak_ = key(printed), key(d["gtxt"]), key(d["atxt"])
            if pk == ak_ != gk_:
                p = "B" if d["flip"] is False else "A"
            elif pk == gk_:
                p = "A" if d["flip"] is False else "B"
            elif d["kind"] != "marks" and distance(pk, ak_) < distance(pk, gk_):
                p = "B" if d["flip"] is False else "A"
            else:
                p = "U"                            # nearer Argon, or a tie: keep the edition
        if p in ("A", "B"):
            chosen = "azure" if (p == "A") == d["flip"] else "gemini"
        elif p == "N" and printed and len(d["g"]) == 1 and len(d["a"]) == 1:
            chosen = "printed"
        else:
            chosen = "gemini"
        new = {"azure": d["atxt"], "gemini": d["gtxt"], "printed": printed}[chosen]
        if chosen == "printed" and max(sim(skel(new), skel(d["gtxt"])), sim(skel(new), skel(d["atxt"]))) < 0.6:
            chosen, new = "gemini(rejected-other)", d["gtxt"]
        applied = False
        if not chosen.startswith("gemini") and new != d["gtxt"]:
            ts = [d["toks"][i] for i in d["g"]]
            if all(t["node"] == ts[0]["node"] for t in ts):
                # keep the token's leading/trailing punctuation from the edition (Azure glues it differently)
                orig = getattr(ts[0]["node"][0], ts[0]["node"][1])[ts[0]["start"]:ts[-1]["end"]]
                lead = re.match(r"^[^\w؀-ۿ]*", orig).group()
                trail = re.search(r"[^\w؀-ۿ]*$", orig).group()
                core = re.sub(r"^[^\w؀-ۿ]+|[^\w؀-ۿ]+$", "", new)
                edits.append((ts[0]["node"], ts[0]["start"], ts[-1]["end"], lead + core + trail))
                applied = True
        rec["decisions"].append(dict(n=d["n"], kind=d["kind"], gemini=d["gtxt"], azure=d["atxt"], pick=p,
                                     printed=printed, chosen=chosen, applied=applied))
    by_node: dict = {}
    for node, s, e, t in edits:
        by_node.setdefault((id(node[0]), node[1]), (node, []))[1].append((s, e, t))
    for (_, _), (node, es) in by_node.items():
        el, which = node
        txt = getattr(el, which) or ""
        for s, e, t in sorted(es, reverse=True):
            txt = txt[:s] + t + txt[e:]
        setattr(el, which, txt)
    rec["applied"] = sum(1 for x in rec["decisions"] if x["applied"])
    return unquote_hrefs(etree.tostring(sec, encoding="unicode", method="html")), rec


def unquote_hrefs(h: str) -> str:
    """lxml percent-encodes non-ASCII in href (fn-2-١ -> fn-2-%D9%A1); put the ids back as written."""
    import urllib.parse
    return re.sub(r'href="(#[^"]*)"', lambda m: f'href="{urllib.parse.unquote(m.group(1))}"', h)


# ------------------------------------------------------------------------------------------------ assemble

def figure_crops(sec_html: str, img_path: Path) -> str:
    """Article view only: each <figure data-bbox> gets its picture cropped from the scan."""
    import cv2

    def rep(m):
        b = re.search(r'data-bbox="([^"]+)"', m.group(1))
        if not b:
            return m.group(0)
        try:
            v = [float(x) for x in re.split(r"[,\s]+", b.group(1).strip()) if x]
            img = cv2.imread(str(img_path), cv2.IMREAD_COLOR)
            H, W = img.shape[:2]
            c = img[int(v[1] * H / 1000):int(v[3] * H / 1000), int(v[0] * W / 1000):int(v[2] * W / 1000)]
            if c.size == 0:
                return m.group(0)
            s = min(1.0, 900 / c.shape[1])
            c = cv2.resize(c, (int(c.shape[1] * s), max(1, int(c.shape[0] * s))), interpolation=cv2.INTER_AREA)
            data = base64.b64encode(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 80])[1]).decode()
            return f'{m.group(0)}<img alt="" style="max-width:100%" src="data:image/jpeg;base64,{data}">'
        except Exception:
            return m.group(0)
    return re.sub(r"<figure\b([^>]*)>", rep, sec_html)


def write_doc(d: Path, stem: str, meta, pages: dict[int, str]):
    (d / "docs").mkdir(parents=True, exist_ok=True)
    doc = ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"></head><body>\n'
           f'<script type="application/json" id="article-meta">{json.dumps(meta, ensure_ascii=False)}</script>\n'
           + "\n".join(pages[k] for k in sorted(pages)) + "\n</body></html>\n")
    (d / "docs" / f"{stem}.html").write_text(doc, encoding="utf-8")


def process_unit(u: dict, do_p2: bool = True) -> dict:
    stem = u["stem"]
    T = doc_table()
    D = T[stem]
    recs = run_unit(u)
    meta, pages, cost = unit_pages(u)
    if not pages:
        return dict(stem=stem, failed=True)
    final, p2cost, p2recs = {}, {}, {}
    rec_dir = ED / "arb"
    rec_dir.mkdir(parents=True, exist_ok=True)

    def one(k):
        pid = pid_of(D, stem, k)
        rf = rec_dir / f"{pid}.json"
        hf = rec_dir / f"{pid}.html"
        if rf.exists() and hf.exists():
            return k, hf.read_text(encoding="utf-8"), json.loads(rf.read_text())
        img = page_image(stem, k)
        import cv2
        H, W = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE).shape[:2]
        words = azure_words(stem, k, W, H)
        new, r = arbitrate(pages[k], img, words, f"{TAG}_p2_{pid}", rec_dir)
        if not r.get("failed"):
            hf.write_text(new, encoding="utf-8")
            rf.write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        return k, new, r

    if do_p2:
        with ThreadPoolExecutor(2) as ex:
            for k, new, r in ex.map(one, sorted(pages)):
                final[k], p2cost[k], p2recs[k] = new, r.get("usd", 0.0), r
                if not r.get("cached_note"):
                    print(f"  p2 {pid_of(D, stem, k)}: {r['n_disputes']} questions, {r.get('applied', 0)} changed "
                          f"${r.get('usd', 0):.4f}", flush=True)
    else:
        final = dict(pages)
    # outputs: pass-1-only copy (to measure pass 2) and the final edition
    for d, pg in ((ED / "p1", pages), (ED, final)):
        d.mkdir(parents=True, exist_ok=True)
        write_doc(d, stem, meta, pg)
        for k in pg:
            pid = pid_of(D, stem, k)
            usd = cost.get(k, 0.0) + (p2cost.get(k, 0.0) if d == ED else 0.0)
            (d / f"{pid}.meta.json").write_text(json.dumps(dict(usd=usd, secs=0.0)))
            if k in D["pids"]:
                (d / f"{pid}.html").write_text(pg[k], encoding="utf-8")
    (ED / "meta").mkdir(exist_ok=True)
    (ED / "meta" / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    (ED / "article").mkdir(exist_ok=True)
    art = {k: figure_crops(v, page_image(stem, k)) for k, v in final.items()}
    (ED / "article" / f"{stem}.html").write_text(article_view(meta, art), encoding="utf-8")
    return dict(stem=stem, kind=u["kind"], pages=sorted(pages), p1_usd=sum(r.get("usd") or 0 for r in recs),
                p2_usd=sum(p2cost.values()), p2=p2recs and {k: dict(q=r["n_disputes"], applied=r.get("applied", 0))
                                                           for k, r in p2recs.items()})


# ------------------------------------------------------------------------------------------------ arb on others

def arb_only(src: Path, name: str):
    """Pass 2 on another approach's per-page HTML for the sample pages (out/E_best/<name>/)."""
    T = doc_table()
    od = ED / name
    rec_dir = od / "arb"
    rec_dir.mkdir(parents=True, exist_ok=True)

    def one(p):
        pid, stem, k = p["page_id"], p["stem"], p["page"]
        f = src / f"{pid}.html"
        if not f.exists():
            return pid, None
        if (od / f"{pid}.html").exists():
            return pid, json.loads((rec_dir / f"{pid}.json").read_text())
        h = f.read_text(encoding="utf-8")
        m = re.search(r"<body[^>]*>(.*)</body>", h, re.S | re.I)
        h = m.group(1) if m else h
        if "<section" not in h:
            h = f'<section class="page" data-page="{k}">{h}</section>'
        img = page_image(stem, k)
        import cv2
        H, W = cv2.imread(str(img), cv2.IMREAD_GRAYSCALE).shape[:2]
        new, r = arbitrate(h, img, azure_words(stem, k, W, H), f"{TAG}_{name}_p2_{pid}", rec_dir)
        if r.get("failed"):
            return pid, r
        (rec_dir / f"{pid}.json").write_text(json.dumps(r, ensure_ascii=False, indent=1), encoding="utf-8")
        (od / f"{pid}.html").write_text(new, encoding="utf-8")
        base = json.loads((src / f"{pid}.meta.json").read_text()).get("usd", 0) if (src / f"{pid}.meta.json").exists() else 0
        (od / f"{pid}.meta.json").write_text(json.dumps(dict(usd=base + r.get("usd", 0), secs=0.0)))
        print(f"  {name} {pid}: {r['n_disputes']} q, {r.get('applied', 0)} changed ${r.get('usd', 0):.4f}", flush=True)
        return pid, r
    with ThreadPoolExecutor(4) as ex:
        list(ex.map(one, sample()["pages"]))


# ------------------------------------------------------------------------------------------------ main

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["plan", "run", "arb-only"])
    ap.add_argument("src", nargs="?")
    ap.add_argument("--stems", nargs="*", default=None)
    ap.add_argument("--no-p2", action="store_true")
    ap.add_argument("--name", default="arbA")
    a = ap.parse_args()
    us = plan()
    if a.stems:
        us = [u for u in us if u["stem"] in a.stems]
    print(f"spent so far ${spent():.3f}, E_best ${spent(TAG):.3f}; sub-cap {subcap()}")
    if a.cmd == "plan":
        tot = 0
        for u in us:
            n = sum(b - a_ + 1 for a_, b, _ in u["chunks"])
            tot += n
            print(f"  {u['stem']:24} {u['kind']:8} {u['chunks']}")
        print(f"  {len(us)} units, {tot} pages to transcribe; at ~$0.025/page ~${tot * 0.025:.2f}")
        return
    if a.cmd == "arb-only":
        arb_only(Path(a.src).resolve(), a.name)
        return
    ED.mkdir(parents=True, exist_ok=True)
    res = []
    with ThreadPoolExecutor(2) as ex:      # x2 threads inside pass 2 = at most 4 calls in flight
        for r in ex.map(lambda u: process_unit(u, not a.no_p2), us):
            res.append(r)
    log = ED / "run_log.jsonl"
    with open(log, "a") as f:
        for r in res:
            f.write(json.dumps(dict(r, when=time.strftime("%Y-%m-%d %H:%M:%S")), default=str) + "\n")
    print(f"done: spent ${spent():.3f}, E_best ${spent(TAG):.3f}")


if __name__ == "__main__":
    main()
