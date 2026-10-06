"""The document as a journal article: one JATS file per document (NISO Z39.96, JATS 1.4, the Journal Archiving
and Interchange tag set, which is meant for digitised back content).

    write(doc, quotes, marks, stem, path, alto_name, meta=None, scan_pdf=None)

What goes where (docs/decisions.md D20, D21); the structure comes from structure.analyse (experiment 26):

  front    journal-meta (Mandumah's journal code; the journal's name when a running head or footer repeats on
           3+ pages), article-meta: the Mandumah id, the rubric above the title as the article's heading
           subject, the title (Gemini's when its title file exists, with Azure's reading of the ink beside it as
           an alt-title) and the authors (honorific in <prefix>, affiliation in <aff>), the year printed in the
           running heads, volume and issue as the id spells them (000 = none, "41,042" = 41-42), the printed
           first and last page numbers, the page count, and custom-meta: where the text and the structure came
           from, the word ids of the title and of each name in the ALTO file, the trust counts, the direction.
  body     Azure's paragraphs in reading order, page furniture and notes left out (they stay in the ALTO file
           with their roles). A heading opens a <sec>. Quran quotations are <named-content content-type="quran">
           linked to https://tanzil.net/#S:A; each note marker found in the text (glued "عاصم(٢).", alone "(٢)",
           raised) is an <xref ref-type="fn"> to its note, the word's letters kept outside the link.
  back     the notes (<fn-group>, one <fn> per note at the foot of a page or in the list at the end, label =
           its number); a section headed المراجع / المصادر becomes a <ref-list> of <mixed-citation>s, one
           headed الهوامش / الحواشي more notes; and a <notes> section listing every quotation with its verse
           (Tanzil's vowelled text, verbatim and credited) and how the printed reading differs from it.

Ids: every block element carries the id of the ALTO TextBlock that holds its words (p<page>b<n>), so a word in
the ALTO file (p<page>w<n>) finds its place here through its block, and each ALTO block points back with
xlink:href="<stem>.jats.xml#<id>". A block split between two elements (a byline glued to a heading, two notes in
one Azure paragraph) gives its id to the first and p<page>b<n>-2 to the next; a block of the front matter that
no element carries (a lone "بقلم :") is anchored by a custom-meta with its id.

Direction: JATS has no direction attribute. The article is xml:lang="ar" and the text is stored in logical
(reading) order, as Unicode requires; a renderer applies the bidirectional algorithm (a stylesheet sets
direction: rtl for xml:lang="ar"). The direction is also stated in custom-meta.

The structure is read from size, ink, place and repetition, and said to be so in custom-meta; nothing here is
checked by a person.
"""
from __future__ import annotations

import re
from collections import Counter
from pathlib import Path

from lxml import etree

from .document import is_real
from .quran import TANZIL_CREDIT, norm
from .structure import NOTE_LABEL_HEAD, id_parts, key
from .trust import summary

XLINK = "http://www.w3.org/1999/xlink"
MML = "http://www.w3.org/1998/Math/MathML"
XMLNS = "http://www.w3.org/XML/1998/namespace"
DOCTYPE = ('<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 '
           'v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">')
DTD_VERSION = "1.4"

_FOOTLABEL = re.compile(r"^\s*[(\[]?([0-9٠-٩]{1,3})[)\]]?\s*[-–.)]?")
_DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
REFS = ("المراجع", "المصادر", "مصادر", "مراجع", "ثبت", "قائمه المصادر", "references", "bibliography", "sources")
NOTES = ("الهوامش", "الحواشي", "هوامش", "حواشي", "notes", "endnotes")
LATIN_WORDS = {"en": {"the", "of", "and", "in", "to", "is", "a", "for", "on", "with"},
               "fr": {"le", "la", "les", "de", "des", "et", "du", "en", "un", "une", "est", "dans"}}


def E(parent, tag, text=None, **attrs):
    a = {}
    for k, v in attrs.items():
        if v is None:
            continue
        if k.startswith("xlink_"):
            k = f"{{{XLINK}}}{k[6:].replace('_', '-')}"
        elif k == "xml_lang":
            k = f"{{{XMLNS}}}lang"
        else:
            k = k.replace("_", "-")
        a[k] = str(v)
    e = etree.SubElement(parent, tag, a)
    if text is not None:
        e.text = text
    return e


