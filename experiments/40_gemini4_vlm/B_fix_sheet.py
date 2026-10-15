"""Experiment 40, approach B: a picture of the fixes Gemini flagged on Azure's lines.

For each flagged fix: the crop of the printed line from the scan, Azure's text with the replaced part marked, the
fix, Gemini's reason and, on truth pages, the verdict against the truth (right / wrong / neutral). Written as HTML
and screenshot in Chromium (out/venv's Playwright) so Arabic shapes properly.

    /home/yassine/inkscript/.venv/bin/python B_fix_sheet.py v1 [--pages pid ...] [--name truth]
"""
from __future__ import annotations

import argparse
import base64
import html
import json
import subprocess

import cv2

from B_azure_anchored import fix_verdicts, page_lines, unit_of, vdir
from common import OUT, page_image_path

SHOT = r"""
import sys
from playwright.sync_api import sync_playwright
with sync_playwright() as p:
    b = p.chromium.launch()
    pg = b.new_page(viewport={"width": 1400, "height": 1000}, device_scale_factor=1)
    pg.goto("file://" + sys.argv[1], wait_until="networkidle", timeout=60000)
    pg.evaluate("document.fonts.ready")
    pg.wait_for_timeout(800)
    pg.screenshot(path=sys.argv[2], full_page=True, type="jpeg", quality=85)
    b.close()
"""

COL = {"right": "#2e7d32", "wrong": "#c62828", "neutral": "#757575", "": "#1565c0"}


def crop(pid, px, pad=14):
    img = cv2.imread(str(page_image_path(pid)))
    h, w = img.shape[:2]
    x0, y0, x1, y1 = [int(v) for v in px]
    c = img[max(0, y0 - pad):min(h, y1 + pad), max(0, x0 - pad):min(w, x1 + pad)]
    s = min(1.0, 1300 / max(1, c.shape[1]))
    if s < 1:
        c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)), interpolation=cv2.INTER_AREA)
    return base64.b64encode(cv2.imencode(".jpg", c, [cv2.IMWRITE_JPEG_QUALITY, 85])[1]).decode()


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("variant")
    ap.add_argument("--pages", nargs="*")
    ap.add_argument("--name", default="fixes")
    ap.add_argument("--max", type=int, default=60)
    a = ap.parse_args()
    d = vdir(a.variant)
    verdict = {(r["page"], r["line"], r["frm"]): r for r in fix_verdicts(a.variant, a.pages)}
    rows = []
    for bf in sorted((d / "book").glob("*.json")):
        pid = bf.stem
        if a.pages and pid not in a.pages:
            continue
        L = {l["id"]: l for l in page_lines(unit_of(pid))}
        for f in json.loads(bf.read_text(encoding="utf-8"))["fixes_applied"]:
            base = L.get(f.get("base") or f["line"]) or L.get(f["line"].rstrip("abcdefgh"))
            if not base or not base.get("px"):
                continue
            v = verdict.get((pid, f["line"], f["from"]))
            rows.append((pid, base, f, v))
    rows = rows[:a.max]
    n = {k: sum(1 for r in rows if r[3] and r[3]["faithful"] == k) for k in ("right", "wrong", "neutral")}
    parts = [f"""<!doctype html><html><head><meta charset="utf-8">
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=block" rel="stylesheet">
<style>body{{font-family:'Scheherazade New',serif;margin:20px;background:#fff;color:#222;width:1340px}}
.r{{border:1px solid #ddd;border-left:8px solid;margin:10px 0;padding:8px 12px}} img{{max-width:1300px;display:block}}
.t{{font-size:24px;direction:rtl;margin:4px 0}} .m{{font-family:sans-serif;font-size:13px;color:#555}}
del{{background:#ffcdd2;text-decoration:none}} ins{{background:#c8e6c9;text-decoration:none}}
h1{{font-family:sans-serif;font-size:20px}}</style></head><body>
<h1>Approach B ({a.variant}): fixes Gemini flagged on Azure's lines - {len(rows)} shown.
On truth pages: <span style="color:{COL['right']}">right {n['right']}</span>,
<span style="color:{COL['wrong']}">wrong {n['wrong']}</span>, <span style="color:{COL['neutral']}">neutral {n['neutral']}</span>;
blue = no truth for this page (judge by eye).</h1>"""]
    for pid, base, f, v in rows:
        vv = v["faithful"] if v else ""
        t = base["text"]
        i = t.find(f["from"])
        az = html.escape(t[:i]) + "<del>" + html.escape(f["from"]) + "</del>" + html.escape(t[i + len(f["from"]):]) \
            if i >= 0 else html.escape(t)
        fx = html.escape(t[:i]) + "<ins>" + html.escape(f.get("to") or "") + "</ins>" + \
            html.escape(t[i + len(f["from"]):]) if i >= 0 else ""
        parts.append(f"""<div class="r" style="border-left-color:{COL[vv]}"><div class="m">{pid} {f['line']} -
<b style="color:{COL[vv]}">{vv or 'no truth'}</b> - Gemini's reason: {html.escape(f.get('why') or '')}</div>
<img src="data:image/jpeg;base64,{crop(pid, base['px'])}"><div class="t">Azure: {az}</div><div class="t">Fixed: {fx}</div></div>""")
    parts.append("</body></html>")
    out = OUT / "B_azure_anchored" / f"fix_sheet_{a.name}.html"
    out.write_text("\n".join(parts), encoding="utf-8")
    jpg = out.with_suffix(".jpg")
    subprocess.run([str(OUT / "venv/bin/python"), "-c", SHOT, str(out), str(jpg)], check=True)
    print("wrote", out, jpg)


if __name__ == "__main__":
    main()
