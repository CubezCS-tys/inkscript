"""Fresh screenshots of the live Desk (http://127.0.0.1:8004) for the business document.

Run with the scratchpad Playwright venv:
    <pw>/bin/python shots.py <token-file>
The token file holds a corrector token for agent:docs-business (never printed). Read-only except that
opening /work leases one task to that actor for 15 minutes.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

BASE = "http://127.0.0.1:8004"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
OUT = Path(__file__).resolve().parent / "img"

# name, path, viewport height, wait (s), clip height (None = viewport)
PAGES = [
    ("index", "/index-home", 1100, 8),
    ("journal", "/journals/J0130", 1100, 6),
    ("article", "/articles/0130-018-072-003?tab=text&view=beside", 1000, 8),
    ("explore", "/explore", 1000, 8),
    ("person", "/persons/A8STQEWEAV", 1100, 6),
    ("work", "/work", 1000, 6),
    ("project", "/project", 1100, 6),
    ("guide", "/how-we-collect", 1000, 6),
    ("librarian", "/librarian", 1000, 6),
]


def main(token_file: str, only: list[str]) -> None:
    token = Path(token_file).read_text().strip()
    OUT.mkdir(exist_ok=True)
    with sync_playwright() as p:
        b = p.chromium.launch(executable_path=CHROME)
        ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
        ctx.add_init_script("try{localStorage.setItem('desk_tour_done','1');localStorage.setItem('deskTourDone','1')}catch(e){}")
        r = ctx.request.post(BASE + "/api/session", data=json.dumps({"token": token}),
                             headers={"content-type": "application/json"})
        print("session", r.status)
        page = ctx.new_page()
        for name, path, h, wait in PAGES:
            if only and name not in only:
                continue
            page.set_viewport_size({"width": 1440, "height": h})
            page.goto(BASE + path, wait_until="networkidle", timeout=90000)
            time.sleep(wait)
            page.screenshot(path=str(OUT / f"{name}.png"))
            print(name, "ok")
        b.close()


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2:])
