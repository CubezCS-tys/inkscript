"""The reading edition: one HTML page per article, written from its master files only (experiment 35).

    write_html(ed, out_root) -> stats         <out_root>/<id>/<id>.html, its page images in <id>/scan/, the
                                              formula/table crops in <id>/crops/, the fonts in <out_root>/fonts/
    Renderer(ed, mode="html"|"epub")          the article as (X)HTML markup; epub.py uses the same renderer

What the page holds: the catalogue front matter (title, authors and affiliations, journal, volume, issue, date
with the Hijri year marked, printed pages, ISSN, DOI, abstracts each in its own language, keywords, Mandumah's
record), the text in reading order (headings, paragraphs, tables right to left, formulas as MathML with their
LaTeX as an annotation), Quran quotations marked with a link to the verse, notes linked both ways, references,
the verses quoted, and "about this edition" (where every part came from). Every paragraph, heading, note, table
and formula has a small button that opens its ink on the scan: the page image clipped by an SVG viewBox in ALTO
pixels (one image per page, loaded only when asked for).

The markup is written as well-formed XHTML (every element closed, MathML in its namespace), so the same string
is a valid HTML5 page and, wrapped differently, an EPUB content document. No request leaves the folder: fonts
are bundled (OFL), the CSS and the few lines of script are inline.
"""
from __future__ import annotations

import json
import re
import shutil
from html import escape
from pathlib import Path

from lxml import etree

from .model import MML, plain

DIGITS_AR = str.maketrans("0123456789", "٠١٢٣٤٥٦٧٨٩")

# The reading face: Noto Naskh Arabic (plain, made for screens) for the text, Markazi Text for the title and
# headings (and for Latin letters, which Noto Naskh Arabic lacks). Both SIL OFL.
FONTS = [("naskh", "regular", "Naskh", 400), ("naskh", "bold", "Naskh", 700),
         ("markazi", "regular", "Markazi", 400), ("markazi", "bold", "Markazi", 700)]
# Arabic (all blocks), Latin-1, general punctuation (incl. the bidi marks), letterlike, arrows, maths operators
SUBSET = ([*range(0x20, 0x7F), *range(0xA0, 0x180), *range(0x600, 0x700), *range(0x750, 0x780),
           *range(0x8A0, 0x900), *range(0xFB50, 0xFE00), *range(0xFE70, 0xFF00), *range(0x2000, 0x2070),
           *range(0x2100, 0x2200), *range(0x2200, 0x2300), 0x25CC, 0x2013, 0x2014])


def a(s) -> str:
    return escape(str(s or ""), quote=True)


def t(s) -> str:
    return escape(str(s or ""), quote=False)


# ---------------------------------------------------------------------------------------------- fonts

def bundle_fonts(fonts_dir: Path) -> list[dict]:
    """Subset WOFF copies of the reading fonts into fonts_dir (once); returns [{family, weight, file}]."""
    from . import fonts as F
    fonts_dir.mkdir(parents=True, exist_ok=True)
    out = []
    for name, weight, fam, w in FONTS:
        dest = fonts_dir / f"{fam}-{weight}.woff"
        if not dest.exists():
            try:
                src = F.font_path(name, weight)
            except Exception:
                continue
            _subset(src, dest)
        out.append(dict(family=fam, weight=w, file=dest.name, name=name))
    for name in {f[0] for f in FONTS}:
        lic = F.licence_path(name)
        d = fonts_dir / f"LICENCE-{name}.txt"
        if lic and not d.exists():
            shutil.copyfile(lic, d)
    return out


def _subset(src: Path, dest: Path):
    from fontTools import subset
    opts = subset.Options()
    opts.layout_features = ["*"]
    opts.name_IDs = ["*"]
    opts.name_languages = ["*"]
    opts.notdef_outline = True
    opts.hinting = False
    opts.flavor = "woff"
    f = subset.load_font(str(src), opts)
    s = subset.Subsetter(opts)
    s.populate(unicodes=SUBSET)
    s.subset(f)
    tmp = dest.with_suffix(".part")
    subset.save_font(f, str(tmp), opts)
    tmp.replace(dest)


def font_css(fonts: list[dict], prefix: str) -> str:
    return "\n".join(f"@font-face{{font-family:'{f['family']}';font-weight:{f['weight']};font-style:normal;"
                     f"font-display:swap;src:url('{prefix}{f['file']}') format('woff')}}" for f in fonts)


# ---------------------------------------------------------------------------------------------- the renderer

HEAD_LABEL = {"ar": "الملخص", "en": "Abstract", "fr": "Résumé", "de": "Zusammenfassung"}
KWD_LABEL = {"ar": "الكلمات المفتاحية", "en": "Keywords", "fr": "Mots-clés"}


def _dir(lang):
    if not lang or lang == "ar":
        return None
    return "auto" if lang == "und" else "ltr"


