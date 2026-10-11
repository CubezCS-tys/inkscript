"""A LuaTeX PDF's text rewritten the way pdfium (Chrome) reads right-to-left text (experiment 35, D27).

    stats = rewrite_visual(doc)          a pymupdf Document, changed in place

LuaTeX draws an Arabic line's glyphs in logical order, right to left. pdfium rebuilds a line with right-to-left
text by reversing its bidi segments (docs/pdf-writing-rules.md, "Text stored the way pdfium inverts it"), so it
reads such a line backwards, letter by letter. Wrapping each word in an /ActualText span (tried first) fixed the
letters but pdfium then skips its own new-line test for those objects and ran short lines together (list items,
headings: 80% of words in order on 0005-055-003-004). Here instead the text is stored as a native Arabic PDF
stores it, as this repository's faithful PDFs do:

  * every line's glyphs in visual order, left to right (sorted by their position on the page), one run per font;
    a vowel mark goes just before the letter it sits on (`كِتابُ` is stored `ُباتِك`, text.visual's rule);
  * a glyph standing for several letters (the lam-alef ligature) has its ToUnicode entry reversed when its
    letters are Arabic, since pdfium reverses them back;
  * kashida (tatweel glyphs babel adds to justify a line) is drawn as a filled bar, not as text, so copied
    words carry no elongation characters;
  * babel's own /ActualText spans (it marks mirrored brackets with them) are dropped: the drawn bracket's own
    character is what pdfium expects, since it mirrors brackets in right-to-left text itself.

The drawing does not change: every glyph keeps its place, font and size (only the order of the text-showing
operators does). Content streams written by LuaTeX are assumed: BT, Tf, `1 0 0 1 x y Tm [..]TJ`, ET; any other
operator ends a group, so lines are only regrouped between graphics-state changes.
"""
from __future__ import annotations

import re
import unicodedata

from . import fonts

_NUM = re.compile(rb"-?\d+(?:\.\d+)?|-?\.\d+")
_TM_TJ = re.compile(rb"^1 0 0 1 (-?[\d.]+) (-?[\d.]+) Tm \[(.*)\]TJ$")
_TM_ANY = re.compile(rb"^1 0 0 1 (-?[\d.]+) (-?[\d.]+) Tm .*(TJ|Tj)$")
_TF = re.compile(rb"^/(\S+) (-?[\d.]+) Tf$")
_TJ_ITEM = re.compile(rb"<([0-9A-Fa-f]+)>|(-?\d+(?:\.\d+)?|-?\.\d+)")
ARABIC = re.compile(r"[؀-ۿݐ-ݿࢠ-ࣿﭐ-﷿ﹰ-﻿]")
TATWEEL = "ـ"


def _parse_w(text: str) -> dict[int, float]:
    toks = re.findall(r"\[|\]|-?\d+(?:\.\d+)?", text)
    w, i = {}, 0
    if toks and toks[0] == "[":
        toks = toks[1:-1]
    while i < len(toks):
        c = int(float(toks[i]))
        if toks[i + 1] == "[":
            j = i + 2
            while toks[j] != "]":
                w[c] = float(toks[j])
                c += 1
                j += 1
            i = j + 1
        else:
            c2, wv = int(float(toks[i + 1])), float(toks[i + 2])
            for k in range(c, c2 + 1):
                w[k] = wv
            i += 3
    return w


def _parse_tounicode(cmap: str) -> dict[int, str]:
    out = {}
    for blk in re.findall(r"beginbfchar(.*?)endbfchar", cmap, re.S):
        for src, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]*)>", blk):
            out[int(src, 16)] = bytes.fromhex(dst).decode("utf-16-be", "replace") if dst else ""
    for blk in re.findall(r"beginbfrange(.*?)endbfrange", cmap, re.S):
        for a, b, dst in re.findall(r"<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>\s*<([0-9A-Fa-f]+)>", blk):
            base = int(dst, 16)
            for k, c in enumerate(range(int(a, 16), int(b, 16) + 1)):
                out[c] = chr(base + k)
    return out


