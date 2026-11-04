"""Experiment 62: the librarian's comparison tools for cited works — folded titles that forgive misprints, hamza /
alef / ya / taa-marbuta variants, the article «ال» and clitics, edition and volume marks, the author's name taken into
the title («مقدمة ابن خلدون»); author names with death dates; Hijri / Gregorian years.

Pure functions, no database. Used by cands62 (blocking), judge62 (the rule proposal) and tools62 (the seen list).
"""
from __future__ import annotations

import re
import sys
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "46_platform_db"))
sys.path.insert(0, str(HERE.parent / "47_platform_v2"))
from common46 import fold, key, latin_key  # noqa: E402

AR = re.compile(r"[؀-ۿ]")


def release() -> Path:
    """The Desk release this pass reads (read-only). Pinned so a newer release does not shift the numbers."""
    import os
    return Path(os.environ.get("LIBRARIAN62_RELEASE",
                               str(Path.home() / "data/desk/releases/R20261023T005909.db")))
LAT = re.compile(r"[A-Za-zÀ-ɏ]")
# marks that never make a title: edition, volume, part, editor's work, numbers, ordinals
MARK = {"ط", "طبعه", "الطبعه", "طبعة", "ج", "جزء", "الجزء", "مج", "مجلد", "المجلد", "مجلدات", "اجزاء", "vol", "volume",
        "tome", "t", "ed", "eds", "edition", "تحقيق", "تح", "تحق", "قسم", "القسم", "part", "teil", "band", "bd", "اول",
        "ثاني", "ثالث", "الاول", "الثاني", "الثالث", "الرابع", "الخامس", "ص", "p", "pp", "no", "n", "ع", "عدد", "العدد",
        "ed", "rev", "2nd", "3rd", "1st", "th", "nd", "rd", "st"}
AR_STOP = {"في", "من", "على", "عن", "الى", "او", "و", "ثم", "مع", "بين", "حول", "نحو", "لدى", "لدي", "عند", "ذلك", "هذه",
           "هذا", "التي", "الذي", "كما", "ما", "لا", "ب", "ل", "ك"}
LAT_STOP = set("the of and in on for a an to with by at from al el la le les de des du et en un une der die und das "
               "its as is are dans sur pour au aux".split())
# classical honorifics and name particles that are not distinctive
NAME_COMMON = set("محمد احمد علي عبد بن ابن ابو ابي ام ال الله حسن حسين محمود مصطفى ابراهيم عمر عثمان يوسف سعيد صالح "
                  "خالد عبدالله عبدالرحمن جمال الدين al el ibn abu bin mohamed mohammed muhammad ahmed ali "
                  "الامام الشيخ الحافظ العلامه الدكتور د دكتور الاستاذ ا م".split())
NAME_COMMON = NAME_COMMON | {fold(w) for w in NAME_COMMON}
# generic short titles that join across articles only through an author (probe B, rule 5)
GENERIC = {"ديوان", "كتاب", "مغني", "لسان", "تهذيب", "كامل", "خزانه", "مقدمه", "صحيح", "سنن", "مسند", "تفسير", "شرح",
           "اغاني", "بيان", "معجم", "قاموس", "تاريخ", "رساله", "مجموع", "فتاوي", "اصول", "مستدرك", "جامع", "موطا",
           "عقد", "طبقات", "ذخيره", "حماسه", "امالي", "خصائص", "عمده", "مثل", "سيره", "تاج", "اعلام", "وفيات", "منهج",
           "نقد", "شعر", "مقاله", "رسائل", "دراسات", "بحوث", "مقالات", "مذكرات", "proceedings", "report", "handbook",
           "دليل", "تقرير", "مجله", "journal", "قرار", "قانون", "دستور", "نظام", "لائحه", "statistics"}


def clean_token(t: str) -> str:
    """One title word, folded: the article and clitics off (Arabic), accents off (Latin)."""
    if AR.search(t):
        for pre in ("وبال", "وكال", "فبال", "ولل", "فال", "وال", "بال", "كال", "لل", "ال"):
            if t.startswith(pre) and len(t) - len(pre) >= 2:
                t = t[len(pre):]
                break
        else:
            if t.startswith("و") and len(t) >= 5:
                t = t[1:]
        if t in ("ابن", "بن"):
            t = "بن"
        if t.endswith("اء") and len(t) >= 4:      # «الصفاء» / «الصفا», «الوفاء» / «الوفا»
            t = t[:-1]
        return t
    return t


