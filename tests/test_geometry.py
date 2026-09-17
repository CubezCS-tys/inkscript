"""Ink -> outlines: the traced polygons must reproduce the printed page."""
import fitz
from inkscript.geometry.trace import render_gray, page_blobs, render_from_outlines, fidelity


def test_outlines_reproduce_the_ink(fixture):
    page = fitz.open(fixture["scan"])[0]
    gray = render_gray(page)
    blobs = page_blobs(gray)
    assert 600 < len(blobs) < 900                       # 735 on this page
    assert fidelity(gray, render_from_outlines(blobs, gray.shape)) > 0.95


def test_holes_are_kept(fixture):
    page = fitz.open(fixture["scan"])[0]
    blobs = page_blobs(render_gray(page))
    assert any(1 in b["holes"] for b in blobs)          # counters of و and ه
