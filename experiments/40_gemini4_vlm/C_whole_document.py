"""Experiment 40, approach C: the whole document in one request.

Each document PDF goes to gemini-4-argon in ONE call; the answer is one semantic HTML document:
article metadata (a JSON block before the pages), then one <section class="page" data-page="N"> per page, with
footnotes linked across the document, furniture kept but marked, and blocks cut by a page break marked
data-continues="next" / data-continued="prev" so a flowing "article view" can join them.

Outputs (out/C_whole_document/):
  raw/<variant>/<stem>.html            the answer as received (+ .json: tokens, usd, secs, finish)
  v/<variant>/docs/<stem>.html         the answer cleaned (what score.py reads, cut by page sections)
  v/<variant>/<pid>.html               the sample pages cut out (page ids as in sample.json, bd_ included)
  v/<variant>/<pid>.meta.json          the page's share of its document's cost
  v/<variant>/article/<stem>.html      the flowing article view (furniture out, page breaks joined, metadata head)
  v/<variant>/meta/<stem>.json         the article metadata
The best variant is copied to out/C_whole_document/{docs,article,meta,<pid>.html} for score.py and render.py.

    .venv/bin/python C_whole_document.py run --variant pdf_low --docs 0197-002-001-003
    .venv/bin/python C_whole_document.py pagewise --docs 0197-002-001-003     (the page-by-page control)
    .venv/bin/python C_whole_document.py analyse --variant pdf_low
"""
from __future__ import annotations

import argparse
import json
import re
import shutil
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common import DOCS, OUT, gemini, sample, spent, strip_fences  # noqa: E402

TAG = "C_whole_document"
SUBCAP = (TAG, 3.5)
CD = OUT / "C_whole_document"
SRC = OUT / "src"

PROMPT = """You are given a scanned Arabic journal article: the attached PDF, {n} page(s){excerpt}.
Turn it into ONE semantic HTML document that is a faithful, complete digital edition of the whole article.

Output exactly this, and nothing else (no commentary, no markdown fences):

1. First, the article's metadata as JSON inside
   <script type="application/json" id="article-meta">{{...}}</script>
   with keys: "title", "subtitle", "authors" (list of {{"name", "affiliation", "email"}}), "abstract" (object, one
   entry per language printed, e.g. {{"ar": "...", "en": "..."}}), "keywords" (object per language, lists),
   "journal", "volume", "issue", "year", "pages_printed" (the printed page numbers, e.g. "45-52"), "language",
   "sections" (the outline: list of {{"level": 2, "title": "...", "page": N}}), "figures" (list of
   {{"page": N, "caption": "...", "description": "a short description of what the figure shows"}}),
   "tables" (list of {{"page": N, "caption": "..."}}). Copy values exactly as printed; null when not printed
   (a journal name or year read from a running header counts as printed).

2. Then, for every page k = 1..{n} of the PDF in order, one
   <section class="page" data-page="k"> ... </section>
   holding everything printed on that page, in reading order (right-to-left columns for Arabic: the right column
   first), with these elements:
   - article title: <h1> (the main title only, once in the whole document); main section headings <h2>;
     sub-headings <h3>; give headings that look the same in print the same level throughout the article
   - body paragraph: <p>, one per printed paragraph (not one per line)
   - numbered / bulleted list: <ol>/<ul> with <li>
   - bibliography / references: <ol class="references"> with one <li> per entry
   - footnote: <aside class="footnote" id="fn-P-M">...</aside> where P is the page number k and M the marker as
     printed; the aside starts with its printed marker. In the text, the marker is
     <sup><a href="#fn-P-M">M</a></sup> exactly where printed. Every marker links to its footnote and every footnote
     is linked from its marker; ids are unique in the whole document.
   - verse (a line of poetry printed as two half-lines): <div class="verse"><span class="hemistich">first half</span>
     <span class="hemistich">second half</span></div>, one div per verse line
   - table: <table> with <tr>, <th>/<td>, rowspan/colspan as printed; caption in <caption>
   - equation: inline <span class="math">\\(LaTeX\\)</span>; display
     <div class="equation"><span class="math">\\[LaTeX\\]</span></div>
   - figure / picture / chart: <figure data-bbox="..."><figcaption>printed caption</figcaption></figure>
   - running header, page number, footer: <header class="furniture">...</header> /
     <footer class="furniture">...</footer> inside the page's section (kept, but marked as furniture)
   - anything else: <div class="other">
   Give every block dir="rtl" or dir="ltr" and lang ("ar", "fr", "en"), and data-bbox="x0,y0,x1,y1": the block's
   box on ITS page in 0-1000 coordinates (x from the left edge, y from the top).

3. Page breaks. When a paragraph, list, table, footnote or verse block is cut by a page break, give its last block
   on page k data-continues="next" and its first block on page k+1 data-continued="prev" (do not repeat words; a
   table's repeated header row on the new page is printed text and is kept). A word hyphenated across the break
   stays split as printed.

Text rules: copy exactly what is printed, character for character: every vowel mark (harakat, shadda, tanween)
where printed and none where not printed; hamza forms, ta marbuta / ha, alif maqsura / ya exactly as printed;
digits as printed (Arabic-Indic stay Arabic-Indic, Western stay Western); Latin text with its accents; Quran
quotations with their brackets and vowels. Do not correct, translate, summarise, complete or modernise anything.
Do not skip any page or any part of a page; the last page matters as much as the first."""

