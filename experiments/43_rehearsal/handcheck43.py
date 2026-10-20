"""Experiment 43: the owner's hand-check pages for a run's masters (no calls), after experiment 41's handcheck.py.

    .venv/bin/python handcheck43.py --run v33_300 --stems S1 S2 ...

out/<run>/handcheck/<stem>.html, one self-contained page per article, plus index.html. For each page: the scan on the
left with every block of our master drawn and numbered (colour = type), and on the right the same blocks in our
reading order: number, type, our text (Azure's words after the model's fixes, as the JATS/ALTO hold them), a yes / no
choice and a note. The doubtful spots flags43 found on that page are listed above it. Marks stay in the browser
(localStorage, per article) and "Export my marks" saves them as JSON. A link opens the article's Layout view.
"""
from __future__ import annotations

import argparse
import base64
import html as H
import json
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import views43 as V4  # noqa: E402
import mread as MR  # noqa: E402
import structure as ST  # noqa: E402
from views43 import art43 as art_of  # noqa: E402  (41's 55 or the fresh sample)

E41 = HERE.parent / "41_azure_structure"
sys.path.insert(0, str(E41))
from handcheck import CSS, JS  # noqa: E402
from render41 import COLOURS  # noqa: E402

KIND = dict(ST.COARSE, endnote="footnote", list="list", other_article="other", figure="caption", noise="furniture",
            ornament="furniture", sidebar="body", boxed="body", page_number="furniture")


def bgr(hexc: str):
    h = hexc.lstrip("#")
    return tuple(int(h[i:i + 2], 16) for i in (4, 2, 0))


def block_html(r) -> str:
    if r["type"] == "figure":
        d = r.get("description") or ""
        txt = " ".join(L.get("html") or "" for L in r["lines"])
        return f"<p><i>[picture]</i> {H.escape(d)}</p>" + (f"<p class='type'>words in it: {txt}</p>" if txt else "")
    lines = [L.get("html") or H.escape(L.get("text") or "") for L in r["lines"] + r.get("extra_lines", [])]
    tag = {"heading": "h3", "title": "h2"}.get(r["type"], "p")
    lang = r.get("lang") or ""
    dirattr = ' dir="ltr"' if lang in ("en", "fr") else ""
    if r["type"] == "verse":
        return f'<p{dirattr}>' + "<br>".join(lines) + "</p>"
    if r["type"] == "table":
        return f'<p{dirattr} style="font-size:.85em">' + " ⏐ ".join(lines) + "</p>"
    return f'<{tag}{dirattr} lang="{lang}">' + " ".join(lines) + f"</{tag}>"


def flags_by_page(run: str, stem: str) -> dict:
    """flags43's flags of this article by page (out/<run>/flags.json)."""
    f = HERE / "out" / run / "flags.json"
    if not f.exists():
        return {}
    art = json.loads(f.read_text(encoding="utf-8")).get("articles", {}).get(stem) or {}
    out = {}
    for x in art.get("flags") or []:
        out.setdefault(x.get("page"), []).append(x)
    return out


