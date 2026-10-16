"""Experiment 41: the text layer of a Chromium-printed PDF, replaced by the one the faithful PDFs carry.

Chromium (Skia) stores Arabic text in a way pdfium reads badly: vowelled words fall apart into letters and lines
(0747's verse), لأ / لإ split ("ا ألسف"), spaces between Latin words vanish in some faces (1140: "dessciences");
pdfium found 96.0% of the words of the 55 articles where the LuaLaTeX editions had 99.5-99.97% (README). So:

  1. deglyph(doc)      every glyph Chromium drew is drawn again from its own outline (one Form XObject per glyph
                       of each embedded font, placed at the glyph's own matrix): the page looks the same and holds
                       no text. Fonts are TrueType (outlines from the embedded FontFile2, fontTools) or Type 3
                       (their CharProcs).
  2. add_layer(...)    the words as the browser laid them out (WORDS_JS, run by print_worker.py before printing:
                       each word's text from the page's DOM and its box from a DOM Range, its baseline from the
                       font's metrics) are written as an invisible text layer with inkscript's own writer
                       (pdf/type3.write_text_layer: one Type 3 glyph per word, stored the way pdfium reads right to
                       left, docs/pdf-writing-rules.md), each word's glyph its box. Selection highlights whole words.

The one-column PDF is paginated by Chromium: an empty marker at the start of each DOM line, the target of a hidden
link, comes out as a named destination giving the line's page and place (measured: MuPDF's own line baselines
jump on vowelled lines, so matching printed lines failed on 0747's verse); the layout PDF's pages are the view's.
"""
from __future__ import annotations

import io
import re
from collections import Counter, defaultdict

