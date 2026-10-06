"""out/report.html: self-contained (images inline), light/dark, phone width."""
import json, base64
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; REP = OUT / "rep"
M = json.load(open(REP / "meta.json")); S = json.load(open(OUT / "summary25_lumpfoot.json")); H = json.load(open(OUT / "heights_summary_lumpfoot.json"))
CK = json.load(open(OUT / "checks25.json"))
img = lambda n, alt="", cls="": f'<img class="{cls}" alt="{alt}" src="data:image/png;base64,{base64.b64encode(open(REP / n, "rb").read()).decode()}">'


def bar(label, v, ci=None, tone="b", note=""):
    w = f'<div class="ci" style="left:{ci[0]}%;width:{max(0.5, ci[1] - ci[0])}%"></div>' if ci else ""
    return f'<div class="bar"><div class="bl">{label}</div><div class="track"><div class="fill {tone}" style="width:{v}%"></div>{w}</div><div class="bv">{v:.1f}%<span>{note}</span></div></div>'


pairs = "".join(f'<figure class="pair"><div class="two"><div>{img("b_" + p["wid"] + ".png", "today")}<small>today</small></div><div>{img("a_" + p["wid"] + ".png", "after")}<small>after</small></div></div>'
                f'<figcaption><b dir="rtl">{p["text"]}</b> · piece <span dir="rtl">{p["piece"]}</span> · letters: {" ".join(f"<i class=c{k}>{u}</i>" for k, u in enumerate(p["letters"]))}</figcaption></figure>' for p in M["pairs"])
still = "".join(f'<figure class="pair"><div class="two"><div>{img("b_" + p["wid"] + ".png")}<small>today</small></div><div>{img("a_" + p["wid"] + ".png")}<small>after</small></div></div><figcaption><b dir="rtl">{p["text"]}</b> · {" ".join(f"<i class=c{k}>{u}</i>" for k, u in enumerate(p["letters"]))}</figcaption></figure>' for p in M["still"])
fonts = ""
for doc, f in M["font"].items():
    ch = f["changed"]; nb = sum(r["verdict"] == "better" for r in ch); nw = sum(r["verdict"] == "worse" for r in ch)
    cells = "".join(f'<div class="glyph {r["verdict"]}"><div class="gl"><b>{r["letter"]}</b> {r["form"]}<em>{r["verdict"]}</em></div><div class="two">{img(r["img"] + "_b.png", "today")}{img(r["img"] + "_a.png", "after")}</div></div>' for r in sorted(ch, key=lambda r: {"better": 0, "worse": 1, "same": 2}[r["verdict"]]))
    fonts += f'<h3>{doc} — {len(ch)} of {f["forms"]} letter-forms changed: <span class="good">{nb} better</span>, <span class="bad">{nw} worse</span>, {len(ch) - nb - nw} about the same</h3><div class="glyphs">{cells}</div>'
