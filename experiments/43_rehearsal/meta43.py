"""Experiment 43: D33 — metadata is corrected, the printed form kept beside it, every change logged (no model calls).

docs/decisions.md D33 (owner and father, 2026-10-18): the title, translated title, author names, affiliations,
keywords, dates, journal name / volume / issue are corrected; the body and the abstract stay as printed (D30).
Called by Master43.build after jats43 fills the slots.

  title     printed visibly as a fragment of a fuller form (0355, 1979: the display title runs into a photograph
            and over the spread; only «اثرالتـ / عـلى تطـ / فـى القـ» on page 1 and «ـور الاجتماعى …» on page 2)
            -> the full form: the catalogue's title (or Gemini's reading of it, whichever holds every printed
            fragment; the catalogue first, unless it adds nothing to what is printed), spelt word by word as the
            print or Gemini spells it where they agree with it letter for letter (ى / ي, hamza, tashkeel aside);
            reason "cut off by the design".
            Else a title with a misprint flag (D30 sic) -> the flag's correction; reason "misprint", source gemini.
            JATS: article-title = the corrected title (no id); the printed lines move, with their id (the ALTO
            points at it) and their line targets, to alt-title[@alt-title-type="printed"] (one per printed piece;
            a title piece on page 2 leaves the body for the front the same way)
  authors   a printed byline that is visibly a fragment of the author's fuller name (0355: «يوسف الشـ» + «ونى» across
            the spread) -> the full name (same choice of source); JATS: the contrib's string-name = the corrected
            name, string-name[@specific-use="printed-on-the-page"] = the printed pieces; a byline piece on page 2
            leaves the body for the front (custom-meta front-matter-block, id kept)
  others    a misprint flag inside a keyword or an affiliation -> its correction in place, the printed form in the
            change log (none in the 55 or the v3 tests)
  log       one custom-meta "metadata-change" per change (field: printed -> corrected; source; reason) and
            out/<masters>/<stem>.metachanges.json (written by masters43.build43) with the structured entries
  person    corrections/<stem>.json (a person's correction; the future correction tool writes it) wins over the
            catalogue and Gemini: {"by": "...", "title": "...", "authors": {"1": "..."}, "note": "..."}
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
CORRECTIONS = HERE / "corrections"
XL = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
TASHKEEL = re.compile(r"[ً-ْٰ]")
TATWEEL = "ـ"


def norm(s: str) -> str:
    """Letters only, Arabic spelling variants folded (ى/ي, ة/ه, hamza seats, tashkeel, tatweel)."""
    s = TASHKEEL.sub("", s or "").replace(TATWEEL, "")
    s = s.translate(str.maketrans("ىةأإآٱؤئ", "يهااااوي"))
    return "".join(ch for ch in s.casefold() if ch.isalnum())


def plain(s: str) -> str:
    """Display form of a word: tashkeel and tatweel out, spacing tidied."""
    return " ".join(TASHKEEL.sub("", s or "").replace(TATWEEL, "").split())


def tx(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def fragments(pieces: list[str]) -> list[str]:
    """The printed words of the pieces, as letter strings (a word cut by the design ends in a tatweel)."""
    out = []
    for p in pieces:
        for w in p.split():
            n = norm(w)
            if len(n) >= 2:
                out.append(n)
    return out


def cut_evidence(pieces: list[str]) -> bool:
    return any(w.endswith(TATWEEL) or w.startswith(TATWEEL) for p in pieces for w in p.split())


def holds(cand: str, frags: list[str]) -> bool:
    c = norm(cand)
    return bool(c) and all(f in c for f in frags)


def choose_full(pieces: list[str], cands: list[tuple[str, str]]) -> tuple[str, str] | None:
    """(full form, source) when the printed pieces are visibly a fragment of a fuller form: every printed word
    found inside it, a word cut by the design (tatweel at its edge), and the fuller form longer than what is printed.
    The catalogue first, unless it adds nothing to the print (then it was itself read from the cut print) and
    another source does."""
    frags = fragments(pieces)
    if not frags or not cut_evidence(pieces):
        return None
    joined = "".join(frags)
    longest = max(len(norm(p)) for p in pieces)
    ok = [(v, src) for v, src in cands if v and holds(v, frags) and len(norm(v)) > longest
          and norm(v) != joined]                    # not merely the printed fragments run together
    if not ok:
        return None
    return ok[0]


def respell(full: str, spellings: list[str]) -> str:
    """The full form word by word in the print's (or Gemini's) spelling where it is the same word letter for
    letter (ى / ي, hamza, tashkeel aside); the catalogue's spelling elsewhere."""
    words = {}
    for s in spellings:
        for w in s.split():
            if w.startswith(TATWEEL) or w.endswith(TATWEEL):
                continue
            words.setdefault(norm(w), plain(w))
    return " ".join(words.get(norm(w), plain(w)) for w in full.split())


def person_corrections(stem: str) -> dict:
    f = CORRECTIONS / f"{stem}.json"
    if not f.exists():
        return {}
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except ValueError:
        return {}