# Run in the page (Playwright evaluate) with the root selector and the kind; returns the lines of words.
WORDS_JS = r"""
([kind]) => {
 const roots = kind === 'layout' ? [...document.querySelectorAll('.lpage')] : [document.querySelector('article.ed') || document.body];
 const SKIP = '.katex,.ob,.contmark,script,style,button,figure.clip,.noise,math,.pop,.links,svg';
 const cv = document.createElement('canvas').getContext('2d'), mc = {};
 function metrics(cs) {
  const k = cs.fontStyle + ' ' + cs.fontWeight + ' 100px ' + cs.fontFamily;
  if (!(k in mc)) { cv.font = k; const m = cv.measureText('بx'); mc[k] = [m.fontBoundingBoxAscent / 100, m.fontBoundingBoxDescent / 100]; }
  return mc[k]; }
 const disp = new Map();
 function blockOf(e) { while (e) { let d = disp.get(e); if (d === undefined) { d = getComputedStyle(e).display; disp.set(e, d); }
   if (!d.startsWith('inline') && d !== 'contents') return e; e = e.parentElement; } return null; }
 const lines = [], starts = [];
 roots.forEach((root, pi) => {
  const R0 = root.getBoundingClientRect();
  const ox = kind === 'layout' ? R0.left : -scrollX, oy = kind === 'layout' ? R0.top : -scrollY;
  const tw = document.createTreeWalker(root, NodeFilter.SHOW_TEXT, {acceptNode(n) {
    const e = n.parentElement; return (!e || e.closest(SKIP)) ? 2 : 1; }});
  const words = []; let cur = null, curB = null, curS = null, n;
  const close = () => { if (cur) words.push(cur); cur = null; };
  while ((n = tw.nextNode())) {
   const e = n.parentElement, b = blockOf(e), s = e.closest('sup,a.fnref');
   if (b !== curB || s !== curS) { close(); curB = b; curS = s; }
   const t = n.data;
   for (let i = 0; i < t.length; i++) {
    if (/\s/.test(t[i])) { close(); continue; }
    if (!cur) cur = {text: '', segs: [], block: b, el: e, sup: s};
    cur.text += t[i];
    const sg = cur.segs[cur.segs.length - 1];
    if (sg && sg[0] === n && sg[2] === i) sg[2] = i + 1; else cur.segs.push([n, i, i + 1]);
   }
  }
  close();
  const byBlock = new Map();
  const rg = document.createRange();
  for (const w of words) {
   const cs = getComputedStyle(w.el), fs = parseFloat(cs.fontSize), [a] = metrics(cs);
   const L = w.segs[w.segs.length - 1];
   rg.setStart(w.segs[0][0], w.segs[0][1]); rg.setEnd(L[0], L[2]);
   let rs = [...rg.getClientRects()].filter(r => r.width > 0.05 && r.height > 0.05);
   if (!rs.length) continue;
   let pieces = [{text: w.text, rs}];
   const tops = rs.map(r => r.top), h = Math.min(...rs.map(r => r.height));
   if (Math.max(...tops) - Math.min(...tops) > 0.5 * h) {          // a word broken over lines: per character
    pieces = []; let cp = null;
    for (const [nd, s0, s1] of w.segs) for (let i = s0; i < s1; i++) {
     rg.setStart(nd, i); rg.setEnd(nd, i + 1);
     const r = [...rg.getClientRects()].filter(r => r.width > 0.05)[0]; if (!r) continue;
     if (cp && Math.abs(r.top - cp.rs[0].top) < 0.5 * r.height) { cp.text += nd.data[i]; cp.rs.push(r); }
     else { cp = {text: nd.data[i], rs: [r]}; pieces.push(cp); }
    }
   }
   for (const pc of pieces) {
    const x0 = Math.min(...pc.rs.map(r => r.left)) - ox, x1 = Math.max(...pc.rs.map(r => r.right)) - ox;
    const top = Math.min(...pc.rs.map(r => r.top)) - oy, bot = Math.max(...pc.rs.map(r => r.bottom)) - oy;
    const base = pc.rs[0].top - oy + a * fs * (pc.rs[0].height / Math.max(1e-6, fs * (metrics(cs)[0] + metrics(cs)[1])));
    let ls = byBlock.get(w.block); if (!ls) { ls = []; byBlock.set(w.block, ls); }
    // a note call (superscript) belongs to the line of the text it hangs on
    const tol = w.sup ? 0.8 * parseFloat(getComputedStyle(w.sup.parentElement).fontSize) : 0.3 * fs;
    let ln = ls.find(l => Math.abs(l.base - base) < tol);
    if (!ln) { ln = {p: pi, base, fs, tag: w.block ? w.block.tagName : '', words: []}; ls.push(ln); lines.push(ln); }
    // the line's marker goes before its second word (inside the line: Chromium drops a destination on the
    // column's right edge, where a right-to-left line starts), before its first if it has one word; a line
    // opened by a later piece of a word broken over lines gets its marker from its next word
    if (ln.words.length < 2 && pc === pieces[0]) { const r0 = document.createRange(); r0.setStart(w.segs[0][0], w.segs[0][1]);
     r0.collapse(true); const st = starts.find(x => x[0] === ln); if (st) st[1] = r0; else starts.push([ln, r0]); }
    ln.words.push({t: pc.text, x0, x1, top, bot, fs});
   }
  }
 });
 // the one-column page is paginated by Chromium: an empty marker at the start of each line, the target of a
 // hidden link, becomes a named destination in the PDF (its page and place); the layout is not changed by it
 if (kind !== 'layout') {
  const hid = document.createElement('div'); hid.style.display = 'none';
  starts.forEach(([ln, r0], i) => { const m = document.createElement('span'); m.id = 'inkm' + i; r0.insertNode(m);
   const a = document.createElement('a'); a.href = '#inkm' + i; hid.appendChild(a); ln.m = i; });
  document.body.appendChild(hid);
  starts.forEach(([ln], i) => { const r = document.getElementById('inkm' + i).getBoundingClientRect();
   ln.mtop = r.top + scrollY; ln.mleft = r.left + scrollX; });
 }
 return {kind, lines, width: innerWidth};
}
"""


# ------------------------------------------------------------------------------------------------ 1. deglyph

class _PdfPen:
    """fontTools pen -> PDF path operators (quadratic curves raised to cubic by BasePen)."""

    def __init__(self, glyphset):
        from fontTools.pens.basePen import BasePen

        ops = self.ops = []

        class P(BasePen):
            def _moveTo(self, p):
                ops.append(f"{p[0]:.1f} {p[1]:.1f} m")

            def _lineTo(self, p):
                ops.append(f"{p[0]:.1f} {p[1]:.1f} l")

            def _curveToOne(self, p1, p2, p3):
                ops.append(f"{p1[0]:.1f} {p1[1]:.1f} {p2[0]:.1f} {p2[1]:.1f} {p3[0]:.1f} {p3[1]:.1f} c")

            def _closePath(self):
                ops.append("h")

        self.pen = P(glyphset)


