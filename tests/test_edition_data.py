"""Experiment 35: the article as data (Markdown, JSONL) and the automatic checks of the editions, on the
hand-made test masters (tests/fixtures/edition: a table with merged cells, MathML formulas; not archive pages)."""
import json
import random
from pathlib import Path

import pytest

from inkscript.edition.check import (allowed_extra, check_article, lcs_len, order_expected, reading_order, text_of_jsonl,
                                     text_of_md, tokens, words_once)
from inkscript.edition.data import fold, full_text, jsonl_line, markdown, record
from inkscript.edition.model import load

FX = Path(__file__).parent / "fixtures" / "edition"
TABLE_MATH = FX / "test-0001-table-math.jats.xml"
TWO_COL = FX / "test-0002-two-columns.jats.xml"
need = pytest.mark.skipif(not TABLE_MATH.exists(), reason="hand-made test masters not present")


def test_fold():
    assert fold("إِنَّ الأمَّةَ") == "ان الامه"
    assert fold("مصطفى ـــ کتاب ی") == "مصطفي  كتاب ي"
    assert fold("٢٠١٢ و۱۳۹۰") == "2012 و1390"
    assert fold("نمی‌خواهم") == "نميخواهم"
    assert fold("Hake, 1998") == "Hake, 1998"            # Latin and punctuation untouched


def test_tokens_cut_alike():
    # a note marker glued to its word, or apart, gives the same tokens; vowel marks, tatweel and alef forms vanish
    assert tokens("عاصمٌ(٢).") == tokens("عاصم ( ٢ ) .") == ["عاصم", "2"]
    assert tokens("أحمد ـ إلى") == ["احمد", "الي"]
    assert tokens("ﻻ") == ["لا"]                       # a PDF's lam-alef ligature (NFKC)
    assert tokens("Hake, 1998") == ["hake", "1998"]


def test_lcs_matches_brute_force():
    rnd = random.Random(7)

    def brute(a, b):
        t = [[0] * (len(b) + 1) for _ in range(len(a) + 1)]
        for i in range(len(a)):
            for j in range(len(b)):
                t[i + 1][j + 1] = t[i][j] + 1 if a[i] == b[j] else max(t[i][j + 1], t[i + 1][j])
        return t[-1][-1]
    for _ in range(50):
        a = [rnd.choice("abcd") for _ in range(rnd.randint(0, 30))]
        b = [rnd.choice("abcd") for _ in range(rnd.randint(0, 30))]
        assert lcs_len(a, b) == brute(a, b)


def test_reading_order_finds_swapped_blocks():
    blocks = [[f"w{b}_{i}" for i in range(6)] for b in range(5)]
    flat = [t for b in blocks for t in b]
    ok = reading_order(flat, flat, blocks)
    assert ok["share"] == 1.0 and ok["block_inversions"] == 0 and ok["blocks_placed"] == 5
    swapped = blocks[0] + blocks[2] + blocks[1] + blocks[3] + blocks[4]
    bad = reading_order(flat, [t for t in swapped], blocks)
    assert bad["block_inversions"] == 1 and bad["share"] < 1.0


@need
def test_markdown_and_record_of_table_and_maths(tmp_path):
    ed = load(TABLE_MATH)
    md = markdown(ed)
    assert md.startswith("---\nid: \"test-0001-table-math\"")
    assert "rights:" in md and "\n# " in md
    assert '<table dir="rtl">' in md and 'colspan="2"' in md and 'rowspan="2"' in md
    assert md.count("$$") >= 4 and "\\tag{" in md                 # two displayed formulas, numbered
    assert "[^fn-p1-1]" in md and "\n[^fn-p1-1]: " in md
    rec = record(ed)
    assert rec["id"] == ed.stem and rec["tables"] and rec["formulas"]
    t = rec["tables"][0]
    first = t["rows"][0]["cells"]
    assert first[0]["text"] == "الفئة"                               # reading order: the rightmost column first
    assert any(c["colspan"] == 2 for c in first)
    disp = [f for f in rec["formulas"] if f["display"]]
    assert disp and all(f["mathml"].startswith("<math") and f["tex"] for f in disp)
    assert any(not f["display"] for f in rec["formulas"])            # the inline formula
    assert rec["text_search"] == fold(rec["text"])
    assert rec["provenance"]["sources"]["alto"]["sha256"]
    json.loads(jsonl_line(ed))                                        # one valid JSON line
    # the files a user gets carry every ink word exactly once
    (tmp_path / "a.md").write_text(md, encoding="utf-8")
    (tmp_path / "a.jsonl").write_text(jsonl_line(ed) + "\n", encoding="utf-8")
    r = check_article(ed, dict(md=tmp_path / "a.md", jsonl=tmp_path / "a.jsonl"))
    for k in ("md", "jsonl"):
        w = r[k]["words"]
        assert w["missing"] == 0 and w["duplicated"] == 0, (k, w)
    assert r["md"]["formulas"]["found"] == r["md"]["formulas"]["expected"] == 3


@need
def test_words_once_sees_a_missing_and_a_duplicated_word(tmp_path):
    ed = load(TWO_COL)
    text = text_of_jsonl(jsonl_line(ed))
    assert words_once(ed, text)["exactly_once"]
    allowed = allowed_extra(ed)        # a word the front matter also prints could hide its duplicate (by design)
    word = next(w.text for w in ed.ink_words() if len(w.text) > 4 and len(tokens(w.text)) == 1 and
                not allowed[tokens(w.text)[0]] and
                sum(tokens(x.text) == tokens(w.text) for x in ed.ink_words()) == 1)
    tok = tokens(word)[0]
    cut = " ".join(t for t in tokens(text) if t != tok)
    r = words_once(ed, cut)
    assert r["missing"] >= 1 and not r["exactly_once"]
    assert any(x["token"] == tok for x in r["examples_missing"])
    r = words_once(ed, text + " " + word)
    assert r["duplicated"] == 1 and r["missing"] == 0


@need
def test_order_expected_follows_the_master():
    ed = load(TWO_COL)
    blocks = order_expected(ed)
    flat = [t for b in blocks for t in b]
    body = tokens(full_text(ed))
    assert reading_order(flat, body)["share"] > 0.9
