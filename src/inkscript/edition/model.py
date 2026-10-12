"""One article read from its master files (JATS + ALTO) into the shape every derived edition is written from
(experiment 35).

    ed = load(jats_path)                     # <id>.alto.xml and <id>.pdf (the faithful PDF) are found beside it
    ed.front                                 # title, authors, journal, date, volume/issue, pages, abstracts, ids...
    ed.body                                  # [Node] in reading order: heading (level) | p | ref-head | ref
    ed.notes                                 # [Note]: footnotes/endnotes, each [Node] paragraphs
    ed.verses                                # [dict]: the Quran quotations' verses (tanzil), from <notes>
    ed.pages                                 # {n: Page}: size in ALTO pixels and in PDF points, blocks in ALTO order
    ed.blocks                                # {block id: Block}: role, box, lines of words, the JATS element it feeds
    ed.regions(node)                         # [(page, (x, y, w, h))]: where a node's ink is on the scan

Nothing here is invented: every string comes from the JATS (the article as read and structured) or the ALTO (the
words and where they are). Inline content is kept as runs so each writer can render it in its own markup:

    {"t": "text", "s": "..."}                plain text
    {"t": "fnref", "rid": "fn-p2-1", "s": "(١)"}
    {"t": "quran", "id", "href", "title", "match": "matches-verse"|..., "inl": [...]}
    {"t": "b"|"i"|"sup"|"sub", "inl": [...]}
    {"t": "link", "href", "inl": [...]}

Block ids are shared by the two files (D20): an ALTO TextBlock p<page>b<n> has the id of the JATS element holding
its words, or points at it (xlink:href) when a paragraph runs on to the next page; p3b4-2 is a second element cut
from block p3b4.
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

from lxml import etree

ALTO_NS = "http://www.loc.gov/standards/alto/ns-v4#"
_A = "{%s}" % ALTO_NS
XLINK = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
BLOCK_ID = re.compile(r"^p(\d+)(?:b\d+|t\d+(?:c\d+)?|eq\d+|f\d+)(?:-\d+)?$")   # a block, a table (cell), a formula,
#                                                                          a figure
MML = "http://www.w3.org/1998/Math/MathML"
FURNITURE = {"pageHeader", "pageFooter", "pageNumber"}


def _parser():
    return etree.XMLParser(load_dtd=False, no_network=True, resolve_entities=False, huge_tree=True)


def txt(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def base_id(i: str) -> str:
    return re.sub(r"-\d+$", "", i or "")


# ---------------------------------------------------------------------------------------------- ALTO side

@dataclass
class Word:
    id: str
    text: str
    box: tuple            # x, y, w, h in ALTO pixels
    conf: float | None = None
    mark: str | None = None       # trust mark: agreed | flagged | verified | corrected
    lang: str | None = None
    math: bool = False            # the ink of an inline formula (TAGREFS kind.formula): rendered as maths


@dataclass
class Line:
    id: str
    box: tuple
    words: list


@dataclass
class Block:
    id: str
    page: int
    role: str             # body | title | rubric | author | sectionHeading | footnote | pageHeader | ...
    box: tuple
    lines: list
    target: str | None    # the JATS element id it feeds (its own id, or where its xlink:href points)
    lang: str | None = None
    regions: list = field(default_factory=list)   # TAGREFS region.* (vowelled, handwritten, decorative)
    kind: str = ""        # what the JATS made of it: title, author, heading, p, fn, ref, table, cell, formula,
    #                       front, stray, furniture
    table: str | None = None   # a table cell's ComposedBlock id

    @property
    def words(self):
        return [w for ln in self.lines for w in ln.words]

    @property
    def furniture(self) -> bool:
        return self.role in FURNITURE


@dataclass
class Page:
    n: int
    w: float              # ALTO pixels
    h: float
    pt_w: float = 0.0     # the faithful PDF's page in points
    pt_h: float = 0.0
    printed: str | None = None
    born: bool = False
    handwritten: bool = False
    blocks: list = field(default_factory=list)


def _box(el) -> tuple:
    return tuple(float(el.get(k) or 0) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))


def read_alto(path: Path) -> tuple[dict, dict]:
    root = etree.parse(str(path), _parser()).getroot()
    pages, blocks = {}, {}
    for pg in root.iter(_A + "Page"):
        n = int(pg.get("PHYSICAL_IMG_NR") or pg.get("ID")[4:])
        page = Page(n, float(pg.get("WIDTH") or 0), float(pg.get("HEIGHT") or 0), printed=pg.get("PRINTED_IMG_NR"),
                    born=pg.get("PAGECLASS") == "born-digital", handwritten=pg.get("PAGECLASS") == "handwritten")
        for tb in pg.iter(_A + "TextBlock", _A + "Illustration", _A + "ComposedBlock"):
            if tb.tag != _A + "TextBlock":           # a formula or figure (Illustration), a table (ComposedBlock)
                href = tb.get(XLINK + "href")
                b = Block(tb.get("ID"), n, (tb.get("TYPE") or "figure").lower(), _box(tb), [],
                          href.split("#", 1)[1] if href and "#" in href else None)
                page.blocks.append(b)
                blocks[b.id] = b
                continue
            parent = tb.getparent()
            in_table = parent.get("ID") if parent.tag == _A + "ComposedBlock" else None
            refs = (tb.get("TAGREFS") or "role.body").split()
            role = next((r[5:] for r in refs if r.startswith("role.")), "body")
            href = tb.get(XLINK + "href")
            lines = []
            for tl in tb.iter(_A + "TextLine"):
                ws = []
                for s in tl.iter(_A + "String"):
                    tr = (s.get("TAGREFS") or "").split()
                    ws.append(Word(s.get("ID"), s.get("CONTENT") or "", _box(s),
                                   float(s.get("WC")) if s.get("WC") else None,
                                   next((r[6:] for r in tr if r.startswith("trust.")), None), s.get("LANG"),
                                   "kind.formula" in tr))
                lines.append(Line(tl.get("ID"), _box(tl), ws))
            b = Block(tb.get("ID"), n, role, _box(tb), lines,
                      href.split("#", 1)[1] if href and "#" in href else None, tb.get("LANG"),
                      [r[7:] for r in refs if r.startswith("region.")])
            b.table = in_table
            page.blocks.append(b)
            blocks[b.id] = b
        pages[n] = page
    return pages, blocks


# ---------------------------------------------------------------------------------------------- JATS side

@dataclass
class Node:
    kind: str             # heading | p | ref-head | ref
    inl: list
    id: str | None = None
    level: int = 0        # heading depth (1 = top section)
    lang: str | None = None
    ctype: str | None = None   # content-type: vowelled, handwritten, decorative
    blocks: list = field(default_factory=list)   # ALTO block ids whose words this node holds
    extra: dict = field(default_factory=dict)    # formula: label, mathml, tex, graphic; table: rows, caption...

    @property
    def text(self) -> str:
        if self.kind == "table":
            return " ".join(plain(c["inl"]) for r in self.extra["rows"] for c in r["cells"])
        if self.kind == "formula":
            return self.extra.get("ink", "")
        if self.kind == "figure":
            return plain(self.extra.get("caption") or [])
        return plain(self.inl)


@dataclass
class Note:
    id: str
    label: str
    paras: list           # [Node]
    page: int | None = None


def plain(inl) -> str:
    out = []
    for r in inl:
        if r["t"] in ("text", "fnref"):
            out.append(r["s"])
        elif r["t"] == "math":
            out.append(r.get("ink") or r.get("tex") or "")
        else:
            out.append(plain(r["inl"]))
    return "".join(out)


def _inline(el, out=None) -> list:
    """An element's mixed content as runs (see the module doc)."""
    out = [] if out is None else out

    def text(s):
        if s:
            if out and out[-1]["t"] == "text":
                out[-1]["s"] += s
            else:
                out.append({"t": "text", "s": s})
    text(el.text)
    for c in el:
        tag = c.tag if isinstance(c.tag, str) else ""
        if tag == "xref":
            out.append({"t": "fnref", "rid": c.get("rid") or "", "s": txt(c) or "*"})
        elif tag == "named-content" and c.get("content-type") == "quran":
            out.append({"t": "quran", "id": c.get("id") or "", "href": c.get(XLINK + "href") or "",
                        "title": c.get(XLINK + "title") or "", "match": c.get("specific-use") or "",
                        "inl": _inline(c)})
        elif tag in ("bold", "italic", "sup", "sub"):
            out.append({"t": {"bold": "b", "italic": "i"}.get(tag, tag), "inl": _inline(c)})
        elif tag in ("ext-link", "uri"):
            out.append({"t": "link", "href": c.get(XLINK + "href") or "", "inl": _inline(c)})
        elif tag == "inline-formula":
            out.append(dict(t="math", id=c.get("id") or "", **_math(c)))
        elif tag:
            for r in _inline(c):
                if r["t"] == "text":
                    text(r["s"])
                else:
                    out.append(r)
        text(c.tail)
    # one space between words, none at the ends
    for r in out:
        if r["t"] == "text":
            r["s"] = re.sub(r"\s+", " ", r["s"])
    if out and out[0]["t"] == "text":
        out[0]["s"] = out[0]["s"].lstrip()
    if out and out[-1]["t"] == "text":
        out[-1]["s"] = out[-1]["s"].rstrip()
    return [r for r in out if r["t"] != "text" or r["s"]]


