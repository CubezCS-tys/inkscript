"""Experiment 41: a local reader for Argon's 55 articles (no Gemini calls; local rendering only).

Rebuilds each article from Argon's saved answers (out/argon/raw/, through structure.assemble, so the text, fixes, flags
and blocks are exactly the experiment's) and writes a reading edition:

  out/reader/index.html            the library: every article with title, authors, journal, year, pages, decade,
                                   a thumbnail of its first page; grouped by decade, journal or not; sortable; search
  out/reader/<stem>.html           the article: header from the metadata (title, subtitle, authors + affiliations,
                                   abstracts, keywords, journal / volume / year), then the flowing text: running heads
                                   and page numbers out, paragraphs joined across page breaks with a [p. k] marker in
                                   the margin, headings at their levels, verse in two half-lines, tables, equations
                                   (KaTeX), figures cropped from the 300 dpi scans with their captions, footnotes as
                                   calls that pop the note and jump to it and back, D30 misprint flags (wavy underline,
                                   proposed correction on hover / tap), Gemini's fixes of Azure's misreadings behind a
                                   toggle, data-added text marked. "Scan" puts the page scans beside the text (pointing
                                   at a block outlines it on the scan).
  out/reader/scans/<stem>/pNNN.jpg 1200 px JPEGs of the pages (grey when the page has no colour)
  out/reader/figs/<stem>/pNNN-k.jpg figure crops (from out/pages/, the 300 dpi renders; regenerated from the PDF if absent)
  out/reader/thumbs/<stem>.jpg     240 px first-page thumbnails

    /home/yassine/inkscript/.venv/bin/python reader.py [--stems ...] [--force-images]

Browser libraries: Scheherazade New (Google Fonts), KaTeX 0.16.9 (cdnjs). Nothing is inlined but the text.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import sys
import tempfile
from collections import Counter
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import structure as ST  # noqa: E402
from structure import OUT, is_rtl, page_image, sample  # noqa: E402

RUN = "argon"
READER = OUT / "reader"
SCAN_W, SCAN_Q, THUMB_W, FIG_MAXW = 1200, 62, 240, 1400
KATEX = "https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9"
FONTS = "https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=swap"

# ------------------------------------------------------------------------------------------------ text with marks

FO, FC = "", ""          # fix open (followed by its index char) / fix close
PH0, PH1 = "", ""        # placeholder brackets (index char between)
IDX = 0xE200                         # index chars live in the private-use area: no model string can match them


def _strip_fix(t: str) -> str:
    return re.sub(f"{FO}.|{FC}", "", t)


def _rep(t: str, s: str, ph: str) -> tuple[str, bool]:
    """Replace the first s in t with ph; if a fix mark sits inside s, drop the line's fix marks and try again."""
    if s in t:
        return t.replace(s, ph, 1), True
    t2 = _strip_fix(t)
    if s in t2:
        return t2.replace(s, ph, 1), True
    return t, False


def text_html(self, lid, calls=(), source="model"):
    """structure.Store.text_html, plus Gemini's applied fixes as span.fix (Azure's reading kept in data-azure)."""
    _LAST[0] = self
    L = self.lines[lid]
    t = L["text"]
    if not calls:
        calls = VERSE_CALLS.get(lid, []) or VERSE_CALLS.get(L.get("split_of") or "\0", [])
    if not hasattr(self, "_fx"):
        self._fx = {}
        for f in self.applied:
            self._fx.setdefault(f["at"], []).append(f)
    fixes = []
    for f in self._fx.get(lid, []):
        to = f.get("to") or ""
        if to and to in t:
            k = len(fixes)
            t, _ = _rep(t, to, FO + chr(IDX + k) + to + FC)
            fixes.append(f)
    reps, k = {}, 0

    def ph():
        nonlocal k
        k += 1
        return PH0 + chr(IDX + 1000 + k) + PH1
    for m in self.math.get(lid, []):
        p = ph()
        t, ok = _rep(t, m["from"], p)
        if ok:
            reps[p] = f'<span class="math">\\({html.escape(m["latex"])}\\)</span>'
    for s in self.sic.get(lid, []):
        p = ph()
        t, ok = _rep(t, s["text"], p)
        if ok:
            reps[p] = (f'<span class="sic" tabindex="0" data-corr="{html.escape(s["corr"])}" '
                       f'data-why="{html.escape(s.get("why") or "")}">{html.escape(s["text"])}</span>')
    for c in calls:
        mk = c.get("marker")
        if not mk:
            continue
        p = ph()
        t, ok = _rep(t, mk, p)
        if ok:
            fid = ST.fn_norm(c.get("fn"))
            reps[p] = (f'<sup class="call"><a href="#n-{html.escape(fid)}" data-fn="{html.escape(fid)}">'
                       f'{html.escape(mk)}</a></sup>')
            c["_placed"] = True
    t = html.escape(t)
    for p, r in reps.items():
        t = t.replace(p, r)

    def fopen(m):
        f = fixes[ord(m.group(1)) - IDX]
        return (f'<span class="fix" tabindex="0" data-azure="{html.escape(f.get("from") or "")}" '
                f'data-why="{html.escape(f.get("why") or "")}">')
    t = re.sub(f"{FO}(.)", fopen, t)
    return t.replace(FC, "</span>")


ST.Store.text_html = text_html
_LAST = [None]
VERSE_CALLS = {}        # structure.assemble does not pass a verse block's calls to its half-lines: placed here


def verse_calls(a: dict) -> dict:
    out = {}
    for x, y in ST.chunks(a):
        rf = OUT / RUN / "raw" / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if not rf.exists():
            continue
        for pg in (ST.jl(rf).get("answer") or {}).get("pages") or []:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                if isinstance(b, dict) and b.get("type") == "verse":
                    for c in b.get("calls") or []:
                        if isinstance(c, dict):
                            out.setdefault(str(c.get("line")), []).append(dict(c))
    return out


def capture(a: dict) -> dict | None:
    """Run structure.assemble on Argon's saved answers, keeping its blocks and metadata; nothing written to out/argon."""
    cap = {}
    VERSE_CALLS.clear()
    VERSE_CALLS.update(verse_calls(a))
    real_out, real_raw, real_view = ST.OUT, ST.raw_file, ST.article_view
    with tempfile.TemporaryDirectory() as td:
        ST.OUT = Path(td)
        ST.raw_file = lambda run, stem, x, y: real_out / run / "raw" / f"{stem}_c{x:03d}-{y:03d}.json"
        ST.article_view = lambda meta, blocks, pages: cap.update(meta=meta, blocks=blocks, pages=pages) or ""
        try:
            book = ST.assemble(RUN, a)
        finally:
            ST.OUT, ST.raw_file, ST.article_view = real_out, real_raw, real_view
    if not book:
        return None
    cap["book"] = book
    cap["S"] = _LAST[0]
    return cap


# ------------------------------------------------------------------------------------------------ images

def _jpeg(img, path: Path, q: int):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes())


def _resize_w(img, w):
    h0, w0 = img.shape[:2]
    if w0 <= w:
        return img
    return cv2.resize(img, (w, int(round(h0 * w / w0))), interpolation=cv2.INTER_AREA)


