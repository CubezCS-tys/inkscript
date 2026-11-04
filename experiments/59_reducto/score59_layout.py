"""Experiment 59: Reducto's layout (block types, reading order, footnotes, tables) against our masters' line roles.

    /home/appuser/inkscript/.venv/bin/python score59_layout.py [--variant r1]   -> out/layout_scores_<variant>.json

The same method as exp 58 (score58_layout.py, whose helpers are imported): reference = experiment 43's run
v33_300b_fix3 (Gemini 4 Argon line roles after the code rules = what the masters are built from); every Azure line
gets Reducto's block type from the block it overlaps most (>= 0.3 of the line) and its rank from Reducto's word
order (word citations, in reading order: the first Reducto word the line overlaps); also Indra's (exp 58) on the
same pages for a like-for-like comparison.  Pages: the 27 layout pages of units59.json.
Reducto has no footnote type: "Footer" stands in for footnote as it does for running foot (we report how footnote
lines are typed, and whether they are kept out of body blocks: "separated").
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "41_azure_structure"))
sys.path.insert(0, str(E / "58_indra_ocr"))
from structure import page_lines  # noqa: E402
from score58_layout import G2C, I2C, ALSO_OK, gemini_pages, inter, kendall, gem_table_html, strip_text, grid, base  # noqa: E402

OUT = HERE / "out"
RULES = E / "43_rehearsal/out/v33_300b_fix3/rules"
R2C = {"Text": "body", "Title": "heading", "Section Header": "heading", "Header": "furniture", "Footer": "furniture",
       "Page Number": "furniture", "List Item": "list", "Table": "table", "Figure": "figure", "Key Value": "other",
       "Checkbox": "other", "Comment": "other", "Signature": "other", "none": "none"}
# Reducto's only word for a note at the foot of the page is Footer
R_ALSO_OK = dict(ALSO_OK, footnote={"furniture"})


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def reducto_page(variant, pid, W, H):
    f = OUT / "reducto" / variant / f"{pid}.json"
    if not f.exists():
        return None
    j = jl(f)
    blocks, words = [], []
    for ch in j.get("chunks_full") or []:
        for b in ch["blocks"]:
            bb = b["bbox"]
            box = [bb["left"] * W, bb["top"] * H, (bb["left"] + bb["width"]) * W, (bb["top"] + bb["height"]) * H]
            k = len(blocks)
            blocks.append(dict(type=b["type"], box=box, content=b["content"]))
            for w in (b.get("extra") or {}).get("word_citations") or []:
                wb = w.get("bbox")
                if wb:
                    words.append(([wb["left"] * W, wb["top"] * H, (wb["left"] + wb["width"]) * W,
                                   (wb["top"] + wb["height"]) * H], k))
    return blocks, words


def indra_page(pid):
    f = E / "58_indra_ocr/out/indra/lay300" / f"{pid}.json"
    if not f.exists():
        return None
    ind = jl(f)
    return ind


def assign(az, boxes, labels, min_ov=0.3):
    out = {}
    B = np.array(boxes, float).reshape(-1, 4)
    for l in az:
        bx = np.array(l["px"], float)
        area = max((bx[2] - bx[0]) * (bx[3] - bx[1]), 1.0)
        ov = inter(bx, B)
        out[l["id"]] = (labels[int(ov.argmax())], int(ov.argmax())) if len(ov) and ov.max() / area >= min_ov else ("none", None)
    return out


def ranks_from(az, boxes, min_ov=0.2):
    B = np.array(boxes, float).reshape(-1, 4)
    out = {}
    for l in az:
        bx = np.array(l["px"], float)
        area = max((bx[2] - bx[0]) * (bx[3] - bx[1]), 1.0)
        ov = inter(bx, B)
        if not len(ov):
            out[l["id"]] = None
            continue
        warea = np.maximum((B[:, 2] - B[:, 0]) * (B[:, 3] - B[:, 1]), 1.0)
        hit = np.where((ov / warea >= 0.5) & (warea < 0.6 * area))[0]   # word boxes lying on this line
        # the first word (in the reader's order) that lies on this line; a whole-line box needs min_ov
        out[l["id"]] = int(hit.min()) if len(hit) else (int(ov.argmax()) if ov.max() / area >= min_ov else None)
    return out


def score_reader(name, seq, gtype, az, lab_rank, tomap, also):
    lab_of = {i: lr[0] for i, lr in lab_rank["lab"].items()}
    blk_of = {i: lr[1] for i, lr in lab_rank["lab"].items()}
    ord_of = lab_rank["rank"]
    conf = Counter()
    ok = n = 0
    for i, t in gtype.items():
        lab = lab_of[i]
        conf[(t, lab)] += 1
        gc, ic = G2C.get(t, "other"), tomap.get(lab, "other")
        good = ic == gc or ic in also.get(gc, set())
        if gc != "noise":
            ok += int(good)
            n += 1
    ranks = [ord_of[i] for i, t, k in seq if ord_of.get(i) is not None]
    kc, pairs = kendall(ranks)
    nf = [ord_of[i] for i, t, k in seq if ord_of.get(i) is not None and t not in ("header", "footer")]
    kcb, pairsb = kendall(nf)
    # footnotes separated: a Gemini footnote line in a block that holds no Gemini body line, typed not-body
    fn_lines = [i for i, t, k in seq if t == "footnote"]
    body_blocks = {blk_of[i] for i, t, k in seq if G2C.get(t) == "body" and blk_of.get(i) is not None}
    sep = sum(1 for i in fn_lines if blk_of.get(i) is not None and blk_of[i] not in body_blocks
              and tomap.get(lab_of[i]) != "body")
    return dict(agree=ok, n=n, kendall=kc, pairs=pairs, kendall_body=kcb, pairs_body=pairsb,
                fn_lines=len(fn_lines), fn_separated=sep, conf={f"{g}|{l}": c for (g, l), c in conf.items()})


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--variant", default="r1")
    a = ap.parse_args()
    from inkscript.gold.score import teds
    from inkscript.gold.text import folded
    arts = {x["stem"]: x for x in jl(E / "43_rehearsal/sample43b.json")["articles"]}
    units = [u for u in jl(OUT / "units59.json") if "layout" in u["sets"]]
    want = {(u["stem"], u["page"]): u for u in units}
    rows, tables = [], []
    conf = {"reducto": Counter(), "indra": Counter()}
    for f in sorted(RULES.glob("*.json")):
        d = jl(f)
        stem = d["stem"]
        if not any(s == stem for s, _ in want):
            continue
        gp = gemini_pages(d["answer"])
        for p, (seq, tabs, noise) in gp.items():
            if (stem, p) not in want:
                continue
            pid = f"{stem}_p{p:03d}"
            az, W, H = page_lines(arts[stem], p)
            azb = {l["id"]: l for l in az}
            aztext = {l["id"]: l["text"] for l in az}
            seq = [x for x in seq if x[0] in azb]
            gtype = {i: t for i, t, k in seq}
            for l in az:
                gtype.setdefault(l["id"], "noise")
            rp = reducto_page(a.variant, pid, W, H)
            if rp is None:
                continue
            blocks, words = rp
            lr_r = dict(lab=assign(az, [b["box"] for b in blocks], [b["type"] for b in blocks]),
                        rank=ranks_from(az, [w[0] for w in words]) if words else
                        {i: v[1] for i, v in assign(az, [b["box"] for b in blocks], [b["type"] for b in blocks]).items()})
            res = dict(id=pid, stem=stem, page=p, lines=len(az),
                       reducto=score_reader("reducto", seq, gtype, az, lr_r, R2C, R_ALSO_OK))
            ind = indra_page(pid)
            if ind:
                ib = [b["bbox"] for b in ind["blocks"]]
                il = [ln["box"] for ln in ind["lines"]]
                lr_i = dict(lab=assign(az, ib, [b["label"] for b in ind["blocks"]]), rank=ranks_from(az, il))
                res["indra"] = score_reader("indra", seq, gtype, az, lr_i, I2C, ALSO_OK)
            left = sum(1 for l in az if l["px"][2] < 0.52 * W and l["px"][2] - l["px"][0] > 0.2 * W)
            right = sum(1 for l in az if l["px"][0] > 0.48 * W and l["px"][2] - l["px"][0] > 0.2 * W)
            res["multicol"] = left >= 8 and right >= 8
            res["rtl"] = sum(bool(re.search(r"[؀-ۿ]", l["text"])) for l in az) > 0.5 * len(az)
            res["reducto_types"] = dict(Counter(b["type"] for b in blocks))
            for k in ("reducto", "indra"):
                if k in res:
                    for gl, c in res[k]["conf"].items():
                        conf[k][gl] += c
            rows.append(res)
            # tables: each Gemini table paired with the Reducto Table block it overlaps most
            rt = [(j, b) for j, b in enumerate(blocks) if b["type"] == "Table"]
            for k, trows in tabs:
                ids = [base(i) for r in trows for c in r for i in c.get("lines", [])]
                bxs = [azb[i]["px"] for i in ids if i in azb]
                if not bxs:
                    continue
                gb = np.array([min(b[0] for b in bxs), min(b[1] for b in bxs), max(b[2] for b in bxs), max(b[3] for b in bxs)])
                garea = (gb[2] - gb[0]) * (gb[3] - gb[1])
                best, bo = None, 0.0
                for j, b in rt:
                    o = inter(gb, np.array(b["box"])[None])[0] / max(garea, 1)
                    if o > bo:
                        best, bo = b, o
                gh = gem_table_html(trows, {i: folded(v) for i, v in aztext.items()})
                row = dict(id=pid, gemini_grid=grid(gh), found=best is not None and bo >= 0.3)
                if row["found"]:
                    rh = re.sub(r"<(?!/?(table|tr|td|th)\b)[^>]+>", "", best["content"])
                    rh_t = re.sub(r">([^<]+)<", lambda m: ">" + folded(m.group(1)) + "<", rh)
                    row.update(reducto_grid=grid(rh), teds_struct=teds(strip_text(gh), strip_text(rh)),
                               teds_text=teds(gh, rh_t))
                tables.append(row)
    summ = {}
    for k in ("reducto", "indra"):
        rr = [r[k] for r in rows if k in r]
        if not rr:
            continue
        def kc(sel, key="kendall", pk="pairs"):
            s = [x for x in sel if x[key] is not None]
            if not s:
                return None
            return dict(pages=len(s), pair_weighted=round(sum(x[key] * x[pk] for x in s) / sum(x[pk] for x in s), 4),
                        exact_pages=round(sum(x[key] >= 0.9999 for x in s) / len(s), 4))
        mc = [r[k] for r in rows if k in r and r["multicol"]]
        summ[k] = dict(pages=len(rr), lines=sum(x["n"] for x in rr),
                       role_agreement=round(sum(x["agree"] for x in rr) / max(sum(x["n"] for x in rr), 1), 4),
                       order_all=kc(rr), order_body=kc(rr, "kendall_body", "pairs_body"), order_multicol=kc(mc),
                       order_multicol_body=kc(mc, "kendall_body", "pairs_body"),
                       footnote_lines=sum(x["fn_lines"] for x in rr), footnote_separated=sum(x["fn_separated"] for x in rr))
        # per coarse class recall
        cc = Counter()
        tomap, also = (R2C, R_ALSO_OK) if k == "reducto" else (I2C, ALSO_OK)
        for gl, c in conf[k].items():
            g, l = gl.split("|")
            gc = G2C.get(g, "other")
            good = tomap.get(l, "other") == gc or tomap.get(l, "other") in also.get(gc, set())
            cc[(gc, good)] += c
        summ[k]["per_class"] = {gc: dict(lines=cc[(gc, True)] + cc[(gc, False)],
                                         agree=round(cc[(gc, True)] / max(cc[(gc, True)] + cc[(gc, False)], 1), 3))
                                for gc in sorted({g for g, _ in cc})}
        # what the reader calls each Gemini type
        byg = {}
        for gl, c in conf[k].items():
            g, l = gl.split("|")
            byg.setdefault(g, Counter())[l] += c
        summ[k]["confusion"] = {g: dict(v.most_common()) for g, v in sorted(byg.items())}
    tf = [t for t in tables if "teds_struct" in t]
    summ["tables"] = dict(gemini_tables=len(tables), found=sum(t["found"] for t in tables), compared=len(tf),
                          teds_struct=round(float(np.mean([t["teds_struct"] for t in tf])), 3) if tf else None,
                          teds_text=round(float(np.mean([t["teds_text"] for t in tf])), 3) if tf else None,
                          same_grid=sum(t["reducto_grid"] == t["gemini_grid"] for t in tf), rows=tables)
    summ["pages"] = [dict(id=r["id"], multicol=r["multicol"], rtl=r["rtl"], lines=r["lines"],
                          reducto=dict((k, r["reducto"][k]) for k in ("agree", "n", "kendall", "kendall_body", "fn_lines", "fn_separated")),
                          indra=dict((k, r["indra"][k]) for k in ("agree", "n", "kendall", "kendall_body", "fn_lines", "fn_separated")) if "indra" in r else None)
                     for r in rows]
    (OUT / f"layout_scores_{a.variant}.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    show = {k: v for k, v in summ.items() if k not in ("pages",)}
    show["tables"] = {k: v for k, v in summ["tables"].items() if k != "rows"}
    print(json.dumps(show, ensure_ascii=False, indent=1))
    for r in summ["pages"]:
        x, y = r["reducto"], r["indra"] or {}
        print(f"{r['id']:28s} {'2col' if r['multicol'] else '    '} {'rtl' if r['rtl'] else 'ltr'} roles R {x['agree']}/{x['n']}"
              f" I {y.get('agree')}/{y.get('n')}  order R {x['kendall'] if x['kendall'] is None else round(x['kendall'], 3)}"
              f" I {y.get('kendall') if y.get('kendall') is None else round(y['kendall'], 3)}  fn {x['fn_separated']}/{x['fn_lines']}")


if __name__ == "__main__":
    main()
