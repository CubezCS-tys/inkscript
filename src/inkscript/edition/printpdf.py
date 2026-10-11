"""The re-typeset print editions of an article, set by LuaLaTeX (experiment 35, D27).

    layout_pdf(ed, out_path)     the LAYOUT-FAITHFUL edition: the original's page size, every ALTO line set in a
                                 clean face at the place and width the print had it (line for line), justified
                                 where the print was justified (babel's kashida justification), titles and
                                 headings at their own relative size, page furniture in grey, table rules,
                                 formulas typeset (or the scan crop when the LaTeX does not compile)
    onecol_pdf(ed, out_path)     the CLEAN ONE-COLUMN edition: A4, a research-paper title block from the catalogue
                                 front matter, headings, justified body, footnotes at the foot of the page,
                                 Quran quotations tinted with their verse reference, tables right to left with
                                 merged cells, maths, references, a colophon

Both return a dict of numbers (pages, seconds, engine, lines squeezed, missing glyphs, maths fallbacks...).

Why LuaLaTeX and how the text copies out right: see docs/decisions.md D27 and experiments/35_edition/README.md.
In short: HarfBuzz shaping, babel's kashida justification, and a text pdfium (Chrome) reads in logical order.
LuaTeX writes an Arabic line's glyphs right to left, which pdfium reads backwards; after LuaTeX,
pdftext.rewrite_visual stores every line's glyphs in visual order with a real space glyph in each word gap,
vowel marks and kashida as outlines (the marks' letters kept in the text), the way the faithful PDF is written
(docs/pdf-writing-rules.md). The PDF is marked /Direction /R2L like every inkscript output (D18).

Layout: lines are set at 10 pt and scaled per block (\\scalebox), never with a font size per block (each size
loaded a HarfBuzz font: 1.8 GB for 9 pages; scaled, 0.3 GB). Lines sharing a band (a table row) are written left
to right.
"""
from __future__ import annotations

import hashlib
import os
import re
import shutil
import subprocess
import tempfile
import time
from pathlib import Path
from statistics import median

from .. import text as T
from . import fonts
from .model import Edition

LUALATEX = os.environ.get("INKSCRIPT_LUALATEX") or shutil.which("lualatex") or "lualatex"
ARABIC = re.compile(r"[\u0600-\u06FF\u0750-\u077F\u08A0-\u08FF\uFB50-\uFDFF\uFE70-\uFEFF]")
LATIN = re.compile(r"[A-Za-z\u00C0-\u024F]")
TEX_SPECIAL = {"\\": r"\textbackslash{}", "{": r"\{", "}": r"\}", "#": r"\#", "$": r"\$", "%": r"\%",
               "&": r"\&", "_": r"\_", "^": r"\textasciicircum{}", "~": r"\textasciitilde{}"}


# ---------------------------------------------------------------------------------------------- TeX helpers

def esc(s: str) -> str:
    return "".join(TEX_SPECIAL.get(c, c) for c in s)


def _hex(s: str) -> str:
    return "FEFF" + s.encode("utf-16-be").hex().upper()


ACTUALTEXT = False     # per-word /ActualText: tried and set aside (pdfium then joins short lines); see pdftext.py


def word(w: str, ltr_line: bool = False) -> str:
    """One word. With ACTUALTEXT, wrapped in a span whose /ActualText is the word stored the way pdfium inverts
    it; by default plain, and pdftext.rewrite_visual stores the glyphs in visual order after LuaTeX."""
    w = w.strip()
    if not w:
        return ""
    if not ACTUALTEXT:
        return esc(w)
    vis = T.visual(w, ltr_line=True) if ltr_line else T.visual(w, in_rtl_line=True)
    return r"\aw{%s}{%s}" % (_hex(vis), esc(w))


def words(s: str, ltr_line: bool = False) -> str:
    return " ".join(word(w, ltr_line) for w in s.split())


def is_ltr(s: str) -> bool:
    return len(LATIN.findall(s)) > len(ARABIC.findall(s))


def _fontspec_dir() -> tuple[str, str]:
    reg = fonts.font_path("markazi", "regular")
    fonts.font_path("markazi", "bold")
    return str(reg.parent) + "/", reg.name.replace("-Regular.ttf", "")


PREAMBLE = r"""\documentclass[11pt]{article}
\usepackage{fontspec}
\usepackage[bidi=basic]{babel}
\babelprovide[import,main,justification=kashida]{arabic}
\babelprovide[import]{english}
\directlua{luaotfload.add_fallback("inkfb", {"Amiri:mode=harf;", "Noto Naskh Arabic:mode=harf;", "Noto Sans:mode=harf;", "DejaVu Sans:mode=harf;"})}
\babelfont{rm}[Renderer=HarfBuzz,Path=%(dir)s,Extension=.ttf,UprightFont=*-Regular,BoldFont=*-Bold,RawFeature={fallback=inkfb}]{%(base)s}
\babelfont[english]{rm}[Renderer=HarfBuzz,Path=%(dir)s,Extension=.ttf,UprightFont=*-Regular,BoldFont=*-Bold,RawFeature={fallback=inkfb}]{%(base)s}
\newfontfamily\amiri[Renderer=HarfBuzz,Script=Arabic]{Amiri}
\usepackage{amsmath}
\usepackage[math-style=ISO]{unicode-math}
\setmathfont{Latin Modern Math}
\usepackage{graphicx}
\usepackage[table]{xcolor}
\usepackage{multirow}
\definecolor{furn}{gray}{0.5}
\definecolor{quran}{RGB}{20,95,60}
\definecolor{rule}{gray}{0.35}
%% a word whose copy text is given (pdfium reads the /ActualText)
\protected\def\aw#1#2{\pdfextension literal page{/Span <</ActualText <#1>>> BDC}#2\pdfextension literal page{EMC}}
%% every face's space glyph is shipped once a page (white, in the corner), so each font subset carries a space
%% that pdftext.rewrite_visual puts between words (pdfium copies words apart only with a space in the run)
\AddToHook{shipout/background}{\put(2,-2){\makebox(0,0)[lt]{\color{white}\fontsize{4}{4}\selectfont\char32{\bfseries\char32}\char32}}}
"""


def _preamble() -> str:
    d, base = _fontspec_dir()
    return PREAMBLE % dict(dir=d, base=base)


