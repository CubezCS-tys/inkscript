"""Experiment 43: the correction tool, version 1 (owner-approved 2026-10-20; docs/ideas.md "A correction tool on the
Layout view"). For the owner alone, in the browser, on the Layout view. No model calls.

Every correction made in the browser is a patch with source "person" (patches43.py format), keyed to Azure's line
ids, never an edit to a master. The page keeps them in the browser and exports them as one JSON file; this script
writes them into the patches of a run and rebuilds the masters of the articles they touch (person > judge > gemini).

    correct43.py build  --run v33_300 [--stems ...] [--no-views]
        the Layout view of each article (views43, with the data-alto hook) into out/correct/<run>/views/mirror/,
        and beside it the editing page out/correct/<run>/views/edit/<stem>.html: the same page + correct43.js /
        correct43.css + the article's data (its blocks as the run's answers have them, Azure's lines and words
        with their boxes, the notes, which ALTO block holds which Azure lines); edit/index.html lists the articles.
    correct43.py import FILE --run v33_300 [--out out/v33_300_judged] [--no-build]
        a "corrections" export: for each article the person's patches replace that article's earlier person
        patches in <out>/patches/<stem>.json (the judge's stay); then patches43.build for those articles.
    gold43.py import FILE   an article marked "now right" in the export joins the gold set, with its patches.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
OUT = HERE / "out"
PY = sys.executable
KIND = "inkscript-corrections"


def jload(p: Path, default=None):
    return json.loads(Path(p).read_text(encoding="utf-8")) if Path(p).exists() else default


# ------------------------------------------------------------------------------------------------ the article's data

def _box_close(a, b, tol=2.0):
    return all(abs(x - y) <= tol for x, y in zip(a, b))


def alto_map(alto: Path, lines_px: dict, first: int) -> dict:
    """ALTO block id -> {"p": article page, "lines": Azure line ids (by the TextLine's box: masters.py writes
    Azure's px box), "box": px} for every TextBlock, ComposedBlock and Illustration."""
    from lxml import etree
    root = etree.parse(str(alto)).getroot()
    q = lambda el: etree.QName(el).localname        # noqa: E731
    out = {}

    def box(el):
        try:
            x, y, w, h = (float(el.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT"))
            return [x, y, x + w, y + h]
        except (TypeError, ValueError):
            return None
    for P in root.iter():
        if q(P) != "Page":
            continue
        p = int(P.get("PHYSICAL_IMG_NR")) + first - 1
        cand = {lid: px for lid, (pp, px) in lines_px.items() if pp == p}
        for el in P.iter():
            if q(el) not in ("TextBlock", "ComposedBlock", "Illustration") or not el.get("ID"):
                continue
            ids = []
            for tl in el.iter():
                if q(tl) != "TextLine":
                    continue
                b = box(tl)
                hit = [lid for lid, px in cand.items() if b and _box_close(b, px)]
                if hit and hit[0] not in ids:
                    ids.append(hit[0])
            out[el.get("ID")] = dict(p=p, lines=ids, box=box(el))
    return out


def article_data(a: dict, run: str, masters: Path) -> dict:
    """What the editing page needs, from the run's (rule-applied) answers, Azure and the master's ALTO."""
    import masters43 as M43
    import patches43 as PA
    M43.ST.PAGES = OUT / "pages"
    stem = a["stem"]
    files = [OUT / run / "rules" / f"{stem}_c{x:03d}-{y:03d}.json" for x, y in M43.ST.chunks(a)]
    recs = [jload(f) for f in files]
    if not all(recs):
        raise FileNotFoundError(f"{stem}: answers missing in out/{run}/rules")
    pages = sorted({p for r in recs for p in range(r["first"], r["last"] + 1)})
    answers = [r["answer"] for r in recs]
    S = M43.Store43(a, pages, answers)
    words = M43.azure_words(a)
    D = dict(stem=stem, run=run, first=a.get("first", 1), pages={}, alto={}, notes=[], fixes={}, sic={})
    lines_px = {}
    for p in pages:
        W, H = S.dims[p]
        D["pages"][str(p)] = dict(W=W, H=H, blocks=[], lines={}, noise=[])
    for lid, L in S.lines.items():
        if L.get("split"):                                  # the parts stand for it
            continue
        p = L["page"]
        base = L.get("split_of") or lid
        try:
            ws = words(base)
        except (IndexError, KeyError, ValueError):
            ws = []
        if L.get("split_of"):
            sp = L.get("word_span")
            ws = ws[sp[0]:sp[1]] if sp else []
        D["pages"][str(p)]["lines"][lid] = dict(
            t=L["text"], az=L.get("azure_text", L["text"]), px=[round(v, 1) for v in L["px"]],
            w=[[w["text"], round(w["conf"], 3) if w.get("conf") is not None else None] + [round(v) for v in w["box"]]
               for w in ws])
        lines_px[lid] = (p, L["px"])
    for r in recs:
        ans = r["answer"]
        for pg in ans.get("pages") or []:
            if not isinstance(pg, dict) or str(pg.get("page")) not in D["pages"]:
                continue
            P = D["pages"][str(pg["page"])]
            for b in pg.get("blocks") or []:
                if not isinstance(b, dict):
                    continue
                shape = "lines" if b.get("lines") else "hemistichs" if b.get("hemistichs") else \
                    "rows" if b.get("rows") else "box"
                x = dict(type=b.get("type"), lines=PA.block_lines(b), shape=shape)
                for k in ("level", "note_kind", "id", "marker", "box", "calls"):
                    if b.get(k) not in (None, [], ""):
                        x[k] = b[k]
                if "calls" in x:
                    x["calls"] = [dict(line=str(c.get("line")), marker=c.get("marker"), fn=c.get("fn"))
                                  for c in x["calls"] if isinstance(c, dict)]
                P["blocks"].append(x)
                if b.get("type") == "footnote" and b.get("id"):
                    t = " ".join(P["lines"].get(i, {}).get("t", "") for i in x["lines"][:2])
                    D["notes"].append(dict(id=b["id"], marker=b.get("marker"), page=pg["page"], text=t[:90],
                                           kind=b.get("note_kind") or "footnote"))
        pre = {str(i) for i in ans.get("noise") or []}
        for p, P in D["pages"].items():
            P["noise"] += sorted(i for i in pre if i.split(":")[0] == p and i in P["lines"])
        for f in ans.get("fixes") or []:
            if isinstance(f, dict) and f.get("line"):
                D["fixes"].setdefault(str(f["line"]), []).append([f.get("from"), f.get("to"), f.get("why")])
        for s in ans.get("sic") or []:
            if isinstance(s, dict) and s.get("line"):
                D["sic"].setdefault(str(s["line"]), []).append([s.get("text"), s.get("corr")])
    alto = masters / f"{stem}.alto.xml"
    if alto.exists():
        D["alto"] = alto_map(alto, lines_px, D["first"])
    m = re.search(r"<article-title[^>]*>(.*?)</article-title>", (masters / f"{stem}.jats.xml").read_text(encoding="utf-8"),
                  re.S) if (masters / f"{stem}.jats.xml").exists() else None
    D["title"] = re.sub(r"\s+", " ", re.sub(r"<[^>]+>", "", m.group(1))).strip() if m else stem
    return D


# ------------------------------------------------------------------------------------------------ the pages

def edit_page(mirror_html: str, D: dict) -> str:
    """The Layout view + the tool: its stylesheet, the data, the script; "All" goes to the tool's index."""
    s = mirror_html.replace('href="../index.html">&larr; All', 'href="index.html">&larr; All', 1)
    s = s.replace("</head>", '<link rel="stylesheet" href="../correct43.css">\n</head>', 1)
    data = json.dumps(D, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    tail = (f'<script id="cdata" type="application/json">{data}</script>\n'
            f'<script src="../correct43.js"></script>\n</body>')
    i = s.rfind("</body>")
    return s[:i] + tail + s[i + len("</body>"):]


def index_page(run: str, rows: list[dict]) -> str:
    flags = (jload(OUT / run / "flags.json") or {}).get("articles", {})
    rows = sorted(rows, key=lambda r: (-flags.get(r["stem"], {}).get("high", 0), -flags.get(r["stem"], {}).get("medium", 0)))
    tr = "".join(
        f'<tr data-stem="{html.escape(r["stem"])}"><td><a href="{html.escape(r["stem"])}.html">{html.escape(r["stem"])}</a></td>'
        f'<td dir="auto">{html.escape(r["title"])}</td><td>{r["pages"]}</td>'
        f'<td>{flags.get(r["stem"], {}).get("high", 0)}</td><td class="mine"></td></tr>' for r in rows)
    return f"""<!doctype html><html lang="en"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1"><title>Corrections · {html.escape(run)}</title>
<link rel="stylesheet" href="../correct43.css"></head><body class="cidx">
<h1>Correction tool · {html.escape(run)}</h1>
<p>Open an article, click a block on our page (right of the scan) and correct it in the panel. Your corrections stay in
this browser; <b>Export corrections</b> saves them all as one file for <code>correct43.py import</code>.
<button type="button" id="cexport-all">Export corrections</button> <span id="ccount"></span></p>
<table><thead><tr><th>article</th><th>title</th><th>pages</th><th>high flags</th><th>my corrections</th></tr></thead>
<tbody>{tr}</tbody></table>
<script>window.CINDEX={json.dumps(run)};</script><script src="../correct43.js"></script></body></html>"""


def build(run: str, stems: list[str] | None, views: bool = True) -> dict:
    import run43
    arts = {a["stem"]: a for a in run43.articles("b")}
    masters = OUT / run / "masters"
    stems = stems or sorted(s for s in arts if (masters / f"{s}.alto.xml").exists())
    vdir = OUT / "correct" / run / "views"
    (vdir / "edit").mkdir(parents=True, exist_ok=True)
    if views:
        subprocess.run([PY, str(HERE / "views43.py"), "--masters", str(masters), "--out", str(vdir), "--stems", *stems],
                       check=True, cwd=HERE, stdout=subprocess.DEVNULL)
    for f in ("correct43.js", "correct43.css"):
        shutil.copyfile(HERE / f, vdir / f)
    rows, errs = [], {}
    for s in stems:
        mf = vdir / "mirror" / f"{s}.html"
        try:
            D = article_data(arts[s], run, masters)
        except Exception as e:                              # noqa: BLE001  (one article must not stop the rest)
            errs[s] = f"{type(e).__name__}: {e}"
            continue
        if not mf.exists():
            errs[s] = "no Layout view"
            continue
        (vdir / "edit" / f"{s}.html").write_text(edit_page(mf.read_text(encoding="utf-8"), D), encoding="utf-8")
        nalto = sum(1 for v in D["alto"].values() if v["lines"])
        rows.append(dict(stem=s, title=D["title"], pages=len(D["pages"]), alto=len(D["alto"]), alto_lines=nalto))
    (vdir / "edit" / "index.html").write_text(index_page(run, rows), encoding="utf-8")
    rep = dict(run=run, made=time.strftime("%Y-%m-%d %H:%M"), pages=len(rows), errors=errs)
    (OUT / "correct" / run / "build.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"{len(rows)} editing pages -> {vdir / 'edit'}; errors {len(errs)}: {list(errs)[:5]}")
    return rep


# ------------------------------------------------------------------------------------------------ import

def read_export(fn: Path) -> dict:
    d = jload(fn)
    if not isinstance(d, dict) or d.get("kind") != KIND:
        raise SystemExit(f"{fn}: not a corrections export (kind {KIND})")
    return d


def import_corrections(fn: Path, run: str, out: Path, rebuild: bool = True) -> dict:
    import patches43 as PA
    d = read_export(fn)
    if d.get("run") and d["run"] != run:
        raise SystemExit(f"{fn}: corrections of run {d['run']}, not {run}")
    pdir = Path(out) / "patches"
    done = {}
    for stem, item in sorted((d.get("articles") or {}).items()):
        mine = []
        for p in item.get("patches") or []:
            if p.get("source") != "person" or p.get("action") not in PA.ACTIONS:
                print(f"  {stem}: {p.get('id')} refused (source {p.get('source')}, action {p.get('action')})")
                continue
            mine.append(dict(p, run=run, article=stem, apply=p.get("apply", True)))
        old = PA.load_patches(pdir, stem)
        keep = [p for p in old if p.get("source") != "person"]
        if not mine and len(keep) == len(old):
            continue
        PA.save_patches(pdir, stem, keep + mine)
        done[stem] = dict(person=len(mine), replaced=len(old) - len(keep), others=len(keep))
        print(f"  {stem}: {len(mine)} person patch(es) written ({len(old) - len(keep)} earlier replaced; "
              f"{len(keep)} judge/retry kept) -> {pdir / (stem + '.json')}")
    if rebuild and done:
        res = PA.build(run, Path(out), sorted(done))
        for s, r in res.items():
            done[s].update(r)
    return done


def main():
    ap = argparse.ArgumentParser()
    sp = ap.add_subparsers(dest="cmd", required=True)
    p = sp.add_parser("build")
    p.add_argument("--run", default="v33_300")
    p.add_argument("--stems", nargs="*")
    p.add_argument("--no-views", action="store_true", help="reuse the Layout views already in out/correct/<run>/views")
    p = sp.add_parser("import")
    p.add_argument("file")
    p.add_argument("--run", default="v33_300")
    p.add_argument("--out", default=None, help="the patched run folder (default out/<run>_judged)")
    p.add_argument("--no-build", action="store_true")
    a = ap.parse_args()
    if a.cmd == "build":
        build(a.run, a.stems, not a.no_views)
    else:
        out = Path(a.out) if a.out else OUT / f"{a.run}_judged"
        import_corrections(Path(a.file), a.run, out, not a.no_build)


if __name__ == "__main__":
    main()