def mathml_str(el) -> str:
    """A MathML element (mml: prefix in JATS) as plain MathML in its own default namespace, for HTML and EPUB."""
    def copy(e):
        tag = etree.QName(e).localname
        n = etree.Element(f"{{{MML}}}{tag}", nsmap={None: MML} if tag == "math" else None)
        for k, v in e.attrib.items():
            if not k.startswith("{"):
                n.set(k, v)
        n.text = e.text
        for c in e:
            if isinstance(c.tag, str):
                cc = copy(c)
                cc.tail = c.tail
                n.append(cc)
        return n
    return etree.tostring(copy(el), encoding="unicode")


def _math(el) -> dict:
    """An <inline-formula> or <disp-formula>: its MathML, LaTeX, scan crop and the printed symbols (ink)."""
    m = el.find(f".//{{{MML}}}math")
    tex = el.find(".//tex-math")
    g = el.find(".//graphic")
    return dict(mathml=mathml_str(m) if m is not None else "",
                tex=(tex.text or "").strip() if tex is not None else "",
                graphic=g.get(XLINK + "href") if g is not None else "",
                dir=m.get("dir") if m is not None else None, ink=math_ink(m) if m is not None else "")


def math_ink(m) -> str:
    """The printed symbols of a formula in reading order (mi/mn/mo/mtext), for the word checks."""
    return " ".join((e.text or "").strip() for e in m.iter() if isinstance(e.tag, str)
                    and etree.QName(e).localname in ("mi", "mn", "mo", "mtext") and (e.text or "").strip())


