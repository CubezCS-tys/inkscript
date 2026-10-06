"""The owner's page: the trade-off as a picture, then whole pages with the flagged words tinted on the scan.

    .venv/bin/python make_report.py      -> out/report.html (self-contained)
"""
import base64
import html
import json
import sys
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import analyze as A  # noqa: E402
import flag as F  # noqa: E402
from docs import list_docs  # noqa: E402
from trust_pdf import LABEL  # noqa: E402

OUT = HERE / "out"; E19 = HERE.parent / "19_azure_map/out"
EV = json.load(open(OUT / "flag_eval.json"))
CONF = json.load(open(OUT / "confirm.json"))
CHK = json.load(open(OUT / "0582-004-009-012_vector_trust_check.json"))
DOCS = list_docs()
PAGES = [("0582-004-009-012", p) for p in (1, 2, 3, 4, 5)] + [("1005-000-001-002", 10), ("1005-000-001-002", 12), ("0618-021-002-004", 3)]
E = html.escape


def b64(img, q=62):
    ok, b = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, q]); return "data:image/jpeg;base64," + base64.b64encode(b).decode()


def b64png(path, maxw=None):
    img = cv2.imread(str(path))
    if maxw and img.shape[1] > maxw:
        img = cv2.resize(img, (maxw, int(img.shape[0] * maxw / img.shape[1])), interpolation=cv2.INTER_AREA)
    ok, b = cv2.imencode(".png", img); return "data:image/png;base64," + base64.b64encode(b).decode()


def page_img(pdf, pn, dpi=110):
    import pymupdf
    pix = pymupdf.open(str(pdf))[pn - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csGRAY)
    g = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
    return cv2.cvtColor(g, cv2.COLOR_GRAY2BGR), pix.w, pix.h


def why_text(w):
    t = "; ".join(LABEL.get(r, r) for r in w["why"])
    if w.get("conf") is not None: t += f" · confidence {w['conf']:.2f}"
    if w.get("gemini"): t += f" · Gemini reads «{w['gemini']}»"
    return t


def page_block(stem, pn):
    t = [w for w in json.loads((OUT / "trust" / f"{stem}.json").read_text()) if w["page"] == pn and w["box"]]
    img, W, H = page_img(DOCS[stem]["pdf"], pn)
    Wp, Hp = W * 300 / 110, H * 300 / 110          # the boxes are 300-dpi pixels
    marks = []
    nf = sum(w["mark"] == "flagged" for w in t); nv = sum(w["mark"] == "verified" for w in t)
    for w in t:
        if w["mark"] not in ("flagged", "verified"): continue
        x0, y0, x1, y1 = w["box"]
        st = f"left:{x0 / Wp * 100:.2f}%;top:{y0 / Hp * 100:.2f}%;width:{(x1 - x0) / Wp * 100:.2f}%;height:{(y1 - y0) / Hp * 100:.2f}%"
        if w["mark"] == "flagged":
            marks.append(f'<span class="mk f" style="{st}" tabindex="0"><i dir="auto"><b dir="rtl">{E(w["text"])}</b> — {E(why_text(w))}</i></span>')
        else:
            marks.append(f'<span class="mk v" style="{st}"></span>')
    words = sum(1 for w in t if w["mark"] != "punctuation")
    cap = f"{stem} · page {pn} · {words} words · <strong>{nf} flagged</strong>" + (f" · {nv} verified by a Quran verse or Gemini" if nv else "")
    return f'<figure class="page"><div class="pg" style="aspect-ratio:{W}/{H}"><img src="{b64(img)}" alt="page {pn} of {stem}">{"".join(marks)}</div><figcaption>{cap}</figcaption></figure>'


