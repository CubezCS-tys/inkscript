"""The ink-glyph PDF, judged by Chrome's engine (pdfium)."""
import pytest
from inkscript.pdf.native import build_document
from inkscript.verify.engines import pdfium_words, pdfium_order


@pytest.fixture(scope="module")
def built(fixture, tmp_path_factory):
    out = tmp_path_factory.mktemp("native")
    r = build_document(fixture["stem"], fixture["azure_dir"], fixture["scan"], fixture["gemini_md"], out, True, 0.6)
    return out, r


def test_words_copy_out_intact(built, fixture):
    out, r = built
    v = pdfium_words(out / f"{fixture['stem']}.pdf", r, fixture["azure_dir"])
    tw, ti = sum(x["words"] for x in v), sum(x["intact"] for x in v)
    assert ti / tw > 0.97


def test_reading_order(built, fixture):
    out, _ = built
    inv, lines = pdfium_order(out / f"{fixture['stem']}.pdf")
    assert inv == 0 and lines > 100


def test_vector_page_draws_like_the_scan(built, fixture):
    import fitz, numpy as np
    from inkscript.geometry.trace import render_gray, fidelity
    out, _ = built
    scan = render_gray(fitz.open(fixture["scan"])[0])
    vec = render_gray(fitz.open(out / f"{fixture['stem']}_vector.pdf")[0])
    assert vec.shape == scan.shape
    assert fidelity(scan, vec) > 0.75                   # renderer anti-aliasing thins strokes; 0.8 typical
