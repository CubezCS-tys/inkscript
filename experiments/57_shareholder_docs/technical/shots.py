"""Screenshots of the live Desk (:8004) and the platform's schema page (:8003) for the technical documentation.

Read-only: it signs in with a corrector token (read from the file named by DESK_TOKEN_FILE, never printed), opens
pages and takes screenshots. It does not open the Work page (claiming a task writes a lease) and clicks no button
that writes. Run with a Playwright venv:

    DESK_TOKEN_FILE=/path/to/mode-600/token  <pw-venv>/bin/python shots.py [name ...]
"""
import os
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
IMG = HERE / "img"
DESK = "http://127.0.0.1:8004"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
INIT = "try{localStorage.setItem('desk_tour_done','1');localStorage.setItem('deskTourDone','1')}catch(e){}"

# name -> (url, viewport height, full_page, wait ms, extra action)
SHOTS = {
    "project_map": (f"{DESK}/project", 1000, False, 3500, None),
    "project_details": (f"{DESK}/project?tab=details", 1100, False, 2500, None),
    "index_home": (f"{DESK}/index-home", 1300, False, 6000, None),
    "journal_0130": (f"{DESK}/journals/J0130", 1300, False, 5000, None),
    "person_record": (f"{DESK}/persons/A8STQEWEAV", 1100, False, 4000, None),
    "article_beside": (f"{DESK}/articles/0130-018-072-003?tab=text&view=beside", 1000, False, 6000,
                       lambda pg: (pg.evaluate("window.scrollTo(0, 830)"), pg.wait_for_timeout(4000))),
    "article_fields": (f"{DESK}/articles/0130-018-072-003?tab=fields", 1100, False, 4000, None),
    "article_citations": (f"{DESK}/articles/0130-018-072-003?tab=citations", 1100, False, 5000, None),
    "explore_articles": (f"{DESK}/explore", 950, False, 5000, None),
    "explore_refs": (f"{DESK}/explore?e=references", 950, False, 5000, None),
    "guide": (f"{DESK}/how-we-collect", 1150, False, 4000, None),
    "librarian": (f"{DESK}/librarian", 1150, False, 5000, None),
    "most_cited": (f"{DESK}/most-cited", 1000, False, 4000, None),
    "releases": (f"{DESK}/releases", 1100, False, 4000, None),
    "institutions": (f"{DESK}/institutions", 1000, False, 4000, None),
    "ink": ("http://127.0.0.1:8003/diagram/ink.html?n=0069-000-026-005%7Cfn-p15-13", 640, False, 4000, None),
    "mirror": (f"{DESK}/views/j0130_final/mirror/0130-018-072-003.html", 1000, False, 5000, None),
}


def main(names):
    token = Path(os.environ["DESK_TOKEN_FILE"]).read_text().strip()
    IMG.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        ctx.add_init_script(INIT)
        page = ctx.new_page()
        page.goto(f"{DESK}/signin")
        r = page.request.post(f"{DESK}/api/session", data={"token": token})
        print("sign-in", r.status)
        for name in names or SHOTS:
            url, h, full, wait, action = SHOTS[name]
            page.set_viewport_size({"width": 1440, "height": h})
            try:
                page.goto(url, wait_until="networkidle", timeout=60000)
            except Exception as e:  # noqa: BLE001
                print(name, "goto:", type(e).__name__)
            page.wait_for_timeout(wait)
            if action:
                action(page)
            page.screenshot(path=str(IMG / f"{name}.png"), full_page=full)
            print(name, "ok", page.url.replace(DESK, ""))
        b.close()


if __name__ == "__main__":
    main(sys.argv[1:])
