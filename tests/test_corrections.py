"""Corrections from exact sources (experiment 27): what is proposed, what is not, how the PDF takes it, and the
fixture end to end — an accepted correction written into the PDF's text, the ALTO, the JATS and the trust PDF,
the ink pixel-identical, and a second run changing nothing."""
import json
import shutil

import pytest

from inkscript.enrich.corrections import propose, ortho, corrected_text, overlay, load as load_log, save as save_log
from inkscript.enrich.document import load
from inkscript.enrich.judge import Judge, order, VERSION
from inkscript.enrich.quran import check_document
from inkscript.enrich.trust import assess, refine
from inkscript.pdf.correct import units_of

from test_enrich import azure_json, sig


def props_of(tmp_path, line, conf=None):
    doc = load(azure_json(tmp_path, [line], conf=conf))
    quotes = check_document(doc)
    return doc, quotes, *propose(doc, quotes)


def test_misreading_is_proposed_from_the_verse(tmp_path):
    doc, quotes, props, skipped = props_of(tmp_path, "﴿ الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدبن ﴾")
    assert [(p["was"], p["text"], p["kind"], p["ref"]) for p in props] == [("الدبن", "الدين", "dots", "1:4")]
    assert props[0]["id"] == doc["words"][[w["text"] for w in doc["words"]].index("الدبن")]["id"]


def test_authors_wording_and_spelling_are_not_proposed(tmp_path):
    # a و added before a verse word is the author's choice (و/ف), not a misreading
    _, _, props, skipped = props_of(tmp_path, "﴿ الحمد لله رب العالمين والرحمن الرحيم مالك يوم الدين ﴾")
    assert props == [] and any(s["category"] == "wording" for s in skipped)
    assert ortho("داود") == ortho("داوود") and ortho("فطرة") == ortho("فطرت") and ortho("مسؤولا") == ortho("مسئولا")
    assert ortho("رفير") != ortho("زفير")


def test_a_merge_keeps_the_prints_letters_and_gains_spaces(tmp_path):
    _, _, props, _ = props_of(tmp_path, "خالدين فيها ما دامت السماوات والأرض إلاماشاء ربك إن ربك فعال لما يريد")
    m = [p for p in props if p["kind"] == "merge"]
    assert len(m) == 1 and m[0]["text"] == "إلا ما شاء" and m[0]["was"] == "إلاماشاء"
    # dealt over glyphs: no glyph gets a bare space, and the units give the text back
    u = units_of("إلا ما شاء")
    assert "".join(u) == "إلا ما شاء" and all(x.strip() for x in u)
    assert corrected_text("﴿وَإِدْ", [dict(w="وإذ", v="وَإِذْ")]) == "﴿وَإِذْ"


def test_overlay_marks_corrected_and_quotation_equals_verse(tmp_path):
    doc, quotes, props, _ = props_of(tmp_path, "﴿ الحمد لله رب العالمين الرحمن الرحيم مالك يوم الدبن ﴾")
    marks = assess(doc, quotes)
    assert quotes[0]["differs"] == 1
    n = overlay(doc, marks, [dict(props[0], status="applied")], quotes)
    w = next(w for w in doc["words"] if w["id"] == props[0]["id"])
    assert n == 1 and w["out"] == "الدين" and marks[w["idx"]].mark == "corrected" and marks[w["idx"]].other == "الدبن"
    assert quotes[0]["differs"] == 0 and quotes[0]["corrected"] == 1


def test_fewer_false_flags_rule():
    lexicon = {"كلمة": 12}
    # a word flagged for confidence alone, read confidently in 5+ other documents, conf >= 0.6: not flagged
    assert refine(["conf"], sig(conf=0.7), dict(key="كلمة"), lexicon) == []
    assert refine(["conf"], sig(conf=0.5), dict(key="كلمة"), lexicon) == ["conf"]          # too unsure
    assert refine(["conf"], sig(conf=0.7), dict(key="نادرة"), lexicon) == ["conf"]         # not a common word
    assert refine(["conf", "speck"], sig(conf=0.7), dict(key="كلمة"), lexicon) == ["conf", "speck"]


