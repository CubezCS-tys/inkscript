"""The trust flag: which free signals mark a word "check this", and why. Chosen in analyze.py (see README).

    flag_reasons(signals_row) -> list of reasons (empty: the word is not flagged)

A row is one word's signals (signals.py). DEFAULT names the rule used for the TEI files, the report and the
_trust.pdf.
"""

# ---------------------------------------------------------------- signals (each: row -> reason or None)

def low_conf(t):
    return lambda r: "low confidence" if r["conf"] is not None and r["conf"] < t else None


def speck(r):          # a speck or a stray mark: a small box alone (or nearly) on its line, or a box far too narrow for its
    # letters, unless Azure is very sure (page numbers and note numbers are small and alone too); a box under 0.3 of the
    # document's word height always
    small = (r["h_rel"] < 0.65 and r["line_n"] <= 2) or r["w_rel"] < 0.4
    return "speck or stray mark" if (small and r["conf"] < 0.98) or r["h_rel"] < 0.3 else None


def ornament(r):       # display type, calligraphy, stamps, white-on-black: very large, or very dense ink, alone on its line
    return "ornament, stamp or display type" if (r["h_rel"] > 2.5 or r["ink"] > 0.33) and r["line_n"] <= 3 and r["conf"] < 0.95 else None


def persian(r):
    return "Persian letter the build does not fold" if r["persian"] else None


def quran(r):
    return "differs from the Quran verse" if r["quran"] in ("dots", "letters", "other") else None


def latin(r):          # a Latin word on an Arabic page: transliteration marks, formulas, or a speck read as Latin
    return "Latin word on an Arabic page" if r["latin"] and r["arabic_page"] and r["conf"] < 0.95 else None


def old(t):            # pre-2000 scans: a stricter confidence bar
    return lambda r: "low confidence (old print)" if r["year"] and r["year"] < 2000 and r["conf"] < t else None


def hamza(r):          # a print that omits the hamza, read by a model that adds it
    return "hamza in a print that omits it" if r["hamza_doc"] and r["hamza"] else None


def salla(r):
    return "ﷺ ligature" if r["salla"] else None


def supnum(r):
    return "superscript note number?" if r["supnum"] and r["conf"] < 0.9 else None


def rule(*sigs):
    def f(r):
        if not r.get("real", True):      # no letter or digit (punctuation alone): not assessed, as in experiment 19
            return []
        why = [w for w in (s(r) for s in sigs) if w]
        return why
    return f


BASE = [persian, quran]
SIG_INK = [speck, ornament]
RULES = {
    "conf < 0.8 (experiment 19)": rule(low_conf(0.8)),
    "conf < 0.8 + Persian + Quran": rule(low_conf(0.8), *BASE),
    "+ speck & ornament": rule(low_conf(0.8), *BASE, *SIG_INK),
    "+ Latin on Arabic page": rule(low_conf(0.8), *BASE, *SIG_INK, latin),
    "+ old prints at conf < 0.9": rule(low_conf(0.8), *BASE, *SIG_INK, latin, old(0.9)),
    "+ hamza in hamza-omitting prints": rule(low_conf(0.8), *BASE, *SIG_INK, latin, old(0.9), hamza),
    "conf < 0.9": rule(low_conf(0.9)),
    "conf < 0.7 + Persian + Quran + speck & ornament + Latin": rule(low_conf(0.7), *BASE, *SIG_INK, latin),
}
DEFAULT = "+ Latin on Arabic page"


def default_rule(r):
    return RULES[DEFAULT](r)




def flag_reasons(r):
    return RULES[DEFAULT](r)
