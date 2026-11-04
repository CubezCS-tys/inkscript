"""Render every deck slide (and the gate 2 page) to PNG, and the deck to PDF via print (experiment 73, agent C).
Run with experiments/52_journal_gate1/out/pwvenv/bin/python. Opens the HTML files directly (file://)."""
import sys
from pathlib import Path
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[1] / "49_correction_desk" / "web" / "public"
OUT = Path(__file__).resolve().parent / "out" / "c_shots"
OUT.mkdir(parents=True, exist_ok=True)
what = sys.argv[1:] or ["deck", "gate2", "pdf"]
with sync_playwright() as p:
    b = p.chromium.launch()
    if "deck" in what:
        pg = b.new_page(viewport={"width": 1440, "height": 810})
        errs = []
        pg.on("console", lambda m: errs.append(m.text) if m.type == "error" else None)
        pg.goto((ROOT / "pitch" / "index.html").as_uri() + "#1")
        pg.wait_for_timeout(400)
        n = pg.evaluate("document.querySelectorAll('.slide').length")
        for i in range(1, n + 1):
            if i > 1:
                pg.keyboard.press("ArrowRight")
            pg.wait_for_timeout(250)
            over = pg.evaluate("""() => { const s=document.querySelector('.slide.on'); const r=[];
              s.querySelectorAll('*').forEach(e=>{ const b=e.getBoundingClientRect(), sb=s.getBoundingClientRect();
                if(b.width>0 && (b.bottom>sb.bottom+1 || b.right>sb.right+1)) r.push(e.tagName+'.'+e.className); });
              return [s.scrollHeight>s.clientHeight+1, r.slice(0,5)]; }""")
            pg.screenshot(path=str(OUT / f"slide{i:02d}.png"))
            print(i, "overflow" if over[0] else "ok", over[1])
        pg.keyboard.press("n"); pg.wait_for_timeout(200)
        pg.screenshot(path=str(OUT / "slide_notes_example.png"))
        print("console errors:", errs)
    if "gate2" in what:
        pg = b.new_page(viewport={"width": 1440, "height": 900})
        pg.goto((ROOT / "gate2" / "index.html").as_uri()); pg.wait_for_timeout(400)
        pg.screenshot(path=str(OUT / "gate2_fold.png"))
        pg.screenshot(path=str(OUT / "gate2_full.png"), full_page=True)
    if "pdf" in what:
        pg = b.new_page(viewport={"width": 1280, "height": 720})
        pg.goto((ROOT / "pitch" / "index.html").as_uri()); pg.wait_for_timeout(400)
        pg.emulate_media(media="print")
        pg.pdf(path=str(OUT / "deck_print.pdf"), prefer_css_page_size=True, print_background=True)
        print("pdf written")
    b.close()
