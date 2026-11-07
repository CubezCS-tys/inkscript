"""Render a local HTML file to PNG with headless Chromium (experiment 52's playwright venv), for Telegram updates.

    $PW shot77.py page.html out.png [width]
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

CHROME = "/home/appuser/.cache/ms-playwright/chromium-1243/chrome-linux64/chrome"
src, dst = Path(sys.argv[1]).resolve(), sys.argv[2]
w = int(sys.argv[3]) if len(sys.argv) > 3 else 1000
with sync_playwright() as p:
    b = p.chromium.launch(executable_path=CHROME)
    pg = b.new_page(viewport={"width": w, "height": 400}, device_scale_factor=1.5)
    pg.goto(src.as_uri())
    pg.wait_for_timeout(500)
    pg.screenshot(path=dst, full_page=True)
    b.close()
print(dst)
