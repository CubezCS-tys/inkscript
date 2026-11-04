"""Experiment 65 (2026-11-02): experiment 61's leaks closed in the masters (no model calls; every answer, old or new).

Experiment 61 ("nothing lost") found printed lines that reach no field. This module adds the fields; it never changes
a printed word (D30): every value below is a copy of printed text (or its normalised form, kept beside the printed
one), and the text of every block stays as it was.

  subtitle(Mo, A)        M5   Gemini's subtitle as <subtitle> also when it is printed inside the title lines
                              (specific-use="in-printed-title"; masters41 left it out then)
  apply(Mo, A, answers)       after refs43 / enrich43, in masters43.build43:
      later bylines      M4   a byline printed in the text (p content-type="byline": a second byline, the summary
                              page's English byline, a closing signature) linked to its authors (contrib/xref
                              ref-type="other" specific-use="printed-again" -> the paragraph); a name there in the
                              other script, matched by its consonants (meta43.same_person_latin >= 0.7), kept as the
                              person's string-name[@xml:lang][@specific-use="printed-again"]; the closing place and
                              date («تحريرا في ...») as custom-meta "signature"
      identifiers        step 2   ORCID (ISO 7064 check), DOI, ISSN (check digit), e-mail, URL and phone, on every
                              line of every page; each attached by position (a line naming an author, the same
                              byline block, the nearest name above it in that block, one author) to an author
                              (contrib-id, email, uri, address/phone), the article (article-id doi, email, ext-link),
                              the journal (journal-meta issn) or a reference (its element-citation pub-id doi); a
                              reference's or the running head's id stays where it is printed and is listed only.
                              Every id found (also those only listed) -> Mo.found_ids -> <stem>.ids.json beside the
                              masters, with its page, Azure line, ALTO TextLine and block, place and owner.
      article lines      P2 by code   "how to cite this article" (custom-meta how-to-cite), the journal's section /
                              rubric printed over the title (article-categories subj-group subj-group-type="heading"),
                              the licence / copyright line (permissions: copyright-statement, license/license-p)
      prompt v3.6        P1-P3   metadata authors[].position (meta43.names_pre), enrich "doi", "license",
                              "section" (article keys) and "printings" (any chunk: every other printing of an author
                              with its lines, ids, e-mail, post and the corresponding mark) -> the same homes
"""
from __future__ import annotations

import json
import os
import re
import unicodedata
from collections import Counter, defaultdict
from itertools import permutations

from lxml import etree

# EXP65_OFF=1: today's code without experiment 65 (the control build that proves no printed text changed)
ON = os.environ.get("EXP65_OFF") != "1"
XL = "{http://www.w3.org/1999/xlink}"
XML_LANG = "{http://www.w3.org/XML/1998/namespace}lang"
DIG = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
TASHKEEL = re.compile("[\u0610-\u061a\u064b-\u065f\u0670\u06d6-\u06ed\u0640]")   # marks and tatweel only
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي"})

# ------------------------------------------------------------------------------------------------ patterns
DASH = r"[-‐‑–—]"
ORCID_LOOSE = re.compile(rf"(?<![\d])(\d{{4}})\s*{DASH}?\s*(\d{{4}})\s*{DASH}?\s*(\d{{4}})\s*{DASH}?\s*(\d{{3}}[\dXx])(?![\dA-Za-z])")
ORCID_STRICT = re.compile(r"(?<![\d-])(000[09]-\d{4}-\d{4}-\d{3}[\dX])(?![\d-])")
ORCID_WORD = re.compile(r"orcid", re.I)
DOI = re.compile(r"(?<![\w.])(10\.\d{4,9})\s*/\s*([^\s\"<>«»]+(?:\s*[-‐/]\s*[^\s\"<>«»]+)*)")   # «10.29343/ 2 - 102 -3»
ISSN = re.compile(rf"((?:e|p|print|online|electronic)?\s*{DASH}?\s*ISSN|ردمد|الترقيم\s+الدولي)[^0-9٠-٩\n]{{0,30}}"
                  rf"([0-9٠-٩]{{4}})\s*{DASH}?\s*([0-9٠-٩]{{3}}[0-9٠-٩Xx])", re.I)
EMAIL = re.compile(r"[\w.+-]+\s?@\s?[\w-]+(?:\.[\w-]+)+")
URL = re.compile(r"(?:https?\s?:\s?//|www\.)[^\s<>\"«»]+", re.I)
PHONE_LABEL = re.compile(r"(?:هاتف|الهاتف|جوال|الجوال|نقال|تلفون|تليفون|تلفونات|فاكس|الفاكس|\btel\b\.?|t[ée]l[ée]phone|"
                         r"\bphone\b|mobile|\bmob\b\.?|\bfax\b|\bgsm\b)", re.I)
PHONE_NUM = re.compile(r"\+?[0-9٠-٩][0-9٠-٩\s()\-/.]{5,24}[0-9٠-٩]")
PHONE_INTL = re.compile(r"(?<![\w.])\+[0-9٠-٩]{1,3}[\s-]?[0-9٠-٩][0-9٠-٩\s-]{6,16}[0-9٠-٩]")
CITE = re.compile(r"^\W*(للاستشهاد|طريقة\s+الاستشهاد|الاستشهاد\s+المرجعي|للإحالة|للاحالة|توثيق\s+البحث|كيفية\s+الاستشهاد|"
                  r"to\s+cite\s+this|cite\s+this\s+article|how\s+to\s+cite|citation\s*:|pour\s+citer)", re.I)
