"""The document as a journal article: one JATS file per document (NISO Z39.96, JATS 1.4, the Journal Archiving
and Interchange tag set, which is meant for digitised back content).

    write(doc, quotes, marks, stem, path, alto_name)

What goes where (docs/decisions.md D20):

  front    journal-meta (Mandumah's journal code; a journal title only when a running head repeats on 3+
           pages), article-meta: the Mandumah id, the rubric above the title as the article's heading subject,
           the title and author(s) found on page 1 by position, volume and issue as the id spells them, the
           printed first and last page numbers when the page-number rule finds them, the page count, and
           custom-meta: where the text came from, the trust counts, the writing direction, the ALTO file.
  body     Azure's paragraphs in reading order. A large short paragraph opens a <sec>; running heads, page
           numbers and footers are left out of the article text (they stay in the ALTO file with their roles).
           Quran quotations are <named-content content-type="quran"> linked to https://tanzil.net/#S:A;
           a note marker "(3)" whose footnote is on the same page is an <xref ref-type="fn">.
  back     the footnotes (<fn-group>, one <fn> per numbered note, label = its number); a section headed
           المراجع / المصادر becomes a <ref-list> of <mixed-citation>s, one headed الهوامش / الحواشي more
           footnotes; and a <notes> section listing every quotation with its verse (Tanzil's vowelled text,
           verbatim and credited) and how the printed reading differs from it.

Ids: every block element carries the id of the ALTO TextBlock that holds its words (p<page>b<n>), so a word in
the ALTO file (p<page>w<n>) finds its place here through its block, and each ALTO block points back with
xlink:href="<stem>.jats.xml#<id>".

Direction: JATS has no direction attribute. The article is xml:lang="ar" and the text is stored in logical
(reading) order, as Unicode requires; a renderer applies the bidirectional algorithm (a stylesheet sets
direction: rtl for xml:lang="ar"). The direction is also stated in custom-meta.

Role rules are position guesses (experiment 20) and are said to be so in custom-meta; nothing here is checked
by a person.
"""
from __future__ import annotations

import re
import statistics
from collections import Counter
from pathlib import Path

from lxml import etree

from .document import is_real
from .quran import TANZIL_CREDIT, norm
from .trust import summary

XLINK = "http://www.w3.org/1999/xlink"
MML = "http://www.w3.org/1998/Math/MathML"
XMLNS = "http://www.w3.org/XML/1998/namespace"
DOCTYPE = ('<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with MathML3 '
           'v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">')
DTD_VERSION = "1.4"

_MARKER = re.compile(r"^[(\[]([0-9٠-٩]{1,3})[)\]][.,،:؛]?$")
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


ABSTRACT = {"ملخص", "الملخص", "مستخلص", "المستخلص", "ملخصالبحث", "abstract", "résumé", "resume", "summary"}
BASMALA = "بسماللهالرحمن"
BYLINE = {"بقلم", "اعداد", "تاليف"}
NOT_AUTHOR = ("أولا", "ثانيا", "مقدمة", "المقدمة", "تمهيد", "المبحث", "الفصل", "المطلب")


def front_matter(doc: dict) -> dict:
    """Rubric, title and authors on page 1, by position (resp: rules): among page 1's paragraphs before its first
    body paragraph, the title is the one with the largest letters (at least 1.25x the page's median word
    height); large paragraphs above it are the rubric (the journal's section name); the first short paragraph
    (<= 6 words) after it is the author line; anything after that is body."""
    words, paras, kinds = doc["words"], doc["paras"], doc["roles"]
    p1 = [p for p in paras if words[p["words"][0]]["page"] == 1]
    if not p1:
        return {}
    hs = [w["box"][3] - w["box"][1] for w in words if w["page"] == 1]
    med = statistics.median(hs) if hs else 1
    cand = []
    for p in p1:
        if kinds[p["idx"]] in ("pageHeader", "pageNumber", "pageFooter"):
            continue
        key = norm(_text(doc, p["words"]))
        if kinds[p["idx"]] in (None, "footnote") and len(p["words"]) > 12 or key in ABSTRACT \
                or _text(doc, p["words"]).strip().lower().rstrip(":") in ABSTRACT:
            break                                   # the body, or the abstract, has begun
        if key.startswith(BASMALA) or len(re.sub(r"[\W\d_]", "", _text(doc, p["words"]))) < 3:   # the invocation, or a stray mark: neither rubric, title nor author
            continue
        cand.append(p)
    if not cand:
        return {}
    size = {p["idx"]: statistics.median([words[k]["box"][3] - words[k]["box"][1] for k in p["words"]]) for p in cand}
    title = max(cand, key=lambda p: size[p["idx"]])
    if size[title["idx"]] < 1.25 * med or len(title["words"]) > 25:
        return {}
    i = cand.index(title)
    out = dict(title=title["idx"], rubric=[p["idx"] for p in cand[:i]], authors=[])
    rest = cand[i + 1:i + 3]
    if rest and norm(_text(doc, rest[0]["words"])) in BYLINE and len(rest) > 1:
        rest = rest[1:]                             # "بقلم :" alone on its line: the name is the next paragraph
    for p in rest[:1]:
        key = norm(_text(doc, p["words"]))
        if len(p["words"]) <= 6 and key not in BYLINE and not any(key.startswith(norm(h)) for h in NOT_AUTHOR):
            out["authors"].append(p["idx"])
    return out


