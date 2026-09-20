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

# Share of a page's junk glyphs that must be mapped before the page trusts
# its own fixed fonts instead of our layer. Off (> 1): on the 451-document
# sample two documents crossed 99.5% and their fixed fonts read back as
# nothing in pdfium (1400-008-004-005: 1 of 553 words on a page). The
# neutralised-junk path is the verified one; the switch waits for a
# verification of its own.
FIX_COVERAGE = 1.01
LETTERS = True
LEARN_FROM = 1500      # pieces the document's atlas is learned from
CUT_ALL = True        # cut every piece the pen path finds cuts for; the two witnesses' verdict is reported, not enforced:
                      # a wrong cut moves a highlight, exactly what the equal slices of an uncut piece do, while
                      # most rejected cuts were right (experiment 09, rejected45 sheet)                                        # letter-level pieces where the document agrees (geometry/letters.py)


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
    good = re.compile(r"[\u0600-\u06FF\uFB50-\uFDFF\uFE70-\uFEFFA-Za-z0-9]")   # Arabic incl. presentation forms (typeset fonts)
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


def _azure_lines(az_page, pw):
    """Azure's lines of a page as lists of its words (with x1 for ordering)."""
    if not az_page:
        return []
    out = []
    for l in az_page.get("lines", []):
        xs = l["polygon"][0::2]; ys = l["polygon"][1::2]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        inside = [dict(content=w["text"], x1=w["box"][2]) for w in pw
                  if x0 - 0.02 <= (w["box"][0] + w["box"][2]) / 2 <= x1 + 0.02 and y0 - 0.02 <= (w["box"][1] + w["box"][3]) / 2 <= y1 + 0.02]
        if inside:
            out.append(inside)
    return out


def neutralise_text(doc, page, fonts: set) -> int:
    """Wrap every text object that uses one of `fonts` (resource names) in a
    marked-content span whose /ActualText is a single space. Viewers keep
    drawing the glyphs — on a typeset page they are the visible ink — but
    pdfium, MuPDF and poppler extract the span's ActualText instead of the
    junk, so our layer is the page's only text. Returns objects wrapped."""
    import re
    n = 0
    for xref in page.get_contents():
        raw = doc.xref_stream(xref)
        if raw is None or b"BT" not in raw:
            continue
        k = 0
        def wrap(m):
            nonlocal k
            if any(re.search(rb"/" + re.escape(f.encode()) + rb"\s+[-\d.]+\s+Tf", m.group(0)) for f in fonts):
                k += 1; return b"/Span << /ActualText ( ) >> BDC\n" + m.group(0) + b"\nEMC"
            return m.group(0)
        new = re.sub(rb"BT\b.*?\bET\b", wrap, raw, flags=re.S)
        if k:
            doc.update_stream(xref, new); n += k
    return n