SECTION = re.compile(r"^\W*(المقالات|البحوث\s+والدراسات|بحوث\s+ودراسات|البحوث|الدراسات|دراسات|بحوث|مقالات|ملف\s+العدد|"
                     r"افتتاحية\s+العدد|الافتتاحية|كلمة\s+العدد|عرض\s+كتاب|عروض\s+الكتب|قراءات|قراءة\s+في\s+كتاب|تقارير|"
                     r"تجارب\s+إبداعية|research\s+papers?|research\s+articles?|original\s+articles?|articles|editorial|"
                     r"book\s+reviews?|review\s+articles?)\W*$", re.I)
LICENSE = re.compile(r"(رخصة|المشاع\s+الإبداعي|المشاع\s+الابداعي|الوصول\s+المفتوح|licen[cs]e|creative\s*commons|"
                     r"\bcc[\s-]?by\b|copyright|©|حقوق\s+(?:الطبع|النشر|المؤلف)|جميع\s+الحقوق|all\s+rights\s+reserved|"
                     r"open\s+access)", re.I)
CC_URL = re.compile(r"(?:https?://)?creativecommons\.org/licenses/[\w./-]+", re.I)
SIGN = re.compile(r"(تحريرا|تحريراً|حرر|كتب|صدر)\s+في|^\W*(في|بتاريخ)\s*[:：]?\s*[0-9٠-٩]", re.I)
DATE = re.compile(r"[0-9٠-٩]{1,4}\s*[/\-.]\s*[0-9٠-٩]{1,2}\s*[/\-.]\s*[0-9٠-٩]{2,4}|"
                  r"(?:19|20|13|14)[0-9]{2}|[١٢][٣٤٩٠][٠-٩]{2}")
AFF_WORDS = re.compile(r"جامعة|كلية|قسم|معهد|مركز|وزارة|university|faculty|college|department|institute|e-?mail|"
                       r"orcid|@|https?:|[0-9٠-٩]{3}", re.I)
SIG_EXCL = re.compile(r"جامعة|كلية|قسم|معهد|مركز|وزارة|university|faculty|college|department|institute|e-?mail|"
                      r"orcid|@|https?:", re.I)
POST = re.compile(r"^\W*(?:أستاذة?|استاذة?|الأستاذة?|مدرسة?|محاضرة?|باحثة?|طالبة?|طالب|معيدة?|عميدة?|وكيلة?|رئيسة?\s+قسم|"
                  r"خبيرة?|مستشارة?|مديرة?|مفتشة?|موجهة?|معلمة?|أخصائية?|اخصائية?|عضو\s+هيئة|دكتوراه|ماجستير|"
                  r"(?:full\s+|associate\s+|assistant\s+)?professor|lecturer|researcher|ph\.?\s?d|student|doctoral|"
                  r"doctorant|dean|head\s+of|teacher|instructor|ma[iî]tre|docteur|chercheu[rs]e?|enseignante?|"
                  r"consultant|director|inspector|specialist|candidate)(?![\w؀-ۿ])", re.I)
AFF_STEM = re.compile(r"جامع|كلي|قسم|معهد|مركز|وزار|أكاديمي|اكاديمي|مدرسة|مديرية|إدارة|ادارة|مختبر|"
                      r"universit|facult|college|department|dept\b|institut|school|centre|center|ministry|academy|"
                      r"laborator", re.I)
NAME_LABEL = re.compile(r"^\W*(?:اسم\s+(?:ال)?(?:مؤلف|باحث)\w*(?:\s+\w+)?|(?:main\s+|co-?)?author(?:'s)?\s+name|"
                        r"name)\s*[:：]\s*", re.I)


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = TASHKEEL.sub("", s).translate(FOLD).translate(DIG).casefold()
    return " ".join(re.sub(r"[^\w@.+-]+", " ", s).replace("_", " ").split())


def toks(s: str) -> list[str]:
    return [t.strip(".-+") for t in fold(s).replace(".", " ").split() if len(t.strip(".-+")) > 1]


