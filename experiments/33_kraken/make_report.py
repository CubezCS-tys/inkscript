"""The owner's page: out/report.html (self-contained; images embedded).

    out/env/bin/python make_report.py
Reads out/results.json (evaluate.py with every tag), out/preds/, out/segeval/, out/vlm/score.json,
out/gpu_spend.jsonl, the line images, and the words around the numbers from report_text.json beside this script.
"""
import base64, html, io, json, random, sys
from pathlib import Path
from PIL import Image, ImageDraw
sys.path.insert(0, str(Path(__file__).resolve().parent))
from textnorm import faithful, is_arabic_line
from rapidfuzz.distance import Levenshtein

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); HERE = Path(__file__).resolve().parent
R = json.load(open(OUT / "results.json"))
TXT = json.load(open(HERE / "report_text.json")) if (HERE / "report_text.json").exists() else {}
BEST = TXT.get("best", "ftB")                                          # the fine-tuned VGSL model shown as "after"
PP = TXT.get("pp", "ppB")
MODELS = TXT.get("models", ["base", "pp0", "cpuq", "ftA", "ppA", "ftB", "ppB"])
NAMES = {"base": "Kraken out of the box (OpenITI print model)", "pp0": "PP-OCRv6 small out of the box",
         "cpuq": "Kraken, a quarter epoch on CPU (1 h)", "ftA": "Kraken round A (born-digital lines, GPU)",
         "ppA": "PP-OCRv6 round A (born-digital lines, GPU)", "ftB": "Kraken round B (+ real scan lines read by Azure)",
         "ppB": "PP-OCRv6 round B (+ real scan lines read by Azure)", "ftC": "Kraken round C (+ old prints, footnotes, vowelled)",
         "azure": "Azure"}
SERIES = [("base", "before"), (BEST, "after"), (PP, "pp"), ("azure", "azure")]


def img64(im, h=None, q=80):
    im = im if isinstance(im, Image.Image) else Image.open(im)
    im = im.convert("RGB") if im.mode not in ("L", "RGB") else im
    if h:
        im = im.resize((max(1, int(im.width * h / im.height)), h), Image.LANCZOS)
    b = io.BytesIO(); im.save(b, "JPEG", quality=q)
    return "data:image/jpeg;base64," + base64.b64encode(b.getvalue()).decode()


def marked(ref, hyp):
    ref, hyp = faithful(ref), faithful(hyp or "")
    if not hyp:
        return '<span class="miss">(nothing read)</span>'
    out = []
    for tag, i1, i2, j1, j2 in Levenshtein.opcodes(ref, hyp):
        seg = html.escape(hyp[j1:j2])
        if tag == "equal":
            out.append(seg)
        elif tag in ("replace", "insert"):
            out.append(f'<span class="bad">{seg if seg.strip() else "&#x2423;"}</span>')
        else:
            out.append(f'<span class="gap" title="missing: {html.escape(ref[i1:i2])}">&#x2038;</span>')
    return "".join(out)


def card(src, gold, gold_label, rows, meta):
    h = [f'<div class="ex"><div class="meta">{meta}</div><img src="{src}" alt="line image">',
         f'<div class="t gold"><span class="who">{gold_label}</span><span class="txt" dir="rtl">{gold}</span></div>']
    for who, txt, c in rows:
        h.append(f'<div class="t"><span class="who">{who} <small>{pct(c)}</small></span><span class="txt" dir="rtl">{txt}</span></div>')
    return "\n".join(h + ["</div>"])


def cer(ref, hyp):
    g = faithful(ref); return Levenshtein.distance(g, faithful(hyp or "")) / max(len(g), 1)


def pct(x, d=1):
    return "–" if x is None else f"{100 * x:.{d}f}%"


def g(d, *ks):
    for k in ks:
        if not isinstance(d, dict) or k not in d:
            return None
        d = d[k]
    return d


def trip(x):
    return (x["rate"], x["lo"], x["hi"]) if isinstance(x, dict) and x.get("rate") is not None else (None, None, None)


