"""Experiment 43: experiment 41's Layout view (views.build_layout, read from masters by mread.load) drawn from a
masters folder of this experiment. No model calls; nothing in experiment 41 changes (build_layout is copied here as
build_layout43 with the changes below).

* text of another article (ALTO role.otherArticle): slightly muted text, one quiet mark per contiguous region (a
  thin rule on its outer side, one small label "from another article" at its top); pictures and captions inside the
  region belong to it; the bar's "Hide other articles" hides them all (remembered in the browser);
* ornaments (ALTO role.ornament) are left to the scan;
* a figure with words printed inside it (JATS <p content-type="text-in-figure">) is the picture only, with a small
  "text" button that opens its words in a box to read and copy;
* running text wraps round a figure that intrudes into its box (per printed line, from Azure's line boxes).

    views43.py --masters out/v2_55/masters --out out/v2_55/views --stems 0493-000-029-001 0197-002-001-003
"""
from __future__ import annotations

import argparse
import json
import statistics
import sys
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import masters43  # noqa: E402,F401  (paths to experiment 41)
import views as V  # noqa: E402
import mread as MR  # noqa: E402
import reader as R  # noqa: E402
import structure as ST  # noqa: E402
from structure import art_of  # noqa: E402
from views import (E, FS_K, GROUP, WHOLE, FONTS, KATEX, BASE_CSS, LAYOUT_CSS, COMMON_JS, LAYOUT_JS,  # noqa: E402
                   PAGE_TPL, bar, boxstyle, continues_next, crop, pieces_of, rows_of, scan)

CSS43 = r"""
.pc.t-other_article .tx{color:color-mix(in srgb,var(--ink) 66%,var(--paper))}
.pc.oa.fg img{opacity:.9}
.pc.oa .tx{color:color-mix(in srgb,var(--ink) 66%,var(--paper))}
.oa-reg{position:absolute;pointer-events:none;z-index:2}
.oa-reg::after{content:"";position:absolute;top:0;bottom:0;right:-1.3cqw;
border-right:2px solid color-mix(in srgb,var(--ink) 28%,transparent)}
.lpage[dir="ltr"] .oa-reg::after{right:auto;left:-1.3cqw;border-right:0;
border-left:2px solid color-mix(in srgb,var(--ink) 28%,transparent)}
.oa-lab{position:absolute;top:0;right:-1.3cqw;transform:translateY(-115%);white-space:nowrap;direction:ltr;
font:500 max(9px,1.05cqw)/1.2 var(--ui);color:var(--muted);letter-spacing:.02em}
.lpage[dir="ltr"] .oa-lab{right:auto;left:-1.3cqw}
body.hideoa .pc.t-other_article,body.hideoa .pc.oa,body.hideoa .oa-reg{visibility:hidden}
.pc .wf{display:block}
.pc.t-boxed{background:color-mix(in srgb,var(--ink) 6%,var(--paper));outline:1.5px solid color-mix(in srgb,var(--ink) 35%,transparent);
outline-offset:.5cqw;border-radius:2px}
.pc.t-trans_title .tx{font-weight:600}
.figtx{position:absolute;bottom:.5em;left:.5em;z-index:5;font:600 max(10px,1.1cqw)/1 var(--ui);padding:.4em .7em;
border-radius:999px;border:1px solid color-mix(in srgb,var(--ink) 25%,transparent);background:var(--paper);
color:var(--ink);cursor:pointer;box-shadow:0 1px 3px rgba(0,0,0,.18)}
.figtx:hover,.figtx:focus-visible{background:var(--chip)}
.ftbox{max-width:min(36rem,calc(100vw - 32px));width:100%;border:1px solid var(--rule);border-radius:8px;padding:0;
background:var(--paper);color:var(--ink);box-shadow:0 10px 40px rgba(0,0,0,.25)}
.ftbox::backdrop{background:rgba(0,0,0,.3)}
.fthead{display:flex;gap:8px;align-items:center;padding:10px 12px;border-bottom:1px solid var(--rule);font:600 13px/1.2 var(--ui)}
.fthead b{flex:1}
.fthead button{font:600 12px/1 var(--ui);padding:7px 11px;border-radius:999px;border:1px solid var(--rule);
background:var(--chip);color:var(--ink);cursor:pointer}
.fttext{padding:14px 16px 18px;font:400 20px/1.7 var(--text);white-space:pre-wrap;user-select:text;max-height:60vh;overflow:auto}
"""