class Meta:
    def __init__(self, Mo, A):
        self.M, self.A = Mo, A
        self.am = A.find("front/article-meta")
        self.body = A.find("body")
        self.tl2lid = {v: k for k, v in Mo.tl_of.items()}
        self.changes = []
        self.person = person_corrections(Mo.stem)
        self.cat = None
        if Mo.a.get("jats") and Path(Mo.a["jats"]).exists():
            try:
                self.cat = etree.parse(Mo.a["jats"], etree.XMLParser(load_dtd=False, no_network=True)).getroot()
            except Exception:
                self.cat = None
        self.p0 = min(Mo.pages) if Mo.pages else 1

    def page_of(self, el) -> int | None:
        for t in el.iter("target"):
            lid = self.tl2lid.get(t.get("id"))
            if lid:
                return self.M.S.lines[lid]["page"]
        return None

    def log(self, field, printed, corrected, source, reason, **extra):
        e = dict(field=field, printed=printed, corrected=corrected, source=source, reason=reason, **extra)
        self.changes.append(e)
        self.M.stats[f"meta_corrected_{field.split('[')[0]}"] += 1

    # ---------------------------------------------------------------- title
    def title(self):
        tg = self.am.find("title-group")
        at = tg.find("article-title") if tg is not None else None
        if at is None or not self.M.whole_start:
            return
        later = [t for t in self.body.iter("title") if t.get("content-type") == "title"
                 and (self.page_of(t) or 99) <= self.p0 + 1]
        pieces = [tx(at)] + [tx(t) for t in later]
        cat_t = tx(self.cat.find("front/article-meta/title-group/article-title")) if self.cat is not None else ""
        gem_t = " ".join(str(self.M.meta.get("title") or "").split())
        person = (self.person.get("title") or "").strip()
        full, src, reason = None, None, None
        if person:
            full, src, reason = person, "person", self.person.get("reason") or "corrected by a person"
        else:
            ch = choose_full(pieces, [(cat_t, "catalogue"), (gem_t, "gemini")])
            if ch:
                full = respell(ch[0], pieces + [gem_t])
                src, reason = ch[1], "cut off by the design"
        moved = []
        if full is None:
            sics = [n for n in at.iter("named-content") if n.get("content-type") == "sic" and n.get(XL + "title")]
            if not sics:
                return
            c = copy_el(at)
            for n in list(c.iter("named-content")):
                if n.get("content-type") == "sic" and n.get(XL + "title"):
                    replace_text(n, n.get(XL + "title"))
            full, src, reason = tx(c), "gemini", "misprint"
            later = []
        printed = " … ".join(pieces[:1 + len(later)])
        if plain(full) == plain(tx(at)) and not later:
            return
        alt = etree.Element("alt-title", {"alt-title-type": "printed"})
        if at.get("id"):
            alt.set("id", at.get("id"))
            del at.attrib["id"]
        alt.text = at.text
        for c in list(at):
            alt.append(c)
        at.text = full
        at.addnext(alt)
        moved.append(alt)
        last = alt
        for t in later:                                     # a title piece on page 2: front, not a section
            a2 = etree.Element("alt-title", {"alt-title-type": "printed"})
            if t.get("id"):
                a2.set("id", t.get("id"))
            a2.text = t.text
            for c in list(t):
                a2.append(c)
            last.addnext(a2)
            last = a2
            sec = t.getparent()
            sec.remove(t)
            unwrap(sec)
        # keep JATS order in title-group: article-title, subtitle, trans-title-group, alt-title ...
        order = ["article-title", "subtitle", "trans-title-group", "alt-title", "fn-group"]
        kids = sorted(list(tg), key=lambda e: order.index(e.tag) if e.tag in order else 9)
        for e in kids:
            tg.append(e)
        self.log("title", printed, full, src, reason,
                 alternatives={k: v for k, v in (("catalogue", cat_t), ("gemini", gem_t)) if v and v != full})

    # ---------------------------------------------------------------- authors
    def authors(self):
        if not self.M.whole_start:
            return
        bylines = [r for r in self.M.recs if r["type"] == "byline" and r["page"] <= self.p0 + 1]
        if not bylines:
            return
        pieces = [" ".join(self.M.S.lines[i]["text"] for i in r["ids"]) for r in bylines]
        contribs = list(self.am.iterfind("contrib-group/contrib"))
        cat_names = []
        if self.cat is not None:
            for c in self.cat.iterfind("front/article-meta/contrib-group/contrib"):
                for nm in c.iter("name"):
                    if nm.get(XML_LANG) in (None, "ar"):
                        cat_names.append(" ".join(x for x in (tx(nm.find("given-names")), tx(nm.find("surname")))
                                                  if x))
                        break
        for k, c in enumerate(contribs, 1):
            sn = [s for s in c.iter("string-name")]
            if not sn:
                continue
            main = next((s for s in sn if s.get("specific-use") != "printed-on-the-page"), sn[0])
            gem = tx(main)
            frags = fragments(pieces)
            mine = [p for p in pieces if any(norm(w) in norm(gem) or any(norm(w) in norm(x) for x in cat_names)
                                             for w in p.split() if len(norm(w)) >= 2)]
            if not mine:
                continue
            person = str((self.person.get("authors") or {}).get(str(k)) or "").strip()
            if person:
                full, src, reason = person, "person", self.person.get("reason") or "corrected by a person"
            else:
                ch = choose_full(mine, [(x, "catalogue") for x in cat_names] + [(gem, "gemini")])
                if not ch:
                    continue
                full, src, reason = respell(ch[0], mine + [gem]), ch[1], "cut off by the design"
                if src == "gemini" and any(holds(x, fragments(mine)) for x in cat_names):
                    reason += ("; the catalogue's authority name «" + "», «".join(cat_names) + "» is only the "
                               "printed fragments joined (read from the cut print): Gemini's fuller reading kept, "
                               "for a person to confirm")
            printed = " … ".join(mine)
            del frags
            for s in sn:                                    # the old "printed-on-the-page" was Gemini's reading
                if s.get("specific-use") == "printed-on-the-page":
                    del s.attrib["specific-use"]
            main = sn[-1] if len(sn) else main
            main.text = full
            for ch_ in list(main):
                main.remove(ch_)
            pr = etree.Element("string-name", {"specific-use": "printed-on-the-page"})
            pr.text = printed
            par = main.getparent()
            if par.tag != "name-alternatives":
                na = etree.Element("name-alternatives")
                main.addprevious(na)
                na.append(main)
                par = na
            main.addnext(pr)
            self.log(f"author[{k}]", printed, full, src, reason,
                     alternatives={"catalogue": cat_names, "gemini": gem})
            # a byline piece on page 2 printed in the body: to the front, as a printed front-matter block
            for r in bylines:
                if r["page"] == self.p0:
                    continue
                for p in list(self.body.iter("p")):
                    if p.get("content-type") == "byline" and self.page_of(p) == r["page"]:
                        cmg = self.am.find("custom-meta-group")
                        cm = etree.SubElement(cmg, "custom-meta", {"id": p.get("id")} if p.get("id") else {})
                        etree.SubElement(cm, "meta-name").text = "front-matter-block"
                        mv = etree.SubElement(cm, "meta-value")
                        mv.text = p.text
                        for ch_ in list(p):
                            mv.append(ch_)
                        p.getparent().remove(p)

    # ---------------------------------------------------------------- keywords, affiliations
    def flags_in_place(self):
        for tag, field in (("kwd", "keyword"), ("aff", "affiliation"), ("trans-title", "translated title")):
            for el in self.am.iter(tag):
                for n in list(el.iter("named-content")):
                    if n.get("content-type") == "sic" and n.get(XL + "title"):
                        printed = tx(el)
                        replace_text(n, n.get(XL + "title"))
                        self.log(field, printed, tx(el), "gemini", "misprint")

    def write_log(self):
        cmg = self.am.find("custom-meta-group")
        if cmg is None:
            return
        for k, e in enumerate(self.changes, 1):
            c = etree.SubElement(cmg, "custom-meta", {"id": f"metachange{k}"})
            etree.SubElement(c, "meta-name").text = "metadata-change"
            etree.SubElement(c, "meta-value").text = (f"{e['field']}: «{e['printed']}» -> «{e['corrected']}» "
                                                      f"(source: {e['source']}; reason: {e['reason']})")

    # ---------------------------------------------------------------- page range
    def page_range(self):
        """fpage / lpage consistent with the scan (2026-10-20, coordinator: 142 articles of the 300 where the
        catalogue's range fits the scan's page count and the masters' does not, e.g. 1058-005-993-021: Gemini gave
        «450-459», the range of its first chunk only; the folios read 450 ... 469 on the 20 pages). The printed
        range is kept when it already spans the scan's pages; else the folios read on the first and last pages (lone
        numbers in the running heads / feet; a jump to a later part of the issue is kept: 1010-006 34-58); else the
        catalogue's range when it spans the scan's pages; else the folios' offset from the pages that carry one;
        else fpage + pages - 1. Logged like any D33 change."""
        import statistics
        n = len(self.M.pages)
        p0, p1 = min(self.M.pages), max(self.M.pages)
        fol = {}
        for r in self.M.recs:
            if r.get("type") not in ("header", "footer") or r.get("_other"):
                continue
            for lid in r.get("ids") or []:
                L = self.M.S.lines.get(lid)
                m = PAGE_NO.match(L["text"]) if L else None
                if m:
                    fol.setdefault(L["page"], []).append(int(m.group(1).translate(DIG)))
        fol = {p: v[0] for p, v in fol.items() if len(v) == 1}
        fp_el, lp_el = self.am.find("fpage"), self.am.find("lpage")
        old = (fp_el.text if fp_el is not None else None, lp_el.text if lp_el is not None else None)
        num = lambda v: int(v) if v and str(v).isdigit() else None                               # noqa: E731
        cat = catalogue_pages(self.M.stem)
        if CATALOGUE_FIRST and cat and cat[1] - cat[0] + 1 == n and (num(old[0]), num(old[1])) != tuple(cat):
            # experiment 74 (exp 70's issue 4, D33-like): the catalogue's range wins when it spans the scan's pages
            # (exp 70: 2 of 10 spot-checked articles carried the reader's wrong lpage, e.g. 105 for 121)
            new, src = tuple(cat), "catalogue (its range spans the scan's pages; the catalogue wins, exp 74)"
            ps = sorted(fol)
        elif num(old[0]) and num(old[1]) and num(old[1]) - num(old[0]) + 1 == n:
            return                                   # already spans the scan's pages (1289: 16-17, catalogue too)
        else:
            new, src = None, None
            ps = sorted(fol)
        seq0 = n <= 2 or fol.get(p0 + 1) == fol.get(p0, -9) + 1 or fol.get(p0 + 2) == fol.get(p0, -9) + 2
        seq1 = n <= 2 or fol.get(p1 - 1) == fol.get(p1, -9) - 1 or fol.get(p1 - 2) == fol.get(p1, -9) - 2
        if new is not None:
            pass
        elif p0 in fol and p1 in fol and fol[p1] >= fol[p0] and seq0 and seq1:     # (a lone year is not a folio)
            new, src = (fol[p0], fol[p1]), "printed folios (first and last page)"
        elif cat and cat[1] - cat[0] + 1 == n:
            new, src = cat, "catalogue (its range spans the scan's pages)"
        elif len(ps) >= 2:
            head = [fol[p] - p for p in ps[:3]]
            tail = [fol[p] - p for p in ps[-3:]]
            o0, o1 = statistics.mode(head), statistics.mode(tail)
            if head.count(o0) >= 2 or len(ps) == 2 and head[0] == head[-1]:
                new = (p0 + o0, p1 + (o1 if tail.count(o1) >= 2 else o0))
                src = "printed folios (offset from the pages that carry one)"
        if new is None and num(old[0]):
            new, src = (num(old[0]), num(old[0]) + n - 1), "the scan's page count"
        if new is None or new[0] <= 0 or new[1] < new[0]:
            return
        for tag, el, v in (("fpage", fp_el, new[0]), ("lpage", lp_el, new[1])):
            if el is not None and el.text == str(v):
                continue
            if el is None:
                el = etree.Element(tag)
                after = [x for x in ("fpage", "issue", "volume", "pub-date") if self.am.find(x) is not None]
                if after:
                    self.am.find(after[0]).addnext(el)
                else:
                    self.am.find("counts").addprevious(el)
            printed = el.text
            el.text = str(v)
            self.log(tag, printed, str(v), src, "page range consistent with the scan's "
                     f"{n} pages", pages_in_scan=n, folios=len(ps))

    def run(self):
        for e in getattr(self.M, "name_changes", []):       # names_pre (before jats43): honorifics, roles, scripts
            self.log(e.pop("field"), e.pop("printed"), e.pop("corrected"), e.pop("source"), e.pop("reason"), **e)
        for e in hijri_year(self.M, self.A):
            self.log(e.pop("field"), e.pop("printed"), e.pop("corrected"), e.pop("source"), e.pop("reason"), **e)
        self.page_range()
        self.title()
        self.authors()
        self.flags_in_place()
        self.write_log()
        self.M.meta_changes = self.changes
        return self.changes


