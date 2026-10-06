"""The owner's page: a few documents of the product set as they come out, the set's numbers beside them.

    python showcase.py STEM[:PAGE] ...        -> out/showcase.html  (self-contained: page images embedded)

For each document: one page of the faithful PDF with the trust marks tinted from its ALTO file (amber: flagged,
green underline: verified, dashed blue: a Quran quotation, linked to tanzil.net), tap or hover for a word's id,
reading, confidence and reasons; beside it the JATS file as a readable outline (front matter, sections, notes,
quotations with their verses), and the two XML elements that describe one word. Numbers from out/set/summary.json.
"""
import base64
import html
import json
import re
import sys
from pathlib import Path

from lxml import etree

HERE = Path(__file__).resolve().parent
SET = HERE / "out" / "set"
A = "{http://www.loc.gov/standards/alto/ns-v4#}"
XL = "{http://www.w3.org/1999/xlink}"
E = html.escape


def find(stem):
    for d in sorted(SET.glob("w*")):
        if (d / f"{stem}.alto.xml").exists():
            return d
    raise SystemExit(f"{stem}: not built")


def alto_page(path, page):
    t = etree.parse(str(path))
    tags = {}
    for tg in t.iter(A + "OtherTag"):
        tags[tg.get("ID")] = dict(label=tg.get("LABEL"), uri=tg.get("URI"), desc=tg.get("DESCRIPTION"), type=tg.get("TYPE"))
    pg = t.find(f".//{A}Page[@ID='page{page}']")
    W, H = float(pg.get("WIDTH")), float(pg.get("HEIGHT"))
    words = []
    for s in pg.iter(A + "String"):
        refs = (s.get("TAGREFS") or "").split()
        alts = [(a.get("PURPOSE"), a.text) for a in s.findall(A + "ALTERNATIVE")]
        words.append(dict(id=s.get("ID"), text=s.get("CONTENT"), wc=s.get("WC"),
                          box=[float(s.get(k)) for k in ("HPOS", "VPOS", "WIDTH", "HEIGHT")],
                          mark=next((r.split(".")[1] for r in refs if r.startswith("trust.")), None),
                          why=[tags[r]["label"] for r in refs if r.startswith("why.")],
                          quote=next((r for r in refs if r.startswith("quran")), None), alts=alts,
                          line=s.getparent().get("ID"), xml=re.sub(r' xmlns(:\w+)?="[^"]*"', "", etree.tostring(s, encoding="unicode")).strip()))
    return W, H, words, tags


def page_choice(path):
    """The page with the most quotation words, then the most flagged words."""
    t = etree.parse(str(path))
    best = None
    for pg in t.iter(A + "Page"):
        refs = [s.get("TAGREFS") or "" for s in pg.iter(A + "String")]
        sc = (sum("quran" in r for r in refs), sum("trust.flagged" in r for r in refs))
        if best is None or sc > best[0]:
            best = (sc, int(pg.get("PHYSICAL_IMG_NR")))
    return best[1]


def render(pdf, page, width=900):
    import pymupdf
    d = pymupdf.open(str(pdf))
    p = d[page - 1]
    pix = p.get_pixmap(matrix=pymupdf.Matrix(width / p.rect.width, width / p.rect.width))
    data = pix.tobytes("jpeg", jpg_quality=72)
    d.close()
    return "data:image/jpeg;base64," + base64.b64encode(data).decode()