def _colourless(img) -> bool:
    small = _resize_w(img, 400)
    return float(np.percentile(cv2.cvtColor(small, cv2.COLOR_BGR2HSV)[..., 1], 99)) < 30


_imgs = {}


def page_img(a, p):
    key = (a["stem"], p)
    if key not in _imgs:
        _imgs.clear()
        _imgs[key] = cv2.imread(str(page_image(a, p)), cv2.IMREAD_COLOR)
    return _imgs[key]


def make_scan(a, p, force=False) -> str:
    rel = f"scans/{a['stem']}/p{p:03d}.jpg"
    f = READER / rel
    if force or not f.exists():
        img = _resize_w(page_img(a, p), SCAN_W)
        _jpeg(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY) if _colourless(img) else img, f, SCAN_Q)
    return rel


def make_thumb(a, force=False) -> str:
    rel = f"thumbs/{a['stem']}.jpg"
    f = READER / rel
    if force or not f.exists():
        _jpeg(_resize_w(page_img(a, a["first"]), THUMB_W), f, 70)
    return rel


def make_fig(a, p, k, box, force=False) -> str | None:
    """Crop a figure from the 300 dpi page; box in 0-1000 page coordinates, padded a little (Gemini's boxes are loose
    or tight by a few per mille)."""
    rel = f"figs/{a['stem']}/p{p:03d}-{k}.jpg"
    f = READER / rel
    if force or not f.exists():
        img = page_img(a, p)
        if img is None:
            return None
        H, W = img.shape[:2]
        x0, y0, x1, y1 = box
        pad = 4
        x0, x1 = sorted((max(0, x0 - pad), min(1000, x1 + pad)))
        y0, y1 = sorted((max(0, y0 - pad), min(1000, y1 + pad)))
        crop = img[int(y0 * H / 1000):int(y1 * H / 1000), int(x0 * W / 1000):int(x1 * W / 1000)]
        if crop.size == 0 or crop.shape[0] < 8 or crop.shape[1] < 8:
            return None
        crop = _resize_w(crop, FIG_MAXW)
        _jpeg(cv2.cvtColor(crop, cv2.COLOR_BGR2GRAY) if _colourless(crop) else crop, f, 80)
    return rel


# ------------------------------------------------------------------------------------------------ article

E = html.escape
TAG_RE = re.compile(r"<(\w+)([^>]*)>(.*)</\1>\s*$", re.S)
JOIN = {"paragraph", "quote", "list_item", "reference", "abstract", "caption", "keywords"}
LISTS = {"list_item", "reference"}