def _table(tw) -> dict:
    """A <table-wrap>: label, caption, and the XHTML table's rows, cells in reading order (the first cell of a
    row is the rightmost on the page; dir="rtl" puts it there)."""
    rows = []
    for sec in ("thead", "tbody", "tfoot", None):
        trs = tw.findall(f".//table/{sec}/tr") if sec else tw.findall(".//table/tr")
        for tr in trs:
            cells = []
            for c in tr:
                if c.tag in ("th", "td"):
                    cells.append(dict(th=c.tag == "th", id=c.get("id"), colspan=int(c.get("colspan") or 1),
                                      rowspan=int(c.get("rowspan") or 1), scope=c.get("scope"), inl=_inline(c),
                                      align=c.get("align"), blocks=[]))
            rows.append(dict(head=sec == "thead", foot=sec == "tfoot", cells=cells))
    cap = tw.find("caption")
    capp = cap.find("p") if cap is not None else None
    g = tw.find("alternatives/graphic")
    if g is None:
        g = tw.find("graphic")
    return dict(label=txt(tw.find("label")),
                caption=_inline(capp if capp is not None else cap) if cap is not None else [],
                rows=rows, graphic=g.get(XLINK + "href") if g is not None else "",
                foot=txt(tw.find("table-wrap-foot")),
                caption_id=(capp.get("id") if capp is not None else None) or (cap.get("id") if cap is not None
                                                                             else None))


