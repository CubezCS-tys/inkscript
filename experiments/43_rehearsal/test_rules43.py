"""Unit tests of experiment 43's code rules (rules43.py), on small made-up answers. No data, no calls.

    .venv/bin/pytest -q experiments/43_rehearsal/test_rules43.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import rules43 as RU  # noqa: E402


def L(text, b, page=1):
    return dict(text=text, b=b, page=page)


LINES = {
    "1:1": L("عنوان المقال الطويل", [300, 50, 700, 80]),
    "1:2": L("هذا سطر أول من الفقرة الأولى في العمود", [100, 100, 900, 120]),
    "1:3": L("وهذا سطر ثان من الفقرة نفسها في العمود", [100, 125, 900, 145]),
    "1:4": L("وهذا سطر ثالث نسيه النموذج في الفقرة", [100, 150, 900, 170]),
    "1:5": L("ins", [474, 300, 493, 310]),                     # a speck read as letters
    "1:6": L("أزواجويت", [990, 410, 997, 445]),                 # vertical junk at the page edge
    "1:7": L("كلام مقال آخر في أعلى الصفحة الأخرى", [520, 400, 900, 420]),
    "1:8": L("ومواصلة ذلك المقال الآخر في سطر ثان", [520, 425, 900, 445]),
    "1:9": L("وسطر ثالث من المقال الآخر قبل نهايته", [520, 450, 900, 470]),
    "1:10": L("رقم ١٢", [480, 960, 520, 975]),
}


def ans_base():
    return {"pages": [{"page": 1, "blocks": [
        {"type": "title", "lines": ["1:1"]},
        {"type": "paragraph", "lines": ["1:2", "1:3"]},
        {"type": "footer", "lines": ["1:10"]}]}],
        "noise": ["1:5", "1:6", "1:7", "1:8", "1:9"]}


def test_has_words():
    assert RU.has_words(LINES["1:2"])
    assert not RU.has_words(LINES["1:5"])          # 3 letters
    assert not RU.has_words(LINES["1:6"])          # too narrow for 8 letters, at the edge


def test_never_noise_merges_a_dropped_line_and_blocks_a_run():
    ans, log = RU.normalize(ans_base(), LINES)
    blocks = ans["pages"][0]["blocks"]
    para = blocks[1]
    assert para["lines"] == ["1:2", "1:3", "1:4"]                 # the dropped line joins its paragraph, in place
    other = [b for b in blocks if b.get("from_noise") is True]
    assert len(other) == 1 and other[0]["type"] == "other" and other[0]["lines"] == ["1:7", "1:8", "1:9"]
    assert blocks[-1]["type"] == "footer"                          # placed before the page's closing furniture
    assert set(ans["noise"]) == {"1:5", "1:6"}                     # specks stay noise
    assert len(log["never_noise"]) == 4


def test_other_article_lines_are_not_noise_and_counted():
    a = ans_base()
    a["noise"] = ["1:5", "1:6"]
    a["pages"][0]["blocks"].insert(0, {"type": "other_article", "lines": ["1:7", "1:8", "1:9"]})
    a["pages"][0]["blocks"][2]["lines"].append("1:4")
    ans, log = RU.normalize(a, LINES)
    assert log["other_article_blocks"] == 1 and log["other_article_lines"] == 3
    assert log["never_noise"] == []


def test_verse_cut_by_word_index():
    lines = {"3:4": L("من نور وجنتها من حسن غرتها ٥ من طيب طرتها من طرفها الثمل", [130, 115, 865, 151], 3)}
    a = {"pages": [{"page": 3, "blocks": [{"type": "verse", "cut": {"3:4": 7}, "hemistichs": [["3:4"]]}]}]}
    ans, log = RU.normalize(a, lines)
    assert log["cuts"] == 1
    sp = ans["splits"][0]
    assert sp["parts"] == ["من نور وجنتها من حسن غرتها ٥", "من طيب طرتها من طرفها الثمل"]
    assert ans["pages"][0]["blocks"][0]["hemistichs"] == [["3:4a"], ["3:4b"]]
    # the ornament at the right half's inner edge is found in code
    assert ans["_ornaments"] == [dict(line="3:4", word=7, text="٥", source="code")]


def test_bad_cut_is_logged():
    lines = {"3:4": L("كلمة واحدة", [130, 115, 865, 151], 3)}
    a = {"pages": [{"page": 3, "blocks": [{"type": "verse", "cut": {"3:4": 5}, "hemistichs": [["3:4a"], ["3:4b"]]}]}]}
    ans, log = RU.normalize(a, lines)
    assert log["cuts"] == 0 and len(log["bad_cuts"]) == 1


def test_model_ornament_checked_and_call_marker_kept():
    lines = {"2:9": L("وعن ملوك كرام قد مضوا قددا ٥", [492, 402, 867, 433], 2),
             "2:19": L("حتى يجيبك عنهم شاهد الطلل ٣", [135, 399, 464, 433], 2)}
    a = {"pages": [{"page": 2, "blocks": [{"type": "verse", "hemistichs": [["2:9"], ["2:19"]],
                                           "calls": [{"line": "2:19", "marker": "٣", "fn": "fn-2-3"}]}]}],
         "ornaments": [{"line": "2:9", "word": 9, "text": "٥"}]}          # wrong word number: the nearest ٥ is taken
    ans, log = RU.normalize(a, lines)
    assert ans["_ornaments"] == [dict(line="2:9", word=7, text="٥", source="model")]


def test_ornament_inside_a_fix_is_left_to_the_fix():
    lines = {"8:4": L("أثم التمنى إذا جائتك سائلة *", [498, 115, 879, 146], 8),
             "8:24": L("أرجعتها وهي في عقر مع الحبل", [149, 112, 479, 148], 8)}
    a = {"pages": [{"page": 8, "blocks": [{"type": "verse", "hemistichs": [["8:4"], ["8:24"]]}]}],
         "fixes": [{"line": "8:4", "from": "سائلة *", "to": "سائلة"}]}
    ans, _ = RU.normalize(a, lines)
    assert ans["_ornaments"] == []


def test_endnote_becomes_linked_footnote():
    lines = {"9:1": L("١- انظر ابن خلدون، المقدمة، ص ١٢", [100, 100, 900, 120], 9)}
    a = {"pages": [{"page": 9, "blocks": [{"type": "endnote", "marker": "١", "id": "en-1", "lines": ["9:1"]}]}]}
    ans, log = RU.normalize(a, lines)
    b = ans["pages"][0]["blocks"][0]
    assert b["type"] == "footnote" and b["note_kind"] == "endnote" and b["id"] == "en-1" and log["endnotes"] == 1


def test_bad_split_is_undone():
    lines = {"21:63": L("ما بعد الحرب العالمية الثانية كان عليه", [134, 858, 882, 882], 21)}
    a = {"pages": [{"page": 21, "blocks": [{"type": "paragraph", "lines": ["21:63a"]},
                                            {"type": "paragraph", "lines": ["21:63b"]}]}],
         "splits": [{"line": "21:63", "parts": ["ما بعد الحرب العالمية", "والشخصيات إنه يؤمن"]}]}
    ans, log = RU.normalize(a, lines)
    assert ans["pages"][0]["blocks"][0]["lines"] == ["21:63"] and ans["pages"][0]["blocks"][1]["lines"] == []
    assert ans["splits"] == [] and len(log["bad_splits"]) == 1


def test_fixes_counted_not_changed():
    lines = {"3:34": L("الجدولالآتى", [100, 100, 900, 120], 3)}
    a = {"pages": [], "fixes": [{"line": "3:34", "from": "الجدولالآتى", "to": "الجدول الآتى"},
                                {"line": "3:34", "from": "أكثر", "to": "اكثر"}]}
    ans, log = RU.normalize(a, lines)
    assert len(ans["fixes"]) == 2 and len(log["fixes_spacing"]) == 1 and len(log["fixes_orthographic"]) == 1
