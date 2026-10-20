"""Experiment 43: the JATS slots experiment 41's masters left empty, filled after Master43.build() (no model calls).

Each slot moves or copies what the article already holds; element ids are kept, so every ALTO block still points at
its JATS element and the Layout view draws each block where it is printed. Sources: the blocks (prompt v2 / v3 block
types), the answer's metadata (v2: abstract line ids, keywords strings, affiliation, email; v3 adds trans_titles,
history, aff_parts) and, as a fallback for answers that lack a v3 field, the printed text itself.

  translated title   a title block marked translated (v3) or, for older answers, a Latin block on page 1 that matches
                     the catalogue's translated title -> title-group/trans-title-group[@xml:lang]/trans-title (the
                     printed lines; the catalogue's trans-subtitle splits off the last lines when it matches them).
                     The printed one wins: the catalogue's is dropped when it says the same, else kept as
                     alt-title[@alt-title-type="catalogue-translation"]
  abstracts          body p[@content-type="abstract"] (and p whose lines the metadata lists as an abstract) ->
                     article-meta/abstract (the article's language) and trans-abstract[@xml:lang] (others); a heading
                     «الملخص» / «Abstract» just above becomes the abstract's title. Out of the body, so an edition
                     prints each abstract once (inkscript edition reads front abstracts)
  keywords           body p[@content-type="keywords"] -> kwd-group[@kwd-group-type="author-printed"][@xml:lang]
                     (label -> title, one kwd per keyword); the metadata's keywords when no block holds them.
                     The catalogue's kwd-groups stay, with specific-use="catalogue"
  history            dates printed about the article (received / revised / accepted / published): v3 metadata
                     "history" or the printed labels (تاريخ الاستلام ...; Received ...) -> history/date[@date-type]
                     with day / month / year and @iso-8601-date; a published date also as a second pub-date
                     [@date-type="pub"] with day and month (after the catalogue's, which has the year only; the DTD
                     has no specific-use on pub-date). A body block that is only dates goes to the front
                     as a printed front-matter block (out of the article's running text)
  affiliations       contrib/aff keeps the printed string; its parts tagged in place: institution
                     [@content-type="dept" | "orgname"], addr-line[@content-type="city"], country, email (v3
                     aff_parts; else a country list and institution words)
  catalogue people   a printed author the catalogue names too: its authority id (contrib-id), structured names
                     (name-alternatives: Arabic and Latin surname / given-names, the printed string-name kept) and
                     role
  boxed text         p[@content-type="boxed"] (v3 block type "boxed"; one box = the blocks with the same "box"
                     number on a page, carried in the block's level) -> boxed-text
  endnotes           fn of an endnote (id en-...) -> back/fn-group[@content-type="endnotes"]; the heading just above
                     the run becomes its title; footnotes stay in fn-group[@content-type="footnotes"]; ids and calls
                     unchanged
  ack / appendices   a section headed شكر وتقدير / Acknowledgements -> back/ack; ملحق / الملاحق / Appendix ->
                     back/app-group/app
"""
from __future__ import annotations

import copy
import re
import unicodedata

from lxml import etree

XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

AM_ORDER = ["article-id", "article-version", "article-version-alternatives", "article-categories", "title-group",
            "contrib-group", "aff", "aff-alternatives", "x", "author-notes", "content-language", "pub-date",
            "pub-date-not-available", "volume", "volume-id", "volume-series", "issue", "issue-id", "issue-title",
            "issue-title-group", "issue-sponsor", "issue-part", "volume-issue-group", "isbn", "supplement", "fpage",
            "lpage", "page-range", "elocation-id", "email", "ext-link", "uri", "product", "supplementary-material",
            "history", "pub-history", "permissions", "self-uri", "related-article", "related-object", "abstract",
            "trans-abstract", "kwd-group", "funding-group", "support-group", "conference", "counts",
            "custom-meta-group"]

ABSTRACT_HEAD = re.compile(r"^(ال)?(ملخص|مستخلص|خلاصة)(\s+(ال)?(بحث|دراسة|مقال))?|^(abstract|r[ée]sum[ée]|summary)$",
                           re.I)
KW_LABEL = re.compile(r"^\s*((ال)?كلمات\s+(ال)?(مفتاحية|دالة|مفتاحيه)|key\s*-?\s*words?|mots[\s-]*cl[ée]s|"
                      r"index\s+terms)\s*[:：.\-–]?\s*", re.I)
