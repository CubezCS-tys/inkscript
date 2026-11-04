"""Prompt v3.5 (draft): the "enrich" part checked by rules43 (enrich43.check) and the new keys of a cited work
(refs43.v35_parts). The answers below are SIMULATED (hand-made; no model was called)."""
from __future__ import annotations

import copy
import sys
from collections import Counter
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "41_azure_structure"))
import enrich43  # noqa: E402
import refs43  # noqa: E402

LINES = {"1:1": dict(text="ندوة خبراء", b=[0, 0, 1, 1], page=1),
         "1:2": dict(text="الكويت ٢٠ -٢٥ نوفمبر ١٩٧٦", b=[0, 0, 1, 1], page=1),
         "1:3": dict(text="* Corresponding author: Mouloud Mammeri University", b=[0, 0, 1, 1], page=1),
         "2:5": dict(text="المصدر: من إعداد الباحث", b=[0, 0, 1, 1], page=2)}
SIMULATED = {"pages": [{"page": 2, "blocks": [{"type": "figure", "box": [100, 100, 500, 400], "lines": []},
                                              {"type": "figure", "box": [100, 500, 500, 800], "lines": []},
                                              {"type": "paragraph", "lines": ["2:5"]}]}],
             "fixes": [],
             "enrich": {"doc_type": "conference_paper", "conference": {"name": "مؤتمر لم يطبع", "place": "الكويت",
                                                                       "date": "٢٠ -٢٥ نوفمبر ١٩٧٦"},
                        "authors": [{"a": 1, "corresp": True, "note": ["1:3", "9:9"], "orcid": "0000-0001-2345-6789"},
                                    {"name": "no number"}],
                        "figures": {"2": ["map", "selfie"]},
                        "table_notes": [{"of": "f2.2", "lines": ["2:5"], "kind": "source"}],
                        "scan": {"2": ["cut_edge", "coffee"]}, "colour": "red"}}


def test_check_keeps_checked_values_and_logs_the_rest():
    ans, log = copy.deepcopy(SIMULATED), {}
    enrich43.check(ans, LINES, log)
    E = ans["enrich"]
    assert E["doc_type"] == "conference_paper"
    assert E["conference"] == {"place": "الكويت", "date": "٢٠ -٢٥ نوفمبر ١٩٧٦"}      # the name is not printed here
    assert E["authors"] == [{"a": 1, "corresp": True, "note": ["1:3"]}]               # ORCID not printed; 9:9 not here
    blocks = ans["pages"][0]["blocks"]
    assert blocks[0]["_kind"] == "map" and blocks[1]["_kind"] == "other"              # unknown kind -> other
    assert E["table_notes"] == [{"lines": ["2:5"], "kind": "source", "fig": {"page": 2, "box": [100, 500, 500, 800]}}]
    assert E["scan"] == {"2": ["cut_edge"]}
    why = {d["key"] for d in log["enrich"]}
    assert {"conference.name", "authors.orcid", "authors.note", "authors", "colour"} <= why


def test_older_answers_untouched():
    ans, log = {"pages": [], "fixes": []}, {}
    enrich43.check(ans, LINES, log)                     # rules43 only calls check when "enrich" is in the answer
    assert ans == {"pages": [], "fixes": [], "enrich": {}} or "enrich" not in log
    assert enrich43.apply(None, None, answers=[{"pages": []}]) == Counter()


def test_v35_work_keys_and_v33_work_unchanged():
    printed = ("ابن هشام الأنصاري (ت 761هـ): أوضح المسالك، تحقيق محيي الدين عبد الحميد، ط5، بيروت، 1966م / 1386هـ، "
               "ص 32. Retrieved 12 May 2020")
    v33 = {"type": "book", "authors": [{"surname": "ابن هشام الأنصاري"}], "title": "أوضح المسالك", "year": "1966م",
           "place": "بيروت", "pages": "ص 32"}
    v35 = dict(v33, authors=[{"surname": "ابن هشام الأنصاري", "died": "761هـ"}],
               editors=[{"surname": "محيي الدين عبد الحميد"}], edition="ط5", year2="1386هـ", cited="ص 32",
               accessed="12 May 2020", translators=[{"surname": "not printed"}])
    del v35["pages"]
    st = Counter()
    a = refs43.citation(v33, printed, st, "ar")
    st2 = Counter()
    b = refs43.citation(copy.deepcopy(v33), printed, st2, "ar")
    assert etree.tostring(a) == etree.tostring(b) and not any(k.startswith("refs_v35") for k in st)
    st3 = Counter()
    c = refs43.citation(v35, printed, st3, "ar")
    x = etree.tostring(c, encoding="unicode")
    assert '<person-group person-group-type="editor"><name><surname>محيي الدين عبد الحميد</surname>' in x
    assert '<comment content-type="death-date">761هـ</comment>' in x and "<edition>ط5</edition>" in x
    assert '<year calendar="gregorian">1966م</year><year calendar="islamic">1386هـ</year>' in x
    assert '<page-range content-type="cited-pages">32</page-range>' in x and "<fpage>" not in x
    assert '<date-in-citation content-type="access-date">12 May 2020</date-in-citation>' in x
    assert "translator" not in x and st3["refs_dropped_not_printed_translators"] == 1
