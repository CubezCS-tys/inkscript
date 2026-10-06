"""The enrich step: Quran matching, the trust flag, and the fixture end to end with --xml --trust.

The end-to-end test builds the bundled document with `inkscript native --vector --verify --xml --trust` and
checks that both XML files validate against the official schemas (JATS 1.4 Archiving DTD, ALTO 4.4 XSD; fetched
once into ~/.cache/inkscript/schemas, skipped without network) and that the trust PDFs read in pdfium exactly
as the faithful ones: 1,246/1,246 words intact, 113/113 lines in order, the original bytes a prefix.
"""
import json
import re

import pytest

from inkscript.enrich.document import load
from inkscript.enrich.quran import check_document, norm, noalef, quran, skel
from inkscript.enrich.trust import assess, reasons


# ---------------------------------------------------------------- a small Azure reading, written to disk

def azure_json(tmp_path, lines, conf=None, page=(8.5, 11.0)):
    """An Azure prebuilt-read JSON: one page, one paragraph per line, each word 0.5 in wide on its line."""
    content, words, alines, paras = "", [], [], []
    conf = conf or {}
    for li, text in enumerate(lines):
        if content:
            content += "\n"
        start = len(content)
        y = 1.0 + li * 0.4
        for k, t in enumerate(text.split()):
            if k:
                content += " "
            x = page[0] - 1.0 - k * 0.6
            words.append(dict(content=t, span=dict(offset=len(content), length=len(t)),
                              confidence=conf.get(t, 0.99),
                              polygon=[x - 0.5, y, x, y, x, y + 0.25, x - 0.5, y + 0.25]))
            content += t
        span = dict(offset=start, length=len(content) - start)
        alines.append(dict(content=text, spans=[span]))
        paras.append(dict(content=text, spans=[span],
                          boundingRegions=[dict(pageNumber=1, polygon=[1, y, 7.5, y, 7.5, y + 0.3, 1, y + 0.3])]))
    j = dict(analyzeResult=dict(content=content, modelId="prebuilt-read", apiVersion="test",
                                pages=[dict(pageNumber=1, width=page[0], height=page[1], unit="inch", angle=0,
                                            words=words, lines=alines)], paragraphs=paras))
    p = tmp_path / "doc.json"
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return p


# ---------------------------------------------------------------- Quran

def test_tanzil_text_ships_whole():
    q = quran()
    assert len(q.verse_text) == 6236 and len(q.sura_name) == 114
    assert q.sura_name[1] == "الفاتحة"


def test_normalisation_keys():
    assert norm("الرَّحْمَٰنِ") == "الرحمن"
    assert norm("إِيَّاكَ") == "اياك" and norm("ٱلْكِتَٰبُ") == "الكتب"
    assert noalef(norm("العالمين")) == noalef(norm("العلمين"))        # Uthmani spelling matches on noalef
    assert skel(norm("الرجيم")) == skel(norm("الرحيم"))              # differ by dots only


def test_quotation_found_and_cited(tmp_path):
    doc = load(azure_json(tmp_path, ["قال تعالى ﴿ الحمد لله رب العالمين الرحمن الرحيم ﴾ (الفاتحة: 2)"]))
    qs = check_document(doc)
    assert len(qs) == 1
    q = qs[0]
    assert (q["sura"], q["aya"], q["aya_end"]) == (1, 2, 3) and q["differs"] == 0
    assert q["citation_agrees"] is True
    assert "تعالى" not in [doc["words"][k]["text"] for k in q["doc_words"]]


def test_misread_word_is_a_difference(tmp_path):
    # Azure-style misreading: يوم الدبن for يوم الدين (dots), inside the brackets
    doc = load(azure_json(tmp_path, ["﴿ الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدبن ﴾"]))
    q = check_document(doc)[0]
    assert (q["sura"], q["aya"], q["aya_end"]) == (1, 2, 4)
    diffs = [o for o in q["ops"] if o.get("verdict")]
    assert len(diffs) == 1 and diffs[0]["kind"] == "dots"
    assert doc["words"][diffs[0]["doc"][0]]["text"] == "الدبن"


def test_uthmani_spelling_matches(tmp_path):
    doc = load(azure_json(tmp_path, ["﴿ الحمد لله رب العلمين ﴾"]))
    q = check_document(doc)
    assert q and q[0]["differs"] == 0


def test_prose_is_not_a_quotation(tmp_path):
    doc = load(azure_json(tmp_path, ["قال الله في كتابه وهو أعلم بما يقول في هذا الباب"]))
    assert check_document(doc) == []


# ---------------------------------------------------------------- the trust flag

def sig(**kw):
    s = dict(conf=0.99, h_rel=1.0, w_rel=1.0, line_n=10, latin=False, arabic_page=True, persian=False, ink=0.15,
             quran=(None, None))
    s.update(kw)
    return s


def test_flag_reasons():
    assert reasons(sig()) == []
    assert reasons(sig(conf=0.79)) == ["conf"]
    assert reasons(sig(conf=0.80)) == []
    assert reasons(sig(h_rel=0.5, line_n=1, conf=0.9)) == ["speck"]
    assert reasons(sig(h_rel=0.5, line_n=1, conf=0.99)) == []          # Azure very sure: a page number, say
    assert reasons(sig(h_rel=0.2)) == ["speck"]                          # tiny: always
    assert reasons(sig(h_rel=3.0, line_n=1, conf=0.9)) == ["ornament"]
    assert reasons(sig(ink=0.5, line_n=2, conf=0.9)) == ["ornament"]
    assert reasons(sig(latin=True, conf=0.9)) == ["latin"]
    assert reasons(sig(latin=True, conf=0.9, arabic_page=False)) == []
    assert reasons(sig(persian=True)) == ["persian"]
    assert reasons(sig(quran=("dots", "الدين"))) == ["quran"]