def curve_svg(series, points, title, ymax=1.0):
    Wd, Ht, L, R, T, B = 560, 330, 52, 16, 14, 44
    xmax = 0.25
    X = lambda v: L + min(v, xmax) / xmax * (Wd - L - R)
    Y = lambda v: T + (1 - v / ymax) * (Ht - T - B)
    g = []
    for v in (0, 0.05, 0.10, 0.15, 0.20, 0.25):
        g.append(f'<line class="grid" x1="{X(v):.1f}" x2="{X(v):.1f}" y1="{T}" y2="{Ht - B}"/><text class="tick" x="{X(v):.1f}" y="{Ht - B + 16}" text-anchor="middle">{v:.0%}</text>')
    for v in (0, 0.25, 0.5, 0.75, 1.0):
        g.append(f'<line class="grid" x1="{L}" x2="{Wd - R}" y1="{Y(v):.1f}" y2="{Y(v):.1f}"/><text class="tick" x="{L - 6}" y="{Y(v) + 4:.1f}" text-anchor="end">{v:.0%}</text>')
    g.append(f'<text class="axl" x="{(L + Wd - R) / 2}" y="{Ht - 6}" text-anchor="middle">share of words flagged (what a reader is asked to look at)</text>')
    g.append(f'<text class="axl" transform="translate(13,{(T + Ht - B) / 2}) rotate(-90)" text-anchor="middle">errors caught</text>')
    for cls, pts, lab in series:
        d = " ".join(f"{'M' if i == 0 else 'L'}{X(p['flagged']):.1f},{Y(p['caught']):.1f}" for i, p in enumerate(pts) if p["flagged"] <= xmax + 0.02)
        g.append(f'<path class="ln {cls}" d="{d}"/>')
        for p in pts:
            if p["flagged"] > xmax: continue
            tip = f"{lab}, confidence below {p['t']:.2f}: {p['flagged']:.1%} of words flagged, {p['caught']:.0%} of errors caught"
            g.append(f'<circle class="pt {cls}" cx="{X(p["flagged"]):.1f}" cy="{Y(p["caught"]):.1f}" r="3.5" data-tip="{E(tip)}"/>')
            for tv in (0.8, 0.9):
                if abs(p["t"] - tv) < 1e-9:
                    dx, dy = (6, 15) if cls == "s1" else (-6, -8)
                    g.append(f'<text class="lbl" x="{X(p["flagged"]) + dx:.1f}" y="{Y(p["caught"]) + dy:.1f}" text-anchor="{'start' if cls == 's1' else 'end'}">{tv}</text>')
    for p in points:
        g.append(f'<circle class="star" cx="{X(p["flagged"]):.1f}" cy="{Y(p["caught"]):.1f}" r="7" data-tip="{E(p["tip"])}"/>'
                 f'<text class="lbl strong" x="{X(p["flagged"]) - 10:.1f}" y="{Y(p["caught"]) - 10:.1f}" text-anchor="end">{E(p["label"])}</text>')
    return f'<svg viewBox="0 0 {Wd} {Ht}" role="img" aria-label="{E(title)}">{"".join(g)}</svg>'


def unweighted_curve(extra):
    rows = A.ROWS; ne = sum(r["truth"] for r in rows); pts = []
    for t in [0.0, 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.75, 0.8, 0.85, 0.9, 0.93, 0.95, 0.97, 0.99, 1.01]:
        f = F.rule(F.low_conf(t), *extra)
        pts.append(dict(t=t, flagged=A.measure(rows, f)["flagged"], caught=sum(1 for r in rows if r["truth"] and f(r)) / ne))
    return pts


def crop_cell(wid, text, judge, note):
    p = E19 / "crops" / (wid.replace(":", "_") + ".png")
    if not p.exists(): p = OUT / "confirm_crops" / (wid.replace(":", "_") + ".png")
    img = f'<img src="{b64png(p, 520)}" alt="">' if p.exists() else ""
    return (f'<div class="crop">{img}<div class="cap"><span class="ar">Azure <bdi>{E(text)}</bdi> · ink <bdi>{E(judge or "")}</bdi></span><br><small>{E(note)}</small></div></div>')


