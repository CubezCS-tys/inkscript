"""Experiment 85: shared pieces -- the comparison form, the dispute types, the locked-journal guard, paths.

The comparison form `sform` is experiment 81's scorer fix applied to the strict (every-letter) form: experiment 77's
cleaning (clean_label = the scorer's `faithful`), then PUNCTUATION ONLY removed (Unicode categories P* and S*, and
`_`), spaces collapsed.  The lab's `no_punct` removes `[^\\w\\s]`, which also turns every vowel mark into a space;
here marks stay marks.  Letters, dots, hamza forms, ى/ي, ة/ه, vowel marks, digits and word spaces count.

Dispute types (azure vs v1, both in `sform`; the first that applies):
  same        equal once the mark-as-space artefact is gone (a dispute only under no_punct)
  space       equal with every space removed
  marks       equal with vowel marks / tanwin / shadda / sukun / dagger alif removed
  hamza_alif  equal with أ إ آ ٱ -> ا
  ya          equal with ى -> ي
  ta          equal with ة -> ه
  conv_mixed  equal only with two or more of these folds
  one_letter  one edit (insert, delete or substitute) of any other character
  multi       anything else
Each convention type carries a direction (which side has the space / mark / hamza / ى / ة).
"""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from pathlib import Path

from rapidfuzz.distance import Levenshtein

HERE = Path(__file__).resolve().parent
E = HERE.parent
ROOT = E.parent
OUT = HERE / "out"
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "84_display_fonts"))
sys.path.insert(0, str(ROOT / "src"))

from common77 import clean_label  # noqa: E402

HELD3 = E / "83_reader_scale/out/held/held_v3.jsonl.gz"      # v1's reads of the 444,265 held lines
HELD4 = E / "83_reader_scale/out/held/held_v4.jsonl.gz"      # v3's reads of the 343,174 still held after v3
SPLIT76 = E / "76_finetune_pilot/out/split76.json"

_WS = re.compile(r"\s+")
HARAKAT = re.compile("[ً-ٰٟۖ-ۭ࣓-ࣿ]")
ALIF = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا"})
YA = str.maketrans({"ى": "ي"})
TA = str.maketrans({"ة": "ه"})


def sform(s: str | None) -> str:
    s = clean_label(s or "")
    s = "".join(" " if (unicodedata.category(c)[0] in "PS" or c == "_") else c for c in s)
    return _WS.sub(" ", s).strip()


FOLDS = {
    "space": lambda s: s.replace(" ", ""),
    "marks": lambda s: _WS.sub(" ", HARAKAT.sub("", s)).strip(),
    "hamza_alif": lambda s: s.translate(ALIF),
    "ya": lambda s: s.translate(YA),
    "ta": lambda s: s.translate(TA),
}
CONV = list(FOLDS)


def _all(s: str, which) -> str:
    for k in which:
        s = FOLDS[k](s)
    return s


def _dir(kind: str, a: str, b: str) -> str:
    """Which side carries the feature: 'az' (Azure has more of it), 'v1', or 'both'."""
    if kind == "space":
        ca, cb = a.count(" "), b.count(" ")
    elif kind == "marks":
        ca, cb = len(HARAKAT.findall(a)), len(HARAKAT.findall(b))
    elif kind == "hamza_alif":
        ca, cb = sum(a.count(c) for c in "أإآٱ"), sum(b.count(c) for c in "أإآٱ")
    elif kind == "ya":
        ca, cb = a.count("ى"), b.count("ى")
    elif kind == "ta":
        ca, cb = a.count("ة"), b.count("ة")
    else:
        return "-"
    return "az" if ca > cb else "v1" if cb > ca else "both"


def dtype(az: str, v1: str) -> tuple[str, str]:
    """(type, direction) of the difference between Azure's and v1's readings (raw strings)."""
    a, b = sform(az), sform(v1)
    if a == b:
        return "same", "-"
    for k in CONV:
        if FOLDS[k](a) == FOLDS[k](b):
            return k, _dir(k, a, b)
    if _all(a, CONV) == _all(b, CONV):
        return "conv_mixed", "-"
    if Levenshtein.distance(a, b) == 1:
        return "one_letter", "-"
    return "multi", "-"


def era3(year) -> str:
    try:
        y = int(str(year)[:4])
    except (TypeError, ValueError):
        return "?"
    return "pre-1950" if y < 1950 else "1950-1999" if y < 2000 else "2000+"


def held_out_codes() -> set[str]:
    return set(json.loads(SPLIT76.read_text())["test"])


def guard(keys, what: str = "") -> int:
    """Every key that will be trained on or shown: never a LOCKED journal (experiment 84) and never an experiment-76
    held-out journal.  Raises when the locked list does not exist yet (no silent pass)."""
    from locked import LOCKED, assert_not_locked
    if not LOCKED.exists():
        raise RuntimeError(f"{LOCKED} does not exist yet: refusing to go on without the locked-journal list")
    keys = list(keys)
    n = assert_not_locked(keys)
    ho = held_out_codes()
    bad = [k for k in keys if str(k)[:4] in ho]
    if bad:
        raise AssertionError(f"{len(bad)} {what} item(s) from experiment 76's held-out journals, e.g. {bad[:5]}")
    return n
