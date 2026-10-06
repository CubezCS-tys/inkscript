"""out/summary.json + out/judged.json + calibration -> out/report.html (self-contained: crops embedded, light/dark, phone width)."""
import json, base64, html, sys
from pathlib import Path
from collections import defaultdict
import cv2
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import strata as S

s = json.load(open(OUT / "summary.json")); rows = json.load(open(OUT / "judged.json"))
cal = {m: json.load(open(OUT / "calibration" / f"{m}.json")) for m in ("gemini-3.8-flash", "gemini-3.1-pro-preview") if (OUT / "calibration" / f"{m}.json").exists()}
acal_p = OUT / "calibration" / "gemini-3.8-flash_archive.json"; acal = json.load(open(acal_p)) if acal_p.exists() else None
look = json.load(open(OUT / "look.json")) if (OUT / "look.json").exists() else {}
E = html.escape
pct = lambda x, d=1: "–" if x != x else f"{100 * x:.{d}f}%"


def img64(wid, h=64, maxw=620):
    im = cv2.imread(str(OUT / "crops" / (wid.replace(":", "_") + ".png")))
    if im is None: return ""
    sc = h / im.shape[0]; im = cv2.resize(im, (max(1, int(im.shape[1] * sc)), h), interpolation=cv2.INTER_AREA)
    if im.shape[1] > maxw:                                  # keep the yellow word in view: centre the cut on it
        c = im.shape[1] // 2; im = im[:, max(0, c - maxw // 2): c + maxw // 2]
    ok, b = cv2.imencode(".png", im)
    return f'<img alt="" src="data:image/png;base64,{base64.b64encode(b.tobytes()).decode()}">'


def interval_chart(items, xmax=None, unit_label="words with a letter error"):
    """Horizontal dot + 95% interval per row. items: (label, sub, block)."""
    xmax = xmax or max(0.02, max((b["hi"] for _, _, b in items if b["n"]), default=0.02) * 1.08)
    W, L, R, rowh = 760, 300, 30, 34; H = rowh * len(items) + 40; pw = W - L - R
    x = lambda v: L + pw * min(v, xmax) / xmax
    out = [f'<svg viewBox="0 0 {W} {H}" class="chart" role="img" aria-label="{E(unit_label)} by group, with 95% intervals">']
    step = 0.005 if xmax <= 0.04 else (0.01 if xmax <= 0.1 else 0.05)
    t = 0.0
    while t <= xmax + 1e-9:
        out.append(f'<line x1="{x(t):.1f}" x2="{x(t):.1f}" y1="8" y2="{H - 28}" class="grid"/><text x="{x(t):.1f}" y="{H - 10}" class="tick" text-anchor="middle">{100 * t:.1f}%</text>')
        t += step
    for k, (lab, sub, b) in enumerate(items):
        y = 22 + k * rowh
        out.append(f'<g class="row"><title>{E(lab)}: {b["errors"]} letter errors in {b["n"]} judged words ({b["docs"]} documents); weighted rate {pct(b["rate"], 2)}, 95% interval {pct(b["lo"], 2)} – {pct(b["hi"], 2)}</title>'
                   f'<rect x="0" y="{y - 14}" width="{W}" height="{rowh - 4}" class="hit"/>'
                   f'<text x="{L - 10}" y="{y - 1}" class="lab" text-anchor="end">{E(lab)}</text>'
                   f'<text x="{L - 10}" y="{y + 12}" class="sub" text-anchor="end">{E(sub)}</text>')
        if b["n"]:
            out.append(f'<line x1="{x(b["lo"]):.1f}" x2="{x(b["hi"]):.1f}" y1="{y}" y2="{y}" class="ci"/>'
                       f'<circle cx="{x(b["rate"]):.1f}" cy="{y}" r="5" class="dot"/>'
                       f'<text x="{min(x(b["hi"]) + 8, W - 4):.1f}" y="{y + 4}" class="val">{pct(b["rate"], 2 if b["rate"] < 0.01 else 1)}</text>')
        out.append("</g>")
    out.append("</svg>")
    return "".join(out)


