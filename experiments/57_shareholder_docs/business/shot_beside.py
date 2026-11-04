"""The article beside its scan, scrolled so the two panes fill the frame (run like shots.py)."""
import json, sys, time
from pathlib import Path
from playwright.sync_api import sync_playwright
BASE = "http://127.0.0.1:8004"
CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
OUT = Path(__file__).resolve().parent / "img"
token = Path(sys.argv[1]).read_text().strip()
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    ctx = b.new_context(viewport={"width": 1440, "height": 1000}, device_scale_factor=2)
    ctx.add_init_script("try{localStorage.setItem('desk_tour_done','1');localStorage.setItem('deskTourDone','1')}catch(e){}")
    ctx.request.post(BASE + "/api/session", data=json.dumps({"token": token}), headers={"content-type": "application/json"})
    pg = ctx.new_page()
    pg.goto(BASE + "/articles/0130-018-072-003?tab=text&view=beside", wait_until="networkidle", timeout=90000)
    time.sleep(4)
    el = pg.get_by_text("Page 1 · printed 51").first
    y = el.evaluate("e => e.getBoundingClientRect().top + window.scrollY")
    pg.evaluate(f"window.scrollTo(0, {y} - 130)")
    time.sleep(5)
    pg.screenshot(path=str(OUT / "article_beside.png"))
    b.close()
print("ok")
