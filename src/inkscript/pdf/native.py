"""Scanned PDF -> PDF whose text layer is the page's own ink (see type3.py),
page 1 carrying Gemini's words when a cached read exists, Azure's elsewhere.
Writes <stem>.pdf (scan + zero-opacity glyphs) and, with vector=True,
<stem>_vector.pdf (glyphs only, no image)."""
from __future__ import annotations
import json
from pathlib import Path
import numpy as np, fitz

from ..ocr.azure import load_azure
from ..ocr.align import page1_text
from ..text import fold_digits
from ..geometry.trace import page_blobs, DPI
from ..geometry.layout import layout_page
from .type3 import write_text_layer, stray_paths, append_content
from ..geometry.alphabet import Alphabet, prepare, to_json, to_svg, to_sheet

def build_document(stem, azure_dir, scan_pdf, gemini_md, out_dir, vector, min_exact):
    words, _, dims = load_azure(azure_dir / stem / f"{stem}.json")
    j = json.load(open(azure_dir / stem / f"{stem}.json")); ar = j.get("analyzeResult", j)
    az_pages = {p["pageNumber"]: p for p in ar["pages"]}
    src = fitz.open(scan_pdf)
    vec = fitz.open() if vector else None
    report = dict(doc=stem, pages=[])
    # One shape alphabet for the whole document. It labels the ink — every
    # glyph records which shapes it is made of — and is exported beside the
    # PDF as the document's typeface. It never replaces an outline: the
    # measured cost of drawing one occurrence with another's ink is a median
    # 15% of its pixels, six times the tracing error.
    A = Alphabet(); placements = []
    for pno in range(src.page_count):
        pn = pno + 1
        page = src[pno]
        pwords = [w for w in words if w["page"] == pn]
        info = dict(page=pn, words=len(pwords), text="azure")
        if pn == 1 and gemini_md and gemini_md.exists():
            texts, st = page1_text(pwords, fold_digits(gemini_md.read_text(encoding="utf-8")), min_exact)
            info["text"] = st["page1"]
        else:
            texts = None
        if texts is None:
            texts = [w["text"] for w in pwords]
        if not pwords or pn not in dims:
            report["pages"].append(dict(info, lines=0, glyphs=0)); continue
        pix = page.get_pixmap(dpi=DPI, colorspace=fitz.csGRAY)
        gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        W_in, H_in = dims[pn]
        blobs = page_blobs(gray)
        prepare(blobs)
        for b in blobs:
            b["page"] = pn; b["shape"] = A.assign(b)
        lines, stray = layout_page(pwords, texts, az_pages[pn].get("lines", []), blobs, pix.w / W_in, pix.h / H_in)
        for L in lines:
            for w in L:
                if w["blobs"]:
                    w["shapes"] = [b["shape"] for b in sorted(w["blobs"], key=lambda b: -b["x"])]
                    placements.append(dict(page=pn, text=w["text"].strip() or w["az"], shapes=w["shapes"],
                                           box=[int(w["x0"]), int(w["y0"]), int(w["x1"]), int(w["y1"])]))
        M = ~page.transformation_matrix
        content, glyphs, pstats = write_text_layer(src, page, M, lines, f"P{pn}", invisible=True)
        append_content(src, page, content.encode())
        if vec is not None:
            vp = vec.new_page(width=page.rect.width, height=page.rect.height)
            Mv = ~vp.transformation_matrix
            vcontent, _, _ = write_text_layer(vec, vp, Mv, lines, f"P{pn}", invisible=False)
            append_content(vec, vp, (stray_paths(stray, Mv) + vcontent).encode())
        report["pages"].append(dict(info, lines=sum(1 for L in lines if any(w["blobs"] for w in L)),
                                    glyphs=glyphs, blobs=len(blobs), stray=len(stray), pieces=pstats,
                                    placed=[w["text"].strip() or w["az"] for L in lines for w in L if w["blobs"]]))
    out_dir.mkdir(parents=True, exist_ok=True)
    src.save(out_dir / f"{stem}.pdf", garbage=3, deflate=True); src.close()
    if len(A):
        to_json(A, out_dir / f"{stem}.shapes.json", placements)
        to_svg(A, out_dir / f"{stem}.alphabet.svg")
        to_sheet(A, out_dir / f"{stem}.alphabet.png")
        report["alphabet"] = dict(shapes=len(A), blobs=sum(A.counts),
                                  repeated=sum(c for c in A.counts if c > 1))
    if vec is not None:
        vec.save(out_dir / f"{stem}_vector.pdf", garbage=3, deflate=True); vec.close()
    return report
