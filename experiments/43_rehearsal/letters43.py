"""Experiment 43, letter fix (2026-10-22, owner-approved under D30): Azure's Persian look-alike letters on Arabic
pages written back as the Arabic letters the print shows, each as a code fix of Azure's reading (the same path as
rules43.guillemet_halves: a fix {line, from, to, why} in the answer, so the JATS gets a named-content reader-fix
whose xlink:title keeps Azure's word, the ALTO String an ALTERNATIVE with Azure's word, and the back notes list it).

    ی (U+06CC) -> ي where it joins a following letter, ى at a word's end     src/inkscript/text.py fold_letters
    ک (U+06A9) -> ك                                                          (imported, not copied; src/ untouched)
    ھ (U+06BE), ہ (U+06C1) -> ه ; ڪ (U+06AA) -> ك                             (here: the same misreading, heh / kaf)

ی at a word's end is ي or ى on the print; code cannot tell which reliably (out/lettersfix/progress.md: Azure's ی covers
both, ~1/3 printed dotted in 73 words looked at; an ink check of the dots and a spelling model were each wrong too
often), so it takes text.py's choice ى, the more frequent (the platform's search folds ى and ي anyway); the fix's
`why` says the dot was not checked.

Not folded: a line in another language written in Arabic letters (Persian, Urdu, Kurdish, Ottoman), where ی and ک
are the print's own letters (`foreign`), and every line of a block whose lines are mostly such lines.
Used by lettersfix43.py only (it wraps rules43 at run time; rules43.py itself is unchanged).
"""
from __future__ import annotations

import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))
from inkscript.text import fold_letters  # noqa: E402

import rules43 as RU  # noqa: E402
from patches43 import block_lines  # noqa: E402

TARGET = re.compile(r"[یکھہڪ]")
EXTRA = str.maketrans({"ھ": "ه", "ہ": "ه", "ڪ": "ك"})
KURDISH = re.compile(r"[ەۆڵێڕ]")                      # Kurdish (Sorani) letters: 0396's header and abstract
URDU = re.compile(r"[ٹڈڑںۓ]")
PERSIAN = re.compile(r"[پچژگ]")
# words of Persian / Urdu / Ottoman that are not Arabic words (که, او, هم, تا, بر, با, من are left out: Arabic words or
# Azure's split of an Arabic word, «تحر که» = تحركه)
FA_WORDS = {"است", "این", "را", "از", "برای", "شده", "بود", "کرد", "کرده", "های", "یک", "نیز", "اند", "شد", "کند",
            "باشد", "دارد", "می", "نمی", "آنها", "چو", "هست", "نیست", "شود", "کنند", "گفت", "اگر", "چون", "بی", "اینکه",
            "ایله", "اولان", "ایدی", "دیر"}
UR_WORDS = {"کے", "کی", "میں", "ہے", "سے", "کو", "نے", "ہیں", "یہ", "وہ", "بھی", "تھا", "گیا", "اور"}
WORD = re.compile(r"[ء-ۿ]+")


def foreign(text: str) -> str | None:
    """Why the line is in another language written in Arabic letters, or None. One odd letter is not enough: Azure
    also misreads Arabic as پ / گ / چ / ٹ («پیروت», «ارتباگًا», «اناٹ»)."""
    ws = WORD.findall(text)
    fa = sum(w in FA_WORDS for w in ws)
    ur = sum(w in UR_WORDS for w in ws)
    if len(KURDISH.findall(text)) >= 2:
        return "kurdish letters"
    if len(URDU.findall(text)) >= 2 or ur >= 2:
        return "urdu"
    p = len(PERSIAN.findall(text))
    if fa >= 2 or (fa and p) or p >= 2:
        return "persian"
    return None


def fold_word(w: str) -> str:
    return fold_letters(w).translate(EXTRA)


def fix_span(t: str, s: int, e: int, rep: str):
    """(from, to) for replacing t[s:e] by rep (same length): whole words, widened leftwards until `from` first occurs at
    that place in Azure's text AND `to` first occurs there in the fixed text (41's runs mark a fix at the first
    occurrence of its corrected text: «کان» -> «كان» would be marked on an earlier «فكان» otherwise)."""
    t2 = t[:s] + rep + t[e:]
    a, b = s, e
    while a > 0 and not t[a - 1].isspace():
        a -= 1
    while b < len(t) and not t[b].isspace():
        b += 1
    while t.find(t[a:b]) != a or t2.find(t2[a:b]) != a:
        if a == 0:
            return None
        a2 = t.rfind(" ", 0, max(0, a - 1))
        a = 0 if a2 < 0 else a2 + 1
    return t[a:b], t2[a:b]


def _block_lines(ans, lines) -> list[list[str]]:
    out = []
    for pg in ans.get("pages") or []:
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            if isinstance(b, dict):
                ls = [RU.base_of(x, lines) or x for x in block_lines(b)]
                if ls:
                    out.append(ls)
    return out