class Renderer:
    def __init__(self, ed, mode: str = "html", crops: dict | None = None):
        self.ed, self.mode = ed, mode
        self.crops = crops or {}         # node id -> relative path of its scan crop (formulas, tables)
        self.ids = set()
        self.refcount = {}               # note id -> markers seen
        self.notes = {n.id: n for n in ed.notes}
        self.verse = {}                  # tanzil href -> verse text
        for v in ed.verses:
            if v.get("href"):
                self.verse.setdefault(v["href"], v.get("verse", ""))

    def uid(self, base: str) -> str:
        base = re.sub(r"[^A-Za-z0-9_.-]", "-", base or "x")
        if not re.match(r"[A-Za-z_]", base):
            base = "x" + base
        i, k = base, 1
        while i in self.ids:
            k += 1
            i = f"{base}-{k}"
        self.ids.add(i)
        return i

    # -------------------------------------------------------------- inline
    def inl(self, runs) -> str:
        out = []
        for ri, r in enumerate(runs):
            k = r["t"]
            if k == "text":
                out.append(t(r["s"]))
            elif k == "fnref":
                rid = r["rid"]
                if rid not in self.notes:          # a marker whose note the master does not hold: text only
                    out.append(f'<span class="fnref">{t(r["s"])}</span>')
                    continue
                n = self.refcount.get(rid, 0) + 1
                self.refcount[rid] = n
                rid_id = "ref-" + rid + ("" if n == 1 else f"-{n}")
                self.ids.add(rid_id)
                ep = ' epub:type="noteref" role="doc-noteref"' if self.mode == "epub" else ' role="doc-noteref"'
                out.append(f'<a class="fnref" id="{a(rid_id)}" href="#n-{a(rid)}"{ep}>{t(r["s"])}</a>')
            elif k == "quran":
                cls = "quran" + ("" if r.get("match") == "matches-verse" else " differs")
                verse = self.verse.get(r.get("href"), "")
                tip = f' title="{a(verse)}"' if verse else ""
                # one badge for a quotation the master holds in several pieces (split by punctuation)
                nxt = next((x for x in runs[ri + 1:] if not (x["t"] == "text" and len(x["s"].strip()) <= 3)),
                           None)
                same = nxt is not None and nxt["t"] == "quran" and nxt.get("href") == r.get("href")
                out.append(f'<span class="{cls}"{tip}>{self.inl(r["inl"])}</span>{"" if same else self.badge(r)}')
            elif k in ("b", "i", "sup", "sub"):
                out.append(f"<{k}>{self.inl(r['inl'])}</{k}>")
            elif k == "link":
                out.append(f'<a href="{a(r["href"])}">{self.inl(r["inl"])}</a>')
            elif k == "math":
                out.append(self.math(r, block=False))
        return "".join(out)

    def badge(self, r) -> str:
        name, _, ref = (r.get("title") or "").rpartition(" ")
        ref = ref or (r.get("href") or "").rsplit("#", 1)[-1]
        return (f'<a class="qref" href="{a(r.get("href"))}" title="{a(r.get("title") or "")}">'
                f'{t(name)}{" " if name else ""}<bdi dir="ltr">{t(ref)}</bdi></a>')

    def math(self, m, block: bool) -> str:
        """MathML as written in the master, its LaTeX kept as an annotation (and alttext); a formula with no
        MathML falls back to its LaTeX as code, then to its scan crop."""
        mml = m.get("mathml") or ""
        if not mml:
            if m.get("tex"):
                return f'<code class="tex" dir="ltr">{t(m["tex"])}</code>'
            return ""
        try:
            el = etree.fromstring(mml)
        except etree.XMLSyntaxError:
            return f'<code class="tex" dir="ltr">{t(m.get("tex"))}</code>'
        el.set("display", "block" if block else "inline")
        if m.get("tex"):
            el.set("alttext", m["tex"])
            kids = [c for c in el]
            sem = etree.SubElement(el, f"{{{MML}}}semantics")
            row = etree.SubElement(sem, f"{{{MML}}}mrow")
            for c in kids:
                row.append(c)
            if el.text and el.text.strip():
                row.text = el.text
            el.text = None
            ann = etree.SubElement(sem, f"{{{MML}}}annotation", encoding="application/x-tex")
            ann.text = m["tex"]
        return etree.tostring(el, encoding="unicode")

    # -------------------------------------------------------------- the original on the scan
    def og(self, node_or_ids, crop: str | None = None) -> str:
        if self.mode != "html":
            return ""
        regs = self.ed.regions(node_or_ids)
        if not regs:
            return ""
        spec = ";".join(f"{p}:{int(x)},{int(y)},{int(w)},{int(h)}" for p, (x, y, w, h) in regs)
        extra = f' data-crop="{a(crop)}"' if crop else ""
        return (f'<button type="button" class="og" data-r="{spec}"{extra} title="الأصل في الصفحة الممسوحة '
                f'(view the original)" aria-label="الأصل"></button>')

    def block_attrs(self, n, cls=None) -> str:
        at = []
        if n.id:
            at.append(f'id="{a(self.uid("j-" + n.id))}"')
        c = [cls] if cls else []
        if n.ctype:
            c.append(n.ctype)
        if c:
            at.append(f'class="{a(" ".join(c))}"')
        d = _dir(n.lang)
        if d:
            at.append(f'lang="{a(n.lang)}" dir="{d}"' if n.lang != "und" else f'dir="{d}"')
        return (" " + " ".join(at)) if at else ""

    # -------------------------------------------------------------- blocks
    def node(self, n) -> str:
        if n.kind == "heading":
            h = min(6, n.level + 1)
            return f"<h{h}{self.block_attrs(n, 'heading')}>{self.inl(n.inl)}{self.og(n)}</h{h}>"
        if n.kind == "p":
            if not n.inl:
                return ""
            return f"<p{self.block_attrs(n)}>{self.inl(n.inl)}{self.og(n)}</p>"
        if n.kind == "formula":
            x = n.extra
            lab = f'<span class="eqlabel">{t(x.get("label"))}</span>' if x.get("label") else ""
            body = self.math(x, block=True)
            crop = self.crops.get(n.id)
            if not body and crop:
                body = f'<img class="crop" src="{a(crop)}" alt="{a(x.get("tex") or "formula")}"/>'
            return (f'<div{self.block_attrs(n, "formula")}><div class="eq">{body}</div>{lab}'
                    f'{self.og(n, crop)}</div>')
        if n.kind == "table":
            return self.table(n)
        if n.kind == "figure":
            x = n.extra
            crop = self.crops.get(n.id)
            cap = self.inl(x.get("caption") or [])
            lab = f'<span class="flabel">{t(x.get("label"))}</span> ' if x.get("label") else ""
            alt = plain(x.get("caption") or []) or "picture"
            img = f'<img class="fig" src="{a(crop)}" alt="{a(alt)}"/>' if crop else ""
            fc = f"<figcaption>{lab}{cap}</figcaption>" if (cap or lab) else ""
            return f'<figure{self.block_attrs(n, "figure")}>{img}{fc}{self.og(n, crop)}</figure>' if (img or fc) else ""
        return ""

    def table(self, n) -> str:
        x = n.extra
        cap = ""
        if x.get("label") or x.get("caption"):
            lab = f'<span class="tlabel">{t(x.get("label"))}</span> ' if x.get("label") else ""
            cap = f"<caption>{lab}{self.inl(x.get('caption') or [])}{self.og(n, self.crops.get(n.id))}</caption>"
        parts = {"head": [], "body": [], "foot": []}
        for r in x["rows"]:
            cells = []
            for c in r["cells"]:
                tag = "th" if c["th"] else "td"
                at = []
                if c.get("id"):
                    at.append(f'id="{a(self.uid("j-" + c["id"]))}"')
                if c.get("colspan", 1) > 1:
                    at.append(f'colspan="{c["colspan"]}"')
                if c.get("rowspan", 1) > 1:
                    at.append(f'rowspan="{c["rowspan"]}"')
                if c.get("scope") and self.mode == "html":
                    at.append(f'scope="{a(c["scope"])}"')
                cells.append(f"<{tag}{(' ' + ' '.join(at)) if at else ''}>{self.inl(c['inl'])}</{tag}>")
            parts["head" if r["head"] else "foot" if r["foot"] else "body"].append(f"<tr>{''.join(cells)}</tr>")
        rows = ""
        if parts["head"]:
            rows += f"<thead>{''.join(parts['head'])}</thead>"
        if parts["body"]:
            rows += f"<tbody>{''.join(parts['body'])}</tbody>"
        if parts["foot"]:
            rows += f"<tfoot>{''.join(parts['foot'])}</tfoot>"
        og = "" if cap else self.og(n, self.crops.get(n.id))
        foot = f'<p class="tfoot">{t(x.get("foot"))}</p>' if x.get("foot") else ""
        return (f'<div{self.block_attrs(n, "tablewrap")}><div class="tscroll"><table dir="rtl">{cap}{rows}'
                f'</table></div>{og}{foot}</div>')

    # -------------------------------------------------------------- front matter
    def front(self) -> str:
        f, ed = self.ed.front, self.ed
        o = ['<header class="front">']
        line = []
        if f.get("journal"):
            line.append(f'<span class="journal">{t(f["journal"])}</span>')
        vi = []
        if f.get("volume"):
            vi.append(f"المجلد {t(f['volume'])}")
        if f.get("issue"):
            vi.append(f"العدد {t(f['issue'])}")
        if vi:
            line.append(f"<span>{'، '.join(vi)}</span>")
        if f.get("date"):
            hijri = " هـ" if f.get("calendar") == "islamic" and "هـ" not in f["date"] else ""
            line.append(f"<span>{t(f['date'])}{hijri}</span>")
        if line:
            o.append(f'<p class="masthead">{" · ".join(line)}</p>')
        rub = [s for s in f.get("subjects", []) if s.get("id")]
        for s in rub:
            n = _ids_node(s["id"], self.ed)
            o.append(f'<p class="rubric">{t(s["text"])}{self.og(n)}</p>')
        title_inl = f.get("title_inl") or ([{"t": "text", "s": f.get("title", "")}] if f.get("title") else [])
        tnode = _ids_node(f.get("title_id"), self.ed)
        o.append(f'<h1 class="title">{self.inl(title_inl)}{self.og(tnode) if f.get("title_id") else ""}</h1>')
        if f.get("subtitle"):
            o.append(f'<p class="subtitle">{t(f["subtitle"])}</p>')
        for tt in f.get("trans_titles", []):
            if tt.get("title"):
                lg = tt.get("lang") or "en"
                sub = f": {t(tt['subtitle'])}" if tt.get("subtitle") else ""
                o.append(f'<p class="trans-title" lang="{a(lg)}" dir="ltr">{t(tt["title"])}{sub}</p>')
        if f.get("authors"):
            o.append('<ul class="authors">')
            for au in f["authors"]:
                nm = t(au.get("display"))
                en = (f' <span class="en" lang="en" dir="ltr">{t(au["name_en"])}</span>'
                      if au.get("name_en") else "")
                aff = "".join(f'<span class="aff">{t(x)}</span>' for x in au.get("aff", []) if x)
                og = self.og(_ids_node(au["id"], self.ed)) if au.get("id") else ""
                o.append(f'<li><span class="name">{nm}</span>{og}{en}{aff}</li>')
            o.append("</ul>")
        shown = {" ".join(x.split()) for au in f.get("authors", [])
                 for x in [au.get("display") or ""] + list(au.get("aff", []))}
        for fb in f.get("front_blocks", []):
            if " ".join(fb["text"].split()) in shown:      # the same line already shown as an affiliation
                continue
            o.append(f'<p class="printed">{t(fb["text"])}{self.og(_ids_node(fb["id"], self.ed))}</p>')
        facts = []
        if f.get("journal"):
            j = t(f["journal"]) + (f' (<bdi lang="en" dir="ltr">{t(f["journal_en"])}</bdi>)'
                                   if f.get("journal_en") else "")
            facts.append(("المجلة", j))
        if f.get("publisher"):
            facts.append(("الناشر", t(f["publisher"]) + (f"، {t(f['publisher_loc'])}" if f.get("publisher_loc")
                                                          else "")))
        for i in f.get("issn", []):
            facts.append(("ISSN", f'<bdi dir="ltr">{t(i)}</bdi>'))
        if f.get("volume"):
            facts.append(("المجلد", t(f["volume"])))
        if f.get("issue"):
            facts.append(("العدد", t(f["issue"])))
        if f.get("year"):
            y = t(f["year"]) + (" هـ" if f.get("calendar") == "islamic" else " م")
            facts.append(("السنة", y))
        if f.get("fpage"):
            pp = f"{t(f['fpage'])}–{t(f['lpage'])}" if f.get("lpage") else t(f["fpage"])
            facts.append(("الصفحات", f'<bdi dir="ltr">{pp}</bdi>'))
        if f.get("page_count"):
            facts.append(("عدد الصفحات", t(f["page_count"])))
        if f.get("doi"):
            facts.append(("DOI", f'<a dir="ltr" href="https://doi.org/{a(f["doi"])}">{t(f["doi"])}</a>'))
        if f.get("record"):
            facts.append(("سجل المنظومة", f'<bdi dir="ltr">{t(f["record"])}</bdi>'))
        if f.get("article_id"):
            facts.append(("المعرّف", f'<bdi dir="ltr">{t(f["article_id"])}</bdi>'))
        if facts:
            wide = {"المجلة", "الناشر", "DOI"}
            rows = [('<div class="wide">' if k in wide else "<div>") + f"<dt>{k}</dt><dd>{v}</dd></div>"
                    for k, v in facts]
            o.append('<dl class="facts">' + "".join(rows) + "</dl>")
        for ab in f.get("abstracts", []):
            lg = ab.get("lang") or "ar"
            d = "" if lg == "ar" else f' lang="{a(lg)}" dir="ltr"'
            ps = "".join(f"<p>{t(p)}</p>" for p in ab.get("paras", []) if p)
            o.append(f'<section class="abstract"{d}><h2>{HEAD_LABEL.get(lg, "Abstract")}</h2>{ps}</section>')
        for kg in f.get("keywords", []):
            if not kg.get("kwds"):
                continue
            lg = kg.get("lang") or "ar"
            d = "" if lg == "ar" else f' lang="{a(lg)}" dir="ltr"'
            ks = "".join(f"<li>{t(k)}</li>" for k in kg["kwds"])
            o.append(f'<div class="kwds"{d}><span class="lab">{KWD_LABEL.get(lg, "Keywords")}</span>'
                     f"<ul>{ks}</ul></div>")
        o.append("</header>")
        return "".join(o)

    # -------------------------------------------------------------- back matter
    def notes_html(self) -> str:
        if not self.ed.notes:
            return ""
        o = ['<section class="notes" id="notes"><h2>الهوامش</h2>']
        for n in self.ed.notes:
            nid = "n-" + n.id
            self.ids.add(nid)
            back = f'<a class="back" href="#ref-{a(n.id)}" title="العودة إلى موضع الإحالة">{t(n.label or "•")}</a>'
            if n.id not in self.refcount:
                back = f'<span class="back">{t(n.label or "•")}</span>'
            pg = (f'<span class="npage">ص <bdi>{str(n.page).translate(DIGITS_AR)}</bdi></span>'
                  if n.page else "")
            paras = "".join(f"<p{self.block_attrs(p)}>{self.inl(p.inl)}{self.og(p)}</p>" for p in n.paras if p.inl)
            if self.mode == "epub":
                o.append(f'<aside epub:type="footnote" role="doc-footnote" id="{a(nid)}" class="note">'
                         f'<div class="nl">{back}{pg}</div><div class="nb">{paras}</div></aside>')
            else:
                o.append(f'<div class="note" id="{a(nid)}" role="doc-footnote"><div class="nl">{back}{pg}</div>'
                         f'<div class="nb">{paras}</div></div>')
        o.append("</section>")
        return "".join(o)

    def refs_html(self) -> str:
        if not self.ed.refs:
            return ""
        o = ['<section class="refs" id="refs">']
        if not any(r.kind == "ref-head" and r.inl for r in self.ed.refs[:1]):
            o.append("<h2>المراجع</h2>")
        open_list = False
        for r in self.ed.refs:
            if r.kind == "ref-head":
                if open_list:
                    o.append("</ul>")
                    open_list = False
                if r.inl:
                    o.append(f"<h3{self.block_attrs(r, 'heading')}>{self.inl(r.inl)}{self.og(r)}</h3>")
            else:
                if not open_list:
                    o.append('<ul class="reflist">')
                    open_list = True
                o.append(f"<li{self.block_attrs(r)}>{self.inl(r.inl)}{self.og(r)}</li>")
        if open_list:
            o.append("</ul>")
        o.append("</section>")
        return "".join(o)

    def verses_html(self) -> str:
        if not self.ed.verses:
            return ""
        o = ['<section class="verses" id="verses"><h2>الآيات المقتبسة</h2><ul>']
        for v in self.ed.verses:
            name, _, ref = (v.get("ref") or "").rpartition(" ")
            o.append(f'<li><a class="qref" href="{a(v.get("href"))}">{t(name)} <bdi dir="ltr">{t(ref)}</bdi></a> '
                     f'<span class="verse">﴿{t(v.get("verse"))}﴾</span>'
                     + (f' <span class="vnote">{t(v.get("note"))}</span>' if v.get("note") else "") + "</li>")
        o.append("</ul></section>")
        return "".join(o)

    def about_html(self, links: list | None = None) -> str:
        f = self.ed.front
        m = f.get("meta", {})

        def mv(k):
            return (m.get(k) or [("", None)])[0][0]
        rows = [("Generated from", f"the master files {self.ed.stem}.jats.xml (JATS 1.4: the article) and "
                                   f"{self.ed.stem}.alto.xml (ALTO 4.4: every word and its box) by inkscript "
                                   f"edition (experiment 35). Nothing was retyped or edited by hand; the "
                                   f"typeface is new, the words are the ones read off the page.")]
        for k, lab in (("text-source", "Text read by"), ("structure-source", "Structure"),
                       ("catalogue", "Front matter"), ("catalogue-check", "Catalogue check"),
                       ("trust", "Trust marks"), ("quran-quotations", "Quran quotations"),
                       ("corrections", "Corrections")):
            if mv(k):
                rows.append((lab, mv(k)))
        rows.append(("Fonts", "Noto Naskh Arabic (Google) and Markazi Text (Borna Izadpanah), SIL Open Font "
                              "Licence."))
        o = ['<section class="about" id="about" lang="en" dir="ltr"><h2>About this edition</h2><dl>']
        o += [f"<div><dt>{t(k)}</dt><dd>{t(v)}</dd></div>" for k, v in rows]
        o.append("</dl>")
        if links:
            o.append('<p class="links">' + " · ".join(f'<a href="{a(h)}">{t(lab)}</a>' for lab, h in links)
                     + "</p>")
        o.append("</section>")
        return "".join(o)

    # -------------------------------------------------------------- the whole article
    def article(self, links: list | None = None) -> str:
        body = "".join(self.node(n) for n in self.ed.body)
        # notes after the body (their markers must be counted first), references, verses, about
        return (f'<article class="ed" lang="ar" dir="rtl">{self.front()}<div class="body">{body}</div>'
                f"{self.refs_html()}{self.notes_html()}{self.verses_html()}{self.about_html(links)}</article>")