def _mathtex(tex: str, rtl: bool = False) -> str:
    """tex-math made printable: Arabic letters and digits outside \\text{} go into \\text{}. Right to left
    (MathML dir="rtl"), LuaTeX lays the formula out with \\mathdir TRT but does not mirror the parentheses, so
    they are swapped here."""
    if rtl:
        tex = tex.translate(str.maketrans("()", ")("))
    out, i, depth_text = [], 0, 0
    # find \text{...} spans and leave them alone
    spans = []
    for m in re.finditer(r"\\text\s*\{", tex):
        j, d = m.end(), 1
        while j < len(tex) and d:
            d += {"{": 1, "}": -1}.get(tex[j], 0)
            j += 1
        spans.append((m.start(), j))
    pos = 0
    for a, b in spans + [(len(tex), len(tex))]:
        chunk = tex[pos:a]
        chunk = re.sub(r"([\u0600-\u06FF\u0750-\u077F]+)", r"\\text{\1}", chunk)
        out.append(chunk)
        out.append(tex[a:b])
        pos = b
    return "".join(out)


_MATH_OK: dict[str, bool] = {}


def mathbox(tex: str, rtl: bool, display: bool) -> str:
    """A formula as TeX: inline or display style, right to left when the master says so."""
    d = r"\mathdir TRT" if rtl else r"\mathdir TLT"
    return r"{%s$%s%s$}" % (d, r"\displaystyle " if display else "", _mathtex(tex, rtl))


def math_ok(tex: str, timeout: int = 60) -> bool:
    """Does this formula compile (alone, with the editions' preamble)? Cached by its text."""
    k = hashlib.md5(tex.encode()).hexdigest()
    if k in _MATH_OK:
        return _MATH_OK[k]
    doc = _preamble() + "\\begin{document}\n%s\n\n%s\n\\end{document}\n" % (
        mathbox(tex, True, True), mathbox(tex, False, False))
    with tempfile.TemporaryDirectory(prefix="ink-math-") as d:
        (Path(d) / "m.tex").write_text(doc, encoding="utf-8")
        try:
            r = subprocess.run([LUALATEX, "-interaction=nonstopmode", "-halt-on-error", "m.tex"], cwd=d,
                               capture_output=True, timeout=timeout)
            log = (Path(d) / "m.log").read_text(errors="replace") if (Path(d) / "m.log").exists() else ""
            ok = r.returncode == 0 and "Missing character" not in log
        except subprocess.TimeoutExpired:
            ok = False
    _MATH_OK[k] = ok
    return ok