PAGE_PROMPT_NOTE = "\n\n(This PDF is ONE page, page {k} of a longer article; emit its section with data-page=\"{k}\" and use P={k} in footnote ids. Emit the metadata block too, with what this page shows.)"

VARIANTS = {
    "pdf_low": dict(input="pdf", thinking="low", resolution="high"),
    "pdf_med": dict(input="pdf", thinking="medium", resolution="high"),
    "img_low": dict(input="img", thinking="low", resolution="high"),
}


# ------------------------------------------------------------------------------------------------ documents

def doc_table() -> dict:
    """stem -> {pdf, pages, pids (sample page ids inside), page (sample page numbers)}."""
    S = sample()
    out = {}
    for d in S["docs"]:
        out[d["stem"]] = dict(pdf=Path(d["pdf"]), pages=d["pages"], pids={})
    for p in S["pages"]:
        f = Path(p["source_pdf"])
        if p["stem"] not in out:
            import pymupdf
            with pymupdf.open(str(f)) as d:
                n = len(d)
            out[p["stem"]] = dict(pdf=f, pages=n, pids={})
        out[p["stem"]]["pids"][p["page"]] = p["page_id"]
    return out


def excerpt_pdf(stem: str, first: int, last: int) -> Path:
    """Pages first..last (1-based) of a long document as their own PDF (for the 'window' runs)."""
    D = doc_table()[stem]
    f = CD / "excerpts" / f"{stem}_p{first:03d}-{last:03d}.pdf"
    if not f.exists():
        import pymupdf
        f.parent.mkdir(parents=True, exist_ok=True)
        with pymupdf.open(str(D["pdf"])) as d:
            o = pymupdf.open()
            o.insert_pdf(d, from_page=first - 1, to_page=last - 1)
            o.save(str(f), garbage=3, deflate=True)
    return f


def page_jpegs(pdf: Path) -> list[bytes]:
    import pymupdf
    out = []
    with pymupdf.open(str(pdf)) as d:
        for pg in d:
            pix = pg.get_pixmap(dpi=200, alpha=False)
            out.append(pix.tobytes("jpeg", jpg_quality=88))
    return out


# ------------------------------------------------------------------------------------------------ one call

def unit_name(stem: str, first: int | None, last: int | None) -> str:
    return stem if first is None else f"{stem}_w{first:03d}-{last:03d}"