def _ids_node(i, ed):
    """A stand-in node for a front-matter element: the blocks that are it or point at it."""
    from .model import Node, base_id
    n = Node("p", [], i)
    if i and ed is not None:
        n.blocks = [b.id for b in ed.blocks.values() if b.id == base_id(i) or b.target == base_id(i)]
    else:
        n.blocks = [i] if i else []
    return n


# ---------------------------------------------------------------------------------------------- the page

CSS = r"""
:root{--bg:#fbfaf7;--fg:#1d1b18;--mute:#6b665d;--rule:#e2ddd2;--acc:#7a3b12;--quran:#5b4a12;--qbg:#f6efd6;
--card:#fff;--link:#8a3c0c;color-scheme:light dark}
@media (prefers-color-scheme:dark){:root{--bg:#16150f;--fg:#ece7dc;--mute:#a59f92;--rule:#36332b;--acc:#e6a56a;
--quran:#ecd890;--qbg:#2c2614;--card:#201f19;--link:#f0b27a}}
*{box-sizing:border-box}
html{background:var(--bg);color:var(--fg);-webkit-text-size-adjust:100%}
body{margin:0;font-family:'Naskh','Markazi',serif;font-size:1.0625rem;line-height:1.95}
.ed{max-width:40rem;margin:0 auto;padding:1.25rem 1rem 4rem}
a{color:var(--link)}
.front{border-bottom:1px solid var(--rule);padding-bottom:1rem;margin-bottom:1.5rem}
.masthead{font-size:.85rem;color:var(--mute);margin:0 0 1rem}
.masthead .journal{font-weight:700}
.rubric{font-size:.9rem;color:var(--acc);margin:.2rem 0}
h1.title{font-family:'Markazi','Naskh',serif;font-weight:700;font-size:1.9rem;line-height:1.45;margin:.3rem 0 .6rem}
.subtitle{font-family:'Markazi',serif;font-size:1.3rem;margin:.2rem 0}
.trans-title{font-family:'Markazi',serif;font-size:1.05rem;color:var(--mute);margin:.1rem 0 .5rem;line-height:1.4}
.authors{list-style:none;padding:0;margin:.6rem 0}
.authors li{margin:.25rem 0}
.authors .name{font-weight:700}
.authors .en{display:block;font-family:'Markazi',serif;color:var(--mute);font-size:.95rem;line-height:1.3;text-align:right}
.authors .aff{display:block;font-size:.85rem;color:var(--mute);line-height:1.6}
.printed{font-size:.9rem;color:var(--mute);margin:.2rem 0}
.facts{display:grid;grid-template-columns:repeat(auto-fill,minmax(9rem,1fr));gap:.05rem 1.5rem;font-size:.82rem;
margin:.9rem 0;line-height:1.55}
.facts .wide{grid-column:1/-1}
.facts div{display:flex;gap:.4rem}.facts dt{color:var(--mute)}.facts dd{margin:0}
p.verse{text-align:center;text-indent:0;margin:.1rem 0}
.abstract{background:var(--card);border:1px solid var(--rule);border-radius:6px;padding:.4rem .9rem;margin:.8rem 0;
font-size:.95rem}
.abstract h2{font-size:1rem;margin:.3rem 0}
.abstract[dir=ltr]{font-family:'Markazi',serif;font-size:1.08rem;line-height:1.55}
.kwds{font-size:.85rem;margin:.6rem 0;display:flex;flex-wrap:wrap;gap:.3rem;align-items:baseline}
.kwds .lab{color:var(--mute)}
.kwds ul{display:contents;list-style:none}
.kwds li{border:1px solid var(--rule);border-radius:1rem;padding:0 .6rem}
.body p,.notes p,.reflist li{text-align:justify;margin:0 0 .8rem;hyphens:none}
.body p[dir=ltr],.body p[dir=auto]{font-family:'Markazi',serif;font-size:1.12rem;line-height:1.6;text-align:start}
h2,h3,h4,h5,h6{font-family:'Markazi','Naskh',serif;font-weight:700;line-height:1.5;margin:1.6rem 0 .5rem}
.body h2{font-size:1.45rem}.body h3{font-size:1.25rem}.body h4,.body h5,.body h6{font-size:1.12rem}
.vowelled{line-height:2.25}
.quran{color:var(--quran);background:var(--qbg);border-radius:3px;padding:0 .15em;box-decoration-break:clone;
-webkit-box-decoration-break:clone}
.qref{font-size:.72rem;text-decoration:none;border:1px solid currentColor;border-radius:.6rem;padding:0 .35rem;
margin-inline-start:.25rem;white-space:nowrap;vertical-align:.1em}
a.fnref{font-size:.75em;vertical-align:super;line-height:0;text-decoration:none;padding:0 .1em}
.notes,.refs,.verses{border-top:1px solid var(--rule);margin-top:2rem;font-size:.92rem}
.notes h2,.refs h2,.verses h2{font-size:1.15rem}
.note{display:flex;gap:.6rem;margin:.35rem 0;scroll-margin-top:1rem}
.note .nl{flex:0 0 2.2rem;text-align:center;line-height:1.5;padding-top:.3rem}
.note .back{display:block;font-weight:700;text-decoration:none}
.note .npage{display:block;font-size:.66rem;color:var(--mute);white-space:nowrap}
.note .nb{flex:1;min-width:0}
.note p{margin:0 0 .3rem}
.note:target,.fnref:target{background:var(--qbg)}
.reflist{padding-inline-start:1rem}
.verses ul{padding-inline-start:1rem}.verse{font-family:'Naskh',serif}.vnote{color:var(--mute);font-size:.8rem}
.tablewrap{margin:1rem 0}
.tscroll{overflow-x:auto}
table{border-collapse:collapse;font-size:.92rem;line-height:1.6;margin:0 auto}
caption{caption-side:top;font-weight:700;padding:.3rem 0;font-size:.92rem}
th,td{border:1px solid var(--rule);padding:.25rem .55rem;text-align:center;vertical-align:middle}
thead th{background:var(--card);border-bottom:2px solid var(--fg)}
tbody th{text-align:start}
.formula{display:flex;align-items:center;gap:.6rem;margin:1rem 0}
.formula .eq{flex:1;overflow-x:auto;text-align:center}
math[display=block]{font-size:1.15em}
math{font-family:'Naskh','Markazi',math}
.eqlabel{color:var(--mute)}
img.crop{max-width:100%}
figure.figure{margin:1rem 0;text-align:center}figure.figure img.fig{max-width:100%;height:auto}
figure.figure figcaption{font-size:.85rem;margin-top:.3rem}
code.tex{font-size:.85rem}
button.og{all:unset;cursor:pointer;color:var(--mute);opacity:.55;display:inline-block;vertical-align:middle;
margin-inline-start:.3rem;line-height:0;padding:.15rem}
button.og:hover,button.og:focus-visible,button.og[aria-expanded=true]{opacity:1;color:var(--acc)}
button.og::before{content:"";display:inline-block;width:.95rem;height:.95rem;background:currentColor;
-webkit-mask:var(--ogi) center/contain no-repeat;mask:var(--ogi) center/contain no-repeat}
:root{--ogi:url("data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 16 16'%3E%3Crect x='2.5' y='1.5' width='11' height='13' rx='1' fill='none' stroke='black'/%3E%3Cpath d='M5 5h6M5 8h6M5 11h4' stroke='black'/%3E%3C/svg%3E")}
figure.clip{margin:.2rem 0 1rem;padding:.4rem;background:#fff;border:1px solid var(--rule);border-radius:6px}
figure.clip svg{display:block;width:100%;height:auto}
figure.clip figcaption{font-size:.72rem;color:#6b665d;margin-top:.2rem}
@media (prefers-color-scheme:dark){figure.clip{background:#e9e5dc}}
.about{border-top:1px solid var(--rule);margin-top:2.5rem;font-family:'Markazi',serif;font-size:.98rem;
line-height:1.45;color:var(--mute)}
.about h2{font-size:1.1rem;color:var(--fg)}
.about dl div{margin:.35rem 0}.about dt{font-weight:700;color:var(--fg)}.about dd{margin:0}
.links a{white-space:nowrap}
@media (min-width:52rem){body{font-size:1.125rem}.ed{padding-top:2.5rem}h1.title{font-size:2.3rem}}
@media print{button.og,figure.clip{display:none}}
"""

