"""The owner's page for experiment 28: the set's numbers as pictures, a gallery of documents, and what broke.

    .venv/bin/python experiments/28_scale/showcase.py STEM[:PAGE] ...   -> out/showcase.html (self-contained)

Numbers from out/set/summary.json (summarize.py); "what broke" from out/failures.json (written by hand after the hunt:
[{kind, count, what, why, fix, examples: [{doc, page, box?: [x0,y0,x1,y1] in scan pixels, pdf?: "trust|faithful|scan", caption}]}]).
Page pictures are JPEG thumbnails (the page at 640 px, crops at 720 px) so the file stays small.
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SET = OUT / "set"
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
XL = "{http://www.w3.org/1999/xlink}"
E = html.escape


def find(stem):
    for d in sorted(SET.glob("w*")):
        if (d / f"{stem}.alto.xml").exists() or (d / f"{stem}.pdf").exists():
            return d
    raise SystemExit(f"{stem}: not built")


def jpeg(pdf, page, width=640, clip=None, scan_wh=None, q=62):
    """A page (or a clip of it, given in scan pixels of a page scan_wh wide/high) as a data: URI."""
    import pymupdf
    d = pymupdf.open(str(pdf))
    p = d[page - 1]
    r = p.rect
    if clip and scan_wh:
        sx, sy = r.width / scan_wh[0], r.height / scan_wh[1]
        c = pymupdf.Rect(clip[0] * sx, clip[1] * sy, clip[2] * sx, clip[3] * sy) & r
        z = width / c.width
        pix = p.get_pixmap(matrix=pymupdf.Matrix(z, z), clip=c)
    else:
        pix = p.get_pixmap(matrix=pymupdf.Matrix(width / r.width, width / r.width))
    data = pix.tobytes("jpeg", jpg_quality=q)
    d.close()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def alto_page(path, page):
    t = etree.parse(str(path))
    tags = {tg.get("ID"): dict(label=tg.get("LABEL"), uri=tg.get("URI"), desc=tg.get("DESCRIPTION"))
            for tg in t.iter(A + "OtherTag")}
    pg = t.find(f".//{A}Page[@ID='page{page}']")
    W, H = float(pg.get("WIDTH")), float(pg.get("HEIGHT"))
    words = []
    for s in pg.iter(A + "String"):
        refs = (s.get("TAGREFS") or "").split()
        alts = [(a.get("PURPOSE"), a.text) for a in s.findall(A + "ALTERNATIVE")]
        words.append(dict(id=s.get("ID"), text=s.get("CONTENT"), wc=s.get("WC"),
                          box=[float(s.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")],
                          mark=next((r.split(".")[1] for r in refs if r.startswith("trust.")), None),
                          why=[tags[r]["label"] for r in refs if r.startswith("why.") and r in tags],
                          quote=next((r for r in refs if r.startswith("quran")), None), alts=alts,
                          line=s.getparent().get("ID")))
    return W, H, words, tags


def page_wh(alto, page):
    for ev, el in etree.iterparse(str(alto), events=("start",), tag=A + "Page"):
        if el.get("ID") == f"page{page}":
            return float(el.get("WIDTH")), float(el.get("HEIGHT"))
    return None


def page_choice(path):
    """The page with the most corrected words, then quotation words, then flagged words."""
    t = etree.parse(str(path))
    best = None
    for pg in t.iter(A + "Page"):
        refs = [s.get("TAGREFS") or "" for s in pg.iter(A + "String")]
        sc = (sum("trust.corrected" in r for r in refs), sum("quran" in r for r in refs), sum("trust.flagged" in r for r in refs))
        if best is None or sc > best[0]:
            best = (sc, int(pg.get("PHYSICAL_IMG_NR")))
    return best[1]


def jats_outline(path):
    r = etree.parse(str(path)).getroot()
    g = lambda x: " ".join((r.findtext(x) or "").split())
    out = dict(title=" ".join("".join(r.find(".//article-title").itertext()).split()) if r.find(".//article-title") is not None else "",
               subject=g(".//subject"), journal=g(".//journal-title"), fpage=g(".//fpage"), lpage=g(".//lpage"),
               authors=[" ".join("".join(c.itertext()).split()) for c in r.iter("contrib")],
               sections=[" ".join("".join(s.find("title").itertext()).split()) for s in r.iter("sec") if s.find("title") is not None],
               body_p=len(r.findall("./body//p")), fns=len(r.findall(".//fn")),
               xrefs=len([x for x in r.iter("xref") if x.get("ref-type") == "fn"]), quotes=[])
    for p in r.iterfind(".//notes/p[@id]"):
        link = p.find("ext-link"); verse = p.find("named-content")
        if link is None: continue
        out["quotes"].append(dict(label=link.text, href=link.get(XL + "href"), verse=verse.text if verse is not None else "",
                                  rest=(verse.tail or "").strip(" —") if verse is not None else ""))
    return out


def pct(a, b, n=1):
    return f"{100 * a / max(1, b):.{n}f}%"


# ---------- charts (inline SVG, one hue; values as text tokens) ----------

def strip(docs, key, label, fmt, lo, hi, weak_low=True, n_label=4, unit="%"):
    """One dot per document on a horizontal axis from lo to hi; the weakest few named."""
    W, H, L, R = 760, 92, 14, 14
    xs = lambda v: L + (min(max(v, lo), hi) - lo) / (hi - lo) * (W - L - R)
    vals = [(d, key(d)) for d in docs if key(d) is not None]
    vals.sort(key=lambda x: x[1], reverse=not weak_low)
    # stack dots in columns of equal x so the distribution's shape shows
    cols = {}
    dots = []
    for d, v in vals:
        cx = round(xs(v) / 6) * 6
        k = cols.get(cx, 0); cols[cx] = k + 1
        cy = 66 - k * 6.5
        if cy < 10: cy = 10
        tip = f"{d['doc']} · {d.get('year') or '?'} · {fmt(v)}"
        dots.append(f'<circle class="dot" cx="{cx}" cy="{cy:.1f}" r="3.4"><title>{E(tip)}</title></circle>')
    ticks = []
    for i in range(5):
        v = lo + (hi - lo) * i / 4
        ticks.append(f'<line class="tick" x1="{xs(v):.0f}" x2="{xs(v):.0f}" y1="72" y2="76"/>'
                     f'<text class="ax" x="{xs(v):.0f}" y="88" text-anchor="middle">{fmt(v)}</text>')
    weak = vals[:n_label]
    names = ", ".join(f"<b>{E(d['doc'])}</b> {fmt(v)}" for d, v in weak)
    med = sorted(v for _, v in vals)[len(vals) // 2] if vals else 0
    return f"""<figure class="strip"><figcaption><span>{label}</span><span class="med">median document {fmt(med)}</span></figcaption>