class _GlyphFont:
    """One embedded font of the PDF: glyph code -> Form XObject xref (made on first use), the font's
    glyph-to-text matrix, the code width in bytes and the glyph advances (for a Tj of several codes)."""

    def __init__(self, doc, xref: int):
        self.doc, self.xref = doc, xref
        o = doc.xref_object(xref)
        self.type3 = "/Subtype /Type3" in o
        self.forms = {}
        self.widths = {}
        if self.type3:
            fm = [float(v) for v in re.search(r"/FontMatrix\s*\[([^\]]*)\]", o).group(1).split()]
            self.fm = fm
            self.nbytes = 1
            self.procs = {}
            enc = re.search(r"/Differences\s*\[([^\]]*)\]", o)
            names, code = {}, 0
            if enc:
                for tok in re.findall(r"/[^\s/\[\]]+|\d+", enc.group(1)):
                    if tok.isdigit():
                        code = int(tok)
                    else:
                        names[code] = tok[1:]
                        code += 1
            cp = doc.xref_get_key(xref, "CharProcs")
            cpo = doc.xref_object(int(cp[1].split()[0])) if cp[0] == "xref" else cp[1]
            pmap = {k: int(v) for k, v in re.findall(r"/([^\s/<>]+)\s+(\d+) 0 R", cpo)}
            self.procs = {c: pmap.get(nm) for c, nm in names.items()}
            res = doc.xref_get_key(xref, "Resources")
            self.res = (res[1] if res[0] == "xref" else res[1]) if res[0] in ("xref", "dict") else "<< >>"
            fc = int(re.search(r"/FirstChar\s+(\d+)", o).group(1)) if "/FirstChar" in o else 0
            wm = re.search(r"/Widths\s*\[([^\]]*)\]", o)
            if wm:
                for i, v in enumerate(wm.group(1).split()):
                    self.widths[fc + i] = float(v) * fm[0]          # glyph space -> text space (1/1000 not used)
            return
        self.nbytes = 2
        dfx = int(re.search(r"/DescendantFonts\s*\[\s*(\d+) 0 R", o).group(1))
        do = doc.xref_object(dfx)
        fdx = int(re.search(r"/FontDescriptor\s+(\d+) 0 R", do).group(1))
        ffx = int(re.search(r"/FontFile2\s+(\d+) 0 R", doc.xref_object(fdx)).group(1))
        from fontTools.ttLib import TTFont
        self.tt = TTFont(io.BytesIO(doc.xref_stream(ffx)), lazy=True)
        self.upem = self.tt["head"].unitsPerEm
        self.order = self.tt.getGlyphOrder()
        self.gs = self.tt.getGlyphSet()
        self.fm = [1.0 / self.upem, 0, 0, 1.0 / self.upem, 0, 0]
        from inkscript.edition.pdftext import _parse_w
        wm = re.search(r"/W\s*(\d+) 0 R", do)
        wt = doc.xref_object(int(wm.group(1))) if wm else (re.search(r"/W\s*(\[.*?\]\s*\])", do, re.S) or [None, ""])[1]
        dw = re.search(r"/DW\s+(\d+)", do)
        self.dw = float(dw.group(1)) if dw else 1000.0
        self.widths = {k: v / 1000.0 for k, v in (_parse_w(wt) if wt else {}).items()}

    def advance(self, code: int) -> float:
        if self.type3:
            return self.widths.get(code, 0.0)
        return self.widths.get(code, self.dw / 1000.0)

    def form(self, code: int) -> int | None:
        if code in self.forms:
            return self.forms[code]
        doc = self.doc
        x = None
        if self.type3:
            px = self.procs.get(code)
            if px:
                body = doc.xref_stream(px).decode("latin1")
                body = re.sub(r"^[\s\S]*?\b(d0|d1)\b", "", body, count=1)      # the width / box operator is not a form's
                x = doc.get_new_xref()
                doc.update_object(x, "<< /Type /XObject /Subtype /Form /BBox [-100000 -100000 100000 100000] "
                                     "/Resources %s >>" % self.res)
                doc.update_stream(x, body.encode("latin1"))
        else:
            if code < len(self.order):
                pen = _PdfPen(self.gs)
                g = self.gs[self.order[code]]
                g.draw(pen.pen)
                if pen.ops:
                    x = doc.get_new_xref()
                    doc.update_object(x, "<< /Type /XObject /Subtype /Form /BBox [-%d -%d %d %d] /Resources << >> >>"
                                      % (4 * self.upem, 4 * self.upem, 4 * self.upem, 4 * self.upem))
                    doc.update_stream(x, (" ".join(pen.ops) + " f").encode())
        self.forms[code] = x
        return x