def run_one(variant: str, stem: str, first: int | None = None, last: int | None = None, dry=False) -> dict | None:
    """One document (or the window first..last of it) in one call. Returns the run record."""
    V = VARIANTS[variant]
    D = doc_table()[stem]
    name = unit_name(stem, first, last)
    rawd = CD / "raw" / variant
    rawd.mkdir(parents=True, exist_ok=True)
    rec_f = rawd / f"{name}.json"
    if rec_f.exists() and (rawd / f"{name}.html").exists():
        return json.loads(rec_f.read_text())
    if first is None:
        pdf, n, excerpt = D["pdf"], D["pages"], ""
    else:
        pdf, n = excerpt_pdf(stem, first, last), last - first + 1
        excerpt = (f" (an excerpt: printed-PDF pages {first}-{last} of a {D['pages']}-page article; number the "
                   f"sections 1..{n} as they come in this excerpt)")
    prompt = PROMPT.format(n=n, excerpt=excerpt)
    max_out = min(65000, 4500 * n + 6000)
    kw = dict(tag=f"{TAG}_{variant}_{name}", json_out=False, max_out=max_out, thinking=V["thinking"],
              resolution=V["resolution"], subcap=SUBCAP)
    if V["input"] == "pdf":
        kw["pdf"] = pdf
    else:
        kw["images"] = page_jpegs(pdf)
        prompt = prompt.replace("the attached PDF", "the attached page images (Image 1 = page 1, ...)")
    if dry:
        print(f"  dry {name}: {n} pages, max_out {max_out}")
        return None
    info = {}
    ans, usd = gemini(prompt, info=info, **kw)
    rec = dict(variant=variant, stem=stem, unit=name, first=first, last=last, pages=n, usd=usd, **{
        k: info.get(k) for k in ("finish", "tin", "tout", "think", "secs", "cached", "error")})
    if ans is None:
        rec["failed"] = True
        print(f"  {name}: FAILED ({info.get('finish') or info.get('error')}) ${usd:.4f}", flush=True)
        (rawd / f"{name}.failed.json").write_text(json.dumps(rec, indent=1))
        return rec
    (rawd / f"{name}.html").write_text(strip_fences(ans), encoding="utf-8")
    rec_f.write_text(json.dumps(rec, indent=1))
    print(f"  {name}: {n} p, in {rec['tin']} out {rec['tout']} (think {rec['think']}) ${usd:.4f} "
          f"{rec['secs'] or 0:.0f}s {rec['finish']}", flush=True)
    return rec


def run_pagewise(stem: str, k: int) -> dict | None:
    """The control: the same prompt for ONE page (a one-page PDF), thinking low."""
    rawd = CD / "raw" / "pagewise"
    rawd.mkdir(parents=True, exist_ok=True)
    name = f"{stem}_p{k:03d}"
    if (rawd / f"{name}.html").exists():
        return json.loads((rawd / f"{name}.json").read_text())
    pdf = excerpt_pdf(stem, k, k)
    prompt = PROMPT.format(n=1, excerpt="") + PAGE_PROMPT_NOTE.format(k=k)
    info = {}
    ans, usd = gemini(prompt, pdf=pdf, tag=f"{TAG}_pagewise_{name}", json_out=False, max_out=16000,
                      thinking="low", subcap=SUBCAP, info=info)
    rec = dict(variant="pagewise", stem=stem, unit=name, page=k, usd=usd,
               **{x: info.get(x) for x in ("finish", "tin", "tout", "think", "secs")})
    if ans is None:
        print(f"  {name}: FAILED", flush=True)
        return None
    h = strip_fences(ans)
    # the one-page answer numbers its section k already (asked); make sure
    h = re.sub(r'(<section\b[^>]*data-page=")\d+(")', rf"\g<1>{k}\2", h)
    (rawd / f"{name}.html").write_text(h, encoding="utf-8")
    (rawd / f"{name}.json").write_text(json.dumps(rec, indent=1))
    print(f"  {name}: in {rec['tin']} out {rec['tout']} ${usd:.4f}", flush=True)
    return rec


