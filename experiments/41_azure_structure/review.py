"""Experiment 41: a contact page to look at the print PDFs beside the scans (no model calls).

    .venv/bin/python review.py [--stems ...] [--dpi 70]

out/formats_review.html: for the 5 hand-checked articles every printed page, for the other articles every page
that holds a table: the scan | that page of the layout PDF | the page(s) of the one-column PDF that carry most of
its words. Pictures rendered with pdftoppm (poppler) into out/formats_review/<stem>/, scans from out/views/scans/.
Notes per article (what is wrong, seen on these pictures) are in NOTES below and printed above each article.
"""
from __future__ import annotations

import argparse
import html
import json
import re
import subprocess
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import OUT, sample  # noqa: E402

E = html.escape
FMT = OUT / "views" / "formats"
PRINT = OUT / "views" / "print"
NEW = OUT / "prints"                              # the new PDFs (rendered from here, before and after the swap)
WORDS = NEW / "words"
REV = OUT / "formats_review"
FIVE = ["0747-001-003-001", "2382-005-003-001", "0877-007-027-003", "0924-012-005-007", "1140-000-021-003"]
NOTES_F = HERE / "formats_review_notes.json"      # {stem: [fault, ...]}: written by hand after looking


def printed_pages(stem: str) -> list[tuple[int, bool]]:
    """(printed page number, holds a table) for each page of the layout print, in order."""
    s = (PRINT / f"{stem}.layout.html").read_text(encoding="utf-8")
    parts = re.split(r'(?=<div class="lpage" data-p=")', s)[1:]
    return [(int(re.match(r'<div class="lpage" data-p="(\d+)"', p).group(1)), "t-table" in p) for p in parts]


def onecol_pages_for(stem: str) -> dict[int, list[int]]:
    """Layout page index -> the one-column pages whose words are mostly that page's (each one-column page once)."""
    lay = json.loads((WORDS / f"{stem}.layout.json").read_text())
    one = json.loads((WORDS / f"{stem}.onecol.json").read_text())
    import pymupdf
    d = pymupdf.open(str(OUT / "prints" / f"{stem}.onecol.pdf"))
    names = d.resolve_names()
    per_one = {}
    for ln in one["lines"]:
        nd = names.get(f"inkm{ln.get('m', -1)}")
        if nd and nd.get("page", -1) >= 0:
            per_one.setdefault(nd["page"], Counter()).update(w["t"] for w in ln["words"])
    per_lay = {}
    for ln in lay["lines"]:
        per_lay.setdefault(ln["p"], Counter()).update(w["t"] for w in ln["words"])
    out = {}                                           # each one-column page goes to the layout page it shares most words with
    for q, c in per_one.items():
        n = sum(c.values()) or 1
        best = max(per_lay, key=lambda p: sum((per_lay[p] & c).values()) / n)
        out.setdefault(best, []).append(q)
    for p, ws in per_lay.items():                      # a page that got none: the one-column page holding most of its words
        if not out.get(p) and per_one:
            out[p] = [max(per_one, key=lambda q: sum((ws & per_one[q]).values()))]
        out[p] = sorted(out.get(p, []))
    return out


