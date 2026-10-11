"""The article as data, for search and for AI (experiment 35): Markdown with a YAML header, and one JSONL record.

    markdown(ed) -> str        YAML front matter, # title, ## headings, paragraphs, [^fn] notes, Quran quotations
                               ﴿…﴾ with their verse link, HTML tables (dir="rtl"), $…$ / $$…$$ LaTeX (olmOCR's
                               convention), references, the catalogue's abstract
    record(ed) -> dict         one JSONL line: metadata, sections, notes, references, quotations, tables, formulas,
                               `text` (exact, as read) and `text_search` (folded), provenance, scan regions
    fold(text) -> str          the search form of Arabic text (research/04 §4.2, Lucene's ArabicNormalizer folds)

Everything comes from the master files (model.load); nothing is invented. Text is kept exactly as read: the
folded form is a second field, never a replacement.
"""
from __future__ import annotations

import hashlib
import html
import json
import re
import time
from pathlib import Path

from lxml import etree

from .model import Edition, Node, plain

GENERATOR = "inkscript edition (experiment 35)"
RIGHTS = "Mandumah licensed content; open release is the owner's decision"
LABELS = dict(volume="المجلد", issue="العدد", pages="ص", abstract="الملخص", abstract_other="Abstract",
              keywords="الكلمات المفتاحية", refs="المراجع", notes="الهوامش")


def labels_text(ed=None) -> str:
    """The words the Markdown adds of its own (for the word checks' allowed extras)."""
    langs = " ".join(a["lang"] for a in ed.front["abstracts"]) if ed is not None else ""
    return " ".join(LABELS.values()) + " tag " + langs          # tag: a displayed formula's \tag{n}

# ---------------------------------------------------------------------------------------------- folding

_HARAKAT = re.compile("[ً-ٰٟۖ-ۭـ]")     # tashkeel, superscript alef, Quranic signs, tatweel
_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ی": "ي", "ک": "ك",
                       "ي": "ي", "‌": None, "‍": None})


def fold(text: str) -> str:
    """Search form: no harakat or tatweel; أ إ آ ٱ → ا, ى → ي, ة → ه; Persian ی ک → ي ك; Arabic-Indic and
    Persian digits → 0-9; no ZWNJ/ZWJ. Spacing and punctuation are kept."""
    return _HARAKAT.sub("", text or "").translate(_FOLD).translate(_DIGITS)


# ---------------------------------------------------------------------------------------------- helpers

def _version() -> str:
    try:
        from importlib.metadata import version
        return version("inkscript")
    except Exception:
        from .. import __version__
        return __version__


def _sha256(p) -> str | None:
    if not p or not Path(p).exists():
        return None
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _meta1(ed: Edition, name: str) -> str:
    v = ed.front["meta"].get(name)
    return v[0][0] if v else ""


_TRUST = re.compile(r"(\d+) words verified, (\d+) agreed, (\d+) flagged(?:, (\d+) corrected)?")


def trust_counts(ed: Edition) -> dict:
    m = _TRUST.search(_meta1(ed, "trust"))
    out = dict(verified=0, agreed=0, flagged=0, corrected=0)
    if m:
        out.update(verified=int(m[1]), agreed=int(m[2]), flagged=int(m[3]), corrected=int(m[4] or 0))
    q = re.match(r"(\d+) found, (\d+) equal", _meta1(ed, "quran-quotations"))
    out["quran_found"], out["quran_equal"] = (int(q[1]), int(q[2])) if q else (0, 0)
    return out