ACK_HEAD = re.compile(r"^((ال)?شكر(\s+و\s*|\s+و)(ال)?(تقدير|عرفان)|(كلمة\s+)?شكر|acknowledg(e)?ments?|remerciements?)$",
                      re.I)
APP_HEAD = re.compile(r"^((ال)?(ملحق|ملاحق)(\s+(رقم\s*)?[\d\w()]{1,4})?(\s+البحث|\s+الدراسة)?|appendi(x|ces)"
                      r"(\s+[\w\d]{1,3})?|annexes?(\s+[\w\d]{1,3})?)$", re.I)

H_LABELS = [
    ("received", r"تاريخ\s*(ال)?(استلام|إستلام|استقبال|إستقبال|ارسال|إرسال|تسليم|إيداع|ايداع|تقديم|ورود)(\s+(ال)?بحث)?|"
                 r"(تاريخ\s*)?(ال)?(استلام|الإستلام|إستلام)|received|date\s+of\s+(receipt|submission)|submitted|re[çc]u"),
    ("revised", r"تاريخ\s*(ال)?(تعديل|مراجعة)|revised|r[ée]vis[ée]"),
    ("reviewed", r"تاريخ\s*(ال)?تحكيم|reviewed"),
    ("accepted", r"تاريخ\s*(ال)?(قبول|موافقة)(\s+(لل|ال)?نشر)?|(ال)?قبول\s+(لل)?نشر|accepted|accept[ée]"),
    ("published", r"تاريخ\s*(ال)?(نشر|اصدار|إصدار)|published(\s+online)?|publi[ée]"),
]
H_RE = re.compile("|".join(f"(?P<{k}>{v})" for k, v in H_LABELS), re.I)

MONTHS = {}
for _n, _names in enumerate([
        "يناير جانفي كانون الثاني january janvier jan", "فبراير فيفري شباط february février fevrier feb",
        "مارس آذار اذار march mars mar", "أبريل ابريل إبريل أفريل افريل نيسان april avril apr",
        "مايو ماي أيار ايار may mai", "يونيو يونيه جوان حزيران june juin jun",
        "يوليو يوليه جويلية جويلة تموز july juillet jul", "أغسطس اغسطس أوت اوت آب اب august août aout aug",
        "سبتمبر أيلول ايلول september septembre sep sept", "أكتوبر اكتوبر تشرين الأول october octobre oct",
        "نوفمبر تشرين الثاني november novembre nov", "ديسمبر كانون الأول december décembre decembre dec"], 1):
    for _w in re.split(r"\s+", _names):
        MONTHS.setdefault(_w, _n)
TWO_WORD_MONTHS = {"كانون الثاني": 1, "تشرين الأول": 10, "تشرين الاول": 10, "تشرين الثاني": 11, "كانون الأول": 12,
                   "كانون الاول": 12}

COUNTRIES = ["مصر", "ليبيا", "تونس", "الجزائر", "المغرب", "السودان", "موريتانيا", "السعودية", "المملكة العربية السعودية",
             "الأردن", "الاردن", "سوريا", "سورية", "لبنان", "فلسطين", "العراق", "الكويت", "قطر", "البحرين", "الإمارات",
             "الامارات", "الإمارات العربية المتحدة", "عمان", "سلطنة عمان", "اليمن", "تركيا", "إيران", "ماليزيا",
             "فرنسا", "Egypt", "Libya", "Tunisia", "Algeria", "Algérie", "Morocco", "Maroc", "Sudan", "Saudi Arabia",
             "KSA", "Jordan", "Syria", "Lebanon", "Liban", "Palestine", "Iraq", "Kuwait", "Qatar", "Bahrain", "UAE",
             "United Arab Emirates", "Oman", "Yemen", "Turkey", "Malaysia", "France", "USA", "UK", "Canada"]
ORG_WORDS = re.compile(r"جامعة|الجامعة|معهد|مركز|أكاديمية|اكاديمية|وزارة|هيئة|مجمع|المجمع|university|université|"
                       r"universite|institute|institut|center|centre|academy|ministry|école|ecole|school", re.I)
DEPT_WORDS = re.compile(r"كلية|قسم|شعبة|مخبر|مختبر|faculty|faculté|faculte|department|département|departement|"
                        r"college|laborator", re.I)
EMAIL = re.compile(r"[\w.+-]+@[\w-]+(\.[\w-]+)+")


