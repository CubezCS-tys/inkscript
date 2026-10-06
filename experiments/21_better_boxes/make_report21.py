"""out/report.html: the owner's page — the same real words with the cutter's letter boxes before and after the
change, laid on the scan; the before/after numbers as bars. Self-contained, light/dark, phone width.

    ../../.venv/bin/python make_report21.py
"""
import json, base64, html
from pathlib import Path
import cv2
import judge21 as Q
J, R = Q.J, Q.R
OUT = Q.OUT
LAB = {"cutter": "before", "cutter_new": "after", "equal": "equal slices"}


def word_strip(w, side=0.45, target_h=74):
    gray = J.J17.page_image(J.scan_of(w["doc"]), w["page"])
    x0, y0, x1, y1 = w["box"]; h = max(20, y1 - y0); H, W = gray.shape
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h)); cy0, cy1 = max(0, int(y0 - 0.2 * h)), min(H, int(y1 + 0.2 * h))
    g = gray[cy0:cy1, cx0:cx1]; s = target_h / g.shape[0]
    g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    ok, b = cv2.imencode(".png", g, [cv2.IMWRITE_PNG_COMPRESSION, 9])
    return "data:image/png;base64," + base64.b64encode(b.tobytes()).decode(), cx0, cx1 - cx0, g.shape[1], g.shape[0]


def strip_html(w, m, oks, img, focus=None):
    src, cx0, cw, pw, ph = img; bands, labels = [], []
    for k, cell in enumerate(w[m]):
        a, b = (cell[0] - cx0) / cw * 100, (cell[1] - cx0) / cw * 100
        ok = oks[k]; cls = "ok" if ok else "bad" if ok is not None else "na"; alt = " alt" if k % 2 else ""; f = " focus" if focus is not None and k in focus else ""
        bands.append(f'<div class="band {cls}{alt}{f}" style="left:{a:.2f}%;width:{max(0.4, b - a):.2f}%"></div>')
        labels.append(f'<span class="lab {cls}" style="left:{(a + b) / 2:.2f}%">{html.escape(w["text"][k])}</span>')
    return (f'<div class="strip"><div class="mname">{LAB[m]}</div><div class="pic" style="aspect-ratio:{pw}/{ph};max-width:{int(pw * 1.4)}px">'
            f'<img src="{src}" alt="">{"".join(bands)}</div><div class="labs">{"".join(labels)}</div></div>')


def bar(label, v, ci, cls):
    return (f'<div class="brow"><div class="blab">{label}</div><div class="btrack"><div class="bfill {cls}" style="width:{v}%"></div>'
            f'<div class="ci" style="left:{ci[0]}%;width:{max(0.4, ci[1] - ci[0])}%"></div></div><div class="bval">{v:.0f}%<small> {ci[0]:.0f}–{ci[1]:.0f}</small></div></div>')


