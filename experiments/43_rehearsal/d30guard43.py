"""Experiment 66 (D30 guard): refuse a reader's "fix" of Azure's reading when the print was most likely right.

D30: the text is the print as printed. A fix is allowed only for Azure's misreadings; Gemini Argon sometimes "fixes"
words Azure read right («first» -> «firsf», «يريد» -> «يزيد») or overwrites the author's misprint. This module looks
at each fix with what the code knows (Azure's word confidences, the edit's shape, whether the words are real words)
and refuses the risky ones. A refused fix is never applied: the printed (Azure) word stays and the reader's proposal
travels beside it as a flag {"line", "text", "corr", "why", "kind": "model-suggestion"} in ans["sic"] (the masters
write it as named-content content-type="model-suggestion" once masters.py reads "kind"; until then it shows as a
sic flag, which keeps the text right in either case).

    guard(ans, lines, words=None, log=None, lexicon_=None)  in place; returns the list of refused fixes
    edit_class(frm, to) -> str                              the edit's kind (see CLASSES)
    features(fix, lines, words, W) -> dict                  what the decision looks at
    decide(feat) -> (keep, reason)                          the rule (see "the rule" below)

Hook point (one line, rules43.normalize, just before the last rule `fixes(ans, log)`):
    import d30guard43; d30guard43.guard(ans, lines, words, log)
`words` is masters43.azure_words(a) (Azure's words with "conf"); without it no fix is refused. Code fixes (`why`
starting "code:": letters43, guillemets) are never touched. Measurement and thresholds: experiments/66_d30_guard/README.md.
"""
from __future__ import annotations

import difflib
import re
import unicodedata
from pathlib import Path

HERE = Path(__file__).resolve().parent

TASHKEEL = re.compile(r"[ً-ْٰـ]")
AR = re.compile(r"[؀-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
AR_LET = re.compile(r"[ء-غف-يٱ-ۓۺ-ۼݐ-ݿ]")
LA_LET = re.compile(r"[A-Za-zÀ-ɏ]")
DIGIT = re.compile(r"[0-9٠-٩۰-۹]")
PERSIAN = set("یکھہڪۀۃ")                               # Azure's look-alikes of ي ك ه ة
HAMZA = set("ءأإآٱؤئ")
ALIF = set("اأإآٱ")
# the dotless skeleton (rasm): letters that differ only by dots share a class
RASM = str.maketrans({
    "ب": "ٮ", "ت": "ٮ", "ث": "ٮ", "ن": "ٮ", "ي": "ٮ", "ى": "ٮ", "ئ": "ٮ", "ی": "ٮ", "پ": "ٮ",
    "ج": "ح", "خ": "ح", "چ": "ح", "ذ": "د", "ز": "ر", "ژ": "ر", "ش": "س", "ض": "ص", "ظ": "ط", "غ": "ع",
    "ف": "ڡ", "ق": "ڡ", "ة": "ه", "ھ": "ه", "ہ": "ه", "ۀ": "ه", "ۃ": "ه", "ك": "ک", "ڪ": "ک", "گ": "ک",
    "أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ؤ": "و", "ء": None,
})
ORTH = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ى": "ي", "ة": "ه", "ؤ": "و", "ئ": "ي", "ء": None,
                      "ی": "ي", "ک": "ك", "ھ": "ه", "ہ": "ه", "ڪ": "ك", "ۀ": "ه", "ۃ": "ه"})
TO_LATIN_DIGIT = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")

CLASSES = ("spacing", "punct", "tashkeel", "persian", "hamza", "ya_alif_maqsura", "ta_marbuta", "digits",
           "digit_letter", "letter_mark", "dots", "ar_swap", "ar_indel", "latin_accent", "latin_case", "latin_swap", "latin_indel",
           "script_mix", "rewrite", "other")


def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", s) if not unicodedata.combining(c))


def _changed(frm: str, to: str):
    """(removed chars, added chars, opcodes) of the character diff."""
    sm = difflib.SequenceMatcher(None, frm, to, autojunk=False)
    rem, add, ops = [], [], []
    for op, i1, i2, j1, j2 in sm.get_opcodes():
        if op == "equal":
            continue
        rem.append(frm[i1:i2])
        add.append(to[j1:j2])
        ops.append(op)
    return "".join(rem), "".join(add), ops