<svg viewBox="0 0 {W} {H}" role="img" aria-label="{E(label)}: one dot per document">
<line class="base" x1="{L}" x2="{W - R}" y1="72" y2="72"/>{''.join(ticks)}{''.join(dots)}</svg>
<p class="weak">weakest: {names}</p></figure>"""


def bars(rows, title, fmt, maxv, note=""):
    """Horizontal bars, one per decade (rows: [(label, value, n_docs, detail)])."""
    W, rowh, L = 520, 26, 74
    h = rowh * len(rows) + 8
    out = []
    for i, (lab, v, n, det) in enumerate(rows):
        y = 4 + i * rowh
        w = max(2, (W - L - 70) * (v / maxv if maxv else 0))
        out.append(f'<text class="ax" x="{L - 8}" y="{y + 15}" text-anchor="end">{E(lab)}</text>'
                   f'<rect class="bar" x="{L}" y="{y + 4}" width="{w:.1f}" height="{rowh - 10}" rx="3"><title>{E(lab)}: {fmt(v)} · {n} documents{(" · " + E(det)) if det else ""}</title></rect>'
                   f'<text class="val" x="{L + w + 6:.1f}" y="{y + 15}">{fmt(v)}</text>'
                   f'<text class="nn" x="{W - 4}" y="{y + 15}" text-anchor="end">{n}</text>')
    return f"""<figure class="bars"><figcaption>{title}</figcaption>