# ------------------------------------------------------------------------------------------------ post-processing

META_RE = re.compile(r'<script[^>]*id="article-meta"[^>]*>(.*?)</script>', re.S | re.I)
SEC_RE = re.compile(r'<section\b[^>]*class="[^"]*\bpage\b[^"]*"[^>]*>', re.I)


def split_answer(h: str) -> tuple[dict | None, dict[int, str]]:
    """(metadata, {page number: section HTML incl. its tags})."""
    meta = None
    m = META_RE.search(h)
    if m:
        try:
            meta = json.loads(m.group(1))
        except Exception:
            meta = {"_unparsed": m.group(1)[:2000]}
    secs = {}
    ms = list(SEC_RE.finditer(h))
    for i, mm in enumerate(ms):
        pm = re.search(r'data-page="(\d+)"', mm.group(0))
        if not pm:
            continue
        end = ms[i + 1].start() if i + 1 < len(ms) else len(h)
        part = h[mm.start():end]
        part = re.sub(r"</article>\s*$|</body>\s*$|</html>\s*$", "", part.strip()).strip()
        secs[int(pm.group(1))] = part
    return meta, secs


def assemble(variant: str, stem: str) -> dict | None:
    """Merge the raw answer(s) of one document (whole, or its windows) into v/<variant>/docs/<stem>.html with the
    PDF's own page numbers, write the sample pages, the metadata and the article view."""
    rawd = CD / "raw" / variant
    vd = CD / "v" / variant
    D = doc_table()[stem]
    pieces = []           # (offset, html, rec)
    whole = rawd / f"{stem}.html"
    if whole.exists():
        pieces.append((0, whole.read_text(encoding="utf-8"), json.loads((rawd / f"{stem}.json").read_text())))
    else:
        for f in sorted(rawd.glob(f"{stem}_w*.html")):
            a = int(re.search(r"_w(\d+)-", f.name).group(1))
            pieces.append((a - 1, f.read_text(encoding="utf-8"), json.loads(f.with_suffix(".json").read_text())))
    if not pieces:
        return None
    meta, pages, usd, npages = None, {}, 0.0, 0
    for off, h, rec in pieces:
        m, secs = split_answer(h)
        meta = meta or m
        usd += rec.get("usd") or 0
        npages += rec["pages"]
        for k, s in secs.items():
            K = k + off
            s = re.sub(r'(<section\b[^>]*data-page=")\d+(")', rf"\g<1>{K}\2", s, count=1)
            if off:      # footnote ids of a window: keep them unique in PDF page numbers
                s = re.sub(r'(id="|href="#)fn-(\d+)-', lambda mo: f"{mo.group(1)}fn-{int(mo.group(2)) + off}-", s)
            pages[K] = s
    for d in ("docs", "meta", "article"):
        (vd / d).mkdir(parents=True, exist_ok=True)
    doc = ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"></head><body>\n'
           f'<script type="application/json" id="article-meta">{json.dumps(meta, ensure_ascii=False)}</script>\n'
           + "\n".join(pages[k] for k in sorted(pages)) + "\n</body></html>\n")
    (vd / "docs" / f"{stem}.html").write_text(doc, encoding="utf-8")
    (vd / "meta" / f"{stem}.json").write_text(json.dumps(meta, ensure_ascii=False, indent=1), encoding="utf-8")
    per_page = usd / max(1, npages)
    for k, pid in D["pids"].items():
        if k in pages:
            (vd / f"{pid}.html").write_text(pages[k], encoding="utf-8")
            (vd / f"{pid}.meta.json").write_text(json.dumps(dict(usd=per_page, secs=0.0)))
    (vd / "article" / f"{stem}.html").write_text(article_view(meta, pages), encoding="utf-8")
    return dict(stem=stem, pages=sorted(pages), usd=usd, per_page=per_page)


