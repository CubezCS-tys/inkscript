"""out/rivers/*.jpg -> out/rivers.html, with what each page shows (captions written after looking at every image)."""
from pathlib import Path
import html
OUT = Path(__file__).parent / "out"
PAGES = [  # (page, what it is, verdict, what you see)
 ("0737-001-020-003_p009", "two columns, before 1960", "works",
  "The red gutter runs the full height between the columns, so the page splits into right column, left column, running header and page number. The blue patches are where a paragraph ends short: the river finds paragraph ends too."),
 ("0781-010-055-015_p006", "body text beside a column of references, 2000s", "works",
  "The thin printed rule between the columns becomes a wall (green), so the body and the reference list come apart cleanly, with the header and footer as their own blocks."),
 ("0299-000-004-010_p002", "two columns with Quran verses, 1970s", "works",
  "Two columns, cut by a clean gutter. Inside each column, the blue shows the breaks around verses and the ornament."),
 ("0460-009-003-012_p010", "text, equations, footnotes and a small table, 1980s", "works best",
  "The most useful result: paragraphs, each equation, the footnote references and the small table each come out as their own block. The rivers inside the equation even split it into its parts."),
 ("0582-004-009-012_p002", "single column, the fixture", "mostly",
  "Paragraphs are found from the wider gaps between them. The footnotes stay joined to the last paragraph, because the gap above them is no wider than a paragraph gap and there is no rule."),
 ("0747-001-003-001_p006", "poetry with footnotes, before 1960", "half",
  "The gap between the two halves of each verse is found, so verse is visible as verse. But the footnotes are swallowed into the right half's block, and the header line is lost."),
 ("0924-012-005-007_p002", "a table of accounts, before 1960", "rough, but telling",
  "The blocks are rough, but look at the red: the gaps between the table's columns light up as gutters. That is the table's grid, found from white space alone, and it is exactly what a table specialist needs."),
 ("1865-000-143-005_p017", "magazine page with a photo, 2020s", "text yes, photo no",
  "The two columns, the header and the footer are found. But the grey photo counts as paper (it is lighter than ink), so it shows as a river: pictures need their own finder."),
 ("0005-055-003-004_p008", "single column of bulleted points, 2000s", "no split",
  "One block for the whole page. The points are separated by a little extra space, but not enough to stand out from the normal line gap. Here, the dashes at the start of each line are the real signal, not the white space."),
 ("0266-006-002-001_p042", "single column with a heading and footnotes", "no split",
  "One block. The heading's gap only covers part of the width, and the short rule above the footnotes is too short to count as a wall. A single column needs more than rivers: indents, rules and font size."),
]
cards = "".join(f"""<section><h2>{html.escape(k)} <span class=v>{html.escape(v)}</span></h2><p>{html.escape(t)}</p>
<figure><img loading=lazy src="rivers/{p}.jpg"><figcaption>{p}: the scan · the rivers (<b class=r>red</b> column gutters, <b class=b>blue</b> gaps between blocks, <b class=g>green</b> printed rules) · the blocks they leave</figcaption></figure></section>""" for p, k, v, t in PAGES)
(OUT / "rivers.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Rivers of paper</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}} main{{max-width:1250px;margin:auto}}
h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.15rem;margin:2em 0 .2em}} .v{{font-size:.8rem;font-weight:600;color:var(--acc);border:1px solid var(--acc);border-radius:10px;padding:1px 8px;margin-left:6px}}
p{{max-width:820px}} .lede{{font-size:1.1rem}} figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}} img{{width:100%;display:block;background:#fff}}
figcaption{{font-size:.85rem;color:var(--mut);padding-top:4px}} .r{{color:#d33}} .b{{color:#2a86d8}} .g{{color:#2a2}}
.note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:820px;border-radius:4px}}
</style></head><body><main><h1>Rivers of paper</h1>
<p class=lede>Your liquid, one scale up. Around a letter it traces the letter; around a page, the white space forms rivers that cut the page into its blocks. No model was used: only the ink, smeared sideways so each line becomes a bar, and the paper left between the bars.</p>
<p class=note><b>How:</b> a tall, thin channel of paper (at least 8 lines tall) is a column gutter, in <b class=r>red</b>. A flat channel clearly wider than this page's own normal line gap is a break between blocks, in <b class=b>blue</b>; the normal gap is measured on each page. A long printed line is a wall, in <b class=g>green</b>. Whatever ink the rivers and walls cut apart is a block, shown boxed on the right. Script: <code>experiments/39_ink_geometry/rivers.py</code>.</p>
<p><b>The short version:</b> the rivers are excellent at <b>columns</b> and good at <b>separating different kinds of things</b> (equations, tables, references), and they even find a table's grid and a verse's two halves. They are weak where the page doesn't use white space to separate things: <b>a single column</b>, where headings and footnotes are marked by size, indents and short rules, and <b>photos</b>, which aren't dark enough to count as ink. So the rivers give the edges; the other eye (a model that looks at the whole page) has to say what each block is, and catch what white space doesn't show.</p>
{cards}</main></body></html>""")
