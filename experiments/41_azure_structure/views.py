"""Experiment 41: two side-by-side views of Argon's 55 articles (no Gemini calls; local rendering only).

The owner did not like the flowing reader (reader.py): they want the original on one side and ours on the other.

  out/views/index.html                 every article, with links to both views
  out/views/pages/<stem>.html          PAGE BY PAGE: one row per printed page, the scan on the left and our rebuilt
                                       content of exactly that page on the right (running heads and page numbers
                                       muted, headings, paragraphs, verse in two half-lines, real tables, KaTeX
                                       equations, figure crops, that page's footnotes at its foot, misprint flags,
                                       Gemini's fixes behind a toggle). Pointing at a block outlines it on the scan.
                                       On a phone the scan stacks above ours, page by page.
  out/views/mirror/<stem>.html         MIRROR: a born-digital twin of each page. A page box with the scan's aspect
                                       ratio; every Azure line (after Gemini's splits and fixes) placed at its own box,
                                       its text in Scheherazade New (Latin lines in Noto Serif), sized from the box
                                       height of its block and stretched or squeezed (scaleX, in the browser, after
                                       the font loads) to the box width; figures as crops at their boxes, equations as
                                       KaTeX fitted to their box, table cells at their boxes. Scan beside it at the same
                                       size; "Blocks" outlines blocks by type; "Overlay" lays the twin on the scan with
                                       an opacity slider.
  out/views/scans/, figs/, thumbs/     JPEGs hard-linked (or copied) from out/reader/ (made there by reader.py; made
                                       here from out/pages/ if absent)

    /home/yassine/inkscript/.venv/bin/python views.py [--stems ...]

Text, blocks, fixes, flags and calls come from reader.capture (structure.assemble on out/argon/raw/, nothing written
to out/argon). Browser libraries: Scheherazade New and Noto Serif (Google Fonts), KaTeX 0.16.9 (cdnjs).
"""
from __future__ import annotations

import argparse
import html
import json
import os
import re
import shutil
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import reader as R  # noqa: E402  (patches structure.Store.text_html: fixes as span.fix, calls as sup.call)
import structure as ST  # noqa: E402
from structure import OUT, is_rtl, sample  # noqa: E402

VIEWS = OUT / "views"
E = html.escape
KATEX = R.KATEX
FONTS = ("https://fonts.googleapis.com/css2?family=Scheherazade+New:wght@400;700"
         "&family=Noto+Serif:ital,wght@0,400;0,700;1,400&display=swap")
FS_K = 0.72             # mirror: font-size = FS_K x the block's median line-box height (tuned by eye on the showcase)

# ------------------------------------------------------------------------------------------------ images


def _link(src: Path, dst: Path):
    dst.parent.mkdir(parents=True, exist_ok=True)
    if dst.exists():
        return
    try:
        os.link(src, dst)
    except OSError:
        shutil.copy2(src, dst)


def _via_reader(fn, rel, *args):
    """Reuse reader.py's JPEG from out/reader/<rel>; make it there if absent; link it into out/views/<rel>."""
    src = R.READER / rel
    if not src.exists():
        out = fn(*args)
        if out is None:
            return None
    _link(src, VIEWS / rel)
    return rel


def scan(a, p):
    return _via_reader(R.make_scan, f"scans/{a['stem']}/p{p:03d}.jpg", a, p)


def fig(a, p, k, box):
    return _via_reader(R.make_fig, f"figs/{a['stem']}/p{p:03d}-{k}.jpg", a, p, k, box)


def thumb(a):
    return _via_reader(R.make_thumb, f"thumbs/{a['stem']}.jpg", a)


# ------------------------------------------------------------------------------------------------ shared


def line_html(S, lid, calls):
    cs = [c for c in calls if str(c.get("line")) in (lid, S.lines[lid].get("split_of") or "\0")]
    return S.text_html(lid, cs)


def note_items(recs, called=None):
    """Footnote blocks of one page -> list of (fn_id, dir, inner html, marker)."""
    out = []
    for rec in recs:
        tag, at, inner = R.split_tag(rec["html"])
        d = "rtl" if ' dir="rtl"' in at else "ltr"
        if rec["continued"] and not out:
            out.append(dict(fid=None, dir=d, parts=[inner], marker=None, cont=True))
        elif rec["continued"] and out:
            out[-1]["parts"].append(inner)
        else:
            out.append(dict(fid=rec.get("fn_id"), dir=d, parts=[inner], marker=rec.get("marker"), cont=False))
    return out


def note_li(n):
    mk = n["marker"] or ""
    first = R.num_ar(R.plain(n["parts"][0]))
    starts = first[:len(mk) + 2].lstrip("( ").startswith(R.num_ar(mk)) if mk else True
    idattr = f' id="n-{E(n["fid"])}"' if n["fid"] else ""
    cont = '<span class="contmark" title="continued from the previous page">&#8627;</span> ' if n["cont"] else ""
    return (f'<li{idattr} dir="{n["dir"]}">{cont}' + ("" if starts else f'<span class="nmk">{E(mk)}</span> ')
            + " ".join(n["parts"]) + "</li>")