JS43 = r"""
setToggle('hideoa',store('views-hideoa')==='1');
const ftb=document.querySelector('.ftbox'),ftt=ftb&&ftb.querySelector('.fttext'),ftc=ftb&&ftb.querySelector('.ftcopy');
document.addEventListener('click',e=>{const b=e.target.closest('.figtx');if(!b||!ftb)return;e.preventDefault();
 ftt.textContent=b.dataset.text;ftt.dir=b.dataset.lang==='ar'?'rtl':'ltr';ftt.lang=b.dataset.lang||'';
 ftc.textContent='Copy';try{ftb.showModal()}catch(err){ftb.setAttribute('open','')}});
if(ftb){ftb.querySelector('.ftclose').addEventListener('click',()=>ftb.close());
 ftb.addEventListener('click',e=>{if(e.target===ftb)ftb.close()});
 ftc.addEventListener('click',async()=>{const t=ftt.textContent;let ok=false;
  try{await navigator.clipboard.writeText(t);ok=true}catch(err){}
  if(!ok){try{const r=document.createRange();r.selectNodeContents(ftt);const s=getSelection();s.removeAllRanges();
   s.addRange(r);ok=document.execCommand('copy')}catch(err){}}
  ftc.textContent=ok?'Copied':'Select and copy'})}
"""

FTBOX = ('<dialog class="ftbox" aria-label="Text in the picture"><div class="fthead" dir="ltr"><b>Text in the picture</b>'
         '<button type="button" class="ftcopy">Copy</button><button type="button" class="ftclose">Close</button></div>'
         '<div class="fttext" tabindex="0"></div></dialog>')


V.GROUP.setdefault("boxed", "body")                # v3: boxed text (JATS boxed-text), drawn as a box
V.GROUP.setdefault("trans_title", "head")
_KIND41 = MR.Doc.kind


def kind43(self, el, role):
    """experiment 41's kind, plus the elements jats43 moved into the front and back (their ids kept): a printed
    translated title, a keywords group, the title of an abstract or of the endnotes, boxed text, ack / appendix."""
    tg, par = el.tag, el.getparent()
    ptg = par.tag if par is not None else ""
    if tg == "trans-title":
        return "trans_title", {}
    if tg == "kwd-group":
        return "keywords", {}
    if tg == "title" and ptg in ("abstract", "trans-abstract", "fn-group", "ack", "app"):
        return "heading", dict(level="2")
    if tg == "p" and ptg == "boxed-text":
        return "boxed", {}
    return _KIND41(self, el, role)


MR.Doc.kind = kind43


def load43(a):
    doc = MR.load(a)
    other, orn = set(), set()
    for b in doc["D"].A.iter(MR._q("TextBlock")):
        if "role.otherArticle" in (b.get("TAGREFS") or ""):
            other.add(b.get("ID"))
        if "role.ornament" in (b.get("TAGREFS") or ""):
            orn.add(b.get("ID"))
    for rec in doc["blocks"]:
        if rec.get("alto") in other:
            rec["type"] = "other_article"
        if rec["type"] == "figure":
            el = doc["D"].by_id.get(rec.get("target"))
            alts = el.findall("alt-text") if el is not None else []
            rec["descriptions"] = {(x.get(MR.XML_LANG) or doc["lang"]): (x.text or "") for x in alts}
            here = rec["descriptions"].get(doc["lang"])
            if here:                                       # the description in the article's language first
                rec["description"] = here
            ps = el.findall("p[@content-type='text-in-figure']") if el is not None else []
            if ps:
                rec["fig_text"] = "\n".join(" ".join("".join(p.itertext()).split()) for p in ps)
    doc["blocks"] = [r for r in doc["blocks"] if r.get("alto") not in orn]     # ornaments: ink only (the scan)
    return doc


