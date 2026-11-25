"""Experiment 103, job A: put a line's Latin and digit runs into logical (typing) order.

The convention (experiment 97's ruling: mixed lines are typed in LOGICAL order, so that a Chromium RTL paragraph
shows them as printed), made exact here:
  - Arabic is typed right to left, as read.
  - An ISLAND is a stretch of the line, as seen on the page, with no Arabic letter in it, from its first to its
    last Latin letter or digit.  If it holds a Latin letter it is ONE unit, typed left to right as an English typist
    types it, with the spaces, commas, full stops, colons, brackets and digits inside it: «(Adin, 2005)»,
    «ISSN: 1112-9751», «(Deroy, 1955, p. 121)», «Nonaka (1994)».  A bracket of the unit whose partner sits just
    outside it goes with it; a bracket that still has no partner splits the island (so «كوفيد-19 (Chen, ...» keeps
    19 with the Arabic word).
  - A stretch of digits with no Latin letter is split into numbers at every separator the bidi algorithm does not
    join between Arabic-context digits (it lays them right to left): «23-26» for a printed 26-23, «1998، 2001».
  - Everything outside the units keeps its place in reading order (brackets as the logical character whose
    mirrored shape is seen).
A candidate is accepted only if it DISPLAYS as the line is seen (fribidi = the Unicode bidi algorithm in an RTL
paragraph; selftest103 checks it against headless Chromium).  Otherwise the line is left as Azure gave it.
Lines with no Arabic letter, or with no Latin letter and no digit, are never touched.

  fix_line(azure_text)            the line as seen = how Azure's own string displays (diag103 checks, with Azure's
                                  word boxes, that it displays as printed: it does on 99.9% of mixed lines);
  azure_style(visual)             the synthesizer for the self-test: Azure's ordering habit, measured on real lines
                                  (reverse the line as seen, then turn back each Latin run (Latin letter to Latin
                                  letter) and each number; brackets outside them mirrored).
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from bidi103 import _mirror, fribidi_display, is_mark  # noqa: E402

AR_LETTER = re.compile("[ؠ-يٮ-ۓەۺ-ۿݐ-ݿﭐ-﷿ﹰ-﻿]")
LAT = re.compile("[A-Za-zÀ-ɏͰ-ϿḀ-ỿ]")
DIG = re.compile("[0-9٠-٩۰-۹]")
OPEN, CLOSE = "([{<«‹", ")]}>»›"
JOIN_AN = set(".,:/٫٬ ")      # common separators: joined between two digits in an Arabic context
JOIN_EN = JOIN_AN | set("-+−")
_WS = re.compile(r"\s+")


def clean_label(s: str) -> str:
    """Experiment 77's training-label form (copied from common77.clean_label, unchanged in effect)."""
    s = unicodedata.normalize("NFC", s or "")
    s = re.sub("[ﭐ-﷿ﹰ-ﻼ]", lambda m: unicodedata.normalize("NFKC", m.group()) if m.group() != "ﷺ" else m.group(), s)
    s = s.replace("ـ", "")
    return _WS.sub(" ", s).strip()


def _kind(c: str) -> str:
    if AR_LETTER.match(c):
        return "A"
    if LAT.match(c):
        return "L"
    if DIG.match(c):
        return "D"
    return "N"


def visual_clusters(s: str, rtl: bool = True) -> list[str]:
    """The line as seen, left to right, as clusters (base SHAPE + its marks); odd-level bases mirrored."""
    cl = []
    for i, c in enumerate(s):
        if is_mark(c) and cl:
            cl[-1].append(i)
        else:
            cl.append([i])
    _, v2l, lev = fribidi_display(s, rtl)
    pos = {li: vi for vi, li in enumerate(v2l)}
    cl.sort(key=lambda c: pos[c[0]])
    return [(_mirror(s[c[0]]) if lev[c[0]] % 2 else s[c[0]]) + "".join(s[x] for x in c[1:]) for c in cl]


def display_key(s: str) -> str:
    """What a comparison of two displays looks at: the shapes left to right, marks kept on their base."""
    return "".join(visual_clusters(s))


# ------------------------------------------------------------------------------------------------ units

def _num_units(S, kinds, a, b, join):
    units, k = [], a
    while k <= b:
        if kinds[k] != "D":
            k += 1
            continue
        e = k
        while True:
            if e + 1 <= b and kinds[e + 1] == "D":
                e += 1
            elif e + 2 <= b and S[e + 1][0] in join and kinds[e + 2] == "D":
                e += 2
            else:
                break
        units.append((k, e))
        k = e + 1
    return units