def plain(h: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", "", h or ""))).strip()


def nows(s):
    return re.sub(r"\s+", "", s or "")


def num_ar(s: str) -> str:
    return str(s).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789"))


def split_tag(h: str):
    h = re.sub(r' data-lines="[^"]*"', "", h)
    m = TAG_RE.match(h.strip())
    if not m:
        return None, "", h
    return m.group(1), m.group(2), m.group(3)


def seg_attrs(rec, S) -> str:
    """data-page, data-bbox (the block's box on its page) and data-lb (each of its lines' boxes, 0-1000) so the scan
    pane can outline exactly the lines (a block's union box spans both columns when it turns a column)."""
    m = re.search(r' data-bbox="[^"]*"', rec.get("html") or "")
    lb = [S.lines[i]["b"] for i in rec.get("ids") or [] if S is not None and S.lines[i]["page"] == rec["page"]]
    if rec.get("fig_box"):
        lb = [rec["fig_box"]]
    lbs = ";".join(",".join(str(round(v)) for v in b) for b in lb)
    return f' data-seg data-page="{rec["page"]}"' + (m.group(0) if m else "") + (f' data-lb="{lbs}"' if lbs else "")


AR_CH = re.compile(r"[\u0600-\u06ff\u0750-\u077f\ufb50-\ufdff\ufe70-\ufeff]")
LA_CH = re.compile(r"[A-Za-z\u00c0-\u024f]")


def redir(attrs: str, inner: str) -> str:
    """A block with Arabic and Latin words that structure.py called ltr (more Latin letters, e.g. a heading
    "4. النتائج والمناقشة results and discussion") reads right to left when a third of its letters are Arabic."""
    if ' dir="ltr"' not in attrs:
        return attrs
    t = plain(inner)
    ar, la = len(AR_CH.findall(t)), len(LA_CH.findall(t))
    if ar and ar >= 0.3 * (ar + la):
        attrs = attrs.replace(' dir="ltr"', ' dir="rtl"')
        attrs = re.sub(r' lang="\w+"', ' lang="ar"', attrs)
    return attrs


def meta_texts(meta) -> dict:
    """Plain strings of the metadata fields that the header shows (used to avoid printing them twice)."""
    m = meta or {}
    ab = m.get("abstract") if isinstance(m.get("abstract"), dict) else {}
    kw = m.get("keywords")
    kws = []
    if isinstance(kw, dict):
        for v in kw.values():
            kws += v if isinstance(v, list) else [v]
    elif isinstance(kw, list):
        kws = kw
    elif isinstance(kw, str):
        kws = [kw]
    return dict(title=m.get("title") or "", authors=bool(m.get("authors")),
                abstracts=[nows(v) for v in ab.values() if isinstance(v, str) and v.strip()],
                keywords=[nows(x)[:20] for x in kws if isinstance(x, str) and x.strip()])


def suppressed(rec, mt, first_page) -> bool:
    T = rec["type"]
    t = nows(plain(rec.get("html")))
    if not t:
        return False
    if T == "title" and mt["title"]:
        return t in nows(mt["title"]) or nows(mt["title"]) in t or rec["page"] == first_page
    if T == "byline" and mt["authors"]:
        return rec["page"] == first_page
    if T == "abstract" and mt["abstracts"]:
        return any(t[:60] in a or a[:60] in t for a in mt["abstracts"])
    if T == "keywords" and mt["keywords"]:
        return any(k in t for k in mt["keywords"])
    return False


def lang_dir(meta, blocks) -> tuple[str, str]:
    lg = (meta or {}).get("language") or ""
    if lg in ("fr", "en"):
        return lg, "ltr"
    if lg == "ar":
        return "ar", "rtl"
    r = sum(1 for b in blocks if ' dir="rtl"' in (b.get("html") or ""))
    return ("ar", "rtl") if r >= len(blocks) / 2 else ("en", "ltr")


L10N = {
    "ar": dict(notes="الحواشي", abstract="الملخص", keywords="الكلمات المفتاحية", library="المكتبة", page="ص"),
    "fr": dict(notes="Notes", abstract="Résumé", keywords="Mots-clés", library="Bibliothèque", page="p."),
    "en": dict(notes="Notes", abstract="Abstract", keywords="Keywords", library="Library", page="p."),
}
AB_LABEL = {"ar": "الملخص", "en": "Abstract", "fr": "Résumé"}


def build_header(meta, a, lang, info) -> str:
    m = meta or {}
    lz = L10N.get(lang, L10N["en"])
    kick = []
    journal = m.get("journal") or a.get("journal")
    if journal:
        kick.append(f'<span class="journal">{E(journal)}</span>')
    vi = " · ".join(x for x in [f'{m["volume"]}' if m.get("volume") else "", f'{m["issue"]}' if m.get("issue") else ""]
                    if x)
    if vi:
        kick.append(f"<span>{E(vi)}</span>")
    yr = m.get("year") or a.get("year")
    if yr:
        kick.append(f"<span>{E(str(yr))}</span>")
    if m.get("pages_printed"):
        kick.append(f'<span>{E(lz["page"])} {E(str(m["pages_printed"]))}</span>')
    out = ['<header class="art-head">', f'<p class="kicker">{" <i>·</i> ".join(kick)}</p>' if kick else ""]
    title = m.get("title") or info.get("title") or a["stem"]
    out.append(f'<h1 dir="auto">{E(title)}</h1>')
    if m.get("subtitle"):
        out.append(f'<p class="subtitle" dir="auto">{E(m["subtitle"])}</p>')
    aus = m.get("authors") or []
    if aus:
        out.append('<ul class="authors">')
        for au in aus:
            if isinstance(au, dict):
                nm = au.get("name") or ""
                af = au.get("affiliation") or ""
                em = au.get("email") or ""
                out.append(f'<li><span class="au-name" dir="auto">{E(nm)}</span>'
                           + (f'<span class="au-aff" dir="auto">{E(af)}</span>' if af else "")
                           + (f'<span class="au-mail" dir="ltr">{E(em)}</span>' if em else "") + "</li>")
            elif isinstance(au, str):
                out.append(f'<li><span class="au-name" dir="auto">{E(au)}</span></li>')
        out.append("</ul>")
    ab = m.get("abstract") if isinstance(m.get("abstract"), dict) else {}
    kw = m.get("keywords")
    kwd = kw if isinstance(kw, dict) else ({lang: kw} if kw else {})
    langs = [k for k in list(ab) + [k for k in kwd if k not in ab]]
    for lg in langs:
        txt = ab.get(lg) if isinstance(ab.get(lg), str) else ""
        k = kwd.get(lg)
        if isinstance(k, list):
            k = "، ".join(x for x in k if isinstance(x, str)) if lg == "ar" else ", ".join(x for x in k if isinstance(x, str))
        if not (txt and txt.strip()) and not k:
            continue
        d = "rtl" if lg == "ar" else "ltr"
        lab = AB_LABEL.get(lg, "Abstract")
        klab = L10N.get(lg, L10N["en"])["keywords"]
        out.append(f'<section class="abstract" dir="{d}" lang="{E(lg)}">'
                   + (f'<h2>{E(lab)}</h2><p>{E(txt)}</p>' if txt and txt.strip() else "")
                   + (f'<p class="kw"><b>{E(klab)}:</b> {E(k)}</p>' if k else "") + "</section>")
    out.append(f'<p class="provenance" dir="ltr">{info["prov"]}</p>')
    out.append("</header>")
    return "\n".join(x for x in out if x)


def build_article(a: dict, cap: dict, force=False) -> dict:
    meta, blocks, pages, book = cap["meta"], cap["blocks"], cap["pages"], cap["book"]
    stem = a["stem"]
    lang, ddir = lang_dir(meta, blocks)
    lz = L10N.get(lang, L10N["en"])
    mt = meta_texts(meta)
    first = pages[0]

    items = []          # dict(type, page, tag, attrs, parts[list of html], after[list], marker_before)
    notes = []          # dict(page, fn_id, marker, parts)
    pending = []        # pages whose marker is still to be placed
    seen_page = set()
    fig_k = {}
    missing_figs = []
    title_guess = ""

    def marker(p, inline=False):
        cls = "pm in" if inline else "pm"
        return f'<a class="{cls}" href="#pg-{p}" id="pg-{p}" data-p="{p}">{E(lz["page"])}&#8239;{p}</a>'

    for rec in blocks:
        T, p = rec["type"], rec["page"]
        if p not in seen_page:
            seen_page.add(p)
            pending.append(p)
        if T in ("header", "footer"):
            continue
        if T in ("title", "heading") and not title_guess:
            title_guess = plain(rec["html"])
        if T == "footnote":
            tag, at, inner = split_tag(rec["html"])
            if rec["continued"] and notes:
                notes[-1]["parts"].append(f'<span class="brk" title="{E(lz["page"])} {p}"></span>{inner}')
            else:
                notes.append(dict(page=p, fn_id=rec.get("fn_id") or f"fn-{p}-{len(notes)}", marker=rec.get("marker"),
                                  parts=[inner], dir="rtl" if ' dir="rtl"' in at else "ltr"))
            continue
        if suppressed(rec, mt, first):
            continue
        sa = seg_attrs(rec, cap.get("S"))
        tag, at, inner = split_tag(rec["html"])
        if T == "figure":
            box = rec.get("fig_box")
            fig_k[p] = fig_k.get(p, 0) + 1
            src = make_fig(a, p, fig_k[p], box, force) if box else None
            desc = rec.get("description") or ""
            inner_cap = inner if rec["ids"] else ""
            if src:
                body = f'<img src="{src}" alt="{E(desc)}" title="{E(desc)}" loading="lazy">'
            else:
                missing_figs.append(dict(page=p, description=desc))
                body = f'<div class="fig-missing">[{E(desc) or "figure"}]</div>'
            items.append(dict(type=T, page=p, html=None, fig=body, caption=[inner_cap] if inner_cap else [],
                              sa=sa, markers=pending))
            pending = []
            continue
        joined = False
        if rec["continued"] and T in JOIN:
            # the last item of the same type, skipping figures / captions / tables placed between (top of the new page)
            j = len(items) - 1
            while j >= 0 and items[j]["type"] in ("figure", "table", "other") and items[j]["page"] == p:
                j -= 1
            if j >= 0 and items[j]["type"] == T and items[j].get("tag"):
                mk = "".join(marker(q, True) for q in pending)
                items[j]["parts"].append(f'<span class="brk"></span>{mk}<span{sa}>{inner}</span>')
                items[j]["after"] += [h for h in rec.get("missed_html", [])]
                pending = []
                joined = True
        if joined:
            continue
        if tag in ("table", "div") or T in ("table", "verse", "equation"):
            h = re.sub(r"^<(\w+)", lambda m: f"<{m.group(1)}{sa}", re.sub(r' data-lines="[^"]*"', "", rec["html"]), 1)
            if T == "table":
                td = re.search(r' dir="(\w+)"', h)
                h = f'<div class="tablewrap" dir="{td.group(1) if td else ddir}">{h}</div>'
            items.append(dict(type=T, page=p, html=h, markers=pending, after=list(rec.get("missed_html", []))))
        else:
            if T == "title":            # a title that is not the article's (a section title on a later page)
                tag = "h2"
            at = redir(re.sub(r' data-bbox="[^"]*"', "", at), inner)
            items.append(dict(type=T, page=p, tag=tag, attrs=at + sa, parts=[inner], markers=pending,
                              after=list(rec.get("missed_html", []))))
        pending = []

    # captions next to a figure on the same page become its figcaption
    out_items = []
    for i, it in enumerate(items):
        if it["type"] == "caption" and it.get("tag"):
            nxt = items[i + 1] if i + 1 < len(items) else None
            prv = out_items[-1] if out_items else None
            if prv and prv["type"] == "figure" and prv["page"] == it["page"] and not prv.get("cap_from_next"):
                prv["caption"].append("".join(it["parts"]))
                prv["markers"] += it["markers"]
                continue
            if nxt and nxt["type"] == "figure" and nxt["page"] == it["page"]:
                nxt["caption"].insert(0, "".join(it["parts"]))
                nxt["markers"] = it["markers"] + nxt["markers"]
                nxt["cap_from_next"] = True
                continue
        out_items.append(it)
    items = out_items

    # render
    body, open_list = [], None
    for it in items:
        want = ("references" if it["type"] == "reference" else "list") if it["type"] in LISTS else None
        mk = "".join(f'<div class="pbreak">{marker(q)}</div>' for q in it["markers"])
        if want != open_list:
            if open_list:
                body.append("</ol>")
            if want:
                body.append(f'<ol class="{want}">')
            open_list = want
        if want:            # markers inside the li (an ol holds only li)
            body.append(f'<li{it["attrs"]}>{mk}{" ".join(it["parts"])}</li>')
        elif it["type"] == "figure":
            cap = " ".join(it["caption"])
            body.append(mk + f'<figure class="fig"{it["sa"]}>{it["fig"]}'
                        + (f'<figcaption dir="auto">{cap}</figcaption>' if cap else "") + "</figure>")
        elif it.get("html"):
            body.append(mk + it["html"])
        else:
            cls = ""
            if it["type"] == "other":
                cls = ' class="other"'
            body.append(mk + f'<{it["tag"]}{cls if "class=" not in it["attrs"] else ""}{it["attrs"]}>'
                        + " ".join(it["parts"]) + f'</{it["tag"]}>')
        for h in it.get("after", []):
            body.append(re.sub(r"^<p ", '<p class="added" ', h))
    if open_list:
        body.append("</ol>")
    for q in pending:
        body.append(f'<div class="pbreak">{marker(q)}</div>')

    # footnote calls: one id per first call, so a note can jump back
    called = set()

    def call_id(m):
        fid = m.group(1)
        if fid in called:
            return m.group(0)
        called.add(fid)
        return m.group(0) + f' id="c-{fid}"'
    body_html = re.sub(r'<a href="#n-([^"]+)" data-fn="[^"]+"', call_id, "\n".join(body))
    note_html = []
    if notes:
        note_html.append(f'<section class="notes" id="notes"><h2>{E(lz["notes"])}</h2>')
        byp = {}
        for n in notes:
            byp.setdefault(n["page"], []).append(n)
        for p, ns in byp.items():
            note_html.append(f'<h3><a class="pm-link" href="#pg-{p}" data-p="{p}">{E(lz["page"])}&#8239;{p}</a></h3><ol>')
            for n in ns:
                fid = E(n["fn_id"])
                back = (f' <a class="back" href="#c-{fid}" aria-label="back">&#8617;</a>' if n["fn_id"] in called else "")
                mk = n["marker"] or ""
                starts = num_ar(plain(n["parts"][0]))[:len(mk) + 2].lstrip("( ").startswith(num_ar(mk)) if mk else True
                note_html.append(f'<li id="n-{fid}" dir="{n["dir"]}">'
                                 + ("" if starts else f'<span class="nmk">{E(mk)}</span> ') +
                                 f'{" ".join(n["parts"])}{back}</li>')
            note_html.append("</ol>")
        note_html.append("</section>")

    sic_n = len(book.get("sic") or [])
    fix_n = body_html.count('class="fix"')
    added_n = body_html.count('class="added"')
    kind = (f'pages {first}–{pages[-1]} of {a.get("pages_total")} (a window of a long article)'
            if a.get("kind") == "window" else f'{len(pages)} pages')
    prov = (f'{kind} · text: Azure · structure: Gemini 4 Argon (exp 41) · '
            f'<button class="linkish" data-toggle="fixes">{fix_n} fixes of Azure</button> · '
            f'{sic_n} suspected misprints flagged' + (f' · {added_n} added lines' if added_n else ""))
    info = dict(title=title_guess, prov=prov)
    header = build_header(meta, a, lang, info)
    title = (meta or {}).get("title") or title_guess or stem

    scans = [make_scan(a, p, force) for p in pages]
    page_data = json.dumps(dict(stem=stem, pages=pages, scans=scans, lang=lang))
    page = PAGE.format(lang=E(lang), dir=ddir, title=E(title), title_short=E(title[:90]), katex=KATEX,
                       fonts=FONTS, css=CSS, header=header, body=body_html, notes="\n".join(note_html),
                       data=page_data, js=ARTICLE_JS, library=E(lz["library"]))
    (READER / f"{stem}.html").write_text(page, encoding="utf-8")

    m = meta or {}
    aus = [au.get("name") if isinstance(au, dict) else au for au in (m.get("authors") or [])]
    types = book.get("types") or {}
    lc = Counter(lg for b in blocks if b["type"] not in ("header", "footer")
                 for lg in re.findall(r' lang="(\w+)"', b.get("html") or "")[:1])
    blangs = {lg for lg, n in lc.items() if n >= max(2, 0.05 * sum(lc.values()))}
    return dict(stem=stem, title=title, subtitle=m.get("subtitle") or "", authors=[x for x in aus if x],
                journal=m.get("journal") or a.get("journal") or "", year=num_ar(a.get("year") or m.get("year") or ""),
                decade=a.get("decade") or "", pages=len(pages), pages_total=a.get("pages_total"), kind=a.get("kind"),
                first=first, last=pages[-1], dir=ddir, lang=lang, thumb=make_thumb(a, force),
                verse=types.get("verse", 0), equations=types.get("equation", 0), tables=types.get("table", 0),
                figures=types.get("figure", 0), footnotes=types.get("footnote", 0), fixes=fix_n, sic=sic_n,
                langs=sorted(blangs), missing_figs=missing_figs)


# ------------------------------------------------------------------------------------------------ templates

CSS = r"""
:root{--bg:#f6f2e9;--paper:#fffdf7;--ink:#211d17;--muted:#71685b;--faint:#a89f90;--rule:#e4dccb;--accent:#8e3b22;
--chip:#efe8da;--fix:#dcebfb;--fixline:#2c6cb0;--sic:#c2621b;--added:#fdf0c4;--addedline:#a67c00;--box:#d0461d;
--pane:#ebe5d8;--shadow:0 1px 2px rgba(60,40,10,.06),0 8px 28px rgba(60,40,10,.08);
--ui:system-ui,-apple-system,"Segoe UI",Roboto,sans-serif;--text:"Scheherazade New","Amiri","Noto Naskh Arabic",serif}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#13110e;--paper:#1a1814;--ink:#ebe4d6;
--muted:#a89e8d;--faint:#7a7264;--rule:#332e27;--accent:#e39472;--chip:#2a2620;--fix:#1d3550;--fixline:#86b8ee;
--sic:#eaa060;--added:#3a3115;--addedline:#d8b24d;--box:#ff7a4d;--pane:#0f0e0b;--shadow:0 1px 2px rgba(0,0,0,.3)}}
:root[data-theme="dark"]{--bg:#13110e;--paper:#1a1814;--ink:#ebe4d6;--muted:#a89e8d;--faint:#7a7264;--rule:#332e27;
--accent:#e39472;--chip:#2a2620;--fix:#1d3550;--fixline:#86b8ee;--sic:#eaa060;--added:#3a3115;--addedline:#d8b24d;
--box:#ff7a4d;--pane:#0f0e0b;--shadow:0 1px 2px rgba(0,0,0,.3)}
*{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--ink);font-family:var(--text);font-size:21px;line-height:1.85;
overflow-x:hidden}
a{color:var(--accent)}
.bar{position:sticky;top:0;z-index:20;display:flex;align-items:center;gap:10px;height:48px;padding:0 16px;
background:color-mix(in srgb,var(--bg) 88%,transparent);backdrop-filter:blur(8px);border-bottom:1px solid var(--rule);
font:14px/1 var(--ui)}
.bar .home{text-decoration:none;color:var(--muted);white-space:nowrap}
.bar .t{flex:1;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--muted);
font-family:var(--text);font-size:16px}
.bar button,.tool{font:13px/1 var(--ui);color:var(--ink);background:var(--chip);border:1px solid var(--rule);
border-radius:999px;padding:7px 12px;cursor:pointer;white-space:nowrap}
.bar button[aria-pressed="true"]{background:var(--ink);color:var(--bg);border-color:var(--ink)}
.layout{display:grid;grid-template-columns:minmax(0,1fr)}
.sheet{position:relative;max-width:46rem;width:100%;margin:0 auto;padding:28px 16px 96px}
@media (min-width:900px){.sheet{padding-inline-start:4.6rem;padding-inline-end:2rem;max-width:52rem}}
.art-head{margin-bottom:2.2em;padding-bottom:1.4em;border-bottom:1px solid var(--rule)}
.kicker{font:13px/1.6 var(--ui);color:var(--muted);margin:0 0 .6em;letter-spacing:.01em}
.kicker .journal{color:var(--accent);font-weight:600}
.kicker i{font-style:normal;color:var(--faint);padding:0 .25em}
h1{font-size:2em;line-height:1.35;margin:.1em 0 .25em;font-weight:700;text-wrap:balance}
.subtitle{font-size:1.2em;color:var(--muted);margin:0 0 .6em}
.authors{list-style:none;padding:0;margin:.8em 0;display:flex;flex-wrap:wrap;gap:.4em 2em}
.authors li{display:flex;flex-direction:column;line-height:1.45}
.au-name{font-weight:700}.au-aff{font-size:.8em;color:var(--muted);max-width:34em}
.au-mail{font:12px var(--ui);color:var(--muted)}
.abstract{background:var(--paper);border:1px solid var(--rule);border-radius:10px;padding:.7em 1.1em;margin:1em 0;
font-size:.92em}
.abstract h2{font:600 12px/1 var(--ui);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:.6em 0 .2em}
.abstract p{margin:.3em 0;text-align:justify}
.abstract .kw{font-size:.95em;color:var(--muted)}.abstract .kw b{color:var(--ink);font-weight:700}
.provenance{font:12px/1.6 var(--ui);color:var(--faint);margin:1em 0 0}
html[dir="rtl"] .provenance{text-align:right}
.linkish{all:unset;cursor:pointer;color:var(--muted);text-decoration:underline dotted;text-underline-offset:3px}
h2,h3,h4,h5,h6{line-height:1.45;margin:1.4em 0 .4em;font-weight:700;text-wrap:balance}
h2{font-size:1.38em}h3{font-size:1.18em}h4{font-size:1.05em}h5,h6{font-size:1em}
p{margin:0 0 .75em;text-align:justify;text-justify:inter-word;hyphens:auto}
.text [dir="ltr"],.notes [dir="ltr"],.abstract[dir="ltr"]{font-size:.93em;line-height:1.7}
p.byline{color:var(--muted);text-align:start}
p.keywords{color:var(--muted)}
p.abstract{background:var(--paper);border-inline-start:3px solid var(--rule);padding:.4em .9em}
p.caption,figcaption{font-size:.85em;color:var(--muted);text-align:center;line-height:1.6}
blockquote{margin:.6em 1.6em;color:var(--ink);border-inline-start:2px solid var(--rule);padding-inline-start:1em}
div.other{font-size:.85em;color:var(--muted)}
ol.list,ol.references{list-style:none;padding:0;margin:0 0 .8em}
ol.list li{margin:0 0 .35em;padding-inline-start:1.2em;text-indent:-1.2em}
ol.references{font-size:.88em;line-height:1.65}ol.references li{margin:0 0 .45em;padding-inline-start:1.6em;text-indent:-1.6em}
.verse{display:grid;grid-template-columns:1fr 1fr;gap:0 2.4em;margin:.1em auto;max-width:40em}
.verse .hemistich{text-align:center;text-align-last:center}
.verse.free{display:block;text-align:center}
@media (max-width:560px){.verse{grid-template-columns:1fr;gap:0}.verse .hemistich{text-align:start}
.verse .hemistich+.hemistich{text-align:end}}
.verse+.verse{margin-top:0}
@media (max-width:560px){.verse{margin-bottom:.55em}}
.tablewrap{overflow-x:auto;margin:1em 0;-webkit-overflow-scrolling:touch}
table{border-collapse:collapse;font-size:.8em;line-height:1.5;margin:0 auto}
td,th{border:1px solid var(--rule);padding:4px 9px;vertical-align:top}
th{background:var(--chip);font-weight:700}
tr:nth-child(even) td{background:color-mix(in srgb,var(--paper) 60%,transparent)}
.equation{direction:ltr;text-align:center;margin:.8em 0;overflow-x:auto;overflow-y:hidden}
.katex{font-size:1.02em}.katex-display{margin:.3em 0}
.fig{margin:1.4em 0;text-align:center}
.fig img{max-width:100%;max-height:75vh;width:auto;height:auto;border-radius:4px;box-shadow:var(--shadow);background:#fff}
:root[data-theme="dark"] .fig img{filter:brightness(.9)}
.fig-missing{font:13px var(--ui);color:var(--faint);border:1px dashed var(--rule);padding:1em}
sup.call{line-height:0;font-size:.62em;font-family:var(--ui);font-weight:600}
sup.call a{text-decoration:none;padding:0 .15em;border-radius:3px}
sup.call a:hover,sup.call a:focus{background:var(--chip)}
.sic{text-decoration:underline wavy var(--sic);text-decoration-thickness:1px;text-underline-offset:5px;cursor:help}
body.fixes .fix{background:var(--fix);box-shadow:inset 0 -2px 0 var(--fixline);border-radius:2px;cursor:help}
p.added,.added{background:var(--added);border-inline-start:3px solid var(--addedline);padding:.2em .8em;border-radius:3px}
p.added::before{content:"added";font:600 10px/1 var(--ui);letter-spacing:.06em;text-transform:uppercase;
color:var(--addedline);margin-inline-end:.6em;vertical-align:middle}
.brk{display:inline-block;width:1px;height:.9em;background:var(--faint);opacity:.6;margin:0 .3em;vertical-align:middle}
.pm{font:600 11px/1 var(--ui);color:var(--faint);text-decoration:none;white-space:nowrap;
unicode-bidi:isolate}
.pm:hover{color:var(--accent)}
.pbreak{position:relative;height:0}
@media (min-width:900px){
.pbreak .pm{position:absolute;inset-inline-start:-3.9rem;top:.75em}
.pm.in{position:absolute;inset-inline-start:.7rem;margin-top:.7em}}
@media (max-width:899.98px){
.pbreak{height:auto;display:flex;align-items:center;gap:.6em;margin:.6em 0}
.pbreak::before,.pbreak::after{content:"";flex:1;border-top:1px solid var(--rule)}
.pm.in{display:inline-block;background:var(--chip);border-radius:999px;padding:3px 6px;margin:0 .2em;vertical-align:middle}}
li .pbreak{margin-inline-start:-1.2em}
.notes{margin-top:3em;padding-top:1em;border-top:1px solid var(--rule);font-size:.86em;line-height:1.7}
.notes>h2{font:600 13px/1 var(--ui);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);margin:0 0 1em}
.notes h3{font:600 11px/1 var(--ui);margin:1.4em 0 .4em}
.notes h3 a{color:var(--faint);text-decoration:none}
.notes ol{list-style:none;padding:0;margin:0}
.notes li{margin:0 0 .45em;padding:.15em .4em;border-radius:5px}
.notes li:target{background:var(--added)}
.nmk{font:600 .78em var(--ui);color:var(--accent);margin-inline-end:.25em}
.back{text-decoration:none;font-family:var(--ui);font-size:.85em;padding:0 .3em}
:target{scroll-margin-top:80px}
.pop{position:fixed;z-index:50;max-width:min(26rem,calc(100vw - 32px));background:var(--paper);color:var(--ink);
border:1px solid var(--rule);border-radius:10px;box-shadow:0 10px 40px rgba(0,0,0,.18);padding:.7em .95em;
font-size:17px;line-height:1.7;display:none}
.pop.on{display:block}
.pop .lab{font:600 10px/1.4 var(--ui);letter-spacing:.07em;text-transform:uppercase;color:var(--muted);display:block}
.pop .val{font-size:1.1em}
.pop .why{font:12px/1.5 var(--ui);color:var(--muted);display:block;margin-top:.3em}
.pop a.go{font:12px var(--ui);display:inline-block;margin-top:.4em}
.scanpane{display:none}
body.scan .scanpane{display:flex;flex-direction:column;background:var(--pane);border-inline-start:1px solid var(--rule)}
.scanhead{display:flex;align-items:center;gap:8px;padding:8px 12px;font:13px var(--ui);color:var(--muted);
border-bottom:1px solid var(--rule)}
.scanhead .lab{flex:1}
.scanhead button{font:13px var(--ui);background:var(--chip);color:var(--ink);border:1px solid var(--rule);border-radius:6px;
padding:4px 10px;cursor:pointer}
.scanbody{flex:1;overflow:auto;padding:10px}
.scanwrap{position:relative;margin:0 auto;max-width:100%}
.scanwrap img{display:block;width:100%;height:auto;background:#fff;box-shadow:var(--shadow)}
.hboxes{position:absolute;inset:0;pointer-events:none}
.hboxes div{position:absolute;border:1.5px solid var(--box);background:color-mix(in srgb,var(--box) 12%,transparent);
border-radius:2px}
[data-seg].hot{background:color-mix(in srgb,var(--box) 7%,transparent);border-radius:3px}
@media (min-width:1000px){body.scan .layout{grid-template-columns:minmax(0,1fr) minmax(0,47vw)}
body.scan .scanpane{position:sticky;top:48px;height:calc(100vh - 48px)}
body.scan .sheet{max-width:46rem}}
@media (max-width:999.98px){body.scan .scanpane{position:fixed;inset:auto 0 0 0;height:48vh;z-index:15;
box-shadow:0 -6px 24px rgba(0,0,0,.15);border-top:1px solid var(--rule)}
body.scan .sheet{padding-bottom:52vh}}
@media (max-width:600px){body{font-size:19px}h1{font-size:1.6em}.bar{gap:6px}.bar button{padding:6px 9px}
.bar .t{display:none}}
"""

PAGE = """<!doctype html>
<html lang="{lang}" dir="{dir}"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title_short}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<link rel="stylesheet" href="{katex}/katex.min.css">
<style>{css}</style></head>
<body>
<nav class="bar" dir="ltr"><a class="home" href="index.html">&larr; {library}</a><span class="t" dir="auto">{title_short}</span>
<button type="button" data-toggle="scan" aria-pressed="false" title="Scans beside the text (s)">Scan</button>
<button type="button" data-toggle="fixes" aria-pressed="false" title="Highlight Gemini's fixes of Azure's misreadings (f)">Fixes</button>
<button type="button" id="theme" title="Light / dark">Auto</button></nav>
<div class="layout">
<main class="sheet">
{header}
<article class="text">
{body}
</article>
{notes}
</main>
<aside class="scanpane" dir="ltr"><div class="scanhead"><button type="button" data-step="-1">&lsaquo;</button>
<span class="lab"></span><button type="button" data-step="1">&rsaquo;</button></div>
<div class="scanbody"><div class="scanwrap"><img alt="scan"><div class="hboxes"></div></div></div></aside>
</div>
<div class="pop" role="tooltip"></div>
<script src="{katex}/katex.min.js"></script>
<script>const DOC={data};</script>
<script>{js}</script>
</body></html>
"""

COMMON_JS = r"""
const root=document.documentElement;const themeBtn=document.getElementById('theme');
function store(k,v){try{if(v===undefined)return localStorage.getItem(k);localStorage.setItem(k,v)}catch(e){return null}}
function setTheme(t){if(t==='auto')root.removeAttribute('data-theme');else root.setAttribute('data-theme',t);
 if(themeBtn)themeBtn.textContent=t==='auto'?'Auto':t==='dark'?'Dark':'Light';store('reader-theme',t)}
setTheme(store('reader-theme')||'auto');
if(themeBtn)themeBtn.onclick=()=>{const c=store('reader-theme')||'auto';setTheme(c==='auto'?'light':c==='light'?'dark':'auto')};
"""

ARTICLE_JS = COMMON_JS + r"""
const body=document.body;
document.querySelectorAll('.math').forEach(el=>{let s=el.textContent.trim(),d=false;
 if(s.startsWith('\\[')){d=true;s=s.slice(2,-2)}else if(s.startsWith('\\(')){s=s.slice(2,-2)}
 try{katex.render(s,el,{displayMode:d,throwOnError:false,strict:'ignore'})}catch(e){}});
function setToggle(name,on){body.classList.toggle(name,on);
 document.querySelectorAll('.bar [data-toggle="'+name+'"]').forEach(b=>b.setAttribute('aria-pressed',on));
 store('reader-'+name,on?'1':'0');if(name==='scan'&&on)follow(true)}
document.querySelectorAll('[data-toggle]').forEach(b=>b.addEventListener('click',()=>{
 const n=b.dataset.toggle;setToggle(n,!body.classList.contains(n))}));
// scans
const pane=document.querySelector('.scanpane'),img=pane.querySelector('img'),hbox=pane.querySelector('.hboxes'),
 lab=pane.querySelector('.lab');let cur=null;
function show(p,bbox){const i=DOC.pages.indexOf(p);if(i<0)return;
 if(p!==cur){cur=p;img.src=DOC.scans[i];lab.textContent='page '+p+'  ('+(i+1)+' / '+DOC.pages.length+')';
  pane.querySelector('.scanbody').scrollTop=0}
 hbox.innerHTML='';
 if(bbox){const bs=bbox.split(';').map(x=>x.split(',').map(Number));let top=1000;
  for(const b of bs){const d=document.createElement('div');Object.assign(d.style,{left:b[0]/10+'%',top:b[1]/10+'%',
   width:(b[2]-b[0])/10+'%',height:(b[3]-b[1])/10+'%'});hbox.appendChild(d);top=Math.min(top,b[1])}
  const sb=pane.querySelector('.scanbody'),y=top/1000*img.clientHeight;
  if(y<sb.scrollTop||y>sb.scrollTop+sb.clientHeight-60)sb.scrollTop=Math.max(0,y-60)}}
pane.querySelectorAll('[data-step]').forEach(b=>b.onclick=()=>{const i=DOC.pages.indexOf(cur)+ +b.dataset.step;
 if(i>=0&&i<DOC.pages.length)show(DOC.pages[i])});
const marks=[...document.querySelectorAll('.text .pm')];
function follow(force){if(!body.classList.contains('scan'))return;let p=DOC.pages[0];
 const lim=innerHeight*0.38;for(const m of marks){if(m.getBoundingClientRect().top<lim)p=+m.dataset.p;else break}
 if(force||p!==cur)show(p)}
let tick=false;addEventListener('scroll',()=>{if(!tick){tick=true;requestAnimationFrame(()=>{tick=false;follow()})}},{passive:true});
let hot=null;
function point(el){if(hot)hot.classList.remove('hot');hot=el;if(!el)return;
 if(body.classList.contains('scan')){el.classList.add('hot');show(+el.dataset.page,el.dataset.lb||el.dataset.bbox)}}
document.querySelector('.text').addEventListener('mouseover',e=>{const s=e.target.closest('[data-seg]');if(s!==hot)point(s)});
document.querySelector('.text').addEventListener('mouseleave',()=>{point(null);hbox.innerHTML=''});
document.querySelectorAll('.pm,.pm-link').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();
 if(!body.classList.contains('scan'))setToggle('scan',true);show(+a.dataset.p)}));
// popovers: misprint flags, fixes (when shown), footnote calls
const pop=document.querySelector('.pop');let popFor=null,hideT=null;
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function popHtml(el){
 if(el.classList.contains('sic'))return '<span class="lab">'+(DOC.lang==='ar'?'كذا في الأصل · as printed':'as printed')+
  '</span><span class="val">'+esc(el.textContent)+'</span><span class="lab" style="margin-top:.4em">'+
  (DOC.lang==='ar'?'لعل الصواب · probably':'probably')+'</span><span class="val">'+esc(el.dataset.corr)+'</span>'+
  (el.dataset.why?'<span class="why">'+esc(el.dataset.why)+'</span>':'');
 if(el.classList.contains('fix'))return '<span class="lab">Azure read</span><span class="val">'+esc(el.dataset.azure)+
  '</span><span class="lab" style="margin-top:.4em">Gemini (on the scan)</span><span class="val">'+esc(el.textContent)+
  '</span>'+(el.dataset.why?'<span class="why">'+esc(el.dataset.why)+'</span>':'');
 const n=document.getElementById('n-'+el.dataset.fn);
 if(n){const c=n.cloneNode(true);c.querySelectorAll('.back').forEach(x=>x.remove());
  return '<div dir="'+n.dir+'">'+c.innerHTML+'</div><a class="go" href="#n-'+esc(el.dataset.fn)+'">&darr; note</a>'}
 return null}
function openPop(el){const h=popHtml(el);if(!h)return;clearTimeout(hideT);popFor=el;pop.innerHTML=h;pop.classList.add('on');
 const r=el.getBoundingClientRect(),pw=pop.offsetWidth,ph=pop.offsetHeight;
 let x=Math.min(Math.max(16,r.left+r.width/2-pw/2),innerWidth-pw-16),y=r.bottom+8;
 if(y+ph>innerHeight-8)y=Math.max(8,r.top-ph-8);pop.style.left=x+'px';pop.style.top=y+'px'}
function closePop(){pop.classList.remove('on');popFor=null}
function target(e){const t=e.target.closest('.sic,sup.call a'+(body.classList.contains('fixes')?',.fix':''));return t}
document.addEventListener('click',e=>{if(e.target.closest('.pop'))return;const t=target(e);
 if(t){if(t.matches('sup.call a'))e.preventDefault();if(popFor===t)closePop();else openPop(t)}else closePop()});
if(matchMedia('(hover:hover)').matches){
 document.addEventListener('mouseover',e=>{const t=target(e);if(t&&t!==popFor)openPop(t);
  else if(!t&&!e.target.closest('.pop')&&popFor){clearTimeout(hideT);hideT=setTimeout(closePop,350)}});
 pop.addEventListener('mouseenter',()=>clearTimeout(hideT))}
addEventListener('keydown',e=>{if(e.target.closest('input,textarea')||e.metaKey||e.ctrlKey||e.altKey)return;
 if(e.key==='s')setToggle('scan',!body.classList.contains('scan'));
 if(e.key==='f')setToggle('fixes',!body.classList.contains('fixes'));if(e.key==='Escape')closePop()});
addEventListener('scroll',()=>{if(popFor)closePop()},{passive:true});
setToggle('fixes',store('reader-fixes')==='1');setToggle('scan',store('reader-scan')==='1'&&innerWidth>=1000);
"""

INDEX = """<!doctype html>
<html lang="en" dir="ltr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Experiment 41 library</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<style>{css}
.lib{{max-width:76rem;margin:0 auto;padding:28px 16px 80px}}
.lib h1{{font:700 28px/1.2 var(--ui);margin:.2em 0 .2em}}
.lede{{font:15px/1.6 var(--ui);color:var(--muted);max-width:52rem;margin:0 0 1.4em}}
.controls{{display:flex;flex-wrap:wrap;gap:8px;align-items:center;font:13px var(--ui);margin-bottom:1.2em}}
.controls label{{color:var(--muted)}}
.controls select,.controls input{{font:14px var(--ui);background:var(--paper);color:var(--ink);border:1px solid var(--rule);
border-radius:8px;padding:7px 10px}}
.controls input{{flex:1;min-width:12rem}}
.group h2{{font:600 13px/1 var(--ui);letter-spacing:.08em;text-transform:uppercase;color:var(--accent);
margin:2em 0 .8em;display:flex;gap:.6em;align-items:baseline}}
.group h2 span{{color:var(--faint);font-weight:500;letter-spacing:0;text-transform:none}}
.grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,21rem),1fr));gap:14px}}
.card{{display:flex;gap:14px;background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:12px;
text-decoration:none;color:var(--ink);box-shadow:var(--shadow);transition:transform .12s,border-color .12s}}
.card:hover{{transform:translateY(-2px);border-color:var(--accent)}}
.card img{{width:84px;height:118px;object-fit:cover;object-position:top;border-radius:4px;flex:none;background:#fff;
border:1px solid var(--rule)}}
.card .meta{{min-width:0;flex:1;display:flex;flex-direction:column;gap:3px}}
.card .ti{{font-family:var(--text);font-size:19px;line-height:1.45;font-weight:700;display:-webkit-box;
-webkit-line-clamp:3;-webkit-box-orient:vertical;overflow:hidden}}
.card .au{{font-family:var(--text);font-size:15px;color:var(--muted);line-height:1.4;white-space:nowrap;overflow:hidden;
text-overflow:ellipsis}}
.card .jr{{font:12px/1.5 var(--ui);color:var(--muted)}}
.card .jr .st{{white-space:nowrap}}
.card .jr b{{font-weight:600;color:var(--ink)}}
.chips{{display:flex;flex-wrap:wrap;gap:4px;margin-top:auto;padding-top:4px}}
.chips span{{direction:ltr;unicode-bidi:isolate;font:11px/1 var(--ui);background:var(--chip);color:var(--muted);border-radius:999px;padding:4px 7px}}
.chips span.hi{{color:var(--accent)}}
.foot{{font:12px/1.6 var(--ui);color:var(--faint);margin-top:3em}}
</style></head><body>
<nav class="bar"><span class="home">inkscript · experiment 41</span><span class="t"></span>
<button type="button" id="theme">Auto</button></nav>
<main class="lib">
<h1>The 55 articles, as Argon rebuilt them</h1>
<p class="lede">Azure's text, Gemini 4 Argon's structure ({npages} pages, 1932–2025). Each article opens as a reading
edition; its <b>Scan</b> button puts the page scans beside the text, <b>Fixes</b> shows where Gemini corrected Azure,
and a wavy underline marks a suspected misprint in the print itself (kept as printed).</p>
<div class="controls"><label for="grp">Group</label><select id="grp"><option value="decade">by decade</option>
<option value="journal">by journal</option><option value="none">none</option></select>
<label for="srt">Sort</label><select id="srt"><option value="year">year</option><option value="pages">pages</option>
<option value="title">title</option></select>
<input id="q" type="search" placeholder="search title, author, journal…" dir="auto"></div>
<div id="out"></div>
<noscript>{noscript}</noscript>
<p class="foot">Generated by experiments/41_azure_structure/reader.py from out/argon/raw/ (no model calls).</p>
</main>
<script>const ARTS={data};</script>
<script>{common}
const out=document.getElementById('out'),grp=document.getElementById('grp'),srt=document.getElementById('srt'),
 q=document.getElementById('q');
function esc(s){{return String(s??'').replace(/[&<>"]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}}[c]))}}
function card(a){{const ch=[];
 ch.push('<span>'+(a.kind==='window'?'pp. '+a.first+'–'+a.last+' of '+a.pages_total:a.pages+' pp.')+'</span>');
 if(a.verse)ch.push('<span class="hi">verse</span>');if(a.equations)ch.push('<span class="hi">equations '+a.equations+'</span>');
 if(a.tables)ch.push('<span>tables '+a.tables+'</span>');if(a.figures)ch.push('<span>figures '+a.figures+'</span>');
 if(a.footnotes)ch.push('<span>notes '+a.footnotes+'</span>');
 a.langs.filter(l=>l!=='ar').forEach(l=>ch.push('<span class="hi">'+esc(l)+'</span>'));
 if(a.fixes)ch.push('<span>fixes '+a.fixes+'</span>');if(a.sic)ch.push('<span>flags '+a.sic+'</span>');
 return '<a class="card" dir="'+a.dir+'" href="'+esc(a.stem)+'.html"><img src="'+esc(a.thumb)+'" alt="" loading="lazy"><div class="meta">'+
  '<div class="ti" dir="'+a.dir+'">'+esc(a.title)+'</div>'+(a.authors.length?'<div class="au" dir="auto">'+esc(a.authors.join(' · '))+'</div>':'')+
  '<div class="jr"><b dir="auto">'+esc(a.journal)+'</b> '+esc(a.year)+' · <span class="st" dir="ltr">'+esc(a.stem)+'</span></div>'+
  '<div class="chips">'+ch.join('')+'</div></div></a>'}}
function render(){{const s=q.value.trim().toLowerCase();let xs=ARTS.filter(a=>!s||[a.title,a.subtitle,a.journal,a.stem,
 a.year,...a.authors].join(' ').toLowerCase().includes(s));
 const k=srt.value;xs.sort((a,b)=>k==='pages'?b.pages-a.pages:k==='title'?a.title.localeCompare(b.title,'ar'):
  (a.year||'9999').localeCompare(b.year||'9999'));
 const g=grp.value,groups=new Map();
 for(const a of xs){{const key=g==='decade'?(a.decade||'unknown'):g==='journal'?(a.journal||'—'):'';
  if(!groups.has(key))groups.set(key,[]);groups.get(key).push(a)}}
 let keys=[...groups.keys()];if(g==='decade')keys.sort((a,b)=>(a.startsWith('pre')?'0':a).localeCompare(b.startsWith('pre')?'0':b));else if(g==='journal')keys.sort((a,b)=>groups.get(b).length-groups.get(a).length||a.localeCompare(b,'ar'));
 out.innerHTML=keys.map(key=>'<section class="group">'+(key?'<h2><bdi>'+esc(key)+'</bdi><span>'+groups.get(key).length+'</span></h2>':'')+
  '<div class="grid">'+groups.get(key).map(card).join('')+'</div></section>').join('')||'<p class="lede">nothing matches</p>';
 store('reader-lib',JSON.stringify({{g:grp.value,k:srt.value}}))}}
try{{const p=JSON.parse(store('reader-lib')||'{{}}');if(p.g)grp.value=p.g;if(p.k)srt.value=p.k}}catch(e){{}}
[grp,srt].forEach(x=>x.onchange=render);q.oninput=render;render();
</script></body></html>
"""


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--force-images", action="store_true")
    args = ap.parse_args()
    READER.mkdir(parents=True, exist_ok=True)
    arts = sample()
    lib_f = READER / "library.json"
    lib = {x["stem"]: x for x in json.loads(lib_f.read_text())} if lib_f.exists() else {}
    for a in arts:
        if args.stems and a["stem"] not in args.stems:
            continue
        cap = capture(a)
        if cap is None:
            print(f"  {a['stem']}: no answers", flush=True)
            continue
        info = build_article(a, cap, args.force_images)
        lib[a["stem"]] = info
        print(f"  {a['stem']:24} p{info['pages']:>2} fixes {info['fixes']:>3} flags {info['sic']:>3} figs "
              f"{info['figures']}" + (f" MISSING {len(info['missing_figs'])}" if info["missing_figs"] else ""), flush=True)
    order = [a["stem"] for a in arts if a["stem"] in lib]
    rows = [lib[s] for s in order]
    lib_f.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    nos = "".join(f'<p><a href="{E(r["stem"])}.html">{E(r["title"])}</a> — {E(r["journal"])} {E(r["year"])}</p>'
                  for r in rows)
    slim = [{k: v for k, v in r.items() if k != "missing_figs"} for r in rows]
    (READER / "index.html").write_text(INDEX.format(fonts=FONTS, css=CSS, npages=sum(r["pages"] for r in rows),
                                                    data=json.dumps(slim, ensure_ascii=False), common=COMMON_JS,
                                                    noscript=nos), encoding="utf-8")
    print(f"{len(rows)} articles -> {READER}/index.html")


if __name__ == "__main__":
    main()
