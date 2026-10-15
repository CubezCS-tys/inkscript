"""Experiment 41: the owner's report, out/report.html (self-contained, no calls).

    /home/yassine/inkscript/.venv/bin/python report.py

Reads out/scores.json (score41.py), out/judged.json (by-eye verdicts), out/sheets/<run>_items.json, the spend log,
the renders (render41.py) and the page images; pictures are composed here, downscaled and embedded as JPEG.
"""
from __future__ import annotations

import base64
import html as H
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from structure import COARSE, OUT, art_of, page_image, page_lines, sample  # noqa: E402
from render41 import COLOURS, block_boxes, boxes_panel, render_panel, sections  # noqa: E402
from sheets import crop  # noqa: E402

S = json.loads((OUT / "scores.json").read_text(encoding="utf-8"))
J = json.loads((OUT / "judged.json").read_text(encoding="utf-8"))
SPEND = [json.loads(l) for l in (OUT / "gemini_spend.jsonl").read_text().splitlines() if l.strip()]
PAGES_PER_DOC = 15.9
SIZE = [0]


def b64img(img, w=1500, q=72):
    if img.shape[1] > w:
        img = cv2.resize(img, (w, int(img.shape[0] * w / img.shape[1])), interpolation=cv2.INTER_AREA)
    data = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q])[1].tobytes()
    SIZE[0] += len(data)
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def strip(img, text, h=40):
    bar = np.full((h, img.shape[1], 3), 255, np.uint8)
    cv2.putText(bar, text, (8, int(h * 0.72)), cv2.FONT_HERSHEY_SIMPLEX, h / 42, (50, 50, 50), 2)
    return np.vstack([bar, img])


def fit_h(img, height):
    s = height / img.shape[0]
    return cv2.resize(img, (max(1, int(img.shape[1] * s)), height), interpolation=cv2.INTER_AREA)


def hstack(panels, gap=12):
    h = max(p.shape[0] for p in panels)
    panels = [np.pad(p, ((0, h - p.shape[0]), (0, 0), (0, 0)), constant_values=255) for p in panels]
    out = panels[0]
    for p in panels[1:]:
        out = np.hstack([out, np.full((h, gap, 3), 255, np.uint8), p])
    return out


def compose(stem, p, which=("scan", "argon:blocks", "flash:blocks", "argon:render", "flash:render"), height=1100,
            crop_y=None):
    a = art_of(stem)
    scan = cv2.imread(str(page_image(a, p)), cv2.IMREAD_COLOR)
    secs = {r: sections(r, stem).get(p, "") for r in ("argon", "flash")}
    panels = []
    for w in which:
        if w == "scan":
            im, lab = scan, "scan"
        elif w.endswith(":blocks"):
            r = w.split(":")[0]
            im, lab = boxes_panel(scan, block_boxes(secs[r])), f"{r}: blocks"
        else:
            r = w.split(":")[0]
            im = render_panel(OUT / r / "render" / f"{stem}_p{p:03d}.png", height)
            lab = f"{r}: rendered"
            if im is None:
                continue
            panels.append(strip(im, lab))
            continue
        if crop_y:
            H_ = im.shape[0]
            im = im[int(crop_y[0] * H_):int(crop_y[1] * H_)]
        panels.append(strip(fit_h(im, height), lab))
    return hstack(panels)


def fig(img, caption, w=1500, q=70):
    return (f'<figure><a href="#" class="zoom"><img loading="lazy" src="{b64img(img, w, q)}" alt=""></a>'
            f'<figcaption>{caption}</figcaption></figure>')


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


# ------------------------------------------------------------------------------------------------ numbers

T = {r: S["per_run"][r]["totals"] for r in S["per_run"]}
P = S["pair"]["argon~flash"]
NZ = S["noise"]


def truth_summary(kind=None):
    rows = [r for r in S["truth_pages"] if (kind is None or r["kind"] == kind) and all(k in r for k in ("azure", "argon", "flash"))]
    out = {"pages": len(rows), "words": sum(r["truth_words"] for r in rows)}
    for name in ("azure", "argon", "flash", "argon/edition", "flash/edition"):
        rr = [r for r in rows if name in r]
        e = sum(r[name]["bag_err"] for r in rr)
        n = sum(r[name]["bag_n"] for r in rr)
        c = sum(r[name]["cer"] for r in rr)
        ch = sum(r[name]["chars"] for r in rr)
        out[name] = dict(bag=e / n if n else None, cer=c / ch if ch else None)
    return out


TS = {k: truth_summary(k) for k in ("gold", "bd", None)}
FV = {r: Counter(x["verdict"] for row in S["truth_pages"] for x in row.get("fix_verdicts", {}).get(r, [])) for r in ("argon", "flash")}
JV = {r: {k: Counter(v for i, v in J[r].items() if f"-{k}-" in i) for k in ("sic", "fix")} for r in ("argon", "flash")}
REFX = {}
for r in ("argon", "flash"):
    d = S["referee"][r]
    n = sum(v["n"] for k, v in d["by_label"].items() if k != "references")
    a = sum(v["agree"] for k, v in d["by_label"].items() if k != "references")
    REFX[r] = a / n if n else None