def copy_el(el):
    import copy
    return copy.deepcopy(el)


def replace_text(n, text):
    """An inline element replaced by plain text (kept in its parent's text flow)."""
    par = n.getparent()
    t = (text or "") + (n.tail or "")
    prev = n.getprevious()
    if prev is not None:
        prev.tail = (prev.tail or "") + t
    else:
        par.text = (par.text or "") + t
    par.remove(n)


def unwrap(sec):
    """A section emptied of its title: its content takes its place in the parent."""
    par = sec.getparent()
    if par is None:
        return
    prev = sec.getprevious()
    if prev is not None and prev.tag == "sec":          # JATS: no paragraph after a section at one level
        for c in list(sec):
            prev.append(c)
        par.remove(sec)
        return
    i = par.index(sec)
    for c in list(sec):
        par.insert(i, c)
        i += 1
    par.remove(sec)


PAGE_NO = re.compile(r"^[\s\-–—_.]*([0-9٠-٩]{1,4})[\s\-–—_.]*$")
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789")
MARC = Path.home() / "data" / "marc" / "marc.db"


# experiment 74: META43_CATALOGUE_FIRST=1 lets the catalogue's page range win over the reader's (gate 2 builds)
CATALOGUE_FIRST = __import__("os").environ.get("META43_CATALOGUE_FIRST") == "1"


def catalogue_pages(stem: str):
    """(page_first, page_last) of the stem's catalogue record (marc.db, experiment 45), or None."""
    if not MARC.exists():
        return None
    import sqlite3
    try:
        con = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
        row = con.execute("SELECT r.page_first, r.page_last FROM pdf_ids p JOIN records r ON r.rec = p.rec "
                          "WHERE p.stem = ? AND r.page_first IS NOT NULL ORDER BY p.seq LIMIT 1", (stem,)).fetchone()
        con.close()
    except Exception:                                        # noqa: BLE001
        return None
    return (int(row[0]), int(row[1])) if row and row[1] is not None else None


def apply(Mo, A):
    return Meta(Mo, A).run()


# ------------------------------------------------------------------------------------------------ fix round 3
# (2026-10-20, the proof pack's metadata sample: honorifics kept in names (0071, 0631, 0806, 2483, 8480), a translator
# and a Latin spelling listed as authors (1036), an editorial committee from the last page as authors (1633), the Hijri
# year in <year> (0266, 0596, 0764). Built from the exam's 300: every honorific and role phrase Gemini read.)

HON_WORD = (r"(?:الأستاذة?|الاستاذة?|أستاذة?|استاذة?|الدكتورة?|دكتورة?|الشيخ|المحامي|المحامى|السير|البروفيسور|البروفسور|"
            r"بروفيسور|بروفسور|المهندسة?|الأديبة?|الشاعرة?|السيدة?(?=\s*/))")
