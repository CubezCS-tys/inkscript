"""Experiment 35: the owner's report, out/report.html (pictures first; numbers from out/numbers.json, the judge's
answers from out/judge.json, the engine bake-off from out/bakeoff.json).

    PYTHONPATH=src .venv/bin/python experiments/35_edition/make_report.py
(phone screenshots first: experiments/35_edition/shots.py with a playwright Python, into out/report/shots/)
"""
from __future__ import annotations

import html
import json
from collections import Counter
from pathlib import Path

import pymupdf

OUT = Path("/home/yassine/inkscript/experiments/35_edition/out")
MERGED = Path("/home/yassine/inkscript/experiments/29_catalogue/out/merged")
FIX = Path(__file__).resolve().parents[2] / "tests" / "fixtures" / "edition"
IMG = OUT / "report" / "img"

# (id, page, why it is here)
ARTICLES = [
    ("0460-005-002-007", 1, "a first page: title, author, footnotes (1980s)"),
    ("0868-042-163-040", 4, "two columns (2000s)"),
    ("0089-116-001-002", 35, "footnotes at the foot of the page (2020s)"),
    ("0596-031-001-013", 1, "Quran quotations in vowelled script, two columns, a title page"),
    ("0562-028-109-009", 27, "a page with two tables (2010s)"),
    ("2262-000-008-004", 14, "a ruled table under a paragraph (2010s)"),
]
TESTS = [("test-0001-table-math", 1, "display and inline formulas (MathML + LaTeX + scan crop)"),
         ("test-0001-table-math", 2, "a table with merged cells, header rows, row headers"),
         ("test-0002-two-columns", 1, "two columns, a 4 x 7 table with merged header cells")]


def shot(pdf: Path, page: int, name: str, dpi: int = 70) -> str:
    IMG.mkdir(parents=True, exist_ok=True)
    f = IMG / name
    if not f.exists():
        with pymupdf.open(str(pdf)) as d:
            d[min(page, len(d)) - 1].get_pixmap(dpi=dpi).save(str(f), jpg_quality=80)   # a short PDF: its last page
    return f"report/img/{name}"


def esc(s) -> str:
    return html.escape(str(s))


def verdict_box(r) -> str:
    if not r:
        return "<p class='muted'>not judged</p>"
    bits = [f"<b>overall {r['overall']}/5</b> · placement {r['placement']} · typography {r['typography']} · "
            f"blocks {r['blocks_original']} → {r['blocks_rebuilt']} · same blocks: {r['same_blocks']} · "
            f"order: {r['same_order']} · headings: {r['headings']}",
            f"<i>{esc(r['summary'])}</i>"]
    for k, lab in (("missing", "missing"), ("extra", "extra"), ("moved", "moved"), ("heading_issues", "headings"),
                   ("text_issues", "text")):
        if r.get(k):
            bits.append(f"<span class='tag'>{lab}</span> " + "; ".join(esc(x) for x in r[k][:3]))
    return "<div class='verdict'>" + "<br>".join(bits) + "</div>"


def files_line(root: Path, i: str, rel: str) -> str:
    names = [("reading HTML", f"{i}.html"), ("EPUB", f"{i}.epub"), ("layout PDF", f"{i}.layout.pdf"),
             ("one-column PDF", f"{i}.onecol.pdf"), ("Markdown", f"{i}.md"), ("JSON record", f"{i}.jsonl"),
             ("checks", f"{i}.checks.json")]
    return " · ".join(f"<a href='{rel}/{i}/{n}'>{lab}</a>" for lab, n in names if (root / i / n).exists())


def checks_line(root: Path, i: str) -> str:
    p = root / i / f"{i}.checks.json"
    if not p.exists():
        return ""
    c = json.loads(p.read_text())
    out = []
    for k, lab in (("html", "HTML"), ("epub", "EPUB"), ("md", "MD"), ("jsonl", "JSONL"), ("layout_pdf", "layout"),
                   ("onecol_pdf", "1-col")):
        v = c.get(k, {}).get("words")
        if not v:
            continue
        s = f"{lab} {v['found']}/{v['expected']}"
        if v["duplicated"]:
            s += f" (+{v['duplicated']} twice)"
        o = c[k].get("order")
        if o:
            s += f", in order {100 * o['share']:.1f}%"
        out.append(s)
    return "<p class='checks'>words found: " + " · ".join(out) + "</p>"