o = s["overall"]
strata_items = sorted([(b["label"], f'{b["errors"]} of {b["n"]} judged · {pct(b["share"])} of the archive\'s words', b) for st, b in s["strata"].items() if b["n"]],
                      key=lambda t: -t[2]["rate"])
dec_items = [(d, f'{b["errors"]} of {b["n"]} judged · {b["docs"]} documents', b) for d, b in s["decades"].items() if b["n"]]

CAUSE_NAMES = [("misread", "ordinary word misread", 1), ("hamza added", "hamza added", 1), ("ya", "ى / ي", 1), ("superscript", "superscript numbers", 1),
               ("ligature", "ﷺ ligature", 1), ("encoding", "Persian code points", 1), ("latin", "Latin script", 1), ("speck", "specks read as words", 0),
               ("decorative", "calligraphy, ornaments, stamps", 0), ("handwriting", "handwriting", 0)]
KIND_NAME = {"dots": "dots (same skeleton, other dots)", "hamza": "hamza", "ya": "ى / ي", "ta": "ة / ه", "drop": "Azure dropped a letter",
             "add": "Azure added a letter", "edge": "first or last letter: Azure has it, the judge does not", "space": "split or merged words",
             "digits": "digits", "latin": "Latin script", "other": "more than one letter", "punct": "punctuation only (not counted)",
             "box": "Azure's box does not hold one word (not counted)", "unsure": "the ink cannot settle it (not counted)"}
cause_items = sorted([(dict((c, n) for c, n, _ in CAUSE_NAMES).get(c, c), f"{b['errors']} found", b) for c, b in s.get("cause_rates", {}).items()
                      if c not in ("judge wrong", "unsettled", "box")], key=lambda t: -t[2]["rate"])
by_kind = defaultdict(list)
for r in rows:
    if r["kind"]: by_kind[r["kind"]].append(r)

CAUSE = [("misread", "An ordinary printed word misread", True), ("hamza added", "Print has no hamza; Azure wrote one", True),
         ("ya", "ى / ي: Azure wrote the other one", True), ("superscript", "Superscript note numbers", True),
         ("ligature", "The ﷺ ligature", True), ("encoding", "Persian code points (looks right, breaks search)", True),
         ("latin", "Latin script: transliteration marks, order, maths", True), ("speck", "Specks, blobs, stray punctuation read as words", False),
         ("decorative", "Calligraphy, ornamental titles, stamps, white on black", False), ("handwriting", "Handwriting", False),
         ("box", "Boxing, not reading (counted by the judge, not by eye)", None), ("unsettled", "The ink does not settle it by eye", None),
         ("judge wrong", "The judge was wrong", None)]


def card(r):
    lk = look.get(r["id"])
    return (f'<figure class="ex">{img64(r["id"])}<figcaption><span class="az" dir="auto">Azure: <b>{E(r["text"])}</b></span>'
            f'<span class="ju" dir="auto">judge: <b>{E(r["judge"]) or "—"}</b></span>'
            f'<span class="meta">{E(S.LABEL[r["stratum"]])} · Azure conf {r["conf"] if r["conf"] is not None else "–"} · {E(r["doc"])} p{r["page"]}'
            f'{" · " + E(KIND_NAME.get(r["kind"], r["kind"] or "")) if r["kind"] else ""}</span></figcaption></figure>')


ex_html = []
for c, name, counted in CAUSE:
    v = sorted([r for r in rows if r.get("cause") == c], key=lambda r: (r["stratum"], r["id"]))
    if not v: continue
    tag = "" if counted is None else (' <span class="pill t">printed text</span>' if counted else ' <span class="pill n">not text</span>')
    ex_html.append(f'<h3>{E(name)} <span class="count">{len(v)}</span>{tag}</h3><div class="exs">{"".join(card(r) for r in v[:12])}</div>')
