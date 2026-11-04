"""Experiment 43: parsed references and the works a note cites (prompt v3.2 candidate; no model calls here).

Prompt v3.2 asks, per reference block, for "parsed": [W] and, per footnote / endnote that cites works, for
"cites": [W, ...], W = {type, authors [{surname, given}], year, title, source, volume, issue, pages, publisher,
place, series (v3.3), doi, url, lang}, every value an exact substring of the printed entry. structure.assemble keeps only known
block keys, so the parts are read from the answer files themselves (the rules/ or raw/ folder the masters are built
from) and matched to the JATS by the block's first line: line id -> ALTO TextLine id (Mo.tl_of) -> the <target> of
that id -> its ref or fn.

JATS (1.4 Archiving, checked against the DTD):
  ref   <mixed-citation> (the printed entry, untouched) then one <element-citation publication-type=...> per work
        (ref-model allows several citations in one ref)
  fn    after the note's printed paragraph(s): <p content-type="parsed-citations"> holding one element-citation per
        cited work (fn-model is (label?, p+); p takes %citation.class;). The p has no <target>, so the Layout view
        (drawn from the ALTO's targets) never shows it; inkscript edition skips it (edition/model.py), as it skips an
        element-citation beside a mixed-citation, so nothing prints twice.
Every field is checked: whitespace-normalised, it must be a substring of the entry's printed text (else dropped and
counted); a year must hold a number from 1 to 2100 (a Hijri year passes; «د.ت» is dropped: the printed entry keeps
it). A work left with no field is not written.
Tidy (2026-10-19, applies to saved answers too): volume / issue / pages lose printed labels («Vol.», «ع»، «مج»، «ص»,
«pp.», «وما بعدها», «et s.»); a year given as a whole date keeps the year in <year> and the date in <string-date>; a
web address cut by Azure's line breaks is joined. The mixed-citation / note text keep the printed form.
Prompt v3.5 (draft, 2026-10-22; v35_parts): W's new optional keys — editors, translators, an author's "died",
edition, cal / year2, cited (the page pointed to, apart from the work's own range), accessed, library / shelf / folio
(type manuscript), conf (type conference), degree — written only when present, so every earlier answer builds the
same element-citations as before.

    import refs43; refs43.add_parsed(Mo, A, raw_dir)        -> Counter of what was written and dropped
"""
from __future__ import annotations

import json
import os
import re
from collections import Counter
from pathlib import Path

from lxml import etree

XL = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
HYPH_BREAK = re.compile(r"(?<=[^\W\d_])[-‐­]\s+(?=[^\W\d_])")   # experiment 65 M7: «Psychol- ogy»
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TYPES = {"book": "book", "journal": "journal", "chapter": "book", "thesis": "thesis", "web": "web", "other": "other",
         "manuscript": "manuscript", "conference": "confproc"}          # the last two: prompt v3.5 types
SIMPLE = [("volume", "volume"), ("issue", "issue"), ("publisher", "publisher-name"), ("place", "publisher-loc")]


def ws(s) -> str:
    return " ".join(str(s or "").split())


def answers_of(a: dict, raw_dir: Path) -> list[dict]:
    """The chunk answers of one article in raw_dir (rules43 output or raw answers), in page order."""
    import structure as ST
    out = []
    for x, y in ST.chunks(a):
        f = Path(raw_dir) / f"{a['stem']}_c{x:03d}-{y:03d}.json"
        if f.exists():
            ans = json.loads(f.read_text(encoding="utf-8")).get("answer")
            if isinstance(ans, dict):
                out.append(ans)
    return out


def parsed_blocks(answers: list[dict]):
    """(kind "parsed" | "cites", first line id, [W]) for each block that carries parts."""
    for ans in answers:
        for pg in ans.get("pages") or []:
            for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
                if not isinstance(b, dict):
                    continue
                lines = b.get("lines") or []
                if not lines:
                    continue
                for key in ("parsed", "cites"):
                    ws_ = b.get(key)
                    if isinstance(ws_, dict):
                        ws_ = [ws_]
                    if isinstance(ws_, list) and ws_:
                        yield key, str(lines[0]), [w for w in ws_ if isinstance(w, dict)]


def year_ok(s: str) -> bool:
    m = re.search(r"\d{1,4}", s.translate(DIGITS))
    return bool(m) and 1 <= int(m.group(0)) <= 2100


