"""Experiment 60: the side-by-side of every page where Claude's master and Argon's differ (scan | Argon | Claude),
line by line, from the two ALTOs (both are built on Azure's same lines, so a line is the same line in both when its
box is). Text differences get a crop of the scan's line; role / order differences list the lines with each
reader's role and block number.

    side60.py --test t1 [--pages proof]           -> out/side/t1.html (+ out/side/img/)
    side60.py --test t2                           -> out/side/t2.html (pages where the two differ, gate-1 sample)
"""
from __future__ import annotations

import argparse
import html
import json
from pathlib import Path

from lxml import etree

from common60 import E43, OUT, jl

PAGES = E43 / "out" / "pages"
FIXED = E43 / "out" / "pages_fixed"


def lines_of(masters: Path, stem: str, page: int) -> list[dict]:
    f = masters / f"{stem}.alto.xml"
    root = etree.parse(str(f)).getroot()
    ns = root.nsmap.get(None)
    pg = root.find(f".//{{{ns}}}Page[@ID='page{page}']")
    out = []
    if pg is None:
        return out
    for bi, tb in enumerate(pg.iter(f"{{{ns}}}TextBlock"), 1):
        role = next((r[5:] for r in (tb.get("TAGREFS") or "").split() if r.startswith("role.")), "?")
        for ln in tb.iter(f"{{{ns}}}TextLine"):
            words = [s.get("CONTENT") for s in ln.iter(f"{{{ns}}}String")]
            alts = [a.text for s in ln.iter(f"{{{ns}}}String") for a in s.iter(f"{{{ns}}}ALTERNATIVE")]
            box = tuple(round(float(ln.get(k))) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
            out.append(dict(box=box, role=role, block=bi, text=" ".join(words), alts=alts))
    return out


def key(b):
    return (round(b[0] / 4), round(b[1] / 4))


def page_img(stem, page):
    f = FIXED / f"{stem}_p{page:03d}.jpg"
    return f if f.exists() else PAGES / f"{stem}_p{page:03d}.jpg"


def crop(stem, page, box, dst: Path, pad=14):
    import cv2
    if dst.exists():
        return
    img = cv2.imread(str(page_img(stem, page)))
    if img is None:
        return
    H, W = img.shape[:2]
    x, y, w, h = box
    c = img[max(0, y - pad):min(H, y + h + pad), max(0, x - pad):min(W, x + w + pad)]
    if c.size == 0:
        return
    s = min(1.0, 900 / c.shape[1])
    if s < 1:
        c = cv2.resize(c, (int(c.shape[1] * s), int(c.shape[0] * s)), interpolation=cv2.INTER_AREA)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), c, [cv2.IMWRITE_JPEG_QUALITY, 82])


def thumb(stem, page, dst: Path, height: int = 700):
    import cv2
    if dst.exists():
        return
    img = cv2.imread(str(page_img(stem, page)))
    if img is None:
        return
    s = height / img.shape[0]
    img = cv2.resize(img, (int(img.shape[1] * s), height), interpolation=cv2.INTER_AREA)
    dst.parent.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(dst), img, [cv2.IMWRITE_JPEG_QUALITY, 75])


def compare(A: Path, C: Path, stem: str, page: int):
    la, lc = lines_of(A, stem, page), lines_of(C, stem, page)
    ma, mc = {key(l["box"]): l for l in la}, {key(l["box"]): l for l in lc}
    text, struct = [], []
    # block order: the sequence of (role) with block numbers mapped through shared lines
    for k in list(ma) + [k for k in mc if k not in ma]:
        a, c = ma.get(k), mc.get(k)
        if a and c and a["text"] != c["text"]:
            text.append((a, c))
        if (a is None) != (c is None):
            struct.append((a, c))
        elif a and c and a["role"] != c["role"]:
            struct.append((a, c))
    # order: Claude's line order against Argon's
    oa = [k for k in ma if k in mc]
    oc = [k for k in mc if k in ma]
    order_same = oa == oc
    return text, struct, order_same, len(la), len(lc)


CSS = """<style>
:root{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--a:#9b4d00;--c:#0b5a8a;--line:#e3e0d8;--card:#fff}
@media (prefers-color-scheme: dark){:root{--bg:#191917;--fg:#ecebe6;--mut:#a3a29b;--a:#f0a35e;--c:#79c0f0;--line:#34332f;--card:#22221f}}
body{background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif;margin:0 auto;max-width:1300px;padding:16px}
h1{font-size:22px}h2{font-size:17px;margin-top:28px;border-top:1px solid var(--line);padding-top:14px}
.row{display:grid;grid-template-columns:minmax(0,1.3fr) minmax(0,1fr) minmax(0,1fr);gap:10px;align-items:start;
 border-bottom:1px solid var(--line);padding:6px 0}
.row img{max-width:100%;border:1px solid var(--line);background:#fff}
.t{direction:rtl;unicode-bidi:plaintext;font-family:'Noto Naskh Arabic','Amiri',serif;font-size:17px}
.a{color:var(--a)}.c{color:var(--c)}.m{color:var(--mut);font-size:13px}
.v{background:var(--card);border:1px solid var(--line);padding:8px 10px;border-radius:6px;margin:6px 0}
.hd{font-weight:600}.thumb{float:right;margin:0 0 8px 12px;max-width:260px}
@media (max-width:700px){.row{grid-template-columns:1fr}.thumb{float:none;max-width:100%}}
</style>"""