HON_ABBR = r"(?:[أمدذ]\s*[./:]\s*)+"                  # أ.د.  أ.د/  أ.م.د/  أ. م.د /  د.  د/  د :  د .  ذ.  م.م.
HON_LAT = r"(?:Dr|Pr|Prof|Professor|Mme|Mr|Mrs|Ms)(?:\.|\b)\s*(?:[:/]\s*)?"
HON_TAIL = re.compile(r"[\s،,]+(?:المحامي|المحامى|المحامية|المهندس|المهندسة)\s*$")
HONORIFIC = re.compile(rf"^\s*(?:{HON_WORD}\s*[./:]?\s*|{HON_ABBR}|د\s+(?=\S\S)|{HON_LAT})")
ROLES = [                                  # Gemini's printed role phrase (or the heading over a later byline) -> contrib-type
    ("translator", re.compile(r"ترجم|تعريب|عربه|نقله\s+إلى|traduc|tradui|translat", re.I)),
    ("reviewer", re.compile(r"مراجع|راجعه|review|révis", re.I)),
    ("editor", re.compile(r"تحرير|حرره|editor|edited|éditeur|comité\s+de\s+rédaction|هيئة\s+التحرير|editorial", re.I)),
    ("supervisor", re.compile(r"إشراف|اشراف|المشرف|supervis|directeur\s+de\s+th", re.I)),
    ("rapporteur", re.compile(r"مقرر|rapporteur", re.I)),
]
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
ARABIC = re.compile(r"[؀-ۿ]")


def strip_honorific(name: str) -> tuple[str, str]:
    """(name without its leading honorifics / titles, the honorifics taken off); the name itself is never emptied."""
    n, took = " ".join((name or "").split()), []
    for _ in range(4):
        m = HONORIFIC.match(n)
        if not m or not m.group(0).strip():
            break
        rest = n[m.end():].strip(" ./:")
        if len(norm(rest)) < 3 or len(rest.split()) < 1:
            break
        took.append(m.group(0).strip())
        n = rest
    m = HON_TAIL.search(n)                          # a profession printed after the name (0806 «انور شاؤل المحامى»)
    if m and len(norm(n[:m.start()])) >= 3:
        took.append(m.group(0).strip(" ،,"))
        n = n[:m.start()].strip(" ،,")
    return n, " ".join(took)


def role_kind(text: str) -> str | None:
    for kind, rx in ROLES:
        if rx.search(text or ""):
            return kind
    return None


_AR = str.maketrans({"ب": "B", "ت": "T", "ط": "T", "ث": "T", "ج": "G", "غ": "G", "خ": "K", "ق": "K", "ك": "K",
                     "د": "D", "ض": "D", "ذ": "D", "ر": "R", "ز": "S", "ظ": "S", "س": "S", "ص": "S", "ش": "S",
                     "ف": "F", "ل": "L", "م": "M", "ن": "N"})


def skeleton(name: str) -> str:
    """Consonants of a name, Arabic or Latin, in one rough class alphabet (a transliteration check, not a spelling)."""
    out = []
    for w in name.split():
        if ARABIC.search(w):
            w = re.sub(r"^ال", "", TASHKEEL.sub("", w))
            s = "".join(ch for ch in w.translate(_AR) if ch.isascii() and ch.isupper())
        else:
            w = re.sub(r"^(al|el)[-‐]", "", w.lower())
            w = w.replace("sh", "s").replace("ch", "s").replace("kh", "k").replace("th", "t").replace("gh", "g") \
                .replace("ph", "f").replace("ou", "u")
            m = {"c": "K", "k": "K", "q": "K", "g": "G", "j": "G", "s": "S", "z": "S", "x": "KS", "p": "B", "b": "B",
                 "v": "F", "f": "F", "t": "T", "d": "D", "r": "R", "l": "L", "m": "M", "n": "N"}
            s = "".join(m.get(ch, "") for ch in w)
        out.append(re.sub(r"(.)\1+", r"\1", s))
    return "".join(out)


def same_person_latin(ar: str, la: str) -> float:
    import difflib
    a, b = skeleton(ar), skeleton(la)
    if len(a) < 3 or len(b) < 3:
        return 0.0
    return difflib.SequenceMatcher(None, a, b).ratio()


def names_pre(Mo, A):
    """Before jats43 matches the catalogue's people: each contrib's name without honorifics (the printed name kept as
    string-name[@specific-use="printed-on-the-page"] in name-alternatives), its role from the printed role phrase
    (translator, reviewer, editor, supervisor, rapporteur: contrib-type and <role>; not an author), a Latin spelling
    printed beside an Arabic name folded into that person (string-name xml:lang, its id kept), a byline under an
    editorial committee's heading on a later page tagged so. Every change goes to Mo.name_changes (meta43 logs it)."""
    am = A.find("front/article-meta")
    cg = am.find("contrib-group") if am is not None else None
    Mo.name_changes = []
    if cg is None:
        return
    aus = [au for au in (Mo.meta.get("authors") or []) if isinstance(au, dict) and au.get("name")]
    contribs = list(cg.iterfind("contrib"))
    if len(aus) != len(contribs):
        return
    later = later_byline_heading(Mo)
    page_text = norm(" ".join(str(L.get("text") or "") for L in Mo.S.lines.values()))
    for k, (c, au) in enumerate(zip(contribs, aus), 1):
        sn = c.find("string-name")
        if sn is None:
            continue
        printed = " ".join("".join(sn.itertext()).split())
        clean, took = strip_honorific(printed)
        role_txt = " ".join(str(au.get("role") or "").split())
        kind = role_kind(role_txt)
        if kind is None:
            h = next((v for q, v in later.items() if len(norm(printed)) >= 6 and norm(printed) in q), None)
            if h:
                kind = "rapporteur" if re.search(r"rapport|مقرر", h, re.I) else role_kind(h) or None
                role_txt = h if kind else role_txt
        if took:
            sn.text = clean
            for ch in list(sn):
                sn.remove(ch)
            na = etree.Element("name-alternatives")
            sn.addprevious(na)
            na.append(sn)
            pr = etree.SubElement(na, "string-name", {"specific-use": "printed-on-the-page"})
            pr.text = printed
            Mo.name_changes.append(dict(field=f"author[{k}]", printed=printed, corrected=clean, source="code",
                                        reason=f"honorific / title «{took}» taken out of the name (kept in the printed "
                                               f"form)"))
            Mo.stats["names_honorific_out"] += 1
        exp65 = os.environ.get("EXP65_OFF") != "1"     # experiment 65 (off: the control build)
        if took and exp65:                             # M6 (exp 65): the honorific as its own part, string unchanged
            prefix_in_printed(c, took)
        if kind:
            c.set("contrib-type", kind)
            if c.find("role") is None:
                r = etree.Element("role")
                r.text = role_txt
                last = [e for e in c if e.tag in ("contrib-id", "name-alternatives", "string-name", "name")][-1]
                last.addnext(r)
            Mo.name_changes.append(dict(field=f"author[{k}]", printed=f"author: {printed}",
                                        corrected=f"{kind}: {clean}", source="code",
                                        reason=f"printed role «{role_txt}»: not an author"))
            Mo.stats[f"names_role_{kind}"] += 1
        pos36 = " ".join(str(au.get("position") or "").split())      # prompt v3.6: the post as its own value,
        if pos36 and norm(pos36) not in page_text:                 # kept when it is printed
            Mo.stats["names_position_not_printed"] += 1
            pos36 = ""
        if role_txt and not kind and exp65:            # M1 / M6 (exp 65): a post, a role phrase, an honorific
            role_parts(Mo, c, role_txt, pos36)
        elif pos36 and exp65:
            role_parts(Mo, c, "", pos36)
    # a Latin spelling printed beside an Arabic name (1036 «جيوسيب كاروزو» / «Giuseppe Caruso»): one person
    contribs = list(cg.iterfind("contrib"))
    twins_given = set()                                # (exp 65) authors the answer's enrich pairs (same_as):
    if os.environ.get("EXP65_OFF") != "1" and getattr(Mo, "raw_dir", None):   # meta43.enrich folds those
        import enrich43
        for ans in enrich43.answers_of(Mo.a, Mo.raw_dir)[:1]:
            for x in (ans.get("enrich") or {}).get("authors") or []:
                if isinstance(x, dict) and x.get("same_as") and str(x.get("a", "")).isdigit():
                    twins_given |= {int(x["a"]) - 1, int(x["same_as"]) - 1}
    for c1, c2 in fold_pairs([c for i, c in enumerate(contribs) if i not in twins_given]):
        if c1.getparent() is None or c2.getparent() is None:
            continue
        n1, n2 = (" ".join("".join(main_name(c).itertext()).split()) for c in (c1, c2))
        if not n1 or not n2 or c1.get("contrib-type") != c2.get("contrib-type"):
            continue
        ar, la = (c1, c2) if ARABIC.search(n1) and not ARABIC.search(n2) and LATIN.search(n2) else \
            (c2, c1) if ARABIC.search(n2) and not ARABIC.search(n1) and LATIN.search(n1) else (None, None)
        if ar is None:
            continue
        na_, nl = (" ".join("".join(main_name(c).itertext()).split()) for c in (ar, la))
        sc = same_person_latin(na_, nl)
        if sc < 0.7:
            continue
        if os.environ.get("EXP65_OFF") != "1" and any(s.get(XML_LANG) for s in ar.iter("string-name")):
            continue                                   # (exp 65) this person has its Latin spelling already
        sn = main_name(ar)
        na = sn.getparent() if sn.getparent().tag == "name-alternatives" else None
        if na is None:
            na = etree.Element("name-alternatives")
            sn.addprevious(na)
            na.append(sn)
        ls = etree.SubElement(na, "string-name", {XML_LANG: "en"})
        if la.get("id"):
            ls.set("id", la.get("id"))
        ls.text = nl
        if os.environ.get("EXP65_OFF") != "1":
            keep_twin_parts(ar, la, na)                # M2 (exp 65): every aff, e-mail, post and id of the twin
        else:
            for e in la:
                if e.tag in ("email", "aff") and ar.find(e.tag) is None:
                    ar.append(e)
        cg.remove(la)
        Mo.name_changes.append(dict(field="authors", printed=f"«{na_}» and «{nl}» as two authors",
                                    corrected=f"«{na_}» (Latin spelling «{nl}»)", source="code",
                                    reason=f"one person printed in two scripts (consonant skeletons {sc:.2f})"))
        Mo.stats["names_latin_folded"] += 1