def _spans(t: str, final: str, toks: list[tuple[int, int]]) -> list[tuple[int, int]] | None:
    """Non-overlapping spans (whole words) covering the changed tokens, each such that, applied left to right as
    structure.Store does (first occurrence of `from` in the text so far), its `from` first occurs at its place and its
    `to` first occurs at its place in the final line (where 41's runs marks it). Spans that would overlap are merged
    into one fix. None when no such spans exist (the line is then left as Azure read it, logged)."""
    spans: list[list[int]] = []
    for s, e in toks:
        a, b = s, e
        while a > 0 and not t[a - 1].isspace():
            a -= 1
        while b < len(t) and not t[b].isspace():
            b += 1
        while True:
            for sp in [x for x in spans if x[0] < b and a < x[1]]:
                a, b = min(a, sp[0]), max(b, sp[1])
                spans.remove(sp)
            before = t
            for x, y in spans:                            # all earlier spans lie left of this one
                before = before[:x] + final[x:y] + before[y:]
            if before.find(before[a:b]) == a and final.find(final[a:b]) == a:
                break
            if a == 0:
                return None
            a2 = t.rfind(" ", 0, max(0, a - 1))
            a = 0 if a2 < 0 else a2 + 1
        spans.append([a, b])
        spans.sort()
    return [tuple(x) for x in spans]


def _fold_meta(v, log, path=""):
    """Gemini's metadata strings copy Azure's letters («فی کتابیه»): folded the same way, so that 41's comparison of the
    metadata with the printed lines still sees them as the same words (0763's subtitle otherwise came back as new)."""
    if isinstance(v, str):
        if TARGET.search(v) and not foreign(v):
            new = " ".join(fold_word(w) for w in v.split(" "))
            if new != v:
                log.append(dict(field=path, frm=v, to=new))
                return new
        return v
    if isinstance(v, list):
        return [_fold_meta(x, log, f"{path}[{k}]") for k, x in enumerate(v)]
    if isinstance(v, dict):
        return {k: _fold_meta(x, log, f"{path}.{k}") for k, x in v.items()}
    return v


def letters_fix(ans, lines, log):
    """The fixes (after every other rule, on the line's text as the earlier fixes leave it). log["letters"]: one entry
    per word changed; log["letters_foreign"]: the lines left alone, with why; log["letters_meta"]: metadata strings."""
    fx = ans.setdefault("fixes", [])
    lg, lf = log.setdefault("letters", []), log.setdefault("letters_foreign", [])
    if isinstance(ans.get("metadata"), dict):
        ans["metadata"] = _fold_meta(ans["metadata"], log.setdefault("letters_meta", []), "metadata")
    for pg in ans.get("pages") or []:                 # Gemini's parsed citations: checked against the printed text too
        for b in (pg.get("blocks") or []) if isinstance(pg, dict) else []:
            for key in ("parsed", "cites"):          # refs43 keeps a part only when it is printed
                if isinstance(b, dict) and b.get(key):
                    b[key] = _fold_meta(b[key], log.setdefault("letters_meta", []), f"p{pg.get('page')}.{key}")
    why_line = {lid: foreign(L["text"]) for lid, L in lines.items() if TARGET.search(L["text"])}
    left = {lid: w for lid, w in why_line.items() if w}
    for ls in _block_lines(ans, lines):                # a block mostly in another language: all its lines
        own = [x for x in ls if x in lines]
        nf = sum(1 for x in own if foreign(lines[x]["text"]))
        if own and nf * 2 >= len(own):
            for x in own:
                if x in why_line and x not in left:
                    left[x] = "block in another language"
    why = "code: Azure's Persian look-alike letter for the printed Arabic one (letters43, D30 reader misread)"
    for lid, L in lines.items():
        if lid not in why_line:
            continue
        if lid in left:
            lf.append(dict(line=lid, page=L["page"], why=left[lid], text=L["text"][:120]))
            continue
        t = RU._sim_text(ans, lid, L["text"])
        toks, final = [], t
        for m in re.finditer(r"\S+", t):
            if TARGET.search(m.group(0)):
                new = fold_word(m.group(0))
                if new != m.group(0):
                    toks.append((m.start(), m.end()))
                    final = final[:m.start()] + new + final[m.end():]
        if not toks:
            continue
        sp = _spans(t, final, toks)
        words = [dict(line=lid, page=L["page"], frm=t[s:e], to=final[s:e],
                      kinds=[f"{a}>{b}" for a, b in zip(t[s:e], final[s:e]) if a != b]) for s, e in toks]
        if sp is None:
            lg += [dict(w, placed=False) for w in words]
            continue
        cur = t
        for a, b in sp:
            frm, to = cur[a:b], final[a:b]
            assert cur.find(frm) == a and final.find(to) == a
            w = why + ("; ی at a word's end written ى, the print's dot not checked" if "ی" in frm and
                       any(x == "ی" and y == "ى" for x, y in zip(frm, to)) else "")
            fx.append({"line": lid, "from": frm, "to": to, "why": w})
            cur = cur[:a] + to + cur[b:]
        lg += [dict(w, placed=True) for w in words]
        for sc in ans.get("sic") or []:             # a misprint flag quoting Azure's word: the word as now written
            if isinstance(sc, dict) and str(sc.get("line")) == lid and TARGET.search(sc.get("text") or ""):
                new = " ".join(fold_word(w) for w in sc["text"].split(" "))
                if new != sc["text"] and new in final:
                    log.setdefault("letters_sic", []).append(dict(line=lid, frm=sc["text"], to=new))
                    sc["text"] = new