<svg viewBox="0 0 {W} {h}" role="img" aria-label="{E(title)} by decade">{''.join(out)}</svg>{f'<p class="note">{note}</p>' if note else ''}</figure>"""


# ---------- one document ----------

def doc_section(stem, page, summ):
    d = find(stem)
    alto = d / f"{stem}.alto.xml"
    page = page or page_choice(alto)
    W, H, words, tags = alto_page(alto, page)
    img = jpeg(d / f"{stem}.pdf", page, 640)
    o = jats_outline(d / f"{stem}.jats.xml")
    s = next((x for x in summ["docs"] if x["doc"] == stem), {})
    rects, quotes = [], {}
    for w in words:
        x, y, ww, hh = w["box"]
        q = tags.get(w["quote"]) if w["quote"] else None
        alt = "; ".join(("Azure read" if p == "azure-reading" else (p or "")) + f" «{t or ''}»" for p, t in w["alts"])
        tip = f'{w["text"]} · {w["mark"] or "-"}' + (f' · {", ".join(w["why"])}' if w["why"] else "") + (f" · {alt}" if alt else "")
        if w["mark"] in ("flagged", "corrected", "verified"):
            rects.append(f'<rect class="w {w["mark"]}" x="{x:.0f}" y="{y:.0f}" width="{ww:.0f}" height="{hh:.0f}"><title>{E(tip)}</title></rect>')
        if q:
            quotes.setdefault((w["quote"], w["line"]), []).append(w["box"])
    for (qid, _), bs in quotes.items():
        x0 = min(b[0] for b in bs) - 6; y0 = min(b[1] for b in bs) - 6
        x1 = max(b[0] + b[2] for b in bs) + 6; y1 = max(b[1] + b[3] for b in bs) + 6
        rects.append(f'<a href="{tags[qid]["uri"]}" target="_blank" rel="noopener"><rect class="q" x="{x0:.0f}" y="{y0:.0f}" '
                     f'width="{x1 - x0:.0f}" height="{y1 - y0:.0f}"><title>{E(tags[qid]["label"] or "")}</title></rect></a>')
    nf = sum(w["mark"] == "flagged" for w in words); nc = sum(w["mark"] == "corrected" for w in words)
    corr = [w for w in words if w["mark"] == "corrected"]
    fr = []
    if o["subject"]: fr.append(("rubric", f'<span class="ar">{E(o["subject"])}</span>'))
    fr.append(("title", f'<span class="ar">{E(o["title"])}</span>' if o["title"] else "<i>not found</i>"))
    if s.get("cat_title"):
        ok = (s.get("title_sim") or 0) >= 0.6
        fr.append(("catalogue", f'<span class="ar">{E(s["cat_title"])}</span> <span class="{"okc" if ok else "badc"}">{"matches" if ok else "differs"}</span>'))
    fr.append(("authors", ", ".join(f'<span class="ar">{E(a)}</span>' for a in o["authors"]) or "<i>none found</i>"))
    if o["journal"]: fr.append(("journal (running heads)", f'<span class="ar">{E(o["journal"])}</span>'))
    if o["fpage"]: fr.append(("printed pages", f'{E(o["fpage"])}–{E(o["lpage"])}'))
    fr.append(("body", f'{o["body_p"]} paragraphs, {len(o["sections"])} headings, {o["fns"]} notes, {o["xrefs"]} markers linked'))
    secs = "".join(f"<li>{E(x)}</li>" for x in o["sections"][:7]) + ("<li>…</li>" if len(o["sections"]) > 7 else "")
    qs = "".join(f'<li><a href="{q["href"]}" target="_blank" rel="noopener">{E(q["label"] or "")}</a>'
                 f'<span class="v">{E(q["verse"] or "")}</span></li>' for q in o["quotes"][:3])
    cl = "".join(f'<li><span class="ar">{E(dict(w["alts"]).get("azure-reading", "?") or "?")}</span> → <span class="ar ok">{E(w["text"])}</span></li>' for w in corr[:6])
    meta = " · ".join(x for x in [str(s.get("year") or ""), E(s.get("journal") or ""), f'{s.get("pages", "?")} pages', f"page {page}"] if x)
    return f"""
