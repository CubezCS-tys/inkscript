"""Experiment 40: each approach's HTML rendered in a real Chromium, next to the scan, for looking.

    /home/yassine/inkscript/.venv/bin/python render.py out/<approach> [--pages pid,pid] [--force]

For every out/<approach>/<pid>.html (and every page section of out/<approach>/docs/<stem>.html):
  out/<approach>/render/<pid>.png    the HTML as a reader would see it: Scheherazade New (Google Fonts), KaTeX 0.16.9
                                     (cdnjs) for \\(..\\) / \\[..\\], right-to-left, each block with a thin coloured
                                     edge by its type (legend at the top)
  out/<approach>/side/<pid>.jpg      three panels: the scan | the scan with the HTML's data-bbox boxes coloured by
                                     block type (only when the HTML has boxes) | the rendered HTML
The browser: Playwright's headless Chromium from out/venv (python3 -m venv out/venv; out/venv/bin/pip install
playwright==1.64.0; out/venv/bin/playwright install chromium-headless-shell). Without it the wrapped HTML is still
written (render/<pid>.html) and the side image has two panels.
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
from pathlib import Path

import cv2
import numpy as np

from common import HERE, OUT, page_image_path
from score import blocks_of

VENV_PY = OUT / "venv/bin/python"
COLOURS = {  # BGR for cv2, and the same as CSS hex
    "furniture": "#9e9e9e", "heading": "#d32f2f", "body": "#1e88e5", "list": "#00acc1", "verse": "#8e24aa",
    "footnote": "#fb8c00", "references": "#6d4c41", "caption": "#ec407a", "table": "#43a047",
    "equation": "#c2185b", "other": "#fdd835"}

TEMPLATE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=block" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
<style>
 body{margin:0;background:#fff;color:#111;font-family:'Scheherazade New',serif;font-size:21px;line-height:1.65}
 .sheet{width:860px;padding:28px 36px;box-sizing:border-box}
 .legend{font:12px sans-serif;direction:ltr;color:#555;margin-bottom:14px}
 .legend b{display:inline-block;width:10px;height:10px;margin:0 3px 0 10px;vertical-align:middle}
 h1,h2,h3,h4{margin:.5em 0 .3em;line-height:1.35;border-inline-start:4px solid %(heading)s;padding-inline-start:8px}
 h1{font-size:1.6em} h2{font-size:1.3em} h3{font-size:1.12em}
 p{margin:.35em 0;border-inline-start:3px solid %(body)s;padding-inline-start:8px;text-align:justify}
 ol,ul{border-inline-start:3px solid %(list)s;margin:.4em 0;padding-inline-start:2em}
 ol.references,.references ol,.references ul{border-color:%(references)s;font-size:.92em}
 li p{border:0;padding:0}
 .verse{display:grid;grid-template-columns:1fr 1fr;gap:0 3em;border-inline-start:3px solid %(verse)s;padding-inline-start:8px;margin:.15em 0}
 .verse .hemistich{text-align:center}
 aside.footnote{font-size:.85em;border-inline-start:3px solid %(footnote)s;padding-inline-start:8px;margin:.2em 0;color:#333}
 aside.footnote p{border:0;padding:0;margin:0}
 .footnotes,aside.footnote:first-of-type{border-top:1px solid #bbb;padding-top:4px}
 header.furniture,footer.furniture,.furniture{font-size:.8em;color:#777;border-inline-start:3px solid %(furniture)s;padding-inline-start:8px;margin:.2em 0}
 table{border-collapse:collapse;margin:.5em 0;font-size:.9em;border-inline-start:3px solid %(table)s}
 td,th{border:1px solid #999;padding:2px 6px;vertical-align:top} th{background:#f2f2f2}
 caption,figcaption,.caption{color:%(caption)s;font-size:.9em}
 .equation{border-inline-start:3px solid %(equation)s;padding-inline-start:8px;direction:ltr;text-align:center;margin:.4em 0}
 figure{border:1px dashed #bbb;margin:.5em 0;padding:6px;min-height:40px;border-inline-start:3px solid %(other)s}
 figure:empty::after,figure:not(:has(img))::before{content:'[figure]';color:#aaa;font:12px sans-serif}
 figure img{display:none}
 [lang=en],[lang=fr],[dir=ltr]{font-family:'Times New Roman',serif;font-size:.92em}
 section.page{border-bottom:2px dashed #ccc;padding-bottom:10px;margin-bottom:10px}
 sup{font-size:.7em}
</style></head><body><div class="sheet"><div class="legend">%(legend)s</div>
%(content)s
</div><script>
 window.addEventListener('load',()=>{try{renderMathInElement(document.body,{delimiters:[
  {left:'\\\\[',right:'\\\\]',display:true},{left:'\\\\(',right:'\\\\)',display:false},{left:'$$',right:'$$',display:true}],
  throwOnError:false})}catch(e){} document.fonts.ready.then(()=>{document.body.dataset.ready='1'})});
</script></body></html>"""

SHOT = r"""
import json, sys
from playwright.sync_api import sync_playwright
jobs = json.load(open(sys.argv[1]))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 860, "height": 1200}, device_scale_factor=1.5)
    for src, dst in jobs:
        try:
            pg.goto("file://" + src, wait_until="networkidle", timeout=60000)
            pg.wait_for_selector("body[data-ready='1']", timeout=20000)
        except Exception as e:
            print("  slow page", src, type(e).__name__, flush=True)
        pg.screenshot(path=dst, full_page=True)
        print("  shot", dst, flush=True)
    b.close()
"""


