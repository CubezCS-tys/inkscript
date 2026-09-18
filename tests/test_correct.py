"""A corrected reading written into the finished PDF, without a rebuild."""
import json
import pypdfium2 as pdfium
from inkscript.pdf.native import build_document
from inkscript.pdf.correct import apply_corrections
from inkscript.pdf.inspect import page_glyphs


def test_correction_lands_in_chrome_and_nowhere_else(fixture, tmp_path):
    out = tmp_path / "native"
    build_document(fixture["stem"], fixture["azure_dir"], fixture["scan"], fixture["gemini_md"], out, False, 0.6)
    pdf = out / f"{fixture['stem']}.pdf"; shapes = json.loads((out / f"{fixture['stem']}.shapes.json").read_text(encoding="utf-8"))
    target = next(p for p in shapes["placements"] if p["page"] == 2 and len(p["text"]) >= 4 and p["text"].isalpha())
    before = pdfium.PdfDocument(str(pdf))[1].get_textpage().get_text_range()
    assert target["text"] in before
    done = apply_corrections(pdf, [dict(page=2, box=target["box"], text="تصحيح")], out / f"{fixture['stem']}.shapes.json")
    assert done[0]["applied"] and done[0]["was"] == target["text"]
    after = pdfium.PdfDocument(str(pdf))[1].get_textpage().get_text_range()
    assert "تصحيح" in after and after.count(target["text"]) == before.count(target["text"]) - 1
    assert len(after.split()) == len(before.split())                       # nothing else moved
    shapes2 = json.loads((out / f"{fixture['stem']}.shapes.json").read_text(encoding="utf-8"))
    assert any(p.get("corrected") and p["text"] == "تصحيح" for p in shapes2["placements"])
    assert (out / f"{fixture['stem']}.corrections.json").exists()


def test_page_glyphs_read_back_what_was_placed(fixture, tmp_path):
    import fitz
    out = tmp_path / "native"
    r = build_document(fixture["stem"], fixture["azure_dir"], fixture["scan"], fixture["gemini_md"], out, False, 0.6)
    doc = fitz.open(out / f"{fixture['stem']}.pdf")
    g = page_glyphs(doc, 1)
    assert len(g) == r["pages"][1]["glyphs"]
    assert all(x["paths"] and x["box"][2] > x["box"][0] for x in g)