def doc_info(a, cap):
    meta = cap["meta"] or {}
    lang, ddir = R.lang_dir(meta, cap["blocks"])
    title = meta.get("title") or next((R.plain(b["html"]) for b in cap["blocks"] if b["type"] in ("title", "heading")),
                                      a["stem"])
    bits = [x for x in [meta.get("journal") or a.get("journal"), str(meta.get("year") or a.get("year") or "")] if x]
    return lang, ddir, title, " · ".join(bits)


# ------------------------------------------------------------------------------------------------ view 1: pages


def page_content(a, cap, p, fig_k):
    S = cap["S"]
    recs = [r for r in cap["blocks"] if r["page"] == p]
    body, notes, open_list, foot = [], [], None, []
    for rec in recs:
        T = rec["type"]
        if T == "footnote":
            notes.append(rec)
            continue
        want = ("references" if T == "reference" else "list") if T in R.LISTS else None
        if want != open_list:
            if open_list:
                body.append("</ol>")
            if want:
                body.append(f'<ol class="{want}">')
            open_list = want
        sa = R.seg_attrs(rec, S)
        cont = ('<span class="contmark" title="continues from the previous page">&#8627;</span>'
                if rec["continued"] else "")
        tag, at, inner = R.split_tag(rec["html"])
        if T in ("header", "footer"):
            (foot if T == "footer" and rec is not recs[0] else body).append(
                f'<div class="furn"{sa} dir="auto">{inner}</div>')
        elif T == "figure":
            box = rec.get("fig_box")
            fig_k[p] = fig_k.get(p, 0) + 1
            src = fig(a, p, fig_k[p], box) if box else None
            desc = rec.get("description") or ""
            capt = ""           # a figure's own lines are the words inside the drawing: already in the crop
            fw = min(100, max(25, round((box[2] - box[0]) / 10 * 1.15))) if box else 100
            im = (f'<img src="../{src}" alt="{E(desc)}" title="{E(desc)}" loading="lazy" style="width:{fw}%">' if src else
                  f'<div class="fig-missing">[{E(desc) or "figure"}]</div>')
            body.append(f'<figure class="fig"{sa}>{im}' + (f'<figcaption dir="auto">{capt}</figcaption>' if capt else "")
                        + "</figure>")
        elif T in ("table", "verse", "equation") or tag in ("table", "div"):
            h = re.sub(r"^<(\w+)", lambda m: f"<{m.group(1)}{sa}", re.sub(r' data-lines="[^"]*"', "", rec["html"]), 1)
            if T == "table":
                td = re.search(r' dir="(\w+)"', h)
                h = f'<div class="tablewrap" dir="{td.group(1) if td else "auto"}">{h}</div>'
            body.append(cont + h if cont and T != "table" else h)
        else:
            if T == "title":
                tag = "h1"
            at = R.redir(re.sub(r' data-bbox="[^"]*"', "", at), inner)
            cls = ' class="other"' if T == "other" and "class=" not in at else ""
            body.append(f"<{tag}{cls}{at}{sa}>{cont}{inner}</{tag}>")
        for h in rec.get("missed_html", []):
            body.append(re.sub(r"^<p ", '<p class="added" ', h))
    if open_list:
        body.append("</ol>")
    nl = note_items(notes)
    if nl:
        body.append('<section class="pnotes"><ol>' + "".join(note_li(n) for n in nl) + "</ol></section>")
    body += foot
    return "\n".join(body)


def build_pages(a, cap):
    stem, pages, S = a["stem"], cap["pages"], cap["S"]
    lang, ddir, title, sub = doc_info(a, cap)
    lz = R.L10N.get(lang, R.L10N["en"])
    fig_k, rows = {}, []
    for i, p in enumerate(pages):
        W, H = S.dims[p]
        src = scan(a, p)
        rows.append(
            f'<section class="prow" id="p{p}" data-p="{p}">'
            f'<div class="plab"><a href="#p{p}">page {p}</a><span>{i + 1} / {len(pages)}</span></div>'
            f'<div class="pscan"><div class="scanwrap" style="aspect-ratio:{W}/{H}">'
            f'<img src="../{src}" alt="scan of page {p}" loading="{"eager" if i < 2 else "lazy"}" '
            f'width="{W}" height="{H}"><div class="hboxes"></div></div></div>'
            f'<div class="pours" dir="{ddir}" lang="{E(lang)}">{page_content(a, cap, p, fig_k)}</div></section>')
    fix_n = sum(r.count('class="fix"') for r in rows)
    sic_n = sum(r.count('class="sic"') for r in rows)
    head = (f'<header class="vhead" dir="{ddir}"><h1 dir="auto">{E(title)}</h1><p class="kicker" dir="auto">{E(sub)}</p>'
            f'<p class="provenance" dir="ltr">{len(pages)} pages · scan on the left, our rebuild of the same page on '
            f'the right (text: Azure, structure: Gemini 4 Argon, exp 41) · {fix_n} fixes of Azure (button '
            f'<b>Fixes</b>) · {sic_n} suspected misprints (wavy underline, kept as printed) · '
            f'<a href="../mirror/{stem}.html">mirror view</a></p></header>')
    page = PAGE_TPL.format(lang=E(lang), title=E(title[:90]), fonts=FONTS, katex=KATEX, css=BASE_CSS + PAGES_CSS,
                           bar=bar(title, [("fixes", "Fixes", "Highlight Gemini's fixes of Azure's misreadings (f)")],
                                   ("mirror", stem)),
                           body=head + '<main class="prows">' + "\n".join(rows) + "</main>",
                           data=json.dumps(dict(stem=stem, lang=lang)), js=COMMON_JS + PAGES_JS)
    (VIEWS / "pages").mkdir(parents=True, exist_ok=True)
    (VIEWS / "pages" / f"{stem}.html").write_text(page, encoding="utf-8")
    return lz