def run_lualatex(tex: str, out_pdf: Path, timeout: int = 900, runs: int = 1, keep_tex: bool = False) -> dict:
    """Compile (nice, a timeout, a temporary folder removed afterwards). Returns seconds, the peak memory of the
    LuaTeX process (GNU time, when present), the log's missing characters, errors, and its INKSTAT lines."""
    out_pdf = Path(out_pdf)
    t0 = time.time()
    gtime = "/usr/bin/time" if Path("/usr/bin/time").exists() else None
    peak = 0
    with tempfile.TemporaryDirectory(prefix="ink-edition-") as d:
        src = Path(d) / "e.tex"
        src.write_text(tex, encoding="utf-8")
        if keep_tex:
            out_pdf.with_suffix(".tex").write_text(tex, encoding="utf-8")
        rc, log = 1, ""
        for _ in range(runs):
            cmd = ["nice", "-n", "10", LUALATEX, "-interaction=nonstopmode", "e.tex"]
            if gtime:
                cmd = [gtime, "-f", "%M", "-o", str(Path(d) / "mem.txt")] + cmd
            try:
                r = subprocess.run(cmd, cwd=d, capture_output=True, timeout=timeout)
                rc = r.returncode
            except subprocess.TimeoutExpired:
                rc = -9
                break
            try:
                peak = max(peak, int((Path(d) / "mem.txt").read_text().split()[-1]) // 1024)
            except (OSError, ValueError, IndexError):
                pass
        log = (Path(d) / "e.log").read_text(errors="replace") if (Path(d) / "e.log").exists() else ""
        pdf = Path(d) / "e.pdf"
        ok = pdf.exists() and pdf.stat().st_size > 0
        if ok:
            out_pdf.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(pdf, out_pdf)
    missing = re.findall(r"Missing character: There is no (.) \(U\+([0-9A-F]+)\)", log)
    errors = re.findall(r"^! (.*)$", log, re.M)
    stats = {}
    for k, v in re.findall(r"INKSTAT (\w+)=(\d+)", log):
        stats[k] = int(v)
    return dict(ok=ok, rc=rc, seconds=round(time.time() - t0, 2), peak_mb=peak,
                missing=sorted({m[1] for m in missing}), missing_n=len(missing), errors=errors[:5],
                overfull=len(re.findall(r"^Overfull \\hbox", log, re.M)), **stats)


def latin_document(ed: Edition) -> bool:
    """An article written mostly in Latin script (an English or French article in an Arabic journal): its PDF is
    not marked right to left. Marked R2L, pdfium read such pages backwards (0694, 0739, 1140: 23-25% of words in
    order; experiment 35)."""
    lat = ara = 0
    for w in ed.ink_words(rendered_only=False):
        if re.search(r"[A-Za-z\u00C0-\u024F]", w.text):
            lat += 1
        elif re.search(r"[\u0600-\u06FF]", w.text):
            ara += 1
    return lat > ara


def finish_pdf(path: Path, title: str = "", author: str = "", subject: str = "", reorder: bool = True,
               rtl: bool = True):
    """Store the text the way pdfium reads it (pdftext.rewrite_visual), mark the PDF right to left (D18) and
    Arabic, and write its document info. Returns rewrite_visual's counts."""
    import pymupdf
    from .pdftext import rewrite_visual
    path = Path(path)
    d = pymupdf.open(str(path))
    turned = {}
    if reorder:
        turned = rewrite_visual(d)
    cat = d.pdf_catalog()
    d.xref_set_key(cat, "ViewerPreferences", "<</Direction /%s /DisplayDocTitle true>>" % ("R2L" if rtl else "L2R"))
    d.xref_set_key(cat, "Lang", pymupdf.get_pdf_str("ar" if rtl else "en"))
    d.set_metadata(dict(title=title, author=author, subject=subject, creator="inkscript edition (experiment 35)",
                        producer="LuaHBTeX + babel (kashida); inkscript"))
    tmp = path.with_suffix(".tmp.pdf")
    d.save(str(tmp), garbage=1, deflate=True)
    d.close()
    tmp.replace(path)
    return turned


# ---------------------------------------------------------------------------------------------- reading order

def block_order(ed: Edition) -> dict[str, int]:
    """Each block's place in the article's reading order (front matter, body, notes, references); furniture and
    stray blocks have none."""
    seq = []
    f = ed.front
    by_kind = {}
    for b in ed.blocks.values():
        by_kind.setdefault(b.kind, []).append(b)
    for k in ("rubric", "title", "author", "front"):
        seq += [b.id for b in sorted(by_kind.get(k, []), key=lambda b: (b.page, b.box[1]))]
    for n in ed.nodes():
        seq += n.blocks
    order = {}
    for bid in seq:
        order.setdefault(bid, len(order))
    return order


def page_blocks(ed: Edition, n: int):
    """A page's blocks in the order they are written: reading order, then stray blocks, furniture last."""
    order = block_order(ed)
    bl = ed.pages[n].blocks
    return sorted(bl, key=lambda b: (0 if b.id in order else (2 if b.furniture else 1),
                                     order.get(b.id, 0), b.box[1], -b.box[0]))


# ---------------------------------------------------------------------------------------------- layout-faithful

LAYOUT_LUA = r"""
\usepackage{luacode}
\begin{luacode*}
-- Every line is set at 10 pt and scaled to its block's size (one font instance per face: a font size per block
-- loaded a HarfBuzz font each time, 1.8 GB for 9 pages).
inkfit = {r = {}, squeezed = 0, shrunk = 0}
function inkfit.start() inkfit.r = {} end
function inkfit.measure(avail_bp)
  local w = tex.box[0].width
  if w > 0 then table.insert(inkfit.r, 10 * avail_bp * 65781.76 / w) end
end
function inkfit.size(sh, smin, key)
  local r = inkfit.r
  table.sort(r)
  local s = sh
  if #r > 0 then
    local lo = r[1]
    local q = r[math.max(1, math.floor(#r * 0.10 + 0.5))]
    s = math.min(sh, q, lo * 1.04)
  end
  if s < smin then s = smin end
  tex.sprint(string.format("\\def\\bs{%.4f}\\def\\bkm{%d}", s / 10, math.floor(s * 100 + 0.5)))
  if key then
    tex.sprint(string.format("\\expandafter\\def\\csname bs@%s\\endcsname{%.4f}", key, s / 10))
    tex.sprint(string.format("\\expandafter\\def\\csname bkm@%s\\endcsname{%d}", key, math.floor(s * 100 + 0.5)))
  end
end
\end{luacode*}
\newbox\inkline
\newdimen\inknat
\newdimen\inkav
% \Ln{x left bp}{baseline y bp}{width bp}{mode J|R|L|C}{content}; \bs = scale (size / 10 pt), \bkm = 1000 x scale
\def\Ln#1#2#3#4#5{%
  \setbox\inkline\hbox{\textdir TRT#5}%
  \inknat=\wd\inkline
  \inkav=\dimexpr #3bp * 1000 / \bkm\relax
  \ifdim\inknat>\inkav \directlua{inkfit.squeezed = inkfit.squeezed + 1}%
    \put(#1,#2){\makebox(0,0)[bl]{\scalebox{\bs}{\resizebox{\inkav}{\height}{\box\inkline}}}}%
  \else\if J#4%
    \ifdim\inknat>0.80\inkav
      \put(#1,#2){\makebox(0,0)[bl]{\scalebox{\bs}{\parbox[b]{\inkav}{\pardir TRT\textdir TRT\parfillskip=0pt\emergencystretch=1em\noindent#5}}}}%
    \else \put(#1,#2){\makebox(#3,0)[br]{\scalebox{\bs}{\box\inkline}}}\fi
  \else\if R#4\put(#1,#2){\makebox(#3,0)[br]{\scalebox{\bs}{\box\inkline}}}%
  \else\if L#4\put(#1,#2){\makebox(#3,0)[bl]{\scalebox{\bs}{\box\inkline}}}%
  \else\put(#1,#2){\makebox(#3,0)[b]{\scalebox{\bs}{\box\inkline}}}\fi\fi\fi\fi}
% \Rn{x bp}{y bp}{length bp}{angle}{content}: a line printed sideways (a landscape table on a portrait page),
% set like \Ln at the block's scale and fitted to its length, then turned by angle (90: it reads downwards)
\def\Rn#1#2#3#4#5{%
  \setbox\inkline\hbox{\textdir TRT#5}%
  \inknat=\wd\inkline
  \inkav=\dimexpr #3bp * 1000 / \bkm\relax
  \ifdim\inknat>\inkav \directlua{inkfit.squeezed = inkfit.squeezed + 1}%
    \put(#1,#2){\rotatebox{#4}{\makebox(0,0)[bl]{\scalebox{\bs}{\resizebox{\inkav}{\height}{\box\inkline}}}}}%
  \else\put(#1,#2){\rotatebox{#4}{\makebox(#3,0)[b]{\scalebox{\bs}{\box\inkline}}}}\fi}
% \UseB{block}: that block's size, measured earlier on the page (lines are written in their own order)
\def\UseB#1{\expandafter\let\expandafter\bs\csname bs@#1\endcsname\expandafter\let\expandafter\bkm\csname bkm@#1\endcsname}
\def\Msr#1#2{\setbox0\hbox{\textdir TRT #2}\directlua{inkfit.measure(#1)}}
% the re-flowed alternative (measured against line for line): a block's words as one paragraph at the block's
% width, from the line-fit size down by 6% steps until it fits the block's height
\newcount\inkk \newcount\inkgo \newdimen\inkh
\def\inkscale{\directlua{tex.sprint(tex.count.inkk / 1000)}}
\def\Blk#1#2#3#4#5#6{%
  \inkk=\bkm\relax
  \loop
    \inkav=\dimexpr #3bp*1000/\inkk\relax
    \setbox\inkline\vbox{\hsize=\inkav\pardir TRT\textdir TRT\ifnum#5=1 \centering\fi\noindent #6\par}%
    \inkh=\dimexpr(\ht\inkline+\dp\inkline)*\inkk/1000\relax
    \inkgo=0 \ifdim\inkh>#4bp \ifnum\inkk>350 \inkgo=1 \inkk=\numexpr\inkk*94/100\relax\fi\fi
  \ifnum\inkgo=1 \directlua{inkfit.shrunk = inkfit.shrunk + 1}\repeat
  \put(#1,#2){\makebox(0,0)[tl]{\scalebox{\inkscale}{\box\inkline}}}}
"""


def _line_mode(line, block, all_lines) -> str:
    """How a line sits in its block: J justified (full width), R right-aligned, L left-aligned, C centred."""
    bx, _, bw, _ = block.box
    x, _, w, _ = line.box
    gl, gr = x - bx, (bx + bw) - (x + w)
    ltr = is_ltr(" ".join(wd.text for wd in line.words))
    full = w >= 0.93 * bw
    if full and len(all_lines) > 1:
        return "J"
    if len(all_lines) == 1 or block.kind in ("title", "heading", "author", "rubric") or block.furniture:
        if abs(gl - gr) < 0.12 * bw and min(gl, gr) > 0.04 * bw:
            return "C"
        if gr <= gl:
            return "R"
        return "L"
    if ltr:
        return "L" if gl <= gr else "R"
    return "R" if gr <= max(gl, 0.04 * bw) else ("C" if abs(gl - gr) < 0.12 * bw else "L")


def _owners(rows):
    """The grid of a table: owner[(row, col)] = the cell covering that slot (colspan/rowspan), cols in reading
    order (col 0 is the rightmost on the page)."""
    owner, start = {}, {}
    for ri, r in enumerate(rows):
        ci = 0
        for c in r["cells"]:
            while (ri, ci) in owner:
                ci += 1
            start[id(c)] = (ri, ci)
            for dr in range(c["rowspan"]):
                for dc in range(c["colspan"]):
                    owner[(ri + dr, ci + dc)] = c
            ci += c["colspan"]
    return owner, start


def _table_rules(ed: Edition, tb, sc: float, H: float) -> list[str]:
    """The rules of a table, from its cells' boxes on the page and its grid in the master: a frame, and a rule
    between two slots only where they belong to different cells (so merged cells stay merged). In bp."""
    node = next((n for n in ed.body if n.kind == "table" and n.id == tb.id), None)
    if node is None:
        return []
    rows = node.extra["rows"]
    owner, start = _owners(rows)
    nr = max((k[0] for k in owner), default=-1) + 1
    nc = max((k[1] for k in owner), default=-1) + 1
    if not nr or not nc:
        return []
    def box(c):
        bx = [ed.blocks[b].box for b in c.get("blocks", []) if b in ed.blocks]
        if not bx:
            return None
        return (min(b[0] for b in bx), min(b[1] for b in bx), max(b[0] + b[2] for b in bx), max(b[1] + b[3] for b in bx))
    L, R, T, B = [None] * nc, [None] * nc, [None] * nr, [None] * nr
    for c in [c for r in rows for c in r["cells"]]:
        bb = box(c)
        if bb is None:
            continue
        ri, ci = start[id(c)]
        if c["colspan"] == 1:
            L[ci] = bb[0] if L[ci] is None else min(L[ci], bb[0])
            R[ci] = bb[2] if R[ci] is None else max(R[ci], bb[2])
        if c["rowspan"] == 1:
            T[ri] = bb[1] if T[ri] is None else min(T[ri], bb[1])
            B[ri] = bb[3] if B[ri] is None else max(B[ri], bb[3])
    x, y, w, h = tb.box
    for arr in (L, R):                      # columns with no single cell: spread over the table evenly
        for j in range(nc):
            if arr[j] is None:
                arr[j] = x + w - (j + (0.9 if arr is L else 0.1)) * w / nc
    for arr in (T, B):
        for i in range(nr):
            if arr[i] is None:
                arr[i] = y + (i + (0.1 if arr is T else 0.9)) * h / nr
    lh = median([b[3] for c in [c for r in rows for c in r["cells"]] for b in
                 [ed.blocks[k].box for k in c.get("blocks", []) if k in ed.blocks]] or [20])
    pad = 0.35 * lh
    xb = [R[0] + pad] + [(L[j] + R[j + 1]) / 2 for j in range(nc - 1)] + [L[nc - 1] - pad]   # x of col j's right edge
    yb = [T[0] - pad] + [(B[i] + T[i + 1]) / 2 for i in range(nr - 1)] + [B[nr - 1] + pad]
    P = lambda X, Y: (X * sc, H - Y * sc)
    out = []
    def hline(x0, x1, yy):
        a, b_ = P(min(x0, x1), yy)
        out.append(r"\put(%.2f,%.2f){\color{rule}\line(1,0){%.2f}}" % (a, b_, abs(x1 - x0) * sc))
    def vline(xx, y0, y1):
        a, b_ = P(xx, max(y0, y1))
        out.append(r"\put(%.2f,%.2f){\color{rule}\line(0,1){%.2f}}" % (a, b_, abs(y1 - y0) * sc))
    for j in range(nc):                     # top and bottom of the frame, and rules between rows
        hline(xb[j], xb[j + 1], yb[0])
        hline(xb[j], xb[j + 1], yb[nr])
        for i in range(nr - 1):
            if owner.get((i, j)) is not owner.get((i + 1, j)):
                hline(xb[j], xb[j + 1], yb[i + 1])
    for i in range(nr):                     # sides of the frame, and rules between columns
        vline(xb[0], yb[i], yb[i + 1])
        vline(xb[nc], yb[i], yb[i + 1])
        for j in range(nc - 1):
            if owner.get((i, j)) is not owner.get((i, j + 1)):
                vline(xb[j + 1], yb[i], yb[i + 1])
    for i in range(nr):                     # a header row shaded lightly, as print often does
        if rows[i]["head"] if i < len(rows) else False:
            a, b_ = P(xb[nc], yb[i + 1])
            out.insert(0, r"\put(%.2f,%.2f){\color{black!6}\rule{%.2fbp}{%.2fbp}}" % (a, b_, (xb[0] - xb[nc]) * sc,
                                                                                    (yb[i + 1] - yb[i]) * sc))
    return out


def _formula(ed: Edition, b, sc: float, H: float, st: dict) -> str:
    node = next((n for n in ed.body if n.kind == "formula" and n.id in (b.id, b.target)), None)
    x, y, w, h = (v * sc for v in b.box)
    if node is None:
        return ""
    tex, g = node.extra.get("tex", ""), node.extra.get("graphic", "")
    label = node.extra.get("label", "")
    if tex and math_ok(tex):
        st["math_typeset"] += 1
        lab = (r"\makebox[0pt][l]{%s}" % words(label)) if label else ""
        body = mathbox(tex, node.extra.get("dir") == "rtl", True)
        return (r"\put(%.1f,%.1f){\makebox(0,0)[l]{%s}}" % (x, H - y - h / 2, lab) +
                r"\put(%.1f,%.1f){\makebox(%.1f,%.1f)[c]{\fitbox{%.1f}{%.1f}{%s}}}" % (x, H - y - h, w, h, w, h, body))
    p = (Path(ed.jats_path).parent / g) if g else None
    if p is not None and p.exists():
        st["math_crop"] += 1
        return r"\put(%.1f,%.1f){\includegraphics[width=%.1fbp,height=%.1fbp]{%s}}" % (x, H - y - h, w, h, p)
    st["math_missing"] += 1
    return ""


FITBOX = r"""
\newbox\fitb
% \fitbox{w bp}{h bp}{content}: the content at its natural size, scaled down only if it is larger than w x h
\def\fitbox#1#2#3{\setbox\fitb\hbox{#3}%
  \ifdim\wd\fitb>#1bp \setbox\fitb\hbox{\resizebox{#1bp}{!}{\box\fitb}}\fi
  \ifdim\dimexpr\ht\fitb+\dp\fitb\relax>#2bp \setbox\fitb\hbox{\resizebox{!}{#2bp}{\box\fitb}}\fi
  \box\fitb}
"""


def layout_tex(ed: Edition, height_k: float = 1.3, baseline: float = 0.9, mode: str = "lines") -> tuple[str, dict]:
    # baseline: where in an ALTO line's box the rebuilt baseline goes; height_k: the size cap from the line's
    # height. Chosen by ink correlation with the scan (bake-off, 3 documents): baseline 0.66 -> 0.33-0.43,
    # 0.74 -> 0.51-0.60, 0.82 -> 0.67-0.72, 0.90 -> 0.58-0.76 (0.94 no better on two of three); height_k 1.05 vs
    # 1.3 changes it by under 0.01.
    """mode "lines": every ALTO line set at its own place and width (the default, D27); "reflow": each block's
    words re-flowed as one paragraph in the block's box (the alternative it was measured against)."""
    st = dict(lines=0, justified=0, blocks=0, math_typeset=0, math_crop=0, math_missing=0, tables=0)
    th_ids = {k for n in ed.body if n.kind == "table" for r in n.extra["rows"] for c in r["cells"] if c["th"]
              for k in c.get("blocks", [])}
    out = [_preamble(), r"\usepackage{calc}", LAYOUT_LUA, FITBOX,
           r"\setlength{\parindent}{0pt}\setlength{\unitlength}{1bp}\pagestyle{empty}"
           r"\setlength{\topskip}{0pt}\setlength{\voffset}{-1in}\setlength{\hoffset}{-1in}"
           r"\setlength{\oddsidemargin}{0pt}\setlength{\topmargin}{0pt}\setlength{\headheight}{0pt}"
           r"\setlength{\headsep}{0pt}\setlength{\footskip}{0pt}\setlength{\marginparwidth}{0pt}",
           "\\begin{document}\\pagedir TLT\\bodydir TLT\\fontsize{10}{12}\\selectfont\n"]
    for n in ed.page_numbers:
        pg = ed.pages[n]
        W, H = pg.pt_w, pg.pt_h
        sc = W / pg.w if pg.w else 1.0
        out.append(r"\pagewidth=%.2fbp\pageheight=%.2fbp\textwidth=%.2fbp\textheight=%.2fbp\hsize=\textwidth"
                   r"\vsize=\textheight" % (W, H, W, H) + "\n")
        out.append(r"\pardir TLT\textdir TLT\noindent\begin{picture}(%.2f,%.2f)(0,0)" % (W, H - 1) + "\n")
        pending = []             # (top, bottom, x, command) of each line, in reading order
        for b in page_blocks(ed, n):
            if b.role == "formula" or b.kind == "formula":
                out.append(_formula(ed, b, sc, H, st) + "\n")
                continue
            if b.role == "table" and not b.lines:
                st["tables"] += 1
                out.extend(s + "\n" for s in _table_rules(ed, b, sc, H))
                continue
            lines = [ln for ln in b.lines if ln.words]
            if not lines:
                continue
            st["blocks"] += 1
            lh = median(_ext(ln)[1] for ln in lines) * sc
            sh = max(4.0, lh * height_k)
            out.append(r"\directlua{inkfit.start()}")
            texts = []
            for ln in lines:
                s = " ".join(w.text for w in ln.words)
                ltr = is_ltr(s)
                t = words(s, ltr)
                if ltr:
                    t = r"\foreignlanguage{english}{%s}" % t
                texts.append(t)
                out.append(r"\Msr{%.2f}{%s}" % (_ext(ln)[0] * sc, t))
            out.append(r"\directlua{inkfit.size(%.2f, 3.5, '%s')}" % (sh, b.id) + "\n")
            grey = b.furniture or b.kind == "stray"
            bold = b.kind in ("title", "heading") or b.role in ("title", "sectionHeading") or b.id in th_ids
            pre = (r"\color{furn}" if grey else "") + (r"\bfseries{}" if bold else "")   # {}: Arabic letters are
            #                                                     letters to TeX and would lengthen a control word
            if mode == "reflow":
                x, y, w, h = b.box
                s = " ".join(wd.text for ln in lines for wd in ln.words)
                ltr = is_ltr(s)
                t = words(s, ltr)
                if ltr:
                    t = r"\foreignlanguage{english}{%s}" % t
                centred = int(len(lines) <= 2 and _line_mode(lines[0], b, lines) == "C")
                out.append(r"\Blk{%.2f}{%.2f}{%.2f}{%.2f}{%d}{{%s%s}}" % (x * sc, H - y * sc, w * sc, h * sc * 1.08,
                                                                           centred, pre, t) + "\n")
                st["lines"] += len(lines)
                continue
            for ln, t in zip(lines, texts):
                x, y, w, h = ln.box
                length, thick, angle = _ext(ln)
                if angle:                       # printed sideways: turned, placed by its own box
                    st["lines"] += 1
                    st["sideways"] = st.get("sideways", 0) + 1
                    px = (x + w * baseline) if angle == 90 else (x + w * (1 - baseline))
                    py = H - (y + h) * sc if angle == 90 else H - y * sc
                    pending.append((y, y + h, x, r"\UseB{%s}\Rn{%.2f}{%.2f}{%.2f}{%d}{{%s%s}}" % (
                        b.id, px * sc if angle == 90 else px * sc, py, length * sc, angle, pre, t) + "\n"))
                    continue
                lm = _line_mode(ln, b, lines)
                st["lines"] += 1
                st["justified"] += lm == "J"
                pending.append((y, y + h, x, r"\UseB{%s}\Ln{%.2f}{%.2f}{%.2f}{%s}{{%s%s}}" % (
                    b.id, x * sc, H - (y + h * baseline) * sc, w * sc, lm, pre, t) + "\n"))
        out.extend(c for c in _band_order(pending))
        out.append("\\end{picture}\n\\newpage\n")
    out.append("\\directlua{texio.write_nl('log', 'INKSTAT squeezed=' .. inkfit.squeezed)"
               "texio.write_nl('log', 'INKSTAT shrunk=' .. inkfit.shrunk)}\n\\end{document}\n")
    return "".join(out), st


def _ext(ln) -> tuple[float, float, int]:
    """A line's length along its text, its thickness, and its turn: 0 for a line printed across the page; 90 for a
    line printed sideways that reads downwards, -90 upwards (a landscape table turned on a portrait page: 9 pages
    of the 205 documents, experiment 35's judge saw them as scattered crumbs)."""
    x, y, w, h = ln.box
    if h > 1.8 * w and (len(ln.words) >= 2 or h > 3 * w):
        ys = [wd.box[1] + wd.box[3] / 2 for wd in ln.words]
        angle = 90 if len(ys) < 2 or ys[0] <= ys[-1] else -90
        return h, w, angle
    return w, h, 0


def _band_order(lines):
    """Lines in reading order, except that consecutive lines sharing a band (the cells of a table row, a verse's
    two halves, a heading beside its number) are written left to right: pdfium joins text that overlaps vertically
    into one line and expects its runs in visual order (docs/pdf-writing-rules.md, "Runs sharing a band go left to
    right")."""
    out, band = [], []
    def flush():
        out.extend(c for *_, c in sorted(band, key=lambda t: t[2]))
        band.clear()
    for ln in lines:
        if band:
            t0, b0 = min(t[0] for t in band), max(t[1] for t in band)
            ov = min(b0, ln[1]) - max(t0, ln[0])
            if ov <= 0.5 * min(b0 - t0, ln[1] - ln[0]):
                flush()
        band.append(ln)
    flush()
    return out


def layout_pdf(ed: Edition, out_path, keep_tex: bool = False, timeout: int = 1200, **opts) -> dict:
    tex, st = layout_tex(ed, **opts)
    r = run_lualatex(tex, Path(out_path), timeout=timeout, keep_tex=keep_tex)
    if r["ok"]:
        st["lines_reordered"] = finish_pdf(Path(out_path), ed.front.get("title", ""),
                                           "; ".join(a["display"] for a in ed.front["authors"]),
                   "layout-faithful re-typeset edition of %s" % ed.stem, rtl=not latin_document(ed))
    st.update(r)
    st.update(engine="lualatex", variant="layout", pages=len(ed.pages))
    return st


# ---------------------------------------------------------------------------------------------- one column

def _inl(ed: Edition, inl, ltr=False, notes=None, st=None) -> str:
    """Inline runs to TeX: words with their copy text, footnotes, Quran quotations, maths."""
    out = []
    for r in inl:
        t = r["t"]
        if t == "text":
            s = r["s"]
            lead = " " if s[:1].isspace() else ""
            tail = " " if s[-1:].isspace() else ""
            out.append(lead + words(s, ltr) + tail)
        elif t == "fnref":
            note = notes.get(r["rid"]) if notes is not None else None
            if note is not None and not note.get("used"):
                note["used"] = True
                body = " ".join(_inl(ed, p.inl, is_ltr(p.text), None, st) for p in note["note"].paras)
                out.append(r"\footnote{%s}" % body)
                st["footnotes"] += 1
            elif note is not None:
                out.append(r"\footnotemark[%d]" % note["num"])
            else:
                out.append(words(r["s"], ltr))
        elif t == "quran":
            ref = r.get("title", "")
            name, _, num = ref.rpartition(" ")
            out.append(r"{\color{quran}%s}\,{\footnotesize\color{quran}[%s\,\foreignlanguage{english}{%s}]}"
                       % (_inl(ed, r["inl"], ltr, notes, st), words(name), word(num, True)))
            st["quran"] += 1
        elif t == "math":
            tex = r.get("tex", "")
            if tex and math_ok(tex):
                out.append(mathbox(tex, r.get("dir") == "rtl", False))
                st["math_typeset"] += 1
            else:
                out.append(words(r.get("ink", ""), ltr))
                st["math_text"] += 1
        elif t in ("b", "i"):
            out.append((r"\textbf{%s}" if t == "b" else r"\textit{%s}") % _inl(ed, r["inl"], ltr, notes, st))
        elif t in ("sup", "sub"):
            out.append((r"\textsuperscript{%s}" if t == "sup" else r"\textsubscript{%s}")
                       % _inl(ed, r["inl"], ltr, notes, st))
        elif t == "link":
            out.append(_inl(ed, r["inl"], ltr, notes, st))
    return "".join(out)


def _para(ed, n, notes, st) -> str:
    ltr = bool(n.lang) and n.lang not in ("und",) and is_ltr(n.text) or (n.lang == "und" and is_ltr(n.text))
    body = _inl(ed, n.inl, ltr, notes, st)
    if ltr:
        return r"\begin{otherlanguage}{english}%s\end{otherlanguage}" % body
    return body


def _grid(rows):
    """Rows of cells (with colspan/rowspan) to a grid: per row, [(kind, cell, k)]: ("cell", c, 0) where a cell
    starts, ("cover", c, k) in the k-th row below it that a rowspan covers."""
    occ, grid = {}, []
    for ri, r in enumerate(rows):
        line, ci = [], 0
        cells = list(r["cells"])
        while cells or (ri, ci) in occ:
            if (ri, ci) in occ:
                c, k = occ[(ri, ci)]
                line.append(("cover", c, k))
                ci += c["colspan"]
                continue
            c = cells.pop(0)
            line.append(("cell", c, 0))
            for dr in range(1, c["rowspan"]):
                occ[(ri + dr, ci)] = (c, dr)
            ci += c["colspan"]
        grid.append((r, line))
    ncol = max((sum(c["colspan"] for _, c, _ in line) for _, line in grid), default=1)
    return grid, ncol


def _table_tex(ed, n, notes, st) -> str:
    r"""A table, right to left: the master stores each row's cells in reading order (the first is the rightmost);
    the tabular is set left to right with the columns reversed, which puts the first cell on the right whatever
    babel does with tabular direction. Merged cells: \multicolumn, and \multirow written in the LAST row it
    spans with a negative count, so a shaded row below does not paint over it."""
    grid, ncol = _grid(n.extra["rows"])
    st["tables"] += 1
    rows = []
    for r, line in grid:
        cells, col, cover = [], 0, set()
        for kind, c, k in line:
            span = c["colspan"]
            last = c["rowspan"] - 1
            if (kind == "cell" and last == 0) or (kind == "cover" and k == last):
                body = r"{\textdir TRT %s}" % _inl(ed, c["inl"], False, notes, st)
                if c["th"]:
                    body = r"\textbf{%s}" % body
                if last:
                    body = r"\multirow{-%d}{*}{%s}" % (c["rowspan"], body)
            else:
                body = ""
            if k < last:
                cover.update(range(col, col + span))
            if span > 1:
                body = r"\multicolumn{%d}{|c|}{%s}" % (span, body)
            cells.append(body)
            col += span
        pre = r"\rowcolor{black!8}" if r["head"] else ""
        rows.append(pre + " & ".join(reversed(cells)) + r" \\")
        mirrored = {ncol - 1 - k for k in cover}
        if mirrored:
            segs, start = [], None
            for k in range(ncol + 1):
                if k < ncol and k not in mirrored:
                    start = k if start is None else start
                elif start is not None:
                    segs.append(r"\cline{%d-%d}" % (start + 1, k))
                    start = None
            rows.append("".join(segs))
        else:
            rows.append(r"\hline")
    cap = _inl(ed, n.extra.get("caption", []), False, notes, st)
    lab = words(n.extra.get("label", "")) if n.extra.get("label") else ""
    return ("\\begin{table}[htbp]\\centering\n" + (r"\caption*{%s %s}" % (lab, cap) if (cap or lab) else "") +
            "\n{\\textdir TLT\\begin{tabular}{|%s|}\\hline\n" % "|".join(["c"] * ncol) + "\n".join(rows) +
            "\n\\end{tabular}}\n\\end{table}\n")


COLOPHON_AR = "طبعة معاد تنضيدها من ملفات المصدر (JATS و ALTO)؛ المسح الضوئي هو الشاهد."
COLOPHON_EN = "Re-typeset edition from the master files (JATS + ALTO); the scan is the evidence."
# the words the one-column print adds of its own (for the word checks)
ONECOL_LABELS = " ".join([COLOPHON_AR, COLOPHON_EN, "Text: words verified agreed flagged corrected per-word marks in "
                          "the ALTO file", "Abstract الملخص Keywords الكلمات المفتاحية ISSN DOI Mandumah"])


def onecol_tex(ed: Edition) -> tuple[str, dict]:
    st = dict(paragraphs=0, headings=0, footnotes=0, endnotes=0, quran=0, math_typeset=0, math_text=0,
              math_crop=0, tables=0, refs=0)
    f = ed.front
    notes = {}
    for i, nt in enumerate(ed.notes, 1):
        notes[nt.id] = dict(note=nt, num=i, used=False)
    authors = f["authors"]
    out = [_preamble(), r"""\usepackage[a4paper,margin=2.3cm,top=2.4cm,bottom=2.6cm]{geometry}
\usepackage{caption}
\usepackage{fancyhdr}
\usepackage[hidelinks,unicode,pdfusetitle]{hyperref}
\setlength{\parindent}{1.2em}\setlength{\parskip}{0.25em}
\linespread{1.12}
\pagestyle{fancy}\fancyhf{}\renewcommand{\headrulewidth}{0pt}
\fancyfoot[C]{\small\thepage}
\fancyhead[C]{\footnotesize\color{black!60} %s}
\makeatletter\renewcommand\@makefntext[1]{\noindent\makebox[1.6em][r]{\@thefnmark.\ }#1}\makeatother
\begin{document}
""" % words(f.get("journal", ""))]
    # ---- title block
    out.append(r"\begin{center}")
    if f.get("subjects"):
        rub = next((s["text"] for s in f["subjects"] if s.get("id")), "")
        if rub:
            out.append(r"{\small\color{black!60}%s}\par\medskip" % words(rub))
    out.append(r"{\LARGE\bfseries %s\par}" % words(f.get("title", "")))
    if f.get("subtitle"):
        out.append(r"\smallskip{\large %s\par}" % words(f["subtitle"]))
    for tt in f.get("trans_titles", [])[:1]:
        if tt.get("title"):
            out.append(r"\smallskip{\normalsize\itshape\foreignlanguage{english}{%s}\par}" % words(tt["title"], True))
    out.append(r"\bigskip")
    for a in authors:
        aff = "; ".join(a.get("aff") or [])
        out.append(r"{\large %s}\par" % words(a["display"]))
        if a.get("name_en"):
            out.append(r"{\small\foreignlanguage{english}{%s}}\par" % words(a["name_en"], True))
        if aff:
            out.append(r"{\small\color{black!70}%s}\par" % words(aff))
        out.append(r"\smallskip")
    facts = []
    if f.get("journal"):
        facts.append(words(f["journal"]))
    vi = []
    if f.get("volume"):
        vi.append(words("مج " + f["volume"]))
    if f.get("issue"):
        vi.append(words("ع " + f["issue"]))
    if vi:
        facts.append("، ".join(vi))
    if f.get("date") or f.get("year"):
        facts.append(words(f.get("date") or f.get("year")))
    if f.get("fpage"):
        facts.append(words("ص " + f["fpage"] + ("–" + f["lpage"] if f.get("lpage") else "")))
    if facts:
        out.append(r"\medskip{\small %s}\par" % r" \textbullet{} ".join(facts))
    ids = []
    if f.get("issn"):
        ids.append("ISSN " + ", ".join(f["issn"]))
    if f.get("doi"):
        ids.append("DOI " + f["doi"])
    ids.append("Mandumah " + (f.get("article_id") or ed.stem) + (" / " + f["record"] if f.get("record") else ""))
    out.append(r"\end{center}")
    out.append(r"\begin{otherlanguage}{english}\begin{center}\footnotesize\color{black!60}%s\end{center}"
               r"\end{otherlanguage}" % words(" · ".join(ids), True))
    for ab in f.get("abstracts", []):
        ltr = ab.get("lang") not in (None, "ar")
        head = "Abstract" if ltr else "الملخص"
        body = r"\par ".join(words(p, ltr) for p in ab["paras"])
        blk = r"\begin{quote}\small\textbf{%s.} %s\end{quote}" % (words(head, ltr), body)
        out.append((r"\begin{otherlanguage}{english}%s\end{otherlanguage}" % blk) if ltr else blk)
    for kg in f.get("keywords", []):
        ltr = kg.get("lang") not in (None, "ar")
        if kg["kwds"]:
            line = r"\begin{quote}\small\textbf{%s:} %s\end{quote}" % (
                words("Keywords" if ltr else "الكلمات المفتاحية", ltr), "، ".join(words(k, ltr) for k in kg["kwds"]))
            out.append((r"\begin{otherlanguage}{english}%s\end{otherlanguage}" % line) if ltr else line)
    out.append(r"\noindent\rule{\textwidth}{0.4pt}\par\medskip")
    # ---- body
    for n in ed.body:
        if n.kind == "heading":
            st["headings"] += 1
            sz = {1: r"\large", 2: r"\normalsize"}.get(n.level, r"\normalsize")
            out.append(r"\par\addvspace{1.1em}{\noindent%s\bfseries %s\par}\nopagebreak\smallskip" %
                       (sz, _inl(ed, n.inl, False, notes, st)))
        elif n.kind == "p":
            st["paragraphs"] += 1
            out.append(_para(ed, n, notes, st) + "\n")
        elif n.kind == "formula":
            tex, g = n.extra.get("tex", ""), n.extra.get("graphic", "")
            lab = n.extra.get("label", "")
            if tex and math_ok(tex):
                st["math_typeset"] += 1
                # set in a left-to-right box (the formula carries its own direction); its number on the left
                out.append(r"\par\medskip\noindent\hbox to\linewidth{\textdir TLT %s\hfil %s\hfil}\par\medskip" %
                           (words(lab), mathbox(tex, n.extra.get("dir") == "rtl", True)))
            elif g and (Path(ed.jats_path).parent / g).exists():
                st["math_crop"] += 1
                out.append(r"\begin{center}\includegraphics[width=0.8\textwidth,keepaspectratio]{%s} %s\end{center}"
                           % (Path(ed.jats_path).parent / g, words(lab)))
        elif n.kind == "table":
            out.append(_table_tex(ed, n, notes, st))
        out.append("\n")
    # notes no marker reached
    left = [v for v in notes.values() if not v["used"]]
    if left:
        out.append(r"\par\bigskip\noindent{\large\bfseries %s}\par\smallskip\begin{small}" % words("هوامش"))
        for v in left:
            st["endnotes"] += 1
            body = " ".join(_inl(ed, p.inl, is_ltr(p.text), None, st) for p in v["note"].paras)
            out.append(r"\noindent %s\ %s\par" % (words(v["note"].label or "•"), body))
        out.append(r"\end{small}")
    if ed.refs:
        out.append(r"\par\bigskip")
        first = True
        for r in ed.refs:
            if r.kind == "ref-head":
                if r.inl:
                    out.append(r"\par\medskip\noindent{\large\bfseries %s}\par\smallskip" % _inl(ed, r.inl, False, None, st))
                elif first:
                    out.append(r"\par\medskip\noindent{\large\bfseries %s}\par\smallskip" % words("المراجع"))
            else:
                st["refs"] += 1
                ltr = is_ltr(r.text)
                p = _inl(ed, r.inl, ltr, None, st)
                p = (r"\begin{otherlanguage}{english}\noindent\hangindent=1.5em %s\par\end{otherlanguage}" % p) if ltr \
                    else (r"\noindent\hangindent=1.5em %s\par" % p)
                out.append(r"{\small %s}" % p)
            first = False
    if ed.verses:
        out.append(r"\par\bigskip\noindent{\bfseries %s}\par\begin{small}" % words("الآيات المقتبسة"))
        for v in [v for v in ed.verses if v.get("verse")]:
            out.append(r"\noindent{\color{quran}﴿%s﴾} \foreignlanguage{english}{%s}\par" %
                       (words(v["verse"]), word(v["ref"].rpartition(" ")[2], True) if v["ref"] else ""))
        out.append(r"\end{small}")
    # colophon
    trust = (f["meta"].get("trust") or [("", None)])[0][0]
    out.append(r"\par\vfill\begin{center}\footnotesize\color{black!55}%s\end{center}" %
               words(COLOPHON_AR))
    out.append(r"\begin{otherlanguage}{english}\begin{center}\footnotesize\color{black!55}%s\end{center}"
               r"\end{otherlanguage}" % words(COLOPHON_EN + (" Text: " + trust if trust else ""), True))
    out.append("\\end{document}\n")
    return "\n".join(out), st


def onecol_pdf(ed: Edition, out_path, keep_tex: bool = False, timeout: int = 1200, **opts) -> dict:
    tex, st = onecol_tex(ed)
    r = run_lualatex(tex, Path(out_path), timeout=timeout, runs=2, keep_tex=keep_tex)
    if r["ok"]:
        st["lines_reordered"] = finish_pdf(Path(out_path), ed.front.get("title", ""),
                                           "; ".join(a["display"] for a in ed.front["authors"]),
                   "one-column re-typeset edition of %s" % ed.stem, rtl=not latin_document(ed))
        import pymupdf
        with pymupdf.open(str(out_path)) as d:
            st["pages_out"] = len(d)
    st.update(r)
    st.update(engine="lualatex", variant="onecol", pages=len(ed.pages))
    return st