def test_marks_on_a_page(tmp_path):
    doc = load(azure_json(tmp_path, ["﴿ الحمد لله رب العالمين ﴾", "كلمة مشكوك فيها هنا"],
                          conf={"العالمين": 0.5, "مشكوك": 0.5}))
    marks = assess(doc, check_document(doc))
    by = {doc["words"][k]["text"]: m for k, m in marks.items()}
    assert by["العالمين"].mark == "verified"          # the verse agrees: outweighs a low confidence
    assert by["مشكوك"].mark == "flagged" and by["مشكوك"].why == ["conf"]
    assert by["كلمة"].mark == "agreed"
    assert "﴿" not in by                               # punctuation alone is not assessed


# ---------------------------------------------------------------- the fixture end to end

@pytest.fixture(scope="module")
def enriched(fixture, tmp_path_factory):
    from inkscript.cli import main
    out = tmp_path_factory.mktemp("enrich")
    fx = fixture["azure_dir"].parent
    rc = main(["native", "--azure-dir", str(fixture["azure_dir"]), "--scan-dir", str(fx / "input"),
               "--frontpage-dir", str(fx / "frontpage"), "--out", str(out), "--vector", "--verify", "--xml", "--trust"])
    assert rc == 0
    rep = json.loads((out / "native_pdf_report.json").read_text(encoding="utf-8"))[0]
    return out, rep


def test_flags_off_by_default(monkeypatch):
    import inkscript.cli as cli
    seen = {}
    monkeypatch.setattr(cli, "cmd_native", lambda a: seen.update(vars(a)) or 0)
    cli.main(["native", "--azure-dir", "x", "--out", "y"])
    assert seen["xml"] is False and seen["trust"] is False


def test_both_xml_files_validate(enriched, fixture):
    from inkscript.enrich import schemas
    out, rep = enriched
    try:
        schemas.jats_dtd(), schemas.alto_xsd()
    except Exception as e:                      # first run without network
        pytest.skip(f"schemas not available: {e}")
    assert schemas.validate_jats(out / f"{fixture['stem']}.jats.xml") == []
    assert schemas.validate_alto(out / f"{fixture['stem']}.alto.xml") == []
    assert rep["enrich"]["jats"]["valid"] and rep["enrich"]["alto"]["valid"]


def test_xml_ids_link_up(enriched, fixture):
    from lxml import etree
    out, rep = enriched
    stem = fixture["stem"]
    jats = etree.parse(str(out / f"{stem}.jats.xml"))
    alto = etree.parse(str(out / f"{stem}.alto.xml"))
    ns = {"a": "http://www.loc.gov/standards/alto/ns-v4#"}
    jids = set(jats.xpath("//@id"))
    xl = "{http://www.w3.org/1999/xlink}href"
    blocks = alto.xpath("//a:TextBlock", namespaces=ns)
    words = alto.xpath("//a:String/@ID", namespaces=ns)
    assert len(words) == len(set(words)) == 1431
    # every block of article text points at its element of the JATS file; running heads and page numbers are
    # not article text and point nowhere
    for b in blocks:
        if b.get("TAGREFS") in ("role.pageNumber", "role.pageHeader", "role.pageFooter"):
            assert b.get(xl) is None
        else:
            assert b.get(xl) and b.get(xl).split("#")[1] in jids, b.get("ID")
    sj = json.loads((out / f"{stem}.shapes.json").read_text(encoding="utf-8"))
    with_word = [p for p in sj["placements"] if "word" in p]
    assert len(with_word) >= 0.99 * len(sj["placements"]) and all(p["word"] in set(words) for p in with_word)
    # the JATS front matter of the fixture
    assert norm(jats.findtext(".//article-title")) == norm("كتاب السماء والعالم")
    assert jats.getroot().get("{http://www.w3.org/XML/1998/namespace}lang") == "ar"
    assert len(jats.xpath("//fn")) >= 10 and jats.xpath("//xref[@ref-type='fn']")


def test_trust_pdf_reads_like_the_faithful_one(enriched, fixture):
    from inkscript.verify.engines import pdfium_lines, pdfium_words
    from inkscript.enrich.trustpdf import check
    out, rep = enriched
    stem = fixture["stem"]
    flagged = rep["enrich"]["trust"]["flagged"]
    assert flagged == 37        # 62 under experiment 22's rule; 25 common words at conf >= 0.6 no longer flagged (experiment 27)
    for base in (f"{stem}.pdf", f"{stem}_vector.pdf"):
        t = out / base.replace(".pdf", "_trust.pdf")
        c = check(out / base, t)
        assert c["ok"] and c["prefix_identical"] and c["direction_r2l_kept"] and c["annotations"] == flagged
        v = pdfium_words(t, rep, fixture["azure_dir"])
        lines = pdfium_lines(t, rep)
        assert (sum(x["intact"] for x in v), sum(x["words"] for x in v)) == (1246, 1246)
        assert (sum(x["in_order"] for x in lines), sum(x["lines"] for x in lines)) == (113, 113)


def test_trust_layer_is_optional_content(enriched, fixture):
    import pymupdf
    out, _ = enriched
    d = pymupdf.open(str(out / f"{fixture['stem']}_trust.pdf"))
    assert [v["name"] for v in d.get_ocgs().values()] == ["Uncertain words"]
    page = d[0]
    a = next(iter(page.annots()))
    assert a.type[1] == "Highlight" and re.search(r"confidence|Gemini|speck|ornament", a.info["content"])
    d.close()
