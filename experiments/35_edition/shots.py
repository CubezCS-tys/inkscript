"""Phone screenshots of reading editions (experiment 35; run with a Python that has playwright, Chromium 153):
    python shots.py OUTDIR EDITIONS_DIR id[:mode] ...
mode: top | og (first paragraph's original opened) | notes | table"""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

root = Path(sys.argv[2])
out = Path(sys.argv[1])
out.mkdir(parents=True, exist_ok=True)
with sync_playwright() as p:
    b = p.chromium.launch()
    for spec in sys.argv[3:]:
        i, _, mode = spec.partition(':')
        mode = mode or 'top'
        wide = mode.endswith('-wide')
        mode = mode.removesuffix('-wide')
        dark = mode.endswith('-dark')
        mode = mode.removesuffix('-dark')
        ctx = b.new_context(viewport={'width': 1280, 'height': 900} if wide else {'width': 390, 'height': 844}, device_scale_factor=1 if wide else 2,
                            color_scheme='dark' if dark else 'light')
        pg = ctx.new_page()
        pg.goto((root / i / f'{i}.html').as_uri())
        pg.wait_for_timeout(500)
        if mode == 'og':
            pg.evaluate("""() => { const bs=[...document.querySelectorAll('.body p button.og')];
                const b=bs[Math.min(2,bs.length-1)]; b.scrollIntoView({block:'start'}); window.scrollBy(0,-60); b.click(); }""")
            pg.wait_for_timeout(1200)
        elif mode == 'notes':
            pg.evaluate("() => { const n=document.querySelector('#notes,.refs'); if(n) n.scrollIntoView(); }")
            pg.wait_for_timeout(300)
        elif mode == 'table':
            pg.evaluate("() => { const n=document.querySelector('.tablewrap,.formula'); if(n) {n.scrollIntoView(); window.scrollBy(0,-120);} }")
            pg.wait_for_timeout(300)
        elif mode == 'quran':
            pg.evaluate("() => { const n=document.querySelector('.body .quran'); if(n) {n.scrollIntoView(); window.scrollBy(0,-200);} }")
            pg.wait_for_timeout(300)
        elif mode == 'about':
            pg.evaluate("() => document.querySelector('#about').scrollIntoView()")
        f = out / f'{i}_{mode}{"_dark" if dark else ""}{"_wide" if wide else ""}.png'
        pg.screenshot(path=str(f))
        w = pg.evaluate("() => document.documentElement.scrollWidth")
        print(f, 'scrollWidth', w)
        ctx.close()
    b.close()
