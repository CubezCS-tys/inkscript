"""out/report.html: what Chromium does with a letter's box, the stacked rule, before/after on the judge, the checks.
Self-contained (images inlined), light/dark, phone width.
    ../../.venv/bin/python make_report23.py
"""
import json, base64, html
from pathlib import Path
import numpy as np, cv2
import judge23 as Q
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; CH = OUT / "chromium"


def b64(img):
    ok, buf = cv2.imencode(".png", img); return "data:image/png;base64," + base64.b64encode(buf.tobytes()).decode()


def word_crop(name, i, pad=(40, 26)):
    d = json.load(open(CH / f"{name}.json")); S, ox, oy, H = d["to_screen"]
    x0 = min(g["box"][0] for g in d["glyphs"]); x1 = max(g["box"][2] for g in d["glyphs"])
    y0 = min(g["box"][1] for g in d["glyphs"]); y1 = max(g["box"][3] for g in d["glyphs"])
    im = cv2.imread(str(CH / f"{name}_{i}.png"))
    a, b = int(x0 * S - ox) - pad[0], int(x1 * S - ox) + pad[0]; c, e = int((H - y1) * S - oy) - pad[1] - 20, int((H - y0) * S - oy) + pad[1]
    return im[max(0, c):e, max(0, a):b], d


def strip(name, n):
    tiles, texts = [], []
    for i in range(n):
        p = CH / f"{name}_{i}.png"
        if not p.exists(): break
        t, d = word_crop(name, i); tiles.append(t); texts.append(d["drags"][i]["text"])
    return tiles, texts


def figure(tiles, caps):
    return "<div class=strip>" + "".join(f"<figure><img src='{b64(t)}' alt=''><figcaption>{html.escape(c)}</figcaption></figure>" for t, c in zip(tiles, caps)) + "</div>"


