"""out/score_yolo.json (round 1) + out/score_yolo2.json (round 2) + out/round2/summary.json (counts and costs from the run's
logs, and the verdict) + both training curves + the training labels -> out/layout_model.html and
out/model/<pid>_r2.jpg (the six pages below, every equation page and the four pages round 2 lost most on) (left: round 1, middle: round 2, right: the Pro referee; thick red outline: that model and the
referee disagree). The six pages are chosen from round 1's scores, as in the round-1 report, so they stay the same."""
import json, csv, html, sys
from collections import defaultdict
from pathlib import Path
import cv2, numpy as np
HERE = Path(__file__).parent; OUT = HERE / "out"; (OUT / "model").mkdir(exist_ok=True)
sys.path.insert(0, str(HERE.parent / "38_parser")); from common import page_image
COL = {"body": (150, 150, 150), "heading": (30, 30, 220), "footnote": (200, 110, 20), "list": (170, 40, 170), "verse": (20, 150, 200),
       "furniture": (90, 90, 90), "caption": (40, 140, 40), "table": (0, 120, 160), "equation": (120, 60, 0), "references": (60, 160, 120),
       "other": (60, 60, 60), "none": (0, 0, 0)}
HEX = {k: "#%02x%02x%02x" % v[::-1] for k, v in COL.items()}
D1, D2 = json.load(open(OUT / "score_yolo.json")), json.load(open(OUT / "score_yolo2.json"))
S1, S2 = D1["scores"], D2["scores"]
assert len(D1["rows"]) == len(D2["rows"])
rows = []
for a, b in zip(D1["rows"], D2["rows"]):
    assert a["pid"] == b["pid"] and a["box"] == b["box"]
    rows.append(dict(a, r1=a["model"], r2=b["model"]))
R = [x for x in rows if x["ref"] not in (None, "other")]
pct = lambda v: f"{100 * v:.0f}%"


def panel(gray, rs, key):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR); over = img.copy()
    for x in rs:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); cv2.rectangle(over, (x0 - 4, y0), (x1 + 4, y1), COL.get(x[key], (0, 0, 0)), -1)
    img = cv2.addWeighted(over, 0.35, img, 0.65, 0)
    for x in rs:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); bad = key != "ref" and x["ref"] not in (None, "other") and x[key] != x["ref"]
        cv2.rectangle(img, (x0 - 4, y0), (x1 + 4, y1), (0, 0, 255) if bad else COL.get(x[key], (0, 0, 0)), 5 if bad else 2)
    return img


by = defaultdict(list)
for x in rows: by[x["pid"]].append(x)
acc = {p: {k: sum(x[k] == x["ref"] for x in v if x["ref"] not in (None, "other")) for k in ("r1", "r2")} | dict(n=sum(x["ref"] not in (None, "other") for x in v), g=v[0]["group"])
       for p, v in by.items()}