def rec_px(r):
    if r.get("box"):
        return list(r["box"])
    bs = [L["px"] for L in r["lines"] + r["extra_lines"]]
    return ST.union(bs) if bs else None


def area(b):
    return max(0.0, b[2] - b[0]) * max(0.0, b[3] - b[1])


def meet(a, b):
    return [max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])]


def oa_regions(recs):
    """Contiguous runs (in reading order) of another article's blocks on a page: their union box, grown by the
    pictures and captions between them or mostly inside it. Returns (boxes, ids of the pictures/captions taken)."""
    runs, cur, pend = [], None, []
    for r in recs:
        T = r["type"]
        if T == "other_article":
            if cur is None:
                cur = dict(recs=[], figs=[])
                runs.append(cur)
            cur["figs"] += pend
            pend = []
            cur["recs"].append(r)
        elif T in ("figure", "caption") and cur is not None:
            pend.append(r)
        elif T in ("header", "footer"):
            continue
        else:
            cur, pend = None, []
    boxes, taken = [], set()
    for run in runs:
        bs = [b for b in (rec_px(r) for r in run["recs"]) if b]
        if not bs:
            continue
        u = ST.union(bs)
        for f in run["figs"]:
            fb = rec_px(f)
            if fb:
                u = ST.union([u, fb])
                taken.add(id(f))
        for f in recs:
            fb = rec_px(f) if f["type"] in ("figure", "caption") and id(f) not in taken else None
            if fb and area(fb) and area(meet(fb, u)) >= 0.5 * area(fb):
                u = ST.union([u, fb])
                taken.add(id(f))
        boxes.append(u)
    return boxes, taken


def fig_px(r, W, H):
    x0, y0, x1, y1 = r["box"]
    px, py = 4 * W / 1000, 4 * H / 1000
    return [max(0, x0 - px), max(0, y0 - py), min(W, x1 + px), min(H, y1 + py)]


