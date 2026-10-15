"""Experiment 41: the owner's hand-check pages (no calls).

    /home/yassine/inkscript/.venv/bin/python handcheck.py --run argon --stems S1 S2 ...

out/handcheck/<stem>.html, one self-contained page per article: for each page of the article, the scan with the
blocks drawn and numbered (colour = block type) beside the digital page as built from Azure's text, every block
numbered with a yes / no choice and a note. Choices are kept in the browser (localStorage, per article) and can be
exported as JSON (button at the top), so nothing is lost when the page is closed.
"""
from __future__ import annotations

import argparse
import base64
import html as H
import json
import re
import sys
from pathlib import Path

import cv2

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, art_of, page_image  # noqa: E402
from render41 import COLOURS, block_boxes, boxes_panel, sections  # noqa: E402

HD = OUT / "handcheck"

CSS = """
:root{--bg:#fafaf7;--fg:#1d1d1b;--muted:#6b6b66;--card:#fff;--line:#e2e2dc;--yes:#2e7d32;--no:#c62828;--accent:#1565c0;
--heading:%(heading)s;--body:%(body)s;--list:%(list)s;--verse:%(verse)s;--footnote:%(footnote)s;--references:%(references)s;
--caption:%(caption)s;--table:%(table)s;--equation:%(equation)s;--furniture:%(furniture)s;--other:%(other)s}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#202020;
--line:#3a3a37;--yes:#66bb6a;--no:#ef5350;--accent:#64b5f6}}
:root[data-theme=dark]{--bg:#161615;--fg:#ecebe6;--muted:#a3a29b;--card:#202020;--line:#3a3a37;--yes:#66bb6a;--no:#ef5350;--accent:#64b5f6}
*{box-sizing:border-box} body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}
header.top{position:sticky;top:0;z-index:5;background:var(--card);border-bottom:1px solid var(--line);padding:8px 16px;
display:flex;flex-wrap:wrap;gap:8px 16px;align-items:center}
header.top h1{font-size:16px;margin:0} header.top .count{color:var(--muted)}
button{font:inherit;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 10px;cursor:pointer}
.help{max-width:1100px;margin:12px auto;padding:0 16px;color:var(--muted)}
.page{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:16px;padding:12px 16px;border-bottom:2px solid var(--line)}
@media (max-width:820px){.page{grid-template-columns:1fr}}
.scan img{width:100%%;height:auto;border:1px solid var(--line);position:sticky;top:56px}
.ptitle{grid-column:1/-1;font-weight:600}
.doc{font-family:'Scheherazade New',serif;font-size:20px;line-height:1.65}
.blk{display:flex;gap:8px;align-items:flex-start;border-inline-start:4px solid var(--c,#999);padding:4px 8px;margin:4px 0;
background:var(--card);border-radius:4px}
.blk .num{font:12px system-ui;color:var(--muted);min-width:26px;padding-top:6px}
.blk .content{flex:1;min-width:0;overflow-x:auto}
.blk .ctl{display:flex;flex-direction:column;gap:4px;font:13px system-ui;direction:ltr;min-width:96px}
.ctl .yn{display:flex;gap:4px} .ctl button{padding:2px 8px}
.blk.yes{outline:2px solid var(--yes)} .blk.no{outline:2px solid var(--no)}
.blk.yes .y{background:var(--yes);color:#fff} .blk.no .n{background:var(--no);color:#fff}
.ctl input{font:12px system-ui;width:100%%;border:1px solid var(--line);background:var(--bg);color:var(--fg);border-radius:4px;padding:2px 4px}
.type{font:11px system-ui;color:var(--muted)}
.content h1,.content h2,.content h3,.content h4,.content p,.content aside,.content header,.content footer,.content figure,
.content blockquote,.content li{margin:0}
.content h1{font-size:1.5em} .content h2{font-size:1.25em} .content h3{font-size:1.1em}
.verse{display:grid;grid-template-columns:1fr 1fr;gap:0 2em}.verse.free{display:block}.verse .hemistich{text-align:center}
table{border-collapse:collapse;font-size:.85em} td,th{border:1px solid var(--line);padding:2px 5px}
.equation{direction:ltr;text-align:center} .sic{text-decoration:underline wavy #e65100}
[data-added]{background:#fff3c4;color:#000} sup{color:var(--accent);font-size:.7em}
[lang=en],[lang=fr]{font-family:'Times New Roman',serif;font-size:.92em}
figure::after{content:'[figure] ' attr(data-description);color:var(--muted);font:12px system-ui}
.legend span{display:inline-block;margin-inline-end:10px;font-size:12px}.legend b{display:inline-block;width:10px;height:10px;margin-inline-end:3px}
"""

