"""out/score/*.json -> out/score/<pid>_vs.jpg (our labels | the referee's) and out/layout_score.html"""
import json, glob, html, sys
from pathlib import Path
import cv2, numpy as np
HERE = Path(__file__).parent; OUT = HERE / "out"
sys.path.insert(0, str(HERE.parent / "38_parser")); from common import page_image
COL = {"body": (150, 150, 150), "heading": (30, 30, 220), "footnote": (200, 110, 20), "list": (170, 40, 170), "verse": (20, 150, 200),
       "furniture": (90, 90, 90), "caption": (40, 140, 40), "table": (0, 120, 160), "equation": (120, 60, 0), "other": (60, 60, 60), None: (0, 0, 0)}
HEX = {k: "#%02x%02x%02x" % v[::-1] for k, v in COL.items() if k}


def panel(gray, rows, key):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR); over = img.copy()
    for x in rows:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); c = COL.get(x[key], (0, 0, 0))
        cv2.rectangle(over, (x0 - 4, y0), (x1 + 4, y1), c, -1)
    img = cv2.addWeighted(over, 0.35, img, 0.65, 0)
    for x in rows:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"])
        cv2.rectangle(img, (x0 - 4, y0), (x1 + 4, y1), (0, 0, 255) if x["ours_m"] != x["ref"] else COL.get(x[key], (0, 0, 0)), 4 if x["ours_m"] != x["ref"] else 2)
    return img


S = json.load(open(OUT / "score_summary.json"))
SHOW = [("0355-000-002-006_p017", "works", "A long plain page: 61 of 64 lines agree."),
        ("0877-007-027-003_p004", "works", "Body and a long run of footnotes: 50 of 55 agree."),
        ("0299-000-004-010_p002", "breaks: columns", "Two columns. Because the rules measure 'the page's column' and this page has two, almost every line looks like a verse (a wide gap mid-line)."),
        ("0073-000-239-002_p024", "breaks: tables", "A table's ruled lines look like a footnote rule, and once one line is a footnote, every line after it becomes one."),
        ("0465-011-001,002-009_p001", "breaks: lists", "Three columns of recommendations numbered أولاً، ثانياً… The rules only know a dash as a list marker."),
        ("0513-001-001-011_p003", "breaks: numbering", "A glossary whose senses are numbered (١) (٢). The footnote rule took those numbers for footnote numbers.")]
for pid, _, _ in SHOW:
    r = json.load(open(OUT / "score" / f"{pid}.json")); g = page_image(pid)
    a, b = panel(g, r["lines"], "ours_m"), panel(g, r["lines"], "ref"); bar = np.full((g.shape[0], 30, 3), 160, np.uint8)
    im = np.hstack([a, bar, b]); s = 1300 / im.shape[0]
    cv2.imwrite(str(OUT / "score" / f"{pid}_vs.jpg"), cv2.resize(im, (int(im.shape[1] * s), 1300), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])
grp = {}
for v in S.values():
    g = grp.setdefault(v["group"], [0, 0, 0]); g[0] += v["ok"]; g[1] += v["n"]; g[2] += 1
bars = "".join(f"<tr><td>{k}</td><td>{v[2]}</td><td><div class=bar><span style='width:{100*v[0]/v[1]:.0f}%'></span></div></td><td>{100*v[0]/v[1]:.0f}%</td></tr>"
               for k, v in sorted(grp.items(), key=lambda kv: -kv[1][0] / kv[1][1]))
legend = " ".join(f"<span class=chip style='background:{HEX[k]}'>{k}</span>" for k in ["body", "heading", "footnote", "list", "verse", "furniture", "table", "equation", "caption", "other"])
cards = "".join(f"<section><h3>{html.escape(t)} <span class=v>{html.escape(v)}</span></h3><p>{html.escape(d)}</p><figure><img loading=lazy src='score/{p}_vs.jpg'>"
                f"<figcaption>left: our rules · right: the referee · thick red outline: they disagree</figcaption></figure></section>" for p, v, d in SHOW for t in [p])
