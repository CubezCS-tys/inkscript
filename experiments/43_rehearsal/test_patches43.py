"""Experiment 43: the patch layer (patches43.py). The build test uses a real article of the 300's answers."""
import copy
import json
import sys
import tempfile
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import patches43 as PA  # noqa: E402


def answers():
    return {"x_c001-002.json": dict(first=1, last=2, answer=dict(noise=["1:9"], pages=[
        dict(page=1, blocks=[
            dict(type="title", lines=["1:1"]),
            dict(type="other", lines=["1:2", "1:3"], from_noise=True),
            dict(type="paragraph", lines=["1:4", "1:5", "1:6"], calls=[dict(line="1:5", marker="(1)", fn="fn-1")]),
            dict(type="figure", box=[100, 100, 300, 300], lines=[]),
            dict(type="footnote", lines=["1:7"], id="fn-1", marker="(1)"),
        ]),
        dict(page=2, blocks=[dict(type="paragraph", lines=["2:1"]), dict(type="paragraph", lines=["2:2"])]),
    ]))}


def P(action, page=1, source="judge", lines=None, blocks=None, created="2026-10-20", pid=None, **payload):
    return dict(id=pid or f"t-{action}-{source}", run="t", article="x", page=page, action=action, source=source,
                targets=dict(lines=lines or [], blocks=blocks or []), payload=payload, apply=True, created=created)


def blk(ans, page, k):
    return ans["x_c001-002.json"]["answer"]["pages"][page - 1]["blocks"][k]


def fp(b):
    return dict(id="b", **PA.fingerprint(b))


def test_no_patch_is_identity():
    a = answers()
    out, log = PA.apply_all(a, [])
    assert out == a and log == []
    p = P("mark_noise", lines=["1:2", "1:3"], kind="show-through")
    p["apply"] = False                       # a proposal not applied changes nothing
    assert PA.apply_all(a, [p])[0] == a


def test_mark_noise_removes_block_and_logs_kind():
    a = answers()
    out, log = PA.apply_all(a, [P("mark_noise", lines=["1:2", "1:3"], kind="show-through")])
    pg = out["x_c001-002.json"]["answer"]
    assert [b["type"] for b in pg["pages"][0]["blocks"]] == ["title", "paragraph", "figure", "footnote"]
    assert "1:2" in pg["noise"] and pg["_noise_kinds"]["1:3"] == "show-through"
    assert log[0]["applied"] and a == answers()          # the input is not touched


def test_mark_noise_drops_call_on_line():
    out, _ = PA.apply_all(answers(), [P("mark_noise", lines=["1:5"], kind="scanner-junk")])
    b = blk(out, 1, 2)
    assert b["lines"] == ["1:4", "1:6"] and b["calls"] == []


def test_set_kind_and_other_article_roundtrip():
    a = answers()
    t = [fp(blk(a, 1, 1))]
    out, _ = PA.apply_all(a, [P("mark_other_article", blocks=t)])
    assert blk(out, 1, 1)["type"] == "other_article"
    out2, _ = PA.apply_all(out, [P("unmark_other_article", blocks=[fp(blk(out, 1, 1))])])
    assert blk(out2, 1, 1)["type"] == "other"
    out3, _ = PA.apply_all(a, [P("set_kind", blocks=[fp(blk(a, 1, 0))], kind="heading")])
    assert blk(out3, 1, 0)["type"] == "heading" and blk(out3, 1, 0)["level"] == 2


def test_split_merge_reorder_box_relink():
    a = answers()
    out, _ = PA.apply_all(a, [P("split_block", blocks=[fp(blk(a, 1, 2))], at_line="1:5")])
    assert blk(out, 1, 2)["lines"] == ["1:4"] and blk(out, 1, 3)["lines"] == ["1:5", "1:6"]
    assert blk(out, 1, 3)["calls"][0]["fn"] == "fn-1" and not blk(out, 1, 2).get("calls")
    out, _ = PA.apply_all(a, [P("merge_blocks", page=2, blocks=[fp(blk(a, 2, 0)), fp(blk(a, 2, 1))])])
    assert out["x_c001-002.json"]["answer"]["pages"][1]["blocks"] == [dict(type="paragraph", lines=["2:1", "2:2"])]
    f = {f"p2b{i + 1}": PA.fingerprint(blk(a, 2, i)) for i in range(2)}
    out, _ = PA.apply_all(a, [P("reorder", page=2, order=["p2b2", "p2b1"], fp=f)])
    assert [b["lines"] for b in out["x_c001-002.json"]["answer"]["pages"][1]["blocks"]] == [["2:2"], ["2:1"]]
    out, _ = PA.apply_all(a, [P("fix_picture_box", blocks=[fp(blk(a, 1, 3))], box=[90, 90, 310, 280])])
    assert blk(out, 1, 3)["box"] == [90, 90, 310, 280]
    out, _ = PA.apply_all(a, [P("relink_call", blocks=[fp(blk(a, 1, 2))], line="1:5", marker="(1)", fn="fn-2")])
    assert blk(out, 1, 2)["calls"][0]["fn"] == "fn-2"


