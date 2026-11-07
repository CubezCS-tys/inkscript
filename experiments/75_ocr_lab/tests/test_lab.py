"""Experiment 75 tests: schemas, the JSONL protocol (fixture worker), Unicode round-trip, runs (resume after a crash,
failures kept), leakage, evaluation basics, annotation revisions.

    cd experiments/75_ocr_lab && /home/appuser/inkscript/.venv/bin/python -m pytest -q tests
All synthetic: no Mandumah page, no model, no network.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(HERE))

from labocr import annotations as A  # noqa: E402
from labocr import evaluation as EV  # noqa: E402
from labocr import ingest as I  # noqa: E402
from labocr import runs as R  # noqa: E402
from labocr.adapters.normalise import html_table_cells, normalise_paddle, normalise_text  # noqa: E402
from labocr.adapters.transport import SubprocessAdapter, WorkerError  # noqa: E402
from labocr.schemas import (Block, EngineConfig, ManifestEntry, PagePrediction, PageRequest,  # noqa: E402
                            PredictionResult, TruthLine, TruthPage, TruthRegion)

FIXTURE = [sys.executable, str(HERE / "workers" / "fixture_worker.py")]
MIXED = "قال «الإسنادُ» في ص ٣٩٦ — see p. 12, éàç; ‏مِنْ‏ 2023"


def make_image(root: Path, name="page.png", w=200, h=300) -> Path:
    import cv2
    import numpy as np
    a = np.full((h, w), 255, np.uint8)
    a[100:120, 20:180] = 0
    p = root / "in" / name
    p.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(p), a)
    return p


def dataset(root: Path, page_ids=("doc_ok",)) -> list[str]:
    entries = []
    for i, d in enumerate(page_ids):
        src = I.ingest_source(make_image(root, f"{d}.png", w=200 + i), root)
        rr = I.render_page(src, root, 1)
        entries.append(ManifestEntry(dataset="t", document_id=d, page_id=I.page_id_of(d, 1), page_number=1,
                                     source_id=src.source_id, render_id=rr.render_id, category="synthetic",
                                     provenance="test", usage="test"))
    I.write_manifest(root, "t", entries)
    return [e.page_id for e in entries]


# ------------------------------------------------------------------------------------------------ schemas

def test_page_numbers_are_one_based():
    with pytest.raises(Exception):
        ManifestEntry(dataset="t", document_id="d", page_id="d_p000", page_number=0, source_id="s", category="c",
                      provenance="p", usage="u")


def test_failed_prediction_needs_error():
    with pytest.raises(Exception):
        PredictionResult(request_id="q", page_id="p", status="failed")


def test_parent_cycle_rejected():
    with pytest.raises(Exception):
        PredictionResult(request_id="q", page_id="p", status="succeeded",
                         blocks=[Block(block_id="a", type="paragraph", parent="b"),
                                 Block(block_id="b", type="paragraph", parent="a")])


def test_bad_box_rejected():
    with pytest.raises(Exception):
        Block(block_id="a", type="paragraph", box=[10, 10, 5, 20])


def test_truth_order_must_cover_lines():
    with pytest.raises(Exception):
        TruthPage(page_id="p", document_id="d", page_number=1, width=1, height=1, revision="r", status="s",
                  provenance="x", lines=[TruthLine(line_id="a", text="x")], order=["a", "b"])


# ------------------------------------------------------------------------------------------------ Unicode

def test_unicode_round_trip_through_protocol(tmp_path):
    """Mixed Arabic/Latin, combining marks, Arabic-Indic digits and bidi marks survive JSON, pydantic and the
    subprocess pipe unchanged (no reversal, no normalisation)."""
    b = Block(block_id="b", type="paragraph", raw_text=MIXED)
    back = Block.model_validate_json(b.model_dump_json())
    assert back.raw_text == MIXED
    assert json.loads(json.dumps(MIXED, ensure_ascii=False)) == MIXED
    img = make_image(tmp_path)
    ad = SubprocessAdapter(FIXTURE)
    try:
        ad.load(EngineConfig(engine="fixture"))
        res = ad.predict(PageRequest(request_id="q1", page_id="x_p001", page_number=1, render_id="r", width=200,
                                     height=300, image_path=str(img)))
    finally:
        ad.close()
    assert "«الإسناد»" in res.blocks[0].raw_text and "٣٩٦" in res.blocks[0].raw_text and "éàç" in res.blocks[0].raw_text


def test_raw_policy_keeps_letter_forms():
    f = EV.POLICIES["raw"]
    for a, b in [("أ", "ا"), ("ى", "ي"), ("ة", "ه"), ("٣", "3"), ("مِن", "من")]:
        assert f(a) != f(b)
    assert EV.POLICIES["folded"]("أ") == EV.POLICIES["folded"]("ا")
    assert EV.POLICIES["folded"]("٣٩٦") == "396"


# ------------------------------------------------------------------------------------------------ protocol

def test_protocol_capabilities_health_and_fixture_label(tmp_path):
    ad = SubprocessAdapter(FIXTURE)
    try:
        caps = ad.capabilities()
        assert caps.is_fixture
        assert ad.health().ok
    finally:
        ad.close()
    assert ad.proc.poll() is not None


def test_protocol_structured_failure_and_timeout(tmp_path):
    img = make_image(tmp_path)
    ad = SubprocessAdapter(FIXTURE, timeouts={"predict": 2})
    try:
        ad.load(EngineConfig(engine="fixture"))
        with pytest.raises(WorkerError) as e:
            ad.predict(PageRequest(request_id="q", page_id="fail_p001", page_number=1, render_id="r", width=1,
                                   height=1, image_path=str(img)))
        assert e.value.error.kind == "other"
        with pytest.raises(WorkerError) as e:
            ad.predict(PageRequest(request_id="q2", page_id="hang_p001", page_number=1, render_id="r", width=1,
                                   height=1, image_path=str(img)))
        assert e.value.error.kind == "timeout"
        assert ad.proc.poll() is not None          # terminated by its own PID
    finally:
        ad.close()


def test_argv_must_be_a_list():
    with pytest.raises(TypeError):
        SubprocessAdapter("python worker.py")      # type: ignore[arg-type]


# ------------------------------------------------------------------------------------------------ runs

def test_run_resume_after_crash_keeps_finished_pages(tmp_path):
    root = tmp_path / "data"
    pids = dataset(root, ("a_ok", "b_crash", "c_fail", "d_empty"))
    marker = tmp_path / "crashed_once"
    import os
    os.environ["FIXTURE_CRASH_ONCE"] = str(marker)
    try:
        rid = R.create_run(root, "t", EngineConfig(engine="fixture"), FIXTURE, is_fixture=True)
        s = R.execute_run(root, rid, max_attempts=2, log=lambda m: None)
    finally:
        os.environ.pop("FIXTURE_CRASH_ONCE", None)
    st = {p["page_id"]: p for p in s["page_states"]}
    assert st["a_ok_p001"]["state"] == "succeeded" and st["a_ok_p001"]["attempts"] == 1
    assert st["b_crash_p001"]["state"] == "succeeded" and st["b_crash_p001"]["attempts"] == 2   # retried after crash
    assert st["c_fail_p001"]["state"] == "failed" and st["c_fail_p001"]["attempts"] == 2        # bounded retries
    assert st["d_empty_p001"]["state"] == "succeeded"
    crash_atts = [a for a in s["attempt_log"] if a["page_id"] == "b_crash_p001"]
    assert crash_atts[0]["error_kind"] == "worker_crash"
    preds = R.load_predictions(root, rid)
    assert preds["d_empty_p001"].result.empty and not preds["a_ok_p001"].result.empty
    # resume: nothing to redo for finished pages; artifacts untouched
    before = (root / preds["a_ok_p001"].raw_artifact).read_bytes()
    s2 = R.execute_run(root, rid, max_attempts=2, log=lambda m: None)
    assert s2["succeeded"] == 3 and (root / preds["a_ok_p001"].raw_artifact).read_bytes() == before


def test_stale_running_page_is_reconciled(tmp_path):
    root = tmp_path / "data"
    dataset(root, ("a_ok",))
    rid = R.create_run(root, "t", EngineConfig(engine="fixture"), FIXTURE, is_fixture=True)
    con = R.connect(root)
    con.execute("UPDATE pages SET state='running', attempts=1 WHERE run_id=?", (rid,))
    con.execute("INSERT INTO attempts (attempt_id, run_id, page_id, n, started_at, status) VALUES (?,?,?,?,?,?)",
                ("x", rid, "a_ok_p001", 1, "t", "running"))
    con.commit()
    assert R.reconcile(con, rid) == 1
    assert con.execute("SELECT status FROM attempts WHERE attempt_id='x'").fetchone()[0] == "stale"


def test_fixture_worker_refused_for_a_real_run(tmp_path):
    root = tmp_path / "data"
    dataset(root, ("a_ok",))
    rid = R.create_run(root, "t", EngineConfig(engine="paddle_vl"), FIXTURE, is_fixture=False)
    s = R.execute_run(root, rid, max_attempts=1, log=lambda m: None)
    p = s["page_states"][0]
    assert p["state"] == "failed" and p["error_kind"] == "load_error" and "fixture" in p["error_message"]
    assert not R.load_predictions(root, rid)


def test_config_change_makes_a_new_run(tmp_path):
    root = tmp_path / "data"
    dataset(root, ("a_ok",))
    r1 = R.create_run(root, "t", EngineConfig(engine="fixture", settings={"max_new_tokens": 10}), FIXTURE, is_fixture=True)
    r2 = R.create_run(root, "t", EngineConfig(engine="fixture", settings={"max_new_tokens": 20}), FIXTURE, is_fixture=True)
    r3 = R.create_run(root, "t", EngineConfig(engine="fixture", settings={"max_new_tokens": 10}), FIXTURE, is_fixture=True)
    assert r1 != r2 and r1 == r3


def test_leakage_and_path_safety(tmp_path):
    e = dict(dataset="t", page_number=1, source_id="s", category="c", provenance="p", usage="u")
    es = [ManifestEntry(document_id="d1", page_id="d1_p001", split="dev", **e),
          ManifestEntry(document_id="d1", page_id="d1_p002", split="test", **dict(e, page_number=2)),
          ManifestEntry(document_id="d2", page_id="d2_p001", split="test", **e)]
    assert I.check_leakage(es) == ["d1"]
    with pytest.raises(ValueError):
        I.safe_child(tmp_path, "../etc/passwd")
    with pytest.raises(ValueError):
        I.page_id_of("../x", 1)


# ------------------------------------------------------------------------------------------------ normalisers

def test_paddle_normaliser_keeps_unmapped_labels_and_tables():
    doc = {"parsing_res_list": [
        {"block_label": "header", "block_content": "مجلة", "block_bbox": [1, 2, 30, 40]},
        {"block_label": "weird_new_label", "block_content": "x", "block_bbox": [1, 50, 30, 60]},
        {"block_label": "table", "block_content": "<table><tr><td rowspan=2>أ</td><td>ب</td></tr><tr><td>ج</td></tr></table>",
         "block_bbox": [1, 70, 30, 90]}]}
    blocks = normalise_paddle({"files": {"res0/x.json": json.dumps(doc, ensure_ascii=False)}}, "pipeline")
    assert [b.type for b in blocks] == ["header", "unknown", "table"]
    assert blocks[1].raw_label == "weird_new_label"
    cells = blocks[2].cells
    assert (cells[2].row, cells[2].col) == (1, 1) and cells[0].row_span == 2   # spatial order, span respected


def test_text_normaliser_has_no_boxes():
    blocks = normalise_text("# عنوان\nسطر\n\n<table><tr><td>1</td></tr></table>", markdown=True)
    assert [b.type for b in blocks] == ["heading", "text", "table"]
    assert all(b.box is None for b in blocks)


def test_html_cells_column_order_not_reversed():
    cells = html_table_cells("<table><tr><th>الاسم</th><th>العمر</th></tr></table>")
    assert [c.text for c in cells] == ["الاسم", "العمر"] and cells[0].header


# ------------------------------------------------------------------------------------------------ evaluation

def _truth():
    return TruthPage(page_id="p_p001", document_id="p", page_number=1, width=100, height=100, revision="r1",
                     status="test", provenance="test",
                     lines=[TruthLine(line_id="l1", text="مجلة الدراسات", box=[10, 5, 90, 10], region="r1"),
                            TruthLine(line_id="l2", text="قال الباحث إن النتائج دالة", box=[10, 20, 90, 30], region="r2"),
                            TruthLine(line_id="l3", text="وأظهرت الدراسة فروقاً", box=[10, 31, 90, 40], region="r2"),
                            TruthLine(line_id="l4", text="1 الهامش الأول", box=[10, 80, 90, 85], region="r3")],
                     order=["l1", "l2", "l3", "l4"],
                     regions=[TruthRegion(region_id="r1", type="header", coarse="furniture", box=[10, 5, 90, 10], order=0),
                              TruthRegion(region_id="r2", type="paragraph", coarse="body", box=[10, 20, 90, 40], order=1),
                              TruthRegion(region_id="r3", type="footnote", coarse="footnote", box=[10, 80, 90, 85], order=2)])


def _pred(blocks):
    return PagePrediction(run_id="r", attempt_id="a", document_id="p", page_number=1, page_id="p_p001",
                          render_id="x", width=100, height=100, engine="e", variant="v",
                          result=PredictionResult(request_id="q", page_id="p_p001", status="succeeded", blocks=blocks))


def test_perfect_prediction_scores_zero():
    t = _truth()
    p = _pred([Block(block_id="b0", type="header", box=[10, 5, 90, 10], raw_text="مجلة الدراسات", order=0),
               Block(block_id="b1", type="paragraph", box=[10, 20, 90, 40],
                     raw_text="قال الباحث إن النتائج دالة\nوأظهرت الدراسة فروقاً", order=1),
               Block(block_id="b2", type="footnote", box=[10, 80, 90, 85], raw_text="1 الهامش الأول", order=2)])
    ev = EV.evaluate_page(p, t)
    assert ev["recognition"]["raw"]["cer"]["rate"] == 0 and ev["recognition"]["raw"]["wer"]["rate"] == 0
    assert ev["layout"]["by_threshold"]["0.5"]["recall"] == 1 and ev["layout"]["by_threshold"]["0.5"]["class_recall"] == 1
    assert ev["reading_order"]["text_position"]["accuracy"] == 1
    assert ev["reading_order"]["block_order"]["accuracy"] == 1
    assert ev["completeness"]["found"] == 4


def test_hamza_error_counts_raw_but_not_folded_and_missing_footnote_is_visible():
    t = _truth()
    p = _pred([Block(block_id="b1", type="paragraph", box=[10, 20, 90, 40],
                     raw_text="مجلة الدراسات\nقال الباحث ان النتائج دالة\nوأظهرت الدراسة فروقاً", order=0)])
    ev = EV.evaluate_page(p, t)
    assert ev["recognition"]["raw"]["cer"]["sub"] >= 1                       # أ/ا counts as printed
    assert "l4" in ev["completeness"]["missing"]                              # the footnote is not silently dropped
    assert ev["recognition"]["raw"]["cer"]["dele"] > 0
    assert ev["layout"]["by_threshold"]["0.5"]["unmatched_truth"]             # header and footnote regions unmatched


def test_reversed_order_is_detected_and_cer_can_exceed_one():
    t = _truth()
    p = _pred([Block(block_id="b0", type="paragraph", raw_text="1 الهامش الأول", order=0),
               Block(block_id="b1", type="paragraph", raw_text="وأظهرت الدراسة فروقاً", order=1),
               Block(block_id="b2", type="paragraph", raw_text="قال الباحث إن النتائج دالة", order=2),
               Block(block_id="b3", type="paragraph", raw_text="مجلة الدراسات", order=3)])
    ev = EV.evaluate_page(p, t)
    assert ev["reading_order"]["text_position"]["accuracy"] == 0
    assert ev["layout"]["available"] is False                                 # no boxes: layout not scored
    long = EV.rate("x" * 50, "ab")
    assert long["rate"] > 1                                                    # unclamped
    assert EV.rate("x", "")["rate"] is None                                   # empty reference: null, not 0


def test_failed_page_stays_in_denominator():
    t = _truth()
    m = EV.micro([dict(page_id="p_p001", status="failed")], {"p_p001": t})
    assert m["cer"] == 1.0 and m["wer"] == 1.0


def test_markup_policy_unwraps_latex_note_calls():
    assert EV.POLICIES["markup_stripped"]("التخصص.$^{1}$") == EV.POLICIES["markup_stripped"]("التخصص.1")
    assert EV.POLICIES["raw"]("التخصص.$^{1}$") != EV.POLICIES["raw"]("التخصص.1")


# ------------------------------------------------------------------------------------------------ annotations

def test_annotation_revisions_append_only(tmp_path):
    body = A.AnnotationBody(lines=[A.AnnLine(line_id="l1", text="نص", region="r1")],
                            regions=[A.AnnRegion(region_id="r1", type="paragraph", box=[0, 0, 10, 10])],
                            started_from="run_x")
    r1 = A.save(tmp_path, "p_p001", body, "owner", "1")
    body2 = body.model_copy(update={"lines": [A.AnnLine(line_id="l1", text="نصّ", region="r1")]})
    r2 = A.save(tmp_path, "p_p001", body2, "owner", "1")
    assert (r1["rev_no"], r2["rev_no"]) == (1, 2) and r2["parent"] == r1["revision_id"]
    assert A.get(tmp_path, r1["revision_id"])["body"]["lines"][0]["text"] == "نص"     # the old revision is untouched
    assert A.latest(tmp_path, "p_p001")["body"]["lines"][0]["text"] == "نصّ"
    t = A.to_truth(A.latest(tmp_path, "p_p001"), "p", 1, 100, 100)
    assert t.lines[0].text == "نصّ" and t.regions[0].coarse == "body"


def test_annotation_rejects_bad_input(tmp_path):
    with pytest.raises(Exception):
        A.AnnRegion(region_id="r", type="script", box=[0, 0, 1, 1])
    with pytest.raises(Exception):
        A.AnnLine(line_id="../x", text="a")
    with pytest.raises(ValueError):
        A.save(tmp_path, "../../etc", A.AnnotationBody(lines=[]), "x", None)


def test_unreadable_lines_left_out_of_truth(tmp_path):
    body = A.AnnotationBody(lines=[A.AnnLine(line_id="l1", text="نص"),
                                   A.AnnLine(line_id="l2", text="???", unreadable=True, reason="stain")])
    r = A.save(tmp_path, "p_p001", body, "owner", None)
    t = A.to_truth(r, "p", 1, 10, 10)
    assert [ln.line_id for ln in t.lines] == ["l1"]


def test_repetition_flag_means_a_loop_not_a_repeated_phrase():
    phrase = "نحو الدمج التربوي لذوي الاحتياجات الخاصة"
    assert not EV.repetition_flag(f"{phrase} في المدارس ثم {phrase} وأيضا {phrase} انتهى")
    assert EV.repetition_flag("بداية " + " ".join([phrase] * 3) + " نهاية")