def main():
    M = json.load(open(OUT / "summary21.json")); S = Q.sample_with_new(); checks = json.load(open(OUT / "checks.json"))
    okmap = {(r["s"], r["w"], r["m"], r["k"]): r["ok"] for r in M["rows"]}
    oks = lambda s, w, m: [okmap.get((s, R.wid(w), m, k)) for k in range(1, len(w["text"]) + 1)]
    spend = J.spent()
    TITLE = {"A": "A · unseen pages, 130 words", "B": "B · unseen pages, 50 words the feeler misread", "C": "C · the fixture 0582, 50 words"}
    heads = []
    for s in ("A", "B", "C"):
        res = M["samples"][s]
        if not res.get("words"): continue
        p = res["paired"]["after_vs_before"]; d = res["after_minus_before_letters_ci"]
        heads.append(f'''<div class="panel"><h3>{TITLE[s]} <small>{res["words"]} words, {res["before"]["letters"]} letters; boxes moved by the change: {M["changed"][s]["boxes_moved"]} in {M["changed"][s]["words_with_a_moved_box"]} words</small></h3>
<div class="sub">letters whose highlight is on the right letter</div>
{bar("before", res["before"]["letter"], res["before"]["letter_ci"], "before")}{bar("after", res["after"]["letter"], res["after"]["letter_ci"], "after")}{bar("equal slices (free)", res["equal"]["letter"], res["equal"]["letter_ci"], "equal")}
<div class="sub">words with every letter right</div>
{bar("before", res["before"]["word"], res["before"]["word_ci"], "before")}{bar("after", res["after"]["word"], res["after"]["word_ci"], "after")}{bar("equal slices (free)", res["equal"]["word"], res["equal"]["word_ci"], "equal")}
<p class="note">Same words, paired: letters right only after the change {p["letters_only_first"]}, only before {p["letters_only_second"]}; words {p["words_only_first"]} vs {p["words_only_second"]}. The gain in letters, 95% interval: {d[0]:+.1f} to {d[1]:+.1f} points.
By book, letters right before → after (equal slices): {"; ".join(f'{k} {v["before"]:.0f} → {v["after"]:.0f}% ({v["equal"]:.0f}%), {v["words"]} words' for k, v in res["by_doc"].items())}.</p></div>''')
    al = M["alef"]
    # examples: every word whose boxes moved, alef words first
    ex = []
    for s in ("C", "A", "B"):
        for w in S[s]:
            if w.get("cutter_new") is None or R.wid(w) not in M["samples"][s].get("word_ids", []): continue
            moved = [k for k, (a, b) in enumerate(zip(w["cutter"], w["cutter_new"])) if abs(a[0] - b[0]) > 0.5 or abs(a[1] - b[1]) > 0.5]
            if not moved: continue
            alef = any(w["text"][k] in "اأ" and k > 0 and w["piece_of"][k - 1] == w["piece_of"][k] for k in moved)
            ob, oa = oks(s, w, "cutter"), oks(s, w, "cutter_new")
            ex.append((not alef, s, w, moved, ob, oa))
    ex.sort(key=lambda t: (t[0], t[1] != "C"))
    cards = []
    al_ex = [e for e in ex if not e[0]][:18]; ot = [e for e in ex if e[0]]
    # the other words the change moved (through the document's atlas): the better, the worse and the level, a few each
    pick = [e for e in ot if sum(map(bool, e[5])) > sum(map(bool, e[4]))][:5] + [e for e in ot if sum(map(bool, e[5])) < sum(map(bool, e[4]))][:4] + [e for e in ot if sum(map(bool, e[5])) == sum(map(bool, e[4]))][:3]
    for nal, s, w, moved, ob, oa in al_ex + pick:
        img = word_strip(w); nb, na = sum(bool(x) for x in ob), sum(bool(x) for x in oa)
        tag = "joined alef" if not nal else "moved through the atlas"
        cards.append(f'<div class="card"><div class="wtitle">{html.escape(w["text"])} <small class="wmeta">{w["doc"]} p{w["page"]} · {tag} · right {nb}→{na} of {len(w["text"])}</small></div>'
                     f'{strip_html(w, "cutter", ob, img, moved)}{strip_html(w, "cutter_new", oa, img, moved)}</div>')
    c = M["control"]
    fx = checks
    page = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Better letter boxes</title>
