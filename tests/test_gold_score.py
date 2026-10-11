"""The gold format and the scorer (experiment 34)."""
import json
import random

import pytest

from inkscript.gold import format as gf
from inkscript.gold.score import (concordance, eq_sim, latex_tokens, loops, match_lines, run, score_page, teds,
                                  tree_distance, table_tree)
from inkscript.gold.text import distance, faithful, folded


def _lev(a, b):
    d = list(range(len(b) + 1))
    for i, x in enumerate(a, 1):
        p, d[0] = d[0], i
        for j, y in enumerate(b, 1):
            p, d[j] = d[j], min(d[j] + 1, d[j - 1] + 1, p + (x != y))
    return d[-1]


def test_distance_matches_plain_dp():
    rnd = random.Random(1)
    for _ in range(300):
        a = "".join(rnd.choice("ابتثج ") for _ in range(rnd.randint(0, 90)))
        b = "".join(rnd.choice("ابتثج ") for _ in range(rnd.randint(0, 90)))
        assert distance(a, b) == _lev(a, b)
    assert distance("ا" * 200, "ب" * 150) == 200       # longer than one machine word
    assert distance("كتب الطالب".split(), "كتب الطلاب".split()) == 1


def test_normalisations():
    assert faithful("العـــربية  \n ") == "العربية"
    assert faithful("ﻻ") == "لا"                      # presentation form decomposed
    assert faithful("ﷺ") == "ﷺ"
    assert folded("أَهْلُ") == folded("اهل") == "اهل"
    assert folded("مكتبة،  ١٩٨٥") == "مكتبه 1985"
    assert folded("فى") == folded("في")
    assert faithful("فى") != faithful("في")


def test_line_matching_and_hallucination():
    gold = [("السطر الاول من النص", None), ("السطر الثاني هنا", None), ("حاشية", None)]
    pred = [("السطر الثاني هنا", None), ("السطر الاول من النس", None), ("كلام مخترع لا وجود له", None)]
    assert match_lines(gold, pred) == [(0, 1), (1, 0)]
    assert concordance([1, 0]) == (0, 1)
    assert loops("و و و و و و") and not loops("كلام عادي جدا")


def _page(lines, status="done", tables=(), equations=()):
    ls = [dict(id=f"l{i:03d}", box=[0, 10 * i, 100, 10 * i + 8], text=t, status="ok", kind=k)
          for i, (t, k) in enumerate(lines, 1)]
    return dict(schema=gf.SCHEMA, page_id="0001-000-000-001_p001", stem="0001-000-000-001", page=1, split="test",
                kinds=["body"], primary="body", decade="1980s", status=status, image=dict(file="x.jpg", width=100,
                height=500, dpi=300), lines=ls, order=[x["id"] for x in ls], regions=[], tables=list(tables),
                equations=list(equations), articles=[])


def test_score_page_counts():
    g = _page([("بسم الله الرحمن الرحيم", "text"), ("الحمد لله", "text"), ("(١) حاشية", "footnote")])
    assert gf.check(g) == []
    perfect = score_page(g, {"lines": [{"text": ln["text"]} for ln in g["lines"]]})
    assert perfect["faithful.char_err"] == 0 and perfect["inserted"] == perfect["dropped"] == 0
    assert perfect["order_ok"] == perfect["order_pairs"] == 3
    bad = score_page(g, {"lines": [{"text": "الحمد لله"}, {"text": "بسم الله الرحمن الرحيم"},
                                   {"text": "سطر لم يطبع ابدا في الصفحة"}, {"text": "الحمد لله"}]})
    assert bad["dropped"] == 1                # the footnote
    assert bad["inserted"] == 1 and bad["repeated"] == 1
    assert bad["order_ok"] == 0 and bad["order_pairs"] == 1
    vowels = score_page(g, {"lines": [{"text": "بِسْمِ اللهِ الرحمن الرحيم"}, {"text": "الحمد لله"}, {"text": "(1) حاشية"}]})
    assert vowels["faithful.char_err"] > 0 and vowels["folded.char_err"] == 0