def _append(el, text):
    """Append text at the end of an element's mixed content."""
    if len(el):
        el[-1].tail = (el[-1].tail or "") + text
    else:
        el.text = (el.text or "") + text


def block_ids(doc: dict) -> dict[int, list[tuple[int, str]]]:
    """Paragraph idx -> [(page, block id)], one block per page the paragraph has words on; ids number the
    blocks of each page in reading order (p<page>b<n>). Shared with the ALTO writer."""
    cnt = Counter()
    out = {}
    for p in doc["paras"]:
        pages = []
        for k in p["words"]:
            pg = doc["words"][k]["page"]
            if pg not in pages:
                pages.append(pg)
        out[p["idx"]] = []
        for pg in pages:
            cnt[pg] += 1
            out[p["idx"]].append((pg, f"p{pg}b{cnt[pg]}"))
    return out


def _lang(text: str) -> str | None:
    """xml:lang for a paragraph that is mostly Latin script (None: Arabic, inherited)."""
    ar = len(re.findall(r"[ء-ي]", text))
    la = len(re.findall(r"[A-Za-zÀ-ɏ]", text))
    if la <= ar:
        return None
    toks = set(re.findall(r"[a-zà-ÿ]+", text.lower()))
    best = max(LATIN_WORDS, key=lambda k: len(toks & LATIN_WORDS[k]))
    return best if toks & LATIN_WORDS[best] else "und"




def key_differs(a: str, b: str) -> bool:
    return key(a) != key(b)


def structure_of(doc: dict, meta: dict | None = None, scan_pdf=None) -> dict:
    """The document's structure (structure.analyse), computed once and kept in doc["structure"]; the
    paragraph roles in doc["roles"] are replaced by it, so the ALTO file tags its blocks the same way."""
    st = doc.get("structure")
    if st is None:
        from .structure import analyse
        st = doc["structure"] = analyse(doc, meta, scan_pdf)
        doc["roles"] = list(st["kinds"])
        for p, r in zip(doc["paras"], doc["roles"]):
            p["kind"] = r
    return st


def front_matter(doc: dict) -> dict:
    """Paragraph-level view of the front matter for the ALTO writer's block roles: the paragraph of the title's
    first word, the rubric's paragraphs, each author's paragraph (structure.analyse finds them word by word)."""
    st = structure_of(doc)
    fr = st["front"]
    if not fr.get("title_words"):
        return {}
    W = doc["words"]
    paras = lambda ks: list(dict.fromkeys(W[k]["para"] for k in ks))
    title = W[fr["title_words"][0]]["para"]
    rub = [i for i in paras(fr.get("rubric_words", [])) if i != title]
    auth = [i for a in fr.get("authors", []) if a["words"] for i in paras(a["words"])[:1] if i != title]
    return dict(title=title, rubric=rub, authors=auth)


def _text(doc, ks):
    return " ".join(doc["words"][k]["out"] for k in ks).strip()


def _ids(doc, ks):
    return " ".join(doc["words"][k]["id"] for k in ks)


