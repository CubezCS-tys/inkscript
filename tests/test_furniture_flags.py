"""Experiment 30 on small Azure readings written to disk: content near the top or bottom of a page is not taken for
page furniture (a table's header and cells, a note, a caption, a heading that opens a page), real running heads and
page numbers still are; and the page / block marks (vowelled text, a handwritten page) replace a flood of word
flags, written into the ALTO (TextBlock TAGREFS region.*, Page PAGECLASS), the JATS (custom-meta, content-type)
and the trust PDF (a page note)."""
import json

from lxml import etree

from inkscript.enrich import alto, jats
from inkscript.enrich.document import load
from inkscript.enrich.quran import check_document
from inkscript.enrich.structure import analyse
from inkscript.enrich.trust import assess, in_region, regions, summary

from test_structure import azure, body_lines

A = "{http://www.loc.gov/standards/alto/ns-v4#}"


def kinds_of(doc, st):
    return {doc["paras"][i]["content"]: st["kinds"][i] for i in range(len(doc["paras"]))}


def test_table_header_at_the_top_is_content_the_running_head_is_not(tmp_path):
    pages = []
    for n in range(3):
        head = [("مجلة كلية الدراسات الإسلامية", 0.4, 0.2, 7.5), (f"{40 + n}", 0.4, 0.2, 1.5)]
        if n == 1:                               # page 2 opens with a table: caption, header row, rows
            rows = [("جدول (٥) المتوسط الحسابي", 0.75, 0.2, 7.5),
                    ("المتغيرات", 1.0, 0.18, 7.5), ("أقل قيمة", 1.0, 0.18, 5.5), ("أكبر قيمة", 1.0, 0.18, 3.5),
                    ("المباريات", 1.25, 0.18, 7.5), ("٤", 1.25, 0.18, 5.5), ("٦", 1.25, 0.18, 3.5),
                    ("الأهداف", 1.5, 0.18, 7.5), ("٣", 1.5, 0.18, 5.5), ("٩", 1.5, 0.18, 3.5)]
            pages.append(head + rows + body_lines(2.0, 20))
        else:
            pages.append(head + body_lines(1.0, 22))
    doc = load(azure(tmp_path, pages))
    k = kinds_of(doc, analyse(doc))
    assert k["مجلة كلية الدراسات الإسلامية"] == "pageHeader"
    assert k["41"] == "pageNumber"
    for cell in ("المتغيرات", "أقل قيمة", "أكبر قيمة", "٤", "٦", "جدول (٥) المتوسط الحسابي"):
        assert k[cell] in (None, "sectionHeading"), cell


def test_notes_captions_and_masthead_words_in_the_text(tmp_path):
    pages = []
    for n in range(3):
        pages.append(body_lines(0.9, 24) + [(f"({n + 1}) المصدر السابق ص ١٢", 10.45, 0.14, 7.5),
                                            (f"{85 + n}", 10.7, 0.15, 4.5)])
    pages[0][0] = ("متوسط عدد ساعات الاستخدام في الأسبوع ٣", 0.5, 0.2, 7.5)   # "عدد" and a digit: not a masthead
    doc = load(azure(tmp_path, pages))
    k = kinds_of(doc, analyse(doc))
    assert k["(1) المصدر السابق ص ١٢"] != "pageFooter"        # the same phrase on every page, but a note
    assert k["متوسط عدد ساعات الاستخدام في الأسبوع ٣"] is None
    assert k["85"] == "pageNumber"


def test_a_small_number_in_a_row_is_a_cell_alone_it_is_a_speck(tmp_path):
    lines = body_lines(0.8, 10) + [("القيمة", 4.0, 0.2, 7.5), ("12", 4.02, 0.08, 5.0), ("40", 4.02, 0.08, 3.0),
                                   ("7", 6.0, 0.08, 0.6)] + body_lines(6.5, 10)
    doc = load(azure(tmp_path, [lines]))
    k = kinds_of(doc, analyse(doc))
    assert k["12"] is None and k["40"] is None
    assert k["7"] == "pageFooter"


VOWELLED = "كَتَبَ الْوَلَدُ دَرْسَهُ فِي الْبَيْتِ ثُمَّ خَرَجَ إِلَى الْحَدِيقَةِ مَعَ أَخِيهِ الصَّغِيرِ"