# ------------------------------------------------------------------------------------------------ view 2: mirror


BIG = {"title", "heading", "byline", "figure"}
BODY = {"paragraph", "quote", "abstract", "list_item", "reference", "verse", "keywords"}


def line_rtl(text, block_rtl):
    """A line with Arabic or Latin letters reads by them; a line of digits and signs (a table cell "-0.26375",
    "0.3287**") takes its block's direction."""
    t = R.plain(text)
    if not ST.AR.search(t) and not ST.LA.search(t):
        return block_rtl
    return is_rtl(t)


def pct(v, tot):
    return f"{v * 100 / tot:.3f}%"


def boxstyle(px, W, H):
    x0, y0, x1, y1 = px
    return f"left:{pct(x0, W)};top:{pct(y0, H)};width:{pct(x1 - x0, W)};height:{pct(y1 - y0, H)}"


def build_mirror(a, cap):
    stem, pages, S = a["stem"], cap["pages"], cap["S"]
    lang, ddir, title, sub = doc_info(a, cap)
    fig_k, rows, hidden_notes = {}, [], []
    stats = dict(lines=0, noise=0)
    for i, p in enumerate(pages):
        W, H = S.dims[p]
        recs = [r for r in cap["blocks"] if r["page"] == p]
        used = set()
        els = []
        tmed = {}                       # median line-box height per block type on this page: one size per kind
        for rec in recs:
            for x in rec["ids"]:
                if S.lines[x]["page"] == p:
                    tmed.setdefault(rec["type"], []).append(S.lines[x]["px"][3] - S.lines[x]["px"][1])
        bodyh = [h for k, v in tmed.items() if k in BODY for h in v]
        bmed = statistics.median(bodyh) if bodyh else None
        tmed = {k: statistics.median(v) for k, v in tmed.items()}
        for rec in recs:
            T = rec["type"]
            ids = [x for x in rec["ids"] if S.lines[x]["page"] == p]
            used.update(rec["ids"])
            calls = list(rec.get("calls") or [])
            if T == "figure" and rec.get("fig_box"):
                fig_k[p] = fig_k.get(p, 0) + 1
                src = fig(a, p, fig_k[p], rec["fig_box"])
                fb = rec["fig_box"]
                bx = [fb[0] * W / 1000, fb[1] * H / 1000, fb[2] * W / 1000, fb[3] * H / 1000]
                if src:
                    els.append(f'<img class="mfig" src="../{src}" alt="{E(rec.get("description") or "")}" '
                               f'style="{boxstyle(bx, W, H)}" loading="lazy">')
                els.append(f'<div class="blk t-figure" style="{boxstyle(bx, W, H)}" data-t="figure"></div>')
                # a figure's ids are the words inside the drawing (labels): drawn by the crop already
                continue
            pxs = [S.lines[x]["px"] for x in ids]
            if pxs:
                ub = ST.union(pxs)
                els.append(f'<div class="blk t-{T}" style="{boxstyle(ub, W, H)}" data-t="{T}"></div>')
            if T == "footnote" and not rec["continued"] and rec.get("fn_id"):
                inner = R.split_tag(rec["html"])[2]
                d = "rtl" if ' dir="rtl"' in rec["html"][:400] else "ltr"
                hidden_notes.append(f'<div hidden id="n-{E(rec["fn_id"])}" dir="{d}">{inner}</div>')
            if T == "equation" and rec.get("latex") and pxs:
                ub = ST.union(pxs)
                els.append(f'<div class="meq" style="{boxstyle(ub, W, H)}"><span class="math">'
                           f'\\[{E(rec["latex"])}\\]</span></div>')
                continue
            if T == "equation" and rec.get("latex"):
                continue
            if T == "table":
                for r in rec.get("rows") or []:
                    for c in r:
                        cb = [S.lines[x]["px"] for x in c["ids"] if S.lines[x]["page"] == p]
                        if cb:
                            els.append(f'<div class="blk cell" style="{boxstyle(ST.union(cb), W, H)}"></div>')
            bdir = ' dir="ltr"' not in (rec.get("html") or "")[:600]
            hs = [S.lines[x]["px"][3] - S.lines[x]["px"][1] for x in ids]
            hmed = statistics.median(hs) if hs else 0
            for x in ids:
                L = S.lines[x]
                h = L["px"][3] - L["px"][1]
                hf = min(hmed, tmed.get(T, hmed) * 1.1, h * 1.3) if hmed else h
                if bmed and T not in BIG:
                    hf = min(hf, bmed * 1.08)       # one tall box (vowel marks, a raised call) does not make a line big
                fs = FS_K * hf / W * 100            # in cqw (1cqw = page width / 100)
                rtl = line_rtl(L["text"], bdir)
                cls = "ln " + ("r" if rtl else "l") + (" th" if T in ("title", "heading") else "")
                els.append(f'<div class="{cls}" dir="{"rtl" if rtl else "ltr"}" data-t="{T}" '
                           f'style="{boxstyle(L["px"], W, H)};--f:{fs:.3f}"><span>{line_html(S, x, calls)}</span></div>')
                stats["lines"] += 1
        # Azure lines no block took (Gemini called them noise, or dropped them): faint, outlined with "Blocks"
        for lid, L in S.lines.items():
            if L["page"] != p or L.get("split") or lid in used:
                continue
            h = L["px"][3] - L["px"][1]
            rtl = line_rtl(L["text"], ddir == "rtl")
            els.append(f'<div class="ln noise {"r" if rtl else "l"}" dir="{"rtl" if rtl else "ltr"}" '
                       f'title="not in any block (Gemini: noise)" style="{boxstyle(L["px"], W, H)};'
                       f'--f:{FS_K * h / W * 100:.3f}"><span>{E(L["text"])}</span></div>')
            stats["noise"] += 1
        src = scan(a, p)
        rows.append(
            f'<section class="mrow" id="p{p}" data-p="{p}">'
            f'<div class="plab"><a href="#p{p}">page {p}</a><span>{i + 1} / {len(pages)}</span></div>'
            f'<div class="mpair">'
            f'<div class="mscan" style="aspect-ratio:{W}/{H}"><img src="../{src}" alt="scan of page {p}" '
            f'loading="{"eager" if i < 2 else "lazy"}" width="{W}" height="{H}"></div>'
            f'<div class="mpage" style="aspect-ratio:{W}/{H}" lang="{E(lang)}">{"".join(els)}</div>'
            f'</div></section>')
    head = (f'<header class="vhead" dir="{ddir}"><h1 dir="auto">{E(title)}</h1><p class="kicker" dir="auto">{E(sub)}</p>'
            f'<p class="provenance" dir="ltr">{len(pages)} pages · scan on the left, a born-digital twin on the right: '
            f'every Azure line at its own place, in Scheherazade New, stretched to its printed width · '
            f'{stats["lines"]} lines' + (f' ({stats["noise"]} more that no block took, faint)' if stats["noise"] else "")
            + f' · <a href="../pages/{stem}.html">page-by-page view</a></p></header>')
    tools = [("fixes", "Fixes", "Highlight Gemini's fixes of Azure's misreadings (f)"),
             ("blocks", "Blocks", "Outline the blocks by type (b)"),
             ("overlay", "Overlay", "Lay the twin over the scan (o)")]
    slider = ('<label class="ovl" title="Opacity of the twin over the scan">'
              '<input type="range" id="ov" min="0" max="100" value="60" aria-label="twin opacity"></label>')
    legend = ('<div class="legend" dir="ltr">' + "".join(
        f'<span class="lg t-{t}">{t.replace("_", " ")}</span>' for t in
        ("title", "heading", "byline", "paragraph", "abstract", "verse", "quote", "list_item", "reference", "table",
         "equation", "caption", "figure", "footnote", "header", "footer", "other")) + "</div>")
    page = PAGE_TPL.format(lang=E(lang), title=E(title[:90]), fonts=FONTS, katex=KATEX, css=BASE_CSS + MIRROR_CSS,
                           bar=bar(title, tools, ("pages", stem), extra=slider),
                           body=head + legend + '<main class="mrows">' + "\n".join(rows) + "</main>"
                           + "".join(hidden_notes),
                           data=json.dumps(dict(stem=stem, lang=lang)), js=COMMON_JS + MIRROR_JS)
    (VIEWS / "mirror").mkdir(parents=True, exist_ok=True)
    (VIEWS / "mirror" / f"{stem}.html").write_text(page, encoding="utf-8")
    return stats