def alto_processing(alto_path) -> list[dict]:
    """The readers and steps named in the ALTO <Description> (read without parsing the pages)."""
    A = "{http://www.loc.gov/standards/alto/ns-v4#}"
    out = []
    try:
        for _, el in etree.iterparse(str(alto_path), events=("end",), tag=(A + "OCRProcessing", A + "Processing",
                                                                            A + "Description"), huge_tree=True,
                                     load_dtd=False, no_network=True, resolve_entities=False):
            if el.tag == A + "Description":
                break

            def first(local):
                e = next(el.iter(A + local), None)
                return " ".join((e.text or "").split()) if e is not None else ""
            out.append(dict(id=el.get("ID"), what=first("processingStepDescription"),
                            software=" ".join(filter(None, (first("softwareCreator"), first("softwareName"),
                                                            first("softwareVersion")))),
                            when=first("processingDateTime") or None))
    except (OSError, etree.XMLSyntaxError):
        pass
    return out


def _quotes(inl, out):
    for r in inl:
        if r["t"] == "quran":
            out.append(r)
        if "inl" in r:
            _quotes(r["inl"], out)
    return out


def _verse_for(ed: Edition, href: str) -> dict | None:
    return next((v for v in ed.verses if v["href"] == href), None)


def _regions(ed: Edition, n) -> list[dict]:
    return [dict(page=p, box=[round(v) for v in b]) for p, b in ed.regions(n)]


def _note_key(rid: str) -> str:
    return re.sub(r"[^\w-]", "", rid) or "note"


# ---------------------------------------------------------------------------------------------- Markdown

def _md_esc(s: str) -> str:
    """Escape what Markdown would otherwise read as markup in running text (kept minimal: the text stays
    readable as plain text)."""
    s = s.replace("\\", "\\\\")
    s = re.sub(r"([*_`\[\]<>|$])", r"\\\1", s)
    return re.sub(r"^(\s*)([#>+-]|\d+[.)])(\s)", r"\1\\\2\3", s)


def _md_inl(inl, notes: set) -> str:
    out = []
    for r in inl:
        t = r["t"]
        if t == "text":
            out.append(_md_esc(r["s"]))
        elif t == "fnref":
            k = _note_key(r["rid"])
            out.append(_md_esc(r["s"]) + (f"[^{k}]" if r["rid"] in notes else ""))
        elif t == "quran":
            ref = r["title"] or r["href"].rsplit("#", 1)[-1]
            q = _md_inl(r["inl"], notes)
            if not re.match(r"^\s*[(﴿«\"“{\[]", q):             # the print's own brackets are kept as they are
                q = "﴿" + q + "﴾"
            out.append(q + (f" ([{ref}]({r['href']}))" if r["href"] else ""))
        elif t == "math":
            out.append(f"${r['tex']}$" if r.get("tex") else _md_esc(r.get("ink") or ""))
        elif t == "b":
            out.append("**" + _md_inl(r["inl"], notes) + "**")
        elif t == "i":
            out.append("*" + _md_inl(r["inl"], notes) + "*")
        elif t in ("sup", "sub"):
            out.append(f"<{t}>" + _md_inl(r["inl"], notes) + f"</{t}>")
        elif t == "link":
            out.append("[" + _md_inl(r["inl"], notes) + "](" + r["href"] + ")")
    return "".join(out)


def _html_inl(inl) -> str:
    """Inline runs as HTML (for table cells inside Markdown)."""
    out = []
    for r in inl:
        t = r["t"]
        if t in ("text", "fnref"):
            out.append(html.escape(r["s"]))
        elif t == "math":
            out.append(f"${html.escape(r['tex'])}$" if r.get("tex") else html.escape(r.get("ink") or ""))
        elif t == "quran":
            out.append("﴿" + _html_inl(r["inl"]) + "﴾")
        elif t in ("b", "i", "sup", "sub"):
            out.append(f"<{t}>{_html_inl(r['inl'])}</{t}>")
        elif t == "link":
            out.append(f'<a href="{html.escape(r["href"])}">{_html_inl(r["inl"])}</a>')
    return "".join(out)


