"""Experiment 46: draw the platform database's tables and declared foreign keys as one self-contained page
(inline SVG, light/dark), /home/yassine/data/platform/schema.html, served by Datasette at
http://127.0.0.1:8002/diagram/schema.html. Read from the db itself (PRAGMA table_info / foreign_key_list), so
re-running it after a schema change redraws the page.

    .venv/bin/python experiments/46_platform_db/diagram46.py [--db DB] [--out FILE]
"""
from __future__ import annotations

import argparse
import html
import json
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common46 import DB  # noqa: E402

BASE = "http://127.0.0.1:8002/platform/"
# groups: (title, css class, [columns of tables]) ; columns are laid out left to right
GROUPS = [
    ("People & institutions", "g-people", [["people", "person_names", "article_authors", "affiliations",
                                            "institutions", "institution_variants"]]),
    ("Catalogue & bibliographic", "g-cat", [["articles", "journals", "issues", "runs", "article_runs"],
                                            ["catalogue_records", "catalogue_authors", "article_dates", "abstracts",
                                             "keywords", "subjects"]]),
    ("Content", "g-content", [["blocks", "notes", "note_calls", "figures"]]),
    ("Citations", "g-cite", [["works", "work_authors", "back_references", "citation_links", "link_checks",
                              "link_runs"]]),
    ("Quality & provenance", "g-qual", [["flags", "judge_findings", "patches", "fixes", "misprints",
                                         "metadata_changes", "catalogue_disagreements", "meta"]]),
]
EXTRA = {  # a few telling columns besides the keys
    "articles": ["rec", "c999", "doi", "title", "pub_year", "fpage", "lpage"],
    "journals": ["title_masters", "issn"], "issues": ["volume", "issue", "year"],
    "runs": ["model", "n_articles", "note"], "article_runs": ["current", "sha"],
    "people": ["authority_id", "display_name", "latin_name"], "person_names": ["form"],
    "article_authors": ["printed_name", "match"], "affiliations": ["printed"],
    "institutions": ["level", "name"], "catalogue_records": ["c999", "is_primary", "title"],
    "catalogue_authors": ["name", "authority_id"], "article_dates": ["date_type", "iso"], "abstracts": ["lang"],
    "keywords": ["term"], "subjects": ["scheme", "term"], "blocks": ["block_id", "page", "kind", "text"],
    "notes": ["kind", "text"], "note_calls": ["block_id"], "figures": ["caption"],
    "works": ["pub_type", "source_title", "year"], "work_authors": ["surname"],
    "back_references": ["marker"], "citation_links": ["best", "score", "method"],
    "link_checks": ["verdict"], "flags": ["kind", "severity"], "judge_findings": ["type", "route", "status"],
    "patches": ["action", "source", "status"], "fixes": ["azure_reading", "print"], "misprints": ["printed", "proposed"],
    "metadata_changes": ["field"], "catalogue_disagreements": ["kind", "severity"],
}
W, LH, HEAD, COLGAP, TOP = 256, 15, 24, 46, 120


def load(con):
    t = {}
    for (name,) in con.execute("SELECT name FROM sqlite_master WHERE type='table' AND name NOT LIKE 'blocks_fts%' "
                               "AND name NOT LIKE 'sqlite_%'"):
        cols = [(r[1], r[5]) for r in con.execute(f"PRAGMA table_info([{name}])")]
        fks = {}
        for r in con.execute(f"PRAGMA foreign_key_list([{name}])"):
            fks.setdefault(r[0], [r[2], [], []])
            fks[r[0]][1].append(r[3])
            fks[r[0]][2].append(r[4])
        n = con.execute(f"SELECT count(*) FROM [{name}]").fetchone()[0]
        t[name] = dict(cols=cols, fks=list(fks.values()), n=n)
    return t


def lines_of(name, info):
    """(text, kind, column) per line: kind pk | fk | stem | run | col."""
    fkcol = {}
    for parent, cs, _ in info["fks"]:
        for c in cs:
            fkcol.setdefault(c, []).append(parent)
    out = []
    pks = [c for c, pk in sorted(info["cols"], key=lambda x: x[1]) if pk]
    for c in pks:
        ps = sorted(set(x for x in fkcol.get(c, []) if x != name))
        out.append((c + (f" → {', '.join(ps)}" if ps else ""), "pk", c))
    for c, pk in info["cols"]:
        if pk or c not in fkcol:
            continue
        ps = [p for p in fkcol[c] if p != name or c == "parent_key"]
        if c == "stem" and "articles" in ps:
            out.append(("stem → articles", "stem", c))
        elif c in ("run", "built_run") and "runs" in ps:
            out.append((f"{c} → runs", "run", c))
        else:
            out.append((f"{c} → {', '.join(sorted(set(ps)))}", "fk", c))
    for c in [c for c, pk in info["cols"] if c not in pks]:
        if c == "stem" and any(x[2] == "stem" for x in out):
            continue
        if c in EXTRA.get(name, []) and not any(x[2] == c for x in out):
            out.append((c, "col", c))
    return out