def test_judge_order_is_blind_and_cached_answers_cost_nothing(tmp_path):
    flips = [order(f"item{i}", "a", "b")[2] for i in range(200)]
    assert 60 < flips.count("B") < 140 and order("x", "a", "b") == order("x", "a", "b")
    cache = tmp_path / "cache.jsonl"
    cache.write_text(json.dumps(dict(model="gemini-3.8-flash", id="w1" + VERSION, verdict="r2", raw="B", text="",
                                     why="dots", A="a", B="b")) + "\n")
    j = Judge("gemini-3.8-flash", cache, tmp_path / "spend.jsonl", cap=0.0)
    res = j.judge([dict(id="w1", scan=None, page=1, box=[0, 0, 1, 1], r1="a", r2="b")])
    assert res["w1"]["verdict"] == "r2" and j.spent() == 0.0 and not (tmp_path / "spend.jsonl").exists()


# ---------------------------------------------------------------- the fixture end to end

@pytest.fixture(scope="module")
def built(fixture, tmp_path_factory):
    from inkscript.cli import main
    out = tmp_path_factory.mktemp("fix")
    fx = fixture["azure_dir"].parent
    assert main(["native", "--azure-dir", str(fixture["azure_dir"]), "--scan-dir", str(fx / "input"),
                 "--frontpage-dir", str(fx / "frontpage"), "--out", str(out), "--vector", "--xml", "--trust"]) == 0
    return out


def test_fix_applies_an_accepted_correction_everywhere_and_only_once(built, fixture):
    import pypdfium2 as pdfium
    from inkscript.enrich.corrections import fix
    stem = fixture["stem"]
    out = built
    aj = fixture["azure_dir"] / stem / f"{stem}.json"
    doc = load(aj, out / f"{stem}.shapes.json")
    # a word of page 2 the PDF carries as Azure read it, given a (pretend) judged correction one letter longer
    w = next(w for w in doc["words"] if w["page"] == 2 and len(w["out"]) >= 4 and w["out"].isalpha() and w["glyphs"]
             and (w["conf"] or 0) > 0.9)
    new = w["out"] + "ة"
    log = out / f"{stem}.corrections.json"
    save_log(log, dict(runs=[], corrections=[dict(id=w["id"], page=w["page"], box=w["box"], was=w["out"], text=new,
                                                  kind="letters", source="test", ref="0:0", status="accepted",
                                                  judge=dict(model="test"))]))
    before = (out / f"{stem}_vector.pdf").read_bytes()
    r = fix(out, stem, aj, fixture["scan"], judge="none", apply=True, echo=lambda *a: None)
    run = r["run"]
    assert run["applied_now"] == 1 and run["statuses"].get("applied") == 1
    for name, v in run["ink"].items():                      # the drawing: same pixels, original bytes first
        assert v["ink_identical"] and v["prefix_identical"] and v["text_changed"] == [2], name
    assert run["enrich_problems"] in ([], None) or all("not validated" in p for p in run["enrich_problems"])
    t = pdfium.PdfDocument(str(out / f"{stem}_vector.pdf"))[1].get_textpage().get_text_range()
    assert new in t
    tt = pdfium.PdfDocument(str(out / f"{stem}_vector_trust.pdf"))[1].get_textpage().get_text_range()
    assert tt == t                                          # the trust copy reads like the corrected PDF
    alto = (out / f"{stem}.alto.xml").read_text(encoding="utf-8")
    s = alto[alto.index(f'ID="{w["id"]}"'):]
    s = s[:s.index("</String>")]
    assert f'CONTENT="{new}"' in s and "trust.corrected" in s and f'PURPOSE="azure-reading">{w["out"]}<' in s
    assert new in (out / f"{stem}.jats.xml").read_text(encoding="utf-8")
    # a second run: nothing new, the PDFs untouched
    after = (out / f"{stem}_vector.pdf").read_bytes()
    assert after[:len(before)] == before
    r2 = fix(out, stem, aj, fixture["scan"], judge="none", apply=True, echo=lambda *a: None)
    assert r2["run"]["applied_now"] == 0 and (out / f"{stem}_vector.pdf").read_bytes() == after
    assert len(load_log(log)["runs"]) == 2
