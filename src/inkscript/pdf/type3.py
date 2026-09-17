"""The page's own ink as a PDF font. One Type 3 font per line, one glyph per
word whose outline is that word's traced ink, mapped through ToUnicode to the
word's text; one text run per line.

Every rule below was found by testing against pdfium (Chrome), MuPDF and
poppler, with a LibreOffice-typeset Arabic PDF as the reference for "native":
see docs/pdf-writing-rules.md.
"""
from __future__ import annotations
import fitz

from ..text import RTL, visual

DPI = 300


SIZE_PT = 8.0


# Gap kept between the declared boxes of adjacent lines, as a fraction of the
# line's ink height. pdfium's line-break decision is a near-zero threshold on
# the gap: boxes that merely touch (under 1pt apart) were read as one line.
GAP_FRAC = 0.30


def hex16(s: str) -> str:
    return s.encode("utf-16-be").hex().upper()


def write_text_layer(doc, pg, M, lines, tag, invisible):
    """Type 3 font per line + one text run per line, appended as content."""
    res = doc.xref_get_key(pg.xref, "Resources")
    if res[0] == "xref":
        res_xref = int(res[1].split()[0])
    else:
        res_xref = doc.get_new_xref(); doc.update_object(res_xref, "<< >>")
        doc.xref_set_key(pg.xref, "Resources", f"{res_xref} 0 R")
    if doc.xref_get_key(res_xref, "Font")[0] == "null":
        doc.xref_set_key(res_xref, "Font", "<< >>")
    if invisible:
        gs = doc.get_new_xref(); doc.update_object(gs, "<< /Type /ExtGState /ca 0 /CA 0 >>")
        if doc.xref_get_key(res_xref, "ExtGState")[0] == "null":
            doc.xref_set_key(res_xref, "ExtGState", "<< >>")
        doc.xref_set_key(res_xref, f"ExtGState/GSinv{tag}", f"{gs} 0 R")
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
    geo.sort(key=lambda g: g["ly1"])
    to_pdf = lambda x, y: fitz.Point(x * 72 / DPI, y * 72 / DPI) * M
    glyphs = 0
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
        if li > 0:
            ly0 = max(ly0, geo[li - 1]["bot"] + gap)
        ws = sorted((w for w in L if w["blobs"]), key=lambda w: w["x0"])
        lim_top = max(1.0, ly1 - ly0) * u
        lim_bot = -((geo[li + 1]["top"] - ly1) - gap) * u if li + 1 < len(geo) else -1e9
        lh = max(1.0, ly1 - ly0)
        gaps = [ws[k + 1]["x0"] - ws[k]["x1"] for k in range(len(ws) - 1)]
        sp_w = float(round(max(1.0, min([g for g in gaps if g > 0] + [0.2 * lh])) * u))   # whole pixels: the glyph's advance and the pen must agree
        procs = {"sp": f"{sp_w:.0f} 0 0 0 0 0 d1\n"}; widths = [sp_w]; names = ["sp"]; tou = [(1, " ")]; shapes = {}
        bbox = [0, 0, 0, 0]
        for k, w in enumerate(ws[:253]):
            code = k + 2
            gx0 = min(p[:, 0].min() for b in w["blobs"] for p in b["paths"]); gx1 = max(p[:, 0].max() for b in w["blobs"] for p in b["paths"])
            gy0 = min(p[:, 1].min() for b in w["blobs"] for p in b["paths"]); gy1 = max(p[:, 1].max() for b in w["blobs"] for p in b["paths"])
            adv = (gx1 - gx0) * u
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
            widths.append(adv); names.append(f"g{code}"); tou.append((code, visual(w["text"].strip() or w["az"])))
            bbox = [0, min(bbox[1], dy0), max(bbox[2], adv), max(bbox[3], dy1)]
            w["_gx0"], w["_adv"] = gx0, adv
            glyphs += 1
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
        doc.xref_set_key(res_xref, f"Font/{fname}", f"{fx} 0 R")
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
            if k:
                parts.append(f"<01> {-((w['_gx0'] - pen) * u - sp_w) * tj:.1f}")
            parts.append(f"<{k + 2:02X}>")
            pen = w["_gx0"] + w["_adv"] / u
        parts.append("<01>")
        out.append(f"BT /{fname} {size_pt:.3f} Tf 1 0 0 1 {origin.x:.2f} {origin.y:.2f} Tm [{' '.join(parts)}] TJ ET")
    out.append("Q")
    return "\n".join(out) + "\n", glyphs


def stray_paths(stray, M):
    to_pdf = lambda x, y: fitz.Point(x * 72 / DPI, y * 72 / DPI) * M
    cmds = ["q 0 g"]
    for bl in stray:
        for p in bl["paths"]:
            pts = [to_pdf(x, y) for x, y in p]
            cmds.append(f"{pts[0].x:.2f} {pts[0].y:.2f} m " + " ".join(f"{q.x:.2f} {q.y:.2f} l" for q in pts[1:]) + " h")
    cmds.append("f* Q")
    return "\n".join(cmds) + "\n"


def append_content(doc, pg, content: bytes):
    cx = doc.get_new_xref(); doc.update_object(cx, "<< >>"); doc.update_stream(cx, content)
    old = pg.get_contents()
    doc.xref_set_key(pg.xref, "Contents", "[" + " ".join(f"{x} 0 R" for x in old + [cx]) + "]")