def article_view(meta, pages: dict[int, str]) -> str:
    """One flowing article: metadata head, furniture removed, page breaks joined, footnotes kept where printed
    (linked), a small page-number marker at each page start."""
    import lxml.html as LH
    from lxml import etree
    body = []
    for k in sorted(pages):
        try:
            sec = LH.fragment_fromstring(pages[k], create_parent="div")
        except Exception:
            continue
        for el in sec.iter():
            if el.tag in ("header", "footer") and "furniture" in (el.get("class") or ""):
                el.drop_tree()
        inner = sec.find(".//section") if sec.find(".//section") is not None else sec
        blocks = list(inner)
        if not blocks:
            continue
        marker = LH.fragment_fromstring(f'<span class="pb" data-page="{k}">[{k}]</span>')
        if body and blocks and blocks[0].get("data-continued") == "prev":
            prev = body[-1]
            first = blocks.pop(0)
            if prev.tag == first.tag and prev.tag in ("p", "aside", "div"):
                prev.append(marker)
                prev[-1].tail = (first.text or "")
                for ch in list(first):
                    prev.append(ch)
            elif prev.tag == first.tag and prev.tag in ("ol", "ul", "table"):
                for ch in list(first):
                    if ch.tag == "caption":
                        continue
                    prev.append(ch)
            else:
                body.append(marker)
                body.append(first)
        else:
            body.append(marker)
        body.extend(blocks)
    m = meta or {}
    head = ["<header class='meta'><div class='lbl'>metadata (from the model's JSON)</div>"]
    if m.get("title"):
        head.append(f"<div class='title'>{m['title']}</div>")
    if m.get("journal") or m.get("year"):
        head.append(f"<div class='journal'>{m.get('journal') or ''} {m.get('volume') or ''} "
                    f"{m.get('issue') or ''} {m.get('year') or ''}</div>")
    for a in m.get("authors") or []:
        if isinstance(a, dict):
            head.append(f"<div class='author'>{a.get('name') or ''} — <i>{a.get('affiliation') or ''}</i></div>")
    for lang, ab in (m.get("abstract") or {}).items():
        if ab:
            d = "ltr" if lang in ("en", "fr") else "rtl"
            head.append(f"<div class='abs' dir='{d}'><b>abstract ({lang})</b> {ab}</div>")
    if m.get("keywords"):
        head.append(f"<div class='kw'>{json.dumps(m['keywords'], ensure_ascii=False)}</div>")
    head.append("</header>")
    css = ("body{font-family:'Scheherazade New',serif;max-width:46em;margin:2em auto;line-height:1.9;font-size:20px}"
           ".pb{color:#999;font-size:12px;margin:0 .3em}.verse{display:flex;justify-content:space-around}"
           "aside.footnote{font-size:15px;border-top:1px solid #ccc;color:#333}.meta{background:#f4f1ea;padding:1em}"
           ".meta .title{font-size:28px;font-weight:bold}.meta .lbl{font-size:11px;color:#888}.abs{font-size:16px;margin:.5em 0}"
           "table{border-collapse:collapse}td,th{border:1px solid #999;padding:2px 6px}")
    return ("<!doctype html><html lang='ar' dir='rtl'><head><meta charset='utf-8'>"
            "<link href='https://fonts.googleapis.com/css2?family=Scheherazade+New&display=swap' rel='stylesheet'>"
            "<link rel='stylesheet' href='https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.css'>"
            "<script defer src='https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/katex.min.js'></script>"
            "<script defer src='https://cdn.jsdelivr.net/npm/katex@0.16.11/dist/contrib/auto-render.min.js' "
            "onload=\"renderMathInElement(document.body);document.body.dataset.ready='1'\"></script>"
            f"<style>{css}</style></head><body>" + "".join(head) +
            "".join(etree.tostring(b, encoding="unicode", method="html") for b in body) + "</body></html>")


# ------------------------------------------------------------------------------------------------ consistency

