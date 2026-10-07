"""The library catalogue as front matter (enrich/catalogue.py, experiment 29): a MARC record read into the index,
its title and names aligned to the ink (the honorific printed before a name kept as its prefix), the journal,
dates, pages, abstract and keywords written into valid JATS, and a record that does not fit its PDF said so."""
import pytest
from lxml import etree

from inkscript.enrich import catalogue, jats
from inkscript.enrich.document import load
from inkscript.enrich.structure import read_meta

from test_structure import azure, body_lines

MARC = """<?xml version="1.0" encoding="UTF-8"?>
<collection>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <leader>00857nam a22001937a 4500</leader>
  <controlfield tag="001">0305520</controlfield>
  <datafield tag="024" ind1=" " ind2=" "><subfield code="3">10.35217/0656-014-010-014</subfield></datafield>
  <datafield tag="041" ind1=" " ind2=" "><subfield code="a">ara</subfield></datafield>
  <datafield tag="044" ind1=" " ind2=" "><subfield code="b">السعودية</subfield></datafield>
  <datafield tag="100" ind1=" " ind2=" "><subfield code="9">208655</subfield><subfield code="a">جمال، أحمد محمد&#x202a;</subfield>
    <subfield code="g">Jamal, Ahmad Mohammad</subfield><subfield code="e">مؤلف</subfield></datafield>
  <datafield tag="245" ind1=" " ind2=" "><subfield code="a">من صور الأشقياء والسعداء :</subfield>
    <subfield code="b">على مائدة القرآن</subfield></datafield>
  <datafield tag="260" ind1=" " ind2=" "><subfield code="b">رابطة العالم الإسلامي</subfield><subfield code="c">1985</subfield>
    <subfield code="g">سبتمبر / ذو الحجة</subfield><subfield code="m">1405</subfield></datafield>
  <datafield tag="300" ind1=" " ind2=" "><subfield code="a">588 - 588</subfield></datafield>
  <datafield tag="336" ind1=" " ind2=" "><subfield code="a">بحوث ومقالات</subfield><subfield code="b">Article</subfield></datafield>
  <datafield tag="520" ind1=" " ind2=" "><subfield code="e">تناول المقال صور الأشقياء والسعداء في القرآن.
كُتب هذا المستخلص من قِبل دار المنظومة 2018</subfield><subfield code="f">The article deals with the images.</subfield></datafield>
  <datafield tag="653" ind1=" " ind2=" "><subfield code="a">القرآن الكريم</subfield><subfield code="a">التفسير</subfield></datafield>
  <datafield tag="692" ind1=" " ind2=" "><subfield code="a">السعادة</subfield><subfield code="b">Happiness</subfield></datafield>
  <datafield tag="773" ind1=" " ind2=" "><subfield code="4">الدراسات الإسلامية</subfield><subfield code="6">Islamic Studies</subfield>
    <subfield code="c">014</subfield><subfield code="l">010</subfield><subfield code="m">س14, ع10</subfield>
    <subfield code="o">0656</subfield><subfield code="s">دعوة الحق</subfield><subfield code="t">Call of Truth</subfield>
    <subfield code="v">014</subfield><subfield code="x">1319-0000</subfield></datafield>
  <datafield tag="856" ind1=" " ind2=" "><subfield code="u">0656-014-010-014.pdf</subfield></datafield>
</record>
<record xmlns="http://www.loc.gov/MARC21/slim">
  <controlfield tag="001">0000002</controlfield>
  <datafield tag="100" ind1=" " ind2=" "><subfield code="a">الفلاني، زيد</subfield><subfield code="e">مؤلف</subfield></datafield>
  <datafield tag="245" ind1=" " ind2=" "><subfield code="a">أثر الضرائب على التجارة الخارجية في الدول النامية</subfield></datafield>
  <datafield tag="260" ind1=" " ind2=" "><subfield code="c">2001</subfield></datafield>
  <datafield tag="300" ind1=" " ind2=" "><subfield code="a">100 - 140</subfield></datafield>
  <datafield tag="856" ind1=" " ind2=" "><subfield code="u">0001-001-001-001.pdf</subfield></datafield>
</record>
</collection>
"""


@pytest.fixture()
def cat(tmp_path):
    src = tmp_path / "marc.xml"
    src.write_text(MARC, encoding="utf-8")
    info = catalogue.build(src, tmp_path / "cat.sqlite", log=lambda *a: None)
    assert info["records"] == "2" and info["pdfs"] == "2"
    return catalogue.Catalogue(tmp_path / "cat.sqlite")


