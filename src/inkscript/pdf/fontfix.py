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


_TOK = re.compile(rb"/([^\s/\[\]()<>{}%]+)|(\()|(<(?![<])[0-9A-Fa-f\s]*>)|(\[)|(\])|(<<|>>)|(-?\d*\.?\d+)|([A-Za-z'\"*]+)|(%[^\n]*)")


def stream_codes(doc, page) -> dict:
    """Char codes per font resource name, in stream order, from the page's
    content: what the text operators actually carry. The bytes are the
    codes for a simple font; two bytes make one code under Identity-H."""
    data = b"".join(doc.xref_stream(x) or b"" for x in page.get_contents())
    fonts = {f[4]: f for f in page.get_fonts(full=True)}
    out = defaultdict(list); seq = []; cur = None; two = False; i = 0; n = len(data); stack = []
    def literal(start):                                                # a (…) string with escapes; returns bytes, end index
        depth = 1; j = start; buf = bytearray()
        while j < n and depth:
            c = data[j]
            if c == 0x5C:                                              # backslash
                j += 1; e = data[j:j + 1]
                if e in b"nrtbf": buf.append({b"n": 10, b"r": 13, b"t": 9, b"b": 8, b"f": 12}[e])
                elif e.isdigit():
                    k = j
                    while k < j + 3 and data[k:k + 1].isdigit(): k += 1
                    buf.append(int(data[j:k], 8) & 255); j = k - 1
                elif e in b"\r\n": pass
                else: buf += e
            elif c == 0x28: depth += 1; buf.append(c)
            elif c == 0x29:
                depth -= 1
                if depth: buf.append(c)
            else: buf.append(c)
            j += 1
        return bytes(buf), j
    def emit(b):
        if cur is None: return
        codes = [int.from_bytes(b[k:k + 2], "big") for k in range(0, len(b) - 1, 2)] if two else list(b)
        out[cur].extend(codes); seq.extend((cur, c) for c in codes)
    while i < n:
        m = _TOK.match(data, i)
        if not m:
            i += 1; continue
        i = m.end()
        if m.group(1): stack.append(("/", m.group(1).decode("latin1")))
        elif m.group(2):
            b, i = literal(i); stack.append(("s", b))
        elif m.group(3): stack.append(("s", bytes.fromhex(re.sub(rb"\s", b"", m.group(3)[1:-1]).decode() + ("0" if len(re.sub(rb"\s", b"", m.group(3)[1:-1])) % 2 else ""))))
        elif m.group(4) or m.group(5) or m.group(6) or m.group(7) or m.group(9): stack.append(("o", m.group(0)))
        elif m.group(8):
            op = m.group(8)
            if op == b"Tf":
                names = [v for t, v in stack if t == "/"]
                if names:
                    cur = names[-1]; f = fonts.get(cur); two = bool(f) and f[2] == "Type0"
            elif op in (b"Tj", b"'", b'"'):
                strs = [v for t, v in stack if t == "s"]
                if strs: emit(strs[-1])
            elif op == b"TJ":
                for t, v in stack:
                    if t == "s": emit(v)
            stack = []
    out["_seq"] = seq                                                  # every code in stream order, with its resource
    return out


def font_chars(page, fonts: dict, doc=None) -> list[dict]:
    """Every glyph of the page's junk fonts: (font resource name, code,
    centre). Codes come from the content stream and are paired with the
    traced glyphs in stream order; the base font name must agree at every
    position (two resources may share one base name — an embedded subset
    and a non-embedded copy — and MuPDF names only the base)."""
    if doc is None:
        return []
    by_res = stream_codes(doc, page)
    fonts_all = {f[4]: f for f in page.get_fonts(full=True)}
    stream = by_res.get("_seq", [])                                     # every code in stream order
    traced = [(s["font"], uni, gid, bbox) for s in sorted(page.get_texttrace(), key=lambda s: s["seqno"]) for uni, gid, origin, bbox in s["chars"]]
    if len(stream) != len(traced):
        return []
    base = lambda f: {f[3], f[3].split("+")[-1]}
    out = []
    for (res, code), (bname, uni, gid, bbox) in zip(stream, traced):
        f = fonts_all.get(res)
        if not f or bname not in base(f):
            return []                                                    # the two orders disagree: no votes from this page
        if res in fonts:
            out.append(dict(font=res, code=code, x=(bbox[0] + bbox[2]) / 2, y=(bbox[1] + bbox[3]) / 2, uni=uni))
    return out


