"""Experiment 41: the masters read back for the Layout view (views.py build_layout). No model calls.

Reads only out/masters/<stem>.jats.xml and <stem>.alto.xml (and the crops beside them):

  ALTO   the pages (size), the blocks of each page in reading order (TextBlock / ComposedBlock table / Illustration),
         each line's box (TextLine) and its words (String; ALTERNATIVE = Azure's reading a fix changed); running heads,
         page numbers and the lines Argon left out (role.noise) live only here
  JATS   what each block is (the element its xlink:href points at), its text with footnote calls (xref), misprint
         flags (named-content sic), Argon's fixes (named-content reader-fix), inline maths (inline-formula), cut
         into printed lines by the empty <target id="<TextLine ID>"/> masters.py writes at each line start; verse
         halves (verse-line), tables (XHTML), equations (tex-math), figures (graphic, alt-text), heading levels
         (sec/@disp-level), added text (p content-type="added" / disp-formula specific-use="added-by-argon", id
         <its block's ALTO id>-a<k>), the why of each fix and flag (back/notes)

    doc = mread.load(a)      # a: one entry of structure.sample()
"""
from __future__ import annotations

import html
import re
from pathlib import Path

from lxml import etree

from structure import OUT

MAST = OUT / "masters"
XL = "{http://www.w3.org/1999/xlink}"
ALTO = "{http://www.loc.gov/standards/alto/ns-v4#}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
E = html.escape


def _q(t):
    return ALTO + t


def _box(el):
    x, y = float(el.get("HPOS")), float(el.get("VPOS"))
    return [x, y, x + float(el.get("WIDTH")), y + float(el.get("HEIGHT"))]


def _tag(el):
    return el.tag if isinstance(el.tag, str) else ""


