"""Experiment 35: the reading HTML and the EPUB 3, written from the hand-made test masters (tables with merged cells,
MathML formulas, a footnote). Fast; epubcheck runs only when its jar is in ~/.cache/inkscript/epubcheck/."""
import json
import re
import subprocess
import zipfile
from pathlib import Path

import pytest
from lxml import etree

from inkscript.edition.epub import write_epub
from inkscript.edition.html import write_html
from inkscript.edition.model import load
from inkscript.viewer.outputs import norm

FX = Path(__file__).parent / "fixtures" / "edition"
IDS = ["test-0001-table-math", "test-0002-two-columns"]
XH = "{http://www.w3.org/1999/xhtml}"
MML = "{http://www.w3.org/1998/Math/MathML}"


@pytest.fixture(scope="module")
def built(tmp_path_factory):
    out = tmp_path_factory.mktemp("editions")
    res = {}
    for i in IDS:
        ed = load(FX / f"{i}.jats.xml")
        res[i] = (ed, write_html(ed, out), write_epub(ed, out))
    return out, res


def _article(html_path):
    """The <article> of the page: the renderer writes it as well-formed XHTML."""
    s = Path(html_path).read_text(encoding="utf-8")
    m = re.search(r"<article .*</article>", s, re.S)
    return etree.fromstring(m[0].encode())


@pytest.mark.parametrize("i", IDS)
def test_html_page(built, i):
    out, res = built
    ed, hs, _ = res[i]
    art = _article(hs["html"])
    assert art.get("dir") == "rtl" and art.get("lang") == "ar"
    # the scan: one image per page, every node with ink has its "original" button
    assert hs["pages"] == len(ed.pages) and all((out / i / "scan" / f"p{n}.jpg").exists() for n in ed.pages)
    with_ink = [n for n in ed.nodes() if n.blocks and (n.inl or n.kind in ("table", "formula"))]
    assert hs["originals"] >= len(with_ink)
    # tables: right to left, merged cells kept, cells in the master's (reading) order
    tables = art.findall(".//table")
    assert len(tables) == sum(n.kind == "table" for n in ed.body) >= 1
    for tb, n in zip(tables, [n for n in ed.body if n.kind == "table"]):
        assert tb.get("dir") == "rtl"
        cells = tb.findall(".//th") + tb.findall(".//td")
        want = [c for r in n.extra["rows"] for c in r["cells"]]
        assert len(cells) == len(want)
        got_order = ["".join(c.itertext()).strip() for r in tb.iter("tr") for c in r if c.tag in ("th", "td")]
        assert [norm(x) for x in got_order] == [norm("".join(x["s"] for x in c["inl"] if "s" in x)) for c in want]
        assert any(int(c.get("colspan", 1)) > 1 for c in cells) or any(int(c.get("rowspan", 1)) > 1 for c in cells)
    # formulas: MathML, with the LaTeX kept as an annotation
    maths = list(art.iter(MML + "math"))
    nf = sum(n.kind == "formula" for n in ed.body)
    assert sum(m.get("display") == "block" for m in maths) == nf
    assert any(m.get("display") == "inline" for m in maths)
    assert all(m.find(f"{MML}semantics/{MML}annotation") is not None for m in maths)
    # notes linked both ways
    for a in art.iter("a"):
        h = a.get("href") or ""
        if h.startswith("#"):
            assert art.find(f".//*[@id='{h[1:]}']") is not None, h
    assert art.findall(".//a[@class='fnref']") and art.findall(".//div[@class='note']")


def test_words_of_the_page_are_in_the_html(built):
    """Every word of a block the master places in the article is in the page (formula ink excepted: maths)."""
    _, res = built
    for i, (ed, hs, _) in res.items():
        text = " ".join(_article(hs["html"]).itertext())
        keys = {norm(w) for w in text.split()}
        joined = norm(text)
        missing = [w.text for w in ed.ink_words() if not w.math and norm(w.text) and norm(w.text) not in keys
                   and norm(w.text) not in joined]
        assert not missing, (i, missing[:10])


@pytest.mark.parametrize("i", IDS)
def test_epub_package(built, i):
    out, res = built
    ed, _, es = res[i]
    z = zipfile.ZipFile(es["epub"])
    assert z.namelist()[0] == "mimetype" and z.read("mimetype") == b"application/epub+zip"
    assert z.getinfo("mimetype").compress_type == zipfile.ZIP_STORED
    opf = etree.fromstring(z.read("OEBPS/package.opf"))
    ns = {"o": "http://www.idpf.org/2007/opf", "dc": "http://purl.org/dc/elements/1.1/"}
    assert opf.find("o:spine", ns).get("page-progression-direction") == "rtl"
    assert opf.find("o:metadata/dc:language", ns).text == "ar"
    item = opf.find("o:manifest/o:item[@id='text']", ns)
    assert "mathml" in (item.get("properties") or "")
    doc = etree.fromstring(z.read("OEBPS/text.xhtml"))
    assert doc.get("dir") == "rtl"
    asides = doc.findall(f".//{XH}aside")
    assert asides and all(a.get("{http://www.idpf.org/2007/ops}type") == "footnote" for a in asides)
    assert any(n.endswith(".woff") for n in z.namelist())


def test_epubcheck(built):
    jar = next(iter(sorted((Path.home() / ".cache/inkscript/epubcheck").glob("epubcheck-*/epubcheck.jar"))), None)
    if jar is None:
        pytest.skip("epubcheck jar not in ~/.cache/inkscript/epubcheck")
    try:
        subprocess.run(["java", "-version"], capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("no java")
    out, res = built
    for i, (_, _, es) in res.items():
        js = out / f"{i}.epubcheck.json"
        subprocess.run(["java", "-Xmx512m", "-jar", str(jar), es["epub"], "--json", str(js)], capture_output=True)
        msgs = json.loads(js.read_text())["messages"]
        bad = [m for m in msgs if m["severity"] in ("FATAL", "ERROR", "WARNING")]
        assert not bad, (i, bad[:3])