# ------------------------------------------------------------------------------------------------ experiment 65
# (2026-11-02, experiment 61's leaks M1, M2, M6: an author's post / rank, the twin's affiliation, e-mail and post, and
# the honorific were only inside the generic front-matter block. Fields are added; no printed text changes (D30).)
ROLE_PHRASE = re.compile(r"^\s*(?:بقلم|إعداد|اعداد|عرض|تأليف|تاليف|تقديم|كتبه|كتبها|إملاء|"
                         r"اسم\s+(?:ال)?(?:مؤلف|باحث)\w*(?:\s+(?:ال)?(?:رئيسي|مشارك|أول|ثاني|الأول|الثاني))?|"
                         r"(?:main\s+|co-?|first\s+|second\s+)?author(?:'s)?\s+name|"
                         r"(?:prepared|presented|written|compiled|reported|reviewed)\s+by|by|par)(?![\w؀-ۿ])"
                         r"\s*[:/.\-–]*\s*", re.I)
HON_PIECE = re.compile(rf"^\s*(?:(?:ل|لل)?{HON_WORD}(?![\w؀-ۿ])\s*[./:]?\s*|{HON_ABBR}\s*|{HON_LAT})", re.I)


POST_START = re.compile(r"(?:أستاذة?|استاذة?|مدرسة?|محاضرة?|باحثة?|طالبة?|طالب|معيدة?|عميدة?|وكيلة?|رئيسة?|خبيرة?|"
                        r"مستشارة?|مديرة?|مفتشة?|موجهة?|معلمة?|أخصائية?|اخصائية?|عضو|professor|lecturer|researcher|"
                        r"student|assistant|associate|dean|teacher|instructor)(?![\w؀-ۿ])", re.I)


def split_role(text: str) -> tuple[list[str], list[str], str]:
    """Gemini's printed role words -> (role phrases «بقلم», honorifics «الدكتور», the rest: a post or rank), each an
    exact substring of the text."""
    t, phrases, hons = " ".join((text or "").split()), [], []
    for _ in range(6):
        m = ROLE_PHRASE.match(t)
        if m and m.group(0).strip():
            phrases.append(m.group(0).strip(" :/.-–"))
            t = t[m.end():]
            continue
        break
    after = t                                     # honorifics only when nothing else follows («الدكتور»,
    for _ in range(4):                            # «للاستاذ»); «أستاذ مساعد», "Professor of ..." are posts
        m = HON_PIECE.match(t)
        if not m or not m.group(0).strip():
            break
        hons.append(m.group(0).strip())
        t = t[m.end():]
    if re.fullmatch(r"\s*[أمدذ]\s*", t) and hons:  # «أ. د»: the last abbreviation printed without its dot
        hons.append(t.strip())
        t = ""
    if t.strip(" ،,:/.-–()") and not (hons and POST_START.match(t.strip(" ،,:/.-–"))):
        hons, t = [], after                       # «د. / أستاذ أصول التربية»: the title, then the post
    if len(hons) == 1 and re.fullmatch(r"(?:أستاذة?|استاذة?)", hons[0].strip(" ./:")) and not t.strip():
        hons, t = [], after                       # a bare «أستاذ» in the role is the rank (Professor), not a title
    return [p for p in phrases if p], hons, t.strip(" ،,:/.-–()")


def honorific_end(n: str) -> int:
    """Where the leading honorifics of a printed name end (strip_honorific's loop, as an offset)."""
    off = 0
    for _ in range(4):
        m = HONORIFIC.match(n[off:])
        if not m or not m.group(0).strip():
            break
        rest = n[off + m.end():].strip(" ./:")
        if len(norm(rest)) < 3 or len(rest.split()) < 1:
            break
        off += m.end()
        while off < len(n) and n[off] in " ./:":
            off += 1
    return off