def body_of(h: str) -> str:
    m = re.search(r"<body[^>]*>(.*)</body>", h, re.S | re.I)
    h = m.group(1) if m else h
    h = re.sub(r"^\s*```(?:html)?\s*|\s*```\s*$", "", h)
    return re.sub(r"<(script|style)\b.*?</\1>", "", h, flags=re.S | re.I)


def wrap(content: str) -> str:
    legend = "".join(f'<b style="background:{c}"></b>{k}' for k, c in COLOURS.items())
    return TEMPLATE % dict(COLOURS, legend=legend, content=content)


def hexbgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def boxes_panel(scan, blocks):
    img = scan.copy()
    H, W = img.shape[:2]
    over = img.copy()
    for b in blocks:
        if not b["bbox"]:
            continue
        x0, y0, x1, y1 = [int(v) for v in (b["bbox"][0] * W / 1000, b["bbox"][1] * H / 1000,
                                           b["bbox"][2] * W / 1000, b["bbox"][3] * H / 1000)]
        c = hexbgr(COLOURS.get(b["label"], "#000000"))
        cv2.rectangle(over, (x0, y0), (x1, y1), c, -1)
        cv2.rectangle(img, (x0, y0), (x1, y1), c, max(2, W // 600))
    return cv2.addWeighted(over, 0.18, img, 0.82, 0)


def side(scan_f: Path, html: str, png: Path | None, out: Path, height: int = 1800):
    scan = cv2.imread(str(scan_f), cv2.IMREAD_COLOR)
    blocks = blocks_of(html)
    panels = [scan]
    if any(b["bbox"] for b in blocks):
        panels.append(boxes_panel(scan, blocks))
    if png and png.exists():
        r = cv2.imread(str(png), cv2.IMREAD_COLOR)
        # the render is as long as its text: show it at the scan's width scale, cut or padded to the scan's height
        s = scan.shape[0] / height
        panels_h = []
        for p in panels:
            panels_h.append(cv2.resize(p, (int(p.shape[1] / s), height), interpolation=cv2.INTER_AREA))
        w = int(height * 0.72)
        r = cv2.resize(r, (w, int(r.shape[0] * w / r.shape[1])), interpolation=cv2.INTER_AREA)
        if r.shape[0] > height:                     # long render: two columns of the render side by side
            k = int(np.ceil(r.shape[0] / height))
            k = min(k, 3)
            parts = [r[i * height:(i + 1) * height] for i in range(k)]
            parts = [np.pad(p, ((0, height - p.shape[0]), (0, 0), (0, 0)), constant_values=255) for p in parts]
            r = np.hstack(parts[::-1])                # read right to left: the start of the text on the right
        else:
            r = np.pad(r, ((0, height - r.shape[0]), (0, 0), (0, 0)), constant_values=255)
        panels = panels_h + [r]
    else:
        s = scan.shape[0] / height
        panels = [cv2.resize(p, (int(p.shape[1] / s), height), interpolation=cv2.INTER_AREA) for p in panels]
    sep = np.full((height, 12, 3), 255, np.uint8)
    row = panels[0]
    for p in panels[1:]:
        row = np.hstack([row, sep, p])
    out.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(out), row, [cv2.IMWRITE_JPEG_QUALITY, 85])


def pages_of(adir: Path) -> dict:
    """pid -> HTML content, from page files and document files."""
    out = {}
    dd = adir / "docs"
    if dd.exists():
        for f in sorted(dd.glob("*.html")):
            h = f.read_text(encoding="utf-8")
            pos = [(m.start(), int(re.search(r'data-page="(\d+)"', m.group(0)).group(1)))
                   for m in re.finditer(r'<section\b[^>]*class="[^"]*\bpage\b[^"]*"[^>]*>', h)
                   if re.search(r'data-page="(\d+)"', m.group(0))]
            pos.append((len(h), None))
            for i, (s, n) in enumerate(pos[:-1]):
                out[f"{f.stem}_p{n:03d}"] = h[s:pos[i + 1][0]]
    for f in sorted(adir.glob("*.html")):
        out[f.stem] = f.read_text(encoding="utf-8")
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--pages", nargs="*", default=[], help="page ids (space-separated; ids can hold commas)")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    adir = Path(a.dir)
    if not adir.is_absolute():
        adir = (HERE / a.dir) if (HERE / a.dir).exists() else Path.cwd() / a.dir
    want = set(a.pages) or None
    pages = {k: v for k, v in pages_of(adir).items() if not want or k in want}
    rd = adir / "render"
    rd.mkdir(parents=True, exist_ok=True)
    jobs = []
    for pid, h in pages.items():
        wf, png = rd / f"{pid}.html", rd / f"{pid}.png"
        w = wrap(body_of(h))
        if a.force or not png.exists() or not wf.exists() or wf.read_text(encoding="utf-8") != w:
            wf.write_text(w, encoding="utf-8")
            jobs.append([str(wf), str(png)])
    browser = VENV_PY.exists()
    if jobs and browser:
        jf = rd / "_jobs.json"
        jf.write_text(json.dumps(jobs))
        r = subprocess.run([str(VENV_PY), "-c", SHOT, str(jf)], text=True)
        if r.returncode:
            print("browser failed: side images without the render")
            browser = False
    elif jobs:
        print("no browser (out/venv missing): wrapped HTML only")
    for pid, h in pages.items():
        try:
            scan = page_image_path(pid)
        except Exception as e:
            print("  no scan for", pid, type(e).__name__)
            continue
        side(scan, h, rd / f"{pid}.png", adir / "side" / f"{pid}.jpg")
    print(f"{len(pages)} pages -> {adir / 'side'}")


if __name__ == "__main__":
    main()