def bars(title, rows, note=""):
    vals = [v for _, v, lo, hi, _ in rows if v is not None] + [hi for _, v, lo, hi, _ in rows if hi is not None]
    top = max(vals + [0.001]) * 1.4
    out = [f'<figure class="bars"><figcaption>{title}</figcaption>']
    for label, v, lo, hi, cls in rows:
        if v is None:
            out.append(f'<div class="row"><span class="lab">{label}</span><span class="track"><span class="na">not measured here</span></span></div>'); continue
        w = 100 * v / top
        ci = f'<span class="ci" style="left:{100 * lo / top:.2f}%;width:{max(0.2, 100 * (hi - lo) / top):.2f}%"></span>' if lo is not None else ""
        lab = f'{pct(v)}' + (f' <small>[{pct(lo)}–{pct(hi)}]</small>' if lo is not None else "")
        out.append(f'<div class="row"><span class="lab">{label}</span><span class="track"><span class="bar {cls}" style="width:{w:.2f}%"></span>{ci}'
                   f'<span class="val" style="left:calc({100 * max(v, hi or 0) / top:.2f}% + 6px)">{lab}</span></span></div>')
    if note:
        out.append(f'<p class="note">{note}</p>')
    out.append("</figure>")
    return "\n".join(out)


bd = R["born_digital_lines"]; sw = R.get("scan_words", {}); pg = R.get("pages", {})
SHORT = {"base": "Kraken, out of the box", BEST: "Kraken, fine-tuned", PP: "PP-OCRv6, fine-tuned", "azure": "Azure"}


def panel_bd(var, sub="arabic", norm="faithful"):
    rows = []
    for t, cls in SERIES:
        key = f"{t}/{var}" if t != "azure" else ("azure/clean" if var == "clean" else None)
        rows.append((SHORT[t], *(trip(g(bd, key, sub, norm, "cer")) if key else (None, None, None)), cls))
    return rows


def panel_sw(grp):
    rows = []
    for t, cls in SERIES:
        x = g(sw, BEST if t == "azure" else t, "unweighted", grp, "azure" if t == "azure" else "kraken")
        rows.append((SHORT[t], *trip(x), cls))
    return rows


def panel_sil(grp="all"):
    return [(SHORT[t], *trip(g(sw, t, "silver_lines", "faithful", grp, "cer")), cls) for t, cls in SERIES if t != "azure"]


def panel_pages():
    return [(SHORT[t], *trip(g(pg, f"{t}/scan_silver", "all", "faithful", "cer")), cls) for t, cls in SERIES if t != "azure"]


sec = []
sec.append(bars("1 · Born-digital lines, clean: characters wrong (faithful: every vowel mark and hamza counts)", panel_bd("clean"),
                f"Truth: the PDF's own text. {bd['n_lines']:,} lines of {bd['n_docs']} documents from {bd['n_journals']} journals no training line came from."))
sec.append(bars("2 · The same lines as scan-like copies (blur, noise, tint, ink spread, JPEG): characters wrong", panel_bd("deg"),
                "Azure read the clean pages only; it never saw these copies."))
sec.append(bars("3 · Real scans: experiment 19's judged words, read wrong", panel_sw("all"),
                "Truth on the ink: Azure's word where the blind Gemini judge said right, the judge's reading where it said wrong. 2,894 words of 139 scanned documents, 1930s–2020s, oversampling titles, numbers and Latin, so harder than an average page. Letters and hamza count; short vowels, kashida, punctuation and ى/ي do not."))
sec.append(bars("4 · The same, body text only", panel_sw("stratum:body")))
sec.append(bars("5 · The same, printed before 2000", panel_sw("pre2000")))
sec.append(bars("6 · Real scan lines against Azure's reading of them (silver: Azure's own errors count against Kraken)", panel_sil()))
sec.append(bars("7 · Whole scanned pages, each reader finding its own lines, against Azure's lines (silver)", panel_pages(),
                "Missed and invented lines included. One page per scanned document of experiment 19 (139 pages)."))

