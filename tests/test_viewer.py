"""`inkscript view` (experiment 31): the fixture built with --xml, then the viewer's data paths checked against the
XML files themselves — the words and boxes of a page, the article's words linked to the right ALTO words, notes
linked to their markers, the server's answers, and a static bundle."""
import json
import re
import threading
import urllib.error
import urllib.request

import pytest
from lxml import etree

from inkscript.viewer.outputs import Outputs, norm
from inkscript.viewer.serve import Data, export, make_handler

A = "{http://www.loc.gov/standards/alto/ns-v4#}"


@pytest.fixture(scope="module")
def built(fixture, tmp_path_factory):
    from inkscript.cli import main
    out = tmp_path_factory.mktemp("view") / "out"
    fx = fixture["azure_dir"].parent
    rc = main(["native", "--azure-dir", str(fixture["azure_dir"]), "--scan-dir", str(fx / "input"),
               "--frontpage-dir", str(fx / "frontpage"), "--out", str(out), "--xml"])
    assert rc == 0
    return out


@pytest.fixture(scope="module")
def data(built, tmp_path_factory):
    return Data(Outputs(built), dpi=40, cache=tmp_path_factory.mktemp("cache"))


def alto_strings(built, stem):
    root = etree.parse(str(built / f"{stem}.alto.xml")).getroot()
    return root, {s.get("ID"): s for s in root.iter(A + "String")}


def get(data, path):
    body, ctype = data.get(path)
    return json.loads(body) if ctype.startswith("application/json") else body


def test_index_row(data, built, fixture):
    stem = fixture["stem"]
    rows = get(data, "index.json")["docs"]
    row = next(r for r in rows if r["id"] == stem)
    _, strings = alto_strings(built, stem)
    assert row["pages"] == 5 and row["title"] and row["authors"]
    flagged = sum("trust.flagged" in (s.get("TAGREFS") or "") for s in strings.values())
    assert row["flagged"] == flagged > 0
    assert row["has_pdf"]