def jats_outline(path):
    t = etree.parse(str(path))
    r = t.getroot()
    g = lambda x: (r.findtext(x) or "").strip()
    out = dict(title=g(".//article-title"), subject=g(".//subject"), fpage=g(".//fpage"), lpage=g(".//lpage"),
               volume=g(".//volume"), issue=g(".//issue"), id=g(".//article-id"),
               authors=[(c.findtext("string-name") or "").strip() for c in r.iter("contrib")],
               sections=[" ".join("".join(s.find("title").itertext()).split()) for s in r.iter("sec") if s.find("title") is not None],
               body_p=len(r.findall("./body//p")), fns=len(r.findall(".//fn")), xrefs=len(r.findall(".//xref")),
               refs=len(r.findall(".//ref")), quotes=[], first_p="")
    fp = r.find("./body//p")
    if fp is not None:
        out["first_p"] = " ".join("".join(fp.itertext()).split())[:260]
    nc = r.find(".//named-content[@content-type='quran']")
    out["nc_xml"] = re.sub(r' xmlns(:\w+)?="[^"]*"', "", etree.tostring(nc, encoding="unicode", with_tail=False)).strip() if nc is not None else ""
    for p in r.iterfind(".//notes/p[@id]"):
        link = p.find("ext-link")
        verse = p.find("named-content")
        rest = (verse.tail or "").strip(" —") if verse is not None else ""
        out["quotes"].append(dict(label=link.text, href=link.get(XL + "href"), verse=verse.text if verse is not None else "",
                                  rest=rest))
    return out


CSS = """
:root{--bg:#f3f4f6;--panel:#ffffff;--fg:#1b2230;--muted:#5d6676;--rule:#d9dde4;--accent:#1f4fa3;
--flag:#e8a317;--flagfill:rgba(232,163,23,.38);--ok:#1e8a4c;--quote:#2c6fd6;--code:#eef0f4;
--display:"IBM Plex Sans Condensed","Arial Narrow",system-ui,sans-serif;--body:"IBM Plex Sans","IBM Plex Sans Arabic",system-ui,sans-serif;
--ar:"IBM Plex Sans Arabic","Noto Naskh Arabic","Geeza Pro",serif;--mono:"IBM Plex Mono",ui-monospace,Menlo,monospace}
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){--bg:#12151b;--panel:#1a1f27;--fg:#e4e8ef;--muted:#9aa3b2;--rule:#2c333e;
--accent:#8fb4ff;--flag:#f0b43a;--flagfill:rgba(240,180,58,.40);--ok:#4cc27e;--quote:#6ea3ff;--code:#222833;color-scheme:dark}}
:root[data-theme="dark"]{--bg:#12151b;--panel:#1a1f27;--fg:#e4e8ef;--muted:#9aa3b2;--rule:#2c333e;--accent:#8fb4ff;--flag:#f0b43a;
--flagfill:rgba(240,180,58,.40);--ok:#4cc27e;--quote:#6ea3ff;--code:#222833;color-scheme:dark}
*{box-sizing:border-box}
body{margin:0;background:var(--bg);color:var(--fg);font:15px/1.55 var(--body)}
.wrap{max-width:1180px;margin:0 auto;padding-inline:16px;padding-block:28px 60px}
h1,h2,h3{font-family:var(--display);text-wrap:balance;margin:0;line-height:1.15}
h1{font-size:2rem;font-weight:600;letter-spacing:-.01em}
h2{font-size:1.45rem;font-weight:600}
h3{font-size:.8rem;text-transform:uppercase;letter-spacing:.08em;color:var(--muted);font-weight:600}
p{max-width:68ch}
.lede{color:var(--muted);margin:.5rem 0 0}
.figs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:1px;background:var(--rule);border:1px solid var(--rule);margin:22px 0 10px}
.fig{background:var(--panel);padding:12px 14px}
.fig b{display:block;font:600 1.5rem/1.1 var(--display);font-variant-numeric:tabular-nums}
.fig span{color:var(--muted);font-size:.82rem}
.files{display:flex;flex-wrap:wrap;gap:8px;margin:14px 0 0}
.files code{font:12.5px var(--mono);background:var(--code);padding:3px 7px;border-radius:3px}
.doc{margin-top:46px;border-top:2px solid var(--fg);padding-top:14px}
.dochead{display:flex;flex-wrap:wrap;gap:6px 18px;align-items:baseline}
.dochead .meta{color:var(--muted);font:13px var(--mono)}
.grid{display:grid;grid-template-columns:minmax(0,1.05fr) minmax(0,1fr);gap:22px;margin-top:14px}
@media (max-width:820px){.grid{grid-template-columns:1fr}.figs{grid-template-columns:repeat(2,minmax(0,1fr))}}
.page{position:relative;background:var(--panel);border:1px solid var(--rule);align-self:start}
.page img{display:block;width:100%;height:auto}
.page svg{position:absolute;inset:0;width:100%;height:100%}
.w{fill:transparent;cursor:pointer}
.w.flagged{fill:var(--flagfill);stroke:var(--flag);stroke-width:3}
.w.sel{stroke:var(--accent);stroke-width:8}
.u{stroke:var(--ok);stroke-width:7}
.q{fill:none;stroke:var(--quote);stroke-width:7;stroke-dasharray:22 12}
.legend{display:flex;flex-wrap:wrap;gap:6px 16px;font-size:.82rem;color:var(--muted);margin:8px 0}
.sw{display:inline-block;width:22px;height:11px;vertical-align:-1px;margin-right:5px}
.sw.f{background:var(--flagfill);border:2px solid var(--flag)}.sw.v{border-bottom:3px solid var(--ok)}.sw.q{border:2px dashed var(--quote)}
.info{min-height:3.2em;background:var(--panel);border:1px solid var(--rule);padding:8px 12px;font-size:.88rem}
.info .ar{font:1.15rem var(--ar)}
.outline{background:var(--panel);border:1px solid var(--rule);padding:16px 18px;min-width:0}
.outline dl{display:grid;grid-template-columns:max-content minmax(0,1fr);gap:4px 14px;margin:8px 0 14px}
.outline dt{color:var(--muted);font-size:.82rem;padding-top:3px}
.outline dd{margin:0}
.ar{font-family:var(--ar);direction:rtl;unicode-bidi:isolate}
.secs{margin:6px 0 14px;padding:0 1.2em 0 0;direction:rtl;font-family:var(--ar)}
.secs li{margin:2px 0}
.qs{list-style:none;padding:0;margin:6px 0 0;display:grid;gap:8px}
.qs li{border-inline-start:3px solid var(--quote);padding:2px 10px}
.qs a{color:var(--accent);font-weight:600}
.qs .v{font:1.05rem/1.9 var(--ar);direction:rtl;display:block}
.qs .d{color:var(--muted);font:0.92rem var(--ar);direction:rtl;display:block}
.qs .d.bad{color:var(--flag)}
pre{background:var(--code);padding:10px 12px;overflow-x:auto;font:12px/1.5 var(--mono);margin:6px 0 12px;max-width:100%}
.tablewrap{overflow-x:auto;margin-top:12px;border:1px solid var(--rule);background:var(--panel)}
table{border-collapse:collapse;width:100%;font-size:.84rem;font-variant-numeric:tabular-nums}
th,td{padding:6px 9px;border-bottom:1px solid var(--rule);text-align:right;white-space:nowrap}
th:first-child,td:first-child{text-align:left}
th{font-weight:600;color:var(--muted);font-size:.76rem;text-transform:uppercase;letter-spacing:.05em}
.okc{color:var(--ok);font-weight:600}.badc{color:var(--flag);font-weight:600}
a:focus-visible,.w:focus-visible{outline:3px solid var(--accent)}
footer{margin-top:40px;color:var(--muted);font-size:.82rem}
"""

