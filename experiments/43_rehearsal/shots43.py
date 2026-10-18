"""Experiment 43: screenshots of Layout-view pages (headless Chromium; run with experiment 40's Playwright venv).

    experiments/40_gemini4_vlm/out/venv/bin/python shots43.py OUT_PREFIX HTML PAGE [PAGE ...]
writes OUT_PREFIX_pNNN.png (the page box only, our side of the view). No model calls.
"""
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

prefix, html, pages = sys.argv[1], Path(sys.argv[2]).resolve(), [int(x) for x in sys.argv[3:]]
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport=dict(width=1400, height=1600), device_scale_factor=1, color_scheme="light")
    pg.goto(html.as_uri(), wait_until="load", timeout=120000)
    try:
        pg.wait_for_function("window.__fit", timeout=60000)
    except Exception:
        pass
    pg.evaluate("document.fonts.ready.then(() => true)")
    pg.wait_for_timeout(1000)
    for n in pages:
        el = pg.query_selector(f"#p{n} .lpage")
        el.scroll_into_view_if_needed()
        pg.wait_for_timeout(300)
        Path(prefix).parent.mkdir(parents=True, exist_ok=True)
        el.screenshot(path=f"{prefix}_p{n:03d}.png")
        print(f"{prefix}_p{n:03d}.png", flush=True)
    b.close()
