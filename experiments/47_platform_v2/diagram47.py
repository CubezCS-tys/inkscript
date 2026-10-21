"""Experiment 47: the platform v2 schema as one self-contained page (inline SVG, light/dark), adapted from experiment
46's diagram46.py: tables grouped as in schema47.sql (provenance, ink, readings, bibliographic, people, citations,
quality, outside data), each box with its row count, its plain description (the @role line), primary key, foreign
keys and a few telling columns; foreign keys inside a group are drawn, keys to another group are named in the box.
Read from the db itself (PRAGMA), so re-running it after a load redraws the counts.
Also writes ink.html, the "show me the ink" page every canned query links to (?a=<anchor_pk>).

    .venv/bin/python experiments/47_platform_v2/diagram47.py [--db DB] [--out DIR]
"""
from __future__ import annotations

import argparse
import html
import sqlite3
import sys
import textwrap
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common47 import DB  # noqa: E402
from schema_doc47 import parse_sql  # noqa: E402

BASE = "http://127.0.0.1:8003/platform_v2/"
CLS = ["g1", "g2", "g3", "g4", "g5", "g6", "g7", "g8"]
EXTRA = {"documents": ["level", "scan_pages"], "pages": ["printed_folio", "running_head"],
         "ink_anchors": ["anchor_key", "method"], "versions": ["run", "is_current", "current_reason"],
         "blocks": ["role", "text", "trust"], "text_corrections": ["layer", "azure_reading", "printed", "proposed"],
         "publications": ["status", "title_shown"], "metadata_assertions": ["field", "form", "value", "is_chosen"],
         "citation_mentions": ["kind", "marker", "printed", "resolve_method"], "cited_works": ["pub_type", "title"],
         "citation_links": ["status", "method", "score"], "persons": ["status", "preferred_name_ar"],
         "authorships": ["role_code", "method"], "flags": ["kind", "severity"], "patches": ["source", "op"],
         "reviews": ["subject_kind", "verdict"], "catalogue_reports": ["kind", "who_is_right"],
         "quran_citations": ["sura", "aya_from"], "verse_lines": ["text"], "runs": ["kind", "model", "usd"]}
W, LH, HEAD, COLGAP, TOP, DLH = 270, 14, 24, 40, 70, 13
PER_COL = 5


def load(con):
    t = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'search_fts_%' "
                               "AND name NOT LIKE 'sqlite_%'"):
        cols = [(r[1], r[5]) for r in con.execute(f"PRAGMA table_info([{name}])")]
        fks = {}
        for r in con.execute(f"PRAGMA foreign_key_list([{name}])"):
            fks.setdefault(r[0], [r[2], [], []])
            fks[r[0]][1].append(r[3])
            fks[r[0]][2].append(r[4])
        try:
            n = con.execute(f"SELECT count(*) FROM [{name}]").fetchone()[0]
        except Exception:
            n = 0
        t[name] = dict(cols=cols, fks=list(fks.values()), n=n)
    return t


def lines_of(name, info, desc):
    out = [(d, "desc", None) for d in textwrap.wrap(desc or "", 44)[:4]]
    pks = [c for c, pk in sorted(info["cols"], key=lambda x: x[1]) if pk]
    if pks:
        out.append(("PK " + ", ".join(pks), "pk", pks[0]))
    for parent, cs, ps in info["fks"]:
        out.append((f"{', '.join(cs)} → {parent}", "fk" if len(cs) == 1 else "fk2", cs[0]))
    for c in EXTRA.get(name, []):
        if c in [x for x, _ in info["cols"]] and c not in pks:
            out.append((c, "col", c))
    return out


