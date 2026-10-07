"""The owner's page for experiment 30: content rescued from the furniture rule, shown on the page; flag maps before
and after the block marks on vowelled and handwritten pages; the numbers as bars. Self-contained (images inlined),
light and dark, phone width.

    PYTHONPATH=src .venv/bin/python experiments/30_furniture_flags/make_report.py   -> out/report.html

Reads out/furniture_eval_after.json, out/furniture_eval_heldout_after.json, out/census_*.json, out/flags_eval.json,
out/flags_set.json, out/judged_context.json, out/reenrich/<stem>/ (reenrich.py) and experiment 28's ALTO files.
"""
import base64
import html
import json
import re
from collections import Counter
from pathlib import Path

import pymupdf
from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
DATA = Path("/home/yassine/inkscript/experiments/28_scale/out")
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
norm = lambda s: re.sub(r"[^ء-يa-zA-Z]", "", s or "")
J = lambda n: json.loads((OUT / n).read_text(encoding="utf-8"))


def wilson(k, n, z=1.96):
    import math
    if not n:
        return (0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, c - h), min(1.0, c + h))


def img(pix) -> str:
    return "data:image/jpeg;base64," + base64.b64encode(pix.tobytes("jpg", jpg_quality=72)).decode()


def crop(stem, page, box, W, H, color=(0.1, 0.65, 0.3), width=560):
    """The page's full width around a block, the block outlined."""
    src = pymupdf.open(str(DATA / "azure" / stem / f"{stem}.pdf"))
    pg = src[page - 1]
    R = pg.rect
    sx, sy = R.width / W, R.height / H
    h = max(box[3] - box[1], 70)
    y0, y1 = max(0, box[1] - 2.2 * h), min(H, box[3] + 2.2 * h)
    x0, x1 = max(0, box[0] - 0.22 * W), min(W, box[2] + 0.22 * W)
    clip = pymupdf.Rect(x0 * sx, y0 * sy, x1 * sx, y1 * sy)
    r = pymupdf.Rect(box[0] * sx - 3, box[1] * sy - 3, box[2] * sx + 3, box[3] * sy + 3)
    pg.draw_rect(r, color=color, width=1.6)
    z = width / clip.width
    pix = pg.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=clip)
    src.close()
    return img(pix)