class _Font:
    def __init__(self, doc, xref: int, basefont: str):
        obj = doc.xref_object(xref)
        self.size_cache = {}
        m = re.search(r"/DescendantFonts\s*\[\s*(\d+) 0 R", obj)
        dobj = doc.xref_object(int(m.group(1))) if m else ""
        wm = re.search(r"/W\s*(\d+) 0 R", dobj)
        wtext = doc.xref_object(int(wm.group(1))) if wm else (re.search(r"/W\s*(\[.*?\]\s*\])", dobj, re.S) or [None, ""])[1]
        self.w = _parse_w(wtext) if wtext else {}
        dw = re.search(r"/DW\s+(\d+)", dobj)
        self.dw = float(dw.group(1)) if dw else 1000.0
        tm = re.search(r"/ToUnicode\s+(\d+) 0 R", obj)
        self.tu_xref = int(tm.group(1)) if tm else 0
        self.uni = _parse_tounicode(doc.xref_stream(self.tu_xref).decode("latin1")) if self.tu_xref else {}
        self.basefont = basefont.split("+", 1)[-1]
        self._bbox = None
        self.cid = "/Type0" in obj and "Identity-H" in obj           # two-byte codes: this rewrite reads them
        self.can_alias = self.cid and "/CIDToGIDMap /Identity" in dobj   # TrueType outlines: aliases possible
        self.desc_xref = int(m.group(1)) if m else 0
        self.w_xref = int(wm.group(1)) if wm else 0
        self.n_base = (max(self.w) + 1) if self.w else 0
        self.aliases = {}            # (gid shown, text) -> alias cid
        self._gs = None

    def alias(self, text: str):
        """A code that draws nothing (the space glyph), zero wide, whose text is `text`: a vowel mark's letter in
        the line's run while the mark itself is drawn as an outline at its own height."""
        if self.space_gid is None or not self.can_alias:
            return None
        k = text
        if k not in self.aliases:
            self.aliases[k] = self.n_base + len(self.aliases)
        return self.aliases[k]

    def finalize(self, doc) -> int:
        """Write the aliases: CIDToGIDMap (identity, then the space glyph), zero widths, ToUnicode entries."""
        if not self.aliases or not self.can_alias:
            return 0
        n = self.n_base + len(self.aliases)
        m = bytearray()
        for c in range(n):
            g = c if c < self.n_base else self.space_gid
            m += bytes(((g >> 8) & 255, g & 255))
        mx = doc.get_new_xref()
        doc.update_object(mx, "<<>>")
        doc.update_stream(mx, bytes(m))
        doc.xref_set_key(self.desc_xref, "CIDToGIDMap", "%d 0 R" % mx)
        if self.w_xref:
            wt = doc.xref_object(self.w_xref).strip()
            wt = wt[:wt.rfind("]")] + " %d [%s] ]" % (self.n_base, " ".join("0" for _ in self.aliases))
            doc.update_object(self.w_xref, wt)
        if self.tu_xref:
            cm = doc.xref_stream(self.tu_xref).decode("latin1")
            ent = "\n".join("<%04X> <%s>" % (cid, t.encode("utf-16-be").hex().upper())
                             for t, cid in self.aliases.items())
            cm = cm.replace("endcmap", "%d beginbfchar\n%s\nendbfchar\nendcmap" % (len(self.aliases), ent), 1)
            doc.update_stream(self.tu_xref, cm.encode("latin1"))
        return len(self.aliases)

    def outline(self, gid: int, x: float, y: float, size: float) -> bytes | None:
        """The glyph drawn as a filled path at (x, y), from the source font file."""
        if self.glyph_bbox(gid) is None:
            return None
        if self._gs is None:
            from fontTools.ttLib import TTFont
            self._gs = TTFont(str(self._path), lazy=True).getGlyphSet()
        from fontTools.pens.basePen import BasePen
        sc = size / self._upm
        ops = []

        class Pen(BasePen):
            def _moveTo(self, p):
                ops.append(b"%.3f %.3f m" % (x + p[0] * sc, y + p[1] * sc))

            def _lineTo(self, p):
                ops.append(b"%.3f %.3f l" % (x + p[0] * sc, y + p[1] * sc))

            def _curveToOne(self, p1, p2, p3):
                ops.append(b"%.3f %.3f %.3f %.3f %.3f %.3f c" % tuple(v for q in (p1, p2, p3)
                                                                      for v in (x + q[0] * sc, y + q[1] * sc)))

            def _qCurveToOne(self, p1, p2):
                p0 = self._getCurrentPoint()
                c1 = (p0[0] + 2 / 3 * (p1[0] - p0[0]), p0[1] + 2 / 3 * (p1[1] - p0[1]))
                c2 = (p2[0] + 2 / 3 * (p1[0] - p2[0]), p2[1] + 2 / 3 * (p1[1] - p2[1]))
                self._curveToOne(c1, c2, p2)

            def _closePath(self):
                ops.append(b"h")
        try:
            self._gs[self._order[gid]].draw(Pen(self._gs))
        except Exception:
            return None
        return (b"\n".join(ops) + b"\nf\n") if ops else b""

    def width(self, gid: int) -> float:
        return self.w.get(gid, self.dw)

    @property
    def space_gid(self):
        if not hasattr(self, "_space"):
            self._space = next((g for g, u in sorted(self.uni.items()) if u == " "), None)
        return self._space

    def is_mark(self, gid: int) -> bool:
        u = self.uni.get(gid, "")
        return bool(u) and all(unicodedata.category(c) == "Mn" for c in u)

    def is_tatweel(self, gid: int) -> bool:
        return self.uni.get(gid, "") == TATWEEL

    def glyph_bbox(self, gid: int):
        """The glyph's ink box in font units, from the source font file (LuaTeX keeps the original glyph ids)."""
        if self._bbox is None:
            self._bbox = {}
            path = None
            name = self.basefont.lower()
            for key, fam in (("markazi", "markazi"), ("amiri", "amiri"), ("notonaskh", "naskh"), ("notokufi", "kufi")):
                if name.replace(" ", "").startswith(key):
                    path = fonts.font_path(fam, "bold" if "bold" in name else "regular")
            if path:
                try:
                    from fontTools.ttLib import TTFont
                    f = TTFont(str(path), lazy=True)
                    self._glyf, self._order, self._upm = f["glyf"], f.getGlyphOrder(), f["head"].unitsPerEm
                    self._path = path
                    self._ok = True
                except Exception:
                    self._ok = False
            else:
                self._ok = False
        if not self._ok:
            return None
        if gid not in self._bbox:
            try:
                g = self._glyf[self._order[gid]]
                self._bbox[gid] = (g.xMin, g.yMin, g.xMax, g.yMax, self._upm) if hasattr(g, "xMin") else None
            except Exception:
                self._bbox[gid] = None
        return self._bbox[gid]


