"""Experiment 53: the Word route. A JATS 1.4 master per publisher's Word file, by code only (no model calls).

    .venv/bin/python experiments/53_word_route/build53.py [stem ...]      (default: out/stems_all.txt)

In:  out/docx/<stem>.docx (the publisher's .doc converted by LibreOffice), the catalogue (inkscript's MARC index),
     out/legacy_pdf/<stem>.pdf (S3 legacy/, made from the same Word file by LibreOffice + Amiri) when present.
Out: out/masters/<stem>.jats.xml (validated against the JATS 1.4 Archiving DTD the scan masters use),
     <stem>.metachanges.json (D33: printed and catalogue forms of the metadata, every change logged),
     <stem>.pdfmap.json (what replaces ALTO: each block's page and box in the legacy PDF, and its estimated printed
     page), <stem>.media/ (the Word file's pictures), out/build.json (per-article counts), stdout summary.

How each part is found (measured in README.md):
  front     the catalogue (title, people with authority ids, journal, year, volume / issue, pages) beside what the
            file's first lines print (D33): printed title kept as alt-title when it differs, printed names as
            string-name, affiliations from the lines under each name (columns split at runs of spaces / tabs),
            abstracts and keywords from their labels, the English block (title, abstract) wherever it sits
  headings  a short paragraph (<= 18 words, no closing full stop) set in a heading font (PT Bold Heading ...) or
            all bold, or a short line ending in a colon; level 1 centred or larger than the body, level 3 numbered
            or sub-numbered, else level 2; Word heading styles / outline levels when a file has them
  lists     Word's own numbered paragraphs (numbering.xml gives the label Word draws)
  notes     Word's own footnotes (footnoteReference -> fn, the call an xref); a «الهوامش» section of typed notes
            -> endnotes, linked to superscript numbers in the text
  tables    Word's tables (gridSpan -> colspan, vMerge -> rowspan), caption from the «جدول (n)» line next to it,
            notes under it (*, ملاحظة, المصدر) -> table-wrap-foot
  refs      every paragraph after a «المراجع» / References heading is one ref (mixed-citation, the Word text);
            fields split by a code parser (APA author (year). title. source, vol(issue), pages / place: publisher)
            and written by experiment 43's refs43.citation (every value checked to be a substring)
"""
from __future__ import annotations

import json
import re
import shutil
import sys
import time
import unicodedata
from collections import Counter
from pathlib import Path

from lxml import etree

sys.dont_write_bytecode = True                      # never write into experiment 43's folder
HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(HERE))
sys.path.insert(1, str(ROOT / "experiments" / "43_rehearsal"))
import docx53 as D  # noqa: E402
import jats43 as J  # noqa: E402  (read-only use: regexes, dates, put, aff tagging)
import refs43  # noqa: E402       (read-only use: citation())
from inkscript.enrich import catalogue as CAT  # noqa: E402
from inkscript.enrich.jats import E, DOCTYPE, XLINK, MML, _append  # noqa: E402
from inkscript.enrich.schemas import validate_jats  # noqa: E402

OUT = HERE / "out"
MAST = OUT / "masters"
XMLNS = "http://www.w3.org/XML/1998/namespace"
XML_LANG = f"{{{XMLNS}}}lang"
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

CAP_T = re.compile(r"^\s*[(\[]?\s*(ال)?(جدول|جـدول)\s*(رقم)?\s*[(\[]?\s*[0-9٠-٩]+|^\s*table\s*(no\.?)?\s*[0-9]+", re.I)
CAP_F = re.compile(r"^\s*[(\[]?\s*(ال)?(شكل|شـكل|رسم|مخطط|صورة|خريطة)\s*(بياني)?\s*(رقم)?\s*[(\[]?\s*[0-9٠-٩]+|"
                   r"^\s*(figure|fig\.?|chart|graph)\s*(no\.?)?\s*[0-9]+", re.I)
TNOTE = re.compile(r"^\s*(\*|ملاحظة|ملحوظة|المصدر|مصدر|note|source|\(?ن\s*=)", re.I)
REF_HEAD = re.compile(r"^(قائمة\s+|ثبت\s+)?(ال)?(مراجع|مصادر)(\s+(و|وال|ال)?(مراجع|مصادر))?"
                      r"(\s+(ال)?(بحث|دراسة|العربية|عربية|الأجنبية|الاجنبية|أجنبية|اجنبية|الإنجليزية|الانجليزية|"
                      r"الإلكترونية|الالكترونية|المستخدمة|باللغة\s+\S+|العربيه|الاجنبيه))*$|"
                      r"^(references?|bibliography|sources|works\s+cited|english\s+references|foreign\s+references)$",
                      re.I)
NOTES_HEAD = re.compile(r"^(ال)?(هوامش|حواشي|إحالات|احالات|الإحالات)(\s+و\s*(ال)?(مراجع|مصادر|تعليقات))?$|^(end)?notes$",
                        re.I)
ORDINAL = re.compile(r"^\s*(أولا|اولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)[ًاَ]*\s*[:：\-–.)]?\s*|"
                     r"^\s*[(\[]?[0-9٠-٩]{1,2}([.\-–][0-9٠-٩]{1,2})*\s*[)\].:\-–]\s*|^\s*[(\[]?[أ-ي]\s*[)\].\-–]\s+")
ORDWORD = re.compile(r"^\s*(أولا|اولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)[ًاَ]*\s*[:：\-–.)ـ]?\s*\S")
LEADIN = re.compile(r"(الآتي|التالي|يلي|كالآتي|كالتالي|الآتية|التالية|الاتية|الاتي|ما\s+يأتي|كما\s+يلي|النحو)\s*[:：]?\s*$")
SUBNUM = re.compile(r"^\s*[(\[]?[0-9٠-٩]{1,2}[.\-–][0-9٠-٩]{1,2}|^\s*[(\[]?[أ-ي]\s*[)\-–]\s|^\s*[-–•]\s")
HONOR = re.compile(r"^\s*(أ\s*\.\s*د\s*\.?|ا\s*\.\s*د\s*\.?|أ\s*\.\s*م\s*\.\s*د\s*\.?|م\s*\.\s*د\s*\.?|د\s*\.|أ\s*\.|"
                   r"الأستاذ(ة)?\s+الدكتور(ة)?|الأستاذ(ة)?|الدكتور(ة)?|prof\.?(essor)?|dr\.?|mr\.?|mrs\.?|ms\.?)\s*", re.I)
# exp 70 (journal 0165): a body that opens with no abstract, right under the byline («مقدمة», «أولاً: الإطار العام»)
BODY_HEAD = re.compile(r"^\s*((أولا|اولا)[ًاَ]*\s*[:：\-–.)]?\s*)?(ال)?(مقدمة|تمهيد|مدخل)(\s|[:：.]|$)|"
                       r"^\s*(أولا|اولا)[ًاَ]*\s*[:：\-–]|^\s*introduction\b", re.I)
AFF_WORDS = re.compile(r"جامع|كلي|قسم|معهد|وزار|مركز|أكاديمي|اكاديمي|مدرس|أستاذ|استاذ|باحث|مدير|خبير|"
                       r"universit|college|faculty|department|institute|ministry|centre|center|professor|lecturer", re.I)
LATIN_FRONT_NAME = re.compile(r"^[A-Z][\w'\-.]+(\s+[A-Z][\w'\-.]*){0,4}$")


# ------------------------------------------------------------------------------------------------ text helpers

def ws(s: str) -> str:
    return " ".join((s or "").split())


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "")
    s = re.sub(r"[ً-ٰٟـ]", "", s)
    s = re.sub("[إأآٱ]", "ا", s).replace("ى", "ي").replace("ة", "ه").replace("ؤ", "و").replace("ئ", "ي")
    return s.translate(DIG).casefold()


def toks(s: str) -> list[str]:
    """Folded words; a joined «و» (and) split off, so «والانفعالية» and «و الانفعالية» are the same words."""
    out = []
    for t in re.findall(r"\w+", fold(s)):
        if len(t) >= 4 and t.startswith("و"):
            t = t[1:]
        if len(t) > 1 and t != "و":
            out.append(t)
    return out


def same_words(a: str, b: str) -> bool:
    return "".join(toks(a)) == "".join(toks(b))


HONOR_SPLIT = re.compile(r"(?:(?<=\s)|^)(?=(?:أ\s*\.\s*د\s*\.|ا\s*\.\s*د\s*\.|أ\s*\.\s*م\s*\.\s*د\s*\.|د\s*\.|م\s*\.|أ\s*\.|"
                         r"الأستاذ|الدكتور|Prof\.|Dr\.)\s*)")


# exp 74 (journal 1001): names printed with a note marker and joined by «، و» («سمية محمد الشديفات1، وعبير محمد
# الشديفات2», «ماجد محمد الزيودي 1 ونجوى علي محمد الشريف 2»): one column per name, split after the marker
MARK_SPLIT = re.compile(r"(?<=[^\s0-9٠-٩])\s*([0-9٠-٩]{1,2}|\*{1,3})(?:\s*[،,]\s*|\s+)(?=[^\s0-9٠-٩،,.])")
MARK_END = re.compile(r"\s*([0-9٠-٩]{1,2}|\*{1,3})\s*$")
DATES_IN_AFF = re.compile(r"[،,]?\s*(ا?سُ?تلم|قُ?بل|received|accepted)\s*(بتاريخ|on)?\s*[:：]?\s*[\d٠-٩/\-.]+", re.I)
NOTE_MARK = re.compile(r"\s*\(\s*\*+\s*\)|\s*\(\s*\)|\*+|\s+\)$")      # «(*)», a «()» or «)» left by a note call
MARK_START = re.compile(r"^\s*([0-9٠-٩]{1,2}|\*{1,3})\s*[.\-–)]?\s*(?=\S)")


def columns(t: str) -> list[str]:
    cols = [c.strip() for c in re.split(r"\t+|\s{3,}", t) if c.strip()]
    if len(cols) == 1 and len(HONOR_SPLIT.findall(t)) >= 2:
        cols = [c.strip() for c in HONOR_SPLIT.split(t) if c and c.strip()]
    cols = [NOTE_MARK.sub("", c).strip() for c in cols]     # exp 74 (0840): «name (*)، …»
    cols = [c[:-1].strip() if c.endswith(")") and "(" not in c else c for c in cols]   # exp 74 (0097): «…الفيومي)»
    split_em = []
    for c in cols:                      # exp 74 (0840): two «name، body، e-mail» groups on one line
        ems = list(J.EMAIL.finditer(c))
        if len(ems) >= 2:
            pos = 0
            for m in ems:
                split_em.append(c[pos:m.end()].strip(" ،,"))
                pos = m.end()
            if c[pos:].strip(" ،,"):
                split_em.append(c[pos:].strip(" ،,"))
        else:
            split_em.append(c)
    cols = [c for c in split_em if c]
    out = []
    for c in cols:                      # exp 74: «name1، وname2»
        parts, pos = [], 0
        for m in (MARK_SPLIT.finditer(c) if not AFF_WORDS.search(c) else ()):   # names only, not «جامعة وهران 2 (…)»
            parts.append(c[pos:m.end(1)].strip())
            pos = m.end()
        tail = c[pos:].strip()
        if parts and tail:
            out += parts + [tail]
        else:
            out.append(c)
    return out