# ---- tidy (2026-10-19, after the v3.2 hand check: 29 "loose" fields were right values carrying printed labels).
# The printed form stays in the mixed-citation / the note's text; the element-citation gets the clean value.
_LBL = [r"vols?\.?", r"v\.", r"tome", r"t\.", r"bd\.?", r"nos?\.?", r"n[°º]\.?", r"nr\.?", r"num(?:éro|ber)?\.?",
        r"issue", r"fasc\.?", r"pp?\.", r"pp", r"pages?", r"s\.",
        r"المجلد", r"مجلد", r"مج\.?", r"م\.", r"الجزء", r"جزء", r"ج\.?", r"العدد", r"عدد", r"ع\.?", r"الصفحات", r"صفحة",
        r"صص\.?", r"ص\.?", r"رقم"]
_TAIL = [r"وما\s+بعدها", r"و\s*ما\s+يليها", r"et\s+s(?:uiv)?\.?", r"et\s+sq{1,2}\.?", r"ff?\."]
_LBL_RE = re.compile(r"^(?:\s*(?:" + "|".join(_LBL) + r")(?=[\s\d٠-٩۰-۹:.\-–(]|$)\s*[:.]?\s*)+", re.I)
_TAIL_RE = re.compile(r"(?:\s*[,،؛;]?\s*(?:" + "|".join(_TAIL) + r"))+\s*[.,،]?\s*$", re.I)
_YEAR_RE = re.compile(r"(?<![\d٠-٩۰-۹])[\d٠-٩۰-۹]{3,4}(?![\d٠-٩۰-۹])")


def clean_label(v: str) -> str:
    """«Vol. 6» -> «6», «ع ٣» -> «٣», «ص ١٢٠ وما بعدها» -> «١٢٠», «pp. 80-94» -> «80-94» (digits kept as printed)."""
    out = _TAIL_RE.sub("", _LBL_RE.sub("", ws(v)))
    out = out.strip(" .,،؛;:()")
    return out or ws(v)


def split_year(v: str) -> tuple[str, str | None]:
    """A year out of a whole date: («15 mars 1987» -> «1987», the date kept); a bare year («١٩٨٤», «1410هـ») -> as is."""
    v = ws(v)
    m = _YEAR_RE.search(v)
    if not m or v.strip(" .،,") == m.group(0):
        return v, None
    rest = (v[:m.start()] + v[m.end():]).strip(" .،,")
    if re.fullmatch(r"(?:هـ|ه|م|ق|AD|AH|H|BC|ق\.?\s*م)\.?", rest):   # 1410هـ / 1990م: a year with its calendar letter
        return v, None
    return m.group(0), v


_URL_CHARS = r"[A-Za-z0-9\-._~:/?#\[\]@!$&'()*+,;=%]"


def join_url(v: str, printed: str) -> str | None:
    """A web address Azure's line breaks cut («http://www.ex ample.org/a»): the model's value without spaces, found in
    the printed text allowing spaces between its characters, then grown over the pieces that follow it in print
    (glued by one space) while the address so far ends mid-way (/ . - _ = ? &) or the next piece holds a / or a dot."""
    u = re.sub(r"\s+", "", str(v or ""))
    if not u:
        return None
    m = re.search(r"\s?".join(re.escape(ch) for ch in u), printed)
    if not m:
        return None
    tail = printed[m.end():]
    while True:
        g = re.match(r"\s(" + _URL_CHARS + r"+)", tail)
        if not g:
            break
        piece = g.group(1)
        if not (re.search(r"[/.\-_=?&]$", u) or re.search(r"[/.]", piece.rstrip(".,;)"))):
            break
        u += piece
        tail = tail[g.end():]
    return u.rstrip(".,;)") or None