# ------------------------------------------------------------------------------------------------ templates


def bar(title, tools, other, extra=""):
    kind, stem = other
    btn = "".join(f'<button type="button" data-toggle="{n}" aria-pressed="false" title="{E(t)}">{E(lab)}</button>'
                  for n, lab, t in tools)
    lab = "Mirror" if kind == "mirror" else "Page by page"
    return (f'<nav class="bar" dir="ltr"><a class="home" href="../index.html">&larr; All</a>'
            f'<span class="t" dir="auto">{E(title[:90])}</span>{btn}{extra}'
            f'<a class="tool" href="../{kind}/{stem}.html">{lab}</a>'
            f'<button type="button" id="theme" title="Light / dark">Auto</button></nav>')


BASE_CSS = R.CSS + r"""
body{font-size:18px;line-height:1.75}
.bar{gap:8px}.bar a.tool{text-decoration:none;color:var(--ink)}
.vhead{max-width:96rem;margin:0 auto;padding:20px 16px 6px}
.vhead h1{font-size:1.6em;margin:0 0 .1em}
.vhead .kicker{margin:0}
.vhead .provenance{margin:.4em 0 0}
.plab{display:flex;gap:.8em;align-items:baseline;font:600 12px/1 var(--ui);color:var(--muted);padding:0 2px 6px;
direction:ltr}
.plab a{color:var(--accent);text-decoration:none;font-size:13px}
.plab span{color:var(--faint);font-weight:500}
.math{unicode-bidi:isolate;direction:ltr}
.contmark{font:600 .8em var(--ui);color:var(--faint);margin-inline-end:.3em}
"""

