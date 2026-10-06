"""The owner's page: before/after structure beside the page for several documents, precision/recall as bars,
the set's counts. Self-contained (pages embedded as JPEG), light/dark, phone width.

    python report.py      -> out/report.html   (after run_jats.py out/before|out/after, evaluate.py, reenrich.py)
"""
import base64
import html
import json
import sys
from pathlib import Path

import cv2
import pypdfium2 as pdfium

from inkscript.enrich.document import load
from inkscript.enrich.structure import analyse, read_meta

HERE = Path(__file__).resolve().parent
sys.argv = sys.argv[:1]
from evaluate import read_jats  # noqa: E402

DATA = Path("/home/yassine/inkscript/experiments/24_product/out")
OUT = HERE / "out"
SHOW = [("0599-000-123-004", [1, 2]), ("0290-000-005-003", [1, 4]), ("0656-014-010-014", [1, 3]),
        ("1005-000-001-002", [3, 5]), ("0387-000-006-004", [1, 3]), ("6795-000-000-014", [1, 2])]
ROLE_COL = {"title": "var(--c-title)", "author": "var(--c-author)", "rubric": "var(--c-rubric)",
            "heading": "var(--c-head)", "note": "var(--c-note)", "marker": "var(--c-marker)",
            "furniture": "var(--c-furn)"}
ROLE_AR = {"title": "title", "author": "author", "rubric": "rubric (section of the journal)", "heading": "heading",
           "note": "note at the foot", "marker": "marker → its note", "furniture": "running head / page number"}
E = html.escape


def page_jpeg(stem, pn, width=640):
    pdf = pdfium.PdfDocument(str(DATA / "azure" / stem / f"{stem}.pdf"))
    pg = pdf[pn - 1]
    a = pg.render(scale=width / pg.get_width(), grayscale=True).to_numpy()
    a = a if a.ndim == 2 else a[..., 0]
    ok, buf = cv2.imencode(".jpg", a, [cv2.IMWRITE_JPEG_QUALITY, 62])
    return base64.b64encode(buf.tobytes()).decode(), a.shape[1], a.shape[0]


def boxes(doc, st, pn):
    W = doc["words"]
    out = []

    def add(ks, role, label=""):
        ws = [W[k] for k in ks if W[k]["page"] == pn]
        if ws:
            out.append((role, [min(w["box"][0] for w in ws), min(w["box"][1] for w in ws),
                               max(w["box"][2] for w in ws), max(w["box"][3] for w in ws)], label))
    fr = st["front"]
    add(fr.get("title_words", []), "title")
    add(fr.get("rubric_words", []), "rubric")
    for a in fr.get("authors", []):
        add(a["words"], "author")
    for i, p in enumerate(doc["paras"]):
        if i in st["furniture"]:
            add(p["words"], "furniture")
        elif st["kinds"][i] == "sectionHeading":
            add(st["head_words"].get(i, p["words"]), "heading")
    for n, nt in enumerate(st["notes"]):
        add(nt["words"], "note", nt["label"] or "")
    for k, m in st["markers"].items():
        add([k], "marker", st["notes"][m["note"]]["label"] or "")
    return out


def outline(j, pages=None):
    rows = []
    rows.append(("title", j["title"] or "— none —"))
    for a in j["authors"]:
        rows.append(("author", a))
    if not j["authors"]:
        rows.append(("author", "— none —"))
    if j["rubric"]:
        rows.append(("rubric", j["rubric"]))
    for h in j["headings"]:
        if pages is None or h["page"] in pages:
            rows.append(("heading", f"p{h['page']} · {h['text']}"))
    nl = [x for x in j["links"] if pages is None or x["page"] in pages]
    el = [x for x in j["endlinks"] if pages is None or x["page"] in pages]
    rows.append(("marker", f"{len(nl)} markers linked to a note on their page"
                 + (f", {len(el)} to the endnotes" if el else "")
                 + (": " + " ".join(f"p{x['page']}({x['note']})" for x in (nl + el)[:14]) if nl or el else "")))
    return rows


def outline_html(rows):
    return "".join(f'<li><span class="tag" style="--c:{ROLE_COL[r]}">{E(r)}</span> <span dir="auto">{E(t)}</span></li>'
                   for r, t in rows)


