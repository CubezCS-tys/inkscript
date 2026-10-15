"""Experiment 41: pictures. Each page section of out/<run>/docs/<stem>.html rendered in headless Chromium (exp 40's
template: Scheherazade New, KaTeX, a coloured edge by block type) and put beside the scan.

    /home/yassine/inkscript/.venv/bin/python render41.py --runs argon flash [--stems ...] [--pages stem_p003 ...]

  out/<run>/render/<stem>_pNNN.png     the page as a reader sees it
  out/side/<stem>_pNNN.jpg             scan | Argon's blocks on the scan | Flash's blocks on the scan | Argon rendered |
                                       Flash rendered (the runs given, in order)
Browser: exp 40's out/venv (Playwright 1.64.0, chromium-headless-shell).
"""
from __future__ import annotations

import argparse
import html as H
import json
import re
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import COARSE, OUT, art_of, page_image, sample  # noqa: E402

VENV_PY = HERE.parent / "40_gemini4_vlm/out/venv/bin/python"
COLOURS = {"furniture": "#9e9e9e", "heading": "#d32f2f", "body": "#1e88e5", "list": "#00acc1", "verse": "#8e24aa",
           "footnote": "#fb8c00", "references": "#6d4c41", "caption": "#ec407a", "table": "#43a047",
           "equation": "#c2185b", "other": "#fdd835"}

TEMPLATE = """<!doctype html><html lang="ar" dir="rtl"><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=block" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
<style>
 body{margin:0;background:#fff;color:#111;font-family:'Scheherazade New',serif;font-size:21px;line-height:1.6}
 .sheet{width:860px;padding:22px 30px;box-sizing:border-box}
 .tag{font:11px sans-serif;color:#666;direction:ltr;margin-bottom:8px}
 [data-n]::before{content:attr(data-n);font:10px sans-serif;color:#999;margin-inline-end:4px}
 table[data-n]::before,ol::before{content:none}
 h1,h2,h3,h4{margin:.45em 0 .25em;line-height:1.35;border-inline-start:4px solid %(heading)s;padding-inline-start:8px}
 h1{font-size:1.55em} h2{font-size:1.28em} h3{font-size:1.1em} h4{font-size:1em}
 p{margin:.3em 0;border-inline-start:3px solid %(body)s;padding-inline-start:8px;text-align:justify}
 p.byline{border-color:%(heading)s;color:#444} p.caption{border-color:%(caption)s;color:%(caption)s}
 ol,ul{border-inline-start:3px solid %(list)s;margin:.3em 0;padding-inline-start:2em;list-style:none}
 ol.references{border-color:%(references)s;font-size:.92em}
 .verse{display:grid;grid-template-columns:1fr 1fr;gap:0 3em;border-inline-start:3px solid %(verse)s;padding-inline-start:8px;margin:.1em 0}
 .verse.free{display:block} .verse .hemistich{text-align:center}
 aside.footnote{display:block;font-size:.85em;border-inline-start:3px solid %(footnote)s;padding-inline-start:8px;margin:.15em 0;color:#333}
 .furniture{display:block;font-size:.8em;color:#777;border-inline-start:3px solid %(furniture)s;padding-inline-start:8px;margin:.15em 0}
 table{border-collapse:collapse;margin:.4em 0;font-size:.88em;border-inline-start:3px solid %(table)s}
 td,th{border:1px solid #999;padding:2px 5px;vertical-align:top} th{background:#f2f2f2}
 .equation{border-inline-start:3px solid %(equation)s;padding-inline-start:8px;direction:ltr;text-align:center;margin:.3em 0}
 figure{border:1px dashed #bbb;margin:.4em 0;padding:6px;min-height:30px;border-inline-start:3px solid %(other)s}
 figure::after{content:'[figure] ' attr(data-description);color:#888;font:12px sans-serif}
 blockquote{margin:.3em 1.5em;border-inline-start:3px solid %(body)s;padding-inline-start:8px}
 .sic{text-decoration:underline wavy #e65100;text-underline-offset:4px}
 [data-added]{background:#fff3c4}
 [data-continued]{border-top:2px dotted #888}
 [lang=en],[lang=fr]{font-family:'Times New Roman',serif;font-size:.92em}
 sup{font-size:.7em;color:#1565c0}
</style></head><body><div class="sheet"><div class="tag">%(tag)s</div>
%(content)s
</div><script>
 window.addEventListener('load',()=>{try{renderMathInElement(document.body,{delimiters:[
  {left:'\\\\[',right:'\\\\]',display:true},{left:'\\\\(',right:'\\\\)',display:false}],throwOnError:false})}catch(e){}
  document.fonts.ready.then(()=>{document.body.dataset.ready='1'})});
</script></body></html>"""