<article class="doc">
 <header><h3>{E(stem)}</h3><span class="meta ar-ok">{meta}</span></header>
 <p class="lede small">{pct(s.get('intact', 0), s.get('words', 0), 2)} words intact · {pct(s.get('in_order', 0), s.get('lines', 0))} lines in order ·
 letters {pct(s.get('letters_cut', 0), s.get('letters_words', 0))} · flagged {pct(s.get('flagged') or 0, s.get('assessed') or 0)} ·
 {s.get('quotes') or 0} quotations · {((s.get('fix') or {}).get('statuses') or {}).get('applied', 0)} corrections written</p>
 <div class="grid">
  <div class="page"><img src="{img}" alt="Page {page} of {E(stem)}, faithful PDF" loading="lazy">
   <svg viewBox="0 0 {W:.0f} {H:.0f}" preserveAspectRatio="none">{''.join(rects)}</svg></div>
  <div class="outline">
   <div class="legend"><span><i class="sw f"></i>flagged ({nf})</span><span><i class="sw c"></i>corrected ({nc})</span><span><i class="sw q"></i>Quran quotation</span></div>
   <dl>{''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in fr)}</dl>
   {'<h4>Headings</h4><ol class="secs">' + secs + '</ol>' if secs else ''}
   {'<h4>Corrected on this page (Azure → verse, judged on the ink)</h4><ul class="corr">' + cl + '</ul>' if cl else ''}
   {'<h4>Quotations</h4><ul class="qs">' + qs + '</ul>' if qs else ''}
  </div>
 </div>
</article>"""


def failure_section(f):
    ex = []
    for e in f.get("examples", [])[:4]:
        try:
            d = find(e["doc"])
        except SystemExit:
            continue
        kind = e.get("pdf", "trust")
        pdf = {"trust": d / f"{e['doc']}_trust.pdf", "faithful": d / f"{e['doc']}.pdf", "vector": d / f"{e['doc']}_vector.pdf",
               "scan": OUT / "azure" / e["doc"] / f"{e['doc']}.pdf"}[kind]
        if not pdf.exists(): pdf = d / f"{e['doc']}.pdf"
        wh = page_wh(d / f"{e['doc']}.alto.xml", e["page"]) if (e.get("box") or e.get("around") or e.get("frac")) else None
        box = e.get("box")
        if e.get("around") and wh:                     # rows around an ALTO block [x, y, w, h], full width
            x, y, w, h = e["around"]; box = [0, max(0, y - 3 * h), wh[0], min(wh[1], y + 4 * h)]
        if e.get("frac") and wh:                       # a band of the page, by fraction of its height
            box = [0, e["frac"][0] * wh[1], wh[0], e["frac"][1] * wh[1]]
        img = jpeg(pdf, e["page"], 720 if box else 420, clip=box, scan_wh=wh)
        ex.append(f'<figure class="ex"><img src="{img}" alt="{E(e["doc"])} page {e["page"]}" loading="lazy">'
                  f'<figcaption><b>{E(e["doc"])}</b> p{e["page"]} — {e.get("caption", "")}</figcaption></figure>')
    return f"""<section class="fail"><header><h3>{E(f['kind'])}</h3><span class="count">{E(str(f.get('count', '')))}</span></header>
