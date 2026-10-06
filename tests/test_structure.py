"""The article's structure (enrich/structure.py, experiment 26) on small Azure readings written to disk: the id's
parts, Gemini's title file aligned to the ink, running heads and page numbers kept out of the text, headings by
size, lists that are not headings, notes at the foot of a page linked from their markers, and valid JATS."""
import json

from lxml import etree

from inkscript.enrich import jats
from inkscript.enrich.document import load
from inkscript.enrich.structure import analyse, id_parts, read_meta


def azure(tmp_path, pages, name="doc"):
    """pages: [[(text, y, h, x_right)], ...] in inches on an 8.5 x 11 page; one line = one paragraph; words 0.45 in
    wide from x_right leftwards (right to left)."""
    content, apages, paras = "", [], []
    for pn, lines in enumerate(pages, 1):
        words, alines = [], []
        for text, y, h, xr in lines:
            if content:
                content += "\n"
            start = len(content)
            for k, t in enumerate(text.split()):
                if k:
                    content += " "
                x = xr - k * 0.5
                words.append(dict(content=t, span=dict(offset=len(content), length=len(t)), confidence=0.99,
                                  polygon=[x - 0.45, y, x, y, x, y + h, x - 0.45, y + h]))
                content += t
            span = dict(offset=start, length=len(content) - start)
            alines.append(dict(content=text, spans=[span]))
            paras.append(dict(content=text, spans=[span], boundingRegions=[dict(pageNumber=pn, polygon=[])]))
        apages.append(dict(pageNumber=pn, width=8.5, height=11.0, unit="inch", angle=0, words=words, lines=alines))
    j = dict(analyzeResult=dict(content=content, modelId="prebuilt-read", apiVersion="test", pages=apages,
                                paragraphs=paras))
    p = tmp_path / f"{name}.json"
    p.write_text(json.dumps(j, ensure_ascii=False), encoding="utf-8")
    return p


BODY = "هذا نص عادي من نصوص المقالة يمتد على السطر كله كما تمتد سطور المتن في الصفحة"


def body_lines(y0, n, h=0.2):
    return [(BODY, y0 + i * 0.3, h, 7.5) for i in range(n)]


def test_id_parts():
    assert id_parts("0656-014-010-014") == dict(journal="0656", volume="14", issue="10", seq="14")
    assert id_parts("0570-000-041,042-012") == dict(journal="0570", issue="41-42", seq="12")
    assert id_parts("0807-008-999-005")["issue_special"] is True
    assert "volume" not in id_parts("6795-000-000-014") and "issue" not in id_parts("6795-000-000-014")


def test_gemini_title_aligned_to_the_ink(tmp_path):
    p = azure(tmp_path, [[("رسالة المسجوالاسا", 1.5, 0.6, 6.0), ("الشيخ مصطفى كمال التارزي", 2.5, 0.25, 6.0)]
                         + body_lines(3.5, 12)])
    (tmp_path / "doc.gemini.title.json").write_text(json.dumps(
        {"title": "رسالة المسجد في الاسلام", "authors": ["الشيخ مصطفى كمال التارزي"]}, ensure_ascii=False),
        encoding="utf-8")
    meta = read_meta("doc", [tmp_path])
    assert meta["gemini"]["title"] == "رسالة المسجد في الاسلام"
    doc = load(p)
    st = analyse(doc, meta)
    fr = st["front"]
    assert fr["title"] == "رسالة المسجد في الاسلام" and fr["title_source"] == "gemini-title-file"
    assert [doc["words"][k]["id"] for k in fr["title_words"]] == ["p1w0001", "p1w0002"]
    a = fr["authors"][0]
    assert a["name"] == "مصطفى كمال التارزي" and a["prefix"] == "الشيخ"
    assert [doc["words"][k]["text"] for k in a["prefix_words"]] == ["الشيخ"]


def test_title_and_byline_from_layout(tmp_path):
    p = azure(tmp_path, [[("على مائدة القرآن", 0.6, 0.25, 7.5), ("من صور الاشقياء والسعداء", 1.2, 0.45, 6.0),
                          ("بقلم الاستاذ احمد محمد جمال", 2.0, 0.2, 5.5)] + body_lines(3.0, 14)])
    st = analyse(load(p))
    fr = st["front"]
    assert fr["title"] == "من صور الاشقياء والسعداء" and fr["rubric"] == "على مائدة القرآن"
    assert fr["authors"][0]["name"] == "احمد محمد جمال" and fr["authors"][0]["prefix"] == "الاستاذ"


