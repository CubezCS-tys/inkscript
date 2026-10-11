"""Experiment 35: which engine sets the print editions? LuaLaTeX (HarfBuzz, babel kashida) against Chromium
(HTML + CSS -> PDF, spaces-only justification), on real documents and the hand-made test masters.

    PYTHONPATH=src .venv/bin/python experiments/35_edition/bakeoff.py [--docs ID ...] [--engines lualatex chromium]

Writes /home/yassine/inkscript/experiments/35_edition/out/bakeoff.json and the PDFs under out/bakeoff/.
Measured per document, engine and variant (layout-faithful, one column):
  pdfium read-back: words found and words in order (experiments/35_edition/printcheck.py)
  justification: word gaps in full-width lines (median, 90th percentile, in line heights), lines with a river
  fit: lines squeezed to fit their width (layout), blocks shrunk; time and peak memory
  faithfulness (layout only): correlation of ink density with the scan on a coarse grid
"""
from __future__ import annotations

import argparse
import html
import json
import subprocess
import sys
import tempfile
import time
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from printcheck import justification, read_back, tokens  # noqa: E402

from inkscript.edition import fonts  # noqa: E402
from inkscript.edition.model import load  # noqa: E402
from inkscript.edition.printpdf import (_line_mode, finish_pdf, is_ltr, layout_pdf,  # noqa: E402
                                        onecol_pdf, page_blocks)

MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")
FIX = HERE.parent.parent / "tests" / "fixtures" / "edition"
OUT = Path("/home/yassine/inkscript/experiments/35_edition/out")
PW = Path("/tmp/claude-1000/-home-yassine-inkscript/ed816869-9be5-4008-b630-480b426fc462/scratchpad/pw/bin/python")
DOCS = ["0005-055-003-004",       # 2004, clean single column, a footnote
        "0048-002-007-009",       # 1985, two columns
        "0367-000-092-026",       # 1997, two columns, 11 pages
        "0392-000-003-002",       # 1991, 46 footnotes and references
        "0747-001-003-001",       # 1950, 74 footnotes
        "0701-010-004-013",       # 1978, Latin-script paragraphs
        "0189-013-006-010",       # 1992, vowelled paragraphs, references, two columns
        "0924-012-005-007"]       # 1932, the oldest
TESTS = ["test-0001-table-math", "test-0002-two-columns"]


# ---------------------------------------------------------------------------------------------- expectations

def expected_layout(ed) -> list[list[str]]:
    """Per page, the tokens of every ALTO word in the order the layout edition writes its blocks."""
    out = []
    for n in ed.page_numbers:
        toks = []
        for b in page_blocks(ed, n):
            for w in b.words:
                toks += tokens(w.text)
        out.append(toks)
    return out


def expected_onecol(ed) -> list[str]:
    """The article's ink text in reading order: title, body, references (notes are counted for words found but
    their place in the order is the foot of a page, so they are left out of the order sequence)."""
    toks = tokens(ed.front.get("title", ""))
    for n in ed.body:
        toks += tokens(n.text)
    for n in ed.refs:
        toks += tokens(n.text)
    return toks


def expected_notes(ed) -> list[str]:
    return [t for nt in ed.notes for p in nt.paras for t in tokens(p.text)]


# ---------------------------------------------------------------------------------------------- Chromium

FONT_CSS = """@font-face{font-family:Mk;src:url(%(reg)s)}@font-face{font-family:Mk;font-weight:bold;src:url(%(bold)s)}
@font-face{font-family:Fb;src:url(%(amiri)s)}"""


def _font_css():
    return FONT_CSS % dict(reg=fonts.font_path("markazi").as_uri(), bold=fonts.font_path("markazi", "bold").as_uri(),
                           amiri=fonts.font_path("amiri").as_uri())


