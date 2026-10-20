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


def test_bad_split_rebuilt_from_azure_words():
    lines = {"21:63": L("كان عليه أن يقدم نحو والشخصيات إنه يؤمن", [134, 858, 882, 882], 21)}
    a = {"pages": [{"page": 21, "blocks": [{"type": "paragraph", "lines": ["21:63a"]},
                                            {"type": "paragraph", "lines": ["21:63b"]}]}],
         "splits": [{"line": "21:63", "parts": ["كان عليه ان يقدم نحو", "والشخصيات إنه يؤمن"]}]}
    ans, log = RU.normalize(a, lines)
    assert ans["splits"][0]["parts"] == ["كان عليه أن يقدم نحو", "والشخصيات إنه يؤمن"]
    assert ans["pages"][0]["blocks"][0]["lines"] == ["21:63a"] and len(log["bad_splits"]) == 1


def test_bad_split_is_undone():
    lines = {"21:63": L("ما بعد الحرب العالمية الثانية كان عليه", [134, 858, 882, 882], 21)}
    a = {"pages": [{"page": 21, "blocks": [{"type": "paragraph", "lines": ["21:63a"]},
                                            {"type": "paragraph", "lines": ["21:63b"]}]}],
         "splits": [{"line": "21:63", "parts": ["ما بعد الحرب", "والشخصيات"]}]}
    ans, log = RU.normalize(a, lines)
    assert ans["pages"][0]["blocks"][0]["lines"] == ["21:63"] and ans["pages"][0]["blocks"][1]["lines"] == []
    assert ans["splits"] == [] and len(log["bad_splits"]) == 1


def test_fixes_counted_not_changed():
    lines = {"3:34": L("الجدولالآتى", [100, 100, 900, 120], 3)}
    a = {"pages": [], "fixes": [{"line": "3:34", "from": "الجدولالآتى", "to": "الجدول الآتى"},
                                {"line": "3:34", "from": "أكثر", "to": "اكثر"}]}
    ans, log = RU.normalize(a, lines)
    assert len(ans["fixes"]) == 2 and len(log["fixes_spacing"]) == 1 and len(log["fixes_orthographic"]) == 1


def test_empty_table_row_is_dropped_and_rowspans_shortened():
    ans = {"pages": [{"page": 6, "blocks": [{"type": "table", "rows": [
        [{"lines": ["6:1"], "th": True, "rowspan": 2}, {"lines": ["6:2"], "th": True, "rowspan": 3}],
        [], [{"lines": ["6:3"]}]]}]}]}
    out, log = RU.normalize(ans, {})
    rows = out["pages"][0]["blocks"][0]["rows"]
    assert log["empty_rows"] == 1 and len(rows) == 2
    assert "rowspan" not in rows[0][0] and rows[0][1]["rowspan"] == 2


def test_exclamation_is_not_turned_into_a_call():
    lines = {"2:8": L("واخرى رقم ٧ وهكذا (!) .", [100, 400, 900, 420], 2),
             "2:25": L("١ - المترجم", [700, 900, 900, 920], 2)}
    ans = {"pages": [{"page": 2, "blocks": [
        {"type": "paragraph", "lines": ["2:8"], "calls": [{"line": "2:8", "marker": "(!)", "fn": "fn-2-1"}]},
        {"type": "footnote", "lines": ["2:25"], "marker": "١", "id": "fn-2-1"}]}],
        "fixes": [{"line": "2:8", "from": "(!)", "to": "(١)"},
                  {"line": "2:8", "from": "وهكذا (!)", "to": "وهكذى (١)"}]}
    out, log = RU.normalize(ans, lines)
    assert out["fixes"] == [{"line": "2:8", "from": "وهكذا (!)", "to": "وهكذى (!)"}]   # the other change stays
    assert out["pages"][0]["blocks"][0]["calls"] == []
    assert len(log["exclamation_kept"]) == 2 and len(log["exclamation_calls_dropped"]) == 1


def test_a_glued_exclamation_call_is_left_to_the_model():
    lines = {"5:6": L("تَخْتَالُ!", [100, 400, 900, 420], 5)}
    ans = {"pages": [{"page": 5, "blocks": [{"type": "paragraph", "lines": ["5:6"],
                                             "calls": [{"line": "5:6", "marker": "١", "fn": "fn-5-1"}]}]}],
           "fixes": [{"line": "5:6", "from": "تَخْتَالُ!", "to": "تَخْتَالُ١"}]}
    out, log = RU.normalize(ans, lines)
    assert len(out["fixes"]) == 1 and len(out["pages"][0]["blocks"][0]["calls"]) == 1
    assert not log["exclamation_kept"]


