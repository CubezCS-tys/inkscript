"""Experiment 75: screenshots of /lab and a browser check of the correction flow (brief §16).

    PW=/home/appuser/inkscript/experiments/52_journal_gate1/out/pwvenv/bin/python
    $PW shots75.py real --token-file <owner token file>    # real lab, read-only: Compare, Correct start screen
    $PW shots75.py test                                     # test copy (labtest_app.py on :8155): start a correction,
                                                            # select an Arabic line, edit, save, reload, scores
Writes out/shots/*.png and out/shots/check_<phase>.json (what was checked, page errors).
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
WEB = "http://127.0.0.1:8154"
OUT = Path(__file__).resolve().parent / "out" / "shots"
OUT.mkdir(parents=True, exist_ok=True)
phase = sys.argv[1]
check = dict(phase=phase, time=time.strftime("%Y-%m-%dT%H:%M:%S"), steps=[])

with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=1)
    ctx.add_init_script("try{localStorage.setItem('desk_tour_done','1');localStorage.setItem('deskTourDone','1')}catch(e){}")
    if phase in ("real", "doc2", "doc3", "orderfree"):
        tok = Path(sys.argv[sys.argv.index("--token-file") + 1]).read_text().strip().split("\t")[-1]
        r = ctx.request.post(f"{WEB}/api/session", data=json.dumps({"token": tok}), headers={"Content-Type": "application/json"})
        assert r.ok, r.text()
    pg = ctx.new_page()
    errs = []
    pg.on("pageerror", lambda e: errs.append(str(e)))
    pg.on("dialog", lambda d: d.accept())

    def shot(name, full=False):
        pg.wait_for_timeout(800)
        pg.screenshot(path=str(OUT / f"{name}.png"), full_page=full)
        check["steps"].append(dict(shot=f"{name}.png"))

    pg.goto(f"{WEB}/lab?tab=compare", timeout=120000)
    pg.wait_for_selector("[data-testid=lab-engine-cards]", timeout=120000)
    pg.wait_for_selector("[data-testid=lab-scan] img", timeout=60000)
    if phase == "orderfree":
        pg.goto(f"{WEB}/lab?doc=doc3/0877-007-027-003_p004&tab=compare")
        pg.wait_for_selector("[data-testid=lab-disagree]", timeout=120000)
        shot("40_doc3_compare_orderfree")
        pg.locator("[data-testid=lab-disagree]").scroll_into_view_if_needed()
        shot("41_doc3_disagree_table")
        pg.goto(f"{WEB}/lab?doc=doc2/0018-010-003-002_p003&tab=scores")
        pg.wait_for_selector("[data-testid=lab-scores]", timeout=120000)
        shot("42_doc2_scores_orderfree")
        check["steps"].append(dict(warning_shown=pg.locator("[data-testid=lab-reader-warning]").count()))
    elif phase == "doc3":
        pg.click("[data-testid=lab-doc-doc3]")
        pg.wait_for_timeout(2500)
        pg.wait_for_selector("[data-testid=lab-scan] img", timeout=60000)
        pg.click("[data-testid=lab-layer-azure_read-existing]")
        pg.click("[data-testid=lab-layer-azure_argon-existing]")
        shot("30_doc3_argon_regions")
        pg.click("[data-testid=lab-layer-azure_argon-existing]")
        pg.click("[data-testid=lab-layer-paddle_vl-pipeline]")
        shot("31_doc3_paddle16_regions_order")
        pg.click("[data-testid=lab-layer-paddle_vl-pipeline]")
        pg.click("[data-testid=lab-layer-combo_paddle_nuqta-regions_speedfix_rtl]")
        shot("32_doc3_combination_rtl_rule")
        shot("33_doc3_full", full=True)
        pg.click("[data-testid=lab-show-dropped] input")
        pg.wait_for_timeout(800)
        shot("34_doc3_full_with_dropped", full=True)
        check["steps"].append(dict(engine_cards=pg.locator("[data-testid=lab-engine-card]").count()))
    elif phase == "doc2":
        pg.click("[data-testid=lab-doc-doc2]")
        pg.wait_for_timeout(2500)
        pg.wait_for_selector("[data-testid=lab-scan] img", timeout=60000)
        shot("20_doc2_compare")
        pg.click("[data-testid=lab-layer-azure_argon-existing]")
        pg.click("[data-testid=lab-layer-paddle_vl-pipeline]")
        shot("21_doc2_paddle16_regions")
        shot("22_doc2_full", full=True)
        pg.click("[data-testid=lab-doc-doc1]")
        pg.wait_for_timeout(2500)
        pg.goto(f"{WEB}/lab?doc=doc1/2399-003-008-002_p021&tab=scores")
        pg.wait_for_selector("[data-testid=lab-scores]", timeout=120000)
        shot("23_doc1_scores_owner_rev1")
        check["steps"].append(dict(switch_docs=pg.locator("[data-testid=lab-docs] button").count()))
    elif phase == "real":
        shot("01_compare")
        # switch on PaddleOCR-VL-1.6's regions and the layout stage alone
        pg.click("[data-testid=lab-layer-azure_read-existing]")
        pg.click("[data-testid=lab-layer-paddle_vl-pipeline]")
        shot("02_compare_paddle16_regions")
        pg.click("[data-testid=lab-layer-paddle_vl-pipeline]")
        pg.click("[data-testid=lab-layer-paddle_vl15_exp36-pipeline]")
        shot("03_compare_paddle15_regions")
        shot("04_compare_full", full=True)
        pg.goto(f"{WEB}/lab?tab=correct")
        pg.wait_for_selector("[data-testid=lab-start-text]")
        shot("05_correct_start")
        pg.goto(f"{WEB}/lab?tab=scores")
        pg.wait_for_timeout(1500)
        shot("06_scores_before_correction")
    else:
        pg.goto(f"{WEB}/lab?tab=correct")
        pg.wait_for_selector("[data-testid=lab-start-text]")
        opts = pg.eval_on_selector_all("[data-testid=lab-start-text] option", "els => els.map(e => [e.value, e.textContent])")
        azure = next(v for v, t in opts if t.startswith("Ours"))
        pg.select_option("[data-testid=lab-start-text]", azure)
        lay = pg.eval_on_selector_all("[data-testid=lab-start-layout] option", "els => els.map(e => [e.value, e.textContent])")
        p16 = next(v for v, t in lay if t.startswith("PaddleOCR-VL-1.6, full"))
        pg.select_option("[data-testid=lab-start-layout]", p16)
        pg.click("[data-testid=lab-start]")
        pg.wait_for_selector("[data-testid=lab-lines] li")
        shot("07_correct_draft")
        # select an Arabic line: its box lights up on the scan
        boxes = pg.locator("[data-testid=lab-line-text]")
        n_lines = boxes.count()
        third = boxes.nth(2)
        third.click()
        before = third.input_value()
        sel = pg.evaluate("() => { const t = document.querySelectorAll('[data-testid=lab-line-text]')[2]; t.setSelectionRange(0, 5); return t.value.substring(t.selectionStart, t.selectionEnd); }")
        check["steps"].append(dict(selected_first_5_chars=sel, logical_order_kept=before.startswith(sel)))
        lit = pg.locator("[data-box^='line:'][style*='2.5px']").count()
        check["steps"].append(dict(line_box_highlighted_on_scan=lit >= 1))
        # an edit: add a word at the end (test only; this copy is thrown away)
        third.fill(before + " ـتجربة")
        pg.locator("[data-testid=lab-line-text]").nth(0).click()
        shot("08_correct_edited")
        pg.click("[data-testid=lab-save]")
        pg.wait_for_selector("[data-testid=lab-scores]", timeout=120000)
        shot("09_scores_after_test_save")
        pg.locator("text=details").first.click()
        shot("10_scores_details", full=True)
        # reload: the saved revision comes back with the edit, the engines' outputs unchanged
        pg.goto(f"{WEB}/lab?tab=correct")
        pg.wait_for_selector("[data-testid=lab-lines] li", timeout=60000)
        after = pg.locator("[data-testid=lab-line-text]").nth(2).input_value()
        check["steps"].append(dict(edit_survives_reload=after.endswith("ـتجربة"), lines=n_lines))
        shot("11_correct_reopened")
    check["page_errors"] = errs
    b.close()

(OUT / f"check_{phase}.json").write_text(json.dumps(check, ensure_ascii=False, indent=1))
print(json.dumps(check, ensure_ascii=False, indent=1))