def table_html(n: Node) -> str:
    """An XHTML table, right to left: the cells are stored in reading order, so dir="rtl" alone puts the first
    one on the right."""
    x = n.extra
    rows = ['<table dir="rtl">']
    cap = plain(x.get("caption") or [])
    if cap or x.get("label"):
        rows.append("<caption>" + html.escape(" ".join(filter(None, (x.get("label"), cap)))) + "</caption>")
    sec = None
    for r in x["rows"]:
        s = "thead" if r["head"] else "tfoot" if r["foot"] else "tbody"
        if s != sec:
            if sec:
                rows.append(f"</{sec}>")
            rows.append(f"<{s}>")
            sec = s
        cells = []
        for c in r["cells"]:
            tag = "th" if c["th"] else "td"
            at = "".join(f' {k}="{c[k]}"' for k in ("colspan", "rowspan") if c[k] > 1)
            if c.get("scope"):
                at += f' scope="{c["scope"]}"'
            cells.append(f"<{tag}{at}>{_html_inl(c['inl'])}</{tag}>")
        rows.append("<tr>" + "".join(cells) + "</tr>")
    if sec:
        rows.append(f"</{sec}>")
    rows.append("</table>")
    return "\n".join(rows)


def _yaml(v, ind=0) -> str:
    """A small YAML writer: strings as JSON strings (valid YAML), lists and dicts in block style."""
    pad = "  " * ind
    if isinstance(v, dict):
        lines = []
        for k, x in v.items():
            if x in (None, "", [], {}):
                continue
            if isinstance(x, (dict, list)):
                lines.append(f"{pad}{k}:\n{_yaml(x, ind + 1)}")
            else:
                lines.append(f"{pad}{k}: {json.dumps(x, ensure_ascii=False)}")
        return "\n".join(lines)
    if isinstance(v, list):
        lines = []
        for x in v:
            if isinstance(x, dict):
                inner = _yaml(x, ind + 1).lstrip()
                lines.append(f"{pad}- {inner}")
            else:
                lines.append(f"{pad}- {json.dumps(x, ensure_ascii=False)}")
        return "\n".join(lines)
    return pad + json.dumps(v, ensure_ascii=False)


def _header(ed: Edition) -> dict:
    f = ed.front
    tc = trust_counts(ed)
    pages = f"{f['fpage']}–{f['lpage']}" if f["fpage"] and f["lpage"] else f["fpage"]
    return dict(
        id=ed.stem, record=f["record"], title=f["title"], subtitle=f["subtitle"],
        title_en=next((t["title"] for t in f["trans_titles"] if t["lang"] == "en"), ""),
        authors=[{k: v for k, v in dict(name=a["display"], name_ar=a["name_ar"], name_en=a["name_en"],
                                         affiliation=a["aff"]).items() if v} for a in f["authors"]],
        journal=f["journal"], journal_en=f["journal_en"], issn=f["issn"], publisher=f["publisher"],
        year=f["year"], calendar=f["calendar"] if f["calendar"] != "gregorian" else "", date=f["date"],
        volume=f["volume"], issue=f["issue"], pages=pages, page_count=f["page_count"], doi=f["doi"],
        language=f["lang"], article_type=f["article_type"],
        keywords=[k for g in f["keywords"] for k in g["kwds"]],
        rights=RIGHTS,
        source=dict(jats=ed.jats_path.name, alto=ed.alto_path.name,
                    scan=ed.pdf_path.name if ed.pdf_path else None),
        trust=dict(verified=tc["verified"], agreed=tc["agreed"], flagged=tc["flagged"], corrected=tc["corrected"]),
        generator=GENERATOR)


