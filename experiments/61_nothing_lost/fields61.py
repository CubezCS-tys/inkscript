"""Experiment 61: the field vocabulary of the "nothing lost" audit.

- `fold` / `toks`: the one text folding used for every comparison (Azure / ALTO words, JATS text, Gemini's values,
  platform rows): diacritics and tatweel out, alef / ya / ta-marbuta / hamza seats and Persian look-alikes folded,
  Arabic-Indic digits to ASCII, punctuation to spaces, Latin lower-cased.
- `jats_class(el)`: a JATS element that carries an ALTO TextBlock (by id or xlink:href) -> (bucket, field), where
  bucket is "a" (a specific field), "b" (generic text only), or "container" (a byline-like block whose words are
  split by matching them against the specific values, `front_values`).
- `REGION`: the ALTO roles of ink the masters keep out of the article (bucket "c"), and the two that are content.
- `detect(text)`: what a line of generic / dropped text most likely is (the field it should have gone to).
- `ASKED`: which prompt version asks for which field (read from prompt43.py; see README "What the prompt asks").
"""
from __future__ import annotations

import re
import unicodedata

# ------------------------------------------------------------------------------------------------ folding
TASHKEEL = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ‌-‏‪-‮]")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ی": "ي", "ئ": "ي", "ة": "ه", "ھ": "ه",
                      "ہ": "ه", "ۀ": "ه", "ؤ": "و", "ک": "ك", "ڪ": "ك", "ء": "",
                      **{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKC", str(s or ""))
    s = TASHKEEL.sub("", s).translate(FOLD).lower()
    s = re.sub(r"(?<=[a-z\u0600-\u06ff])(?=\d)|(?<=\d)(?=[a-z\u0600-\u06ff])", " ", s)   # «Faisal1» = «Faisal» + mark
    return re.sub(r"[^\w@.+-]+", " ", s).replace("_", " ")


def toks(s: str) -> list[str]:
    out = []
    for t in fold(s).split():
        if "@" in t or "/" in t or t.startswith("www") or re.fullmatch(r"[\d.]+", t):
            parts = [t]                              # an e-mail, a web address, a number keep their dots
        else:
            parts = t.replace(".", " ").split()      # «أ.حسن» = «أ» + «حسن»
        for x in parts:
            x = x.strip(".-+")
            if x:
                out.append(x)
    return out


CLITIC = "وبلف"


def same_tok(a: str, b: str) -> bool:
    """a (printed) is b, or b with a one-letter clitic glued in front («وراشد» / «راشد», «بقسم» / «قسم»)."""
    return a == b or (len(a) > 3 and a[0] in CLITIC and a[1:] == b)


def is_word(content: str) -> bool:
    """An ALTO String / Azure word that is a word (not a lone punctuation mark)."""
    return bool(toks(content))


# ------------------------------------------------------------------------------------------------ JATS classes
def _anc(el) -> list[str]:
    return [a.tag for a in el.iterancestors() if isinstance(a.tag, str)]


def jats_class(el) -> tuple[str, str]:
    """(bucket, field) for the JATS element an ALTO TextBlock points at."""
    tag, ct = el.tag, el.get("content-type") or ""
    anc = _anc(el)
    if tag == "article-title":
        return "a", "title"
    if tag == "alt-title":
        return "a", "title"
    if tag == "trans-title":
        return "a", "trans_title"
    if tag == "trans-subtitle":
        return "a", "trans_title"
    if tag == "subtitle":
        return "a", "subtitle"
    if tag in ("td", "th"):
        return "a", "table_cell"
    if tag == "custom-meta":
        return "container", "front_block"
    if tag == "contrib":
        return "container", "contrib"
    if tag == "string-name":
        return "a", "author_name"
    if tag == "kwd-group":
        return "a", "keywords"
    if tag in ("verse-group", "verse-line"):
        return "a", "verse"
    if tag == "mixed-citation":
        return "a", "reference"
    if tag == "disp-formula":
        return "a", "equation"
    if tag == "title":
        par = el.getparent().tag
        return "a", {"abstract": "abstract_label", "trans-abstract": "abstract_label", "ref-list": "heading",
                     "fn-group": "heading", "kwd-group": "keywords"}.get(par, "heading")
    if tag == "p":
        if "abstract" in anc or "trans-abstract" in anc:
            return "a", "abstract"
        if "author-notes" in anc:
            return "a", "author_note"
        if "table-wrap-foot" in anc:
            return "a", "table_note"
        if "fn" in anc:
            fg = next((a for a in el.iterancestors("fn-group")), None)
            return "a", "endnote" if fg is not None and fg.get("content-type") == "endnotes" else "footnote"
        if "fig" in anc and ct in ("figure-note", "source"):
            return "a", "figure_note"
        if "caption" in anc:
            return "a", "caption"
        if "boxed-text" in anc:
            return "a", "boxed_text"
        if "disp-quote" in anc:
            return "a", "quote"
        if "list-item" in anc:
            return "a", "list_item"
        if "ack" in anc:
            return "a", "acknowledgements"
        if "app" in anc and ct != "byline":
            return "a", "appendix"
        if ct == "byline":
            return "container", "byline_in_text"
        if ct == "abstract":
            return "b", "abstract"                   # an abstract left in the body
        if ct == "keywords":
            return "b", "keywords"                   # a keywords line left in the body
        if ct == "other":
            return "b", "other"
        if ct == "caption":
            return "a", "caption"                    # a caption block not tied to a figure: still a caption
        return "a", "paragraph"
    return "b", f"unexpected:{tag}"


# ALTO TextBlocks without a JATS element: what the masters say they are
REGION = {"pageHeader": ("c", "running_head"), "pageFooter": ("c", "running_foot"),
          "pageNumber": ("c", "page_number"), "otherArticle": ("c", "other_article"),
          "ornament": ("c", "ornament"), "pictureJunk": ("c", "picture_junk"),
          "showThrough": ("c", "show_through"), "formulaInk": ("a", "equation"),
          "pictureText": ("pic", "figure_text"), "noise": ("noise", "noise")}

# ------------------------------------------------------------------------------------------------ JATS values
FRONT_VALUE_FIELDS = ("author_name", "email", "position", "role", "author_id", "affiliation", "author_note",
                      "history_date", "pub_date", "conference", "reviewed_work", "thesis", "original", "keywords",
                      "title", "trans_title", "subtitle", "journal_info", "abstract", "doc_type")


def text_of(el) -> str:
    return " ".join("".join(el.itertext()).split()) if el is not None else ""


def front_values(root) -> list[tuple[str, str]]:
    """Every specific value the JATS front holds as a field, as (field, printed text)."""
    am = root.find("front/article-meta")
    out = []
    if am is None:
        return out
    for c in am.iter("contrib"):
        author = (c.get("contrib-type") or "author") == "author"
        for sn in c.iter("string-name"):
            out.append(("author_name", text_of(sn)))
        for x in c.iter("email"):
            out.append(("email", text_of(x)))
        for x in c.findall("role"):
            out.append(("position" if author else "role", text_of(x)))
        for x in c.findall("contrib-id"):
            out.append(("author_id", text_of(x)))
            if x.get("contrib-id-type") == "orcid" and re.fullmatch(r"[\dX-]{19}", text_of(x)):
                out.append(("author_id", "https://orcid.org/" + text_of(x)))   # the printed link form
                out.append(("author_id", "https://orcid.org/" + text_of(x).replace("-", " ")))   # «0000 - 0002 -…»
        for x in c.iter("phone"):                    # experiment 65 homes (absent from earlier masters)
            out.append(("phone_address", text_of(x)))
        for x in c.iter("uri"):
            out.append(("doi_url", text_of(x)))
        for a in c.findall("aff"):
            out.append(("affiliation", text_of(a)))
            for x in a:                              # each tagged part too: an assembled aff (v3.5b parts) is
                if isinstance(x.tag, str) and x.tag in ("institution", "country", "addr-line", "email"):
                    out.append(("email" if x.tag == "email" else "affiliation", text_of(x)))   # not in print order
    for fn in am.iter("fn"):
        if "author-notes" in _anc(fn):
            out.append(("author_note", text_of(fn)))
    for d in am.iter("date"):
        out.append(("history_date", text_of(d.find("string-date")) or text_of(d)))
    for d in am.findall("pub-date"):
        if d.find("string-date") is not None:
            out.append(("pub_date", text_of(d.find("string-date"))))
    for cm in am.iter("custom-meta"):
        nm = (cm.findtext("meta-name") or "").strip()
        if nm == "printed-date":
            out.append(("pub_date", text_of(cm.find("meta-value"))))
        elif nm == "printed-journal":
            out.append(("journal_info", text_of(cm.find("meta-value"))))
        elif nm == "series-part":
            out.append(("title", text_of(cm.find("meta-value")).split(" (series:")[0]))
    for x in am.iter("conf-name", "conf-loc", "conf-date"):
        out.append(("conference", text_of(x)))
    for pr in am.findall("product"):
        out.append(("thesis" if pr.get("product-type") == "thesis" else "reviewed_work", text_of(pr)))
        for x in pr:
            out.append(("thesis" if pr.get("product-type") == "thesis" else "reviewed_work", text_of(x)))
    for ra in am.findall("related-article"):
        for x in ra:
            out.append(("original", text_of(x)))
    for kg in am.iter("kwd-group"):
        if kg.get("specific-use") == "catalogue":
            continue
        for x in kg.findall("kwd"):
            out.append(("keywords", text_of(x)))
        if kg.find("title") is not None:
            out.append(("keywords", text_of(kg.find("title"))))
    for tag, f in (("article-title", "title"), ("alt-title", "title"), ("subtitle", "subtitle"),
                   ("trans-title", "trans_title"), ("trans-subtitle", "trans_title")):
        for x in am.iter(tag):
            out.append((f, text_of(x)))
    jm = root.find("front/journal-meta")
    if jm is not None:
        for x in jm.iter("journal-title"):
            out.append(("journal_info", text_of(x)))
    for tag in ("volume", "issue"):
        for x in am.findall(tag):
            if x.get("content-type") != "catalogue" and len(fold(text_of(x))) >= 3:
                out.append(("journal_info", text_of(x)))
    for ab in am.iter("abstract", "trans-abstract"):
        for p in ab.iter("p", "title"):
            out.append(("abstract", text_of(p)))
    # experiment 65 homes (leaks43; none of them is in an earlier master, so earlier results are unchanged)
    for x in am.findall("article-id"):
        if x.get("pub-id-type") == "doi":
            out += [("article_doi", text_of(x)), ("article_doi", "https://doi.org/" + text_of(x)),
                    ("article_doi", re.sub(r"[-/]", " ", text_of(x)))]       # «10.29343 / 1 - 81 - 1» as printed
    for x in am.findall("email"):
        out.append(("email", text_of(x)))
    for x in am.findall("ext-link") + am.findall("uri"):
        f = "author_id" if x.get("ext-link-type") == "orcid" else "doi_url"
        out.append((f, text_of(x)))
        if x.get("{http://www.w3.org/1999/xlink}href"):
            out.append((f, x.get("{http://www.w3.org/1999/xlink}href")))
        if f == "author_id":
            out.append((f, "https://orcid.org/" + text_of(x).replace("-", " ")))
    for sg in am.iter("subj-group"):
        if sg.get("subj-group-type") == "heading":
            out += [("journal_section", text_of(x)) for x in sg.findall("subject")]
    pm = am.find("permissions")
    if pm is not None:
        out += [("license", text_of(x)) for x in pm if isinstance(x.tag, str)]
    for cm in am.iter("custom-meta"):
        nm = (cm.findtext("meta-name") or "").strip()
        if nm in ("how-to-cite", "signature"):
            out.append((nm.replace("-", "_"), text_of(cm.find("meta-value"))))
    if jm is not None:
        for x in jm.findall("issn"):
            if x.get("specific-use") == "printed":
                out.append(("journal_info", text_of(x)))
    return [(f, v) for f, v in out if toks(v)]


# ------------------------------------------------------------------------------------------------ detectors
# what a line that fell through most likely is. Order matters: the first hit wins.
EMAIL = re.compile(r"[\w.+-]+@[\w-]+\.[\w.-]+")
ORCID = re.compile(r"\b\d{4}-\d{4}-\d{4}-\d{3}[\dX]\b|orcid", re.I)
CORRESP = re.compile(r"corresponding|correspondance|المراسل|للمراسلة|المؤلف المسؤول", re.I)
PHONE = re.compile(r"(هاتف|جوال|فاكس|ص\s*\.?\s*ب|tel\b|t[ée]l[ée]phone|phone|mobile|fax|p\.?\s?o\.?\s?box|\+\d[\d\s-]{6,})",
                   re.I)
DOI = re.compile(r"\bdoi\b|\b10\.\d{4,}\s*/", re.I)
LICENSE = re.compile(r"(رخصة|المشاع\s+الإبداعي|الوصول\s+المفتوح|licen[cs]e|creative\s*commons|\bcc[\s-]?by\b|copyright|©|حقوق\s+(الطبع|النشر|المؤلف)|"
                     r"جميع\s+الحقوق|all\s+rights)", re.I)
HONORIFIC = re.compile(r"^\W*(?:(?:[أامدذ]\s*[./:]\s*)+|(?:ال|لل|ل)?(?:أستاذة?|استاذة?|دكتورة?|تدكتور|شيخ)|prof\.?|dr\.?|"
                       r"pr\.?|professor)\W*$", re.I)
ROLEPHRASE = re.compile(r"^\W*(بقلم|إعداد|اعداد|عرض|تأليف|تاليف|ترجمة|ترجمه|تحقيق|مراجعة|تقديم|إشراف|اشراف|"
                        r"(prepared|presented|translated|reviewed|supervised|written|edited)?\s*by)\b\W*", re.I)
NOT_NAME = set("of in the and for de du des la le à au et with on at في من على عن إلى الى مع".split())
HISTORY = re.compile(r"(تسلم\s+البحث|تسلم|استلم|أجيز|اجيز|ورد\s+البحث|قدم\s+للنشر|تاريخ\s+(ال)?(استلام|إستلام|الاستلام|ارسال|إرسال|الإرسال|الارسال|تسلم|التسلم|قبول|القبول|النشر|"
                     r"التعديل|التحكيم|المراجعة|الإستقبال|الاستقبال|الورود|التقديم)|استلم|قبل\s+للنشر|مقبول\s+للنشر|"
                     r"received|accepted|revised|published\s+online|available\s+online|reçu|accepté)", re.I)
POSITION = re.compile(
    r"(أستاذ|استاذ|الأستاذ|مدرس|المدرس|محاضر|باحث|باحثة|طالب|طالبة|دكتوراه|ماجستير|عميد|وكيل|رئيس\s+قسم|معيد|خبير|"
    r"مستشار|مدير|مديرة|مفتش|موجه|موجهة|معلم|معلمة|أخصائي|اخصائي|عضو\s+هيئة|الأمين\s+العام|أمين\s+عام|رئيس|نائب|professor|prof\.|lecturer|assistant|"
    r"associate|researcher|ph\.?\s?d|student|doctoral|doctorant|dean|head\s+of|teacher|instructor|ma[iî]tre|\bprof\b|"
    r"docteur|chercheur|chercheuse|enseignant|consultant|director|inspector|supervisor|specialist|candidate)", re.I)
AFFIL = re.compile(
    r"(جامعة|الجامعة|كلية|قسم|معهد|المعهد|مركز|المركز|وزارة|أكاديمية|اكاديمية|مدرسة|مديرية|إدارة|ادارة|مختبر|"
    r"university|universit[ée]|faculty|facult[ée]|college|coll[eè]ge|department|d[ée]partement|dept\b|institute|"
    r"institut|school|[ée]cole|cent(er|re)|ministry|minist[eè]re|academy|acad[ée]mie|laborator|laboratoire|"
    r"directorate|office\s+of)", re.I)
COUNTRY = re.compile(
    r"(المملكة|مصر|المغرب|الجزائر|تونس|ليبيا|السودان|الأردن|الاردن|سوريا|سورية|لبنان|العراق|فلسطين|الكويت|السعودية|"
    r"قطر|البحرين|الإمارات|الامارات|عمان|سلطنة|اليمن|موريتانيا|morocco|maroc|egypt|[ée]gypte|algeria|alg[ée]rie|"
    r"tunisia|tunisie|libya|sudan|jordan|syria|lebanon|iraq|palestine|kuwait|saudi|qatar|bahrain|emirates|oman|"
    r"yemen|mauritania|france|\busa\b|\buk\b|\bksa\b|\buae\b|united)", re.I)
JOURNAL = re.compile(r"(issn|isbn|المجلد|العدد|مجلة|vol\.?|volume|issue|no\.\s*\d|doi|pp\.)", re.I)
URL = re.compile(r"(https?://|www\.|doi\.org|10\.\d{4,}/)", re.I)
FUNDING = re.compile(r"(شكر|تمويل|ممول|منحة|بدعم|funded|funding|grant|acknowledg|remerciement)", re.I)
KEYWORDS = re.compile(r"(الكلمات\s+المفتاحية|كلمات\s+مفتاحية|الكلمات\s+الدالة|keywords|key\s+words|mots[\s-]+cl[ée]s)", re.I)
ABSTRACT = re.compile(r"^\W*(الملخص|ملخص|المستخلص|مستخلص|abstract|summary|r[ée]sum[ée])\b", re.I)
DATE = re.compile(r"(\b\d{1,2}\s*[/.-]\s*\d{1,2}\s*[/.-]\s*\d{2,4}\b|\b(19|20|13|14)\d\d\s*(م|هـ|ه)?\b)")
TABLE_NOTE = re.compile(r"(دال[ةه]?\s+عند\s+مستوى|دال[ةه]?\s+عند|\bp\s*[<>≤]\s*0?[.,]\d|^\W*(المصدر|source)\s*:)", re.I)
SECTION = re.compile(r"^\W*(المقالات|البحوث\s+والدراسات|بحوث\s+ودراسات|البحوث|الدراسات|دراسات|بحوث|مقالات|ملف\s+العدد|افتتاحية\s+العدد|"
                     r"الافتتاحية|كلمة\s+العدد|عرض\s+كتاب|عروض\s+الكتب|قراءات|تقارير|research\s+papers|articles|editorial|"
                     r"book\s+reviews?)\W*$", re.I)
DIGITS = str.maketrans({**{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})
LATIN = re.compile(r"[A-Za-zÀ-ɏ]")
ARABIC = re.compile(r"[؀-ۿ]")


def script(s: str) -> str:
    a, l = len(ARABIC.findall(s or "")), len(LATIN.findall(s or ""))
    return "ar" if a >= l and a else ("lat" if l else "none")


def detect(text: str, where: str = "", page: int = 1) -> str:
    """The field a line of generic / dropped text should have gone to (best guess from its words)."""
    t = " ".join(TASHKEEL.sub("", unicodedata.normalize("NFKC", str(text or ""))).translate(DIGITS).split())
    if not t:
        return "unclassified"
    if SECTION.match(t):
        return "journal_section"
    if HONORIFIC.match(t):
        return "honorific"
    if ROLEPHRASE.match(t) and len(t.split()) <= 3:
        return "role"
    if TABLE_NOTE.search(t):
        return "table_note"
    if where == "other" and page > 2 and not HISTORY.search(t):
        return "other"                         # body text Gemini called «other»: no front field to expect
    if EMAIL.search(t):
        return "email"
    if DOI.search(t):
        return "article_doi"
    if LICENSE.search(t):
        return "license"
    if ORCID.search(t):
        return "author_id"
    if CORRESP.search(t):
        return "corresp"
    if KEYWORDS.search(t):
        return "keywords"
    if ABSTRACT.search(t):
        return "abstract"
    if HISTORY.search(t):
        return "history_date"
    if PHONE.search(t):
        return "phone_address"
    if URL.search(t):
        return "doi_url"
    pos, aff = POSITION.search(t), AFFIL.search(t)
    if pos and (not aff or pos.start() < aff.start()):
        return "position"
    if aff or (COUNTRY.search(t) and len(t.split()) <= 6):
        return "affiliation"
    if JOURNAL.search(t) and len(t.split()) <= 12:
        return "journal_info"
    if FUNDING.search(t):
        return "funding_ack"
    if where in ("front_block", "contrib", "byline_in_text") and len(t.split()) <= 5 and not DATE.search(t) \
            and not (set(toks(t)) & NOT_NAME):
        return "author_name"
    if where == "byline_in_text" and DATE.search(t):
        return "signature"                     # the place and date under a closing signature
    if DATE.search(t) and len(t.split()) <= 8:
        return "date"
    if where == "byline_in_text":
        return "signature"
    return "unclassified"


# label words that sit beside a value without being part of it («البريد الإلكتروني:»، «Email:»، «تاريخ الاستلام:»)
LABELS = set(toks("البريد الإلكتروني الالكتروني الإلكتروني البريد بريد email e-mail mail courriel tel tél phone "
                  "هاتف فاكس fax تاريخ الاستلام القبول النشر الإرسال التحكيم received accepted revised published "
                  "الكلمات المفتاحية keywords key words mots clés الملخص abstract ملخص و and et by بقلم إعداد اعداد "
                  "الاستلام التعديل النهائي إجازة اجازة soumission réception acceptation date de "
                  "تم تسلم استلام البحث وأجيز اجيز أجيز للنشر بتاريخ تسليم قبول ارسال إرسال المقال نشر "
                  "publication reçu accepté submitted submission استلم قبل الإيداع الايداع الإرسال الارسال ارسل "
                  "التسلم التسليم تسلم article history available online revised reçu le accepté le "
                  "mobile number phone tel fax هاتف جوال سنة بلد مكان عدد الصفحات ورد للمجلة الناشر year سلم "
                  "تأليف د أ م ا dr prof pr mr mrs ms mme"
                  " doi orcid id"))            # experiment 65: labels beside the DOI / ORCID it stores

# ------------------------------------------------------------------------------------------------ what each prompt asks
ALL = {"v2", "v3", "v3.1", "v3.2", "v3.3", "v3.4", "v3.5", "v3.5b"}
V3 = ALL - {"v2"}
V35 = {"v3.5", "v3.5b"}
ASKED = {
    "title": ALL, "subtitle": ALL, "trans_title": V3, "author_name": ALL, "affiliation": ALL, "aff_parts": V3,
    "faculty": V35, "email": ALL, "author_id": V35, "corresp": V35, "author_note": V35, "history_date": V3,
    "abstract": ALL, "keywords": ALL, "journal_info": ALL, "conference": V35, "thesis": V35, "reviewed_work": V35,
    "original": V35, "doc_type": V35,
    # role: "a phrase printed with it such as بقلم، تأليف، ضبطها وشرحها، ترجمة، by goes in role" (v2+): the role
    # phrase, not the author's post or rank, which no version names
    "role": ALL, "position": set(), "phone_address": set(), "doi_url": set(), "funding_ack": set(),
    "article_doi": set(), "license": set(), "honorific": ALL, "journal_section": set(), "table_note": V35,   # honorific: part of the printed name (v2+)
    "signature": ALL,          # byline: "author names, affiliations, dates and places ... signed at the end"
    "date": set(), "unclassified": set(), "other": set(),
}

LEAK_KINDS = ("mapping", "not_asked", "gemini_missed")