# the full table
def row(t):
    c = lambda key, sub="arabic": pct(g(bd, key, sub, "faithful", "cer", "rate"))
    cs = lambda key, sub="arabic": pct(g(bd, key, sub, "search", "cer", "rate"))
    w = lambda key: pct(g(bd, key, "arabic", "faithful", "wer", "rate"))
    if t == "azure":
        return (f"<tr><td>{NAMES[t]}</td><td>{c('azure/clean')}</td><td>{cs('azure/clean')}</td><td>{w('azure/clean')}</td><td>–</td>"
                f"<td>{pct(g(sw, BEST, 'unweighted', 'all', 'azure', 'rate'))}</td><td>{pct(g(sw, BEST, 'unweighted', 'pre2000', 'azure', 'rate'))}</td>"
                f"<td>{pct(g(sw, BEST, 'unweighted', 'stratum:body', 'azure', 'rate'))}</td><td>(reference)</td><td>{pct(g(pg, 'azure', 'clean', 'faithful', 'cer', 'rate'))}</td><td>(reference)</td></tr>")
    s = lambda grp: pct(g(sw, t, "unweighted", grp, "kraken", "rate"))
    return (f"<tr><td>{NAMES.get(t, t)}</td><td>{c(t + '/clean')}</td><td>{cs(t + '/clean')}</td><td>{w(t + '/clean')}</td><td>{c(t + '/deg')}</td>"
            f"<td>{s('all')}</td><td>{s('pre2000')}</td><td>{s('stratum:body')}</td><td>{pct(g(sw, t, 'silver_lines', 'faithful', 'all', 'cer', 'rate'))}</td>"
            f"<td>{pct(g(pg, t, 'clean', 'faithful', 'cer', 'rate'))}</td><td>{pct(g(pg, t + '/scan_silver', 'all', 'faithful', 'cer', 'rate'))}</td></tr>")


table = ("<table class='wide'><tr><th>reader</th><th>born-digital clean, CER</th><th>… search-folded</th><th>… WER</th><th>scan-like copies, CER</th>"
         "<th>scan words wrong</th><th>… pre-2000</th><th>… body text</th><th>scan lines vs Azure, CER</th><th>born-digital pages, CER</th><th>scan pages vs Azure, CER</th></tr>"
         + "".join(row(t) for t in MODELS + ["azure"]) + "</table>")

kinds = ["body", "footnote", "heading", "vowelled", "numbers", "latin"]
krows = "".join(f"<tr><td>{k}</td><td>{g(bd, 'azure/clean', 'kind:' + k, 'faithful', 'lines')}</td>" + "".join(
    f"<td>{pct(g(bd, key, 'kind:' + k, 'faithful', 'cer', 'rate'))}</td>" for key in ("base/clean", f"{BEST}/clean", f"{PP}/clean", "azure/clean", "base/deg", f"{BEST}/deg", f"{PP}/deg")) + "</tr>" for k in kinds)
strata = ["body", "p1_body", "footnote", "vowelled", "header", "heading", "p1_title", "number", "latin"]
srows = "".join(f"<tr><td>{s}</td><td>{int(g(sw, 'base', 'unweighted', 'stratum:' + s, 'kraken', 'n') or 0)}</td>" + "".join(
    f"<td>{pct(g(sw, t, 'unweighted', 'stratum:' + s, 'kraken', 'rate'))}</td>" for t in MODELS if t in sw) +
    f"<td>{pct(g(sw, BEST, 'unweighted', 'stratum:' + s, 'azure', 'rate'))}</td></tr>" for s in strata)
shead = "".join(f"<th>{t}</th>" for t in MODELS if t in sw)