def junk_fonts(doc, page) -> dict:
    """Non-Dummy fonts on the page whose text extracts as junk, by resource
    name: no ToUnicode, or a ToUnicode that yields mostly symbols (under 90%
    letters and digits over at least five characters)."""
    good = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-z0-9]")
    seen = Counter(); okc = Counter()
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                t = sp["text"].replace(" ", ""); seen[sp["font"]] += len(t); okc[sp["font"]] += len(good.findall(t))
    out = {}
    for xref, ext, subtype, basefont, name, *_ in page.get_fonts(full=True):
        if basefont == "Dummy":
            continue
        base = basefont.split("+")[-1]
        junk_text = seen[base] >= 5 and okc[base] < 0.9 * seen[base]
        if doc.xref_get_key(xref, "ToUnicode")[0] == "xref" and not junk_text:
            continue
        enc = doc.xref_get_key(xref, "Encoding")[1]
        if subtype == "Type0":
            kind = "identity" if "Identity" in enc else "cid"
        else:
            kind = "winansi" if "WinAnsi" in enc else "simple"        # MacRoman, /Differences, built-in: one byte per code
        out[name] = dict(xref=xref, kind=kind)
    return out


def collect_votes(doc, page, words: list[dict], votes: dict) -> dict:
    """Align the page's junk-font glyphs with Azure's word boxes (`load_azure`
    words: box in inches, the rendered page's frame) and vote letters per code."""
    fonts = junk_fonts(doc, page)
    if not fonts:
        return dict(fonts=0, chars=0, aligned=0)
    chars = font_chars(page, fonts, doc)
    boxes = [(w["box"][0] * 72, w["box"][1] * 72, w["box"][2] * 72, w["box"][3] * 72, w["text"]) for w in words]
    def box_of(c):
        for i, (x0, y0, x1, y1, _) in enumerate(boxes):
            if x0 <= c["x"] <= x1 and y0 <= c["y"] <= y1:
                return i
        return None
    # The font's space glyph lies between words, so most of its occurrences
    # fall outside every word box; the ones that fall inside a neighbour's
    # box would be counted as letters and poison that word's votes. A code
    # that is outside boxes 40% of the time is a separator: a space vote,
    # never a letter.
    inside = Counter(); total = Counter()
    for c in chars:
        c["box"] = box_of(c); total[c["code"]] += 1; inside[c["code"]] += c["box"] is not None
    per_word = defaultdict(list)
    for c in chars:
        key = (c["font"], fonts[c["font"]]["xref"], c["code"])
        if inside[c["code"]] < 0.6 * total[c["code"]]:
            votes[key][" "] += 1
        elif c["box"] is not None:
            per_word[c["box"]].append(c)
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
        if len(cs) == 1 and 1 < len(units) <= 3:
            votes[keys[0]]["".join(units[::-1] if RTL.search(text) else units)] += 1   # one glyph, one short word: a ligature (في)
            aligned += 1
        elif len(cs) == len(units):
            for k, u in zip(keys, units):
                votes[k][u] += 1
            aligned += len(cs)
        else:
            records.append((keys, units))
    return dict(fonts=len(fonts), chars=len(chars), aligned=aligned, keys=[(fonts[c["font"]]["xref"], c["code"]) for c in chars])