def test_record_fields(cat):
    r = cat.get("0656-014-010-014")
    assert r["title"] == "من صور الأشقياء والسعداء" and r["subtitle"] == "على مائدة القرآن"   # ISBD ':' dropped
    assert r["names"][0]["name"] == "جمال، أحمد محمد"                                       # bidi mark dropped
    assert r["names"][0]["latin"] == "Jamal, Ahmad Mohammad" and r["names"][0]["auth"] == "208655"
    assert r["journal"]["title"] == "دعوة الحق" and r["journal"]["issn"] == "1319-0000"
    assert r["year"] == "1985" and r["year_hijri"] == "1405"
    assert cat.get("9999-999-999-999") is None


def test_small_parsers():
    assert catalogue.months("يونيو / جمادى الاولى") == dict(gregorian=6, hijri=5)
    assert catalogue.months("ربيع الثاني") == dict(hijri=4)
    assert catalogue.months("ربيع") == dict(season="ربيع")
    assert catalogue.page_range("184 - 238") == (184, 238) and catalogue.page_range("") is None
    assert catalogue.display_name("المحجوب، عبدالمجيد") == "عبدالمجيد المحجوب"
    assert catalogue.contrib_type("مترجم") == "translator" and catalogue.contrib_type("م. مشارك") == "author"
    assert catalogue.num("034") == "34" and catalogue.num("000") == "" and catalogue.num("071,072") == "71-72"


PAGE = [[("على مائدة القرآن", 0.6, 0.25, 7.5), ("من صور الاشقياء والسعداء", 1.2, 0.45, 6.0),
         ("بقلم الاستاذ احمد محمد جمال", 2.0, 0.2, 5.5)] + body_lines(3.0, 10)
        + [("588", 10.4, 0.15, 4.5)]]


def test_catalogue_front_tied_to_the_ink(tmp_path, cat):
    stem = "0656-014-010-014"
    doc = load(azure(tmp_path, PAGE))
    meta = read_meta(stem, [], catalogue=cat)
    out = tmp_path / "doc.jats.xml"
    jats.write(doc, [], {}, stem, out, meta=meta)
    fr = doc["structure"]["front"]
    W = doc["words"]
    assert fr["title"] == "من صور الأشقياء والسعداء" and fr["title_source"].startswith("catalogue")
    assert " ".join(W[k]["out"] for k in fr["title_words"]).endswith("والسعداء")
    a = fr["authors"][0]
    assert " ".join(W[k]["out"] for k in a["words"]) == "احمد محمد جمال"
    assert a["prefix"] == "الاستاذ"                       # the honorific from the page, not the name
    assert fr["catalogue_check"]["verdict"] == "agrees"
    t = etree.parse(str(out))
    am = t.find(".//article-meta")
    assert am.findtext("title-group/article-title") == "من صور الأشقياء والسعداء"
    assert am.findtext("title-group/subtitle") == "على مائدة القرآن"
    nm = am.find("contrib-group/contrib/name-alternatives/name")
    assert (nm.findtext("surname"), nm.findtext("given-names"), nm.findtext("prefix")) == ("جمال", "أحمد محمد", "الاستاذ")
    assert t.findtext(".//journal-meta/journal-title-group/journal-title") == "دعوة الحق"
    assert [p.get("calendar") for p in am.findall("pub-date")] == ["gregorian", "islamic"]
    assert am.find("pub-date[@calendar='islamic']").findtext("month") == "12"
    assert (am.findtext("volume"), am.findtext("issue"), am.findtext("fpage")) == ("14", "10", "588")
    assert am.find("article-id[@pub-id-type='doi']").text == "10.35217/0656-014-010-014"
    assert len(am.findall("kwd-group")) == 3 and am.find("abstract") is not None
    assert "catalogue" in "".join(am.find("custom-meta-group").itertext())
    from inkscript.enrich import schemas
    try:
        schemas.jats_dtd()
    except Exception as e:
        pytest.skip(f"schemas not available: {e}")
    assert schemas.validate_jats(out) == []


def test_a_record_that_does_not_fit_is_reported(tmp_path, cat):
    doc = load(azure(tmp_path, PAGE))
    meta = read_meta("0001-001-001-001", [], catalogue=cat)
    jats.write(doc, [], {}, "0001-001-001-001", tmp_path / "x.jats.xml", meta=meta)
    fr = doc["structure"]["front"]
    assert fr["title"].startswith("أثر الضرائب") and not fr.get("title_words")
    assert fr["catalogue_check"]["verdict"].startswith("disagrees")
    assert "wrong record" in "".join(etree.parse(str(tmp_path / "x.jats.xml")).find(".//custom-meta-group").itertext())


def test_no_catalogue_no_change(tmp_path):
    doc = load(azure(tmp_path, PAGE))
    jats.write(doc, [], {}, "0656-014-010-014", tmp_path / "y.jats.xml", meta=read_meta("0656-014-010-014", []))
    assert "catalogue" not in doc["structure"]["front"]