def tokens(title: str | None, drop: set | None = None) -> list[str]:
    """The title's content words, folded and in order (marks, digits and stop words out; `drop` = author words)."""
    s = re.sub(r"\(\s*[0-9٠-٩]+\s*\)", " ", title or "")
    k = key(s) if AR.search(s) else latin_key(s)
    k = re.sub(r"[0-9]+", " ", k)
    out = []
    for w in k.split():
        if w in MARK or w in AR_STOP or w in LAT_STOP:
            continue
        c = clean_token(w)
        if not c or c in MARK or c in AR_STOP or len(c) < 2:
            continue
        if drop and (c in drop or w in drop or re.sub("^ل", "", c) in drop):
            continue
        out.append(c)
    return out


def tkey(title: str | None, drop: set | None = None) -> str:
    return " ".join(tokens(title, drop))


def near(a: str, b: str) -> bool:
    """Two words alike but for one misprinted letter (or ة/ه, ى/ي already folded): edit distance <= 1 for words of
    4+ letters, <= 2 for 9+."""
    if a == b:
        return True
    la, lb = len(a), len(b)
    if min(la, lb) < 4 or abs(la - lb) > 2:
        return False
    lim = 2 if min(la, lb) >= 9 else 1
    return lev(a, b, lim) <= lim


def lev(a: str, b: str, lim: int = 3) -> int:
    if abs(len(a) - len(b)) > lim:
        return lim + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        best = cur[0]
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            best = min(best, cur[j])
        if best > lim:
            return lim + 1
        prev = cur
    return prev[-1]


def fuzzy_overlap(A: list[str], B: list[str]) -> int:
    """Words of A matched to distinct words of B, exact first, then one-letter misprints."""
    pool = list(B)
    n = 0
    rest = []
    for w in A:
        if w in pool:
            pool.remove(w)
            n += 1
        else:
            rest.append(w)
    for w in rest:
        for x in pool:
            if near(w, x):
                pool.remove(x)
                n += 1
                break
    return n


def title_sim(A: list[str], B: list[str]) -> dict:
    """dice (fuzzy word overlap), cover (share of the shorter title's words in the longer), prefix (the shorter
    title is the start of the longer), chars (letter similarity of the joined keys)."""
    if not A or not B:
        return dict(dice=0.0, cover=0.0, prefix=False, chars=0.0, n_short=min(len(A), len(B)))
    o = fuzzy_overlap(A, B) if len(A) <= len(B) else fuzzy_overlap(B, A)
    s, l = (A, B) if len(A) <= len(B) else (B, A)
    pre = len(s) >= 1 and all(near(x, y) for x, y in zip(s, l[:len(s)]))
    return dict(dice=round(2 * o / (len(A) + len(B)), 3), cover=round(o / len(s), 3), prefix=pre,
                chars=round(SequenceMatcher(None, " ".join(A), " ".join(B), autojunk=False).ratio(), 3)
                if (2 * o / (len(A) + len(B))) < 0.6 and len(s) >= 2 else None,
                n_short=len(s))


# ------------------------------------------------------------------ names
def _join_abd(s: str) -> str:
    return re.sub(r"(?:^|(?<=\s))(ابو|عبد)\s+(?=\S)", r"\1", s)


def name_words(printed: str | None) -> set:
    """The distinctive words of a printed name (honorifics, ibn/abu, common given names and death dates out)."""
    s = re.sub(r"\(?\s*(?:ت|توفي|المتوفى|المتوفي|d|died)\s*\.?\s*[0-9٠-٩]{3,4}\s*(?:هـ|ه|م)?\s*\)?", " ", printed or "")
    s = re.sub(r"[0-9٠-٩]+", " ", s)
    k = _join_abd(latin_key(s))
    out = set()
    for w in k.split():
        w2 = re.sub(r"^(لل|ال)", "", w) if AR.search(w) and len(w) > 4 else w
        if len(w2) >= 3 and w not in NAME_COMMON and w2 not in NAME_COMMON:
            out.add(w2)
    return out


