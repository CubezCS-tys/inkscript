"""Normalisations and error rates used throughout experiment 33.

faithful: what a careful reader of the print would type. NFKC (presentation forms -> letters), no tatweel, one kind
          of digit (Arabic-Indic, Persian and Western digits are the same number; born-digital PDFs often store Western
          codes for Arabic-Indic glyphs), Persian code points that print like Arabic letters folded to them (ی -> ى
          at the end of a word, ي elsewhere; ک -> ك; ھ -> ه), single spaces. Diacritics, hamza forms, ى/ي, ة/ه and punctuation are kept.
search:   what search needs: faithful, then no diacritics, hamza seats folded (أ إ آ ٱ -> ا, ؤ -> و, ئ -> ي), ى -> ي,
          ة -> ه, Persian ی/ک -> ي/ك, punctuation dropped.
"""
import re, unicodedata
from rapidfuzz.distance import Levenshtein

DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")
HARAKAT = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ئ": "ي", "ى": "ي", "ة": "ه", "ی": "ي", "ک": "ك",
                      "ھ": "ه", "ۀ": "ه", "ے": "ي"})
PUNCT = re.compile(r"[^\w\s]|_", re.U)


def faithful(s: str) -> str:
    s = unicodedata.normalize("NFKC", s or "").replace("ـ", "").translate(DIGITS)
    s = re.sub(r"[​-‏‪-‮⁦-⁩﻿]", "", s)
    # Persian letters that print exactly like Arabic ones (typed on a Persian keyboard): yeh dotless at the end of a
    # word, dotted elsewhere; keheh as kaf; heh doachashmee as heh
    s = re.sub("ی(?![ء-يٮ-ۓ])", "ى", s).replace("ی", "ي")
    s = s.replace("ک", "ك").replace("ھ", "ه")
    return re.sub(r"\s+", " ", s).strip()


def search(s: str) -> str:
    s = HARAKAT.sub("", faithful(s)).translate(FOLD)
    s = PUNCT.sub(" ", s)
    return re.sub(r"\s+", " ", s).strip()


NORMS = {"faithful": faithful, "search": search}


def char_edits(gold: str, pred: str) -> int:
    return Levenshtein.distance(gold, pred)


def word_edits(gold: str, pred: str) -> int:
    return Levenshtein.distance(gold.split(), pred.split())


def score(gold: str, pred: str, norm: str) -> dict:
    """Edits and lengths for one line under one normalisation (sum these, then divide)."""
    f = NORMS[norm]; g, p = f(gold), f(pred)
    return dict(ce=char_edits(g, p), cn=len(g), we=word_edits(g, p), wn=len(g.split()))


def is_arabic_line(s: str) -> bool:
    ar = len(re.findall(r"[؀-ۿ]", s)); lat = len(re.findall(r"[A-Za-zÀ-ɏ]", s))
    return ar > 0 and ar >= 2 * lat


def vowelled(s: str) -> bool:
    letters = len(re.findall(r"[ء-ي]", s)); marks = len(re.findall(r"[ً-ْ]", s))
    return marks >= 3 and marks >= 0.08 * max(letters, 1)