def write(doc: dict, quotes: list[dict], marks: dict, stem: str, path: Path, alto_name: str | None = None,
          meta: dict | None = None, scan_pdf=None) -> dict:
    """Write the JATS file; returns counts, and under "_ids" every id written (the ALTO writer links only to
    those). meta: structure.read_meta (Gemini's title file, the id's parts); scan_pdf: for stroke widths."""
    words, paras = doc["words"], doc["paras"]
    st = structure_of(doc, meta, scan_pdf)
    kinds = st["kinds"]
    fr = st["front"]
    idp = st["id"] or id_parts(stem)
    bids = block_ids(doc)
    claimed = set()

    def claim(bid):
        """The block id if no element carries it yet, else a derived one (a paragraph split between two
        elements: the first keeps the block's id, which the ALTO block points at)."""
        if bid not in claimed:
            claimed.add(bid)
            return bid
        n = 2
        while f"{bid}-{n}" in claimed:
            n += 1
        claimed.add(f"{bid}-{n}")
        return f"{bid}-{n}"

    def bid_of(k):
        """The block id of the paragraph (on the word's page) that holds word k."""
        w = words[k]
        return next(b for pg, b in bids[w["para"]] if pg == w["page"])

    front_words = st["front_words"]
    note_word = st["note_word"]
    furniture = st["furniture"]

    nsmap = {"xlink": XLINK, "mml": MML}
    art = etree.Element("article", nsmap=nsmap, attrib={"article-type": "research-article",
                                                        "dtd-version": DTD_VERSION, f"{{{XMLNS}}}lang": "ar"})
    front = E(art, "front")
    jm = E(front, "journal-meta")
    E(jm, "journal-id", idp.get("journal") or stem.split("-")[0], journal_id_type="mandumah")
    head = st.get("journal") or running_head(doc)
    if head:
        jtg = E(jm, "journal-title-group")
        E(jtg, "journal-title", head, specific_use="found-in-running-heads")
    am = E(front, "article-meta")
    E(am, "article-id", stem, pub_id_type="other", assigning_authority="Mandumah")
    ink_meta = []                                  # (name, value, id) for custom-meta
    if fr.get("rubric_words"):
        ac = E(am, "article-categories")
        sg = E(ac, "subj-group", subj_group_type="heading")
        E(sg, "subject", _text(doc, fr["rubric_words"]), id=claim(bid_of(fr["rubric_words"][0])))
        ink_meta.append(("rubric-words", _ids(doc, fr["rubric_words"]), None))
    tg = E(am, "title-group")
    if fr.get("title_words"):
        tw = fr["title_words"]
        printed = _text(doc, tw)
        E(tg, "article-title", fr["title"], id=claim(bid_of(tw[0])))
        if fr.get("title_source", "").startswith("gemini") and key_differs(printed, fr["title"]):
            E(tg, "alt-title", printed, alt_title_type="azure-reading-of-the-ink")
        ink_meta.append(("title-words", _ids(doc, tw), None))
        ink_meta.append(("title-source", fr.get("title_source", ""), None))
    else:
        E(tg, "article-title")
    authors = [a for a in fr.get("authors", []) if a.get("name")]
    if authors:
        cg = E(am, "contrib-group")
        for n, a in enumerate(authors, 1):
            aw = a.get("prefix_words", []) + a["words"]
            c = E(cg, "contrib", contrib_type="author", id=claim(bid_of(aw[0])) if aw else f"contrib{n}")
            sn = E(c, "string-name")
            if a.get("prefix"):
                E(sn, "prefix", a["prefix"])
                _append(sn, " " + a["name"])
            else:
                sn.text = a["name"]
            if a.get("aff"):
                E(c, "aff", a["aff"])
            if a["words"]:
                ink_meta.append((f"author-{n}-words", _ids(doc, a["words"]), None))
            ink_meta.append((f"author-{n}-source", a.get("source", ""), None))
    yr = st.get("year")
    if yr:
        pd = E(am, "pub-date", publication_format="print", date_type="pub",
               calendar="islamic" if yr[0] == "hijri" else "gregorian")
        E(pd, "year", str(yr[1]))
    if idp.get("volume"):
        E(am, "volume", idp["volume"], content_type="from-mandumah-id")
    if idp.get("issue"):
        E(am, "issue", idp["issue"], content_type="from-mandumah-id")
    elif idp.get("issue_special"):
        E(am, "issue", "special", content_type="from-mandumah-id")
    printed_p = printed_pages(doc)
    if printed_p:
        first, last = printed_p[min(printed_p)], printed_p[max(printed_p)]
        E(am, "fpage", str(first - (min(printed_p) - 1)))
        E(am, "lpage", str(last + (len(doc["pages"]) - max(printed_p))))
    cnt = E(am, "counts")
    E(cnt, "page-count", count=len(doc["pages"]))
    cmg = E(am, "custom-meta-group")
    ts = summary(marks)

    def meta_(name, value, id_=None):
        cm = E(cmg, "custom-meta", id=id_)
        E(cm, "meta-name", name)
        E(cm, "meta-value", value)
    meta_("text-direction", "rtl (text stored in logical order; xml:lang carries the script)")
    meta_("text-source", f"Azure Document Intelligence {doc.get('model') or ''} (API {doc.get('api') or '?'})"
          + ("; page 1 read by Google Gemini (the reading the PDF carries)" if doc["gemini_pages"] else ""))
    meta_("structure-source", "inkscript enrich (experiment 26): furniture by repetition and place; notes by "
          "small lines at the foot of a page opening with a number, linked to the marker in that page's text; "
          "headings by size, bold ink, numbering, colon and space; title and authors "
          + ("from Gemini's title file aligned to the printed words" if st.get("gemini")
             else "from page 1's layout") + ". Not checked by a person.")
    if idp.get("seq"):
        meta_("article-sequence-in-issue", idp["seq"] + " (from the Mandumah id)")
    meta_("faithful-pdf", f"{stem}.pdf (each word drawn with its own printed ink)")
    if alto_name:
        meta_("alto-file", alto_name)
    meta_("trust", f"{ts['verified']} words verified, {ts['agreed']} agreed, {ts['flagged']} flagged"
          + (f", {ts['corrected']} corrected from a Quran verse after a judge on the ink ({stem}.corrections.json)"
             if ts.get("corrected") else "") + " (per-word marks in the ALTO file)")
    meta_("quran-quotations", f"{len(quotes)} found, {sum(q['differs'] == 0 for q in quotes)} equal to the verse")
    for name, value, _ in ink_meta:
        meta_(name, value)

    body = E(art, "body")
    back = E(art, "back")
    fng = None
    reflist = None
    notes_mode = None              # inside a "references" or "notes" section at the end
    cur = body
    nsec = 0
    qword = {}
    for n, qt in enumerate(quotes, 1):
        for k in qt["doc_words"]:
            qword[k] = n
    stats = Counter()
    seen_ids = set()
    markers = st["markers"]
    notes = st["notes"]
    fn_id = {}
    for n, nt in enumerate(notes):
        lab = "star" if nt["label"] == "*" else nt["label"]
        base = f"fn-p{nt['page']}-{lab}" if lab else f"fn-p{nt['page']}-x{n}"
        fid = base
        while fid in fn_id.values():
            fid += "x"
        fn_id[n] = fid

    def inline(el, ks, refs=True, override=None):
        """Words into el: quotations wrapped, note markers linked; override: word -> the text to write."""
        i = 0
        first = True
        while i < len(ks):
            k = ks[i]
            q = qword.get(k)
            if not first:
                _append(el, " ")
            first = False
            if refs and k in markers:          # a marker glued to the last word of a quotation: the link wins
                q = None
            if q:
                run = [k]
                while i + 1 < len(ks) and qword.get(ks[i + 1]) == q and not (refs and ks[i + 1] in markers):
                    i += 1
                    run.append(ks[i])
                qt = quotes[q - 1]
                nc = E(el, "named-content", _text(doc, run), content_type="quran",
                       specific_use="matches-verse" if qt["differs"] == 0 else "differs-from-verse",
                       xlink_href=f"https://tanzil.net/#{qt['sura']}:{qt['aya']}",
                       xlink_title=f"{qt['sura_name']} {qt['ref']}")
                nc.set("id", f"quran{q}" if f"quran{q}" not in seen_ids else f"quran{q}-{len(seen_ids)}")
                seen_ids.add(nc.get("id"))
                stats["quran_inline"] += 1
            elif refs and k in markers:
                m = markers[k]
                if m["head"]:
                    _append(el, m["head"])
                E(el, "xref", m["mark"], ref_type="fn", rid=fn_id[m["note"]])
                if m["tail"]:
                    _append(el, m["tail"])
                stats["fn_markers"] += 1
            else:
                _append(el, (override or {}).get(k, words[k]["out"]))
            i += 1

    # the notes at the foot of the pages, in page order; one <p> per Azure paragraph the note runs through, so
    # every ALTO block of a note finds its place here
    if notes:
        fng = E(back, "fn-group")
        for n, nt in enumerate(notes):
            ks = list(nt["words"])
            fn = E(fng, "fn", id=fn_id[n])
            if nt["label"]:
                E(fn, "label", nt["label"])
            override = {}
            lw = nt.get("label_word")
            if lw is not None and lw in ks:
                t = words[lw]["out"]
                if nt["label"] == "*":
                    rest = re.sub(r"^\s*(\(\s*\*\s*\)|\*)", "", t).strip()
                else:
                    m = NOTE_LABEL_HEAD.match(t) or re.match(r"^\s*[0-9٠-٩۰-۹]{1,3}\s*[-–.)]?", t)
                    rest = t[m.end():].lstrip(" -–.:") if m else t
                if rest:
                    override[lw] = rest              # the label glued to the first word: "(٤)سورة"
                else:
                    pos = ks.index(lw)
                    ks.pop(pos)                      # the label word itself, and any lone bracket or dash after it
                    while pos < len(ks) and not is_real(words[ks[pos]]["text"]) and len(words[ks[pos]]["text"].strip()) <= 1:
                        ks.pop(pos)
            groups = []
            for k in ks:
                g = (words[k]["para"], words[k]["page"])
                if not groups or groups[-1][0] != g:
                    groups.append((g, []))
                groups[-1][1].append(k)
            if not groups:
                E(fn, "p", id=claim(bid_of(nt["words"][0])))
            for g, gk in groups:
                e = E(fn, "p", id=claim(bid_of(gk[0])), xml_lang=_lang(_text(doc, gk)))
                inline(e, gk, refs=False, override=override)
            stats["footnotes"] += 1

    for p in paras:
        i = p["idx"]
        kind = kinds[i]
        if i in furniture:
            continue
        ks = [k for k in p["words"] if k not in front_words and k not in note_word]
        if not ks:
            continue
        bid = claim(bid_of(ks[0]))
        txt = _text(doc, ks)
        lang = _lang(txt)
        if kind == "sectionHeading":
            key_ = norm(txt)
            if any(norm(r) and norm(r) in key_ for r in REFS) or txt.strip().lower() in REFS:
                notes_mode = "refs"
                reflist = E(back, "ref-list", id=bid)
                E(reflist, "title", txt)
                continue
            if any(norm(r) and norm(r) in key_ for r in NOTES) and len(ks) <= 3:
                notes_mode = "notes"
                if fng is None:
                    fng = E(back, "fn-group")
                if fng.find("fn") is None and fng.find("title") is None:
                    E(fng, "title", txt, id=bid)
                else:                            # notes heading after the page notes: an anchor for its block
                    meta_("notes-heading", txt, bid)
                continue
            notes_mode = None
            hw = set(st["head_words"].get(i, ks))
            before = [k for k in ks if k not in hw]
            if before:                           # the author's name repeated over the text, then the heading
                e = E(cur, "p", id=bid, xml_lang=_lang(_text(doc, before)))
                inline(e, before)
                stats["paragraphs"] += 1
                bid = claim(bid)
                ks = [k for k in ks if k in hw]
            nsec += 1
            cur = E(body, "sec", id=f"sec{nsec}")
            t = E(cur, "title", id=bid)          # JATS gives <title> no xml:lang
            inline(t, ks)
            stats["sections"] += 1
            continue
        if notes_mode == "refs":
            r = E(reflist, "ref", id=f"ref-{bid}")
            mc = E(r, "mixed-citation", id=bid, xml_lang=lang)
            inline(mc, ks, refs=False)
            stats["references"] += 1
            continue
        if notes_mode == "notes":
            m = _FOOTLABEL.match(words[ks[0]]["text"])
            fn = E(fng, "fn", id=f"fn-{bid}")
            if m:
                E(fn, "label", m.group(1).translate(_DIG))
            e = E(fn, "p", id=bid, xml_lang=lang)
            inline(e, ks, refs=False)
            stats["endnotes"] += 1
            continue
        e = E(cur, "p", id=bid, xml_lang=lang)
        inline(e, ks)
        stats["paragraphs"] += 1

    # every block of the front matter that no element carries yet (a byline word on its own line, the second
    # line of a title) gets an anchor, so each ALTO block finds its place here
    for i, p in enumerate(paras):
        if i in furniture:
            continue
        for pg, b in bids[i]:
            if b not in claimed:
                claimed.add(b)
                ks = [k for k in p["words"] if words[k]["page"] == pg]
                what = "front-matter-block" if any(k in front_words for k in ks) else "block-without-element"
                meta_(what, _text(doc, ks), b)
    written = set(art.xpath("//fn/@id"))
    for x in list(art.iter("xref")):               # a marker whose note ended up elsewhere stays text
        if x.get("rid") not in written:
            par = x.getparent()
            prev = x.getprevious()
            txt = (x.text or "") + (x.tail or "")
            if prev is not None:
                prev.tail = (prev.tail or "") + txt
            else:
                par.text = (par.text or "") + txt
            par.remove(x)
            stats["fn_markers"] -= 1
    for fn in back.iter("fn"):                   # a note whose text was never found still needs a paragraph
        if fn.find("p") is None:
            E(fn, "p")
    if quotes:
        nt = E(back, "notes", notes_type="quran-quotations", id="quran-notes")
        E(nt, "title", "الآيات القرآنية المقتبسة")
        E(nt, "p", f"Each quotation found in the text, linked to its verse and compared word for word. Verse text: "
          f"{TANZIL_CREDIT}, reproduced verbatim.", xml_lang="en")
        for n, qt in enumerate(quotes, 1):
            sp = E(nt, "p", id=f"quran{n}-note")
            label = f"{qt['sura_name']} {qt['sura']}:{qt['aya']}" + (f"–{qt['aya_end']}" if qt["aya_end"] != qt["aya"] else "")
            E(sp, "ext-link", label, ext_link_type="uri", xlink_href=f"https://tanzil.net/#{qt['sura']}:{qt['aya']}")
            _append(sp, " ")
            E(sp, "named-content", qt["verse"], content_type="quran-verse", specific_use="tanzil-simple-1.1")
            status = "يطابق نص الآية" if qt["differs"] == 0 else f"{qt['differs']} موضع يختلف عن نص الآية"
            if qt.get("corrected"):                  # experiment 27: words corrected to the verse after a judge on the ink
                status += f" (صُحّح {qt['corrected']} موضع بعد مراجعة الحبر)"
            _append(sp, f" — {status}")
            for o in qt["ops"]:
                if not o.get("verdict"):
                    continue
                rd = " ".join(words[k]["out"] for k in o["doc"]) or "—"
                vs = " ".join(x["v"] for x in o["q"]) or "—"
                _append(sp, f"؛ المطبوع «{rd}» والآية «{vs}»")
            if qt.get("citation"):
                _append(sp, f"؛ العزو في النص: {qt['citation']['text']}")
    if not len(back):
        art.remove(back)
    if not len(body):
        E(body, "p")
    etree.indent(art, space=" ")      # only element-only content gets whitespace; mixed content is left as is
    path = Path(path)
    data = etree.tostring(art, encoding="unicode")
    path.write_text('<?xml version="1.0" encoding="UTF-8"?>\n' + DOCTYPE + "\n" + data + "\n", encoding="utf-8")
    stats["_ids"] = set(art.xpath("//@id"))
    stats.update(title=bool(fr.get("title_words")), authors=len(authors), quotations=len(quotes),
                 fpage_found=bool(printed_p), notes=len(notes), notes_linked=len({m["note"] for m in markers.values()}),
                 )
    out = dict(stats)
    out["title_source"] = fr.get("title_source", "")
    return out