SHOT = r"""
import json, sys
from playwright.sync_api import sync_playwright
jobs = json.load(open(sys.argv[1]))
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 860, "height": 1200}, device_scale_factor=1.25)
    for src, dst in jobs:
        try:
            pg.goto("file://" + src, wait_until="networkidle", timeout=60000)
            pg.wait_for_selector("body[data-ready='1']", timeout=20000)
        except Exception as e:
            print("  slow page", src, type(e).__name__, flush=True)
        pg.screenshot(path=dst, full_page=True)
    b.close()
"""


def sections(run: str, stem: str) -> dict[int, str]:
    f = OUT / run / "docs" / f"{stem}.html"
    if not f.exists():
        return {}
    h = f.read_text(encoding="utf-8")
    out = {}
    for m in re.finditer(r'<section class="page" data-page="(\d+)"[^>]*>(.*?)</section>', h, re.S):
        out[int(m.group(1))] = m.group(2)
    return out


def block_boxes(sec: str) -> list[tuple[str, list[float], str]]:
    """(coarse label, 0-1000 box, n) of every block of a page section."""
    out = []
    for m in re.finditer(r'<[a-z0-9]+\b[^>]*\bdata-n="(\d+)"[^>]*>', sec):
        tag = m.group(0)
        t = re.search(r'data-type="([^"]+)"', tag)
        b = re.search(r'data-bbox="([^"]+)"', tag)
        if t and b:
            out.append((COARSE.get(t.group(1), "other"), [float(v) for v in b.group(1).split(",")], m.group(1)))
    return out


def hexbgr(h):
    h = h.lstrip("#")
    return (int(h[4:6], 16), int(h[2:4], 16), int(h[0:2], 16))