def _fig(fg) -> dict:
    """A <fig>: label, caption, and the picture (a crop of the scan) it holds."""
    cap = fg.find("caption")
    capp = cap.find("p") if cap is not None else None
    g = fg.find(".//graphic")
    return dict(label=txt(fg.find("label")),
                caption=_inline(capp if capp is not None else cap) if cap is not None else [],
                graphic=g.get(XLINK + "href") if g is not None else "",
                caption_id=(capp.get("id") if capp is not None else None) or (cap.get("id") if cap is not None
                                                                             else None))


def _lang(el):
    v = el.get(XML_LANG)
    return v if v and v != "ar" else None


def _meta(fr) -> dict:
    m = {}
    for cm in fr.iter("custom-meta"):
        m.setdefault(txt(cm.find("meta-name")), []).append((txt(cm.find("meta-value")), cm.get("id")))
    return m


def read_front(art) -> dict:
    fr = art.find("front")
    f = dict(title="", title_id=None, subtitle="", alt_title="", trans_titles=[], authors=[], journal="",
             journal_en="", journal_id="", issn=[], publisher="", publisher_loc="", year="", calendar="gregorian",
             date="", volume="", issue="", fpage="", lpage="", page_count=0, abstracts=[], keywords=[], doi="",
             record="", article_id="", subjects=[], article_type=art.get("article-type") or "", meta={},
             lang=art.get(XML_LANG) or "ar", front_blocks=[])
    if fr is None:
        return f
    jm, am = fr.find("journal-meta"), fr.find("article-meta")
    f["meta"] = _meta(fr)
    if jm is not None:
        f["journal"] = txt(jm.find(".//journal-title"))
        f["journal_en"] = txt(jm.find(".//trans-title"))
        f["journal_id"] = txt(jm.find("journal-id"))
        f["issn"] = [txt(i) for i in jm.findall("issn")]
        f["publisher"] = txt(jm.find(".//publisher-name"))
        f["publisher_loc"] = txt(jm.find(".//publisher-loc"))
    if am is None:
        return f
    for aid in am.findall("article-id"):
        t = aid.get("pub-id-type")
        if t == "doi":
            f["doi"] = txt(aid)
        elif aid.get("custom-type") == "mandumah-record":
            f["record"] = txt(aid)
        elif t == "other":
            f["article_id"] = txt(aid)
    for sg in am.iter("subj-group"):
        for s in sg.findall("subject"):
            f["subjects"].append(dict(text=txt(s), type=sg.get("subj-group-type"), lang=sg.get(XML_LANG),
                                      id=s.get("id")))
    tg = am.find("title-group")
    if tg is not None:
        at = tg.find("article-title")
        f["title"], f["title_id"] = txt(at), (at.get("id") if at is not None else None)
        f["title_inl"] = _inline(at) if at is not None else []
        f["subtitle"] = txt(tg.find("subtitle"))
        f["alt_title"] = txt(tg.find("alt-title"))
        for tt in tg.iter("trans-title-group"):
            f["trans_titles"].append(dict(lang=tt.get(XML_LANG), title=txt(tt.find("trans-title")),
                                          subtitle=txt(tt.find("trans-subtitle"))))
    for c in am.iter("contrib"):
        a = dict(id=c.get("id"), role=txt(c.find("role")), type=c.get("contrib-type") or "author",
                 printed=txt(c.find(".//string-name")), name_ar="", name_en="", prefix="",
                 aff=[txt(x) for x in c.findall("aff")], collab=txt(c.find("collab")))
        for nm in c.iter("name"):
            full = " ".join(filter(None, (txt(nm.find("given-names")), txt(nm.find("surname")))))
            if nm.get(XML_LANG) == "en":
                a["name_en"] = full
            else:
                a["name_ar"] = full
                a["prefix"] = txt(nm.find("prefix"))
        a["display"] = a["printed"] or " ".join(filter(None, (a["prefix"], a["name_ar"]))) or a["collab"] \
            or a["name_en"]
        f["authors"].append(a)
    pd = am.find("pub-date")
    if pd is not None:
        f["year"], f["calendar"] = txt(pd.find("year")), pd.get("calendar") or "gregorian"
        f["date"] = txt(pd.find("string-date")) or f["year"]
    for k in ("volume", "issue", "fpage", "lpage"):
        f[k] = txt(am.find(k))
    pc = am.find(".//page-count")
    f["page_count"] = int(pc.get("count")) if pc is not None else 0
    for ab in list(am.findall("abstract")) + list(am.findall("trans-abstract")):
        f["abstracts"].append(dict(lang=ab.get(XML_LANG) or "ar", type=ab.get("abstract-type") or "",
                                   paras=[txt(p) for p in ab.findall(".//p")] or [txt(ab)]))
    for kg in am.findall("kwd-group"):
        f["keywords"].append(dict(lang=kg.get(XML_LANG) or "ar", type=kg.get("kwd-group-type") or "",
                                  kwds=[txt(k) for k in kg.findall("kwd")]))
    for name in ("front-matter-block",):
        for v, i in f["meta"].get(name, []):
            if i:
                f["front_blocks"].append(dict(id=i, text=v))
    return f


