"""Experiment 43: parsed references and the works a note cites (prompt v3.2 candidate; no model calls here).

Prompt v3.2 asks, per reference block, for "parsed": [W] and, per footnote / endnote that cites works, for
"cites": [W, ...], W = {type, authors [{surname, given}], year, title, source, volume, issue, pages, publisher,
place, doi, url, lang}, every value an exact substring of the printed entry. structure.assemble keeps only known
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

    import refs43; refs43.add_parsed(Mo, A, raw_dir)        -> Counter of what was written and dropped
"""
from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path

from lxml import etree

XL = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TYPES = {"book": "book", "journal": "journal", "chapter": "book", "thesis": "thesis", "web": "web", "other": "other"}
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


def citation(w: dict, printed: str, st: Counter, lang_default: str) -> etree._Element | None:
    """One element-citation from a work's parts; every value checked against the printed text."""
    def ok(field, v):
        v = ws(v)
        if not v:
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
        etree.SubElement(ec, "year").text = y
        n += 1
    elif y:
        st["refs_dropped_year_not_a_year"] += 1
    for k, tag in SIMPLE:
        v = ok(k, w.get(k))
        if v:
            etree.SubElement(ec, tag).text = v
            n += 1
    pp = ok("pages", w.get("pages"))
    if pp:
        m = re.fullmatch(r"\D*?(\d+)\s*[-–—]\s*(\d+)\D*", pp.translate(DIGITS))
        if m:
            etree.SubElement(ec, "fpage").text = m.group(1)
            etree.SubElement(ec, "lpage").text = m.group(2)
        etree.SubElement(ec, "page-range").text = pp
        n += 1
    doi = ok("doi", w.get("doi"))
    if doi:
        etree.SubElement(ec, "pub-id", {"pub-id-type": "doi"}).text = doi
        n += 1
    url = ok("url", w.get("url"))
    if url:
        etree.SubElement(ec, "ext-link", {"ext-link-type": "uri", XL + "href": url}).text = url
        n += 1
    if not n:
        st["refs_dropped_empty_work"] += 1
        return None
    st["refs_fields_written"] += n
    return ec


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
