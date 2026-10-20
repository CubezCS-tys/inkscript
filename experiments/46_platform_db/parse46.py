"""Experiment 46: read one master (JATS + ALTO + sidecars) into rows for the platform database. No writes here."""
from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from lxml import etree

from common46 import fold, key, to_int, year_of

XLINK = "{http://www.w3.org/1999/xlink}href"
XLINK_T = "{http://www.w3.org/1999/xlink}title"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
ALTO_NS = "{http://www.loc.gov/standards/alto/ns-v4#}"

BLOCK_ID = re.compile(r"^p(\d+)(b\d+|t\d+c\d+)$")
LINE_ID = re.compile(r"^p(\d+)")
BACKREF = re.compile(r"(المرجع\s+السابق|مرجع\s+سابق|المصدر\s+السابق|مصدر\s+سابق|المرجع\s+نفسه|المصدر\s+نفسه|"
                     r"المرجع\s+ذاته|المصدر\s+ذاته|نفس\s+المرجع|نفس\s+المصدر|السابق\s+نفسه|م\.\s?س\.?|"
                     r"\bibid\b\.?|\bibidem\b|\bop\.?\s?cit\b\.?|\bid\.\s|\bloc\.?\s?cit\b)", re.I)


def ln(e) -> str:
    return etree.QName(e).localname if isinstance(e.tag, str) else ""


def text_of(e, skip_parsed: bool = True) -> str:
    """The element's text as printed (reader-fix/sic named-content carry the print), parsed citations left out."""
    out = []

    def walk(x):
        if not isinstance(x.tag, str):
            if x.tail:
                out.append(x.tail)
            return
        name = ln(x)
        if skip_parsed and name == "p" and x.get("content-type") == "parsed-citations":
            if x.tail:
                out.append(x.tail)
            return
        if x.text:
            out.append(x.text)
        for c in x:
            walk(c)
        if x is not e and x.tail:
            out.append(x.tail)

    walk(e)
    return " ".join("".join(out).split())


def lang_of(e) -> str | None:
    while e is not None:
        v = e.get(XML_LANG)
        if v:
            return v
        e = e.getparent()
    return None


def ancestors(e):
    p = e.getparent()
    while p is not None:
        yield p
        p = p.getparent()


def sha_of(paths: list[Path]) -> str:
    h = hashlib.sha1()
    for p in paths:
        if p.exists():
            h.update(p.name.encode())
            h.update(p.read_bytes())
    return h.hexdigest()[:16]