def read_body(art) -> tuple[list, list, list, list]:
    body, notes, refs, verses = [], [], [], []

    def node(kind, el, level=0):
        return Node(kind, _inline(el), el.get("id"), level, _lang(el), el.get("content-type"))

    def walk(src, depth):
        for el in src:
            tag = el.tag if isinstance(el.tag, str) else ""
            if tag == "sec":
                walk(el, depth + 1)
            elif tag == "title":
                body.append(node("heading", el, max(1, depth)))
            elif tag == "p":
                body.append(node("p", el))
            elif tag == "disp-formula":
                body.append(Node("formula", [], el.get("id"), extra=dict(label=txt(el.find("label")), **_math(el))))
            elif tag == "table-wrap":
                body.append(Node("table", [], el.get("id"), extra=_table(el)))
            elif tag == "fig":
                body.append(Node("figure", [], el.get("id"), extra=_fig(el)))
            elif tag == "list-item":             # a list item: its printed label (bullet, number) opens its text
                lab = txt(el.find("label"))
                first = True
                for p in el:
                    if isinstance(p.tag, str) and p.tag == "p":
                        n = node("p", p)
                        if first and lab:
                            n.inl.insert(0, {"t": "text", "s": lab + " "})
                            n.extra["list_label"] = lab
                        first = False
                        body.append(n)
                    elif isinstance(p.tag, str) and p.tag != "label":
                        walk([p], depth)
            elif tag:
                walk(el, depth)
    b = art.find("body")
    if b is not None:
        walk(b, 0)
    back = art.find("back")
    if back is not None:
        for g in back:
            tag = g.tag if isinstance(g.tag, str) else ""
            if tag == "fn-group":
                for fn in g.iter("fn"):
                    pm = re.match(r"fn-p(\d+)-", fn.get("id") or "")
                    notes.append(Note(fn.get("id") or "", txt(fn.find("label")),
                                      [node("p", p) for p in fn.findall("p")], int(pm[1]) if pm else None))
            elif tag == "ref-list":
                t = g.find("title")
                if t is not None:
                    n = node("ref-head", t)
                    n.id = n.id or g.get("id")
                    refs.append(n)
                elif g.get("id") and BLOCK_ID.match(g.get("id")):
                    refs.append(Node("ref-head", [], g.get("id")))
                for r in g.iter("ref"):
                    for mc in r:
                        if isinstance(mc.tag, str):
                            refs.append(node("ref", mc))
            elif tag == "notes" and g.get("notes-type") == "quran-quotations":
                for p in g.findall("p"):
                    ext, nc = p.find("ext-link"), p.find("named-content")
                    verses.append(dict(id=p.get("id") or "", href=ext.get(XLINK + "href") if ext is not None else "",
                                       ref=txt(ext), verse=txt(nc), note=(nc.tail or "").strip(" —")
                                       if nc is not None else ""))
    return body, notes, refs, verses