def test_teds():
    a = "<table><tr><td>السنة</td><td>العدد</td></tr><tr><td>1980</td><td>12</td></tr></table>"
    assert teds(a, a) == 1.0
    b = "<table><tr><td>السنة</td><td>العدد</td></tr><tr><td>1980</td><td>13</td></tr></table>"
    assert 0.9 < teds(a, b) < 1.0
    c = "<table><tr><td colspan='2'>السنة العدد</td></tr><tr><td>1980</td><td>12</td></tr></table>"
    assert teds(a, c) < teds(a, b)
    assert teds(a, "") == 0.0 and teds("", a) is None
    t = table_tree(a)
    assert tree_distance(t, t) == 0


def test_equations():
    assert latex_tokens(r"\left( x^{2} \right)") == ["(", "x", "^", "2", ")"]
    assert eq_sim(r"y = a + b x", r"y=a+bx") == (1.0, True)
    s, ex = eq_sim(r"\frac{a}{b}", r"\frac{a}{c}")
    assert 0 < s < 1 and not ex


def test_run_over_a_dir(tmp_path):
    g = _page([("بسم الله الرحمن الرحيم", "text"), ("الحمد لله", "text")],
              tables=[dict(id="t1", html="<table><tr><td>1</td></tr></table>")],
              equations=[dict(id="e1", latex="x+y")])
    (tmp_path / "gold").mkdir()
    gf.save(tmp_path / "gold" / f"{g['page_id']}.json", g)
    (tmp_path / "pred").mkdir()
    (tmp_path / "pred" / f"{g['page_id']}.txt").write_text("بسم الله الرحمن الرحيم\nالحمد لله\n", encoding="utf-8")
    rep = run(tmp_path / "gold", tmp_path / "pred", boot=50)
    s = rep["summary"]["all"]
    assert s["faithful.cer"] == 0 and s["teds"] == 0.0 and s["eq_sim"] == 0.0
    draft = _page([("نص", "text")], status="todo")
    draft["page_id"], draft["stem"] = "0002-000-000-001_p001", "0002-000-000-001"
    gf.save(tmp_path / "gold" / f"{draft['page_id']}.json", draft)
    assert run(tmp_path / "gold", tmp_path / "pred", boot=0)["not_done"] == 1
    assert len(run(tmp_path / "gold", tmp_path / "pred", drafts=True, boot=0)["pages"]) == 2


def test_alto_export_is_valid(tmp_path):
    g = _page([("بسم الله", "text")])
    g["regions"] = [dict(id="r01", type="text", box=[0, 0, 100, 20], column=1, article=None, order=1)]
    for ln in g["lines"]:
        ln["region"] = "r01"
    (tmp_path / "p.alto.xml").write_bytes(gf.to_alto(g))
    from inkscript.enrich.schemas import validate_alto
    assert validate_alto(tmp_path / "p.alto.xml") == []


def test_draft_from_the_fixture(tmp_path):
    from pathlib import Path
    from inkscript.gold.draft import write_pages
    F = Path(__file__).parent / "fixtures" / "0582-004-009-012"
    stem = "0582-004-009-012"
    ids = write_pages(F / "azure" / stem / f"{stem}.json", F / "input" / f"{stem}.pdf", [2], tmp_path,
                      dict(stem=stem, split="dev", pages={2: dict(kinds=["footnotes"], primary="footnotes")}))
    assert ids == [f"{stem}_p002"]
    g = gf.load(tmp_path / f"{stem}_p002.json")
    assert gf.check(g) == []
    assert g["primary"] == "footnotes" and g["image"]["dpi"] == 300 and (tmp_path / f"{stem}_p002.jpg").exists()
    assert len(g["lines"]) == 33 and any(ln["kind"] == "footnote" for ln in g["lines"])
    assert all(r["column"] == 1 or r["type"] == "furniture" for r in g["regions"])    # one column, footnotes too
    assert write_pages(F / "azure" / stem / f"{stem}.json", F / "input" / f"{stem}.pdf", [2], tmp_path,
                       dict(stem=stem)) == []                                       # never overwritten
    rep = run(tmp_path, reader="azure-draft", drafts=True, boot=0)
    assert rep["summary"]["all"]["faithful.cer"] == 0