PAGES_CSS = r"""
.prows{max-width:96rem;margin:0 auto;padding:8px 16px 80px}
.prow{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);grid-template-areas:"lab lab" "scan ours";
gap:0 22px;padding:18px 0 26px;border-top:1px solid var(--rule)}
.prow .plab{grid-area:lab}
.pscan{grid-area:scan;position:sticky;top:56px;align-self:start}
.scanwrap{position:relative;margin:0 auto;max-height:calc(100vh - 70px);max-width:100%}
.scanwrap img{display:block;width:100%;height:100%;object-fit:contain;background:#fff;box-shadow:var(--shadow);
border-radius:2px}
.pours{grid-area:ours;background:var(--paper);border:1px solid var(--rule);border-radius:6px;box-shadow:var(--shadow);
padding:22px 26px 18px;min-width:0}
.pours h1{font-size:1.55em;margin:.1em 0 .3em;text-align:center}
.pours h2{font-size:1.28em}.pours h3{font-size:1.12em}
.pours>*:first-child{margin-top:0}
.pours [dir="ltr"]{font-family:"Noto Serif",Georgia,serif;font-size:.86em;line-height:1.65}
.pours .katex{font-family:KaTeX_Main,"Times New Roman",serif}
.furn{font:13px/1.5 var(--ui);color:var(--faint);text-align:center;margin:0 0 .8em;font-family:var(--text)}
.furn:last-child{margin:1em 0 0}
.pnotes{margin-top:1.2em;padding-top:.6em;border-top:1px solid var(--rule);font-size:.82em;line-height:1.65}
.pnotes ol{list-style:none;margin:0;padding:0}.pnotes li{margin:0 0 .3em;padding:.1em .3em;border-radius:4px}
.pnotes li:target{background:var(--added)}
.pours .fig{margin:1em 0}
.pours .fig img{max-height:60vh}
.verse{max-width:none}
.pours table{font-size:.78em}
@media (max-width:820px){.prow{grid-template-columns:minmax(0,1fr);grid-template-areas:"lab" "scan" "ours";gap:10px}
.pscan{position:static}.scanwrap{max-height:none}.pours{padding:16px 14px}}
"""