def vowelled_doc(tmp_path, handwritten_page=False):
    """Page 1: plain text, then a vowelled story whose words Azure reads at 0.5-0.7 (one at 0.05); page 2: ten
    lines Azure styles as handwritten."""
    p = azure(tmp_path, [body_lines(0.8, 3) + [(VOWELLED, 2.0 + i * 0.3, 0.2, 7.5) for i in range(6)],
                         body_lines(0.8, 10)])
    j = json.loads(p.read_text(encoding="utf-8"))
    ar = j["analyzeResult"]
    vw = [w for w in ar["pages"][0]["words"] if any("ً" <= c <= "ْ" for c in w["content"])]
    for w in vw:
        w["confidence"] = 0.6
    vw[-1]["confidence"] = 0.05
    if handwritten_page:
        ws = ar["pages"][1]["words"]
        ar["styles"] = [dict(isHandwritten=True, confidence=0.95,
                             spans=[dict(offset=ws[0]["span"]["offset"],
                                         length=ws[-1]["span"]["offset"] + 10 - ws[0]["span"]["offset"])])]
        for w in ws:
            w["confidence"] = 0.4
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return load(p)


def test_vowelled_block_carries_the_mark_not_every_word(tmp_path):
    doc = vowelled_doc(tmp_path)
    reg = regions(doc)
    marked = {i for i, ms in reg["blocks"].items() if "vowelled" in ms}
    assert marked and all(doc["paras"][i]["content"] == VOWELLED for i in marked)
    marks = assess(doc, check_document(doc))
    story = [k for i in marked for k in doc["paras"][i]["words"]]
    flagged = [k for k in story if marks[k].mark == "flagged"]
    assert len(flagged) == 1 and doc["words"][flagged[0]]["conf"] == 0.05      # far below its block: kept
    assert all(marks[k].region == ["vowelled"] for k in story)
    s = summary(marks)
    assert s["in_marked_blocks"]["vowelled"] == len(story) and s["flagged_in_marked_blocks"] == 1
    # outside a marked block nothing changes; inside, a specific reason stays
    assert in_region(["conf"], dict(conf=0.5), dict(marks=[])) == ["conf"]
    assert in_region(["conf", "quran"], dict(conf=0.5), dict(marks=["vowelled"], block_med=0.6, block_q10=0.3)) == ["quran"]


def test_handwritten_page_in_alto_jats_and_trust_pdf(tmp_path):
    import pymupdf
    doc = vowelled_doc(tmp_path, handwritten_page=True)
    marks = assess(doc, check_document(doc))
    assert doc["regions"]["pages"] == {2: "handwritten"}
    p2 = [k for k, m in marks.items() if doc["words"][k]["page"] == 2]
    assert all(marks[k].mark == "agreed" and marks[k].region == ["handwritten"] for k in p2)   # 0.4 everywhere
    jats.structure_of(doc)
    out = tmp_path / "doc.jats.xml"
    r = jats.write(doc, [], marks, "0000-001-002-003", out, "doc.alto.xml")
    t = etree.parse(str(out))
    names = {cm.findtext("meta-name"): cm.findtext("meta-value") for cm in t.iter("custom-meta")}
    assert names["reading-handwritten"].startswith("handwritten page:") and "page(s) 2" in names["reading-handwritten"]
    assert "reading-vowelled" in names
    assert {p.get("content-type") for p in t.iter("p")} >= {"vowelled", "handwritten"}
    alto.write(doc, [], marks, "doc", tmp_path / "doc.alto.xml", "doc.jats.xml", jats_ids=r["_ids"])
    a = etree.parse(str(tmp_path / "doc.alto.xml"))
    assert [pg.get("PAGECLASS") for pg in a.iter(A + "Page")] == [None, "handwritten"]
    tags = {tg.get("ID") for tg in a.iter(A + "OtherTag")}
    assert {"region.handwritten", "region.vowelled"} <= tags
    blocks = [tb.get("TAGREFS") for tb in a.iter(A + "TextBlock")]
    assert any("region.vowelled" in b for b in blocks) and any("region.handwritten" in b for b in blocks)
    # the trust PDF: a page note and the outlines, in their own layer
    from inkscript.enrich import trustpdf
    pdf = pymupdf.open()
    for _ in range(2):
        pdf.new_page(width=612, height=792)
    pdf.save(str(tmp_path / "doc.pdf"))
    t_pdf, n = trustpdf.write(tmp_path / "doc.pdf", doc, marks, [])
    d = pymupdf.open(str(t_pdf))
    notes = [a_.info["content"] for pg in d for a_ in pg.annots() if a_.type[1] == "Text"]
    assert any(c.startswith("Handwritten page.") for c in notes)
    assert any("Vowelled text in" in c for c in notes)
    assert "Reading marks" in [v["name"] for v in d.get_ocgs().values()]