def _mul(a, b):
    """Row-vector PDF matrices: a then b."""
    return [a[0] * b[0] + a[1] * b[2], a[0] * b[1] + a[1] * b[3],
            a[2] * b[0] + a[3] * b[2], a[2] * b[1] + a[3] * b[3],
            a[4] * b[0] + a[5] * b[2] + b[4], a[4] * b[1] + a[5] * b[3] + b[5]]


_HEX = re.compile(r"<([0-9A-Fa-f]*)>")


def _resources_xref(doc, page) -> int:
    res = doc.xref_get_key(page.xref, "Resources")
    if res[0] == "xref":
        return int(res[1].split()[0])
    x = doc.get_new_xref()
    doc.update_object(x, res[1] if res[0] == "dict" else "<< >>")
    doc.xref_set_key(page.xref, "Resources", f"{x} 0 R")
    return x


def deglyph(doc) -> dict:
    """Every text block of every page replaced by its glyphs drawn as forms. Returns counts."""
    st = Counter()
    fonts = {}
    for page in doc:
        rx = _resources_xref(doc, page)
        fmap = {}
        fk = doc.xref_get_key(rx, "Font")
        fo = doc.xref_object(int(fk[1].split()[0])) if fk[0] == "xref" else (fk[1] if fk[0] == "dict" else "")
        for nm, fx in re.findall(r"/([^\s/<>]+)\s+(\d+) 0 R", fo):
            fx = int(fx)
            if fx not in fonts:
                try:
                    fonts[fx] = _GlyphFont(doc, fx)
                except Exception as e:                    # noqa: BLE001
                    fonts[fx] = None
                    st["font_errors"] += 1
                    st[f"font_error:{type(e).__name__}"] += 1
            fmap[nm] = fonts[fx]
        used = {}
        for cx in page.get_contents():
            lines = doc.xref_stream(cx).decode("latin1").split("\n")
            out, inbt = [], False
            font = size = None
            tlm = [1, 0, 0, 1, 0, 0]
            for ln in lines:
                s = ln.strip()
                if s == "BT":
                    inbt, tlm = True, [1, 0, 0, 1, 0, 0]
                    continue
                if s == "ET":
                    inbt = False
                    continue
                if not inbt:
                    out.append(ln)
                    continue
                if s.endswith("Tf"):
                    m = re.match(r"/(\S+)\s+(-?[\d.]+)\s+Tf$", s)
                    font, size = fmap.get(m.group(1)), float(m.group(2))
                    if font is None:
                        st["text_in_unknown_font"] += 1
                    continue
                if s.endswith(" Tm"):
                    tlm = [float(v) for v in s.split()[:6]]
                    continue
                if s.endswith("BDC") or s.endswith("BMC") or s == "EMC":
                    st["marked_content_dropped"] += 1
                    continue
                if s.endswith("Tj"):
                    m = re.match(r"(?:(-?[\d.]+)\s+(-?[\d.]+)\s+Td\s+)?<([0-9A-Fa-f]*)>\s*Tj$", s)
                    if not m:
                        st["unparsed"] += 1
                        out.append(ln)
                        continue
                    if m.group(1) is not None:
                        tx, ty = float(m.group(1)), float(m.group(2))
                        tlm = [tlm[0], tlm[1], tlm[2], tlm[3],
                               tx * tlm[0] + ty * tlm[2] + tlm[4], tx * tlm[1] + ty * tlm[3] + tlm[5]]
                    if font is None:
                        continue
                    hx = m.group(3)
                    nb = 2 * font.nbytes
                    tm = list(tlm)
                    for k in range(0, len(hx), nb):
                        code = int(hx[k:k + nb], 16)
                        fx = font.form(code)
                        if fx:
                            mat = _mul([v * size for v in font.fm], tm)
                            nm = used.setdefault(fx, f"Gl{fx}")
                            out.append("q %s cm /%s Do Q" % (" ".join(f"{v:.5g}" for v in mat), nm))
                            st["glyphs"] += 1
                        adv = font.advance(code) * size
                        tm = [tm[0], tm[1], tm[2], tm[3], adv * tm[0] + tm[4], adv * tm[1] + tm[5]]
                    continue
                st["unparsed"] += 1
                out.append(ln)
            doc.update_stream(cx, "\n".join(out).encode("latin1"))
        if used:
            xk = doc.xref_get_key(rx, "XObject")
            if xk[0] == "xref":
                tx, pre = int(xk[1].split()[0]), ""
            else:
                if xk[0] == "null":
                    doc.xref_set_key(rx, "XObject", "<< >>")
                tx, pre = rx, "XObject/"
            for fx, nm in used.items():
                doc.xref_set_key(tx, pre + nm, f"{fx} 0 R")
        doc.xref_set_key(rx, "Font", "<< >>")
    return dict(st)