def article_card(i, page, why, root: Path, rel: str, scan: Path, judge: dict, onecol_page: int = 1) -> str:
    sc = shot(scan, page, f"{i}_p{page}_scan.jpg")
    la = shot(root / i / f"{i}.layout.pdf", page, f"{i}_p{page}_layout.jpg")
    oc = shot(root / i / f"{i}.onecol.pdf", onecol_page, f"{i}_onecol_p{onecol_page}.jpg")
    pref = ("top", "og", "notes", "quran", "table")
    shots = sorted((OUT / "report" / "shots").glob(f"{i}_*.png"),
                   key=lambda s: pref.index(s.stem.split("_", 1)[1]) if s.stem.split("_", 1)[1] in pref else 9)
    ph = "".join(f"<figure><img loading='lazy' src='report/shots/{s.name}'><figcaption>phone, "
                 f"{esc(s.stem.split('_', 1)[1])}</figcaption></figure>" for s in shots[:1])
    r = judge.get(f"{i}#p{page}")
    return f"""<section class='card'><h3>{esc(i)} · page {page} <span class='muted'>— {esc(why)}</span></h3>
<div class='row'>
<figure><a href='{sc}'><img loading='lazy' src='{sc}'></a><figcaption>the scan</figcaption></figure>
<figure><a href='{la}'><img loading='lazy' src='{la}'></a><figcaption>layout-faithful rebuild</figcaption></figure>
<figure><a href='{oc}'><img loading='lazy' src='{oc}'></a><figcaption>one-column edition, page {onecol_page}</figcaption></figure>
{ph}{"".join(f"<figure><img loading='lazy' src='report/shots/{s.name}'><figcaption>phone, {esc(s.stem.split('_', 1)[1])}</figcaption></figure>" for s in shots[1:2])}</div>
{verdict_box(r)}
{checks_line(root, i)}
<p class='files'>{files_line(root, i, rel)}</p></section>"""