JS = r"""
(function(){
var P=window.__PAGES||{};
function clip(spec,crop){
  var f=document.createElement('figure');f.className='clip';
  spec.split(';').forEach(function(s){
    var m=s.split(':'),p=m[0],r=m[1].split(',').map(Number),pg=P[p];if(!pg)return;
    var pad=Math.round(pg[0]*0.012),x=Math.max(0,r[0]-pad),y=Math.max(0,r[1]-pad),
        w=Math.min(pg[0]-x,r[2]+2*pad),h=Math.min(pg[1]-y,r[3]+2*pad);
    var ns='http://www.w3.org/2000/svg',sv=document.createElementNS(ns,'svg');
    sv.setAttribute('viewBox',x+' '+y+' '+w+' '+h);
    sv.style.maxWidth=Math.round(w*pg[3])+'px';
    var im=document.createElementNS(ns,'image');im.setAttribute('href',pg[2]);
    im.setAttribute('width',pg[0]);im.setAttribute('height',pg[1]);sv.appendChild(im);f.appendChild(sv);
    var c=document.createElement('figcaption');c.textContent='الأصل، الصفحة '+(+p).toLocaleString('ar-EG');
    f.appendChild(c);});
  return f;}
document.addEventListener('click',function(e){
  var b=e.target.closest('button.og');if(!b)return;
  var host=b.closest('p,h1,h2,h3,h4,h5,h6,li,div.formula,div.tablewrap,div.note')||b.parentNode;
  var nx=host.nextElementSibling;
  if(b.getAttribute('aria-expanded')==='true'&&nx&&nx.classList.contains('clip')){nx.remove();
    b.setAttribute('aria-expanded','false');return;}
  var f=clip(b.dataset.r,b.dataset.crop);
  if(host.tagName==='LI'&&host.parentNode.classList.contains('authors')){host.appendChild(f);}
  else host.parentNode.insertBefore(f,host.nextSibling);
  b.setAttribute('aria-expanded','true');});
})();
"""


