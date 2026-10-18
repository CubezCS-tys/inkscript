"""refs43: parsed references and note citations (prompt v3.2 candidate). The answer below is SIMULATED (hand-made;
no model was called): two reference entries (Arabic, English) and a note citing two works, with one field that is
not printed (dropped) and a «د.ت» year (dropped; the printed entry keeps it)."""
from __future__ import annotations

import sys
from pathlib import Path
from types import SimpleNamespace

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "41_azure_structure"))
import refs43  # noqa: E402

DOCTYPE = ('<!DOCTYPE article PUBLIC "-//NLM//DTD JATS (Z39.96) Journal Archiving and Interchange DTD with '
           'MathML3 v1.4 20241031//EN" "JATS-archivearticle1-4-mathml3.dtd">')

REF_AR = "الجابري، محمد عابد. تكوين العقل العربي. بيروت: مركز دراسات الوحدة العربية، ١٩٨٤."
REF_EN = "Buhl, M. L. The Goddesses of the Egyptian Tree Cult. JNES, Vol. 6, No. 2, 1947, pp. 80-94."
NOTE = ("٣- ابن خلدون، المقدمة، القاهرة، د.ت، ص ١٢٠؛ وانظر: حسين، طه. في الأدب الجاهلي، القاهرة، ١٩٢٧، ص ٥٥.")

SIMULATED_ANSWER = {   # SIMULATED: hand-made in the shape prompt v3.2 asks for
    "pages": [{"page": 5, "blocks": [
        {"type": "reference", "lines": ["5:1"], "parsed": [
            {"type": "book", "authors": [{"surname": "الجابري", "given": "محمد عابد"}], "year": "١٩٨٤",
             "title": "تكوين العقل العربي", "publisher": "مركز دراسات الوحدة العربية", "place": "بيروت",
             "lang": "ar"}]},
        {"type": "reference", "lines": ["5:2"], "parsed": [
            {"type": "journal", "authors": [{"surname": "Buhl", "given": "M. L."}], "year": "1947",
             "title": "The Goddesses of the Egyptian Tree Cult", "source": "JNES", "volume": "6", "issue": "2",
             "pages": "80-94", "doi": "10.1086/370859", "lang": "en"}]},        # the DOI is not printed: dropped
        {"type": "footnote", "lines": ["5:3"], "marker": "٣", "cites": [
            {"type": "book", "authors": [{"surname": "ابن خلدون"}], "title": "المقدمة", "place": "القاهرة",
             "year": "د.ت", "pages": "ص ١٢٠"},
            {"type": "book", "authors": [{"surname": "حسين", "given": "طه"}], "title": "في الأدب الجاهلي",
             "place": "القاهرة", "year": "١٩٢٧", "pages": "ص ٥٥"}]},
    ]}]}


def article():
    A = etree.fromstring(f"""<article xmlns:xlink="http://www.w3.org/1999/xlink"
 xmlns:mml="http://www.w3.org/1998/Math/MathML" article-type="research-article" dtd-version="1.4" xml:lang="ar">
<front><article-meta><title-group><article-title>عنوان</article-title></title-group></article-meta></front>
<body><p>نص<xref ref-type="fn" rid="fn-p5-1">٣</xref></p></body>
<back><fn-group><fn id="fn-p5-1"><label>٣</label><p id="p5b3"><target id="p5b3l1"/>{NOTE}</p></fn></fn-group>
<ref-list><ref id="r1"><mixed-citation id="p5b1"><target id="p5b1l1"/>{REF_AR}</mixed-citation></ref>
<ref id="r2"><mixed-citation id="p5b2"><target id="p5b2l1"/>{REF_EN}</mixed-citation></ref></ref-list></back>
</article>""")
    Mo = SimpleNamespace(a={"stem": "test"}, lang="ar", tl_of={"5:1": "p5b1l1", "5:2": "p5b2l1", "5:3": "p5b3l1"})
    return Mo, A


def test_parsed_refs_and_note_citations_valid(tmp_path):
    Mo, A = article()
    printed_before = ["".join(m.itertext()) for m in A.iter("mixed-citation")]
    st = refs43.add_parsed(Mo, A, answers=[SIMULATED_ANSWER])
    assert st["refs_parsed"] == 2 and st["refs_element_citations"] == 2
    assert st["refs_notes_citing"] == 1 and st["refs_note_citations"] == 2
    assert st["refs_dropped_not_printed_doi"] == 1
    assert st["refs_dropped_year_not_a_year"] == 1
    # the printed entries are untouched
    assert ["".join(m.itertext()) for m in A.iter("mixed-citation")] == printed_before
    r1 = A.find(".//ref[@id='r1']/element-citation")
    assert r1.get("publication-type") == "book"
    assert r1.findtext("person-group/name/surname") == "الجابري"
    assert r1.findtext("source") == "تكوين العقل العربي" and r1.findtext("publisher-loc") == "بيروت"
    r2 = A.find(".//ref[@id='r2']/element-citation")
    assert r2.get("{http://www.w3.org/XML/1998/namespace}lang") == "en"
    assert r2.findtext("article-title") == "The Goddesses of the Egyptian Tree Cult" and r2.findtext("source") == "JNES"
    assert (r2.findtext("fpage"), r2.findtext("lpage")) == ("80", "94") and r2.find("pub-id") is None
    note = A.findall(".//fn/p[@content-type='parsed-citations']/element-citation")
    assert [e.findtext("person-group/name/surname") for e in note] == ["ابن خلدون", "حسين"]
    assert note[0].find("year") is None and note[1].findtext("year") == "١٩٢٧"
    f = tmp_path / "t.jats.xml"
    f.write_bytes(etree.tostring(A, xml_declaration=True, encoding="UTF-8", doctype=DOCTYPE))
    from inkscript.enrich.schemas import validate_jats
    assert validate_jats(f) == []


def test_raw_dir_and_no_parts(tmp_path):
    import json
    Mo, A = article()
    Mo.a = {"stem": "x-1", "first": 5, "last": 5, "n": 1, "kind": "whole"}
    st = refs43.add_parsed(Mo, A, answers=[{"pages": [{"page": 5, "blocks": [
        {"type": "reference", "lines": ["5:1"]}]}]}])               # a v3.1 answer: nothing to add
    assert not st and A.find(".//element-citation") is None
    import structure as ST
    (x, y), = ST.chunks(Mo.a)
    (tmp_path / f"x-1_c{x:03d}-{y:03d}.json").write_text(json.dumps({"answer": SIMULATED_ANSWER}, ensure_ascii=False))
    assert refs43.add_parsed(Mo, A, raw_dir=tmp_path)["refs_parsed"] == 2


def test_edition_prints_each_reference_once(tmp_path):
    Mo, A = article()
    refs43.add_parsed(Mo, A, answers=[SIMULATED_ANSWER])
    from inkscript.edition import model
    body, notes, refs, verses = model.read_body(A)
    assert [n.kind for n in refs] == ["ref", "ref"]
    note = next(n for n in notes if n.id == "fn-p5-1")
    assert len(note.paras) == 1