JS = r"""
const KEY = 'hc41:' + document.body.dataset.stem + ':' + document.body.dataset.run;
let S = {}; try { S = JSON.parse(localStorage.getItem(KEY) || '{}'); } catch (e) { S = {}; }
function save(){ try { localStorage.setItem(KEY, JSON.stringify(S)); } catch (e) {} count(); }
function count(){ const n = document.querySelectorAll('.blk').length; const y = Object.values(S).filter(v => v.ok === 'yes').length;
  const no = Object.values(S).filter(v => v.ok === 'no').length;
  document.getElementById('count').textContent = `${y} yes · ${no} no · ${n - y - no} not marked, of ${n} blocks`; }
function paint(el){ const id = el.dataset.id, v = S[id] || {}; el.classList.toggle('yes', v.ok === 'yes'); el.classList.toggle('no', v.ok === 'no');
  el.querySelector('input').value = v.note || ''; }
document.querySelectorAll('.blk').forEach(el => {
  const id = el.dataset.id;
  el.querySelector('.y').onclick = () => { S[id] = Object.assign(S[id] || {}, {ok: (S[id]||{}).ok === 'yes' ? null : 'yes'}); paint(el); save(); };
  el.querySelector('.n').onclick = () => { S[id] = Object.assign(S[id] || {}, {ok: (S[id]||{}).ok === 'no' ? null : 'no'}); paint(el); save(); };
  el.querySelector('input').oninput = e => { S[id] = Object.assign(S[id] || {}, {note: e.target.value}); save(); };
  paint(el);
});
document.getElementById('export').onclick = () => {
  const out = {stem: document.body.dataset.stem, run: document.body.dataset.run, exported: new Date().toISOString(),
    blocks: [...document.querySelectorAll('.blk')].map(el => ({block: el.dataset.id, page: +el.dataset.page,
      type: el.dataset.type, ok: (S[el.dataset.id]||{}).ok || null, note: (S[el.dataset.id]||{}).note || ''}))};
  const a = document.createElement('a'); a.href = URL.createObjectURL(new Blob([JSON.stringify(out, null, 1)], {type: 'application/json'}));
  a.download = `handcheck_${out.stem}_${out.run}.json`; a.click(); };
document.getElementById('allyes').onclick = () => { if (!confirm('Mark every unmarked block yes?')) return;
  document.querySelectorAll('.blk').forEach(el => { const id = el.dataset.id; if (!(S[id]||{}).ok) { S[id] = Object.assign(S[id]||{}, {ok:'yes'}); paint(el);} }); save(); };
document.getElementById('theme').onclick = () => { const r = document.documentElement;
  r.dataset.theme = r.dataset.theme === 'dark' ? 'light' : 'dark'; };
count();
window.addEventListener('load', () => { try { renderMathInElement(document.body, {delimiters: [
  {left: '\\[', right: '\\]', display: true}, {left: '\\(', right: '\\)', display: false}], throwOnError: false}); } catch (e) {} });
"""


