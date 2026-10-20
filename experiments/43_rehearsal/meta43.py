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
        if num(old[0]) and num(old[1]) and num(old[1]) - num(old[0]) + 1 == n:
            return                                   # already spans the scan's pages (1289: 16-17, catalogue too)
        new, src = None, None
        ps = sorted(fol)
        cat = catalogue_pages(self.M.stem)
        seq0 = n <= 2 or fol.get(p0 + 1) == fol.get(p0, -9) + 1 or fol.get(p0 + 2) == fol.get(p0, -9) + 2
        seq1 = n <= 2 or fol.get(p1 - 1) == fol.get(p1, -9) - 1 or fol.get(p1 - 2) == fol.get(p1, -9) - 2
        if p0 in fol and p1 in fol and fol[p1] >= fol[p0] and seq0 and seq1:     # (a lone year is not a folio)
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
    # a Latin spelling printed beside an Arabic name (1036 «جيوسيب كاروزو» / «Giuseppe Caruso»): one person
    contribs = list(cg.iterfind("contrib"))
    for c1, c2 in zip(contribs, contribs[1:]):
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
        for e in la:
            if e.tag in ("email", "aff") and ar.find(e.tag) is None:
                ar.append(e)
        cg.remove(la)
        Mo.name_changes.append(dict(field="authors", printed=f"«{na_}» and «{nl}» as two authors",
                                    corrected=f"«{na_}» (Latin spelling «{nl}»)", source="code",
                                    reason=f"one person printed in two scripts (consonant skeletons {sc:.2f})"))
        Mo.stats["names_latin_folded"] += 1


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