def read_alto(path: Path) -> tuple[dict, dict]:
    blocks, lines = {}, {}
    if not path.exists():
        return blocks, lines
    for ev, el in etree.iterparse(str(path), events=("start",)):
        t = el.tag
        if t == ALTO_NS + "TextBlock" or t == ALTO_NS + "TextLine":
            i = el.get("ID")
            try:
                box = tuple(float(el.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
            except (TypeError, ValueError):
                continue
            (blocks if t.endswith("TextBlock") else lines)[i] = box
    return blocks, lines


def union(boxes):
    boxes = [b for b in boxes if b]
    if not boxes:
        return None
    x0 = min(b[0] for b in boxes)
    y0 = min(b[1] for b in boxes)
    x1 = max(b[0] + b[2] for b in boxes)
    y1 = max(b[1] + b[3] for b in boxes)
    return (x0, y0, x1 - x0, y1 - y0)


def block_kind(e) -> str:
    name, ct = ln(e), e.get("content-type")
    anc = [ln(a) for a in ancestors(e)]
    anc_ct = [a.get("content-type") for a in ancestors(e)]
    if name == "article-title":
        return "title"
    if name == "alt-title":
        return "title-printed"
    if name == "trans-title":
        return "title-en"
    if name == "subtitle":
        return "subtitle"
    if name == "kwd-group":
        return "keywords"
    if name == "custom-meta":
        return "front-matter"
    if name == "mixed-citation":
        return "reference"
    if name == "verse-group":
        return "verse"
    if name in ("th", "td"):
        return "table-cell"
    if name == "title":
        if "caption" in anc:
            return "caption"
        if "ref-list" in anc[:1]:
            return "references-heading"
        return "heading"
    if name == "p":
        if ct == "abstract":
            return "abstract"
        if "fn" in anc:
            i = anc.index("fn")
            grp = list(ancestors(e))[i].getparent()
            return "endnote" if grp is not None and grp.get("content-type") == "endnotes" else "footnote"
        if ct in ("boxed", "caption", "text-in-figure", "byline", "added", "other"):
            return ct
        if "caption" in anc:
            return "caption"
        if "list-item" in anc:
            return "list-item"
        if "disp-quote" in anc:
            return "quote"
        if "boxed-text" in anc:
            return "boxed"
        if "app" in anc:
            return "appendix"
        if "ack" in anc:
            return "acknowledgements"
        return "paragraph"
    return name


def parse_article(mdir: Path, stem: str, run: str) -> dict:
    jp = mdir / f"{stem}.jats.xml"
    ap = mdir / f"{stem}.alto.xml"
    root = etree.parse(str(jp)).getroot()
    ablocks, alines = read_alto(ap)
    R: dict = {k: [] for k in ("blocks", "notes", "note_calls", "figures", "works", "work_authors", "back_references",
                               "fixes", "misprints", "metadata_changes", "keywords", "authors", "affiliations",
                               "dates", "abstracts")}
    S = dict(source="masters", run=run)
    front = root.find("front")
    am = front.find("article-meta")
    jm = front.find("journal-meta")
    art_lang = root.get(XML_LANG)

    def first(path, base=am):
        x = base.find(path) if base is not None else None
        return text_of(x) if x is not None else None

    # ---- stamps
    stamp = {}
    sj = mdir / f"{stem}.stamp.json"
    if sj.exists():
        stamp = json.loads(sj.read_text(encoding="utf-8"))
    for cm in am.iter("custom-meta"):
        i = cm.get("id") or ""
        if i.startswith("stamp-"):
            stamp.setdefault(i[6:].replace("-", "_"), text_of(cm.find("meta-value")))
    patches_applied = None
    for cm in am.iter("custom-meta"):
        if text_of(cm.find("meta-name")) == "pipeline-patches":
            patches_applied = text_of(cm.find("meta-value"))

    # ---- titles
    tg = am.find("title-group")
    at = tg.find("article-title") if tg is not None else None
    title = text_of(at) if at is not None else None
    printed = None
    meta_title = None
    for alt in (tg.findall("alt-title") if tg is not None else []):
        if alt.get("alt-title-type") == "printed":
            printed = text_of(alt)
        elif alt.get("alt-title-type") == "metadata":
            meta_title = text_of(alt)
    if printed is None and at is not None and at.get("id"):
        printed = title
    sub = first("title-group/subtitle")
    tt = am.find("trans-title-group/trans-title")
    title_en = text_of(tt) if tt is not None else None

    # ---- ids, dates, pages
    doi = None
    for pid in am.findall("article-id") + am.findall("pub-id"):
        if pid.get("pub-id-type") == "doi":
            doi = text_of(pid)
    pub_year, pub_date = None, None
    for pd in am.findall("pub-date"):
        y = first("year", pd)
        sd = first("string-date", pd)
        hij = pd.get("calendar") == "islamic"             # experiment 43 fix round 3: the Hijri year beside
        if not hij:                                        # (or, alone, instead of) the Gregorian one
            pub_year = pub_year or year_of(y)
            pub_date = pub_date or sd or y
        R["dates"].append(dict(stem=stem, date_type="pub-hijri" if hij else "pub", iso=pd.get("iso-8601-date"),
                               year=year_of(y), printed=sd or y, **S))
    for d in am.findall("history/date"):
        R["dates"].append(dict(stem=stem, date_type=d.get("date-type"), iso=d.get("iso-8601-date"),
                               year=year_of(first("year", d)), printed=first("string-date", d) or first("year", d), **S))
    pc = am.find("counts/page-count")

    # ---- abstracts
    ab = {"ar": [], "en": []}
    for tag in ("abstract", "trans-abstract"):
        for a in am.findall(tag):
            lang = a.get(XML_LANG) or ("en" if tag == "trans-abstract" else (art_lang or "ar"))
            for i, p in enumerate(a.findall(".//p")):
                t = text_of(p)
                R["abstracts"].append(dict(stem=stem, lang=lang, seq=i, text=t, block_id=p.get("id"), **S))
                ab.setdefault(lang, []).append(t)

    # ---- keywords
    kseq = 0
    for kg in am.findall("kwd-group"):
        lang = kg.get(XML_LANG) or art_lang or "ar"
        for k in kg.findall("kwd"):
            raw = text_of(k)
            term = re.sub(r"^\s*(الكلمات\s+المفتاحية|كلمات\s+مفتاحية|الكلمات\s+الدالة|كلمات\s+دالة|مصطلحات\s+أساسية|"
                          r"المصطلحات\s+الأساسية|key\s*words?|mots[- ]cl[ée]s)\s*[:：\-]\s*", "", raw, flags=re.I)
            term = term.strip(" .،,;؛")
            if term:
                R["keywords"].append(dict(stem=stem, seq=kseq, lang=lang, term=term, term_printed=raw,
                                          term_key=key(term), **S))
                kseq += 1

    # ---- authors and affiliations
    for i, c in enumerate(am.iter("contrib")):
        nm = c.find("string-name")
        if nm is None:                                     # the corrected name inside name-alternatives (D33)
            nm = next((x for x in c.iterfind("name-alternatives/string-name")
                       if x.get("specific-use") != "printed-on-the-page" and not x.get(XML_LANG)), None)
        if nm is not None:
            name = text_of(nm)
        else:
            n = c.find("name")
            name = " ".join(x for x in (first("given-names", n), first("surname", n)) if x) if n is not None else ""
        em = c.find("email")
        R["authors"].append(dict(stem=stem, seq=i, printed_name=name, email=text_of(em) if em is not None else None,
                                 role=c.get("contrib-type") or "author", **S))
        for j, a in enumerate(c.findall("aff")):
            orgs = [text_of(x) for x in a.findall("institution") if x.get("content-type") != "dept"]
            depts = [text_of(x) for x in a.findall("institution") if x.get("content-type") == "dept"]
            city = [text_of(x) for x in a.findall("addr-line")]
            ctry = [text_of(x) for x in a.findall("country")]
            R["affiliations"].append(dict(stem=stem, author_seq=i, seq=j, printed=text_of(a),
                                          orgname=" | ".join(orgs) or None, dept=" | ".join(depts) or None,
                                          city=" | ".join(city) or None, country=" | ".join(ctry) or None, **S))

    # ---- blocks (document order)
    seen = set()
    ord_ = 0
    for e in root.iter():
        if not isinstance(e.tag, str):
            continue
        i = e.get("id")
        if not i or i in seen or not BLOCK_ID.match(i):
            continue
        seen.add(i)
        name = ln(e)
        if name == "custom-meta":
            mv = e.find("meta-value")
            t = text_of(mv) if mv is not None else ""
        elif name == "verse-group":
            t = " / ".join(text_of(v) for v in e.findall("verse-line"))
        elif name == "kwd-group":
            t = "؛ ".join(text_of(k) for k in e.findall("kwd"))
        else:
            t = text_of(e)
        lines = [x.get("id") for x in e.iter("target") if x.get("id")]
        pages = [int(LINE_ID.match(x).group(1)) for x in lines if LINE_ID.match(x)]
        page = int(BLOCK_ID.match(i).group(1))
        box = ablocks.get(i) or union([alines.get(x) for x in lines])
        sec = next((a.get("id") for a in ancestors(e) if ln(a) == "sec"), None)
        R["blocks"].append(dict(stem=stem, block_id=i, page=page, last_page=max(pages) if pages else page, ord=ord_,
                                kind=block_kind(e), section=sec, lang=lang_of(e) or art_lang, text=t,
                                text_folded=fold(t), alto_lines=json.dumps(lines),
                                hpos=box[0] if box else None, vpos=box[1] if box else None,
                                width=box[2] if box else None, height=box[3] if box else None, **S))
        ord_ += 1
    block_of_line = {}
    for b in R["blocks"]:
        for x in json.loads(b["alto_lines"]):
            block_of_line.setdefault(x, b["block_id"])

    # ---- notes and calls
    for o, fn in enumerate(root.iter("fn")):
        fid = fn.get("id")
        grp = fn.getparent()
        kind = "endnote" if grp is not None and grp.get("content-type") == "endnotes" else "footnote"
        m = re.match(r"fn-p(\d+)-", fid or "")
        lab = fn.find("label")
        texts = [text_of(p) for p in fn.findall("p") if p.get("content-type") != "parsed-citations"]
        R["notes"].append(dict(stem=stem, note_id=fid, kind=kind, page=int(m.group(1)) if m else None,
                               label=text_of(lab) if lab is not None else None, text=" ".join(texts), n_calls=0,
                               n_works=len(fn.findall(".//element-citation")), ord=o, **S))
    calls = {}
    for x in root.iter("xref"):
        if x.get("ref-type") != "fn":
            continue
        blk = None
        for a in ancestors(x):
            if a.get("id") and BLOCK_ID.match(a.get("id")):
                blk = a.get("id")
                break
        if blk is None:   # a call inside a line: find the preceding target
            prev = x.getprevious()
            while prev is not None and ln(prev) != "target":
                prev = prev.getprevious()
            if prev is not None:
                blk = block_of_line.get(prev.get("id"))
        R["note_calls"].append(dict(stem=stem, note_id=x.get("rid"), call_text=text_of(x), block_id=blk,
                                    page=int(BLOCK_ID.match(blk).group(1)) if blk and BLOCK_ID.match(blk) else None,
                                    **S))
        calls[x.get("rid")] = calls.get(x.get("rid"), 0) + 1
    for n in R["notes"]:
        n["n_calls"] = calls.get(n["note_id"], 0)

    # ---- figures, tables, equations
    def page_of_id(i):
        m = re.match(r"p(\d+)", i or "")
        return int(m.group(1)) if m else None

    for f in root.iter("fig"):
        cap = f.find("caption")
        alts = f.findall("alt-text")
        g = f.find("graphic")
        R["figures"].append(dict(
            stem=stem, xml_id=f.get("id"), kind="figure", page=page_of_id(f.get("id")),
            label=text_of(f.find("label")) if f.find("label") is not None else None,
            caption=text_of(cap) if cap is not None else None,
            alt_ar=next((text_of(a) for a in alts if a.get(XML_LANG) in (None, "ar")), None),
            alt_en=next((text_of(a) for a in alts if a.get(XML_LANG) == "en"), None),
            text_in_figure=" | ".join(text_of(p) for p in f.iter("p") if p.get("content-type") == "text-in-figure")
            or None, graphic=g.get(XLINK) if g is not None else None, tex=None, has_mathml=0,
            specific_use=f.get("specific-use"), n_cells=None, **S))
    for t in root.iter("table-wrap"):
        cap = t.find("caption")
        alts = t.findall("alt-text")
        R["figures"].append(dict(
            stem=stem, xml_id=t.get("id"), kind="table", page=page_of_id(t.get("id")),
            label=text_of(t.find("label")) if t.find("label") is not None else None,
            caption=text_of(cap) if cap is not None else None,
            alt_ar=next((text_of(a) for a in alts if a.get(XML_LANG) in (None, "ar")), None),
            alt_en=next((text_of(a) for a in alts if a.get(XML_LANG) == "en"), None),
            text_in_figure=None, graphic=None, tex=None, has_mathml=0, specific_use=t.get("specific-use"),
            n_cells=len(t.findall(".//td")) + len(t.findall(".//th")), **S))
    MML = "{http://www.w3.org/1998/Math/MathML}math"
    for kind, tag in (("equation", "disp-formula"), ("inline-equation", "inline-formula")):
        for k, q in enumerate(root.iter(tag)):
            tex = q.find(".//tex-math")
            R["figures"].append(dict(
                stem=stem, xml_id=q.get("id") or f"{tag}{k + 1}", kind=kind, page=page_of_id(q.get("id")),
                label=text_of(q.find("label")) if q.find("label") is not None else None, caption=None,
                alt_ar=None, alt_en=None, text_in_figure=None, graphic=None,
                tex=(tex.text or "").strip() if tex is not None else None,
                has_mathml=int(q.find(".//" + MML) is not None), specific_use=q.get("specific-use"), n_cells=None,
                **S))
    for k, g in enumerate(root.iter("inline-graphic")):
        R["figures"].append(dict(stem=stem, xml_id=g.get("id") or f"ig{k + 1}", kind="inline-picture",
                                 page=None, label=None, caption=None, alt_ar=None, alt_en=None, text_in_figure=None,
                                 graphic=g.get(XLINK), tex=None, has_mathml=0, specific_use=g.get("specific-use"),
                                 n_cells=None, **S))

    # ---- works (parsed citations) and back references
    word = 0
    for ref in root.iter("ref"):
        mc = ref.find("mixed-citation")
        ptxt = text_of(mc) if mc is not None else None
        pg = page_of_id(mc.get("id")) if mc is not None else None
        for s, ec in enumerate(ref.findall("element-citation")):
            _work(R, stem, "reference", ref.get("id"), s, word, ec, ptxt, pg, S)
            word += 1
    fns = {fn.get("id"): fn for fn in root.iter("fn")}
    for n in R["notes"]:
        fn = fns[n["note_id"]]
        ecs = fn.findall(".//element-citation")
        for s, ec in enumerate(ecs):
            _work(R, stem, "note", n["note_id"], s, word, ec, n["text"], n["page"], S)
            word += 1
        m = BACKREF.search(n["text"] or "")
        if m:
            R["back_references"].append(dict(
                backref_id=f"{stem}|{n['note_id']}", stem=stem, note_id=n["note_id"], ord=word, marker=m.group(1),
                hint=n["text"][:m.start()].strip(" ،,:.-()0123456789٠١٢٣٤٥٦٧٨٩"), printed=n["text"],
                has_parsed=int(bool(ecs)), page=n["page"], **S))
            word += 1

    # ---- fixes and misprints (notes in back)
    for notes in root.iter("notes"):
        nt = notes.get("notes-type")
        for p in notes.findall("p"):
            nc = {x.get("content-type"): x for x in p.iter("named-content")}
            al = nc.get("alto-line")
            href = al.get(XLINK) if al is not None else None
            lab = text_of(al) if al is not None else None
            page = to_int(lab.split(":")[0]) if lab else None
            why = text_of(nc["why"]) if "why" in nc else None
            if nt == "reader-fixes":
                R["fixes"].append(dict(stem=stem, fix_id=p.get("id"),
                                       azure_reading=text_of(nc["azure-reading"]) if "azure-reading" in nc else None,
                                       print=text_of(nc["print"]) if "print" in nc else None, why=why,
                                       alto_line=href.split("#")[-1] if href else None, line_label=lab, page=page,
                                       **S))
            elif nt == "suspected-misprints":
                R["misprints"].append(dict(stem=stem, sic_id=p.get("id"),
                                           printed=text_of(nc["printed"]) if "printed" in nc else None,
                                           proposed=text_of(nc["proposed-correction"])
                                           if "proposed-correction" in nc else None, why=why,
                                           alto_line=href.split("#")[-1] if href else None, line_label=lab,
                                           page=page, **S))

    # ---- D33 metadata changes
    mc = mdir / f"{stem}.metachanges.json"
    if mc.exists():
        d = json.loads(mc.read_text(encoding="utf-8"))
        for k, ch in enumerate(d.get("changes") or []):
            R["metadata_changes"].append(dict(stem=stem, seq=k, field=ch.get("field"), printed=ch.get("printed"),
                                              corrected=ch.get("corrected"), change_source=ch.get("source"),
                                              reason=ch.get("reason"),
                                              alternatives=json.dumps(ch.get("alternatives"), ensure_ascii=False),
                                              rule=d.get("rule"), **S))

    kinds = [f["kind"] for f in R["figures"]]
    R["article"] = dict(
        stem=stem, run=run, journal_id=(jm.findtext("journal-id") if jm is not None else None) or stem.split("-")[0],
        issue_id="-".join(stem.split("-")[:3]), doi=doi, language=art_lang, title=title, title_printed=printed,
        title_metadata=meta_title, title_en=title_en, subtitle=sub, volume=first("volume"), issue=first("issue"),
        pub_year=pub_year, pub_date=pub_date, fpage=first("fpage"), lpage=first("lpage"),
        scan_pages=int(pc.get("count")) if pc is not None and (pc.get("count") or "").isdigit() else None,
        abstract_ar="\n".join(ab.get("ar") or []) or None, abstract_en="\n".join(ab.get("en") or []) or None,
        n_blocks=len(R["blocks"]), n_notes=len(R["notes"]), n_refs=len(list(root.iter("ref"))),
        n_works=len(R["works"]), n_figures=kinds.count("figure"), n_tables=kinds.count("table"),
        n_equations=kinds.count("equation"), n_fixes=len(R["fixes"]), n_misprints=len(R["misprints"]),
        prompt=stamp.get("prompt"), prompt_hash=stamp.get("prompt_hash"), rules_hash=stamp.get("rules_hash"),
        model=stamp.get("model"), made=stamp.get("made"), patches_applied=patches_applied,
        jats_path=str(jp), alto_path=str(ap), pdf_path=str(mdir / f"{stem}.pdf"), source="masters")
    R["journal_title"] = jm.findtext("journal-title-group/journal-title") if jm is not None else None
    R["sha"] = sha_of([jp, mdir / f"{stem}.metachanges.json", mdir / f"{stem}.patches.json"])
    return R


def _work(R, stem, origin, cid, seq, ord_, ec, printed, page, S):
    wid = f"{stem}|{'ref' if origin == 'reference' else 'note'}:{cid}|{seq}"
    names = []
    for k, n in enumerate(ec.iter("name")):
        sn = n.findtext("surname") or ""
        gn = n.findtext("given-names") or ""
        names.append((sn.strip(), gn.strip()))
    for sn in ec.iter("string-name"):
        names.append((text_of(sn), ""))
    for col in ec.iter("collab"):
        names.append((text_of(col), ""))
    for k, (sn, gn) in enumerate(names):
        R["work_authors"].append(dict(work_id=wid, seq=k, surname=sn, given=gn, name_key=key(f"{gn} {sn}")))
    f = {}
    extra = {}
    for c in ec:
        if not isinstance(c.tag, str):
            continue
        n = ln(c)
        if n == "person-group":
            continue
        t = text_of(c)
        if n == "ext-link":
            f["url"] = c.get(XLINK) or t
        elif n == "pub-id":
            if c.get("pub-id-type") == "doi":
                f["doi"] = t
            else:
                extra[f"pub-id:{c.get('pub-id-type')}"] = t
        elif n in ("article-title", "chapter-title", "source", "year", "volume", "issue", "fpage", "lpage",
                   "page-range", "publisher-name", "publisher-loc", "series"):
            f[n] = t
        else:
            extra[n] = t
    first_author = " ".join(x for x in (names[0][1], names[0][0]) if x) if names else None
    R["works"].append(dict(
        work_id=wid, stem=stem, origin=origin, container_id=cid, seq=seq, ord=ord_,
        pub_type=ec.get("publication-type"), authors=json.dumps(names, ensure_ascii=False) if names else None,
        first_author=first_author, first_author_key=key(names[0][0]) if names else None,
        article_title=f.get("article-title"), chapter_title=f.get("chapter-title"), source_title=f.get("source"),
        year=f.get("year"), year_int=year_of(f.get("year")), volume=f.get("volume"), issue=f.get("issue"),
        fpage=f.get("fpage"), lpage=f.get("lpage"), page_range=f.get("page-range"),
        publisher=f.get("publisher-name"), place=f.get("publisher-loc"), doi=f.get("doi"), url=f.get("url"),
        series=f.get("series"), extra=json.dumps(extra, ensure_ascii=False) if extra else None, printed=printed,
        page=page, **S))