def _text(doc, ks):
    return " ".join(doc["words"][k]["out"] for k in ks).strip()


def write(doc: dict, quotes: list[dict], marks: dict, stem: str, path: Path, alto_name: str | None = None) -> dict:
    """Write the JATS file; returns counts, and under "_ids" every id written (the ALTO writer links only to
    those)."""
    words, paras, kinds = doc["words"], doc["paras"], doc["roles"]
    bids = block_ids(doc)
    fm = front_matter(doc)
    used = set([fm.get("title")] + fm.get("rubric", []) + fm.get("authors", [])) if fm else set()

    nsmap = {"xlink": XLINK, "mml": MML}
    art = etree.Element("article", nsmap=nsmap, attrib={"article-type": "research-article",
                                                        "dtd-version": DTD_VERSION, f"{{{XMLNS}}}lang": "ar"})
    front = E(art, "front")
    jm = E(front, "journal-meta")
    parts = stem.split("-")
    E(jm, "journal-id", parts[0], journal_id_type="mandumah")
    head = running_head(doc)
    if head:
        jtg = E(jm, "journal-title-group")
        E(jtg, "journal-title", head, specific_use="guessed-from-running-heads")
    am = E(front, "article-meta")
    E(am, "article-id", stem, pub_id_type="other", assigning_authority="Mandumah")
    if fm.get("rubric"):
        ac = E(am, "article-categories")
        sg = E(ac, "subj-group", subj_group_type="heading")
        E(sg, "subject", " ".join(_text(doc, paras[i]["words"]) for i in fm["rubric"]), id=bids[fm["rubric"][0]][0][1])
    tg = E(am, "title-group")
    E(tg, "article-title", _text(doc, paras[fm["title"]]["words"]) if fm else None,
      id=bids[fm["title"]][0][1] if fm else None)
    if fm.get("authors"):
        cg = E(am, "contrib-group")
        for i in fm["authors"]:
            c = E(cg, "contrib", contrib_type="author", id=bids[i][0][1])
            E(c, "string-name", _text(doc, paras[i]["words"]))
    if len(parts) >= 3:
        E(am, "volume", parts[1].lstrip("0") or "0", content_type="from-mandumah-id")
        E(am, "issue", parts[2].lstrip("0") or "0", content_type="from-mandumah-id")
    printed = printed_pages(doc)
    if printed:
        first, last = printed[min(printed)], printed[max(printed)]
        E(am, "fpage", str(first - (min(printed) - 1)))
        E(am, "lpage", str(last + (len(doc["pages"]) - max(printed))))
    cnt = E(am, "counts")
    E(cnt, "page-count", count=len(doc["pages"]))
    cmg = E(am, "custom-meta-group")
    ts = summary(marks)

    def meta(name, value):
        cm = E(cmg, "custom-meta")
        E(cm, "meta-name", name)
        E(cm, "meta-value", value)
    meta("text-direction", "rtl (text stored in logical order; xml:lang carries the script)")
    meta("text-source", f"Azure Document Intelligence {doc.get('model') or ''} (API {doc.get('api') or '?'})"
         + ("; page 1 read by Google Gemini (the reading the PDF carries)" if doc["gemini_pages"] else ""))
    meta("structure-source", "position rules (inkscript enrich, experiment 20): title, authors, sections, footnotes "
         "and references are guesses from position and letter size, not checked by a person")
    meta("faithful-pdf", f"{stem}.pdf (each word drawn with its own printed ink)")
    if alto_name:
        meta("alto-file", alto_name)
    meta("trust", f"{ts['verified']} words verified, {ts['agreed']} agreed, {ts['flagged']} flagged"
         + (f", {ts['corrected']} corrected from a Quran verse after a judge on the ink ({stem}.corrections.json)"
            if ts.get("corrected") else "") + " (per-word marks in the ALTO file)")
    meta("quran-quotations", f"{len(quotes)} found, {sum(q['differs'] == 0 for q in quotes)} equal to the verse")

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
    fn_ids = {}                    # (page, label) -> fn id
    last_fn = None
    # footnotes first, so markers in the body can point at them
    for p in paras:
        if kinds[p["idx"]] != "footnote" or p["idx"] in used:
            continue
        pg = words[p["words"][0]]["page"]
        m = _FOOTLABEL.match(words[p["words"][0]]["text"])
        if m:
            lab = m.group(1).translate(_DIG)
            fid = f"fn-p{pg}-{lab}"
            while fid in fn_ids.values():
                fid += "x"
            fn_ids[(pg, lab)] = fid
    fn_el = {}
    stats = Counter()

    def inline(el, ks, page, refs=True):
        """Words of one paragraph into el: quotations wrapped, note markers linked."""
        i = 0
        first = True
        while i < len(ks):
            k = ks[i]
            q = qword.get(k)
            if not first:
                _append(el, " ")
            first = False
            if q:
                run = [k]
                while i + 1 < len(ks) and qword.get(ks[i + 1]) == q:
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
            else:
                w = words[k]
                m = _MARKER.match(w["out"])
                fid = fn_ids.get((page, m.group(1).translate(_DIG))) if m and refs else None
                if fid:
                    E(el, "xref", w["out"], ref_type="fn", rid=fid)
                    stats["fn_markers"] += 1
                else:
                    _append(el, w["out"])
            i += 1
    seen_ids = set()

    for p in paras:
        i = p["idx"]
        kind = kinds[i]
        if i in used or kind in ("pageHeader", "pageFooter", "pageNumber"):
            continue
        bid = bids[i][0][1]
        pg = bids[i][0][0]
        ks = p["words"]
        txt = _text(doc, ks)
        lang = _lang(txt)
        if kind == "footnote" and not notes_mode:
            if fng is None:
                fng = E(back, "fn-group")
            m = _FOOTLABEL.match(words[ks[0]]["text"])
            fid = fn_ids.get((pg, m.group(1).translate(_DIG))) if m else None
            if fid and fid not in fn_el:
                fn = E(fng, "fn", id=fid)
                E(fn, "label", m.group(1).translate(_DIG))
                fn_el[fid] = fn
                last_fn = fn
                if _FOOTLABEL.fullmatch(words[ks[0]]["text"].strip()):
                    ks = ks[1:]                  # the label word itself, and any lone bracket or dash after it
                    while ks and not is_real(words[ks[0]]["text"]) and len(words[ks[0]]["text"].strip()) <= 1:
                        ks = ks[1:]
            elif last_fn is not None:
                fn = last_fn                     # a note's continuation
            else:
                fn = last_fn = E(fng, "fn", id=f"fn-{bid}")
            if ks:                               # a label alone on its line: the next paragraph is its text
                e = E(fn, "p", id=bid, xml_lang=lang)
                inline(e, ks, pg, refs=False)
            elif fn.find("label") is not None and fn.find("label").get("id") is None:
                fn.find("label").set("id", bid)
            stats["footnotes"] += 1
            continue
        if kind in ("sectionHeading", "title"):
            key = norm(txt)
            if any(norm(r) and norm(r) in key for r in REFS) or txt.strip().lower() in REFS:
                notes_mode = "refs"
                reflist = E(back, "ref-list", id=bid)
                E(reflist, "title", txt)
                continue
            if any(norm(r) and norm(r) in key for r in NOTES) and len(ks) <= 3:
                notes_mode = "notes"
                if fng is None:
                    fng = E(back, "fn-group")
                continue
            notes_mode = None
            nsec += 1
            cur = E(body, "sec", id=f"sec{nsec}")
            t = E(cur, "title", id=bid)          # JATS gives <title> no xml:lang
            inline(t, ks, pg)
            stats["sections"] += 1
            continue
        if notes_mode == "refs":
            r = E(reflist, "ref", id=f"ref-{bid}")
            mc = E(r, "mixed-citation", id=bid, xml_lang=lang)
            inline(mc, ks, pg)
            stats["references"] += 1
            continue
        if notes_mode == "notes":
            m = _FOOTLABEL.match(words[ks[0]]["text"])
            fn = E(fng, "fn", id=f"fn-{bid}")
            if m:
                E(fn, "label", m.group(1).translate(_DIG))
            e = E(fn, "p", id=bid, xml_lang=lang)
            inline(e, ks, pg, refs=False)
            stats["endnotes"] += 1
            continue
        e = E(cur, "p", id=bid, xml_lang=lang)
        inline(e, ks, pg)
        stats["paragraphs"] += 1

    written = set(art.xpath("//fn/@id"))
    for x in list(art.iter("xref")):               # a marker whose note ended up elsewhere (a reference list) stays text
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
    stats.update(title=bool(fm), authors=len(fm.get("authors", [])) if fm else 0, quotations=len(quotes),
                 fpage_found=bool(printed))
    return dict(stats)


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
