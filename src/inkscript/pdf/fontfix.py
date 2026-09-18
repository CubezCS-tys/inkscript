"""Give a typeset page's junk-encoded fonts a ToUnicode built from the OCR.

Some born-digital journals were set with fonts whose text extracts as
symbols (`ΔϴϤϨΘϟ`): a TrueType font under WinAnsiEncoding, or an embedded
subset under Identity-H, either way without a ToUnicode. The ink is the
font's own glyphs, so our ink layer is the wrong tool; what the page needs
is the mapping code → letter. Azure read the rendered page, so its word
boxes tell which glyphs form which word. Each glyph inside a word box gets
the word's letters, visual order against reading order, and every code's
letter is settled by vote across the document. The font then reads in every
viewer, and the page is native text — no invisible layer, no second layer.
"""
from __future__ import annotations
import re
from collections import Counter, defaultdict
import fitz

from ..text import RTL, ARABIC_LETTER, MARKS
from .type3 import hex16

LIG = {"لا": "لا", "لأ": "لأ", "لإ": "لإ", "لآ": "لآ"}     # one glyph, two letters


def _letters(text: str) -> list[str]:
    """The text as the glyph sequence a typeset font would use: lam-alef
    ligatures as one unit, combining marks folded onto the letter before."""
    out = []
    i = 0
    while i < len(text):
        two = text[i:i + 2]
        if two in LIG:
            out.append(two); i += 2; continue
        ch = text[i]
        if MARKS.match(ch) and out:
            out[-1] += ch
        else:
            out.append(ch)
        i += 1
    return out


def font_chars(page, fonts: dict) -> list[dict]:
    """Every glyph of the page's junk fonts: (font resource name, code, centre)."""
    out = []
    for span in page.get_texttrace():
        fname = span["font"]
        if fname not in fonts:
            continue
        kind = fonts[fname]["kind"]
        for uni, gid, origin, bbox in span["chars"]:
            if kind == "identity":
                code = gid
            else:
                try:
                    code = chr(uni).encode("cp1252")[0]                  # WinAnsi: the junk char IS the code
                except (UnicodeEncodeError, ValueError):
                    continue
            out.append(dict(font=fname, code=code, x=(bbox[0] + bbox[2]) / 2, y=(bbox[1] + bbox[3]) / 2, uni=uni))
    return out


def junk_fonts(doc, page) -> dict:
    """Non-Dummy fonts on the page with no ToUnicode, keyed by the base font
    name as `get_texttrace` reports it (with and without the subset tag)."""
    out = {}
    for xref, ext, subtype, basefont, name, *_ in page.get_fonts(full=True):
        if basefont == "Dummy" or doc.xref_get_key(xref, "ToUnicode")[0] == "xref":
            continue
        enc = doc.xref_get_key(xref, "Encoding")[1]
        if subtype == "Type0" and "Identity" in enc:
            kind = "identity"
        elif subtype in ("TrueType", "Type1") and "WinAnsi" in enc:
            kind = "winansi"
        else:
            continue
        for key in {basefont, basefont.split("+")[-1]}:
            out[key] = dict(xref=xref, kind=kind)
    return out


def collect_votes(doc, page, words: list[dict], votes: dict) -> dict:
    """Align the page's junk-font glyphs with Azure's word boxes (`load_azure`
    words: box in inches, the rendered page's frame) and vote letters per code."""
    fonts = junk_fonts(doc, page)
    if not fonts:
        return dict(fonts=0, chars=0, aligned=0)
    chars = font_chars(page, fonts)
    boxes = [(w["box"][0] * 72, w["box"][1] * 72, w["box"][2] * 72, w["box"][3] * 72, w["text"]) for w in words]
    per_word = defaultdict(list)
    for c in chars:
        for i, (x0, y0, x1, y1, _) in enumerate(boxes):
            if x0 <= c["x"] <= x1 and y0 <= c["y"] <= y1:
                per_word[i].append(c); break
    aligned = 0
    records = votes.setdefault("_records", [])                       # words the exact pass cannot settle, for `settle`
    for i, cs in per_word.items():
        text = boxes[i][4].strip()
        units = _letters(text)
        cs = sorted(cs, key=lambda c: c["x"])                          # visual order, left to right
        if not units:
            continue
        if RTL.search(text):
            units = units[::-1]                                        # right-to-left script: rightmost glyph is the first letter
        keys = [(c["font"], fonts[c["font"]]["xref"], c["code"]) for c in cs]
        if len(cs) == len(units):
            for k, u in zip(keys, units):
                votes[k][u] += 1
            aligned += len(cs)
        elif abs(len(cs) - len(units)) == 1:
            records.append((keys, units))
    return dict(fonts=len(fonts), chars=len(chars), aligned=aligned)