def wrap_floats(B, Ls, nrow, figs, W):
    """Floats that make a text box's lines stop short of a figure that intrudes into it: per printed line beside
    the figure, as much width as the print leaves that line short (Azure's line boxes); if the lines say nothing
    (Azure's line ran under the picture), the figure's own width inside the box."""
    lh = (B[3] - B[1]) / max(1, nrow)
    cq = lambda v: f"{v / W * 100:.3f}cqw"                          # noqa: E731
    per_side = {"right": [], "left": []}
    for F in figs:
        I = meet(B, F)
        if area(I) <= 0.002 * area(B) or area(meet(B, F)) >= 0.8 * area(B):
            continue
        side = "right" if (F[0] + F[2]) / 2 > (B[0] + B[2]) / 2 else "left"
        intr = I[2] - I[0]
        rows = {}
        for L in Ls:
            vo = min(L[3], I[3]) - max(L[1], I[1])
            if vo <= 0.3 * (L[3] - L[1]):
                continue
            k = min(nrow - 1, max(0, int(((L[1] + L[3]) / 2 - B[1]) // lh)))
            ind = B[2] - L[2] if side == "right" else L[0] - B[0]
            rows[k] = max(rows.get(k, 0.0), max(0.0, ind))
        if not rows:
            continue
        if max(rows.values()) < 0.25 * intr:
            rows = {k: intr for k in rows}
        k0, k1 = min(rows), max(rows)
        ws = [rows.get(k, max(rows.get(k - 1, 0), rows.get(k + 1, 0))) for k in range(k0, k1 + 1)]
        per_side[side].append((k0, [w + 0.006 * W if w > 0 else 0 for w in ws]))
    out = []
    for side, stacks in per_side.items():
        at = 0
        for k0, ws in sorted(stacks):
            if k0 < at:
                ws, k0 = ws[at - k0:], at
            if not ws:
                continue
            out.append(f'<span class="wf" style="float:{side};clear:{side};width:0;height:{cq((k0 - at) * lh)}"></span>')
            out += [f'<span class="wf" style="float:{side};clear:{side};width:{cq(w)};height:{cq(lh)}"></span>'
                    for w in ws]
            at = k0 + len(ws)
    return "".join(out)


def build_layout43(a, doc):
    """experiment 41's views.build_layout (copied; 41 is never edited) with experiment 43's changes:
    * a figure with words printed inside it is drawn as the picture only, with a "text" button that opens its words
      (from the JATS <p content-type="text-in-figure">) in a box to read and copy;
    * a block of running text whose box a figure intrudes into wraps round it: floats at the start of the text,
      one per printed line beside the figure, as wide as the print leaves that line short (Azure's line boxes), so
      the text flows round a round photo as the print does;
    * text of another article: one quiet mark per contiguous region (a thin rule on its outer side and one small
      label at its top), the text slightly muted, figures inside the region belong to it; a bar toggle hides them."""
    stem, D = a["stem"], doc["D"]
    lang, ddir, title, sub = doc["lang"], doc["ddir"], doc["title"], doc["sub"]
    blocks = doc["blocks"]
    LX = {L["id"]: L for r in blocks for L in r["lines"] + r["extra_lines"]}
    SL = SimpleNamespace(lines=LX)                               # pieces_of reads .lines[id]["px"]
    hgt = lambda L: L["px"][3] - L["px"][1]                       # noqa: E731
    pos = {id(r): i for i, r in enumerate(blocks)}
    allbody = [hgt(L) for r in blocks if GROUP.get(r["type"]) == "body" for L in r["lines"]]
    doc_body = statistics.median(allbody) if allbody else 40
    rows, prints = [], []
    stats = dict(blocks=0, pieces=0, turned=0, noise=0)
    for i, pg in enumerate(doc["pages"]):
        p, W, H = pg["p"], pg["W"], pg["H"]
        recs = [r for r in blocks if r["page"] == p]
        k = lambda h: FS_K * h / W * 100                      # line-box height (px) -> font size in cqw
        hs = {}
        for r in recs:
            for L in r["lines"] + r["extra_lines"]:
                hs.setdefault(GROUP.get(r["type"], "other"), []).append(hgt(L))
        med = {g: statistics.median(v) for g, v in hs.items()}
        fbody = k(med.get("body", doc_body))
        fnote = k(min(med.get("note", doc_body * 0.8), med.get("body", doc_body)))
        els, arrows_seq, num = [], [], 0
        regions, oa_figs = oa_regions(recs)
        figs_px = [fig_px(r, W, H) for r in recs if r["type"] == "figure" and r.get("box")]
        fn_first = True
        for rec in recs:
            T, g = rec["type"], GROUP.get(rec["type"], "other")
            ids = [L["id"] for L in rec["lines"]]
            lg = rec.get("lang") or lang
            d = "rtl" if lg == "ar" else "ltr"
            d = "rtl" if d == "ltr" and R.redir(' dir="ltr"', " ".join(L["html"] or "" for L in rec["lines"])) \
                == ' dir="rtl"' else d
            cont_next = continues_next(rec, blocks, pos[id(rec)])
            if T == "figure":
                src = crop(a, rec.get("src"))
                x0, y0, x1, y1 = rec["box"]
                px, py = 4 * W / 1000, 4 * H / 1000            # the crop's margin (masters.py crop, rel_pad)
                bx = [max(0, x0 - px), max(0, y0 - py), min(W, x1 + px), min(H, y1 + py)]
                num += 1
                both = " | ".join(f"{k}: {v}" for k, v in (rec.get("descriptions") or {}).items() if v)
                im = (f'<img src="../{src}" alt="{E(rec.get("description") or "")}" title="{E(both)}" '
                      f'loading="lazy">' if src else
                      f'<span class="fig-missing">[{E(rec.get("description") or "figure")}]</span>')
                ftx = rec.get("fig_text") or ""
                btn = (f'<button type="button" class="figtx" title="The words printed in this picture" '
                       f'data-text="{E(ftx)}" data-lang="{E(rec.get("lang") or lang)}">text</button>' if ftx else "")
                oa = " oa" if id(rec) in oa_figs else ""
                els.append(f'<div class="pc fg t-figure{oa}" data-t="figure" style="{boxstyle(bx, W, H)}">{im}{btn}'
                           f'<span class="ob">{num}</span></div>')
                arrows_seq.append((bx, num, False))
                stats["blocks"] += 1
                continue
            if T == "equation" and rec.get("latex") is not None and rec.get("box"):
                ids = [L["id"] for L in rec["extra_lines"]] or ids
            if not ids:
                continue
            if T in WHOLE:
                pcs = [dict(ids=ids, box=ST.union([LX[x]["px"] for x in ids]))]
            else:
                pcs = pieces_of(ids, SL)
            if len(pcs) == 1 and rec.get("box"):              # the ALTO block's box: also the ink of a line a fix
                pcs[0]["box"] = list(rec["box"])                # emptied (Argon: not text), as the scan shows it
            num += 1
            stats["blocks"] += 1
            stats["turned"] += len(pcs) > 1
            # base size (cqw) and the block's printed line pitch
            if g == "head":
                bh = statistics.median([hgt(LX[x]) for x in ids])
                f0 = min(k(bh), fbody * 3.2)
            elif g == "note":
                f0 = fnote
            elif g == "table":
                f0 = fbody * 0.9
            elif g in ("caption", "header", "footer", "other"):
                f0 = min(k(med.get(g, doc_body * 0.8)), fbody * 1.3)
            else:
                f0 = fbody
            for j, pc in enumerate(pcs):
                bx = pc["box"]
                last_piece = j == len(pcs) - 1
                if T == "verse":
                    hems = [h for h in rec.get("hemistichs") or [] if h]
                    nrow = max(1, (len(hems) + 1) // 2) if len(hems) > 1 else 1
                    inner = MR.verse_inner(D, rec, W, H)
                    cols = ""
                    if len(hems) == 2:
                        b1 = ST.union([LX[x]["px"] for x in hems[0] if x in LX])
                        b2 = ST.union([LX[x]["px"] for x in hems[1] if x in LX])
                        bw = (bx[2] - bx[0]) or 1
                        w1, w2 = (b1[2] - b1[0]) / bw, (b2[2] - b2[0]) / bw
                        gp = max(0.025, 1 - w1 - w2)
                        cols = f";--c1:{w1 * 100:.1f}fr;--c2:{w2 * 100:.1f}fr;--cg:{gp * 100:.1f}%"
                    cls = "verse" + (" free" if len(hems) == 1 else "")
                    content = f'<div class="tx {cls}" dir="{d}" style="{cols[1:]}">{inner}</div>'
                elif T == "table":
                    h = MR.table_html(D, rec["table"], d, lg)
                    nrow = max(1, h.count("<tr>"))
                    content = f'<div class="tx" dir="{d}">{h}</div>'
                elif T == "equation" and rec.get("latex"):
                    nrow = 1
                    content = (f'<div class="tx eq" dir="ltr"><span class="math">\\[{E(rec["latex"])}\\]</span></div>')
                else:
                    nrow = rows_of([LX[x]["px"] for x in pc["ids"]])
                    txt = " ".join(LX[x]["html"] or "" for x in pc["ids"])
                    if j == 0 and rec["continued"]:
                        txt = '<span class="contmark" title="continues from the previous page">&#8627;</span>' + txt
                    if last_piece:
                        for t in rec.get("added", []):
                            txt += f' <span class="added">{E(t)}</span>'
                    lvl = f" h{rec.get('level')}" if T == "heading" and str(rec.get("level") or "").isdigit() else ""
                    cls = "tx" + lvl + (" more" if g in ("body", "note") and (not last_piece or cont_next) else "")
                    idattr = ""
                    if T == "footnote" and j == 0 and not rec["continued"] and rec.get("fn_id"):
                        idattr = f' id="n-{E(rec["fn_id"])}"'
                    if g in ("body", "note", "caption", "other") and figs_px:
                        txt = wrap_floats(bx, [LX[x]["px"] for x in pc["ids"]], nrow, figs_px, W) + txt
                    content = f'<div class="{cls}"{idattr} dir="{d}">{txt}</div>'
                lh = (bx[3] - bx[1]) / nrow / W * 100
                extra = " oa" if id(rec) in oa_figs else ""
                if T == "footnote" and fn_first and not rec["continued"]:
                    extra, fn_first = " fn1", False
                badge = f'<span class="ob">{num}</span>' if j == 0 else ""
                if last_piece and cont_next:
                    badge += '<span class="ob nx" title="continues on the next page">&#8618;</span>'
                els.append(f'<div class="pc g-{g} t-{T}{extra}" data-t="{T}" data-g="{g}" '
                           f'style="{boxstyle(bx, W, H)};--f:{f0:.3f};--lh:{lh:.3f}">{content}{badge}</div>')
                arrows_seq.append((bx, num, j > 0))
                stats["pieces"] += 1
        # lines no block took (the ALTO's role.noise): shown only with "Blocks"
        for L in doc["noise"].get(p, []):
            h = hgt(L)
            els.append(f'<div class="pc noise" dir="auto" title="not in any block (Gemini: noise)" '
                       f'style="{boxstyle(L["px"], W, H)};--f:{k(h):.3f};--lh:{h / W * 100:.3f}">'
                       f'<div class="tx">{E(L["text"])}</div></div>')
            stats["noise"] += 1
        # reading order: block to block (solid), column turns inside a block (dashed)
        sw = W * 0.0022
        svg = [f'<svg class="ord" viewBox="0 0 {W} {H}" aria-hidden="true"><defs><marker id="ah{p}" viewBox="0 0 10 10" '
               f'refX="9" refY="5" markerWidth="5" markerHeight="5" orient="auto-start-reverse">'
               f'<path d="M0,0L10,5L0,10z" class="ahd"/></marker></defs>']
        for (b0, n0, _), (b1, n1, turn) in zip(arrows_seq, arrows_seq[1:]):
            x0, y0 = (b0[0] + b0[2]) / 2, (b0[1] + b0[3]) / 2
            x1, y1 = (b1[0] + b1[2]) / 2, (b1[1] + b1[3]) / 2
            dx, dy = x1 - x0, y1 - y0
            ln = (dx * dx + dy * dy) ** .5 or 1
            sh = min(ln * 0.18, W * 0.02)
            xa, ya, xb, yb = x0 + dx / ln * sh, y0 + dy / ln * sh, x1 - dx / ln * sh, y1 - dy / ln * sh
            mx, my = (xa + xb) / 2 - dy * 0.12, (ya + yb) / 2 + dx * 0.12      # a slight bow so arrows stay apart
            svg.append(f'<path d="M{xa:.0f},{ya:.0f}Q{mx:.0f},{my:.0f} {xb:.0f},{yb:.0f}" class="{"tn" if turn else "bk"}" '
                       f'stroke-width="{sw:.1f}"' + (f' stroke-dasharray="{W * .008:.0f},{W * .006:.0f}"' if turn else "")
                       + f' marker-end="url(#ah{p})"/>')
        svg.append("</svg>")
        for rb in regions:
            els.append(f'<div class="oa-reg" style="{boxstyle(rb, W, H)}" aria-hidden="true">'
                       f'<span class="oa-lab">from another article</span></div>')
        prints.append((p, W, H, "".join(e for e in els if 'class="pc noise"' not in e)))
        src = scan(a, p)
        rows.append(
            f'<section class="mrow" id="p{p}" data-p="{p}">'
            f'<div class="plab"><a href="#p{p}">page {p}</a><span>{i + 1} / {len(doc["pages"])}</span></div>'
            f'<div class="mpair">'
            f'<div class="mscan" style="aspect-ratio:{W}/{H}"><img src="../{src}" alt="scan of page {p}" '
            f'loading="{"eager" if i < 2 else "lazy"}" width="{W}" height="{H}"></div>'
            f'<div class="lpage" style="aspect-ratio:{W}/{H}" lang="{E(lang)}" dir="{ddir}">{"".join(els)}'
            f'{"".join(svg)}</div>'
            f'</div></section>')
    fix_n = sum(r.count('class="fix"') for r in rows)
    sic_n = sum(r.count('class="sic"') for r in rows)
    head = (f'<header class="vhead" dir="{ddir}"><h1 dir="auto">{E(title)}</h1><p class="kicker" dir="auto">{E(sub)}</p>'
            f'<p class="provenance" dir="ltr">{len(doc["pages"])} pages · scan on the left; on the right each block of the '
            f'printed page at its own place, its text set in our type (Scheherazade New), flowing and justified, one '
            f'size per kind of block on each page · {stats["blocks"]} blocks in {stats["pieces"]} boxes '
            f'({stats["turned"]} turn a column or page) · {fix_n} fixes (<b>Fixes</b>) · {sic_n} suspected misprints '
            f'(wavy underline) · <b>Order</b> shows Gemini\'s reading order · text that does not fit its box after '
            f'shrinking is left visible, with a red edge · '
            f'<a href="../mirror_lines/{stem}.html">line-by-line version</a> · '
            f'<a href="../pages/{stem}.html">page by page</a></p></header>')
    has_oa = any(r["type"] == "other_article" for r in blocks)
    tools = [("fixes", "Fixes", "Highlight Gemini's fixes of Azure's misreadings (f)"),
             ("blocks", "Blocks", "Outline the blocks by type (b)"),
             ("order", "Order", "Number the blocks in reading order and draw the path (r)"),
             ("overlay", "Overlay", "Lay our page over the scan (o)")]
    if has_oa:
        tools.append(("hideoa", "Hide other articles", "Hide the text and pictures of other articles printed on "
                                                       "these pages"))
    slider = ('<label class="ovl" title="Opacity of our page over the scan">'
              '<input type="range" id="ov" min="0" max="100" value="60" aria-label="page opacity"></label>')
    legend = ('<div class="legend" dir="ltr">' + "".join(
        f'<span class="lg t-{t}">{t.replace("_", " ")}</span>' for t in
        ("title", "trans_title", "heading", "byline", "paragraph", "abstract", "boxed", "verse", "quote", "list_item",
         "reference", "table",
         "equation", "caption", "figure", "footnote", "header", "footer", "other")) +
        '<span class="lg noise">not in any block</span></div>')
    page = PAGE_TPL.format(lang=E(lang), title=E(title[:90]), fonts=FONTS, katex=KATEX, css=BASE_CSS + V.MIRROR_CSS + LAYOUT_CSS + CSS43,
                           bar=bar(title, tools, [(f"../mirror_lines/{stem}.html", "Lines"),
                                                  (f"../pages/{stem}.html", "Page by page")], extra=slider),
                           body=head + legend + '<main class="mrows">' + "\n".join(rows) + "</main>" + FTBOX,
                           data=json.dumps(dict(stem=stem, lang=lang)), js=COMMON_JS + LAYOUT_JS + JS43)
    (V.VIEWS / "mirror").mkdir(parents=True, exist_ok=True)
    (V.VIEWS / "mirror" / f"{stem}.html").write_text(page, encoding="utf-8")
    V.write_layout_print(stem, lang, ddir, title, prints)
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--masters", required=True)
    ap.add_argument("--out", default=str(HERE / "out" / "views"))
    ap.add_argument("--stems", nargs="+", required=True)
    a = ap.parse_args()
    MR.MAST = Path(a.masters).resolve()
    V.VIEWS = Path(a.out).resolve()
    V.write_layout_print = lambda *x, **k: None              # the print page is not part of this check
    for s in a.stems:
        st = build_layout43(art_of(s), load43(art_of(s)))
        print(s, st, "->", V.VIEWS / "mirror" / f"{s}.html")


if __name__ == "__main__":
    main()
