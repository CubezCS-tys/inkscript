"""out/score_yolo.json + the training curve -> out/layout_model.html and out/model/<pid>_vs.jpg
(left: the fine-tuned model, right: the Pro referee; thick red outline: they disagree)."""
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
D = json.load(open(OUT / "score_yolo.json")); S, rows = D["scores"], D["rows"]
R = [x for x in rows if x["ref"] not in (None, "other")]


def panel(gray, rs, key):
    img = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR); over = img.copy()
    for x in rs:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); cv2.rectangle(over, (x0 - 4, y0), (x1 + 4, y1), COL.get(x[key], (0, 0, 0)), -1)
    img = cv2.addWeighted(over, 0.35, img, 0.65, 0)
    for x in rs:
        x0, y0, x1, y1 = (int(round(v)) for v in x["box"]); bad = x["ref"] not in (None, "other") and x["model"] != x["ref"]
        cv2.rectangle(img, (x0 - 4, y0), (x1 + 4, y1), (0, 0, 255) if bad else COL.get(x[key], (0, 0, 0)), 5 if bad else 2)
    return img


by = defaultdict(list)
for x in rows: by[x["pid"]].append(x)
acc = {p: (sum(x["model"] == x["ref"] for x in v if x["ref"] not in (None, "other")), sum(x["ref"] not in (None, "other") for x in v), v[0]["group"]) for p, v in by.items()}
show = []
for g in ["plain text", "columns", "decorative", "tables", "equations"]:
    ps = sorted((p for p, a in acc.items() if a[2] == g and a[1] >= 15), key=lambda p: -acc[p][0] / acc[p][1])
    if ps: show.append((ps[len(ps) // 2], g, "a typical page"))
worst = min((p for p in acc if acc[p][1] >= 15), key=lambda p: acc[p][0] / acc[p][1]); show.append((worst, acc[worst][2], "its worst page"))
for pid, _, _ in show:
    g = page_image(pid); a, b = panel(g, by[pid], "model"), panel(g, by[pid], "ref"); bar = np.full((g.shape[0], 30, 3), 160, np.uint8)
    im = np.hstack([a, bar, b]); s = 1300 / im.shape[0]
    cv2.imwrite(str(OUT / "model" / f"{pid}_vs.jpg"), cv2.resize(im, (int(im.shape[1] * s), 1300), interpolation=cv2.INTER_AREA), [cv2.IMWRITE_JPEG_QUALITY, 82])

# lines whose label dots.mocr can say at all (it has no verse or references): the fair head-to-head
F = [x for x in R if x["ref"] not in ("verse", "references")]
cm = lambda x: x['dots'] if x['dots'] in ('table', 'equation') else x['model']
comb = sum(cm(x) == x['ref'] for x in R) / len(R)
fair = {m: sum(x[m] == x["ref"] for x in F) / len(F) for m in ("rules", "dots", "model")}

cur = [{k.strip(): v.strip() for k, v in r.items()} for r in csv.DictReader(open(OUT / "gpu/out/run/results.csv"))]
ep = [int(r["epoch"]) for r in cur]
key = next(k for k in cur[0] if "mAP50(B)" in k); m50 = [float(r[key]) for r in cur]
W_, H_ = 640, 220; xs = lambda e: 40 + (e - 1) / max(ep) * (W_ - 60); ys = lambda v: H_ - 30 - v * (H_ - 50)
pts = " ".join(f"{xs(e):.1f},{ys(v):.1f}" for e, v in zip(ep, m50)); best = max(range(len(m50)), key=lambda i: m50[i])
svg = (f"<svg viewBox='0 0 {W_} {H_}' width='100%' style='max-width:{W_}px'><g stroke='var(--line)'>" +
       "".join(f"<line x1=40 x2={W_-20} y1={ys(v):.0f} y2={ys(v):.0f} /><text x=6 y={ys(v)+4:.0f} fill='var(--mut)' stroke=none font-size=11>{v:.1f}</text>" for v in (0, .2, .4, .6, .8)) +
       f"</g><polyline fill=none stroke='var(--bar)' stroke-width=2.5 points='{pts}'/><circle cx={xs(ep[best]):.1f} cy={ys(m50[best]):.1f} r=5 fill='var(--acc)'/>"
       f"<text x={xs(ep[best])+8:.0f} y={ys(m50[best])-8:.0f} fill='var(--acc)' font-size=12>kept: epoch {ep[best]}</text>"
       f"<text x={W_/2:.0f} y={H_-6} fill='var(--mut)' font-size=11 text-anchor=middle>epoch (stopped at {max(ep)}: no gain for 20)</text></svg>")


def bar(v, c="var(--bar)"): return f"<div class=bar><span style='width:{100*v:.0f}%;background:{c}'></span></div>"


def row3(name, d):
    return (f"<tr><td>{html.escape(name)}</td><td>{d['n']}</td>" + "".join(f"<td>{bar(d[m], c)}<small>{100*d[m]:.0f}%</small></td>"
            for m, c in (("rules", "#999"), ("dots", "#5b7fb5"), ("model", "var(--bar)"))) + "</tr>")


groups = "".join(row3(g, S[g]) for g in ["plain text", "columns", "decorative", "tables", "equations"])
labels = "".join(row3(l, S["label " + l]) for l in ["body", "heading", "list", "verse", "footnote", "references", "furniture", "caption", "table", "equation"] if "label " + l in S)
legend = " ".join(f"<span class=chip style='background:{HEX[k]}'>{k}</span>" for k in ["body", "heading", "footnote", "references", "list", "verse", "furniture", "table", "equation", "caption", "other", "none"])
cards = "".join(f"<section><h3>{html.escape(g)} <span class=v>{html.escape(w)}</span></h3><p>{acc[p][0]} of {acc[p][1]} lines agree ({100*acc[p][0]/acc[p][1]:.0f}%). <code>{p}</code></p>"
                f"<figure><img loading=lazy src='model/{p}_vs.jpg'><figcaption>left: the model · right: the referee · thick red outline: they disagree</figcaption></figure></section>" for p, g, w in show)
a = S["all"]
(OUT / "layout_model.html").write_text(f"""<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1">
<title>Layout model, trained</title><style>
:root{{--bg:#fbfaf7;--fg:#1d1c1a;--mut:#6b675f;--card:#fff;--line:#e3dfd6;--acc:#9a4a12;--bar:#3a7d44}}
@media (prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a}}}}
:root[data-theme=dark]{{--bg:#161514;--fg:#ece8e1;--mut:#a29d93;--card:#211f1d;--line:#36332f;--acc:#e59a5c;--bar:#6fbf7a}}
body{{background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,sans-serif;margin:0;padding:24px 16px}} main{{max-width:1200px;margin:auto}}
h1{{font-size:1.8rem;margin:0 0 .3em}} h2{{font-size:1.25rem;margin:1.8em 0 .4em}} h3{{font-size:1.05rem;margin:1.8em 0 .2em}} p,li{{max-width:840px}} .lede{{font-size:1.1rem}}
.tw{{overflow-x:auto}} table{{border-collapse:collapse}} td,th{{padding:5px 10px;border-bottom:1px solid var(--line);text-align:left;white-space:nowrap}} .bar{{width:150px;max-width:22vw;height:10px;background:var(--line);border-radius:6px;display:inline-block;margin-right:6px}} .bar span{{display:block;height:100%;border-radius:6px}}
.big{{display:flex;gap:14px;flex-wrap:wrap;margin:1em 0}} .big div{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px 16px;min-width:150px}} .big b{{font-size:1.8rem;display:block}}
.v{{font-size:.8rem;color:var(--acc);border:1px solid var(--acc);border-radius:10px;padding:1px 8px;margin-left:6px;font-weight:600}}
figure{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:6px}} img{{width:100%;display:block;background:#fff}} figcaption{{font-size:.85rem;color:var(--mut);padding-top:4px}}
.chip{{color:#fff;font-size:.8rem;padding:1px 7px;border-radius:8px;display:inline-block;margin:2px}} .note{{background:var(--card);border-left:4px solid var(--acc);padding:10px 14px;max-width:840px;border-radius:4px}}
</style></head><body><main><h1>Layout model, trained</h1>
<p class=lede>A small layout model (DocLayout-YOLO), fine-tuned on 2,508 of our own pages, each labelled line by line by Gemini Flash. It was tested on the 44 pilot pages it never saw, against Gemini Pro as the referee. It now names <b>{100*a['model']:.0f}%</b> of lines the way the referee does. dots.mocr gets {100*a['dots']:.0f}% and our hand rules {100*a['rules']:.0f}%. It runs on a laptop CPU at about 1.5 seconds a page, with no Gemini.</p>
<div class=big><div>model<b>{100*a['model']:.1f}%</b></div><div>dots.mocr<b>{100*a['dots']:.1f}%</b></div><div>rules<b>{100*a['rules']:.1f}%</b></div><div>model + dots<b>{100*comb:.1f}%</b><small>dots for tables, equations</small></div><div>cost<b>$1.70</b><small>GPU, 2 h</small></div></div>
<p class=note><b>Fair to dots.</b> dots.mocr has no label for verse or reference lists, so it can never get those right. On the lines whose label both models can give, the model scores <b>{100*fair['model']:.1f}%</b> and dots <b>{100*fair['dots']:.1f}%</b>. So on the labels they share, <b>dots is still better</b>, mostly because of tables and equations. The model's overall lead comes from what dots can't say: verse, reference lists, and lists.</p>
<p class=note><b>Two experts together.</b> Take the model's label, but where dots.mocr says "table" or "equation", take dots instead. That gives <b>{100*comb:.1f}%</b> of all lines, better than either alone. This is the connect-the-specialists picture in miniature: dots knows where tables and equations are, the model knows what kind of text a line is.</p>
<h2>By kind of page</h2><div class=tw><table><tr><th>pages</th><th>lines</th><th>rules</th><th>dots.mocr</th><th>model</th></tr>{groups}</table></div>
<h2>By label</h2><p>Share of the referee's lines of each kind that were named the same.</p><div class=tw><table><tr><th>label</th><th>lines</th><th>rules</th><th>dots.mocr</th><th>model</th></tr>{labels}</table></div>
<h2>Where it is still wrong</h2><ol>
<li><b>Equations: 0 of 49.</b> Only 77 equation lines were in training, so it never learned them. It calls them "other" or "verse". dots.mocr gets 94%. Since equations are a hand-off to the equations specialist anyway, the cheap fix is more equation pages in training, or letting dots flag them.</li>
<li><b>Numbered lists read as body:</b> 46 lines. It finds about half the list lines, but when it does say "list" it is right 84% of the time.</li>
<li><b>Reference lists read as footnotes:</b> 20 lines. They look alike: small type, numbered, at the end.</li>
<li><b>Table rows called footnotes or missed:</b> 33 lines, mostly at the edges of tables.</li>
<li><b>Headings: 64%.</b> This is the weakest common label, as I guessed last night. Headings vary most from book to book, so this is where the whole-document sense (the style sheet) should help.</li></ol>
<h2>How the training went</h2><p>Validation score (mAP50) on 185 pages from 22 held-out books. It rose fast, then levelled off; training stopped itself at epoch 52 and kept epoch {ep[best]}.</p>{svg}
<h2>Pages, side by side</h2><p>{legend}</p>{cards}
<p class=note><b>What it means.</b> One small model, trained on about $12 of Gemini labels, replaces Gemini for this job. It beats the bigger general model overall, and together with it reaches {100*comb:.0f}%. It names lines and hands off; it doesn't read tables or equations. Two notes on honesty. The referee is a model, not a person. And the test pages are the hard pilot set: plain books should score higher (95% on the plain-text pages here). The library's own final step crashed on the GPU (a bug in fusing its layers), so predictions were run here on the CPU from the saved weights, unfused. Scripts: <code>train_pages.py</code>, <code>make_yolo.py</code>, <code>gpu/</code>, <code>predict_local.py</code>, <code>score_yolo.py</code>, <code>report_yolo.py</code>.</p>
</main></body></html>""")
print(fair, show)
