"""Experiment 43: the correction tool's end-to-end test, part 1 — corrections made in headless Chromium by clicking
(experiment 40's Playwright venv), screenshots, and the export file.

    experiments/40_gemini4_vlm/out/venv/bin/python correct_test43.py [BASE_URL]
BASE_URL defaults to http://127.0.0.1:8899/correct/edit/ (the 8899 server of experiment 41's views, where
out/correct/v33_300/views is linked as "correct"). Writes out/correct/test/corrections_test.json, plan.json (what
each correction should do, for part 2) and screenshots in out/correct/shots/. Part 2: correct_check43.py.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
BASE = sys.argv[1] if len(sys.argv) > 1 else "http://127.0.0.1:8899/correct/edit/"
OUTD, SHOTS = HERE / "out" / "correct" / "test", HERE / "out" / "correct" / "shots"
OUTD.mkdir(parents=True, exist_ok=True)
SHOTS.mkdir(parents=True, exist_ok=True)
plan, errors = [], []


def alto_with(pg, line):
    return pg.evaluate("l => Object.entries(CORRECT.data.alto).filter(([k, v]) => v.lines.includes(l)).map(x => x[0])[0]", line)


def click_block(pg, line=None, alto=None):
    a = alto or alto_with(pg, line)
    pg.locator(f'.lpage .pc[data-alto="{a}"]').first.click()
    pg.wait_for_timeout(150)
    return a


def btn(pg, text):
    pg.locator("#cpanel button", has_text=text).first.click()
    pg.wait_for_timeout(150)


def tick(pg, line):
    pg.locator(f'#cpanel input[aria-label="select line {line}"]').check()
    pg.wait_for_timeout(100)


def word(pg, line, i):
    pg.locator("#cpanel .cl", has=pg.locator("code", has_text=line)).locator("button.cw").nth(i).click()
    pg.wait_for_timeout(150)
    return pg.locator("#cpanel .cl", has=pg.locator("code", has_text=line)).locator("button.cw").nth(i).inner_text()


def shot(pg, name, page=None):
    if page:
        pg.evaluate(f"document.getElementById('p{page}').scrollIntoView()")
        pg.wait_for_timeout(200)
    pg.screenshot(path=str(SHOTS / f"{name}.png"))


def open_article(ctx, stem):
    pg = ctx.new_page()
    pg.on("pageerror", lambda e: errors.append(f"{stem}: {e}"))
    pg.goto(BASE + stem + ".html", wait_until="load")
    pg.wait_for_timeout(1000)
    return pg


def n_patches(pg):
    return pg.evaluate("CORRECT.store().patches.length")


with sync_playwright() as p:
    b = p.chromium.launch()
    ctx = b.new_context(viewport=dict(width=1500, height=1050), color_scheme="light")   # one profile: one localStorage
    first = ctx.new_page()
    first.goto(BASE + "index.html")
    first.evaluate("Object.keys(localStorage).filter(k => k.startsWith('inkscript.correct.v1:')).forEach(k => localStorage.removeItem(k))")

    # ---- 0744 p1: show-through (the reverse side read as text), a misread word, a misprint, a note link
    s = "0744-000-059-007"
    pg = open_article(ctx, s)
    click_block(pg, "1:1")
    pg.select_option('#cpanel select[aria-label="kind"]', "noise")
    pg.select_option("#cpanel select.cnk", "show-through")
    btn(pg, "Apply")
    plan.append(dict(stem=s, what="noise", lines=["1:1", "1:2", "1:3", "1:4", "1:5"]))
    click_block(pg, "1:6")
    ls = ["1:6", "1:7", "1:8", "1:9", "1:10", "1:11", "1:12", "1:13", "1:18", "1:20"]
    for x in ls:
        tick(pg, x)
    btn(pg, "Selected lines are noise")
    plan.append(dict(stem=s, what="noise", lines=ls))
    click_block(pg, "1:45")
    w = word(pg, "1:46", 1)
    pg.fill("#cpanel input.cin", w + "ة")
    btn(pg, "Azure misread")
    plan.append(dict(stem=s, what="misread", line="1:46", frm=w, to=w + "ة"))
    w2 = word(pg, "1:47", 0)
    pg.fill("#cpanel input.cin", "قال")
    btn(pg, "Misprint in the print")
    plan.append(dict(stem=s, what="misprint", line="1:47", frm=w2, to="قال"))
    shot(pg, "0744_p1_after", 1)
    btn(pg, "My corrections")
    pg.wait_for_timeout(200)
    shot(pg, "0744_my_corrections")
    btn(pg, "Block")
    # a note link: the first block with a call, its first call pointed at another note of the article
    call = pg.evaluate("""() => { const D = CORRECT.data; for (const [p, P] of Object.entries(D.pages))
        for (const b of P.blocks) if (b.calls && b.calls.length) { const c = b.calls[0];
          const o = D.notes.find(n => n.id !== c.fn); if (o) return {p, line: c.line, marker: c.marker, fn: c.fn, to: o.id}; }
        return null; }""")
    if call:
        click_block(pg, call["line"])
        row = pg.locator("#cpanel .crow", has=pg.locator(".cmk", has_text=f"({call['line']})")).first
        row.locator("select").select_option(call["to"])
        row.locator("button", has_text="Link").click()
        pg.wait_for_timeout(150)
        plan.append(dict(stem=s, what="relink", **call))
        shot(pg, "0744_relink", call["p"])
    print(s, n_patches(pg), "corrections")

    # ---- 2048 p1: author and affiliation in one byline -> split; a block moved; two paragraphs merged
    s = "2048-015-001-019"
    pg = open_article(ctx, s)
    click_block(pg, "1:6")
    tick(pg, "1:7")
    btn(pg, "Split before")
    plan.append(dict(stem=s, what="split", before=["1:6"], after=["1:7", "1:8"]))
    shot(pg, "2048_p1_split", 1)
    order = pg.evaluate("CORRECT.model('2').blocks.map(b => [b.type, b.lines])")
    k = next(i for i in range(len(order) - 1) if order[i][0] == "paragraph" and order[i + 1][0] == "paragraph")
    click_block(pg, order[k][1][0])
    btn(pg, "Merge with the next block")
    plan.append(dict(stem=s, what="merge", page=2, a=order[k][1], b=order[k + 1][1]))
    o1 = pg.evaluate("CORRECT.model('1').blocks.map(b => [b.type, b.lines])")
    j = next(i for i, x in enumerate(o1) if x[0] == "other")
    click_block(pg, o1[j][1][0])
    btn(pg, "Move up")
    plan.append(dict(stem=s, what="move_up", page=1, block=o1[j][1], over=o1[j - 1][1]))
    shot(pg, "2048_p1_after", 1)
    print(s, n_patches(pg), "corrections")

    # ---- 0617 p3: the signature drawn as a large heading -> a paragraph; p1 picture box; one change undone
    s = "0617-024-021,024-010"
    pg = open_article(ctx, s)
    click_block(pg, "3:7")
    pg.select_option('#cpanel select[aria-label="kind"]', "paragraph")
    btn(pg, "Apply")
    plan.append(dict(stem=s, what="kind", lines=["3:8", "3:7"], to="paragraph"))
    click_block(pg, "3:22")                                     # a change made, then undone: not exported
    pg.select_option('#cpanel select[aria-label="kind"]', "paragraph")
    btn(pg, "Apply")
    pg.locator("#cpanel .cpatch button", has_text="Undo").first.click()
    pg.wait_for_timeout(150)
    fig = pg.evaluate("Object.entries(CORRECT.data.alto).find(([k, v]) => v.p === 1 && !v.lines.length)[0]")
    click_block(pg, alto=fig)
    btn(pg, "Redraw the box")
    h = pg.locator(".cboxedit .chandle.se").bounding_box()
    pg.mouse.move(h["x"] + h["width"] / 2, h["y"] + h["height"] / 2)
    pg.mouse.down()
    pg.mouse.move(h["x"] + 40, h["y"] + 30, steps=5)
    pg.mouse.up()
    shot(pg, "0617_p1_box", 1)
    btn(pg, "Save the box")
    box = pg.evaluate("CORRECT.store().patches.slice(-1)[0].payload.box")
    plan.append(dict(stem=s, what="box", page=1, box=box))
    pg.locator("#cgold").count() or btn(pg, "My corrections")
    pg.wait_for_timeout(150)
    pg.check("#cgold")
    shot(pg, "0617_my_corrections")
    print(s, n_patches(pg), "corrections")

    # ---- the phone: the panel at the bottom
    ph = b.new_context(viewport=dict(width=390, height=844), device_scale_factor=2, is_mobile=True, has_touch=True,
                       color_scheme="light").new_page()
    ph.goto(BASE + "2048-015-001-019.html", wait_until="load")
    ph.wait_for_timeout(800)
    ph.locator('.lpage .pc[data-alto="p1b3"]').first.tap()
    ph.wait_for_timeout(300)
    ph.evaluate("document.getElementById('p1').scrollIntoView()")
    ph.screenshot(path=str(SHOTS / "phone_2048_p1.png"))

    # ---- export (index page: every article of the run)
    first.goto(BASE + "index.html", wait_until="load")
    first.wait_for_timeout(300)
    first.screenshot(path=str(SHOTS / "index.png"))
    with first.expect_download() as dl:
        first.click("#cexport-all")
    f = OUTD / "corrections_test.json"
    dl.value.save_as(str(f))
    b.close()

(OUTD / "plan.json").write_text(json.dumps(plan, ensure_ascii=False, indent=1), encoding="utf-8")
d = json.loads(f.read_text(encoding="utf-8"))
print("exported", {k: len(v["patches"]) for k, v in d["articles"].items()}, "->", f)
print("page errors:", errors or "none")
sys.exit(1 if errors else 0)