def main():
    S = json.load(open(OUT / "summary23.json")); st = S["stacked"]
    checks = [json.loads(l) for l in open(OUT / "checks.jsonl")]
    parts = []
    # Chromium: single letters, before / after
    for w in ("المحكم", "على"):
        for v, lab in (("base", "today"), ("cell", "stacked rule")):
            t, x = strip(f"{v}_{w}_single", 8)
            parts.append(f"<h4>{w} — {lab}: each letter selected alone</h4>" + figure(t, [f"copied «{s}»" for s in x]))
        for v, lab in (("base", "today"), ("cell", "stacked rule")):
            t, x = strip(f"{v}_{w}", 8)
            parts.append(f"<h4>{w} — {lab}: dragging from the right, letter by letter</h4>" + figure(t, [f"«{s}»" for s in x]))
    chrom = "\n".join(parts)
    line = ""
    for v, lab in (("base", "today"), ("cell", "stacked rule")):
        d = json.load(open(CH / f"{v}_line.json")); im = cv2.imread(str(CH / f"{v}_line_0.png"))
        line += f"<figure class=wide><img src='{b64(im[150:380, 0:840])}' alt=''><figcaption>{lab}: a drag over a whole stretch of the line; copied «{html.escape(d['drags'][0]['text'])}»</figcaption></figure>"
    probe = f"<figure class=wide><img src='{b64(cv2.imread(str(CH / 'ala_cmp2.png')))}' alt=''><figcaption>على on the fixture (page 3), real Chromium 153. Row 1: today, each letter alone — a full-height column. Row 2: every letter in its own copy of the font, FontBBox = its own box — each letter alone gets its own height. Row 3: the same PDF, dragging — Chromium merges the line's boxes into one rectangle. Row 4: boxes widened to each letter's ink (overlapping in x) — selecting ل alone picks up ى too (copied «لى»).</figcaption></figure>"
    # judge examples
    its, ref = Q.items(); byid = {it["id"]: it for it in its}
    rows = S["rows"]; ex = [r for r in rows if r["before"] is not None and r["after"] is not None]
    pick = [r for r in ex if r["after"] and not r["before"]][:10] + [r for r in ex if r["before"] and not r["after"]][:6] + [r for r in ex if not r["before"] and not r["after"]][:6]
    def lab(v): return "<b class=ok>right</b>" if v else "<b class=no>wrong</b>"
    cards = ""
    for r in pick:
        a = Q.item_image(byid[r["i0"]]); b = Q.item_image(byid[r["i1"]])
        cards += (f"<div class=card><div class=pair><figure><img src='{b64(a)}' alt=''><figcaption>today {lab(r['before'])}</figcaption></figure>"
                  f"<figure><img src='{b64(b)}' alt=''><figcaption>own height {lab(r['after'])}</figcaption></figure></div>"
                  f"<p>{html.escape(r['letter'])} ({r['role']}), {r['w']}</p></div>")
    def ci(d): return f"{d['rate']}% <small>({d['ci'][0]}–{d['ci'][1]})</small>"
    samp = "".join(f"<tr><td>{s}</td><td>{v['words']}</td><td>{v['before']['letter']}% <small>({v['before']['letter_ci'][0]}–{v['before']['letter_ci'][1]})</small></td><td>{v['after']['letter']}% <small>({v['after']['letter_ci'][0]}–{v['after']['letter_ci'][1]})</small></td>"
                   f"<td>{v['before']['word']}%</td><td>{v['after']['word']}%</td><td>{v['words_only_after']} vs {v['words_only_before']}</td></tr>" for s, v in S["samples"].items())
    names = {"A": "A · 130 unseen words", "B": "B · 50 unseen, feeler misread", "C": "C · 50 fixture words"}
    samp = samp.replace("<td>A</td>", f"<td>{names['A']}</td>").replace("<td>B</td>", f"<td>{names['B']}</td>").replace("<td>C</td>", f"<td>{names['C']}</td>")
    chk = "".join(f"<tr class='{'' if c['variant'] == 'before' else 'after'}'><td>{c['doc']}</td><td>{'today' if c['variant'] == 'before' else 'stacked rule'}</td><td>{c['checks']['intact']}</td><td>{c['checks']['lines']}</td><td>{c['checks']['inversions']}</td><td>{c['checks'].get('coverage', '')}</td></tr>" for c in checks)
    up, lo = st["upper"], st["lower"]; pa = st["paired"]
    doc = f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Stacked letter highlights</title>
