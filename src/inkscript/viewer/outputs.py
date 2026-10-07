"""What `inkscript view` shows, read from a build's output files only (never from the enrich code's state).

    Outputs(out_dir, scan_dir=None)
      .docs()                      stem -> Doc, every <stem>.alto.xml under out_dir (any depth) with its page source
      .index()                     the picker's rows: title, journal, year, pages, flagged/corrected counts
      .doc(stem)                   Doc: pages, the ALTO tags (trust marks, reasons, quotations), per-page words
      Doc.page(n)                  one page's blocks > lines > words with boxes, marks, alternatives, glyph ids
      Doc.article()                the JATS rendered as HTML, every word a <span data-w="p<page>w<n>"> linked to
                                   its ALTO String (aligned within its block), every block a data-b
      Doc.image(n, dpi)            the page as PNG (pymupdf), from the faithful PDF (its background is the scan)

The page image: <stem>.pdf beside the ALTO file is the faithful PDF, whose page is the scan with the ink glyphs
drawn invisibly over it, so it renders as the scan. --scan-dir points at the original scans instead.

The two files link through ids (docs/decisions.md D20): each ALTO TextBlock (p<page>b<n>) has the same id as the
JATS element that holds its words, or points at it with xlink:href when a paragraph continues on the next page.
JATS has no per-word ids, so the article's words are matched here to the block's ALTO words in reading order.
"""
from __future__ import annotations

import json
import re
import threading
from collections import OrderedDict
from pathlib import Path

from lxml import etree

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
XLINK = "http://www.w3.org/1999/xlink"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
_A = "{%s}" % ALTO_NS
_BLOCK_ID = re.compile(r"^p\d+b\d+(-\d+)?$")
_TRUST = re.compile(r"(\d+) words verified, (\d+) agreed, (\d+) flagged(?:, (\d+) corrected)?")
_MARKS = re.compile(r"[ً-ٰٟـۖ-ۭ]")         # tashkeel, tatweel, Quranic signs
_PUNCT = re.compile(r"[\s()\[\]{}«»\"'.,:;!?،؛؟\-–—ـ*/\\]+")
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
FURNITURE = {"pageHeader", "pageFooter", "pageNumber"}


def _parser():
    return etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False, huge_tree=True)


def norm(t: str) -> str:
    """A key for matching a word of the article to a word of the page: no vowel marks, no punctuation, one
    form of alef / ya / ta marbuta, Western digits."""
    t = _MARKS.sub("", t or "").translate(_DIG)
    t = re.sub("[إأآٱ]", "ا", t).replace("ى", "ي").replace("ة", "ه")
    return _PUNCT.sub("", t)