spend_pilot = sum(r["usd"] for r in SPEND[:14])
spend_main = {k: sum(r["usd"] for r in SPEND[14:] if r["tag"].startswith(k + "_") and not r["tag"].startswith(k + "_r2"))
              for k in ("argon", "flash")}
spend_r2 = sum(r["usd"] for r in SPEND[14:] if "_r2_" in r["tag"])
spend_total = sum(r["usd"] for r in SPEND)
calls = len(SPEND)


def per_page_label_disagreement():
    out = []
    for a in sample():
        la = json.loads((OUT / "argon/labels" / f"{a['stem']}.json").read_text(encoding="utf-8"))
        lb = json.loads((OUT / "flash/labels" / f"{a['stem']}.json").read_text(encoding="utf-8"))
        A = {re.sub(r"[a-p]$", "", r["id"]): r for r in la["lines"]}
        B = {re.sub(r"[a-p]$", "", r["id"]): r for r in lb["lines"]}
        per = defaultdict(lambda: [0, 0, Counter()])
        for i in set(A) & set(B):
            per[A[i]["page"]][1] += 1
            if A[i]["label"] != B[i]["label"]:
                per[A[i]["page"]][0] += 1
                per[A[i]["page"]][2][(A[i]["label"], B[i]["label"])] += 1
        for p, (d, n, c) in per.items():
            out.append(dict(stem=a["stem"], page=p, diff=d, n=n, pairs=c.most_common(2)))
    return sorted(out, key=lambda x: -x["diff"])


DIS = per_page_label_disagreement()

# archive scale
def archive(usd_per_page, mult=1.0):
    pp = usd_per_page * mult
    return dict(mpages=pp * 1e6, mdocs=pp * 1e6 * PAGES_PER_DOC)


UP = {r: T[r]["usd_per_page"] for r in ("argon", "flash")}

# ------------------------------------------------------------------------------------------------ page

CSS = """
:root{--bg:#f8f7f3;--fg:#1c1c1a;--muted:#67665f;--card:#ffffff;--line:#e3e1d9;--accent:#1f5fa8;--good:#2e7d32;--bad:#c62828;
--warn:#b26a00;--argon:#6a3fb5;--flash:#d0761a;--azure:#3a7bd5;--chip:#f0eee7}
@media (prefers-color-scheme:dark){:root:not([data-theme=light]){--bg:#151514;--fg:#ebeae4;--muted:#a5a49c;--card:#1f1f1e;
--line:#363632;--accent:#7fb2ef;--good:#6fcf75;--bad:#ef6b6b;--warn:#f0b041;--argon:#b896f2;--flash:#f2a65a;--azure:#79a9ef;--chip:#2a2a28}}
:root[data-theme=dark]{--bg:#151514;--fg:#ebeae4;--muted:#a5a49c;--card:#1f1f1e;--line:#363632;--accent:#7fb2ef;--good:#6fcf75;
--bad:#ef6b6b;--warn:#f0b041;--argon:#b896f2;--flash:#f2a65a;--azure:#79a9ef;--chip:#2a2a28}
*{box-sizing:border-box} html{-webkit-text-size-adjust:100%}
body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.6 -apple-system,system-ui,'Segoe UI',sans-serif}
main{max-width:1080px;margin:0 auto;padding:16px}
h1{font-size:28px;line-height:1.25;margin:12px 0 4px} h2{font-size:21px;margin:36px 0 8px;border-top:1px solid var(--line);padding-top:20px}
h3{font-size:17px;margin:20px 0 6px} .sub{color:var(--muted)} p{margin:8px 0}
.lede{font-size:18px} .ar{font-family:'Scheherazade New','Noto Naskh Arabic',serif;font-size:1.15em}
.tiles{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px;margin:16px 0}
.tile{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}
.tile .k{font-size:13px;color:var(--muted)} .tile .v{font-size:15px;margin-top:4px}
.bar{display:grid;grid-template-columns:62px 1fr 64px;align-items:center;gap:8px;margin:5px 0;font-size:14px}
.bar .t{height:12px;background:var(--chip);border-radius:6px;overflow:hidden} .bar .t i{display:block;height:100%}
.argon{color:var(--argon)} .flash{color:var(--flash)} .azure{color:var(--azure)}
figure{margin:14px 0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px}
figure img{width:100%;height:auto;display:block;border-radius:6px;background:#fff}
figcaption{font-size:14px;color:var(--muted);padding:6px 4px 2px}
table{border-collapse:collapse;width:100%;font-size:14px;background:var(--card)} .tw{overflow-x:auto;margin:10px 0}
th,td{border-bottom:1px solid var(--line);padding:6px 8px;text-align:start;vertical-align:top} th{color:var(--muted);font-weight:600}
td.n{text-align:end;font-variant-numeric:tabular-nums;white-space:nowrap}
.verdict{background:var(--card);border-inline-start:5px solid var(--accent);border-radius:8px;padding:12px 16px;margin:14px 0}
.chip{display:inline-block;background:var(--chip);border-radius:12px;padding:1px 9px;font-size:13px;margin:2px}
.good{color:var(--good)} .bad{color:var(--bad)} .warn{color:var(--warn)}
.flag{display:grid;grid-template-columns:1fr;gap:4px;background:var(--card);border:1px solid var(--line);border-radius:8px;padding:8px;margin:8px 0}
.flag img{max-width:100%;background:#fff;border-radius:4px}
.cols{display:grid;grid-template-columns:1fr 1fr;gap:12px} @media (max-width:760px){.cols{grid-template-columns:1fr}}
#lb{position:fixed;inset:0;background:rgba(0,0,0,.88);display:none;z-index:9;overflow:auto;cursor:zoom-out}
#lb img{max-width:none;width:auto;min-width:100%;display:block}
button.theme{position:fixed;top:10px;inset-inline-end:10px;z-index:5;font:13px system-ui;border:1px solid var(--line);background:var(--card);color:var(--fg);border-radius:6px;padding:4px 8px}
code{font-size:13px;background:var(--chip);padding:1px 4px;border-radius:4px;word-break:break-all}
"""