def markdown(ed: Edition) -> str:
    f = ed.front
    notes = {n.id for n in ed.notes}
    out = ["---", _yaml(_header(ed)), "---", ""]
    for s in f["subjects"]:
        if s.get("id"):                                      # a rubric printed on the page
            out += [f"**{_md_esc(s['text'])}**", ""]
    out += ["# " + (_md_inl(f.get("title_inl") or [], notes) or _md_esc(f["title"]) or ed.stem), ""]
    if f["subtitle"]:
        out += ["## " + _md_esc(f["subtitle"]), ""]
    for a in f["authors"]:
        line = "**" + _md_esc(a["display"]) + "**"
        if a["aff"]:
            line += " — " + _md_esc("، ".join(a["aff"]))
        out += [line, ""]
    for fb in f["front_blocks"]:
        out += [_md_esc(fb["text"]), ""]
    facts = [x for x in (f["journal"], f"{LABELS['volume']} {f['volume']}" if f["volume"] else "",
                         f"{LABELS['issue']} {f['issue']}" if f["issue"] else "", f["date"] or f["year"],
                         f"{LABELS['pages']} {f['fpage']}–{f['lpage']}" if f["fpage"] else "") if x]
    if facts:
        out += ["> " + _md_esc("، ".join(facts)), ""]
    for ab in f["abstracts"]:
        out += ["## " + (LABELS["abstract"] if ab["lang"] == "ar" else f"{LABELS['abstract_other']} ({ab['lang']})"), ""]
        out += [_md_esc(p) for p in ab["paras"] if p] + [""]
    kw = [k for g in f["keywords"] for k in g["kwds"]]
    if kw:
        out += [f"**{LABELS['keywords']}:** " + _md_esc("، ".join(kw)), ""]
    out += ["---", ""]
    for n in ed.body:
        out += _md_node(n, notes)
    if ed.refs:
        if ed.refs[0].kind != "ref-head" or not ed.refs[0].inl:
            out += ["## " + LABELS["refs"], ""]
        for n in ed.refs:
            if n.kind == "ref-head":
                if n.inl:
                    out += ["## " + _md_inl(n.inl, notes), ""]
            else:
                out += ["- " + _md_inl(n.inl, notes)]
        out += [""]
    if ed.notes:
        out += ["## " + LABELS["notes"], ""]
        for note in ed.notes:
            k = _note_key(note.id)
            paras = [_md_inl(p.inl, notes) for p in note.paras] or [""]
            lab = f"({_md_esc(note.label)}) " if note.label else ""      # the printed label, as on the page
            out.append(f"[^{k}]: {lab}{paras[0]}")
            for p in paras[1:]:
                out.append("    " + p)
        out += [""]
    return "\n".join(out).rstrip() + "\n"


def _md_node(n: Node, notes: set) -> list[str]:
    if n.kind == "heading":
        return ["#" * min(6, n.level + 1) + " " + _md_inl(n.inl, notes), ""]
    if n.kind == "formula":
        x = n.extra
        body = x.get("tex") or x.get("ink") or ""
        lines = ["$$", body + (f" \\tag{{{x['label'].strip('()')}}}" if x.get("label") else ""), "$$", ""]
        return lines
    if n.kind == "table":
        return [table_html(n), ""]
    s = _md_inl(n.inl, notes)
    if n.lang:
        return [f'<div lang="{n.lang}" dir="ltr">', "", s, "", "</div>", ""]
    return [s, ""] if s else []


# ---------------------------------------------------------------------------------------------- JSONL record

def _node_rec(ed, n: Node) -> dict:
    d = dict(id=n.id, kind=n.kind, text=n.text, regions=_regions(ed, n))
    if n.lang:
        d["lang"] = n.lang
    if n.ctype:
        d["content_type"] = n.ctype
    return d


