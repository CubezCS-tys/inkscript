"""out/senses/<pid>.json + .jpg -> out/senses.html"""
import json, html
from pathlib import Path
OUT = Path(__file__).parent / "out"; e = html.escape
PAGES = [("0266-006-002-001_p042", "Heading, verse and footnotes in one column",
          "The rivers saw one block here. The other senses separate everything: the header row, three paragraphs, the numbered heading "
          "(its line spacing, its number, and strokes 23% thicker than the page's text), the verse (a wide gap in the middle of the line), "
          "and the footnotes (the short rule above them, then letters about 10% smaller)."),
         ("0005-055-003-004_p008", "A page of bullet points",
          "The rivers saw one block here too. Azure's words show each point starts with a dash, and the lines after it continue the point. "
          "The page number at the top is recognised as a lone number, not a bullet.")]
COLOR = {"heading": "#d33", "footnote": "#1a6fd8", "verse": "#c8961e", "paragraph start": "#3a3", "bullet": "#a2a",
         "bullet, continued": "#c7c", "furniture": "#666", "body": "#999"}
secs = []
for pid, title, text in PAGES:
    L = json.load(open(OUT / "senses" / f"{pid}.json"))
    rows = "".join(f"<tr><td dir=rtl class=ar>{e(l['text'][:70])}</td><td><b style='color:{COLOR[l['label']]}'>{e(l['label'])}</b></td>"
                   f"<td>{l['size']}×</td><td>{l['bold']}×</td><td>{'' if l['gap_above'] is None else str(l['gap_above']) + '×'}</td><td>{e('; '.join(l['why']))}</td></tr>" for l in L)
    secs.append(f"""<section><h2>{e(title)}</h2><p>{e(text)}</p><div class=pair>
<figure><img loading=lazy src="rivers/{pid}.jpg"><figcaption>what the rivers saw: one block</figcaption></figure>
<figure><img loading=lazy src="senses/{pid}.jpg"><figcaption>what the other senses see, line by line</figcaption></figure></div>
<details><summary>every line and why</summary><div class=tw><table><tr><th>line (Azure)</th><th>label</th><th>letter size</th><th>stroke</th><th>spacing above</th><th>reason</th></tr>{rows}</table></div></details></section>""")
(OUT / "senses.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>The other senses</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}} main{{max-width:1250px;margin:auto}}
h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.2rem;margin:2em 0 .3em}} p{{max-width:840px}} .lede{{font-size:1.1rem}}
.pair{{display:grid;grid-template-columns:1.35fr 1fr;gap:10px;align-items:start}} figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}}
img{{width:100%;display:block;background:#fff}} figcaption{{font-size:.85rem;color:var(--mut);padding-top:4px}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse;font-size:.88rem;margin-top:8px}} td,th{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left;vertical-align:top}} .ar{{font-size:1rem;white-space:nowrap}}
summary{{cursor:pointer;color:var(--acc);margin-top:10px}} .note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:840px;border-radius:4px}}
@media (max-width:760px){{.pair{{grid-template-columns:1fr}}}}
</style></head><body><main><h1>The other senses</h1>
<p class=lede>On these two pages, the rivers of paper saw one block each, because the page doesn't separate its parts with white space. Here every line is labelled again, still with no model, from three other things we hold for free:</p>
<p class=note><b>The ink:</b> letter size (how tall the line's ink is), stroke thickness (bold), indents, centring, the spacing above the line, and a short printed rule.<br>
<b>Azure's words:</b> a leading dash, numbering like "٦ ـ", footnote numbers "(١٦٧)" that also appear as markers in the body.<br>
<b>The page:</b> the top row, set apart or only a number, is the running header and page number.<br>
Each number is relative to the page itself (1.23× means 23% more than this page's typical line), so the same rules work on a 1950 page and a 2020 one.</p>
{''.join(secs)}
<p class=note><b>Honest limits.</b> Two pages are a demonstration, not a measurement. The rules were tuned while looking at these two pages, in four rounds. Run on hundreds of pages they will break in new ways; the next step would be the 44 pilot pages, scored against hand labels. The page's own draft labels disagree with ours on 5 lines, and on all 5 the scan shows ours is right: four lines of footnote (١٦٧) under the rule, and the verse, both drafted as plain text. Script: <code>experiments/39_ink_geometry/senses.py</code>.</p>
</main></body></html>""")