END = re.compile(r"[.!?؟:»\"”)\]…]\s*$")


def page_stats(h: str) -> dict:
    """Per page: footnote refs/asides, headings by level, last body block text, continuation marks."""
    import lxml.html as LH
    try:
        sec = LH.fragment_fromstring(h, create_parent="div")
    except Exception:
        return {}
    refs = [a.get("href", "")[1:] for a in sec.iter("a") if (a.get("href") or "").startswith("#")]
    asides = [x.get("id") for x in sec.iter("aside") if "footnote" in (x.get("class") or "")]
    heads = {lv: [re.sub(r"\s+", " ", x.text_content()).strip() for x in sec.iter(lv)] for lv in ("h1", "h2", "h3", "h4")}
    def is_flow(x):
        c = x.get("class") or ""
        if x.tag not in ("p", "li", "div", "td") or _in_furn_or_fn(x) or not x.text_content().strip():
            return False
        return x.tag != "div" or "verse" in c
    flow = [x for x in sec.iter() if is_flow(x)]
    last = re.sub(r"\s+", " ", flow[-1].text_content()).strip() if flow else ""
    last_is_verse = bool(flow) and "verse" in (flow[-1].get("class") or "")
    first = flow[0] if flow else None
    fns = [x for x in sec.iter("aside") if "footnote" in (x.get("class") or "")]
    fn_last = re.sub(r"\s+", " ", fns[-1].text_content()).strip() if fns else ""
    return dict(refs=refs, asides=asides, heads=heads, last_text=last[-60:],
                cut=bool(last) and not last_is_verse and not END.search(last),
                fn_cut=bool(fn_last) and not END.search(fn_last),
                fn_continues=bool(fns) and fns[-1].get("data-continues") == "next",
                continues=any(x.get("data-continues") == "next" for x in sec.iter()),
                continued=first is not None and any(x.get("data-continued") == "prev" for x in sec.iter()))


def _in_furn_or_fn(x) -> bool:
    while x is not None:
        c = x.get("class") or ""
        if "furniture" in c or "footnote" in c or x.tag in ("header", "footer", "figcaption", "caption"):
            return True
        x = x.getparent()
    return False


def consistency(pages: dict[int, str]) -> dict:
    st = {k: page_stats(v) for k, v in pages.items()}
    allrefs = [(k, r) for k, s in st.items() for r in s.get("refs", [])]
    ids = [a for s in st.values() for a in s.get("asides", []) if a]
    idset = set(ids)
    linked = sum(1 for _, r in allrefs if r in idset)
    referenced = sum(1 for a in idset if any(r == a for _, r in allrefs))
    ks = sorted(st)
    bounds = [(a, b) for a, b in zip(ks, ks[1:]) if b == a + 1]
    cut = [(a, b) for a, b in bounds if st[a].get("cut")]
    joined = [(a, b) for a, b in bounds if st[a].get("continues") and st[b].get("continued")]
    joined_cut = [(a, b) for a, b in cut if (a, b) in joined]
    fn_cut = [(a, b) for a, b in bounds if st[a].get("fn_cut")]
    fn_joined = [(a, b) for a, b in fn_cut if st[a].get("fn_continues")]
    h1 = sum(len(s.get("heads", {}).get("h1", [])) for s in st.values())
    pages_first_head_h1 = sum(1 for k in ks[1:] if st[k].get("heads", {}).get("h1"))
    return dict(pages=len(ks), footnote_refs=len(allrefs), footnotes=len(ids), duplicate_footnote_ids=len(ids) - len(idset),
                refs_linked=linked, footnotes_referenced=referenced, boundaries=len(bounds),
                boundaries_cut_midsentence=len(cut), boundaries_joined=len(joined),
                cut_boundaries_joined=len(joined_cut), footnote_cut_boundaries=len(fn_cut),
                footnote_cut_joined=len(fn_joined), h1_count=h1, later_pages_with_h1=pages_first_head_h1,
                heading_seq=[(k, lv, t[:40]) for k in ks for lv in ("h1", "h2", "h3", "h4")
                             for t in st[k].get("heads", {}).get(lv, [])],
                headings={lv: sum(len(s.get("heads", {}).get(lv, [])) for s in st.values()) for lv in ("h1", "h2", "h3", "h4")})