# ---------------------------------------------------------------- line finder
seg_html = ""
SE = {t: json.load(open(OUT / "segeval" / f"{t}.json")) for t in ("blla", TXT.get("seg", "segcpu")) if (OUT / "segeval" / f"{t}.json").exists()}
if SE:
    names = {"blla": "kraken's default line finder", TXT.get("seg", "segcpu"): "fine-tuned on Mandumah pages"}
    rws = "".join(f"<tr><td>{names[t]}</td><td>{v['summary']['silver']:,}</td><td>{pct(v['summary']['found_share'])}</td><td>{pct(v['summary']['missed_share'])}</td>"
                  f"<td>{pct(v['summary']['merged_share'])}</td><td>{pct(v['summary']['split_share'])}</td><td>{v['summary']['extra']}</td>"
                  f"<td>{pct(v['summary']['baseline_dist_median'])}</td><td>{pct(v['summary']['within_quarter_height'])}</td></tr>" for t, v in SE.items())
    seg_html = (f"<table><tr><th>line finder</th><th>Azure lines</th><th>found</th><th>missed</th><th>merged</th><th>split</th><th>extra</th>"
                f"<th>baseline off by (median, share of line height)</th><th>baselines within a quarter of the height</th></tr>{rws}</table>")
    # pages drawn: Azure's lines (blue boxes) and each finder's baselines
    sys.path.insert(0, str(HERE)); from seg_look import read_xml
    pages = TXT.get("seg_pages") or sorted((OUT / "segeval" / "blla").glob("*.json"))[:3]
    for pname in [Path(p).stem for p in pages]:
        xml = OUT / "seg" / "test" / f"{pname}.xml"
        if not xml.exists():
            continue
        img, silver = read_xml(xml); cells = []
        for t in SE:
            pj = OUT / "segeval" / t / f"{pname}.json"
            if not pj.exists():
                continue
            im = Image.open(img).convert("RGB"); d = ImageDraw.Draw(im)
            for l in silver:
                d.polygon(l["boundary"], outline=(120, 140, 230))
            for l in json.load(open(pj))["lines"]:
                d.line([tuple(p) for p in l["baseline"]], fill=(220, 40, 40) if t == "blla" else (20, 150, 60), width=3)
            r = SE[t]["pages"].get(pname, {})
            cells.append(f'<figure class="pg"><img src="{img64(im, 900, 70)}" alt="page"><figcaption>{names[t]}: found {r.get("found")}, missed {r.get("missed")}, merged {r.get("merged")}, split {r.get("split")}, extra {r.get("extra")} of {r.get("silver")}</figcaption></figure>')
        seg_html += f'<div class="pair">{"".join(cells)}</div>'

# ---------------------------------------------------------------- VLM
vlm_html = ""
if (OUT / "vlm" / "score.json").exists():
    V = json.load(open(OUT / "vlm" / "score.json"))
    L = V["lines"]; P = V["pages"]
    vlm_html = (f"<table><tr><th></th><th>scan lines: characters different from Azure</th><th>judged words wrong</th></tr>"
                + "".join(f"<tr><td>{k}</td><td>{pct(v.get('cer_vs_azure'))}</td><td>{pct(v.get('judged_word_wrong'))}</td></tr>" for k, v in L.items())
                + "</table><table><tr><th></th><th>pages: Azure's words left out</th><th>words Azure never read</th><th>longest repeated 4-word run</th></tr>"
                + "".join(f"<tr><td>{k}</td><td>{pct(v['skipped'])}</td><td>{pct(v['invented'])}</td><td>{v['max_loop']}</td></tr>" for k, v in P.items()) + "</table>")
    ex = V["examples"]; random.Random(4).shuffle(ex)
    for e in ex[:6]:
        img = OUT / "scan" / "img" / f"{e['id']}.png"
        vlm_html += card(img64(img, 58), html.escape(faithful(e["azure"])), "Azure's line (silver)",
                         [("PaddleOCR-VL", marked(e["azure"], e["vlm"]), cer(e["azure"], e["vlm"])),
                          (SHORT[BEST], marked(e["azure"], e.get(BEST, "")), cer(e["azure"], e.get(BEST, "")))],
                         f"{e['id']} · stratum {e['stratum']}")
    runaway = [json.loads(l) for l in open(OUT / "vlm" / "vlm_out.jsonl") if '"page"' in l]
    runaway = max(runaway, key=lambda r: r["new_tokens"]) if runaway else None
    if runaway:
        vlm_html += (f'<p class="note">The page that ran away: {runaway["id"]}, {runaway["new_tokens"]} tokens in {runaway["seconds"]:.0f} s '
                     f'(the cap). Its first lines:</p><pre class="vlm" dir="rtl">{html.escape(runaway["text"][:420])}</pre>')

