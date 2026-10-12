"""out/summary.json + out/<page>/*.jpg -> out/report.html"""
import json, html
from pathlib import Path
OUT = Path(__file__).parent / "out"
S = json.load(open(OUT / "summary.json"))
e = html.escape
tot_ink = sum(s["ink"] for s in S); tot_ok = sum(s["ink"] - s["missed"] for s in S)
rows = "".join(f"<tr><td>{e(s['kind'])}</td><td>{s['shapes']:,}</td><td>{s['holes']:,}</td><td>{s['points']:,}</td><td>{s['fidelity']*100:.1f}%</td></tr>" for s in S)
secs = []
for s in S:
    p = s["page"]
    secs.append(f"""<section><h2>{e(s['kind'])} <small>{e(p)}</small></h2>
<p class=nums>{s['shapes']:,} shapes ({s['holes']:,} holes, {s['rules']} ruled lines) drawn with {s['points']:,} corner points. Redrawn from the shapes alone, the page matches {s['fidelity']*100:.1f}% of the scan's ink.</p>
<div class=three><figure><img loading=lazy src="{p}/scan.jpg"><figcaption>the scan</figcaption></figure>
<figure><img loading=lazy src="{p}/shapes.jpg"><figcaption>the shapes: each one its own colour</figcaption></figure>
<figure><img loading=lazy src="{p}/redrawn.jpg"><figcaption>the page drawn from the shapes only</figcaption></figure>
<figure><img loading=lazy src="{p}/diff.jpg"><figcaption>the difference: <b class=r>red</b> missed, <b class=b>blue</b> extra</figcaption></figure></div>
<div class=zoom><figure><img loading=lazy src="{p}/zoom_scan.jpg"><figcaption>close-up of the scan</figcaption></figure>
<figure><img loading=lazy src="{p}/zoom_shapes.jpg"><figcaption>the same close-up as geometry: {s['zoom_shapes']} shapes, {s['zoom_points']:,} red corner points</figcaption></figure></div></section>""")
page = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Ink as geometry</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}}
main{{max-width:1200px;margin:auto}} h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.2rem;margin:2.2em 0 .3em}} h2 small{{color:var(--mut);font-weight:400;font-size:.8rem}}
.lede{{font-size:1.1rem;max-width:760px}} .nums{{color:var(--mut);margin:.2em 0 .8em}}
ol.steps{{max-width:820px}} ol.steps li{{margin:.5em 0}}
table{{border-collapse:collapse;margin:1em 0;font-size:.95rem}} td,th{{border-bottom:1px solid var(--line);padding:6px 12px;text-align:left}}
.three{{display:grid;grid-template-columns:repeat(4,1fr);gap:10px}} .zoom{{display:grid;grid-template-columns:1fr;gap:10px;margin-top:10px}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}} img{{width:100%;display:block;background:#fff;border-radius:4px}}
figcaption{{font-size:.85rem;color:var(--mut);padding:4px 2px 0}} .r{{color:#d22}} .b{{color:#1a6fd8}}
.note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:820px;border-radius:4px}}
@media (max-width:760px){{.three{{grid-template-columns:1fr 1fr}}}}
</style></head><body><main>
<h1>Ink as geometry</h1>
<p class=lede>Your picture from September was this: the letters are fixed obstacles, a liquid flows round them, and the outline it leaves behind is the letter's shape, stored as numbers. Below is that geometry taken from seven very different pages, next to the original. Over all seven, the shapes reproduce <b>{tot_ok/tot_ink*100:.1f}%</b> of the ink exactly, pixel for pixel.</p>
<h2>How it is done</h2>
<ol class=steps>
<li><b>Look closely.</b> The page is drawn at 300 dots per inch in shades of grey, so a letter is about 30–60 dots tall.</li>
<li><b>Ink or paper?</b> Every dot is either ink or paper. The cut-off grey is picked for each page as the one that best splits the page into two groups (Otsu's method), so a pale old print and a dark modern one each get their own.</li>
<li><b>Pull out the straight rules first.</b> Any perfectly straight run of ink longer than 4% of the page (table borders, underlines, header lines) is lifted out on its own. Otherwise an underline glues itself to every word it touches.</li>
<li><b>Let the liquid flow.</b> Each island of touching ink becomes one shape. The liquid runs round its edge and records the border. Where paper is trapped inside (the loop of و, ه, ص), that's kept as a hole, just as the liquid would fill it from inside.</li>
<li><b>Keep only the corners.</b> The border is simplified to the corner points needed to stay within 0.6 of a dot (about 0.05 mm) of the real edge. Straight stretches need two points, curves need many. Those points are the numbers.</li>
<li><b>Check by redrawing.</b> The page is painted again from the shapes alone, with no image, and compared dot by dot with the scan.</li>
</ol>
<p class=note>A shape is an island of ink, not a letter. In Arabic, letters that join are one island (a whole word part such as بال), and each dot and vowel mark is its own small island. Cutting the islands into single letters was the next step: following the pen path (experiment 9, <code>geometry/penpath.py</code>). This page shows only the first step, the outline. The code is <code>src/inkscript/geometry/trace.py</code>, about 40 lines.</p>
<h2>The seven pages in numbers</h2>
<table><tr><th>page</th><th>shapes</th><th>holes</th><th>corner points</th><th>ink reproduced</th></tr>{rows}</table>
<p class=nums>The ~3–5% not reproduced is almost all on the very edges of letters: dots that sit right on the cut-off grey, the rounding of corners to 0.6 of a dot, and the hair-thin dark line the scanner leaves along the page edge (the red down the sides). Look at the thin red and blue fringes in the difference pictures. Nothing that a reader would call a letter goes missing; specks smaller than 6 dots are dropped on purpose as dust.</p>
{''.join(secs)}
<p class=nums style="margin-top:3em">Built by <code>experiments/39_ink_geometry/look.py</code> and <code>report.py</code>. Pages come from experiment 38 and the test fixture. Nothing was paid.</p>
</main></body></html>"""
(OUT / "report.html").write_text(page)