def head_meta(ed) -> str:
    f = ed.front
    m = [f'<meta name="citation_title" content="{a(f.get("title"))}"/>']
    for au in f.get("authors", []):
        nm = au.get("name_ar") or au.get("display") or au.get("name_en")
        if nm:
            m.append(f'<meta name="citation_author" content="{a(nm)}"/>')
    if f.get("year"):
        m.append(f'<meta name="citation_publication_date" content="{a(f["year"])}"/>')
    for k, v in (("citation_journal_title", f.get("journal")), ("citation_volume", f.get("volume")),
                 ("citation_issue", f.get("issue")), ("citation_firstpage", f.get("fpage")),
                 ("citation_lastpage", f.get("lpage")), ("citation_doi", f.get("doi")),
                 ("citation_publisher", f.get("publisher"))):
        if v:
            m.append(f'<meta name="{k}" content="{a(v)}"/>')
    for i in f.get("issn", []):
        m.append(f'<meta name="citation_issn" content="{a(i)}"/>')
    m.append('<meta name="citation_language" content="ar"/>')
    ld = {"@context": "https://schema.org", "@type": "ScholarlyArticle", "headline": f.get("title"),
          "name": f.get("title"), "inLanguage": "ar",
          "author": [{"@type": "Person", "name": au.get("name_ar") or au.get("display"),
                      **({"alternateName": au["name_en"]} if au.get("name_en") else {}),
                      **({"affiliation": au["aff"][0]} if au.get("aff") else {})}
                     for au in f.get("authors", []) if au.get("display") or au.get("name_ar")],
          "identifier": [x for x in (f.get("article_id"), f.get("doi") and "doi:" + f["doi"]) if x]}
    if f.get("year"):
        ld["datePublished"] = f["year"]
    if f.get("fpage"):
        ld["pageStart"] = f["fpage"]
    if f.get("lpage"):
        ld["pageEnd"] = f["lpage"]
    if f.get("journal"):
        per = {"@type": "Periodical", "name": f["journal"]}
        if f.get("issn"):
            per["issn"] = f["issn"]
        isp = {"@type": "PublicationIssue", "isPartOf": per}
        if f.get("issue"):
            isp["issueNumber"] = f["issue"]
        if f.get("volume"):
            isp = {"@type": "PublicationVolume", "volumeNumber": f["volume"], "isPartOf": per,
                   **({"hasPart": {"@type": "PublicationIssue", "issueNumber": f["issue"]}} if f.get("issue")
                      else {})}
        ld["isPartOf"] = isp
    kw = [k for g in f.get("keywords", []) for k in g.get("kwds", [])]
    if kw:
        ld["keywords"] = kw
    ab = next((x for x in f.get("abstracts", []) if x.get("lang", "ar") == "ar"), None)
    if ab:
        ld["abstract"] = " ".join(ab.get("paras", []))
    js = json.dumps(ld, ensure_ascii=False).replace("</", "<\\/")
    m.append(f'<script type="application/ld+json">{js}</script>')
    return "\n".join(m)