def render(pdf: Path, idx: int, dst: Path, dpi: int) -> str:
    if not dst.exists():
        dst.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["pdftoppm", "-r", str(dpi), "-f", str(idx + 1), "-l", str(idx + 1), "-jpeg", "-jpegopt",
                        "quality=82", "-singlefile", str(pdf), str(dst.with_suffix(""))], check=True)
    return str(dst.relative_to(OUT))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    ap.add_argument("--dpi", type=int, default=70)
    a = ap.parse_args()
    notes = json.loads(NOTES_F.read_text()) if NOTES_F.exists() else {}
    arts = [x["stem"] for x in sample()]
    if a.stems:
        arts = [s for s in arts if s in a.stems]
    order = [s for s in FIVE if s in arts] + [s for s in arts if s not in FIVE]
    secs, n_rows = [], 0
    for s in order:
        pages = printed_pages(s)
        five = s in FIVE
        want = [(i, p, t) for i, (p, t) in enumerate(pages) if five or t]
        if not want:
            continue
        oc = onecol_pages_for(s)
        rows = []
        for i, p, t in want:
            scan = OUT / "views" / "scans" / s / f"p{p:03d}.jpg"
            lay = render(NEW / f"{s}.layout.pdf", i, REV / s / f"layout-{i + 1:03d}.jpg", a.dpi)
            ones = [render(NEW / f"{s}.onecol.pdf", q, REV / s / f"onecol-{q + 1:03d}.jpg", a.dpi)
                    for q in oc.get(i, [])]
            cells = [f'<figure><img loading="lazy" src="{E(str(scan.relative_to(OUT)))}" alt=""><figcaption>scan, '
                     f'printed page {p}</figcaption></figure>',
                     f'<figure><img loading="lazy" src="{E(lay)}" alt=""><figcaption>layout PDF, page {i + 1}'
                     f'</figcaption></figure>',
                     '<div class="ones">' + "".join(
                         f'<figure><img loading="lazy" src="{E(o)}" alt=""><figcaption>one-column PDF, page '
                         f'{int(re.search(r"onecol-(\d+)", o).group(1))}</figcaption></figure>' for o in ones) + "</div>"]
            rows.append(f'<div class="row{" tab" if t else ""}">{"".join(cells)}</div>')
            n_rows += 1
        nt = notes.get(s) or []
        nl = ("<ul class=\"notes\">" + "".join(f"<li>{E(x)}</li>" for x in nt) + "</ul>") if nt else \
            '<p class="notes none">No notes written for this article.</p>'
        links = (f'<a href="views/formats/{s}/{s}.layout.pdf">layout PDF</a> · '
                 f'<a href="views/formats/{s}/{s}.onecol.pdf">one-column PDF</a> · '
                 f'<a href="views/mirror/{s}.html">Layout view</a> · <a href="views/formats/{s}/{s}.html">web page</a>')
        secs.append(f'<section id="{s}"><h2>{s}{" · hand-checked" if five else ""} '
                    f'<small>{len(want)} of {len(pages)} pages{" (pages with a table)" if not five else ""}</small></h2>'
                    f'<p class="links">{links}</p>{nl}{"".join(rows)}</section>')
    toc = " ".join(f'<a href="#{s}">{s}</a>' for s in order if f'id="{s}"' in "".join(secs))
    page = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Print PDFs review</title>
<style>
:root{{--bg:#f6f4ef;--fg:#1d1b18;--mute:#6b665d;--rule:#ddd6c8;--card:#fff;--acc:#8e3b22}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16150f;--fg:#ece7dc;--mute:#a59f92;--rule:#36332b;
--card:#201f19;--acc:#e39472}}}}
:root[data-theme="dark"]{{--bg:#16150f;--fg:#ece7dc;--mute:#a59f92;--rule:#36332b;--card:#201f19;--acc:#e39472}}
*{{box-sizing:border-box}}
body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,sans-serif}}
main{{max-width:120rem;margin:0 auto;padding:16px}}
h1{{font-size:22px;margin:.3em 0}}
.lede{{color:var(--mute);max-width:60rem}}
.toc{{display:flex;flex-wrap:wrap;gap:4px 10px;font-size:13px;margin:10px 0 20px}}
a{{color:var(--acc)}}
section{{border-top:1px solid var(--rule);padding:14px 0 24px}}
h2{{font-size:17px;margin:0 0 4px}}h2 small{{color:var(--mute);font-weight:400}}
.links{{font-size:13px;margin:0 0 8px}}
.notes{{background:var(--card);border:1px solid var(--rule);border-radius:8px;padding:8px 12px 8px 28px;margin:0 0 12px;
max-width:70rem}}.notes.none{{padding:8px 12px;color:var(--mute)}}
.row{{display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:12px;align-items:start;margin:0 0 14px}}
.row.tab{{border-inline-start:3px solid var(--acc);padding-inline-start:8px}}
figure{{margin:0;background:var(--card);border:1px solid var(--rule);border-radius:4px;padding:4px}}
figure img{{display:block;width:100%;height:auto;background:#fff}}
figcaption{{font-size:12px;color:var(--mute);padding:2px 2px 0}}
.ones{{display:grid;grid-template-columns:repeat(auto-fit,minmax(10rem,1fr));gap:8px}}
@media (max-width:720px){{.row{{grid-template-columns:1fr}}}}
</style></head><body><main>
<h1>Print PDFs beside the scans</h1>
<p class="lede">Layout PDF: the Layout view printed by Chromium 156, one PDF page per printed page. One-column PDF: the
web page printed by Chromium with its print stylesheet (A4). Text layer of both: the browser's words, written as an
invisible layer by inkscript's own writer (textlayer.py). Shown: every page of the 5 hand-checked articles and every
page with a table in the others ({n_rows} rows; pages with a table have a coloured edge). Rendered with pdftoppm at
{a.dpi} dpi. Notes above each article are what was seen on these pictures.</p>
<div class="toc">{toc}</div>
{"".join(secs)}
<p class="lede">Generated by experiments/41_azure_structure/review.py.</p></main></body></html>
"""
    (OUT / "formats_review.html").write_text(page, encoding="utf-8")
    print(f"{n_rows} rows -> {OUT / 'formats_review.html'}")


if __name__ == "__main__":
    main()
