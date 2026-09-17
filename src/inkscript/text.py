"""Arabic text helpers shared by both halves: matching normalisation, digit
folding, and the visual-order form a PDF stores."""
from __future__ import annotations
import re, unicodedata

# Tashkeel, superscript alef, and tatweel — the marks the engines disagree about.
STRIP = re.compile(r"[ً-ْٰـ]")


# Arabic variants, then Perso-Arabic. The corpus is not purely Arabic — at least
# one journal here is Urdu, and on those pages Azure normalises the letterforms
# to their Arabic shapes (کی -> كى, ھندوستان -> هندوستان) while Gemini keeps the
# Urdu ones. Folding only the Arabic set made every Urdu word look like a
# mismatch and collapsed one document's alignment to 38%.
FOLD = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا",
                      "ة": "ه", "ى": "ي", "ﻻ": "لا",
                      "ی": "ي", "ے": "ي", "ئ": "ي",      # yeh forms
                      "ک": "ك", "ڪ": "ك",                # kaf forms
                      "ھ": "ه", "ہ": "ه", "ۀ": "ه",      # heh forms
                      "ں": "ن", "ؤ": "و"})


PUNCT = re.compile(r"[^\w؀-ۿ]+")


def norm(w: str) -> str:
    """Match key for one token. Aggressive on purpose — see module docstring."""
    w = unicodedata.normalize("NFKC", w)
    w = STRIP.sub("", w).translate(FOLD)
    return PUNCT.sub("", w)


ARABIC = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


# Letters Urdu and Persian use and Arabic does not. A page with none of them is
# Arabic, and on an Arabic page every digit is Arabic-Indic.
NON_ARABIC_LETTERS = re.compile(r"[ٹڈڑںھہےۓگکپچژ]")


PERSIAN_TO_ARABIC_DIGITS = str.maketrans("۰۱۲۳۴۵۶۷۸۹", "٠١٢٣٤٥٦٧٨٩")


def fold_digits(text: str) -> str:
    """Gemini's one systematic slip: Persian digits on Arabic pages.

    ٢ and ۲ are near-identical glyphs, and on 6 of 25 Arabic front pages Gemini
    wrote some numbers each way — `۲۷` beside `٧` on the same page — while
    Azure never did. A reader searching a year or issue number typed with
    Arabic-Indic digits then misses it. Urdu/Persian pages are left alone:
    there the Persian digits are correct.
    """
    if NON_ARABIC_LETTERS.search(text):
        return text
    return text.translate(PERSIAN_TO_ARABIC_DIGITS)


# What for_word reverses: Arabic-script letters and Arabic-Indic digits (٠-٩).
# NOT the Extended Arabic-Indic digits Urdu uses (۰-۹): Unicode classes those as
# European numbers, PyMuPDF already lays them out left to right, and reversing
# them turned the page number ۱۳۶۶ into ۶۶۳۱ in the extracted text.
RTL = re.compile(r"[؀-ۯۺ-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")


MARKS = re.compile(r"[\u064B-\u065F\u0670]")        # tashkeel and superscript alef


def visual(s: str) -> str:
    """A glyph's text in visual order: what a native Arabic PDF stores."""
    toks = s.split()
    if not any(RTL.search(t) for t in toks):
        return s
    def vis(t):
        if not RTL.search(t):
            return t
        runs = re.findall(r"[0-9٠-٩]+|[^0-9٠-٩]+", t)
        return "".join(r if re.match(r"[0-9٠-٩]", r) else r[::-1] for r in reversed(runs))
    return " ".join(vis(t) for t in reversed(toks))


# ---- pieces: where printed Arabic must break
# Letters that never join to the letter after them (Unicode joining type R),
# plus non-joining hamza. After any of these a new stroke begins.
RIGHT_JOINING = set("اأإآدذرزوؤةىٱ")
NON_JOINING = set("ء")
TRANSPARENT = re.compile(r"[ؐ-ًؚ-ٰٟۖ-ۭ]")   # marks ride on the letter before
ARABIC_LETTER = re.compile(r"[ؠ-يٮ-ۓۺ-ۿـ]")


def pieces(word: str) -> list[str]:
    """Split a word's text where the script cannot connect.

    `الحكم` -> ['ا', 'لحكم']; `126/4` -> ['126/4']; `العربى،` -> ['ا', 'لعر', 'بى', '،'].
    Arabic letters group into connected runs by the joining rules. Anything
    else — digits, Latin, punctuation — forms one piece per run: printed as
    one blob per character, but a viewer's bidi keeps `126/4` in order only
    if it is one glyph. Marks stay with the letter they sit on.
    """
    out: list[str] = []
    cur = ""; joins_left = False           # does the run so far accept a letter on its left?
    for ch in word:
        if TRANSPARENT.match(ch):
            if cur: cur += ch
            elif out: out[-1] += ch
            continue
        if ARABIC_LETTER.match(ch):
            if cur and joins_left:
                cur += ch
            else:
                if cur: out.append(cur)
                cur = ch
            joins_left = ch not in RIGHT_JOINING and ch not in NON_JOINING
            if ch in NON_JOINING:
                out.append(cur); cur = ""; joins_left = False
        else:
            if cur and ARABIC_LETTER.match(cur[0]):
                out.append(cur); cur = ""
            joins_left = False
            if not ch.strip():
                if cur: out.append(cur); cur = ""
            else:
                cur += ch                  # digits, Latin, punctuation: one piece per run (`126/4`, `(1)`), read as one by a viewer's bidi
    if cur: out.append(cur)
    return out
