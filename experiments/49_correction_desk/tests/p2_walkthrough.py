"""P2 walk-through in a real Chromium (Playwright), against the running Desk: web on 127.0.0.1:8004, API on :8005.

    PW=/tmp/claude-1001/-home-appuser-inkscript/<session>/scratchpad/pw    # a venv with `playwright`
    $PW/bin/python tests/p2_walkthrough.py [--keep]

1. signs in with the demo corrector token of `agent:p2-walkthrough` (from /home/appuser/data/desk/demo_tokens.txt,
   mode 600; tokens are never printed);
2. does 5 real tasks from the live queue across the three kinds, through the screens (buttons and keyboard
   shortcuts), each decision noted "P2 walk-through (test; reverted after)";
3. an admin (`agent:p1-demo-admin`) builds a release from the Releases page;
4. checks that the before/after view shows the change (counts moved in the top-cited list, the cards changed);
5. opens an Article page and checks the full text, the authors and the citations render, with ink crops loaded;
then (unless --keep) reverts the 5 decisions as their owner and builds a clean-up release, so the Desk is back to
where it was (the decisions stay in the append-only log, superseded). Screenshots go to out/p2_shots/.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import Page, sync_playwright

HERE = Path(__file__).resolve().parent
SHOTS = HERE.parent / "out" / "p2_shots"
WEB, API = "http://127.0.0.1:8004", "http://127.0.0.1:8005/desk/api"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
ACTOR, ADMIN = "agent:p2-walkthrough", "agent:p1-demo-admin"
NOTE = "P2 walk-through (test; reverted after)"
TOK = dict(line.split("\t", 1) for line in Path("/home/appuser/data/desk/demo_tokens.txt").read_text().splitlines())
LOG: list[str] = []


def say(msg: str) -> None:
    LOG.append(msg)
    print(msg, flush=True)


def call(path: str, actor: str, body: dict | None = None, method: str | None = None):
    req = urllib.request.Request(API + path, method=method or ("POST" if body is not None else "GET"),
                                 data=json.dumps(body).encode() if body is not None else None,
                                 headers={"X-Desk-Token": TOK[actor].strip(), "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=120) as r:
        return json.loads(r.read() or b"null")


def sign_in(page: Page, actor: str) -> None:
    page.goto(WEB + "/signin")
    page.fill("input[name=token]", TOK[actor].strip())
    page.click("button:has-text('Sign in')")
    page.wait_for_url(WEB + "/")


def wait_task(page: Page, kind: str) -> str:
    page.goto(f"{WEB}/work?kind={kind}")
    page.wait_for_selector(f"[data-testid=task][data-kind={kind}]", timeout=30000)
    page.wait_for_load_state("networkidle")
    return page.get_attribute("[data-testid=task]", "data-task")


def saved(page: Page, task_id: str) -> None:
    page.wait_for_selector("[data-testid=saved]", timeout=20000)
    page.wait_for_function(f"() => !document.querySelector('[data-task=\"{task_id}\"]')", timeout=20000)


def crops_loaded(page: Page, scope: str = "") -> int:
    return page.evaluate(f"""() => [...document.querySelectorAll('{scope} img[data-crop]')]
        .filter(i => i.complete && i.naturalWidth > 0).length""")


def wait_build(page: Page, before: str | None) -> str:
    t0 = time.time()
    while time.time() - t0 < 600:
        st = call("/build", ADMIN)
        if not st.get("running") and st.get("release_id") and st["release_id"] != before:
            if st.get("error"):
                raise SystemExit(f"build failed: {st['error']}")
            return st["release_id"]
        time.sleep(2)
    raise SystemExit("build timed out")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--keep", action="store_true", help="leave the walk-through's decisions in place")
    a = ap.parse_args()
    SHOTS.mkdir(parents=True, exist_ok=True)
    t_start = time.time()
    since = call("/decisions?actor_id=" + ACTOR + "&limit=500", ACTOR)
    seen = {d["decision_id"] for d in since}
    base_release = (call("/state", ACTOR) or {}).get("release_id")
    base_kinds = {r["kind"]: r["open"] + r["claimed"] for r in call("/stats/kinds", ACTOR)}
    say(f"start: newest release {base_release}; open tasks {base_kinds}")
    timings: dict = {}
    ok = True
    with sync_playwright() as p:
        br = p.chromium.launch(executable_path=CHROME, args=["--no-sandbox"])
        ctx = br.new_context(viewport={"width": 1440, "height": 1000})
        page = ctx.new_page()
        errors: list[str] = []
        page.on("pageerror", lambda e: errors.append(str(e)))

        # 1. sign in, the Overview
        sign_in(page, ACTOR)
        page.wait_for_selector("[data-testid=queue] tbody tr")
        page.screenshot(path=str(SHOTS / "01_overview.png"))
        say("1. signed in as " + ACTOR + "; Overview shows the queue by kind")

        # 2. five real tasks across the three kinds
        done = []
        # 2a. work joined without an author: split when the detector found 2+ author groups, else "all one work"
        for i in range(2):
            t0 = time.time()
            tid = wait_task(page, "work_joined_without_author")
            page.wait_for_function("() => [...document.querySelectorAll('[data-testid=members] img[data-crop]')].some(i => i.complete && i.naturalWidth > 0)", timeout=20000)
            n_crops = crops_loaded(page, "[data-testid=members]")
            page.fill("#note", NOTE)
            can_split = page.is_enabled("[data-testid=save-split]")
            if i == 0:
                page.screenshot(path=str(SHOTS / "02_work_task.png"), full_page=True)
            if can_split:
                page.locator("[data-testid=members] li").first.focus()
                page.keyboard.press("Enter")             # the shortcut for "Save split"
            else:
                page.click("[data-testid=all-one]")
            saved(page, tid)
            done.append(("work_joined_without_author", tid, "split_work" if can_split else "confirm_work", n_crops))
            timings[f"task {tid}"] = round(time.time() - t0, 1)
        # 2b. possible same work: "Same work" by key 1, then "Not the same" by key 2
        for key, op in (("1", "same_work"), ("2", "not_same_work")):
            t0 = time.time()
            tid = wait_task(page, "possible_same_work")
            page.wait_for_function("() => [...document.querySelectorAll('img[data-crop]')].some(i => i.complete && i.naturalWidth > 0)", timeout=20000)
            n_crops = crops_loaded(page)
            page.fill("#note", NOTE)
            page.locator("body").click(position={"x": 5, "y": 300})
            page.keyboard.press(key)
            saved(page, tid)
            done.append(("possible_same_work", tid, op, n_crops))
            timings[f"task {tid}"] = round(time.time() - t0, 1)
        # 2c. a byline twin: the machine's guess when it has one ("Same person", Enter), else "None of them" (n)
        t0 = time.time()
        # skip one first, to check Skip gives the task back and serves another
        tid0 = wait_task(page, "byline_twin")
        page.click("[data-testid=skip]")
        page.wait_for_function(f"() => !document.querySelector('[data-task=\"{tid0}\"]')", timeout=20000)
        tid = wait_task(page, "byline_twin")
        assert tid != tid0, "a skipped task came back"
        page.wait_for_load_state("networkidle")
        page.wait_for_timeout(1000)                  # a byline with no ink anchor shows the grey stripes instead
        n_crops = crops_loaded(page)
        page.fill("#note", NOTE)
        task = call("/queue/next?kind=byline_twin", ACTOR)       # the held task: same one the screen shows
        has_guess = bool(task and str(task["task_id"]) == tid and task.get("machine_guess"))
        page.locator("body").click(position={"x": 5, "y": 300})
        page.keyboard.press("Enter" if has_guess else "n")
        saved(page, tid)
        done.append(("byline_twin", tid, "same_person" if has_guess else "not_same_person", n_crops))
        timings[f"task {tid}"] = round(time.time() - t0, 1)
        say(f"2. five tasks answered through the screens (skipped task {tid0} first): " +
            "; ".join(f"{k} task {t}: {o} ({c} ink crops)" for k, t, o, c in done))

        mine = [d for d in call("/decisions?actor_id=" + ACTOR + "&limit=500", ACTOR) if d["decision_id"] not in seen]
        say(f"   decisions made: {len(mine)} — " + ", ".join(f"{d['op']} {d['subject_keys']}" for d in mine))
        if len([d for d in mine if d.get("task_id")]) < 5:
            say("   FAIL: fewer than 5 task decisions")
            ok = False

        # the Work page of a decided card: History shows the decision with its owner, and "Change" for the owner
        wk = next((d for d in mine if d["op"] in ("split_work", "same_work", "confirm_work")), None)
        if wk:
            page.goto(f"{WEB}/works/{wk['subject_keys'][0].split(':')[1]}")
            page.click("button[role=tab]:has-text('History')")
            page.wait_for_selector(f"[data-decision='{wk['decision_id']}']")
            row = page.locator(f"[data-decision='{wk['decision_id']}']")
            has_change = row.locator("button:has-text('Change')").count() == 1
            say(f"   Work page History: the decision shows its owner; owner sees 'Change': {has_change}")
            ok &= has_change

        # 3. an admin builds a release from the Releases page
        t0 = time.time()
        actx = br.new_context(viewport={"width": 1440, "height": 1000})
        ap_ = actx.new_page()
        ap_.on("pageerror", lambda e: errors.append(str(e)))
        sign_in(ap_, ADMIN)
        ap_.goto(WEB + "/releases")
        ap_.fill("input[placeholder^='Note']", "P2 walk-through: 5 test decisions (reverted by the next release)")
        ap_.click("[data-testid=build]")
        rid = wait_build(ap_, base_release)
        timings["release (build + summaries + detectors)"] = round(time.time() - t0, 1)
        say(f"3. release {rid} built from the Releases page in {timings['release (build + summaries + detectors)']} s")

        # 4. before / after
        ap_.goto(f"{WEB}/releases?id={rid}")
        ap_.wait_for_selector("[data-testid=diff] [data-testid=top-after] tbody tr", timeout=60000)
        d = call(f"/releases/{rid}/diff", ADMIN)
        cards_changed = {c["card"] for c in d["cards"]}
        mine_cards = {k.split(":")[1] for x in mine for k in x["subject_keys"] if k.startswith("work:")}
        moved = [w for w in d["top"] + d["top_before"] if w["n_before"] != w["n_after"]]
        changed_rows = ap_.locator("[data-testid=diff] tr[data-changed='1']").count()
        ap_.screenshot(path=str(SHOTS / "03_release_before_after.png"), full_page=False)
        say(f"4. before/after ({d['before']} → {d['after']}): {len(d['cards'])} cards changed "
            f"({', '.join(sorted(cards_changed & mine_cards)) or 'none of ours'} are ours); "
            f"{len(moved)} top-list counts moved; {changed_rows} rows highlighted; persons: {len(d['persons'])}")
        for w in moved[:6]:
            say(f"   {w['id']} «{w['title']}»: cited by {w['n_before']} → {w['n_after']} "
                f"(rank {w.get('rank_before')} → {w.get('rank_after')})")
        if not (cards_changed & mine_cards):
            say("   FAIL: the before/after does not show our cards")
            ok = False

        # 5. an Article page: full text, authors, citations with ink crops
        t0 = time.time()
        stem = None
        for x in mine:
            if x["op"] in ("split_work", "same_work", "confirm_work", "not_same_work"):
                w = call(f"/works/{x['subject_keys'][0].split(':')[1]}", ACTOR)
                if w.get("members"):
                    stem = w["members"][0]["stem"]
                    break
        stem = stem or "1967-000-008-012"
        page.goto(f"{WEB}/articles/{stem}")
        page.wait_for_selector("[data-testid=fulltext] [data-block]", timeout=30000)
        n_blocks = page.locator("[data-testid=fulltext] [data-block]").count()
        n_authors = page.locator("[data-testid=authors] li").count()
        rtl = page.locator("[data-testid=fulltext] p[dir=rtl]").count()
        page.locator("[data-ink]").first.click()
        page.wait_for_timeout(1500)
        page.screenshot(path=str(SHOTS / "04_article.png"), full_page=False)
        page.click("button[role=tab]:has-text('Citations')")
        page.wait_for_selector("[data-testid=citations] li")
        n_cit = page.locator("[data-testid=citations] li").count()
        page.evaluate("() => document.querySelectorAll('[data-testid=citations] img[data-crop]').forEach(i => i.loading = 'eager')")
        page.wait_for_function("() => [...document.querySelectorAll('[data-testid=citations] img[data-crop]')].filter(i => i.complete && i.naturalWidth > 0).length >= Math.min(3, document.querySelectorAll('[data-testid=citations] img[data-crop]').length)", timeout=30000)
        n_crops = crops_loaded(page, "[data-testid=citations]")
        n_cards = page.locator("[data-testid=citations] [data-testid=card-link]").count()
        page.screenshot(path=str(SHOTS / "05_article_citations.png"), full_page=False)
        timings["article page"] = round(time.time() - t0, 1)
        say(f"5. Article {stem}: {n_blocks} blocks in reading order ({rtl} right-to-left), {n_authors} author(s), "
            f"{n_cit} citations, {n_cards} linked to work cards, {n_crops} citation ink crops loaded")
        ok &= n_blocks > 10 and n_authors >= 1 and n_cit >= 1 and n_crops >= 1
        if errors:
            say("   page errors: " + " | ".join(errors[:5]))
            ok = False
        br.close()

    # clean up: the owner reverts the walk-through's decisions, then a release without them
    if not a.keep:
        t0 = time.time()
        for x in mine:
            if x["status"] == "accepted" and x["op"] not in ("revert", "retire"):
                call(f"/decisions/{x['decision_id']}/revert", ACTOR, {"note": "P2 walk-through clean-up"})
        call("/releases", ADMIN, {"note": "P2 walk-through clean-up: its 5 test decisions reverted", "run_detectors": True})
        rid2 = wait_build(None, rid)
        timings["clean-up (revert + release)"] = round(time.time() - t0, 1)
        d2 = call(f"/releases/{rid2}/diff?vs={base_release}", ADMIN) if base_release else None
        back = d2 is not None and not d2["cards"] and not d2["persons"] and \
            all(w["n_before"] == w["n_after"] for w in d2["top"])
        kinds = {r["kind"]: r["open"] + r["claimed"] for r in call("/stats/kinds", ACTOR)}
        say(f"6. clean-up: {len(mine)} decisions reverted by their owner; release {rid2}; "
            f"same cards and top list as {base_release}: {back}; open tasks now {kinds} (were {base_kinds})")
        ok &= back
    timings["total"] = round(time.time() - t_start, 1)
    say("timings (s): " + json.dumps(timings))
    (SHOTS / "walkthrough_log.txt").write_text("\n".join(LOG) + "\n", encoding="utf-8")
    say("RESULT: " + ("PASS" if ok else "FAIL"))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