def build_document(stem, azure_dir, scan_pdf, gemini_md, out_dir, vector, min_exact):
    words, _, dims = load_azure(azure_dir / stem / f"{stem}.json")
    j = json.load(open(azure_dir / stem / f"{stem}.json")); ar = j.get("analyzeResult", j)
    az_pages = {p["pageNumber"]: p for p in ar["pages"]}
    src = fitz.open(scan_pdf)
    # Typeset pages whose fonts have no usable encoding get a ToUnicode built
    # from Azure's words (pdf/fontfix.py); such a page is then native text
    # and needs no ink layer. Votes are collected over the whole document.
    from collections import Counter, defaultdict
    from .fontfix import collect_votes, write_tounicode, junk_fonts
    votes = defaultdict(Counter); junk_pages = {}; junk_named = {}
    for pno in range(src.page_count):
        jf = junk_fonts(src, src[pno])
        if jf and text_words(src[pno])[0] == 0:
            junk_named[pno + 1] = set(jf)                              # resource names, before any ToUnicode is added
            junk_pages[pno + 1] = collect_votes(src, src[pno], [w for w in words if w["page"] == pno + 1], votes)["keys"]
    from .fontfix import coverage, settle
    if votes:
        settle(votes)
    mapping = write_tounicode(src, votes) if votes else {}
    # a page is native once (nearly) every junk glyph has its letter; a page
    # the votes could not cover keeps our ink layer over its junk text
    fixed_pages = {pn: coverage(keys, mapping) for pn, keys in junk_pages.items()} if mapping else {}
    # Measured on 0470: at 93-98% coverage the fixed fonts read back at 88%
    # of words in Chrome, our layer at 100%. So a page switches to its own
    # fonts only when practically every glyph is covered; otherwise it keeps
    # our layer and its junk text is neutralised (`neutralise_text`).
    fixed_pages = {pn: c for pn, c in fixed_pages.items() if c >= FIX_COVERAGE}
    if mapping:
        src = fitz.open("pdf", src.tobytes())                 # reopen: MuPDF caches the fonts' encodings
    vec = fitz.open() if vector else None
    report = dict(doc=stem, pages=[], fonts_fixed={str(k): len(v) for k, v in mapping.items()}, fixed_pages=sorted(fixed_pages))

    page1_cache = {}
    def page_texts(pn, pwords):
        """The words' texts for the layout: Gemini's on page 1 (aligned into Azure's boxes), Azure's elsewhere."""
        if pn == 1 and gemini_md and gemini_md.exists():
            if 1 not in page1_cache:
                page1_cache[1] = page1_text(pwords, fold_digits(strip_markdown(gemini_md.read_text(encoding="utf-8"))), min_exact)
            texts, st = page1_cache[1]
            if texts is not None:
                return texts, st
            return [w["text"] for w in pwords], st
        return [w["text"] for w in pwords], None

    def page_geometry(page, pn, pwords, texts):
        """Render, turn a sideways page upright, trace the ink, lay the words out. Used by both passes."""
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
        blobs = page_blobs(gray)
        lines, stray = layout_page(pwords, texts, az_pages[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        return dict(gray=gray, rot=rot, frame=frame, blobs=blobs, lines=lines, stray=stray)

    # First pass — letters inside connected runs (geometry/letters.py): align
    # every piece's letters to its ink, then learn what each letter-form
    # shows in this document and keep only the plans the document agrees
    # with. The geometry is computed twice; the plans are small.
    from ..geometry.letters import letters_of, line_geometry
    from ..geometry.penpath import verdict as letter_verdict, units_forms, plan as letter_plan, solve as solve_letters, accepted as letters_accepted, apply as apply_letters, finalize as finalize_letters
    import cv2
    from ..geometry.layout import split_word
    from ..text import MARKS, pieces as text_pieces, ARABIC_LETTER
    letter_plans = {}; letters_tried = 0
    if LETTERS:
        # The document's alphabet is learned from its first LEARN_FROM pieces (rounds over all of them at once);
        # every later piece is cut against that atlas and reduced to its letters' outlines straight away, so a
        # long document costs no more memory than a short one.
        live = []; atlas = None

        def learn():
            a = solve_letters([p for _, p, _ in live])
            for key_, p, word in live:
                letter_plans[key_] = finalize_letters(p, word)
            live.clear()
            return a

        for pno in range(src.page_count):
            pn = pno + 1
            if pn in fixed_pages or (pn not in junk_pages and born_digital(src[pno])):
                continue
            pwords = [w for w in words if w["page"] == pn]
            if not pwords or pn not in dims:
                continue
            texts, _ = page_texts(pn, pwords)
            G = page_geometry(src[pno], pn, pwords, texts)
            _, ink = cv2.threshold(G["gray"], 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
            for li, L in enumerate(G["lines"]):
                bl = [b for w in L if w["blobs"] for b in w["blobs"]]
                if not bl:
                    continue
                lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl))
                lg = line_geometry(ink, bl)
                for wi, w in enumerate(L):
                    if not w["blobs"] or MARKS.search(w["text"]):
                        continue
                    for k, pc in enumerate(split_word(w, lh)):
                        t = pc["text"].strip()
                        uf = units_forms(t)
                        letters_tried += bool(uf and len(uf[0]) >= 2)
                        p = letter_plan(uf[0], pc["blobs"], lg, uf[1]) if uf and len(uf[0]) >= 2 else None
                        if not p:
                            continue
                        word = pc["blobs"][0].get("word")
                        if atlas is None:
                            live.append(((pn, li, wi, k), p, word))
                            if len(live) >= LEARN_FROM:
                                atlas = learn()
                        else:
                            apply_letters(p, atlas); letter_plans[(pn, li, wi, k)] = finalize_letters(p, word)
        if atlas is None:
            atlas = learn()
        majority = atlas["ref"]; all_plans = list(letter_plans.values())
        kept = {}
        for (pn, li, wi, k), p in letter_plans.items():
            if CUT_ALL or p["verdict"] == "cut":
                kept.setdefault((pn, li, wi), {})[k] = p
        from collections import Counter
        report["letters_why"] = dict(Counter(letter_verdict(p) for p in all_plans), **{"no pen path": letters_tried - len(all_plans)})
        report["letters"] = dict(planned=len(letter_plans), accepted=sum(len(v) for v in kept.values()), letter_forms=len(majority))
        letter_plans = kept
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
        # a junk-font page counts as native only when its fonts were fixed
        # well enough; a partial fix must not make it look born-digital
        if (pn in fixed_pages) or (pn not in junk_pages and born_digital(page)):
            strip_text_objects(src, page)                 # Azure's layer over typeset text: the real fonts stay, the Dummy layer goes
            if pn not in fixed_pages:
                jf = set(junk_fonts(src, page))
                if jf:
                    neutralise_text(src, page, jf)         # a junk-encoded font beside real ones: its symbols leave the text
            info = dict(page=pn, words=sum(1 for w in words if w["page"] == pn), text="native-digital", lines=0, glyphs=0)
            if pn in fixed_pages:
                # fonts fixed from the OCR: verify the page's own text against Azure's words, like a layer of ours
                pw = [w for w in words if w["page"] == pn]
                info.update(text="native-fixed", placed=[w["text"] for w in pw],
                            runs=[" ".join(w["content"] for w in sorted(l_words, key=lambda w: -w["x1"]))
                                  for l_words in _azure_lines(az_pages.get(pn), pw)])
            report["pages"].append(info)
            if vec is not None:
                vec.insert_pdf(src, from_page=pno, to_page=pno)
            continue
        # The corpus PDFs are Azure's own searchable PDFs: strip that text
        # layer first, or the page carries two layers and every viewer reads
        # both. Redaction was not enough — MuPDF left 19 of 34 runs it could
        # not measure — so every text object is cut out of the content
        # streams directly; the image and any line art are untouched.
        strip_text_objects(src, page)
        jf = set(junk_fonts(src, page)) | set(junk_named.get(pn, ()))
        if jf:
            neutralise_text(src, page, jf)                 # symbol junk beside our layer would be a second text

        pwords = [w for w in words if w["page"] == pn]
        info = dict(page=pn, words=len(pwords), text="azure")
        texts, st = page_texts(pn, pwords)
        if st:
            info["text"] = st["page1"]
        if not pwords or pn not in dims:
            report["pages"].append(dict(info, lines=0, glyphs=0)); continue
        G = page_geometry(page, pn, pwords, texts)
        gray, rot, frame, blobs, lines, stray = G["gray"], G["rot"], G["frame"], G["blobs"], G["lines"], G["stray"]
        info["rotated"] = rot
        prepare(blobs)
        for b in blobs:
            b["page"] = pn; b["shape"] = A.assign_and_release(b)
        # Letters inside connected runs: the plans made in the first pass and
        # accepted by the document's own majority become letter pieces.
        for li, L in enumerate(lines):
            for wi, w in enumerate(L):
                lp = letter_plans.get((pn, li, wi))
                if lp:
                    w["letter_plans"] = lp
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
        del blobs, lines, stray, gray, G                   # a page's ink is not needed once written
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