def is_latin(s: str) -> bool:
    return J.is_latin(s or "")


def strip_end(s: str) -> str:
    return re.sub(r"[\s:：.\-–«»)(]+$", "", re.sub(r"^[\s\d٠-٩.\-–)(«»]+", "", ws(s)))


def ptext(b) -> str:
    if b["kind"] == "p":
        return ws(b["text"].replace("\t", " "))
    return " ".join(ptext(p) for row in b["rows"] for c in row for p in c["paras"])


# ------------------------------------------------------------------------------------------------ inline content

class Inline:
    """Runs -> JATS mixed content inside an element (italic / sup / sub kept; bold kept only where asked)."""

    def __init__(self, art):
        self.art = art

    def fill(self, el, runs, keep_bold=False, strip_label=None):
        segs = []
        for r in runs:
            if "fn" in r:
                segs.append(("fn", r))
            elif "t" in r:
                t = r["t"].replace("\t", " ").replace("\n", " ")
                if t:
                    segs.append(("t", r, t))
        # whitespace: collapse, trim both ends
        out = []
        for s in segs:
            if s[0] == "t":
                out.append([s[1], s[2]])
            else:
                out.append([s[1], None])
        txt = "".join(x[1] or "" for x in out)
        lead = len(txt) - len(txt.lstrip())
        trail = len(txt) - len(txt.rstrip())
        # cut leading / trailing whitespace from the segments
        k = lead
        for x in out:
            if x[1] is None or k <= 0:
                continue
            c = min(k, len(x[1]))
            x[1] = x[1][c:]
            k -= c
        k = trail
        for x in reversed(out):
            if x[1] is None or k <= 0:
                continue
            c = min(k, len(x[1]))
            x[1] = x[1][:len(x[1]) - c]
            k -= c
        prev_space = False
        for r, t in out:
            if t is None:
                self.art.fn_call(el, r)
                prev_space = False
                continue
            t = re.sub(r"\s+", " ", t)
            if prev_space and t.startswith(" "):
                t = t[1:]
            if not t:
                continue
            prev_space = t.endswith(" ")
            tag = None
            if r.get("sup"):
                tag = "sup"
            elif r.get("sub"):
                tag = "sub"
            elif r.get("i") and t.strip():
                tag = "italic"
            elif keep_bold and r.get("b") and t.strip():
                tag = "bold"
            if tag:
                last = el[-1] if len(el) else None
                if last is not None and last.tag == tag and not (last.tail or ""):
                    last.text = (last.text or "") + t
                else:
                    E(el, tag, t)
            else:
                _append(el, t)
        return el


# ------------------------------------------------------------------------------------------------ references

YEAR_P = re.compile(r"[(\"“”]\s*((?:1[6-9]|20)[0-9]{2}\s*[a-zأ-ي]?|[١٢][٠-٩]{3}\s*[أ-ي]?|1[34][0-9]{2}\s*(?:هـ|ه)?|n\.\s*d\.?|د\s*\.\s*ت\.?|"
                    r"بدون\s+تاريخ|in\s+press|قيد\s+النشر|تحت\s+الطبع)\s*[),،\"“”]")
JOURNAL_TAIL = re.compile(
    r"[,،.]\s*(?:(?:vol\.?|مج(?:لد)?\.?|المجلد)\s*)?([0-9٠-٩]{1,4})\s*(?:\(\s*([0-9٠-٩][0-9٠-٩\-–/ ،,]*)\s*\))?"
    r"\s*(?:[,،]\s*(?:(?:no\.?|ع(?:دد)?\.?|العدد)\s*([0-9٠-٩]{1,4})\s*[,،])?\s*(?:pp?\.?|ص\s*ص?\.?|ص\.?ص\.?)?\s*"
    r"([0-9٠-٩]{1,5}\s*[-–—]\s*[0-9٠-٩]{1,5}|[0-9٠-٩]{1,5}))?", re.I)
PLACE_PUB = re.compile(r"(?:^|[.،,]\s*)([^.:،,()]{2,40}?)\s*:\s*([^.:]{2,120}?)\s*\.?\s*$")
PLACES = re.compile(r"^(بيروت|القاهرة|عمان|عمّان|الكويت|الرياض|جدة|مكة|المدينة|دمشق|حلب|بغداد|تونس|الجزائر|الرباط|"
                    r"الدار البيضاء|فاس|الدوحة|المنامة|أبوظبي|ابوظبي|دبي|الشارقة|العين|مسقط|صنعاء|الخرطوم|طرابلس|الإسكندرية|"
                    r"الاسكندرية|المنصورة|أسيوط|اسيوط|غزة|القدس|نابلس|إربد|اربد|الزرقاء|لبنان|مصر|الأردن|الاردن|سوريا|السعودية|"
                    r"Paris|London|New York|Boston|Oxford|Cambridge|Chicago|Washington|Toronto|Baltimore|Beirut|Cairo|"
                    r"Amman|Kuwait|Riyadh|Thousand Oaks|San Francisco|Mahwah|Hillsdale|Englewood Cliffs|Upper Saddle River|"
                    r"Philadelphia|Berlin|Geneva|Genève|Montréal|Montreal|Lyon|Bruxelles|Sydney|Melbourne)\b", re.I)
PUBWORDS = re.compile(r"(دار|مكتبة|مؤسسة|منشورات|المجلس|مطبعة|مطابع|المكتب|الدار|الهيئة|المنظمة|وزارة|عالم الكتب|"
                      r"\bPress\b|Publish|Publications|Books|Editions?|éd\b|PUF|Hachette|Routledge|Wiley|Sage|Pearson|"
                      r"Erlbaum|Guilford|McGraw|Prentice|Allyn|Harper|Springer|Elsevier|Macmillan|Norton|Penguin)", re.I)
THESIS = re.compile(r"رسالة|أطروحة|اطروحة|ماجستير|دكتوراه|dissertation|thesis", re.I)
LATIN_AUTH = re.compile(r"([A-Z][A-Za-z'’\-]+(?:\s+(?:[A-Z][a-z][A-Za-z'’\-]+|de|van|von|al|el))*)\s*,\s*"
                        r"((?:[A-Z]\s*\.?\s*-?\s*)+(?:\s*[A-Z][a-z]+\.?)?)(?=\s*(?:[,&]|and\b|$))")


def parse_ref(t: str, italic: str | None = None) -> dict:
    """A work's parts from one printed reference (APA-like), every value a substring of t; {} when nothing fits."""
    s = re.sub(r"^\s*[(\[]?[0-9٠-٩]{1,3}\s*[)\].\-–]\s*", "", t)
    w = {"lang": "en" if is_latin(s) else "ar"}
    m = YEAR_P.search(s)
    if m and m.start() < 300:
        auth = s[:m.start()].strip(" .،,؛;")
        w["year"] = m.group(1).strip()
        rest = s[m.end():].lstrip(" .،,:")
    else:
        ys = list(re.finditer(r"(?<![0-9٠-٩])((?:1[6-9]|20)[0-9]{2}|[١٢][٠-٩]{3})(?![0-9٠-٩])", s))
        if ys:
            w["year"] = ys[-1].group(1)
        # «Surname، Given: Title» or «Surname, Given. Title»
        m2 = re.match(r"^([^:،,.()]{2,40}[،,][^:،,.()]{2,40})\s*[:.]\s*", s)
        if not m2:
            return w if "year" in w else {}
        auth = m2.group(1)
        rest = s[m2.end():]
    # authors
    au = []
    if is_latin(auth):
        for a in LATIN_AUTH.finditer(auth):
            au.append({"surname": a.group(1).strip(), "given": a.group(2).strip(" ,")})
        if not au and auth:
            au.append({"surname": auth})
    elif auth:
        for part in re.split(r"\s*[؛;]\s*|\s*&\s*|\s+و(?=\s*[^\s،]{2,}\s*[،,])", auth):
            part = part.strip(" .،,")
            if au and part.startswith("وال"):
                part = part[1:]
            if not part:
                continue
            sg = re.split(r"\s*[،,]\s*", part, maxsplit=1)
            if len(sg) == 2 and sg[0] and sg[1]:
                au.append({"surname": sg[0], "given": sg[1]})
            else:
                au.append({"surname": part})
    if au:
        w["authors"] = au
    # title: up to the first full stop / question mark followed by a space
    mt = re.search(r"(?<=[^\s.])[.?؟]\s+(?=\S)", rest)
    if mt and mt.start() > 3:
        title = rest[:mt.start() + (1 if rest[mt.start()] in "?؟" else 0)].strip()
        rem = rest[mt.end():]
    else:
        title, rem = rest.strip(" ."), ""
    if italic and italic.strip(" .,") and italic.strip(" .,") in title and is_latin(t):
        pass
    rem_s = rem.strip()
    if not rem_s and re.search(r"[،,]", title):
        # «title، place، publisher» with commas only: the first segment that is a place or a publisher ends it
        segs = re.split(r"\s*[،,]\s*", title)
        cut = next((k for k, g in enumerate(segs) if k and (PLACES.search(g) or PUBWORDS.search(g) or
                                                              re.match(r"(مجلة|حولية|دورية|journal|revue)", g, re.I))), None)
        if cut:
            head = ", " if "," in title and "،" not in title else "، "
            title_c = title[:title.find(segs[cut], len(head.join(segs[:cut])) - 1)].rstrip(" ،,")
            rem_s = title[len(title_c):].lstrip(" ،,")
            title = title_c
    w["title"] = title
    if THESIS.search(rem_s or title):
        w["type"] = "thesis"
        uni = re.search(r"(جامعة\s[^.،,]{2,60}|[A-Z][\w ]{2,60}University[\w ]{0,30}|University of [\w ]{2,40})", rem_s)
        if uni:
            w["publisher"] = uni.group(1).strip()
        return w
    mj = JOURNAL_TAIL.search(rem_s) if rem_s else None
    if mj and mj.start() > 1 and (mj.group(4) or mj.group(2)):
        w["type"] = "journal"
        w["source"] = rem_s[:mj.start()].strip(" .،,")
        if re.match(r"(مجلة|حولية|دورية)", w["source"]) and "،" in w["source"]:
            w["source"] = w["source"].split("،")[0].strip()
        w["volume"] = mj.group(1)
        if mj.group(2):
            w["issue"] = mj.group(2).strip()
        elif mj.group(3):
            w["issue"] = mj.group(3)
        if mj.group(4):
            w["pages"] = mj.group(4).strip()
        return w
    mp = PLACE_PUB.search(rem_s) if rem_s else None
    if mp:
        w["type"] = "book"
        w["place"], w["publisher"] = mp.group(1).strip(), mp.group(2).strip(" .")
        return w
    mjj = re.match(r"((?:مجلة|حولية|دورية|journal|revue)[^،,.]{2,80})", rem_s, re.I) if rem_s else None
    if mjj:
        w["type"] = "journal"
        w["source"] = mjj.group(1).strip()
        nums = re.findall(r"(?:(مج|المجلد|vol\.?|v)\s*\.?\s*([0-9٠-٩]{1,4}))|(?:(ع|العدد|no\.?|n)\s*\.?\s*([0-9٠-٩]{1,4}))|"
                          r"(?:(ص\s*ص?|pp?)\s*\.?\s*([0-9٠-٩]{1,5}\s*[-–]\s*[0-9٠-٩]{1,5}))", rem_s, re.I)
        for a, b_, c, d, e, f in nums:
            if b_ and "volume" not in w:
                w["volume"] = b_
            if d and "issue" not in w:
                w["issue"] = d
            if f and "pages" not in w:
                w["pages"] = f
        return w
    if rem_s and (PLACES.search(rem_s) or PUBWORDS.search(rem_s)) and not re.search(r"https?://|www\.", rem_s):
        w["type"] = "book"
        for g in re.split(r"\s*[،,]\s*", rem_s.strip(" .")):
            if not g:
                continue
            if "place" not in w and PLACES.search(g) and len(g.split()) <= 3:
                w["place"] = g.strip(" .")
            elif "publisher" not in w and PUBWORDS.search(g):
                w["publisher"] = g.strip(" .")
            elif re.fullmatch(r"(ط|الطبعة|ed\.?|edition)\s*\S*|\S+\s+(ed\.?|edition)", g, re.I):
                w["edition"] = g.strip(" .")
        return w
    if re.search(r"https?://|www\.", t):
        w["type"] = "web"
        u = re.search(r"(https?://\S+|www\.\S+)", t)
        if u:
            w["url"] = u.group(1).rstrip(".,)")
        return w
    w["type"] = "book" if rem_s else "other"
    if rem_s:
        pub = rem_s.strip(" .")
        if len(pub) < 120:
            w["publisher"] = pub
    return w