show = []
for g in ["plain text", "columns", "decorative", "tables", "equations"]:
    ps = sorted((p for p, a in acc.items() if a["g"] == g and a["n"] >= 15), key=lambda p: -acc[p]["r1"] / acc[p]["n"])
    if ps: show.append((ps[len(ps) // 2], g, "a typical page"))
worst = min((p for p in acc if acc[p]["n"] >= 15), key=lambda p: acc[p]["r1"] / acc[p]["n"]); show.append((worst, acc[worst]["g"], "round 1's worst page"))
EQP = sorted((p for p, a in acc.items() if a["g"] == "equations"), key=lambda p: acc[p]["r1"] - acc[p]["r2"])   # all equation pages, most improved first
LOST = sorted(acc, key=lambda p: acc[p]["r2"] - acc[p]["r1"])[:4]                                   # the four pages round 2 lost most lines on
for pid in {p for p, _, _ in show} | set(EQP) | set(LOST):
    g = page_image(pid); bar = np.full((g.shape[0], 30, 3), 160, np.uint8)
    im = np.hstack([panel(g, by[pid], "r1"), bar, panel(g, by[pid], "r2"), bar, panel(g, by[pid], "ref")]); s = 1300 / im.shape[0]
    cv2.imwrite(str(OUT / "model" / f"{pid}_r2.jpg"), cv2.resize(im, (int(im.shape[1] * s), 1300), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])

# the training mix: lines of each label in round 1's training pages and in round 2's
NAMES = ["furniture", "heading", "body", "list", "verse", "footnote", "references", "caption", "table", "equation", "other"]
MIX = {}
for y in ("yolo", "yolo2"):
    c = defaultdict(int)
    for f in (OUT / "train" / y / "labels/train").glob("*.txt"):
        for l in f.read_text().splitlines():
            if l.strip(): c[NAMES[int(l.split()[0])]] += 1
    MIX[y] = c
mmax = max(max(c.values()) for c in MIX.values())
mix = "".join(f"<tr><td>{k}</td>" + "".join(f"<td><div class=bar style='width:220px'><span style='width:{100*MIX[y][k]/mmax:.1f}%;background:{HEX[k] if k != 'body' else '#888'}'></span></div><small>{MIX[y][k]:,}</small></td>" for y in ("yolo", "yolo2")) +
              f"<td>×{MIX['yolo2'][k]/max(1, MIX['yolo'][k]):.1f}</td></tr>" for k in ["body", "table", "list", "references", "furniture", "heading", "footnote", "other", "caption", "verse", "equation"])

# model + dots: the model's label, but dots.mocr's wherever dots says table or equation
comb = {k: sum((x["dots"] if x["dots"] in ("table", "equation") else x[k]) == x["ref"] for x in R) / len(R) for k in ("r1", "r2")}
F = [x for x in R if x["ref"] not in ("verse", "references")]                  # labels dots.mocr can say at all
fair = {m: sum(x[m] == x["ref"] for x in F) / len(F) for m in ("rules", "dots", "r1", "r2")}
EQ = [x for x in R if x["group"] == "equations"]; EQL = [x for x in EQ if x["ref"] == "equation"]
eq = dict(pages=len({x["pid"] for x in EQ}), n=len(EQ), neq=len(EQL), **{f"{k}_all": sum(x[k] == x["ref"] for x in EQ) / len(EQ) for k in ("dots", "r1", "r2")},
          **{f"{k}_eq": sum(x[k] == "equation" for x in EQL) / max(1, len(EQL)) for k in ("dots", "r1", "r2")})


def curve(path):
    cur = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(open(path))]
    key = next(k for k in cur[0] if "mAP50(B)" in k)
    return [int(r["epoch"]) for r in cur], [float(r[key]) for r in cur]


C = {"r1": curve(OUT / "gpu/out/run/results.csv"), "r2": curve(OUT / "gpu2/out/run/results.csv")}
W_, H_ = 640, 230; emax = max(max(e) for e, _ in C.values())
xs = lambda e: 40 + (e - 1) / emax * (W_ - 60); ys = lambda v: H_ - 30 - v * (H_ - 50)
svg = (f"<svg viewBox='0 0 {W_} {H_}' width='100%' style='max-width:{W_}px'><g stroke='var(--line)'>" +
       "".join(f"<line x1=40 x2={W_-20} y1={ys(v):.0f} y2={ys(v):.0f} /><text x=6 y={ys(v)+4:.0f} fill='var(--mut)' stroke=none font-size=11>{v:.1f}</text>" for v in (0, .2, .4, .6, .8)) + "</g>")
for k, col, name in (("r1", "#999", "round 1"), ("r2", "var(--bar)", "round 2")):
    ep, m = C[k]; b = max(range(len(m)), key=lambda i: m[i])
    svg += (f"<polyline fill=none stroke='{col}' stroke-width=2.5 points='{' '.join(f'{xs(e):.1f},{ys(v):.1f}' for e, v in zip(ep, m))}'/>"
            f"<circle cx={xs(ep[b]):.1f} cy={ys(m[b]):.1f} r=5 fill='{col}'/><text x={xs(ep[b])+8:.0f} y={ys(m[b])+(-8 if k == 'r2' else 16):.0f} fill='{col}' font-size=12>{name}: kept epoch {ep[b]} of {max(ep)}</text>")
svg += f"<text x={W_/2:.0f} y={H_-6} fill='var(--mut)' font-size=11 text-anchor=middle>epoch</text></svg>"
best = {k: (C[k][0][max(range(len(C[k][1])), key=lambda i: C[k][1][i])], max(C[k][1]), max(C[k][0])) for k in C}


def bar(v, c="var(--bar)"): return f"<div class=bar><span style='width:{100*v:.0f}%;background:{c}'></span></div>"


def row4(name, d1, d2):
    cells = [(d1["rules"], "#999"), (d1["dots"], "#5b7fb5"), (d1["model"], "#c2b59b"), (d2["model"], "var(--bar)")]
    dlt = 100 * (d2["model"] - d1["model"])
    return (f"<tr><td>{html.escape(name)}</td><td>{d1['n']}</td>" + "".join(f"<td>{bar(v, c)}<small>{100*v:.0f}%</small></td>" for v, c in cells) +
            f"<td class={'up' if dlt > 0.5 else 'down' if dlt < -0.5 else ''}>{dlt:+.0f}</td></tr>")


HEAD = "<tr><th>{}</th><th>lines</th><th>rules</th><th>dots.mocr</th><th>round 1</th><th>round 2</th><th>change</th></tr>"
groups = "".join(row4(g, S1[g], S2[g]) for g in ["plain text", "columns", "decorative", "tables", "equations"])
labels = "".join(row4(l, S1["label " + l], S2["label " + l]) for l in ["body", "heading", "list", "verse", "footnote", "references", "furniture", "caption", "table", "equation"] if "label " + l in S1)
legend = " ".join(f"<span class=chip style='background:{HEX[k]}'>{k}</span>" for k in ["body", "heading", "footnote", "references", "list", "verse", "furniture", "table", "equation", "caption", "other", "none"])
card = lambda p, g, w: (f"<section><h3>{html.escape(g)} <span class=v>{html.escape(w)}</span></h3><p>Round 1: {acc[p]['r1']} of {acc[p]['n']} lines agree ({100*acc[p]['r1']/acc[p]['n']:.0f}%). "
                         f"Round 2: {acc[p]['r2']} ({100*acc[p]['r2']/acc[p]['n']:.0f}%). <code>{p}</code></p>"
                         f"<figure><img loading=lazy src='model/{p}_r2.jpg'><figcaption>left: round 1 · middle: round 2 · right: the referee · thick red outline: that model and the referee disagree</figcaption></figure></section>")
eqcards = "".join(card(p, "equations", f"{acc[p]['r2'] - acc[p]['r1']:+d} lines") for p in EQP)
lostcards = "".join(card(p, acc[p]["g"], f"{acc[p]['r2'] - acc[p]['r1']:+d} lines") for p in LOST)
cards = "".join(f"<section><h3>{html.escape(g)} <span class=v>{html.escape(w)}</span></h3><p>Round 1: {acc[p]['r1']} of {acc[p]['n']} lines agree ({100*acc[p]['r1']/acc[p]['n']:.0f}%). "
                f"Round 2: {acc[p]['r2']} ({100*acc[p]['r2']/acc[p]['n']:.0f}%). <code>{p}</code></p>"
                f"<figure><img loading=lazy src='model/{p}_r2.jpg'><figcaption>left: round 1 · middle: round 2 · right: the referee · thick red outline: that model and the referee disagree</figcaption></figure></section>" for p, g, w in show)
a1, a2 = S1["all"], S2["all"]
INFO = json.load(open(OUT / "round2/summary.json"))                              # filled by hand from the run's logs
L2 = lambda l, k="model": S2["label " + l][k]; L1 = lambda l, k="model": S1["label " + l][k]
(OUT / "layout_model.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Layout model, trained</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12;--bar:#3a7d44;--up:#2f7d3a;--down:#b3261e}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a;--up:#7fd08a;--down:#f08a80}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a;--up:#7fd08a;--down:#f08a80}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}} main{{max-width:1200px;margin:auto}}
h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.25rem;margin:1.8em 0 .4em}} h3{{font-size:1.05rem;margin:1.8em 0 .2em}} p,li{{max-width:840px}} .lede{{font-size:1.1rem}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse}} td,th{{padding:5px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}} .bar{{width:110px;max-width:16vw;height:10px;background:var(--line);border-radius:6px;display:inline-block;margin-right:6px}} .bar span{{display:block;height:100%;border-radius:6px}}
td.up{{color:var(--up);font-weight:600}} td.down{{color:var(--down);font-weight:600}}
.big{{display:flex;gap:14px;flex-wrap:wrap;margin:1em 0}} .big div{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;min-width:150px}} .big b{{font-size:1.8rem;display:block}} .big s{{color:var(--mut);font-size:1rem}}
.v{{font-size:.8rem;color:var(--acc);border:1px solid var(--acc);border-radius:10px;padding:1px 8px;margin-left:6px;font-weight:600}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}} img{{width:100%;display:block;background:#fff}} figcaption{{font-size:.85rem;color:var(--mut);padding-top:4px}}
.chip{{color:#fff;font-size:.8rem;padding:1px 7px;border-radius:8px;display:inline-block;margin:2px}} .note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:840px;border-radius:4px}}
</style></head><body><main><h1>Layout model, trained</h1>
<p class=lede>A small layout model (DocLayout-YOLO) names each line of a scanned page: body, heading, list, verse, footnote, and so on. Round 1 was fine-tuned on 2,508 of our pages, each labelled line by line by Gemini Flash. Round 2 added {INFO['r2_pages']:,} more pages: every page with equations from {INFO['new_docs']} new documents, plus the pages round 1 was least sure of. Both rounds were tested on the same 44 pilot pages, which neither saw, against Gemini Pro as the referee. Round 1 named <b>{100*a1['model']:.1f}%</b> of lines the way the referee does; round 2 names <b>{100*a2['model']:.1f}%</b>.</p>
<div class=big><div>round 2<b>{100*a2['model']:.1f}%</b><s>round 1 {100*a1['model']:.1f}%</s></div><div>round 2 + dots<b>{100*comb['r2']:.1f}%</b><s>round 1 + dots {100*comb['r1']:.1f}%</s></div><div>dots.mocr<b>{100*a1['dots']:.1f}%</b></div><div>rules<b>{100*a1['rules']:.1f}%</b></div>
<div>equation lines<b>{100*eq['r2_eq']:.0f}%</b><s>round 1 {100*eq['r1_eq']:.0f}% · dots {100*eq['dots_eq']:.0f}%</s></div><div>cost, round 2<b>${INFO['gemini']:.2f} + ${INFO['gpu']:.2f}</b><small>Gemini labels + GPU ({INFO['gpu_h']:.1f} h)</small></div></div>
{INFO['verdict']}
<h2>What round 2 added</h2><ul>
<li><b>Equation pages from new journals.</b> {INFO['new_docs']} new documents from {INFO['new_journals']} journals that have no page in the test set ({html.escape(INFO['journals'])}), so nothing about the test pages leaked in. Every page with at least two lines that look like maths was kept: {INFO['maths_pages']} pages.</li>
<li><b>The pages the model was least sure of.</b> Round 1's model was run on {INFO['cands']:,} candidate pages; the rest of the {INFO['chosen']:,} were those where the most lines had no confident box, or where it said equation, caption or other.</li>
<li><b>Labels:</b> Gemini Flash, as in round 1: {INFO['labelled']:,} pages labelled for ${INFO['gemini']:.2f}. Equation lines in training: <b>{INFO['eq_r1']} → {INFO['eq_r2']}</b>; table lines {INFO['tab_r1']:,} → {INFO['tab_r2']:,}; list lines {INFO['list_r1']:,} → {INFO['list_r2']:,}; heading lines {INFO['head_r1']:,} → {INFO['head_r2']:,}.</li>
<li><b>Training:</b> the same settings as round 1, started from the same public weights (not from round 1), so the two rounds compare cleanly.</li></ul>
<h2>The {eq['pages']} equation pages</h2><p>The test set has {eq['pages']} pages that are mostly equations: {eq['n']} lines, {eq['neq']} of them equations by the referee's reading.</p>
<div class=tw><table><tr><th></th><th>dots.mocr</th><th>round 1</th><th>round 2</th></tr>
<tr><td>all lines on these pages</td><td>{pct(eq['dots_all'])}</td><td>{pct(eq['r1_all'])}</td><td><b>{pct(eq['r2_all'])}</b></td></tr>
<tr><td>equation lines named equation</td><td>{pct(eq['dots_eq'])}</td><td>{pct(eq['r1_eq'])}</td><td><b>{pct(eq['r2_eq'])}</b></td></tr></table></div>
<h2>What the training saw</h2><p>Lines of each kind in the training pages, round 1 (left) and round 2 (right). Round 2 more than tripled the table lines, while footnotes and verse barely grew.</p><div class=tw><table><tr><th></th><th>round 1 ({INFO['train_pages_r1']:,} pages)</th><th>round 2 ({INFO['train_pages_r2']:,} pages)</th><th></th></tr>{mix}</table></div>
<h2>All {eq['pages']} equation pages, round 1 and round 2</h2><p>Look for the equation colour (blue) in the middle panel: round 1 never used it. {legend}</p>{eqcards}
<h2>By kind of page</h2><div class=tw><table>{HEAD.format('pages')}{groups}</table></div>
<h2>By label</h2><p>Share of the referee's lines of each kind that were named the same. Change is in percentage points, round 1 → round 2.</p><div class=tw><table>{HEAD.format('label')}{labels}</table></div>
<p class=note><b>Fair to dots.</b> dots.mocr has no label for verse or reference lists. On the lines whose label both can give: dots {100*fair['dots']:.1f}%, round 1 {100*fair['r1']:.1f}%, round 2 {100*fair['r2']:.1f}%.</p>
<p class=note><b>Two experts together.</b> Take the model's label, but where dots.mocr says "table" or "equation", take dots instead: round 1 + dots {100*comb['r1']:.1f}%, round 2 + dots <b>{100*comb['r2']:.1f}%</b>.</p>
{INFO['wrong']}
<h2>The four pages round 2 lost most on</h2><p>{legend}</p>{lostcards}
<h2>How the training went</h2><p>Validation score (mAP50) on the held-out books. Round 1 was checked on 185 pages from 22 books; round 2 on those same pages plus {INFO['val_added']} pages from its own held-out books, so the two curves are on slightly different pages. Round 1 kept epoch {best['r1'][0]} (stopped at {best['r1'][2]}); round 2 kept epoch {best['r2'][0]} (stopped at {best['r2'][2]}).</p>{svg}
<h2>The same six pages, round 1 and round 2</h2><p>{legend}</p>{cards}
<p class=note><b>Honesty notes.</b> The referee is a model, not a person. The test pages are the hard pilot set: plain books score higher. The test pages are only 44, so a change of one or two points on a single label can be a handful of lines. {INFO['notes']} Scripts: <code>more_pages.py</code>, <code>round2.py</code>, <code>train_pages.py</code>, <code>make_yolo.py</code>, <code>gpu/</code>, <code>predict_local.py</code>, <code>score_yolo.py</code>, <code>report_yolo.py</code>.</p>
</main></body></html>""")
print("fair", fair, "comb", comb, "eq", eq, "show", show, "best", best)
