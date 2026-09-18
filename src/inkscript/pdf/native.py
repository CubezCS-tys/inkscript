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
    """True when the page's text is set in real fonts: a typeset page,
    already native text. Azure's invisible 'Dummy' layer may sit on top of
    it (the corpus has typeset journals that went through OCR anyway); the
    page is still native when the real fonts carry at least half as many
    words as that layer. A scan whose page carries a real font only for a
    digitally added stamp, folio or header is still a scan."""
    real, dummy = text_words(page)
    return real > 0 and real >= 0.5 * dummy


def text_words(page) -> tuple[int, int]:
    """(readable words in real fonts, words in Azure's Dummy layer). A font
    without a usable encoding extracts as symbol junk (`ΔϴϤϨΘϟ`); those
    words are not text anyone can search or copy and do not count."""
    import re
    good = re.compile(r"[\u0600-\u06FFA-Za-z0-9]")
    real = dummy = chars = goodc = 0
    for b in page.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for sp in l["spans"]:
                if sp["font"] == "Dummy":
                    dummy += len(sp["text"].split())
                else:
                    real += len(sp["text"].split())
                    t = sp["text"].replace(" ", ""); chars += len(t); goodc += len(good.findall(t))
    if chars and goodc < 0.5 * chars:                 # mostly symbols: a font with no usable encoding
        real = 0
    return real, dummy


def strip_text_objects(doc, page) -> int:
    """Remove Azure's invisible text objects from the page's content streams.
    When the page has only the 'Dummy' font every BT…ET block goes; when a
    real font shares the page, only blocks that select a Dummy font are cut,
    so a digitally added header keeps its text. Returns how many."""
    import re
    dummies = [f[4].encode() for f in page.get_fonts(full=True) if f[3] == "Dummy"]
    only_dummy = all(f[3] == "Dummy" for f in page.get_fonts())
    # A real font whose text extracts as symbol junk stays: on a typeset
    # page it IS the visible ink (stripping it blanked 41 pages). Our layer
    # goes on top with Azure's reading; the junk lines remain in the text
    # Chrome extracts, and the order check leaves them out.
    n = 0
    for xref in page.get_contents():
        raw = doc.xref_stream(xref)
        if raw is None or b"BT" not in raw:
            continue
        if only_dummy:
            new, k = re.subn(rb"BT\b.*?\bET\b", b"", raw, flags=re.S)
        else:
            k = 0
            def cut(m):
                nonlocal k
                if any(re.search(rb"/" + re.escape(d) + rb"\b", m.group(0)) for d in dummies):
                    k += 1; return b""
                return m.group(0)
            new = re.sub(rb"BT\b.*?\bET\b", cut, raw, flags=re.S)
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
            strip_text_objects(src, page)                 # Azure's layer over typeset text: the real fonts stay, the Dummy layer goes
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
            b["page"] = pn; b["shape"] = A.assign_and_release(b)
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
        n_lines = sum(1 for L in lines if any(w["blobs"] for w in L))
        content, glyphs, pstats = write_text_layer(src, page, M, lines, f"P{pn}", invisible=True, frame=frame)
        append_content(src, page, content.encode())
        n_blobs, n_stray = len(blobs), len(stray)
        placed_texts = [w["text"].strip() or w["az"] for L in lines for w in L if w["blobs"]]
        # Each line's words right to left by position: the reading order of
        # its Arabic words as the ink has them, which is what the line-order
        # check compares Chrome's text with. Azure's own word order is not
        # reliable on vowelled verse or table rows.
        run_texts = [" ".join(w["text"].strip() or w["az"] for w in sorted((w for w in L if w["blobs"]), key=lambda w: -w["x1"])) for L in lines]
        if vec is not None:
            vp = vec.new_page(width=page.rect.width, height=page.rect.height)
            Mv = ~vp.transformation_matrix
            vcontent, _, _ = write_text_layer(vec, vp, Mv, lines, f"P{pn}", invisible=False, frame=frame)
            append_content(vec, vp, (stray_paths(stray, Mv, frame) + vcontent).encode())
        del blobs, lines, stray, gray, pix                 # a page's ink is not needed once written
        import gc; gc.collect()
        report["pages"].append(dict(info, lines=n_lines,
                                    glyphs=glyphs, blobs=n_blobs, stray=n_stray, pieces=pstats, placed=placed_texts, runs=run_texts))
    out_dir.mkdir(parents=True, exist_ok=True)
    src.save(out_dir / f"{stem}.pdf", garbage=3, deflate=True); src.close()
    if len(A):
        for pr in A.protos:                                # export needs the outlines, not the rasters
            for k in ("fill", "edge", "dist"):
                pr.pop(k, None)
        to_json(A, out_dir / f"{stem}.shapes.json", placements)
        to_svg(A, out_dir / f"{stem}.alphabet.svg")
        to_sheet(A, out_dir / f"{stem}.alphabet.png")
        report["alphabet"] = dict(shapes=len(A), blobs=sum(A.counts),
                                  repeated=sum(c for c in A.counts if c > 1))
    if vec is not None:
        vec.save(out_dir / f"{stem}_vector.pdf", garbage=3, deflate=True); vec.close()
    return report