def build(con):
    T = load(con)
    pos, frames, x = {}, [], 20
    for gi, (title, cls, cols) in enumerate(GROUPS):
        gx = x
        gbottom = 0
        for col in cols:
            y = TOP + 34
            for name in col:
                if name not in T:
                    continue
                ls = lines_of(name, T[name])
                h = HEAD + LH * len(ls) + 8
                pos[name] = dict(x=x, y=y, h=h, lines=ls)
                y += h + 18
            gbottom = max(gbottom, y)
            x += W + COLGAP
        frames.append((title, cls, gx - 12, TOP, x - COLGAP - gx + 24, gbottom - TOP))
        x += 18
    width, height = x, max(f[5] for f in frames) + TOP + 30

    def row_y(name, col):
        p = pos[name]
        for i, (_, _, c) in enumerate(p["lines"]):
            if c == col:
                return p["y"] + HEAD + LH * i + LH * 0.7
        return p["y"] + HEAD / 2

    svg = []
    for title, cls, fx, fy, fw, fh in frames:
        svg.append(f'<rect class="frame {cls}" x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="10"/>'
                   f'<text class="gtitle" x="{fx + 12}" y="{fy + 22}">{html.escape(title)}</text>')
    # trunk: stem -> articles from the groups that are not next to it
    a = pos["articles"]
    trunk_y = 62
    ax = a["x"] + W / 2
    far = [f for f in frames if f[1] in ("g-content", "g-cite", "g-qual")]
    svg.append(f'<path class="trunk" d="M{ax},{a["y"]} V{trunk_y} H{far[-1][2] + far[-1][4] / 2}"/>')
    svg.append(f'<polygon class="trunkhead" points="{ax - 6},{a["y"] - 10} {ax + 6},{a["y"] - 10} {ax},{a["y"]}"/>')
    for title, cls, fx, fy, fw, fh in far:
        k = sum(1 for n, p in pos.items() if fx <= p["x"] < fx + fw and any(f[0] == "articles" for f in T[n]["fks"]))
        cx = fx + fw / 2
        svg.append(f'<path class="trunk" d="M{cx},{fy} V{trunk_y}"/>'
                   f'<text class="tlabel" x="{cx + 6}" y="{trunk_y + 30}">→ articles · {k} tables</text>')
    svg.append(f'<text class="tlabel" x="{ax + 8}" y="{trunk_y - 8}">every per-article table: stem → articles(stem)</text>')
    # edges
    edges = []
    for name, info in T.items():
        if name not in pos:
            continue
        for parent, cs, ps in info["fks"]:
            if parent not in pos:
                continue
            if parent == "articles" and pos[name]["x"] - a["x"] > 2 * (W + COLGAP):
                continue      # far groups: drawn by the trunk (the column is named in the box)
            if cs == ["stem"] and parent == "articles":
                kind = "e-stem"
            elif parent == "runs":
                continue      # shown as the 'run → runs' line in each box
            else:
                kind = "e-fk" if len(cs) == 1 else "e-compound"
            edges.append((name, cs[-1] if len(cs) > 1 and cs[0] == "stem" else cs[0], parent, ps[-1], kind))
    for child, col, parent, pcol, kind in edges:
        c, p = pos[child], pos[parent]
        y1, y2 = row_y(child, col), row_y(parent, pcol)
        if child == parent:
            x1 = c["x"] + W
            d = f"M{x1},{y1} C{x1 + 36},{y1} {x1 + 36},{y2 - 14} {x1},{p['y'] + HEAD / 2}"
        elif abs(c["x"] - p["x"]) < 1:
            x1 = c["x"] + W
            bend = 34 + abs(y1 - y2) * 0.06
            d = f"M{x1},{y1} C{x1 + bend},{y1} {x1 + bend},{y2} {x1 + 1},{y2}"
        elif p["x"] > c["x"]:
            x1, x2 = c["x"] + W, p["x"]
            m = (x1 + x2) / 2
            d = f"M{x1},{y1} C{m},{y1} {m},{y2} {x2},{y2}"
        else:
            x1, x2 = c["x"], p["x"] + W
            m = (x1 + x2) / 2
            d = f"M{x1},{y1} C{m},{y1} {m},{y2} {x2},{y2}"
        title = f"{child}.{col} → {parent}.{pcol}" + (" (compound key, not followed by Datasette)"
                                                      if kind == "e-compound" else "")
        svg.append(f'<path class="edge {kind}" d="{d}" marker-end="url(#arrow-{kind})"><title>{html.escape(title)}'
                   f'</title></path>')
    # boxes on top
    for name, p in pos.items():
        x0, y0 = p["x"], p["y"]
        svg.append(f'<a href="{BASE}{name}" target="_blank"><title>{html.escape(DESC.get(name, ""))}</title><g class="box">'
                   f'<rect class="body" x="{x0}" y="{y0}" width="{W}" height="{p["h"]}" rx="6"/>'
                   f'<path class="head" d="M{x0},{y0 + HEAD} V{y0 + 6} a6,6 0 0 1 6,-6 H{x0 + W - 6} a6,6 0 0 1 6,6 '
                   f'V{y0 + HEAD} Z"/>'
                   f'<text class="tname" x="{x0 + 9}" y="{y0 + 16.5}">{name}</text>'
                   f'<text class="tcount" x="{x0 + W - 9}" y="{y0 + 16.5}" text-anchor="end">{T[name]["n"]:,}</text>'
                   '</g></a>')
        for i, (text, kind, _) in enumerate(p["lines"]):
            ty = y0 + HEAD + LH * i + LH * 0.75 + 1
            mark = {"pk": "◆ ", "fk": "→ ", "stem": "", "run": "", "col": ""}[kind]
            svg.append(f'<text class="c c-{kind}" x="{x0 + 10}" y="{ty}">{mark}{html.escape(text)}</text>')
    defs = "".join(f'<marker id="arrow-{k}" viewBox="0 0 10 10" refX="9" refY="5" markerWidth="7" markerHeight="7" '
                   f'orient="auto-start-reverse"><path class="ah {k}" d="M0,0 L10,5 L0,10 z"/></marker>'
                   for k in ("e-fk", "e-compound", "e-stem"))
    body = (f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" '
            f'role="img" aria-label="Tables of platform.db and their foreign keys"><defs>{defs}</defs>'
            + "".join(svg) + "</svg>")
    nfk = sum(len(i["fks"]) for i in T.values())
    nsingle = sum(1 for i in T.values() for f in i["fks"] if len(f[1]) == 1)
    return PAGE.format(svg=body, ntables=len(pos), nfk=nfk, nsingle=nsingle, ncomp=nfk - nsingle,
                       tlist=table_list(T, pos))