FIT_JS = """
(function(){
  var st={squeezed:0,lines:0};
  document.querySelectorAll('.blk').forEach(function(b){
    var ls=b.querySelectorAll('.ln'), r=[];
    ls.forEach(function(l){var s=l.querySelector('span'); s.style.fontSize='10pt';
      var w=s.getBoundingClientRect().width; if(w>0) r.push(10*parseFloat(l.dataset.w)*96/72/w);});
    r.sort(function(a,b){return a-b;});
    var s=parseFloat(b.dataset.sh);
    if(r.length){var q=r[Math.max(0,Math.round(r.length*0.10)-1)]; s=Math.min(s,q,r[0]*1.04);}
    if(s<3.5) s=3.5;
    ls.forEach(function(l){var sp=l.querySelector('span'); sp.style.fontSize=s+'pt'; st.lines++;
      var avail=parseFloat(l.dataset.w)*96/72, nat=sp.getBoundingClientRect().width;
      if(nat>avail){st.squeezed++; sp.style.display='inline-block'; sp.style.transformOrigin=(l.dataset.m=='L'?'left':'right');
        sp.style.transform='scaleX('+(avail/nat)+')';}
      else if(l.dataset.m=='J' && nat>0.8*avail){l.style.textAlignLast='justify'; l.style.textAlign='justify';}
    });
  });
  window.inkstat=st;
})();
"""


def chromium_layout_html(ed) -> str:
    css = [_font_css(), "*{margin:0;padding:0}body{font-family:Mk,Fb}",
           ".pg{position:relative;overflow:hidden;break-after:page}",
           ".ln{position:absolute;white-space:nowrap;line-height:1}",
           ".furn{color:#808080}.b{font-weight:bold}"]
    sizes, pages = {}, []
    for n in ed.page_numbers:
        pg = ed.pages[n]
        W, H = pg.pt_w, pg.pt_h
        key = "p%dx%d" % (round(W * 10), round(H * 10))
        sizes[key] = (W, H)
        sc = W / pg.w
        parts = ['<div class="pg" style="page:%s;width:%.2fpt;height:%.2fpt">' % (key, W, H)]
        for b in page_blocks(ed, n):
            lines = [ln for ln in b.lines if ln.words]
            if not lines:
                continue
            from statistics import median
            sh = max(4.0, median(ln.box[3] for ln in lines) * sc * 1.05)
            cls = "blk" + (" furn" if b.furniture or b.kind == "stray" else "") + \
                (" b" if b.kind in ("title", "heading") or b.role in ("title", "sectionHeading") else "")
            parts.append('<div class="%s" data-sh="%.2f">' % (cls, sh))
            for ln in lines:
                x, y, w, h = ln.box
                s = " ".join(wd.text for wd in ln.words)
                m = _line_mode(ln, b, lines)
                al = {"J": "right", "R": "right", "L": "left", "C": "center"}[m]
                d = "ltr" if is_ltr(s) else "rtl"
                parts.append('<div class="ln" dir="%s" data-w="%.2f" data-m="%s" style="left:%.2fpt;top:%.2fpt;'
                             'width:%.2fpt;height:%.2fpt;line-height:%.2fpt;text-align:%s"><span>%s</span></div>'
                             % (d, w * sc, m, x * sc, y * sc, w * sc, h * sc, h * sc, al, html.escape(s)))
            parts.append("</div>")
        parts.append("</div>")
        pages.append("".join(parts))
    for k, (W, H) in sizes.items():
        css.append("@page %s{size:%.2fpt %.2fpt;margin:0}" % (k, W, H))
    return ('<!doctype html><html lang="ar"><head><meta charset="utf-8"><style>%s</style></head><body>%s'
            '<script>%s</script></body></html>' % ("\n".join(css), "".join(pages), FIT_JS))


def _inl_html(inl):
    out = []
    for r in inl:
        t = r["t"]
        if t in ("text", "fnref"):
            out.append(html.escape(r["s"]) if t == "text" else "<sup>%s</sup>" % html.escape(r["s"]))
        elif t == "quran":
            out.append('<span style="color:#145f3c">%s</span> <small>[%s]</small>' % (_inl_html(r["inl"]),
                                                                                   html.escape(r.get("title", ""))))
        elif t == "math":
            out.append(r.get("mathml") or html.escape(r.get("ink", "")))
        else:
            out.append(_inl_html(r.get("inl", [])))
    return "".join(out)