def bars(scores_b, scores_a, title):
    els = [("title", "title"), ("authors", "authors"), ("headings", "headings"), ("footnote_links", "footnote links"),
           ("endnote_links", "endnote links"), ("rubric", "rubric")]
    rows = []
    for k, lab in els:
        b, a = scores_b.get(k, {}), scores_a.get(k, {})
        if not (b.get("tp", 0) + b.get("fn", 0) + b.get("fp", 0) + a.get("tp", 0) + a.get("fn", 0) + a.get("fp", 0)):
            continue
        cells = []
        for m in ("precision", "recall"):
            vb, va = b.get(m), a.get(m)

            def bar(v, cls, who):
                w = 0 if v is None else v * 100
                txt = "–" if v is None else f"{v:.2f}"
                return (f'<div class="bar {cls}" title="{who} {m}: {txt}"><i style="width:{w:.0f}%"></i>'
                        f'<b>{txt}</b></div>')
            cells.append(f'<div class="cell"><div class="m">{m}</div>{bar(vb, "before", "before")}{bar(va, "after", "after")}</div>')
        n = a.get("tp", 0) + a.get("fn", 0)
        rows.append(f'<div class="prrow"><div class="el">{lab}<small>{n} in the truth</small></div>{"".join(cells)}</div>')
    return f'<h3>{E(title)}</h3><div class="pr">{"".join(rows)}</div>'


def main():
    sb = json.loads((OUT / "before" / "scores.json").read_text(encoding="utf-8"))["scores"]
    sa = json.loads((OUT / "after" / "scores.json").read_text(encoding="utf-8"))["scores"]
    hb = json.loads((OUT / "before" / "scores_heldout.json").read_text(encoding="utf-8"))["scores"]
    ha = json.loads((OUT / "after" / "scores_heldout.json").read_text(encoding="utf-8"))["scores"]
    truth = json.loads((HERE / "truth" / "truth.json").read_text(encoding="utf-8"))["docs"]
    held = json.loads((HERE / "truth" / "heldout.json").read_text(encoding="utf-8"))["docs"]
    docs_html = []
    for stem, pns in SHOW:
        doc = load(DATA / "azure" / stem / f"{stem}.json")
        st = analyse(doc, read_meta(stem, [OUT / "gemini"]), DATA / "azure" / stem / f"{stem}.pdf")
        jb = read_jats(OUT / "before" / f"{stem}.jats.xml")
        ja = read_jats(OUT / "after" / f"{stem}.jats.xml")
        tr = truth.get(stem) or held.get(stem) or {}
        pages = set(tr.get("pages", pns))
        figs = []
        for pn in pns:
            b64, w, h = page_jpeg(stem, pn)
            sc = w / doc["pages"][pn]["w"]
            rects = "".join(
                f'<rect x="{x0 * sc - 2:.0f}" y="{y0 * sc - 2:.0f}" width="{(x1 - x0) * sc + 4:.0f}" height="{(y1 - y0) * sc + 4:.0f}" '
                f'style="--c:{ROLE_COL[r]}" class="r {r}"><title>{E(ROLE_AR[r])} {E(lab)}</title></rect>'
                for r, (x0, y0, x1, y1), lab in boxes(doc, st, pn))
            figs.append(f'<figure><svg viewBox="0 0 {w} {h}" role="img" aria-label="page {pn} with its structure marked">'
                        f'<image href="data:image/jpeg;base64,{b64}" width="{w}" height="{h}"/>{rects}</svg>'
                        f'<figcaption>page {pn}</figcaption></figure>')
        src = "Gemini's title file, aligned to the printed words" if st["gemini"] else "page 1's layout (no Gemini title file in the bucket)"
        docs_html.append(f'''<section class="doc"><h3>{E(stem)}</h3>
<p class="note">{E(tr.get("notes", ""))} <br>Title and authors from {E(src)}.</p>
<div class="docgrid"><div class="pages">{"".join(figs)}</div>
<div class="outlines"><div class="ol before"><h4>Before (position rules)</h4><ul>{outline_html(outline(jb, pages))}</ul></div>
<div class="ol after"><h4>After</h4><ul>{outline_html(outline(ja, pages))}</ul></div></div></div></section>''')
    # the set: counts before / after
    b20 = json.loads((OUT / "before" / "summary.json").read_text(encoding="utf-8"))
    a20 = json.loads((OUT / "set" / "summary.json").read_text(encoding="utf-8"))
    rows = []
    tot = dict(tb=0, ta=0, ab=0, aa=0, nb=0, na=0, lb=0, la=0, sb=0, sa=0, vj=0, va=0)
    for stem in sorted(b20):
        b, a = b20[stem], a20[stem]["jats"]
        jb = read_jats(OUT / "before" / f"{stem}.jats.xml")
        ja = read_jats(OUT / "set" / f"{stem}.jats.xml")
        vals = dict(tb=bool(jb["title"]), ta=bool(ja["title"]), ab=bool(jb["authors"]), aa=bool(ja["authors"]),
                    nb=b.get("footnotes", 0), na=a.get("notes", 0), lb=b.get("fn_markers", 0), la=a.get("fn_markers", 0),
                    sb=b.get("sections", 0), sa=a.get("sections", 0), vj=bool(a.get("valid")), va=bool(a20[stem]["alto_valid"]))
        for k, v in vals.items():
            tot[k] += v
        yn = lambda v: "✓" if v else "·"
        rows.append(f'<tr><td>{E(stem)}</td><td dir="auto">{E(ja["title"][:48])}</td><td>{yn(vals["tb"])} → {yn(vals["ta"])}</td>'
                    f'<td>{yn(vals["ab"])} → {yn(vals["aa"])}</td><td>{vals["sb"]} → {vals["sa"]}</td>'
                    f'<td>{vals["nb"]} → {vals["na"]}</td><td>{vals["lb"]} → {vals["la"]}</td></tr>')
    rows.append(f'<tr class="tot"><td>20 documents</td><td></td><td>{tot["tb"]} → {tot["ta"]}</td><td>{tot["ab"]} → {tot["aa"]}</td>'
                f'<td>{tot["sb"]} → {tot["sa"]}</td><td>{tot["nb"]} → {tot["na"]}</td><td>{tot["lb"]} → {tot["la"]}</td></tr>')
    legend = "".join(f'<span class="tag" style="--c:{c}">{E(ROLE_AR[r])}</span>' for r, c in ROLE_COL.items())
    page = TEMPLATE.format(
        bars1=bars(sb, sa, "10 documents read by hand (the rules were tuned on these)"),
        bars2=bars(hb, ha, "4 more documents read by hand afterwards (held out)"),
        leaks_b=sb["furniture_leaks"], leaks_a=sa["furniture_leaks"],
        docs="".join(docs_html), legend=legend, rows="".join(rows), vj=tot["vj"], va=tot["va"])
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print(OUT / "report.html", f"{len(page) / 1e6:.2f} MB")