def build(run: str, stem: str, view_url: str, why: str = "") -> tuple[Path, int]:
    MR.MAST = (HERE / "out" / run / "masters").resolve()
    a = art_of(stem)
    ST.PAGES = HERE / "out" / "pages" if a.get("set") == "b" else E41 / "out" / "pages"
    doc = V4.load43(a)
    fl = flags_by_page(run, stem)
    pages_html, nb = [], 0
    for pg in doc["pages"]:
        p, W = pg["p"], pg["W"]
        recs = [r for r in doc["blocks"] if r["page"] == p]
        scan = cv2.imread(str(ST.page_image(a, p)), cv2.IMREAD_COLOR)
        k = scan.shape[1] / W
        rows = []
        for i, r in enumerate(recs, 1):
            nb += 1
            c = COLOURS.get(KIND.get(r["type"], "other"), "#999")
            box = V4.rec_px(r)
            if box:
                x0, y0, x1, y1 = (int(v * k) for v in box)
                cv2.rectangle(scan, (x0, y0), (x1, y1), bgr(c), 5)
                cv2.rectangle(scan, (x1 - 70, y0), (x1, y0 + 52), bgr(c), -1)
                cv2.putText(scan, str(i), (x1 - 66, y0 + 42), cv2.FONT_HERSHEY_SIMPLEX, 1.4, (255, 255, 255), 3)
            bid = f"p{p}-{i}"
            rows.append(f'<div class="blk" data-id="{bid}" data-page="{p}" data-type="{r["type"]}" style="--c:{c}">'
                        f'<div class="num">{i}</div><div class="content"><div class="type">{H.escape(r["type"])}'
                        f'{" · continues" if r.get("continued") else ""}</div>{block_html(r)}</div>'
                        f'<div class="ctl"><div class="yn"><button class="y" title="right">yes</button>'
                        f'<button class="n" title="wrong">no</button></div><input placeholder="note"></div></div>')
        w = 1100
        img = cv2.resize(scan, (w, int(scan.shape[0] * w / scan.shape[1])), interpolation=cv2.INTER_AREA)
        b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 70])[1].tobytes()).decode()
        fx = "".join(f"<li><b>{H.escape(str(x.get('severity', '')))}</b> {H.escape(str(x.get('kind', '')))}: "
                     f"{H.escape(str(x.get('reason') or ''))[:300]}</li>"
                     for x in fl.get(p, []))
        pages_html.append(f'<section class="page"><div class="ptitle">Page {p}'
                          f'{f"<ul class=type>{fx}</ul>" if fx else ""}</div>'
                          f'<div class="scan"><img loading="lazy" src="data:image/jpeg;base64,{b64}" alt="scan of page {p}"></div>'
                          f'<div class="doc" dir="{doc["ddir"]}">{"".join(rows) or "<i>no blocks</i>"}</div></section>')
    legend = "".join(f'<span><b style="background:{c}"></b>{k}</span>' for k, c in COLOURS.items())
    page = f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hand check {H.escape(stem)}</title>
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS % COLOURS}</style></head>
<body data-stem="{H.escape(stem)}" data-run="{run}">
<header class="top"><h1>Hand check · {H.escape(stem)} · {run}</h1><span class="count" id="count"></span>
<button id="export">Export my marks (JSON)</button><button id="allyes">Mark the rest yes</button><button id="theme">Light / dark</button>
<a href="{view_url}" target="_blank">Layout view ↗</a></header>
<div class="help"><p><b>{H.escape(doc["title"] or "")}</b></p><p>{H.escape(why)}</p>
<p>Each page: the scan on the left with our blocks drawn and numbered (colour = type); on the right the same blocks in
our reading order with our text. For each block press <b>yes</b> if it is right (type, lines, place in the reading
order, text, verse halves, table, note links) or <b>no</b> and say why in the note. Doubtful spots our checks found are
listed under the page number. Marks stay in this browser; press <i>Export</i> to save them as a file.</p>
<p class="legend">{legend}</p></div>
{''.join(pages_html)}
<script>{JS.replace("'hc41:'", "'hc43:'").split("window.addEventListener('load'")[0]}</script></body></html>"""
    out = HERE / "out" / run / "handcheck"
    out.mkdir(parents=True, exist_ok=True)
    f = out / f"{stem}.html"
    f.write_text(page, encoding="utf-8")
    return f, nb


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", required=True)
    ap.add_argument("--stems", nargs="+", required=True)
    ap.add_argument("--why", help="JSON {stem: why picked}")
    ap.add_argument("--view-base", default="http://127.0.0.1:8899/{run}/mirror/{stem}.html")
    a = ap.parse_args()
    why = json.loads(Path(a.why).read_text(encoding="utf-8")) if a.why else {}
    items = []
    for s in a.stems:
        f, nb = build(a.run, s, a.view_base.format(run=a.run, stem=s), why.get(s, ""))
        items.append((s, f.name, nb))
        print(f"{f}  {nb} blocks, {f.stat().st_size / 1e6:.1f} MB", flush=True)
    lis = "".join(f'<li><a href="{fn}">{H.escape(s)}</a> — {nb} blocks. {H.escape(why.get(s, ""))}</li>'
                  for s, fn, nb in items)
    (HERE / "out" / a.run / "handcheck" / "index.html").write_text(
        f"""<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hand check {a.run}</title><style>body{{font:16px/1.5 system-ui;max-width:900px;margin:24px auto;padding:0 16px}}</style>
</head><body><h1>Hand check · {a.run}</h1><p>One page per article: yes / no and a note per block, then Export my marks.</p>
<ol>{lis}</ol></body></html>""", encoding="utf-8")


if __name__ == "__main__":
    main()