def test_precedence_person_over_judge():
    a = answers()
    t = [fp(blk(a, 1, 1))]
    j = P("set_kind", blocks=t, kind="paragraph", source="judge", created="2026-10-19")
    h = P("mark_other_article", blocks=t, source="person", created="2026-10-21")
    out, log = PA.apply_all(a, [j, h])
    assert blk(out, 1, 1)["type"] == "other_article"
    assert [e["applied"] for e in log] == [True, False] and "overridden" in log[1]["why"]


def test_stale_target_skipped():
    a = answers()
    out, log = PA.apply_all(a, [P("set_kind", blocks=[dict(id="p1b9", lines=["1:99"])], kind="heading")])
    assert out == a and not log[0]["applied"]


STEM = "0744-000-059-007"


@pytest.mark.skipif(not (PA.OUT / "v33_300" / "rules" / f"{STEM}_c001-004.json").exists(), reason="run not here")
def test_build_off_equals_build_without_layer():
    """patch off = identical master: build43 on the run's answers vs patches43.build --off (stamps stripped)."""
    import masters43 as M43
    import run43
    M43.ST.PAGES = PA.OUT / "pages"
    a = next(x for x in run43.articles("b") if x["stem"] == STEM)
    with tempfile.TemporaryDirectory() as td:
        td = Path(td)
        M43.build43(a, PA.OUT / "v33_300" / "rules", td / "plain" / "masters", True, run="t")
        (td / "j" / "patches").mkdir(parents=True)
        p = P("mark_noise", lines=["1:1", "1:2"], kind="show-through")
        PA.save_patches(td / "j" / "patches", STEM, [dict(p, article=STEM)])
        PA.build("v33_300", td / "j", [STEM], off=True)
        for ext in ("jats.xml", "alto.xml"):
            x = (td / "plain" / "masters" / f"{STEM}.{ext}").read_bytes()
            y = (td / "j" / "masters" / f"{STEM}.{ext}").read_bytes()
            assert M43.strip_stamp(x) == M43.strip_stamp(y), ext
        PA.build("v33_300", td / "j", [STEM])                      # on: the two lines leave the text
        y = (td / "j" / "masters" / f"{STEM}.jats.xml").read_bytes()
        assert b"pipeline-patches" in y and M43.strip_stamp(x) != M43.strip_stamp(y)
        log = json.loads((td / "j" / "masters" / f"{STEM}.patches.json").read_text())
        assert log["applied"][0]["id"] == p["id"]
        from inkscript.enrich.schemas import validate_jats
        assert not validate_jats(td / "j" / "masters" / f"{STEM}.jats.xml")


# ------------------------------------------------------------------ correction tool v1: a person's word fixes and chains

def test_fix_word_person_only_and_kinds():
    a = answers()
    a["x_c001-002.json"]["answer"]["fixes"] = [dict(line="1:4", **{"from": "جماو الكبير", "to": "جمار الكبير"}, why="g")]
    j = P("fix_word", source="judge", line="1:4", kind="misread", to="x", **{"from": "y"})
    out, log = PA.apply_all(a, [j])
    assert out == a and not log[0]["applied"] and "person" in log[0]["why"]
    h = P("fix_word", source="person", line="1:4", kind="misread", to="جمال", **{"from": "جماو"})
    out, log = PA.apply_all(a, [h])
    fx = out["x_c001-002.json"]["answer"]["fixes"]
    assert log[0]["applied"] and len(fx) == 1 and fx[0]["from"] == "جماو" and fx[0]["to"] == "جمال"
    assert fx[0]["_was"][0]["to"] == "جمار الكبير"                 # the model's fix it replaced is kept beside it
    m = P("fix_word", source="person", line="1:6", kind="misprint", to="وإرثه", pid="m", **{"from": "ووإرثه"})
    out, _ = PA.apply_all(a, [m])
    ans = out["x_c001-002.json"]["answer"]
    assert ans["sic"] == [dict(line="1:6", text="ووإرثه", corr="وإرثه", why="person", source="person")]
    assert ans["fixes"] == a["x_c001-002.json"]["answer"]["fixes"]     # D30: the printed text stays
    back = P("fix_word", source="person", line="1:4", kind="misread", to="جماو", pid="b", **{"from": "جماو"})
    assert PA.apply_all(a, [back])[0]["x_c001-002.json"]["answer"]["fixes"] == []   # Azure was right


def test_person_chain_and_word_fix_beside_structure():
    a = answers()
    s = P("split_block", source="person", blocks=[fp(blk(a, 1, 2))], at_line="1:5", created="2026-10-20T10:00:01", pid="h1")
    k = P("set_kind", source="person", blocks=[dict(id="b", lines=["1:5", "1:6"], type="paragraph")], kind="quote",
          created="2026-10-20T10:00:02", pid="h2")
    w = P("fix_word", source="person", line="1:5", kind="misread", to="b", created="2026-10-20T10:00:03", pid="h3",
          **{"from": "a"})
    j = P("mark_noise", source="judge", lines=["1:6"], kind="scanner-junk", pid="j1")
    out, log = PA.apply_all(a, [j, s, k, w])
    assert [e["applied"] for e in log] == [True, True, True, False]      # person's three, then the judge overridden
    assert blk(out, 1, 3)["type"] == "quote" and blk(out, 1, 3)["lines"] == ["1:5", "1:6"]