<style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#66625a;--card:#fff;--line:#e2ded5;--ok:#1d7a3e;--no:#b3261e;--acc:#2a5d9f}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161614;--fg:#ecebe6;--mut:#a39f95;--card:#201f1c;--line:#38362f;--ok:#62c38a;--no:#f08a80;--acc:#8db4ea}}}}
:root[data-theme=dark]{{--bg:#161614;--fg:#ecebe6;--mut:#a39f95;--card:#201f1c;--line:#38362f;--ok:#62c38a;--no:#f08a80;--acc:#8db4ea}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:0 16px}}
main{{max-width:1000px;margin:0 auto;padding:24px 0 64px}} h1{{font-size:1.6rem;margin:.2em 0}} h2{{margin-top:2em;border-bottom:1px solid var(--line);padding-bottom:.2em}}
h4{{margin:1.2em 0 .3em;font-weight:600}} small{{color:var(--mut)}} .lead{{color:var(--mut);max-width:62ch}}
.strip{{display:flex;flex-wrap:wrap;gap:8px}} figure{{margin:0}} figure img{{display:block;max-width:100%;border:1px solid var(--line);border-radius:4px;background:#fff}}
figcaption{{font-size:.8rem;color:var(--mut);margin-top:2px}} .wide img{{width:100%}}
.cards{{display:grid;grid-template-columns:repeat(auto-fill,minmax(290px,1fr));gap:12px}} .card{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px}}
.pair{{display:grid;grid-template-columns:1fr 1fr;gap:6px}} .card p{{margin:.3em 0 0;font-size:.85rem;color:var(--mut)}}
.ok{{color:var(--ok)}} .no{{color:var(--no)}} .tw{{overflow-x:auto}} table{{border-collapse:collapse;font-size:.92rem;min-width:520px}} td,th{{border-bottom:1px solid var(--line);padding:4px 8px;text-align:left}}
tr.after td{{font-weight:600}} .big{{font-size:1.25rem}} .verdict{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;border-radius:4px}}
</style></head><body><main>
<h1>Can a stacked letter's highlight sit on its own letter?</h1>
<p class=lead>Experiment 23, 2026-10-06. Where one letter sits above the next (لمـ, فى, مح), today's highlight is a column the height of the line,
so it cannot pick out the upper letter from the lower one. Everything below about the highlight was checked in a real Chromium 153 (the D18 set-up), not reasoned about.</p>
<div class=verdict><p class=big><b>What we found.</b> Chromium can do it, but the judge says it makes things worse, and pdfium breaks lines.
A letter's highlight is as wide as its declared box (d1) and as tall as its <b>font's</b> FontBBox, which today the whole line shares. Give a stacked letter its own copy of the font and Chromium draws its highlight at its own height. Copying and selection order still work.
But the judge marks stacked letters right less often: <b>{st['before']['rate']}% → {st['after']['rate']}%</b> (paired: {pa['only_after']} better, {pa['only_before']} worse; difference {st['after_minus_before_ci'][0]} to {st['after_minus_before_ci'][1]} points).
The reason is that a letter's own ink, as the cutter assigns it, is often wrong where today's full-height column hid that: a و whose loop went to the next letter keeps only its tail. And 1036 and 0772 lose lines. <b>Do not apply.</b></p></div>

<h2>1 · What Chromium 153 does with a letter's box</h2>
<ul>
<li><b>Width comes from the glyph's d1 box</b>, not from the advance: widening one letter's d1 by 6 px moved the edge of its highlight by exactly that much.</li>
<li><b>Height comes from the font's FontBBox</b>, not from d1: shortening a letter's d1 changed nothing on screen. Changing the line font's FontBBox moved the top and bottom of every highlight in that line.</li>
<li>So within one line font, every highlight is as tall as the line. A letter gets its own height only if it has <b>its own font</b>, which means its own text object.</li>
<li>When you drag across several letters, Chromium draws one rectangle around all of them, so a drag looks the same as before. The difference shows when a single letter is selected, and in the judge's question.</li>
<li>Boxes that overlap in x <b>break selection</b>: with ى's box widened under ل, selecting ل alone copied «لى». So the rule keeps today's widths (letters still tile the word) and changes only the height.</li>
</ul>
{probe}
{chrom}
<h4>A whole line</h4><div class=strip>{line}</div>
<p><small>With d1 at the line's full height, selecting ى alone in على also copied a space («ى »). A drag that includes a stacked letter can reach a little higher or lower than before: the line's rectangle grows to the stacked letter's whole ink, which today is clipped at the line above.</small></p>

<h2>2 · The rule tried</h2>
<p>Two neighbouring cut letters of one word count as <b>stacked</b> when their bodies (each letter's largest outline, dots and holes left out) overlap horizontally by at least 40% of the narrower one, and their centres are at least a quarter of the pair's joint height apart.
Each of the two then gets its own copy of the line's font, with FontBBox set to its advance × its own ink height, and its own TJ. Its d1 takes the line's full height: pdfium starts a new line between two objects whose boxes do not overlap vertically.
The cuts themselves are not changed. On the fixture this applies to 468 letters, on 1036 1,542, on 0618 2,136 and on 0772 2,552.</p>

<h2>3 · Before / after on the judge</h2>
<p>Experiment 18's judge: Gemini 3.8 Flash, two questions, right = graded EXACT <i>and</i> the blind answer brackets exactly that letter.
Same sample words; {st['judged']} stacked letters in them. One change was needed because a highlight can now be shorter than the word: the prompts say "a rectangular region" instead of "a vertical band".
So the <i>today</i> boxes were asked again under the same prompt, and before and after stay paired.</p>
<div class=tw><table><tr><th>stacked letters</th><th>right</th></tr>
<tr><td>today, 18/21's prompt</td><td>{ci(st['old'])}</td></tr>
<tr><td>today, region prompt</td><td>{ci(st['before'])}</td></tr>
<tr class=after><td>own height, region prompt</td><td>{ci(st['after'])}</td></tr>
<tr><td>after − before (paired bootstrap)</td><td>{st['after_minus_before_ci'][0]} to {st['after_minus_before_ci'][1]} points</td></tr>
<tr><td>upper letter of the pair</td><td>{up['before']} → {up['after']} of {up['n']}</td></tr>
<tr><td>lower letter of the pair</td><td>{lo['before']} → {lo['after']} of {lo['n']}</td></tr></table></div>
<h4>Whole samples (every other letter keeps experiment 21's verdict: its box is unchanged)</h4>
<div class=tw><table><tr><th>sample</th><th>words</th><th>letters today</th><th>letters after</th><th>words today</th><th>words after</th><th>words right only after vs only before</th></tr>{samp}</table></div>
<h4>Real crops: the box today (left) and with its own height (right), as the judge saw them. First the letters that improved, then those that got worse, then those wrong both ways.</h4>
<div class=cards>{cards}</div>

<h2>4 · Did anything that works break?</h2>
<p>pdfium (the pinned 5.12.1) checks from <code>--verify</code>, plus letter coverage, on experiment 21's builds before and after the rule:</p>
<div class=tw><table><tr><th>doc</th><th></th><th>words intact</th><th>lines in order</th><th>inversions</th><th>coverage</th></tr>{chk}</table></div>
<p>The fixture and 0618 come through unchanged; on the fixture the copied text differs only in five lines losing a leading space.
<b>1036 page 1 (a title page with very large glyphs) and 13 pages of 0772 lose lines</b>: pdfium breaks the line where a stacked letter's text object starts.
Getting this far took two other fixes. pdfium sorts a line's text objects by where each one starts, so a letter followed by a backwards pen move had to stay in the line's font. And a word space has to travel with the letter's object, or pdfium drops the space. The rule pdfium uses for the remaining breaks has not been measured yet.</p>

<h2>5 · What it means</h2>
<ul>
<li>A partial-height highlight is possible in today's Chromium. It needs one font per letter: Chromium takes the height from FontBBox, never from d1.</li>
<li>The height cannot come from the letter's own ink as the cutter assigns it today. On stacked pairs that ink is often wrong: a و whose loop went to the next letter, or a ل without its foot. Today's full-height column hides those mistakes, because the stretch of baseline is right more often than the ink. The judge saw it: {pa['only_before']} letters got worse, {pa['only_after']} got better. Many of the "stacked" pairs the rule found are really wrong cuts, not letters written one above the other.</li>
<li>Splitting a line into several text objects is also fragile in pdfium's line building: two of four books lost lines.</li>
<li>Widening a box to a letter's ink (boxes that overlap in x) is ruled out: it broke selecting a single letter.</li>
<li>Next: stacked letters first need the right <i>ink</i>, a cutter question, not a box question. Only once the ink is right is a per-letter font worth trying again, and only after finding out why pdfium breaks those lines (1036 p1, 0772 p38).</li>
</ul>
<p><small>Code: chromium.py (scripted Chromium 153), splitfont.py (hand-made probes), stackrule.py + post.py (the rule, applied to finished PDFs), checks.py / run_checks.sh, boxes23.py, judge23.py, analyze23.py. inspect.patch: page_glyphs reads a line written as several TJ.</small></p>
</main></body></html>"""
    (OUT / "report.html").write_text(doc, encoding="utf-8"); print("written", len(doc) // 1024, "KB")


if __name__ == "__main__":
    main()