def printed_form(c, create_from: str | None = None):
    """The contrib's string-name[@specific-use="printed-on-the-page"] (no xml:lang); with create_from, made when
    missing (the main name moved into name-alternatives beside it)."""
    pr = next((s for s in c.iter("string-name") if s.get("specific-use") == "printed-on-the-page"
               and not s.get(XML_LANG)), None)
    if pr is not None or create_from is None:
        return pr
    sn = main_name(c)
    if sn.getparent() is None:
        return None
    na = sn.getparent() if sn.getparent().tag == "name-alternatives" else None
    if na is None:
        na = etree.Element("name-alternatives")
        sn.addprevious(na)
        na.append(sn)
    pr = etree.SubElement(na, "string-name", {"specific-use": "printed-on-the-page"})
    pr.text = create_from
    return pr


def prefix_in_printed(c, took: str = ""):
    """M6: the leading honorific of the printed name as <prefix>, a profession after it as <suffix>; the string's
    text is unchanged."""
    pr = printed_form(c)
    if pr is None or len(pr):
        return
    n = pr.text or ""
    off = honorific_end(n)
    m = HON_TAIL.search(n)
    tail = m.start() if m and m.start() > off and len(norm(n[off:m.start()])) >= 3 else len(n)
    if off <= 0 and tail == len(n):
        return
    pr.text = ""
    last = None
    if off > 0:
        last = etree.SubElement(pr, "prefix")
        last.text = n[:off].rstrip()
        last.tail = n[len(last.text):tail]
    else:
        pr.text = n[:tail]
    if tail < len(n):
        sx = etree.SubElement(pr, "suffix")
        lead = len(n[tail:]) - len(n[tail:].lstrip(" ،,"))
        if last is None:
            pr.text = n[:tail + lead]
        else:
            last.tail = n[len(last.text):tail + lead]
        sx.text = n[tail + lead:]


def role_parts(Mo, c, role_txt: str, position: str = ""):
    """M1 / M6: the printed role words that name no translator / reviewer / editor / ...: a role phrase («بقلم»,
    "by") as <role content-type="role-phrase">, an honorific as the printed name's <prefix>, the rest (a post or
    rank: «أستاذ مساعد», "PhD Student in Sociology") as <role content-type="position">. A v3.6 "position" wins over
    the rest."""
    phrases, hons, rest = split_role(role_txt)
    pos = position or rest
    if hons:
        nm = " ".join("".join(main_name(c).itertext()).split())
        pr = printed_form(c)
        if pr is None:
            pr = printed_form(c, create_from="")
            pr.text = nm
        h = " ".join(hons)
        pre = pr.find("prefix")
        if pre is None:
            pre = etree.Element("prefix")
            pre.text = h
            pre.tail = " " + (pr.text or "")
            pr.text = ""
            pr.insert(0, pre)
        elif norm(h) not in norm(pre.text or ""):
            pre.text = f"{h} {pre.text or ''}".strip()
        Mo.stats["names_honorific_from_role"] += 1
    anchor = [e for e in c if e.tag in ("contrib-id", "name-alternatives", "string-name", "name")]
    last = anchor[-1] if anchor else None
    for ct, v in [("role-phrase", p) for p in phrases] + ([("position", pos)] if pos and norm(pos) else []):
        if any(r.get("content-type") == ct and norm(tx(r)) == norm(v) for r in c.findall("role")):
            continue
        r = etree.Element("role", {"content-type": ct})
        r.text = v
        if last is not None:
            last.addnext(r)
        else:
            c.append(r)
        last = r
        Mo.stats[f"names_role_{ct.replace('-', '_')}"] += 1


def keep_twin_parts(ar, la, na):
    """M2: the twin's (another script's) affiliations, e-mails, posts, ids and printed form kept in the person,
    marked with their language; a twin affiliation points at the one in the article's script it translates (rid)."""
    nl = " ".join("".join(main_name(la).itertext()).split())
    lang = "en" if LATIN.search(nl) and not ARABIC.search(nl) else "ar"
    ar_affs = [a for a in ar.findall("aff") if not a.get(XML_LANG)]
    k = 0
    for e in list(la):
        tag = e.tag
        if tag == "aff":
            if any(norm(tx(x)) == norm(tx(e)) for x in ar.findall("aff")):
                continue
            e.set(XML_LANG, e.get(XML_LANG) or lang)
            if k < len(ar_affs):
                if not ar_affs[k].get("id"):
                    ar_affs[k].set("id", f"{ar.get('id') or 'contrib'}-aff{k + 1}")
                e.set("rid", ar_affs[k].get("id"))
            if not e.get("id") and la.get("id"):
                e.set("id", f"{la.get('id')}-aff{k + 1}")
            k += 1
            ar.append(e)
        elif tag == "email":
            if any(tx(x).lower() == tx(e).lower() for x in ar.iter("email")):
                continue
            ar.append(e)
        elif tag == "role":
            if not e.get(XML_LANG):
                e.set(XML_LANG, lang)
            ar.append(e)
        elif tag == "contrib-id":
            if any(x.get("contrib-id-type") == e.get("contrib-id-type") and tx(x) == tx(e)
                   for x in ar.findall("contrib-id")):
                continue
            ar.insert(0, e)
        elif tag in ("xref", "uri", "ext-link", "address"):
            ar.append(e)
        elif tag == "name-alternatives" and na is not None:
            for s in e.findall("string-name"):
                if s.get("specific-use") == "printed-on-the-page":
                    s.set(XML_LANG, lang)
                    na.append(s)


def fold_pairs(contribs: list) -> list:
    """The (Arabic, Latin) contrib pairs names_pre tries to fold. Before experiment 65: neighbours only, so with
    «A, B, A', B'» (0130-027-105-003) B and A' were folded into one person. Since: each Latin name with the Arabic
    name its consonants match best (neighbours first on a tie), each Arabic name used once."""
    if os.environ.get("EXP65_OFF") == "1":
        return list(zip(contribs, contribs[1:]))
    nm = {id(c): " ".join("".join(main_name(c).itertext()).split()) for c in contribs}
    ar = [c for c in contribs if ARABIC.search(nm[id(c)])]
    la = [c for c in contribs if not ARABIC.search(nm[id(c)]) and LATIN.search(nm[id(c)])]
    cand = []
    for l in la:
        for a in ar:
            if a.get("contrib-type") == l.get("contrib-type"):
                d = abs(contribs.index(a) - contribs.index(l))
                cand.append((-same_person_latin(nm[id(a)], nm[id(l)]), d, contribs.index(l), a, l))
    cand.sort(key=lambda x: x[:3])
    out, used = [], set()
    for sc, d, _, a, l in cand:
        if -sc < 0.7 or id(a) in used or id(l) in used:
            continue
        used |= {id(a), id(l)}
        out.append((a, l) if contribs.index(a) < contribs.index(l) else (l, a))
    return sorted(out, key=lambda p: contribs.index(p[0]))


def main_name(c):
    for s in c.iter("string-name"):
        if s.get("specific-use") != "printed-on-the-page" and not s.get(XML_LANG):
            return s
    return next(c.iter("string-name"), etree.Element("string-name"))