# ------------------------------------------------------------------------------------------------ the article

class Article:
    def __init__(self, stem: str, docx: Path, rec: dict | None, cat_desc: str):
        self.stem, self.rec, self.cat_desc = stem, rec or {}, cat_desc
        self.doc = D.read_docx(docx)
        self.st = Counter()
        self.changes = []
        self.fn_order = {}             # Word footnote id -> (jats id, label)
        self.ids = Counter()
        self.lang = CAT.language(self.rec) or "ar"
        self.lang_cat = self.lang
        long_ = [b for b in self.doc["blocks"] if b.get("kind") == "p" and len(ptext(b).split()) > 25][:60]
        if self.lang != "en" and len(long_) >= 5 and sum(is_latin(ptext(b)) for b in long_) >= 0.7 * len(long_):
            self.lang = "en"           # exp 74 (1001-010-001-008): an English text under an Arabic catalogue record
            self.st["lang_en_from_text"] += 1
        self.inline = Inline(self)
        self.blockmap = []             # (jats id, text) in reading order, for the legacy PDF map
        self.used_fn = set()

    # -------------------------------------------------------------- ids
    def nid(self, p):
        self.ids[p] += 1
        return f"{p}{self.ids[p]}"

    # -------------------------------------------------------------- footnote calls
    def fn_call(self, el, r):
        wid = r["fn"]
        if wid not in self.doc["footnotes"]:
            self.st["fn_calls_without_note"] += 1
            return
        if wid not in self.fn_order:
            n = len(self.fn_order) + 1
            self.fn_order[wid] = (f"fn{n}", r.get("mark") or str(n))
        fid, lab = self.fn_order[wid]
        E(el, "xref", lab, ref_type="fn", rid=fid)
        self.used_fn.add(wid)
        self.st["fn_calls_linked"] += 1

    # -------------------------------------------------------------- block tests
    def heading_kind(self, b, i, blocks) -> str | None:
        """'style' | 'font' | 'bold' | 'colon' | 'centre' | None: why this paragraph is a heading."""
        if b["kind"] != "p" or b.get("in_table"):
            return None
        t = ptext(b)
        if not t or CAP_T.match(t) or CAP_F.match(t) or t.startswith("*"):
            return None
        nw = len(t.split())
        if b.get("outline") is not None and nw <= 25:
            return "style"
        if LEADIN.search(t) or (t.startswith("و") and nw > 6 and not ORDWORD.match(t)):
            return None
        if len(t) > 160 or nw > 18:
            return None
        if re.search(r"[.。]$", t) and not re.search(r"\.\.\.$", t):
            return None
        if b["hfont"] >= 0.6:
            return "font"
        if b["bold"] >= 0.9 and not t.endswith(("،", ",")):
            return "bold"
        nxt0 = blocks[i + 1] if i + 1 < len(blocks) else None
        if re.search(r"[:：]$", t) and nw <= 5 and ":" not in t[:-1] and \
                not re.search(r"(الآتي|التالي|يلي|كالآتي|كالتالي|الآتية|التالية|الاتية|الاتي)\s*[:：]$", t) and \
                not (nxt0 is not None and nxt0["kind"] == "p" and nxt0.get("num") and nxt0.get("label")):
            return "colon"
        nxt = next((x for x in blocks[i + 1:i + 2]), None)
        if b.get("jc") == "center" and nw <= 10 and nxt is not None and nxt["kind"] == "p" and \
                len(ptext(nxt).split()) > 25:
            return "centre"
        return None

    NUMLAB = re.compile(r"^\s*[(\[]?(?:([0-9٠-٩]{1,2}(?:\s*[.\-–_]\s*[0-9٠-٩]{1,2})*)|[أ-ي]|[a-zA-Z])\s*[)\]_\-–.:]\s*\S|"
                        r"^\s*(أولا|اولا|ثانيا|ثالثا|رابعا|خامسا|سادسا|سابعا|ثامنا|تاسعا|عاشرا)[ًاَ]*\s*[:：\-–.)]?\s*\S")

    def level(self, b, commit=False) -> int:
        """Level 1 for a centred or larger heading, 2 for another plain one; a numbered heading (Word's list
        number, «1-», «أ-», «أولاً») sits one level under the last plain heading, a «1-2» one more."""
        if b.get("outline") is not None:
            return min(3, b["outline"] + 1)
        t = ptext(b)
        if getattr(self, "has_ordinal", False) and ORDWORD.match(t):
            if commit:
                self._last_plain = 1
            return 1
        m = self.NUMLAB.match(t)
        if (b.get("num") and b.get("label")) or m:
            base = getattr(self, "_last_plain", 1)
            deeper = 1 if (m and m.group(1) and re.search(r"[.\-–_]\s*[0-9٠-٩]", m.group(1))) else 0
            return min(3, base + 1 + deeper)
        lv = 1 if (b.get("jc") == "center" or (b.get("size") or 0) >= self.doc["body_size"] + 4) else 2
        if getattr(self, "has_ordinal", False):
            lv = 2
        if commit:
            self._last_plain = lv
        return lv

    # -------------------------------------------------------------- build
    def build(self) -> etree._Element:
        rec = self.rec
        art = etree.Element("article", nsmap={"xlink": XLINK, "mml": MML},
                            attrib={"article-type": "research-article", "dtd-version": "1.4", XML_LANG: self.lang})
        self.art_el = art
        front = E(art, "front")
        jm = E(front, "journal-meta")
        E(jm, "journal-id", self.stem.split("-")[0], journal_id_type="mandumah")
        CAT.jats_journal_meta(E, jm, rec)
        if jm.find("journal-title-group") is None:
            jtg = etree.Element("journal-title-group")
            jm.insert(1, jtg)
            E(jtg, "journal-title", self.printed_journal() or "")
        am = E(front, "article-meta")
        self.am = am
        E(am, "article-id", self.stem, pub_id_type="other", assigning_authority="Mandumah")
        CAT.jats_article_ids(E, am, rec)
        ac = E(am, "article-categories")
        CAT.jats_categories(E, ac, rec)
        self.tg = E(am, "title-group")
        E(self.tg, "article-title", rec.get("title") or "")
        if rec.get("subtitle"):
            E(self.tg, "subtitle", rec["subtitle"], specific_use="catalogue")
        blocks = self.flatten_front_tables(self.doc["blocks"])
        self.blocks = blocks
        body_start = self.front(blocks, ac)
        if not len(ac):
            am.remove(ac)
        # people, dates, volume, pages (catalogue)
        CAT.jats_dates(E, am, rec)
        j = rec.get("journal", {})
        vol, iss = CAT.num(j.get("volume", "")), CAT.num(j.get("issue", ""))
        if vol:
            E(am, "volume", vol, content_type="catalogue")
        if iss:
            E(am, "issue", iss if iss != "999" else "special", content_type="catalogue")
        rng = CAT.page_range(rec.get("pages", ""))
        if rng:
            E(am, "fpage", str(rng[0]), content_type="catalogue")
            E(am, "lpage", str(rng[1]), content_type="catalogue")
        self.rng = rng
        self.write_front_extras()
        if rng:
            cnt = E(am, "counts")
            E(cnt, "page-count", count=rng[1] - rng[0] + 1)
        body = E(art, "body")
        back = E(art, "back")
        self.back = back
        self.has_ordinal = sum(1 for k, b in enumerate(blocks[body_start:]) if b["kind"] == "p" and
                               ORDWORD.match(ptext(b)) and self.heading_kind(b, body_start + k, blocks)) >= 2
        self.body_blocks(blocks[body_start:], body, back)
        self.footnotes(back)
        self.history()
        self.custom(am)
        for el in (back,):
            if not len(el):
                art.remove(el)
        if not len(body):
            E(body, "p")
        self.order_meta(am)
        return art

    # -------------------------------------------------------------- front-matter tables -> lines
    def flatten_front_tables(self, blocks):
        """A table among the first lines (bylines set in a table): its rows as lines, cells as columns."""
        out = []
        seen_body = 0
        for b in blocks:
            if b["kind"] == "table" and seen_body < 2 and len(out) < 25:
                for row in b["rows"]:
                    cells = [" ".join(ptext(p) for p in c["paras"]) for c in row]
                    if not any(cells):
                        continue
                    # one line per paragraph row inside the cells, columns aligned
                    depth = max(len(c["paras"]) for c in row)
                    for k in range(depth):
                        parts = [ptext(c["paras"][k]) if k < len(c["paras"]) else "" for c in row]
                        if not any(parts):
                            continue
                        line = "\t\t\t".join(parts)
                        src = next(c["paras"][k] for c in row if k < len(c["paras"]))
                        nb = dict(src, text=line, runs=[dict(t=line, b=src["bold"] > 0.5, i=False, sup=False,
                                                             sub=False)], in_table=False, from_table=True)
                        out.append(nb)
                self.st["front_tables_flattened"] += 1
                continue
            if b["kind"] == "p" and len(ptext(b).split()) > 30:
                seen_body += 1
            out.append(b)
        return out

    # -------------------------------------------------------------- the front
    def front(self, blocks, ac) -> int:
        rec = self.rec
        title_t = set(toks(rec.get("title", "") + " " + rec.get("subtitle", "")))
        n = len(blocks)
        used = set()
        # title: the run of early paragraphs whose words are the catalogue title's
        best = None
        for i in range(min(14, n)):
            b = blocks[i]
            if b["kind"] != "p":
                continue
            w = toks(ptext(b))
            if not w or not title_t:
                continue
            share = sum(1 for x in w if x in title_t) / len(w)
            if share >= 0.7:
                k = i
                got = list(w)
                while k + 1 < n and blocks[k + 1]["kind"] == "p":
                    w2 = toks(ptext(blocks[k + 1]))
                    if w2 and sum(1 for x in w2 if x in title_t) / len(w2) >= 0.7 and \
                            len(set(got) | set(w2)) <= len(title_t) + 3:
                        got += w2
                        k += 1
                    else:
                        break
                cover = len(set(got) & title_t) / len(title_t)
                if best is None or cover > best[2]:
                    best = (i, k, cover)
                if cover > 0.9:
                    break
        self.title_span = None
        if best and best[2] >= 0.5:
            i0, i1, cover = best
            printed = ws(" ".join(ptext(blocks[x]) for x in range(i0, i1 + 1)))
            printed = re.sub(r"\(\s*\*+\s*\)|\*+$", "", printed).strip()
            self.title_span = (i0, i1)
            used.update(range(i0, i1 + 1))
            self.st["front_title_found"] += 1
            self.st[f"front_title_cover_{'full' if cover >= 0.95 else 'part'}"] += 1
            cat_full = ws(rec.get("title", "") + (" " + rec["subtitle"] if rec.get("subtitle") else ""))
            at = self.tg.find("article-title")
            if J.norm(printed) in (J.norm(cat_full), J.norm(rec.get("title", ""))):
                self.st["front_title_same"] += 1
            elif same_words(printed, cat_full) or same_words(printed, rec.get("title", "")):
                # the same words, spelt (hamza, spacing, punctuation) as printed: the printed form is the title
                at.text = printed
                if self.tg.find("subtitle") is not None and same_words(printed, cat_full):
                    self.tg.remove(self.tg.find("subtitle"))
                E(self.tg, "alt-title", cat_full, alt_title_type="catalogue")
                self.st["front_title_same_words_printed_spelling"] += 1
            else:
                E(self.tg, "alt-title", printed, alt_title_type="printed")
                self.log("title", printed, cat_full, "catalogue", "the catalogue's form; the Word file's first "
                         "lines print other words (a misprint, a cut, or a catalogue rewording)")
                self.st["front_title_differs"] += 1
            for x in range(i0, i1 + 1):
                for r in blocks[x]["runs"]:
                    if "fn" in r:                  # a note on the title (author note, funding)
                        self.title_note = r
            # what stands above the title: the rubric (البحوث والدراسات)
            for x in range(0, i0):
                if blocks[x]["kind"] == "p" and len(ptext(blocks[x]).split()) <= 6:
                    sg = E(ac, "subj-group", subj_group_type="heading", specific_use="printed")
                    E(sg, "subject", ptext(blocks[x]))
                    used.add(x)
                    self.st["front_rubric"] += 1
        else:
            self.st["front_title_not_found"] += 1
        start = (self.title_span[1] + 1) if self.title_span else 0
        # the abstract heading(s), keywords, the Latin block; the body starts at the first other heading after them
        self.abstracts = []                # (lang, title text | None, [blocks])
        self.kwds = []                     # (lang, text)
        self.trans_title = []              # printed Latin title lines
        self.front_lines = []              # printed lines with no slot (kept as front-matter blocks)
        self.bylines = []                  # (index, columns)
        i = start
        body_start = None
        seen_abs = False
        while i < n:
            b = blocks[i]
            if b["kind"] != "p":
                if seen_abs or i - start > 12:
                    body_start = i
                    break
                i += 1
                continue
            t = ptext(b)
            h = strip_end(t)
            m_abs = J.ABSTRACT_HEAD.match(h) or re.match(r"^(ال)?(ملخص|مستخلص)(\s+(ال)?(بحث|دراسة))?\s*[:：]|"
                                                         r"^abstract\s*[:：.\-–]", t, re.I)
            if m_abs:
                lang = "en" if is_latin(h) or re.match(r"^abstract", t, re.I) else "ar"
                head = t
                paras = []
                rest = t[m_abs.end():].strip(" :：.-–") if len(t.split()) > 4 else ""
                if rest:
                    head = t[:m_abs.end()].strip()
                    paras.append(dict(b, runs=self.cut_runs(b["runs"], m_abs.end()), text=rest))
                used.add(i)
                k = i + 1
                while k < n and blocks[k]["kind"] == "p":
                    tk = ptext(blocks[k])
                    if J.KW_LABEL.match(tk) or self.heading_kind(blocks[k], k, blocks) or \
                            (lang == "ar" and is_latin(tk) and len(tk.split()) < 40) or \
                            (lang == "en" and not is_latin(tk)):
                        break
                    paras.append(blocks[k])
                    used.add(k)
                    k += 1
                self.abstracts.append((lang, head, paras))
                self.st[f"front_abstract_{lang}"] += 1
                seen_abs = True
                i = k
                continue
            if J.KW_LABEL.match(t):
                self.kwds.append(("en" if is_latin(t) else "ar", t))
                used.add(i)
                seen_abs = True
                i += 1
                continue
            hk = self.heading_kind(b, i, blocks)
            if not seen_abs and BODY_HEAD.match(h) and len(t.split()) <= 12:
                body_start = i                 # exp 70: the body's first heading, no abstract above it
                break
            if seen_abs and not is_latin(t) and (hk or len(t.split()) > 25):
                body_start = i
                break
            if seen_abs and self.lang == "en" and is_latin(t) and (hk or len(t.split()) > 25):
                body_start = i                 # exp 74 (journal 1001): an English article's body after its abstract
                break
            if not seen_abs and len(t.split()) > 40 and not is_latin(t):
                body_start = i                 # no abstract: the running text starts here
                break
            if seen_abs and is_latin(t) and len(t.split()) > 40:
                # an English abstract with no heading
                self.abstracts.append(("en", None, [b]))
                used.add(i)
                i += 1
                continue
            if is_latin(t) and seen_abs and not self.trans_title and (b["bold"] > 0.5 or b.get("jc") == "center"):
                self.trans_title.append(t)
                used.add(i)
                k = i + 1
                while k < n and blocks[k]["kind"] == "p" and is_latin(ptext(blocks[k])) and \
                        self.same_style(b, blocks[k]) and not self.looks_byline_latin(blocks[k]["text"]):
                    self.trans_title.append(ptext(blocks[k]))
                    used.add(k)
                    k += 1
                i = k
                continue
            self.front_lines.append((i, b["text"]))
            used.add(i)
            i += 1
        if body_start is None:
            body_start = i
        # notes called from the title, the bylines or the affiliations: author notes
        abs_ids = {id(b) for _, _, ps in self.abstracts for b in ps}
        self.front_notes = []
        self.front_note_block = {}         # exp 70: the front block each author note is called from
        for x in range(0, body_start):
            if blocks[x]["kind"] == "p" and id(blocks[x]) not in abs_ids:
                for r in blocks[x]["runs"]:
                    if "fn" in r:
                        self.front_notes.append(r)
                        self.front_note_block[id(r)] = x
        # English abstract / title at the end of the article
        self.tail_latin(blocks, body_start)
        self.people([(k, t) for k, t in self.front_lines if not is_latin(t)],
                    [(k, t) for k, t in self.front_lines if is_latin(t)])
        self.st["front_blocks"] += body_start
        return body_start

    def same_style(self, a, b):
        return (a.get("jc") == b.get("jc")) and abs(a["bold"] - b["bold"]) < 0.5 and len(ptext(b).split()) < 25

    @staticmethod
    def looks_byline_latin(t):
        cols = [c for c in re.split(r"\t+|\s{3,}", t) if c.strip()]
        w = t.split()
        name = 1 < len(w) <= 4 and all(x[:1].isupper() for x in w) and not any(
            x.lower().strip(",.:") in ("and", "of", "the", "in", "for", "a", "an", "on", "to", "study", "children",
                                       "child", "education", "strategy", "program") for x in w)
        return len(cols) >= 2 or name or bool(re.match(r"^(prof|dr|mr|mrs|ms)\b", t, re.I))

    def cut_runs(self, runs, k):
        """runs with the first k characters of their text removed."""
        out = []
        left = k
        for r in runs:
            if "t" in r and left > 0:
                if len(r["t"]) <= left:
                    left -= len(r["t"])
                    continue
                r = dict(r, t=r["t"][left:])
                left = 0
            out.append(r)
        return out

    def tail_latin(self, blocks, body_start):
        """An «Abstract» heading after the body started: the English abstract printed at the end (and the English
        title lines just above it). Marked so the body skips them."""
        self.tail_skip = set()
        for i in range(body_start, len(blocks)):
            b = blocks[i]
            if b["kind"] != "p":
                continue
            t = ptext(b)
            if not re.match(r"^\s*abstract\s*[:：.\-–]?\s*", t, re.I) or len(t.split()) > 200:
                continue
            m = re.match(r"^\s*abstract\s*[:：.\-–]?\s*", t, re.I)
            paras = []
            if len(t.split()) > 4:
                paras.append(dict(b, runs=self.cut_runs(b["runs"], m.end()), text=t[m.end():]))
            k = i + 1
            while k < len(blocks) and blocks[k]["kind"] == "p" and is_latin(ptext(blocks[k])) and \
                    not J.KW_LABEL.match(ptext(blocks[k])) and not self.heading_kind(blocks[k], k, blocks):
                paras.append(blocks[k])
                self.tail_skip.add(k)
                k += 1
            while k < len(blocks) and blocks[k]["kind"] == "p" and J.KW_LABEL.match(ptext(blocks[k])):
                self.kwds.append(("en", ptext(blocks[k])))
                self.tail_skip.add(k)
                k += 1
            if not paras:
                continue
            self.abstracts.append(("en", t[:m.end()].strip(), paras))
            self.tail_skip.add(i)
            self.st["tail_abstract_en"] += 1
            # Latin lines just above (title, names, affiliations)
            j = i - 1
            above = []
            while j >= body_start and blocks[j]["kind"] == "p" and is_latin(ptext(blocks[j])) and \
                    len(ptext(blocks[j]).split()) <= 30 and i - j <= 10:
                above.insert(0, j)
                j -= 1
            if above:
                if not self.trans_title:
                    self.trans_title.append(ptext(blocks[above[0]]))
                    above = above[1:]
                for x in above:
                    self.front_lines.append((x, blocks[x]["text"]))
                self.tail_skip.update(above)
                self.tail_skip.update(range(j + 1, i))
            break

    # -------------------------------------------------------------- people
    def people(self, ar_lines, la_lines):
        names = [p for p in self.rec.get("names", []) if p.get("name")]
        cg = None
        printed_of = {}            # catalogue index -> dict(printed, prefix, aff)
        unmatched_cols = []
        # bylines: a line whose columns hold catalogue names
        lines = ar_lines
        k = 0
        taken = set()
        while k < len(lines):
            idx, t = lines[k]
            cols = columns(t)
            hits = []
            inline_aff = {}
            k_c = 0
            while k_c < len(cols):                # exp 74 (0523): «وعهود ياسر الجدي وعذاري العلي»: two catalogue names
                c = cols[k_c]
                for m in re.finditer(r"\s+و(?=[؀-ۿ])", c):
                    a_, b_ = c[:m.start()].strip(), c[m.end():].strip()
                    ha = self.match_name(a_.lstrip("و").strip() or a_, names, taken)
                    hb = self.match_name(b_, names, taken | ({ha} if ha is not None else set()))
                    if ha is not None and hb is not None and ha != hb and len(a_.split()) >= 2 and len(b_.split()) >= 2:
                        cols[k_c:k_c + 1] = [a_, "و" + b_]
                        self.st["front_names_split_at_wa"] += 1
                        break
                k_c += 1
            for n_c, c in enumerate(cols):
                ci = self.match_name(c, names, taken)
                if ci is None and "،" in c:
                    # exp 74 (journal 0840): «وهيبة محمدي (*)، جامعة وهران 2 (الجزائر)، wahiba…@gmail.com»: the name,
                    # then its affiliation (and e-mail) on the same line after «،»
                    left, rest = c.split("،", 1)
                    left = NOTE_MARK.sub("", left).strip()
                    if rest.strip() and (AFF_WORDS.search(rest) or J.EMAIL.search(rest)):
                        ci = self.match_name(left, names, taken)
                        if ci is not None:
                            cols[n_c] = left
                            inline_aff[n_c] = rest.strip(" ،")
                hits.append(ci)
            if any(h is not None for h in hits):
                for n_c, (c, h) in enumerate(zip(cols, hits)):
                    if h is None:
                        unmatched_cols.append(c)
                        continue
                    if c.startswith("و") and n_c and \
                            self.match_name(c[1:].strip(), names, taken) == h and \
                            fold(c.split()[0]) not in {fold(w) for w in (names[h].get("name") or "").replace("،", " ").split()}:
                        c = c[1:].strip()       # exp 74: «… الشديفات1، وعبير …»: the «و» joining two names
                    taken.add(h)
                    pm = HONOR.match(c)
                    prefix = c[:pm.end()].strip() if pm and pm.end() else None
                    mk = MARK_END.search(c) if re.search(r"[؀-ۿA-Za-z]{2}", c) else None   # exp 74: «… السليمان 1»
                    printed_of[h] = dict(printed=c[:mk.start()].strip() if mk else c, prefix=prefix,
                                         aff=[inline_aff[n_c]] if n_c in inline_aff else [],
                                         marker=mk.group(1).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                                         if mk else None)
                # the lines below until the next byline: affiliations, by column
                j = k + 1
                while j < len(lines):
                    t2 = lines[j][1]
                    cols2 = columns(t2)
                    if any(self.match_name(c, names, taken) is not None or
                           ("،" in c and self.match_name(NOTE_MARK.sub("", c.split("،", 1)[0]).strip(), names, taken)
                            is not None) for c in cols2):
                        break                          # exp 74: the next «name، body، e-mail» line
                    if len(t2.split()) > 25 or BODY_HEAD.match(t2.strip()) or \
                            (len(t2.split()) > 6 and not AFF_WORDS.search(t2)) or \
                            (t2.strip().endswith((":", "：")) and not AFF_WORDS.search(t2)) or \
                            not re.search(r"[A-Za-z؀-ۿ]{2}", t2) or \
                            (t2.strip().endswith((".", "…")) and len(t2.split()) > 3 and not AFF_WORDS.search(t2)):
                        break                                  # exp 70: running text / a label / a mark is no affiliation
                    hh = [h for h in hits if h is not None]
                    ms = MARK_START.match(t2)
                    mkd = {printed_of[h].get("marker"): h for h in hh if printed_of[h].get("marker")}
                    if ms and mkd:              # exp 74: «1. أستاذ … جامعة طيبة» -> the name marked 1
                        mk = ms.group(1).translate(str.maketrans("٠١٢٣٤٥٦٧٨٩", "0123456789"))
                        if mk in mkd:
                            printed_of[mkd[mk]]["aff"].append(t2[ms.end():].strip())
                            self.st["front_aff_by_marker"] += 1
                        else:
                            for h in hh:
                                printed_of[h]["aff"].append(t2[ms.end():].strip())
                    elif len(cols2) == len(hits) and len(hits) > 1:
                        for c, h in zip(cols2, hits):
                            if h is not None:
                                printed_of[h]["aff"].append(c)
                    else:
                        for h in hh:
                            printed_of[h]["aff"].append(" ".join(cols2))
                    j += 1
                    self.st["front_aff_lines"] += 1
                self.bylines.append(idx)
                self.byline_hits = getattr(self, "byline_hits", {})
                self.byline_hits[idx] = [h for h in hits if h is not None]
                k = j
                continue
            k += 1
        used_lines = {idx for idx in self.bylines}
        for p in printed_of.values():
            pass
        # aff lines were consumed via bylines' following lines: mark them used
        consumed = set()
        for k2, (idx, t) in enumerate(lines):
            if idx in used_lines:
                j = k2 + 1
                while j < len(lines) and lines[j][0] not in used_lines:
                    consumed.add(lines[j][0])
                    j += 1
        if names or printed_of:
            cg = E(self.am, "contrib-group")
            self.cg = cg
            for n_, p in enumerate(names, 1):
                pr = printed_of.get(n_ - 1, {})
                affs_ = [DATES_IN_AFF.sub("", x).strip(" ،,") for x in pr.get("aff", [])]   # exp 74 (0523)
                a = dict(catalogue=p, printed=pr.get("printed"), prefix=pr.get("prefix"),
                         aff="، ".join(x for x in affs_ if x) or None)
                c = CAT.jats_contrib(E, cg, a, n_, f"contrib{n_}", _append)
                self.tag_aff(c)
                if pr.get("printed"):
                    self.st["front_names_matched"] += 1
                    nm = CAT.display_name(p["name"])
                    if J.norm(HONOR.sub("", pr["printed"])) != J.norm(nm):
                        self.log(f"author {n_}", pr["printed"], p["name"], "catalogue",
                                 "the catalogue's authority name; the printed form kept as string-name")
                else:
                    self.st["front_names_not_found_in_file"] += 1
                self.st["front_contribs"] += 1
                if p.get("auth"):
                    self.st["front_authority_ids"] += 1
        for c in unmatched_cols:
            self.st["front_printed_names_not_in_catalogue"] += 1
        # Latin bylines: kept as printed front-matter lines
        rest = [(i, t) for i, t in ar_lines if i not in used_lines and i not in consumed] + la_lines
        self.front_lines = sorted(rest)
        self.st["front_lines_kept_as_blocks"] += len(rest)

    def match_name(self, col, names, taken):
        c = toks(HONOR.sub("", col))
        if not c or len(c) > 7:
            return None
        best, bs = None, 0.0
        for k, p in enumerate(names):
            if k in taken:
                continue
            s, g = CAT.split_name(p["name"])
            nt = toks(f"{g} {s}")
            if not nt:
                continue
            # the printed form often drops the father's name: score by the printed tokens found in the catalogue
            hit = sum(1 for x in c if x in nt or any(len(x) > 3 and (x in y or y in x) for y in nt))
            sc = hit / len(c)
            sur = toks(s)
            if sur and not any(x in c or any(len(x) > 3 and (x in y or y in x) for y in c) for x in sur) and \
                    not (sc == 1.0 and len(c) >= 2):
                sc *= 0.5
            if sc > bs:
                best, bs = k, sc
        return best if bs >= 0.6 else None

    def tag_aff(self, c):
        aff = c.find("aff")
        if aff is None or len(aff):
            return
        s = aff.text or ""
        spans = J.Slots.no_overlap(J.Slots.guess_aff(None, s) + [(m.start(), m.end(), "email", None)
                                                                 for m in J.EMAIL.finditer(s)])
        if not spans:
            return
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
        last.tail = s[pos:]
        self.st["front_affs_tagged"] += 1

    # -------------------------------------------------------------- abstracts, keywords, translated title
    def write_front_extras(self):
        am = self.am
        rec = self.rec
        # translated title: printed first, the catalogue's beside it
        if self.trans_title:
            pt = ws(" ".join(self.trans_title))
            g = etree.Element("trans-title-group", {XML_LANG: "en", "specific-use": "printed"})
            E(g, "trans-title", pt)
            at = self.tg.find("alt-title")
            (at.addprevious(g) if at is not None else self.tg.append(g))
            if rec.get("title_en"):
                ct = ws(rec["title_en"] + (" " + rec["subtitle_en"] if rec.get("subtitle_en") else ""))
                if J.norm(ct) != J.norm(pt):
                    E(self.tg, "alt-title", ct, alt_title_type="catalogue-translation", xml_lang="en")
            self.st["front_trans_title_printed"] += 1
        elif rec.get("title_en"):
            CAT.jats_trans_title(E, self.tg, rec)
            g = self.tg.find("trans-title-group")
            g.set("specific-use", "catalogue")
            at = self.tg.find("alt-title")
            if at is not None:
                at.addprevious(g)
        got_lang = set()
        for k, (lang, head, paras) in enumerate(sorted(self.abstracts, key=lambda x: x[0] != self.lang)):
            first = lang == self.lang and "main" not in got_lang
            el = etree.Element("abstract" if first else "trans-abstract", {"abstract-type": "printed"})
            if not first:
                el.set(XML_LANG, lang)
            if head:
                E(el, "title", strip_end(head) if len(head) < 40 else head)
            for b in paras:
                p = E(el, "p", id=self.nid("w"))
                self.inline.fill(p, b["runs"])
                self.blockmap.append((p.get("id"), ptext(b)))
            J.put(am, el)
            got_lang.add("main" if first else lang)
            self.st["jats_abstract" if first else "jats_trans_abstract"] += 1
        if "main" not in got_lang:
            for code, text in self.rec.get("abstracts", []):
                if code in ("a", "e") and self.lang == "ar":
                    el = etree.Element("abstract", {"abstract-type": "catalogue", "specific-use": "catalogue"})
                    E(el, "p", text)
                    J.put(am, el)
                    self.st["jats_abstract_from_catalogue"] += 1
                    break
        for lang, t in self.kwds:
            kg = J.Slots.kwd_group(self.fake_slots(), t, lang, None)
            if kg is not None:
                J.put(am, kg)
                self.st["jats_kwd_groups_printed"] += 1
        if rec.get("keywords"):
            kg = etree.Element("kwd-group", {"kwd-group-type": "subject-terms", "specific-use": "catalogue",
                                             XML_LANG: "ar"})
            for k in dict.fromkeys(rec["keywords"]):
                E(kg, "kwd", k)
            J.put(am, kg)

    def fake_slots(self):
        class S:
            pass
        s = S()
        s.lang = self.lang
        s.st = Counter()
        return s

    # -------------------------------------------------------------- the body
    def body_blocks(self, blocks, body, back):
        base = len(self.blocks) - len(blocks)
        stack = [(0, body)]
        mode = "body"
        reflist = None
        refsub = None
        notes = None
        app_group = None
        i = 0
        list_el = None
        list_key = None
        pending_caption = None
        last_table = None

        def parent():
            return stack[-1][1]

        def close_list():
            nonlocal list_el, list_key
            list_el, list_key = None, None

        n = len(blocks)
        while i < n:
            gi = base + i
            b = blocks[i]
            if gi in self.tail_skip:
                i += 1
                continue
            if b["kind"] == "table":
                close_list()
                if mode in ("refs", "notes"):
                    # a table after the reference list, with no heading: an appendix
                    mode = "app"
                    if app_group is None:
                        app_group = etree.SubElement(back, "app-group")
                    sec = E(app_group, "app", id=self.nid("app"))
                    stack = [(0, sec)]
                    self.st["appendices_untitled_after_refs"] += 1
                cap = pending_caption
                pending_caption = None
                if cap is None:
                    # a caption under the table
                    nb = blocks[i + 1] if i + 1 < n else None
                    if nb is not None and nb["kind"] == "p" and CAP_T.match(ptext(nb)):
                        cap = [nb]
                        self.tail_skip.add(base + i + 1)
                last_table = self.table(parent(), b, cap)
                i += 1
                # notes under the table
                while i < n and blocks[i]["kind"] == "p" and TNOTE.match(ptext(blocks[i])) and \
                        len(ptext(blocks[i]).split()) <= 40:
                    foot = last_table.find("table-wrap-foot")
                    if foot is None:
                        foot = E(last_table, "table-wrap-foot")
                    p = E(foot, "p", id=self.nid("w"), content_type="table-note")
                    self.inline.fill(p, blocks[i]["runs"])
                    self.blockmap.append((p.get("id"), ptext(blocks[i])))
                    self.st["table_notes"] += 1
                    i += 1
                continue
            t = ptext(b)
            if not t and not b["images"]:
                i += 1
                continue
            # a table caption: held for the table that follows (up to two lines)
            if CAP_T.match(t) and mode != "refs":
                k = i + 1
                cap = [b]
                if k < n and blocks[k]["kind"] == "p" and blocks[k].get("jc") == b.get("jc") and \
                        len(ptext(blocks[k]).split()) <= 20 and not CAP_T.match(ptext(blocks[k])) and \
                        k + 1 < n and blocks[k + 1]["kind"] == "table":
                    cap.append(blocks[k])
                    k += 1
                if k < n and blocks[k]["kind"] == "table":
                    pending_caption = cap
                    i = k
                    continue
            if b["images"] and mode != "refs":
                close_list()
                self.figure(parent(), b, blocks, i)
                i += 1
                continue
            if CAP_F.match(t) and getattr(self, "_fig_caption_used", None) == base + i:
                i += 1
                continue
            hk = self.heading_kind(b, i, blocks)
            h = strip_end(ORDINAL.sub("", t)).strip(" ,،:：.")
            if hk or (mode == "refs" and len(t.split()) <= 5 and REF_HEAD.search(h)):
                close_list()
                low = h
                if NOTES_HEAD.match(low):
                    mode = "notes"
                    notes = etree.SubElement(back, "fn-group", {"content-type": "endnotes"})
                    E(notes, "title", t)
                    self.st["notes_section"] += 1
                    i += 1
                    continue
                if REF_HEAD.search(low) and len(low.split()) <= 6 and not J.APP_HEAD.match(low):
                    if mode != "refs":
                        mode = "refs"
                        reflist = etree.SubElement(back, "ref-list")
                        E(reflist, "title", t)
                        refsub = None
                        self.st["refs_heading"] += 1
                    else:
                        refsub = E(reflist, "ref-list")
                        E(refsub, "title", t)
                        self.st["refs_subheading"] += 1
                    i += 1
                    continue
                if mode == "refs" and (len(t.split()) <= 4 and not J.APP_HEAD.match(low) and
                                       not J.ACK_HEAD.match(low) and re.search(r"عربي|أجنبي|اجنبي|english|foreign|"
                                                                                r"arabic|انجليزي|إنجليزي", low, re.I)):
                    refsub = E(reflist, "ref-list")
                    E(refsub, "title", t)
                    self.st["refs_subheading"] += 1
                    i += 1
                    continue
                if J.APP_HEAD.match(low) or J.ACK_HEAD.match(low) or mode in ("refs", "notes", "app") or True:
                    kind = "app" if J.APP_HEAD.match(low) else ("ack" if J.ACK_HEAD.match(low) else None)
                    if kind == "app" or (mode == "app" and self.level(b) == 1):
                        mode = "app"
                        if app_group is None:
                            app_group = etree.SubElement(back, "app-group")
                        sec = E(app_group, "app", id=self.nid("app"))
                        E(sec, "title", t)
                        stack = [(0, sec)]
                        self.st["appendices"] += 1
                        i += 1
                        continue
                    if kind == "ack":
                        mode = "ack"
                        sec = etree.Element("ack", id=self.nid("ack"))
                        back.insert(0, sec)
                        E(sec, "title", t)
                        stack = [(0, sec)]
                        self.st["ack"] += 1
                        i += 1
                        continue
                    if mode in ("refs", "notes"):
                        # a real heading after the reference list: back to the body (or the appendix)
                        if hk in ("font", "style") or (hk == "bold" and self.level(b) == 1):
                            mode = "body"
                            stack = [(0, body)]
                        else:
                            hk = None
                if hk:
                    lv = self.level(b, commit=True)
                    while len(stack) > 1 and stack[-1][0] >= lv:
                        stack.pop()
                    sec = E(parent(), "sec", id=self.nid("s"), disp_level=str(lv))
                    if b.get("label"):
                        E(sec, "label", b["label"])
                    tt = E(sec, "title", id=self.nid("h"))
                    self.inline.fill(tt, b["runs"])
                    self.strip_colon(tt)
                    self.blockmap.append((tt.get("id"), t))
                    stack.append((lv, sec))
                    self.st["headings"] += 1
                    self.st[f"headings_by_{hk}"] += 1
                    self.st[f"headings_level_{lv}"] += 1
                    i += 1
                    continue
            if mode == "refs":
                self.add_ref(refsub if refsub is not None else reflist, b)
                i += 1
                continue
            if mode == "notes":
                m = re.match(r"^\s*[(\[]?\s*([0-9٠-٩]{1,3})\s*[)\]]?\s*[-–.:]?\s*", t)
                if m:
                    lab = m.group(1).translate(DIG)
                    fid = f"en{lab}"
                    while fid in self.ids:          # exp 70: numbering that restarts (two «1») must not reuse an id
                        fid = self.nid("en")
                    fn = E(notes, "fn", id=fid)
                    self.ids[fn.get("id")] += 1
                    E(fn, "label", m.group(0).strip())
                    p = E(fn, "p", id=self.nid("w"))
                    self.inline.fill(p, b["runs"])
                    self.blockmap.append((p.get("id"), t))
                    self.st["endnotes_typed"] += 1
                else:
                    last = notes.findall("fn")
                    if last:
                        p = E(last[-1], "p", id=self.nid("w"))
                        self.inline.fill(p, b["runs"])
                        self.blockmap.append((p.get("id"), t))
                    else:
                        p = E(parent(), "p", id=self.nid("w"))
                        self.inline.fill(p, b["runs"])
                        self.blockmap.append((p.get("id"), t))
                i += 1
                continue
            # lists: Word's own numbered paragraphs
            if b.get("num") and b.get("label") is not None and b.get("lfmt") not in (None, "none"):
                key = (b["num"][0],)
                if list_el is None or list_key != key or list_el.getparent() is not parent():
                    list_el = E(parent(), "list", list_type="bullet" if b["lfmt"] == "bullet" else "order")
                    list_key = key
                    self.st["lists"] += 1
                li = E(list_el, "list-item")
                if b["label"]:
                    E(li, "label", b["label"])
                p = E(li, "p", id=self.nid("w"))
                self.inline.fill(p, b["runs"])
                self.lang_of(p, t)
                self.blockmap.append((p.get("id"), t))
                self.st["list_items"] += 1
                i += 1
                continue
            close_list()
            p = E(parent(), "p", id=self.nid("w"))
            self.inline.fill(p, b["runs"], keep_bold=0.0 < b["bold"] < 0.9)
            self.lang_of(p, t)
            if b.get("textbox"):
                p.set("content-type", "text-box")
                self.st["textbox_paragraphs"] += 1
            if 0.0 < b["bold"] < 0.6 and b["runs"] and next((r for r in b["runs"] if r.get("t", "").strip()),
                                                             {}).get("b"):
                self.st["run_in_bold_heads"] += 1
            self.blockmap.append((p.get("id"), t))
            self.st["paragraphs"] += 1
            i += 1
        # endnotes typed in the text: link superscript numbers to them
        if notes is not None:
            if notes.find("fn") is None:
                back.remove(notes)
                self.st["notes_heading_without_numbered_notes"] += 1
            else:
                self.link_typed_notes(body, notes)

    def strip_colon(self, el):
        if len(el):
            last = el[-1]
            if last.tail:
                last.tail = re.sub(r"\s*[:：]\s*$", "", last.tail)
        elif el.text:
            el.text = re.sub(r"\s*[:：]\s*$", "", el.text)

    def lang_of(self, p, t):
        if self.lang == "ar" and is_latin(t):
            p.set(XML_LANG, "en" if not re.search(r"\b(le|la|les|des|du|et)\b", t) else "fr")

    def link_typed_notes(self, body, notes):
        ids = {fn.get("id") for fn in notes.findall("fn")}
        for sup in list(body.iter("sup")):
            m = re.fullmatch(r"\s*[(\[]?([0-9٠-٩]{1,3})[)\]]?\s*", sup.text or "")
            if m and f"en{m.group(1).translate(DIG)}" in ids:
                sup.tag = "xref"
                sup.set("ref-type", "fn")
                sup.set("rid", f"en{m.group(1).translate(DIG)}")
                self.st["endnote_calls_linked"] += 1

    # -------------------------------------------------------------- tables, figures
    def table(self, par, b, cap):
        tw = E(par, "table-wrap", id=self.nid("t"))
        if cap:
            ct = ws(" ".join(ptext(c) for c in cap))
            m = CAP_T.match(ct)
            lab = ct[:m.end()].strip() + (")" if "(" in ct[:m.end()] and ct[m.end():m.end() + 1] == ")" else "")
            rest = ct[len(lab):].strip(" :：-–.")
            E(tw, "label", lab)
            if rest:
                c = E(tw, "caption")
                E(c, "title", rest)
            for c in cap:
                self.blockmap.append((tw.get("id"), ptext(c)))
            self.st["tables_captioned"] += 1
        tb = E(tw, "table")
        rows = b["rows"]
        nh = b["header_rows"]
        if nh:
            th = E(tb, "thead")
            self.rows(th, rows[:nh], "th")
        tbd = E(tb, "tbody")
        self.rows(tbd, rows[nh:] if nh else rows, "td")
        if not len(tbd):
            tb.remove(tbd)
            if nh:
                tbd = E(tb, "tbody")
                tr = E(tbd, "tr")
                E(tr, "td")
        self.st["tables"] += 1
        self.st["table_cells"] += sum(len(r) for r in rows)
        return tw

    def rows(self, parent, rows, tag):
        for r in rows:
            tr = E(parent, "tr")
            for c in r:
                td = E(tr, tag, colspan=str(c["colspan"]) if c["colspan"] > 1 else None,
                       rowspan=str(c["rowspan"]) if c["rowspan"] > 1 else None)
                first = True
                for p in c["paras"]:
                    if not ptext(p):
                        continue
                    if not first:
                        E(td, "break")
                    self.inline.fill(td, p["runs"])
                    first = False

    def figure(self, par, b, blocks, i):
        t = ptext(b)
        if t and not CAP_F.match(t):
            p = E(par, "p", id=self.nid("w"))
            self.inline.fill(p, b["runs"])
            self.blockmap.append((p.get("id"), t))
        for rid in b["images"]:
            fig = E(par, "fig", id=self.nid("f"))
            cap = None
            if CAP_F.match(t):
                cap = t
            else:
                for k in (i + 1, i - 1):
                    if 0 <= k < len(blocks) and blocks[k]["kind"] == "p" and CAP_F.match(ptext(blocks[k])):
                        cap = ptext(blocks[k])
                        if k == i + 1:
                            self._fig_caption_used = (len(self.blocks) - len(blocks)) + k
                        break
            if cap:
                m = CAP_F.match(cap)
                lab = cap[:m.end()].strip()
                if "(" in lab and not lab.endswith(")") and cap[m.end():m.end() + 1] == ")":
                    lab += ")"
                E(fig, "label", lab)
                rest = cap[len(lab):].strip(" :：-–.")
                if rest:
                    c = E(fig, "caption")
                    E(c, "title", rest)
                self.st["figures_captioned"] += 1
                self.blockmap.append((fig.get("id"), cap))
            target = self.doc["media"].get(rid)
            if target:
                name = Path(target).name
                E(fig, "graphic", xlink_href=f"{self.stem}.media/{name}")
                self.media.append(target)
            else:
                E(fig, "graphic", xlink_href="missing")
                self.st["figures_without_media"] += 1
            self.st["figures"] += 1

    # -------------------------------------------------------------- references
    def add_ref(self, rl, b):
        t = ptext(b)
        if not t:
            return
        if rl is None:
            return
        ref = E(rl, "ref", id=self.nid("r"))
        mc = E(ref, "mixed-citation", id=self.nid("w"))
        self.inline.fill(mc, b["runs"])
        self.blockmap.append((mc.get("id"), t))
        self.st["refs"] += 1
        italic = " ".join(r["t"] for r in b["runs"] if r.get("i") and r.get("t", "").strip())
        w = parse_ref(t, italic)
        plain = ws("".join(mc.itertext()))
        ec = refs43.citation(w, plain, self.st, self.lang) if w else None
        if ec is not None:
            ref.append(ec)
            self.st["refs_with_fields"] += 1
            have = {e.tag for e in ec.iter()}
            if {"person-group", "year"} <= have and ({"article-title", "source"} & have):
                self.st["refs_author_year_title"] += 1
            self.st[f"refs_type_{ec.get('publication-type')}"] += 1
        else:
            self.st["refs_mixed_only"] += 1

    # -------------------------------------------------------------- footnotes
    def footnotes(self, back):
        if not self.doc["footnotes"]:
            return
        fg = etree.Element("fn-group", {"content-type": "footnotes"})
        rl = back.find("ref-list")
        back.insert(0, fg) if rl is None else rl.addprevious(fg)
        an = None
        for k, tn in enumerate(getattr(self, "front_notes", []), 1):
            if tn["fn"] not in self.doc["footnotes"] or tn["fn"] in self.fn_order:
                continue
            if an is None:
                an = E(self.am, "author-notes")
            fid = f"fn-front{k}"
            fn = E(an, "fn", id=fid, fn_type="other")
            E(fn, "label", (tn.get("mark") or "").strip() or "*")
            for b in self.doc["footnotes"][tn["fn"]]:
                p = E(fn, "p", id=self.nid("w"))
                self.inline.fill(p, [r for r in b["runs"] if "fn" not in r])
                self.blockmap.append((p.get("id"), ptext(b)))
            self.fn_order[tn["fn"]] = (fid, "*")
            self.st["front_notes_to_author_notes"] += 1
            self.note_aff(tn, fid, k)
        for wid, ps in self.doc["footnotes"].items():
            if wid not in self.fn_order:
                n = len(self.fn_order) + 1
                self.fn_order[wid] = (f"fn{n}", str(n))
                self.st["footnotes_without_call"] += 1
        for wid, (fid, lab) in sorted(((k, v) for k, v in self.fn_order.items() if not v[0].startswith("fn-front")),
                                      key=lambda x: int(x[1][0][2:])):
            fn = E(fg, "fn", id=fid)
            E(fn, "label", lab)
            ps = self.doc["footnotes"].get(wid) or []
            for b in ps:
                p = E(fn, "p", id=self.nid("w"))
                self.inline.fill(p, [r for r in b["runs"] if "fn" not in r])
                self.blockmap.append((p.get("id"), ptext(b)))
            if not ps:
                E(fn, "p")
            self.st["footnotes"] += 1
        if not len(fg.findall("fn")):
            back.remove(fg)

    def note_aff(self, tn, fid, k):
        """exp 70: an author note that states the author's post and institution («* أستاذ ... كلية ... جامعة ...») is
        that author's affiliation when the contrib has none printed under the name: the note called from a byline
        goes to the names of that byline in order; a note elsewhere (on the title) goes to a sole author, or to the
        k-th author when there are as many notes as authors."""
        cg = getattr(self, "cg", None)
        if cg is None:
            return
        text = ws(" ".join(ptext(b) for b in self.doc["footnotes"].get(tn["fn"]) or []))
        text = re.sub(r"^[\W_0-9٠-٩]+", "", text).strip()      # rules, bullets, «(*)», «?)» before the words
        if not text or not AFF_WORDS.search(text) or len(text.split()) > 60:
            return
        if re.match(r"^\s*(ال)?(مؤلف|باحث)\s+(ال)?(مرسل|المراسل)|^\s*corresponding\s+author", text, re.I) and \
                not re.search(r"جامع|كلي|معهد|مركز|وزار|مخبر|univ|instit|facult", text, re.I):
            self.st["front_note_corresponding_only"] += 1     # exp 74 (0840): «المؤلف المرسل: أستاذة …», no body
            return
        if re.match(r"^\s*(ال)?عنوان\s+(ال)?(أصلي|اصلي)|^\s*original\s+title", text, re.I):
            self.st["front_note_original_title"] += 1          # exp 74 (0097): a book review's original title
            return
        contribs = cg.findall("contrib")
        x = self.front_note_block.get(id(tn))
        hits = getattr(self, "byline_hits", {}).get(x)
        tgt = None
        if hits:
            done = getattr(self, "_note_hit", {})
            n = done.get(x, 0)
            done[x] = n + 1
            self._note_hit = done
            if n < len(hits):
                tgt = hits[n]
        elif len(contribs) == 1:
            tgt = 0
        elif len(self.front_notes) == len(contribs):
            tgt = k - 1
        if tgt is None or tgt >= len(contribs):
            self.st["front_note_aff_unplaced"] += 1
            return
        c = contribs[tgt]
        if c.find("aff") is not None:
            return
        E(c, "xref", (tn.get("mark") or "*").strip() or "*", ref_type="fn", rid=fid)
        E(c, "aff", text, specific_use="author-note")
        self.tag_aff(c)
        self.st["front_note_aff"] += 1

    # -------------------------------------------------------------- history, custom meta
    def history(self):
        got = {}
        lines = [ws(t) for _, t in self.front_lines] + [ptext(b) for b in self.blocks[-12:] if b["kind"] == "p"]
        for t in lines:
            for h in J.history_in(t):
                got.setdefault(h["type"], h)
        if not got:
            return
        hist = etree.Element("history")
        for typ in ("received", "reviewed", "revised", "accepted", "published"):
            if typ in got:
                hist.append(J.date_el("date", typ, got[typ]["date"], got[typ]["text"]))
                self.st["history_dates"] += 1
        J.put(self.am, hist)

    def printed_journal(self):
        h = " ".join(self.doc["header"])
        m = re.search(r"مجلة\s+[؀-ۿ ]{3,40}?(?=\s{2,}|\s+العدد|$)", h)
        return ws(m.group(0)) if m else None

    def custom(self, am):
        cmg = E(am, "custom-meta-group")

        def meta_(name, value):
            cm = E(cmg, "custom-meta")
            E(cm, "meta-name", name)
            E(cm, "meta-value", value)
        meta_("text-direction", "rtl (text stored in logical order; xml:lang carries the script)")
        meta_("text-source", f"publisher's Word file (no scan): {self.stem}.doc (Mandumah's Word originals, "
                             f"/home/adminuser/ai_data/.../docs), converted to .docx by LibreOffice 24.2; the text is "
                             f"the file's text as typed, nothing corrected (D30)")
        meta_("structure-source", "code only, no model (experiment 53, build53.py): headings from the file's fonts, "
                                  "bold, alignment and colons; lists from Word's numbering; footnotes from Word's own "
                                  "notes; tables from Word's tables; references one per paragraph after the "
                                  "references heading, fields split by a code parser")
        meta_("metadata-source", "catalogue (MARC, D33): title, people with authority ids, journal, year, volume, "
                                 "issue, pages; the file's printed forms kept beside them; changes in "
                                 f"{self.stem}.metachanges.json")
        pj = self.printed_journal()
        if pj:
            meta_("printed-journal", pj)
        h = " ".join(self.doc["header"])
        mi = re.search(r"العدد\s+[؀-ۿ ]{2,40}?(?=\s{2,}|$)", h)
        if mi:
            meta_("printed-issue", ws(mi.group(0)))
        ps = self.doc["page_start"]
        if ps:
            ok = self.rng and ps == self.rng[0]
            meta_("word-page-numbering", f"the Word file numbers its first page {ps}" +
                  (f" (the catalogue's first page: {self.rng[0]}, {'the same' if ok else 'different'})"
                   if self.rng else ""))
        meta_("ink", f"no scan: block positions in the legacy PDF (S3 legacy/{self.stem}/{self.stem}.pdf, made from "
                     f"this Word file by LibreOffice + Amiri) in {self.stem}.pdfmap.json, with each block's "
                     f"estimated printed page")
        if self.front_lines:
            for idx, t in self.front_lines:
                cm = E(cmg, "custom-meta")
                E(cm, "meta-name", "front-matter-block")
                E(cm, "meta-value", ws(t))
        if self.cat_desc:
            meta_("catalogue", self.cat_desc + f"; record {self.rec.get('id', '?')}")

    def order_meta(self, am):
        kids = [c for c in am if isinstance(c.tag, str)]
        kids.sort(key=lambda c: J.AM_ORDER.index(c.tag) if c.tag in J.AM_ORDER else 99)
        for c in kids:
            am.remove(c)
        for c in kids:
            am.append(c)

    def log(self, field, printed, corrected, source, reason):
        self.changes.append(dict(field=field, printed=printed, corrected=corrected, source=source, reason=reason))