def main():
    nums = json.loads((OUT / "numbers.json").read_text())
    jd = json.loads((OUT / "judge.json").read_text())
    judge = {r["key"]: r for r in jd["rows"]}
    rows = jd["rows"]
    arch = [r for r in rows if r["stratum"] not in ("hand-made",) and not r["stratum"].startswith("planted")]
    planted = [r for r in rows if r["stratum"].startswith("planted")]
    ed = OUT / "editions"
    tm = OUT / "testmasters"
    E = nums["editions"]
    O = nums["order"]

    def pct(k):
        return f"{E[k]['found_pct']:.2f}%"
    head = f"""<!doctype html><html lang='en'><head><meta charset='utf-8'>
<meta name='viewport' content='width=device-width,initial-scale=1'><title>Rebuilt editions</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--muted:#6b675f;--line:#e2ded5;--card:#fff;--accent:#8a4b1f;--good:#2f6b3a;--bad:#9b2c2c}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#171614;--fg:#ece8e0;--muted:#a19b90;--line:#34312c;--card:#1f1e1b;--accent:#e0a36f;--good:#7cc08a;--bad:#e08a8a}}}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:0 16px 60px}}
main{{max-width:1240px;margin:0 auto}} h1{{font-size:1.7rem;margin:28px 0 4px}} h2{{margin-top:44px;border-bottom:1px solid var(--line);padding-bottom:4px}}
.muted{{color:var(--muted);font-weight:400}} a{{color:var(--accent)}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px;margin:18px 0}}
.card h3{{margin:2px 0 10px;font-size:1.05rem}}
.row{{display:flex;gap:12px;overflow-x:auto;align-items:flex-start}}
figure{{margin:0;flex:0 0 auto}} figure img{{height:430px;border:1px solid var(--line);background:#fff;display:block}}
figcaption{{font-size:.8rem;color:var(--muted);text-align:center}}
.verdict{{font-size:.88rem;margin-top:8px;padding:8px 10px;border-left:3px solid var(--accent);background:color-mix(in srgb,var(--accent) 6%,transparent)}}
.tag{{display:inline-block;font-size:.72rem;padding:0 6px;border-radius:8px;background:var(--line)}}
.checks,.files{{font-size:.82rem;margin:6px 0 0}}
table{{border-collapse:collapse;font-size:.9rem;margin:10px 0}} td,th{{border:1px solid var(--line);padding:4px 8px;text-align:right}} th{{background:color-mix(in srgb,var(--line) 50%,transparent)}}
td:first-child,th:first-child{{text-align:left}}
.warn{{border:2px dashed var(--accent);padding:8px 12px;border-radius:8px}}
.big{{font-size:1.05rem}} ul li{{margin:4px 0}}
@media (max-width:700px){{figure img{{height:300px}}}}
</style></head><body><main>
<h1>Every edition from the master files <span class='muted'>— experiment 35, 2026-10-11</span></h1>
<p class='big'>From each article's JATS + ALTO alone (and its scan, for pictures), the generator <code>inkscript edition</code>
writes a reading web page for phones, an EPUB, two new print PDFs (one keeping the page's layout, one in a single
column like a research paper), a Markdown file and a dataset record, and checks every one of them. It ran on all
<b>{nums['documents']}</b> documents ({nums['pages']:,} pages): <b>0 failures</b>, 18 minutes on 2 workers,
at most 0.6 GB per worker, {sum(nums['sizes'].values()):.0f} MB in all.</p>
"""
    # ---- numbers
    t = ["<h2>The numbers</h2><p>Does every printed word the article should carry come out of each edition "
         "once? The words are read back from the finished files (the PDFs through pdfium, the engine Chrome uses), "
         "never from the generator's own strings.</p><table><tr><th>edition</th><th>words found</th>"
         "<th>body words lost</th><th>title/author words differing</th><th>printed twice</th><th>words in order</th></tr>"]
    labels = dict(html="reading HTML", epub="EPUB", md="Markdown", jsonl="dataset record (JSONL)",
                  layout_pdf="layout-faithful PDF (all words, page furniture too)", onecol_pdf="one-column PDF (numbers left out*)")
    for k in ("html", "epub", "md", "jsonl", "layout_pdf", "onecol_pdf"):
        v = E[k]
        o = O.get(k)
        t.append(f"<tr><td>{labels[k]}</td><td>{v['found']:,} / {v['expected']:,} ({v['found_pct']:.2f}%)</td>"
                 f"<td>{v['missing_body']}</td><td>{v['missing_front']}</td><td>{v['duplicated']}</td>"
                 f"<td>{(str(round(o['share_pct'], 1)) + '% (median document ' + str(round(100 * o['median_doc'], 1)) + '%)') if o else '—'}</td></tr>")
    t.append("</table><p class='muted'>* the one-column print numbers its notes 1, 2, 3… through the article and its "
             "pages anew, so the printed note numbers cannot match there; digits are left out of its count. "
             "Title/author words differing: the reading editions take the title from the library catalogue, which "
             "sometimes words it differently from the page. Words out of order in the PDFs are almost all Latin "
             "lines (English references) inside Arabic documents: they copy with their words reversed, the known "
             "price of marking the PDF right to left (D18).</p>")
    # ---- judge
    C = Counter
    caught = {f: sum(1 for r in planted if r.get("fault") == f and (
        (f == "drop" and r["missing"]) or (f == "swap" and (r["moved"] or r["same_order"] != "yes" or
                                                            r["text_issues"] or r["overall"] <= 3)) or
        (f == "heading" and (r["headings"] != "right" or r["heading_issues"]))))
        for f in ("drop", "swap", "heading")}
    nf = C(r.get("fault") for r in planted)
    j = [f"""<h2>The judge</h2><p>Gemini 3.1 Pro looked at {len(arch)} sampled archive pages (stratified: first pages,
footnotes, two columns, tables, Quran quotations, headings, plain pages, 1930s–2020s) plus the 3 hand-made pages, each time the
scan beside the layout-faithful rebuild, and answered: same blocks? same order? anything missing or extra? headings right?
Cost <b>${jd['spent']:.2f}</b> (cap $5; answers cached).</p>
<table><tr><th>on {len(arch)} archive pages</th><th></th></tr>
<tr><td>same blocks</td><td>{dict(C(r['same_blocks'] for r in arch))}</td></tr>
<tr><td>same order</td><td>{dict(C(r['same_order'] for r in arch))}</td></tr>
<tr><td>headings</td><td>{dict(C(r['headings'] for r in arch))}</td></tr>
<tr><td>overall (1–5)</td><td>{dict(sorted(C(r['overall'] for r in arch).items()))}</td></tr>
<tr><td>pages with something missing / extra</td><td>{sum(bool(r['missing']) for r in arch)} / {sum(bool(r['extra']) for r in arch)}</td></tr>
</table>
<p><b>Is the judge any good?</b> On {len(planted)} rebuilt pages a fault was put in on purpose, without telling it:
a paragraph left out — caught <b>{caught['drop']}/{nf['drop']}</b>; two paragraphs' texts swapped — caught
<b>{caught['swap']}/{nf['swap']}</b>; a heading set as body text — caught <b>{caught['heading']}/{nf['heading']}</b>
(and the one it "caught" was on a page it failed anyway). So when it says a block is missing or moved, believe it;
when it says headings are right, it has not really looked.</p>"""]
    for r in planted:
        j.append(f"<div class='verdict'><span class='tag'>planted: {esc(r['fault'])}</span> {esc(r['key'])} — "
                 f"{esc(r.get('fault_detail', ''))}<br><i>judge:</i> {esc(r['summary'])}</div>")
    # what it caught on real pages
    j.append("<h3>What it caught on real pages</h3>")
    bad = [r for r in arch if r["overall"] <= 3 or r["missing"] or r["extra"]]
    for r in bad:
        j.append(f"<div class='verdict'><b>{esc(r['key'])}</b> overall {r['overall']}: {esc(r['summary'])}"
                 + ("<br>missing: " + "; ".join(esc(x) for x in r["missing"]) if r["missing"] else "")
                 + ("<br>extra: " + "; ".join(esc(x) for x in r["extra"]) if r["extra"] else "")
                 + ("<br>text: " + "; ".join(esc(x) for x in r["text_issues"][:2]) if r["text_issues"] else "")
                 + "</div>")
    s1 = shot(MERGED / "0886-012-044-006.pdf", 6, "0886_p6_scan.jpg")
    s2 = shot(ed / "0886-012-044-006" / "0886-012-044-006.layout.pdf", 6, "0886_p6_layout_after.jpg")
    before = OUT / "report" / "img" / "0886_p6_layout_before.png"
    j.append(f"""<div class='card'><h3>A fault the judge found, fixed: a table printed sideways</h3>
<p>0886-012-044-006 page 6 is a landscape table turned on a portrait page. The first rebuild set every sideways line
across the page in a sliver of its box — crumbs (judge: overall 1, "a complete failure"). Lines whose box is tall and
narrow are now turned (9 pages of the 205 documents have them). The judge still finds the table hard to read without
its rules (overall 2): the table's cells were never recognised as a table in the master.</p>
<div class='row'><figure><img src='{s1}'><figcaption>the scan</figcaption></figure>
{"<figure><img src='report/img/" + before.name + "'><figcaption>first rebuild</figcaption></figure>" if before.exists() else ""}
<figure><img src='{s2}'><figcaption>now</figcaption></figure></div></div>""")
    # ---- articles
    a = ["<h2>Six archive articles</h2><p>For each: the scan, the layout-faithful rebuild of the same page, the first "
         "page of the one-column edition, the reading page on a phone, the judge's answer, the word checks and every "
         "file. Click a picture for full size.</p>"]
    for i, p, why in ARTICLES:
        a.append(article_card(i, p, why, ed, "editions", MERGED / f"{i}.pdf", judge))
    tst = ["""<h2>Tables and equations — hand-made test files</h2>
<p class='warn'><b>These are not archive pages.</b> The 205 master files have no structured tables and no equations
(the future Kraken + VLM stage will write them), so two small test articles were written by hand in the master
format — JATS with an XHTML table (merged cells, header rows, cells stored right column first) and MathML formulas
(<code>dir="rtl"</code>, with <code>&lt;tex-math&gt;</code> and a scan crop in <code>&lt;alternatives&gt;</code>), and a
matching ALTO — and their "scan" was typeset in Chromium in another font and roughened. They test that every edition
renders tables right to left and maths as maths.</p>"""]
    for i, p, why in TESTS:
        tst.append(article_card(i, p, why, tm, "testmasters", FIX / f"{i}.pdf", judge,
                                onecol_page=1))
    extra = sorted((OUT / "report" / "shots").glob("test-*.png"))
    tst.append("<div class='row'>" + "".join(f"<figure><img loading='lazy' src='report/shots/{s.name}'>"
                                              f"<figcaption>{esc(s.stem)}</figcaption></figure>" for s in extra) + "</div>")
    # ---- engine
    bk = json.loads((OUT / "bakeoff.json").read_text())
    agg = {}
    for k, v in bk.items():
        if not isinstance(v, dict) or "read" not in v:
            continue
        parts = k.split("|")
        key = "|".join(parts[1:])
        agg.setdefault(key, []).append(v)
    eng = ["<h2>Which typesetting engine</h2><p>Both engines set the same pages from the same master; the PDFs were "
           "read back with pdfium. Chromium (HTML → PDF) loses a third to half of the words in pdfium: its lam-alef "
           "(لا) comes back as ال, spaces vanish, brackets turn. LuaLaTeX (HarfBuzz, babel's Arabic with kashida) "
           "with our own rewrite of the text layer (each line stored as the faithful PDF stores it) reads back whole. "
           "Line for line (every printed line set at its own place and width) matched the scan better than re-flowing "
           "each block (ink correlation).</p><table><tr><th>engine · variant</th><th>documents</th>"
           "<th>words found (median)</th><th>in order (median)</th><th>seconds a document</th><th>ink match with the scan</th></tr>"]
    import statistics as st
    for key in ("lualatex|layout", "lualatex|layout|reflow", "lualatex|onecol", "chromium|layout", "chromium|onecol"):
        vs = agg.get(key, [])
        if not vs:
            continue
        ic = [v["ink_corr"] for v in vs if v.get("ink_corr") is not None]
        eng.append(f"<tr><td>{key.replace('|', ' · ')}</td><td>{len(vs)}</td>"
                   f"<td>{st.median(v['read']['found_pct'] for v in vs):.1f}%</td>"
                   f"<td>{st.median(v['read']['order_pct'] for v in vs):.1f}%</td>"
                   f"<td>{st.median(v['seconds'] for v in vs):.1f}</td><td>{st.median(ic):.2f}</td></tr>" if ic else
                   f"<tr><td>{key.replace('|', ' · ')}</td><td>{len(vs)}</td>"
                   f"<td>{st.median(v['read']['found_pct'] for v in vs):.1f}%</td>"
                   f"<td>{st.median(v['read']['order_pct'] for v in vs):.1f}%</td>"
                   f"<td>{st.median(v['seconds'] for v in vs):.1f}</td><td>—</td></tr>")
    eng.append("</table>")
    wrong = """<h2>What is wrong</h2><ul>
<li><b>Latin lines inside Arabic documents copy with their words reversed</b> in both PDFs (English references at the end of an article: pages at 20% in order). The same price as the faithful PDF pays for being marked right to left (D18). Whole English articles are now left to right (3 documents: 23% → 99.9% in order).</li>
<li><b>Headings:</b> the judge does not notice a heading set as body text (0 of 2 planted), so "headings right 34/36" is weak evidence; look at the pictures.</li>
<li><b>Tables in the archive are only boxes of words</b> — the masters do not know they are tables, so the layout rebuild draws no rules and the reading editions show the cells as short paragraphs. Real tables need the future master (the hand-made tests show the editions are ready for it).</li>
<li><b>Kashida:</b> few are inserted (1–14 a document); lines are justified mostly by spacing; 15–25% of lines are squeezed by up to 4% to fit their box.</li>
<li>Pictures, rules, logos and ornaments are not reproduced in the rebuild (text only); a logo's lettering appears as text.</li>
<li>Inline formulas copy out of the print PDF in a jumbled order; a tanween before a colon moves after it; Chromium does not mirror ∑ in right-to-left MathML.</li>
<li>Latin words with f-ligatures inside Arabic lines of the one-column PDF copy with two letters swapped (alhatif → alhatfi).</li>
<li>Master quirks seen through the editions: note numbers glued to words, numbers in tables read as footnotes (0562, 2025), a catalogue title worded differently from the page.</li>
</ul>"""
    (OUT / "report.html").write_text(head + "".join(t) + "".join(a) + "".join(j) + "".join(tst) + "".join(eng)
                                     + wrong + "</main></body></html>", encoding="utf-8")
    print(OUT / "report.html")


if __name__ == "__main__":
    main()
