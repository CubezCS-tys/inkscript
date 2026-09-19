"""The page's own ink as a PDF font. One Type 3 font per line, one glyph per
word whose outline is that word's traced ink, mapped through ToUnicode to the
word's text; one text run per line.

Every rule below was found by testing against pdfium (Chrome), MuPDF and
poppler, with a LibreOffice-typeset Arabic PDF as the reference for "native":
see docs/pdf-writing-rules.md.
"""
from __future__ import annotations
import fitz

from ..text import RTL, visual, latin_majority
from ..geometry.layout import split_word

DPI = 300


SIZE_PT = 8.0
SIZE_MODE = "fixed"                                 # "gap": per-line size from the widest word gap (Firefox)
SIZE_MAX = 48.0
BAND_SORT = True                                    # same-band runs left to right (see write_text_layer)


# Gap kept between the declared boxes of adjacent lines, as a fraction of the
# line's ink height. pdfium's line-break decision is a near-zero threshold on
# the gap: boxes that merely touch (under 1pt apart) were read as one line.
GAP_FRAC = 0.30


def hex16(s: str) -> str:
    return s.encode("utf-16-be").hex().upper()


class Frame:
    """The pixel frame the layout was done in, relative to the page's own.

    rot=0: the page as rendered. rot=90 / -90: the page image was turned so
    that sideways text (Azure angle ≈ ±90°) reads horizontally; (u, v) are
    pixels in that turned image, W and H the page image's own width/height.
    """
    def __init__(self, rot: int, W: int, H: int):
        self.rot, self.W, self.H = rot, W, H

    def to_page(self, u, v):
        if self.rot == 90:    return self.W - v, u          # image turned counter-clockwise
        if self.rot == -90:   return v, self.H - u          # clockwise
        return u, v

    def text_axes(self):
        """(x-axis, y-axis) of text space in page-pixel terms (y down)."""
        if self.rot == 90:    return (0, 1), (1, 0)
        if self.rot == -90:   return (0, -1), (-1, 0)
        return (1, 0), (0, -1)


