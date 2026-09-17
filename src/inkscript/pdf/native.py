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
from ..text import fold_digits, strip_markdown
from ..geometry.trace import page_blobs, DPI
from ..geometry.layout import layout_page
from .type3 import write_text_layer, stray_paths, append_content, Frame
from ..geometry.alphabet import Alphabet, prepare, to_json, to_svg, to_sheet

def born_digital(page) -> bool:
    """True when the page's text is set in real fonts rather than Azure's
    invisible 'Dummy' layer over a scan."""
    fonts = page.get_fonts()
    return any(f[3] != "Dummy" for f in fonts) and bool(page.get_text("text").strip())


def strip_text_objects(doc, page) -> int:
    """Remove every BT…ET block from the page's content streams. Returns how many."""
    import re
    n = 0
    for xref in page.get_contents():
        raw = doc.xref_stream(xref)
        if raw is None or b"BT" not in raw:
            continue
        new, k = re.subn(rb"BT\b.*?\bET\b", b"", raw, flags=re.S)
        if k:
            doc.update_stream(xref, new); n += k
    return n


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
        # A born-digital page (real embedded fonts: a modern journal typeset
        # in InDesign) already IS native text; its visible text must not be
        # touched and it needs no ink glyphs. Azure's searchable PDFs of
        # scans carry exactly one font, 'Dummy', for their invisible layer.
        if born_digital(page):
            report["pages"].append(dict(page=pn, words=sum(1 for w in words if w["page"] == pn), text="native-digital", lines=0, glyphs=0))
            if vec is not None:
                vec.insert_pdf(src, from_page=pno, to_page=pno)
            continue
        # The corpus PDFs are Azure's own searchable PDFs: strip that text
        # layer first, or the page carries two layers and every viewer reads
        # both. Redaction was not enough — MuPDF left 19 of 34 runs it could
        # not measure — so every text object is cut out of the content
        # streams directly; the image and any line art are untouched.
        strip_text_objects(src, page)
        pwords = [w for w in words if w["page"] == pn]
        info = dict(page=pn, words=len(pwords), text="azure")
        if pn == 1 and gemini_md and gemini_md.exists():
            texts, st = page1_text(pwords, fold_digits(strip_markdown(gemini_md.read_text(encoding="utf-8"))), min_exact)
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
        # Sideways pages (tables printed landscape; Azure's page angle ≈ ±90°):
        # turn the image and every box upright, lay out as usual, and let the
        # text matrix turn the glyphs back. Otherwise the "lines" run down
        # the page and the horizontal-line writer mis-spaces them.
        ang = az_pages[pn].get("angle") or 0.0
        rot = 90 if ang > 45 else -90 if ang < -45 else 0
        frame = Frame(rot, pix.w, pix.h)
        if rot:
            gray = np.ascontiguousarray(np.rot90(gray, 1 if rot == 90 else -1))
            def turn(b):
                x0, y0, x1, y1 = b["box"]
                if rot == 90:  u0, v0, u1, v1 = y0, W_in - x1, y1, W_in - x0
                else:          u0, v0, u1, v1 = H_in - y1, x0, H_in - y0, x1
                return dict(b, box=(u0, v0, u1, v1))
            pwords = [turn(w) for w in pwords]
            W_in, H_in = H_in, W_in
        info["rotated"] = rot
        blobs = page_blobs(gray)
        prepare(blobs)
        for b in blobs:
            b["page"] = pn; b["shape"] = A.assign(b)
        lines, stray = layout_page(pwords, texts, az_pages[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        for L in lines:
            for w in L:
                if w["blobs"]:
                    bs = sorted(w["blobs"], key=lambda b: -b["x"])
                    w["shapes"] = [b["shape"] for b in bs]
                    # The word's ink signature: its shape ids right to left, each
                    # small blob tagged by where it sits (above / on / below the
                    # word's middle) so that ب ن ي — same base, different dot
                    # placement — do not share a signature.
                    mid = (w["y0"] + w["y1"]) / 2; lh_w = max(1.0, w["y1"] - w["y0"])
                    tags = []
                    for b in bs:
                        pos = "m" if b["h"] >= 0.3 * lh_w else ("a" if b["cy"] < mid - 0.1 * lh_w else "b" if b["cy"] > mid + 0.1 * lh_w else "m")
                        tags.append(f"{b['shape']}{pos}")
                    placements.append(dict(page=pn, text=w["text"].strip() or w["az"], shapes=w["shapes"], sig="+".join(tags),
                                           box=[int(w["x0"]), int(w["y0"]), int(w["x1"]), int(w["y1"])], rot=rot))
        M = ~page.transformation_matrix
        content, glyphs, pstats = write_text_layer(src, page, M, lines, f"P{pn}", invisible=True, frame=frame)
        append_content(src, page, content.encode())
        if vec is not None:
            vp = vec.new_page(width=page.rect.width, height=page.rect.height)
            Mv = ~vp.transformation_matrix
            vcontent, _, _ = write_text_layer(vec, vp, Mv, lines, f"P{pn}", invisible=False, frame=frame)
            append_content(vec, vp, (stray_paths(stray, Mv, frame) + vcontent).encode())
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