def printed_pages(doc: dict) -> dict[int, int]:
    """Physical page -> printed page number, where the page-number rule found one that fits a steady run
    (number - page constant on most pages)."""
    found = {}
    for p in doc["paras"]:
        if doc["roles"][p["idx"]] == "pageNumber":
            t = re.sub(r"[^0-9٠-٩]", "", p["content"]).translate(_DIG)
            pg = doc["words"][p["words"][0]]["page"]
            if t and len(t) <= 4:
                found.setdefault(pg, int(t))
    if not found:
        return {}
    off = Counter(v - k for k, v in found.items()).most_common(1)[0]
    if off[1] < max(2, len(found) // 2):
        return {}
    return {k: v for k, v in found.items() if v - k == off[0]}


def running_head(doc: dict) -> str | None:
    """The most repeated running head, if it repeats on 3+ pages and is not the title (experiment 20)."""
    c = Counter()
    for p in doc["paras"]:
        if doc["roles"][p["idx"]] == "pageHeader":
            t = re.sub(r"[\d٠-٩۰-۹\-–—()|]", "", " ".join(doc["words"][k]["out"] for k in p["words"])).strip()
            if len(t) > 3:
                c[t] += 1
    if c:
        t, n = c.most_common(1)[0]
        if n >= 3:
            return t
    return None