MIRROR_CSS = r"""
.mrows{max-width:110rem;margin:0 auto;padding:8px 16px 80px}
.mrow{padding:14px 0 22px;border-top:1px solid var(--rule)}
.mpair{display:grid;grid-template-columns:minmax(0,1fr) minmax(0,1fr);gap:18px;align-items:start}
.mscan,.mpage{position:relative;width:100%;box-shadow:var(--shadow);border-radius:2px;overflow:hidden}
.mscan img{display:block;width:100%;height:100%;background:#fff}
.mpage{container-type:inline-size;background:var(--paper);color:var(--ink)}
.ln{position:absolute;display:flex;align-items:center;justify-content:flex-start;white-space:nowrap;
font-family:var(--text)}
.ln>span{display:inline-block;flex:none;font-size:calc(var(--f) * var(--z,1) * 1cqw);line-height:1;
transform-origin:100% 50%;transform:scaleX(var(--sx,1))}
.ln.l>span{transform-origin:0 50%;font-family:"Noto Serif",Georgia,serif}
.ln.th>span{font-weight:700}
.ln.noise{opacity:.35}
.ln sup.call{font-size:.55em;line-height:0}
.meq{position:absolute;display:flex;align-items:center;justify-content:center;overflow:visible}
.meq>.math{display:inline-block;transform-origin:50% 50%;white-space:nowrap}
.meq .katex-display{margin:0}
.mfig{position:absolute;object-fit:fill;background:#fff}
.blk{position:absolute;pointer-events:none;display:none;border:1px solid var(--c,#999);
background:color-mix(in srgb,var(--c,#999) 7%,transparent);border-radius:1px}
.blk.cell{border-style:dotted;background:none;--c:#2f7d6b}
body.blocks .blk{display:block}
body.blocks .ln.noise{outline:1px dashed #b00;opacity:.6}
.legend{display:none;flex-wrap:wrap;gap:4px;max-width:110rem;margin:0 auto;padding:4px 16px 0}
body.blocks .legend{display:flex}
.lg{font:11px/1 var(--ui);padding:4px 7px;border-radius:999px;border:1px solid var(--c);color:var(--ink);
background:color-mix(in srgb,var(--c) 14%,transparent)}
.t-title,.t-heading{--c:#b5442a}.t-byline{--c:#c27a1a}.t-paragraph{--c:#6b7a8f}.t-abstract{--c:#7a5aa8}
.t-keywords{--c:#7a5aa8}.t-verse{--c:#1f8a5c}.t-quote{--c:#4a8f9c}.t-list_item{--c:#3a6fb0}.t-reference{--c:#2d5a8a}
.t-table{--c:#2f7d6b}.t-equation{--c:#a83a7a}.t-caption{--c:#8a6d3b}.t-figure{--c:#d0461d}.t-footnote{--c:#8f8a30}
.t-header,.t-footer{--c:#9a9a9a}.t-other{--c:#aaa}
.ovl{display:none;align-items:center}.ovl input{width:90px}
body.overlay .ovl{display:flex}
body.overlay .mrows{max-width:62rem}
body.overlay .mpair{grid-template-columns:minmax(0,1fr)}
body.overlay .mscan,body.overlay .mpage{grid-area:1/1}
body.overlay .mpage{background:transparent;box-shadow:none;opacity:var(--ov,.6)}
body.overlay .mpage .ln{color:#c0301a}
body.overlay .mfig{opacity:.0}
@media (max-width:820px){.mpair{grid-template-columns:minmax(0,1fr);gap:10px}.bar .t{display:none}}
"""

PAGE_TPL = """<!doctype html>
<html lang="{lang}" dir="ltr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{title}</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{fonts}" rel="stylesheet">
<link rel="stylesheet" href="{katex}/katex.min.css">
<style>{css}</style></head>
<body>
{bar}
{body}
<div class="pop" role="tooltip"></div>
<script src="{katex}/katex.min.js"></script>
<script>const DOC={data};</script>
<script>{js}</script>
</body></html>
"""

COMMON_JS = R.COMMON_JS + r"""
const body=document.body;
document.querySelectorAll('.math').forEach(el=>{let s=el.textContent.trim(),d=false;
 if(s.startsWith('\\[')){d=true;s=s.slice(2,-2)}else if(s.startsWith('\\(')){s=s.slice(2,-2)}
 try{katex.render(s,el,{displayMode:d,throwOnError:false,strict:'ignore'})}catch(e){}});
const hooks={};
function setToggle(name,on){body.classList.toggle(name,on);
 document.querySelectorAll('.bar [data-toggle="'+name+'"]').forEach(b=>b.setAttribute('aria-pressed',on));
 store('views-'+name,on?'1':'0');if(hooks[name])hooks[name](on)}
document.querySelectorAll('[data-toggle]').forEach(b=>b.addEventListener('click',()=>{
 const n=b.dataset.toggle;setToggle(n,!body.classList.contains(n))}));
const pop=document.querySelector('.pop');let popFor=null,hideT=null;
function esc(s){return (s||'').replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]))}
function popHtml(el){const ar=DOC.lang==='ar';
 if(el.classList.contains('sic'))return '<span class="lab">'+(ar?'كذا في الأصل · as printed':'as printed')+
  '</span><span class="val">'+esc(el.textContent)+'</span><span class="lab" style="margin-top:.4em">'+
  (ar?'لعل الصواب · probably':'probably')+'</span><span class="val">'+esc(el.dataset.corr)+'</span>'+
  (el.dataset.why?'<span class="why">'+esc(el.dataset.why)+'</span>':'');
 if(el.classList.contains('fix'))return '<span class="lab">Azure read</span><span class="val">'+esc(el.dataset.azure)+
  '</span><span class="lab" style="margin-top:.4em">Gemini (on the scan)</span><span class="val">'+esc(el.textContent)+
  '</span>'+(el.dataset.why?'<span class="why">'+esc(el.dataset.why)+'</span>':'');
 const n=document.getElementById('n-'+el.dataset.fn);
 if(n){return '<div dir="'+n.dir+'">'+n.innerHTML+'</div>'+(n.hidden?'':'<a class="go" href="#n-'+esc(el.dataset.fn)+'">&darr; note</a>')}
 return null}
function openPop(el){const h=popHtml(el);if(!h)return;clearTimeout(hideT);popFor=el;pop.innerHTML=h;pop.classList.add('on');
 const r=el.getBoundingClientRect(),pw=pop.offsetWidth,ph=pop.offsetHeight;
 let x=Math.min(Math.max(16,r.left+r.width/2-pw/2),innerWidth-pw-16),y=r.bottom+8;
 if(y+ph>innerHeight-8)y=Math.max(8,r.top-ph-8);pop.style.left=x+'px';pop.style.top=y+'px'}
function closePop(){pop.classList.remove('on');popFor=null}
function target(e){return e.target.closest('.sic,sup.call a'+(body.classList.contains('fixes')?',.fix':''))}
document.addEventListener('click',e=>{if(e.target.closest('.pop'))return;const t=target(e);
 if(t){if(t.matches('sup.call a'))e.preventDefault();if(popFor===t)closePop();else openPop(t)}else closePop()});
if(matchMedia('(hover:hover)').matches){
 document.addEventListener('mouseover',e=>{const t=target(e);if(t&&t!==popFor)openPop(t);
  else if(!t&&!e.target.closest('.pop')&&popFor){clearTimeout(hideT);hideT=setTimeout(closePop,350)}});
 pop.addEventListener('mouseenter',()=>clearTimeout(hideT))}
addEventListener('scroll',()=>{if(popFor)closePop()},{passive:true});
addEventListener('keydown',e=>{if(e.target.closest('input,textarea')||e.metaKey||e.ctrlKey||e.altKey)return;
 const k={f:'fixes',b:'blocks',o:'overlay'}[e.key];
 if(k&&document.querySelector('.bar [data-toggle="'+k+'"]'))setToggle(k,!body.classList.contains(k));
 if(e.key==='Escape')closePop()});
"""