def later_byline_heading(Mo) -> dict:
    """norm(byline text) -> the heading over it, for bylines on a page after the article's first two whose
    heading names a committee (1633 p6 «Comité de rédaction du rapport général du colloque»)."""
    out, head = {}, None
    p0 = min(Mo.pages) if Mo.pages else 1
    for r in Mo.recs:
        t = " ".join(Mo.S.lines[i]["text"] for i in r.get("ids") or [] if i in Mo.S.lines)
        if r["type"] == "heading":
            if re.search(r"comit[ée]|rédaction|rapporteur|هيئة\s+التحرير|لجنة|مقرر|editorial", t, re.I):
                head = (r["page"], t)
            elif head and head[0] != r["page"]:
                head = None
        elif r["type"] == "byline" and head and r["page"] == head[0] and r["page"] > p0 + 1:
            for ln in t.split("  ") + [t]:
                out[norm(ln)] = head[1]
            for i in r.get("ids") or []:
                out[norm(Mo.S.lines[i]["text"])] = head[1]
    return out


HIJRI_MARK = re.compile(r"هـ|ه\b|ﻫ|AH\b|H\b", re.I)


def hijri_year(Mo, A):
    """A pub-date year that is a Hijri year (1300-1500, the printed date marked هـ or carrying no Gregorian year):
    the Gregorian year beside it (printed: a 4-digit year >= 1800 in the printed date; else the catalogue's year of
    the issue when it agrees with the conversion within 2 years) in pub-date[@calendar="gregorian"], the Hijri in a
    second pub-date[@calendar="islamic"]; with no Gregorian known, the one pub-date marked islamic. Never a bare
    Hijri number in <year> (fix round 3)."""
    am = A.find("front/article-meta")
    if am is None:
        return []
    DIGS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
    printed = str(Mo.meta.get("year") or "").translate(DIGS)
    changes = []
    for pd in am.findall("pub-date"):
        y_el = pd.find("year")
        if y_el is None or pd.get("calendar"):
            continue
        y = int(y_el.text) if (y_el.text or "").strip().isdigit() else None
        if y is None or not 1300 <= y <= 1500:
            continue
        greg = [int(x) for x in re.findall(r"(?<!\d)(\d{4})(?!\d)", printed) if 1800 <= int(x) <= 2100]
        conv = y * 0.970229 + 621.5643
        g, src = None, None
        if greg:
            g, src = min(greg, key=lambda v: abs(v - conv)), "printed date (the Gregorian year beside the Hijri)"
        else:
            cy = str(Mo.a.get("year") or "")
            if cy.isdigit() and abs(int(cy) - conv) <= 2:
                g, src = int(cy), "catalogue (the issue's Gregorian year, agreeing with the Hijri year)"
        if g is not None:
            import copy
            h = copy.deepcopy(pd)
            h.set("calendar", "islamic")
            for e in list(h):
                if e.tag != "year":
                    h.remove(e)
            y_el.text = str(g)
            pd.set("calendar", "gregorian")
            if pd.get("iso-8601-date"):
                pd.set("iso-8601-date", str(g) + pd.get("iso-8601-date")[4:])
            pd.addnext(h)
            changes.append(dict(field="year", printed=str(y), corrected=f"{g} (Hijri {y} kept, calendar islamic)",
                                source=src, reason=f"the printed year {y} is Hijri ({Mo.meta.get('year')})"))
        else:
            pd.set("calendar", "islamic")
            changes.append(dict(field="year", printed=str(y), corrected=f"{y} (calendar islamic)", source="code",
                                reason=f"Hijri year with no Gregorian year known ({Mo.meta.get('year')})"))
        Mo.stats["year_hijri"] += 1
    return changes


# ------------------------------------------------------------------------------------------------ prompt v3.5 (draft)
# (2026-10-22, experiment 51's priority-1 items about the article and its authors; README "Prompt v3.5". Called by
# enrich43.apply only when an answer carries "enrich": earlier answers never reach this code. Values were checked in
# rules43 (enrich43.check: substrings of the printed text, line ids, closed lists); nothing here retypes text.)

DOC_JATS = {"research": "research-article", "review": "review-article", "editorial": "editorial",
            "book_review": "book-review", "report": "meeting-report", "conference_paper": "research-article",
            "thesis_summary": "dissertation", "interview": "discussion", "news": "news", "letter": "letter",
            "obituary": "obituary", "poem": "other", "documents": "other", "bibliography": "other",
            "front_matter": "other", "other": "other"}
AFF_TAGS = {"department": ("institution", "dept"), "faculty": ("institution", "faculty"),
            "institution": ("institution", "orgname"), "city": ("addr-line", "city"), "country": ("country", None)}


def _contrib(cg, k: int):
    """The contrib of metadata author k (its id contrib<k>), also when names_pre folded it into another person."""
    if cg is None:
        return None, False
    for c in cg.iterfind("contrib"):
        if c.get("id") == f"contrib{k}":
            return c, False
    for s in cg.iter("string-name"):
        if s.get("id") == f"contrib{k}":
            return next(s.iterancestors("contrib")), True
    return None, False


def _log(Mo, A, field, printed, corrected, reason):
    """A D33 metadata change after meta43.apply has written its log: appended to Mo.meta_changes and the JATS."""
    ch = getattr(Mo, "meta_changes", None)
    if ch is None:
        Mo.meta_changes = ch = []
    ch.append(dict(field=field, printed=printed, corrected=corrected, source="gemini", reason=reason))
    cmg = A.find("front/article-meta/custom-meta-group")
    if cmg is not None:
        c = etree.SubElement(cmg, "custom-meta", {"id": f"metachange{len(ch)}"})
        etree.SubElement(c, "meta-name").text = "metadata-change"
        etree.SubElement(c, "meta-value").text = (f"{field}: «{printed}» -> «{corrected}» (source: gemini; reason: "
                                                  f"{reason})")
    Mo.stats[f"meta_corrected_{field.split('[')[0]}"] += 1


def _tag_parts(el, s: str, parts: dict):
    """el's text = s with each part (an exact substring) tagged in place (as jats43.affs does)."""
    import jats43 as J
    spans = []
    for k, v in parts.items():
        if k in AFF_TAGS and v and v in s:
            i = s.index(v)
            spans.append((i, i + len(v)) + AFF_TAGS[k])
    for m in J.EMAIL.finditer(s):
        spans.append((m.start(), m.end(), "email", None))
    spans = J.Slots.no_overlap(spans)
    for ch in list(el):
        el.remove(ch)
    el.text = s
    pos, last = 0, None
    for i, j, tag, ct in spans:
        if last is None:
            el.text = s[pos:i]
        else:
            last.tail = s[pos:i]
        last = etree.SubElement(el, tag, {"content-type": ct} if ct else {})
        last.text = s[i:j]
        pos = j
    if last is not None:
        last.tail = s[pos:]