# ------------------------------------------------------------------------------------------------ 2. the layer

PX = 300 / 72            # points -> 300 dpi pixels (type3.DPI)


def _word(w: dict, x0, x1, base, fs) -> dict:
    """A word for type3.write_text_layer, in 300 dpi pixels: its box from 0.8 em above the baseline to 0.25 em
    below, one rectangle as its (invisible) ink."""
    import numpy as np
    y0, y1 = base - 0.8 * fs, base + 0.25 * fs
    path = np.array([[x0, y0], [x1, y0], [x1, y1], [x0, y1]], dtype=float)
    blob = dict(x=x0, y=y0, w=x1 - x0, h=y1 - y0, paths=[path])
    return dict(text=w["t"], az=w["t"], x0=x0, x1=x1, y0=y0, y1=base, blobs=[blob])


def page_lines_layout(dom: dict, npages: int) -> dict:
    """Layout PDF: DOM coordinates are CSS px from each page's top left; 1 CSS px = 0.75 pt."""
    out = defaultdict(list)
    k = 0.75 * PX
    for ln in dom["lines"]:
        ws = [_word(w, w["x0"] * k, w["x1"] * k, ln["base"] * k, ln["fs"] * k) for w in ln["words"]]
        if ws and ln["p"] < npages:
            out[ln["p"]].append(ws)
    return out


def page_lines_onecol(dom: dict, doc, margin_left_pt: float, margin_top_pt: float) -> tuple[dict, dict]:
    """One-column PDF: each DOM line's page and vertical offset from its marker's named destination (WORDS_JS)."""
    names = doc.resolve_names()
    out = defaultdict(list)
    placed, lost = 0, []
    for i, ln in enumerate(dom["lines"]):
        nd = names.get(f"inkm{ln.get('m', -1)}")
        if not nd or nd.get("page", -1) < 0:
            lost.append(" ".join(w["t"] for w in ln["words"])[:60])
            continue
        pg = doc[nd["page"]]
        top = pg.rect.height - nd["to"][1]                 # the destination's y, from the content box's top
        off = top + margin_top_pt - ln["mtop"] * 0.75      # DOM pt -> page pt, for this line
        ws = []
        for w in ln["words"]:
            ws.append(_word(w, (w["x0"] * 0.75 + margin_left_pt) * PX, (w["x1"] * 0.75 + margin_left_pt) * PX,
                            (ln["base"] * 0.75 + off) * PX, ln["fs"] * 0.75 * PX))
        out[nd["page"]].append(ws)
        placed += 1
    return out, dict(dom_lines=len(dom["lines"]), placed=placed, unplaced_examples=lost[:6], unplaced=len(lost))


def add_layer(doc, lines_by_page: dict, rtl: bool) -> dict:
    """The invisible word layer (inkscript's writer) on each page."""
    import fitz
    from inkscript.pdf import type3
    type3.split_word = lambda w, lh: [dict(w, first=True, split=False, tok=0)]   # a box per word, never cut
    type3.R2L = rtl
    st = Counter()
    for pi, page in enumerate(doc):
        lines = lines_by_page.get(pi) or []
        if not lines:
            continue
        lines = [L[i:i + 250] for L in lines for i in range(0, len(L), 250)]
        M = ~page.transformation_matrix
        content, glyphs, pst = type3.write_text_layer(doc, page, M, lines, f"W{pi}", invisible=True)
        page.wrap_contents()
        x = doc.get_new_xref()
        doc.update_object(x, "<< >>")
        doc.update_stream(x, content.encode())
        cont = doc.xref_get_key(page.xref, "Contents")
        arr = cont[1] if cont[0] == "array" else f"[{cont[1]}]"
        doc.xref_set_key(page.xref, "Contents", arr[:-1] + f" {x} 0 R]")
        st["words"] += pst["words"]
        st["lines"] += len(lines)
    _ = fitz
    return dict(st)