def _unbalanced(S, a, b):
    stack, bad = [], []
    for k in range(b, a - 1, -1):                      # left to right on the page
        c = S[k][0]
        if c in OPEN:
            stack.append(k)
        elif c in CLOSE:
            if stack and OPEN.index(S[stack[-1]][0]) == CLOSE.index(c):
                stack.pop()
            else:
                bad.append(k)
    return bad + stack


def _extend_brackets(S, a, b, lo, hi):
    txt = "".join(S[k][0] for k in range(b, a - 1, -1))
    depth = sum(txt.count(o) for o in OPEN) - sum(txt.count(c) for c in CLOSE)
    if depth > 0:                       # an unclosed "(": its ")" is at the unit's right = before a in the scan
        k = a - 1
        while k >= lo and S[k] == " ":
            k -= 1
        if k >= lo and S[k][0] in CLOSE:
            a = k
    elif depth < 0:
        k = b + 1
        while k < hi and S[k] == " ":
            k += 1
        if k < hi and S[k][0] in OPEN:
            b = k
    return a, b


def _lat_units(S, kinds, a, b, lo, hi, join, mode):
    if mode:
        a, b = _extend_brackets(S, a, b, lo, hi)
    if mode == 2:
        bad = sorted(_unbalanced(S, a, b))
        if bad:
            out, start = [], a
            for cut in bad + [b + 1]:
                seg = [k for k in range(start, cut) if kinds[k] in "LD"]
                if seg:
                    sa, sb = seg[0], seg[-1]
                    if any(kinds[k] == "L" for k in range(sa, sb + 1)):
                        out.append((sa, sb))
                    else:
                        out.extend(_num_units(S, kinds, sa, sb, join))
                start = cut + 1
            return out
    return [(a, b)]


def _units(S, kinds, join, mode):
    units, n, i = [], len(S), 0
    while i < n:
        if kinds[i] == "A":
            i += 1
            continue
        j = i
        while j < n and kinds[j] != "A":
            j += 1
        i0, j0 = i, j
        if mode == 2:                       # a number set solid against an Arabic word («المريض-15») stays with it
            if i > 0 and kinds[i - 1] == "A":
                k = i
                while k < j and (kinds[k] == "D" or S[k][0] in "-‐‑"):
                    k += 1
                if k > i and (k == j or S[k] == " ") and any(kinds[m] == "D" for m in range(i, k)):
                    units.extend(_num_units(S, kinds, i, k - 1, join))
                    i0 = k
            if j < n and kinds[j] == "A":
                k = j - 1
                while k >= i0 and (kinds[k] == "D" or S[k][0] in "-‐‑"):
                    k -= 1
                if k < j - 1 and (k < i0 or S[k] == " ") and any(kinds[m] == "D" for m in range(k + 1, j)):
                    units.extend(_num_units(S, kinds, k + 1, j - 1, join))
                    j0 = k + 1
        seg = [k for k in range(i0, j0) if kinds[k] in "LD"]
        if seg:
            a, b = seg[0], seg[-1]
            if any(kinds[k] == "L" for k in range(a, b + 1)):
                units.extend(_lat_units(S, kinds, a, b, i0, j0, join, mode))
            else:
                units.extend(_num_units(S, kinds, a, b, join))
        i = j
    return units


def _emit(S, units, outside):
    """S: clusters right to left (shapes).  Units are written left to right as seen; outside clusters by `outside`."""
    in_unit = {}
    for a, b in units:
        for k in range(a, b + 1):
            in_unit[k] = (a, b)
    out, k = [], 0
    while k < len(S):
        if k in in_unit:
            a, b = in_unit[k]
            out.extend(S[m] for m in range(b, a - 1, -1))
            k = b + 1
        else:
            out.append(outside(k))
            k += 1
    return "".join(out)


def natural_from_visual(vis: list[str], outside_chars=None):
    """vis: clusters left to right as seen.  Returns the first candidate whose display equals vis, or None.
    outside_chars: optional logical character per cluster for clusters outside the units (Azure's own); by default
    the mirror of the shape (an RTL neutral)."""
    S = vis[::-1]
    kinds = [_kind(c[0]) for c in S]
    key = "".join(vis)
    seen = set()
    for mode in (2, 1, 0):
        for join in (JOIN_AN, JOIN_EN):
            for outside in ((lambda k: outside_chars[::-1][k]) if outside_chars else None,
                            lambda k: _mirror(S[k][0]) + S[k][1:]):
                if outside is None:
                    continue
                cand = _emit(S, _units(S, kinds, join, mode), outside)
                if cand in seen:
                    continue
                seen.add(cand)
                if display_key(cand) == key:
                    return cand
    return None


