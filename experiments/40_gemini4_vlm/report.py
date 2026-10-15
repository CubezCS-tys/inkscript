"""Build the owner's report for experiment 40: out/report.html (one self-contained page, images inlined).

    .venv/bin/python report.py

Images are cut and compressed from the approaches' side pictures with ImageMagick (`convert`) into out/report_img/.
Every number below comes from the approaches' score files, the reviewer's re-check, or the order-free word measure
(D_subset.py's bag of words vs the 9 truth pages, with the two orders of tanween+alef made the same).
"""
import base64
import html
import subprocess
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
IMG = OUT / "report_img"
IMG.mkdir(exist_ok=True)

# (name, source relative to out/, ImageMagick operations)
CUTS = [
    ("hero", "E_best/side/0747-001-003-001_p006.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("A", "A_oneshot/side/1000-000-020-028_p019.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("B", "B_azure_anchored/side/0924-012-005-007_p002.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("C", "C_whole_document/article_shots/2382-005-003-001_first4screens.jpg",
     ["-crop", "2512x2000+0+0", "+repage", "-resize", "1800x", "-quality", "68"]),
    ("D", "D_agentic/Bxc/fixes/0737-001-020-003_p009_r00.png", ["-resize", "900x", "-quality", "70"]),
    ("E", "E_best/article_shots/0870-017-001-003_top.jpg", ["-crop", "1000x2100+0+0", "+repage", "-quality", "68"]),
    ("table", "E_best/side/0200-000-140-006_p022.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("equation", "E_best/side/2382-005-003-001_p005.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("silent", "A_oneshot/silent_corrections_0005.jpg", ["-quality", "75"]),
    ("hamza", "E_best/side/0732-019-222,224-040_p001.jpg", ["-resize", "2400x", "-quality", "66"]),
    ("order", "E_best/side/0355-000-002-006_p017.jpg", ["-resize", "2400x", "-quality", "66"]),
]
# pass-2 gallery rows (each row 98 px, header 72 px): rows 7-16 (restored misprints and wrong ه→ة), 55-59 + 75
GALLERY = OUT / "E_best/arb_gallery.jpg"


def cut():
    for name, src, ops in CUTS:
        dst = IMG / f"{name}.jpg"
        if not dst.exists():
            subprocess.run(["convert", str(OUT / src), *ops, "-strip", str(dst)], check=True)
    for name, crops in (("arb_words", [(660, 980)]), ("arb_numbers", [(5364, 490), (7324, 98)])):
        dst = IMG / f"{name}.jpg"
        if dst.exists():
            continue
        parts = [IMG / "_h.jpg"]
        subprocess.run(["convert", str(GALLERY), "-crop", "1300x72+0+0", "+repage", str(parts[0])], check=True)
        for i, (y, h) in enumerate(crops):
            p = IMG / f"_r{i}.jpg"
            subprocess.run(["convert", str(GALLERY), "-crop", f"1300x{h}+0+{y}", "+repage", str(p)], check=True)
            parts.append(p)
        subprocess.run(["convert", *map(str, parts), "-append", "-quality", "70", "-strip", str(dst)], check=True)
        for p in parts:
            p.unlink()


def img(name, alt):
    b = base64.b64encode((IMG / f"{name}.jpg").read_bytes()).decode()
    return (f'<button class="shot" type="button" aria-label="Open larger: {html.escape(alt)}">'
            f'<img src="data:image/jpeg;base64,{b}" alt="{html.escape(alt)}" loading="lazy"></button>')


# ---------- the accuracy dial ----------
# order-free share of words wrong vs the 9 truth pages (vowel marks counted), $ per page at the launch price
DIAL = [
    # key, label, usd/page, words wrong, group, label dx, label dy, anchor
    ("A1", "A one call (low thinking)", 0.0178, 1.72, "A", -9, -7, "end"),
    ("A2", "A same call, other media setting", 0.0158, 2.56, "A", 9, -6, "start"),
    ("A3", "A high thinking", 0.0459, 2.11, "A", 0, -12, "middle"),
    ("B1", "B Azure-anchored", 0.0199, 1.47, "B", 8, -20, "start"),
    ("B5", "B strict fixes (11 pages)", 0.0183, 1.27, "B", 9, 15, "start"),
    ("C", "C whole document", 0.0183, 1.44, "C", -9, 5, "end"),
    ("E", "E combined (pass 1 + 2)", 0.0222, 1.39, "E", 9, 4, "start"),
    ("D1", "D loose prompt", 0.0157, 4.31, "D", 9, 4, "start"),
    ("D2", "D loose prompt + check", 0.0244, 3.14, "D", 9, 4, "start"),
    ("D3", "D strict prompt", 0.0158, 2.32, "D", -9, 8, "end"),
    ("D4", "D strict + Azure-guided check", 0.0240, 2.26, "D", 9, -6, "start"),
    ("D5", "D re-read every block", 0.0380, 2.09, "D", 6, 18, "end"),
    ("D6", "+ page check", 0.0448, 2.09, "D", 8, 18, "end"),
]
AZURE = 1.65


def dial_svg():
    W, H = 800, 430
    x0, x1, y0, y1 = 70, 770, 390, 30
    xs = lambda c: x0 + (c - 0.005) / (0.05 - 0.005) * (x1 - x0)
    ys = lambda e: y0 - e / 4.6 * (y0 - y1)
    o = [f'<svg viewBox="0 0 {W} {H}" role="img" aria-label="Words wrong against the truth versus dollars per page">']
    for e in (0, 1, 2, 3, 4):
        y = ys(e)
        o.append(f'<line x1="{x0}" x2="{x1}" y1="{y:.1f}" y2="{y:.1f}" class="grid"/>'
                 f'<text x="{x0 - 8}" y="{y + 4:.1f}" class="tick" text-anchor="end">{e}%</text>')
    for c in (0.01, 0.02, 0.03, 0.04, 0.05):
        x = xs(c)
        o.append(f'<line x1="{x:.1f}" x2="{x:.1f}" y1="{y0}" y2="{y0 + 5}" class="axis"/>'
                 f'<text x="{x:.1f}" y="{y0 + 20}" class="tick" text-anchor="middle">${c:.2f}</text>')
    o.append(f'<line x1="{x0}" x2="{x1}" y1="{y0}" y2="{y0}" class="axis"/>')
    o.append(f'<text x="{(x0 + x1) / 2}" y="{H - 4}" class="lab" text-anchor="middle">dollars per page (launch price; doubles on 1 December)</text>')
    o.append(f'<text x="16" y="{(y0 + y1) / 2}" class="lab" text-anchor="middle" transform="rotate(-90 16 {(y0 + y1) / 2})">words wrong vs the truth (lower is better)</text>')
    ya = ys(AZURE)
    o.append(f'<line x1="{x0}" x2="{x1}" y1="{ya:.1f}" y2="{ya:.1f}" class="azure"/>'
             f'<text x="{x1}" y="{ya + 16:.1f}" class="azlab" text-anchor="end">Azure 1.65% (already paid for)</text>')
    o.append(f'<text x="{x0 + 6}" y="{y1 + 4}" class="tick">↑ dots.mocr 6.7%, off the chart ($0.0002 a page on a rented GPU)</text>')
    for k, lab, c, e, g, dx, dy, anc in DIAL:
        x, y = xs(c), ys(e)
        o.append(f'<g class="pt g{g}"><circle cx="{x:.1f}" cy="{y:.1f}" r="{7 if k == "E" else 5.5}"><title>{lab}: {e:.2f}% words wrong, ${c:.4f} a page</title></circle>'
                 f'<text x="{x + dx:.1f}" y="{y + dy:.1f}" text-anchor="{anc}">{html.escape(lab)} · {e:.2f}%</text></g>')
    o.append("</svg>")
    return "".join(o)


CSS = """
/* layout: one reading column of 72ch with full-bleed pictures up to 1180px; tiles in an auto-fit grid */
:root{
  --paper:#f3f5f6; --sheet:#ffffff; --ink:#18232b; --muted:#5a6872; --rule:#d5dde2;
  --accent:#1d5e78; --accent-soft:#e1eef3;
  --good:#2f7d4f; --warn:#a86512; --bad:#b33a3a;
  --gA:#1d5e78; --gB:#7a4fa0; --gC:#2f7d4f; --gD:#a86512; --gE:#c2364f;
  --f-display:"Newsreader","Iowan Old Style",Georgia,serif;
  --f-body:"Atkinson Hyperlegible",system-ui,-apple-system,"Segoe UI",sans-serif;
  --f-data:"IBM Plex Mono",ui-monospace,Menlo,Consolas,monospace;
  --f-ar:"Scheherazade New","Amiri","Noto Naskh Arabic",serif;
}
@media (prefers-color-scheme: dark){:root:not([data-theme="light"]){
  --paper:#11181d; --sheet:#1a232a; --ink:#e3e9ec; --muted:#9aa8b1; --rule:#2c3943;
  --accent:#7fc0da; --accent-soft:#1d3440; --good:#6cc28f; --warn:#e0a251; --bad:#ec7f7f;
  --gA:#7fc0da; --gB:#c09be0; --gC:#6cc28f; --gD:#e0a251; --gE:#f0798f; color-scheme:dark}}
:root[data-theme="dark"]{
  --paper:#11181d; --sheet:#1a232a; --ink:#e3e9ec; --muted:#9aa8b1; --rule:#2c3943;
  --accent:#7fc0da; --accent-soft:#1d3440; --good:#6cc28f; --warn:#e0a251; --bad:#ec7f7f;
  --gA:#7fc0da; --gB:#c09be0; --gC:#6cc28f; --gD:#e0a251; --gE:#f0798f; color-scheme:dark}
*{box-sizing:border-box}
body{background:var(--paper);color:var(--ink);font:16px/1.6 var(--f-body);margin:0}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:28px 64px}
.col{max-width:72ch}
h1,h2,h3{font-family:var(--f-display);font-weight:600;line-height:1.2;text-wrap:balance;margin:0}
h1{font-size:clamp(1.9rem,4.5vw,2.9rem);letter-spacing:-.01em}
h2{font-size:clamp(1.4rem,3vw,1.85rem);margin-top:56px;padding-top:18px;border-top:1px solid var(--rule)}
h3{font-size:1.2rem}
p{margin:.6em 0}
.eyebrow{font:600 .75rem/1 var(--f-data);letter-spacing:.12em;text-transform:uppercase;color:var(--accent)}
.lede{font-size:1.12rem;color:var(--ink)}
.muted{color:var(--muted)}
.ar{font-family:var(--f-ar);font-size:1.2em;direction:rtl;unicode-bidi:isolate}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(240px,1fr));gap:14px;margin:26px 0 8px}
.tile{background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:16px 18px;display:flex;flex-direction:column;gap:6px;min-width:0}
.tile .k{font:600 .72rem/1.2 var(--f-data);letter-spacing:.1em;text-transform:uppercase;color:var(--muted)}
.tile .v{font:600 2.1rem/1.1 var(--f-display);font-variant-numeric:tabular-nums}
.tile .c{font-size:.92rem;color:var(--muted)}
.bars{display:grid;gap:4px;margin-top:4px;font:.78rem/1.2 var(--f-data);font-variant-numeric:tabular-nums}
.bar{display:grid;grid-template-columns:8.5em 1fr 3.6em;align-items:center;gap:6px}
.bar i{display:block;height:8px;border-radius:2px;background:var(--rule)}
.bar i b{display:block;height:100%;border-radius:2px;background:var(--accent)}
.bar.them i b{background:var(--muted)}
.bar span:last-child{text-align:right}
figure{margin:18px 0 0}
figure.tall .shot{max-width:min(100%,520px)}
figcaption{font-size:.92rem;color:var(--muted);margin-top:6px;max-width:80ch}
.shot{display:block;width:100%;padding:0;border:1px solid var(--rule);border-radius:4px;background:#fff;cursor:zoom-in}
.shot:focus-visible{outline:3px solid var(--accent);outline-offset:2px}
.shot img{display:block;width:100%;height:auto}
.legend3{display:flex;flex-wrap:wrap;gap:6px 18px;font:.8rem var(--f-data);color:var(--muted);margin-top:8px}
.approaches{display:grid;gap:34px;margin-top:20px}
.appr{display:grid;grid-template-columns:minmax(0,1fr);gap:10px}
.appr header{display:flex;flex-wrap:wrap;align-items:baseline;gap:6px 14px}
.tag{font:700 .8rem/1 var(--f-data);color:var(--sheet);background:var(--accent);border-radius:3px;padding:5px 7px}
.tA{background:var(--gA)}.tB{background:var(--gB)}.tC{background:var(--gC)}.tD{background:var(--gD)}.tE{background:var(--gE)}
.facts{display:flex;flex-wrap:wrap;gap:6px 16px;font:.85rem/1.4 var(--f-data);color:var(--muted);font-variant-numeric:tabular-nums}
.facts b{color:var(--ink);font-weight:600}
.split{display:grid;grid-template-columns:minmax(0,1.15fr) minmax(0,1fr);gap:22px;align-items:start}
.split.narrow{grid-template-columns:minmax(0,1fr) minmax(0,1.3fr)}
@media (max-width:760px){.split,.split.narrow{grid-template-columns:minmax(0,1fr)}}
.chart{overflow-x:auto;background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:10px;margin-top:16px}
.chart svg{min-width:640px;width:100%;height:auto;display:block;font-family:var(--f-data)}
.chart .grid{stroke:var(--rule);stroke-width:1}
.chart .axis{stroke:var(--muted);stroke-width:1}
.chart .tick{fill:var(--muted);font-size:11px}
.chart .lab{fill:var(--muted);font-size:12px}
.chart .azure{stroke:var(--ink);stroke-dasharray:5 4;stroke-width:1.4}
.chart .azlab{fill:var(--ink);font-size:12px;font-weight:600}
.chart .pt text{font-size:10.5px;fill:var(--ink)}
.chart .gA circle{fill:var(--gA)}.chart .gB circle{fill:var(--gB)}.chart .gC circle{fill:var(--gC)}.chart .gD circle{fill:var(--gD)}.chart .gE circle{fill:var(--gE)}
.chart circle{stroke:var(--sheet);stroke-width:1.5}
.tablewrap{overflow-x:auto;margin-top:14px}
table{border-collapse:collapse;font-size:.9rem;min-width:560px;width:100%;font-variant-numeric:tabular-nums}
th,td{padding:7px 10px;border-bottom:1px solid var(--rule);text-align:left;vertical-align:top}
th{font:600 .75rem/1.3 var(--f-data);letter-spacing:.06em;text-transform:uppercase;color:var(--muted)}
td.n{text-align:right;font-family:var(--f-data);font-size:.85rem}
tr.best td{background:var(--accent-soft)}
.fail{border-left:4px solid var(--bad);padding-left:14px}
.ok{border-left:4px solid var(--good);padding-left:14px}
.note{border-left:4px solid var(--warn);padding-left:14px}
ul.tight{padding-left:1.2em;margin:.4em 0}
ul.tight li{margin:.35em 0}
.plan{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:12px;margin-top:16px}
.plan div{background:var(--sheet);border:1px solid var(--rule);border-radius:6px;padding:12px 14px;min-width:0}
.plan h3{font-size:1.02rem;display:flex;gap:8px;align-items:center}
.pill{font:700 .68rem/1 var(--f-data);letter-spacing:.06em;text-transform:uppercase;border-radius:20px;padding:4px 8px;border:1.5px solid currentColor}
.p-good{color:var(--good)}.p-warn{color:var(--warn)}.p-bad{color:var(--bad)}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.88);overflow:auto;z-index:10;cursor:zoom-out;padding:env(safe-area-inset-top,0px) 0 env(safe-area-inset-bottom,0px)}
#lb img{display:block;max-width:none;width:auto;margin:0 auto;background:#fff}
#lb p{color:#eee;font:.85rem var(--f-data);text-align:center;margin:8px}
footer{margin-top:56px;font-size:.85rem;color:var(--muted)}
code{font-family:var(--f-data);font-size:.85em}
"""


def bar(label, value, maxv, them=False, fmt="{:.1f}%"):
    w = 100 * value / maxv
    return (f'<div class="bar{" them" if them else ""}"><span>{label}</span><i><b style="width:{w:.0f}%"></b></i>'
            f'<span>{fmt.format(value)}</span></div>')


def build():
    cut()
    t_text = "".join([bar("Argon (E)", 1.39, 7.3), bar("Argon (C)", 1.44, 7.3), bar("Azure", 1.65, 7.3, True),
                      bar("dots.mocr", 6.73, 7.3, True)])
    t_layout = "".join([bar("Argon (A)", 96.8, 100), bar("exp 39 model", 84.3, 100, True),
                        bar("dots.mocr", 80.2, 100, True), bar("Azure", 74.0, 100, True)])
    page = f"""<title>Gemini Argon Edition</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Atkinson+Hyperlegible:wght@400;700&family=IBM+Plex+Mono:wght@400;600&family=Newsreader:opsz,wght@6..72,500;6..72,600&family=Scheherazade+New:wght@400;700&display=swap">
<style>{CSS}</style>
<div class="wrap">
<header class="col">
  <p class="eyebrow">Experiment 40 · 15 October 2026 · $13.34 of the $20 cap</p>
  <h1>How far does Gemini 4 alone take a scanned Mandumah article?</h1>
  <p class="lede">Five teams tried five ways of turning our scanned Arabic journals into a clean digital edition with
  only <b>gemini-4-argon</b> looking at the page. The answer: in one call per page or per article, at about two cents a
  page, it gives far better <b>structure</b> than anything we have, and text about as good as Azure's. But the text
  is not <b>exactly as printed</b>. Argon quietly corrects misprints and adds hamzas the page does not have.</p>
</header>

<section class="tiles" aria-label="Headline numbers">
  <div class="tile"><span class="k">Text: words wrong vs the truth</span><span class="v">1.4%</span>
    <div class="bars">{t_text}</div>
    <span class="c">9 truth pages, order ignored, vowel marks counted. E, C and B (1.47%) are a tie within run-to-run noise. On the owner's 5 gold pages alone Azure wins: 1.54% vs Argon 1.76–1.96%.</span></div>
  <div class="tile"><span class="k">Layout: lines with the right block type</span><span class="v">96.8%</span>
    <div class="bars">{t_layout}</div>
    <span class="c">The same 21 pages (892 lines) of experiment 39's test set. 39's headline 87.7% / 84.4% is on all 44 pages. The referee that labelled the lines is also a Gemini, which may flatter Argon.</span></div>
  <div class="tile"><span class="k">Cost per page</span><span class="v">$0.018</span>
    <div class="bars">{bar("one call", 1.8, 4.5, fmt="{:.1f}¢")}{bar("E combined", 2.2, 4.5, fmt="{:.1f}¢")}{bar("D best", 4.5, 4.5, True, fmt="{:.1f}¢")}</div>
    <span class="c">Launch price, until 30 November. From 1 December the price doubles. Batch mode is half price.</span></div>
  <div class="tile"><span class="k">The whole archive (1M documents ≈ 15.9M pages)</span><span class="v">$176k</span>
    <div class="bars">{bar("Batch, now", 176, 705, fmt="${:.0f}k")}{bar("Standard, now", 353, 705, True, fmt="${:.0f}k")}{bar("Batch, Dec", 353, 705, True, fmt="${:.0f}k")}{bar("Standard, Dec", 705, 705, True, fmt="${:.0f}k")}</div>
    <span class="c">At E's $0.022 a page. About 9 days at 500 requests at once, if Google's quota allows it.</span></div>
</section>

<figure>
  {img("hero", "Vowelled verse page 0747 p006: scan, scan with Argon's blocks, Argon's page rendered")}
  <figcaption><b>What Argon makes of a vowelled poem (0747 p006, approach E).</b> Left: the scan. Middle: Argon's blocks
  drawn on the scan (purple = verse, orange = footnotes, grey = running header). Right: the digital page rendered in
  Chromium. Each verse is two half-lines side by side, the vowel marks are kept, each footnote number links to its note.
  Azure gives this page as a flat list of lines and reads it column by column. Tap any picture to see it full size.</figcaption>
</figure>

<h2>What each approach produces</h2>
<p class="col">Every approach wrote the same format (semantic HTML: headings, paragraphs, verse, footnotes, tables,
LaTeX equations, figures, page furniture) and was scored by the same script on the same 25 hand-picked hard pages,
plus 19 pages from three whole articles.</p>
<div class="approaches">

<article class="appr">
  <header><span class="tag tA">A</span><h3>One page in, one finished page out</h3></header>
  <div class="facts"><span><b>$0.018</b> a page</span><span><b>18 s</b></span><span>words wrong <b>1.72%</b></span><span>layout <b>96.8%</b></span></div>
  <p class="col">The simplest thing: the page picture, one prompt, one answer. Thinking "high" costs three times as
  much and gains nothing; two settings that should have made the same call differed by almost a point, so the setting
  does not matter. Reads verse and multi-column pages in the right order. Silently corrects misprints.</p>
  <figure>{img("A", "Approach A on 1000 p019: Quran quotes and verse with footnotes")}
  <figcaption>1000 p019: Quran quotes, verse lines (purple) and footnotes (orange), with the footnote numbers linked.</figcaption></figure>
</article>

<article class="appr">
  <header><span class="tag tB">B</span><h3>Argon arranges, Azure supplies the words</h3></header>
  <div class="facts"><span><b>$0.020</b> a page + Azure</span><span><b>17 s</b></span><span>words wrong <b>1.47%</b> (strict fixes 1.27%)</span><span>layout <b>96.8%</b></span><span>0 of 1,855 lines lost</span></div>
  <p class="col">Argon sees the page and Azure's numbered lines, and answers only with line numbers grouped into blocks
  (verse, table cells, footnotes, equations as LaTeX). The script builds the page from Azure's own text, so no word can
  be invented; any fix Argon proposes is listed with its reason. With the strict fix rule it is the most faithful reader
  in the experiment on the owner's gold pages (0.83% words wrong vs Azure's 1.54%), but on only 11 pages. Pictures
  with no text disappear, and text Azure missed stays missing.</p>
  <figure>{img("B", "Approach B on 0924 p002: a 1930 accounts page turned into tables")}
  <figcaption>0924 p002, a 1930 accounts page of a lawyers' journal: Azure's lines become real tables (green) with the
  pound and millieme columns.</figcaption></figure>
</article>

<article class="appr">
  <header><span class="tag tC">C</span><h3>The whole article in one call</h3></header>
  <div class="facts"><span><b>$0.018</b> a page</span><span>words wrong <b>1.44%</b></span><span>layout <b>93.2%</b></span><span>footnotes linked <b>143/144</b></span><span>cut paragraphs joined <b>37/44</b></span></div>
  <p class="col">The PDF of a whole article (up to 12 pages) goes in; one edition comes out with the title, authors,
  abstracts and keywords in both languages, journal and year on top, one section per page, and paragraphs cut by a
  page break flagged so they can be joined. Text is as good as page by page, heading levels follow the printed
  numbering (10/10 against 6/10 page by page), and it is 18% cheaper. No answer was cut off, up to 19,000 tokens.</p>
  <figure>{img("C", "Approach C: the flowing article view of 2382 with metadata, sections and equations")}
  <figcaption>2382 as a flowing article: metadata card, title, abstract in Arabic and English, numbered sections,
  data table and the six equations typeset. Running headers and page numbers are gone.</figcaption></figure>
</article>

<article class="appr">
  <header><span class="tag tD">D</span><h3>Draft, then zoom in and look again</h3></header>
  <div class="facts"><span><b>$0.016–0.045</b> a page</span><span>up to <b>74 s</b></span><span>words wrong <b>2.32% → 2.09%</b></span><span>layout <b>92.9%</b></span></div>
  <p class="col">A draft, then every region cut from the 300 dpi scan and re-read zoomed, then a last check of the whole
  page. The biggest finding was the prompt, not the passes: telling Argon to copy only the vowel marks that are printed
  halved its errors (4.38% to 2.32%) at no cost. After that, looking again fixed real dots and digits but moved the
  numbers little, for 2.8 times the cost.</p>
  <figure class="tall">{img("D", "Approach D: a zoomed re-read fixes tahtafa to takhtafa on 0737 p009")}
  <figcaption>0737 p009: the zoomed re-read sees the dot on the خ and corrects <span class="ar">تحتفى</span> to
  <span class="ar">تختفى</span>.</figcaption></figure>
</article>

<article class="appr">
  <header><span class="tag tE">E</span><h3>The combination: whole article, strict prompt, then a vote on doubtful words</h3></header>
  <div class="facts"><span><b>$0.022</b> a page</span><span>words wrong <b>1.39%</b></span><span>layout <b>96.3%</b></span><span>footnotes linked <b>188/188</b></span><span>22-page article in 3 chunks</span></div>
  <p class="col">C's whole-article call with D's strict prompt and the fixes for every fault A to D found (no double
  list numbers, free verse as verse, figures boxed and cropped in). Long articles go in chunks of 10 pages with page 1
  and the previous chunk's outline carried along: on the 22-page 0870 all 45 footnotes linked across chunks. Then
  where Argon and Azure disagree on a word, a blind zoomed crop goes back to Argon and two of three readings win. That
  vote changed 89 of 971 words; some were good, some made the text less faithful (below).</p>
  <figure class="tall">{img("E", "Approach E: the top of the 22-page article 0870 as a flowing edition")}
  <figcaption>The top of the 22-page 0870 (a law-journal article on the legal status of ships) as one flowing article, with footnotes under each page
  section and French references kept in Latin script.</figcaption></figure>
</article>
</div>

<h2>The accuracy dial</h2>
<p class="col">Each dot is one way of running Argon. Lower is fewer words wrong against the 9 pages where we know the
true text; further right is more money per page. The dashed line is Azure. Two things to read from it: everything
below about 2.3% is one cluster, and identical calls differ by about one point (the two A dots on the left made the
same call in effect). Paying for more passes does not buy a better text.</p>
<div class="chart">{dial_svg()}</div>
<div class="legend3"><span style="color:var(--gA)">● A one call</span><span style="color:var(--gB)">● B Azure-anchored</span><span style="color:var(--gC)">● C whole article</span><span style="color:var(--gD)">● D look again</span><span style="color:var(--gE)">● E combined</span></div>
<div class="tablewrap"><table>
<thead><tr><th>reader</th><th>words wrong, 9 truth pages</th><th>owner's 5 gold pages</th><th>4 born-digital pages</th><th>$ / page</th></tr></thead>
<tbody>
<tr><td>Azure (today's reader)</td><td class="n">1.65%</td><td class="n">1.54%</td><td class="n">1.77%</td><td class="n">paid</td></tr>
<tr class="best"><td>B strict fixes: Azure's words, Argon's structure</td><td class="n">1.27%</td><td class="n">0.83%</td><td class="n">—</td><td class="n">0.018</td></tr>
<tr><td>B Azure-anchored</td><td class="n">1.47%</td><td class="n">1.32%</td><td class="n">—</td><td class="n">0.020</td></tr>
<tr><td>E combined</td><td class="n">1.39%</td><td class="n">1.76%</td><td class="n">0.99%</td><td class="n">0.022</td></tr>
<tr><td>C whole article</td><td class="n">1.44%</td><td class="n">1.86%</td><td class="n">0.99%</td><td class="n">0.018</td></tr>
<tr><td>A one call</td><td class="n">1.72%</td><td class="n">1.96%</td><td class="n">—</td><td class="n">0.018</td></tr>
<tr><td>D best (every block re-read)</td><td class="n">2.09%</td><td class="n">2.31%</td><td class="n">—</td><td class="n">0.045</td></tr>
<tr><td>dots.mocr (experiment 36)</td><td class="n">6.73%</td><td class="n">7.25%</td><td class="n">—</td><td class="n">0.0002</td></tr>
</tbody></table></div>
<p class="col muted">Order ignored (reading order is scored separately: 98% for every Argon approach). Both ways of
writing tanween with alef counted the same; before that, C scored 2.10% because it writes <span class="ar">ًا</span>
where the truth has <span class="ar">اً</span>, which look identical. Gemini's lead comes from the born-digital pages,
mostly two of them; on the owner's scans Azure is still better than any Argon-only reading.</p>

<h2>Tables and equations</h2>
<div class="split">
  <figure>{img("table", "Table page 0200 p022: scan and Argon's rendered table with merged cells")}
  <figcaption><b>0200 p022.</b> A statistics table with headers merged across two and three rows, and a rotated cell
  on the right. Argon gives a real HTML table with the merges (right). Azure gives cells in a flat grid.
  Table agreement with Gemini Pro's drafts: 0.54–0.57 for every approach, Azure 0.20, on only 4 tables.</figcaption></figure>
  <figure>{img("equation", "Equation page 2382 p005: diagram and six equations as LaTeX")}
  <figcaption><b>2382 p005.</b> Six panel-data equations come out as LaTeX with subscripts and numbering, typeset
  with KaTeX (right). The diagram is boxed as a figure and cropped into the article view. All approaches read the
  equations the same; E's higher equation score was only how leader dots were written, so it cannot rank them.</figcaption></figure>
</div>

<h2>Where it fails, shown honestly</h2>
<div class="split narrow">
  <div class="fail col"><h3>It corrects the printer</h3>
  <p>On gold page 0005 p008 the print says <span class="ar">المتعمون</span> and <span class="ar">بطريقه</span>.
  Argon wrote <span class="ar">المتعلمون</span> and <span class="ar">بطريقة</span>, against an explicit instruction
  to copy misprints. It also turns <span class="ar">چ</span> into <span class="ar">ج</span>. For an edition this is
  a kindness; for the faithful text layer it is a defect, and no prompt stopped it entirely.</p></div>
  <figure>{img("silent", "Crop of 0005 p008 showing the printed misprints")}
  <figcaption>The printed lines: <span class="ar">المتعمون</span> in line 1, <span class="ar">بطريقه</span> in line 2.</figcaption></figure>
</div>
<div class="split narrow" style="margin-top:26px">
  <div class="fail col"><h3>The vote helps and hurts</h3>
  <p>E's second pass puts back misprints Argon had corrected: <span class="ar">لأساوب، دخل، عميات، تعم</span>. But in
  the same rows it also turns the printed <span class="ar">البيئه</span> and <span class="ar">والكتابه</span> into
  <span class="ar">ة</span>, because Azure and the blind crop agreed against the ink. It cut
  <span class="ar">زيادة</span> to <span class="ar">يادة</span>, and swapped eight numbers with dashes to Azure's
  order (75-58 → 58-75), which a crop cannot settle. A mistake Azure and Argon share never reaches the vote.</p></div>
  <figure>{img("arb_words", "Pass-2 vote rows: restored misprints and wrong ta marbuta changes")}
  <figcaption>Columns: crop of the printed word (red line), Argon, Azure, the blind zoomed reading, what was kept.
  Right: <span class="ar">لأساوب، دخل، عميات، تعم</span>. Wrong: <span class="ar">البيئة، والكتابة، بالمدرسة</span>.</figcaption></figure>
</div>
<figure>{img("arb_numbers", "Pass-2 vote rows: number order swapped and a word cut short")}
<figcaption>Number pairs flipped to Azure's order, and <span class="ar">زيادة</span> cut to <span class="ar">يادة</span>. The
order of digits around a dash inside Arabic text is a direction question the picture cannot answer.</figcaption></figure>
<div class="split narrow" style="margin-top:26px">
  <div class="fail col"><h3>Hamzas that are not printed</h3>
  <p>The poem 0732 p001 prints <span class="ar">وبعد ان تسكن</span> without the hamza. E, C and B all write
  <span class="ar">أن</span> (B because Azure itself does), and they drop the printed shadda in
  <span class="ar">الطّويلة</span>. Only A kept <span class="ar">ان</span>. The layout is right: title, poet, numbered
  sections, free verse line by line.</p></div>
  <figure>{img("hamza", "0732 p001 free verse: layout right, hamza added")}
  <figcaption>0732 p001, section 1, line 4 on the right.</figcaption></figure>
</div>
<div class="split narrow" style="margin-top:26px">
  <div class="note col"><h3>Where the score lies, not Argon</h3>
  <p>The worst-scoring gold page, 0355 p017, scores 20% characters wrong for every Argon approach. The gold's first
  line runs across both columns, inherited from Azure's draft. Argon reads the right column, then the left, which is
  correct. The same happens on verse pages, where Azure reads column by column. That is why this report uses words
  wrong with order ignored.</p></div>
  <figure>{img("order", "0355 p017 two-column page read in the right order")}
  <figcaption>0355 p017: two columns, read right column first.</figcaption></figure>
</div>

<h2>What Argon alone cannot do yet</h2>
<ul class="tight col">
  <li><b>Text exactly as printed.</b> It repairs misprints, adds hamzas, drops some printed vowel marks and shaddas,
  and writes <span class="ar">ة</span>/<span class="ar">ه</span> by sense where the dots are faint. Prompts and a
  second look reduce this; nothing stops it.</li>
  <li><b>The same answer twice.</b> Identical calls differ by about one point of words wrong.</li>
  <li><b>Word or line positions.</b> Its block boxes are good (99% hit Azure's lines) but there are no word
  coordinates, so inkscript's ink PDFs still need Azure's boxes.</li>
  <li><b>Say how sure it is.</b> At low and medium thinking it spends no thinking at all, and gives no confidence.</li>
  <li><b>Long articles in one answer.</b> About 30 pages fit the output limit; past that it needs chunks. Only one
  long article (22 pages) was tried that way.</li>
  <li><b>Pictures.</b> Figures are boxed and described; nothing yet crops photos and drawings as well as a picture
  specialist would. Pages with no text lose their figure in B.</li>
  <li><b>Proof on a large truth set.</b> Truth exists for 9 pages. A, B, C and E cannot be ranked against each other
  on that.</li>
</ul>

<h2>What this means for the specialist plan</h2>
<p class="col">The plan: Azure as truth for the text, our own specialists for layout, order, style, tables, equations,
pictures, the whole document, a writer and an auditor. This experiment says where Argon could stand in for a
specialist, and where it should not.</p>
<div class="plan">
  <div><h3>Text <span class="pill p-good">Azure stays</span></h3><p>Argon is not exactly-as-printed. The most faithful text here came from Azure's words with Argon only arranging them (B strict, 0.83% on gold). Argon is useful as a second reader that points at doubtful words, not as the one that decides.</p></div>
  <div><h3>Layout and order <span class="pill p-good">Argon is ahead</span></h3><p>96.8% of lines typed right against 84.3% for the experiment 39 model on the same pages, and right-column-first order on every multi-column page. It could do this job directly, or label training pages for our own model at about $0.02 a page, with no dots licence question.</p></div>
  <div><h3>Tables <span class="pill p-good">strong</span></h3><p>Real tables with merged and rotated cells even on 1930s accounts. B-style (Azure's cell text, Argon's grid) keeps the words safe.</p></div>
  <div><h3>Equations <span class="pill p-warn">good, unproven</span></h3><p>LaTeX that renders, on every approach. Only 3 equations were scored; gold equations are needed.</p></div>
  <div><h3>Pictures <span class="pill p-bad">still needed</span></h3><p>Boxes and descriptions only. A picture specialist is still needed.</p></div>
  <div><h3>Whole document <span class="pill p-good">strong</span></h3><p>Metadata in both languages, consistent heading levels, footnotes linked across pages (188/188), broken paragraphs joined (45/51). This is the clearest gain over page-by-page work.</p></div>
  <div><h3>Style <span class="pill p-warn">partial</span></h3><p>Bold was added to the format in E; italics, sizes and fonts were not tested.</p></div>
  <div><h3>Writer <span class="pill p-good">fits B</span></h3><p>B is already a writer: it builds the edition from Azure's text and Argon's blocks, and lists every change it would like to make.</p></div>
  <div><h3>Auditor <span class="pill p-warn">not alone</span></h3><p>Argon checking Argon shares its own language bias, and the vote with Azure lets shared mistakes through. An independent reader (Kraken) is still the right auditor.</p></div>
</div>

<footer class="col">
  <p>Sample: 25 pages chosen for stated reasons (5 owner gold, 4 born-digital, equations, tables, poetry, footnotes,
  Quran, columns, pre-1960 prints, mixed Latin, a front page) plus 19 pages of three whole articles; E also ran 26
  whole articles or windows (143 pages). Spend from the log: $13.34 of $20 (setup $0.004, A $2.53, B $1.98, C $2.96,
  D $2.49, E $3.39). Every quality number was reproduced by a reviewer from the saved outputs. Prices: $2 / $10 per
  million input / output tokens until 30 November 2026, $4 / $20 from 1 December.</p>
  <p>Code and notes: <code>experiments/40_gemini4_vlm/</code>; outputs and every side picture under its <code>out/</code>.</p>
</footer>
</div>
<div id="lb" hidden><p>Tap to close</p><img alt=""></div>
<script>
(function(){{
  var lb=document.getElementById('lb'), im=lb.querySelector('img');
  document.querySelectorAll('.shot').forEach(function(b){{
    b.addEventListener('click',function(){{var s=b.querySelector('img');im.src=s.src;im.alt=s.alt;lb.hidden=false;lb.scrollTop=0;}});
  }});
  lb.addEventListener('click',function(){{lb.hidden=true;im.removeAttribute('src');}});
  document.addEventListener('keydown',function(e){{if(e.key==='Escape')lb.hidden=true;}});
}})();
</script>
"""
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print(OUT / "report.html", round((OUT / "report.html").stat().st_size / 1e6, 2), "MB")


if __name__ == "__main__":
    build()
