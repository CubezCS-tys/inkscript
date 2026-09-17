"""Gemini's words into Azure's boxes on page 1."""
import re
from inkscript.ocr.azure import load_azure
from inkscript.ocr.align import page1_text
from inkscript.text import fold_digits


def test_page1_aligns(fixture):
    words, _, _ = load_azure(fixture["azure_dir"] / fixture["stem"] / f"{fixture['stem']}.json")
    p1 = [w for w in words if w["page"] == 1]
    texts, st = page1_text(p1, fold_digits(fixture["gemini_md"].read_text(encoding="utf-8")), 0.6)
    assert st["page1"] == "gemini"
    assert st["exact_of_azure"] > 0.95
    bare = re.sub(r"[\u064B-\u0652]", "", " ".join(texts))   # vowel marks off: their order varies between readers
    assert "السماء" in bare and "التيماء" not in bare            # the title Azure misread, corrected by Gemini


def test_title_backstop_when_page_fails(fixture):
    words, _, _ = load_azure(fixture["azure_dir"] / fixture["stem"] / f"{fixture['stem']}.json")
    p1 = [w for w in words if w["page"] == 1]
    texts, st = page1_text(p1, fold_digits(fixture["gemini_md"].read_text(encoding="utf-8")), 1.01)
    assert st["page1"] == "gemini-title" and texts is not None