def enrich(Mo, A, answers: list[dict], st):
    """The article-level keys of the first chunk's "enrich" -> JATS (enrich43 docstring has the list)."""
    import jats43 as J
    import refs43
    E = answers[0].get("enrich") if answers and isinstance(answers[0].get("enrich"), dict) else {}
    am = A.find("front/article-meta")
    if am is None:
        return
    dt = E.get("doc_type")
    if dt:
        A.set("article-type", DOC_JATS.get(dt, "other"))
        ac = am.find("article-categories")
        if ac is None:
            ac = J.put(am, etree.Element("article-categories"))
        sg = etree.SubElement(ac, "subj-group", {"subj-group-type": "document-type", "specific-use": "argon"})
        etree.SubElement(sg, "subject").text = dt
        st[f"enrich_doc_{dt}"] += 1
    cf = E.get("conference")
    if cf:
        el = etree.Element("conference")
        for k, tag in (("name", "conf-name"), ("date", "conf-date"), ("place", "conf-loc")):
            if cf.get(k):
                etree.SubElement(el, tag).text = cf[k]
        J.put(am, el)
        st["enrich_conference"] += 1
        sub_ = am.find("title-group/subtitle")
        if sub_ is not None:
            s = tx(sub_)
            covered = norm("".join(cf.get(k, "") for k in ("name", "place", "date")))
            if s and norm(s) and (norm(s) in covered or sum(len(norm(v)) for v in cf.values()
                                                             if norm(v) and norm(v) in norm(s)) >= 0.8 * len(norm(s))):
                sub_.getparent().remove(sub_)
                _log(Mo, A, "subtitle", s, "conference (conf-name / conf-loc / conf-date)",
                     "a conference line printed under the title, not a subtitle (prompt v3.5)")
    th = E.get("thesis")
    if th:
        pr = etree.Element("product", {"product-type": "thesis"})
        if th.get("supervisor"):
            pg = etree.SubElement(pr, "person-group", {"person-group-type": "supervisor"})
            etree.SubElement(pg, "string-name").text = th["supervisor"]
        for k, tag, at in (("degree", "comment", {"content-type": "degree"}), ("university", "institution", {}),
                           ("year", "year", {})):
            if th.get(k):
                etree.SubElement(pr, tag, at).text = th[k]
        J.put(am, pr)
        st["enrich_thesis"] += 1
    rv = E.get("reviewed")
    if isinstance(rv, dict):
        printed = " ".join(" ".join(str(L.get("text") or "") for L in Mo.S.lines.values()).split())
        ec = refs43.citation(rv, printed, st, getattr(Mo, "lang", "ar"))
        if ec is not None:
            pr = etree.Element("product", {"product-type": "book"})
            for ch in list(ec):
                pr.append(ch)
            J.put(am, pr)
            st["enrich_reviewed_book"] += 1
    og = E.get("original")
    if og:
        ra = etree.Element("related-article", {"related-article-type": "translated-from", "id": "related-original"})
        if og.get("lang"):
            ra.set(XML_LANG, og["lang"])
        for k, tag in (("title", "article-title"), ("author", "string-name"), ("source", "source")):
            if og.get(k):
                e = etree.SubElement(ra, tag)
                e.text = og[k]
                e.tail = " "
        J.put(am, ra)
        st["enrich_original"] += 1
    pt = E.get("part")
    if pt and pt.get("n"):
        c = etree.SubElement(am.find("custom-meta-group"), "custom-meta", {"id": "enrich-series-part"})
        etree.SubElement(c, "meta-name").text = "series-part"
        etree.SubElement(c, "meta-value").text = pt["n"] + (f" (series: {pt['of']})" if pt.get("of") else "")
        st["enrich_series_part"] += 1
    # authors
    cg = am.find("contrib-group")
    import enrich43
    for au in E.get("authors") or []:
        c, folded = _contrib(cg, au["a"])
        if c is None:
            st["enrich_author_not_found"] += 1
            continue
        if au.get("corresp"):
            c.set("corresp", "yes")
            st["enrich_corresp"] += 1
        ids = ([("orcid", au["orcid"])] if au.get("orcid") else []) + sorted((au.get("ids") or {}).items())
        for k, v in reversed(ids):
            e = etree.Element("contrib-id", {"contrib-id-type": k})
            e.text = v
            c.insert(0, e)
            st[f"enrich_contrib_id_{k}"] += 1
        for k_, af in enumerate(au.get("affs") or []):
            old = c.find("aff")
            s = tx(old) if old is not None else ""
            if k_ == 0 and old is not None and all(v in s for v in af.values()):
                _tag_parts(old, s, af)                        # the printed string, re-tagged with a faculty part
                st["enrich_aff_retagged"] += 1
                continue
            new = etree.SubElement(c, "aff", {"content-type": "additional", "specific-use": "parts-as-printed"})
            _tag_parts(new, "، ".join(af[k] for k in ("faculty", "department", "institution", "city", "country")
                                     if af.get(k)), af)
            st["enrich_aff_added"] += 1
        for lid in au.get("note") or []:
            el = enrich43.target_el(A, Mo, lid)
            fn = next((e for e in ([el] + list(el.iterancestors()) if el is not None else []) if e.tag == "fn"), None)
            if fn is None or fn.getparent() is None or fn.getparent().tag == "author-notes":
                continue
            grp = fn.getparent()
            grp.remove(fn)
            if grp.tag == "fn-group" and grp.find("fn") is None:
                grp.getparent().remove(grp)
            an = am.find("author-notes")
            if an is None:
                an = J.put(am, etree.Element("author-notes"))
            fn.set("fn-type", "custom")
            fn.set("custom-type", "author-note")
            an.append(fn)
            if fn.get("id"):
                x = etree.SubElement(c, "xref", {"ref-type": "author-notes", "rid": fn.get("id")})
                x.text = ""
            st["enrich_author_note"] += 1
        if au.get("same_as"):
            twin, _ = _contrib(cg, au["same_as"])
            if twin is None or twin is c or folded:
                st["enrich_same_as_already_one"] += 1
                continue
            ar, la = (twin, c)                                # c (author a) is author same_as printed again
            if ARABIC.search(tx(main_name(c))) and not ARABIC.search(tx(main_name(twin))):
                ar, la = c, twin                              # the person keeps the article's (Arabic) name
            nl = " ".join("".join(main_name(la).itertext()).split())
            sn = main_name(ar)
            na = sn.getparent() if sn.getparent().tag == "name-alternatives" else None
            if na is None:
                na = etree.Element("name-alternatives")
                sn.addprevious(na)
                na.append(sn)
            ls = etree.SubElement(na, "string-name", {XML_LANG: "en" if LATIN.search(nl) and not ARABIC.search(nl)
                                                      else "ar"})
            ls.set("id", la.get("id"))
            ls.text = nl
            if os.environ.get("EXP65_OFF") != "1":
                keep_twin_parts(ar, la, na)           # M2 (exp 65): every aff, e-mail, post and id of the twin
            else:
                for e in list(la):
                    if e.tag in ("email", "aff", "contrib-id") and ar.find(e.tag) is None:
                        (ar.insert(0, e) if e.tag == "contrib-id" else ar.append(e))
            if la.get("corresp"):
                ar.set("corresp", la.get("corresp"))
            cg.remove(la)
            _log(Mo, A, "authors", f"«{tx(sn)}» and «{nl}» as two authors", f"«{tx(sn)}» (also printed «{nl}»)",
                 "one person printed in two scripts (prompt v3.5 same_as)")
            st["enrich_same_as_folded"] += 1
