"""Arabic text helpers shared by both halves: matching normalisation, digit
folding, and the visual-order form a PDF stores."""
from __future__ import annotations
import re
import unicodedata, unicodedata

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


CLUSTER = re.compile(r".[\u0610-\u061A\u064B-\u065F\u0670\u06D6-\u06ED]*")   # a character with the marks that follow it


def _keeps_order(c: str) -> bool:
    """Characters pdfium never reverses inside a run: its 'left' and 'weak
    left' bidi segments (Latin letters; digits, vowel marks, and the
    separators , . / - : + % that Unicode classes CS/ES/ET/NSM/AN/EN/BN)."""
    return unicodedata.bidirectional(c) in ("L", "AN", "EN", "NSM", "CS", "ES", "ET", "BN")


def visual(s: str) -> str:
    """A glyph's text in visual order: what a native Arabic PDF stores.

    pdfium (Chrome; branches 7559–7947 and main) rebuilds a line whose
    text has right-to-left segments by reversing the ORDER of its bidi
    segments and then reversing each Arabic (and neutral-after-Arabic)
    segment in place, while Latin, digit, mark and separator segments keep
    their internal order. The inverse of that is: reverse the whole string,
    then put every run of order-keeping characters back the way it was.
    Digits stay `362`, a word's vowel marks stay after their letters
    (`كِتابُ` is stored `ُباتِك`), `126/4` stays whole, `379هـ)` becomes
    `)ـه379`. Words in a line are separate glyphs laid out left to right,
    so a glyph holding several words reverses their order too.

    pdfium build 7999 (pypdfium2 5.13) briefly switched the auto-order off
    and read words in stream order with marks in place; main restored it.
    Verify against 7947 (pypdfium2 5.12.1), which behaves like Chrome."""
    if not RTL.search(s):
        return s
    out, i, n = [], 0, len(s)
    rev = s[::-1]
    while i < n:
        if _keeps_order(rev[i]):
            j = i
            while j < n and _keeps_order(rev[j]):
                j += 1
            out.append(rev[i:j][::-1]); i = j
        else:
            out.append(rev[i]); i += 1
    return "".join(out)


def chrome_reads(line: str) -> str:
    """What pdfium (Chrome 144, branch 7559; also 7665–7947 and main) makes
    of a line's stored text: CPDF_TextPage::CloseTempLine with
    CFX_BidiString's automatic overall direction. Kept here as the
    reference the storage is verified against; `visual` is its inverse."""
    segs = []                                              # [start, count, class]
    for i, c in enumerate(line):
        b = unicodedata.bidirectional(c)
        d = "L" if b == "L" else "LW" if b in ("AN", "EN", "NSM", "CS", "ES", "ET", "BN") else "R" if b in ("R", "AL") else "N"
        if segs and segs[-1][2] == d:
            segs[-1][1] += 1
        else:
            segs.append([i, 1, d])
    nR = sum(1 for x in segs if x[2] == "R"); nL = sum(1 for x in segs if x[2] == "L")
    cur = "L"
    if nR > 0 and nR >= nL:
        segs = segs[::-1]; cur = "R"
    out = []
    for st, n, d in segs:
        part = line[st:st + n]
        if d == "R" or (d == "N" and cur == "R"):
            cur = "R"; out.append(part[::-1])
        else:
            if d != "LW":
                cur = "L"
            out.append(part)
    return "".join(out)


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


def strip_markdown(text: str) -> str:
    """Gemini sometimes decorates a transcription (`# طنجة`, `---`, `**x**`)
    despite the prompt. Those marks are not on the page; remove them before
    the words are aligned to Azure's boxes."""
    out = []
    for line in text.split("\n"):
        if re.fullmatch(r"\s*[-*_=]{3,}\s*", line):
            continue
        line = re.sub(r"^\s*#{1,6}\s+", "", line)
        line = re.sub(r"\*\*(.+?)\*\*", r"\1", line)
        out.append(line)
    return "\n".join(out)
