"""The schema diagram (http://127.0.0.1:8003/diagram/schema47.html) as two halves of its SVG: img/schema_a.png,
img/schema_b.png, and the first 1440 px at full size, img/schema_detail.png. Read-only (Datasette serves the page; nothing is clicked)."""
from pathlib import Path
from playwright.sync_api import sync_playwright
IMG = Path(__file__).resolve().parent / "img"
with sync_playwright() as p:
    b = p.chromium.launch(executable_path="/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome")
    pg = b.new_page(viewport={"width": 6800, "height": 1200}, device_scale_factor=1.5)
    pg.goto("http://127.0.0.1:8003/diagram/schema47.html", wait_until="networkidle")
    pg.wait_for_timeout(1500)
    r = pg.evaluate("(()=>{const r=document.querySelector('svg').getBoundingClientRect();return [r.x,r.y,r.width,r.height]})()")
    x, y, w, h = r
    cut = 3800   # between the bibliographic layer and people
    pg.screenshot(path=str(IMG / "schema_a.png"), clip={"x": x, "y": y, "width": cut, "height": h})
    pg.screenshot(path=str(IMG / "schema_b.png"), clip={"x": x + cut, "y": y, "width": w - cut, "height": h})
    pg2 = b.new_page(viewport={"width": 1440, "height": 1200}, device_scale_factor=2)
    pg2.goto("http://127.0.0.1:8003/diagram/schema47.html", wait_until="networkidle")
    pg2.wait_for_timeout(1500)
    pg2.screenshot(path=str(IMG / "schema_detail.png"), clip={"x": 0, "y": y, "width": 1440, "height": h})
    b.close()
print("ok", r)