def main():
    R = {r["name"]: r for r in EV["rules"]}
    d = R[F.DEFAULT]; c19 = R["conf < 0.8 (experiment 19)"]; strict = R["+ hamza in hamza-omitting prints"]; old = R["+ old prints at conf < 0.9"]
    extra = [F.persian, F.quran, F.speck, F.ornament, F.latin]
    sv_w = curve_svg([("s1", EV["curve_conf"], "Azure's confidence alone"), ("s2", EV["curve_default"], "confidence + free signals")],
                     [dict(flagged=d["flagged"], caught=d["caught"], label="default", tip=f"Default: {d['flagged']:.1%} flagged, {d['caught']:.0%} caught (weighted)"),
                      dict(flagged=strict["flagged"], caught=strict["caught"], label="strict", tip=f"Strict: {strict['flagged']:.1%} flagged, {strict['caught']:.0%} caught")],
                     "Errors caught against words flagged, weighted as the archive")
    cu1, cu2 = unweighted_curve([]), unweighted_curve(extra)
    sv_u = curve_svg([("s1", cu1, "Azure's confidence alone"), ("s2", cu2, "confidence + free signals")],
                     [dict(flagged=d["flagged"], caught=d["caught_unweighted"], label="default", tip=f"Default: {d['n_caught']} of {d['n_errors']} judged errors")],
                     "Errors caught, each judged error counted once")

    def row(name, label=None, cls=""):
        m = R[name]; c = m["ci"]
        return (f'<tr class="{cls}"><td>{E(label or name)}</td><td>{m["flagged"]:.1%}<small> {c["flagged"][0]:.1%}–{c["flagged"][1]:.1%}</small></td>'
                f'<td>{m["per_page"]:.0f}</td><td>{m["caught"]:.0%}<small> {c["caught"][0]:.0%}–{c["caught"][1]:.0%}</small></td>'
                f'<td>{m["n_caught"]}/{m["n_errors"]}<small> {c["caught_unweighted"][0]:.0%}–{c["caught_unweighted"][1]:.0%}</small></td>'
                f'<td>{m["left"]:.2%}<small> {c["left"][0]:.2%}–{c["left"][1]:.2%}</small></td><td>1 in {1 / m["precision"]:.0f}</td></tr>')
    table = "".join([row("conf < 0.8 (experiment 19)", "confidence below 0.8 (experiment 19's rule)"),
                     row("conf < 0.9", "confidence below 0.9"),
                     row("+ speck & ornament", "0.8 + Persian + Quran + speck & ornament"),
                     row(F.DEFAULT, "default: … + Latin word on an Arabic page", "def"),
                     row("+ old prints at conf < 0.9", "… + old prints (pre-2000) at 0.9"),
                     row("+ hamza in hamza-omitting prints", "strict: … + hamza in a print that omits it"),
                     row("conf < 0.7 + Persian + Quran + speck & ornament + Latin", "the same signals with confidence below 0.7")])
    sig_rows = "".join(f'<tr><td>{E(k)}</td><td>{v["flags"]}</td><td>{v["errors"]}</td><td>+{v["new_flags"]}</td><td>+{v["new_errors"]}</td></tr>'
                       for k, v in EV["signals"].items())
    caught = "".join(f'<tr><td>{E(k)}</td><td>{v["caught"]} of {v["n"]}</td></tr>' for k, v in sorted(EV["by_cause"].items(), key=lambda kv: -kv[1]["n"]))
    NOTE = {"hamza added": "hamza the print omits; Azure sure", "box": "box held more than the word", "unsettled": "ink does not settle it",
            "latin": "Latin diacritic or order", "ya": "ى/ي", "misread": "ordinary misread"}
    missed = "".join(crop_cell(m["id"], m["text"], m["judge"], f"{NOTE.get(m['cause'], m['cause'])} · confidence {m['conf']:.2f}") for m in EV["missed"])
    ex_ids = ["0596-047-563-016:3:401", "0755-013-142-007:8:288", "0629-021-011-009:6:71", "0412-002-004-003:2:46", "0357-022-043-011:7:22", "0679-000-014-004:69:118"]
    J = {r["id"]: r for r in json.load(open(E19 / "judged.json"))}
    caught_ex = "".join(crop_cell(i, J[i]["text"], J[i]["judge"], f"{J[i]['cause']} · flagged: {', '.join(F.flag_reasons(next(r for r in A.ROWS if r['id'] == i)))}") for i in ex_ids)
    cf = EV["confirm"]; kept = [r for r in CONF if r["verdict"] != "right"]
    conf_cells = "".join(crop_cell(r["id"], r["text"], r["judge_text"], f"{r['verdict']} · {r['judge_why']}") for r in kept)
    spent = sum(json.loads(l)["usd"] for l in open(OUT / "spend.jsonl"))
    pages = "".join(page_block(s, p) for s, p in PAGES)
    shot_page = b64png(OUT / "chromium/trust_p3_hover.png", 760)
    import re
    def grab(stem, pat):
        for l in open(OUT / "tei" / f"{stem}.tei.xml", encoding="utf-8"):
            if re.search(pat, l) and "<w " in l: return l.strip()
        return ""
    tei_ex = html.escape("\n".join(x for x in [grab("0582-004-009-012", ">الخيبة<"), grab("0582-004-009-012", "trust.agreed"),
                                               grab("1005-000-001-002", "trust.verified"), grab("1005-000-001-002", "why.quran"),
                                               grab("0618-021-002-004", "why.speck"), grab("0618-021-002-004", "why.latin")] if x))
    teisum = json.load(open(OUT / "tei/summary.json"))
    tei_rows = "".join(f'<tr><td>{s}</td><td>{v["words"]:,}</td><td>{v["verified"]}</td><td>{v["agreed"]:,}</td><td>{v["flagged"]}</td>'
                       f'<td>{", ".join(f"{k} {n}" for k, n in sorted(v["why"].items(), key=lambda kv: -kv[1]))}</td></tr>' for s, v in teisum.items())
    pre, post = EV["pre-2000"], EV["2000+"]
    oldpre = A.full([r for r in A.ROWS if r["year"] and r["year"] < 2000], "old", F.RULES["+ old prints at conf < 0.9"], ci=False)

    H = f'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Uncertain-word marks</title>
