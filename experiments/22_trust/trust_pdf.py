"""The trust marks inside a PDF, without touching what the faithful PDF draws.

    .venv/bin/python trust_pdf.py BUILT_PDF TRUST_JSON AZURE_JSON REPORT_JSON   -> <BUILT_PDF stem>_trust.pdf

A copy of the built PDF gets one highlight annotation per flagged word: a pale amber box over the word whose pop-up
note says why it is flagged (and Azure's confidence). The annotations sit in one optional-content group,
"Uncertain words", so a viewer with a layers panel can switch them off; any viewer can hide annotations.

The copy is written as an *incremental update*: the original file's bytes come first, unchanged, and the annotations
are appended after them. So the faithful drawing is the same bytes, not merely the same look. Checked here:
  1. the first N bytes of the copy are the original file (N = its size);
  2. pdfium (the pinned build, Chrome's engine) gives the same text on every page, character for character, and the
     same character boxes;
  3. the build's own checks (words intact, lines in order) give the same numbers on both files.
"""
import hashlib
import json
import shutil
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
sys.path.insert(0, str(REPO / "src"))

AMBER = (1.0, 0.72, 0.18)
LABEL = {"conf": "Azure is unsure of this word", "speck": "a speck or stray mark read as a word",
         "ornament": "ornament, stamp or display type", "latin": "Latin word on an Arabic page",
         "persian": "Persian letter in an Arabic word", "quran": "differs from the Quran verse",
         "gemini": "Gemini reads it differently", "conf_old": "old print, Azure not sure", "hamza": "hamza the print may omit",
         "salla": "the ﷺ ligature", "supnum": "a note number may be lost"}


def make(built: Path, trust_json: Path, azure_json: Path) -> Path:
    import pymupdf
    out = built.with_name(built.stem + "_trust.pdf")
    shutil.copyfile(built, out)
    words = json.loads(trust_json.read_text(encoding="utf-8"))
    j = json.loads(azure_json.read_text(encoding="utf-8")); ar = j.get("analyzeResult", j)
    apages = {p["pageNumber"]: p for p in ar["pages"]}
    poly = {(p["pageNumber"], k): w["polygon"] for p in ar["pages"] for k, w in enumerate(p.get("words", []))}
    doc = pymupdf.open(str(out))
    oc = doc.add_ocg("Uncertain words", on=True)
    n = 0
    for w in words:
        if w["mark"] != "flagged":
            continue
        pg = doc[w["page"] - 1]; ap = apages[w["page"]]
        unit = 72.0 if ap.get("unit", "inch") == "inch" else 1.0
        sx = pg.rect.width / (ap["width"] * unit); sy = pg.rect.height / (ap["height"] * unit)
        p = poly[(w["page"], w["pi"])]
        pts = [pymupdf.Point(p[i] * unit * sx, p[i + 1] * unit * sy) for i in range(0, 8, 2)]
        # Azure's polygon runs clockwise from the top-left corner; a quad wants ul, ur, ll, lr
        q = pymupdf.Quad(pts[0], pts[1], pts[3], pts[2])
        a = pg.add_highlight_annot(q)
        a.set_colors(stroke=AMBER); a.set_opacity(0.45)
        why = "; ".join(LABEL.get(r, r) for r in w["why"])
        conf = f" (Azure's confidence {w['conf']:.2f})" if w.get("conf") is not None else ""
        alt = f". Azure reads «{w['text']}», Gemini «{w['gemini']}»" if w.get("gemini") else ""
        # Chromium's note pop-up draws no Arabic (checked: the word came out blank), so the reason is in plain words
        # and the word itself is left out; the word is under the highlight anyway.
        a.set_info(title="inkscript · uncertain word", content=f"{why[:1].upper() + why[1:]}{conf}{alt}", subject="uncertain word")
        a.set_oc(oc)
        a.update()
        n += 1
    doc.save(str(out), incremental=True, encryption=pymupdf.PDF_ENCRYPT_KEEP)
    doc.close()
    print(f"{out}: {n} highlight annotations")
    return out


def check(built: Path, trust: Path, report_json: Path, azure_dir: Path) -> dict:
    import pypdfium2 as pdfium
    from inkscript.verify.engines import pdfium_words, pdfium_lines
    a, b = built.read_bytes(), trust.read_bytes()
    res = dict(original_bytes=len(a), trust_bytes=len(b), prefix_identical=b[:len(a)] == a,
               original_sha256=hashlib.sha256(a).hexdigest())
    da, db = pdfium.PdfDocument(str(built)), pdfium.PdfDocument(str(trust))
    same_text = same_boxes = 0; chars = 0; annots = 0
    for i in range(len(da)):
        ta, tb = da[i].get_textpage(), db[i].get_textpage()
        same_text += ta.get_text_range() == tb.get_text_range()
        na, nb = ta.count_chars(), tb.count_chars(); chars += na
        same_boxes += na == nb and all(ta.get_charbox(k) == tb.get_charbox(k) for k in range(na))
        annots += len(list(db[i].get_objects())) - len(list(da[i].get_objects()))     # page objects: must be 0 (annotations are not page content)
    res.update(pages=len(da), pages_same_text=same_text, pages_same_char_boxes=same_boxes, chars=chars, extra_page_objects=annots)
    da.close(); db.close()
    rep = json.loads(report_json.read_text()); rep = rep[0] if isinstance(rep, list) else rep
    for name, f in (("original", built), ("trust", trust)):
        v = pdfium_words(f, rep, azure_dir); l = pdfium_lines(f, rep)
        res[name] = dict(words=sum(x["words"] for x in v), intact=sum(x["intact"] for x in v),
                         lines=sum(x["lines"] for x in l), in_order=sum(x["in_order"] for x in l))
    import pymupdf
    d = pymupdf.open(str(trust))
    res["annotations"] = sum(len(list(p.annots())) for p in d)
    res["direction_r2l_kept"] = "/R2L" in d.xref_object(d.pdf_catalog())
    d.close()
    return res


if __name__ == "__main__":
    built, tj, aj, rj = map(Path, sys.argv[1:5])
    t = make(built, tj, aj)
    r = check(built, t, rj, aj.parent.parent)
    print(json.dumps(r, indent=1))
    (HERE / "out" / (t.stem + "_check.json")).write_text(json.dumps(r, indent=1))