class Doc:
    def __init__(self, a: dict):
        self.a, self.stem = a, a["stem"]
        parser = etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False)
        self.J = etree.parse(str(MAST / f"{self.stem}.jats.xml"), parser).getroot()
        self.A = etree.parse(str(MAST / f"{self.stem}.alto.xml"), parser).getroot()
        self.by_id = {e.get("id"): e for e in self.J.iter() if isinstance(e.tag, str) and e.get("id")}
        self.why = {}                                   # note id (fix<k> / sic<k>) -> why
        self.fixes_of = {}                              # TextLine ID -> [(Azure's reading, the print, why)]
        for n in self.J.iter("notes"):
            for p in n.findall("p"):
                nc = {c.get("content-type"): c for c in p.findall("named-content")}
                w = nc.get("why")
                self.why[p.get("id")] = (w.text or "") if w is not None else ""
                ln = nc.get("alto-line")
                if n.get("notes-type") == "reader-fixes" and ln is not None and ln.get(XL + "href"):
                    tl = ln.get(XL + "href").split("#", 1)[-1]
                    self.fixes_of.setdefault(tl, []).append(((nc["azure-reading"].text or ""),
                                                             (nc["print"].text or ""), self.why[p.get("id")]))
        self.seg = {}                                   # TextLine ID -> the line's HTML (view markup)
        for t in self.J.iter("target"):
            if t.get("id"):
                self.seg[t.get("id")] = self._segment(t)
        self.added = {}                                 # ALTO block id -> [added text]
        for e in self.J.iter("p", "disp-formula"):
            i = e.get("id") or ""
            m = re.fullmatch(r"(.+)-a\d+", i)
            if not m:
                continue
            if e.tag == "p" and e.get("content-type") == "added":
                self.added.setdefault(m.group(1), []).append("".join(e.itertext()).strip())
            elif e.tag == "disp-formula" and e.get("specific-use") == "added-by-argon":
                tm = e.find(".//tex-math")
                self.added.setdefault(m.group(1), []).append((tm.text or "").strip() if tm is not None else "")

    # ------------------------------------------------------------ inline markup -> the view's HTML
    def _inl(self, el) -> str:
        """An inline element (and what it holds) as reader.text_html writes it."""
        tg = _tag(el)
        inner = lambda: (E(el.text or "") + "".join(self._inl(c) + E(c.tail or "") for c in el))  # noqa: E731
        if tg == "xref":
            rid = el.get("rid") or ""
            mk = "".join(el.itertext())
            if rid:
                return f'<sup class="call"><a href="#n-{E(rid)}" data-fn="{E(rid)}">{E(mk)}</a></sup>'
            return f'<sup class="call"><a>{E(mk)}</a></sup>'      # a call whose note Argon did not find
        if tg == "named-content" and el.get("content-type") == "sic":
            return (f'<span class="sic" tabindex="0" data-corr="{E(el.get(XL + "title") or "")}" '
                    f'data-why="{E(self.why.get(el.get("rid"), ""))}">{E("".join(el.itertext()))}</span>')
        if tg == "named-content" and el.get("content-type") == "reader-fix":
            return (f'<span class="fix" tabindex="0" data-azure="{E(el.get(XL + "title") or "")}" '
                    f'data-why="{E(self.why.get(el.get("rid"), ""))}">{inner()}</span>')
        if tg == "inline-formula":
            tm = el.find(".//tex-math")
            return f'<span class="math">\\({E((tm.text or "") if tm is not None else "")}\\)</span>'
        if tg == "target":
            return ""
        return inner()

    def _segment(self, t) -> str:
        """The line a target starts: its tail and the siblings after it, up to the next target."""
        out = [E(t.tail or "")]
        n = t.getnext()
        while n is not None and _tag(n) != "target":
            out.append(self._inl(n) + E(n.tail or ""))
            n = n.getnext()
        return "".join(out).strip()

    # ------------------------------------------------------------ ALTO lines
    def lines(self, tb) -> list[dict]:
        out = []
        for tl in tb.findall(_q("TextLine")):
            words = tl.findall(_q("String"))
            out.append(dict(id=tl.get("ID"), px=_box(tl), text=" ".join(w.get("CONTENT") for w in words),
                            html=self.seg.get(tl.get("ID")), words=words))
        return out

    def words_html(self, L) -> str:
        """A line only the ALTO holds (running head, page number, a contributor's printed name): its words, each of
        Argon's fixes on it (the reader-fixes notes link their line) marked as reader.text_html marks them."""
        t = L["text"]
        FO, FC, IDX = "\ue000", "\ue001", 0xE200
        fixes = []
        for frm, to, why in self.fixes_of.get(L["id"], []):
            if to and to in t:
                t = t.replace(to, FO + chr(IDX + len(fixes)) + to + FC, 1)
                fixes.append((frm, why))
        t = E(t)

        def fopen(m):
            frm, why = fixes[ord(m.group(1)) - IDX]
            return f'<span class="fix" tabindex="0" data-azure="{E(frm)}" data-why="{E(why)}">'
        t = re.sub(f"{FO}(.)", fopen, t)
        return t.replace(FC, "</span>")

    # ------------------------------------------------------------ what a block is
    def kind(self, el, role) -> tuple[str, dict]:
        """(Argon's block type, extras) of the JATS element an ALTO block points at."""
        tg, ct = el.tag, el.get("content-type")
        par = el.getparent()
        ptg = par.tag if par is not None else ""
        if tg == "article-title":
            return "title", {}
        if tg in ("custom-meta", "contrib"):
            return ("title" if role == "title" else "byline"), {}
        if tg == "title":
            if ct == "title":
                return "title", {}
            if ptg == "ref-list":
                m = re.fullmatch(r"heading-level-(\w+)", ct or "")
                return "heading", dict(level=m.group(1) if m else None)
            return "heading", dict(level=par.get("disp-level"))
        if tg == "mixed-citation":
            return "reference", {}
        if tg == "verse-group":
            return "verse", {}
        if tg == "p":
            if ptg == "fn":
                return "footnote", dict(fn_id=par.get("id"))
            if ptg == "disp-quote":
                return "quote", {}
            if ptg == "list-item":
                return "list_item", {}
            if ptg == "caption":
                return "caption", {}
            return (ct or "paragraph"), {}
        return tg, {}

    def lang_of(self, el, tb) -> str:
        e = el
        while e is not None:
            if e.get(XML_LANG):
                return e.get(XML_LANG)
            if e.tag == "sec" or e.tag == "article":
                pass
            e = e.getparent()
        return tb.get("LANG") or "ar"