# ------------------------------------------------------------------------------------------------ main

def plan_units(stems, window_long: int = 12):
    """Whole documents up to `window_long` pages; longer ones as a window around their sample page(s)."""
    T = doc_table()
    out = []
    for s in stems:
        D = T[s]
        if D["pages"] <= window_long:
            out.append((s, None, None))
        else:
            for k in sorted(D["pids"]):
                a, b = (k, k + 1) if k < D["pages"] else (k - 1, k)   # the sample page and its neighbour
                out.append((s, a, b))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["run", "pagewise", "assemble", "analyse", "promote", "plan"])
    ap.add_argument("--variant", default="pdf_low")
    ap.add_argument("--docs", nargs="*", default=None, help="stems (default: every sample document)")
    ap.add_argument("--threads", type=int, default=3)
    ap.add_argument("--dry", action="store_true")
    a = ap.parse_args()
    T = doc_table()
    stems = a.docs or list(T)
    if a.cmd == "plan":
        for s, f, l in plan_units(stems):
            n = T[s]["pages"] if f is None else l - f + 1
            print(s, "whole" if f is None else f"window {f}-{l}", n, "pages")
        return
    if a.cmd == "run":
        units = plan_units(stems)
        print(f"{len(units)} calls, {sum(T[s]['pages'] if f is None else l - f + 1 for s, f, l in units)} pages; "
              f"{TAG} spent so far ${spent(TAG):.3f}")
        with ThreadPoolExecutor(min(4, a.threads)) as ex:
            list(ex.map(lambda u: run_one(a.variant, *u, dry=a.dry), units))
        for s in stems:
            assemble(a.variant, s)
        print(f"{TAG} spent ${spent(TAG):.3f}")
    elif a.cmd == "pagewise":
        jobs = [(s, k) for s in stems for k in range(1, T[s]["pages"] + 1)]
        with ThreadPoolExecutor(min(4, a.threads)) as ex:
            list(ex.map(lambda j: run_pagewise(*j), jobs))
        vd = CD / "v" / "pagewise"
        (vd / "docs").mkdir(parents=True, exist_ok=True)
        for s in stems:
            parts = []
            for k in range(1, T[s]["pages"] + 1):
                f = CD / "raw" / "pagewise" / f"{s}_p{k:03d}.html"
                if f.exists():
                    _, secs = split_answer(f.read_text(encoding="utf-8"))
                    if secs:
                        parts.append(next(iter(secs.values())))
                        pid = T[s]["pids"].get(k)
                        if pid:
                            (vd / f"{pid}.html").write_text(parts[-1], encoding="utf-8")
            (vd / "docs" / f"{s}.html").write_text("<html><body>\n" + "\n".join(parts) + "\n</body></html>",
                                                   encoding="utf-8")
        print(f"{TAG} spent ${spent(TAG):.3f}")
    elif a.cmd == "assemble":
        for s in stems:
            print(assemble(a.variant, s))
    elif a.cmd == "analyse":
        vd = CD / "v" / a.variant
        res = {}
        for f in sorted((vd / "docs").glob("*.html")):
            _, secs = split_answer(f.read_text(encoding="utf-8"))
            res[f.stem] = consistency(secs)
        (vd / "consistency.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
        for k, v in res.items():
            print(k, v)
    elif a.cmd == "promote":
        vd = CD / "v" / a.variant
        for f in vd.rglob("*"):
            if f.is_file():
                t = CD / f.relative_to(vd)
                t.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, t)
        (CD / "BEST_VARIANT").write_text(a.variant + "\n")


if __name__ == "__main__":
    main()
