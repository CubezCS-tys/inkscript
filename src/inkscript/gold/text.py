"""Text normalisations for scoring, and a fast edit distance (experiment 34).

faithful(s)  what the page prints, in code points: NFC; tatweel removed (layout, not text); whitespace collapsed;
             the presentation forms U+FB50-FEFC decomposed (NFKC on those characters only) so a reader that emits
             them is not punished for the encoding. Vowel marks, hamza and alef forms, ى/ي, ة/ه, digits and
             punctuation all count. A Persian ی or ک counts as an error (it breaks search).
folded(s)    what a search needs: faithful, then vowel marks and Quranic marks removed, alef forms → ا, ؤ → و,
             ئ → ي, ى → ي, ة → ه, Persian look-alikes → Arabic, Arabic-Indic and Persian digits → ASCII,
             punctuation removed, Latin lowercased. (KITAB-Bench and Misraj report on text close to this.)
distance(a, b)  Levenshtein distance of two sequences (str or list), Myers/Hyyrö bit-parallel: a 3,000-character
             page against another takes milliseconds in pure Python.
"""
from __future__ import annotations

import re
import unicodedata

TATWEEL = "ـ"
HARAKAT = re.compile("[ً-ٰٟۖ-ۭ࣓-ࣿ]")
_WS = re.compile(r"\s+")
_PRES = re.compile("[ﭐ-﷿ﹰ-ﻼ]")
_FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ٲ": "ا", "ٳ": "ا", "ؤ": "و", "ئ": "ي",
                       "ى": "ي", "ة": "ه", "ی": "ي", "ي": "ي", "ک": "ك", "ھ": "ه", "ۀ": "ه", "ە": "ه",
                       "ے": "ي", "ۃ": "ه",
                       **{chr(0x660 + i): str(i) for i in range(10)}, **{chr(0x6f0 + i): str(i) for i in range(10)}})
_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)


def faithful(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    if _PRES.search(s):
        s = _PRES.sub(lambda m: unicodedata.normalize("NFKC", m.group()) if m.group() != "ﷺ" else m.group(), s)
    s = s.replace(TATWEEL, "")
    return _WS.sub(" ", s).strip()


def folded(s: str) -> str:
    s = faithful(s).replace("ﷺ", "صلى الله عليه وسلم")
    s = HARAKAT.sub("", s).translate(_FOLD)
    s = _PUNCT.sub(" ", s).lower()
    return _WS.sub(" ", s).strip()


NORMS = {"faithful": faithful, "folded": folded}


def distance(a, b) -> int:
    """Levenshtein distance (unit costs) between two sequences of hashable items."""
    if len(a) < len(b):
        a, b = b, a
    m = len(b)
    if m == 0:
        return len(a)
    peq: dict = {}
    for i, c in enumerate(b):
        peq[c] = peq.get(c, 0) | (1 << i)
    mask = (1 << m) - 1
    hibit = 1 << (m - 1)
    pv, mv, score = mask, 0, m
    for c in a:
        eq = peq.get(c, 0)
        xv = eq | mv
        xh = (((eq & pv) + pv) ^ pv) | eq
        ph = mv | (~(xh | pv) & mask)
        mh = pv & xh
        if ph & hibit:
            score += 1
        elif mh & hibit:
            score -= 1
        ph = ((ph << 1) | 1) & mask
        mh = (mh << 1) & mask
        pv = mh | (~(xv | ph) & mask)
        mv = ph & xv
    return score


def words(s: str) -> list[str]:
    return s.split()