(OUT / "layout_score.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Layout senses, scored</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12;--bar:#3a7d44}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}} main{{max-width:1200px;margin:auto}}
h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.25rem;margin:1.8em 0 .4em}} h3{{font-size:1.05rem;margin:1.8em 0 .2em}} p,li{{max-width:840px}} .lede{{font-size:1.1rem}}
table{{border-collapse:collapse}} td,th{{padding:5px 10px;border-bottom:1px solid var(--line);text-align:left}} .bar{{width:260px;max-width:40vw;height:12px;background:var(--line);border-radius:6px}} .bar span{{display:block;height:100%;background:var(--bar);border-radius:6px}}
.v{{font-size:.8rem;color:var(--acc);border:1px solid var(--acc);border-radius:10px;padding:1px 8px;margin-left:6px;font-weight:600}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}} img{{width:100%;display:block;background:#fff}} figcaption{{font-size:.85rem;color:var(--mut);padding-top:4px}}
.chip{{color:#fff;font-size:.8rem;padding:1px 7px;border-radius:8px;display:inline-block;margin:2px}} .note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:840px;border-radius:4px}}
</style></head><body><main><h1>Layout senses, scored</h1>
<p class=lede>The line labeller that was perfect on its two pages, frozen with no further tuning, run on all 44 pilot pages. Overall it agrees with the referee on <b>47%</b> of the lines it is meant to handle. On plain single-column text it agrees on <b>72%</b>, and on columns, tables, equations and decorative pages it mostly breaks. Perfect on two pages really was the easy kind of perfect.</p>
<p class=note><b>The referee.</b> No page has hand-made layout labels: the 9 gold pages were corrected for text only. So Gemini (3.1 Pro) labelled every line from the page image alone, never seeing our rules. I checked its two biggest disagreements with ours by eye, and it was right both times. Cost: $0.52. Only lines the rules are meant to handle are scored (body, heading, footnote, list, verse, page furniture); table cells, equations, captions and other lines are left out, since the rules have no label for them.</p>
<h2>Agreement by kind of page</h2><table><tr><th>pages</th><th>n</th><th></th><th></th></tr>{bars}</table>
<h2>Why it breaks: five causes, all visible</h2><ol>
<li><b>It assumes one column.</b> On two- and three-column pages, every line with a wide gap looks like a verse: 389 lines were called verse, and only 6% were right. The fix is the design we already talked about: rivers first split the columns, then the senses work inside each block.</li>
<li><b>One footnote makes everything after it a footnote.</b> A table's ruled line looks like the short line above footnotes, so whole tables became footnotes: 549 lines called footnote, 16% right. Real footnotes were still found 85% of the time.</li>
<li><b>Lists only know the dash.</b> Lists numbered أولاً، ثانياً, (١) (٢) or 1- were missed: 14% of list lines found.</li>
<li><b>Page furniture only at the top.</b> Footers, journal names at the bottom and side notes were missed: 25% found. Repetition across pages, the whole-document sense, is what catches these.</li>
<li><b>Headings are too varied for one rule.</b> Large display titles, centred titles without numbers, and bold run-in headings: 27% found, and only a third of what it called a heading was one.</li></ol>
<h2>Six pages, side by side</h2><p>{legend}</p>{cards}
<p class=note><b>What it means.</b> The signals are real: where the page is a single column of text, measurements and text patterns get most lines right with no model. But the rules are brittle the moment the page is not what they were built on, which is exactly why they should sit <i>after</i> the rivers, which split columns and set tables and equations apart, and why a model is still needed for whatever the measurements can't settle. The labeller was not changed for this run, so these are honest numbers. Scripts: <code>score_layout.py</code>, <code>score_report.py</code>.</p>
</main></body></html>""")