<style>
:root{{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e2ded6;--before:#9fb6dd;--after:#2f6fd6;--eq:#a3a3aa;--ok:#2f6fd6;--bad:#d93a2b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16171a;--card:#202226;--ink:#ececef;--mute:#9a9aa3;--line:#33353b;--before:#4a5f86;--after:#6ea0ff;--eq:#76767e;--ok:#6ea0ff;--bad:#ff6b5c}}}}
:root[data-theme="dark"]{{--bg:#16171a;--card:#202226;--ink:#ececef;--mute:#9a9aa3;--line:#33353b;--before:#4a5f86;--after:#6ea0ff;--eq:#76767e;--ok:#6ea0ff;--bad:#ff6b5c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:1.7rem;margin:.2em 0}}h2{{margin-top:2em;font-size:1.25rem}}h3{{font-size:1.05rem;margin:.2em 0 .6em}}
small,.wmeta,.note,.sub{{color:var(--mute);font-weight:400}}.sub{{font-size:.85rem;margin-top:.6em}}p.lede{{color:var(--mute);max-width:46em}}.note{{font-size:.9rem}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}
.brow{{display:grid;grid-template-columns:minmax(96px,150px) 1fr 100px;gap:10px;align-items:center;margin:6px 0}}
@media (max-width:600px){{.brow{{grid-template-columns:1fr 92px;gap:2px 10px}}.blab{{grid-column:1/-1;font-size:.85rem}}}}
.btrack{{position:relative;height:20px;background:var(--line);border-radius:6px}}.bfill{{height:100%;border-radius:6px}}
.bfill.before{{background:var(--before)}}.bfill.after{{background:var(--after)}}.bfill.equal{{background:var(--eq)}}
.ci{{position:absolute;top:-4px;height:28px;border-left:2px solid var(--ink);border-right:2px solid var(--ink);opacity:.5}}
.bval{{font-variant-numeric:tabular-nums;font-weight:600}}.bval small{{font-weight:400}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,300px),1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}}.wtitle{{font-size:1.3rem;font-weight:600}}.wtitle small{{font-size:.75rem}}
.strip{{margin-top:6px}}.mname{{font-size:.78rem;color:var(--mute)}}
.pic{{position:relative;width:100%;background:#fff;border-radius:4px;overflow:hidden}}.pic img{{width:100%;height:100%;display:block}}
.band{{position:absolute;top:0;bottom:0;mix-blend-mode:multiply;background:rgba(47,111,214,.22);border-left:1px solid rgba(47,111,214,.7)}}
.band.alt{{background:rgba(29,154,119,.22);border-left-color:rgba(29,154,119,.7)}}
.band.focus{{background:rgba(47,111,214,.42)}}.band.alt.focus{{background:rgba(29,154,119,.42)}}
.band.bad{{background:repeating-linear-gradient(45deg,rgba(217,58,43,.42) 0 5px,rgba(217,58,43,.16) 5px 10px);border-left:1px solid #d93a2b}}
.labs{{position:relative;height:1.6em;direction:ltr}}.lab{{position:absolute;transform:translateX(-50%);font-size:1rem;font-weight:600;color:var(--ok)}}.lab.bad{{color:var(--bad)}}.lab.na{{color:var(--mute)}}
.legend span{{display:inline-block;margin-right:14px;font-size:.9rem}}.sw{{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:5px}}
.kpis{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:10px}}.kpi{{border:1px solid var(--line);border-radius:10px;padding:10px;background:var(--card)}}.big{{font-size:1.5rem;font-weight:700;font-variant-numeric:tabular-nums}}
</style></head><body><main>
<h1>A final alef now gets its whole stem</h1>
<p class="lede">Experiment 21, 2026-10-06. When a word ends in a joined alef (كان، منها، كتاب) the selection highlight used to be a thin sliver at the
foot of the alef. The cause: the cutter walks along the word's pen path, and it started that walk at the very top of the alef's stem, so the
alef owned only the top of its stem and its box was the stretch from the stem's edge to its middle. Now the walk ends at the stem's foot; the
whole stem hangs from that point like any other tall stroke, and the alef's box covers it. Nothing else in the cutter was changed.</p>
<div class="kpis">
<div class="kpi"><div class="big">{al["before"][0]} → {al["after"][0]}</div>of {al["after"][1]} joined alefs judged right (equal slices: {al["equal"][0]})</div>
<div class="kpi"><div class="big">{M["wrong"]["before"][0]} → {M["wrong"]["after"][0]}</div>wrong boxes of {M["wrong"]["after"][1]} (all samples)</div>
<div class="kpi"><div class="big">{fx["after"]["intact"]}</div>fixture words intact in pdfium (before {fx["before"]["intact"]})</div>
<div class="kpi"><div class="big">{fx["after"]["coverage"]}</div>fixture letter coverage (before {fx["before"]["coverage"]})</div>
</div>
<h2>The numbers</h2>
<p class="lede">Experiment 18's judge, unchanged: Gemini looks at the scan with one letter's highlight tinted, two separate questions, "right" only when both agree
(calibrated strict: never accepted a box a whole letter off, but refuses about one right box in six). Same words, same crops. Boxes the change did not
move keep experiment 18's verdicts; only moved boxes were asked again, shuffled together with {c["n"]} of 18's own boxes asked a second time as a control.</p>
{"".join(heads)}
<h2>The same words, before and after</h2>
<p class="note">First the words ending in a joined alef; then a few words whose boxes moved for another reason — the document's alphabet of letter pictures is learned from its own cut letters, so once alefs are cut right, the letters before them are pictured right too and some other cuts shift (better, worse and level shown).</p>
<p class="legend"><span><i class="sw" style="background:rgba(47,111,214,.45)"></i><i class="sw" style="background:rgba(29,154,119,.45)"></i>a letter's highlight, judged right (colours alternate; darker = a box the change moved)</span><span><i class="sw" style="background:repeating-linear-gradient(45deg,rgba(217,58,43,.6) 0 4px,rgba(217,58,43,.2) 4px 8px)"></i>judged wrong</span> The letter under each box is the one it claims.</p>
<div class="cards">{"".join(cards)}</div>
<div class="panel"><h3>How steady is the judge?</h3><p class="note">Of {c["n"]} boxes asked twice (same picture, temperature 0), {c["same"]} got the same verdict; {c["right_then_wrong"]} flipped right→wrong and {c["wrong_then_right"]} wrong→right.
The judge is noisy box by box but not biased, which is why the intervals above are wide and the paired counts matter more than any single box.</p></div>
<div class="panel"><h3>Nothing that worked broke</h3><p class="note">The fixture built with the change, in this process, exactly as <code>inkscript native --vector --verify</code>:
words intact {fx["after"]["intact"]} (before {fx["before"]["intact"]}), lines in order {fx["after"]["lines"]} (before {fx["before"]["lines"]}), letter coverage {fx["after"]["coverage"]} (before {fx["before"]["coverage"]}).
The unseen books: {html.escape(fx.get("unseen", ""))}.</p></div>
<p class="note">Judge spend for this experiment: ${spend:.2f} (cap $10). The proposed change to <code>src/inkscript/geometry/penpath.py</code> is <code>experiments/21_better_boxes/penpath.patch</code>.</p>
</main></body></html>'''
    (OUT / "report.html").write_text(page, encoding="utf-8"); print("wrote", OUT / "report.html", f"{len(page) / 1e6:.2f} MB", len(cards), "cards")


if __name__ == "__main__":
    main()
