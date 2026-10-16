"""Print HTML pages to PDF with headless Chromium (Playwright). Run by prints.py with a Python that has Playwright
(experiments/40_gemini4_vlm/out/venv), not the project's .venv.

    <playwright python> print_worker.py JOBS.json

JOBS.json: [{"html": path, "pdf": path, "kind": "layout"|"onecol", "width": css px, "words": path}]. One browser for all jobs;
the layout view is printed once its own fitting has run (window.__fit); the web page once its fonts are in and
its tables fitted to the text width (window.__fitTables), with a page number at the foot. Both print at their
CSS page size. Before printing, the words as laid out (textlayer.WORDS_JS) go to the job's "words" file. One JSON
line per job on stdout.
"""
import json
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

FIT_WEB = """async () => { await document.fonts.ready;
  if (window.__fitTables) window.__fitTables();
  const T = [...document.querySelectorAll('.tscroll')].map(w => { const t = w.querySelector('table');
    return {w: w.clientWidth, t: t ? t.offsetWidth : 0, squeeze: !!(t && t.classList.contains('squeeze')),
            font: t ? parseFloat(getComputedStyle(t).fontSize) : 0}; });
  return {tables: T.length, squeezed: T.filter(x => x.squeeze).length, wider: T.filter(x => x.t > x.w + 1).length,
          min_font_px: T.length ? Math.min(...T.map(x => x.font)) : null}; }"""
FOOTER = ('<div style="width:100%;font-size:8px;font-family:serif;color:#777;text-align:center">'
          '<span class="pageNumber"></span></div>')
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textlayer import WORDS_JS  # noqa: E402  (a JS string; textlayer needs nothing else here)

jobs = json.loads(Path(sys.argv[1]).read_text())
with sync_playwright() as p:
    b = p.chromium.launch()
    print(json.dumps(dict(chromium=b.version)), flush=True)
    for j in jobs:
        t0 = time.time()
        r = dict(pdf=j["pdf"], kind=j["kind"])
        try:
            pg = b.new_page(viewport=dict(width=int(j.get("width") or 800), height=1100), color_scheme="light")
            pg.emulate_media(media="print")
            pg.goto(Path(j["html"]).resolve().as_uri(), wait_until="load", timeout=120000)
            if j["kind"] == "layout":
                pg.wait_for_function("window.__fit", timeout=120000)
                r["fit"] = pg.evaluate("window.__fit")
            else:                                    # the web page: its fonts, then its own table fitting
                r["fit"] = pg.evaluate(FIT_WEB)
            pg.wait_for_timeout(150)
            if j.get("words"):                       # the words as laid out, for the text layer (textlayer.py)
                Path(j["words"]).write_text(json.dumps(pg.evaluate(WORDS_JS, [j["kind"]]), ensure_ascii=False))
            Path(j["pdf"]).parent.mkdir(parents=True, exist_ok=True)
            foot = j["kind"] == "onecol"
            pg.pdf(path=j["pdf"], prefer_css_page_size=True, print_background=True, display_header_footer=foot,
                   header_template="<span></span>", footer_template=FOOTER, tagged=True, outline=True)
            pg.close()
            r["ok"] = True
        except Exception as e:                       # noqa: BLE001  (reported, the next job goes on)
            r["ok"] = False
            r["error"] = f"{type(e).__name__}: {e}"[:400]
        r["seconds"] = round(time.time() - t0, 2)
        print(json.dumps(r, ensure_ascii=False), flush=True)
    b.close()
