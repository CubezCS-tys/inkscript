"""Experiment 58: could Indra take work off Gemini?  Code rules on top of Indra's labels, and page triage, measured
against Gemini's line roles (out/layout_lines.jsonl from score58_layout.py).  No calls.

    python3 hybrid58.py   -> out/hybrid_scores.json and a printout

1. Indra + rules (a fair shot at what Indra's labels miss):
   footnotes  a line below half the page whose height is under 0.88 x the page's median body-line height, labelled
              Text / List-Group / Footnote by Indra, or any line under the top of the page's first Indra Footnote
              block in the same horizontal span -> footnote
   furniture  a line in the top or bottom 6% of the page that is short (under 40% of the page width) -> furniture
2. Triage: which pages could skip Gemini's per-page structure work?
   T0 Indra-plain: only Text / Section-Header / Page-Header / Page-Footer blocks
   T1 T0, not page 1, and no footnote candidate (rule above), no two lines side by side on a one-column page
      (verse halves), no line starting with a list / note marker
   For each: the share of pages, the share Gemini also calls plain, line-role agreement, order agreement.
Price model (cost58.py, v3.3 Batch tokens): per page 1,295 image + 1,268 Azure-line + 801 prompt input tokens,
892 output tokens; $1 / $5 per M; v3.5b is ~$0.0094 a page.
"""
import json
import re
import statistics as st
from collections import Counter
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
G2C = {"paragraph": "body", "quote": "body", "abstract": "body", "keywords": "body", "boxed": "body",
       "title": "heading", "trans_title": "heading", "heading": "heading", "byline": "byline",
       "list_item": "list", "reference": "reference", "footnote": "footnote", "verse": "verse", "table": "table",
       "equation": "equation", "caption": "caption", "figure": "figure", "header": "furniture",
       "footer": "furniture", "other_article": "other_article", "other": "other", "noise": "noise"}
I2C = {"Text": "body", "Section-Header": "heading", "Page-Header": "furniture", "Page-Footer": "furniture",
       "List-Group": "list", "Table": "table", "Caption": "caption", "Footnote": "footnote",
       "Table-Of-Contents": "other", "Form": "other", "Picture": "figure", "none": "none"}
ALSO_OK = {"byline": {"body", "heading"}, "reference": {"list", "body"}, "verse": {"body"},
           "equation": {"body"}}
SIMPLE = {"Text", "Section-Header", "Page-Header", "Page-Footer"}
COMPLEX_G = {"footnote", "list_item", "reference", "verse", "table", "equation", "caption", "figure",
             "other_article", "title", "byline", "abstract", "keywords", "trans_title", "boxed", "other"}
MARK = re.compile(r"^\s*[\(\[]?\s*[0-9٠-٩]{1,3}\s*[\)\]\-\.]")
PAGE_USD = 0.0094
IN_IMG, IN_AZ, IN_PROMPT, OUT_TOK = 1295, 1268, 801, 892
P_IN, P_OUT = 1.0, 5.0


def ok(g, lab):
    gc, ic = G2C.get(g, "other"), I2C.get(lab, "other")
    return ic == gc or ic in ALSO_OK.get(gc, set())


def rules(pg):
    """Indra label per line after the two code rules (coarse class)."""
    L, W, H = pg["lines"], pg["W"], pg["H"]
    hs = [l["px"][3] - l["px"][1] for l in L if l["lab"] == "Text"]
    med = st.median(hs) if hs else None
    fn_top = [l["px"] for l in L if l["lab"] == "Footnote"]
    out = {}
    for l in L:
        c = I2C.get(l["lab"], "other")
        x0, y0, x1, y1 = l["px"]
        h = y1 - y0
        if c in ("body", "list", "footnote") and med and y0 > 0.5 * H and h < 0.88 * med:
            c = "footnote"
        if c in ("body", "list") and any(y0 >= f[1] - 2 and min(x1, f[2]) - max(x0, f[0]) > 0.3 * (x1 - x0)
                                         for f in fn_top):
            c = "footnote"
        if (y1 < 0.06 * H or y0 > 0.94 * H) and (x1 - x0) < 0.4 * W and c in ("body", "heading", "list"):
            c = "furniture"
        out[l["i"]] = c
    return out, med


def ok_c(g, c):
    gc = G2C.get(g, "other")
    return c == gc or c in ALSO_OK.get(gc, set())


def side_by_side(L, W):
    rows = 0
    for a in L:
        for b in L:
            if a is b or a["px"][0] <= b["px"][2]:
                continue
            ov = min(a["px"][3], b["px"][3]) - max(a["px"][1], b["px"][1])
            if ov > 0.6 * min(a["px"][3] - a["px"][1], b["px"][3] - b["px"][1]) and a["px"][0] - b["px"][2] > 0.03 * W:
                rows += 1
    return rows


def kendall(xs):
    n = len(xs)
    c = p = 0
    for i in range(n):
        for j in range(i + 1, n):
            if xs[i] != xs[j]:
                p += 1
                c += xs[i] < xs[j]
    return (c / p if p else None), p