A = S["all"]; st = S["stacked"]
ck_rows = "".join(f'<tr><td>{d}</td><td>{c["today"]["intact"]}</td><td>{c["after"]["intact"]}</td><td>{c["today"]["lines"]}</td><td>{c["after"]["lines"]}</td><td>{c["today"]["coverage"]}</td><td>{c["after"]["coverage"]}</td><td>{c["text_changed"]}</td></tr>' for d, c in CK.items())
sm = "".join(f'<tr><td>{s}</td><td>{v["words"]}</td><td>{v["before"]["letter"]} ({v["before"]["letter_ci"][0]}–{v["before"]["letter_ci"][1]})</td><td>{v["after"]["letter"]} ({v["after"]["letter_ci"][0]}–{v["after"]["letter_ci"][1]})</td><td>{v["diff_ci"][0]} to {v["diff_ci"][1]}</td><td>{v["before"]["word"]} → {v["after"]["word"]}</td></tr>' for s, v in S["samples"].items())
spend = sum(json.loads(l)["usd"] for l in open(OUT / "spend.jsonl"))
html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Join Ink</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1d1b;--mut:#6b6a66;--card:#fff;--line:#e3e1db;--b:#8a8f99;--a:#2f6fd6;--good:#1f8a4c;--bad:#c0392b;--ci:#1d1d1b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#161615;--fg:#ecebe6;--mut:#a3a29c;--card:#22221f;--line:#3a3935;--b:#7d828c;--a:#6aa0ff;--good:#4cc27e;--bad:#ff7a6b;--ci:#ecebe6}}}}
:root[data-theme="dark"]{{--bg:#161615;--fg:#ecebe6;--mut:#a3a29c;--card:#22221f;--line:#3a3935;--b:#7d828c;--a:#6aa0ff;--good:#4cc27e;--bad:#ff7a6b;--ci:#ecebe6}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1080px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:1.9rem;line-height:1.2;margin:.2em 0}}h2{{margin-top:2.4em;font-size:1.35rem;border-top:1px solid var(--line);padding-top:1em}}h3{{font-size:1.05rem;margin:1.6em 0 .6em}}
p,li{{max-width:72ch}}.lede{{font-size:1.1rem;color:var(--mut)}}.good{{color:var(--good)}}.bad{{color:var(--bad)}}
img{{max-width:100%;height:auto;display:block;background:#fff;border-radius:6px;image-rendering:pixelated}}
.pairs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:14px}}
.pair{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}}.two{{display:grid;grid-template-columns:1fr 1fr;gap:8px;align-items:end}}
.two small{{display:block;text-align:center;color:var(--mut);font-size:.8rem}}figcaption{{font-size:.85rem;color:var(--mut);margin-top:6px}}figcaption b{{color:var(--fg);font-size:1.05rem}}
i{{font-style:normal;padding:0 3px;border-radius:3px;color:#fff}}.c0{{background:#2878d6}}.c1{{background:#3c963c}}.c2{{background:#d23c3c}}.c3{{background:#0096aa}}.c4{{background:#aa3caa}}.c5{{background:#c88c00}}
.explain{{display:grid;grid-template-columns:1fr 1fr;gap:14px}}@media(max-width:640px){{.explain{{grid-template-columns:1fr}}}}
.glyphs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(230px,1fr));gap:10px}}.glyph{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}}
.glyph.better{{border-color:var(--good)}}.glyph.worse{{border-color:var(--bad)}}.gl{{font-size:.85rem;color:var(--mut);display:flex;gap:6px;align-items:baseline}}.gl b{{font-size:1.3rem;color:var(--fg)}}.gl em{{margin-left:auto;font-style:normal}}
.glyph.better em{{color:var(--good)}}.glyph.worse em{{color:var(--bad)}}
.bars{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:14px;margin:10px 0}}.bar{{display:grid;grid-template-columns:minmax(120px,30%) 1fr 92px;gap:10px;align-items:center;margin:7px 0}}
.bl{{font-size:.9rem}}.track{{position:relative;height:18px;background:color-mix(in srgb,var(--line) 60%,transparent);border-radius:4px}}.fill{{height:100%;border-radius:4px}}.fill.b{{background:var(--b)}}.fill.a{{background:var(--a)}}.fill.g{{background:var(--good)}}
.ci{{position:absolute;top:7px;height:4px;border-left:2px solid var(--ci);border-right:2px solid var(--ci);background:color-mix(in srgb,var(--ci) 45%,transparent)}}.bv{{font-variant-numeric:tabular-nums;font-size:.9rem}}.bv span{{display:block;color:var(--mut);font-size:.75rem}}
.tw{{overflow-x:auto}}table{{border-collapse:collapse;font-size:.88rem;font-variant-numeric:tabular-nums;min-width:560px}}td,th{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left}}
.note{{background:var(--card);border-left:4px solid var(--a);padding:10px 14px;border-radius:6px}}
@media(max-width:640px){{.bar{{grid-template-columns:1fr;gap:3px}}}}
</style></head><body><main>
<h1>Who owns the ink at a join</h1>
<p class="lede">Experiment 25 · 2026-10-06. Where one letter sits on another (لو، جنو، هو، لقو), the cutter often gave the next letter's head to the letter before it, so a final و was only its tail. One new rule about heads fixes the ink on most of these words. The selection boxes barely move, and the books' fonts get their missing heads back.</p>

<h2>What it looks like</h2>
<p>Each letter's ink is shown in its own colour. The black line is the pen path the cutter follows, and the white dots are its cuts. Left: today's src. Right: with the patch.</p>
<div class="pairs">{pairs}</div>