def fig_page(extra_blocks, fig_box=(400, 250, 900, 650)):
    lines = {"1:2": L("الأطفال وأولياء الأمور والمعلمات", [175, 205, 807, 254]),
             "1:5": L("ترى من يختار البرامج التلفزيونية التي", [480, 415, 810, 442]),
             "1:6": L("يشاهدها الأطفال على شاشات التلفزيون", [480, 445, 825, 465]),
             "1:9": L("تلعب المواد الإعلامية دوراً مهماً في تنشئة", [500, 700, 900, 720])}
    blocks = [{"type": "title", "lines": ["1:2"]},
              {"type": "figure", "box": list(fig_box), "lines": [], "description": "tv"}] + extra_blocks
    return {"pages": [{"page": 1, "blocks": blocks}]}, lines


def test_text_inside_a_figure_becomes_the_figures_text_and_the_box_leaves_the_title():
    ans, lines = fig_page([{"type": "abstract", "lines": ["1:5", "1:6"]},
                           {"type": "paragraph", "lines": ["1:9"]}])
    out, log = RU.normalize(ans, lines)
    bl = out["pages"][0]["blocks"]
    assert [b["type"] for b in bl] == ["title", "figure", "paragraph"]
    assert bl[1]["lines"] == ["1:5", "1:6"] and len(log["text_in_figure"]) == 1
    assert bl[1]["box"][1] == 258 and len(log["figure_trim"]) == 1       # cut back below the title's line


def test_a_background_picture_under_the_title_keeps_its_text():
    ans, lines = fig_page([{"type": "abstract", "lines": ["1:5", "1:6"]}, {"type": "paragraph", "lines": ["1:9"]}],
                          fig_box=(100, 150, 950, 650))
    out, log = RU.normalize(ans, lines)
    assert [b["type"] for b in out["pages"][0]["blocks"]] == ["title", "figure", "abstract", "paragraph"]
    assert not log["text_in_figure"]


# ---------------------------------------------------------------- a picture is never lost (rules43.pictures)

def _words(table):
    def w(lid):
        return [dict(text=t, box=None, conf=c) for t, c in table.get(lid, [])]
    return w


def test_junk_line_and_real_words():
    lines = {"3:31": dict(text="FRES safd.", b=[591, 659, 831, 689], page=3),
             "3:21": dict(text="nbt pr Imn- Re", b=[136, 488, 363, 506], page=3),
             "3:29": dict(text="نقرأ بعض النقوش", b=[701, 638, 906, 656], page=3)}
    w = _words({"3:31": [("FRES", .29), ("safd.", .37)], "3:21": [("nbt", .96), ("pr", .99), ("Imn-", .98), ("Re", .35)],
                "3:29": [("نقرأ", .94), ("بعض", .98), ("النقوش", .97)]})
    assert RU.junk_line("3:31", lines, w)
    assert not RU.junk_line("3:21", lines, w)          # transliteration is text
    assert not RU.junk_line("3:29", lines, w)


def test_new_figure_from_ink_takes_the_junk_out_of_the_text():
    lines = {"3:29": dict(text="نقرأ بعض النقوش", b=[701, 638, 906, 656], page=3),
             "3:31": dict(text="FRES safd.", b=[591, 659, 831, 689], page=3),
             "3:32": dict(text="ترتيل يقال بواسطة المعبودة", b=[128, 691, 868, 707], page=3)}
    w = _words({"3:29": [("نقرأ", .94), ("بعض", .98), ("النقوش", .97)], "3:31": [("FRES", .29), ("safd.", .37)],
                "3:32": [("ترتيل", .98), ("يقال", .98), ("بواسطة", .99), ("المعبودة", .98)]})
    w.ink = lambda p, mask: [dict(box=[202, 660, 590, 688], fill=0.15, dark=900)]
    ans = {"pages": [{"page": 3, "blocks": [{"type": "paragraph", "lines": ["3:29"]},
                                            {"type": "quote", "lines": ["3:31", "3:32"]}]}], "noise": []}
    out, log = RU.normalize(ans, lines, w)
    bl = out["pages"][0]["blocks"]
    figs = [b for b in bl if b["type"] == "figure"]
    assert len(figs) == 1 and figs[0]["level"] == "ink" and figs[0]["box"][2] >= 831
    assert all("3:31" not in (b.get("lines") or []) for b in bl)
    assert "3:31" in out["_picture_junk"] and "3:31" in out["noise"]