JS = """
document.querySelectorAll('.page svg').forEach(svg=>{
 const info=document.getElementById(svg.dataset.info);
 svg.addEventListener('click',e=>{const r=e.target.closest('.w');if(!r)return;
  svg.querySelectorAll('.sel').forEach(x=>x.classList.remove('sel'));r.classList.add('sel');
  const d=r.dataset;let h=`<b>${d.id}</b> · <span class="ar">${d.t}</span> · confidence ${d.wc||'—'} · <b>${d.m||'punctuation, not assessed'}</b>`;
  if(d.why)h+=` — ${d.why}`; if(d.alt)h+=`<br>${d.alt}`; if(d.q)h+=`<br>Quran quotation: <a href="${d.qu}" target="_blank" rel="noopener">${d.ql}</a> (${d.qd})`;
  info.innerHTML=h;});
});
"""


def doc_section(stem, page, summ):
    d = find(stem)
    page = page or page_choice(d / f"{stem}.alto.xml")
    W, H, words, tags = alto_page(d / f"{stem}.alto.xml", page)
    img = render(d / f"{stem}.pdf", page)
    o = jats_outline(d / f"{stem}.jats.xml")
    s = next((x for x in summ["docs"] if x["doc"] == stem), {})
    rects, unders, quotes = [], [], {}
    for w in words:
        x, y, ww, hh = w["box"]
        q = tags.get(w["quote"]) if w["quote"] else None
        alt = "; ".join(("Azure read" if p == "azure-reading" else "the verse has") + f" <span class='ar'>{E(t or '')}</span>" for p, t in w["alts"])
        rects.append(f'<rect class="w {w["mark"] or ""}" x="{x:.0f}" y="{y:.0f}" width="{ww:.0f}" height="{hh:.0f}" '
                     f'data-id="{w["id"]}" data-t="{E(w["text"])}" data-wc="{w["wc"] or ""}" data-m="{w["mark"] or ""}" '
                     f'data-why="{E(", ".join(w["why"]))}" data-alt="{E(alt)}"'
                     + (f' data-q="1" data-qu="{q["uri"]}" data-ql="{E(q["label"])}" data-qd="{E(q["desc"])}"' if q else "")
                     + f'><title>{E(w["text"])} · {w["mark"] or "-"}{" · " + E(", ".join(w["why"])) if w["why"] else ""}</title></rect>')
        if w["mark"] == "verified":
            unders.append(f'<line class="u" x1="{x:.0f}" x2="{x + ww:.0f}" y1="{y + hh + 4:.0f}" y2="{y + hh + 4:.0f}"/>')
        if q:
            quotes.setdefault((w["quote"], w["line"]), []).append(w["box"])
    qrects = []
    for (qid, _), bs in quotes.items():
        x0 = min(b[0] for b in bs) - 6; y0 = min(b[1] for b in bs) - 6
        x1 = max(b[0] + b[2] for b in bs) + 6; y1 = max(b[1] + b[3] for b in bs) + 6
        qrects.append(f'<a href="{tags[qid]["uri"]}" target="_blank" rel="noopener"><rect class="q" x="{x0:.0f}" y="{y0:.0f}" '
                      f'width="{x1 - x0:.0f}" height="{y1 - y0:.0f}"><title>{E(tags[qid]["label"])}: {E(tags[qid]["desc"])}</title></rect></a>')
    nflag = sum(w["mark"] == "flagged" for w in words)
    nver = sum(w["mark"] == "verified" for w in words)
    sample = next((w for w in words if w["quote"] and w["mark"] == "flagged"), None) or \
        next((w for w in words if w["mark"] == "flagged"), None) or (words[0] if words else None)
    meta = []
    if s.get("year"):
        meta.append(str(s["year"]))
    meta.append(f'{s.get("pages", "?")} pages')
    meta.append(f'page {page} shown')
    fr = []
    if o["subject"]:
        fr.append(("rubric", f'<span class="ar">{E(o["subject"])}</span>'))
    fr.append(("title", f'<span class="ar">{E(o["title"])}</span>' if o["title"] else "<i>not found by the position rules</i>"))
    if o["authors"]:
        fr.append(("author", ", ".join(f'<span class="ar">{E(a)}</span>' for a in o["authors"])))
    fr.append(("id", f'{E(o["id"])} · volume {E(o["volume"])}, issue {E(o["issue"])}'))
    if o["fpage"]:
        fr.append(("pages", f'{E(o["fpage"])}–{E(o["lpage"])} (printed page numbers)'))
    fr.append(("body", f'{o["body_p"]} paragraphs, {len(o["sections"])} sections'))
    fr.append(("notes", f'{o["fns"]} footnotes, {o["xrefs"]} markers linked to them' + (f', {o["refs"]} references' if o["refs"] else "")))
    secs = "".join(f"<li>{E(x)}</li>" for x in o["sections"][:8]) + ("<li>…</li>" if len(o["sections"]) > 8 else "")
    qs = "".join(f'<li><a href="{q["href"]}" target="_blank" rel="noopener">{E(q["label"])}</a>'
                 f'<span class="v">{E(q["verse"])}</span><span class="d{" bad" if "يختلف" in q["rest"] else ""}">{E(q["rest"])}</span></li>'
                 for q in o["quotes"][:6])
    more = f'<p class="lede">… and {len(o["quotes"]) - 6} more in the file.</p>' if len(o["quotes"]) > 6 else ""
    return f"""
<section class="doc" id="d{stem}">
 <div class="dochead"><h2>{E(stem)}</h2><span class="meta">{" · ".join(meta)}</span></div>
 <p class="lede">{s.get('intact', 0):,}/{s.get('words', 0):,} words intact and {s.get('in_order', 0)}/{s.get('lines', 0)} lines in order in Chrome's engine ·
 letters selectable in {100 * s.get('letters_cut', 0) / max(1, s.get('letters_words', 1)):.1f}% of words ·
 {s.get('flagged') or 0} of {s.get('assessed') or 0} words flagged ({100 * (s.get('flagged') or 0) / max(1, s.get('assessed') or 1):.1f}%) ·
 {s.get('quotes') or 0} Quran quotations, {s.get('quotes_equal') or 0} equal to the verse ·
 JATS {'valid' if s.get('jats_valid') else 'INVALID'}, ALTO {'valid' if s.get('alto_valid') else 'INVALID'} ·
 trust PDF {'identical text' if s.get('trust_pdfs_ok') else 'CHECK FAILED'}</p>
 <div class="grid">
  <div>
   <div class="legend"><span><i class="sw f"></i>flagged ({nflag} on this page)</span><span><i class="sw v"></i>verified ({nver})</span><span><i class="sw q"></i>Quran quotation (opens the verse)</span></div>
   <div class="page"><img src="{img}" alt="Page {page} of {E(stem)}, from the faithful PDF">
    <svg viewBox="0 0 {W:.0f} {H:.0f}" preserveAspectRatio="none" data-info="i{stem}">{''.join(rects)}{''.join(unders)}{''.join(qrects)}</svg></div>
   <div class="info" id="i{stem}">Tap or hover a word on the page to see what the ALTO file holds for it.</div>
  </div>
  <div class="outline">
   <h3>The article, from {E(stem)}.jats.xml</h3>
   <dl>{''.join(f'<dt>{k}</dt><dd>{v}</dd>' for k, v in fr)}</dl>
   {'<h3>Sections</h3><ol class="secs">' + secs + '</ol>' if secs else ''}
   {'<h3>First paragraph</h3><p class="ar" style="font-size:1.02rem">' + E(o["first_p"]) + '…</p>' if o["first_p"] else ''}
   {'<h3>Quran quotations, checked against the verse</h3><ul class="qs">' + qs + '</ul>' + more if qs else ''}
   <h3 style="margin-top:14px">One word in the ALTO file</h3>
   <pre>{E(sample["xml"]) if sample else ''}</pre>
   {'<h3>A quotation in the JATS file</h3><pre>' + E(o["nc_xml"][:700]) + '</pre>' if o["nc_xml"] else ''}
  </div>
 </div>
</section>"""