def test_page_words_are_the_alto_strings(data, built, fixture):
    stem = fixture["stem"]
    root, strings = alto_strings(built, stem)
    doc = get(data, f"{stem}/doc.json")
    assert [p["n"] for p in doc["page_list"]] == [1, 2, 3, 4, 5]
    assert "trust.flagged" in doc["tags"] and "why.conf" in doc["tags"]
    seen = 0
    for p in root.iter(A + "Page"):
        n = int(p.get("PHYSICAL_IMG_NR"))
        pd = get(data, f"{stem}/page-{n}.json")
        assert (pd["w"], pd["h"]) == (float(p.get("WIDTH")), float(p.get("HEIGHT")))
        words = [w for b in pd["blocks"] for ln in b["lines"] for w in ln["w"]]
        assert [w["id"] for w in words] == [s.get("ID") for s in p.iter(A + "String")]
        for w in words:
            s = strings[w["id"]]
            assert w["t"] == s.get("CONTENT")
            assert w["b"] == [int(s.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]
            tr = (s.get("TAGREFS") or "").split()
            assert ("trust." + w["m"]) in tr if "m" in w else not any(t.startswith("trust.") for t in tr)
            alts = [a.text for a in s.iter(A + "ALTERNATIVE")]
            assert [a[1] for a in w.get("alt", [])] == alts
        seen += len(words)
        for b in pd["blocks"]:                          # block roles as tagged
            tb = root.find(f".//{A}TextBlock[@ID='{b['id']}']")
            assert ("role." + b["role"]) == tb.get("TAGREFS").split()[0]
    assert seen == len(strings) > 1000
    p1 = [w for b in get(data, f"{stem}/page-1.json")["blocks"] for ln in b["lines"] for w in ln["w"]]
    assert sum("g" in w for w in p1) >= 0.9 * len(p1)            # each word's glyphs in shapes.json


def test_article_words_link_to_their_alto_words(data, built, fixture):
    stem = fixture["stem"]
    root, strings = alto_strings(built, stem)
    art = get(data, f"{stem}/article.json")
    h = etree.HTML(art["html"])
    spans = h.xpath("//span[@data-w]")
    assert art["linked"] == len(spans) and art["linked"] >= 0.97 * art["words"]
    for s in spans:                                     # each linked piece is (part of) that word
        assert norm(s.text) in norm(strings[s.get("data-w")].get("CONTENT")) or not norm(s.text)
    # every non-furniture block on the page has a place in the article
    blocks = {b.get("ID"): b.get("TAGREFS").split()[0] for b in root.iter(A + "TextBlock")}
    placed = {b for e in h.xpath("//*[@data-b]") for b in e.get("data-b").split()}
    body = [b for b, r in blocks.items() if r not in ("role.pageHeader", "role.pageFooter", "role.pageNumber")]
    assert set(placed) <= set(blocks)
    assert sum(b in placed for b in body) >= 0.95 * len(body)
    # the words of the article in reading order are the page's words in reading order
    order = list(strings)
    pos = [order.index(s.get("data-w")) for s in h.xpath("//div[@class='body']//span[@data-w]")]
    assert sum(b >= a for a, b in zip(pos, pos[1:])) >= 0.98 * (len(pos) - 1)


def test_article_notes_and_front(data, fixture):
    stem = fixture["stem"]
    h = etree.HTML(get(data, f"{stem}/article.json")["html"])
    refs = h.xpath("//a[@class='fnref']")
    assert refs, "the fixture's notes are linked from the text"
    ids = set(h.xpath("//@id"))
    for a in refs:
        assert "j-" + a.get("data-rid") in ids
    assert h.xpath("//h1[@class='title']")[0].get("data-words")
    assert h.xpath("//article")[0].get("dir") == "rtl"


def test_page_image_and_xml(data, fixture):
    stem = fixture["stem"]
    png = get(data, f"{stem}/page-2.png")
    assert png[:8] == b"\x89PNG\r\n\x1a\n"
    assert get(data, f"{stem}/page-2.png") == png      # second time from the cache
    assert get(data, f"{stem}/alto.xml").startswith(b"<?xml")
    assert b"<article" in get(data, f"{stem}/jats.xml")
    for bad in ("nope/doc.json", f"{stem}/page-9.json", f"{stem}/../x", "../../etc/passwd"):
        with pytest.raises(KeyError):
            data.get(bad)


def test_server_answers(data, fixture):
    from http.server import ThreadingHTTPServer
    stem = fixture["stem"]
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(data))
    threading.Thread(target=httpd.serve_forever, daemon=True).start()
    base = f"http://127.0.0.1:{httpd.server_address[1]}/"
    try:
        def fetch(p):
            with urllib.request.urlopen(base + p) as r:
                return r.status, r.headers["Content-Type"], r.read()
        st, ct, body = fetch("")
        assert st == 200 and b"app.js" in body and b"window.STATIC" not in body
        assert fetch("app.js")[0] == 200 and fetch("app.css")[0] == 200
        st, ct, body = fetch(f"data/{stem}/page-1.json")
        assert ct.startswith("application/json") and json.loads(body)["n"] == 1
        assert fetch(f"data/{stem}/page-1.png")[2][:4] == b"\x89PNG"
        for p in ("data/x/doc.json", "data/../../etc/passwd", "secret.txt"):
            with pytest.raises(urllib.error.HTTPError) as e:
                fetch(p)
            assert e.value.code == 404
    finally:
        httpd.shutdown()
        httpd.server_close()


def test_static_bundle(built, fixture, tmp_path, monkeypatch):
    from inkscript.cli import main
    monkeypatch.setenv("XDG_CACHE_HOME", str(tmp_path / "cache"))
    stem = fixture["stem"]
    dest = tmp_path / "bundle"
    assert main(["view", str(built), "--static", str(dest), "--doc", stem, "--dpi", "30"]) == 0
    assert "window.STATIC=true" in (dest / "index.html").read_text(encoding="utf-8")
    assert (dest / "app.js").exists() and (dest / "data" / stem / "page-5.png").exists()
    for f in ("index.json", f"{stem}/doc.json", f"{stem}/article.json", f"{stem}/page-3.json", f"{stem}/alto.xml"):
        js = (dest / "data" / (f + ".js")).read_text(encoding="utf-8")
        m = re.match(r'window\.__put\("([^"]+)",(.*)\);\n$', js, re.S)
        assert m and m[1] == f
        v = json.loads(m[2])
        if f.endswith(".xml"):
            assert v.startswith("<?xml")
    assert export.__doc__