def test_furniture_two_photos_and_bridge():
    assert RU.same_place([463, 28, 561, 95], [463, 30, 560, 96])
    assert RU.same_place([840, 902, 928, 967], [72, 903, 160, 968])            # mirrored on the facing page
    two = [dict(box=[95, 190, 499, 326], fill=.5, dark=1), dict(box=[527, 190, 929, 326], fill=.6, dark=1)]
    assert len(RU.bridged([dict(x) for x in two], [])) == 2                     # bare paper between: two photos
    cover = [dict(box=[113, 695, 179, 887], fill=.3, dark=1), dict(box=[252, 695, 297, 887], fill=.6, dark=1)]
    assert len(RU.bridged(cover, [[185, 700, 250, 730]])) == 1                  # printed words between: one


def test_picture_among_other_article_and_swapped_box():
    lines = {f"4:{k}": dict(text="نص مقالة أخرى هنا", b=[100, 100 + 40 * k, 900, 130 + 40 * k], page=4)
             for k in range(1, 6)}
    ans = {"pages": [{"page": 4, "blocks": [
        {"type": "other_article", "lines": ["4:1", "4:2", "4:3", "4:4", "4:5"]},
        {"type": "figure", "box": [100, 400, 500, 600], "lines": []}]}]}
    out, log = RU.normalize(ans, lines)
    f = [b for b in out["pages"][0]["blocks"] if b["type"] == "figure"][0]
    assert f["level"] == "other"
    lines2 = {f"1:{k}": dict(text="سطر من النص الجاري", b=[70, 340 + 30 * k, 300, 360 + 30 * k], page=1)
              for k in range(1, 6)}
    ans2 = {"pages": [{"page": 1, "blocks": [{"type": "paragraph", "lines": list(lines2)},
                                             {"type": "figure", "box": [65, 342, 474, 848], "lines": []}]}]}
    out2, _ = RU.normalize(ans2, lines2)
    f2 = [b for b in out2["pages"][0]["blocks"] if b["type"] == "figure"][0]
    assert f2["box"] == [342, 65, 848, 474]


# ---- layout rules (2026-10-18: 0478 p4, blocks drawn on top of each other)

P4 = {
    "4:1": L("٥٩", [128, 112, 147, 122], 4),
    "4:2": L("الاداري - القادسية للعلوم الادارية والاقتصادية المجلد (٧) العدد (٢)", [490, 113, 860, 125], 4),
    "4:3": L("١ -تقليل الوقت غير المستغل أو خسارة", [526, 151, 856, 170], 4),
    "4:4": L("الموازنه .", [784, 171, 858, 189], 4),
    "4:5": L("٢ -تقليل عدد محطات العمل .", [641, 190, 858, 208], 4),
    "4:21": L("١ -قيود الأسبقيه", [710, 457, 856, 475], 4),
    "4:23": L("Precedence Requiements", [527, 459, 700, 474], 4),
    "4:44": L("وهي عباره عن القيود الماديه ( الطبيعيه ) على", [529, 496, 860, 517], 4),
    "4:58": L("على نوع المليات المؤداةفي خط التجميع ،اذ ان", [528, 516, 858, 535], 4),
    "4:59": L("ان هذه القيود سوف تحد من قدرة مصمم خط", [527, 534, 860, 554], 4),
    "4:60": L("خط التدفق لتحقيق الموازنه في مهام العمل", [529, 553, 858, 573], 4),
}
P5 = {"5:1": L("الاداري - القادسية للعلوم الادارية والاقتصادية المجلد (٧) العدد (٢)", [490, 113, 860, 125], 5),
      "5:2": L("نص الصفحة التالية من المقال في العمود", [526, 151, 856, 170], 5)}


def test_long_heading_split_into_heading_and_paragraph():
    a = {"pages": [{"page": 4, "blocks": [
        {"type": "heading", "level": 4, "lines": ["4:21", "4:23", "4:44", "4:58", "4:59", "4:60"]}]}]}
    ans, log = RU.normalize(a, {k: v for k, v in P4.items() if k in ("4:21", "4:23", "4:44", "4:58", "4:59", "4:60")})
    bl = ans["pages"][0]["blocks"]
    assert bl[0]["type"] == "heading" and bl[0]["lines"] == ["4:21", "4:23"]
    assert bl[1]["type"] == "paragraph" and bl[1]["lines"] == ["4:44", "4:58", "4:59", "4:60"]
    assert log["long_headings"][0]["action"].startswith("split")