def _fix_tounicode(doc, f: _Font, done: set) -> int:
    """Reverse multi-letter Arabic entries (ligatures): pdfium reverses a right-to-left segment's letters."""
    if not f.tu_xref or f.tu_xref in done:
        return 0
    done.add(f.tu_xref)
    s = doc.xref_stream(f.tu_xref).decode("latin1")
    n = 0

    def fix(m):
        nonlocal n
        src, dst = m.group(1), m.group(2)
        try:
            u = bytes.fromhex(dst).decode("utf-16-be")
        except (ValueError, UnicodeDecodeError):
            return m.group(0)
        if len(u) >= 2 and ARABIC.search(u) and not re.search(r"[A-Za-z0-9]", u):
            n += 1
            # marks stay after their letter inside the reversed sequence (text.visual's rule)
            return "<%s> <%s>" % (src, u[::-1].encode("utf-16-be").hex().upper())
        return m.group(0)
    s2 = re.sub(r"<([0-9A-Fa-f]{4})>\s*<([0-9A-Fa-f]{8,})>", fix, s)
    if n:
        doc.update_stream(f.tu_xref, s2.encode("latin1"))
        f.uni = _parse_tounicode(s2)
    return n


def _glyphs(tj: bytes, x: float, y: float, size: float, f: _Font):
    out = []
    pen = x
    for hexs, num in _TJ_ITEM.findall(tj):
        if hexs:
            for k in range(0, len(hexs), 4):
                gid = int(hexs[k:k + 4], 16)
                w = f.width(gid)
                out.append([pen, y, gid, w])
                pen += w * size / 1000
        else:
            pen -= float(num) * size / 1000
    return out