PAGES_JS = r"""
// pointing at a block outlines its lines on that page's scan
let hot=null;
function point(el){if(hot){hot.classList.remove('hot');const hb=hot.closest('.prow').querySelector('.hboxes');hb.innerHTML=''}
 hot=el;if(!el)return;el.classList.add('hot');const hb=el.closest('.prow').querySelector('.hboxes');
 const bb=el.dataset.lb||el.dataset.bbox;if(!bb)return;
 for(const s of bb.split(';')){const b=s.split(',').map(Number),d=document.createElement('div');
  Object.assign(d.style,{left:b[0]/10+'%',top:b[1]/10+'%',width:(b[2]-b[0])/10+'%',height:(b[3]-b[1])/10+'%'});hb.appendChild(d)}}
document.querySelectorAll('.pours').forEach(o=>{o.addEventListener('mouseover',e=>{const s=e.target.closest('[data-seg]');
 if(s!==hot)point(s)});o.addEventListener('mouseleave',()=>point(null))});
setToggle('fixes',store('views-fixes')==='1');
"""

MIRROR_JS = r"""
// fit every line to its box: font from the box height (python), then scaleX to the box width; a line far wider
// than its box (Azure's box shorter than the words) is first made smaller, so no glyph is squeezed below 70%
function fit(){const ls=[...document.querySelectorAll('.mpage .ln>span')];
 ls.forEach(s=>{s.style.removeProperty('--z');s.style.removeProperty('--sx');s.style.wordSpacing=''});
 const w1=ls.map(s=>s.offsetWidth),bw=ls.map(s=>s.parentNode.clientWidth),z=[];
 ls.forEach((s,i)=>{const k=w1[i]?bw[i]/w1[i]:1;z[i]=k<0.7?Math.max(k/0.7,0.4):1;if(z[i]!==1)s.style.setProperty('--z',z[i])});
 const w2=ls.map((s,i)=>z[i]!==1?s.offsetWidth:w1[i]),fs=ls.map(s=>parseFloat(getComputedStyle(s).fontSize)),ws=[];
 // a short line is widened first by its word spaces (as a justified print line is), up to 0.35 em a space, then stretched at most 1.3x (a split line's box,
 // cut from Azure's merged line by letter share, can be far wider than its words)
 ls.forEach((s,i)=>{const n=(s.textContent.trim().match(/\s+/g)||[]).length;ws[i]=0;
  if(n&&w2[i]&&bw[i]>w2[i]*1.02){ws[i]=Math.min((bw[i]-w2[i])/n,fs[i]*0.35);s.style.wordSpacing=ws[i].toFixed(2)+'px'}});
 const w3=ls.map((s,i)=>ws[i]?s.offsetWidth:w2[i]);
 ls.forEach((s,i)=>{if(!w3[i])return;const k=Math.min(bw[i]/w3[i],1.3);s.style.setProperty('--sx',k.toFixed(4))});
 document.querySelectorAll('.meq').forEach(m=>{const s=m.firstElementChild;s.style.transform='';
  const k=Math.min(m.clientWidth/(s.offsetWidth||1),m.clientHeight/(s.offsetHeight||1)*1.15,3);
  s.style.transform='scale('+k.toFixed(4)+')'})}
let rt=null,lastW=innerWidth;
addEventListener('resize',()=>{if(innerWidth===lastW)return;lastW=innerWidth;clearTimeout(rt);rt=setTimeout(fit,150)});
(document.fonts&&document.fonts.ready?document.fonts.ready:Promise.resolve()).then(()=>{fit();body.classList.add('fitted')});
const ov=document.getElementById('ov');
function setOv(v){document.documentElement.style.setProperty('--ov',(v/100).toFixed(2));store('views-ov',v)}
ov.addEventListener('input',()=>setOv(ov.value));ov.value=store('views-ov')||60;setOv(ov.value);
hooks.overlay=()=>requestAnimationFrame(fit);
setToggle('fixes',store('views-fixes')==='1');setToggle('blocks',store('views-blocks')==='1');
setToggle('overlay',store('views-overlay')==='1');
"""

