"""A PDF's ink glyphs with their DECLARED box (d1: llx lly urx ury), not only their advance: pdf/inspect.page_glyphs
reads the box as [origin, origin + urx]; here llx is honoured too (a box may start left of the glyph's origin)."""
import re, sys
from pathlib import Path
import fitz
REPO = Path(__file__).resolve().parents[2]; sys.path.insert(0, str(REPO / "src"))
from inkscript.pdf.inspect import page_glyphs
from inkscript.pdf.type3 import DPI

_P = {}


def glyphs(doc, pno):
    """page_glyphs (pno 1-based) + d1, origin and box in points (y up) and in scan pixels (y down)."""
    pg = doc[pno - 1]; out = page_glyphs(doc, pno - 1)
    for g in out:
        fx = g["font_xref"]
        if fx not in _P:
            obj = doc.xref_object(fx)
            procs = dict(re.findall(r"/(\w+) (\d+) 0 R", re.search(r"/CharProcs\s*<<(.*?)>>", obj, re.S).group(1)))
            names = re.search(r"/Differences\s*\[\s*1\s*(.*?)\]", obj, re.S).group(1).split()
            fm = float(re.search(r"/FontMatrix\s*\[\s*([\d.]+)", obj).group(1))
            _P[fx] = (procs, names, fm)
        procs, names, fm = _P[fx]
        px = int(procs[names[g["code"] - 1].lstrip("/")]); d1 = [float(x) for x in doc.xref_stream(px).decode().split("\n")[0].split()[:6]]
        k = (g["box"][2] - g["box"][0]) / d1[4] if d1[4] else fm * 8.0
        ox = g["box"][0]; oy = g["box"][1] - d1[3] * k
        g["d1"], g["proc_xref"], g["origin"] = d1, px, (ox, oy)
        g["box"] = [ox + d1[2] * k, oy + d1[3] * k, ox + d1[4] * k, oy + d1[5] * k]
        a = fitz.Point(g["box"][0], g["box"][1]) * pg.transformation_matrix * (DPI / 72.0)
        b = fitz.Point(g["box"][2], g["box"][3]) * pg.transformation_matrix * (DPI / 72.0)
        g["box_px"] = [min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)]
    return out


def find_word(gl, text):
    """Runs of glyphs (stream order = left to right) whose texts, read right to left, spell `text`."""
    vis = text[::-1]; res = []
    for i in range(len(gl)):
        s, j = "", i
        while j < len(gl) and len(s) < len(vis) and gl[j]["font"] == gl[i]["font"]:
            s += gl[j]["text"]; j += 1
        if s == vis and (i == 0 or gl[i - 1]["text"] in (" ", "") or gl[i - 1]["font"] != gl[i]["font"] or abs(gl[i - 1]["box"][2] - gl[i]["box"][0]) > 0.3):
            res.append(gl[i:j])
    return res