DESC = json.load(open(Path(__file__).with_name("table_descriptions.json"), encoding="utf-8"))


def table_list(T, pos):
    out = []
    for title, cls, cols in GROUPS:
        items = []
        for name in [n for col in cols for n in col if n in T]:
            rel = "; ".join(f"{', '.join(cs)} → {p}" for p, cs, _ in T[name]["fks"]) or "—"
            items.append(f'<li><a href="{BASE}{name}">{name}</a> <span class="n">{T[name]["n"]:,}</span>'
                         f'<br><span class="desc">{html.escape(DESC.get(name, ""))}</span>'
                         f'<br><span class="rel">{html.escape(rel)}</span></li>')
        out.append(f'<section><h3 class="{cls}-t">{html.escape(title)}</h3><ul>{"".join(items)}</ul></section>')
    return "".join(out)


PAGE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Platform database schema</title>
<style>
:root {{ --bg:#f7f6f2; --fg:#1d1d1f; --muted:#6b6a66; --box:#ffffff; --line:#c9c6bd; --edge:#4a5bd0;
  --edge2:#b0721e; --stem:#8f8c84; --pk:#1d1d1f; --chip-stem:#2f6f62; --chip-run:#8a8780;
  --people:#e8eefc; --cat:#f2ece0; --content:#e6f2ec; --cite:#f4e8f1; --qual:#f6ebe4; --head:#2e3440; --headfg:#fff; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97;
  --box:#212328; --line:#3c3f46; --edge:#8d9bff; --edge2:#e3a857; --stem:#77746e; --pk:#f2f0ea; --chip-stem:#6fc2ae;
  --chip-run:#8e8b85; --people:#1d2333; --cat:#2a261e; --content:#1b2a23; --cite:#2b1f29; --qual:#2d221c;
  --head:#3b4252; --headfg:#f2f2f2; }} }}
:root[data-theme="dark"] {{ --bg:#16171a; --fg:#e8e6e1; --muted:#a19e97; --box:#212328; --line:#3c3f46; --edge:#8d9bff;
  --edge2:#e3a857; --stem:#77746e; --pk:#f2f0ea; --chip-stem:#6fc2ae; --chip-run:#8e8b85; --people:#1d2333; --cat:#2a261e;
  --content:#1b2a23; --cite:#2b1f29; --qual:#2d221c; --head:#3b4252; --headfg:#f2f2f2; }}
html, body {{ margin:0; background:var(--bg); color:var(--fg);
  font:15px/1.45 system-ui, -apple-system, "Segoe UI", sans-serif; }}
header, .list, .legend {{ max-width:1100px; margin:0 auto; padding:0 16px; }}
h1 {{ font-size:1.5rem; margin:20px 0 4px; }} p {{ margin:6px 0; }} .muted {{ color:var(--muted); }}
a {{ color:var(--edge); }}
.legend {{ display:flex; flex-wrap:wrap; gap:6px 20px; font-size:13px; margin-top:10px; }}
.legend span {{ white-space:nowrap; }} .sw {{ display:inline-block; width:22px; height:0; border-top:2px solid;
  vertical-align:middle; margin-right:6px; }}
.scroll {{ overflow:auto; -webkit-overflow-scrolling:touch; margin:12px 0; border-top:1px solid var(--line);
  border-bottom:1px solid var(--line); }}
svg {{ display:block; font-family: ui-monospace, "SF Mono", Menlo, Consolas, monospace; }}
.frame {{ stroke:var(--line); stroke-width:1; }} .g-people {{ fill:var(--people); }} .g-cat {{ fill:var(--cat); }}
.g-content {{ fill:var(--content); }} .g-cite {{ fill:var(--cite); }} .g-qual {{ fill:var(--qual); }}
.gtitle {{ font:600 15px system-ui, sans-serif; fill:var(--fg); }}
.box .body {{ fill:var(--box); stroke:var(--line); }} .box .head {{ fill:var(--head); }}
.box:hover .body {{ stroke:var(--edge); stroke-width:2; }}
.tname {{ fill:var(--headfg); font-weight:700; font-size:12.5px; }} .tcount {{ fill:var(--headfg); opacity:.75; font-size:11px; }}
.c {{ font-size:11.5px; fill:var(--muted); }} .c-pk {{ fill:var(--pk); font-weight:700; }}
.c-fk {{ fill:var(--edge); }} .c-stem {{ fill:var(--chip-stem); }} .c-run {{ fill:var(--chip-run); }}
.edge {{ fill:none; stroke-width:1.5; }} .e-fk {{ stroke:var(--edge); }}
.e-compound {{ stroke:var(--edge2); stroke-dasharray:5 3; }} .e-stem {{ stroke:var(--chip-stem); opacity:.55; }}
.ah.e-fk {{ fill:var(--edge); }} .ah.e-compound {{ fill:var(--edge2); }} .ah.e-stem {{ fill:var(--chip-stem); }}
.trunk {{ fill:none; stroke:var(--chip-stem); stroke-width:3; opacity:.6; }} .trunkhead {{ fill:var(--chip-stem); opacity:.8; }}
.tlabel {{ font:12px system-ui, sans-serif; fill:var(--chip-stem); }}
.list {{ display:grid; grid-template-columns:repeat(auto-fit, minmax(240px, 1fr)); gap:4px 24px; padding-bottom:32px; }}
.list h3 {{ font-size:1rem; margin:14px 0 4px; }} .list ul {{ list-style:none; padding:0; margin:0; }}
.list li {{ margin:0 0 6px; font-size:14px; }} .rel {{ color:var(--muted); font-size:12.5px; }} .desc {{ font-size:13.5px; }}
.n {{ color:var(--muted); font-size:12px; }}
</style></head><body>
<header>
<h1>Platform database: tables and links</h1>
<p class="muted">platform.db (experiment 46): {ntables} tables, {nfk} declared foreign keys ({nsingle} single-column,
which Datasette turns into links; {ncomp} compound, drawn dashed, documentation only). Click a table to open it in
Datasette. Numbers are rows. Keys are declared, not enforced (loads run with foreign_keys off; fk46.py counts orphans).</p>
</header>
<div class="legend">
<span><i class="sw" style="border-color:var(--edge)"></i>foreign key (Datasette link)</span>
<span><i class="sw" style="border-color:var(--edge2);border-top-style:dashed"></i>compound key (not followed by Datasette)</span>
<span><i class="sw" style="border-color:var(--chip-stem);border-top-width:3px"></i>stem → articles</span>
<span>◆ primary key</span><span style="color:var(--chip-run)">run → runs: in every table read from a run</span>
</div>
<div class="scroll">{svg}</div>
<div class="list">{tlist}</div>
</body></html>
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--out", default=str(Path(DB).parent / "schema.html"))
    a = ap.parse_args(argv)
    con = sqlite3.connect(f"file:{a.db}?mode=ro", uri=True)
    Path(a.out).write_text(build(con), encoding="utf-8")
    print(a.out)


if __name__ == "__main__":
    main()