def test_running_heads_and_page_numbers_are_not_text(tmp_path):
    pages = []
    for n in range(3):
        pages.append([("مجلة كلية الدراسات الإسلامية", 0.5, 0.2, 7.5)] + body_lines(1.2, 20)
                     + [(f"{85 + n}", 10.4, 0.15, 4.5)])
    doc = load(azure(tmp_path, pages))
    st = analyse(doc)
    heads = [i for i, p in enumerate(doc["paras"]) if p["content"].startswith("مجلة")]
    nums = [i for i, p in enumerate(doc["paras"]) if p["content"].isdigit()]
    assert all(st["kinds"][i] == "pageHeader" for i in heads)
    assert all(st["kinds"][i] == "pageNumber" for i in nums)
    assert st["journal"] == "مجلة كلية الدراسات الإسلامية"


def test_headings_by_size_and_lists_are_not_headings(tmp_path):
    lines = body_lines(0.8, 6) + [("الفصل الأول مدخل", 2.9, 0.32, 7.5)] + body_lines(3.4, 4) \
        + [("1 - أولها", 4.7, 0.2, 7.5), ("2 - ثانيها", 5.0, 0.2, 7.5), ("3 - ثالثها", 5.3, 0.2, 7.5)] \
        + body_lines(5.7, 10)
    doc = load(azure(tmp_path, [lines]))
    st = analyse(doc)
    got = [doc["paras"][i]["content"] for i, k in enumerate(st["kinds"]) if k == "sectionHeading"]
    assert got == ["الفصل الأول مدخل"]


def test_notes_linked_from_their_markers(tmp_path):
    lines = body_lines(0.8, 10) + [("قال عاصم(٢). وقرأ نافع (١) كذلك في هذه الرواية المشهورة عند القراء جميعا", 3.9, 0.2, 7.5)] \
        + body_lines(4.2, 12) + [("(١) نافع المدني أحد القراء السبعة", 8.8, 0.14, 7.5),
                                 ("(٢) عاصم بن أبي النجود الكوفي", 9.1, 0.14, 7.5)]
    p = azure(tmp_path, [lines])
    doc = load(p)
    st = analyse(doc)
    assert [(n["label"], n["page"]) for n in st["notes"]] == [("1", 1), ("2", 1)]
    marks = {doc["words"][k]["text"]: (m["mark"], st["notes"][m["note"]]["label"]) for k, m in st["markers"].items()}
    assert marks == {"عاصم(٢).": ("(٢)", "2"), "(١)": ("(١)", "1")}
    out = tmp_path / "doc.jats.xml"
    jats.write(doc, [], {}, "0000-001-002-003", out)
    t = etree.parse(str(out))
    xr = {x.text: x.get("rid") for x in t.iter("xref")}
    assert xr == {"(٢)": "fn-p1-2", "(١)": "fn-p1-1"}
    assert t.find(".//fn[@id='fn-p1-1']/label").text == "1"
    assert "نافع المدني" in "".join(t.find(".//fn[@id='fn-p1-1']/p").itertext())
    assert t.findtext(".//volume") == "1" and t.findtext(".//issue") == "2"
    # the note text is not article text, and the glued word keeps its letters
    body = "".join(t.find(".//body").itertext())
    assert "نافع المدني" not in body and "عاصم" in body


def test_structure_jats_validates(tmp_path):
    from inkscript.enrich import schemas
    import pytest
    try:
        schemas.jats_dtd()
    except Exception as e:
        pytest.skip(f"schemas not available: {e}")
    pages = [[("على مائدة القرآن", 0.6, 0.25, 7.5), ("من صور الاشقياء والسعداء", 1.2, 0.45, 6.0),
              ("بقلم الاستاذ احمد محمد جمال", 2.0, 0.2, 5.5)] + body_lines(3.0, 10)
             + [("قال عاصم(١). وقرأ غيره كذلك في هذه الرواية المشهورة عند القراء جميعا", 6.1, 0.2, 7.5)]
             + [("الفصل الأول مدخل", 6.6, 0.32, 7.5)] + body_lines(7.1, 5)
             + [("(١) عاصم بن أبي النجود الكوفي", 9.1, 0.14, 7.5), ("588", 10.4, 0.15, 4.5)]]
    doc = load(azure(tmp_path, pages))
    out = tmp_path / "doc.jats.xml"
    jats.write(doc, [], {}, "0656-014-010-014", out)
    assert schemas.validate_jats(out) == []