def edit_class(frm: str, to: str) -> str:
    """The edit's kind, checked from the narrowest (most typical of Azure) to the broadest."""
    frm, to = frm or "", to or ""
    if re.sub(r"\s+", "", frm) == re.sub(r"\s+", "", to):
        return "spacing"
    f0, t0 = re.sub(r"\s+", "", frm), re.sub(r"\s+", "", to)
    rem, add, ops = _changed(f0, t0)
    ch = rem + add
    if not ch:
        return "spacing"
    if TASHKEEL.sub("", f0) == TASHKEEL.sub("", t0):
        return "tashkeel"
    f1, t1 = TASHKEEL.sub("", f0), TASHKEEL.sub("", t0)
    rem, add, ops = _changed(f1, t1)
    ch = rem + add
    letters_ch = [c for c in ch if c.isalpha()]
    if not letters_ch and not DIGIT.search(ch):
        return "punct"
    if any(c in PERSIAN for c in rem) and f1.translate(ORTH) == t1.translate(ORTH):
        return "persian"
    if f1.translate(ORTH) == t1.translate(ORTH):
        if set(ch) <= set("ىي"):
            return "ya_alif_maqsura"
        if set(ch) <= set("ةه"):
            return "ta_marbuta"
        return "hamza"
    if DIGIT.search(ch):
        if all(DIGIT.match(c) or not c.isalnum() for c in ch):
            return "digits"
        return "digit_letter"
    if add and not any(c.isalpha() for c in add) and rem and all(c.isalpha() for c in rem):
        return "letter_mark"                       # a printed mark Azure read as a letter («المتوسطر» for «المتوسط(»)
    ar = bool(AR_LET.search(ch))
    la = bool(LA_LET.search(ch))
    if ar and la:
        return "script_mix"
    if ar:
        if f1.translate(RASM) == t1.translate(RASM):
            return "dots"
        if len(frm.split()) > 2 or len(to.split()) > 2 or len(letters_ch) > 6:
            return "rewrite"
        if all(o == "replace" for o in ops) and len(rem) == len(add):
            return "ar_swap"
        if all(o in ("insert", "delete") for o in ops):
            return "ar_indel"
        return "ar_swap"
    if la:
        if strip_accents(f1) == strip_accents(t1):
            return "latin_accent"
        if f1.lower() == t1.lower():
            return "latin_case"
        if len(letters_ch) > 6:
            return "rewrite"
        if all(o in ("insert", "delete") for o in ops):
            return "latin_indel"
        return "latin_swap"
    return "other"


def script_of(s: str) -> str:
    a, l = len(AR_LET.findall(s or "")), len(LA_LET.findall(s or ""))
    if a and l:
        return "mixed"
    if a:
        return "ar"
    if l:
        return "latin"
    if DIGIT.search(s or ""):
        return "digits"
    return "marks"


# --------------------------------------------------------------------------------------------- lexicon
# The word test is wordlist43's (out/wordlist43.txt: words seen in >= 3 catalogue abstracts / titles or Azure texts of
# the sampled articles, folded; a clitic or suffix may be stripped). Without the list the test gives None and the
# guard refuses nothing (today's behaviour).
PUNCT_EDGE = re.compile(r"^[^\w]+|[^\w]+$")


def lexicon():
    import wordlist43
    return wordlist43.load()


def is_word(t: str, W: dict):
    import wordlist43
    return wordlist43.known(t, W)


def all_words(tokens, W):
    """True when every token with letters is a known word, False when one is not, None when none can be judged."""
    ks = [k for k in (is_word(t, W) for t in tokens) if k is not None]
    return None if not ks else all(ks)


def changed_tokens(frm: str, to: str):
    """The tokens that differ (from side, to side), word by word when the counts agree, else all of them."""
    a, b = frm.split(), to.split()
    if len(a) == len(b):
        pairs = [(x, y) for x, y in zip(a, b) if x != y]
        return [x for x, _ in pairs], [y for _, y in pairs]
    return a, b


def al_prefix(frm: str, to: str) -> bool:
    """Every changed word differs only by ال <-> ل / لل at its start (Azure reads a ل as ال and back: a known Azure
    error, 6 of 7 right in the sample), and none is the word الله / لله."""
    cf, ct = changed_tokens(TASHKEEL.sub("", frm or ""), TASHKEEL.sub("", to or ""))
    if not cf or len(cf) != len(ct):
        return False
    for a, b in zip(cf, ct):
        a, b = PUNCT_EDGE.sub("", a), PUNCT_EDGE.sub("", b)
        if {a, b} & {"الله", "لله"} or not a or not b:
            return False
        ok = (a[1:] == b[1:] and {a[0], b[0]} == {"ا", "ل"}) or (a == "ا" + b and b.startswith("ل")) or \
             (b == "ا" + a and a.startswith("ل"))
        if not ok:
            return False
    return True