<h2>Why it happened: the pen circles the head and comes back</h2>
<div class="explain"><figure class="pair">{img("explain_b.png")}<figcaption>Today, <b dir="rtl">هو</b>. The pen comes from the ه, goes once round the و's head, and leaves into the tail <em>from the same point</em>. The shortest path therefore skips the circle, and the whole head hangs from that one point (red ring: a lump much thicker than a stroke). The cut fell just below it, so the head went to the ه.</figcaption></figure>
<figure class="pair">{img("explain_a.png")}<figcaption>After. A new hard fact, like the dots and the tall stroke: <b>a letter that has no head (ا د ر ل ن ب ت ي ى س …) may not own one; a letter with a head (و ف ق م ه ة ص ط, ع/غ when joined) is rewarded for owning it.</b> The cut moves up past the head's root. The tail and head are now one letter, as the pen wrote them.</figcaption></figure></div>
<p>Today every <span dir="rtl">و</span> is cut the same way, so the document's atlas learned that a final <span dir="rtl">و</span> is a bare tail and kept confirming it. This is the self-confirming error the atlas is prone to (D10). Only a fact from outside the atlas can break it. On the four books' sample pages, a lump appears inside the stretch of 19% of final <span dir="rtl">و</span> today and 43% after (isolated <span dir="rtl">و</span>: 64%). Open heads, which have a hole, are not lumps and are not affected.</p>
<p>A second, small change: a final <span dir="rtl">أ</span> whose stem wiggles or has a flag at the top is now recognised as a stem (it extends experiment 21's <code>stem_foot</code>). It changed 2 boxes in the sample.</p>

<h2>The book's font as a witness</h2>
<p>Each letter-form below is restored from its best printings (experiment 11), today (left) and after (right). Only the forms that changed are shown. A wrong glyph means a wrong cut repeated across the whole document.</p>
{fonts}
<p>Still wrong in 0582, before and after: the medial <span dir="rtl">ل</span> of <span dir="rtl">على</span> keeps the first stretch of the <span dir="rtl">ى</span>'s descent, and the final <span dir="rtl">أ</span> keeps its neighbour's tooth.</p>

<h2>Per-letter ink, counted by eye</h2>
<p>All 52 pieces that hold experiment 23's 112 stacked letters, drawn before and after (<code>out/pairs_a.png</code>, <code>pairs_b.png</code>). For each stacked letter: is its own ink, and only its own, coloured as that letter? 17 letters were too small or unclear to call.</p>
<div class="bars">{bar("today", 100 * 52 / 95, None, "b", "52 of 95")}{bar("after", 100 * 76 / 95, None, "a", "76 of 95")}</div>
<p>24 letters got better and none got worse. Most of the gains are a <span dir="rtl">و</span> getting its head back, together with the letter before it losing that head. The 19 that are still wrong have other causes. In 7 the path starts in the wrong place: the word is larger than its line (a heading), or the start was chosen too low, as in <span dir="rtl">مسئو، صفه، ميه</span>. In 8 the cuts are shifted by one letter in pieces that touch other ink or are underlined. One is a <span dir="rtl">ق</span> head that is not solid (<span dir="rtl">بق</span>). The other 3 are unclear joins. Among 40 random pieces anywhere on the sample pages whose cuts the patch changed, 6 are clearly better (all a <span dir="rtl">و</span> head), none is clearly worse, 32 move by a pixel or two along a connecting stroke, and 2 are unclear.</p>
<div class="pairs">{still}</div>

<h2>The judge (blind, paired)</h2>
<p>This is experiment 18's calibrated judge, run on 18's 230 sample words. Unchanged boxes keep their earlier verdicts, and only the {A['moved']} boxes that moved were asked again. Today's highlight is a full-height column over a letter's stretch of the baseline. Giving a head to the next letter moves that column by only a few pixels, so <b>the judge barely sees the change</b>.</p>
<div class="bars">{bar("all letters · today", A['before']['letter'], A['before']['letter_ci'], "b")}{bar("all letters · after", A['after']['letter'], A['after']['letter_ci'], "a")}
{bar("112 stacked · today", 100 * st['before'] / st['n'], st['before_ci'], "b")}{bar("112 stacked · after", 100 * st['after'] / st['n'], st['after_ci'], "a")}
{bar("words · today", A['before']['word'], A['before']['word_ci'], "b")}{bar("words · after", A['after']['word'], A['after']['word_ci'], "a")}</div>
<p>Letters: paired difference {A['diff_ci'][0]} to {A['diff_ci'][1]} points ({A['better']} better, {A['worse']} worse among the moved boxes). For comparison, when the same unchanged boxes were simply asked again, {S['control']['right_then_wrong']} went from right to wrong and {S['control']['wrong_then_right']} the other way, out of {S['control']['n']}. Stacked letters: {st['before']} → {st['after']} of 112 (paired {st['diff_ci'][0]} to {st['diff_ci'][1]}).</p>
<div class="tw"><table><tr><th>sample</th><th>words</th><th>letters today</th><th>after</th><th>paired diff</th><th>words right</th></tr>{sm}</table></div>

<h2>Option: each stacked letter highlighted over its own ink (experiment 23, again)</h2>
<p>In experiment 23, a highlight only as tall as the letter's own ink made the judge worse, because it exposed the wrong ink. The same 112 letters were judged again under 23's wording, now with the new ink.</p>
<div class="bars">{bar("full height · today's cuts", H['today_full']['rate'], H['today_full']['ci'], "b")}{bar("own height · today's cuts (23)", H['today_own']['rate'], H['today_own']['ci'], "b")}{bar("full height · new cuts", H['full']['rate'], H['full']['ci'], "a")}{bar("own height · new cuts", H['own']['rate'], H['own']['ci'], "a")}</div>
<p>The new ink makes own-height highlights clearly better than they were: 40 → 53 of 112, paired +2.8 to +20.4 points. The final <span dir="rtl">و</span> goes from 0 to 11 of 12. It is still <b>not better than a full-height column</b> (53 vs 54). A joined <span dir="rtl">ل</span> then gets a sliver over its stem (5 or 6 of 16), and 23 found that the per-letter fonts break lines in two books. Not recommended yet.</p>

<h2>Nothing that worked broke (to within 1–2 words of coverage)</h2>
<p>Each book was built twice in this process with <code>inkscript native … --vector --verify</code>: once with today's src, once with the patch.</p>
<div class="tw"><table><tr><th>doc</th><th>words intact today</th><th>after</th><th>lines today</th><th>after</th><th>letter coverage today</th><th>after</th><th>copied text</th></tr>{ck_rows}</table></div>

<h2>Tried and dropped</h2>
<ul><li><b>"A lam keeps its foot"</b>: a joined <span dir="rtl">ل</span> is penalised when its cut sits right at the root of its stem. The judge stayed flat (71.0%, B sample −2.4), own-height <span dir="rtl">ل</span> went 6 → 5 of 16, so it was dropped. Where a lam's foot ends is unclear in these faces.</li>
<li><b>The trained reader (experiment 16) as a third witness</b>: not used. Its boundary head was trained on this same cutter's cuts in 93 books, so on <span dir="rtl">و</span> it would repeat today's mistake.</li>
<li><b>Following direction and curvature at every join</b>: the only systematic error found was a head hanging from one point, where the pen arrives and leaves at the same spot. There, direction says nothing, and what decides is which letter has a head.</li></ul>

<h2>What it means</h2>
<div class="note"><p>Apply <code>experiments/25_join_ink/penpath.patch</code> (when no set run is going). It gives letters their own ink at stacked joins on 76 of 95 hand-counted stacked letters, against 52 today. It restores the heads of the final <span dir="rtl">و</span> and <span dir="rtl">ق</span> and the medial <span dir="rtl">ل</span>/<span dir="rtl">ط</span> in the fonts of three books (10 forms better, 1 worse). It is neutral on the full-height judge. Words intact and lines in order are identical; letter coverage is 1–2 words lower in two books. It is also the step experiment 23 named as needed before per-letter heights are worth anything, and they now come within a point of full height.</p></div>
<p style="color:var(--mut);font-size:.85rem;margin-top:2em">Gemini spend for this experiment: ${spend:.2f} (cap $10). Code and data: <code>experiments/25_join_ink/</code>.</p>
</main></body></html>"""
(OUT / "report.html").write_text(html); print("report", len(html) // 1024, "KB")