SPACE_FONT = "InkSp"           # Helvetica (base 14, not embedded): only its space, between words
SPACE_W = 278                  # Helvetica's space width (1/1000 em)
SPACE_GAP = 0.12               # a gap wider than this (em of the line's font) between two glyphs is a word space
_COLOR = re.compile(rb"^[-\d. ]+ (g|G|rg|RG|k|K)( [-\d. ]+ (g|G|rg|RG|k|K))*$")


def _rewrite_group(blocks, fontmap, st, init_color, final_color=None) -> bytes:
    """blocks: [(fontname, size, x, y, tj, color)] in stream order -> the same glyphs, each line in visual order,
    a space glyph in every word gap, kashida as bars."""
    gl, raw = [], []             # gl: [x, y, gid, w, font, size, order, color]; raw: blocks left as they were
    for i, (fn, size, x, y, tj, col, line) in enumerate(blocks):
        f = fontmap.get(fn)
        if f is None:                # a font this rewrite does not read (TeX's maths fonts): its text stays as is
            raw.append((fn, size, col, line))
            continue
        for g in _glyphs(tj, x, y, size, f):
            gl.append(g + [fn, size, i, col, len(gl)])
    if not gl and not raw:
        return b""
    last_color = final_color if final_color is not None else blocks[-1][5]
    bases = sorted({round(g[1], 1) for g in gl if not fontmap[g[4]].is_mark(g[2])})
    paths = []                   # (colour, path ops): vowel marks and kashida, drawn as outlines
    def line_of(g):
        if not bases:
            return round(g[1], 1)
        return min(bases, key=lambda b: abs(b - g[1]))
    lines = {}
    for g in gl:
        lines.setdefault(line_of(g), []).append(g)
    out, emitted = [], [init_color]
    def color(col):
        if col is not None and col != emitted[0]:
            out.append(col + b"\n")
            emitted[0] = col
    for ly, gs in sorted(lines.items(), key=lambda kv: min(g[6] for g in kv[1])):
        base = [g for g in gs if not fontmap[g[4]].is_mark(g[2])]
        def key(g):
            f = fontmap[g[4]]
            if f.is_mark(g[2]) and base:
                # its letter: the base glyph written just before it (HarfBuzz writes a mark after its letter)
                # if it sits over that letter; else the letter under it
                cx = g[0] + g[3] * g[5] / 2000
                prev = [b for b in base if b[8] < g[8]]
                host = max(prev, key=lambda b: b[8]) if prev else None
                if host is None or not (host[0] - 0.25 * g[5] <= cx <= host[0] + host[3] * host[5] / 1000 + 0.25 * g[5]):
                    host = min(base, key=lambda b: 0 if b[0] <= cx <= b[0] + b[3] * b[5] / 1000
                               else min(abs(cx - b[0]), abs(cx - b[0] - b[3] * b[5] / 1000)))
                return (host[0], 0, g[0])
            return (g[0], 1, 0)
        gs.sort(key=key)
        st["lines"] += 1
        # word gaps: a space glyph of the run's own font goes in (pdfium reads a lone space object as filling the
        # gap and then adds none of its own); kashida bars count as ink, not as a gap
        items, prev_end, prev_size, bars = [], None, None, []
        hosts = {}
        for g in gs:
            f = fontmap[g[4]]
            mark = f.is_mark(g[2])
            if mark and abs(g[1] - ly) >= 0.05:
                # a raised (or lowered) vowel mark: drawn as its outline where it is, and carried in the line's run
                # as a zero-wide code at the baseline, just before its letter
                path = f.outline(g[2], g[0], g[1], g[5])
                cid = f.alias(f.uni.get(g[2], "")) if path is not None else None
                if cid is not None:
                    paths.append((g[7], path))
                    hx = key(g)[0]
                    hy = min(base, key=lambda b: abs(b[0] - hx))[1] if base else ly   # its letter's own baseline
                    items.append(([hx, hy, cid, 0.0, g[4], g[5], g[6], g[7]], None))
                    st["marks"] += 1
                    continue
            sp = None
            if not mark and abs(g[1] - ly) < 0.5:
                if prev_end is not None:
                    gap = g[0] - prev_end
                    if gap > SPACE_GAP * max(prev_size, g[5]):
                        sp = (prev_end, gap)
                prev_end, prev_size = g[0] + g[3] * g[5] / 1000, g[5]
            if f.is_tatweel(g[2]):
                path = f.outline(g[2], g[0], g[1], g[5])
                if path is not None:
                    paths.append((g[7], path))
                    st["kashida"] += 1
                    continue
            if sp:                   # the word space goes before the vowel marks stored ahead of this letter
                k = len(items)
                while k > 0 and items[k - 1][0][3] == 0.0 and items[k - 1][1] is None and \
                        abs(items[k - 1][0][0] - g[0]) < 1e-6:
                    k -= 1
                if k < len(items):
                    items[k] = (items[k][0], sp)
                    sp = None
            items.append((g, sp))
        runs, cur = [], None
        for g, sp in items:
            k = (g[4], g[5], round(g[1], 2), g[7])
            f = fontmap[g[4]]
            if sp and f.space_gid is None:
                runs.append(("hspace", sp, ly, g[5]))
                cur = None
                sp = None
            if cur is None or cur[1] != k:
                cur = ["run", k, [], sp]           # sp: the run starts with a space at sp[0]
                runs.append(cur)
                cur[2].append((g, False))
            else:
                cur[2].append((g, bool(sp)))
        for r in runs:
            if r[0] == "hspace":
                _, (x, gap), y, sz = r
                s_sp = min(sz, 0.9 * gap * 1000 / SPACE_W)
                st["spaces"] += 1
                out.append(b"BT\n/%s %.3f Tf\n1 0 0 1 %.3f %.3f Tm <%02X>Tj\nET\n" % (
                    SPACE_FONT.encode(), s_sp, x, y, 1 + st["spaces"] % 7))
                continue
            (fn, size, yy, col), gg, lead = r[1], r[2], r[3]
            f = fontmap[fn]
            color(col)
            parts, pen = [], None
            x0 = gg[0][0][0]
            if lead:
                x0, pen = lead[0], lead[0] + f.width(f.space_gid) * size / 1000
                parts.append(b"<%04X>" % f.space_gid)
                st["spaces"] += 1
            for g, space in gg:
                if space and pen is not None:
                    parts.append(b"<%04X>" % f.space_gid)
                    pen += f.width(f.space_gid) * size / 1000
                    st["spaces"] += 1
                if pen is not None:
                    kern = (pen - g[0]) * 1000 / size
                    if abs(kern) > 0.05:
                        parts.append(b"%.1f" % kern)
                parts.append(b"<%04X>" % g[2])
                pen = g[0] + g[3] * size / 1000
            out.append(b"BT\n/%s %s Tf\n1 0 0 1 %.3f %.3f Tm [%s]TJ\nET\n" % (
                fn.encode(), (b"%.5f" % size).rstrip(b"0").rstrip(b"."), x0, yy, b"".join(parts)))
    for col, path in paths:
        color(col)
        out.append(path)
    for fn, size, col, line in raw:
        color(col)
        out.append(b"BT\n/%s %s Tf\n%s\nET\n" % (fn.encode(), (b"%.5f" % size).rstrip(b"0").rstrip(b"."), line))
    color(last_color)
    return b"".join(out)


