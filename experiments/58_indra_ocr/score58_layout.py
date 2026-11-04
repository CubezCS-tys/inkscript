"""Experiment 58: Indra's layout (block labels, reading order, tables) against Gemini's line roles, no calls.

    /home/appuser/inkscript/.venv/bin/python score58_layout.py [--variant lay300]   -> out/layout_scores.json

Reference: experiment 43's run v33_300b_fix3 (the proof pack's run: 300 unseen articles, Gemini 4 Argon prompt v3.3
answers after the code rules, out/v33_300b_fix3/rules/*.json).  Every Azure line of a page has Gemini's block type,
its block, and its place in Gemini's reading order (blocks in order; lines in a block in order; table cells row by row;
verse halves in order).  The masters are built from exactly these answers.

Indra ran on the same 300 dpi page images (run58.py --units out/units_lay300.json).  Each Azure line is given:
  label  the Indra block it overlaps most (intersection area / the Azure line's area >= 0.3), else "none"
  order  the reading-order index of the Indra line it overlaps most (Indra's lines are in its reading order)
Measures: confusion (Gemini type x Indra label, in lines), coarse agreement, per-class precision / recall, reading
order (Kendall concordance of the line pairs), same-block agreement of neighbouring lines, tables (paired by box,
rows / columns, TEDS structure-only and with text), plain-page triage (the hybrid question), Gemini tokens per page.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "41_azure_structure"))
from structure import page_lines  # noqa: E402

OUT = HERE / "out"
RULES = E / "43_rehearsal/out/v33_300b_fix3/rules"

# Gemini type -> coarse class; Indra label -> coarse class (only classes both can say are compared as "agree")
G2C = {"paragraph": "body", "quote": "body", "abstract": "body", "keywords": "body", "boxed": "body",
       "title": "heading", "trans_title": "heading", "heading": "heading", "byline": "byline",
       "list_item": "list", "reference": "reference", "footnote": "footnote", "verse": "verse", "table": "table",
       "equation": "equation", "caption": "caption", "figure": "figure", "header": "furniture",
       "footer": "furniture", "other_article": "other_article", "other": "other", "noise": "noise"}
I2C = {"Text": "body", "Section-Header": "heading", "Page-Header": "furniture", "Page-Footer": "furniture",
       "List-Group": "list", "Table": "table", "Caption": "caption", "Footnote": "footnote",
       "Table-Of-Contents": "other", "Form": "other", "Picture": "figure", "none": "none"}
# what counts as agreement for classes Indra has no word for
ALSO_OK = {"byline": {"body", "heading"}, "reference": {"list", "body"}, "verse": {"body"},
           "equation": {"body"}, "other_article": set(), "other": set(), "noise": set()}
SIMPLE_INDRA = {"Text", "Section-Header", "Page-Header", "Page-Footer"}


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def base(i):
    return re.sub(r"[a-z]+$", "", i)


def gemini_pages(ans):
    """page -> (ordered [(azure line id, type, block k)], tables [(block k, rows)], noise ids)."""
    out = {}
    noise = {base(x) for x in (ans.get("noise") or []) if isinstance(x, str)}
    for p in ans["pages"]:
        seq, tabs, seen = [], [], set()
        for k, b in enumerate(p["blocks"]):
            t = b["type"]
            ids = []
            if t == "table":
                for row in b.get("rows", []):
                    for c in row:
                        ids += c.get("lines", [])
                tabs.append((k, b.get("rows", [])))
            elif t == "verse":
                for h in b.get("hemistichs", []):
                    ids += h
            else:
                ids = b.get("lines", []) or []
            for i in ids:
                i = base(str(i))
                if i in seen:
                    continue
                seen.add(i)
                seq.append((i, t, k))
        out[p["page"]] = (seq, tabs, noise)
    return out


def inter(a, B):
    """intersection areas of box a with boxes B [N,4]"""
    if len(B) == 0:
        return np.zeros(0)
    w = np.clip(np.minimum(a[2], B[:, 2]) - np.maximum(a[0], B[:, 0]), 0, None)
    h = np.clip(np.minimum(a[3], B[:, 3]) - np.maximum(a[1], B[:, 1]), 0, None)
    return w * h


def kendall(xs):
    """concordant share of pairs for a sequence of ranks (ties in xs = same Indra line: left out)."""
    n = len(xs)
    if n < 2:
        return None, 0
    x = np.array(xs)
    d = x[None, :] - x[:, None]
    iu = np.triu_indices(n, 1)
    dd = d[iu]
    pairs = int((dd != 0).sum())
    if not pairs:
        return None, 0
    return float((dd > 0).sum() / pairs), pairs


def md_tables(md):
    return re.findall(r"<table.*?</table>", md or "", re.S)


def gem_table_html(rows, text, with_text=True):
    h = "<table>"
    for r in rows:
        h += "<tr>"
        for c in r:
            sp = (f' colspan="{c["colspan"]}"' if c.get("colspan", 1) > 1 else "") + \
                 (f' rowspan="{c["rowspan"]}"' if c.get("rowspan", 1) > 1 else "")
            tx = " ".join(text.get(base(i), "") for i in c.get("lines", [])) if with_text else ""
            h += f"<td{sp}>{tx}</td>"
        h += "</tr>"
    return h + "</table>"


def strip_text(html):
    html = re.sub(r"<th", "<td", html).replace("</th>", "</td>")
    return re.sub(r">([^<]*)<", lambda m: "><", html)


def grid(html):
    rows = re.findall(r"<tr.*?</tr>", html, re.S)
    cols = [sum(int(re.search(r'colspan="?(\d+)', c).group(1)) if "colspan" in c else 1
                for c in re.findall(r"<t[dh][^>]*>", r)) for r in rows]
    return len(rows), max(cols) if cols else 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="lay300")
    ap.add_argument("--rules", default=str(RULES), help="a run's rules/ folder (default: v33_300b_fix3)")
    ap.add_argument("--tag", default="", help="suffix for the output files")
    a = ap.parse_args()
    from inkscript.gold.score import teds
    from inkscript.gold.text import folded
    arts = {x["stem"]: x for x in jl(E / "43_rehearsal/sample43b.json")["articles"]}
    conf = Counter()            # (gemini type, indra label) in lines
    coarse_ok = Counter()       # gemini coarse -> [ok, n]
    pages = []
    linef = open(OUT / f"layout_lines{a.tag}.jsonl", "w", encoding="utf-8")   # every Azure line: for hybrid58.py
    tables = []
    tok = []                    # per chunk: pages, tin, tout, azure chars, answer chars by part
    for f in sorted(Path(a.rules).glob("*.json")):
        d = jl(f)
        stem = d["stem"]
        ans = d["answer"]
        gp = gemini_pages(ans)
        # ---- token use of this chunk (for the cost model)
        az_chars = 0
        for p in gp:
            az_chars += sum(len(l["text"]) for l in page_lines(arts[stem], p)[0])
        parts = {k: len(json.dumps(v, ensure_ascii=False)) for k, v in ans.items()}
        blk = Counter()
        for p in ans["pages"]:
            for b in p["blocks"]:
                blk["references" if b["type"] == "reference" else "footnotes" if b["type"] == "footnote" else
                    "tables" if b["type"] == "table" else "blocks"] += len(json.dumps(b, ensure_ascii=False))
        tok.append(dict(stem=stem, pages=d["pages"], tin=d.get("tin"), tout=d.get("tout"), usd=d.get("usd"),
                        az_chars=az_chars, parts=parts, blocks=dict(blk)))
        for p, (seq, tabs, noise) in gp.items():
            pid = f"{stem}_p{p:03d}"
            fi = OUT / "indra" / a.variant / f"{pid}.json"
            if not fi.exists():
                continue
            ind = jl(fi)
            az, W, H = page_lines(arts[stem], p)
            azb = {l["id"]: np.array(l["px"], float) for l in az}
            aztext = {l["id"]: l["text"] for l in az}
            il = np.array([ln["box"] for ln in ind["lines"]], float).reshape(-1, 4)
            ib = np.array([b["bbox"] for b in ind["blocks"]], float).reshape(-1, 4)
            ilab = [b["label"] for b in ind["blocks"]]
            # every Azure line: Gemini's type (noise if Gemini left it out)
            seq = [x for x in seq if x[0] in azb]          # ids Azure has (a few answers name a line 0)
            gtype = {i: t for i, t, k in seq}
            gblock = {i: k for i, t, k in seq}
            for l in az:
                if l["id"] not in gtype:
                    gtype[l["id"]] = "noise"
            rows = []
            for l in az:
                bx = azb[l["id"]]
                area = max((bx[2] - bx[0]) * (bx[3] - bx[1]), 1.0)
                ov = inter(bx, ib)
                lab = ilab[int(ov.argmax())] if len(ov) and ov.max() / area >= 0.3 else "none"
                ovl = inter(bx, il)
                oi = int(ovl.argmax()) if len(ovl) and ovl.max() / area >= 0.2 else None
                ob = int(ov.argmax()) if len(ov) and ov.max() / area >= 0.3 else None
                rows.append((l["id"], lab, oi, ob))
            lab_of = {i: lab for i, lab, oi, ob in rows}
            ord_of = {i: oi for i, lab, oi, ob in rows}
            blk_of = {i: ob for i, lab, oi, ob in rows}
            # confusion
            ok = n = 0
            for i, t in gtype.items():
                lab = lab_of[i]
                conf[(t, lab)] += 1
                gc, ic = G2C.get(t, "other"), I2C.get(lab, "other")
                good = ic == gc or ic in ALSO_OK.get(gc, set())
                coarse_ok[(gc, good)] += 1
                if gc != "noise":
                    ok += int(good)
                    n += 1
            # order: Gemini's sequence, Indra's line index
            ranks = [ord_of[i] for i, t, k in seq if ord_of.get(i) is not None]
            kc, pairs = kendall(ranks)
            nf = [ord_of[i] for i, t, k in seq if ord_of.get(i) is not None and t not in ("header", "footer")]
            kcb, pairsb = kendall(nf)
            # same-block agreement of neighbours in Gemini's order
            sb = sbn = 0
            for (i1, t1, k1), (i2, t2, k2) in zip(seq, seq[1:]):
                if blk_of.get(i1) is None or blk_of.get(i2) is None:
                    continue
                sb += int((k1 == k2) == (blk_of[i1] == blk_of[i2]))
                sbn += 1
            # multi-column (exp 41's rule)
            left = sum(1 for l in az if l["px"][2] < 0.52 * W and l["px"][2] - l["px"][0] > 0.2 * W)
            right = sum(1 for l in az if l["px"][0] > 0.48 * W and l["px"][2] - l["px"][0] > 0.2 * W)
            gtypes = Counter(t for t in gtype.values())
            gpos = {i: n_ for n_, (i, t, k) in enumerate(seq)}
            linef.write(json.dumps(dict(id=pid, W=W, H=H, lines=[
                dict(i=l["id"], t=l["text"], px=l["px"], g=gtype[l["id"]], gk=gblock.get(l["id"]), go=gpos.get(l["id"]),
                     lab=lab_of[l["id"]], io=ord_of[l["id"]], ib=blk_of[l["id"]]) for l in az]),
                ensure_ascii=False, default=lambda o: o.item() if hasattr(o, "item") else str(o)) + "\n")
            pages.append(dict(id=pid, stem=stem, page=p, lines=len(az), agree=ok, n=n, kendall=kc, pairs=pairs,
                              kendall_body=kcb, pairs_body=pairsb, same_block=sb, same_block_n=sbn,
                              multicol=left >= 8 and right >= 8, indra_labels=dict(Counter(ilab)),
                              gemini_types=dict(gtypes), indra_lines=len(il), first_page=p == 1,
                              indra_ms=ind.get("wall_ms"), timings=ind.get("timings", {})))
            # tables: pair each Gemini table with the Indra Table block it overlaps most
            itabs = [(j, ib[j]) for j, lb in enumerate(ilab) if lb == "Table"]
            ihtml = md_tables(ind.get("markdown"))
            for k, trows in tabs:
                ids = [base(i) for r in trows for c in r for i in c.get("lines", [])]
                bxs = [azb[i] for i in ids if i in azb]
                if not bxs:
                    continue
                gb = np.array([min(b[0] for b in bxs), min(b[1] for b in bxs), max(b[2] for b in bxs),
                               max(b[3] for b in bxs)])
                garea = (gb[2] - gb[0]) * (gb[3] - gb[1])
                best, bo = None, 0.0
                for t_i, (j, bb) in enumerate(itabs):
                    o = inter(gb, bb[None])[0] / max(garea, 1)
                    if o > bo:
                        best, bo = t_i, o
                gh = gem_table_html(trows, {i: folded(v) for i, v in aztext.items()})
                row = dict(id=pid, gemini_grid=grid(gh), cells=sum(len(r) for r in trows), found=best is not None and bo >= 0.3,
                           overlap=round(bo, 2))
                if row["found"] and best < len(ihtml):
                    ih = ihtml[best]
                    ih_t = re.sub(r">([^<]+)<", lambda m: ">" + folded(m.group(1)) + "<", ih)
                    row.update(indra_grid=grid(ih), teds_struct=teds(strip_text(gh), strip_text(ih)),
                               teds_text=teds(gh, ih_t))
                tables.append(row)
    # ---- summaries
    G = sorted({g for g, _ in conf})
    L = sorted({l for _, l in conf})
    gtot = Counter()
    for (g, l), c in conf.items():
        gtot[g] += c
    res = dict(variant=a.variant, pages=len(pages), lines=sum(conf.values()),
               confusion={g: {l: conf[(g, l)] for l in L if conf[(g, l)]} for g in G})
    coarse = {}
    for gc in sorted({g for g, _ in coarse_ok}):
        o, b = coarse_ok[(gc, True)], coarse_ok[(gc, False)]
        coarse[gc] = dict(lines=o + b, agree=round(o / max(o + b, 1), 4))
    res["coarse"] = coarse
    allok = sum(v["lines"] * v["agree"] for k, v in coarse.items() if k != "noise")
    alln = sum(v["lines"] for k, v in coarse.items() if k != "noise")
    res["coarse_overall"] = round(allok / alln, 4)
    # per-class precision / recall in coarse classes Indra can name
    pr = {}
    for c in ("body", "heading", "furniture", "list", "table", "caption", "footnote", "figure"):
        tp = sum(n for (g, l), n in conf.items() if G2C.get(g) == c and I2C.get(l) == c)
        fp = sum(n for (g, l), n in conf.items() if G2C.get(g) != c and I2C.get(l) == c and G2C.get(g) != "noise")
        fn = sum(n for (g, l), n in conf.items() if G2C.get(g) == c and I2C.get(l) != c)
        pr[c] = dict(tp=tp, fp=fp, fn=fn, precision=round(tp / max(tp + fp, 1), 4), recall=round(tp / max(tp + fn, 1), 4))
    res["per_class"] = pr
    # order
    def kc_sum(rows, key="kendall", pk="pairs"):
        rr = [r for r in rows if r[key] is not None]
        if not rr:
            return None
        return dict(pages=len(rr), pair_weighted=round(sum(r[key] * r[pk] for r in rr) / sum(r[pk] for r in rr), 4),
                    exact_pages=round(sum(r[key] >= 0.9999 for r in rr) / len(rr), 4),
                    ge99_pages=round(sum(r[key] >= 0.99 for r in rr) / len(rr), 4),
                    lt90_pages=round(sum(r[key] < 0.9 for r in rr) / len(rr), 4))
    res["order"] = dict(all=kc_sum(pages), body=kc_sum(pages, "kendall_body", "pairs_body"),
                        multicol=kc_sum([r for r in pages if r["multicol"]]),
                        multicol_body=kc_sum([r for r in pages if r["multicol"]], "kendall_body", "pairs_body"))
    res["same_block"] = round(sum(r["same_block"] for r in pages) / max(sum(r["same_block_n"] for r in pages), 1), 4)
    # tables
    tf = [t for t in tables if "teds_struct" in t]
    res["tables"] = dict(gemini_tables=len(tables), found_by_indra=sum(t["found"] for t in tables),
                         compared=len(tf),
                         teds_struct=round(float(np.mean([t["teds_struct"] for t in tf])), 3) if tf else None,
                         teds_text=round(float(np.mean([t["teds_text"] for t in tf])), 3) if tf else None,
                         same_grid=sum(t["indra_grid"] == t["gemini_grid"] for t in tf),
                         same_rows=sum(t["indra_grid"][0] == t["gemini_grid"][0] for t in tf))
    # ---- triage: pages Indra calls plain (only Text / Section-Header / Page-Header / Page-Footer blocks)
    COMPLEX_G = {"footnote", "list_item", "reference", "verse", "table", "equation", "caption", "figure",
                 "other_article", "title", "byline", "abstract", "keywords", "trans_title", "boxed", "other"}

    def triage(rows, name):
        plain = [r for r in rows if set(r["indra_labels"]) <= SIMPLE_INDRA and r["indra_labels"]]
        g_plain = [r for r in plain if not (set(r["gemini_types"]) & COMPLEX_G)]
        missed = Counter()
        for r in plain:
            for t in set(r["gemini_types"]) & COMPLEX_G:
                missed[t] += 1
        agree_lines = sum(r["agree"] for r in plain) / max(sum(r["n"] for r in plain), 1)
        full = sum(r["agree"] == r["n"] for r in plain)
        return dict(name=name, pages=len(rows), indra_plain=len(plain), share=round(len(plain) / max(len(rows), 1), 4),
                    gemini_also_plain=len(g_plain), gemini_found_more=dict(missed.most_common()),
                    line_agreement_on_plain=round(agree_lines, 4), pages_all_lines_agree=full,
                    order_on_plain=kc_sum(plain, "kendall_body", "pairs_body"))
    res["triage"] = [triage(pages, "all pages"), triage([r for r in pages if not r["first_page"]], "pages after page 1")]
    # ---- Gemini token use
    res["tokens"] = tok
    res["page_rows"] = pages
    res["table_rows"] = tables
    (OUT / f"layout_scores{a.tag}.json").write_text(json.dumps(res, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))
    show = {k: v for k, v in res.items() if k not in ("tokens", "page_rows", "table_rows", "confusion")}
    print(json.dumps(show, ensure_ascii=False, indent=1, default=lambda o: o.item() if hasattr(o, "item") else str(o)))


if __name__ == "__main__":
    main()