DEFAULT_LINKS = [("EPUB", "{id}.epub"), ("Print PDF, the page's layout", "{id}.layout.pdf"),
                 ("Print PDF, one column", "{id}.onecol.pdf"), ("Markdown", "{id}.md"), ("JSON record", "{id}.jsonl")]


def write_html(ed, out_root, links: list | None = None, dpi: int = 120) -> dict:
    """<out_root>/<id>/<id>.html (+ scan/, crops/) and <out_root>/fonts/. Returns sizes and counts."""
    from .scan import page_images
    out_root = Path(out_root)
    d = out_root / ed.stem
    d.mkdir(parents=True, exist_ok=True)
    fonts = bundle_fonts(out_root / "fonts")
    imgs = page_images(ed, d, dpi=dpi)
    crops = copy_crops(ed, d)
    pages = {}
    for n, p in imgs.items():
        pg = ed.pages[n]
        pages[n] = [round(pg.w), round(pg.h), f"scan/{p.name}", round(dpi / 300 * 1.25, 3)]
    if links is None:
        links = [(lab, h.format(id=ed.stem)) for lab, h in DEFAULT_LINKS]
    r = Renderer(ed, "html", crops)
    art = r.article(links)
    title = ed.front.get("title") or ed.stem
    page = (f'<!DOCTYPE html>\n<html lang="ar" dir="rtl"><head><meta charset="utf-8"/>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"/>'
            f"<title>{t(title)}</title>\n{head_meta(ed)}\n"
            f"<style>{font_css(fonts, '../fonts/')}{CSS}</style></head>"
            f"<body>{art}<script>window.__PAGES={json.dumps(pages)};{JS}</script></body></html>\n")
    hp = d / f"{ed.stem}.html"
    hp.write_text(page, encoding="utf-8")
    scan_bytes = sum(p.stat().st_size for p in imgs.values())
    return dict(html=str(hp), html_bytes=hp.stat().st_size, pages=len(imgs), scan_bytes=scan_bytes,
                originals=art.count('class="og"'), crops=len(crops))


def copy_crops(ed, d: Path) -> dict:
    """The masters' scan crops of formulas and tables (JATS <graphic specific-use="scan-crop">) into crops/."""
    out = {}
    for n in ed.body:
        g = (n.extra or {}).get("graphic") if n.kind in ("formula", "table", "figure") else None
        if not g or re.match(r"^[a-z]+:", g):
            continue
        src = (ed.jats_path.parent / g).resolve()
        if not src.exists() or not src.is_relative_to(ed.jats_path.parent.resolve()):
            continue
        dst = d / "crops" / src.name
        dst.parent.mkdir(exist_ok=True)
        if not dst.exists():
            shutil.copyfile(src, dst)
        out[n.id] = f"crops/{src.name}"
    return out