# ---------------------------------------------------------------------------------------------- the article

class Edition:
    def __init__(self, stem, jats_path, alto_path, pdf_path, front, body, notes, refs, verses, pages, blocks):
        self.stem, self.jats_path, self.alto_path, self.pdf_path = stem, jats_path, alto_path, pdf_path
        self.front, self.body, self.notes, self.refs, self.verses = front, body, notes, refs, verses
        self.pages, self.blocks = pages, blocks
        self._link()

    def nodes(self):
        """Every node with ink, in reading order: body, notes, references."""
        yield from self.body
        for n in self.notes:
            yield from n.paras
        yield from self.refs

    def _link(self):
        """Tie each JATS element to the ALTO blocks whose words it holds, and say what each block became."""
        pointing = {}
        for b in self.blocks.values():
            pointing.setdefault(b.target or b.id, []).append(b.id)
        for k, lst in pointing.items():          # a block answers for itself first
            if k in lst:
                lst.remove(k)
                lst.insert(0, k)
        kind_of = {"heading": "heading", "p": "p", "ref-head": "ref", "ref": "ref", "formula": "formula"}
        for n in self.body + self.refs:
            if n.kind == "figure":               # the picture's own block, then its caption's
                n.blocks = [b for b in pointing.get(n.id, [n.id]) if b in self.blocks]
                for bid in n.blocks:
                    self.blocks[bid].kind = self.blocks[bid].kind or "figure"
                cid = n.extra.get("caption_id")
                if cid:
                    cb = [b for b in pointing.get(cid, [cid]) if b in self.blocks]
                    for bid in cb:
                        self.blocks[bid].kind = self.blocks[bid].kind or "caption"
                    n.blocks += cb
                continue
            if n.kind == "table":                # the table's own block, then each cell's
                n.blocks = [b for b in pointing.get(n.id, [n.id]) if b in self.blocks]
                for r in n.extra["rows"]:
                    for c in r["cells"]:
                        c["blocks"] = [b for b in pointing.get(c.get("id"), [c.get("id")]) if b in self.blocks]
                        n.blocks += c["blocks"]
                cid = n.extra.get("caption_id")         # the caption's own block (its <p id>), kind "caption"
                if cid:
                    cb = [b for b in pointing.get(cid, [cid]) if b in self.blocks]
                    for bid in cb:
                        self.blocks[bid].kind = self.blocks[bid].kind or "caption"
                    n.blocks = cb + n.blocks
                for bid in n.blocks:
                    self.blocks[bid].kind = self.blocks[bid].kind or ("table" if bid == n.id else "cell")
                continue
            if n.id and BLOCK_ID.match(n.id):
                n.blocks = [b for b in pointing.get(base_id(n.id), [base_id(n.id)]) if b in self.blocks]
                for bid in n.blocks:
                    self.blocks[bid].kind = self.blocks[bid].kind or kind_of[n.kind]
        for note in self.notes:
            for p in note.paras:
                if p.id and BLOCK_ID.match(p.id):
                    p.blocks = list(pointing.get(base_id(p.id), [base_id(p.id)]))
                    for bid in p.blocks:
                        if bid in self.blocks:
                            self.blocks[bid].kind = self.blocks[bid].kind or "fn"
        f = self.front
        if f.get("title_id"):
            for bid in pointing.get(base_id(f["title_id"]), [base_id(f["title_id"])]):
                if bid in self.blocks:
                    self.blocks[bid].kind = "title"
        for a in f["authors"]:
            if a.get("id") and BLOCK_ID.match(a["id"]):
                for bid in pointing.get(base_id(a["id"]), [base_id(a["id"])]):
                    if bid in self.blocks:
                        self.blocks[bid].kind = self.blocks[bid].kind or "author"
        for s in f["subjects"]:
            if s.get("id") and BLOCK_ID.match(s["id"]) and s["id"] in self.blocks:
                self.blocks[s["id"]].kind = self.blocks[s["id"]].kind or "rubric"
        for fb in f["front_blocks"]:
            if fb["id"] in self.blocks:
                self.blocks[fb["id"]].kind = self.blocks[fb["id"]].kind or "front"
        for b in self.blocks.values():
            if not b.kind:
                b.kind = "furniture" if b.furniture else "stray"

    def regions(self, node_or_ids) -> list[tuple[int, tuple]]:
        """Where on the scan: one box per page (the union of the node's blocks there), in reading order."""
        ids = node_or_ids.blocks if isinstance(node_or_ids, Node) else list(node_or_ids)
        per = {}
        for bid in ids:
            b = self.blocks.get(bid)
            if b is None:
                continue
            x, y, w, h = b.box
            if b.page in per:
                X0, Y0, X1, Y1 = per[b.page]
                per[b.page] = (min(X0, x), min(Y0, y), max(X1, x + w), max(Y1, y + h))
            else:
                per[b.page] = (x, y, x + w, y + h)
        return [(p, (x0, y0, x1 - x0, y1 - y0)) for p, (x0, y0, x1, y1) in per.items()]

    def ink_words(self, rendered_only=True) -> list[Word]:
        """The ALTO words a reading edition must carry: those of blocks the JATS places in the article (body,
        notes, references, title, authors, rubric, front-matter blocks). Furniture and stray blocks are left out
        by the master itself."""
        out = []
        for n in sorted(self.pages):
            for b in self.pages[n].blocks:
                if not rendered_only or b.kind not in ("furniture", "stray"):
                    out.extend(b.words)
        return out

    @property
    def page_numbers(self):
        return sorted(self.pages)


def load(jats_path, alto_path=None, pdf_path=None) -> Edition:
    jats_path = Path(jats_path)
    stem = jats_path.name[:-len(".jats.xml")]
    alto_path = Path(alto_path) if alto_path else jats_path.with_name(f"{stem}.alto.xml")
    pdf_path = Path(pdf_path) if pdf_path else jats_path.with_name(f"{stem}.pdf")
    art = etree.parse(str(jats_path), _parser()).getroot()
    front = read_front(art)
    body, notes, refs, verses = read_body(art)
    pages, blocks = read_alto(alto_path)
    if pdf_path.exists():
        import pymupdf
        with pymupdf.open(str(pdf_path)) as d:
            for n, p in pages.items():
                if n - 1 < len(d):
                    r = d[n - 1].rect
                    p.pt_w, p.pt_h = r.width, r.height
    for p in pages.values():                     # no PDF: ALTO pixels taken as 300 dpi
        if not p.pt_w:
            p.pt_w, p.pt_h = p.w * 72 / 300, p.h * 72 / 300
    return Edition(stem, jats_path, alto_path, pdf_path if pdf_path.exists() else None, front, body, notes, refs,
                   verses, pages, blocks)