def test_long_display_title_kept_whole():
    lines = {f"1:{k}": L(w, [300, 100 + 40 * k, 700, 130 + 40 * k]) for k, w in
             enumerate(["يبحثها", "المؤتمر الإسلامى", "لوزراء", "الخارجية"], 1)}
    a = {"pages": [{"page": 1, "blocks": [{"type": "heading", "lines": list(lines)}]}]}
    ans, log = RU.normalize(a, lines)
    assert ans["pages"][0]["blocks"][0]["lines"] == list(lines)
    assert log["long_headings"][0]["action"] == "kept (flag only)"


def test_running_text_out_of_a_header_block():
    lines = dict(P4, **P5)
    a = {"pages": [{"page": 4, "blocks": [
        {"type": "header", "lines": ["4:2", "4:1", "4:3"]},
        {"type": "list_item", "list": "ol", "lines": ["4:4"]},
        {"type": "list_item", "list": "ol", "lines": ["4:5"]}]},
        {"page": 5, "blocks": [{"type": "header", "lines": ["5:1"]}, {"type": "paragraph", "lines": ["5:2"]}]}]}
    ans, log = RU.normalize(a, lines)
    bl = ans["pages"][0]["blocks"]
    assert bl[0] == {"type": "header", "lines": ["4:2", "4:1"]}
    assert bl[1]["type"] == "list_item" and bl[1]["lines"] == ["4:3"] and bl[1]["list"] == "ol"
    assert len(log["header_text"]) == 1
    assert ans["pages"][1]["blocks"][0]["lines"] == ["5:1"]            # the running head stays


# ------------------------------------------------------------------------------------------------ 2026-10-20 (fixes from the 300)

def test_table_parts_two_columns():
    rows = [[534, 842, 853, 861], [567, 869, 850, 885], [564, 889, 849, 902],           # foot of the right column
            [164, 78, 432, 91], [270, 99, 431, 111], [129, 137, 433, 154]]              # head of the left one
    assert RU.table_parts(rows) == [[0, 1, 2], [3, 4, 5]]
    assert RU.table_parts(rows[:3]) == [[0, 1, 2]]


def test_rubric():
    assert RU.is_rubric("II. - JURISPRUDENCE") and RU.is_rubric("REVUE DES LIVRES") and RU.is_rubric("عرض كتاب")
    assert not RU.is_rubric("LA JUSTICE ADMINISTRATIVE A MADAGASCAR")
    lines = {"1:1": L("REVUE DES LIVRES", [300, 50, 700, 80]), "1:2": L("Un livre sur la démographie", [100, 100, 900, 120]),
             "1:3": L("Cet ouvrage fait le point", [100, 130, 900, 150])}
    ans = {"metadata": {"title": "REVUE DES LIVRES"},
           "pages": [{"page": 1, "blocks": [{"type": "title", "lines": ["1:1"]}, {"type": "heading", "level": 2,
                                                                                  "lines": ["1:2"]},
                                            {"type": "paragraph", "lines": ["1:3"]}]}]}
    out, log = RU.normalize(ans, lines)
    b = out["pages"][0]["blocks"]
    assert [x["type"] for x in b] == ["heading", "title", "paragraph"] and out["metadata"]["title"] == "Un livre sur la démographie"
    assert log["rubric_title"][0]["action"] == "rubric -> heading"


def test_page_numbers_lone_misreading():
    lines = {f"{p}:1": L(t, [480, 960, 520, 975], p) for p, t in zip(range(1, 5), ["٣٤", "٣٥", "٣٩", "٣٧"])}
    ans = {"pages": [{"page": p, "blocks": [{"type": "footer", "lines": [f"{p}:1"]}]} for p in range(1, 5)]}
    out, log = RU.normalize(ans, lines)
    assert log["page_numbers"] == [dict(line="3:1", page=3, printed_read="٣٩", now="٣٦", pages_agreeing=3)]
    jump = {f"{p}:1": L(t, [480, 960, 520, 975], p) for p, t in zip(range(1, 6), ["34", "35", "36", "56", "57"])}
    ans = {"pages": [{"page": p, "blocks": [{"type": "footer", "lines": [f"{p}:1"]}]} for p in range(1, 6)]}
    assert RU.normalize(ans, jump)[1]["page_numbers"] == []                  # a jump in the issue: kept