def chromium_onecol_html(ed) -> str:
    f = ed.front
    css = _font_css() + """
@page{size:A4;margin:2.3cm 2.3cm 2.6cm}body{font-family:Mk,Fb;font-size:11pt;line-height:1.45;text-align:justify}
h1{text-align:center;font-size:20pt}.au{text-align:center}h2{font-size:13pt;margin-top:1em}p{text-indent:1.2em;margin:.2em 0}
.notes{font-size:9pt}table{border-collapse:collapse;margin:auto}td,th{border:1px solid #555;padding:2px 6px}"""
    body = ["<h1>%s</h1>" % html.escape(f.get("title", ""))]
    for a in f["authors"]:
        body.append('<p class="au">%s</p>' % html.escape(a["display"]))
    for n in ed.body:
        lang = ' dir="ltr" lang="en"' if (n.lang and is_ltr(n.text)) else ""
        if n.kind == "heading":
            body.append("<h2>%s</h2>" % _inl_html(n.inl))
        elif n.kind == "p":
            body.append("<p%s>%s</p>" % (lang, _inl_html(n.inl)))
        elif n.kind == "formula":
            body.append('<p style="text-align:center">%s %s</p>' % (n.extra.get("mathml", ""),
                                                                     html.escape(n.extra.get("label", ""))))
        elif n.kind == "table":
            rows = []
            for r in n.extra["rows"]:
                cells = "".join('<%s colspan="%d" rowspan="%d">%s</%s>' % ("th" if c["th"] else "td", c["colspan"],
                                                                           c["rowspan"], _inl_html(c["inl"]),
                                                                           "th" if c["th"] else "td")
                                for c in r["cells"])
                rows.append("<tr>%s</tr>" % cells)
            body.append('<table dir="rtl">%s</table>' % "".join(rows))
    if ed.notes:
        body.append('<div class="notes"><h2>الهوامش</h2>')
        for nt in ed.notes:
            body.append("<p>%s %s</p>" % (html.escape(nt.label), " ".join(_inl_html(p.inl) for p in nt.paras)))
        body.append("</div>")
    for r in ed.refs:
        body.append(("<h2>%s</h2>" if r.kind == "ref-head" else '<p class="ref">%s</p>') % _inl_html(r.inl))
    return ('<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8"><style>%s</style></head><body>%s'
            '<script>window.inkstat={}</script></body></html>' % (css, "\n".join(body)))


PRINT_PY = r"""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
src, dst = sys.argv[1], sys.argv[2]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page()
    pg.goto(Path(src).resolve().as_uri())
    pg.wait_for_load_state("networkidle")
    pg.wait_for_timeout(200)
    st = pg.evaluate("window.inkstat || {}")
    pg.pdf(path=dst, prefer_css_page_size=True, print_background=True)
    b.close()
print(json.dumps(st))
"""


def chromium_pdf(html_text: str, out_pdf: Path, timeout: int = 600) -> dict:
    out_pdf.parent.mkdir(parents=True, exist_ok=True)
    src = out_pdf.with_suffix(".html")
    src.write_text(html_text, encoding="utf-8")
    t0 = time.time()
    with tempfile.NamedTemporaryFile("w", suffix=".py", delete=False) as f:
        f.write(PRINT_PY)
        script = f.name
    r = subprocess.run(["/usr/bin/time", "-f", "%M", "nice", "-n", "10", str(PW), script, str(src), str(out_pdf)],
                       capture_output=True, text=True, timeout=timeout)
    Path(script).unlink(missing_ok=True)
    st = {}
    try:
        st = json.loads(r.stdout.strip().splitlines()[-1])
    except (ValueError, IndexError):
        pass
    try:
        peak = int(r.stderr.strip().splitlines()[-1]) // 1024     # the driver only: Chromium's own processes not counted
    except (ValueError, IndexError):
        peak = None
    ok = out_pdf.exists()
    if ok:
        finish_pdf(out_pdf, "", "", "")
    return dict(ok=ok, seconds=round(time.time() - t0, 2), peak_mb_driver=peak, engine="chromium", **st)