def _skip(s: str):
    if not AR_LETTER.search(s):
        return "no Arabic letter"
    if not (LAT.search(s) or DIG.search(s)):
        return "no Latin letter or digit"
    return None


def fix_line(s: str):
    """Text mode: the line as seen is how Azure's string displays."""
    info = {"changed": False, "why": _skip(s), "kinds": []}
    if info["why"]:
        return s, info
    # Azure's own logical character for each cluster (as seen), used outside the units
    cl = []
    for i, c in enumerate(s):
        if is_mark(c) and cl:
            cl[-1].append(i)
        else:
            cl.append([i])
    _, v2l, lev = fribidi_display(s)
    pos = {li: vi for vi, li in enumerate(v2l)}
    cl.sort(key=lambda c: pos[c[0]])
    vis = [(_mirror(s[c[0]]) if lev[c[0]] % 2 else s[c[0]]) + "".join(s[x] for x in c[1:]) for c in cl]
    own = ["".join(s[x] for x in c) for c in cl]
    cand = natural_from_visual(vis, own)
    if cand is None:
        info["why"] = "no candidate displays as Azure's line: left as is"
        return s, info
    if cand == s:
        info["why"] = "already in logical order"
        return s, info
    info.update(changed=True, why="reordered", kinds=change_kinds(s, cand))
    return cand, info


# ------------------------------------------------------------------------------------------------ Azure's habit

_RUN_LAT = re.compile("[A-Za-zÀ-ɏ](?:[^؀-ۿ]*[A-Za-zÀ-ɏ])?")
_RUN_NUM = re.compile("[0-9\u0660-\u0669\u06F0-\u06F9]+(?:[.,:/\u066B\u066C][0-9\u0660-\u0669\u06F0-\u06F9]+)*")


def azure_style(visual: str) -> str:
    """Azure's ordering, as measured on real lines: the line as seen, reversed; then each Latin run (Latin letter
    to Latin letter) and each number turned back; brackets outside them mirrored."""
    cls = []
    for c in visual:
        if is_mark(c) and cls:
            cls[-1] += c
        else:
            cls.append(c)
    S = "".join(cls[::-1])                     # reversed by cluster: marks stay after their base
    spans = []
    for m in _RUN_LAT.finditer(S):
        spans.append((m.start(), m.end()))
    taken = [False] * len(S)
    for a, b in spans:
        for k in range(a, b):
            taken[k] = True
    for m in _RUN_NUM.finditer(S):
        if not any(taken[m.start():m.end()]):
            spans.append((m.start(), m.end()))
    spans.sort()
    out, k = [], 0
    for a, b in spans:
        out.extend(_mirror(c) for c in S[k:a])
        out.append(_rev_clusters(S[a:b]))
        k = b
    out.extend(_mirror(c) for c in S[k:])
    return "".join(out)


def _rev_clusters(t: str) -> str:
    cls = []
    for c in t:
        if is_mark(c) and cls:
            cls[-1] += c
        else:
            cls.append(c)
    return "".join(cls[::-1])


def change_kinds(old: str, new: str):
    """Which kinds of run were reordered (a line can have several): by the islands whose text differs."""
    kinds = set()
    o_isl, n_isl = _islands(old), _islands(new)
    for t in [t for t in n_isl if t not in o_isl] or n_isl:
        lat, dig = bool(LAT.search(t)), bool(DIG.search(t))
        if "%" in t or "٪" in t:
            kinds.add("percent")
        if lat and dig:
            kinds.add("latin_citation")
        elif lat:
            kinds.add("latin_term")
        elif dig:
            kinds.add("digit_group")
        if lat and any(c in t for c in OPEN + CLOSE):
            kinds.add("mixed_brackets")
    return sorted(kinds)


def _islands(s: str):
    return [m.group().strip() for m in re.finditer("[^ؠ-يٮ-ۓۺ-ۿ]+", s)
            if LAT.search(m.group()) or DIG.search(m.group())]


if __name__ == "__main__":
    for t in sys.argv[1:]:
        print(fix_line(t), "| azure_style(display):", azure_style(display_key(t)))
