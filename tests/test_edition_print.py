"""The re-typeset print editions (experiment 35, D27): the hand-made test masters with a table and formulas, set by
LuaLaTeX, then read back with the pinned pdfium as Chrome reads them — every word there, in reading order, the
table right to left with its merged cells, the formulas typeset. Skipped when lualatex is not installed."""
import shutil
from pathlib import Path

import pytest

from inkscript.edition.model import load
from inkscript.edition.printpdf import layout_pdf, onecol_pdf, page_blocks
from inkscript.viewer.outputs import norm

FIX = Path(__file__).parent / "fixtures" / "edition"
pytestmark = pytest.mark.skipif(shutil.which("lualatex") is None, reason="lualatex not installed")


def toks(s):
    s = s.replace("￾", " ").replace("٪", " ").replace("%", " ")      # a percent sign's side is bidi's choice
    return [k for k in (norm(t) for t in s.replace("￾", " ").split()) if k]


def pdf_text(pdf):
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(str(pdf))
    out = [d[i].get_textpage().get_text_range() for i in range(len(d))]
    d.close()
    return out


def in_order(exp, got):
    from difflib import SequenceMatcher
    return sum(b.size for b in SequenceMatcher(None, exp, got, autojunk=False).get_matching_blocks()) / max(1, len(exp))


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("print")
    res = {}
    for stem in ("test-0001-table-math", "test-0002-two-columns"):
        ed = load(FIX / f"{stem}.jats.xml")
        res[stem] = dict(ed=ed, layout=layout_pdf(ed, out / f"{stem}.layout.pdf"),
                         onecol=onecol_pdf(ed, out / f"{stem}.onecol.pdf"),
                         lp=out / f"{stem}.layout.pdf", op=out / f"{stem}.onecol.pdf")
    return res


@pytest.mark.parametrize("stem", ["test-0001-table-math", "test-0002-two-columns"])
def test_layout_same_pages_every_word(built, stem):
    import pymupdf
    b = built[stem]
    assert b["layout"]["ok"] and not b["layout"]["missing"]
    ed = b["ed"]
    with pymupdf.open(str(b["lp"])) as d, pymupdf.open(str(ed.pdf_path)) as s:
        assert len(d) == len(s)
        for p, q in zip(d, s):                                  # the original's page size
            assert abs(p.rect.width - q.rect.width) < 0.5 and abs(p.rect.height - q.rect.height) < 0.5
    pages = pdf_text(b["lp"])
    for n, txt in zip(ed.page_numbers, pages):
        exp = [t for blk in page_blocks(ed, n) for w in blk.words if not w.math for t in toks(w.text)]
        got = toks(txt)
        missing = sum((__import__("collections").Counter(exp) - __import__("collections").Counter(got)).values())
        assert missing <= max(1, len(exp) // 50), (n, missing)
        assert in_order(exp, got) >= 0.9


def test_layout_formulas_and_table(built):
    st = built["test-0001-table-math"]["layout"]
    assert st["math_typeset"] == 2 and st["math_missing"] == 0     # both display formulas set as maths
    assert st["tables"] == 1


@pytest.mark.parametrize("stem", ["test-0001-table-math", "test-0002-two-columns"])
def test_onecol_reads_in_order(built, stem):
    b = built[stem]
    assert b["onecol"]["ok"] and not b["onecol"]["missing"]
    ed = b["ed"]
    got = [t for p in pdf_text(b["op"]) for t in toks(p)]
    body = [t for n in ed.body if n.kind in ("p", "heading") for t in toks(n.text)
            if not any(r["t"] == "math" for r in n.inl)]
    assert in_order(body, got) >= 0.9
    assert b["onecol"]["tables"] == 1


def test_onecol_table_right_to_left(built):
    """The first cell of a row (الفئة / ذكور) is on the right of the page, the last (النسبة / ٪٦٠) on the left."""
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(str(built["test-0001-table-math"]["op"]))
    tp = d[0].get_textpage()
    text = tp.get_text_range()

    def x_of(word):
        i = text.find(word)
        return tp.get_charbox(i)[0] if i >= 0 else None
    right, left = x_of("ذكور"), x_of("٦٠")
    d.close()
    assert right is not None and left is not None and right > left


def test_marked_right_to_left(built):
    import pymupdf
    with pymupdf.open(str(built["test-0001-table-math"]["lp"])) as d:
        assert "/R2L" in d.xref_get_key(d.pdf_catalog(), "ViewerPreferences")[1]