# ---------------------------------------------------------------- examples
def load(p):
    return {Path(j["img"]).name: j.get("text") or "" for j in map(json.loads, open(p))} if Path(p).exists() else {}


data = [json.loads(l) for l in open(OUT / "data.jsonl")]
test = [r for r in data if r["split"] == "test" and not r.get("suspect") and is_arabic_line(r["gold"]) and len(faithful(r["gold"])) > 25]
P = {(t, v): load(OUT / "preds" / f"test_{v}_{t}.jsonl") for t in ("base", BEST, PP) for v in ("clean", "deg")}
scan = [json.loads(l) for l in open(OUT / "scan" / "scan.jsonl")]
S = {t: load(OUT / "preds" / f"scan_{t}.jsonl") for t in ("base", BEST, PP)}


def ex_bd(r, v):
    suf = ".png" if v == "clean" else "_d.jpg"; k = r["id"] + suf
    rows = [(SHORT[t], marked(r["gold"], P[(t, v)].get(k, "")), cer(r["gold"], P[(t, v)].get(k, ""))) for t in ("base", BEST, PP)]
    if v == "clean":
        rows.append(("Azure", marked(r["gold"], r["azure"]), cer(r["gold"], r["azure"])))
    return card(img64(OUT / "img" / "test" / k, 58), html.escape(faithful(r["gold"])), "the PDF's own text", rows,
                f'{r["doc"]} p{r["page"]} · {r["kind"]} · {"clean render" if v == "clean" else "scan-like copy"}')


def ex_scan(r):
    k = r["id"] + ".png"
    rows = [(SHORT[t], marked(r["line"], S[t].get(k, "")), cer(r["line"], S[t].get(k, ""))) for t in ("base", BEST, PP)]
    word = f' · judged word «{html.escape(r["word"])}»: ' + ("Azure right" if not r["err"] else f'Azure WRONG, the ink says «{html.escape(r["truth"] or "")}»')
    return card(img64(OUT / "scan" / "img" / k, 58), html.escape(faithful(r["line"])), "Azure's line (silver)", rows,
                f'{r["doc"]} p{r["page"]} · printed {r["year"] or "?"} · stratum {r["stratum"]}{word}')


rng = random.Random(33)
arab = [r for r in scan if is_arabic_line(r["line"]) and len(r["line"]) > 25 and r["id"] + ".png" in S[BEST]]
pick = lambda xs, n: rng.sample(xs, min(n, len(xs)))
old = [r for r in arab if (r["year"] or 3000) < 1980 and r["stratum"] in ("body", "p1_body", "footnote")]
mid = [r for r in arab if 1980 <= (r["year"] or 0) < 2000 and r["stratum"] in ("body", "p1_body", "footnote")]
new = [r for r in arab if (r["year"] or 0) >= 2000 and r["stratum"] in ("body", "p1_body", "footnote")]
vow = [r for r in arab if r["stratum"] == "vowelled"]
azw = [r for r in arab if r["err"]]
scan_ex = ("<h3>Body text and footnotes printed before 1980</h3>" + "".join(ex_scan(r) for r in pick(old, 4))
           + "<h3>1980–1999</h3>" + "".join(ex_scan(r) for r in pick(mid, 3))
           + "<h3>2000 and later</h3>" + "".join(ex_scan(r) for r in pick(new, 3))
           + "<h3>Vowelled</h3>" + "".join(ex_scan(r) for r in pick(vow, 3))
           + "<h3>Lines where Azure itself misread the judged word</h3>" + "".join(ex_scan(r) for r in pick(azw, 4)))
have = [r for r in test if r["id"] + "_d.jpg" in P[(BEST, "deg")]]
gain = sorted(have, key=lambda r: cer(r["gold"], P[(BEST, "deg")][r["id"] + "_d.jpg"]) - cer(r["gold"], P[("base", "deg")][r["id"] + "_d.jpg"]))
worse = [r for r in gain[::-1][:20] if cer(r["gold"], P[(BEST, "deg")][r["id"] + "_d.jpg"]) > cer(r["gold"], P[("base", "deg")][r["id"] + "_d.jpg"])][:3]
bd_ex = ("<h3>Scan-like copies, at random</h3>" + "".join(ex_bd(r, "deg") for r in pick(have, 5))
         + "<h3>Where fine-tuning helped most</h3>" + "".join(ex_bd(r, "deg") for r in gain[:3])
         + "<h3>Where it made things worse</h3>" + ("".join(ex_bd(r, "deg") for r in worse) or "<p>None.</p>")
         + "<h3>Clean renders, at random (Azure too)</h3>" + "".join(ex_bd(r, "clean") for r in pick(have, 4)))