INDEX_CSS = r"""
.lib{max-width:76rem;margin:0 auto;padding:28px 16px 80px}
.lib h1{font:700 26px/1.25 var(--ui);margin:.2em 0}
.lede{font:15px/1.6 var(--ui);color:var(--muted);max-width:52rem;margin:0 0 1.4em}
.list{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,22rem),1fr));gap:12px}
.item{display:flex;gap:12px;background:var(--paper);border:1px solid var(--rule);border-radius:12px;padding:12px;
box-shadow:var(--shadow)}
.item img{width:72px;height:100px;object-fit:cover;object-position:top;border-radius:4px;flex:none;background:#fff;
border:1px solid var(--rule)}
.item .m{flex:1;min-width:0;display:flex;flex-direction:column;gap:4px}
.item .ti{font-family:var(--text);font-size:18px;line-height:1.4;font-weight:700;display:-webkit-box;-webkit-line-clamp:3;
-webkit-box-orient:vertical;overflow:hidden}
.item .jr{font:12px/1.5 var(--ui);color:var(--muted)}
.item .go{display:flex;gap:6px;margin-top:auto;flex-wrap:wrap}
.item .go a{font:13px/1 var(--ui);text-decoration:none;color:var(--ink);background:var(--chip);border:1px solid var(--rule);
border-radius:999px;padding:7px 11px}
.item .go a:hover{border-color:var(--accent);color:var(--accent)}
.foot{font:12px/1.6 var(--ui);color:var(--faint);margin-top:3em}
"""


def write_index(rows):
    cards = []
    for r in rows:
        cards.append(
            f'<div class="item" dir="{r["dir"]}"><img src="{E(r["thumb"])}" alt="" loading="lazy"><div class="m">'
            f'<div class="ti" dir="auto">{E(r["title"])}</div>'
            f'<div class="jr" dir="auto">{E(r["sub"])} · <span dir="ltr">{E(r["stem"])}</span> · {r["pages"]} pp.</div>'
            f'<div class="go" dir="ltr"><a href="pages/{E(r["stem"])}.html">Page by page</a>'
            f'<a href="mirror/{E(r["stem"])}.html">Mirror</a></div></div></div>')
    page = f"""<!doctype html>
<html lang="en" dir="ltr"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Scan beside rebuild</title>
<link rel="preconnect" href="https://fonts.googleapis.com"><link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="{FONTS}" rel="stylesheet">
<style>{BASE_CSS}{INDEX_CSS}</style></head><body>
<nav class="bar"><span class="home">inkscript · experiment 41</span><span class="t"></span>
<button type="button" id="theme">Auto</button></nav>
<main class="lib"><h1>The original beside ours: {len(rows)} articles</h1>
<p class="lede">Each article in two views. <b>Page by page</b>: every printed page as a row, the scan on the left and
our rebuild of that page on the right (Azure's words, Gemini 4 Argon's structure). <b>Mirror</b>: a born-digital twin of
each page, every line set in type at its printed place, beside the scan or laid over it.</p>
<div class="list">{"".join(cards)}</div>
<p class="foot">Generated by experiments/41_azure_structure/views.py from out/argon/raw/ (no model calls).</p></main>
<script>{R.COMMON_JS}</script></body></html>
"""
    (VIEWS / "index.html").write_text(page, encoding="utf-8")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--stems", nargs="*")
    args = ap.parse_args()
    VIEWS.mkdir(parents=True, exist_ok=True)
    arts = sample()
    idx_f = VIEWS / "index.json"
    idx = {x["stem"]: x for x in json.loads(idx_f.read_text())} if idx_f.exists() else {}
    for a in arts:
        if args.stems and a["stem"] not in args.stems:
            continue
        cap = R.capture(a)
        if cap is None:
            print(f"  {a['stem']}: no answers", flush=True)
            continue
        build_pages(a, cap)
        st = build_mirror(a, cap)
        lang, ddir, title, sub = doc_info(a, cap)
        idx[a["stem"]] = dict(stem=a["stem"], title=title, sub=sub, dir=ddir, pages=len(cap["pages"]), thumb=thumb(a),
                              year=str(a.get("year") or ""))
        print(f"  {a['stem']:24} p{len(cap['pages']):>2} lines {st['lines']:>5} noise {st['noise']}", flush=True)
    rows = [idx[a["stem"]] for a in arts if a["stem"] in idx]
    rows.sort(key=lambda r: r["year"] or "9999")
    idx_f.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    write_index(rows)
    print(f"{len(rows)} articles -> {VIEWS}/index.html")


if __name__ == "__main__":
    main()
