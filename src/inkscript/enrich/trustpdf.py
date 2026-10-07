"""The trust marks inside a PDF, without touching what the faithful PDF draws (experiment 22).

    write(built_pdf, doc, marks, quotes, born_digital=()) -> <built stem>_trust.pdf
    check(built_pdf, trust_pdf) -> {...}

A copy of the built PDF gets one highlight annotation per flagged word: a pale amber box over the word whose
pop-up note says why (and Azure's confidence). All of them sit in one optional-content group, "Uncertain
words", so a viewer with a layers panel can switch them off; any viewer can hide annotations.

The copy is an *incremental update*: the original file's bytes come first, unchanged, and the annotations are
appended after them, so the faithful drawing is the same bytes, not merely the same look. `check` confirms it:
the original is a byte-for-byte prefix of the copy, and pdfium (the pinned build, Chrome's engine) gives the same
text and the same character boxes on every page.

Words corrected by `inkscript fix` (experiment 27) get a pale green highlight in a second layer, "Corrected
words", whose note names the verse and the judge.

Blocks where Azure's reading is less reliable as a whole (experiment 30: vowelled text, a handwritten page,
decorative lettering; trust.regions) get a thin dashed blue outline and their page one note saying what the mark
means, in a third layer, "Reading marks"; the words inside are flagged only for a specific reason.

Notes are in English and leave the word out: Chromium's note pop-up draws no Arabic (experiment 22, the word
came out blank). Pages left as they are because they are born-digital get no marks: their text in the PDF is the
publisher's, not Azure's.
"""
from __future__ import annotations

import hashlib
import shutil
from pathlib import Path

from .trust import REASONS, REGIONS, region_summary

AMBER = (1.0, 0.72, 0.18)
LAYER = "Uncertain words"
GREEN = (0.30, 0.78, 0.45)
FIXED_LAYER = "Corrected words"           # experiment 27: words corrected to a Quran verse after a judge on the ink
BLUE = (0.25, 0.45, 0.85)
REGION_LAYER = "Reading marks"            # experiment 30: vowelled / handwritten / decorative blocks, a note per page