# ---------------------------------------------------------------- GPU spend
spend = [json.loads(l) for l in open(OUT / "gpu_spend.jsonl")]
ends = [e for e in spend if e["event"] == "end"]
sp_rows = "".join(f"<tr><td>{e['instance']}</td><td>{e['time'][11:16]}</td><td>{e.get('hours', 0):.2f} h</td><td>${e.get('cost', 0):.2f}</td><td>{html.escape(e.get('jobs', ''))}</td></tr>" for e in ends)
sp_html = (f"<table><tr><th>instance</th><th>ended</th><th>time</th><th>cost</th><th>what ran</th></tr>{sp_rows}</table>"
           f"<p class='note'>{TXT.get('spend_note', '')}</p>")

body = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Kraken on Mandumah</title>
<style>
:root {{ --bg:#fcfcfb; --ink:#0b0b0b; --ink2:#52514e; --line:#e4e2dc; --before:#eb6834; --after:#2a78d6; --pp:#6250d6; --azure:#1baf7a; --bad:#fde2e1; --badink:#b42318; --card:#fff; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3936; --before:#d95926; --after:#3987e5; --pp:#9085e9; --azure:#199e70; --bad:#5a1e1b; --badink:#ffb4ab; --card:#232321; }} }}
:root[data-theme="dark"] {{ --bg:#1a1a19; --ink:#f0efec; --ink2:#c3c2b7; --line:#3a3936; --before:#d95926; --after:#3987e5; --pp:#9085e9; --azure:#199e70; --bad:#5a1e1b; --badink:#ffb4ab; --card:#232321; }}
body {{ background:var(--bg); color:var(--ink); font:15px/1.5 system-ui,sans-serif; margin:0 auto; max-width:1100px; padding:16px; }}
h1 {{ font-size:1.6rem; margin:.2em 0; }} h2 {{ margin-top:2em; border-bottom:1px solid var(--line); padding-bottom:.2em; }}
p, li {{ max-width:78ch; }} .note {{ color:var(--ink2); font-size:.85rem; margin:.3em 0 0; }} .meta {{ color:var(--ink2); font-size:.8rem; }}
.lede {{ font-size:1.02rem; background:var(--card); border:1px solid var(--line); border-radius:8px; padding:12px 16px; }}
figure.bars {{ margin:18px 0; }} figcaption {{ font-weight:600; margin-bottom:6px; }}
.row {{ display:flex; align-items:center; gap:10px; margin:4px 0; }} .lab {{ width:170px; flex:none; color:var(--ink2); font-size:.88rem; }}
.track {{ position:relative; flex:1; height:26px; }}
.bar {{ position:absolute; left:0; top:3px; height:20px; border-radius:0 4px 4px 0; }}
.bar.before {{ background:var(--before); }} .bar.after {{ background:var(--after); }} .bar.pp {{ background:var(--pp); }} .bar.azure {{ background:var(--azure); }}
.ci {{ position:absolute; top:12px; height:2px; background:var(--ink2); opacity:.75; }}
.val {{ position:absolute; top:3px; font-size:.85rem; white-space:nowrap; }} .val small {{ color:var(--ink2); }}
.na {{ color:var(--ink2); font-size:.85rem; position:absolute; left:0; top:4px; }}
table {{ border-collapse:collapse; margin:10px 0; font-size:.86rem; }} td, th {{ border-bottom:1px solid var(--line); padding:4px 8px; text-align:right; vertical-align:top; }}
th {{ color:var(--ink2); font-weight:600; }} td:first-child, th:first-child {{ text-align:left; }}
.scroll {{ overflow-x:auto; }}
.ex {{ background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px; margin:12px 0; overflow-x:auto; }}
.ex img {{ display:block; max-width:100%; height:auto; margin:4px 0 6px auto; background:#fff; }}
.t {{ display:flex; gap:10px; align-items:baseline; padding:2px 0; }} .who {{ width:150px; flex:none; font-size:.8rem; color:var(--ink2); }}
.txt {{ font-size:1.15rem; flex:1; text-align:right; font-family:"Noto Naskh Arabic","Amiri","Traditional Arabic",serif; }}
.gold .txt {{ font-weight:600; }} .bad {{ background:var(--bad); color:var(--badink); border-radius:2px; }} .gap {{ color:var(--badink); font-weight:700; }} .miss {{ color:var(--badink); }}
.key span {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:middle; margin:0 4px 0 12px; }}
.pair {{ display:flex; gap:12px; flex-wrap:wrap; }} figure.pg {{ flex:1 1 420px; margin:8px 0; }} figure.pg img {{ width:100%; height:auto; border:1px solid var(--line); }}
figure.pg figcaption {{ font-weight:400; font-size:.85rem; color:var(--ink2); }}
pre.vlm {{ white-space:pre-wrap; background:var(--card); border:1px solid var(--line); padding:8px; font-family:"Noto Naskh Arabic",serif; }}
@media (max-width:640px) {{ .lab {{ width:96px; }} .who {{ width:90px; }} }}
</style></head><body>
<h1>An open line reader for Mandumah: Kraken, fine-tuned</h1>
<p class="meta">Experiment 33 · 2026-10-11/12 · kraken 7.1.1 · CPU on this machine, training also on rented RTX 5090s</p>
<div class="lede">{TXT.get("lede", "")}</div>
<p class="key">Bars: <span style="background:var(--before)"></span>Kraken out of the box <span style="background:var(--after)"></span>Kraken fine-tuned ({BEST})
<span style="background:var(--pp)"></span>PP-OCRv6 fine-tuned ({PP}) <span style="background:var(--azure)"></span>Azure. Thin grey line: 95% interval, bootstrapped over documents. Shorter is better.</p>
<h2>How many characters and words come out wrong</h2>
{"".join(sec)}
<h2>Every model, every measure</h2>
<div class="scroll">{table}</div>
<p class="note">CER = characters wrong per 100; WER = words. "Faithful" keeps vowel marks, hamza forms, ى/ي, ة/ه and punctuation; "search-folded" drops vowels and punctuation and folds hamza seats, ى→ي, ة→ه. Arabic-Indic and Western digits count as the same digit everywhere (a born-digital PDF does not say which it drew).</p>
<h2>By kind of line (born-digital, characters wrong, faithful)</h2>
<div class="scroll"><table><tr><th>kind</th><th>lines</th><th>Kraken before</th><th>{BEST}</th><th>{PP}</th><th>Azure</th><th>before, scan-like</th><th>{BEST}, scan-like</th><th>{PP}, scan-like</th></tr>{krows}</table></div>
<h2>Real scans by kind of word (words wrong against the ink)</h2>
<div class="scroll"><table><tr><th>stratum</th><th>words</th>{shead}<th>Azure</th></tr>{srows}</table></div>
<h2>The line finder</h2>
{TXT.get("seg_text", "")}
{seg_html}
<h2>A first look at a VLM: PaddleOCR-VL-0.9B</h2>
{TXT.get("vlm_text", "")}
{vlm_html}
<h2>Lines from real scans</h2>
<p>Reference: Azure's line (silver; a Kraken difference is not always a Kraken error). Pink: characters that differ; <span class="gap">&#x2038;</span>: something missing.</p>
{scan_ex}
<h2>Lines from born-digital pages (truth = the PDF's own text)</h2>
{bd_ex}
<h2>What improved, what did not</h2>
{TXT.get("findings", "")}
<h2>What this does not show</h2>
<ul>{TXT.get("caveats", "")}</ul>
<h2>Compute and spend</h2>
{TXT.get("compute", "")}
{sp_html}
</body></html>"""
(OUT / "report.html").write_text(body, encoding="utf-8")
print("wrote", OUT / "report.html", len(body) // 1024, "KB")

