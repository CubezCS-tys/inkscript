"""Screenshots of each <section> of a side-by-side page (Playwright, local Chromium), for looking at them.
    PW_PYTHON shots60.py out/side/t1.html out/side/shots/t1 [ids...]"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright
src, dst = Path(sys.argv[1]).resolve(), Path(sys.argv[2])
ids = sys.argv[3:]
dst.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
    pg = b.new_page(viewport={"width": 1300, "height": 900})
    pg.goto(src.as_uri())
    pg.wait_for_timeout(500)
    for el in pg.query_selector_all("section"):
        i = el.get_attribute("id")[2:]
        if ids and not any(i.startswith(x) for x in ids):
            continue
        el.screenshot(path=str(dst / f"{i}.png"))
    pg.set_viewport_size({"width": 390, "height": 800})
    pg.screenshot(path=str(dst / "_phone.png"))
    b.close()
print("ok")