def page_section(stem, page, A, C, img_dir: Path, verdict: dict | None):
    text, struct, order_same, na, nc = compare(A, C, stem, page)
    tid = f"{stem}_p{page:03d}"
    thumb(stem, page, img_dir / f"{tid}_thumb.jpg")
    h = [f"<section id='s_{tid}'><h2 id='{tid}'>{html.escape(stem)} page {page}</h2>",
         f"<a href='img/{tid}_thumb.jpg'><img class='thumb' src='img/{tid}_thumb.jpg' alt='scan of the page'></a>"]
    if verdict:
        h.append("<div class='v'>" + " ".join(f"<b>{html.escape(k)}</b>: {html.escape(str(v))}<br>"
                                               for k, v in verdict.items()) + "</div>")
    h.append(f"<p class='m'>lines Argon {na}, Claude {nc}; text differs on {len(text)} lines; role / block differs "
             f"on {len(struct)}; reading order of shared lines {'same' if order_same else '<b>differs</b>'}</p>")
    if text:
        h.append("<div class='row hd'><div>scan</div><div class='a'>Argon</div><div class='c'>Claude</div></div>")
    for i, (a, c) in enumerate(text):
        cf = img_dir / f"{tid}_l{i:02d}.jpg"
        crop(stem, page, a["box"], cf)
        h.append(f"<div class='row'><div><img src='img/{cf.name}' alt='scan of the line'></div>"
                 f"<div class='t a'>{html.escape(a['text'])}</div><div class='t c'>{html.escape(c['text'])}</div></div>")
    if struct:
        h.append("<p class='hd'>Roles that differ (line: Argon role / block → Claude role / block)</p><ul>")
        for a, c in struct[:40]:
            l = a or c
            h.append(f"<li><span class='t'>{html.escape(l['text'][:90])}</span> — <span class='a'>"
                     f"{html.escape(a['role']) + ' b' + str(a['block']) if a else 'not on the page'}</span> → "
                     f"<span class='c'>{html.escape(c['role']) + ' b' + str(c['block']) if c else 'not on the page'}"
                     f"</span></li>")
        h.append("</ul>")
    h.append("<div style='clear:both'></div></section>")
    return "\n".join(h), dict(text=len(text), struct=len(struct), order_same=order_same)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--test", default="t1")
    ap.add_argument("--pages", help="json list of [stem, page] (default: the test's differing pages)")
    a = ap.parse_args()
    T = OUT / a.test
    A, C = T / "argon_build" / "masters", T / "build" / "masters"
    side = OUT / "side"
    img = side / "img"
    verdicts = jl(T / "page_verdicts.json") if (T / "page_verdicts.json").exists() else {}
    if a.pages:
        pages = jl(a.pages)
    elif a.test == "t1":
        pages = [[r["stem"], r["page"]] for r in jl(T / "pages.json") if not r["claude_same_as_argon_plain"]]
    else:
        pages = jl(T / "side_pages.json")
    secs, stats = [], {}
    for s, p in pages:
        sec, st = page_section(s, p, A, C, img, verdicts.get(f"{s} {p}"))
        secs.append(sec)
        stats[f"{s} {p}"] = st
    title = {"t1": "Claude vs Argon: proof pages", "t2": "Claude vs Argon: gate 1"}.get(a.test, a.test)
    toc = " · ".join(f"<a href='#{s}_p{p:03d}'>{s[:9]} p{p}</a>" for s, p in pages)
    doc = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' "
           f"content='width=device-width,initial-scale=1'><title>{title}</title>{CSS}</head><body>"
           f"<h1>{title}</h1><p class='m'>Experiment 60. Each page where the two masters differ: the scan's line, "
           f"Argon's text (orange), Claude's (blue). Built from the two ALTOs (same Azure lines). "
           f"{len(pages)} pages.</p><p class='m'>{toc}</p>" + "\n".join(secs) + "</body></html>")
    (side / f"{a.test}.html").write_text(doc, encoding="utf-8")
    (T / "side_stats.json").write_text(json.dumps(stats, ensure_ascii=False, indent=1))
    print(side / f"{a.test}.html", len(pages), "pages")


if __name__ == "__main__":
    main()