def _align(keys, units, best_of, share_of):
    """Best alignment of a word's glyphs (in reading order) with its letters:
    a glyph may stand for one to three letters (ligatures), a glyph may
    stand for nothing (a kashida, a mark the OCR did not write), a letter
    may have no glyph. Scored by the votes so far. Returns (score per glyph
    used, pairs)."""
    m, n = len(keys), len(units)
    NEG = -1e9
    best = [[NEG] * (n + 1) for _ in range(m + 1)]; back = [[None] * (n + 1) for _ in range(m + 1)]
    best[0][0] = 0.0
    for i in range(m + 1):
        for j in range(n + 1):
            if best[i][j] == NEG:
                continue
            if i < m:                                                  # glyph i stands for nothing
                v = best[i][j] - 0.6
                if v > best[i + 1][j]:
                    best[i + 1][j] = v; back[i + 1][j] = (i, j, None)
            if j < n:                                                  # letter j has no glyph
                v = best[i][j] - 0.8
                if v > best[i][j + 1]:
                    best[i][j + 1] = v; back[i][j + 1] = (i, j, None)
            if i < m:
                for k in (1, 2, 3):
                    if j + k > n:
                        break
                    u = "".join(units[j:j + k])
                    known = best_of.get(keys[i])
                    sc = (share_of[keys[i]] if known == u else -0.5) if known else 0.15 - 0.1 * (k - 1)
                    v = best[i][j] + sc
                    if v > best[i + 1][j + k]:
                        best[i + 1][j + k] = v; back[i + 1][j + k] = (i, j, u)
    pairs = []; i, j = m, n
    while (i, j) != (0, 0):
        pi, pj, u = back[i][j]
        if u is not None:
            pairs.append((keys[pi], u))
        i, j = pi, pj
    return best[m][n] / max(1, m), pairs[::-1]


def settle(votes: dict) -> int:
    """Second pass for words that are one glyph short (a two-letter ligature
    such as في) or one glyph long (a mark or a kashida): try every merge of
    two adjacent letters, or every dropped glyph, and keep the reading whose
    other glyphs agree best with the first pass; it must agree on at least
    60% of them. Returns glyphs settled."""
    records = votes.pop("_records", [])
    best_of = {k: c.most_common(1)[0][0] for k, c in votes.items() if c}
    settled = 0
    later = []
    for keys, units in records:
        if abs(len(keys) - len(units)) != 1:
            later.append((keys, units)); continue
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
        else:
            later.append((keys, units))
    # third pass: everything left, by alignment against the votes so far
    for _round in range(2):
        best_of = {k: c.most_common(1)[0][0] for k, c in votes.items() if c}
        share_of = {k: c.most_common(1)[0][1] / sum(c.values()) for k, c in votes.items() if c}
        rest = []
        for keys, units in later:
            score, pairs = _align(keys, units, best_of, share_of)
            known = sum(1 for k, _ in pairs if k in best_of)
            if pairs and score >= 0.3 and known >= 0.5 * len(pairs):
                for k, u in pairs:
                    votes[k][u] += 1
                settled += len(pairs)
            else:
                rest.append((keys, units))
        later = rest
    return settled


def coverage(keys: list, mapping: dict) -> float:
    """Share of a page's junk-font glyphs (the `keys` collect_votes returned
    for it, before any ToUnicode was written) whose code now has a letter."""
    if not keys:
        return 0.0
    return sum(1 for xref, code in keys if code in mapping.get(xref, {})) / len(keys)


def write_tounicode(doc, votes: dict, min_votes: int = 1, min_share: float = 0.5) -> dict:
    """One ToUnicode per font from the votes; codes without a clear winner
    stay as they are. A value of several letters (a ligature) is stored the
    way our own layer stores text — reversed, marks kept in place — because
    pdfium reverses an Arabic segment character by character.
    Returns {font xref: {code: letter}}."""
    from ..text import visual
    votes.pop("_records", None)
    by_font = defaultdict(dict)
    for (fname, xref, code), cnt in votes.items():
        letter, n = cnt.most_common(1)[0]
        if n >= min_votes and n / sum(cnt.values()) >= min_share:
            by_font[(fname, xref)][code] = visual(letter, True) if len(letter) > 1 else letter
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