def blocks_of_section(sec: str) -> list[tuple[str, str, str]]:
    """(n, type, outer HTML) of each top-level block of a page section (list wrappers dropped)."""
    import lxml.html as LH
    root = LH.fragment_fromstring(sec, create_parent="div")
    out = []
    for el in root.xpath(".//*[@data-n]"):
        h = LH.tostring(el, encoding="unicode")
        if el.tag == "li":
            h = f"<ol style='list-style:none;padding:0;margin:0'>{h}</ol>"
        out.append((el.get("data-n"), el.get("data-type"), h))
    return out


def build(run: str, stem: str):
    from structure import COARSE
    a = art_of(stem)
    secs = sections(run, stem)
    pages_html = []
    nb = 0
    for p in range(a["first"], a["last"] + 1):
        s = secs.get(p, "")
        scan = cv2.imread(str(page_image(a, p)), cv2.IMREAD_COLOR)
        img = boxes_panel(scan, block_boxes(s))
        w = 1100
        img = cv2.resize(img, (w, int(img.shape[0] * w / img.shape[1])), interpolation=cv2.INTER_AREA)
        b64 = base64.b64encode(cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 72])[1].tobytes()).decode()
        rows = []
        for n, t, h in blocks_of_section(s):
            nb += 1
            c = COLOURS.get(COARSE.get(t, "other"), "#999")
            rows.append(f'<div class="blk" data-id="{n}" data-page="{p}" data-type="{t}" style="--c:{c}">'
                        f'<div class="num">{n}</div><div class="content"><div class="type">{H.escape(t)}</div>{h}</div>'
                        f'<div class="ctl"><div class="yn"><button class="y" title="right">yes</button>'
                        f'<button class="n" title="wrong">no</button></div><input placeholder="note"></div></div>')
        pages_html.append(f'<section class="page"><div class="ptitle">Page {p}</div>'
                          f'<div class="scan"><img loading="lazy" src="data:image/jpeg;base64,{b64}" alt="scan of page {p}"></div>'
                          f'<div class="doc" dir="rtl">{"".join(rows) or "<i>no blocks</i>"}</div></section>')
    legend = "".join(f'<span><b style="background:{c}"></b>{k}</span>' for k, c in COLOURS.items())
    doc = f"""<!doctype html><html lang="ar"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Hand check {H.escape(stem)}</title>
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=swap" rel="stylesheet">
<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.css">
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/katex.min.js"></script>
<script src="https://cdnjs.cloudflare.com/ajax/libs/KaTeX/0.16.9/contrib/auto-render.min.js"></script>
<style>{CSS % COLOURS}</style></head>
<body data-stem="{H.escape(stem)}" data-run="{run}">
<header class="top"><h1>Hand check · {H.escape(stem)} · {run}</h1><span class="count" id="count"></span>
<button id="export">Export my marks (JSON)</button><button id="allyes">Mark the rest yes</button><button id="theme">Light / dark</button></header>
<div class="help"><p>Each page: the scan on the left with the blocks drawn and numbered (colour = type), the digital page on the
right built from Azure's words. For each numbered block, press <b>yes</b> if it is right (the right type, the right lines,
in the right place in the reading order, the right text; tables, verse halves, equations and footnote links as printed),
or <b>no</b> and say why in the note. Your marks stay in this browser; press <i>Export</i> to save them as a file.</p>
<p class="legend">{legend}</p><p>{H.escape(a['why'])}; {a['n']} pages ({a['kind']}).</p></div>
{''.join(pages_html)}
<script>{JS}</script></body></html>"""
    HD.mkdir(parents=True, exist_ok=True)
    f = HD / f"{stem}.html"
    f.write_text(doc, encoding="utf-8")
    print(f"{f}  {nb} blocks, {f.stat().st_size / 1e6:.1f} MB")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--run", default="argon")
    ap.add_argument("--stems", nargs="+", required=True)
    a = ap.parse_args()
    for s in a.stems:
        build(a.run, s)


if __name__ == "__main__":
    main()