ex_html.append('<h2>Not counted as letter errors</h2><p class="note">Punctuation only, boxing faults (Azure\'s box holds part of a word or two words), and ink the judge could not settle. A few of each.</p>')
for k in ("punct", "box", "unsure"):
    v = sorted(by_kind.get(k, []), key=lambda r: r["id"])
    if v: ex_html.append(f'<h3>{E(KIND_NAME[k])} <span class="count">{len(v)}</span></h3><div class="exs">{"".join(card(r) for r in v[:6])}</div>')

def cal_rows():
    out = []
    for m, c in cal.items():
        sm = c["summary"]; t = sm["true (false alarm = not RIGHT)"]; p = sm["perturbed (miss = not WRONG)"]
        out.append(f'<tr><td>{E(m)}</td><td>{t["n"] - t["ok"]} / {t["n"]}</td><td>{p["n"] - p["ok"]} / {p["n"]}</td><td>{p["gave_back"]} / {p["n"]}</td></tr>')
    return "".join(out)


def acal_rows():
    if not acal: return ""
    out = []
    for k, v in acal["summary"].items():
        if k.startswith("perturbed in"):
            st = k.replace("perturbed in ", ""); out.append(f'<tr><td>{E(S.LABEL.get(st, st))}</td><td>{v["n"] - v["ok"]} / {v["n"]}</td></tr>')
    p = acal["summary"]["perturbed (miss = not WRONG)"]
    out.append(f'<tr class="tot"><td>all</td><td>{p["n"] - p["ok"]} / {p["n"]}</td></tr>')
    return "".join(out)


conf = s["confidence"]
conf_rows = "".join(f'<tr><td>&lt; {t["t"]}</td><td>{pct(t["flagged_share"])}</td><td>{pct(t["recall"], 0)}</td><td>{pct(t["precision"])}</td></tr>' for t in conf["thresholds"])
cause_n = s.get("causes", {})
dk = s["docs"]["kinds"]; drawn = s["docs"]["drawn"]

page = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Azure Error Map</title>
<style>
:root{{color-scheme:light;--bg:#fcfcfb;--card:#ffffff;--ink:#0b0b0b;--ink2:#52514e;--ink3:#8a897f;--line:#e4e3dd;--acc:#2a78d6;--warn:#eb6834;--paper:#ffffff}}
@media (prefers-color-scheme:dark){{:root:not([data-theme="light"]){{color-scheme:dark;--bg:#1a1a19;--card:#232321;--ink:#fff;--ink2:#c3c2b7;--ink3:#8f8e85;--line:#3a3936;--acc:#3987e5;--warn:#d95926}}}}
:root[data-theme="dark"]{{color-scheme:dark;--bg:#1a1a19;--card:#232321;--ink:#fff;--ink2:#c3c2b7;--ink3:#8f8e85;--line:#3a3936;--acc:#3987e5;--warn:#d95926}}
*{{box-sizing:border-box}} body{{margin:0;background:var(--bg);color:var(--ink);font:16px/1.55 system-ui,-apple-system,"Segoe UI",sans-serif}}
main{{max-width:980px;margin:0 auto;padding:24px 16px 64px}}
h1{{font-size:1.7rem;margin:0 0 .3rem}} h2{{margin-top:2.4rem;font-size:1.25rem;border-top:1px solid var(--line);padding-top:1.2rem}} h3{{font-size:1.02rem;margin:1.6rem 0 .5rem}}
.lede{{color:var(--ink2);max-width:46em}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(190px,1fr));gap:12px;margin:20px 0}}
.tile{{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 14px}} .tile b{{display:block;font-size:1.6rem}} .tile span{{color:var(--ink2);font-size:.88rem}}
.chart{{width:100%;min-width:640px;height:auto;display:block}} .chart .grid{{stroke:var(--line)}} .chart .tick,.chart .sub{{fill:var(--ink3);font-size:11px}}
.chart .lab{{fill:var(--ink);font-size:13px}} .chart .val{{fill:var(--ink2);font-size:12px}} .chart .ci{{stroke:var(--acc);stroke-width:2;stroke-linecap:round}}
.chart .dot{{fill:var(--acc);stroke:var(--bg);stroke-width:2}} .chart .hit{{fill:transparent}} .chart .row:hover .hit{{fill:var(--line);opacity:.45}}
.scroll{{overflow-x:auto}} table{{border-collapse:collapse;font-size:.92rem;margin:.6rem 0}} td,th{{border-bottom:1px solid var(--line);padding:5px 10px;text-align:left;vertical-align:top}} th{{color:var(--ink2);font-weight:600}}
tr.tot td{{font-weight:600}}
.exs{{display:grid;grid-template-columns:repeat(auto-fill,minmax(300px,1fr));gap:10px}}
.ex{{margin:0;background:var(--card);border:1px solid var(--line);border-radius:10px;padding:8px;overflow:hidden}}
.ex img{{display:block;max-width:100%;height:auto;border-radius:4px;background:var(--paper)}}
.ex figcaption{{display:flex;flex-direction:column;gap:1px;margin-top:6px;font-size:.9rem}}
.az b,.ju b{{font-size:1.1rem;font-family:"Noto Naskh Arabic","Amiri","Geeza Pro",serif}} .ju b{{color:var(--warn)}} .meta{{color:var(--ink3);font-size:.78rem}} .look{{color:var(--ink2)}}
.count{{color:var(--ink3);font-weight:400}} .more{{color:var(--ink3);font-size:.85rem}} .note{{color:var(--ink2);font-size:.92rem;max-width:46em}}
code{{font-size:.88em}} .pill{{font-size:.72rem;font-weight:500;border-radius:99px;padding:1px 8px;margin-left:6px;border:1px solid var(--line);color:var(--ink2)}} .pill.n{{border-style:dashed}}
</style></head><body><main>
<h1>Where does Azure's reading fail?</h1>
<p class="lede">{drawn} documents drawn at random from the Mandumah corpus (1,013,912 documents). {s['n_docs']} of them are scans; {s['n_words']:,} of their words were
drawn by where they sit on the page and judged one by one on the ink by Gemini (calibrated below). A <i>letter error</i> is any word whose letters,
dots, hamza or digits differ from the print; punctuation, short vowels and boxing faults are counted apart. Experiment 19, 2026-10-06.</p>

<div class="tiles">
<div class="tile"><b>{pct(o['rate'], 2)}</b><span>of words in scanned documents carry a letter error (95%: {pct(o['lo'], 2)} – {pct(o['hi'], 2)}), weighted to the archive's mix</span></div>
<div class="tile"><b>{pct(dk.get('born-digital', 0) / drawn, 0)}</b><span>of documents drawn are born-digital ({dk.get('born-digital', 0)} of {drawn}): typeset text, no OCR needed</span></div>
<div class="tile"><b>{o['errors']}</b><span>letter errors found in {s['n_words']:,} judged words; {s['box']['errors']} more were boxing faults</span></div>
<div class="tile"><b>{pct(s['printed_arabic']['rate'], 2)}</b><span>of words are <i>printed Arabic</i> read wrong, by eye (95%: {pct(s['printed_arabic']['lo'], 2)} – {pct(s['printed_arabic']['hi'], 2)}); the rest of the errors are specks, ornaments, handwriting and Latin</span></div>
<div class="tile"><b>{conf['auc']:.2f}</b><span>how well Azure's own confidence ranks its errors (AUC; 0.5 = chance, 1 = perfect)</span></div>
</div>

<h2>Error rate by place on the page</h2>
<p class="note">Dot = weighted rate, bar = 95% interval (bootstrap over documents). Sorted worst first. Place is read from geometry (Azure gives no roles):
"small print" and "large print" are by line size, so they hold more than footnotes and headings (tables, captions, signatures). Hover a row for the counts.
Each judged word stands for all the words of its kind in its document, so one long document weighs a lot: body text's 1.3% is 7 errors in 655 words, and one
partly handwritten document (0679-000-014-004, 17,296 words) alone is 0.5 points of it. Read the raw counts beside the dots.</p>
<div class="scroll">{interval_chart(strata_items)}</div>

<h2>What causes them</h2>
<p class="note">Each judged error looked at by eye and given a cause. Rate = share of the archive's words (weighted), 95% interval.</p>
<div class="scroll">{interval_chart(cause_items)}</div>

<h2>By decade of publication</h2>
<p class="note">Year from the corpus's own catalogue (MARC field 260c). Few documents per decade: wide intervals.</p>
<div class="scroll">{interval_chart(dec_items)}</div>
<p class="note">Scans with only Azure's font: {s['print']['scan']['errors']} errors in {s['print']['scan']['n']} words ({pct(s['print']['scan']['rate'], 2)});
typeset pages whose fonts give no usable text (Azure read the rendered page): {s['print']['scan+real-font']['errors']} in {s['print']['scan+real-font']['n']} ({pct(s['print']['scan+real-font']['rate'], 2)}).</p>

<h2>The judge, and how far to trust it</h2>
<p class="note">Shown one reading (Azure's, not named) and asked whether it is exactly what the ink says, else what the ink says. Calibrated on the owner's hand-marked pages
(experiment 12): 100 words marked right, shown as they are (a "wrong" verdict = false alarm), and 100 more shown with one mark changed (a "right" verdict = miss).</p>
<div class="scroll"><table><tr><th>model</th><th>false alarms</th><th>misses</th><th>gave back the true word</th></tr>{cal_rows()}</table></div>
<p class="note">The archive was judged by Flash; every word Flash did not call right went to Pro for a second opinion ({s['flash_pro']['flagged_by_flash']} words; Pro cleared {s['flash_pro']['pro_cleared']}).
Misses on the archive's own prints — judged words shown again with one mark changed:</p>
<div class="scroll"><table><tr><th>stratum</th><th>missed</th></tr>{acal_rows()}</table></div>

<h2>Does Azure's confidence find the errors?</h2>
<p class="note">AUC {conf['auc']:.2f} over {conf['n']} words with {conf['errors']} letter errors. If the archive flagged every word under a threshold:</p>
<div class="scroll"><table><tr><th>confidence</th><th>words flagged</th><th>errors caught</th><th>flagged words that are wrong</th></tr>{conf_rows}</table></div>

<h2>The errors, on the ink</h2>
<p class="note">Every crop is the scan at 300 dpi, the word's paper tinted yellow, nothing drawn on the ink. The judge's {o['errors']} letter errors, each looked at by eye by the agent (not the owner) and grouped by what caused it.
"Printed text" = the error a reader of the text meets; "not text" = ink that is not running text, which Azure turned into words anyway.</p>
{''.join(ex_html)}

<h2>Also</h2>
<p class="note">Encoding: {s['encoding_slips']['slips']} of {s['encoding_slips']['words']:,} words in the scanned documents ({s['encoding_slips']['docs_with']} documents) use a Persian/Urdu code point
(ی ک ہ ھ …) that looks like an Arabic letter but breaks search — checked in code over every word, no judge needed.
Short vowels: on {s['harakat']['n']} vowelled words whose letters were right, the judge said the marks differ from the print on {s['harakat']['differ']} (not calibrated).</p>
<p class="note">Spend: ${s['spend']:.2f}. Code and method: <code>experiments/19_azure_map/README.md</code>.</p>
</main></body></html>"""
(OUT / "report.html").write_text(page)
print("wrote", OUT / "report.html", f"{len(page) / 1e6:.1f} MB")
