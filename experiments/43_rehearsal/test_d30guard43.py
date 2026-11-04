"""Experiment 66: unit tests of the D30 guard (d30guard43.py). No data needed: a tiny word list stands in for
wordlist43's.   .venv/bin/pytest -q experiments/43_rehearsal/test_d30guard43.py"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import d30guard43 as G  # noqa: E402
import wordlist43 as WL  # noqa: E402

W = {WL.fold(w): 10 for w in ["حال", "مال", "تلك", "ثمر", "ممر", "متخصصة", "تعليم", "first", "الرجلين", "على",
                               "علم", "الأرض", "سيدنا", "كتاب"]}


def lines_words(text, confs):
    lines = {"3:8": {"text": text, "b": [0, 0, 100, 10], "page": 3}}
    ws = [{"text": t, "box": [0, 0, 1, 1], "conf": c} for t, c in zip(text.split(), confs)]
    return lines, (lambda lid: ws)


def test_edit_classes():
    assert G.edit_class("حال", "مال") == "ar_swap"
    assert G.edit_class("ثلك", "تلك") == "dots"
    assert G.edit_class("أيامم", "أيامهم") == "ar_indel"
    assert G.edit_class("إلى", "الى") == "hamza"
    assert G.edit_class("فى", "في") == "ya_alif_maqsura"
    assert G.edit_class("جامعة", "جامعه") == "ta_marbuta"
    assert G.edit_class("الطبی", "الطبي") == "persian"
    assert G.edit_class("((انظر", "«انظر") == "punct"
    assert G.edit_class("١٩٦٨/٦/٢٠٦", "١٩٦٨/٦/٢٦") == "digits"
    assert G.edit_class("ه", "٥") == "digit_letter"
    assert G.edit_class("المتوسطر", "المتوسط(") == "letter_mark"
    assert G.edit_class("Clement", "Clément") == "latin_accent"
    assert G.edit_class("first", "firsf") == "latin_swap"
    assert G.edit_class("وتحس ـين", "وتحسين") == "tashkeel"
    assert G.edit_class("ال كتاب", "الكتاب") == "spacing"


def test_prefix_and_added():
    assert G.al_prefix("التلامذة", "لتلامذة") and G.al_prefix("العبارة", "للعبارة")
    assert not G.al_prefix("وما لله", "وما الله")          # the word الله / لله is never this class
    assert not G.al_prefix("حال", "مال")
    assert G.adds_tokens(": مجموع", "R_i : مجموع") and not G.adds_tokens("حال", "مال")


def test_refuse_sure_letter_edit_into_a_word():
    lines, words = lines_words("الاخيرة ، حال نحو تطبيق", [0.99, 0.99, 0.988, 0.99, 0.99])
    ans = {"fixes": [{"line": "3:8", "from": "حال", "to": "مال", "why": "mim not ha"}]}
    log = {}
    refused = G.guard(ans, lines, words, log, W)
    assert len(refused) == 1 and ans["fixes"] == [] and log["fixes_refused_d30"] == refused
    s = ans["sic"][0]
    assert s["text"] == "حال" and s["corr"] == "مال" and s["kind"] == "model-suggestion" and s["line"] == "3:8"
    assert "D30 guard" in s["why"] and "mim not ha" in s["why"]


def test_printed_misprint_becomes_a_flag():
    lines, words = lines_words("برفضها لكل ثلك الفضائل", [0.99, 0.99, 0.973, 0.99])
    ans = {"fixes": [{"line": "3:8", "from": "ثلك", "to": "تلك", "why": "ta not tha"}], "sic": []}
    G.guard(ans, lines, words, None, W)
    assert ans["fixes"] == [] and ans["sic"][0]["text"] == "ثلك"


def test_kept():
    lines, words = lines_words("ينفق بسورة عشوائية فى المدفع", [0.99, 0.62, 0.99, 0.99, 0.99])
    fixes = [
        {"line": "3:8", "from": "بسورة", "to": "بصورة"},                 # Azure unsure (0.62)
        {"line": "3:8", "from": "فى", "to": "في"},                         # ya / alif maqsura: orthographic
        {"line": "3:8", "from": "عشوائية", "to": "عشوائيه"},               # ta marbuta
        {"line": "3:8", "from": "المدفع", "to": "المدفغ"},                 # into a non-word: a misprint written as printed
        {"line": "3:8", "from": "ينفق", "to": "ينفق", "why": "code: letters43"},
    ]
    ans = {"fixes": [dict(f) for f in fixes]}
    assert G.guard(ans, lines, words, None, W) == []
    assert len(ans["fixes"]) == 5 and "sic" not in ans


def test_no_words_or_no_lexicon_refuses_nothing():
    lines, _ = lines_words("الاخيرة ، حال نحو", [0.99] * 4)
    ans = {"fixes": [{"line": "3:8", "from": "حال", "to": "مال"}]}
    assert G.guard(ans, lines, None, None, W) == []               # no Azure confidences: nothing refused
    lines, words = lines_words("الاخيرة ، حال نحو", [0.99] * 4)
    assert G.guard(ans, lines, words, None, {}) == []             # no word list: nothing refused


def test_split_line_and_latin():
    lines, words = lines_words("Sure first word", [0.99, 0.99, 0.99])
    ans = {"fixes": [{"line": "3:8a", "from": "first", "to": "firsf"}]}
    assert G.guard(ans, lines, words, None, W) == []               # Latin edits are left to the reader (README)
    f = G.features({"line": "3:8a", "from": "first", "to": "firsf"}, lines, words, W)
    assert f["conf_min"] == 0.99 and f["from_real"] is True and f["to_real"] is False
