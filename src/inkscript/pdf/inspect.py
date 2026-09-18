"""Read a finished PDF's text layer back: every glyph of every ink font on a
page, with its stored text, its box and its outline, taken from the Type 3
fonts themselves. What the storyboard draws and what `correct` edits."""
from __future__ import annotations
import re
import fitz
from .type3 import DPI


def page_glyphs(doc, pno: int, tag: str | None = None) -> list[dict]:
    """Glyphs of page `pno` (0-based) in stream order. Each: font (resource
    name), font_xref, tounicode_xref, code, text (as stored), box in PDF points
    [x0, y0, x1, y1] (y up), box_px in scan pixels (y down, like the Azure
    boxes and shapes.json), paths (outline polygons in PDF points), ids."""
    pg = doc[pno]; c = pg.read_contents().decode("latin1"); H = pg.rect.height
    tag = tag or f"P{pno + 1}"
    out = []
    for fn, fx in {f[4]: f[0] for f in pg.get_fonts(full=True)}.items():
        if not re.match(rf"T3{re.escape(tag)}L\d+$", fn):
            continue
        obj = doc.xref_object(fx); tu = doc.xref_get_key(fx, "ToUnicode"); tux = int(tu[1].split()[0])
        cmap = doc.xref_stream(tux).decode()
        bf = {int(code, 16): "".join(chr(int(h[i:i + 4], 16)) for i in range(0, len(h), 4)) for code, h in re.findall(r"<([0-9A-F]{2})> <([0-9A-F]+)>", cmap)}
        fm = float(re.search(r"/FontMatrix\s*\[\s*([\d.]+)", obj).group(1))
        widths = [float(x) for x in re.search(r"/Widths\s*\[(.*?)\]", obj, re.S).group(1).split()]
        names = re.search(r"/Differences\s*\[\s*1\s*(.*?)\]", obj, re.S).group(1).split()
        procs = dict(re.findall(r"/(\w+) (\d+) 0 R", re.search(r"/CharProcs\s*<<(.*?)>>", obj, re.S).group(1)))
        m = re.search(r"BT /%s ([\d.]+) Tf ([-\d. ]+) Tm \[(.*?)\] TJ ET" % re.escape(fn), c, re.S)
        if not m:
            continue
        size = float(m.group(1)); tmv = [float(x) for x in m.group(2).split()]; ox, oy = tmv[4], tmv[5]; k = fm * size; pen = ox
        for tok in re.findall(r"<([0-9A-F]{2})>|(-?[\d.]+)", m.group(3)):
            if tok[0]:
                code = int(tok[0], 16); nm = names[code - 1].lstrip("/"); w = widths[code - 1] * k
                if not nm.startswith("sp"):
                    px = int(procs[nm]); body = doc.xref_stream(px).decode(); paths = []
                    for seg in re.findall(r"(-?\d+ -?\d+ m(?: -?\d+ -?\d+ l)+ h)", body):
                        pts = [(float(a), float(b)) for a, b in re.findall(r"(-?\d+) (-?\d+) [ml]", seg)]
                        paths.append([[pen + qx * k, oy + qy * k] for qx, qy in pts])
                    d1 = [float(x) for x in body.split("\n")[0].split()[:6]]
                    ids = re.findall(r"/InkShapes \[([^\]]*)\]", doc.xref_object(px))
                    box = [pen, oy + d1[3] * k, pen + d1[4] * k, oy + d1[5] * k]
                    # scan pixels: through the page's own transformation (crop
                    # box offset, rotation), the frame the Azure boxes and
                    # shapes.json placements use
                    a = fitz.Point(box[0], box[1]) * pg.transformation_matrix * (DPI / 72.0)
                    b = fitz.Point(box[2], box[3]) * pg.transformation_matrix * (DPI / 72.0)
                    out.append(dict(font=fn, font_xref=fx, tounicode_xref=tux, code=code, text=bf.get(code, ""), box=box,
                                    box_px=[min(a.x, b.x), min(a.y, b.y), max(a.x, b.x), max(a.y, b.y)], paths=paths,
                                    ids=ids[0].split() if ids else []))
                pen += w
            else:
                pen -= float(tok[1]) / 1000 * size
    return out


def set_glyph_text(doc, glyph: dict, stored: str) -> None:
    """Rewrite one glyph's ToUnicode entry (the stored, visual-order string)."""
    from .type3 import hex16
    tux = glyph["tounicode_xref"]; cmap = doc.xref_stream(tux).decode()
    line = re.compile(r"<%02X> <[0-9A-F]+>" % glyph["code"])
    if not line.search(cmap):
        raise ValueError(f"glyph code {glyph['code']} not in the font's ToUnicode")
    doc.update_stream(tux, line.sub(f"<{glyph['code']:02X}> <{hex16(stored)}>", cmap, count=1).encode())