JS = """
document.querySelectorAll('a.zoom').forEach(a=>a.addEventListener('click',e=>{e.preventDefault();
 const lb=document.getElementById('lb');lb.innerHTML='<img src="'+a.querySelector('img').src+'">';lb.style.display='block';}));
document.getElementById('lb').onclick=e=>{e.currentTarget.style.display='none';};
document.querySelector('button.theme').onclick=()=>{const r=document.documentElement;r.dataset.theme=r.dataset.theme==='dark'?'light':'dark';};
"""


def bars(rows, maxv, fmt=lambda v: f"{100 * v:.2f}%"):
    out = []
    for name, v, cls in rows:
        w = 0 if v is None else min(100, 100 * v / maxv)
        out.append(f'<div class="bar"><span class="{cls}">{name}</span><span class="t"><i style="width:{w:.1f}%;'
                   f'background:var(--{cls})"></i></span><span>{fmt(v) if v is not None else "–"}</span></div>')
    return "".join(out)


def tile(k, body):
    return f'<div class="tile"><div class="k">{k}</div><div class="v">{body}</div></div>'


def flag_rows(run, kinds=("sic",), n=6, verdict=None):
    items = json.loads((OUT / "sheets" / f"{run}_items.json").read_text(encoding="utf-8"))
    out = []
    for x in items:
        if x["kind"] not in kinds:
            continue
        v = J[run].get(x["id"])
        if verdict and v != verdict:
            continue
        c = crop(art_of(x["stem"]), x["page"], x["line"])
        if c is None:
            continue
        img, az = c
        cls = {"right": "good", "wrong": "bad"}.get(v, "warn")
        why = J.get("why_wrong", {}).get(x["id"], "")
        out.append(f'<div class="flag"><img src="{b64img(img, 900, 70)}" alt=""><div>{"printed" if x["kind"] == "sic" else "Azure"}: '
                   f'<b class="ar" dir="auto">{H.escape(x["frm"])}</b> &nbsp;→&nbsp; {"proposed" if x["kind"] == "sic" else "fixed to"}: '
                   f'<b class="ar" dir="auto">{H.escape(x["to"] or "∅")}</b></div><div class="sub">{H.escape(x["stem"])} p{x["page"]} · '
                   f'{H.escape(x.get("why") or "")} · <span class="{cls}">judged {v}</span>'
                   f'{(" — " + H.escape(why)) if why else ""}</div></div>')
        if len(out) >= n:
            break
    return "".join(out)


ORDER_NOTE = {   # looked at by eye, 2026-10-15
    ("0355-000-002-006", 1): "Two columns under a photo, with Azure lines running across both: Argon makes one paragraph "
                             "read right column then left; Flash cuts the crossing lines into a third, middle block. Argon is right.",
    ("1054-023-010-019", 1): "The paragraph at the foot of the right column goes on at the top of the left: Argon follows it "
                             "there; Flash glues the top of the left column to the first paragraph and reads the left column "
                             "before the rest of the right. Argon is right.",
    ("0737-001-020-003", 11): "The same: the right column's last paragraph continues at the top of the left. Argon follows it; "
                              "Flash attaches it to the paragraph continued from the previous page. Argon is right.",
}