def write_text_layer(doc, pg, M, lines, tag, invisible, frame: "Frame | None" = None):
    """Type 3 font per line + one text run per line, appended as content."""
    frame = frame or Frame(0, 0, 0)
    res = doc.xref_get_key(pg.xref, "Resources")
    if res[0] == "xref":
        res_xref = int(res[1].split()[0])
    else:
        # Resources may be inherited from the Pages tree. A fresh dictionary
        # on the page would shadow the inherited one and the page's image
        # XObject would vanish ("cannot find XObject resource 'Im0'": whole
        # documents rendered blank). Copy the inherited dictionary first.
        inherited = res[1] if res[0] == "dict" else None
        if inherited is None:
            parent = doc.xref_get_key(pg.xref, "Parent")
            while parent[0] == "xref":
                px = int(parent[1].split()[0]); r = doc.xref_get_key(px, "Resources")
                if r[0] == "xref":
                    inherited = doc.xref_object(int(r[1].split()[0])); break
                if r[0] == "dict":
                    inherited = r[1]; break
                parent = doc.xref_get_key(px, "Parent")
        res_xref = doc.get_new_xref(); doc.update_object(res_xref, inherited or "<< >>")
        doc.xref_set_key(pg.xref, "Resources", f"{res_xref} 0 R")
    def subdict(name):
        """(xref, key prefix) to add entries to Resources/<name>: the
        sub-dictionary may be inline, missing, or an indirect object (an
        inherited Resources copy), and PyMuPDF refuses a key path through
        an indirect reference."""
        v = doc.xref_get_key(res_xref, name)
        if v[0] == "xref":
            return int(v[1].split()[0]), ""
        if v[0] == "null":
            doc.xref_set_key(res_xref, name, "<< >>")
        return res_xref, name + "/"
    font_x, font_p = subdict("Font")
    if invisible:
        gs = doc.get_new_xref(); doc.update_object(gs, "<< /Type /ExtGState /ca 0 /CA 0 >>")
        gx, gp = subdict("ExtGState")
        doc.xref_set_key(gx, f"{gp}GSinv{tag}", f"{gs} 0 R")
    out = ["q", f"/GSinv{tag} gs" if invisible else "0 g"]
    live = [L for L in lines if any(w["blobs"] for w in L)]
    # Lines in page order, each with its baseline (bottom of Azure's boxes)
    # and its ink extent. A glyph's declared box is clipped at the ink of the
    # line above and the line below, so no two lines' boxes ever touch: pdfium
    # merges text whose boxes overlap into one line.
    geo = []
    for L in live:
        bl = [b for w in L if w["blobs"] for b in w["blobs"]]
        geo.append(dict(L=L, ly1=max(w["y1"] for w in L if w["blobs"]), top=min(b["y"] for b in bl), bot=max(b["y"] + b["h"] for b in bl)))
    # Vertical neighbours (for box clipping) come from the page order; the
    # runs themselves are written in Azure's line order, which is reading
    # order: on a two-column page Azure gives the right column's lines, then
    # the left's, band by band. Sorting by baseline interleaved the columns.
    by_y = sorted(geo, key=lambda g: g["ly1"])
    for i, g in enumerate(by_y):
        # Vertical neighbours are the nearest runs on OTHER bands. A run on
        # the same baseline (a bracketed phrase set apart, the two halves of
        # a running head) is not above or below; taken as one, it clipped
        # the declared boxes of a whole line to a sliver at the baseline.
        lh = max(1.0, g["bot"] - g["top"])
        g["above"] = next((by_y[j] for j in range(i - 1, -1, -1) if by_y[j]["ly1"] < g["ly1"] - 0.5 * lh), None)
        g["below"] = next((by_y[j] for j in range(i + 1, len(by_y)) if by_y[j]["ly1"] > g["ly1"] + 0.5 * lh), None)
    # Runs that share a band (a run's baseline inside the previous run's
    # ink: table cells, a running head's two halves, the two columns of a
    # line pair) are one line to pdfium — it joins text objects whose boxes
    # overlap vertically whatever the horizontal gap, then reverses the
    # whole line's segments. So within a band the runs go left to right,
    # and the reversal gives them back right to left, in reading order.
    # Written in Azure's (reading) order they came back swapped.
    ordered, i = [], 0
    while BAND_SORT and i < len(geo):
        band, j = [geo[i]], i + 1
        while j < len(geo):
            g, last = geo[j], band[-1]
            if abs(g["ly1"] - last["ly1"]) < 0.5 * min(last["bot"] - last["top"], g["bot"] - g["top"]):
                band.append(g); j += 1
            else:
                break
        band.sort(key=lambda g: min(w["x0"] for w in g["L"] if w["blobs"]))
        ordered += band; i = j
    geo = ordered or geo
    def to_pdf(u, v):
        x, y = frame.to_page(u, v)
        return fitz.Point(x * 72 / DPI, y * 72 / DPI) * M
    (ax, ay), (bx, by) = frame.text_axes()
    # M's linear part maps page-pixel directions to PDF directions.
    a, b = M.a * ax + M.c * ay, M.b * ax + M.d * ay
    c, d = M.a * bx + M.c * by, M.b * bx + M.d * by
    tm = f"{a:.4f} {b:.4f} {c:.4f} {d:.4f}"
    glyphs = 0
    stats = dict(words=0, split=0, pieces=0)
    for li, g in enumerate(geo):
        L, ly1, ly0 = g["L"], g["ly1"], g["top"]
        size_pt = SIZE_PT
        # Glyph space is in PIXELS: FontMatrix scales one glyph unit to one
        # scan pixel at SIZE_PT, so outline coordinates are the traced integers
        # and the geometry is stored unchanged to the pixel. (Decimal 1/1000
        # units cost 19% more after compression for no extra precision.)
        # TJ adjustments are in thousandths of text space regardless of the
        # font matrix, hence `tj` for those.
        km = 72.0 / (DPI * size_pt)                        # glyph unit (1 px) in text space
        u = 1.0
        tj = 1000.0 * km
        ly1 = int(round(ly1))                              # integer baseline: every glyph coordinate stays integral
        gap = max(2.0, GAP_FRAC * (g["bot"] - g["top"]))
        if g["above"] is not None:
            # Clipping stops at the neighbour's ink plus the gap even when the
            # neighbour's brackets or descenders reach below this line's top:
            # the boxes then shrink to a sliver on the baseline (a hairline
            # highlight on that line), but a box that overlapped the
            # neighbour's made pdfium read the two lines as one (page 2 of
            # the fixture fell from 113 lines to 7 when the clip stopped at
            # the midpoint of the overlap instead).
            ly0 = max(ly0, g["above"]["bot"] + gap)
        # One glyph per connected piece of ink where text and ink agree on
        # the count (see layout.split_word); the word otherwise. Pieces are
        # laid out in visual order; a word's pieces carry its id so that the
        # space glyph goes between words only.
        lh_line = max(1.0, g["bot"] - g["top"])
        rtl_line = any(RTL.search(w["text"]) for w in L)
        ltr_line = rtl_line and latin_majority(" ".join(w["text"] for w in L))   # pdfium reads it left to right
        ws = []
        for wid, w in enumerate(sorted((w for w in L if w["blobs"]), key=lambda w: w["x0"])):
            pcs = split_word(w, lh_line)
            # Within a word, pieces go in text order reversed (right to left),
            # not by ink position: a و whose tail sweeps under the next letter
            # starts further left than that letter and would otherwise be
            # written after it, and the word would copy out as `اولعالم`.
            for pc in reversed(pcs) if len(pcs) > 1 else pcs:
                pc["_wid"] = (wid, pc.get("tok", 0)); ws.append(pc)   # a space glyph goes between tokens, not pieces
        stats["words"] += wid + 1 if L else 0
        stats["split"] += sum(1 for w in ws if w["split"] and w["first"])
        stats["pieces"] += len(ws)
        stats["letters"] = stats.get("letters", 0) + sum(1 for w in ws if w.get("letter"))
        lim_top = max(1.0, ly1 - ly0) * u
        lim_bot = -((g["below"]["top"] - ly1) - gap) * u if g["below"] is not None else -1e9
        lh = max(1.0, ly1 - ly0)
        gaps = [ws[k + 1]["x0"] - ws[k]["x1"] for k in range(len(ws) - 1)]
        if SIZE_MODE == "gap":
            # pdf.js (Firefox) infers spaces from the pen's jumps relative to
            # the font size: a jump under 0.102 x size is no space (words
            # merge) and one over 0.6 x size starts a new item, and items
            # come out in stream order, so a right-to-left line breaks into
            # halves that copy out swapped. Size each line so its widest
            # word gap stays inside that window. pdfium does not care.
            wgaps = [ws[k + 1]["x0"] - ws[k]["x1"] for k in range(len(ws) - 1) if ws[k + 1]["_wid"] != ws[k]["_wid"]]
            if wgaps:
                size_pt = min(SIZE_MAX, max(SIZE_PT, max(wgaps) * 72.0 / DPI / 0.55))
                km = 72.0 / (DPI * size_pt); tj = 1000.0 * km
        sp_w = float(round(max(1.0, min([g for g in gaps if g > 0] + [0.2 * lh])) * u))   # whole pixels: the glyph's advance and the pen must agree
        procs = {"sp": f"{sp_w:.0f} 0 0 0 0 0 d1\n"}; widths = [sp_w]; names = ["sp"]; tou = [(1, " ")]; shapes = {}
        bbox = [0, 0, 0, 0]
        for k, w in enumerate(ws[:253]):
            code = k + 2
            gx0 = min(p[:, 0].min() for b in w["blobs"] for p in b["paths"]); gx1 = max(p[:, 0].max() for b in w["blobs"] for p in b["paths"])
            gy0 = min(p[:, 1].min() for b in w["blobs"] for p in b["paths"]); gy1 = max(p[:, 1].max() for b in w["blobs"] for p in b["paths"])
            if w.get("cell"):
                # A pen-path letter: origin and advance are its stretch of the baseline; its ink may reach outside
                # (a kaf's arm over the next letter), as a typeset glyph's does.
                gx0, gx1 = w["cell"]
            adv = (gx1 - gx0) * u
            # Inside a word, a piece's advance runs up to the next piece, so
            # no pen adjustment is needed between them: pdfium turns a kerning
            # adjustment after a narrow glyph into a generated space, which
            # copied `الحكم` out as `ا لحكم` and `362` as `3 6 2`.
            if k + 1 < len(ws) and ws[k + 1]["_wid"] == w["_wid"]:
                nxt = ws[k + 1]["cell"][0] if ws[k + 1].get("cell") else min(p[:, 0].min() for b in ws[k + 1]["blobs"] for p in b["paths"])
                adv = max(adv, (nxt - gx0) * u)
            cmds = []
            for b in w["blobs"]:
                for p in b["paths"]:
                    pts = [((px - gx0) * u, (ly1 - py) * u) for px, py in p]
                    cmds.append(f"{pts[0][0]:.0f} {pts[0][1]:.0f} m " + " ".join(f"{x:.0f} {y:.0f} l" for x, y in pts[1:]) + " h")
            by0, by1 = (ly1 - gy1) * u, (ly1 - gy0) * u
            # Clip the declared box at the neighbouring lines, but never to
            # nothing: a glyph lying wholly past the clip (a superscript, a
            # lone mark) would declare an inverted box, and pdfium then drops
            # it and mis-splits the line. Keep at least 30% of its height.
            keep = 0.3 * max(1.0, by1 - by0)
            dy1 = max(min(by1, lim_top), by0 + keep)
            dy0 = min(max(by0, min(lim_bot, 0.0)), dy1 - keep)
            procs[f"g{code}"] = f"{adv:.0f} 0 0 {dy0:.0f} {adv:.0f} {dy1:.0f} d1\n" + "\n".join(cmds) + "\nf*\n"
            shapes[f"g{code}"] = w.get("shapes")
            widths.append(adv); names.append(f"g{code}"); tou.append((code, visual(w["text"].strip() or w["az"], rtl_line, ltr_line)))
            bbox = [0, min(bbox[1], dy0), max(bbox[2], adv), max(bbox[3], dy1)]
            w["_gx0"], w["_adv"] = gx0, adv
            glyphs += 1
        # pdfium drops a text object as a duplicate (fake bold) when one of
        # the five objects before it has the same number of items with the
        # same char codes and lies within a fraction of a line of it. Two
        # runs with the same word count have identical codes here, so a
        # whole body line vanished (0005, page 4). The closing space glyph
        # therefore has six spellings, chosen by line number.
        end_code = 1
        if li % 6:
            # codes are positional (Differences from 1), so the closing
            # glyph's CODE must differ: pad with unused copies of the space
            for v in range(li % 6):
                nm = f"sp{v}"; procs[nm] = procs["sp"]; names.append(nm); widths.append(sp_w); tou.append((len(names), " "))
            end_code = len(names)
        cp = {}
        for nm, body in procs.items():
            x = doc.get_new_xref()
            # /InkShapes: the document-alphabet ids of the blobs this glyph is
            # made of (right to left). Knowledge about the ink, not a drawing
            # shortcut — the outline is always this occurrence's own.
            ids = shapes.get(nm)
            doc.update_object(x, "<< /InkShapes [%s] >>" % " ".join(str(i) for i in ids) if ids else "<< >>")
            doc.update_stream(x, body.encode()); cp[nm] = x
        tu = doc.get_new_xref(); doc.update_object(tu, "<< >>")
        doc.update_stream(tu, ("/CIDInit /ProcSet findresource begin 12 dict begin begincmap /CMapName /T3-UCS def /CMapType 2 def\n"
            "1 begincodespacerange <00> <FF> endcodespacerange\n" + f"{len(tou)} beginbfchar\n"
            + "".join(f"<{c:02X}> <{hex16(s)}>\n" for c, s in tou)
            + "endbfchar\nendcmap CMapName currentdict /CMap defineresource pop end end").encode())
        fx = doc.get_new_xref()
        doc.update_object(fx, "<< /Type /Font /Subtype /Type3 /FontBBox [%d %d %d %d] /FontMatrix [%.8f 0 0 %.8f 0 0] "
            "/CharProcs << %s >> /Encoding << /Type /Encoding /Differences [1 %s] >> /FirstChar 1 /LastChar %d /Widths [%s] "
            "/Resources << >> /ToUnicode %d 0 R >>" % (bbox[0], bbox[1] - 1, bbox[2] + 1, bbox[3] + 1, km, km,
            " ".join(f"/{nm} {x} 0 R" for nm, x in cp.items()), " ".join("/" + nm for nm in names), len(names),
            " ".join(f"{wd:.0f}" for wd in widths), tu))
        fname = f"T3{tag}L{li}"
        doc.xref_set_key(font_x, f"{font_p}{fname}", f"{fx} 0 R")
        origin = to_pdf(ws[0]["_gx0"], ly1)
        parts, pen = [], ws[0]["_gx0"]
        # Each run starts and ends with the space glyph (advance cancelled).
        # pdfium decides "new line or same line" from the y jump measured
        # against the WIDTH of the last glyph of one run and the first of the
        # next; a word-wide glyph made 15pt line pitch look like one line, and
        # pdfium then sorted equal-x runs among themselves — body lines came
        # out swapped in pairs. A narrow glyph at both ends restores the test.
        parts.append(f"<01> {sp_w * tj:.1f}")
        for k, w in enumerate(ws[:253]):
            if k and w["_wid"] != ws[k - 1]["_wid"]:
                back = (w["_gx0"] - pen) * u - sp_w                # pen travel after the space glyph
                if back < 0:
                    # The next word starts inside the previous one's ink (a
                    # kerned pair): a backwards move right after the space
                    # glyph loses the space in pdfium (`سبأ لم` copied out as
                    # `سبألم`). Move back before the space instead, so the
                    # space glyph ends exactly where the next word begins.
                    parts.append(f"{-back * tj:.1f} <01>")
                else:
                    parts.append(f"<01> {-back * tj:.1f}")
            elif k and abs((w["_gx0"] - pen) * u) >= 1:
                parts.append(f"{-((w['_gx0'] - pen) * u) * tj:.1f}")
            parts.append(f"<{k + 2:02X}>")
            pen = w["_gx0"] + w["_adv"] / u
        parts.append(f"<{end_code:02X}>")
        out.append(f"BT /{fname} {size_pt:.3f} Tf {tm} {origin.x:.2f} {origin.y:.2f} Tm [{' '.join(parts)}] TJ ET")
    out.append("Q")
    return "\n".join(out) + "\n", glyphs, stats


def stray_paths(stray, M, frame: "Frame | None" = None):
    frame = frame or Frame(0, 0, 0)
    def to_pdf(u, v):
        x, y = frame.to_page(u, v)
        return fitz.Point(x * 72 / DPI, y * 72 / DPI) * M
    cmds = ["q 0 g"]
    for bl in stray:
        for p in bl["paths"]:
            pts = [to_pdf(x, y) for x, y in p]
            cmds.append(f"{pts[0].x:.2f} {pts[0].y:.2f} m " + " ".join(f"{q.x:.2f} {q.y:.2f} l" for q in pts[1:]) + " h")
    cmds.append("f* Q")
    return "\n".join(cmds) + "\n"


def append_content(doc, pg, content: bytes):
    # Scanner content often leaves a page-level `cm` (e.g. a flipped 0.75
    # scale) without q/Q. Our text would inherit it and pdfium would read
    # every word mirrored, so wrap the existing streams in q … Q first.
    if not pg.is_wrapped:
        pg.wrap_contents()
    cx = doc.get_new_xref(); doc.update_object(cx, "<< >>"); doc.update_stream(cx, content)
    old = pg.get_contents()
    doc.xref_set_key(pg.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in old + [cx]) + "]")