def _add_space_font(doc, page) -> None:
    """/InkSp (Helvetica, WinAnsi) in the page's font resources."""
    if not hasattr(doc, "_ink_space_font"):
        x = doc.get_new_xref()
        doc.update_object(x, "<</Type/Font/Subtype/Type1/BaseFont/Helvetica/Encoding<</Type/Encoding"
                             "/BaseEncoding/WinAnsiEncoding/Differences[1/space/space/space/space/space/space/space]>>>>")
        doc._ink_space_font = x
    x = doc._ink_space_font
    kind, val = doc.xref_get_key(page.xref, "Resources")
    if kind == "xref":
        rx = int(val.split()[0])
        fk, fv = doc.xref_get_key(rx, "Font")
        if fk == "xref":
            doc.xref_set_key(int(fv.split()[0]), SPACE_FONT, "%d 0 R" % x)
        else:
            doc.xref_set_key(rx, "Font/" + SPACE_FONT, "%d 0 R" % x)
    else:
        fk, fv = doc.xref_get_key(page.xref, "Resources/Font")
        if fk == "xref":
            doc.xref_set_key(int(fv.split()[0]), SPACE_FONT, "%d 0 R" % x)
        else:
            doc.xref_set_key(page.xref, "Resources/Font/" + SPACE_FONT, "%d 0 R" % x)