def citation(w: dict, printed: str, st: Counter, lang_default: str) -> etree._Element | None:
    """One element-citation from a work's parts; every value checked against the printed text."""
    def ok(field, v):
        v = ws(v)
        if not v:
            return None
        if v not in printed and os.environ.get("EXP65_OFF") != "1":
            # experiment 65 M7: a part broken at a hyphenated line break («Psychol- ogy») is the printed word
            # («Psychology» or «Psychol-ogy» in the entry); the joined form is kept when it is in the entry
            for alt in (HYPH_BREAK.sub("", v), HYPH_BREAK.sub("-", v)):
                if alt != v and alt in printed:
                    st[f"refs_hyphen_joined_{field}"] += 1
                    return alt
            if HYPH_BREAK.search(printed) and v in HYPH_BREAK.sub("", printed):
                st[f"refs_hyphen_joined_{field}"] += 1
                return v
            st[f"refs_dropped_not_printed_{field}"] += 1
            return None
        if v not in printed:
            st[f"refs_dropped_not_printed_{field}"] += 1
            return None
        return v

    typ = str(w.get("type") or "other").lower()
    ec = etree.Element("element-citation", {"publication-type": TYPES.get(typ, "other")})
    lg = str(w.get("lang") or "").lower()
    if lg in ("ar", "fr", "en") and lg != lang_default:
        ec.set(XML_LANG, lg)
    n = 0
    names = []
    for au in w.get("authors") or []:
        if isinstance(au, str):
            au = {"surname": au}
        if not isinstance(au, dict):
            continue
        sn, gn = ok("surname", au.get("surname")), ok("given", au.get("given"))
        if sn:
            nm = etree.Element("name")
            etree.SubElement(nm, "surname").text = sn
            if gn:
                etree.SubElement(nm, "given-names").text = gn
            names.append(nm)
        elif gn:
            sn_ = etree.Element("string-name")
            sn_.text = gn
            names.append(sn_)
    if names:
        pg = etree.SubElement(ec, "person-group", {"person-group-type": "author"})
        for nm in names:
            pg.append(nm)
        n += len(names)
    title, source = ok("title", w.get("title")), ok("source", w.get("source"))
    if typ == "chapter" and title:
        etree.SubElement(ec, "chapter-title").text = title
        n += 1
    elif title and (source or typ in ("journal", "web")):
        etree.SubElement(ec, "article-title").text = title
        n += 1
    elif title:                                 # a book, thesis, manuscript: its title is the source
        source = source or title
    if source:
        etree.SubElement(ec, "source").text = source
        n += 1
    y = ok("year", w.get("year"))
    if y and year_ok(y):
        yy, whole = split_year(y)
        etree.SubElement(ec, "year").text = yy
        if whole:
            etree.SubElement(ec, "string-date").text = whole
            st["refs_tidy_year_from_date"] += 1
        n += 1
    elif y:
        st["refs_dropped_year_not_a_year"] += 1
    for k, tag in SIMPLE:
        v = ok(k, w.get(k))
        if v:
            if k in ("volume", "issue"):
                c = clean_label(v)
                if c != v:
                    st[f"refs_tidy_label_{k}"] += 1
                v = c
            etree.SubElement(ec, tag).text = v
            n += 1
    ser = ok("series", w.get("series"))
    if ser:
        etree.SubElement(ec, "series").text = ser
        n += 1
    pp = ok("pages", w.get("pages"))
    if pp:
        c = clean_label(pp)
        if c != pp:
            st["refs_tidy_label_pages"] += 1
        pp = c
        a = pp.translate(DIGITS)
        m = re.fullmatch(r"\D*?(\d+)\s*[-–—]\s*(\d+)\D*", a)
        if m:
            etree.SubElement(ec, "fpage").text = m.group(1)
            etree.SubElement(ec, "lpage").text = m.group(2)
        elif re.fullmatch(r"\d+", a):
            etree.SubElement(ec, "fpage").text = a
        etree.SubElement(ec, "page-range").text = pp
        n += 1
    doi = ok("doi", w.get("doi"))
    if doi:
        etree.SubElement(ec, "pub-id", {"pub-id-type": "doi"}).text = doi
        n += 1
    url = None
    if ws(w.get("url")):
        url = join_url(w.get("url"), printed)
        if url is None:
            st["refs_dropped_not_printed_url"] += 1
        elif url != ws(w.get("url")) or url not in printed:
            st["refs_tidy_url_joined"] += 1
    if url:
        etree.SubElement(ec, "ext-link", {"ext-link-type": "uri", XL + "href": url}).text = url
        n += 1
    n += v35_parts(w, ec, ok, typ, st)
    if not n:
        st["refs_dropped_empty_work"] += 1
        return None
    st["refs_fields_written"] += n
    return ec


V35_KEYS = ("editors", "translators", "edition", "cal", "year2", "cited", "accessed", "library", "shelf", "folio",
            "conf", "degree")


def _persons(v, ok, field):
    out = []
    for au in (v if isinstance(v, list) else [v]):
        if isinstance(au, str):
            au = {"surname": au}
        if not isinstance(au, dict):
            continue
        sn, gn = ok(field, au.get("surname")), ok(field, au.get("given"))
        if sn:
            nm = etree.Element("name")
            etree.SubElement(nm, "surname").text = sn
            if gn:
                etree.SubElement(nm, "given-names").text = gn
            out.append(nm)
        elif gn:
            e = etree.Element("string-name")
            e.text = gn
            out.append(e)
    return out