<p>{f.get('what', '')}</p>{f'<p class="why"><b>Why.</b> {f["why"]}</p>' if f.get('why') else ''}
{f'<p class="fix"><b>Proposed.</b> {f["fix"]}</p>' if f.get('fix') else ''}
<div class="exs">{''.join(ex)}</div></section>"""


CSS = """
:root{--bg:#f6f6f4;--panel:#fff;--fg:#14171c;--muted:#5b616b;--rule:#dcdcd6;--accent:#2a78d6;--dot:#2a78d6;
--flag:#d08a00;--flagfill:rgba(237,161,0,.35);--ok:#1a8a52;--okfill:rgba(26,138,82,.32);--quote:#2a78d6;--bad:#c23b3a;
--display:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif;--body:"IBM Plex Sans",system-ui,sans-serif;
--ar:"IBM Plex Sans Arabic","Noto Naskh Arabic","Geeza Pro",serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace;color-scheme:light}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#121416;--panel:#1b1e22;--fg:#eceef1;--muted:#a3a9b3;--rule:#2e333a;
--accent:#3987e5;--dot:#5598e7;--flag:#e0a52a;--flagfill:rgba(224,165,42,.38);--ok:#3cba78;--okfill:rgba(60,186,120,.35);--quote:#5598e7;--bad:#e66767;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#121416;--panel:#1b1e22;--fg:#eceef1;--muted:#a3a9b3;--rule:#2e333a;--accent:#3987e5;--dot:#5598e7;--flag:#e0a52a;
--flagfill:rgba(224,165,42,.38);--ok:#3cba78;--okfill:rgba(60,186,120,.35);--quote:#5598e7;--bad:#e66767;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--body)}
.wrap{max-width:1120px;margin:0 auto;padding:28px 16px 60px}
h1,h2,h3,h4{font-family:var(--display);margin:0;line-height:1.15;text-wrap:balance}
h1{font-size:2.05rem;font-weight:600}h2{font-size:1.45rem;font-weight:600;margin-top:44px;padding-top:12px;border-top:2px solid var(--fg)}
h3{font-size:1.1rem;font-weight:600}h4{font-size:.76rem;text-transform:uppercase;letter-spacing:.07em;color:var(--muted);margin:12px 0 4px}
p{max-width:72ch}.lede{color:var(--muted)}.small{font-size:.86rem;margin:4px 0 0}
code{font:.86em var(--mono)}
.figs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin:20px 0 6px}
.fig{background:var(--panel);padding:12px 14px}.fig b{display:block;font:600 1.5rem/1.1 var(--display);font-variant-numeric:tabular-nums}
.fig span{color:var(--muted);font-size:.8rem}
@media (max-width:760px){.figs{grid-template-columns:repeat(2,minmax(0,1fr))}}
figure{margin:0}
.strip{background:var(--panel);border:1px solid var(--rule);padding:10px 12px 6px;margin:10px 0}
.strip figcaption{display:flex;justify-content:space-between;gap:10px;flex-wrap:wrap;font-weight:600;font-size:.92rem}
.strip .med{color:var(--muted);font-weight:400}
.strip svg,.bars svg{width:100%;height:auto;display:block}
.dot{fill:var(--dot);stroke:var(--panel);stroke-width:1.2}.dot:hover{fill:var(--flag)}
.base{stroke:var(--muted);stroke-width:1}.tick{stroke:var(--muted)}
.ax{fill:var(--muted);font:11px var(--body)}.val{fill:var(--fg);font:600 11.5px var(--body)}.nn{fill:var(--muted);font:11px var(--body)}
.weak{font-size:.78rem;color:var(--muted);margin:2px 0 4px;max-width:none}.weak b{color:var(--fg);font-weight:600;font-family:var(--mono);font-size:.74rem}
.barsgrid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}
@media (max-width:760px){.barsgrid{grid-template-columns:1fr}}
.bars{background:var(--panel);border:1px solid var(--rule);padding:10px 12px}.bars figcaption{font-weight:600;font-size:.92rem;margin-bottom:4px}
.bar{fill:var(--dot)}.note{font-size:.78rem;color:var(--muted);margin:4px 0 0}
.doc{margin-top:28px;border-top:1px solid var(--rule);padding-top:12px}
.doc header{display:flex;flex-wrap:wrap;gap:4px 14px;align-items:baseline}.meta{color:var(--muted);font-size:.84rem}
.grid{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;margin-top:10px}
@media (max-width:820px){.grid{grid-template-columns:1fr}}
.page{position:relative;background:#fff;border:1px solid var(--rule);align-self:start}
.page img{display:block;width:100%;height:auto}.page svg{position:absolute;inset:0;width:100%;height:100%}
.w.flagged{fill:var(--flagfill);stroke:var(--flag);stroke-width:2}.w.corrected{fill:var(--okfill);stroke:var(--ok);stroke-width:5}
.w.verified{fill:transparent}.q{fill:none;stroke:var(--quote);stroke-width:6;stroke-dasharray:20 10}
.legend{display:flex;flex-wrap:wrap;gap:4px 14px;font-size:.8rem;color:var(--muted)}
.sw{display:inline-block;width:20px;height:10px;vertical-align:-1px;margin-right:5px}
.sw.f{background:var(--flagfill);border:2px solid var(--flag)}.sw.c{background:var(--okfill);border:2px solid var(--ok)}.sw.q{border:2px dashed var(--quote)}
.outline{background:var(--panel);border:1px solid var(--rule);padding:12px 14px;min-width:0;font-size:.9rem}
.outline dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:3px 12px;margin:8px 0}
.outline dt{color:var(--muted);font-size:.78rem;padding-top:3px}.outline dd{margin:0;overflow-wrap:anywhere}
.ar{font-family:var(--ar);direction:rtl;unicode-bidi:isolate}.ok{color:var(--ok);font-weight:600}
.secs,.corr,.qs{margin:2px 0;padding-inline-start:1.2em}.secs{direction:rtl;font-family:var(--ar)}
.qs{list-style:none;padding:0}.qs li{border-inline-start:3px solid var(--quote);padding:1px 8px;margin:4px 0}
.qs .v{display:block;font:1rem/1.8 var(--ar);direction:rtl}.qs a{color:var(--accent)}
.okc{color:var(--ok);font-weight:600}.badc{color:var(--bad);font-weight:600}
.fail{background:var(--panel);border:1px solid var(--rule);border-inline-start:4px solid var(--bad);padding:12px 14px;margin:14px 0}
.fail header{display:flex;justify-content:space-between;gap:10px;align-items:baseline}.fail .count{font:600 1.05rem var(--display);color:var(--bad);white-space:nowrap}
.fail p{margin:6px 0;font-size:.92rem}.fail .why,.fail .fix{color:var(--muted)}
.exs{display:grid;grid-template-columns:repeat(auto-fill,minmax(240px,1fr));gap:10px;margin-top:8px}
.ex{border:1px solid var(--rule);background:var(--bg)}.ex img{display:block;width:100%;height:auto;background:#fff}
.ex figcaption{font-size:.78rem;padding:5px 7px;color:var(--muted)}.ex figcaption b{color:var(--fg);font-family:var(--mono);font-weight:400}
.tablewrap{overflow-x:auto;border:1px solid var(--rule);background:var(--panel);margin-top:8px}
table{border-collapse:collapse;width:100%;font-size:.8rem;font-variant-numeric:tabular-nums}
th,td{padding:5px 8px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th:first-child,td:first-child,th:nth-child(2),td:nth-child(2){text-align:left}
th{color:var(--muted);font-weight:600;font-size:.72rem;text-transform:uppercase;letter-spacing:.04em}
details summary{cursor:pointer;color:var(--accent);margin-top:10px}
footer{margin-top:40px;color:var(--muted);font-size:.8rem}
"""


def main():
    summ = json.loads((SET / "summary.json").read_text(encoding="utf-8"))
    t = summ["total"]
    docs = [d for d in summ["docs"] if d.get("built")]
    fails = json.loads((OUT / "failures.json").read_text(encoding="utf-8")) if (OUT / "failures.json").exists() else []
    picks = [(a.partition(":")[0], int(a.partition(":")[2]) if a.partition(":")[2] else None) for a in sys.argv[1:]]
    fx = t.get("fix_statuses") or {}
    figs = [(f"{t['documents']} · {t['pages']:,}", f"documents · pages built end to end ({len(t['crashed'])} crashed, {len(t['timeouts'])} timed out)"),
            (pct(t["intact"], t["words"], 2), f"words intact in Chrome's engine ({t['intact']:,}/{t['words']:,})"),
            (pct(t["in_order"], t["lines"], 2), f"lines in reading order ({t['in_order']:,}/{t['lines']:,})"),
            (pct(t["letters_cut"], t["letters_words"]), "words with every letter selectable"),
            (pct(t["flagged"], t["assessed"]), f"words flagged to check ({t['flagged']:,})"),
            (f"{t['quotes']:,}", f"Quran quotations found; {t['quotes_equal']} equal to the verse after corrections"),
            (f"{fx.get('applied', 0)}", f"corrections written ({t['fix_proposed']} proposed, judged on the ink; ${t['fix_spend']:.2f})"),
            (f"{t['jats_valid']}/{t['alto_valid']}", f"of {t['documents']} JATS / ALTO files valid against the schemas"),
            (f"{t['title_right']}/{t['with_cat_title']}", f"titles that match the catalogue (found {t['title_found']})"),
            (f"{t['authors_hit']}/{t['authors_cat']}", "catalogue authors found in the JATS"),
            (f"{t['wall_s'] / max(1, t['pages']):.0f} s", "a page, one worker (3 ran side by side)"),
            (f"{t['peak_mb_max'] / 1024:.1f} GB", "peak memory of the largest document")]
    # distributions
    sp = lambda a, b: (100 * a / b) if b else None
    strips = [
        strip(docs, lambda d: sp(d["letters_cut"], d["letters_words"]), "Words with every letter selectable, per document", lambda v: f"{v:.0f}%", 70, 100),
        strip(docs, lambda d: sp(d["flagged"] or 0, d["assessed"] or 0), "Words flagged to check, per document", lambda v: f"{v:.0f}%", 0, 40, weak_low=False),
        strip(docs, lambda d: sp(d["in_order"], d["lines"]), "Lines in reading order, per document", lambda v: f"{v:.0f}%", 80, 100),
        strip(docs, lambda d: sp(d["intact"], d["words"]), "Words intact, per document", lambda v: f"{v:.1f}%", 98, 100),
        strip(docs, lambda d: (d["wall_s"] / d["pages"]) if d.get("wall_s") and d.get("pages") else None,
              "Build time per page, per document (one worker)", lambda v: f"{v:.0f}s", 0, 60, weak_low=False),
    ]
    bd = summ["by_decade"]
    keys = (["<1960"] if "<1960" in bd else []) + sorted(k for k in bd if k not in ("?", "<1960")) + (["?"] if "?" in bd else [])
    mk = lambda f: [(k, f(bd[k]), bd[k]["documents"], "") for k in keys]
    barsh = [
        bars(mk(lambda a: 100 * a["letters_cut"] / max(1, a["letters_words"])), "Words with every letter selectable", lambda v: f"{v:.1f}%", 100),
        bars(mk(lambda a: 100 * a["flagged"] / max(1, a["assessed"])), "Words flagged to check", lambda v: f"{v:.1f}%",
             max(100 * a["flagged"] / max(1, a["assessed"]) for a in bd.values()) * 1.1),
        bars(mk(lambda a: 100 * a["title_right"] / max(1, a["with_cat_title"])), "Title matches the catalogue", lambda v: f"{v:.0f}%", 100),
        bars(mk(lambda a: 100 * a["in_order"] / max(1, a["lines"])), "Lines in reading order", lambda v: f"{v:.1f}%", 100),
        bars(mk(lambda a: a["quotes"] / max(1, a["documents"])), "Quran quotations per document", lambda v: f"{v:.1f}",
             max(a["quotes"] / max(1, a["documents"]) for a in bd.values()) * 1.1),
        bars(mk(lambda a: a["wall_s"] / max(1, a["pages"])), "Seconds a page", lambda v: f"{v:.0f}s",
             max(a["wall_s"] / max(1, a["pages"]) for a in bd.values()) * 1.1),
    ]
    rows = "".join(
        f"<tr><td>{E(d['doc'])}</td><td class='ar'>{E((d.get('journal') or '')[:34])}</td><td>{d.get('year') or ''}</td><td>{d.get('pages', '')}</td>"
        f"<td>{pct(d.get('intact', 0), d.get('words', 0), 2)}</td><td>{pct(d.get('in_order', 0), d.get('lines', 0))}</td>"
        f"<td>{pct(d.get('letters_cut', 0), d.get('letters_words', 0))}</td><td>{pct(d.get('flagged') or 0, d.get('assessed') or 0)}</td>"
        f"<td>{d.get('quotes') or 0}</td><td>{((d.get('fix') or {}).get('statuses') or {}).get('applied', 0)}</td>"
        f"<td class='{'okc' if d.get('jats_valid') and d.get('alto_valid') else 'badc'}'>{'valid' if d.get('jats_valid') and d.get('alto_valid') else 'NO'}</td>"
        f"<td class='{'okc' if (d.get('title_sim') or 0) >= .6 else 'badc'}'>{'yes' if (d.get('title_sim') or 0) >= .6 else ('—' if not d.get('cat_title') else 'no')}</td>"
        f"<td>{d.get('peak_mb') or ''}</td><td>{(d.get('wall_s') or 0) / 60:.1f}</td></tr>" for d in docs)
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Inkscript At Scale</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono&family=IBM+Plex+Sans+Arabic:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style></head><body><div class="wrap">
<h1>{t['documents']} scanned articles through the whole product</h1>
<p class="lede">Every document went through <code>inkscript native --vector --verify --xml --trust</code> and then <code>inkscript fix --apply</code>:
the PDF whose text is the printed ink, a copy with uncertain words highlighted, the article as JATS, every word as ALTO, Quran quotations checked
and corrected. 127 are every scan of experiment 19's random draw from the archive; {t['documents'] - 127 if t['documents'] > 127 else 0} were drawn fresh by decade, one per journal.
None of them tuned any rule. Experiment 28, built 6–7 October 2026.</p>
<div class="figs">{''.join(f'<div class="fig"><b>{a}</b><span>{b}</span></div>' for a, b in figs)}</div>

<h2>Across the documents</h2>
<p class="lede">One dot per document; hover a dot for its id, year and value. The weakest are named under each line.</p>
{''.join(strips)}

<h2>By decade of printing</h2>
<p class="lede">The catalogue's year. The grey number at the end of each bar is how many documents the decade holds.</p>
<div class="barsgrid">{''.join(barsh)}</div>

<h2>What broke</h2>
<p class="lede">Each kind of failure found in the set, how often, and real examples (thumbnails of the trust copy: amber = flagged word, or the scan).</p>
{''.join(failure_section(f) for f in fails) or '<p>(not yet written)</p>'}

<h2>A gallery of documents</h2>
<p class="lede">The faithful PDF's page with the marks its ALTO file carries — amber flagged, green a word corrected from its verse, dashed blue a Quran quotation (opens the verse) — beside what the JATS file says about the article. Hover a mark for the word.</p>
{''.join(doc_section(s, p, summ) for s, p in picks)}

<h2>Every document</h2>
<details><summary>Show the table ({t['documents']} rows)</summary>
<div class="tablewrap"><table><thead><tr><th>document</th><th>journal</th><th>year</th><th>pages</th><th>words intact</th><th>lines in order</th><th>letters</th><th>flagged</th><th>quotations</th><th>corrected</th><th>XML</th><th>title = catalogue</th><th>peak MB</th><th>min</th></tr></thead>
<tbody>{rows}</tbody></table></div></details>
<footer>Quran verse text: Tanzil Project (Simple v1.1), CC BY 3.0, tanzil.net. Flagged words are candidates to check, not errors (about one flag in seven is a real error, experiment 27).
Titles and authors are scored against the MARC catalogue (letters-only similarity ≥ 0.6). experiments/28_scale (showcase.py).</footer>
</div></body></html>"""
    out = OUT / "showcase.html"
    out.write_text(body, encoding="utf-8")
    print(out, f"{len(body) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