def alto_words(path, page):
    t = etree.parse(str(path))
    for pg in t.iter(A + "Page"):
        if int(pg.get("PHYSICAL_IMG_NR")) != page:
            continue
        words, blocks = [], []
        for tb in pg.iter(A + "TextBlock"):
            regs = [x[7:] for x in (tb.get("TAGREFS") or "").split() if x.startswith("region.")]
            box = [float(tb.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")]
            if regs:
                blocks.append((box, regs))
            for s in tb.iter(A + "String"):
                tr = (s.get("TAGREFS") or "").split()
                words.append(([float(s.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")], "trust.flagged" in tr))
        return words, blocks, pg.get("PAGECLASS")
    return [], [], None


def flag_map(stem, page, after_alto, width=420):
    """Two renderings of one page: flagged words in amber before (experiment 28's build) and after; the blocks
    carrying a mark outlined in blue."""
    before_alto = next(iter(DATA.glob(f"set/w*/{stem}.alto.xml")))
    out = []
    for label, path in (("before", before_alto), ("after", after_alto)):
        words, blocks, pclass = alto_words(path, page)
        src = pymupdf.open(str(DATA / "azure" / stem / f"{stem}.pdf"))
        pg = src[page - 1]
        R = pg.rect
        t = etree.parse(str(path))
        P = next(p for p in t.iter(A + "Page") if int(p.get("PHYSICAL_IMG_NR")) == page)
        sx, sy = R.width / float(P.get("WIDTH")), R.height / float(P.get("HEIGHT"))
        nf = 0
        for b, fl in words:
            if fl:
                nf += 1
                pg.draw_rect(pymupdf.Rect(b[0] * sx, b[1] * sy, (b[0] + b[2]) * sx, (b[1] + b[3]) * sy),
                             color=None, fill=(1.0, 0.7, 0.15), fill_opacity=0.5, overlay=True)
        if label == "after":
            for b, regs in blocks:
                pg.draw_rect(pymupdf.Rect(b[0] * sx - 4, b[1] * sy - 4, (b[0] + b[2]) * sx + 4, (b[1] + b[3]) * sy + 4),
                             color=(0.2, 0.4, 0.9), width=1.2, dashes="[4 3] 0")
        pix = pg.get_pixmap(matrix=pymupdf.Matrix(width / R.width, width / R.width))
        src.close()
        regs = sorted({r for b, rs in blocks for r in rs})
        out.append(dict(label=label, src=img(pix), flagged=nf, words=len(words), regions=regs, pclass=pclass))
    return out


def bar(label, before, after, mx=100.0, unit="%", note=""):
    wb, wa = 100 * before / mx, 100 * after / mx
    return (f'<div class="bar"><div class="bl">{html.escape(label)}</div><div class="bt">'
            f'<div class="b b0" style="width:{wb:.1f}%"><span>{before:.1f}{unit}</span></div>'
            f'<div class="b b1" style="width:{wa:.1f}%"><span>{after:.1f}{unit}</span></div></div>'
            f'<div class="bn">{html.escape(note)}</div></div>')


def ci_row(label, k, n, ci, cls):
    lo, hi = 100 * ci[0], 100 * ci[1]
    p = 100 * k / n if n else 0
    return (f'<div class="ci"><div class="bl">{html.escape(label)}</div><div class="ct">'
            f'<div class="cw {cls}" style="left:{lo:.1f}%;width:{hi - lo:.1f}%"></div>'
            f'<div class="cp {cls}" style="left:{p:.1f}%"></div></div>'
            f'<div class="bn">{k} / {n} ({p:.0f}%, 95% interval {lo:.0f}–{hi:.0f}%)</div></div>')


def main():
    tune, held = J("furniture_eval_after.json"), J("furniture_eval_heldout_after.json")
    cb, ca = J("census_before.json"), J("census_after.json")
    fe, fs, jc = J("flags_eval.json"), J("flags_set.json"), J("judged_context.json")
    nb, na = sum(len(r["furniture"]) for r in cb.values()), sum(len(r["furniture"]) for r in ca.values())

    def lone(c):
        n = d = 0
        for r in c.values():
            cnt = Counter(norm(b["text"]) for b in r["furniture"])
            k = sum(1 for b in r["furniture"] if len(norm(b["text"])) >= 3 and cnt[norm(b["text"])] <= 2)
            n += k
            d += bool(k)
        return n, d
    lb, la = lone(cb), lone(ca)
    # ---- rescued content on the page
    picks = [("tune", 5, "the article's title on page 1 (it comes back as the running head later)"),
             ("tune", 12, "a heading that opens a page"), ("tune", 3, "a table's header row at the top of a page"),
             ("tune", 13, "a figure's source above the footer frame"), ("tune", 28, "an endnote"),
             ("tune", 110, "a heading: «عدد» is not a masthead"), ("tune", 117, "a number in a table's row"),
             ("held", 18, "the first line of a page"), ("held", 11, "a figure's caption"), ("held", 50, "a note numbered 17")]
    rows = {"tune": {r["n"]: r for r in tune["rows"]}, "held": {r["n"]: r for r in held["rows"]}}
    rescued_html = []
    for src, n, what in picks:
        r = rows[src][n]
        if r["verdict"] != "content" or r["still"]:
            continue
        c = cb[r["doc"]]
        W, H = next((b["W"], b["H"]) for b in c["furniture"] if b["page"] == r["page"])
        rescued_html.append(f'<figure><img alt="" src="{crop(r["doc"], r["page"], r["box"], W, H)}">'
                            f'<figcaption><b>{html.escape(what)}</b> · {r["doc"]} p{r["page"]} · was '
                            f'“{html.escape(r["rule"])}”</figcaption></figure>')
    leak_html = []
    for src, n, what in (("tune", 7, "a logo's lettering read as a table (7894's masthead)"),
                         ("held", 6, "the same logo, another page")):
        r = rows[src][n]
        c = cb[r["doc"]]
        W, H = next((b["W"], b["H"]) for b in c["furniture"] if b["page"] == r["page"])
        leak_html.append(f'<figure><img alt="" src="{crop(r["doc"], r["page"], r["box"], W, H, color=(0.85, 0.2, 0.2))}">'
                         f'<figcaption><b>{html.escape(what)}</b> · {r["doc"]} p{r["page"]}</figcaption></figure>')
    # ---- flag maps
    maps = []
    for stem, page, what in (("0657-021-007-010", 1, "a vowelled short story"), ("0408-011-007,008-006", 1, "vowelled verse"),
                             ("0679-000-014-004", 64, "a handwritten page in an appendix")):
        a = OUT / "reenrich" / stem / f"{stem}.alto.xml"
        if not a.exists():
            continue
        m = flag_map(stem, page, a)
        cells = "".join(f'<figure><img alt="" src="{x["src"]}"><figcaption><b>{x["label"]}</b>: {x["flagged"]} of '
                        f'{x["words"]} words flagged ({100 * x["flagged"] / max(1, x["words"]):.0f}%)'
                        + (f' · marks: {", ".join(x["regions"])}' if x["regions"] else "")
                        + (f' · PAGECLASS {x["pclass"]}' if x["pclass"] and x["label"] == "after" else "")
                        + '</figcaption></figure>' for x in m)
        maps.append(f'<h3>{html.escape(what)} <span class="muted">{stem} p{page}</span></h3><div class="pair">{cells}</div>')
    # ---- numbers
    k = fs["kinds"]
    order = ["under 5% vowelled", "5-20% vowelled", "20-50% vowelled", "over 50% vowelled", "handwritten pages", "all"]
    kind_bars = "".join(bar(f'{n.replace("handwritten pages", "with handwritten pages")} ({k[n]["docs"]} docs)', 100 * k[n]["before"] / k[n]["words"], 100 * k[n]["after"] / k[n]["words"],
                            mx=65) for n in order if n in k)
    bm = fs["by_mark"]
    mark_bars = "".join(bar(f'in {m} blocks ({bm[m + "_words"]:,} words)', 100 * bm[m + "_before"] / bm[m + "_words"],
                            100 * bm[m + "_after"] / bm[m + "_words"], mx=80) for m in ("vowelled", "decorative", "handwritten")
                        if bm.get(m + "_words"))
    res = fe["results"]
    b0 = res["before (experiment 27's rule)"]
    a0 = res["after: in marked blocks, conf < 0.5 x median, lowest tenth"]
    judged_marks = Counter(m for f in jc for m in f["ctx"]["marks"])
    judged_err = Counter(m for f in jc if f["truth"] for m in f["ctx"]["marks"])
    ts, hs = tune["summary"], held["summary"]
    hstr = held["strata"]
    rel_ok = hstr["released-letters"]["rescued"] + hstr["released-number"]["rescued"]
    rel_n = hstr["released-letters"]["rescued"] + hstr["released-number"]["rescued"] + \
        (hstr["released-letters"]["furniture"] - hstr["released-letters"]["kept"]) + \
        (hstr["released-number"]["furniture"] - hstr["released-number"]["kept"])
    page = TEMPLATE.format(
        nb=f"{nb:,}", na=f"{na:,}",
        v50b=100 * k["over 50% vowelled"]["before"] / k["over 50% vowelled"]["words"],
        v50a=100 * k["over 50% vowelled"]["after"] / k["over 50% vowelled"]["words"],
        hwb=100 * bm["handwritten_before"] / bm["handwritten_words"], hwa=100 * bm["handwritten_after"] / bm["handwritten_words"], lb=lb[0], lbd=lb[1], la=la[0], lad=la[1],
        rescued="".join(rescued_html), leaks="".join(leak_html), maps="".join(maps),
        ci_tune="".join([ci_row("content kept as content", ts["rescued"], ts["content"], ts["rescued_ci"], "g"),
                         ci_row("furniture still set aside", ts["kept"], ts["furniture"], ts["kept_ci"], "b")]),
        ci_held="".join([ci_row("blocks released are content", rel_ok, rel_n, wilson(rel_ok, rel_n), "g"),
                         ci_row("blocks still set aside by place are furniture", hstr["still-by-place"]["kept"],
                                hstr["still-by-place"]["kept"] + hstr["still-by-place"]["content"] - hstr["still-by-place"]["rescued"],
                                wilson(hstr["still-by-place"]["kept"], hstr["still-by-place"]["kept"] + hstr["still-by-place"]["content"]
                                       - hstr["still-by-place"]["rescued"]), "b")]),
        kind_bars=kind_bars, mark_bars=mark_bars,
        j_flag_b=f'{100 * b0["all"]["flagged_w"]:.1f}', j_flag_a=f'{100 * a0["all"]["flagged_w"]:.1f}',
        ci_judged="".join([ci_row("errors flagged word by word, before", b0["all"]["caught"], b0["all"]["errors"], b0["all"]["caught_ci"], "b"),
                           ci_row("errors flagged word by word, after", a0["all"]["caught"], a0["all"]["errors"], a0["all"]["caught_ci"], "g"),
                           ci_row("errors flagged, or inside a marked block, after", a0["all"]["caught_or_covered"], a0["all"]["errors"],
                                  wilson(a0["all"]["caught_or_covered"], a0["all"]["errors"]), "g")]),
        m_words=b0["marked"]["words"], m_err=b0["marked"]["errors"], m_fb=b0["marked"]["flagged_n"], m_fa=a0["marked"]["flagged_n"],
        m_cb=b0["marked"]["caught"], m_ca=a0["marked"]["caught"],
        jm=", ".join(f"{m} {n} ({judged_err[m]} errors)" for m, n in judged_marks.most_common()))
    (OUT / "report.html").write_text(page, encoding="utf-8")
    print("out/report.html", len(page) // 1024, "KB")


TEMPLATE = """<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Furniture and flags</title>
<style>
:root {{ --bg:#fbfaf7; --fg:#1d1d1b; --muted:#6b6862; --card:#ffffff; --line:#e4e0d8; --amber:#e8a33d; --blue:#3d6fd6;
  --green:#2f9e5a; --red:#c8433a; --b0:#c9c3b8; }}
@media (prefers-color-scheme: dark) {{ :root:not([data-theme="light"]) {{ --bg:#16161a; --fg:#ecebe6; --muted:#a29f98;
  --card:#202026; --line:#33333b; --b0:#55535c; }} }}
:root[data-theme="dark"] {{ --bg:#16161a; --fg:#ecebe6; --muted:#a29f98; --card:#202026; --line:#33333b; --b0:#55535c; }}
* {{ box-sizing:border-box }}
body {{ margin:0; background:var(--bg); color:var(--fg); font:16px/1.55 system-ui, -apple-system, "Segoe UI", sans-serif; }}
main {{ max-width:1080px; margin:0 auto; padding:24px 16px 64px }}
h1 {{ font-size:1.7rem; margin:.2em 0 .3em }} h2 {{ margin-top:2.2em; font-size:1.3rem }} h3 {{ font-size:1.05rem; margin:1.6em 0 .5em }}
.muted {{ color:var(--muted); font-weight:400 }}
.lead {{ font-size:1.05rem; max-width:62ch }}
.tiles {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(200px,1fr)); gap:12px; margin:18px 0 }}
.tile {{ background:var(--card); border:1px solid var(--line); border-radius:10px; padding:12px 14px }}
.tile b {{ display:block; font-size:1.5rem }} .tile span {{ color:var(--muted); font-size:.9rem }}
.grid {{ display:grid; grid-template-columns:repeat(auto-fit,minmax(320px,1fr)); gap:14px }}
figure {{ margin:0; background:var(--card); border:1px solid var(--line); border-radius:10px; overflow:hidden }}
figure img {{ width:100%; display:block; background:#fff }}
figcaption {{ padding:8px 10px; font-size:.88rem; color:var(--muted) }} figcaption b {{ color:var(--fg) }}
.pair {{ display:grid; grid-template-columns:1fr 1fr; gap:10px }}
@media (max-width:560px) {{ .pair {{ grid-template-columns:1fr }} }}
.bar, .ci {{ display:grid; grid-template-columns:minmax(120px,230px) 1fr; gap:4px 12px; align-items:center; margin:10px 0 }}
.bl {{ font-size:.92rem }} .bn {{ grid-column:2; font-size:.82rem; color:var(--muted) }}
.bt {{ display:flex; flex-direction:column; gap:3px }}
.b {{ height:16px; border-radius:3px; position:relative; min-width:2px }}
.b span {{ position:absolute; left:calc(100% + 6px); top:-2px; font-size:.8rem; white-space:nowrap }}
.b0 {{ background:var(--b0) }} .b1 {{ background:var(--amber) }}
.ct {{ position:relative; height:18px; background:var(--line); border-radius:9px }}
.cw {{ position:absolute; top:4px; height:10px; border-radius:5px; opacity:.45 }}
.cp {{ position:absolute; top:1px; width:4px; height:16px; margin-left:-2px; border-radius:2px }}
.g {{ background:var(--green) }} .b {{ }} .cw.b, .cp.b {{ background:var(--blue) }}
.key {{ font-size:.85rem; color:var(--muted) }} .key i {{ display:inline-block; width:12px; height:12px; border-radius:2px; vertical-align:-1px; margin:0 4px 0 10px }}
@media (max-width:560px) {{ .bar, .ci {{ grid-template-columns:1fr }} .bn {{ grid-column:1 }} }}
</style></head><body><main>
<h1>Content kept, flags that mean something</h1>
<p class="lead">Experiment 30 fixes two things the 205-document run found. Text near the top or bottom of a page
— a table's header, a heading opening a page, a note, a caption — was taken for running heads and left out of the
article. And on vowelled or handwritten pages most words were flagged, which told the reader nothing.</p>
<div class="tiles">
<div class="tile"><b>{nb} → {na}</b><span>blocks set aside as page furniture on the 205 documents</span></div>
<div class="tile"><b>{lb} → {la}</b><span>“lone” blocks with letters set aside ({lbd} → {lad} documents)</span></div>
<div class="tile"><b>{v50b:.0f}% → {v50a:.0f}%</b><span>words flagged on the two most vowelled documents</span></div>
<div class="tile"><b>{hwb:.0f}% → {hwa:.0f}%</b><span>words flagged on the handwritten pages</span></div>
</div>

<h2>1 · Content that is no longer set aside</h2>
<p>Each block below was taken for page furniture before (the rule it fell under is in the caption) and is article text
now: it reaches the JATS. Outlined in green on the scan.</p>
<div class="grid">{rescued}</div>
<h3>How often it is right <span class="muted">— the furniture sample read by eye</span></h3>
<p class="key">Tuning sample: 140 of the blocks the old rule set aside, drawn by kind (repeats, top 8%, bottom 6%,
side tabs, masthead, specks, page numbers), each judged on the page image.</p>
{ci_tune}
<p class="key">Held out: 60 blocks drawn afterwards from what the new rule changed on the 205 documents.</p>
{ci_held}
<p>What still goes wrong: a logo's lettering that looks like a table (one document, every page), a calligraphic
running head that Azure reads differently each time, a table that starts at the very top of a page with nothing
above it.</p>
<div class="grid">{leaks}</div>
<p class="key">Experiment 26's hand-read truth is unchanged: title 10/10, headings precision 0.89 recall 0.93,
footnote links 30/31, endnote links 15/15, <b>0 furniture leaks</b>; held-out 4 documents: 0 leaks.</p>

<h2>2 · Marks on the block, flags on the word</h2>
<p>Where Azure's reading is weaker as a whole — a <b>vowelled</b> block, a <b>handwritten</b> page, <b>decorative</b>
lettering on a printed page — the block now carries the mark (dashed blue). A word keeps its own amber flag only
when something points at it: a Quran difference, Gemini's other reading, a Persian letter, a speck, a Latin word,
or a confidence far below its own block's (under half the block's median and in its lowest tenth).</p>
<p class="key"><i style="background:var(--amber)"></i>flagged word <i style="background:none;border:1.5px dashed var(--blue)"></i>marked block</p>
{maps}

<h3>Words flagged, by kind of document <span class="muted">— 205 documents, 881,793 words</span></h3>
<p class="key"><i style="background:var(--b0)"></i>before <i style="background:var(--amber)"></i>after</p>
{kind_bars}
<h3>Inside the marked blocks</h3>
{mark_bars}

<h3>Errors still found <span class="muted">— experiment 19's 2,935 judged words, nothing paid again</span></h3>
<p>Words flagged {j_flag_b}% → {j_flag_a}% (weighted to the archive). Of the 61 judged errors, the ones that lost
their word flag are all inside a marked block, where the block's mark tells the reader to check.</p>
{ci_judged}
<p class="key">In marked blocks: {m_words} judged words with {m_err} errors; flagged {m_fb} → {m_fa}, errors flagged
word by word {m_cb} → {m_ca}. By mark: {jm}. The sample is small there: the intervals are wide.</p>

<h2>Where the marks go</h2>
<p><b>ALTO 4.4</b>: an OtherTag per mark used (<code>region.vowelled</code>, <code>region.handwritten</code>,
<code>region.decorative</code>, TYPE reading-reliability) referenced from each marked TextBlock's TAGREFS; a
handwritten page also gets <code>PAGECLASS="handwritten"</code> (ALTO gives Page no TAGREFS; PAGECLASS is its
user-defined class). <b>JATS</b>: custom-meta <code>reading-vowelled</code> etc. with pages, counts and block ids,
and <code>&lt;p content-type="vowelled"&gt;</code>. <b>Trust PDF</b>: a dashed outline per marked block and one note per
page, in a layer “Reading marks” that can be switched off; the faithful PDF's bytes stay first and unchanged.</p>
</main></body></html>
"""

if __name__ == "__main__":
    main()