def boxes_panel(scan, boxes, numbers=True):
    img = scan.copy()
    Hh, W = img.shape[:2]
    over = img.copy()
    for lab, b, n in boxes:
        x0, y0, x1, y1 = int(b[0] * W / 1000), int(b[1] * Hh / 1000), int(b[2] * W / 1000), int(b[3] * Hh / 1000)
        c = hexbgr(COLOURS.get(lab, "#000000"))
        cv2.rectangle(over, (x0, y0), (x1, y1), c, -1)
        cv2.rectangle(img, (x0, y0), (x1, y1), c, max(2, W // 500))
    img = cv2.addWeighted(over, 0.2, img, 0.8, 0)
    if numbers:
        for lab, b, n in boxes:
            x1, y0 = int(b[2] * W / 1000), int(b[1] * Hh / 1000)
            fs = max(0.8, W / 1800)
            cv2.putText(img, n, (x1 + 4, y0 + int(24 * fs)), cv2.FONT_HERSHEY_SIMPLEX, fs, (255, 255, 255), 6)
            cv2.putText(img, n, (x1 + 4, y0 + int(24 * fs)), cv2.FONT_HERSHEY_SIMPLEX, fs,
                        hexbgr(COLOURS.get(lab, "#000")), 2)
    return img


def wrap(content: str, tag: str) -> str:
    return TEMPLATE % dict(COLOURS, content=content, tag=H.escape(tag))


def shoot(jobs):
    if not jobs:
        return
    jf = OUT / "_shot_jobs.json"
    jf.write_text(json.dumps(jobs))
    subprocess.run([str(VENV_PY), "-c", SHOT, str(jf)], text=True)


def fit_h(img, height):
    s = height / img.shape[0]
    return cv2.resize(img, (max(1, int(img.shape[1] * s)), height), interpolation=cv2.INTER_AREA)


def render_panel(png: Path, height: int):
    r = cv2.imread(str(png), cv2.IMREAD_COLOR)
    if r is None:
        return None
    w = int(height * 0.7)
    r = cv2.resize(r, (w, max(1, int(r.shape[0] * w / r.shape[1]))), interpolation=cv2.INTER_AREA)
    if r.shape[0] > height:
        k = min(3, int(np.ceil(r.shape[0] / height)))
        parts = [r[i * height:(i + 1) * height] for i in range(k)]
        parts = [np.pad(p, ((0, height - p.shape[0]), (0, 0), (0, 0)), constant_values=255) for p in parts]
        r = np.hstack(parts[::-1])
    else:
        r = np.pad(r, ((0, height - r.shape[0]), (0, 0), (0, 0)), constant_values=255)
    return r


def label_strip(img, text):
    bar = np.full((44, img.shape[1], 3), 255, np.uint8)
    cv2.putText(bar, text, (10, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (60, 60, 60), 2)
    return np.vstack([bar, img])


def render_pages(runs, stems=None, pids=None, height=1500, force=False):
    todo = []
    for a in sample():
        if stems and a["stem"] not in stems:
            continue
        for p in range(a["first"], a["last"] + 1):
            pid = f"{a['stem']}_p{p:03d}"
            if pids and pid not in pids:
                continue
            todo.append((a, p, pid))
    jobs = []
    secs = {}
    for run in runs:
        rd = OUT / run / "render"
        rd.mkdir(parents=True, exist_ok=True)
        for a, p, pid in todo:
            if (run, a["stem"]) not in secs:
                secs[(run, a["stem"])] = sections(run, a["stem"])
            s = secs[(run, a["stem"])].get(p)
            if s is None:
                continue
            wf, png = rd / f"{pid}.html", rd / f"{pid}.png"
            w = wrap(s, f"{run} · {pid}")
            if force or not png.exists() or not wf.exists() or wf.read_text(encoding="utf-8") != w:
                wf.write_text(w, encoding="utf-8")
                jobs.append([str(wf), str(png)])
    shoot(jobs)
    sd = OUT / "side"
    sd.mkdir(parents=True, exist_ok=True)
    for a, p, pid in todo:
        scan = cv2.imread(str(page_image(a, p)), cv2.IMREAD_COLOR)
        panels = [label_strip(fit_h(scan, height), "scan")]
        rend = []
        for run in runs:
            s = secs.get((run, a["stem"]), {}).get(p)
            if s is None:
                continue
            panels.append(label_strip(fit_h(boxes_panel(scan, block_boxes(s)), height), f"{run}: blocks"))
            r = render_panel(OUT / run / "render" / f"{pid}.png", height)
            if r is not None:
                rend.append(label_strip(r, f"{run}: rendered"))
        panels += rend
        sep = np.full((height + 44, 14, 3), 255, np.uint8)
        row = panels[0]
        for x in panels[1:]:
            row = np.hstack([row, sep, x])
        cv2.imwrite(str(sd / f"{pid}.jpg"), row, [cv2.IMWRITE_JPEG_QUALITY, 82])
    print(f"{len(todo)} pages -> {sd}")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--runs", nargs="+", default=["argon", "flash"])
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--pages", nargs="*")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    render_pages(a.runs, a.stems, set(a.pages) if a.pages else None, force=a.force)


if __name__ == "__main__":
    main()
