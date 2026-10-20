"""Experiment 47: shared helpers for the platform v2 builder — paths, experiment 46's folding and similarity
(imported, not copied), the search stemmer, Arabic name parts, both calendars, ISSN check digits, the Quran's
sura table (structure only), and the schema loader (schema47.sql plus the builder's few documented deviations)."""
from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E46 = REPO / "experiments" / "46_platform_db"
sys.path.insert(0, str(E46))
from common46 import fold, key, latin_key, ratio, to_int, tokset, year_of  # noqa: E402,F401

E43 = REPO / "experiments" / "43_rehearsal"
OUT43 = E43 / "out"
DATA = Path.home() / "data" / "platform_v2"
DB = DATA / "platform_v2.db"
V46 = Path.home() / "data" / "platform" / "platform.db"
MARC = Path.home() / "data" / "marc" / "marc.db"
SCHEMA = HERE / "schema47.sql"

# ------------------------------------------------------------------ schema
# Deviations from schema47.sql, applied as text substitutions when the db is created (each one in README.md):
DEVIATIONS = [
    # 1. mention_id is built on Azure word numbers so that it is the SAME in every run's version of an article; with
    #    all versions in the db it cannot be unique on its own. Unique per version instead.
    ("mention_id TEXT NOT NULL UNIQUE,", "mention_id TEXT NOT NULL,"),
    ("CREATE INDEX cm_version ON citation_mentions(version_id, reading_ord);",
     "CREATE INDEX cm_version ON citation_mentions(version_id, reading_ord);\n"
     "CREATE UNIQUE INDEX cm_mention_id ON citation_mentions(version_id, mention_id);\n"
     "CREATE INDEX cm_mention_key ON citation_mentions(mention_id);"),
]
EXTRA_SQL = """
-- builder report (not part of the target design): v46 table -> v2 count, and why they differ
CREATE TABLE IF NOT EXISTS reconciliation_v46 (
  v46_table TEXT NOT NULL, v46_rows INTEGER, v2_table TEXT NOT NULL, v2_rows INTEGER, v2_query TEXT,
  same INTEGER, why TEXT, PRIMARY KEY (v46_table, v2_table)
);
"""


def schema_sql() -> str:
    s = SCHEMA.read_text(encoding="utf-8")
    for a, b in DEVIATIONS:
        assert a in s, a
        s = s.replace(a, b)
    return s + EXTRA_SQL


def connect(path: Path = DB, ro: bool = False) -> sqlite3.Connection:
    if ro:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        new = not path.exists()
        con = sqlite3.connect(path)
        con.execute("PRAGMA journal_mode=WAL")
        if new or not con.execute("SELECT 1 FROM sqlite_master WHERE name = 'versions'").fetchone():
            con.executescript(schema_sql())
        con.executescript(EXTRA_SQL)
        # declared, not enforced while loading (children are written before parents); checked with
        # PRAGMA foreign_key_check after every load
        con.execute("PRAGMA foreign_keys=OFF")
    con.row_factory = sqlite3.Row
    return con


def marc() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def now() -> str:
    return time.strftime("%Y-%m-%d %H:%M:%S")


def sha_file(p: Path) -> str | None:
    if not p.exists():
        return None
    return hashlib.sha1(p.read_bytes()).hexdigest()[:16]


def sha_files(paths) -> str:
    h = hashlib.sha1()
    for p in paths:
        if p and Path(p).exists():
            h.update(Path(p).name.encode())
            h.update(Path(p).read_bytes())
    return h.hexdigest()[:16]


def jdump(x) -> str | None:
    if x is None:
        return None
    return x if isinstance(x, str) else json.dumps(x, ensure_ascii=False)