def build(con, groups):
    T = load(con)
    desc = {name: role for g, ts in groups for name, role, _ in ts}
    pos, frames, x = {}, [], 20
    for gi, (title, ts) in enumerate(groups):
        names = [n for n, _, _ in ts if n in T]
        gx, gbottom = x, 0
        for k in range(0, len(names), PER_COL):
            y = TOP + 34
            for name in names[k:k + PER_COL]:
                ls = lines_of(name, T[name], desc.get(name))
                h = HEAD + LH * len(ls) + 10
                pos[name] = dict(x=x, y=y, h=h, lines=ls, g=gi)
                y += h + 16
            gbottom = max(gbottom, y)
            x += W + COLGAP
        frames.append((title, CLS[gi % len(CLS)], gx - 12, TOP, x - COLGAP - gx + 24, gbottom - TOP))
        x += 24
    width, height = x, max(f[5] for f in frames) + TOP + 30

    def row_y(name, col):
        p = pos[name]
        for i, (_, kind, c) in enumerate(p["lines"]):
            if c == col and kind in ("pk", "fk", "fk2", "col"):
                return p["y"] + HEAD + LH * i + LH * 0.7
        return p["y"] + HEAD / 2

    svg = []
    for title, cls, fx, fy, fw, fh in frames:
        svg.append(f'<rect class="frame {cls}" x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="10"/>'
                   f'<text class="gtitle" x="{fx + 12}" y="{fy + 22}">{html.escape(title.split(" — ")[0])}</text>')
    nin = nout = 0
    for name, info in T.items():
        if name not in pos:
            continue
        for parent, cs, ps in info["fks"]:
            if parent not in pos:
                continue
            if pos[parent]["g"] != pos[name]["g"]:
                nout += 1
                continue
            nin += 1
            c, p = pos[name], pos[parent]
            y1, y2 = row_y(name, cs[0]), row_y(parent, ps[0] or "")
            kind = "e-fk" if len(cs) == 1 else "e-compound"
            if name == parent:
                x1 = c["x"] + W
                d = f"M{x1},{y1} C{x1 + 30},{y1} {x1 + 30},{y2 - 12} {x1},{p['y'] + HEAD / 2}"
            elif abs(c["x"] - p["x"]) < 1:
                x1 = c["x"] + W
                bend = 26 + abs(y1 - y2) * 0.05
                d = f"M{x1},{y1} C{x1 + bend},{y1} {x1 + bend},{y2} {x1 + 1},{y2}"
            elif p["x"] > c["x"]:
                x1, x2 = c["x"] + W, p["x"]
                m = (x1 + x2) / 2
                d = f"M{x1},{y1} C{m},{y1} {m},{y2} {x2},{y2}"
            else:
                x1, x2 = c["x"], p["x"] + W
                m = (x1 + x2) / 2
                d = f"M{x1},{y1} C{m},{y1} {m},{y2} {x2},{y2}"
            svg.append(f'<path class="edge {kind}" d="{d}" marker-end="url(#arrow-{kind})"><title>'
                       f'{html.escape(name + "." + ", ".join(cs) + " → " + parent)}</title></path>')
    for name, p in pos.items():
        x0, y0 = p["x"], p["y"]
        svg.append(f'<a href="{BASE}{name}" target="_blank"><title>{html.escape(desc.get(name) or "")}</title>'
                   f'<g class="box"><rect class="body" x="{x0}" y="{y0}" width="{W}" height="{p["h"]}" rx="6"/>'
                   f'<path class="head" d="M{x0},{y0 + HEAD} V{y0 + 6} a6,6 0 0 1 6,-6 H{x0 + W - 6} a6,6 0 0 1 6,6 '
                   f'V{y0 + HEAD} Z"/><text class="tname" x="{x0 + 9}" y="{y0 + 16.5}">{name}</text>'
                   f'<text class="tcount" x="{x0 + W - 9}" y="{y0 + 16.5}" text-anchor="end">{T[name]["n"]:,}</text>'
                   '</g></a>')
        for i, (text, kind, _) in enumerate(p["lines"]):
            ty = y0 + HEAD + LH * i + LH * 0.75 + 2
            mark = {"pk": "◆ ", "fk": "→ ", "fk2": "⇢ ", "col": "· ", "desc": ""}[kind]
            svg.append(f'<text class="c c-{kind}" x="{x0 + 10}" y="{ty}">{mark}{html.escape(text)}</text>')
    defs = "".join(f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path class="ah {k}" d="M0,0 L10,5 L0,10 z"/></marker>'
                   for k in ("e-fk", "e-compound"))
    body = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="Tables of platform_v2.db and their foreign keys"><defs>{defs}</defs>'
            + "".join(svg) + "</svg>")
    nfk = sum(len(i["fks"]) for i in T.values())
    views = [r[0] for r in con.execute("SELECT name FROM sqlite_master WHERE type='view' ORDER BY name")]
    lst = []
    for gi, (title, ts) in enumerate(groups):
        items = []
        for name, role, _ in ts:
            if name not in T:
                continue
            rel = "; ".join(f"{', '.join(cs)} → {p}" for p, cs, _ in T[name]["fks"]) or "—"
            items.append(f'<li><a href="{BASE}{name}">{name}</a> <span class="n">{T[name]["n"]:,}</span><br>'
                         f'<span class="desc">{html.escape(role or "")}</span><br><span class="rel">{html.escape(rel)}'
                         f'</span></li>')
        lst.append(f'<section><h3>{html.escape(title)}</h3><ul>{"".join(items)}</ul></section>')
    lst.append("<section><h3>Views (computed, never stored)</h3><ul>" + "".join(
        f'<li><a href="{BASE}{v}">{v}</a></li>' for v in views) + "</ul></section>")
    return PAGE.format(svg=body, ntables=len(pos), nfk=nfk, nin=nin, nout=nout, nviews=len(views),
                       tlist="".join(lst))


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Platform v2 schema</title>
<style>
:root {{ --bg:#f7f6f2; --fg:#1d1d1f; --muted:#6b6a66; --box:#ffffff; --line:#c9c6bd; --edge:#4a5bd0; --edge2:#b0721e;
  --pk:#1d1d1f; --head:#2e3440; --headfg:#fff; --g1:#eeeeee; --g2:#e6f2ec; --g3:#e8eefc; --g4:#f2ece0; --g5:#f4e8f1;
  --g6:#fbeee0; --g7:#f6ebe4; --g8:#eaf1f4; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97;
  --box:#212328; --line:#3c3f46; --edge:#8d9bff; --edge2:#e3a857; --pk:#f2f0ea; --head:#3b4252; --headfg:#f2f2f2;
  --g1:#222326; --g2:#1b2a23; --g3:#1d2333; --g4:#2a261e; --g5:#2b1f29; --g6:#2d2619; --g7:#2d221c; --g8:#1c272b; }} }}
:root[data-theme="dark"] {{ --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97; --box:#212328; --line:#3c3f46; --edge:#8d9bff;
  --edge2:#e3a857; --pk:#f2f0ea; --head:#3b4252; --headfg:#f2f2f2; --g1:#222326; --g2:#1b2a23; --g3:#1d2333;
  --g4:#2a261e; --g5:#2b1f29; --g6:#2d2619; --g7:#2d221c; --g8:#1c272b; }}
html, body {{ margin:0; background:var(--bg); color:var(--fg); font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
header, .list, .legend {{ max-width:1100px; margin:0 auto; padding:0 16px; }}
h1 {{ font-size:1.5rem; margin:20px 0 4px; }} p {{ margin:6px 0; }} .muted {{ color:var(--muted); }} a {{ color:var(--edge); }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px 20px; font-size:13px; margin-top:10px; }}
.sw {{ display:inline-block; width:22px; height:0; border-top:2px solid; vertical-align:middle; margin-right:6px; }}
.scroll {{ overflow:auto; -webkit-overflow-scrolling:touch; margin:12px 0; border-top:1px solid var(--line); border-bottom:1px solid var(--line); }}
svg {{ display:block; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}
.frame {{ stroke:var(--line); }} .g1 {{ fill:var(--g1); }} .g2 {{ fill:var(--g2); }} .g3 {{ fill:var(--g3); }} .g4 {{ fill:var(--g4); }}
.g5 {{ fill:var(--g5); }} .g6 {{ fill:var(--g6); }} .g7 {{ fill:var(--g7); }} .g8 {{ fill:var(--g8); }}
.gtitle {{ font:600 15px system-ui, sans-serif; fill:var(--fg); }}
.box .body {{ fill:var(--box); stroke:var(--line); }} .box .head {{ fill:var(--head); }} .box:hover .body {{ stroke:var(--edge); stroke-width:2; }}
.tname {{ fill:var(--headfg); font-weight:700; font-size:12.5px; }} .tcount {{ fill:var(--headfg); opacity:.75; font-size:11px; }}
.c {{ font-size:11px; fill:var(--muted); }} .c-desc {{ font-family:system-ui, sans-serif; font-size:11.5px; fill:var(--fg); }}
.c-pk {{ fill:var(--pk); font-weight:700; }} .c-fk {{ fill:var(--edge); }} .c-fk2 {{ fill:var(--edge2); }}
.edge {{ fill:none; stroke-width:1.4; }} .e-fk {{ stroke:var(--edge); }} .e-compound {{ stroke:var(--edge2); stroke-dasharray:5 3; }}
.ah.e-fk {{ fill:var(--edge); }} .ah.e-compound {{ fill:var(--edge2); }}
.list {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:4px 24px; padding-bottom:32px; }}
.list h3 {{ font-size:1rem; margin:14px 0 4px; }} .list ul {{ list-style:none; padding:0; margin:0; }}
.list li {{ margin:0 0 6px; font-size:14px; }} .rel {{ color:var(--muted); font-size:12.5px; }} .desc {{ font-size:13.5px; }}
.n {{ color:var(--muted); font-size:12px; }}
</style></head><body>
<header>
<h1>Platform v2: tables and links</h1>
<p class="muted">platform_v2.db (experiment 47): {ntables} tables and {nviews} views, {nfk} declared foreign keys
({nin} inside a group are drawn; {nout} to another group are named in the box). Each box: rows, what a row is,
◆ primary key, → foreign keys (⇢ compound, documentation only), · a few columns. Click a table to open it.
Any row with an <code>anchor_pk</code> opens its ink: <a href="ink.html">ink.html</a>.</p>
</header>
<div class="legend"><span><i class="sw" style="border-color:var(--edge)"></i>foreign key (a Datasette link)</span>
<span><i class="sw" style="border-color:var(--edge2);border-top-style:dashed"></i>compound key</span></div>
<div class="scroll">{svg}</div>
<div class="list">{tlist}</div>
</body></html>
"""

INK = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Show me the ink</title>
<style>
:root { --bg:#f7f6f2; --fg:#1d1d1f; --muted:#6b6a66; --line:#c9c6bd; --hl:#d4380d; --card:#fff; }
@media (prefers-color-scheme: dark) { :root:not([data-theme="light"]) { --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97;
  --line:#3c3f46; --hl:#ff7a45; --card:#212328; } }
:root[data-theme="dark"] { --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97; --line:#3c3f46; --hl:#ff7a45; --card:#212328; }
html, body { margin:0; background:var(--bg); color:var(--fg); font:15px/1.5 system-ui, sans-serif; }
main { max-width:980px; margin:0 auto; padding:12px 16px 40px; }
h1 { font-size:1.3rem; margin:8px 0; } .muted { color:var(--muted); font-size:13px; } code { font-size:13px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 12px; margin:10px 0; }
.ar { direction:rtl; font-size:18px; } canvas { max-width:100%; height:auto; border:1px solid var(--line); border-radius:6px; }
form { display:flex; gap:8px; flex-wrap:wrap; } input { font:inherit; padding:4px 8px; width:9em; }
a { color:#4a5bd0; }
</style></head><body><main>
<h1>Show me the ink</h1>
<form><label>anchor_pk <input name="a" id="a"></label><button>show</button></form>
<div id="info" class="card muted">An ink anchor is a page and a span of Azure's word numbers
(<code>stem|p&lt;page&gt;|w&lt;first&gt;-&lt;last&gt;</code>), the same in every run. Give its anchor_pk, or a
link that survives rebuilds: <code>?k=&lt;anchor_key&gt;</code>, or <code>?n=&lt;stem&gt;|&lt;note id&gt;</code>
(the first citation of that note in the shown reading; <code>&amp;i=2</code> for the second).</div>
<h2 style="font-size:1rem">The crop</h2><canvas id="crop"></canvas>
<h2 style="font-size:1rem">The page</h2><canvas id="page"></canvas>
<p class="muted">Page images: experiments/43_rehearsal/out/pages (300 of the 354 documents); boxes are ALTO page pixels
scaled to the image.</p>
</main>
<script>
const q = new URLSearchParams(location.search);
let a = q.get("a");
const DB = "/platform_v2";
async function row(sql, params) {
  const u = new URL(DB + ".json", location.origin);
  u.searchParams.set("sql", sql); u.searchParams.set("_shape", "objects");
  for (const [k, v] of Object.entries(params)) u.searchParams.set(k, v);
  const r = await fetch(u); const j = await r.json(); return (j.rows || [])[0];
}
function esc(s) { return String(s ?? "").replace(/[&<>]/g, c => ({"&":"&amp;","<":"&lt;",">":"&gt;"}[c])); }
(async () => {
  // links that survive a rebuild: the anchor's natural key, or a note of the shown reading (follow-up 2026-10-21)
  if (!a && q.get("k")) a = (await row("select anchor_pk from ink_anchors where anchor_key = :k", {k: q.get("k")}) || {}).anchor_pk;
  if (!a && q.get("n")) {
    const [s, n] = q.get("n").split("|");
    const r = await row(`select m.anchor_pk from citation_mentions m join versions v on v.version_id = m.version_id
      and v.is_current = 1 where v.stem = :s and m.container_id = :n and m.anchor_pk is not null
      order by m.reading_ord, m.seq_in_container limit 1 offset cast(:o as integer)`, {s, n, o: Math.max(0, (+q.get("i") || 1) - 1)});
    a = r && r.anchor_pk;
    if (!a) { document.getElementById("info").textContent = "No ink for " + q.get("n"); return; }
  }
  if (!a) return;
  document.getElementById("a").value = a;
  const an = await row("select * from ink_anchors where anchor_pk = :a", {a});
  const info = document.getElementById("info");
  if (!an) { info.textContent = "No anchor " + a; return; }
  const pg = await row("select * from pages where stem = :s and page = :p", {s: an.stem, p: an.page});
  info.innerHTML = `<b>${esc(an.anchor_key)}</b> · method <b>${esc(an.method)}</b> · lowest Azure confidence
    ${an.wc_min ?? "?"}<div class="ar">${esc(an.text_azure)}</div>
    <a href="${DB}/ink_anchors/${a}">anchor row</a> · <a href="${DB}/pages/${encodeURIComponent(an.stem)},${an.page}">page row</a>
    · <a href="${DB}/documents/${encodeURIComponent(an.stem)}">document</a>`;
  if (!pg || !pg.page_image_key) { info.innerHTML += "<p>No page image on this machine for this document.</p>"; return; }
  const img = new Image(); img.src = "/pages/" + pg.page_image_key;
  img.onload = () => {
    const sx = img.naturalWidth / pg.width_px, sy = img.naturalHeight / pg.height_px;
    const bx = an.x * sx, by = an.y * sy, bw = an.w * sx, bh = an.h * sy;
    const P = document.getElementById("page"), k = Math.min(1, 900 / img.naturalWidth);
    P.width = img.naturalWidth * k; P.height = img.naturalHeight * k;
    const c = P.getContext("2d"); c.drawImage(img, 0, 0, P.width, P.height);
    c.strokeStyle = getComputedStyle(document.documentElement).getPropertyValue("--hl"); c.lineWidth = 3;
    c.strokeRect(bx * k, by * k, bw * k, bh * k);
    const pad = 30, C = document.getElementById("crop");
    const cx = Math.max(0, bx - pad), cy = Math.max(0, by - pad);
    const cw = Math.min(img.naturalWidth - cx, bw + 2 * pad), ch = Math.min(img.naturalHeight - cy, bh + 2 * pad);
    C.width = cw; C.height = ch; const d = C.getContext("2d");
    d.drawImage(img, cx, cy, cw, ch, 0, 0, cw, ch); d.strokeStyle = c.strokeStyle; d.lineWidth = 2;
    d.strokeRect(bx - cx, by - cy, bw, bh);
  };
})();
</script></body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--out", default=str(Path(DB).parent))
    a = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    groups = [(g, ts) for g, ts in parse_sql((HERE / "schema47.sql").read_text(encoding="utf-8"))]
    groups[-1][1].append(("reconciliation_v46", "Builder report: platform.db (v46) counts beside v2's, and why.", {}))
    out = Path(a.out)
    (out / "schema47.html").write_text(build(con, groups), encoding="utf-8")
    (out / "ink.html").write_text(INK, encoding="utf-8")
    print(out / "schema47.html", out / "ink.html")


if __name__ == "__main__":
    main()