def adds_tokens(frm: str, to: str) -> bool:
    """The fix keeps Azure's words and adds printed text Azure left out (a call marker, a subscript, a bullet)."""
    a, b = (frm or "").split(), (to or "").split()
    if len(b) <= len(a):
        return False
    it = iter(b)
    return all(any(x == y for y in it) for x in a)


# --------------------------------------------------------------------------------------------- features
def span_words(text: str, frm: str, ws: list | None):
    """Azure's words (dicts with "text", "conf") that the first occurrence of frm in the line text touches."""
    i = text.find(frm) if frm else -1
    if i < 0 or not ws:
        return []
    j = i + len(frm)
    out, pos = [], 0
    for w in ws:
        t = w.get("text") or ""
        k = text.find(t, pos) if t else -1
        if k < 0:
            continue
        pos = k + len(t)
        if k < j and k + len(t) > i:
            out.append(w)
    return out


def features(fix: dict, lines: dict, words=None, W: dict | None = None) -> dict:
    frm, to = str(fix.get("from") or ""), str(fix.get("to") or "")
    lid = str(fix.get("line") or "")
    base = lid if lid in lines else (lid[:-1] if lid[:-1] in lines else None)
    text = lines[base]["text"] if base else ""
    ws = []
    if base and words is not None:
        try:
            ws = span_words(text, frm, words(base))
        except Exception:                       # noqa: BLE001 - no Azure words for the line: no confidences
            ws = []
    confs = [w.get("conf") for w in ws if isinstance(w.get("conf"), (int, float))]
    W = lexicon() if W is None else W
    cf, ct = changed_tokens(frm, to)
    return dict(cls=edit_class(frm, to), conf_min=min(confs) if confs else None,
                from_real=all_words(cf, W) if W else None, to_real=all_words(ct, W) if W else None,
                al=al_prefix(frm, to), added=adds_tokens(frm, to), code=str(fix.get("why") or "").startswith("code:"))


# --------------------------------------------------------------------------------------------- the rule
# Measured in experiments/66_d30_guard (270 fixes judged on the scans). Where Azure was sure of the word (every word
# of the fix >= 0.97) and Gemini changes Arabic letters (dots, a letter swapped, a letter added or dropped) into a
# known word, the print was Azure's reading in about two thirds of the cases (69% in a fresh check of 40): either Gemini's "fix" is wrong (حال -> مال) or
# it overwrites the author's misprint (ثلك -> تلك), which D30 keeps with a sic. Everything else is allowed: the edit
# kinds typical of Azure (punctuation, digits, Persian look-alikes, hamza / ya / ta marbuta forms, vowel marks,
# Latin letters and symbols, ال <-> ل at a word's start, text Azure left out) and every fix of a word Azure was
# unsure of.
ARABIC_LETTER = {"dots", "ar_swap", "ar_indel"}
CONF_SURE = 0.97                 # 0.95-0.97 blocked more good fixes than bad ones (README)


def decide(f: dict) -> tuple[bool, str]:
    """(keep, reason)."""
    if f["code"]:
        return True, "code fix"
    if f["cls"] not in ARABIC_LETTER:
        return True, f"edit kind {f['cls']}"
    if f["al"] or f["added"]:
        return True, "ال / ل prefix" if f["al"] else "adds printed text"
    c = f["conf_min"]
    if c is None or c < CONF_SURE:
        return True, "Azure unsure"
    if f["to_real"] is not True:
        return True, "the fix's word is not a known word (a printed misprint written as printed)"
    return False, f"Azure sure ({c:.3f}) and the fix changes Arabic letters ({f['cls']}) into a known word"


def guard(ans: dict, lines: dict, words=None, log: dict | None = None, lexicon_: dict | None = None) -> list:
    """Refuse risky fixes in ans["fixes"] (in place); each becomes a model-suggestion flag in ans["sic"]: the
    printed (Azure) text stays, Gemini's word travels beside it."""
    W = lexicon() if lexicon_ is None else lexicon_
    keep, refused = [], []
    for f in ans.get("fixes") or []:
        if not isinstance(f, dict) or not f.get("from") or not f.get("to"):
            keep.append(f)
            continue
        ok, why = decide(features(f, lines, words, W))
        if ok:
            keep.append(f)
            continue
        refused.append(dict(f, guard=why))
        ans.setdefault("sic", []).append({"line": f.get("line"), "text": f["from"], "corr": f["to"],
                                          "why": f"model suggestion, not applied (D30 guard: {why})"
                                                 + (f"; reader: {f['why']}" if f.get("why") else ""),
                                          "kind": "model-suggestion"})
    if "fixes" in ans:
        ans["fixes"] = keep
    if log is not None:
        log.setdefault("fixes_refused_d30", []).extend(refused)
    return refused