def write(built: Path, doc: dict, marks: dict, quotes: list[dict], born_digital=()) -> tuple[Path, int]:
    import pymupdf
    built = Path(built)
    out = built.with_name(built.stem + "_trust.pdf")
    shutil.copyfile(built, out)
    verse_of = {}
    for qt in quotes:
        for k in qt["doc_words"]:
            verse_of[k] = f"{qt['sura']}:{qt['aya']}"
    pdf = pymupdf.open(str(out))
    oc = pdf.add_ocg(LAYER, on=True)
    oc_fixed = None
    n = 0
    for w in doc["words"]:
        m = marks.get(w["idx"])
        if m is None or m.mark not in ("flagged", "corrected") or w["page"] in born_digital or w["page"] > pdf.page_count:
            continue
        pg = pdf[w["page"] - 1]
        apg = doc["pages"][w["page"]]
        sx, sy = pg.rect.width / apg["w"], pg.rect.height / apg["h"]       # scan pixels -> page points
        p = w["poly"]
        pts = [pymupdf.Point(p[i] * sx, p[i + 1] * sy) for i in range(0, 8, 2)]
        # Azure's polygon runs clockwise from the top-left corner; a quad wants ul, ur, ll, lr
        a = pg.add_highlight_annot(pymupdf.Quad(pts[0], pts[1], pts[3], pts[2]))
        if m.mark == "corrected":
            if oc_fixed is None:
                oc_fixed = pdf.add_ocg(FIXED_LAYER, on=True)
            a.set_colors(stroke=GREEN)
            a.set_opacity(0.35)
            judge = (w.get("corrected") or {}).get("judge") or "a judge"
            ref = (m.source or "").replace("quran ", "")
            a.set_info(title="inkscript · corrected word",
                       content=f"Corrected to the Quran verse {ref} (tanzil.net): looking at the scan, {judge} picked the "
                               "verse's word over Azure's reading, blind. Azure's reading is kept in the ALTO file.",
                       subject="corrected word")
            a.set_oc(oc_fixed)
            a.update()
            n += 1
            continue
        a.set_colors(stroke=AMBER)
        a.set_opacity(0.45)
        why = "; ".join(REASONS[r][0] for r in m.why)
        if "quran" in m.why and w["idx"] in verse_of:
            why += f" (Quran {verse_of[w['idx']]}, tanzil.net)"
        conf = f" (Azure's confidence {w['conf']:.2f})" if w["conf"] is not None else ""
        a.set_info(title="inkscript · uncertain word", content=why[:1].upper() + why[1:] + conf,
                   subject="uncertain word")
        a.set_oc(oc)
        a.update()
        n += 1
    n += _region_marks(pdf, doc, marks, born_digital)
    pdf.save(str(out), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    pdf.close()
    return out, n


def _region_marks(pdf, doc: dict, marks: dict, born_digital=()) -> int:
    """Experiment 30: each block marked vowelled / handwritten / decorative gets a thin dashed blue outline, and its
    page one note (top corner, in English) saying what the mark means; both in the layer "Reading marks"."""
    import pymupdf
    reg = region_summary(doc, marks)
    if not reg:
        return 0
    W = doc["words"]
    oc = pdf.add_ocg(REGION_LAYER, on=True)
    per_page = {}
    n = 0
    for m, e in reg.items():
        for i in e["blocks"]:
            p = doc["paras"][i]
            for pg in sorted({W[k]["page"] for k in p["words"]}):
                if pg in born_digital or pg > pdf.page_count:
                    continue
                ws = [W[k] for k in p["words"] if W[k]["page"] == pg]
                page = pdf[pg - 1]
                apg = doc["pages"][pg]
                sx, sy = page.rect.width / apg["w"], page.rect.height / apg["h"]
                x0, y0 = min(w["box"][0] for w in ws), min(w["box"][1] for w in ws)
                x1, y1 = max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)
                r = pymupdf.Rect(x0 * sx - 2, y0 * sy - 2, x1 * sx + 2, y1 * sy + 2)
                a = page.add_rect_annot(r)
                a.set_colors(stroke=BLUE)
                a.set_border(width=0.6, dashes=[2, 2])
                a.set_opacity(0.6)
                a.set_info(title="inkscript · " + REGIONS[m][0], content=REGIONS[m][1], subject=REGIONS[m][0])
                a.set_oc(oc)
                a.update()
                n += 1
                d = per_page.setdefault(pg, {})
                d[m] = d.get(m, 0) + 1
    hw = (doc.get("regions") or {}).get("pages") or {}
    for pg, d in sorted(per_page.items()):
        page = pdf[pg - 1]
        lines = []
        for m, c in d.items():
            if m == "handwritten" and pg in hw:
                lines.append(f"Handwritten page. {REGIONS[m][1]}")
            else:
                lines.append(f"{REGIONS[m][0][:1].upper() + REGIONS[m][0][1:]} in {c} block(s) on this page, outlined "
                             f"in blue. {REGIONS[m][1]}")
        a = page.add_text_annot(pymupdf.Point(page.rect.width - 24, 12), "\n\n".join(lines), icon="Note")
        a.set_info(title="inkscript · reading marks", subject="reading marks")
        a.set_colors(stroke=BLUE)
        a.set_oc(oc)
        a.update()
        n += 1
    return n


def check(built: Path, trust: Path) -> dict:
    """Same bytes first, same text and character boxes in pdfium on every page, /Direction /R2L kept."""
    import pymupdf
    import pypdfium2 as pdfium
    a, b = Path(built).read_bytes(), Path(trust).read_bytes()
    res = dict(prefix_identical=b[:len(a)] == a, original_bytes=len(a), trust_bytes=len(b),
               original_sha256=hashlib.sha256(a).hexdigest())
    da, db = pdfium.PdfDocument(str(built)), pdfium.PdfDocument(str(trust))
    same_text = same_boxes = chars = 0
    try:
        for i in range(len(da)):
            ta, tb = da[i].get_textpage(), db[i].get_textpage()
            same_text += ta.get_text_range() == tb.get_text_range()
            na, nb = ta.count_chars(), tb.count_chars()
            chars += na
            same_boxes += na == nb and all(ta.get_charbox(k) == tb.get_charbox(k) for k in range(na))
        res.update(pages=len(da), pages_same_text=same_text, pages_same_char_boxes=same_boxes, chars=chars)
    finally:
        da.close()
        db.close()
    d = pymupdf.open(str(trust))
    res["annotations"] = sum(len(list(p.annots())) for p in d)
    res["direction_r2l_kept"] = "/R2L" in d.xref_object(d.pdf_catalog())
    d.close()
    res["ok"] = bool(res["prefix_identical"] and res["pages_same_text"] == res["pages"]
                     and res["pages_same_char_boxes"] == res["pages"])
    return res