def main():
    summ = json.loads((SET / "summary.json").read_text(encoding="utf-8"))
    t = summ["total"]
    picks = []
    for a in sys.argv[1:]:
        stem, _, pg = a.partition(":")
        picks.append((stem, int(pg) if pg else None))
    pc = lambda a, b: f"{100 * a / max(1, b):.2f}%"
    figs = [(f"{t['documents']} · {t['pages']}", "documents · pages, built end to end"),
            (pc(t["intact"], t["words"]), f"words intact in Chrome's engine ({t['intact']:,}/{t['words']:,})"),
            (pc(t["in_order"], t["lines"]), f"lines in reading order ({t['in_order']:,}/{t['lines']:,})"),
            (f"{100 * t['letters_cut'] / max(1, t['letters_words']):.1f}%", "words with every letter selectable"),
            (f"{100 * t['flagged'] / max(1, t['assessed']):.1f}%", f"words flagged to check ({t['flagged']:,} of {t['assessed']:,})"),
            (f"{t['quotes_equal']}/{t['quotes']}", f"Quran quotations equal to the verse; {t['quotes_differ']} differ"),
            (f"{t['jats_valid']}/{t['documents']}", "JATS and ALTO files valid against the official schemas"),
            (f"{t['trust_pdfs_ok']}/{t['documents']}", "trust PDFs: same bytes first, same text in pdfium")]
    rows = []
    for d in summ["docs"]:
        rows.append(f"<tr><td><a href='#d{d['doc']}'>{E(d['doc'])}</a></td><td>{d['year'] or ''}</td><td>{d['pages']}</td>"
                    f"<td>{d['intact']:,}/{d['words']:,}</td><td>{d['in_order']}/{d['lines']}</td>"
                    f"<td>{100 * d['letters_cut'] / max(1, d['letters_words']):.1f}%</td>"
                    f"<td>{100 * (d['flagged'] or 0) / max(1, d['assessed'] or 1):.1f}%</td><td>{d['verified'] or 0}</td>"
                    f"<td>{d['quotes_equal'] or 0}/{d['quotes'] or 0}</td>"
                    f"<td class='{'okc' if d['jats_valid'] and d['alto_valid'] else 'badc'}'>{'valid' if d['jats_valid'] and d['alto_valid'] else 'no'}</td>"
                    f"<td class='{'okc' if d['trust_pdfs_ok'] else 'badc'}'>{'same' if d['trust_pdfs_ok'] else 'no'}</td>"
                    f"<td>{d.get('peak_mb', '')}</td><td>{round(d.get('wall_s', 0) / 60, 1) or ''}</td></tr>")
    body = f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<title>Inkscript Product Set</title>
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400&family=IBM+Plex+Sans+Arabic:wght@400;600&family=IBM+Plex+Sans+Condensed:wght@600&family=IBM+Plex+Sans:wght@400;600&display=swap">
<style>{CSS}</style></head><body><div class="wrap">
<h1>Twenty scanned articles, built into the product</h1>
<p class="lede">Each document went through <code>inkscript native --vector --verify --xml --trust</code>: the faithful PDF whose text is the printed ink,
the article as publishers keep it (JATS), every word with its box as libraries keep OCR (ALTO), and a copy of the PDF with the uncertain words highlighted.
Numbers are the build's own checks; letter coverage from <code>coverage.py</code>.</p>
<div class="figs">{''.join(f'<div class="fig"><b>{a}</b><span>{b}</span></div>' for a, b in figs)}</div>
<div class="files"><code>&lt;stem&gt;.pdf</code><code>&lt;stem&gt;_vector.pdf</code><code>&lt;stem&gt;_trust.pdf</code><code>&lt;stem&gt;_vector_trust.pdf</code><code>&lt;stem&gt;.jats.xml</code><code>&lt;stem&gt;.alto.xml</code><code>&lt;stem&gt;.shapes.json</code></div>
{''.join(doc_section(s, p, summ) for s, p in picks)}
<section class="doc"><h2>All twenty documents</h2>
<p class="lede">Years are the catalogue's, where experiment 19 fetched it (the other eight are Quran-heavy books from experiment 16). Peak memory and minutes per document, one process each.</p>
<div class="tablewrap"><table><thead><tr><th>document</th><th>year</th><th>pages</th><th>words intact</th><th>lines in order</th><th>letters</th><th>flagged</th><th>verified</th><th>quotations equal</th><th>XML</th><th>trust PDF</th><th>peak MB</th><th>min</th></tr></thead>
<tbody>{''.join(rows)}</tbody></table></div></section>
<footer>Quran verse text: Tanzil Project (Simple v1.1), CC BY 3.0, <a href="https://tanzil.net" target="_blank" rel="noopener">tanzil.net</a>, reproduced verbatim.
Flagged words are candidates to check on the ink, not errors: on experiment 22's judged sample about one flag in seven is a real error, and 0.43% of unflagged words are wrong.
Built by experiments/24_product (showcase.py).</footer>
</div><script>{JS}</script></body></html>"""
    out = HERE / "out" / "showcase.html"
    out.write_text(body, encoding="utf-8")
    print(out, f"{len(body) / 1e6:.1f} MB")


if __name__ == "__main__":
    main()