def rewrite_visual(doc) -> dict:
    st = dict(lines=0, kashida=0, ligatures=0, groups=0, skipped=0, actualtext_dropped=0, spaces=0, marks=0,
              aliases=0)
    fonts_by_xref, done_tu = {}, set()
    for page in doc:
        fontmap = {}
        for xref, _ext, _typ, basefont, name, _enc in page.get_fonts():
            if xref not in fonts_by_xref:
                try:
                    fonts_by_xref[xref] = _Font(doc, xref, basefont)
                    st["ligatures"] += _fix_tounicode(doc, fonts_by_xref[xref], done_tu)
                except Exception:
                    fonts_by_xref[xref] = None
            if fonts_by_xref[xref] is not None and fonts_by_xref[xref].cid:
                fontmap[name] = fonts_by_xref[xref]
        if not fontmap:
            continue
        _add_space_font(doc, page)
        for cx in page.get_contents():
            lines = doc.xref_stream(cx).split(b"\n")
            out, group, raw, i = [], [], [], 0
            marks = []                   # open marked-content sequences: True = an /ActualText span we dropped
            cur_color = [None]
            group_color = [None]
            def flush():
                if group:
                    new = _rewrite_group(group, fontmap, st, group_color[0], cur_color[0])
                    if new is None:
                        out.extend(raw)
                        st["skipped"] += 1
                    else:
                        out.append(new.rstrip(b"\n"))
                        st["groups"] += 1
                group.clear()
                raw.clear()
            while i < len(lines):
                ln = lines[i].strip()
                if ln.endswith(b"BDC") and b"/ActualText" in ln:
                    st["actualtext_dropped"] += 1
                    marks.append(True)
                    i += 1
                    continue
                if ln.endswith(b"BDC") or ln.endswith(b"BMC"):
                    flush()
                    marks.append(False)
                    out.append(lines[i])
                    i += 1
                    continue
                if ln == b"EMC":
                    if marks and marks.pop():
                        i += 1
                        continue
                    flush()
                    out.append(lines[i])
                    i += 1
                    continue
                if ln == b"BT":
                    if not group:
                        group_color[0] = cur_color[0]
                    j, fn, size, ok, blk = i + 1, None, None, True, []
                    col = cur_color[0]
                    while j < len(lines) and lines[j].strip() != b"ET":
                        t = lines[j].strip()
                        m1, m2 = _TF.match(t), _TM_TJ.match(t)
                        if not m2 and fn and fn not in fontmap:
                            m2 = _TM_ANY.match(t)
                        if m1:
                            fn, size = m1.group(1).decode(), float(m1.group(2))
                        elif m2 and fn and fn not in fontmap:
                            blk.append((fn, size, float(m2.group(1)), float(m2.group(2)), b"", col, t))
                        elif m2 and fn:
                            blk.append((fn, size, float(m2.group(1)), float(m2.group(2)), m2.group(3), col, t))
                        elif _COLOR.match(t):
                            col = t
                        elif t.startswith(b"/Span") or t == b"EMC" or not t:
                            pass
                        else:
                            ok = False
                        j += 1
                    if ok and j < len(lines):
                        group.extend(blk)
                        raw.extend(lines[i:j + 1])
                        cur_color[0] = col
                        i = j + 1
                        continue
                    flush()
                    out.extend(lines[i:j + 1])
                    cur_color[0] = col
                    i = j + 1
                    continue
                if _COLOR.match(ln):
                    flush()
                    cur_color[0] = ln
                    out.append(lines[i])
                    i += 1
                    continue
                flush()
                out.append(lines[i])
                i += 1
            flush()
            doc.update_stream(cx, b"\n".join(out))
    for f in fonts_by_xref.values():
        if f is not None and f.cid:
            st["aliases"] += f.finalize(doc)
    return st