TRANSLIT = str.maketrans({"ā": "a", "ī": "i", "ū": "u", "ḥ": "h", "ṣ": "s", "ḍ": "d", "ṭ": "t", "ẓ": "z", "ʿ": "",
                          "ʾ": "", "'": "", "’": "", "‘": ""})
# a rough Arabic -> Latin consonant skeleton, to compare «جاكندوف» with Jackendoff (only as a hint)
AR2LAT = {"ا": "", "ب": "b", "ت": "t", "ث": "th", "ج": "j", "ح": "h", "خ": "kh", "د": "d", "ذ": "dh", "ر": "r",
          "ز": "z", "س": "s", "ش": "sh", "ص": "s", "ض": "d", "ط": "t", "ظ": "z", "ع": "", "غ": "gh", "ف": "f",
          "ق": "q", "ك": "k", "ل": "l", "م": "m", "ن": "n", "ه": "h", "و": "", "ي": "", "ء": "", "پ": "p", "ڤ": "v",
          "گ": "g"}


def skeleton(w: str) -> str:
    """Consonant skeleton of a name word in either script (vowels out): «بياجيه» ~ Piaget → b j / p g: rough."""
    if AR.search(w):
        s = "".join(AR2LAT.get(c, "") for c in w)
    else:
        s = re.sub(r"[aeiouyw]", "", unicodedata.normalize("NFKD", w.lower().translate(TRANSLIT))
                   .encode("ascii", "ignore").decode())
    s = s.replace("ph", "f").replace("p", "b").replace("v", "f").replace("c", "k").replace("q", "k").replace("g", "j")
    s = s.replace("x", "ks").replace("kh", "k").replace("sh", "s").replace("th", "t").replace("dh", "d")
    return re.sub(r"(.)\1+", r"\1", re.sub(r"[^a-z]", "", s))


def author_relation(A: set, B: set, SA: set | None = None, SB: set | None = None) -> str:
    """agree (a surname of one side is a name word of the other, one misprinted letter forgiven) | translit (a
    surname alike across scripts, by consonant skeleton) | weak (only given names shared) | unknown (a side prints
    no author) | contradict. SA / SB are the surname words (default: all words)."""
    if not A or not B:
        return "unknown"
    SA = SA if SA else A
    SB = SB if SB else B

    def meets(S, X):    # a name one letter off only when both are 5+ letters («امدي» is not «حمدي»)
        return bool(S & X) or any(near(a, b) for a in S for b in X if min(len(a), len(b)) >= 5)
    if meets(SA, B) or meets(SB, A):
        return "agree"
    la = {skeleton(a) for a in SA if not AR.search(a)}
    lb = {skeleton(b) for b in SB if not AR.search(b)}
    ra = {skeleton(a) for a in SA if AR.search(a)}
    rb = {skeleton(b) for b in SB if AR.search(b)}
    for L, R_ in ((la, rb), (lb, ra)):
        for x in L:
            for y in R_:
                if len(x) >= 3 and len(y) >= 3 and (x == y or SequenceMatcher(None, x, y).ratio() >= 0.8):
                    return "translit"
    if meets(A, B):
        return "weak"
    return "contradict"


# ------------------------------------------------------------------ years
def years_of(printed: str | None) -> set:
    """Every year printed, both calendars: «1414هـ» -> {1414h, 1994g}; «2003» -> {2003g, 1424h}."""
    from common47 import greg_to_hijri, hijri_to_greg
    out = set()
    f = fold(printed or "")
    for m in re.finditer(r"(?<![0-9])([0-9]{3,4})(?![0-9])\s*(هـ|ه\b|م\b)?", f):
        y = int(m.group(1))
        if y < 100 or y > 2100:
            continue
        hij = m.group(2) in ("هـ", "ه") or y < 1500
        if hij:
            out |= {("h", y), ("g", hijri_to_greg(y))}
        else:
            out |= {("g", y), ("h", greg_to_hijri(y))}
    return out


def year_relation(A: set, B: set) -> str:
    """same (a printed year agrees, either calendar, +-1) | differ | unknown."""
    if not A or not B:
        return "unknown"
    for ca, ya in A:
        for cb, yb in B:
            if ca == cb and abs(ya - yb) <= 1:
                return "same"
    return "differ"


def script_of(s: str | None) -> str:
    if AR.search(s or ""):
        return "ar"
    if LAT.search(s or ""):
        return "lat"
    return "?"
