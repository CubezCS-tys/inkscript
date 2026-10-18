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

    def run(self):
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


def apply(Mo, A):
    return Meta(Mo, A).run()