def settle(votes: dict) -> int:
    """Second pass for words that are one glyph short (a two-letter ligature
    such as في) or one glyph long (a mark or a kashida): try every merge of
    two adjacent letters, or every dropped glyph, and keep the reading whose
    other glyphs agree best with the first pass; it must agree on at least
    60% of them. Returns glyphs settled."""
    records = votes.pop("_records", [])
    best_of = {k: c.most_common(1)[0][0] for k, c in votes.items() if c}
    settled = 0
    for keys, units in records:
        options = []
        if len(keys) == len(units) - 1:
            for j in range(len(units) - 1):
                options.append(units[:j] + [units[j] + units[j + 1]] + units[j + 2:])
        else:
            for j in range(len(keys)):
                options.append((keys[:j] + keys[j + 1:], units))
        scored = []
        for opt in options:
            ks, us = (keys, opt) if isinstance(opt[0], str) else opt
            agree = sum(1 for k, u in zip(ks, us) if best_of.get(k) == u); known = sum(1 for k in ks if k in best_of)
            scored.append((agree, -known, ks, us))
        agree, negknown, ks, us = max(scored)
        if -negknown and agree >= 0.6 * -negknown:
            for k, u in zip(ks, us):
                votes[k][u] += 1
            settled += len(ks)
    return settled


def coverage(doc, page, mapping: dict) -> float:
    """Share of the page's junk-font glyphs whose code now has a letter
    (the fonts are found by xref: they carry a ToUnicode now)."""
    fonts = {}
    for xref, ext, subtype, basefont, name, *_ in page.get_fonts(full=True):
        if xref in mapping:
            kind = "identity" if "Identity" in doc.xref_get_key(xref, "Encoding")[1] else "winansi"
            for key in {basefont, basefont.split("+")[-1]}:
                fonts[key] = dict(xref=xref, kind=kind)
    chars = font_chars(page, fonts)
    if not chars:
        return 0.0
    ok = sum(1 for c in chars if c["code"] in mapping.get(fonts[c["font"]]["xref"], {}))
    return ok / len(chars)


def write_tounicode(doc, votes: dict, min_votes: int = 1, min_share: float = 0.6) -> dict:
    """One ToUnicode per font from the votes; codes without a clear winner
    stay as they are. Returns {font xref: {code: letter}}."""
    votes.pop("_records", None)
    by_font = defaultdict(dict)
    for (fname, xref, code), cnt in votes.items():
        letter, n = cnt.most_common(1)[0]
        if n >= min_votes and n / sum(cnt.values()) >= min_share:
            by_font[(fname, xref)][code] = letter
    out = {}
    for (fname, xref), m in by_font.items():
        two = "Identity" in doc.xref_get_key(xref, "Encoding")[1]
        w = 4 if two else 2
        lines = [f"<{code:0{w}X}> <{hex16(letter)}>" for code, letter in sorted(m.items())]
        cmap = ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /Azure-UCS def /CMapType 2 def\n"
                f"1 begincodespacerange <{0:0{w}X}> <{(1 << (4 * w)) - 1:0{w}X}> endcodespacerange\n")
        for i in range(0, len(lines), 100):
            chunk = lines[i:i + 100]
            cmap += f"{len(chunk)} beginbfchar\n" + "\n".join(chunk) + "\nendbfchar\n"
        cmap += "endcmap CMapName currentdict /CMap defineresource pop end end"
        tu = doc.get_new_xref(); doc.update_object(tu, "<< >>"); doc.update_stream(tu, cmap.encode())
        doc.xref_set_key(xref, "ToUnicode", f"{tu} 0 R")
        out[xref] = m
    return out