def insert(con, table, rows, mode="INSERT OR REPLACE"):
    rows = list(rows)
    if not rows:
        return 0
    cols = list(rows[0])
    con.executemany(f"{mode} INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [tuple(r.get(c) for c in cols) for r in rows])
    return len(rows)


def script(s: str | None) -> str | None:
    if not s:
        return None
    ar = len(re.findall("[؀-ۿ]", s))
    la = len(re.findall("[A-Za-zÀ-ɏ]", s))
    if not ar and not la:
        return None
    return "Arab" if ar >= la else "Latn"


# ------------------------------------------------------------------ search forms
_CLITIC = re.compile(r"^(?:و|ف)?(?:بال|كال|لل|ال|ب|ك|ل)?")


def stem_token(t: str) -> str:
    """Light Arabic clitic stripping (no model): و/ف, then بال/كال/لل/ال/ب/ك/ل, keeping at least 3 letters."""
    if not re.search("[؀-ۿ]", t) or len(t) <= 3:
        return t
    for pre in ("وبال", "وكال", "فبال", "ولل", "فلل", "وال", "فال", "بال", "كال", "لل", "ال", "و", "ف"):
        if t.startswith(pre) and len(t) - len(pre) >= 3:
            return t[len(pre):]
    return t


def stemmed(s: str | None) -> str:
    return " ".join(stem_token(t) for t in fold(s).split())


# ------------------------------------------------------------------ calendars
def hijri_to_greg(h: int) -> int:
    return int(round(h * 0.970229 + 621.5643))


def greg_to_hijri(g: int) -> int:
    return int(round((g - 621.5643) / 0.970229))


HIJRI_MARK = re.compile(r"(\d{3,4})\s*(?:هـ|ه\b|ھ|AH\b|H\b|هجري|للهجرة)")


def calendar_of(printed: str | None, year: int | None) -> str | None:
    """'hijri' when the print marks the year as hijri (هـ) or it is below 1500 (no gregorian scholarly year is)."""
    if not year:
        return None
    f = fold(printed or "")
    if re.search(r"\d\s*(هـ|ه\b|ھ)", f) or "هجري" in f or (year and year < 1500):
        return "hijri"
    return "gregorian"


# ------------------------------------------------------------------ ISSN
def issn_clean(raw: str | None) -> tuple[str | None, int | None]:
    if not raw:
        return None, None
    s = re.sub(r"[^0-9Xx]", "", fold(raw)).upper()
    if len(s) != 8:
        return None, 0
    tot = sum(int(c) * w for c, w in zip(s[:7], range(8, 1, -1)))
    chk = (11 - tot % 11) % 11
    ok = (("X" if chk == 10 else str(chk)) == s[7])
    return f"{s[:4]}-{s[4:]}", int(ok)


# ------------------------------------------------------------------ Arabic names
TITLE_RE = re.compile(r"^\s*(أ\s*\.\s*م\s*\.\s*د\s*\.?|ا\s*\.\s*م\s*\.\s*د\s*\.?|م\s*\.\s*م\s*\.?|أ\s*\.\s*د\s*\.?|"
                      r"ا\s*\.\s*د\s*\.?|أ\s*\.\s*م\s*\.?|د\s*\.|د\s*/|د\s+(?=\S)|الدكتورة|الدكتور|الأستاذة|الأستاذ|"
                      r"الاستاذة|الاستاذ|الشيخ|العلامة|المستشار|السيد|السيدة|أ\s*/|أ\s*\.|م\s*\.|"
                      r"prof\.?|dr\.?|professor|mr\.?|mrs\.?|ms\.?|pr\.?)\s*", re.I)
LAQAB_HEADS = ("الدين", "الدولة", "الإسلام", "الاسلام", "الملك")


def split_titles(name: str) -> tuple[str, str]:
    """('أ.د.', 'إبراهيم خليل') — titles are kept, not thrown away."""
    s, titles = name or "", []
    for _ in range(4):
        m = TITLE_RE.match(s)
        if not m or m.end() == 0:
            break
        titles.append(" ".join(m.group(0).split()))
        s = s[m.end():]
    return " ".join(titles), s.strip(" .،,/:")


def name_parts(name: str) -> dict:
    """Heuristic split of an Arabic name into ism, nasab, nisba, laqab, kunya, family, shuhra (Latin names: family
    = last word). Catalogue headings «surname، given» are turned round first."""
    titles, s = split_titles(name)
    out = dict(titles=titles or None, ism=None, nasab=None, nisba=None, laqab=None, kunya=None, family=None,
               shuhra=None)
    if not s:
        return out
    if re.search("[،,]", s):
        a, b = re.split(r"\s*[،,]\s*", s, maxsplit=1)
        if b and not re.search(r"\d", b):
            s = f"{b} {a}"
    toks = s.split()
    if not re.search("[؀-ۿ]", s):
        out["family"] = toks[-1] if len(toks) > 1 else None
        out["ism"] = " ".join(toks[:-1]) if len(toks) > 1 else toks[0]
        return out
    i = 0
    if toks and toks[0] in ("ابن", "إبن") and len(toks) >= 2:
        out["shuhra"] = " ".join(toks[:2])
        i = 2
    rest = []
    while i < len(toks):
        t = toks[i]
        if t in ("أبو", "ابو", "أبي", "ابي", "أبا", "أم", "ام") and i + 1 < len(toks):
            j = i + 2 if toks[i + 1] in ("عبد",) and i + 2 < len(toks) else i + 1
            out["kunya"] = (out["kunya"] + " " if out["kunya"] else "") + " ".join(toks[i:j + 1])
            i = j + 1
            continue
        if t in ("بن", "ابن", "بنت", "إبن") and i + 1 < len(toks) and (rest or out["kunya"]):
            j = i + 2 if toks[i + 1] in ("عبد",) and i + 2 < len(toks) else i + 1
            out["nasab"] = (out["nasab"] + " " if out["nasab"] else "") + " ".join(toks[i:j + 1])
            i = j + 1
            continue
        if i + 1 < len(toks) and toks[i + 1] in LAQAB_HEADS:
            out["laqab"] = (out["laqab"] + " " if out["laqab"] else "") + f"{t} {toks[i + 1]}"
            i += 2
            continue
        rest.append(t)
        i += 1
    nis = [t for t in rest[1:] if re.match(r"^ال\S+ي$", t)]
    if len(rest) == 1 and re.match(r"^ال\S+ي$", rest[0]) and (out["kunya"] or out["laqab"] or out["shuhra"]):
        nis = rest[:]
    if nis:
        out["nisba"] = " ".join(nis)
    core = [t for t in rest if t not in nis] if len(nis) == len(rest) else rest
    if core and core is not rest or (core and len(nis) < len(rest)):
        if core[0] == "عبد" and len(core) > 1:
            out["ism"] = " ".join(core[:2])
        else:
            out["ism"] = core[0]
        tail = core[2:] if core[0] == "عبد" else core[1:]
        if tail:
            out["family"] = tail[-1]
    return out


def name_key(name: str | None) -> str:
    """Folded name without titles or spaces (for matching; never an identity)."""
    _, s = split_titles(name or "")
    k = key(s) if re.search("[؀-ۿ]", s) else latin_key(s)
    return k.replace(" ", "")


# ------------------------------------------------------------------ the Quran's structure (no text: see README)
SURAS = ("الفاتحة البقرة آل_عمران النساء المائدة الأنعام الأعراف الأنفال التوبة يونس هود يوسف الرعد إبراهيم الحجر "
         "النحل الإسراء الكهف مريم طه الأنبياء الحج المؤمنون النور الفرقان الشعراء النمل القصص العنكبوت الروم لقمان "
         "السجدة الأحزاب سبأ فاطر يس الصافات ص الزمر غافر فصلت الشورى الزخرف الدخان الجاثية الأحقاف محمد الفتح "
         "الحجرات ق الذاريات الطور النجم القمر الرحمن الواقعة الحديد المجادلة الحشر الممتحنة الصف الجمعة المنافقون "
         "التغابن الطلاق التحريم الملك القلم الحاقة المعارج نوح الجن المزمل المدثر القيامة الإنسان المرسلات النبأ "
         "النازعات عبس التكوير الانفطار المطففين الانشقاق البروج الطارق الأعلى الغاشية الفجر البلد الشمس الليل الضحى "
         "الشرح التين العلق القدر البينة الزلزلة العاديات القارعة التكاثر العصر الهمزة الفيل قريش الماعون الكوثر "
         "الكافرون النصر المسد الإخلاص الفلق الناس").split()
SURAS = [s.replace("_", " ") for s in SURAS]
AYAT = [7, 286, 200, 176, 120, 165, 206, 75, 129, 109, 123, 111, 43, 52, 99, 128, 111, 110, 98, 135, 112, 78, 118, 64,
        77, 227, 93, 88, 69, 60, 34, 30, 73, 54, 45, 83, 182, 88, 75, 85, 54, 53, 89, 59, 37, 35, 38, 29, 18, 45, 60,
        49, 62, 55, 78, 96, 29, 22, 24, 13, 14, 11, 11, 18, 12, 12, 30, 52, 52, 44, 28, 28, 20, 56, 40, 31, 50, 40,
        46, 42, 29, 19, 36, 25, 22, 17, 19, 26, 30, 20, 15, 21, 11, 8, 8, 19, 5, 8, 8, 11, 11, 8, 3, 9, 5, 4, 7, 3, 6,
        3, 5, 4, 5, 6]
assert len(SURAS) == 114 and len(AYAT) == 114 and sum(AYAT) == 6236, (len(SURAS), len(AYAT), sum(AYAT))
SURA_KEYS = {}
for _i, _s in enumerate(SURAS, 1):
    _k = key(_s)
    SURA_KEYS[_k] = _i
    SURA_KEYS[re.sub(r"^ال", "", _k)] = _i
SURA_KEYS.update({key("الاسراء"): 17, key("بني إسرائيل"): 17, key("المؤمن"): 40, key("حم السجدة"): 41,
                  key("الدهر"): 76, key("الإنشراح"): 94, key("الانشراح"): 94, key("اقرأ"): 96, key("تبارك"): 67,
                  key("براءة"): 9, key("عم"): 78, key("الأحقاف"): 46, key("لم يكن"): 98, key("التطفيف"): 83})