<style>
:root{{--bg:#fcfcfb;--fg:#0b0b0b;--fg2:#52514e;--mute:#8a8984;--line:#e4e3de;--card:#ffffff;--s1:#2a78d6;--s2:#eb6834;--flag:rgba(235,150,20,.38);--flagb:#c77700;--ver:#1baf7a;--hi:#fff4dc}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#1a1a19;--fg:#fff;--fg2:#c3c2b7;--mute:#8f8e86;--line:#383835;--card:#232322;--s1:#3987e5;--s2:#d95926;--flag:rgba(235,150,20,.42);--flagb:#f0a030;--ver:#199e70;--hi:#3a2f18}}}}
:root[data-theme="dark"]{{--bg:#1a1a19;--fg:#fff;--fg2:#c3c2b7;--mute:#8f8e86;--line:#383835;--card:#232322;--s1:#3987e5;--s2:#d95926;--flag:rgba(235,150,20,.42);--flagb:#f0a030;--ver:#199e70;--hi:#3a2f18}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:1040px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:1.9rem;margin:.2em 0 .1em}}h2{{margin-top:2.2em;font-size:1.35rem}}
p,li{{color:var(--fg)}}.lede{{color:var(--fg2);font-size:1.08rem;max-width:60em}}small{{color:var(--mute)}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:12px;margin:18px 0}}.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}}
.tile b{{display:block;font-size:1.6rem}}.tile span{{color:var(--fg2);font-size:.9rem}}
.charts{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(300px,100%),1fr));gap:16px}}.chart{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:10px}}
.chart h3{{margin:.2em .3em .4em;font-size:1rem}}svg{{width:100%;height:auto;display:block}}
.grid{{stroke:var(--line);stroke-width:1}}.tick{{fill:var(--mute);font-size:11px}}.axl{{fill:var(--fg2);font-size:12px}}
.ln{{fill:none;stroke-width:2}}.ln.s1{{stroke:var(--s1)}}.ln.s2{{stroke:var(--s2)}}.pt{{stroke:var(--card);stroke-width:2}}.pt.s1{{fill:var(--s1)}}.pt.s2{{fill:var(--s2)}}
.star{{fill:none;stroke:var(--fg);stroke-width:2}}.lbl{{fill:var(--fg2);font-size:11px}}.lbl.strong{{fill:var(--fg);font-weight:600;font-size:12px}}
.legend{{display:flex;gap:16px;flex-wrap:wrap;font-size:.9rem;color:var(--fg2);margin:4px 6px}}.legend i{{display:inline-block;width:14px;height:3px;vertical-align:middle;margin-right:6px}}
#tip{{position:fixed;pointer-events:none;background:var(--card);color:var(--fg);border:1px solid var(--line);border-radius:6px;padding:6px 8px;font-size:.85rem;max-width:280px;display:none;z-index:9;box-shadow:0 2px 8px rgba(0,0,0,.15)}}
.tbl{{overflow-x:auto}}table{{border-collapse:collapse;width:100%;font-size:.9rem}}th,td{{text-align:left;padding:6px 8px;border-bottom:1px solid var(--line);vertical-align:top}}th{{color:var(--fg2);font-weight:600}}
td small{{display:block}}tr.def td{{background:var(--hi);font-weight:600}}
.pages{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(460px,100%),1fr));gap:18px}}.page{{margin:0}}.pg{{position:relative;border:1px solid var(--line);background:#fff}}.pg img{{width:100%;display:block}}
.mk{{position:absolute;border-radius:2px}}.mk.f{{background:var(--flag);outline:1px solid var(--flagb);cursor:help}}.mk.v{{border-bottom:2px solid var(--ver)}}
.mk i{{display:none;position:absolute;bottom:115%;left:50%;transform:translateX(-50%);background:var(--card);color:var(--fg);border:1px solid var(--line);padding:5px 8px;border-radius:6px;font:13px/1.4 system-ui,sans-serif;font-style:normal;width:max-content;max-width:240px;z-index:5;box-shadow:0 2px 8px rgba(0,0,0,.2)}}
.mk:hover i,.mk:focus i{{display:block}}.mk:hover,.mk:focus{{z-index:6}}
figcaption{{font-size:.88rem;color:var(--fg2);padding:6px 2px}}
.crops{{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(260px,100%),1fr));gap:12px}}.crop{{background:var(--card);border:1px solid var(--line);border-radius:8px;overflow:hidden}}.crop img{{width:100%;display:block;background:#fff}}.crop .cap{{padding:6px 10px;font-size:.9rem}}
.ar{{font-size:1.15rem}}pre{{background:var(--card);border:1px solid var(--line);border-radius:8px;padding:10px;overflow-x:auto;font-size:.8rem;direction:ltr}}
.shot{{max-width:560px;border:1px solid var(--line);border-radius:8px;overflow:hidden}}.shot img{{width:100%;display:block}}
.key span{{display:inline-block;width:28px;height:14px;vertical-align:middle;margin-right:6px}}
</style></head><body><main>
<h1>Uncertain-word marks</h1>
<p class="lede">Every word of a scanned document gets one mark: <strong>flagged</strong> (with the reason), <strong>verified</strong> (a Quran verse or Gemini agrees), or <strong>agreed</strong> (nothing raised a doubt). The aim (D17): a reader can trust what is not marked. Measured on experiment 19's 2,971 judged words from 139 random scanned documents. Experiment 22, 2026-10-06.</p>
<div class="tiles">
<div class="tile"><b>{d["flagged"]:.1%}</b><span>of words flagged by the default · about {d["per_page"]:.0f} on an average page of {EV["words_per_page"]:.0f} words</span></div>
<div class="tile"><b>{d["n_caught"]} of {d["n_errors"]}</b><span>judged errors caught ({d["caught_unweighted"]:.0%}; weighted as the archive {d["caught"]:.0%}, interval {d["ci"]["caught"][0]:.0%}–{d["ci"]["caught"][1]:.0%})</span></div>
<div class="tile"><b>{d["left"]:.2%}</b><span>of unflagged words are wrong (interval {d["ci"]["left"][0]:.2%}–{d["ci"]["left"][1]:.2%}). Without any mark, 1.55% are</span></div>
<div class="tile"><b>1 in {1 / d["precision"]:.0f}</b><span>flagged words is really wrong. The rest are false alarms, mostly bare-alef words Azure doubts</span></div>
</div>

<h2>1 · The trade-off</h2>
<p>Each dot on a curve is one confidence threshold. Moving right flags more words and catches more errors. The orange curve adds the free signals (specks, ornaments, Latin words on Arabic pages, Persian letters, Quran differences) to the confidence rule. They catch {d["n_caught"] - c19["n_caught"]} more of the judged errors and add only {(d["flagged"] - c19["flagged"]) * 100:.1f} points of flags. Most of those errors are non-text ink, which the archive weights lightly, so the left chart barely moves while the right one does.</p>
<div class="legend"><span><i style="background:var(--s1)"></i>Azure's confidence alone</span><span><i style="background:var(--s2)"></i>confidence + free signals</span><span>○ chosen rules</span></div>
<div class="charts"><div class="chart"><h3>Weighted as the archive</h3>{sv_w}</div><div class="chart"><h3>Each judged error counted once</h3>{sv_u}</div></div>
<p><small>Weighted: each judged word stands for the N/n words of its document and stratum, as in experiment 19. A few long documents carry most of the weight: four added hamzas in body text weigh more than all 26 non-text errors together. That is why the weighted intervals are so wide.</small></p>
<div class="tbl"><table><thead><tr><th>rule</th><th>flagged</th><th>per page</th><th>caught (weighted)</th><th>caught (count)</th><th>wrong among unflagged</th><th>flags that are errors</th></tr></thead><tbody>{table}</tbody></table></div>
<p><strong>Default: Azure's confidence below 0.8, plus four free signals.</strong> The signals are a speck or stray mark, an ornament or stamp, a Latin word on an Arabic page, and a Persian letter the build does not fold. A Quran-verse difference also flags, and a verse agreement verifies. Why this rule: each added signal catches errors at almost no cost in flags. The next step, a 0.9 bar on pre-2000 prints, raises the flags to {old["per_page"]:.0f} words per page overall and {oldpre["per_page"]:.0f} on an old page (from {pre["per_page"]:.0f}), for two more judged errors. One of those two is a single heavy-weight word. It is kept as the <em>strict</em> option, together with the hamza rule. Splitting the default by age: on pre-2000 scans it flags {pre["flagged"]:.1%} and leaves {pre["left"]:.2%} wrong ({pre["n_caught"]}/{pre["n_errors"]} caught). From 2000 on it flags {post["flagged"]:.1%} and leaves {post["left"]:.2%} ({post["n_caught"]}/{post["n_errors"]}).</p>
<div class="tbl"><table><thead><tr><th>signal</th><th>words it marks (of 2,971)</th><th>errors among them</th><th>beyond confidence &lt; 0.8: words</th><th>…errors</th></tr></thead><tbody>{sig_rows}</tbody></table></div>
<p><small>The Quran check cannot be scored here: none of the judged words falls on a quotation word that differs from its verse. Over all 578,852 words of the 139 documents it flags {EV["quran_all_words"]["differing"]} ({EV["quran_all_words"]["share"]:.2%}). On the ink, experiment 20 found 20 of 24 such words to be Azure misreadings. ﷺ and superscript note numbers are already all caught by confidence, so they are not separate signals.</small></p>

<h2>2 · What is caught, and what no free signal catches</h2>
<div class="tbl"><table><thead><tr><th>kind of error (by eye, experiment 19)</th><th>caught by the default</th></tr></thead><tbody>{caught}</tbody></table></div>
<p>Caught: specks, ornaments, handwriting and ﷺ, all of it. Six examples, with what Azure read and what the ink says:</p>
<div class="crops">{caught_ex}</div>
<p><strong>Missed: {len(EV["missed"])} errors.</strong> Azure is sure of all of them (confidence 0.81–0.99), and nothing on the page looks odd. The dangerous ones are the hamza Azure adds where an old print has none (<bdi>أهل</bdi> for <bdi>اهل</bdi>, at 0.99), an ordinary misread (<bdi>الجزي</bdi> for <bdi>الخزي</bdi>, 0.94), ى/ي, and a Latin diacritic. Only a second reading finds these.</p>
<div class="crops">{missed}</div>

<h2>3 · Whole pages, as the owner would see them</h2>
<p class="key"><span style="background:var(--flag);outline:1px solid var(--flagb)"></span>flagged: hover over it (or tap it) for the reason &nbsp; <span style="border-bottom:2px solid var(--ver)"></span>verified by a Quran verse or by Gemini's page-1 reading</p>
<p>The fixture (5 pages, an older print that leaves out most hamzas): most flags are bare-alef words such as <bdi>ان</bdi>, <bdi>انه</bdi> and <bdi>ايضا</bdi>. Azure doubts them because the hamza is missing, but they are printed that way. This is the cost of a 1-in-7 flag. On pages 10 and 12 of 1005-000-001-002, Quran quotations are verified word by word (green). 0618-021-002-004 page 3 shows specks and Latin flags.</p>
<div class="pages">{pages}</div>

<h2>4 · Paying the judge to clear flags</h2>
<p>Experiment 19's verdicts on the flagged words (nothing paid again) say the judge would clear <strong>{cf["cleared"]:.0%}</strong> of the default's flags. That would leave about {cf["flags_left_per_page"]:.0f} flags per page instead of {d["per_page"]:.0f}. With Flash on every flag and Pro on the {cf["flash_not_right"]:.0%} Flash doubts, that costs ${cf["per_word"]:.4f} per flagged word. <strong>Archive-wide</strong> (about {cf["archive_scanned_docs"] / 1e3:.0f}k scanned documents, {cf["archive_words"] / 1e9:.1f} billion words, {cf["flagged_words"] / 1e6:.0f} million flags) that is about <strong>${cf["usd_two_stage"] / 1e3:.0f}k</strong>, roughly half with a batch discount, or ${cf["usd_pro_only"] / 1e3:.0f}k with Pro alone. The judge itself misses about 2% of one-mark errors on archive prints.</p>
<p><strong>Tried on 60 flagged words</strong> of the four scanned TEI documents (spent ${spent:.2f} of the $5 cap): {sum(r["verdict"] == "right" for r in CONF)} cleared, {sum(r["verdict"] == "wrong" for r in CONF)} confirmed wrong, {sum(r["verdict"] == "box" for r in CONF)} bad boxes. The words that stayed flagged are below. Most are hamza questions: Azure added or dropped the hamza the print shows.</p>
<div class="crops">{conf_cells}</div>

<h2>5 · Where the marks are stored</h2>
<p>In each document's TEI file (experiment 20's format, extended), every word carries its mark and its reasons as pointers into two taxonomies, <code>#trust.*</code> and <code>#why.*</code>. All five files validate against <code>tei_all</code> (0 errors).</p>
<pre>{tei_ex}</pre>
<div class="tbl"><table><thead><tr><th>document</th><th>words</th><th>verified</th><th>agreed</th><th>flagged</th><th>reasons</th></tr></thead><tbody>{tei_rows}</tbody></table></div>
<p><small>0642-029-001-016 is born-digital: its PDF keeps the publisher's own text, so its marks describe Azure's reading only.</small></p>

<h2>6 · Marks inside the PDF, the drawing untouched</h2>
<p><code>0582-004-009-012_vector_trust.pdf</code> is a copy of the faithful PDF with {CHK["annotations"]} highlight annotations, one per flagged word. They sit in a layer called “Uncertain words” that a viewer can switch off. The copy is an <em>incremental update</em>: its first {CHK["original_bytes"]:,} bytes are the original file, byte for byte, and the notes come after. In pdfium (5.12.1, Chrome's engine) all {CHK["pages"]} pages give the same text and the same {CHK["chars"]:,} character boxes. Words intact: {CHK["trust"]["intact"]}/{CHK["trust"]["words"]} in both. Lines in order: {CHK["trust"]["in_order"]}/{CHK["trust"]["lines"]} in both. In a real Chromium 153, dragging across the flagged word الخيبة copies it letter by letter (ا, ال, … الخيبة), exactly as in the original. Hovering a flagged word opens its note. Chromium's note box draws no Arabic, so the note gives the reason in plain words.</p>
<div class="shot"><img src="{shot_page}" alt="the trust PDF in Chromium with a note open"></div>
<p><small>Chromium 153, page 3 of the trust copy, mouse resting on a flagged word.</small></p>
</main><div id="tip"></div>
<script>
const tip=document.getElementById('tip');
document.querySelectorAll('[data-tip]').forEach(el=>{{
 el.addEventListener('mousemove',e=>{{tip.textContent=el.dataset.tip;tip.style.display='block';tip.style.left=Math.min(e.clientX+12,innerWidth-290)+'px';tip.style.top=(e.clientY+12)+'px'}});
 el.addEventListener('mouseleave',()=>tip.style.display='none');}});
</script></body></html>'''
    (OUT / "report.html").write_text(H, encoding="utf-8")
    print("out/report.html", len(H) // 1024, "KB")


if __name__ == "__main__":
    main()