def load(a: dict) -> dict:
    """The article as the Layout view draws it: pages, blocks in reading order (type, lines with boxes and HTML,
    continued, extras), lines no block took."""
    D = Doc(a)
    J = D.J
    lang = J.get(XML_LANG) or "ar"
    ddir = "rtl" if lang == "ar" else "ltr"
    def text(path):
        e = J.find(path)
        return " ".join("".join(e.itertext()).split()) if e is not None else ""

    def cmeta(name):
        for c in J.iterfind("front/article-meta/custom-meta-group/custom-meta"):
            if (c.findtext("meta-name") or "") == name:
                return " ".join("".join(c.find("meta-value").itertext()).split())
        return ""
    title = (text("front/article-meta/title-group/alt-title[@alt-title-type='metadata']")
             or text("front/article-meta/title-group/article-title") or a["stem"])
    bits = [x for x in [cmeta("printed-journal") or text("front/journal-meta/journal-title-group/journal-title"),
                        cmeta("printed-date") or text("front/article-meta/pub-date/year")] if x]
    first = a["first"]
    pages, blocks, noise = [], [], {}
    for P in D.A.iter(_q("Page")):
        lp = int(P.get("PHYSICAL_IMG_NR"))
        p = lp + first - 1
        W, H = int(P.get("WIDTH")), int(P.get("HEIGHT"))
        pages.append(dict(p=p, W=W, H=H))
        PS = P.find(_q("PrintSpace"))
        kids = list(PS)
        last = None
        for b in kids:
            tag = etree.QName(b).localname
            href = (b.get(XL + "href") or "").split("#", 1)[-1] or None
            role = (b.get("TAGREFS") or "").replace("role.", "")
            if tag == "TextBlock" and role in ("formulaInk", "pictureText"):
                if last is not None:                   # the ink under a typeset formula, the words in a picture
                    last["extra_lines"] += D.lines(b)
                continue
            if tag == "TextBlock" and role == "noise":
                noise.setdefault(p, []).extend(D.lines(b))
                continue
            rec = dict(page=p, alto=b.get("ID"), lines=[], extra_lines=[], continued=False, added=D.added.get(
                b.get("ID"), []), box=_box(b) if b.get("HPOS") is not None else None)
            if tag == "TextBlock" and href is None:      # running heads and page numbers: ALTO only
                rec["type"] = "header" if role == "pageHeader" else "footer"
                rec["lines"] = D.lines(b)
                for L in rec["lines"]:
                    L["html"] = D.words_html(L)
                rec["lang"] = b.get("LANG") or lang
                rec["continued"] = "flow.continued" in (b.get("TAGREFS") or "")
                blocks.append(rec)
                last = rec
                continue
            el = D.by_id.get(href)
            if el is None:
                continue
            if tag == "Illustration" and b.get("TYPE") == "formula":
                tm = el.find(".//tex-math")
                rec.update(type="equation", latex=(tm.text or "") if tm is not None else "", box=_box(b))
            elif tag == "Illustration":
                g = el.find("graphic")
                alt = el.find("alt-text")
                rec.update(type="figure", box=_box(b), src=g.get(XL + "href") if g is not None else None,
                           description=(alt.text or "") if alt is not None else "")
            elif tag == "ComposedBlock":
                rec.update(type="table", box=_box(b), table=el)
                for c in b.findall(_q("TextBlock")):
                    rec["lines"] += D.lines(c)
                rec["lang"] = el.get(XML_LANG) or lang
            else:
                T, ex = D.kind(el, role)
                if T == "figure-text":                   # words of a figure Argon gave no box: not drawn
                    continue
                rec.update(type=T, **ex)
                rec["lines"] = D.lines(b)
                rec["lang"] = D.lang_of(el, b) if T not in ("title", "byline") else (b.get("LANG") or lang)
                if T == "verse":
                    rec["hemistichs"] = [[t.get("id") for t in vl.iter("target")] for vl in el.findall("verse-line")]
                    rec["verse_el"] = el
                for L in rec["lines"]:
                    if L["html"] is None:                # a line the JATS does not hold (a contributor's name)
                        L["html"] = D.words_html(L)
            rec["continued"] = "flow.continued" in (b.get("TAGREFS") or "")
            rec["target"] = href
            blocks.append(rec)
            last = rec
    return dict(D=D, lang=lang, ddir=ddir, title=title, sub=" · ".join(bits), pages=pages, blocks=blocks,
                noise=noise)


def table_html(D: Doc, el, d: str, lg: str) -> str:
    """A table-wrap's table as structure.py wrote it for the view (rows, th/td, spans; each cell its lines' HTML)."""
    rows = []
    for tr in el.iter("tr"):
        cells = []
        for c in tr:
            if c.tag not in ("th", "td"):
                continue
            sp = "".join(f' {k}="{c.get(k)}"' for k in ("colspan", "rowspan") if c.get(k))
            ts = [t.get("id") for t in c.iter("target")]
            cells.append(f"<{c.tag}{sp}>" + " ".join(D.seg.get(t, "") for t in ts) + f"</{c.tag}>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    return f'<table dir="{d}" lang="{E(lg)}">' + "".join(rows) + "</table>"


def verse_inner(D: Doc, rec, W: int, H: int) -> str:
    """A verse's halves as structure.py wrote them (span.hemistich with its box in 0-1000 units)."""
    box = {L["id"]: L["px"] for L in rec["lines"]}
    out = []
    for h in rec["hemistichs"]:
        if not h:
            continue
        bs = [box[i] for i in h if i in box]
        bb = ""
        if bs:
            x0, y0 = min(b[0] for b in bs) / W * 1000, min(b[1] for b in bs) / H * 1000
            x1, y1 = max(b[2] for b in bs) / W * 1000, max(b[3] for b in bs) / H * 1000
            bb = f' data-bbox="{round(x0)},{round(y0)},{round(x1)},{round(y1)}"'
        out.append(f'<span class="hemistich"{bb}>' + " ".join(D.seg.get(i, "") for i in h) + "</span>")
    return "".join(out)


def crop_path(stem: str, src: str | None) -> Path | None:
    return (MAST / src) if src else None