def record(ed: Edition) -> dict:
    f = ed.front
    tc = trust_counts(ed)
    # sections: a heading opens one; text before the first heading is section 0 without a heading
    sections, cur = [], dict(heading=None, level=0, paragraphs=[])
    tables, formulas, quotes = [], [], []
    for n in ed.body:
        if n.kind == "heading":
            if cur["heading"] is not None or cur["paragraphs"]:
                sections.append(cur)
            cur = dict(heading=n.text, heading_id=n.id, level=n.level, paragraphs=[])
            _quotes(n.inl, quotes)
            continue
        cur["paragraphs"].append(_node_rec(ed, n))
        _quotes(n.inl, quotes)
        if n.kind == "table":
            x = n.extra
            tables.append(dict(id=n.id, label=x.get("label"), caption=plain(x.get("caption") or []),
                               cell_order="logical: the first cell of a row is the rightmost on the page",
                               rows=[dict(head=r["head"], cells=[dict(id=c["id"], th=c["th"], colspan=c["colspan"],
                                                                      rowspan=c["rowspan"], text=plain(c["inl"]))
                                                                 for c in r["cells"]]) for r in x["rows"]],
                               html=table_html(n), regions=_regions(ed, n)))
        elif n.kind == "formula":
            x = n.extra
            formulas.append(dict(id=n.id, display=True, label=x.get("label"), tex=x.get("tex"),
                                 mathml=x.get("mathml"), dir=x.get("dir"), printed=x.get("ink"),
                                 scan_crop=x.get("graphic"), regions=_regions(ed, n)))
        for r in _walk_runs(n.inl):
            if r["t"] == "math":
                formulas.append(dict(id=r.get("id"), display=False, tex=r.get("tex"), mathml=r.get("mathml"),
                                     dir=r.get("dir"), printed=r.get("ink"), paragraph=n.id))
    if cur["heading"] is not None or cur["paragraphs"]:
        sections.append(cur)
    footnotes = []
    for note in ed.notes:
        footnotes.append(dict(id=note.id, label=note.label, page=note.page,
                              text="\n".join(p.text for p in note.paras),
                              regions=[r for p in note.paras for r in _regions(ed, p)]))
        for p in note.paras:
            _quotes(p.inl, quotes)
    refs = [_node_rec(ed, n) for n in ed.refs]
    quran = []
    for q in quotes:
        v = _verse_for(ed, q["href"]) or {}
        quran.append(dict(id=q["id"], ref=q["title"] or v.get("ref"), href=q["href"], quoted=plain(q["inl"]),
                          verse=v.get("verse"), match=q["match"]))
    text = full_text(ed)
    pages = f"{f['fpage']}–{f['lpage']}" if f["fpage"] and f["lpage"] else f["fpage"]
    return dict(
        id=ed.stem, record=f["record"], doi=f["doi"] or None,
        journal=f["journal"], journal_en=f["journal_en"] or None, journal_id=f["journal_id"], issn=f["issn"],
        publisher=f["publisher"], publisher_loc=f["publisher_loc"],
        year=f["year"], date=f["date"], calendar=f["calendar"], volume=f["volume"], issue=f["issue"],
        fpage=f["fpage"], lpage=f["lpage"], pages=pages, page_count=f["page_count"] or len(ed.pages),
        lang=f["lang"], title=f["title"], subtitle=f["subtitle"] or None,
        title_en=next((t["title"] for t in f["trans_titles"] if t["lang"] == "en"), None),
        title_source=_meta1(ed, "title-source") or None,
        authors=[dict(name=a["display"], name_ar=a["name_ar"] or None, name_en=a["name_en"] or None,
                      printed=a["printed"] or None, prefix=a["prefix"] or None, affiliation=a["aff"],
                      role=a["role"] or None) for a in f["authors"]],
        article_type=f["article_type"],
        front_printed=front_printed(ed),
        subjects=[dict(text=s["text"], type=s["type"], lang=s["lang"]) for s in f["subjects"]],
        keywords=[k for g in f["keywords"] for k in g["kwds"]],
        abstracts=[dict(lang=a["lang"], type=a["type"], text="\n".join(a["paras"])) for a in f["abstracts"]],
        sections=sections, footnotes=footnotes, references=refs, quran=quran, tables=tables, formulas=formulas,
        text=text, text_search=fold(text),
        counts=dict(words=len(text.split()), chars=len(text), paragraphs=sum(1 for _ in ed.nodes()),
                    footnotes=len(ed.notes), references=sum(n.kind == "ref" for n in ed.refs),
                    tables=len(tables), formulas=len(formulas), quran=len(quran)),
        rights=RIGHTS,
        provenance=dict(
            text_source=_meta1(ed, "text-source") or None,
            structure_source=_meta1(ed, "structure-source") or None,
            catalogue=_meta1(ed, "catalogue") or None,
            catalogue_check=_meta1(ed, "catalogue-check") or None,
            front_sources=_meta1(ed, "front-sources") or None,
            readers=alto_processing(ed.alto_path),
            trust=dict(verified=tc["verified"], agreed=tc["agreed"], flagged=tc["flagged"],
                       corrected=tc["corrected"], note="per-word marks are in the ALTO file (TAGREFS trust.*)"),
            quran_quotations=dict(found=tc["quran_found"], equal_to_verse=tc["quran_equal"]),
            sources={k: dict(file=Path(p).name, sha256=_sha256(p)) for k, p in
                     (("jats", ed.jats_path), ("alto", ed.alto_path), ("scan", ed.pdf_path)) if p},
            generator=GENERATOR, generator_version=_version(),
            generated=time.strftime("%Y-%m-%dT%H:%M:%S")),
    )


