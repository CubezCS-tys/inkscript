"""Unit tests of jats43 (the JATS slots) and the v3 rule in rules43; no data, no calls.

    .venv/bin/pytest -q experiments/43_rehearsal/test_jats43.py
"""
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

sys.path.insert(0, str(Path(__file__).resolve().parent))
import jats43 as J  # noqa: E402
import rules43 as RU  # noqa: E402


def test_dates_printed_forms():
    assert J.parse_date("2022/05/12") == dict(year=2022, month=5, day=12)
    assert J.parse_date("١٢/٠٥/٢٠٢٢") == dict(year=2022, month=5, day=12)
    assert J.parse_date("22 ماي 2017") == dict(year=2017, month=5, day=22)
    assert J.parse_date("March 3, 2020") == dict(year=2020, month=3, day=3)
    assert J.parse_date("5 كانون الثاني 1999") == dict(year=1999, month=1, day=5)
    assert J.parse_date("no date") is None


def test_history_labels_need_the_date_right_after():
    hs = J.history_in("تاريخ الإستقبال: 10 أفريل 2017 تاريخ التحكيم 02 ماي 2017، تاريخ القبول22 ماي 2017، "
                      "تاريخ النشر على الموقع")
    assert [h["type"] for h in hs] == ["received", "reviewed", "accepted"]
    assert J.history_in("مقبول للنشر بتاريخ 2017/12/3")[0]["text"] == "2017/12/3"
    assert J.history_in("Published by Dar al-Kutub, Beirut 2005") == []     # a reference, not a date


def test_section_heads():
    assert J.ACK_HEAD.match("شكر وتقدير") and J.ACK_HEAD.match("Acknowledgements")
    assert not J.ACK_HEAD.match("مقتضى النعمة شكرها")
    assert J.APP_HEAD.match("الملاحق") and J.APP_HEAD.match("ملحق رقم (1)") and J.APP_HEAD.match("Appendix A")
    assert J.ABSTRACT_HEAD.match("الملخص") and J.ABSTRACT_HEAD.match("Abstract")


def test_keywords_and_affiliation_parts():
    sl = object.__new__(J.Slots)
    sl.lang, sl.st = "ar", Counter()
    kg = sl.kwd_group("الكلمات المفتاحية: الفقر، النمو الاقتصادي، GLS.", "ar", "p1b8")
    assert kg.findtext("title") == "الكلمات المفتاحية:" and [k.text for k in kg] [1:] == ["الفقر", "النمو الاقتصادي", "GLS"]
    sp = J.Slots.no_overlap(sl.guess_aff("كلية الآداب، جامعة المرقب (ليبيا)"))
    assert [(t, c) for _, _, t, c in sp] == [("institution", "dept"), ("institution", "orgname"), ("country", None)]


def test_v3_types():
    ans = {"pages": [{"page": 1, "blocks": [{"type": "title", "lines": ["1:4"], "translated": True, "lang": "en"},
                                            {"type": "boxed", "lines": ["1:9"], "box": 2}]}]}
    out, log = RU.normalize(ans, {"1:4": dict(text="Poverty", b=[0, 0, 100, 10], page=1),
                                  "1:9": dict(text="١٠ ساعات", b=[0, 20, 100, 30], page=1)})
    b = out["pages"][0]["blocks"]
    assert b[0]["type"] == "trans_title" and b[1]["type"] == "boxed" and b[1]["level"] == "2"
    assert log["trans_titles"] == 1 and log["boxed_blocks"] == 1


def test_edition_reads_ack_and_appendix():
    from inkscript.edition.model import read_body
    art = etree.fromstring('<article><body><p id="a">نص</p></body><back><ack><title>شكر وتقدير</title><p id="b">شكرا'
                           '</p></ack><app-group><app><title>ملحق</title><p id="c">جدول</p></app></app-group></back>'
                           '</article>')
    body, *_ = read_body(art)
    assert [n.id for n in body if n.kind == "p"] == ["a", "b", "c"]