# ---------------------------------------------------------------------------------------------- faithfulness

def ink_correlation(scan_pdf, rebuilt_pdf, grid=(60, 42)) -> float:
    """Mean over pages of the correlation of ink density (share of dark pixels per cell of a coarse grid) between
    the scan and the rebuilt page: 1 = the same ink in the same places."""
    import pymupdf
    cs = []
    with pymupdf.open(str(scan_pdf)) as a, pymupdf.open(str(rebuilt_pdf)) as b:
        for i in range(min(len(a), len(b))):
            dens = []
            for d in (a, b):
                pix = d[i].get_pixmap(dpi=50, colorspace=pymupdf.csGRAY)
                g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
                thr = min(170, int(np.percentile(g, 50)) - 40)
                ink = (g < thr).astype(np.float32)
                H, W = ink.shape
                gy, gx = grid
                ink = ink[: H - H % gy, : W - W % gx].reshape(gy, (H - H % gy) // gy, gx, (W - W % gx) // gx)
                dens.append(ink.mean(axis=(1, 3)).ravel())
            if dens[0].std() > 0 and dens[1].std() > 0:
                cs.append(float(np.corrcoef(dens[0], dens[1])[0, 1]))
    return round(float(np.mean(cs)), 3) if cs else 0.0


# ---------------------------------------------------------------------------------------------- the run

def jats_of(i):
    p = FIX / f"{i}.jats.xml"
    return p if p.exists() else MERGED / f"{i}.jats.xml"


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--docs", nargs="*", default=DOCS + TESTS)
    ap.add_argument("--engines", nargs="*", default=["lualatex", "chromium"])
    ap.add_argument("--variants", nargs="*", default=["layout", "onecol"])
    ap.add_argument("--layout-modes", nargs="*", default=["lines"])
    a = ap.parse_args(argv)
    outd = OUT / "bakeoff"
    outd.mkdir(parents=True, exist_ok=True)
    res_path = OUT / "bakeoff.json"
    results = json.loads(res_path.read_text()) if res_path.exists() else {}
    for i in a.docs:
        ed = load(jats_of(i))
        exp_pages, exp_doc, exp_notes = expected_layout(ed), expected_onecol(ed), expected_notes(ed)
        for eng in a.engines:
            for var in a.variants:
                modes = a.layout_modes if (var == "layout" and eng == "lualatex") else [None]
                for mode in modes:
                    key = f"{i}|{eng}|{var}" + (f"|{mode}" if mode and mode != "lines" else "")
                    pdf = outd / (f"{i}.{eng}.{var}" + (f".{mode}" if mode and mode != "lines" else "") + ".pdf")
                    print(key, flush=True)
                    try:
                        if eng == "lualatex":
                            st = layout_pdf(ed, pdf, mode=mode) if var == "layout" else onecol_pdf(ed, pdf)
                        else:
                            h = chromium_layout_html(ed) if var == "layout" else chromium_onecol_html(ed)
                            st = chromium_pdf(h, pdf)
                    except Exception as e:                      # one failure must not stop the bake-off
                        results[key] = dict(ok=False, error=repr(e)[:300])
                        continue
                    if not st.get("ok"):
                        results[key] = st
                        continue
                    if var == "layout":
                        st["read"] = read_back(pdf, expected_pages=exp_pages)
                        if ed.pdf_path:
                            st["ink_corr"] = ink_correlation(ed.pdf_path, pdf)
                    else:
                        st["read"] = read_back(pdf, expected_doc=exp_doc)
                        st["read_notes_found"] = read_back(pdf, expected_doc=exp_notes)["found_pct"] if exp_notes \
                            else None
                    st["just"] = justification(pdf)
                    st["pages"] = len(ed.pages)
                    results[key] = st
                    print("  ", json.dumps({k: st.get(k) for k in ("seconds", "read", "just", "ink_corr",
                                                                   "squeezed")}, ensure_ascii=False), flush=True)
                    res_path.write_text(json.dumps(results, ensure_ascii=False, indent=1))
    res_path.write_text(json.dumps(results, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