def v35_parts(w: dict, ec, ok, typ: str, st: Counter) -> int:
    """Prompt v3.5's new keys of a cited work (experiment 51's priority-1 reference items), each an exact substring
    of the printed entry (checked by ok()). A work without any of these keys (every answer before v3.5) is left
    exactly as before. JATS 1.4 (DTD-checked): person-group editor / translator, edition, year[@calendar] (+ a
    second year in the other calendar), comment[@content-type=death-date | shelfmark | degree], page-range
    [@content-type=cited-pages | folio] (the work's own range stays fpage / lpage / page-range), date-in-citation
    [@content-type=access-date], institution[@content-type=library], conf-name / conf-loc (type conference)."""
    if not any(k in w for k in V35_KEYS) and not any(isinstance(au, dict) and "died" in au
                                                     for au in w.get("authors") or []):
        return 0
    n = 0
    for k, kind in (("editors", "editor"), ("translators", "translator")):
        names = _persons(w.get(k) or [], ok, k)
        if names:
            pg = etree.SubElement(ec, "person-group", {"person-group-type": kind})
            for nm in names:
                pg.append(nm)
            n += len(names)
            st[f"refs_v35_{k}"] += len(names)
    for au in w.get("authors") or []:
        d = ok("died", au.get("died")) if isinstance(au, dict) else None
        if d:
            etree.SubElement(ec, "comment", {"content-type": "death-date"}).text = d
            n += 1
            st["refs_v35_died"] += 1
    ed = ok("edition", w.get("edition"))
    if ed:
        etree.SubElement(ec, "edition").text = ed
        n += 1
        st["refs_v35_edition"] += 1
    y = ec.find("year")
    cal = str(w.get("cal") or "").lower()
    y2 = ok("year2", w.get("year2"))
    if y is not None and (cal or y2):
        y.set("calendar", "islamic" if cal.startswith("hij") else "gregorian")
        st[f"refs_v35_year_{y.get('calendar')}"] += 1
    if y2 and year_ok(y2):
        other = "gregorian" if y is not None and y.get("calendar") == "islamic" or cal.startswith("hij") else "islamic"
        e = etree.Element("year", {"calendar": other})
        e.text = y2
        (y.addnext(e) if y is not None else ec.append(e))
        n += 1
        st["refs_v35_year2"] += 1
    for k, tag, attrs in (("cited", "page-range", {"content-type": "cited-pages"}),
                          ("accessed", "date-in-citation", {"content-type": "access-date"}),
                          ("library", "institution", {"content-type": "library"}),
                          ("shelf", "comment", {"content-type": "shelfmark"}),
                          ("folio", "page-range", {"content-type": "folio"}),
                          ("degree", "comment", {"content-type": "degree"}),
                          ("conf", "conf-name", {})):
        v = ok(k, w.get(k))
        if not v:
            continue
        etree.SubElement(ec, tag, attrs).text = clean_label(v) if k == "cited" else v
        n += 1
        st[f"refs_v35_{k}"] += 1
    if typ == "conference":                     # the place of a conference is where it met, not a publisher's
        for pl in ec.findall("publisher-loc"):
            pl.tag = "conf-loc"
            st["refs_v35_conf_loc"] += 1
    return n


def add_parsed(Mo, A, raw_dir: Path | None = None, answers: list[dict] | None = None) -> Counter:
    """element-citations from the answer's "parsed" / "cites" parts into the article A (after jats43.fill_slots).
    raw_dir: the folder of the answers the masters are built from (or Mo.raw_dir); answers: given directly (tests)."""
    st = Counter()
    if answers is None:
        rd = raw_dir or getattr(Mo, "raw_dir", None)
        if rd is None:
            return st
        answers = answers_of(Mo.a, Path(rd))
    tgt = {t.get("id"): t for t in A.iter("target") if t.get("id")}
    lang = getattr(Mo, "lang", "ar")
    for key, lid, works in parsed_blocks(answers):
        t = tgt.get(Mo.tl_of.get(lid))
        if t is None:
            st[f"refs_{key}_block_not_found"] += 1
            continue
        holder = next((e for e in t.iterancestors() if e.tag in ("ref", "fn")), None)
        if holder is None:
            st[f"refs_{key}_not_ref_or_note"] += 1
            continue
        if holder.tag == "ref":
            mc = holder.find("mixed-citation")
            printed = ws("".join(mc.itertext())) if mc is not None else ""
            after = mc
        else:
            printed = ws(" ".join("".join(p.itertext()) for p in holder.findall("p")
                                  if p.get("content-type") != "parsed-citations"))
            after = None
        ecs = [e for e in (citation(w, printed, st, lang) for w in works) if e is not None]
        if not ecs:
            continue
        if holder.tag == "ref":
            for e in reversed(ecs):
                after.addnext(e)
            st["refs_element_citations"] += len(ecs)
            st["refs_parsed"] += 1
        else:
            p = holder.find("p[@content-type='parsed-citations']")
            if p is None:
                p = etree.SubElement(holder, "p", {"content-type": "parsed-citations"})
            for e in ecs:
                p.append(e)
            st["refs_note_citations"] += len(ecs)
            st["refs_notes_citing"] += 1
    if hasattr(Mo, "stats"):
        Mo.stats.update(st)
    return st