# ------------------------------------------------------------------------------------------------ the legacy PDF

def norm_ar(s):
    s = fold(s)
    return re.sub(r"[^ء-ي0-9]", "", s)


def norm_la(s):
    return re.sub(r"[^a-z0-9]", "", fold(s))


class Legacy:
    """The legacy PDF's text, normalised twice (Arabic letters + digits; Latin letters + digits) with an index back
    to pdfium's characters, so a block's text is found despite the stray Latin letters LibreOffice's justification
    leaves inside Arabic words."""

    def __init__(self, path: Path):
        import pypdfium2 as pdfium
        self.pdf = pdfium.PdfDocument(str(path))
        self.n = len(self.pdf)
        self.pages = []
        self.streams = {"ar": ([], []), "la": ([], [])}
        for k in range(self.n):
            pg = self.pdf[k]
            tp = pg.get_textpage()
            nc = tp.count_chars()
            txt = tp.get_text_range(0, nc) if nc else ""
            self.pages.append((pg, tp, pg.get_size()[1]))
            for key, keep in (("ar", lambda ch: ("ء" <= ch <= "ي") or ch.isdigit()),
                              ("la", lambda ch: ("a" <= ch <= "z") or ch.isdigit())):
                chars, idx = self.streams[key]
                for ci, ch in enumerate(txt):
                    f = fold(ch)
                    if f and keep(f[0]):
                        chars.append(f[0])
                        idx.append((k, ci))
        self.text = {k: "".join(v[0]) for k, v in self.streams.items()}
        self.cursor = {"ar": 0, "la": 0}

    def find(self, text):
        key = "la" if is_latin(text) else "ar"
        s = norm_la(text) if key == "la" else norm_ar(text)
        if len(s) < 6:
            return None
        hay = self.text[key]
        head = s[:40]
        pos = hay.find(head, self.cursor[key])
        if pos < 0:
            pos = hay.find(head)
        if pos < 0:
            return None
        tail = s[-40:]
        end = hay.find(tail, pos + max(0, len(s) - 40 - 50))
        if end < 0 or end - pos > len(s) * 1.5 + 100:
            end = pos + len(head) - 1
        else:
            end = end + len(tail) - 1
        self.cursor[key] = end + 1
        idx = self.streams[key][1]
        out = {}
        for k in range(pos, end + 1, max(1, (end - pos) // 400 or 1)):
            pg, ci = idx[k]
            out.setdefault(pg, []).append(ci)
        pg_e, ci_e = idx[end]
        out.setdefault(pg_e, []).append(ci_e)
        boxes = []
        for pg, cis in sorted(out.items()):
            _, tp, H = self.pages[pg]
            xs = []
            for ci in (min(cis), max(cis)) + tuple(cis[::max(1, len(cis) // 40)]):
                try:
                    x0, y0, x1, y1 = tp.get_charbox(ci)
                    xs.append((x0, H - y1, x1, H - y0))
                except Exception:  # noqa: BLE001
                    pass
            if xs:
                boxes.append(dict(page=pg + 1, box=[round(min(a[0] for a in xs), 1), round(min(a[1] for a in xs), 1),
                                                    round(max(a[2] for a in xs), 1), round(max(a[3] for a in xs), 1)]))
        return dict(pages=boxes, full=end > pos + len(head) - 1)


# ------------------------------------------------------------------------------------------------ one article

def tidy_dtd(art, st):
    """exp 74 (journal 0523): an author note holding only its label («(*)») gets an empty paragraph (its call stays
    valid); a table row every cell of which is covered by a rowspan from above is removed and those rowspans shortened
    (the DTD wants a cell in every tr)."""
    for fn in art.iter("fn"):
        if fn.find("p") is None:
            etree.SubElement(fn, "p")
            st["tidy_fn_label_only"] += 1
    for tb in art.iter("table"):
        rows = list(tb.iter("tr"))
        for i, tr in enumerate(rows):
            if len(tr) or (tr.text or "").strip():
                continue
            for j in range(i):
                for c in rows[j]:
                    rs = int(c.get("rowspan") or 1)
                    if rs > 1 and j + rs - 1 >= i:
                        c.set("rowspan", str(rs - 1)) if rs - 1 > 1 else c.attrib.pop("rowspan")
            tr.getparent().remove(tr)
            st["tidy_empty_row"] += 1


def build_one(stem: str, cat) -> dict:
    t0 = time.time()
    docx = OUT / "docx" / f"{stem}.docx"
    rec = cat.get(stem) if cat else None
    A = Article(stem, docx, rec, cat.describe() if cat else "")
    A.media = []
    art = A.build()
    tidy_dtd(art, A.st)
    MAST.mkdir(parents=True, exist_ok=True)
    out = MAST / f"{stem}.jats.xml"
    xml = etree.tostring(art, encoding="UTF-8", xml_declaration=True, doctype=DOCTYPE, pretty_print=True)
    out.write_bytes(xml)
    errs = validate_jats(out)
    st = A.st
    # media
    if A.media:
        md = MAST / f"{stem}.media"
        md.mkdir(exist_ok=True)
        for t in set(A.media):
            try:
                (md / Path(t).name).write_bytes(A.doc["zip"].read("word/" + t))
            except KeyError:
                st["media_missing"] += 1
    # legacy PDF map + estimated printed page
    lp = OUT / "legacy_pdf" / f"{stem}.pdf"
    pmap = dict(stem=stem, legacy_pdf=str(lp.relative_to(HERE)) if lp.exists() else None, blocks=[])
    total = sum(len(norm_ar(t) or norm_la(t)) for _, t in A.blockmap) or 1
    run = 0
    L = Legacy(lp) if lp.exists() else None
    rng = A.rng
    npr = (rng[1] - rng[0] + 1) if rng else None
    for bid, t in A.blockmap:
        e = dict(id=bid)
        if npr:
            e["printed_page_est"] = rng[0] + min(npr - 1, int(run / total * npr))
        run += len(norm_ar(t) or norm_la(t))
        if L is not None:
            f = L.find(t)
            if f:
                e.update(f)
                st["pdfmap_found"] += 1
                if f["full"]:
                    st["pdfmap_found_whole"] += 1
            else:
                st["pdfmap_not_found"] += 1
        pmap["blocks"].append(e)
    if L is not None:
        pmap["legacy_pages"] = L.n
        st["legacy_pages"] = L.n
    (MAST / f"{stem}.pdfmap.json").write_text(json.dumps(pmap, ensure_ascii=False), encoding="utf-8")
    (MAST / f"{stem}.metachanges.json").write_text(json.dumps(dict(stem=stem, rule="docs/decisions.md D33",
                                                                    changes=A.changes), ensure_ascii=False, indent=1),
                                                   encoding="utf-8")
    st["blocks_mapped"] = len(A.blockmap)
    chars = sum(len(t) for _, t in A.blockmap)
    return dict(stem=stem, valid=not errs, errors=errs[:5], stats=dict(st), chars=chars,
                fn_word=len(A.doc["footnotes"]), page_start=A.doc["page_start"], pages=rec.get("pages") if rec else None,
                secs=round(time.time() - t0, 1))


def main(argv):
    stems = argv or [l.strip() for l in (OUT / "stems_all.txt").read_text().splitlines() if l.strip()]
    cat = CAT.open_catalogue()
    res = []
    for s in stems:
        try:
            r = build_one(s, cat)
        except Exception as e:  # noqa: BLE001
            import traceback
            traceback.print_exc()
            r = dict(stem=s, valid=False, crash=repr(e), stats={})
        res.append(r)
        print(f"{s}: {'valid' if r.get('valid') else 'INVALID'} {r.get('errors', r.get('crash', ''))[:2] if not r.get('valid') else ''}"
              f" headings {r['stats'].get('headings', 0)} refs {r['stats'].get('refs', 0)} "
              f"fn {r['stats'].get('footnotes', 0)} tables {r['stats'].get('tables', 0)} "
              f"pdfmap {r['stats'].get('pdfmap_found', 0)}/{r['stats'].get('blocks_mapped', 0)}", flush=True)
    if not argv:
        (OUT / "build.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
    tot = Counter()
    for r in res:
        tot.update(r.get("stats", {}))
    print(f"\n{len(res)} articles, {sum(1 for r in res if r.get('valid'))} valid")
    for k in sorted(tot):
        print(f"  {k:<44} {tot[k]:>7}")


if __name__ == "__main__":
    main(sys.argv[1:])
