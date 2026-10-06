"""out/report.html: the owner's page. Headline as bars, the judge's calibration as a picture, then real words from the
scan with each method's letter boxes laid on the ink (a wrong box in red), and where each method fails.

    .venv/bin/python make_report.py
"""
import json, base64, random, html
from pathlib import Path
import numpy as np, cv2
import judge18 as J, run18 as R

HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
NAMES = {"cutter": "Letter cutter (today's PDF)", "feeler": "Feeler's cuts", "equal": "Equal slices (free)"}
SHORT = {"cutter": "cutter", "feeler": "feeler", "equal": "equal slices"}


def word_strip(w, side=0.5, target_h=80):
    gray = J.J17.page_image(J.scan_of(w["doc"]), w["page"])
    x0, y0, x1, y1 = w["box"]; h = max(20, y1 - y0); H, W = gray.shape
    cx0, cx1 = max(0, int(x0 - side * h)), min(W, int(x1 + side * h)); cy0, cy1 = max(0, int(y0 - 0.2 * h)), min(H, int(y1 + 0.2 * h))
    g = gray[cy0:cy1, cx0:cx1]; s = target_h / g.shape[0]
    g = cv2.resize(g, None, fx=s, fy=s, interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
    ok, b = cv2.imencode(".png", g)
    return "data:image/png;base64," + base64.b64encode(b.tobytes()).decode(), cx0, cx1 - cx0, g.shape[1], g.shape[0]


def strip_html(w, m, oks, img):
    src, cx0, cw, pw, ph = img
    bands, labels = [], []
    for k, cell in enumerate(w[m]):
        a, b = (cell[0] - cx0) / cw * 100, (cell[1] - cx0) / cw * 100
        ok = oks[k]; cls = "ok" if ok else "bad" if ok is not None else "na"
        alt = " alt" if k % 2 else ""
        bands.append(f'<div class="band {cls}{alt}" style="left:{a:.2f}%;width:{max(0.3, b - a):.2f}%"></div>')
        labels.append(f'<span class="lab {cls}" style="left:{(a + b) / 2:.2f}%">{html.escape(w["text"][k])}</span>')
    return (f'<div class="strip"><div class="mname">{SHORT[m]}</div><div class="pic" style="aspect-ratio:{pw}/{ph};max-width:{int(pw * 1.5)}px">'
            f'<img src="{src}" alt="">{"".join(bands)}</div><div class="labs">{"".join(labels)}</div></div>')


def bar(label, v, ci, cls, n):
    return (f'<div class="brow"><div class="blab">{label}</div><div class="btrack"><div class="bfill {cls}" style="width:{v}%"></div>'
            f'<div class="ci" style="left:{ci[0]}%;width:{max(0.4, ci[1] - ci[0])}%"></div></div><div class="bval">{v:.0f}%<small> {ci[0]:.0f}–{ci[1]:.0f}</small></div></div>')


def main():
    S = json.load(open(OUT / "sample.json")); M = json.load(open(OUT / "summary.json")); cal = [json.loads(l) for l in open(OUT / "calibration.jsonl")]
    words = M["words"]; spend = J.spent()
    A = M["samples"]["A"]; Bs = M["samples"]["B"]; Cs = M["samples"]["C"]

    def head(res, methods, key, cikey):
        return "".join(bar(NAMES[m], res[m]["both"][key], res[m]["both"][cikey], m, res[m]["both"]["words"]) for m in methods)

    def oks(s, w, m):
        return [words.get(f"{s}|{R.wid(w)}|{m}|{k}", {}).get("ok") for k in range(1, len(w["text"]) + 1)]

    # examples: chosen by outcome, deterministic
    rnd = random.Random(7); cats = {"The cutter right, equal slices wrong": [], "Equal slices right, the cutter wrong": [],
                                    "The feeler right where the cutter is wrong": [], "The cutter right where the feeler is wrong": [], "Every method wrong": [], "A joined alef at the end of a piece: the cutter's sliver": []}
    for w in S["A"]:
        if R.wid(w) not in A["word_ids"]: continue
        o = {m: all(oks("A", w, m)) for m in ("cutter", "feeler", "equal")}
        if o["cutter"] and not o["equal"]: cats["The cutter right, equal slices wrong"].append(w)
        if o["equal"] and not o["cutter"]: cats["Equal slices right, the cutter wrong"].append(w)
        if o["feeler"] and not o["cutter"]: cats["The feeler right where the cutter is wrong"].append(w)
        if o["cutter"] and not o["feeler"]: cats["The cutter right where the feeler is wrong"].append(w)
        if not any(o.values()): cats["Every method wrong"].append(w)
        ca, ea = oks("A", w, "cutter"), oks("A", w, "equal")
        if any(c == "ا" and j and not ca[i] and ea[i] for i, (c, j) in enumerate(zip(w["text"], w["joined"]))):
            cats["A joined alef at the end of a piece: the cutter's sliver"].append(w)
    ex_html = []
    for title, ws in cats.items():
        rnd.shuffle(ws); cards = []
        for w in ws[:4]:
            img = word_strip(w)
            cards.append(f'<div class="card"><div class="wtitle" dir="rtl">{html.escape(w["text"])}</div><div class="wmeta">book {w["doc"]}, page {w["page"]}</div>'
                         + "".join(strip_html(w, m, oks("A", w, m), img) for m in ("cutter", "feeler", "equal")) + "</div>")
        ex_html.append(f'<h3>{title} <small>({len(ws)} of {len(A["word_ids"])} words)</small></h3><div class="cards">{"".join(cards) or "<p>none</p>"}</div>')

    # calibration picture
    c = {d["model"] + d["version"]: d["res"] for d in cal}
    cg, cb = c.get("gemini-3.8-flash:b2", {}), c.get("gemini-3.8-flash:b3", {})
    CAL = M["calibration"]; lab = {"sep_true": ("Right box", "should be accepted"), "sep_whole": ("Moved a whole letter", "should be refused"),
                                    "join_whole": ("Moved a whole letter, joined letter", "should be refused"), "sep_half": ("Moved half a letter", "should be refused"),
                                    "join_half": ("Moved half a letter, joined letter", "should be refused")}
    calhtml = ""
    for k in ("sep_true", "sep_whole", "join_whole", "sep_half", "join_half"):
        d = CAL.get(k)
        if not d: continue
        good = d["both"] if k == "sep_true" else d["n"] - d["both"]
        calhtml += f'<div class="cbox"><div>{lab[k][0]}</div><div class="big">{good}/{d["n"]}</div><small>{lab[k][1]} — graded alone {d["graded"] if k == "sep_true" else d["n"] - d["graded"]}/{d["n"]}, blind alone {d["blind"] if k == "sep_true" else d["n"] - d["blind"]}/{d["n"]}</small></div>'
    M["calibration_html"] = calhtml

    def failrow(m):
        f = M["failures"][m]
        if not f["letters"]: return ""
        pos = " · ".join(f'{p}: <b>{100 * a / max(1, b):.0f}%</b> wrong' for p, (a, b) in f["by_position"].items())
        jn = f'joined letters <b>{100 * f["joined"][0] / max(1, f["joined"][1]):.0f}%</b> wrong · separate letters <b>{100 * f["separate"][0] / max(1, f["separate"][1]):.0f}%</b> wrong'
        gv = f["graded_verdict_of_wrong"]; tot = max(1, sum(gv.values()))
        kinds = " · ".join(f'{k.lower()}: {100 * v / tot:.0f}%' for k, v in sorted(gv.items(), key=lambda t: -t[1]))
        worst = " ".join(f'<span class="chip">{l} {a}/{b}</span>' for l, a, b in f["worst_letters"][:6] if a)
        return (f'<div class="fail"><h4>{NAMES[m]}</h4><p>{f["wrong"]} of {f["letters"]} letter boxes wrong. {pos}.</p><p>{jn}.</p>'
                f'<p>When wrong, the graded judge said: {kinds}.</p><p>Most often wrong: {worst}</p></div>')

    from collections import Counter
    ac = Counter()
    for s_, ws in S.items():
        for w in ws:
            for m in R.methods_of(s_):
                for k in range(1, len(w["text"]) + 1):
                    v = words.get(f"{s_}|{R.wid(w)}|{m}|{k}")
                    if v and w["text"][k - 1] == "ا":
                        kind = "joined" if w["joined"][k - 1] else "sep"; ac[(m, kind)] += 1; ac[(m, kind, "ok")] += v["ok"]
    alef = (f"An alef at the end of a joined piece (كان، منها، أسباب) hangs from one point of the pen path, so its stretch of the baseline — its box — "
            f"is a sliver at the alef's foot. The judge accepted the cutter's box on {ac[('cutter', 'joined', 'ok')]} of {ac[('cutter', 'joined')]} such alefs, "
            f"equal slices on {ac[('equal', 'joined', 'ok')]} of {ac[('equal', 'joined')]}, the feeler on {ac[('feeler', 'joined', 'ok')]} of {ac[('feeler', 'joined')]} "
            f"(it uses the same box rule). A separate alef (the ا of ال) is fine: cutter {ac[('cutter', 'sep', 'ok')]} of {ac[('cutter', 'sep')]}. "
            "Joined alefs are one letter in fifteen but about a sixth of the cutter's wrong boxes; giving a letter's box the width of the ink that hangs from it would fix them.")
    pa = A["paired"]
    sens = CAL["sep_true"]["both"] / CAL["sep_true"]["n"]; fhalf = (CAL["sep_half"]["both"] + CAL["join_half"]["both"]) / (CAL["sep_half"]["n"] + CAL["join_half"]["n"])
    def cr(v): return f"{100 * (v / 100 - fhalf) / (sens - fhalf):.0f}–{100 * (v / 100) / sens:.0f}%"
    corr = ", ".join(f"{SHORT[m]} <b>{cr(A[m]['both']['letter'])}</b>" for m in ("cutter", "feeler", "equal"))
    page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Letter Box Placement</title>
<style>
:root{{--bg:#f6f4ef;--card:#fff;--ink:#1d1d1f;--mute:#6b6b70;--line:#e2ded6;--cut:#2f6fd6;--feel:#1d9a77;--eq:#9a9aa2;--ok:#2f6fd6;--ok2:#1d9a77;--bad:#d93a2b}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{--bg:#16171a;--card:#202226;--ink:#ececef;--mute:#9a9aa3;--line:#33353b;--cut:#6ea0ff;--feel:#4fd1a8;--eq:#8d8d96;--bad:#ff6b5c}}}}
:root[data-theme="dark"]{{--bg:#16171a;--card:#202226;--ink:#ececef;--mute:#9a9aa3;--line:#33353b;--cut:#6ea0ff;--feel:#4fd1a8;--eq:#8d8d96;--bad:#ff6b5c}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.5 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}}h1{{font-size:1.7rem;margin:.2em 0}}h2{{margin-top:2.2em;font-size:1.25rem}}h3{{font-size:1.05rem;margin-top:1.6em}}
h3 small,.wmeta,small{{color:var(--mute);font-weight:400}}p.lede{{color:var(--mute);max-width:46em}}
.panel{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}
.brow{{display:grid;grid-template-columns:minmax(96px,170px) 1fr 96px;gap:10px;align-items:center;margin:8px 0}}
.blab{{font-size:.92rem}}@media (max-width:600px){{.brow{{grid-template-columns:1fr 90px;gap:2px 10px}}.blab{{grid-column:1/-1}}}}.btrack{{position:relative;height:22px;background:var(--line);border-radius:6px}}
.bfill{{height:100%;border-radius:6px}}.bfill.cutter{{background:var(--cut)}}.bfill.feeler{{background:var(--feel)}}.bfill.equal{{background:var(--eq)}}
.ci{{position:absolute;top:-4px;height:30px;border-left:2px solid var(--ink);border-right:2px solid var(--ink);opacity:.55}}
.bval{{font-variant-numeric:tabular-nums;font-weight:600}}.bval small{{font-weight:400}}
.grid2{{display:grid;grid-template-columns:repeat(auto-fit,minmax(300px,1fr));gap:12px}}
.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(280px,1fr));gap:12px}}
.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:12px}}
.wtitle{{font-size:1.4rem;font-weight:600}}.strip{{margin-top:8px}}.mname{{font-size:.8rem;color:var(--mute)}}
.pic{{position:relative;width:100%;background:#fff;border-radius:4px;overflow:hidden}}.pic img{{width:100%;height:100%;display:block}}
.band{{position:absolute;top:0;bottom:0;mix-blend-mode:multiply;background:rgba(47,111,214,.30);border-left:1px solid rgba(47,111,214,.8)}}
.band.alt{{background:rgba(29,154,119,.30);border-left-color:rgba(29,154,119,.8)}}
.band.bad{{background:repeating-linear-gradient(45deg,rgba(217,58,43,.42) 0 5px,rgba(217,58,43,.18) 5px 10px);border-left:1px solid #d93a2b}}
.band.na{{background:rgba(120,120,120,.2)}}
.labs{{position:relative;height:1.6em;direction:ltr}}.lab{{position:absolute;transform:translateX(-50%);font-size:1rem;font-weight:600;color:var(--ok)}}
.lab.bad{{color:var(--bad)}}.lab.na{{color:var(--mute)}}
.fail h4{{margin:.2em 0}}.fail p{{margin:.35em 0;font-size:.93rem}}.chip{{display:inline-block;border:1px solid var(--line);border-radius:999px;padding:0 8px;margin:2px;font-size:.9rem}}
.calib{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:10px}}.cbox{{border:1px solid var(--line);border-radius:10px;padding:10px}}
.big{{font-size:1.6rem;font-weight:700}}table{{border-collapse:collapse;font-size:.9rem;width:100%}}td,th{{border-bottom:1px solid var(--line);padding:4px 6px;text-align:left}}
.legend span{{display:inline-block;margin-right:14px;font-size:.9rem}}.sw{{display:inline-block;width:14px;height:14px;border-radius:3px;vertical-align:-2px;margin-right:5px}}
</style></head><body><main>
<h1>Does each letter's highlight sit on its letter?</h1>
<p class="lede">Experiment 18, {M.get("date", "2026-10-06")}. Real words from scanned pages, each letter's selection box laid on the scanned ink, judged blind by Gemini ({M["model"]}). A box counts as right only when it covers that letter's whole body and nothing substantial of a neighbour. Three ways of placing the boxes on the same words.</p>

<h2>Headline: the same {A["cutter"]["both"]["words"]} words, unseen pages</h2>
<div><div class="panel"><b>Letters whose box is right</b>{head(A, ("cutter", "feeler", "equal"), "letter", "letter_ci")}</div>
<div class="panel"><b>Words where every letter's box is right</b>{head(A, ("cutter", "feeler", "equal"), "word", "word_ci")}</div></div>
<p class="lede">These are the words where the feeler read every joined piece as Azure does ({len(S["A"])} drawn; the feeler qualifies on about half of all words). Whiskers: 95% interval. Paired on these words: the cutter alone right on {pa["cutter_vs_equal"]["words_only_first"]} words, equal slices alone on {pa["cutter_vs_equal"]["words_only_second"]}; the feeler alone right against the cutter on {pa["feeler_vs_cutter"]["words_only_first"]}, the cutter alone on {pa["feeler_vs_cutter"]["words_only_second"]}.</p>

<div class="panel"><b>Allowing for the judge.</b> The judge accepted only {CAL["sep_true"]["both"]} of {CAL["sep_true"]["n"]} boxes that were right by construction, and wrongly accepted {CAL["sep_half"]["both"] + CAL["join_half"]["both"]} of {CAL["sep_half"]["n"] + CAL["join_half"]["n"]} half-letter-off boxes and {CAL["sep_whole"]["both"] + CAL["join_whole"]["both"]} of {CAL["sep_whole"]["n"] + CAL["join_whole"]["n"]} whole-letter-off ones. So it is strict: the bars above understate every method alike. Corrected for that (roughly), letters right: {corr}.</div>

<h2>All words, cutter against equal slices</h2>
<div class="grid2"><div class="panel"><b>Unseen pages, words the feeler misread</b> ({Bs["cutter"]["both"]["words"]} words) — letters right{head(Bs, ("cutter", "equal"), "letter", "letter_ci")}<br>words right{head(Bs, ("cutter", "equal"), "word", "word_ci")}</div>
<div class="panel"><b>The bundled fixture, 0582</b> ({Cs["cutter"]["both"]["words"]} words) — letters right{head(Cs, ("cutter", "equal"), "letter", "letter_ci")}<br>words right{head(Cs, ("cutter", "equal"), "word", "word_ci")}</div></div>

<h2>Can the judge tell? (calibration, before measuring)</h2>
<div class="panel"><div class="calib">{M.get("calibration_html", "")}</div>
<p class="lede">The judge is asked two questions about every box, separately: how the band sits on the named letter (exact / mostly / partly / other), and, without being told the letter, which letters the band covers. Right = both agree. Shown boxes that are right by construction (a letter that is its own piece of ink) and the same boxes moved off by a whole letter or by half a letter.</p></div>

<h2>Real words</h2>
<p class="legend"><span><i class="sw" style="background:rgba(47,111,214,.45)"></i><i class="sw" style="background:rgba(29,154,119,.45)"></i>a letter's box, judged right (colours alternate)</span><span><i class="sw" style="background:repeating-linear-gradient(45deg,rgba(217,58,43,.6) 0 4px,rgba(217,58,43,.2) 4px 8px)"></i>judged wrong</span> The letter under each box is the one it claims.</p>
{"".join(ex_html)}

<h2>Where each method fails</h2>
<div class="grid2">{"".join(failrow(m) and f'<div class="panel">{failrow(m)}</div>' for m in ("cutter", "feeler", "equal"))}</div>

<div class="panel"><b>The cutter's one systematic fault: a joined alef.</b> {alef}</div>

<h2>How it was measured</h2>
<div class="panel"><p>Words of 2–7 letters (no lam-alef, no vowel marks) from the bench books' pages that no method trained, tuned or tested on (0618 p1,16; 1036 p1,10; 0772 eight pages) and from the bundled fixture. <b>Cutter</b>: the glyph boxes read back out of today's built PDFs (an uncut piece sliced equally, as Chrome does). <b>Feeler</b>: experiment 16's hybrid reader, its cuts turned into boxes by the cutter's own rule, only on words it reads as Azure does. <b>Equal slices</b>: the word's width divided by its letters — what Chrome shows when a word is one glyph. The judge saw the scan (not our vector drawing), one letter's box tinted blue on the word's yellow paper, ink untouched; it never knew the method, and boxes identical between methods were judged once. Spend ${spend:.2f} of a $10 cap.</p></div>
</main></body></html>"""
    (OUT / "report.html").write_text(page)
    print("wrote", OUT / "report.html", f"{len(page) / 1e6:.2f} MB")


if __name__ == "__main__":
    main()
