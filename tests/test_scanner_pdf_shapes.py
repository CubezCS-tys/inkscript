"""Scanner PDFs come in shapes that broke the writer once: pages inheriting
/Resources from the Pages tree (the page image vanished), and content
streams ending in an unbalanced `cm` (pdfium read every word mirrored)."""
import fitz, numpy as np, pytest
from inkscript.pdf.native import build_document
from inkscript.verify.engines import pdfium_words


def ink(pdf, pn=0):
    a = np.frombuffer(fitz.open(pdf)[pn].get_pixmap(dpi=40, colorspace=fitz.csGRAY).samples, np.uint8)
    return int((a < 128).sum())


def build(fixture, scan, out):
    r = build_document(fixture["stem"], fixture["azure_dir"], scan, fixture["gemini_md"], out, False, 0.6)
    v = pdfium_words(out / f"{fixture['stem']}.pdf", r, fixture["azure_dir"])
    return out / f"{fixture['stem']}.pdf", sum(x["intact"] for x in v) / sum(x["words"] for x in v)


def test_inherited_resources_keep_the_page_image(fixture, tmp_path):
    doc = fitz.open(fixture["scan"])
    pg = doc[0]
    res = doc.xref_get_key(pg.xref, "Resources")
    parent = int(doc.xref_get_key(pg.xref, "Parent")[1].split()[0])
    doc.xref_set_key(parent, "Resources", res[1] if res[0] == "xref" else res[1])
    doc.xref_set_key(pg.xref, "Resources", "null")
    scan = tmp_path / "inherited.pdf"; doc.save(scan)
    assert ink(scan) > 200
    pdf, intact = build(fixture, scan, tmp_path / "out")
    assert ink(pdf) > 0.9 * ink(scan)
    assert intact > 0.97


def test_unbalanced_cm_in_scanner_content(fixture, tmp_path):
    doc = fitz.open(fixture["scan"])
    pg = doc[0]
    xref = pg.get_contents()[-1]
    doc.update_stream(xref, doc.xref_stream(xref) + b"\n0.75 0 0 -0.75 0 792 cm\n")
    scan = tmp_path / "trailing_cm.pdf"; doc.save(scan)
    pdf, intact = build(fixture, scan, tmp_path / "out")
    assert intact > 0.97
    assert abs(ink(pdf) - ink(scan)) < 0.1 * ink(scan)