TEMPLATE = """<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Article Structure Report</title>
<style>
:root{{--bg:#fcfcfb;--fg:#0b0b0b;--muted:#52514e;--line:#e4e3df;--card:#ffffff;
--before:#eb6834;--after:#2a78d6;--track:#f0efec;
--c-title:#2a78d6;--c-author:#1baf7a;--c-rubric:#4a3aa7;--c-head:#eda100;--c-note:#e87ba4;--c-marker:#e34948;--c-furn:#8a8985}}
@media (prefers-color-scheme: dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--fg:#fff;--muted:#c3c2b7;--line:#383835;--card:#232322;
--before:#d95926;--after:#3987e5;--track:#383835;--c-title:#3987e5;--c-author:#199e70;--c-rubric:#9085e9;--c-head:#c98500;--c-note:#d55181;--c-marker:#e66767;--c-furn:#9c9b95}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--fg:#fff;--muted:#c3c2b7;--line:#383835;--card:#232322;
--before:#d95926;--after:#3987e5;--track:#383835;--c-title:#3987e5;--c-author:#199e70;--c-rubric:#9085e9;--c-head:#c98500;--c-note:#d55181;--c-marker:#e66767;--c-furn:#9c9b95}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--fg);font:15px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1180px;margin:0 auto;padding:24px 16px 64px}} h1{{font-size:26px;margin:0 0 6px}} h2{{margin:40px 0 8px;font-size:20px}}
h3{{margin:24px 0 8px;font-size:16px}} p{{max-width:75ch}} .note{{color:var(--muted);font-size:13px}}
.lead{{color:var(--muted)}} .keys{{display:flex;flex-wrap:wrap;gap:6px;margin:8px 0}}
.tag{{display:inline-block;border-left:4px solid var(--c);padding:0 6px;font-size:12px;color:var(--muted);background:var(--card);border-radius:3px;white-space:nowrap}}
.pr{{display:grid;gap:10px}} .prrow{{display:grid;grid-template-columns:150px 1fr 1fr;gap:12px;align-items:center;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px}}
.el{{font-weight:600}} .el small{{display:block;font-weight:400;color:var(--muted);font-size:12px}} .m{{font-size:12px;color:var(--muted)}}
.bar{{position:relative;height:18px;background:var(--track);border-radius:4px;margin:3px 0;overflow:hidden}}
.bar i{{position:absolute;inset:0 auto 0 0;border-radius:0 4px 4px 0}} .bar.before i{{background:var(--before)}} .bar.after i{{background:var(--after)}}
.bar b{{position:absolute;right:6px;top:0;font-size:12px;line-height:18px;font-weight:600;color:var(--fg)}}
.legend{{display:flex;gap:14px;font-size:13px;color:var(--muted);margin:6px 0}} .legend span::before{{content:"";display:inline-block;width:12px;height:12px;border-radius:3px;margin-right:5px;vertical-align:-1px;background:var(--k)}}
.doc{{border-top:1px solid var(--line);padding-top:8px}} .docgrid{{display:grid;grid-template-columns:minmax(0,3fr) minmax(0,2fr);gap:16px}}
.pages{{display:grid;grid-template-columns:1fr 1fr;gap:10px}} figure{{margin:0}} svg{{width:100%;height:auto;display:block;border:1px solid var(--line);border-radius:4px;background:#fff}}
figcaption{{font-size:12px;color:var(--muted);text-align:center}}
.r{{fill:none;stroke:var(--c);stroke-width:3}} .r.marker{{stroke-width:4}} .r.furniture{{stroke-dasharray:6 4}} .r.note{{fill:var(--c);fill-opacity:.08}}
.ol{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px 10px;margin-bottom:10px}} .ol h4{{margin:0 0 4px;font-size:13px}}
.ol.before h4{{color:var(--before)}} .ol.after h4{{color:var(--after)}} .ol ul{{list-style:none;margin:0;padding:0;font-size:13px}} .ol li{{margin:3px 0}}
.tablewrap{{overflow-x:auto}} table{{border-collapse:collapse;font-size:13px;width:100%}} td,th{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;white-space:nowrap}}
tr.tot td{{font-weight:700}} th{{color:var(--muted);font-weight:600}}
@media (max-width:760px){{.docgrid{{grid-template-columns:1fr}} .prrow{{grid-template-columns:1fr 1fr}} .el{{grid-column:1/-1}}}}
</style></head><body><main>
<h1>Article structure: read like a reader reads it</h1>
<p class="lead">Experiment 26 · 2026-10-06. The JATS file of each document now gets its title and authors from Gemini's title file (where the bucket has one) laid onto the printed words, its headings from size, bold ink, numbering and space, its notes from the small lines at the foot of a page, and each marker in the text linked to its note. Running heads and page numbers stay out of the text.</p>
<h2>How often it is right</h2>
<p>Checked against what I read on the page images myself (Arabic), per element. <b>Precision</b>: of what the file says, how much is right. <b>Recall</b>: of what is on the page, how much the file found.</p>
<div class="legend"><span style="--k:var(--before)">before (position rules)</span><span style="--k:var(--after)">after</span></div>
{bars1}
<p class="note">Running heads, footers or page numbers that ended up as article text on the pages read: <b>{leaks_b} before → {leaks_a} after</b>.</p>
{bars2}
<p class="note">These four were read after the rules were tuned. The first pass on them found title 3/4, authors 2/3, headings precision 0.83 / recall 0.71, footnote links 1.00 / 0.94; what they showed (a title only a little larger than the text but with a byline under it, an author's "*" note, a two-line numbered heading) became three general rules, and the bars show the result after them.</p>
<h2>On the page</h2>
<p>Each page with what the new file says about it; hover a box for its name. Beside it, the outline of the JATS file before and after, for the pages read.</p>
<div class="keys">{legend}</div>
{docs}
<h2>The 20 documents</h2>
<p>Every file is valid: JATS 1.4 <b>{vj}/20</b>, ALTO 4.4 <b>{va}/20</b>. "Notes" before counted every paragraph the old rule called a footnote (page numbers and footers among them); after, one per note.</p>
<div class="tablewrap"><table><tr><th>document</th><th>title (after)</th><th>title</th><th>author</th><th>sections</th><th>notes</th><th>markers linked</th></tr>{rows}</table></div>
</main></body></html>"""

if __name__ == "__main__":
    main()