def front_printed(ed: Edition) -> list[dict]:
    """What the master keeps of the first page as printed (a rubric, an affiliation line): kind, text as read,
    and where it is."""
    out = []
    for s in ed.front["subjects"]:
        if s.get("id"):
            out.append(dict(kind="rubric", id=s["id"], text=s["text"], regions=_regions(ed, [s["id"]])))
    for fb in ed.front["front_blocks"]:
        out.append(dict(kind="front", id=fb["id"], text=fb["text"], regions=_regions(ed, [fb["id"]])))
    return out


def _walk_runs(inl):
    for r in inl:
        yield r
        if "inl" in r:
            yield from _walk_runs(r["inl"])


def plain_tex(inl) -> str:
    """Inline runs as plain text, an inline formula as $LaTeX$ (its printed symbols when it has no LaTeX)."""
    out = []
    for r in inl:
        if r["t"] in ("text", "fnref"):
            out.append(r["s"])
        elif r["t"] == "math":
            out.append(f"${r['tex']}$" if r.get("tex") else r.get("ink") or "")
        else:
            out.append(plain_tex(r["inl"]))
    return "".join(out)


def full_text(ed: Edition) -> str:
    """The article's text exactly as read, in reading order: headings and paragraphs (tables row by row, cells in
    reading order), then the references, then the notes, each with its label. One paragraph a line. Formulas as
    LaTeX ($…$ inline, $$…$$ displayed: the convention of LLM corpora such as olmOCR's)."""
    out = []
    for n in ed.body:
        if n.kind == "table":
            x = n.extra
            if x.get("label") or x.get("caption"):
                out.append(" ".join(filter(None, (x.get("label"), plain(x.get("caption") or [])))))
            for r in x["rows"]:
                out.append(" | ".join(plain(c["inl"]) for c in r["cells"]))
        elif n.kind == "formula":
            x = n.extra
            f = f"$${x['tex']}$$" if x.get("tex") else x.get("ink", "")
            out.append(" ".join(filter(None, (f, x.get("label")))))
        else:
            out.append(plain_tex(n.inl))
    for n in ed.refs:
        out.append(plain_tex(n.inl))
    for note in ed.notes:
        for i, p in enumerate(note.paras):
            out.append((f"({note.label}) " if i == 0 and note.label else "") + plain_tex(p.inl))
    return "\n".join(s for s in out if s.strip())


def jsonl_line(ed: Edition) -> str:
    return json.dumps(record(ed), ensure_ascii=False)