def tx(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def norm(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").casefold()
    return re.sub(r"[\W_]+", "", s)


def is_latin(s: str) -> bool:
    lat = sum(1 for c in s if c.isalpha() and c.isascii())
    ar = sum(1 for c in s if "؀" <= c <= "ۿ")
    return lat > 2 * max(ar, 1)


def put(am, el):
    """Insert el into article-meta at its place in the JATS order."""
    rank = AM_ORDER.index(el.tag)
    pos = 0
    for i, c in enumerate(am):
        if isinstance(c.tag, str) and c.tag in AM_ORDER and AM_ORDER.index(c.tag) <= rank:
            pos = i + 1
    am.insert(pos, el)
    return el


def move_children(src, dst):
    dst.text = (dst.text or "") + (src.text or "")
    for c in list(src):
        dst.append(c)


def detach(el):
    """Remove el, keeping its tail text with the previous sibling or the parent."""
    par = el.getparent()
    if el.tail and el.tail.strip():
        prev = el.getprevious()
        if prev is not None:
            prev.tail = (prev.tail or "") + el.tail
        else:
            par.text = (par.text or "") + el.tail
    par.remove(el)


def lang_attr(el, default):
    return el.get(XML_LANG) or default


# ------------------------------------------------------------------------------------------------ dates

def parse_date(s: str) -> dict | None:
    """day / month / year from a printed date: 2022/05/12, 12-05-2022, 12 مايو 2022, May 12, 2022 (digits any
    script). None when no four-digit year."""
    t = (s or "").translate(DIGITS)
    t = re.sub(r"[‎‏؜]", "", t)
    m = re.search(r"\b(\d{4})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{1,2})\b", t)
    if m:
        y, mo, d = int(m[1]), int(m[2]), int(m[3])
        return _ok(y, mo, d)
    m = re.search(r"\b(\d{1,2})\s*[/.\-]\s*(\d{1,2})\s*[/.\-]\s*(\d{4})\b", t)
    if m:
        d, mo, y = int(m[1]), int(m[2]), int(m[3])
        if mo > 12 and d <= 12:
            d, mo = mo, d
        return _ok(y, mo, d)
    low = t.casefold()
    mo = None
    for k, v in TWO_WORD_MONTHS.items():
        if k in low:
            mo = v
    if mo is None:
        for w in re.findall(r"[^\W\d_]+", low):
            if w in MONTHS:
                mo = MONTHS[w]
                break
    y = re.search(r"\b(1[89]\d\d|20\d\d)\b", t)
    if not y:
        return None
    d = re.search(r"\b(\d{1,2})\b", t[:y.start()] + " " + t[y.end():])
    return _ok(int(y[1]), mo, int(d[1]) if d and mo else None)


def _ok(y, mo, d):
    if not (1800 <= y <= 2100):
        return None
    if mo is not None and not 1 <= mo <= 12:
        mo, d = None, None
    if d is not None and not 1 <= d <= 31:
        d = None
    return dict(year=y, month=mo, day=d)


def history_in(text: str) -> list[dict]:
    """(type, printed date, parsed) for each label + date in a line of text."""
    out = []
    ms = list(H_RE.finditer(text or ""))
    for i, m in enumerate(ms):
        end = ms[i + 1].start() if i + 1 < len(ms) else len(text)
        seg = re.sub(r"^[\s:：\-–—،,;؛.]*(بتاريخ|في|on|le)?[\s:：]*", "", text[m.end():end]).strip(" :：-–—،,;؛.")
        first = (re.match(r"[^\W_]+", seg.translate(DIGITS).casefold()) or [""])[0]
        if not (first[:1].isdigit() or first in MONTHS or any(seg.startswith(k) for k in TWO_WORD_MONTHS)):
            continue                                      # the label must be followed by the date itself
        pd = parse_date(seg[:40])
        if pd:
            out.append(dict(type=m.lastgroup, text=seg[:40].strip(), date=pd))
    return out


def date_el(tag, typ, pd, printed, attrs=None):
    el = etree.Element(tag, {"date-type": typ, **(attrs or {})})
    iso = f"{pd['year']:04d}" + (f"-{pd['month']:02d}" if pd["month"] else "") + \
          (f"-{pd['day']:02d}" if pd["month"] and pd["day"] else "")
    el.set("iso-8601-date", iso)
    if pd["day"] and pd["month"]:
        etree.SubElement(el, "day").text = f"{pd['day']:02d}"
    if pd["month"]:
        etree.SubElement(el, "month").text = f"{pd['month']:02d}"
    etree.SubElement(el, "year").text = str(pd["year"])
    if printed:
        etree.SubElement(el, "string-date").text = printed
    return el


# ------------------------------------------------------------------------------------------------ the slots

class Slots:
    def __init__(self, Mo, A):
        self.M, self.A = Mo, A
        self.am = A.find("front/article-meta")
        self.body = A.find("body")
        self.lang = Mo.lang
        self.tl2lid = {v: k for k, v in Mo.tl_of.items()}
        self.st = Mo.stats
        self.meta = Mo.meta or {}

    def back(self):
        b = self.A.find("back")
        if b is None:
            b = etree.SubElement(self.A, "back")
        return b

    def lids(self, el) -> list[str]:
        return [self.tl2lid[t.get("id")] for t in el.iter("target") if t.get("id") in self.tl2lid]

    def run(self):
        self.trans_titles()
        self.abstracts()
        self.keywords()
        self.history()
        self.affs()
        self.people()
        self.boxed()
        self.endnotes()
        self.ack_app()
        self.tidy()

    # ---------------------------------------------------------------- translated title
    def trans_titles(self):
        tg = self.am.find("title-group")
        cat = [t for t in tg.findall("trans-title-group")]
        for t in cat:
            t.set("specific-use", "catalogue")
        printed = []
        for p in list(self.body.iter("p")):
            if p.get("content-type") != "trans_title":
                continue
            lg = p.get(XML_LANG) or ("en" if is_latin(tx(p)) else self.lang)
            g = etree.Element("trans-title-group", {XML_LANG: lg, "specific-use": "printed"})
            tt = etree.SubElement(g, "trans-title", {"id": p.get("id")} if p.get("id") else {})
            move_children(p, tt)
            detach(p)
            same = next((c for c in cat if c.get(XML_LANG) == lg), None)
            if same is not None:
                sub_c = tx(same.find("trans-subtitle"))
                if sub_c and len(self.lids(tt)) >= 2:
                    self.split_subtitle(tt, g, sub_c)
            printed.append(g)
            self.st["jats_trans_title_printed"] += 1
        if not printed:
            return
        anchor = tg.find("trans-title-group")
        for g in printed:
            if anchor is not None:
                anchor.addprevious(g)
            else:
                after = tg.findall("subtitle") or tg.findall("article-title")
                after[-1].addnext(g)
        for c in cat:
            lg = c.get(XML_LANG)
            mine = [g for g in printed if g.get(XML_LANG) == lg]
            if not mine:
                continue
            ct = " ".join(x for x in (tx(c.find("trans-title")), tx(c.find("trans-subtitle"))) if x)
            pt = " ".join(tx(g) for g in mine)
            tg.remove(c)
            if norm(ct) != norm(pt):
                alt = etree.Element("alt-title", {"alt-title-type": "catalogue-translation", XML_LANG: lg})
                alt.text = ct
                alts = tg.findall("alt-title")
                (alts[-1].addnext(alt) if alts else tg.findall("trans-title-group")[-1].addnext(alt))
                self.st["jats_trans_title_catalogue_kept_as_alt"] += 1
            else:
                self.st["jats_trans_title_catalogue_same"] += 1

    def split_subtitle(self, tt, g, sub_c):
        """The catalogue's trans-subtitle printed as the last line(s) of the translated title: into trans-subtitle."""
        targets = [t for t in tt.iter("target")]
        for k in range(1, len(targets)):
            t = targets[k]
            if t.getparent() is not tt:
                continue
            rest = "".join(t.itertext()) + (t.tail or "") + "".join(
                "".join(s.itertext()) + (s.tail or "") for s in t.itersiblings())
            if norm(rest) == norm(sub_c):
                ts = etree.SubElement(g, "trans-subtitle")
                ts.text = ""
                prev = t.getprevious()
                if prev is not None and prev.tail:
                    prev.tail = prev.tail.rstrip()
                elif tt.text:
                    tt.text = tt.text.rstrip()
                for s in [t] + list(t.itersiblings()):
                    ts.append(s)
                self.st["jats_trans_subtitle_split"] += 1
                return

    # ---------------------------------------------------------------- abstracts
    def abstracts(self):
        meta_ids = set()
        ab = self.meta.get("abstract")
        if isinstance(ab, dict):
            for v in ab.values():
                if isinstance(v, list):
                    meta_ids.update(str(x) for x in v)
        ps = []
        for p in self.body.iter("p"):
            if p.getparent().tag in ("fn", "list-item", "disp-quote", "fig", "boxed-text", "caption", "td", "th"):
                continue
            ct = p.get("content-type")
            if ct == "abstract":
                ps.append(p)
            elif ct in (None, "other") and meta_ids:
                ls = self.lids(p)
                if ls and all(l in meta_ids or l.rstrip("abcdefgh") in meta_ids for l in ls):
                    p.set("content-type", "abstract")
                    ps.append(p)
                    self.st["jats_abstract_from_metadata_ids"] += 1
        if not ps:
            return
        groups = {}
        for p in ps:
            lg = p.get(XML_LANG) or (self.lang if not is_latin(tx(p)) or self.lang != "ar" else "en")
            groups.setdefault(lg, []).append(p)
        order = sorted(groups, key=lambda lg: (lg != self.lang, list(groups).index(lg)))
        for k, lg in enumerate(order):
            first = k == 0 and lg == self.lang
            el = etree.Element("abstract" if first else "trans-abstract", {"abstract-type": "printed"})
            if not first:
                el.set(XML_LANG, lg)
            head = self.head_before(groups[lg][0])
            if head is not None:
                t = etree.SubElement(el, "title", {"id": head.get("id")} if head.get("id") else {})
                move_children(head, t)
                sec = head.getparent()
                detach(head)
                self.st["jats_abstract_titles"] += 1
                sec.set("_emptied", "1")
            for p in groups[lg]:
                par = p.getparent()
                detach(p)
                p.attrib.pop(XML_LANG, None)
                el.append(p)
                par.set("_emptied", "1") if par.tag == "sec" else None
            put(self.am, el)
            self.st["jats_abstract" if first else "jats_trans_abstract"] += 1
            self.st["jats_abstract_paragraphs"] += len(groups[lg])

    def head_before(self, p):
        """The heading «الملخص» / «Abstract» heading the section this abstract paragraph opens."""
        sec = p.getparent()
        if sec.tag != "sec":
            return None
        t = sec.find("title")
        if t is None or not ABSTRACT_HEAD.match(re.sub(r"[\s:：.\-–]+$", "", tx(t)).strip()):
            return None
        kids = [c for c in sec if isinstance(c.tag, str) and c is not t]
        if all(c.tag == "p" and c.get("content-type") in ("abstract", "keywords") for c in kids):
            return t
        return None

    # ---------------------------------------------------------------- keywords
    def keywords(self):
        for kg in self.am.findall("kwd-group"):
            if kg.get("specific-use") is None:
                kg.set("specific-use", "catalogue")
        found = set()
        for p in list(self.body.iter("p")):
            if p.get("content-type") != "keywords" or p.getparent().tag in ("fn", "list-item", "td", "th"):
                continue
            t = tx(p)
            lg = p.get(XML_LANG) or ("en" if is_latin(t) else self.lang)
            kg = self.kwd_group(t, lg, p.get("id"))
            if kg is None:
                continue
            par = p.getparent()
            detach(p)
            if par.tag == "sec":
                par.set("_emptied", "1")
            put(self.am, kg)
            found.add(lg)
            self.st["jats_kwd_groups_printed"] += 1
        kw = self.meta.get("keywords")
        if isinstance(kw, dict):
            for lg, v in kw.items():
                if isinstance(v, str) and v.strip() and lg not in found and lg in ("ar", "en", "fr"):
                    kg = self.kwd_group(v, lg, None)
                    if kg is not None:
                        kg.set("specific-use", "metadata")
                        put(self.am, kg)
                        self.st["jats_kwd_groups_from_metadata"] += 1
        # printed groups before the catalogue's
        groups = self.am.findall("kwd-group")
        mine = [g for g in groups if g.get("kwd-group-type") == "author-printed"]
        if mine and groups[0] not in mine:
            for g in mine:
                groups[0].addprevious(g)

    def kwd_group(self, t, lg, id_):
        m = KW_LABEL.match(t)
        label, rest = (t[:m.end()].strip(), t[m.end():]) if m else ("", t)
        kws = [k.strip(" .،,;؛:-–") for k in re.split(r"\s*[،,;؛]\s*|\s+[-–]\s+", rest)]
        kws = [k for k in kws if k]
        if not kws:
            return None
        kg = etree.Element("kwd-group", {"kwd-group-type": "author-printed"})
        if id_:
            kg.set("id", id_)
        if lg != self.lang or lg != "ar":
            kg.set(XML_LANG, lg)
        if label:
            etree.SubElement(kg, "title").text = label
        for k in kws:
            etree.SubElement(kg, "kwd").text = k
        self.st["jats_kwds_printed"] += len(kws)
        return kg

    # ---------------------------------------------------------------- history
    def history(self):
        got = {}
        meta_h = self.meta.get("history")
        if isinstance(meta_h, list):
            for h in meta_h:
                if not isinstance(h, dict):
                    continue
                typ = str(h.get("type") or "").lower()
                pd = parse_date(str(h.get("text") or ""))
                if typ in ("received", "reviewed", "revised", "accepted", "published", "online") and pd and typ not in got:
                    got[typ] = dict(type=typ, text=str(h["text"]).strip(), date=pd, src="metadata")
        # the printed labels (older answers; also the check on the metadata): first page and last page text
        lines = [L for L in self.M.S.lines.values() if L["page"] in (min(self.M.pages), max(self.M.pages))
                 and not L.get("split")] if self.M.whole_start else []
        date_lids = set()
        for L in lines:
            hs = history_in(L["text"])
            for h in hs:
                got.setdefault(h["type"], dict(h, src="printed"))
            if hs:
                date_lids.add(L["id"])
        if not got:
            return
        hist = etree.Element("history")
        for typ in ("received", "reviewed", "revised", "accepted", "online"):
            if typ in got:
                hist.append(date_el("date", typ, got[typ]["date"], got[typ]["text"]))
                self.st["jats_history_dates"] += 1
        if typ_pub := got.get("published"):
            hist.append(date_el("date", "published", typ_pub["date"], typ_pub["text"]))
            self.st["jats_history_dates"] += 1
            pds = self.am.findall("pub-date")
            pd = date_el("pub-date", "pub", typ_pub["date"], None, {"publication-format": "print"})
            if pds:
                pds[-1].addnext(pd)
            else:
                put(self.am, pd)
            self.st["jats_pub_date_printed"] += 1
        if len(hist):
            put(self.am, hist)
        # a body block that is only dates: out of the running text, kept as a printed front-matter block
        for p in list(self.body.iter("p")):
            ls = self.lids(p)
            if ls and p.getparent().tag in ("body", "sec") and all(l in date_lids for l in ls):
                cmg = self.am.find("custom-meta-group")
                c = etree.SubElement(cmg, "custom-meta", {"id": p.get("id")})
                etree.SubElement(c, "meta-name").text = "front-matter-block"
                mv = etree.SubElement(c, "meta-value")
                move_children(p, mv)
                par = p.getparent()
                detach(p)
                if par.tag == "sec":
                    par.set("_emptied", "1")
                self.st["jats_dates_block_to_front"] += 1

    # ---------------------------------------------------------------- affiliations
    def affs(self):
        parts_of = {}
        for au in self.meta.get("authors") or []:
            if isinstance(au, dict) and isinstance(au.get("aff_parts"), dict):
                parts_of[(au.get("affiliation") or "").strip()] = au["aff_parts"]
        for c in self.am.iter("contrib"):
            for aff in c.findall("aff"):
                if len(aff):
                    continue
                s = aff.text or ""
                spans = []
                given = parts_of.get(s.strip()) or {}
                for k, tag, ct in (("department", "institution", "dept"), ("institution", "institution", "orgname"),
                                   ("city", "addr-line", "city"), ("country", "country", None)):
                    v = (given.get(k) or "").strip() if isinstance(given.get(k), str) else ""
                    if v and v in s:
                        i = s.index(v)
                        spans.append((i, i + len(v), tag, ct))
                if not spans:
                    spans = self.guess_aff(s)
                for m in EMAIL.finditer(s):
                    spans.append((m.start(), m.end(), "email", None))
                spans = self.no_overlap(spans)
                if not spans:
                    continue
                aff.text = ""
                pos, last = 0, None
                for i, j, tag, ct in spans:
                    if last is None:
                        aff.text = s[pos:i]
                    else:
                        last.tail = s[pos:i]
                    last = etree.SubElement(aff, tag, {"content-type": ct} if ct else {})
                    last.text = s[i:j]
                    pos = j
                    self.st[f"jats_aff_{tag}{'_' + ct if ct else ''}"] += 1
                last.tail = s[pos:]
                self.st["jats_affs_tagged"] += 1

    def guess_aff(self, s):
        spans = []
        for name in sorted(COUNTRIES, key=len, reverse=True):
            for m in re.finditer(r"(?<![\w])" + re.escape(name) + r"(?![\w])", s):
                spans.append((m.start(), m.end(), "country", None))
        segs = [(m.start(), m.end()) for m in re.finditer(r"[^،,()\-–/\n]+", s)]
        for i, j in segs:
            seg = s[i:j]
            k0 = len(seg) - len(seg.lstrip())
            k1 = len(seg.rstrip())
            if k1 <= k0 or EMAIL.search(seg):
                continue
            if DEPT_WORDS.search(seg):
                spans.append((i + k0, i + k1, "institution", "dept"))
            elif ORG_WORDS.search(seg):
                spans.append((i + k0, i + k1, "institution", "orgname"))
        return spans

    @staticmethod
    def no_overlap(spans):
        out = []
        for sp in sorted(spans, key=lambda x: (x[0], -(x[1] - x[0]))):
            if out and sp[0] < out[-1][1]:
                continue
            out.append(sp)
        return out

    # ---------------------------------------------------------------- the catalogue's people
    def people(self):
        """A printed author the catalogue also names (its printed-on-the-page string or its Arabic name, letters
        only): the catalogue's authority id (contrib-id) and structured names in Arabic and Latin script
        (name-alternatives, the printed string-name kept inside) and its role."""
        if not self.M.a.get("jats"):
            return
        try:
            cat = etree.parse(self.M.a["jats"], etree.XMLParser(load_dtd=False, no_network=True)).getroot()
        except Exception:
            return
        cc = []
        for c in cat.iterfind("front/article-meta/contrib-group/contrib"):
            keys = {norm(tx(x)) for x in c.iter("string-name")}
            for nm in c.iter("name"):
                if nm.get(XML_LANG) in (None, "ar"):
                    keys.add(norm(tx(nm.find("given-names")) + tx(nm.find("surname"))))
            cc.append((keys - {""}, c))
        for c in self.am.iterfind("contrib-group/contrib"):
            sn = c.find("string-name")
            if sn is None:                              # meta43.names_pre: the corrected name in name-alternatives
                sn = next((s for s in c.iterfind("name-alternatives/string-name")
                           if s.get("specific-use") != "printed-on-the-page" and not s.get(XML_LANG)), None)
            if sn is None:
                continue
            k = norm(sn.text or "")
            hit = next((x for keys, x in cc if k and any(k == q or (len(q) > 6 and (q in k or k in q))
                                                          for q in keys)), None)
            if hit is None:
                continue
            for cid in reversed(hit.findall("contrib-id")):
                c.insert(0, copy.deepcopy(cid))
            names = [copy.deepcopy(n) for n in hit.iter("name")]
            if names and sn.getparent().tag == "name-alternatives":     # already corrected (honorific out)
                na = sn.getparent()
                for k_, n in enumerate(names):
                    na.insert(k_, n)
            elif names:
                na = etree.Element("name-alternatives")
                sn.addprevious(na)
                for n in names:
                    na.append(n)
                na.append(sn)
                sn.set("specific-use", "printed-on-the-page")
            role = hit.find("role")
            if role is not None and c.find("role") is None:
                r = copy.deepcopy(role)
                last = [e for e in c if e.tag in ("contrib-id", "name-alternatives", "string-name")][-1]
                last.addnext(r)
            self.st["jats_contrib_from_catalogue"] += 1

    # ---------------------------------------------------------------- boxed text
    def boxed(self):
        box_of = {}
        for r in self.M.recs:
            if r["type"] == "boxed":
                for i in r["ids"]:
                    box_of[i] = (r["page"], r.get("level"))
        n = 0
        for par in list(self.body.iter()):
            kids = [c for c in par if isinstance(c.tag, str)]
            run, key = [], None
            for c in kids + [None]:
                k = None
                if c is not None and c.tag == "p" and c.get("content-type") == "boxed":
                    ls = self.lids(c)
                    k = box_of.get(ls[0], ("?", None)) if ls else ("?", None)
                if run and (k is None or k != key):
                    n += 1
                    bx = etree.Element("boxed-text", {"id": f"bx{n}", "content-type": "box"})
                    run[0].addprevious(bx)
                    for e in run:
                        bx.append(e)
                    self.st["jats_boxed_text"] += 1
                    self.st["jats_boxed_paragraphs"] += len(run)
                    run = []
                if k is not None:
                    run.append(c)
                    key = k

    # ---------------------------------------------------------------- endnotes
    def endnotes(self):
        back = self.A.find("back")
        fg = back.find("fn-group") if back is not None else None
        if fg is None:
            return
        en_ids = {v for k, v in self.M.fn_map.items() if str(k).startswith("en")}
        fg.set("content-type", "footnotes")
        ens = [fn for fn in fg.findall("fn") if fn.get("id") in en_ids]
        if not ens:
            return
        eg = etree.Element("fn-group", {"content-type": "endnotes"})
        fg.addnext(eg)
        head = self.endnote_head(ens[0])
        if head is not None:
            t = etree.SubElement(eg, "title", {"id": head.get("id")} if head.get("id") else {})
            move_children(head, t)
            sec = head.getparent()
            detach(head)
            sec.set("_emptied", "1")
            self.st["jats_endnote_titles"] += 1
        for fn in ens:
            eg.append(fn)
        self.st["jats_endnotes"] += len(ens)
        if not fg.findall("fn"):
            back.remove(fg)

    def endnote_head(self, fn):
        """The heading block just before the first endnote in reading order (هوامش ...), when its section holds
        nothing else."""
        first_lid = next(iter(self.lids(fn)), None)
        if first_lid is None:
            return None
        flow = [r for r in self.M.recs if r["type"] not in ("header", "footer")]
        k = next((i for i, r in enumerate(flow) if first_lid in r["ids"]), None)
        if not k or flow[k - 1]["type"] != "heading" or not flow[k - 1]["ids"]:
            return None
        tl = self.M.tl_of.get(flow[k - 1]["ids"][0])
        if not tl:
            return None
        tgt = self.A.find(f".//target[@id='{tl}']")
        t = tgt.getparent() if tgt is not None else None
        if t is None or t.tag != "title" or t.getparent().tag != "sec":
            return None
        sec = t.getparent()
        if any(isinstance(c.tag, str) and c is not t for c in sec):
            return None
        return t

    # ---------------------------------------------------------------- acknowledgements, appendices
    def ack_app(self):
        for sec in list(self.body.iter("sec")):
            t = sec.find("title")
            if t is None or sec.getparent() is None:
                continue
            h = re.sub(r"^[\s\d٠-٩.\-–)(«»]+|[\s:：.\-–«»)(]+$", "", tx(t))      # «» since rules43.guillemets
            if ACK_HEAD.match(h):
                kind = "ack"
            elif APP_HEAD.match(h):
                kind = "app"
            else:
                continue
            back = self.back()
            detach(sec)
            sec.attrib.pop("disp-level", None)
            if kind == "ack":
                sec.tag = "ack"
                fg = back.find("fn-group")
                (fg.addprevious(sec) if fg is not None else back.insert(0, sec))
                self.st["jats_ack"] += 1
            else:
                ag = back.find("app-group")
                if ag is None:
                    ag = etree.Element("app-group")
                    back.append(ag)
                sec.tag = "app"
                ag.append(sec)
                self.st["jats_app"] += 1
            for s in sec.iter("sec"):
                s.attrib.pop("_emptied", None)

    # ---------------------------------------------------------------- tidy
    def tidy(self):
        for sec in list(self.A.iter("sec")):
            if sec.get("_emptied"):
                del sec.attrib["_emptied"]
                if not any(isinstance(c.tag, str) for c in sec):
                    detach(sec)
                    self.st["jats_sections_emptied"] += 1
        for e in self.A.iter():
            if isinstance(e.tag, str) and "_emptied" in e.attrib:
                del e.attrib["_emptied"]
        if not any(isinstance(c.tag, str) for c in self.body):
            etree.SubElement(self.body, "p")


def fill_slots(Mo, A):
    Slots(Mo, A).run()
    return A


def retype_trans_title(Mo):
    """Older answers (no v3 "translated"): a block on the article's first page in another script than the article,
    not a heading of the body, whose words match the catalogue's translated title, is the printed translated title."""
    if not Mo.whole_start or not Mo.a.get("jats"):
        return
    try:
        cat = etree.parse(Mo.a["jats"], etree.XMLParser(load_dtd=False, no_network=True)).getroot()
    except Exception:
        return
    tts = [" ".join(x for x in (tx(g.find("trans-title")), tx(g.find("trans-subtitle"))) if x)
           for g in cat.iterfind("front/article-meta/title-group/trans-title-group")]
    if not tts:
        return
    for r in Mo.recs:
        if r["page"] != min(Mo.pages) or r["type"] not in ("other", "heading", "paragraph", "title"):
            continue
        t = " ".join(Mo.S.lines[i]["text"] for i in r["ids"])
        if not is_latin(t) or Mo.lang != "ar":
            continue
        w = set(re.findall(r"\w+", t.casefold()))
        for ct in tts:
            cw = set(re.findall(r"\w+", ct.casefold()))
            if w and cw and len(w & cw) >= 0.7 * len(cw) and len(w & cw) >= 0.7 * len(w):
                r["type"] = "trans_title"
                r.setdefault("lang", "en")
                Mo.stats["trans_title_by_catalogue_match"] += 1
                break
