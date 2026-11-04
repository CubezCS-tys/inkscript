"""Tests of the "nothing lost" audit (experiment 61). Run: .venv/bin/pytest -q experiments/61_nothing_lost

The article tests read the release DB, the masters and the saved answers (read-only); they are skipped on a machine
without them (a fresh clone)."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import audit61 as A  # noqa: E402
import fields61 as F  # noqa: E402

STEM = "0130-018-072-003"
need_data = pytest.mark.skipif(not A.RELEASE.exists() or not (A.E43OUT / "j0130_final").exists(),
                               reason="release DB / experiment 43 outputs not on this machine")


def test_fold_and_tokens():
    assert F.toks("أ.د. الحبيب") == ["ا", "د", "الحبيب"]
    assert F.toks("Faisal1*") == ["faisal", "1"]
    assert F.toks("a.zaouji@gmail.com") == ["a.zaouji@gmail.com"]
    assert F.toks("الإسراء ١٩٧٩") == F.toks("الاسراء 1979")


def test_match_values_clitic_and_line_break():
    strings = [dict(content=w) for w in "سحر الشوربجي، وراشد المحرزي".split()]
    got = A.match_values(strings, [("author_name", "راشد المحرزي"), ("author_name", "سحر الشوربجي")])
    assert got == ["author_name"] * 4


def test_detect():
    assert F.detect("PhD Student in Sociology", "front_block") == "position"
    assert F.detect("University of Mohamed V - Faculty of Education Sciences - Morocco", "front_block") == "affiliation"
    assert F.detect("Doi:10.29343/1-79-4", "other") == "article_doi"
    assert F.detect("تم تسلم البحث في يناير 2017 وأجيز للنشر في يوليو 2017", "other") == "history_date"
    assert F.detect("المقالات", "other") == "journal_section"


@pytest.fixture(scope="module")
def example():
    if not A.RELEASE.exists():
        pytest.skip("no release DB")
    A.AZ.update(A.ink47.azure_paths())
    con = A.release()
    V = {v["stem"]: v for v in A.current_versions(con)}[STEM]
    return A.audit_article(con, V)


@need_data
def test_english_affiliation_leak_found(example):
    lk = {x["id"]: x for x in example["leaks"]}
    assert "1:31" in lk, "the printed English affiliation must be reported"
    assert lk["1:31"]["field"] == "affiliation" and lk["1:31"]["kind"] == "mapping"
    assert lk["1:31"]["answer_key"] == "metadata.authors[1].affiliation"
    assert lk["1:30"]["field"] == "position" and lk["1:30"]["kind"] == "mapping"     # PhD Student in Sociology
    assert lk["1:9"]["field"] == "position"                                            # طالبة باحثة في علم الاجتماع
    vals = {(v["key"], v["status"]) for v in example["answer"]["values"]}
    assert ("metadata.authors[1].affiliation", "flattened") in vals
    assert ("metadata.authors[0].role", "flattened") in vals


@need_data
def test_names_email_and_arabic_affiliation_are_fields(example):
    lines = {L["id"]: L for L in example["lines"]}
    assert lines["1:7"]["bucket"] == "a" and lines["1:7"]["field"] == "author_name"     # أمينة زوجي
    assert lines["1:8"]["field"] == "email"
    assert lines["1:10"]["field"] == "affiliation"
    assert lines["1:29"]["field"] == "author_name"                                      # Amina Zaouji (twin)


@need_data
def test_clean_pages_report_no_leaks(example):
    assert [x for x in example["leaks"] if x["page"] != 1] == []
    p2 = [L for L in example["lines"] if L["page"] == 2]
    assert p2 and all(L["bucket"] in ("a", "c") for L in p2)
    assert example["totals"]["lines"].get("d", 0) == 0


@need_data
def test_bilingual_pairs(example):
    b = example["bilingual"]
    assert b["names"]["jats"] == ["ar", "lat"] and b["names"]["linked"]
    assert b["affiliations"]["printed"] == ["ar", "lat"] and b["affiliations"]["jats"] == ["ar"]