def main():
    pages = [json.loads(l) for l in open(OUT / "layout_lines.jsonl", encoding="utf-8")]
    base = Counter()
    rul = Counter()
    pr = Counter()
    rows = []
    for pg in pages:
        L = [l for l in pg["lines"] if l["g"] != "noise"]
        lab_r, med = rules(pg)
        for l in L:
            base[ok(l["g"], l["lab"])] += 1
            rul[ok_c(l["g"], lab_r[l["i"]])] += 1
            for cls in ("footnote", "furniture"):
                gi, ri = G2C.get(l["g"]) == cls, lab_r[l["i"]] == cls
                bi = I2C.get(l["lab"]) == cls
                pr[(cls, "rules", gi, ri)] += 1
                pr[(cls, "indra", gi, bi)] += 1
        labs = {l["lab"] for l in pg["lines"] if l["lab"] != "none"}
        gts = {l["g"] for l in pg["lines"]}
        n_fn_cand = sum(1 for l in pg["lines"] if lab_r[l["i"]] == "footnote")
        n_mark = sum(1 for l in pg["lines"] if MARK.match(l["t"]))
        multicol_like = sum(1 for l in pg["lines"] if (l["px"][2] - l["px"][0]) < 0.45 * pg["W"]) > 0.5 * max(len(pg["lines"]), 1)
        sbs = 0 if multicol_like else side_by_side(pg["lines"], pg["W"])
        seq = sorted([l for l in pg["lines"] if l["go"] is not None and l["io"] is not None
                      and l["g"] not in ("header", "footer")], key=lambda l: l["go"])
        kc, pairs = kendall([l["io"] for l in seq]) if len(seq) < 400 else (None, 0)
        agree = sum(ok(l["g"], l["lab"]) for l in L)   # Indra's own labels (the rules did worse, above)
        rows.append(dict(id=pg["id"], p1=pg["id"].endswith("_p001"), plain_i=bool(labs) and labs <= SIMPLE,
                         plain_g=not (gts & COMPLEX_G), fn_cand=n_fn_cand, marks=n_mark, sbs=sbs, n=len(L),
                         agree=agree, kc=kc, pairs=pairs, g_extra=sorted(gts & COMPLEX_G)))
    res = dict(lines=sum(base.values()), coarse_indra=base[True] / sum(base.values()),
               coarse_indra_rules=rul[True] / sum(rul.values()))
    prc = {}
    for cls in ("footnote", "furniture"):
        for who in ("indra", "rules"):
            tp, fp, fn = pr[(cls, who, True, True)], pr[(cls, who, False, True)], pr[(cls, who, True, False)]
            prc[f"{cls} {who}"] = dict(precision=round(tp / max(tp + fp, 1), 3), recall=round(tp / max(tp + fn, 1), 3),
                                       tp=tp, fp=fp, fn=fn)
    res["footnote_furniture"] = prc

    def tri(name, sel):
        rs = [r for r in rows if sel(r)]
        n = len(rs)
        kk = [r for r in rs if r["kc"] is not None]
        miss = Counter(t for r in rs for t in r["g_extra"])
        return dict(name=name, pages=n, share=round(n / len(rows), 4),
                    gemini_plain=round(sum(r["plain_g"] for r in rs) / max(n, 1), 4),
                    line_agree=round(sum(r["agree"] for r in rs) / max(sum(r["n"] for r in rs), 1), 4),
                    pages_all_agree=round(sum(r["agree"] == r["n"] for r in rs) / max(n, 1), 4),
                    order_pairs=round(sum(r["kc"] * r["pairs"] for r in kk) / max(sum(r["pairs"] for r in kk), 1), 4),
                    order_exact=round(sum(r["kc"] >= 0.9999 for r in kk) / max(len(kk), 1), 4),
                    gemini_found_on_pages={k: v for k, v in miss.most_common(10)})
    T = [tri("T0 Indra-plain", lambda r: r["plain_i"]),
         tri("T0 after page 1", lambda r: r["plain_i"] and not r["p1"]),
         tri("T1 strict", lambda r: r["plain_i"] and not r["p1"] and r["fn_cand"] == 0 and r["sbs"] == 0 and r["marks"] == 0),
         tri("all pages", lambda r: True)]
    res["triage"] = T
    # ---- cost designs (per page, Batch, v3.5b price scaled by token shares)
    tin = IN_IMG + IN_AZ + IN_PROMPT
    unit_in, unit_out = tin * P_IN / 1e6, OUT_TOK * P_OUT / 1e6
    scale = PAGE_USD / (unit_in + unit_out)            # v3.3 tokens -> v3.5b price
    share_in = unit_in / (unit_in + unit_out)
    d = {}
    for t in T[:3]:
        s = t["share"]
        # a skipped page saves its image + Azure lines + its output; the prompt is per chunk and stays
        saved = s * (IN_IMG + IN_AZ) * P_IN / 1e6 + s * OUT_TOK * P_OUT / 1e6
        d["skip " + t["name"]] = dict(pages_skipped=s, saving_share=round(saved / (unit_in + unit_out), 3),
                                      usd_page=round(PAGE_USD * (1 - saved / (unit_in + unit_out)), 5))
    # pre-fill: Gemini answers only the lines where it disagrees with Indra's draft (diff answer); input grows by the
    # labels (about 3 tokens a line, ~45 lines a page)
    blocks_share = 0.39                                  # plain blocks' share of the answer (cost58.py)
    agree = res["coarse_indra_rules"]
    out_saved = blocks_share * agree
    in_added = 45 * 3
    saved = out_saved * unit_out - in_added * P_IN / 1e6
    d["pre-fill, diff answer"] = dict(saving_share=round(saved / (unit_in + unit_out), 3),
                                      usd_page=round(PAGE_USD * (1 - saved / (unit_in + unit_out)), 5))
    res["cost"] = dict(scale_to_v35b=round(scale, 3), input_share=round(share_in, 3), designs=d,
                       note="16 pages a document (exp 40: 15.9); 1M documents = 15.9M pages")
    for k, v in d.items():
        v["usd_1M_docs"] = round(v["usd_page"] * 15.9e6)
    res["cost"]["baseline_usd_1M_docs"] = round(PAGE_USD * 15.9e6)
    (OUT / "hybrid_scores.json").write_text(json.dumps(res, ensure_ascii=False, indent=1))
    print(json.dumps(res, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