def test_math_parts_empty_latex():
    lines = {"5:15": L("بحيث أن ||HT=maxx يوجد", [100, 100, 900, 120]), "5:16": L("-tostST", [400, 125, 500, 140])}
    ans = {"pages": [{"page": 5, "blocks": [{"type": "paragraph", "lines": ["5:15", "5:16"]}]}],
           "math": [{"line": "5:15", "from": "||HT=maxx", "latex": "\\mu_T"}, {"line": "5:16", "from": "-tostST", "latex": ""}]}
    out, log = RU.normalize(ans, lines)
    assert [f["from"] for f in out["fixes"] if f["to"] == ""] == ["-tostST"] and len(out["math"]) == 1


def test_advert_whole():
    lines = {f"2:{k}": L("كلمة من الإعلان", [60, 410 + 40 * k, 490, 430 + 40 * k], 2) for k in range(1, 4)}
    ans = {"pages": [{"page": 2, "blocks": [{"type": "other_article", "lines": list(lines)},
                                            {"type": "figure", "box": [56, 455, 496, 520], "lines": []},
                                            {"type": "figure", "box": [268, 500, 494, 545], "lines": []}]}]}
    out, log = RU.normalize(ans, lines)
    b = out["pages"][0]["blocks"]
    assert len(b) == 1 and b[0]["type"] == "figure" and b[0]["level"] == "other" and b[0]["lines"] == list(lines)


def test_latin_join():
    assert RU.latin_join("to establish a classificat-", "ion scheme for") == "join"
    assert RU.latin_join("the Islamic perspective -", "and this") is None              # a dash, not a cut word
    assert RU.latin_join("القسم-", "الثاني") is None


# ---- fix round 3 (2026-10-20, the proof pack)

def _halves(text, fixes=()):
    ans = {"fixes": list(fixes)}
    log = RU.new_log()
    RU.guillemet_halves(ans, {"1:1": dict(text=text, b=[0, 0, 10, 10], page=1)}, log)
    t = text
    for f in ans["fixes"]:
        if f["from"] in t:
            t = t.replace(f["from"], f["to"], 1)
    return t


def test_guillemet_halves():
    assert _halves("كتاب ((الاستشراق / الشرق كما خلقه الغرب)» المترجم") == "كتاب «الاستشراق / الشرق كما خلقه الغرب» المترجم"
    assert _halves("كلمة « قفا)» وكل") == "كلمة « قفا» وكل"
    assert _halves("«أنه ورثه نبوته وحكمته)).(١٧).") == "«أنه ورثه نبوته وحكمته».(١٧)."
    assert _halves("قال «كتاب (الأمالي)» هنا") == "قال «كتاب (الأمالي)» هنا"           # a real bracket inside
    assert _halves("المهددة بالانقراض)».") == "المهددة بالانقراض»."                   # opener on an earlier line
    # the model already fixed it: nothing more
    assert _halves("الحنفية)» انه", [{"line": "1:1", "from": "الحنفية)»", "to": "الحنفية »"}]) == "الحنفية » انه"


def test_honorifics_and_roles():
    import meta43
    for printed, name in (("أ.د. صالح الدوسي الزهراني", "صالح الدوسي الزهراني"), ("د / علي ابراهيم الفرحان", "علي ابراهيم الفرحان"),
                          ("أ. م.د / سلامة منصور محمد", "سلامة منصور محمد"), ("الدكتور السير سيدنى سميث", "سيدنى سميث"),
                          ("Dr.RAMDANI LAALA", "RAMDANI LAALA"), ("انور شاؤل المحامى", "انور شاؤل"),
                          ("السيد عبد الفتاح عفيفى", "السيد عبد الفتاح عفيفى"), ("داليا سمير سالم", "داليا سمير سالم")):
        assert meta43.strip_honorific(printed)[0] == name, printed
    assert meta43.role_kind("ترجمة") == "translator" and meta43.role_kind("مراجعة:") == "reviewer"
    assert meta43.role_kind("بقلم") is None and meta43.role_kind("إعداد") is None
    assert meta43.same_person_latin("جيوسيب كاروزو", "Giuseppe Caruso") > 0.7
    assert meta43.same_person_latin("جيوسيب كاروزو", "Elizabeth Morgan") < 0.7
