"""Unit tests of experiment 43's flags (flags43.py) on small made-up articles. No data, no calls.

    .venv/bin/pytest -q experiments/43_rehearsal/test_flags43.py
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import flags43 as F  # noqa: E402


def blk(page, typ, ids, **kw):
    return dict(page=page, type=typ, ids=ids, html="<p>x</p>", calls=kw.pop("calls", []), **kw)


def bundle(blocks, first=1, last=3):
    lines = {i: dict(text="كلمات في سطر", b=[100, 100, 900, 120], page=b["page"]) for b in blocks for i in b["ids"]}
    return dict(a=dict(stem="T", first=first, last=last), lines=lines, cap=dict(blocks=blocks), logs=[], answers=[])


def kinds(fl):
    return sorted((f["kind"], f["severity"]) for f in fl)


def test_other_article_top_or_bottom_is_fine():
    B = bundle([blk(3, "header", ["3:1"]), blk(3, "other_article", ["3:2"]),
                blk(3, "paragraph", ["3:3", "3:6", "3:7", "3:8", "3:9", "3:10"]), blk(3, "other_article", ["3:4"]),
                blk(3, "footer", ["3:5"])])
    assert F.check_other(B) == []


def test_other_article_in_the_middle():
    B = bundle([blk(3, "paragraph", ["3:1"]), blk(3, "other_article", ["3:2"]), blk(3, "paragraph", ["3:3"])])
    assert kinds(F.check_other(B)) == [("other_middle", "high")]


def test_other_article_on_an_inner_page():
    B = bundle([blk(1, "paragraph", ["1:1", "1:2", "1:3"]), blk(2, "other_article", ["2:1"]),
                blk(2, "paragraph", ["2:2", "2:3"]), blk(3, "paragraph", ["3:1", "3:2"])])
    assert kinds(F.check_other(B)) == [("other_inner", "medium")]


def test_table_widths_with_spans():
    rows = [[{"colspan": 2}, {}], [{}, {}, {}], [{"rowspan": 2}, {}, {}], [{}, {}]]
    assert F.table_widths(rows) == [3, 3, 3, 3]
    assert F.table_widths([[{}, {}, {}], [{}, {}]]) == [3, 2]


def test_ragged_table_flagged():
    B = bundle([blk(1, "table", ["1:1", "1:2", "1:3", "1:4", "1:5"], rows=[[{}, {}, {}], [{}, {}]])])
    assert kinds(F.check_tables(B)) == [("table_ragged", "medium")]


def test_heading_jump():
    B = bundle([blk(1, "heading", ["1:1"], level=1), blk(1, "heading", ["1:2"], level=3),
                blk(1, "heading", ["1:3"], level=2)])
    assert kinds(F.check_headings(B)) == [("heading_jump", "low")]


def test_type_mix_list_page_between_prose_pages():
    body = lambda p: [blk(p, "paragraph", [f"{p}:{k}" for k in range(1, 13)])]  # noqa: E731
    lst = [blk(2, "list_item", [f"2:{k}" for k in range(1, 13)])]
    B = bundle(body(1) + lst + body(3))
    assert kinds(F.check_mix(B)) == [("type_mix", "low")]
    B = bundle(body(1) + body(2) + body(3))
    assert F.check_mix(B) == []


def test_notes_calls_without_notes_and_orphans():
    calls = [dict(line=f"1:{k}", marker=str(k), fn=f"fn-{k}", page=1) for k in range(1, 7)]
    B = bundle([blk(1, "paragraph", [f"1:{k}" for k in range(1, 7)], calls=calls),
                blk(1, "footnote", ["1:9"], fn_id="fn-1", marker="1"),
                blk(1, "footnote", ["1:10"], fn_id="fn-99", marker="99")])
    got = kinds(F.check_notes(B))
    assert ("call_no_note", "medium") in got          # 5 calls on page 1 have no note
    assert ("call_no_note", "high") in got            # 5 of 6 in the article
    assert ("note_no_call", "low") in got             # fn-99


def test_rescued_noise_severity():
    B = bundle([blk(1, "paragraph", ["1:1"])])
    B["lines"].update({f"1:{k}": dict(text="سطر", b=[0, 0, 1, 1], page=1) for k in range(2, 6)})
    B["logs"] = [dict(never_noise=[dict(line=f"1:{k}", page=1, kind="noise", action="new other block", text="x")
                                   for k in (2, 3, 4)] +
                      [dict(line="1:5", page=1, kind="dropped", action="joined its paragraph block", text="y")])]
    assert kinds(F.check_noise(B)) == [("noise_rescued", "high"), ("noise_rescued", "low")]