def tx(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


# ------------------------------------------------------------------------------------------------ checks
def orcid_ok(s: str) -> bool:
    d = re.sub(r"[^\dX]", "", s.upper())
    if len(d) != 16:
        return False
    tot = 0
    for ch in d[:15]:
        tot = (tot + int(ch)) * 2
    r = (12 - tot % 11) % 11
    return d[15] == ("X" if r == 10 else str(r))


def orcid_fmt(d: str) -> str:
    d = re.sub(r"[^\dX]", "", d.upper())
    return "-".join(d[i:i + 4] for i in range(0, 16, 4))


def issn_ok(s: str) -> bool:
    d = re.sub(r"[^\dX]", "", s.upper().translate(DIG))
    if len(d) != 8 or "X" in d[:7]:
        return False
    tot = sum(int(c) * (8 - i) for i, c in enumerate(d[:7]))
    r = (11 - tot % 11) % 11
    return d[7] == ("X" if r == 10 else str(r))


def doi_clean(s: str) -> str:
    s = re.sub(r"\s+", "", s)
    s = s.rstrip(".,;:)]}»،؛")
    if s.count("(") < s.count(")"):
        s = s.rstrip(")")
    return s


def find_all(text: str) -> list[dict]:
    """Every fixed-format identifier on one printed line: dicts kind / value (normalised) / printed / valid / span."""
    t = text or ""
    tn = t.translate(DIG)
    out, taken = [], []

    def add(kind, value, printed, valid, span, **kw):
        if any(a < span[1] and span[0] < b for a, b in taken):
            return
        taken.append(span)
        out.append(dict(kind=kind, value=value, printed=printed, valid=valid, span=span, **kw))
    has_orcid = bool(ORCID_WORD.search(tn))
    for m in ORCID_STRICT.finditer(tn):
        add("orcid", m.group(1), t[m.start():m.end()], orcid_ok(m.group(1)), m.span())
    if has_orcid:
        for m in ORCID_LOOSE.finditer(tn):
            v = orcid_fmt("".join(m.groups()))
            add("orcid", v, t[m.start():m.end()], orcid_ok(v), m.span())
        if not any(o["kind"] == "orcid" for o in out):           # digits scrambled by the right-to-left line
            m = re.search(r"orcid\.org/\s*([\dXx\s\-‐–]{16,30})", tn, re.I)
            if m and len(re.sub(r"[^\dXx]", "", m.group(1))) == 16:
                d = re.sub(r"[^\dXx]", "", m.group(1)).upper()
                add("orcid", orcid_fmt(d), t[m.start(1):m.end(1)].strip(), orcid_ok(d), m.span(1), scrambled=True)
    for m in DOI.finditer(tn):
        v = doi_clean(m.group(1) + "/" + m.group(2))
        if len(v) > 8:
            add("doi", v, t[m.start():m.end()].strip(), True, m.span())
    for m in ISSN.finditer(tn):
        v = f"{m.group(2)}-{m.group(3).upper()}"
        lab = m.group(1).lower()
        add("issn", v, t[m.start(2):m.end(3)], issn_ok(v), (m.start(2), m.end(3)),
            medium="electronic" if re.search(r"e|online|electr", lab.replace("issn", "")) else
            ("print" if re.search(r"p|print", lab.replace("issn", "")) else None))
    for m in EMAIL.finditer(t):
        v = re.sub(r"\s", "", m.group(0)).strip(".")
        add("email", v, m.group(0), "@" in v and "." in v.split("@")[-1], m.span())
    for m in URL.finditer(t):
        v = re.sub(r"\s", "", m.group(0)).rstrip(".,;:)]»،")
        if re.search(r"doi\.org|orcid\.org", v, re.I):
            continue
        add("url", v, m.group(0), True, m.span())
    lab = PHONE_LABEL.search(t)
    if lab:
        for m in PHONE_NUM.finditer(t, lab.end()):
            pos = m.start()
            for part in re.split(r"(\s+[-–/]\s+|\s*[;,،]\s*)", m.group(0)):   # «٠١٥٥٧٧١١١٨ - ٧٩٤٤٩٤»: two numbers
                d = re.sub(r"[^\d+]", "", part.translate(DIG))
                if 6 <= len(d.lstrip("+")) <= 15 and re.search(r"\d", part.translate(DIG)):
                    i = pos + len(part) - len(part.lstrip())
                    add("phone", d, part.strip(), True, (i, i + len(part.strip())), label=lab.group(0))
                pos += len(part)
    for m in PHONE_INTL.finditer(t):
        d = re.sub(r"[^\d+]", "", m.group(0).translate(DIG))
        if 8 <= len(d.lstrip("+")) <= 15:
            add("phone", d, m.group(0).strip(), True, m.span())
    return out


# ------------------------------------------------------------------------------------------------ the article's lines
class Ctx:
    def __init__(self, Mo, A):
        import enrich43
        self.Mo, self.A = Mo, A
        self.am = A.find("front/article-meta")
        self.block_of, self.order = {}, []
        for lp in sorted(Mo.alto):
            for b in Mo.alto[lp]:
                if b.get("kind") != "text":
                    continue
                for i, lid in enumerate(b.get("ids") or []):
                    if lid in Mo.S.lines and lid not in self.block_of:
                        self.block_of[lid] = (b, i)
                        self.order.append(lid)
        for lid in Mo.S.lines:
            if lid not in self.block_of:
                self.order.append(lid)
        self.el = {lid: enrich43.target_el(A, Mo, lid) for lid in self.order}
        self.first_page = min(Mo.pages) if Mo.pages else 1
        self.contribs = list(self.am.iter("contrib")) if self.am is not None else []

    def text(self, lid) -> str:
        return str(self.Mo.S.lines[lid].get("text") or "")

    def page(self, lid) -> int:
        return int(self.Mo.S.lines[lid].get("page") or 0)

    def place(self, lid) -> str:
        b = self.block_of.get(lid, (None, 0))[0]
        role = (b or {}).get("role") or ""
        if role == "pageHeader":
            return "header"
        if role in ("pageFooter", "pageNumber"):
            return "footer"
        if role in ("otherArticle", "showThrough", "pictureJunk", "ornament"):
            return "not_article"
        el = self.el.get(lid)
        if el is None:
            return "noise"
        anc = [el.tag] + [a.tag for a in el.iterancestors()]
        if "ref" in anc or "ref-list" in anc or "mixed-citation" in anc:
            return "reference"
        if "author-notes" in anc:
            return "author_note"
        if "fn" in anc:
            return "note"
        if "contrib" in anc:
            return "byline"
        if "custom-meta" in anc:
            return "front"
        if any(t in anc for t in ("title-group", "article-title", "trans-title-group", "alt-title")):
            return "title"
        if any(t in anc for t in ("abstract", "trans-abstract", "kwd-group")):
            return "abstract"
        if el.tag == "p" and el.get("content-type") == "byline":
            return "byline_later"
        if any(t in anc for t in ("td", "th", "table-wrap")):
            return "table"
        if el.tag == "p" and el.get("content-type") == "other":
            return "other"
        return "body"

    def alto_line(self, lid) -> str | None:
        return self.Mo.tl_of.get(lid)

    def block_id(self, lid) -> str | None:
        b = self.block_of.get(lid, (None, 0))[0]
        return b.get("id") if b else None

    # ---- authors
    def names(self, c) -> list[list[str]]:
        out = []
        for s in c.iter("string-name"):
            t = toks(tx(s))
            if len(t) >= 2:
                out.append(t)
        for n in c.iter("name"):
            t = toks(" ".join(tx(x) for x in n))
            if len(t) >= 2:
                out.append(t)
        return out

    def names_on(self, text: str) -> list[tuple[int, object]]:
        """(position, contrib) of each author named on this text (all of a name's words, or its first and last)."""
        import meta43
        tt = toks(text)
        nt = meta43.norm(text)
        out = []
        for c in self.contribs:
            for nm in self.names(c):
                if all(w in tt for w in nm) or (len(nm) >= 3 and nm[0] in tt and nm[-1] in tt) or \
                        (len("".join(nm)) >= 8 and meta43.norm(" ".join(nm)) in nt):   # «عبدالحافظ» / «عبد الحافظ»
                    out.append((tt.index(nm[0]) if nm[0] in tt else 0, c))
                    break
        return out


def owner_author(ctx: Ctx, lid: str, value: str = "") -> object | None:
    """The contrib a line's id belongs to, by position: the line names one author; else the nearest line above it in
    its block naming one (or below, when none above); else the blocks before it on the page (3 at most); else the
    e-mail's local part spells an author's Latin name; else the article's only author."""
    named = ctx.names_on(ctx.text(lid))
    if len(named) == 1:
        return named[0][1]
    b, i = ctx.block_of.get(lid, (None, 0))
    if b is not None:
        ids = b.get("ids") or []
        for j in list(range(i - 1, -1, -1)) + list(range(i + 1, len(ids))):
            if ids[j] in ctx.Mo.S.lines:
                n = ctx.names_on(ctx.text(ids[j]))
                if len(n) == 1:
                    return n[0][1]
                if len(n) > 1:
                    break
        lp = ctx.Mo.lp(ctx.page(lid))
        blocks = [x for x in ctx.Mo.alto.get(lp, []) if x.get("kind") == "text"]
        k = next((q for q, x in enumerate(blocks) if x is b), None)
        if k is not None:
            for x in blocks[max(0, k - 3):k][::-1]:
                for lid2 in reversed(x.get("ids") or []):
                    if lid2 in ctx.Mo.S.lines:
                        n = ctx.names_on(ctx.text(lid2))
                        if len(n) == 1:
                            return n[0][1]
    if "@" in value:
        local = re.sub(r"[^a-z]", "", value.split("@")[0].lower())
        hits = [c for c in ctx.contribs if any(len(w) >= 4 and w in local for nm in ctx.names(c) for w in nm
                                                if w.isascii())]
        if len(hits) == 1:
            return hits[0]
    authors = [c for c in ctx.contribs if (c.get("contrib-type") or "author") == "author"]
    if len(authors) == 1:
        return authors[0]
    return None


# ------------------------------------------------------------------------------------------------ JATS writes
def _fid(Mo) -> str:
    Mo._fid = getattr(Mo, "_fid", 0) + 1
    return f"fid{Mo._fid}"


def put_contrib(c, el):
    if el.tag == "contrib-id":
        c.insert(0, el)
        return
    names = [e for e in c if e.tag in ("contrib-id", "name-alternatives", "string-name", "name", "role")]
    (names[-1].addnext(el) if names and el.tag == "role" else c.append(el))


def journal_issn(A, value: str, medium: str | None, fid: str) -> bool:
    jm = A.find("front/journal-meta")
    if jm is None:
        return False
    for x in jm.findall("issn"):
        if re.sub(r"[^\dX]", "", tx(x).upper()) == value.replace("-", ""):
            return False
    el = etree.Element("issn", {"id": fid, "specific-use": "printed"})
    if medium:
        el.set("publication-format", medium)
    el.text = value
    anchor = [e for e in jm if e.tag in ("journal-id", "journal-title-group", "contrib-group", "aff",
                                          "aff-alternatives", "issn")]
    (anchor[-1].addnext(el) if anchor else jm.insert(0, el))
    return True


def identifiers(ctx: Ctx, st: Counter) -> list[dict]:
    """Step 2: every identifier of every line; attached by position; JATS homes; the list for <stem>.ids.json."""
    import jats43 as J
    Mo, A, am = ctx.Mo, ctx.A, ctx.am
    found = []
    for lid in ctx.order:
        for x in find_all(ctx.text(lid)):
            x.update(page=ctx.page(lid), line=lid, alto_line=ctx.alto_line(lid), block=ctx.block_id(lid),
                     place=ctx.place(lid))
            found.append(x)
    # an ORCID printed scrambled (digits of a right-to-left line reordered): the same id when one order of its four
    # groups is an ORCID printed elsewhere in the article
    good = {x["value"] for x in found if x["kind"] == "orcid" and x["valid"]}
    for x in found:
        if x["kind"] == "orcid" and not x["valid"]:
            g = x["value"].split("-")
            hit = sorted({"-".join(p) for p in permutations(g)} & good)
            if len(hit) == 1:
                x.update(value=hit[0], valid=True, scrambled=True, note="printed with its digit groups out of order")
    # the article's own DOI: printed away from the references and notes (front, byline, title page, running head,
    # a short line of its own); the most frequent, page 1 first
    cand = [x for x in found if x["kind"] == "doi" and x["place"] in ("front", "byline", "byline_later", "title",
                                                                       "header", "footer", "other", "noise", "abstract")
            or (x["kind"] == "doi" and x["place"] == "body" and len(toks(ctx.text(x["line"]))) <= 6)]
    art_doi = None
    if cand:
        cnt = Counter(x["value"].lower() for x in cand)
        art_doi = sorted(cnt, key=lambda v: (-cnt[v], min(x["page"] for x in cand if x["value"].lower() == v)))[0]
    have_doi = {tx(e).lower() for e in am.findall("article-id") if e.get("pub-id-type") == "doi"} if am is not None \
        else set()
    for x in found:
        k, v, place = x["kind"], x["value"], x["place"]
        x["owner"] = None
        x["home"] = None
        if place == "not_article" or not x["valid"]:
            continue
        if place == "reference":
            ref = ctx.el[x["line"]]
            ref = next((e for e in [ref] + list(ref.iterancestors()) if e.tag == "ref"), None) if ref is not None \
                else None
            x["owner"] = dict(kind="reference", ref=ref.get("id") if ref is not None else None)
            if k == "doi" and ref is not None:
                ec = ref.find("element-citation")
                if ec is not None and not any(p.get("pub-id-type") == "doi" for p in ec.findall("pub-id")):
                    pid = etree.SubElement(ec, "pub-id", {"pub-id-type": "doi", "specific-use": "printed"})
                    pid.text = v
                    x["home"] = "ref/element-citation/pub-id"
                    st["ids_ref_doi"] += 1
            continue
        if k == "doi":
            if art_doi and v.lower() == art_doi:
                x["owner"] = dict(kind="article")
                if am is not None and v.lower() not in have_doi:
                    fid = _fid(Mo)
                    e = etree.Element("article-id", {"pub-id-type": "doi", "id": fid, "specific-use": "printed"})
                    e.text = v
                    J.put(am, e)
                    have_doi.add(v.lower())
                    x["home"], x["jats_id"] = "article-id[@pub-id-type=doi]", fid
                    st["ids_article_doi"] += 1
                else:
                    x["home"] = "article-id[@pub-id-type=doi]"
            else:
                x["owner"] = dict(kind="mention", where=place)
            continue
        if k == "issn":
            x["owner"] = dict(kind="journal")
            fid = _fid(Mo)
            if journal_issn(A, v, x.get("medium"), fid):
                x["home"], x["jats_id"] = "journal-meta/issn", fid
                st["ids_issn"] += 1
            else:
                x["home"] = "journal-meta/issn"
            continue
        same = next((cc for cc in ctx.contribs if k == "email" and any(tx(e).lower() == v.lower() for e in cc.iter(
            "email")) or k == "orcid" and any(tx(e) == v for e in cc.findall("contrib-id"))), None)
        if same is not None:                                   # Gemini gave it already (or an earlier line did)
            x["owner"], x["home"] = dict(kind="author", contrib=same.get("id")), f"contrib/{k}"
            continue
        if place in ("header", "footer"):                      # the journal's address, site, e-mail
            x["owner"] = dict(kind="journal")
            continue
        authorish = place in ("front", "byline", "byline_later", "title", "author_note") or \
            place in ("note", "other", "abstract") and ctx.page(x["line"]) <= ctx.first_page + 1 or \
            bool(ctx.names_on(ctx.text(x["line"])))
        if not authorish or place == "noise" or (k == "url" and place == "note"):
            x["owner"] = dict(kind="mention", where=place)    # an address quoted in the text, a watermark
            continue
        c = owner_author(ctx, x["line"], v)
        if c is None and k == "orcid":
            c = next((cc for cc in ctx.contribs if any(tx(e) == v for e in cc.findall("contrib-id"))), None)
        if c is not None:
            x["owner"] = dict(kind="author", contrib=c.get("id"))
            fid = _fid(Mo)
            if k == "orcid":
                if any(e.get("contrib-id-type") == "orcid" and tx(e) == v for e in c.findall("contrib-id")):
                    x["home"] = "contrib-id[@contrib-id-type=orcid]"
                    continue
                e = etree.Element("contrib-id", {"contrib-id-type": "orcid", "id": fid, "specific-use": "printed"})
                e.text = v
            elif k == "email":
                if any(tx(e).lower() == v.lower() for e in c.iter("email")):
                    x["home"] = "contrib/email"
                    continue
                e = etree.Element("email", {"id": fid})
                e.text = v
            elif k == "url":
                if any(tx(e) == v for e in c.iter("uri")):
                    continue
                e = etree.Element("uri", {"id": fid})
                e.text = v
            elif k == "phone":
                if any(re.sub(r"[^\d+]", "", tx(e)) == v for e in c.iter("phone")):
                    continue
                ad = c.find("address")
                if ad is None:
                    ad = etree.SubElement(c, "address")
                e = etree.SubElement(ad, "phone", {"id": fid})
                e.text = v
                x["home"], x["jats_id"] = "contrib/address/phone", fid
                st["ids_author_phone"] += 1
                continue
            else:
                continue
            put_contrib(c, e)
            x["home"], x["jats_id"] = f"contrib/{e.tag}", fid
            st[f"ids_author_{k}"] += 1
            continue
        # the article's (no author to tie it to)
        x["owner"] = dict(kind="article")
        if am is None:
            continue
        fid = _fid(Mo)
        if k == "email":
            if any(tx(e).lower() == v.lower() for e in am.iter("email")):
                continue
            e = etree.Element("email", {"id": fid})
            e.text = v
        elif k in ("url", "orcid"):
            href = v if k == "url" else f"https://orcid.org/{v}"
            if any(e.get(XL + "href") == href for e in am.findall("ext-link")):
                continue
            e = etree.Element("ext-link", {"ext-link-type": "uri" if k == "url" else "orcid", XL + "href": href,
                                           "id": fid})
            e.text = v
        else:
            continue                                         # a phone with no author: listed only
        J.put(am, e)
        x["home"], x["jats_id"] = f"article-meta/{e.tag}", fid
        st[f"ids_article_{k}"] += 1
    for x in found:
        st[f"ids_found_{x['kind']}"] += 1
        x.pop("span", None)
    return found


# ------------------------------------------------------------------------------------------------ article lines
def _custom_meta(A, name: str, value: str, cid: str | None = None):
    cmg = A.find("front/article-meta/custom-meta-group")
    if cmg is None:
        return None
    c = etree.SubElement(cmg, "custom-meta", {"id": cid} if cid else {})
    etree.SubElement(c, "meta-name").text = name
    etree.SubElement(c, "meta-value").text = value
    return c


def _block_rest(ctx: Ctx, lid: str, n: int = 6) -> list[str]:
    b, i = ctx.block_of.get(lid, (None, 0))
    if b is None:
        return [lid]
    return [x for x in (b.get("ids") or [])[i:i + n] if x in ctx.Mo.S.lines]


def article_lines(ctx: Ctx, st: Counter, found: list[dict]):
    """P2 by code: how to cite, the journal's section / rubric, the licence / copyright line."""
    import jats43 as J
    am, A = ctx.am, ctx.A
    if am is None:
        return
    FRONTISH = ("front", "byline", "title", "other", "noise", "header", "footer", "note", "byline_later", "abstract")
    seen = set()
    # how to cite
    for lid in ctx.order:
        if ctx.place(lid) in ("reference", "not_article", "table") or not CITE.match(ctx.text(lid)):
            continue
        ids = _block_rest(ctx, lid)
        t = " ".join(ctx.text(i) for i in ids)
        if fold(t) in seen:
            continue
        seen.add(fold(t))
        _custom_meta(A, "how-to-cite", t)
        st["lines_how_to_cite"] += 1
    # the section / rubric over the title (the first two pages, or a running head)
    secs = []
    for lid in ctx.order:
        t = " ".join(ctx.text(lid).split())
        if not t or not SECTION.match(t) or ctx.place(lid) in ("reference", "not_article", "table", "body"):
            continue
        if ctx.page(lid) > ctx.first_page + 1 and ctx.place(lid) != "header":
            continue
        if fold(t) not in [fold(s) for s in secs] and not any(
                fold(tx(x)) == fold(t) for x in am.iter("subject")):
            secs.append(t.strip(" :-–"))
    if secs:
        ac = am.find("article-categories")
        if ac is None:
            ac = J.put(am, etree.Element("article-categories"))
        for t in secs[:2]:
            sg = etree.SubElement(ac, "subj-group", {"subj-group-type": "heading", "specific-use": "printed"})
            etree.SubElement(sg, "subject").text = t
            st["lines_section"] += 1
    # licence / copyright
    cps, lics = [], []
    for lid in ctx.order:
        t = " ".join(ctx.text(lid).split())
        pl = ctx.place(lid)
        if not t or not LICENSE.search(t) or pl not in FRONTISH or len(t.split()) > 40:
            continue
        if pl == "note" and ctx.page(lid) > ctx.first_page:
            continue
        if pl in ("other", "byline_later", "abstract") and ctx.page(lid) > ctx.first_page + 1 and \
                not CC_URL.search(t) and "©" not in t:
            continue
        ids = [lid]
        for nx in _block_rest(ctx, lid, 4)[1:]:           # the sentence runs on (no full stop yet)
            if re.search(r"[.。]\s*$|\)\s*\.?$", ctx.text(ids[-1]).strip()):
                break
            ids.append(nx)
        tt = " ".join(" ".join(ctx.text(i).split()) for i in ids)
        if any(fold(tt) in fold(x) or fold(x) in fold(tt) for x in cps + lics):
            continue
        if re.search(r"©|copyright|جميع\s+الحقوق|all\s+rights|حقوق\s+(?:الطبع|النشر)", tt, re.I) and \
                not re.search(r"creative|licen[cs]|رخصة|المشاع", tt, re.I):
            cps.append(tt)
        else:
            lics.append(tt)
    if cps or lics:
        pm = am.find("permissions")
        if pm is None:
            pm = J.put(am, etree.Element("permissions"))
        for t in cps:
            el = etree.Element("copyright-statement", {"specific-use": "printed"})
            el.text = t
            first_lic = next((i for i, x in enumerate(pm) if x.tag in ("license", "{http://www.niso.org/schemas/ali/1.0/}free_to_read")), None)
            if first_lic is None:        # exp 74 (1001): a license already there (prompt v3.6's) -> the statement
                pm.append(el)            # goes before it, as the DTD orders them
            else:
                pm.insert(first_lic, el)
            st["lines_copyright"] += 1
        for t in lics:
            lic = etree.SubElement(pm, "license", {"specific-use": "printed"})
            m = CC_URL.search(t.replace(" ", "")) or CC_URL.search(t)
            if m:
                u = m.group(0)
                lic.set(XL + "href", u if u.startswith("http") else "https://" + u)
            etree.SubElement(lic, "license-p").text = t
            st["lines_license"] += 1


# ------------------------------------------------------------------------------------------------ M4: later bylines
def later_bylines(ctx: Ctx, st: Counter):
    import meta43
    A = ctx.A
    ps = [p for p in A.iter("p") if p.get("content-type") == "byline" and p.get("id")
          and not any(a.tag in ("front", "contrib") for a in p.iterancestors())]
    sigs = []
    for p in ps:
        lines = [lid for lid in ctx.order if ctx.el.get(lid) is p]
        linked = set()
        for lid in lines:
            t = ctx.text(lid)
            for _, c in ctx.names_on(t):
                linked.add(c)
            # a name in the other script (the summary page's English byline of an Arabic name, or the reverse)
            cand = NAME_LABEL.sub("", t)
            cand = re.split(r"[،,(]", cand)[0]
            clean, took = meta43.strip_honorific(cand)
            clean = clean.strip(" .:-–*")
            words = clean.split()
            if not 2 <= len(words) <= 6 or AFF_WORDS.search(clean) or DATE.search(clean):
                continue
            if ctx.names_on(clean):
                continue
            best = None
            for c in ctx.contribs:
                for s in c.iter("string-name"):
                    nm = tx(s)
                    if bool(meta43.ARABIC.search(nm)) == bool(meta43.ARABIC.search(clean)):
                        continue
                    sc = meta43.same_person_latin(nm, clean) if meta43.ARABIC.search(nm) else \
                        meta43.same_person_latin(clean, nm)
                    if sc >= 0.7 and (best is None or sc > best[0]):
                        best = (sc, c)
            if best is None:
                continue
            c = best[1]
            sn = meta43.main_name(c)
            na = sn.getparent() if sn.getparent() is not None and sn.getparent().tag == "name-alternatives" else None
            if na is None:
                na = etree.Element("name-alternatives")
                sn.addprevious(na)
                na.append(sn)
            if any(fold(tx(x)) == fold(clean) for x in na.iter("string-name")):
                linked.add(c)
                continue
            lang = "ar" if meta43.ARABIC.search(clean) else "en"
            ls = etree.SubElement(na, "string-name", {XML_LANG: lang, "specific-use": "printed-again"})
            ls.text = clean
            linked.add(c)
            st["bylines_name_other_script"] += 1
            if took:
                pr = etree.SubElement(na, "string-name", {XML_LANG: lang, "specific-use": "printed-on-the-page"})
                pre = etree.SubElement(pr, "prefix")
                pre.text = took
                pre.tail = " " + clean
        for c in linked:
            if not any(x.get("rid") == p.get("id") for x in c.findall("xref")):
                etree.SubElement(c, "xref", {"ref-type": "other", "rid": p.get("id"),
                                             "specific-use": "printed-again"})
                st["bylines_linked"] += 1
        # the closing place and date (a signature at the end)
        pg = max((ctx.page(lid) for lid in lines), default=0)
        if pg > ctx.first_page + 1 or not linked:
            for lid in lines:
                t = " ".join(ctx.text(lid).split())
                if (SIGN.search(t) or (DATE.search(t) and len(t.split()) <= 8)) and not SIG_EXCL.search(t) and \
                        not ctx.names_on(t):
                    sigs.append(t)
    for t in dict.fromkeys(sigs):
        _custom_meta(A, "signature", t)
        st["bylines_signature"] += 1


# ------------------------------------------------------------------------------------------------ M1 by code
def posts_in_bylines(ctx: Ctx, st: Counter):
    """A post / rank printed at the start of a byline line («أستاذ مشارك بقسم التربية الخاصة», "Associate Professor")
    that the answer left in no field: the words before the affiliation, kept as the author's <role
    content-type="position"> (exact substring; the author by position, as for an e-mail)."""
    import meta43
    for lid in ctx.order:
        if ctx.place(lid) not in ("front", "byline", "byline_later"):
            continue
        t = " ".join(NAME_LABEL.sub("", ctx.text(lid)).split())
        if not POST.match(t) or EMAIL.search(t) or ctx.names_on(t):
            continue
        words = t.split()
        k = next((i for i, w in enumerate(words) if i > 0 and AFF_STEM.search(w)), len(words))
        pos = " ".join(words[:k]).strip(" ،,:-–/")
        if not pos or len(pos.split()) > 10 or DATE.search(pos):
            continue
        ph, hons, rest = meta43.split_role(pos)
        if not rest:
            continue                                      # an honorific alone («الأستاذة»): not a post
        c = owner_author(ctx, lid)
        if c is None:
            continue
        have = [meta43.norm(tx(r)) for r in c.findall("role")]
        if any(meta43.norm(pos) in h for h in have if h):
            continue
        nm = " ".join("".join(meta43.main_name(c).itertext()).split())
        r = etree.Element("role", {"content-type": "position", "specific-use": "printed-in-byline"})
        if bool(meta43.ARABIC.search(pos)) != bool(meta43.ARABIC.search(nm)):
            r.set(XML_LANG, "ar" if meta43.ARABIC.search(pos) else "en")
        r.text = pos
        put_contrib(c, r)
        st["posts_from_byline_lines"] += 1


# ------------------------------------------------------------------------------------------------ M5
def subtitle(Mo, A):
    """Gemini's subtitle kept as <subtitle> when masters41 left it out because the title lines print it."""
    tg = A.find("front/article-meta/title-group")
    s = " ".join(str((Mo.meta or {}).get("subtitle") or "").split())
    if tg is None or not s or tg.find("subtitle") is not None:
        return
    el = etree.Element("subtitle", {"specific-use": "in-printed-title"})
    el.text = s
    at = tg.find("article-title")
    (at.addnext(el) if at is not None else tg.insert(0, el))
    Mo.stats["subtitle_in_printed_title"] += 1


# ------------------------------------------------------------------------------------------------ prompt v3.6
def v36(ctx: Ctx, answers: list[dict], st: Counter):
    """P2 / P3 values (checked in enrich43.check): the article's DOI, licence lines, section line; every other
    printing of an author (its lines -> xref to the paragraph; its ORCID / e-mail / post / corresponding mark)."""
    import jats43 as J
    import meta43
    A, am, Mo = ctx.A, ctx.am, ctx.Mo
    if am is None:
        return
    E0 = next((a.get("enrich") for a in answers if isinstance(a.get("enrich"), dict)), {}) or {}
    v = E0.get("doi")
    if v and not any(e.get("pub-id-type") == "doi" and tx(e).lower() == v.lower() for e in am.findall("article-id")):
        e = etree.Element("article-id", {"pub-id-type": "doi", "specific-use": "printed"})
        e.text = v
        J.put(am, e)
        st["v36_doi"] += 1
    for key, fn in (("section", "section"), ("license", "license")):
        ls = E0.get(key) or []
        if not ls:
            continue
        t = " ".join(ctx.text(i) for i in ls if i in Mo.S.lines)
        if not t:
            continue
        if key == "section":
            ac = am.find("article-categories")
            if ac is None:
                ac = J.put(am, etree.Element("article-categories"))
            if not any(fold(tx(x)) == fold(t) for x in ac.iter("subject")):
                sg = etree.SubElement(ac, "subj-group", {"subj-group-type": "heading", "specific-use": "argon"})
                etree.SubElement(sg, "subject").text = t
                st["v36_section"] += 1
        else:
            pm = am.find("permissions")
            if pm is None:
                pm = J.put(am, etree.Element("permissions"))
            if not any(fold(t) in fold(tx(x)) or fold(tx(x)) in fold(t) for x in pm):
                lic = etree.SubElement(pm, "license", {"specific-use": "argon"})
                etree.SubElement(lic, "license-p").text = t
                st["v36_license"] += 1
    cg = am.find("contrib-group")
    for ans in answers:
        for pr in (ans.get("enrich") or {}).get("printings") or []:
            c = None
            if pr.get("a"):
                c, _ = meta43._contrib(cg, pr["a"])
            if c is None and pr.get("name"):
                hits = ctx.names_on(pr["name"])
                c = hits[0][1] if len(hits) == 1 else None
            if c is None and pr.get("name"):                  # metadata named no author (0130-027-105-003: the
                if cg is None:                                # byline is printed only on the last pages)
                    cg = J.put(am, etree.Element("contrib-group"))
                c = etree.SubElement(cg, "contrib", {"contrib-type": "author", "specific-use": "from-a-later-printing",
                                                     "id": f"contrib-printing{len(list(am.iter('contrib'))) + 1}"})
                etree.SubElement(c, "string-name").text = pr["name"]
                ctx.contribs = list(am.iter("contrib"))
                st["v36_contrib_from_printing"] += 1
            if c is None:
                st["v36_printing_no_author"] += 1
                continue
            if pr.get("name") and not ctx.names_on(pr["name"]):
                sn = meta43.main_name(c)
                na = sn.getparent() if sn.getparent() is not None and sn.getparent().tag == "name-alternatives" \
                    else None
                if na is None:
                    na = etree.Element("name-alternatives")
                    sn.addprevious(na)
                    na.append(sn)
                lang = "ar" if meta43.ARABIC.search(pr["name"]) else "en"
                if not any(fold(tx(x)) == fold(pr["name"]) for x in na.iter("string-name")):
                    etree.SubElement(na, "string-name", {XML_LANG: lang, "specific-use": "printed-again"}).text = \
                        pr["name"]
            if pr.get("corresp"):
                c.set("corresp", "yes")
            if pr.get("orcid") and not any(tx(e) == pr["orcid"] for e in c.findall("contrib-id")):
                e = etree.Element("contrib-id", {"contrib-id-type": "orcid", "specific-use": "argon"})
                e.text = pr["orcid"]
                c.insert(0, e)
            if pr.get("email") and not any(tx(e).lower() == pr["email"].lower() for e in c.iter("email")):
                e = etree.Element("email")
                e.text = pr["email"]
                put_contrib(c, e)
            if pr.get("position"):
                meta43.role_parts(Mo, c, "", pr["position"])
            for lid in pr.get("lines") or []:
                el = ctx.el.get(lid)
                if el is None or not el.get("id"):
                    continue
                if not any(x.get("rid") == el.get("id") for x in c.findall("xref")):
                    etree.SubElement(c, "xref", {"ref-type": "other", "rid": el.get("id"),
                                                 "specific-use": "printed-again"})
            st["v36_printings"] += 1


# ------------------------------------------------------------------------------------------------ entry
def apply(Mo, A, answers: list[dict] | None = None) -> Counter:
    st = Counter()
    if A.find("front/article-meta") is None:
        return st
    ctx = Ctx(Mo, A)
    later_bylines(ctx, st)
    posts_in_bylines(ctx, st)
    if answers:
        v36(ctx, answers, st)
    found = identifiers(ctx, st)
    article_lines(ctx, st, found)
    Mo.found_ids = found
    if hasattr(Mo, "stats"):
        Mo.stats.update(st)
    return st


def sidecar(Mo) -> dict:
    return dict(stem=Mo.stem, rule="experiment 65 (identifiers by code, every line of every page)",
                ids=getattr(Mo, "found_ids", []))
