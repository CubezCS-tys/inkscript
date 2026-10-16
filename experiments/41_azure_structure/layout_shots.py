"""Experiment 41: screenshots of the Layout view's pages, old (Argon's raw output) against new (the masters), for
looking at them side by side. Run with a Python that has Playwright (experiments/40_gemini4_vlm/out/venv).

    <playwright python> layout_shots.py STEM [STEM ...]

For each article: out/views/print_argon/<stem>.layout.html and out/views/print/<stem>.layout.html opened in headless
Chromium at the page's printed width (96 dpi CSS), fitted by the view's own script (window.__fit), each page
(div.lpage) shot to out/layout_compare/shots/<stem>/p<NNN>.old.png / .new.png. layout_compare.py --shots then
measures and pairs them.
"""
import json
import sys
from pathlib import Path

from playwright.sync_api import sync_playwright

HERE = Path(__file__).resolve().parent
V = HERE / "out" / "views"
OUT = HERE / "out" / "layout_compare" / "shots"

with sync_playwright() as p:
    b = p.chromium.launch()
    for stem in sys.argv[1:]:
        d = OUT / stem
        d.mkdir(parents=True, exist_ok=True)
        for tag, sub in (("old", "print_argon"), ("new", "print")):
            pg = b.new_page(viewport=dict(width=1000, height=1400), device_scale_factor=1.5, color_scheme="light")
            pg.emulate_media(media="print")             # as prints.py prints it
            if tag == "old":     # print_argon/ predates PRINT_CSS's .contmark{display:none} (committed with 239f7f3)
                pg.add_init_script("document.addEventListener('DOMContentLoaded',()=>{const s=document.createElement("
                                   "'style');s.textContent='.contmark{display:none}';document.head.appendChild(s)})")
            pg.goto((V / sub / f"{stem}.layout.html").resolve().as_uri(), wait_until="load", timeout=120000)
            pg.wait_for_function("window.__fit", timeout=120000)
            pg.evaluate("document.fonts.ready.then(() => true)")
            pg.wait_for_timeout(800)
            n = 0
            for el in pg.query_selector_all("div.lpage"):
                pn = int(el.get_attribute("data-p"))
                el.screenshot(path=str(d / f"p{pn:03d}.{tag}.png"))
                n += 1
            print(json.dumps(dict(stem=stem, tag=tag, pages=n, over=len(pg.evaluate("window.__fit").get("over", [])))),
                  flush=True)
            pg.close()
    b.close()