class Doc:
    def __init__(self, stem: str, alto: Path, pdf: Path | None):
        self.stem, self.alto_path, self.pdf = stem, Path(alto), pdf
        self.jats_path = self.alto_path.with_name(f"{stem}.jats.xml")
        self.shapes_path = self.alto_path.with_name(f"{stem}.shapes.json")
        self._lock = threading.Lock()
        self._pages = None
        self._info = None
        self._article = None

    # ------------------------------------------------------------------ ALTO
    def _load(self):
        with self._lock:
            if self._pages is not None:
                return
            root = etree.parse(str(self.alto_path), _parser()).getroot()
            tags = {}
            for t in root.iter(_A + "OtherTag", _A + "StructureTag"):
                tags[t.get("ID")] = dict(type=t.get("TYPE"), label=t.get("LABEL"), desc=t.get("DESCRIPTION"),
                                         uri=t.get("URI"))
            glyphs = self._glyphs()
            pages, words_at = {}, {}
            for pg in root.iter(_A + "Page"):
                n = int(pg.get("PHYSICAL_IMG_NR") or pg.get("ID")[4:])
                blocks = []
                for tb in pg.iter(_A + "TextBlock"):
                    href = tb.get(f"{{{XLINK}}}href")
                    role = (tb.get("TAGREFS") or "role.body").split()[0].removeprefix("role.")
                    blk = dict(id=tb.get("ID"), role=role, b=_box(tb), next=tb.get("IDNEXT"),
                               href=href.split("#", 1)[1] if href and "#" in href else None,
                               dir=tb.get("BASEDIRECTION"), lines=[])
                    for tl in tb.iter(_A + "TextLine"):
                        line = dict(id=tl.get("ID"), b=_box(tl), w=[])
                        for s in tl.iter(_A + "String"):
                            refs = (s.get("TAGREFS") or "").split()
                            w = dict(id=s.get("ID"), t=s.get("CONTENT"), b=_box(s))
                            if s.get("WC") is not None:
                                w["c"] = float(s.get("WC"))
                            mark = next((r[6:] for r in refs if r.startswith("trust.")), None)
                            if mark:
                                w["m"] = mark
                            why = [r[4:] for r in refs if r.startswith("why.")]
                            if why:
                                w["why"] = why
                            q = [r for r in refs if r.startswith("quran")]
                            if q:
                                w["q"] = q[0]
                            alts = [[a.get("PURPOSE") or "", a.text or ""] for a in s.iter(_A + "ALTERNATIVE")]
                            if alts:
                                w["alt"] = alts
                            if s.get("LANG"):
                                w["lang"] = s.get("LANG")
                            g = glyphs.get(w["id"])
                            if g:
                                w["g"] = g
                            line["w"].append(w)
                            words_at[w["id"]] = (n, blk["id"])
                        blk["lines"].append(line)
                    blocks.append(blk)
                pages[n] = dict(n=n, w=float(pg.get("WIDTH") or 0), h=float(pg.get("HEIGHT") or 0),
                                printed=pg.get("PRINTED_IMG_NR"), born=pg.get("PAGECLASS") == "born-digital",
                                blocks=blocks)
            procs = []
            for p in root.iter(_A + "OCRProcessing", _A + "Processing"):
                procs.append(dict(id=p.get("ID"), what=_first_text(p, "processingStepDescription"),
                                  software=" ".join(filter(None, (_first_text(p, "softwareCreator"),
                                                                  _first_text(p, "softwareName"),
                                                                  _first_text(p, "softwareVersion"))))))
            self._tags, self._procs, self._words_at = tags, procs, words_at
            self._pages = pages

    def _glyphs(self) -> dict[str, list[int]]:
        """ALTO word id -> the indexes of its glyphs among shapes.json's placements (the glyph of the word in
        the faithful PDF: its own ink outline; letters are cut inside it)."""
        if not self.shapes_path.exists():
            return {}
        try:
            sj = json.loads(self.shapes_path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return {}
        out = {}
        for i, pl in enumerate(sj.get("placements", [])):
            if pl.get("word"):
                out.setdefault(pl["word"], []).append(i)
        return out

    def page(self, n: int) -> dict:
        self._load()
        return self._pages[n]

    def page_numbers(self) -> list[int]:
        self._load()
        return sorted(self._pages)

    # ------------------------------------------------------------------ JATS front matter
    def info(self) -> dict:
        """Title, journal, year, pages and trust counts, from the JATS front matter (small, read fast)."""
        if self._info is not None:
            return self._info
        d = dict(id=self.stem, title="", journal="", journal_id="", year="", pages=0, verified=0, agreed=0, flagged=0,
                 corrected=0, quotations=0, authors=[], has_pdf=bool(self.pdf), folder=self.alto_path.parent.name)
        if self.jats_path.exists():
            art = etree.parse(str(self.jats_path), _parser()).getroot()
            fr = art.find("front")
            if fr is not None:
                d["title"] = _txt(fr.find(".//article-title"))
                d["journal"] = _txt(fr.find(".//journal-title"))
                d["journal_id"] = _txt(fr.find(".//journal-id"))
                d["year"] = _txt(fr.find(".//pub-date/year"))
                pc = fr.find(".//page-count")
                d["pages"] = int(pc.get("count")) if pc is not None else 0
                d["authors"] = [_txt(s) for s in fr.iter("string-name")]
                for cm in fr.iter("custom-meta"):
                    name, val = _txt(cm.find("meta-name")), _txt(cm.find("meta-value"))
                    if name == "trust":
                        m = _TRUST.search(val)
                        if m:
                            d.update(verified=int(m[1]), agreed=int(m[2]), flagged=int(m[3]),
                                     corrected=int(m[4] or 0))
                    elif name == "quran-quotations":
                        m = re.match(r"(\d+)", val)
                        d["quotations"] = int(m[1]) if m else 0
        self._info = d
        return d

    def summary(self) -> dict:
        """Everything the page and article views need once: page sizes, tags, processing steps."""
        self._load()
        d = dict(self.info())
        d["page_list"] = [dict(n=p["n"], w=p["w"], h=p["h"], printed=p["printed"], born=p["born"])
                          for _, p in sorted(self._pages.items())]
        d["pages"] = len(self._pages)
        d["tags"] = self._tags
        d["processing"] = self._procs
        d["has_jats"] = self.jats_path.exists()
        return d

    # ------------------------------------------------------------------ the article
    def article(self) -> dict:
        if self._article is None:
            self._load()
            self._article = render_article(self)
        return self._article

    # ------------------------------------------------------------------ the page image
    def image(self, n: int, dpi: int = 150) -> bytes:
        import numpy as np
        import pymupdf
        with pymupdf.open(str(self.pdf)) as d:
            page = d[n - 1]
            pix = page.get_pixmap(dpi=dpi, alpha=False)
            a = np.frombuffer(pix.samples, dtype=np.uint8).reshape(pix.height, pix.width, pix.n)
            if pix.n >= 3 and int(np.abs(a[..., 0].astype(np.int16) - a[..., 1]).max()) < 12 \
                    and int(np.abs(a[..., 1].astype(np.int16) - a[..., 2]).max()) < 12:
                pix = page.get_pixmap(dpi=dpi, alpha=False, colorspace=pymupdf.csGRAY)   # a grey scan: 1/3 the bytes
            return pix.tobytes("png")


def _first_text(el, local):
    e = next(el.iter(_A + local), None)
    return (e.text or "").strip() if e is not None else ""


def _txt(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def _box(el) -> list[int]:
    return [int(float(el.get(k) or 0)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]


# ---------------------------------------------------------------------- JATS -> HTML

class _Ctx:
    """One JATS element that carries an ALTO block id: its words, to be matched to the block's ALTO words."""

    def __init__(self, bid):
        self.bid, self.spans = bid, []


def render_article(doc: Doc) -> dict:
    """The JATS file as an HTML fragment (right to left, Arabic), every word that could be matched to its ALTO
    word carrying data-w (its id) and data-m (its trust mark), every block element data-b (its ALTO block ids).
    Returns html and the share of the article's words that link to a word on the page."""
    if not doc.jats_path.exists():
        return dict(html="<p class='empty'>No JATS file beside this ALTO file.</p>", linked=0, words=0)
    art = etree.parse(str(doc.jats_path), _parser()).getroot()
    pages = doc._pages
    # ALTO: block id -> its words in reading order; JATS id -> the ALTO blocks that point at it (continuations)
    block_words, pointing, block_role = {}, {}, {}
    for n in sorted(pages):
        for b in pages[n]["blocks"]:
            block_words[b["id"]] = [w for ln in b["lines"] for w in ln["w"]]
            block_role[b["id"]] = b["role"]
            target = b["href"] or b["id"]
            pointing.setdefault(target, [])
            if b["id"] not in pointing[target]:
                pointing[target].append(b["id"])
    for bid in block_words:                                   # a block always answers for itself first
        lst = pointing.setdefault(bid, [])
        if bid in lst:
            lst.remove(bid)
        lst.insert(0, bid)
    ctxs = []
    E = etree.Element

    def blocks_for(bid):
        base = re.sub(r"-\d+$", "", bid)
        return pointing.get(base, [base])

    def attach_block(h, el):
        i = el.get("id")
        if i and _BLOCK_ID.match(i):
            h.set("data-b", " ".join(blocks_for(i)))
            h.set("id", "j-" + i)

    def words_into(h, el, ctx):
        """Mixed content of a JATS inline-bearing element into the HTML element h."""
        _text_into(h, el.text, ctx, None)
        for c in el:
            tag = c.tag if isinstance(c.tag, str) else ""
            if tag == "xref":
                a = etree.SubElement(h, "a", {"class": "fnref", "href": "#j-" + (c.get("rid") or ""),
                                              "data-rid": c.get("rid") or ""})
                _text_into(a, c.text, ctx, None, wrap=True)
            elif tag == "named-content" and c.get("content-type") == "quran":
                href = c.get(f"{{{XLINK}}}href") or ""
                q = etree.SubElement(h, "span", {"class": "quran " + (c.get("specific-use") or ""),
                                                 "id": "j-" + (c.get("id") or "")})
                inner = etree.SubElement(q, "span", {"class": "qt"})
                words_into(inner, c, ctx)
                _verse_badge(q, href, c.get(f"{{{XLINK}}}title"))
            elif tag in ("italic", "bold", "sup", "sub"):
                s = etree.SubElement(h, {"italic": "i", "bold": "b"}.get(tag, tag))
                words_into(s, c, ctx)
            elif tag in ("ext-link", "uri"):
                a = etree.SubElement(h, "a", {"href": c.get(f"{{{XLINK}}}href") or "", "target": "_blank",
                                              "rel": "noopener"})
                words_into(a, c, ctx)
            else:
                s = etree.SubElement(h, "span", {"class": "jats-" + tag})
                words_into(s, c, ctx)
            _text_into(h, c.tail, ctx, None)

    def block(h_parent, tag, el, cls=None, extra=None):
        h = etree.SubElement(h_parent, tag, {"class": cls} if cls else {})
        if extra:
            for k, v in extra.items():
                h.set(k, v)
        attach_block(h, el)
        lang = el.get(XML_LANG)
        if lang and lang != "ar":
            h.set("lang", lang)
            h.set("dir", "ltr")
        i = el.get("id")
        ctx = _Ctx(i) if i and _BLOCK_ID.match(i) else None
        if ctx:
            ctxs.append(ctx)
        words_into(h, el, ctx)
        return h

    root = E("article", {"class": "jats", "dir": "rtl", "lang": "ar"})
    fr = art.find("front")
    meta = {}
    if fr is not None:
        for cm in fr.iter("custom-meta"):
            meta.setdefault(_txt(cm.find("meta-name")), []).append((_txt(cm.find("meta-value")), cm.get("id")))
        hd = etree.SubElement(root, "header", {"class": "front"})
        subj = fr.find(".//subj-group/subject")
        if subj is not None:
            block(hd, "div", subj, "rubric")
        at = fr.find(".//article-title")
        if at is not None:
            h1 = block(hd, "h1", at, "title")
            tw = (meta.get("title-words") or [("", None)])[0][0]
            if tw:
                h1.set("data-words", tw)
            src = (meta.get("title-source") or [("", None)])[0][0]
            if src:
                h1.set("title", "title from: " + src)
        alt = fr.find(".//alt-title")
        if alt is not None:
            p = etree.SubElement(hd, "p", {"class": "alt-title"})
            lab = etree.SubElement(p, "span", {"class": "lab"})
            lab.text = "قراءة الحبر: "
            _append_text(p, _txt(alt))
        cg = fr.find(".//contrib-group")
        if cg is not None:
            ul = etree.SubElement(hd, "div", {"class": "authors"})
            for n, c in enumerate(cg.iter("contrib"), 1):
                d = etree.SubElement(ul, "div", {"class": "author"})
                attach_block(d, c)
                ctx = _Ctx(c.get("id")) if c.get("id") and _BLOCK_ID.match(c.get("id")) else None
                if ctx:
                    ctxs.append(ctx)
                aw = (meta.get(f"author-{n}-words") or [("", None)])[0][0]
                if aw:
                    d.set("data-words", aw)
                sn = c.find("string-name")
                if sn is not None:
                    nm = etree.SubElement(d, "span", {"class": "name"})
                    pre = sn.find("prefix")
                    if pre is not None:
                        ps = etree.SubElement(nm, "span", {"class": "prefix"})
                        _text_into(ps, pre.text, ctx, None)
                        _text_into(nm, pre.tail, ctx, None)
                    else:
                        _text_into(nm, sn.text, ctx, None)
                aff = c.find("aff")
                if aff is not None:
                    a = etree.SubElement(d, "span", {"class": "aff"})
                    a.text = _txt(aff)
        facts = []
        jt = _txt(fr.find(".//journal-title")) or ""
        if jt:
            facts.append(("journal", jt))
        y = fr.find(".//pub-date")
        if y is not None:
            facts.append(("year", _txt(y.find("year")) + (" هـ" if y.get("calendar") == "islamic" else "")))
        for t, lab in (("volume", "volume"), ("issue", "issue")):
            v = fr.find(f".//article-meta/{t}")
            if v is not None:
                facts.append((lab, _txt(v)))
        fp, lp = _txt(fr.find(".//fpage")), _txt(fr.find(".//lpage"))
        if fp:
            facts.append(("printed pages", f"{fp}–{lp}" if lp else fp))
        pc = fr.find(".//page-count")
        if pc is not None:
            facts.append(("pages", pc.get("count")))
        facts.append(("id", _txt(fr.find(".//article-id"))))
        dl = etree.SubElement(hd, "dl", {"class": "facts", "dir": "ltr"})
        for k, v in facts:
            dt = etree.SubElement(dl, "dt")
            dt.text = k
            dd = etree.SubElement(dl, "dd")
            dd.text = v
        tr = (meta.get("trust") or [("", None)])[0][0]
        if tr:
            p = etree.SubElement(hd, "p", {"class": "trustline", "dir": "ltr"})
            p.text = tr

    body = art.find("body")
    main = etree.SubElement(root, "div", {"class": "body"})

    def walk(src, dst, depth):
        for el in src:
            tag = el.tag if isinstance(el.tag, str) else ""
            if tag == "sec":
                s = etree.SubElement(dst, "section", {"id": "j-" + (el.get("id") or "")})
                walk(el, s, depth + 1)
            elif tag == "title":
                block(dst, f"h{min(6, depth + 1)}", el, "heading")
            elif tag == "p":
                block(dst, "p", el)
            else:
                walk(el, dst, depth)
    if body is not None:
        walk(body, main, 1)

    back = art.find("back")
    if back is not None:
        for g in back:
            tag = g.tag if isinstance(g.tag, str) else ""
            if tag == "fn-group":
                sec = etree.SubElement(root, "section", {"class": "notes"})
                t = g.find("title")
                if t is not None:
                    block(sec, "h2", t, "heading")
                else:
                    h = etree.SubElement(sec, "h2", {"class": "auto"})
                    h.text = "الهوامش"
                ol = etree.SubElement(sec, "ol", {"class": "fn"})
                for fn in g.iter("fn"):
                    li = etree.SubElement(ol, "li", {"id": "j-" + (fn.get("id") or "")})
                    lab = fn.find("label")
                    ls = etree.SubElement(li, "a", {"class": "fnlabel", "href": "#", "data-back": fn.get("id") or ""})
                    ls.text = _txt(lab) if lab is not None else "•"
                    pm = re.match(r"fn-p(\d+)-", fn.get("id") or "")
                    if pm:                                   # notes are numbered per page in many journals
                        ls.set("title", "back to the marker in the text")
                        sp = etree.SubElement(ls, "span", {"class": "fnpage"})
                        sp.text = f"p.{pm[1]}"
                    for p in fn.findall("p"):
                        block(li, "p", p)
            elif tag == "ref-list":
                sec = etree.SubElement(root, "section", {"class": "refs"})
                attach_block(sec, g)
                t = g.find("title")
                h = etree.SubElement(sec, "h2", {"class": "heading"})
                h.text = _txt(t) if t is not None else "المراجع"
                ol = etree.SubElement(sec, "ol", {"class": "reflist"})
                for r in g.iter("ref"):
                    li = etree.SubElement(ol, "li", {"id": "j-" + (r.get("id") or "")})
                    for mc in r:
                        if isinstance(mc.tag, str):
                            block(li, "div", mc, "citation")
            elif tag == "notes":
                sec = etree.SubElement(root, "section", {"class": "quran-notes"})
                t = g.find("title")
                h = etree.SubElement(sec, "h2", {"class": "heading"})
                h.text = _txt(t) if t is not None else "Notes"
                for p in g.findall("p"):
                    hp = etree.SubElement(sec, "p", {"id": "j-" + (p.get("id") or "")})
                    if p.get(XML_LANG) and p.get(XML_LANG) != "ar":
                        hp.set("lang", p.get(XML_LANG))
                        hp.set("dir", "ltr")
                        hp.set("class", "small")
                    hp.text = p.text
                    for c in p:
                        if c.tag == "ext-link":
                            _verse_badge(hp, c.get(f"{{{XLINK}}}href") or "", c.text)
                        elif c.tag == "named-content":
                            s = etree.SubElement(hp, "span", {"class": "verse"})
                            s.text = "﴿" + "".join(c.itertext()) + "﴾"
                        else:
                            s = etree.SubElement(hp, "span")
                            s.text = "".join(c.itertext())
                        s_ = hp[-1]
                        s_.tail = c.tail

    # about this file: the custom-meta, as written
    if meta:
        det = etree.SubElement(root, "details", {"class": "about", "dir": "ltr"})
        sm = etree.SubElement(det, "summary")
        sm.text = "About this file (custom-meta)"
        dl = etree.SubElement(det, "dl")
        for k, vs in meta.items():
            for v, i in vs:
                dt = etree.SubElement(dl, "dt")
                dt.text = k
                dd = etree.SubElement(dl, "dd")
                dd.text = v
                if i and _BLOCK_ID.match(i):
                    dd.set("data-b", " ".join(blocks_for(i)))
                    dd.set("id", "j-" + i)
                    dd.set("dir", "auto")

    # match each block element's words to its ALTO words
    linked = total = 0
    # the elements that share a block (p3b4, p3b4-2: a block split between two elements) take its words in turn
    def split(i):
        m = re.match(r"^(.*?)(?:-(\d+))?$", i)
        return m[1], int(m[2] or 1)
    upto = {}
    for ctx in sorted(ctxs, key=lambda c: split(c.bid)):
        base = split(ctx.bid)[0]
        cands = [w for b in blocks_for(ctx.bid) for w in block_words.get(b, [])]
        total += len(ctx.spans)
        got, end = _align(ctx.spans, cands, upto.get(base, 0))
        if upto.get(base) and len(got) < len(ctx.spans) // 2:    # the parts are not in the block's order (a note
            again, end2 = _align(ctx.spans, cands, 0)            # whose words come after the text it splits from)
            if len(again) > len(got):
                got, end = again, end2
        upto[base] = max(end, upto.get(base, 0))
        for sp, w in got:
            sp.set("data-w", w["id"])
            if w.get("m"):
                sp.set("data-m", w["m"])
            if w.get("q"):
                sp.set("data-q", w["q"])
        linked += len(got)
    out = etree.tostring(root, encoding="unicode", method="html")
    return dict(html=out, linked=linked, words=total)


def _verse_badge(parent, href, title):
    """A small link to the verse: the sura's name, then sura:verse kept left to right."""
    a = etree.SubElement(parent, "a", {"class": "qref", "href": href, "target": "_blank", "rel": "noopener",
                                       "title": "the verse on tanzil.net"})
    name, _, ref = (title or "").rpartition(" ")
    a.text = (name + " ") if name else ""
    b = etree.SubElement(a, "bdi", {"dir": "ltr"})
    b.text = ref or href.rsplit("#", 1)[-1]
    return a


def _append_text(h, text):
    if not text:
        return
    if len(h):
        h[-1].tail = (h[-1].tail or "") + text
    else:
        h.text = (h.text or "") + text


def _text_into(h, text, ctx, _unused, wrap=False):
    """Text into h: with a block context, each whitespace-separated piece becomes a <span class="w">."""
    if not text:
        return
    if ctx is None:
        _append_text(h, text)
        return
    for piece in re.split(r"(\s+)", text):
        if not piece:
            continue
        if piece.isspace():
            _append_text(h, piece)
            continue
        s = etree.SubElement(h, "span", {"class": "w"})
        s.text = piece
        ctx.spans.append(s)


def _align(spans, cands, start=0, look=12) -> tuple[list, int]:
    """Each piece of the article's text to the ALTO word it came from, in reading order, from cands[start:].
    A piece equal to a word (after norm) takes it and moves on; a piece inside a word (the head of "عاصم(٢)."
    before its note link) takes it and stays, so the rest of the word can take it too. Until the first piece is
    placed the search reaches further (words of the block written elsewhere: the front matter, a note), but
    then two pieces in a row must agree. Returns ([(piece, word)], where the next element of the block starts)."""
    keys = [norm(w["t"]) for w in cands]
    pk = [norm(s.text) for s in spans]
    j, n, got = start, 0, []
    for si, s in enumerate(spans):
        k = pk[si]
        if not k:
            k = (s.text or "").strip()
            hit = next((i for i in range(j, min(len(cands), j + 3)) if (cands[i]["t"] or "").strip() == k), None)
        else:
            hit = next((i for i in range(j, min(len(cands), j + look)) if keys[i] == k), None)
            if hit is None:
                hit = next((i for i in range(j, min(len(cands), j + 4)) if keys[i] and k in keys[i]), None)
            if hit is None and n == 0:
                nxt = next((x for x in pk[si + 1:] if x), None)
                hit = next((i for i in range(j, len(cands)) if keys[i] == k and
                            (nxt is None or (i + 1 < len(cands) and nxt in keys[i + 1]))), None)
        if hit is None:
            continue
        got.append((s, cands[hit]))
        n += 1
        j = hit + 1 if keys[hit] == k else hit
    return got, j


# ---------------------------------------------------------------------- the set of documents

class Outputs:
    def __init__(self, out_dir, scan_dir=None, keep: int = 6):
        self.out_dir = Path(out_dir)
        self.scan_dir = Path(scan_dir) if scan_dir else None
        self._docs = None
        self._index = None
        self._open = OrderedDict()            # the few documents whose ALTO is held in memory
        self._keep = keep
        self._lock = threading.Lock()

    def docs(self) -> dict[str, Path]:
        if self._docs is None:
            found = {}
            for a in sorted(self.out_dir.rglob("*.alto.xml")):
                stem = a.name[:-len(".alto.xml")]
                if stem in found or not a.with_name(f"{stem}.jats.xml").exists():
                    continue
                found[stem] = a
            self._docs = found
        return self._docs

    def pdf_for(self, stem: str) -> Path | None:
        if self.scan_dir:
            for c in (self.scan_dir / f"{stem}.pdf", self.scan_dir / stem / f"{stem}.pdf"):
                if c.exists():
                    return c
        p = self.docs()[stem].with_name(f"{stem}.pdf")
        return p if p.exists() else None

    def doc(self, stem: str) -> Doc:
        with self._lock:
            if stem in self._open:
                self._open.move_to_end(stem)
                return self._open[stem]
            if stem not in self.docs():
                raise KeyError(stem)
            d = Doc(stem, self.docs()[stem], self.pdf_for(stem))
            self._open[stem] = d
            while len(self._open) > self._keep:
                self._open.popitem(last=False)
            return d

    def index(self) -> list[dict]:
        if self._index is None:
            self._index = [(self._open.get(stem) or Doc(stem, a, self.pdf_for(stem))).info()
                           for stem, a in self.docs().items()]
        return self._index
