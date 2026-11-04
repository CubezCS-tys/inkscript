"""Experiment 60, test 2: tables and figures where the two masters disagree, drawn side by side (scan | Argon's
table | Claude's table), from the JATS (no calls).

    tables60.py   -> out/side/t2_tables.html (+ img/)
"""
from __future__ import annotations

import html
import xml.etree.ElementTree as ET
from pathlib import Path

from common60 import OUT, jl
from side60 import CSS, thumb

T2 = OUT / "t2"
CASES = [("0130-024-094-002", "p22t1"), ("0130-024-094-002", "p23t1"), ("0130-019-075-003", "p12t1"),
         ("0130-019-075-003", "p13t1"), ("0130-019-075-003", "p17t1"), ("0130-019-075-003", "p22t1")]
FIGS = [("0130-020-079-001", 17), ("0130-020-079-001", 18)]


def table_html(f: Path, tid: str) -> str:
    r = ET.parse(f).getroot()
    tw = next((t for t in r.iter("table-wrap") if t.get("id") == tid), None)
    if tw is None:
        return "<p>(no such table)</p>"
    rows = []
    for tr in tw.iter("tr"):
        cells = "".join(f"<td>{html.escape(' '.join(''.join(c.itertext()).split()))}</td>" for c in tr
                        if c.tag in ("td", "th"))
        rows.append(f"<tr>{cells}</tr>")
    return f"<table class='tb'>{''.join(rows)}</table>"


def figs_of(f: Path, page: int) -> list[str]:
    r = ET.parse(f).getroot()
    out = []
    for fg in r.iter("fig"):
        if (fg.get("id") or "").startswith(f"p{page}f"):
            cap = " ".join("".join(fg.find("caption").itertext()).split()) if fg.find("caption") is not None else ""
            out.append(f"{fg.get('id')} {cap[:80]}")
    return out


def main():
    side = OUT / "side"
    img = side / "img"
    secs = []
    for s, tid in CASES:
        p = int(tid[1:].split("t")[0])
        th = img / f"t2_{s}_p{p:03d}_big.jpg"
        thumb(s, p, th, 1500)
        secs.append(f"<section id='s_t2tab_{s}_{tid}'><h2>{s} table {tid} (page {p})</h2>"
                    f"<div class='row3'><div><img src='img/{th.name}' alt='scan of the page'></div>"
                    f"<div><p class='a hd'>Argon</p>{table_html(T2 / 'argon_build/masters' / f'{s}.jats.xml', tid)}</div>"
                    f"<div><p class='c hd'>Claude</p>{table_html(T2 / 'build/masters' / f'{s}.jats.xml', tid)}</div>"
                    f"</div></section>")
    for s, p in FIGS:
        th = img / f"t2_{s}_p{p:03d}_big.jpg"
        thumb(s, p, th, 1500)
        fa, fc = figs_of(T2 / "argon_build/masters" / f"{s}.jats.xml", p), figs_of(T2 / "build/masters" / f"{s}.jats.xml", p)
        secs.append(f"<section id='s_t2fig_{s}_{p}'><h2>{s} page {p}: figures</h2><div class='row3'>"
                    f"<div><img src='img/{th.name}' alt='scan of the page'></div>"
                    f"<div><p class='a hd'>Argon: {len(fa)}</p><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in fa)}</ul></div>"
                    f"<div><p class='c hd'>Claude: {len(fc)}</p><ul>{''.join(f'<li>{html.escape(x)}</li>' for x in fc)}</ul></div>"
                    f"</div></section>")
    css = CSS.replace("</style>", ".row3{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr) minmax(0,1fr);gap:10px}"
                      ".row3 img{max-width:100%}.tb{border-collapse:collapse;direction:rtl;font-size:12px}"
                      ".tb td{border:1px solid var(--line);padding:2px 4px}"
                      "@media (max-width:700px){.row3{grid-template-columns:1fr}}</style>")
    doc = (f"<!doctype html><html lang='en'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,"
           f"initial-scale=1'><title>Gate 1 tables</title>{css}</head><body><h1>Gate 1: tables and figures</h1>"
           f"<p class='m'>Experiment 60, test 2. Tables whose rows or cells differ between Argon's and Claude's masters, "
           f"and a page whose pictures were cut differently.</p>{''.join(secs)}</body></html>")
    (side / "t2_tables.html").write_text(doc, encoding="utf-8")
    print(side / "t2_tables.html")


if __name__ == "__main__":
    main()
