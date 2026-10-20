"""Experiment 46: shared helpers — paths, Arabic folding (the same search form as experiment 45's marc.db), text
similarity, numbers in Arabic-Indic digits."""
from __future__ import annotations

import re
import sqlite3
import unicodedata
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
E43 = REPO / "experiments" / "43_rehearsal"
OUT43 = E43 / "out"
DATA = Path.home() / "data" / "platform"
DB = DATA / "platform.db"
MARC = Path.home() / "data" / "marc" / "marc.db"

# experiment 45's fold (build45.fold), copied so this file does not import the 10 GB builder's module state
_HARAKAT = re.compile("[ؐ-ًؚ-ٰٟۖ-ۭـ‌-‏‪-‮⁦-⁩﻿]")
_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا", "ؤ": "و", "ئ": "ي", "ى": "ي",
                      "ی": "ي", "ة": "ه", "ک": "ك", "ۀ": "ه", "ہ": "ه",
                      "٠": "0", "١": "1", "٢": "2", "٣": "3", "٤": "4", "٥": "5", "٦": "6", "٧": "7", "٨": "8", "٩": "9",
                      "۰": "0", "۱": "1", "۲": "2", "۳": "3", "۴": "4", "۵": "5", "۶": "6", "۷": "7", "۸": "8", "۹": "9"})


def fold(s: str | None) -> str:
    """Search form: no diacritics or tatweel, alef/hamza forms unified, ى→ي, ة→ه, digits ASCII, lower case."""
    return " ".join(_HARAKAT.sub("", s or "").translate(_MAP).lower().split())


_PUNCT = re.compile(r"[^\w\s]", re.U)


def key(s: str | None) -> str:
    """fold + punctuation removed (for comparing titles and names)."""
    t = fold(s)
    t = "".join(ch if not unicodedata.category(ch).startswith("P") and ch not in "«»<>|+=^~`$" else " " for ch in t)
    return " ".join(_PUNCT.sub(" ", t).replace("_", " ").split())


def latin_key(s: str | None) -> str:
    t = unicodedata.normalize("NFKD", s or "")
    t = "".join(c for c in t if not unicodedata.combining(c))
    return key(t)


def ratio(a: str, b: str) -> float:
    if not a or not b:
        return 0.0
    return SequenceMatcher(None, a, b, autojunk=False).ratio()


def tokset(a: str, b: str) -> float:
    """Share of the shorter title's words found in the other (0..1)."""
    A, B = set(a.split()), set(b.split())
    if not A or not B:
        return 0.0
    return len(A & B) / min(len(A), len(B))


def to_int(s: str | None) -> int | None:
    m = re.search(r"\d+", fold(s or ""))
    return int(m.group()) if m else None


def year_of(s: str | None) -> int | None:
    """First 4-digit number in the string (Arabic-Indic digits folded)."""
    m = re.search(r"(?<!\d)(\d{4})(?!\d)", fold(s or ""))
    return int(m.group(1)) if m else None


def connect(path: Path = DB, ro: bool = False) -> sqlite3.Connection:
    if ro:
        con = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(path)
        con.execute("PRAGMA journal_mode=WAL")
        con.execute("PRAGMA foreign_keys=OFF")
    con.row_factory = sqlite3.Row
    return con


def marc() -> sqlite3.Connection:
    con = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con