def build():
    A, F = T["argon"], T["flash"]
    ts, tg, tb = TS[None], TS["gold"], TS["bd"]
    nart = A["articles"]
    nwhole = sum(1 for a in sample() if a["kind"] == "whole")
    arch = {r: archive(UP[r]) for r in UP}
    body = []
    body.append(f"""<h1>Azure's words, Gemini's structure — on 55 articles</h1>
<p class="sub">Experiment 41 · 15 October 2026 · Gemini spend <b>${spend_total:.2f}</b> of the $20 cap ({calls} calls, from the live log)</p>
<p class="lede">Gemini looks at each page and at Azure's numbered lines, and answers only with line numbers: which lines
make a heading, a paragraph, a footnote, a verse, a table cell, in what order. The digital article is then built from
Azure's own words. Experiment 40 found this the most faithful way on 11 pages. Here it runs on {nwhole} whole articles
and {nart - nwhole} long-article windows ({A['pages']} pages, 1932–2025, 54 journals), once with
<b class="argon">gemini-4-argon</b> and once with <b class="flash">gemini-3.8-flash</b>, the same prompt.</p>
<div class="verdict"><b>Verdict.</b> The format holds up. Over {A['pages']} pages neither model lost a chunk, broke the JSON
or ran out of tokens; {A['lines']:,} Azure lines were each placed once, with {A['dropped']} line dropped by Argon and
{F['dropped']} by Flash, no line used twice. The text is Azure's, so nothing is invented, and with Argon's fixes it is
<i>more</i> faithful than Azure alone ({pct(ts['argon']['bag'], 2)} words wrong against {pct(ts['azure']['bag'], 2)} on
{ts['pages']} truth pages). <b>The two models build almost the same structure</b> (line types agree on
{pct(P['label_agree'])}, reading order {pct(P['order_all'])}, tables {P['teds_mean']:.2f} TEDS), about as close as
Argon is to itself on a repeat call. <b>Use Argon for the edition</b>: its fixes of Azure's misreadings are more and more
often right (judged by eye {JV['argon']['fix']['right']}/40 against Flash {JV['flash']['fix']['right']}/40), its
metadata is better, and the text comes out better. <b>Flash is enough for structure labels</b> (layout, order, tables,
footnote links for training our own specialists) at {UP['flash'] / UP['argon']:.0%} of Argon's price, if its fixes are
not applied.</div>""")

    body.append('<div class="tiles">' + "".join([
        tile(f"Words wrong vs the truth ({ts['pages']} pages: {tg['pages']} owner gold, {tb['pages']} born-digital; order ignored)",
             bars([("Azure", ts["azure"]["bag"], "azure"), ("Argon", ts["argon"]["bag"], "argon"),
                   ("Flash", ts["flash"]["bag"], "flash")], 0.025)),
        tile("Owner gold pages only (20 pages)", bars([("Azure", tg["azure"]["bag"], "azure"),
                                                       ("Argon", tg["argon"]["bag"], "argon"),
                                                       ("Flash", tg["flash"]["bag"], "flash")], 0.02)),
        tile(f"Lines placed exactly once (of {A['lines']:,})",
             f'<span class="argon">Argon</span> dropped {A["dropped"]}, threw {A.get("noise_with_words", 0)} lines with words away as '
             f'"noise" (26 on one page)<br><span class="flash">Flash</span> dropped {F["dropped"]}, {F.get("noise_with_words", 0)} '
             f'word lines as noise<br>duplicated: 0 and 0'),
        tile("Line types vs exp 39's Gemini Pro referee (29 pages, 1,245 lines)",
             bars([("Argon", S["referee"]["argon"]["agree"], "argon"), ("Flash", S["referee"]["flash"]["agree"], "flash")], 1.0,
                  lambda v: f"{100 * v:.1f}%") +
             f'<span class="sub">without the endnotes the referee calls references: Argon {pct(REFX["argon"])}, Flash {pct(REFX["flash"])}</span>'),
        tile("Cost per page (launch prices, Standard)",
             f'<span class="argon">Argon ${UP["argon"]:.4f}</span> · {A["secs_per_page"]:.0f} s<br>'
             f'<span class="flash">Flash ${UP["flash"]:.4f}</span> · {F["secs_per_page"]:.0f} s<br>'
             f'<span class="sub">per article: ${A["usd_per_article"]:.3f} / ${F["usd_per_article"]:.3f}</span>'),
        tile("The archive (1M documents ≈ 15.9M pages)",
             f'<span class="argon">Argon</span> ${arch["argon"]["mdocs"] / 1e3:,.0f}k Standard, ${arch["argon"]["mdocs"] / 2e3:,.0f}k Batch '
             f'(from 1 Dec: ×2)<br><span class="flash">Flash</span> ${arch["flash"]["mdocs"] / 1e3:,.0f}k Standard, '
             f'${arch["flash"]["mdocs"] / 2e3:,.0f}k Batch (from 1 Jan 2027: ×2)'),
    ]) + "</div>")

    # ---------------- showcase
    body.append("<h2>What comes out, beside the scan</h2><p>Each picture: the scan; Argon's blocks drawn on it "
                "(colour = type, number = reading order); Argon's page rendered in Chromium from Azure's words (Flash's is "
                "nearly the same on these pages; the differences are shown further down). "
                "Tap a picture to see it full size.</p>")
    legend = " ".join(f'<span class="chip"><b style="color:{c}">■</b> {k}</span>' for k, c in COLOURS.items())
    body.append(f"<p>{legend}</p>")
    show = [("0747-001-003-001", 6, "Pre-1960 vowelled poem with ten footnotes: every verse in two half-lines, footnote markers linked "
             "(both models). Argon also restored footnote markers Azure read as symbols."),
            ("0924-012-005-007", 2, "1930s accounts: ledger runs become real tables between paragraphs."),
            ("2382-005-003-001", 5, "2020s regression equations: displayed equations as LaTeX, typeset by KaTeX; the diagram boxed as a figure."),
            ("0877-007-027-003", 4, "1960s two columns with footnotes: right column first, the footnotes apart and linked."),
            ("1140-000-021-003", 2, "A French article: left-to-right blocks, headings and notes."),
            ("0355-000-002-006", 17, "Owner gold page, two columns: Azure ran five lines across both columns; both models split them and "
             "read each column whole.")]
    for stem, p, cap in show:
        body.append(fig(compose(stem, p, ("scan", "argon:blocks", "argon:render"), 1300), f"{H.escape(stem)} p{p}. {cap}", 1700, 70))

    # ---------------- Argon vs Flash
    def row(k, a, f, note=""):
        return f"<tr><td>{k}</td><td class='n argon'>{a}</td><td class='n flash'>{f}</td><td class='sub'>{note}</td></tr>"
    rows = [
        row("pages / articles", f"{A['pages']} / {A['articles']}", f"{F['pages']} / {F['articles']}", "same pages for both"),
        row("chunks failed (bad JSON, truncated, refused)", A["chunks_failed"], F["chunks_failed"], f"{A['chunks']} chunks of ≤ 10 pages each"),
        row("Azure lines dropped / duplicated", f"{A['dropped']} / {A['duplicated']}", f"{F['dropped']} / {F['duplicated']}", f"of {A['lines']:,}"),
        row("lines called noise (of them with words)", f"{A['noise']} ({A.get('noise_with_words', 0)})", f"{F['noise']} ({F.get('noise_with_words', 0)})",
            "noise is for specks and ornaments; lines with 3+ letters are really drops: Argon's 26 are the top half of 0656 p4"),
        row("ids it made up (unknown line ids)", A.get("issue_unknown_id", 0), F.get("issue_unknown_id", 0), "Flash: splits whose pieces were not Azure's text"),
        row("words wrong, 34 truth pages (order ignored)", pct(ts["argon"]["bag"], 2), pct(ts["flash"]["bag"], 2), f"Azure {pct(ts['azure']['bag'], 2)}"),
        row("… owner gold, 20 pages", pct(tg["argon"]["bag"], 2), pct(tg["flash"]["bag"], 2), f"Azure {pct(tg['azure']['bag'], 2)}"),
        row("… born-digital, 14 pages", pct(tb["argon"]["bag"], 2), pct(tb["flash"]["bag"], 2), f"Azure {pct(tb['azure']['bag'], 2)}"),
        row("characters wrong in reading order, 34 pages", pct(ts["argon"]["cer"], 2), pct(ts["flash"]["cer"], 2),
            f"Azure {pct(ts['azure']['cer'], 2)}: the truth keeps Azure's line order, so a right column split costs here (exp 40)"),
        row("fixes of Azure's misreadings applied", A["fixes"], F["fixes"], f"rejected (text not in the line): {A['fixes_rejected']} / {F['fixes_rejected']}"),
        row("… on truth pages, closer / further from the truth", f"{FV['argon']['right']} / {FV['argon']['wrong']}", f"{FV['flash']['right']} / {FV['flash']['wrong']}",
            f"neutral {FV['argon']['neutral']} / {FV['flash']['neutral']}"),
        row("… 40 random fixes judged by eye: right / wrong / unsure",
            f"{JV['argon']['fix']['right']} / {JV['argon']['fix']['wrong']} / {JV['argon']['fix']['unsure']}",
            f"{JV['flash']['fix']['right']} / {JV['flash']['fix']['wrong']} / {JV['flash']['fix']['unsure']}", "crop of the printed line beside each"),
        row("misprint flags (D30 span.sic)", A["sic"], F["sic"], "the text stays as printed"),
        row("… judged by eye: right / wrong / unsure",
            f"{JV['argon']['sic']['right']} / {JV['argon']['sic']['wrong']} / {JV['argon']['sic']['unsure']} (of 40 drawn)",
            f"{JV['flash']['sic']['right']} / {JV['flash']['sic']['wrong']} / {JV['flash']['sic']['unsure']} (all 25)", ""),
        row("missed text added (data-added)", A["missed"], F["missed"], "Gemini rarely volunteers text Azure has no line for"),
        row("line types vs Pro referee (29 pages)", pct(S["referee"]["argon"]["agree"]), pct(S["referee"]["flash"]["agree"]),
            f"without references/endnotes: {pct(REFX['argon'])} / {pct(REFX['flash'])}"),
        row("footnote calls linked to a footnote", f"{A['calls_resolved']} / {A['calls']}", f"{F['calls_resolved']} / {F['calls']}",
            f"the rest point to endnotes typed as list or references: {A.get('calls_endnote_match', 0)} / {F.get('calls_endnote_match', 0)} of them have a note starting with that number"),
        row("blocks continued across a page break", A["continued"], F["continued"], f"same first line marked by both: {P['continued_both']}"),
        row("tables / equations / figures", f"{A['tables']} / {A['equations']} / {A['figures']}", f"{F['tables']} / {F['equations']} / {F['figures']}", ""),
        row("metadata strings found verbatim in Azure's text", f"{A['meta_verbatim']} / {A['meta_strings']}", f"{F['meta_verbatim']} / {F['meta_strings']}", ""),
        row("dollars, all pages", f"${A['usd']:.2f}", f"${F['usd']:.2f}", "from the spend log (book/ per article)"),
        row("seconds per page (4 threads)", f"{A['secs_per_page']:.1f}", f"{F['secs_per_page']:.1f}", "model time per call, divided by pages"),
        row("output tokens per page (thinking)", f"{A['tout'] / A['pages']:.0f} ({A['think']})", f"{F['tout'] / F['pages']:.0f} ({F['think']})",
            "thinking low spent no thinking tokens on either model"),
    ]
    body.append(f"""<h2>Argon or Flash</h2>
<p>Same prompt, same {A['pages']} pages, thinking low. Agreement between the two on every line both used
({P['lines']:,} lines): <b>type {pct(P['label_agree'])}</b>, same block or not for consecutive lines
{pct(P['segmentation_agree'])}, reading order {pct(P['order_all'], 2)} of word pairs in the same order (multi-column pages,
{P['multicol_pages']} of them: {pct(P['order_multicol'], 2)}), {P['tables_paired']} tables paired, structure and text
TEDS {P['teds_mean']:.2f}.</p>
<div class="tw"><table><tr><th></th><th class="argon">Argon</th><th class="flash">Flash</th><th>note</th></tr>{''.join(rows)}</table></div>
<h3>How much of the difference is just noise?</h3>
<p>Five articles (52 pages) were sent again with the identical prompt to each model. Argon against itself: types
{pct(NZ['argon~argon_r2']['label_agree'])}, order {pct(NZ['argon~argon_r2']['order_all'], 2)}; Flash against itself:
types {pct(NZ['flash~flash_r2']['label_agree'])}, order {pct(NZ['flash~flash_r2']['order_all'], 2)}. On those same 52 pages
the two models differ about as much as Argon differs from itself (its repeat turned 62 body lines into list items). Small samples:
read every gap under a point or two as noise. Experiment 40 saw identical calls differ by about a point of words
wrong.</p>
<p>On the {len(P['pages_order_below_95'])} pages where the two orders differ by more than 5% of line pairs, the three
looked at by eye (below) are all Argon's: it follows a paragraph from the foot of the right column to the head of the
left; Flash does not.</p>
<p>The two disagree mostly on <b>what a numbered paragraph is</b> (list or body: {sum(c for x, y, c in P['disagreements'] if {x, y} == {'list', 'body'})} lines)
and <b>what endnotes are</b> (footnote, list or references: {sum(c for x, y, c in P['disagreements'] if {x, y} <= {'list', 'references', 'footnote'} and x != y)} lines).
Both are questions of definition that the prompt leaves open, not of seeing.</p>""")

    # disagreement pictures
    body.append("<h3>Where they disagree, as pictures</h3>")
    order_pages = sorted(P["pages_order_below_95"], key=lambda o: o["tau"])[:3]
    for o in order_pages:
        body.append(fig(compose(o["stem"], o["page"], ("scan", "argon:blocks", "flash:blocks"), 1300),
                        f"{o['stem']} p{o['page']}: reading order differs (same order for {100 * o['tau']:.0f}% of line pairs). "
                        + ORDER_NOTE.get((o["stem"], o["page"]), "Follow the block numbers on each."), 1600, 68))
    seen = {(o["stem"], o["page"]) for o in order_pages}
    for d in [d for d in DIS if (d["stem"], d["page"]) not in seen][:3]:
        body.append(fig(compose(d["stem"], d["page"], ("scan", "argon:blocks", "flash:blocks"), 1300),
                        f"{d['stem']} p{d['page']}: {d['diff']} of {d['n']} lines typed differently: "
                        + "; ".join(f"{c} lines Argon {x}, Flash {y}" for (x, y), c in d["pairs"]) + ".", 1600, 68))
    worst_tab = sorted([t for t in P["tables"] if t.get("teds") is not None], key=lambda t: t["teds"])[0]
    body.append(fig(compose(worst_tab["stem"], worst_tab["page"], ("scan", "argon:render", "flash:render"), 1300),
                    f"The table the two read most differently ({worst_tab['stem']} p{worst_tab['page']}, TEDS {worst_tab['teds']:.2f}): "
                    "a 1930s ledger whose columns are not ruled.", 1600, 68))

    # ---------------- text & fixes & flags
    body.append(f"""<h2>The text: Azure's, with fixes and flags</h2>
<p>Gemini may change Azure's text in exactly one way: a <b>fix</b>, where Azure's letters are not the printed letters
(a lost dot, a footnote number read as a symbol, « read as <span class="ar">((</span>). A <b>misprint</b> in the print
itself is never changed; it gets a D30 flag (<code>&lt;span class="sic" data-corr="…"&gt;</code>) beside the printed
word. Words wrong on the {ts['pages']} truth pages fall from {pct(ts['azure']['bag'], 2)} (Azure) to
{pct(ts['argon']['bag'], 2)} with Argon's fixes; Flash's fixes barely move it ({pct(ts['flash']['bag'], 2)}). The text
counted is every Azure line in the model's order with fixes applied; counted as the edition shows it (LaTeX in place of
the formula's characters) Argon is {pct(ts['argon/edition']['bag'], 2)}, because two born-digital pages of linear
programming (1148) turned into LaTeX that the truth has as characters.</p>
<p>Argon still repairs some printed misprints as if they were Azure's misreadings (<span class="ar">المتعمون</span>,
<span class="ar">دخل</span> — the same words experiment 40 caught), and Flash more often (<span class="ar">لأساوب</span>,
<span class="ar">صحه</span>, <span class="ar">اليت</span>, the printer's <span class="ar">٨</span>930 for 1930).
Flash also flags as misprints words Azure simply misread, which leaves the misreading in the text.</p>
<h3>Misprint flags, with the printed line</h3><div class="cols"><div><p class="argon"><b>Argon</b></p>{flag_rows('argon', ('sic',), 5, 'right')}{flag_rows('argon', ('sic',), 2, 'wrong')}</div>
<div><p class="flash"><b>Flash</b></p>{flag_rows('flash', ('sic',), 5, 'right')}{flag_rows('flash', ('sic',), 2, 'wrong')}</div></div>
<h3>Fixes judged wrong</h3><div class="cols"><div>{flag_rows('argon', ('fix',), 3, 'wrong')}</div><div>{flag_rows('flash', ('fix',), 4, 'wrong')}</div></div>
<p class="sub">All judged items: <code>out/sheets/argon_NN.png</code>, <code>out/sheets/flash_NN.png</code>; verdicts in <code>out/judged.json</code>.</p>""")

    # ---------------- metadata
    mrows = []
    for r in S["metadata"]:
        m = r["master"]
        a, f = r.get("argon", {}), r.get("flash", {})

        def cell(x):
            if not x:
                return "–"
            t = x.get("title", {})
            au = x.get("authors", {})
            s = (f'title {"✓" if t.get("exact") else ("≈" if t.get("ratio", 0) >= 0.9 else "✗")} {t.get("ratio", "")}'
                 if t else "")
            if au:
                s += f' · authors {au["matched"]}/{au["master"]}'
            if "abstract" in x:
                s += f' · abstract {x["abstract"]["ratio"]}'
            return s
        mrows.append(f"<tr><td>{H.escape(r['stem'])}</td><td class='ar' dir='rtl'>{H.escape((m['title'] or '')[:80])}</td>"
                     f"<td class='ar argon' dir='rtl'>{H.escape(str((a.get('meta') or {}).get('title') or '')[:80])}</td>"
                     f"<td class='sub'>{cell(a)}</td><td class='sub'>{cell(f)}</td></tr>")

    def msum(run):
        rows_ = [r[run] for r in S["metadata"] if run in r]
        t = [x["title"] for x in rows_ if "title" in x]
        au = [x["authors"] for x in rows_ if "authors" in x]
        ab = [x["abstract"] for x in rows_ if "abstract" in x]
        return (sum(x["exact"] for x in t), sum(x["ratio"] >= 0.9 for x in t), len(t), sum(x["matched"] for x in au),
                sum(x["master"] for x in au), sum(x["ratio"] >= 0.9 for x in ab), len(ab))
    ma, mf = msum("argon"), msum("flash")
    body.append(f"""<h2>Article metadata against the catalogue masters</h2>
<p>{ma[2]} sample articles have a merged catalogue master (experiment 29's JATS: title, authors, abstract). Strings must
be copied from Azure's lines; {A['meta_verbatim']} of {A['meta_strings']} of Argon's were (Flash {F['meta_verbatim']}/{F['meta_strings']}).</p>
<div class="tiles">{tile('Title', f'<span class="argon">Argon</span> exact {ma[0]}/{ma[2]}, ≥ 0.9 alike {ma[1]}/{ma[2]}<br><span class="flash">Flash</span> exact {mf[0]}/{mf[2]}, ≥ 0.9 alike {mf[1]}/{mf[2]}<br><span class="sub">"exact" after folding; the master is normalised (ي for the printed ى, hamzas), the model keeps the print. Flash often puts the subtitle in the title.</span>')}
{tile('Authors', f'<span class="argon">Argon</span> {ma[3]}/{ma[4]} master authors found<br><span class="flash">Flash</span> {mf[3]}/{mf[4]}')}
{tile('Abstract', f'<span class="argon">Argon</span> {ma[5]}/{ma[6]} ≥ 0.9 alike<br><span class="flash">Flash</span> {mf[5]}/{mf[6]}<br><span class="sub">only 6 masters have an abstract; most differ because the catalogue abstract is not the printed one, or the window did not include it</span>')}</div>
<details><summary>Every article with a master</summary><div class="tw"><table><tr><th>article</th><th>master title</th><th>Argon's title</th><th class="argon">Argon</th><th class="flash">Flash</th></tr>{''.join(mrows)}</table></div></details>""")

    # ---------------- cost
    def money(v):
        return f"${v / 1e3:,.0f}k" if v >= 1e4 else f"${v / 1e3:,.1f}k"
    crow = []
    for r, label, later in (("argon", "Argon", "from 1 Dec 2026"), ("flash", "Flash", "from 1 Jan 2027")):
        a1, a2 = archive(UP[r]), archive(UP[r], 2)
        crow.append(f"<tr><td class='{r}'>{label}</td><td class='n'>${UP[r]:.4f}</td><td class='n'>{money(a1['mpages'])} / {money(a1['mpages'] / 2)}</td>"
                    f"<td class='n'>{money(a1['mdocs'])} / {money(a1['mdocs'] / 2)}</td><td class='n'>{money(a2['mdocs'])} / {money(a2['mdocs'] / 2)}</td><td class='sub'>{later}</td></tr>")
    body.append(f"""<h2>Cost</h2>
<p>Per page here: Argon ${UP['argon']:.4f}, Flash ${UP['flash']:.4f} (whole-article chunks share one prompt, so cheaper
than page by page: exp 40's B cost $0.020 a page). Prices checked today on ai.google.dev: Argon $2 / $10 per million
input / output tokens until 30 November, then $4 / $20; Flash $0.75 / $3.75 until 31 December, then $1.50 / $7.50 (not
the $1 / $5 assumed in the brief); Batch is half.</p>
<div class="tw"><table><tr><th></th><th>$ / page</th><th>per million pages, Standard / Batch</th><th>per million documents (15.9 pages), Standard / Batch</th><th>per million documents after the price doubles</th><th></th></tr>{''.join(crow)}</table></div>
<p>Spend from the log: pilot ${spend_pilot:.2f} (both models on 5 articles, and Flash at thinking medium on 2), main run
Argon ${spend_main['argon']:.2f} + Flash ${spend_main['flash']:.2f}, repeat calls ${spend_r2:.2f}; total
<b>${spend_total:.2f}</b> of $20, {calls} calls.</p>
<p><b>Flash at thinking medium</b> (pilot, 2 articles): on the poem it spent 5,500 thinking tokens, still linked no
footnote and cost 40% more; on the 1930s ledger it thought 26,000 tokens and ran out of output (truncated, lost). Low it is.</p>""")

    # ---------------- labels, hand check, method
    body.append(f"""<h2>Training labels for our own specialists</h2>
<p>Every article also gets <code>out/&lt;model&gt;/labels/&lt;stem&gt;.json</code>: each Azure line with its box (300
dpi pixels), text (after fixes), block number, type (and the coarse layout label of experiment 39), heading level,
reading-order rank, verse half, table row / column / span; each block with its continuation, footnote id and the
calls pointing to it; the article metadata. That is what a layout model, a reading-order model, a table model, a
footnote linker and a whole-document metadata model each need, at ${UP['flash']:.4f} a page with Flash. The weak spots
to fix before labelling at scale: the list/body and endnote definitions (one sentence each in the prompt), and the
noise rule (a line with words must never be noise; reject such answers or re-ask).</p>
<h2>Your hand check</h2>
<p>Five articles, Argon's output, one page each in <code>experiments/41_azure_structure/out/handcheck/</code>:
<span class="chip">0747-001-003-001 — 1950s vowelled poem, footnotes</span><span class="chip">2382-005-003-001 — 2020s equations, tables</span>
<span class="chip">0877-007-027-003 — 1960s two columns, footnotes</span><span class="chip">0924-012-005-007 — 1930s accounts tables</span>
<span class="chip">1140-000-021-003 — French, 2010s</span></p>
<p>Open one in a browser. Each page of the article shows the scan with Argon's blocks drawn and numbered on the left,
and the digital page on the right, one numbered block per row. Press <b>yes</b> when a block is right (type, lines,
place in the reading order, text; tables, verse halves, equations and footnote links as printed) or <b>no</b> and write
why in the note. The marks stay in your browser; <b>Export my marks</b> saves them as a JSON file to send back. Works on a
phone (the scan then sits above its blocks).</p>
<h2>How it was done</h2>
<p><b>Sample</b> (<code>out/sample.json</code>, with the reason for each): {nwhole} whole articles of 1–24 pages and
{nart - nwhole} windows (sample page ± 2, with page 1 attached as context) of long articles, so that every experiment-40
truth page, all 20 owner gold pages, 14 born-digital truth pages and 29 of the 44 Pro-referee pages are inside, with
tables, equations, verse, heavy footnotes, two to four columns, French and English, 1932 to 2025, 54 journals,
41 with a catalogue master. <b>Pipeline</b> (<code>structure.py</code>): chunks of ≤ 10 pages; page images (2400 px) and
Azure's lines "page:line [box] text"; a later chunk also gets page 1's image, the outline so far and the last block of the
previous chunk. Strict fix rule (exp 40 B v5), D30 flags, footnote ids and calls, figure boxes, metadata as Azure's
strings. Every answer saved on arrival; resumable. Table cells are put in right-to-left order from Azure's boxes after the
models were seen to give the same table in either direction from one identical call to the next (TEDS 0.3 → 1.0).
<b>Scoring</b> (<code>score41.py</code>): words wrong is 1 − F1 of word multisets (exp 40's measure); referee lines matched
to Azure lines by box and text; pictures by <code>render41.py</code> in headless Chromium.</p>
<p class="sub"><b>Honest limits.</b> Truth for text is 34 pages; the referee is a Gemini too (Pro) and may favour Gemini;
fixes and flags were judged by one reader from crops, 40 of each drawn at random (seed 41); repeat calls only on 5
articles; one run per model. Prompt changes after the pilot: a firmer footnote-call rule (Flash had linked none on the
poem). The windows are not whole articles. Long articles over 24 pages were not run whole.</p>""")

    html = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Azure text, Gemini structure</title>
<link href="https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700&display=swap" rel="stylesheet">
<style>{CSS}</style></head><body><button class="theme">light / dark</button><main>{''.join(body)}</main><div id="lb"></div><script>{JS}</script></body></html>"""
    f = OUT / "report.html"
    f.write_text(html, encoding="utf-8")
    print(f, f"{f.stat().st_size / 1e6:.1f} MB")


if __name__ == "__main__":
    build()
