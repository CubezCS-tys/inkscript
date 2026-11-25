#!/usr/bin/env python3
"""Experiment 100 scorer: OCRia-1's answers (out/model/exam/<stem>_pNNN.json) against experiment 97's final keys, with
experiment 97's own comparison functions (score97.run_part -> compare_page / compare_tab / compare_refs), exactly as key
A is scored against key B, and R1 against the settled readings with experiment 99's truth construction (score99.r1_truth,
imported, not copied).  Q1-Q5 of the README.

    nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python score100.py
    (EXP100_MODEL=<dir with exam/>  EXP100_SCORES=<out dir>: the self-test points both elsewhere)

Writes <scores>/scorecard100.json, scorecard100.md, misses_<PART>.jsonl, r1_lines.jsonl, q2_pages.jsonl.
Reads experiments 97 and 99; writes nothing there.
"""
from __future__ import annotations

import collections as C
import glob
import json
import os
import re
import statistics
import sys
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert100 as V  # noqa: E402
sys.path.insert(0, V.P97)
sys.path.insert(0, f"{V.X}/99_liteparse_baseline/scripts")
import score97 as S  # noqa: E402
import score99 as S99  # noqa: E402  (r1_truth, r1_rates: imported unchanged)
from common97 import LOCK, fold, lev, ws  # noqa: E402

OUT = os.environ.get("EXP100_SCORES") or f"{V.E}/out/scores"
SET = "exam"
AR = re.compile(r"[؀-ۿ]")
LAT = re.compile(r"[A-Za-z]")
TASHKEEL = re.compile(r"[ً-ْٰ]")
AIND = re.compile(r"[٠-٩۰-۹]")
WDIG = re.compile(r"[0-9]")
HAMZA_SET = set("أإآاىيةهءؤئ")


def jl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


def exam_pages():
    return [(a["stem"], p) for a in LOCK["articles"] for p in sorted(set(a["pages"].values()))]


_views = {}


def view(stem, page):
    k = (stem, page)
    if k not in _views:
        ans = V.load_answer(SET, stem, page)
        az = S99.V.packet_page(stem, page)["azure_lines"]
        _views[k] = (V.PageView(ans["raw"] if ans else "", az), ans)
    return _views[k]


# ================================================================================================ structure (Q3, Q4)
def preds(part, gold_files, kinds=None):
    out, missing = {}, 0
    for name, g in gold_files.items():
        if not S._is_eval_file(part, g):
            continue
        stem, page = g["stem"], int(g["page"])
        v, ans = view(stem, page)
        missing += ans is None
        if part == "PAGE":
            out[name] = V.pred_page(stem, page, v)
        elif part == "TAB":
            out[name] = V.pred_tab(stem, page, v)
        else:
            out[name] = V.pred_refs(stem, page, v, kinds=kinds)
    return out, missing


def p1_restricted(acc):
    n = ok = 0
    for (g, p), v in acc["P1_conf"].items():
        if g in V.EXPRESSIBLE:
            n += v
            ok += acc["P1_ok"][(g, p)]
    return dict(lines=n, accuracy=S.rate(ok, n))


def headings_and_furniture(gold_files, pf):
    """Q4 extras: key heading pieces emitted as headings; output headings that are no key heading (invented);
    running heads / page numbers tagged as page furniture; list items."""
    h = C.Counter()
    for name, g in gold_files.items():
        if name not in pf or S.file_left_out(g):
            continue
        p = pf[name]
        prole = {l: q["role"] for q in p["pieces"] for l in q["lines"]}
        ppiece = {l: n for n, q in enumerate(p["pieces"]) for l in q["lines"]}
        groles = {}
        for q in g.get("pieces") or []:
            if S.left_out(q):
                continue
            for l in q.get("lines") or []:
                groles[l] = q
            if q.get("role") == "heading" and not q.get("label_of"):
                h["key_headings"] += 1
                votes = C.Counter(prole.get(l, "(none)") for l in q["lines"])
                h["key_headings_emitted_as_heading"] += votes.most_common(1)[0][0] == "heading"
            if q.get("role") in ("title", "title-translated"):
                h["key_titles"] += 1
                votes = C.Counter(prole.get(l, "(none)") for l in q["lines"])
                h["key_titles_emitted_as_heading"] += votes.most_common(1)[0][0] == "heading"
            if q.get("role") in ("running-head", "page-number"):
                for l in q.get("lines") or []:
                    h[f"key_{q['role']}_lines"] += 1
                    h[f"key_{q['role']}_lines_as_furniture"] += prole.get(l) in ("running-head", "page-number")
                    h[f"key_{q['role']}_lines_same_tag"] += prole.get(l) == q["role"]
        for n, q in enumerate(p["pieces"]):
            if q["role"] != "heading":
                continue
            h["out_headings_with_lines"] += 1
            kr = C.Counter(groles[l].get("role") if l in groles else "(not a key text line)" for l in q["lines"])
            top = kr.most_common(1)[0][0]
            ok = top in ("heading", "title", "title-translated") or any(groles.get(l, {}).get("label_of") for l in q["lines"])
            h["out_headings_invented"] += not ok
            h[f"out_heading_on_key:{top}"] += 1
    return dict(h,
                headings_found=S.rate(h["key_headings_emitted_as_heading"], h["key_headings"]),
                headings_invented=S.rate(h["out_headings_invented"], h["out_headings_with_lines"]),
                titles_as_heading=S.rate(h["key_titles_emitted_as_heading"], h["key_titles"]),
                running_head_as_furniture=S.rate(h["key_running-head_lines_as_furniture"], h["key_running-head_lines"]),
                page_number_as_furniture=S.rate(h["key_page-number_lines_as_furniture"], h["key_page-number_lines"]),
                page_number_tagged_page_number=S.rate(h["key_page-number_lines_same_tag"], h["key_page-number_lines"]))


def score_structure():
    res = {}
    for part, kinds in (("PAGE", None), ("TAB", None), ("REFS", ("list", "paragraph")), ("REFS_list", ("list",))):
        kp = "REFS" if part.startswith("REFS") else part
        gold, src = S.gold_set(kp, "final")
        pf, missing = preds(kp, gold["files"], kinds=kinds)
        acc, diffs, cnt = S.run_part(kp, gold["files"], pf)
        summ = S.summarise(kp, acc)
        summ["_counts"] = dict(cnt, answers_missing=missing)
        summ["_key_state"] = src
        if kp == "PAGE":
            summ["P1_restricted"] = dict(p1_restricted(acc), roles=sorted(V.EXPRESSIBLE))
            lost = sum(v for (g, p), v in acc["P1_conf"].items() if p == S.NO_BLOCK)
            summ["lines_in_no_block"] = dict(n=lost, share=S.rate(lost, sum(acc["P1_conf"].values())))
            summ["Q4"] = headings_and_furniture(gold["files"], pf)
            kinds_emitted = C.Counter(b["kind"] for (st, pg), (v, a) in _views.items() for b in v.blocks)
            summ["blocks_emitted_by_kind"] = dict(kinds_emitted.most_common())
        res[part] = summ
        jl(f"{OUT}/misses_{part}.jsonl", diffs)
    return res


# ================================================================================================ R1 (Q1)
def r1_line_texts():
    use, truth, extra = S99.r1_truth()
    keys = sorted(use)
    texts, recs, omitted = {}, [], []
    for k in keys:
        r = use[k]
        v, ans = view(r["stem"], r["page"])
        t = truth.get(k) or {}
        q = t.get("exact") or t.get("folded") or r["azure"]
        m = v.line_text(q, near_line=r["line"])
        texts[k] = m["text"]
        if k in truth and not m["found"]:
            omitted.append(k)
        recs.append(dict(id=k, kind=r["kind"], truth=t.get("exact"), truth_folded=t.get("folded"), azure=r["azure"],
                         t91=r.get("t91"), ocria1=m["text"], found=m["found"], sim=m["sim"],
                         block_kind=v.blocks[m["block"]]["kind"] if m["block"] is not None else None))
    return use, truth, extra, keys, texts, recs, omitted


def arabic_behaviour(recs):
    """Digits as printed, tashkeel, hamza / ya / alif maqsura / ta marbuta letters, word order in mixed lines."""
    d = C.Counter()
    subs = C.Counter()
    for r in recs:
        t, o = r["truth"], r["ocria1"]
        if not t or not r["found"]:
            continue
        ta, tw = len(AIND.findall(t)), len(WDIG.findall(t))
        oa, ow = len(AIND.findall(o)), len(WDIG.findall(o))
        if ta and not tw:
            d["lines_printed_arabic_indic_digits"] += 1
            d["arabic_indic_digits_in_truth"] += ta
            d["of_them_output_arabic_indic"] += min(ta, oa)
            d["lines_output_switched_to_western"] += ow > 0 and oa == 0
        if tw and not ta and AR.search(t):
            d["arabic_lines_printed_western_digits"] += 1
            d["lines_output_switched_to_arabic_indic"] += oa > 0 and ow == 0
        tk, ok_ = len(TASHKEEL.findall(t)), len(TASHKEEL.findall(o))
        if AR.search(t):
            d["arabic_lines"] += 1
            d["tashkeel_in_truth"] += tk
            d["tashkeel_in_output"] += ok_
            d["lines_with_tashkeel_in_truth"] += tk > 0
            d["lines_with_tashkeel_in_truth_kept_some"] += tk > 0 and ok_ > 0
            d["lines_without_tashkeel_output_added"] += tk == 0 and ok_ > 0
        # letter substitutions among hamza / alif / ya / alif maqsura / ta marbuta / ha (folded: no tashkeel)
        a, b = S.r1_fold(t), S.r1_fold(o)
        try:
            from rapidfuzz.distance import Levenshtein
            for op in Levenshtein.editops(b, a):
                if op.tag == "replace":
                    x, y = a[op.dest_pos], b[op.src_pos]
                    if x in HAMZA_SET and y in HAMZA_SET:
                        subs[f"{x} printed -> {y}"] += 1
        except ImportError:
            pass
        for ch in HAMZA_SET:
            d[f"truth_count_{ch}"] += a.count(ch)
        # mixed Arabic / Latin lines: word order
        if AR.search(t) and LAT.search(t):
            f = lambda s: S.no_punct(S.r1_fold(s)).split()
            T, O = f(t), f(o)
            d["mixed_lines"] += 1
            d["mixed_lines_equal"] += T == O
            if sorted(T) == sorted(O):
                d["mixed_lines_same_words"] += 1
                d["mixed_lines_same_words_wrong_order"] += T != O
    d = dict(d)
    d["hamza_alif_ya_substitutions"] = dict(subs.most_common(15))
    d["hamza_alif_ya_substitutions_total"] = sum(subs.values())
    d["letters_in_set_in_truth"] = sum(v for k, v in d.items() if k.startswith("truth_count_"))
    return d


def score_r1():
    use, truth, extra, keys, texts, recs, omitted = r1_line_texts()
    res = dict(lines=len(keys), with_truth=sum(1 for k in keys if k in truth),
               truth_by=dict(C.Counter(truth[k]["by"] for k in keys if k in truth)), **extra)
    for w in ("azure", "t91"):
        res[f"witness_{w}"] = S99.r1_rates({k: use[k].get(w) or "" for k in keys}, truth, keys)
    res["ocria1"] = S99.r1_rates(texts, truth, keys)
    found = [k for k in keys if k in truth and k not in omitted]
    res["ocria1_found_lines_only"] = S99.r1_rates(texts, truth, found)
    res["omitted"] = dict(n=len(omitted), share=S.rate(len(omitted), res["with_truth"]), ids=omitted,
                          by_kind=dict(C.Counter(use[k]["kind"] for k in omitted)))
    res["by_kind"] = {kd: S99.r1_rates(texts, truth, [k for k in keys if use[k]["kind"] == kd])["folded_no_punct"]
                      for kd in sorted({use[k]["kind"] for k in keys})}
    res["arabic"] = arabic_behaviour(recs)
    jl(f"{OUT}/r1_lines.jsonl", recs)
    return res


# ================================================================================================ Q2
def _letters(s):
    return len(V.nrm(s).replace(" ", ""))


def loops(raw, az_norm):
    """Windows of 50 normalised characters (step 10) that occur >= 4 times in the answer and at least 3 times more
    than on the printed page (Azure's text): a repeated loop, not a table's repeated values."""
    n = V.nrm(V.strip_fence(raw))
    cnt = C.Counter(n[i:i + 50] for i in range(0, max(0, len(n) - 50), 10))
    bad = [(w, c) for w, c in cnt.items() if c >= 4 and len(w.strip()) >= 40 and c >= az_norm.count(w) + 3]
    return dict(loop=bool(bad), windows=len(bad), example=bad[0][0] if bad else None, max_repeats=max([c for _, c in bad], default=0))


def score_q2(truth_texts):
    gold, _ = S.gold_set("PAGE", "final")
    not_text = {}
    for g in gold["files"].values():
        if S._is_eval_file("PAGE", g):
            not_text[(g["stem"], int(g["page"]))] = set(g.get("azure_lines_that_are_not_text") or [])
    rows = []
    for stem, page in exam_pages():
        v, ans = view(stem, page)
        nt = not_text.get((stem, page), set())
        tt = truth_texts.get((stem, page), {})
        total = miss = 0
        missing_lines = []
        cover = [False] * len(v.NT)
        for ln, L in v.lines.items():
            if ln in nt:
                continue
            txt = tt.get(ln, v.texts[ln])
            n = _letters(txt)
            if not n:
                continue
            total += n
            m = L
            if ln in tt:
                r = v.align(txt, near=L["span"][0] if L.get("span") else None)
                m = r if r["found"] or not L["found"] else L
            if not m["found"]:
                miss += n
                missing_lines.append(ln)
            else:
                for k in range(*m["span"]):
                    cover[k] = True
        for k_, b_ in enumerate(v.nblock):          # runs never span two blocks (separators count as covered)
            if b_ is None:
                cover[k_] = True
        # uncovered runs of the answer
        az_norm = V.nrm(" ".join(v.texts[l] for l in sorted(v.texts) if l not in nt))
        runs, cur = [], []
        for k, ch in enumerate(v.NT):
            if not cover[k]:
                cur.append(k)
            elif cur:
                runs.append(cur)
                cur = []
        if cur:
            runs.append(cur)
        out_letters = len(v.NT.replace(" ", ""))
        inv = dup = 0
        inv_examples = []
        for r in runs:
            s = "".join(v.NT[k] for k in r).strip()
            n = len(s.replace(" ", ""))
            if n < 20:
                continue
            if V.fuzz.partial_ratio(s, az_norm) >= 80:
                dup += n
            else:
                inv += n
                if len(inv_examples) < 3:
                    inv_examples.append(v.original(r[0], r[-1] + 1, snap=False)[:160])
        lp = loops(ans["raw"] if ans else "", az_norm)
        usage = (ans or {}).get("usage") or {}
        rows.append(dict(stem=stem, page=page, kind=",".join(k for k, p in next(a for a in LOCK["articles"] if a["stem"] == stem)["pages"].items() if p == page),
                         answered=ans is not None, printed_letters=total, missing_letters=miss,
                         missing_share=round(miss / total, 4) if total else None, missing_lines=missing_lines,
                         output_letters=out_letters, invented_letters=inv, invented_share=round(inv / out_letters, 4) if out_letters else None,
                         unmatched_on_page_letters=dup, invented_examples=inv_examples,
                         finish_reason=(ans or {}).get("finish_reason"), cut_short=(ans or {}).get("finish_reason") == "length",
                         completion_tokens=usage.get("completion_tokens"), **{f"loop_{k}": x for k, x in lp.items()}))
    jl(f"{OUT}/q2_pages.jsonl", rows)
    P = sum(r["printed_letters"] for r in rows)
    O = sum(r["output_letters"] for r in rows)
    worst = sorted(rows, key=lambda r: -((r["missing_share"] or 0) + (r["invented_share"] or 0)))[:10]
    return dict(pages=len(rows), answered=sum(r["answered"] for r in rows),
                missing_share_of_printed=S.rate(sum(r["missing_letters"] for r in rows), P),
                invented_share_of_output=S.rate(sum(r["invented_letters"] for r in rows), O),
                unmatched_but_on_page_share_of_output=S.rate(sum(r["unmatched_on_page_letters"] for r in rows), O),
                missing_share_pages_without_loops=S.rate(sum(r["missing_letters"] for r in rows if not (r["loop_loop"] or r["cut_short"])),
                                                         sum(r["printed_letters"] for r in rows if not (r["loop_loop"] or r["cut_short"]))),
                invented_share_pages_without_loops=S.rate(sum(r["invented_letters"] for r in rows if not (r["loop_loop"] or r["cut_short"])),
                                                          sum(r["output_letters"] for r in rows if not (r["loop_loop"] or r["cut_short"]))),
                pages_missing_over_5pct=sum(1 for r in rows if (r["missing_share"] or 0) > 0.05),
                pages_missing_over_50pct=sum(1 for r in rows if (r["missing_share"] or 0) > 0.5),
                pages_invented_over_5pct=sum(1 for r in rows if (r["invented_share"] or 0) > 0.05),
                pages_cut_short=sum(r["cut_short"] for r in rows), pages_with_loops=sum(r["loop_loop"] for r in rows),
                worst10=[dict(page=f"{r['stem']}_p{r['page']:03d}", kind=r["kind"], missing=r["missing_share"],
                              invented=r["invented_share"], cut_short=r["cut_short"], loop=r["loop_loop"]) for r in worst])


# ================================================================================================ Q5
def score_cost():
    recs = []
    for f in glob.glob(f"{V.MODEL_DIR}/{SET}/*.json"):
        if os.path.basename(f).startswith("_"):
            continue
        d = json.load(open(f))
        recs.append(d)
    toks = sorted((d.get("usage") or {}).get("completion_tokens") or 0 for d in recs)
    ptoks = sorted((d.get("usage") or {}).get("prompt_tokens") or 0 for d in recs)
    if not toks:
        return {}
    q = lambda xs, p: xs[min(len(xs) - 1, int(round(p * (len(xs) - 1))))]
    runs = [json.load(open(f)) for f in glob.glob(f"{V.MODEL_DIR}/{SET}/_run_*.json")]
    wall = sum(r.get("wall_seconds", 0) for r in runs if r.get("ok"))
    done = sum(r.get("ok", 0) for r in runs)
    res = dict(pages=len(recs), output_tokens=dict(median=statistics.median(toks), p90=q(toks, 0.9), max=toks[-1],
                                                  total=sum(toks)),
               prompt_tokens=dict(median=statistics.median(ptoks), max=ptoks[-1]),
               seconds_per_request=dict(median=statistics.median(d["seconds"] for d in recs)),
               wall_seconds=wall, pages_in_wall=done, concurrency=(recs[0].get("settings") or {}).get("concurrency"))
    if wall and done:
        res["pages_per_minute"] = round(done / wall * 60, 2)
    rate_f = f"{V.E}/out/gpu/gpu_rate.json"
    if os.path.exists(rate_f) and wall and done:
        r = json.load(open(rate_f))
        dph = r["usd_per_hour"]
        per1k = dph * (wall / 3600) / done * 1000
        res.update(gpu=r.get("gpu"), usd_per_hour=dph, usd_per_1000_pages=round(per1k, 3),
                   estimate_gate3_usd=[round(per1k * 2700, 0), round(per1k * 3500, 0)],
                   estimate_archive_30M_usd=round(per1k * 30000, 0),
                   estimate_gpu_hours_gate3=[round(wall / done * 2.7e6 / 3600), round(wall / done * 3.5e6 / 3600)],
                   estimate_gpu_hours_30M=round(wall / done * 3e7 / 3600))
    mons = glob.glob(f"{V.E}/out/model/gpumon_exam*.csv")
    mem = []
    for f in mons:
        for line in open(f):
            m = re.search(r",\s*(\d+) MiB", line)
            if m:
                mem.append(int(m.group(1)))
    if mem:
        res["gpu_memory_used_mib_max"] = max(mem)
    return res


# ================================================================================================ main
def truth_by_page():
    use, truth, _ = S99.r1_truth()
    out = C.defaultdict(dict)
    for k, r in use.items():
        t = (truth.get(k) or {}).get("exact")
        if t:
            out[(r["stem"], r["page"])][r["line"]] = t
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    sc = dict(made=__import__("time").strftime("%Y-%m-%d %H:%M"), model_dir=V.MODEL_DIR, role_mapping=V.KIND_TO_KEY,
              expressible_roles=sorted(V.EXPRESSIBLE), found_similarity=V.FOUND_SIM)
    sc["structure"] = score_structure()
    print("structure scored", flush=True)
    sc["R1"] = score_r1()
    print("R1 scored", flush=True)
    sc["Q2"] = score_q2(truth_by_page())
    print("Q2 scored", flush=True)
    sc["Q5"] = score_cost()
    S.jdump(sc, f"{OUT}/scorecard100.json")
    write_md(sc)
    print("wrote", f"{OUT}/scorecard100.json")


def pc(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def write_md(sc):
    st, R, Q2 = sc["structure"], sc["R1"], sc["Q2"]
    g = lambda *ks: _g(st, *ks)
    r1 = lambda x, m: f"{pc(x[m]['letter_error'])} / {pc(x[m]['word_error'])}"
    rows = [
        ("R1 letters / words wrong, exact", r1(R["ocria1"], "exact"), "Azure 0.8% / 4.3%; t91 1.3% / 5.5%", "<= 0.5% / <= 2%"),
        ("R1 folded, punctuation ignored", r1(R["ocria1"], "folded_no_punct"), "Azure 0.6% / 2.3%; t91 0.7% / 2.6%; ocria-nano 8.9% / 26.5%", "<= 0.5% / <= 2%"),
        ("R1 folded, punct. ignored, found lines only", r1(R["ocria1_found_lines_only"], "folded_no_punct"), "–", "–"),
        ("R1 lines omitted (not found)", f"{R['omitted']['n']} of {R['with_truth']} ({pc(R['omitted']['share'])})", "–", "–"),
        ("Q2 printed text missing from the output", pc(Q2["missing_share_of_printed"]), "R2 lost 0% (0.1% keyed)", "<= 0.5%"),
        ("Q2 output text matching nothing on the page", pc(Q2["invented_share_of_output"]), "–", "–"),
        ("Q2 missing / matching nothing, pages without loops", f"{pc(Q2.get('missing_share_pages_without_loops'))} / {pc(Q2.get('invented_share_pages_without_loops'))}", "–", "–"),
        ("Q2 pages cut short / with loops", f"{Q2['pages_cut_short']} / {Q2['pages_with_loops']} of {Q2['pages']}", "–", "–"),
        ("P1 label per line, all roles", f"{pc(g('PAGE','P1','accuracy'))} (n={g('PAGE','P1','lines')})", "95.7%", ">= 97%"),
        ("P1, roles Markdown can name", f"{pc(g('PAGE','P1_restricted','accuracy'))} (n={g('PAGE','P1_restricted','lines')})", "–", "(diagnostic)"),
        ("Key text lines in no output block", pc(g("PAGE", "lines_in_no_block", "share")), "0.1%", "<= 0.5%"),
        ("P2 grouping, same-piece F1", pc(g("PAGE", "P2", "f1")), "99.6%", ">= 95%"),
        ("P3 order, one column", f"{pc(g('PAGE','P3','one','share'))} (n={g('PAGE','P3','one','pairs')})", "99.1%", ">= 98%"),
        ("P3 order, two columns", f"{pc(g('PAGE','P3','two','share'))} (n={g('PAGE','P3','two','pairs')})", "100%", ">= 95%"),
        ("Headings found / invented", f"{pc(g('PAGE','Q4','headings_found'))} / {pc(g('PAGE','Q4','headings_invented'))}", "(P5 not keyed)", ">= 97% / <= 3%"),
        ("Running heads / page numbers as furniture", f"{pc(g('PAGE','Q4','running_head_as_furniture'))} / {pc(g('PAGE','Q4','page_number_as_furniture'))}", "page numbers merged into the head: all 56", "–"),
        ("P7 tables found", f"{pc(g('TAB','P7.found','share'))} (+{g('TAB','P7.found','pred_extra')} extra)", "100%", ">= 98%"),
        ("P7 shape (of found)", f"{pc(g('TAB','P7.shape','share'))} (n={g('TAB','P7.shape','n')})", "100%", ">= 95%"),
        ("P7 header rows (of found)", pc(g("TAB", "P7.header_rows", "share")), "93.0%", "–"),
        ("P7 cells exact / folded", f"{pc(g('TAB','P7.cells','exact'))} / {pc(g('TAB','P7.cells','folded'))} (n={g('TAB','P7.cells','n')})", "90.1% / 98.5%; LiteParse best 26.7% / 28.7%", ">= 99.5%"),
        ("P7 cells content wrong: misplaced / different text", f"{pc(g('TAB','P7.cells','misplaced'))} / {pc(g('TAB','P7.cells','different_text'))}", "–", "–"),
        ("P7 tables with no content-wrong cell", pc(g("TAB", "P7.cell_tables", "zero_content_wrong")), "–", "–"),
        ("P9 reference boundaries (list items + paragraphs)", f"{pc(g('REFS','P9.boundaries','share'))} ({g('REFS','P9.boundaries','pred_refs')} pieces)", "99.2%", ">= 98%"),
        ("P9 boundaries, list items only", pc(g("REFS_list", "P9.boundaries", "share")), "99.2%", "–"),
    ]
    L = [f"# Experiment 100 — OCRia-1 on the extraction exam\n\nScored {sc['made']} ({sc['model_dir']}) against experiment 97's final keys "
         "with experiment 97's own comparison functions.\n",
         "| Measure | OCRia-1 | Baseline (Azure + Gemini / readers) | Pass mark |", "|---|---|---|---|"]
    L += [f"| {a} | {b} | {c} | {d} |" for a, b, c, d in rows]
    L.append(f"\nR1 witnesses through this count: Azure {r1(R['witness_azure'], 'exact')} exact, "
             f"{r1(R['witness_azure'], 'folded_no_punct')} folded; t91 {r1(R['witness_t91'], 'exact')}, {r1(R['witness_t91'], 'folded_no_punct')}.")
    L.append(f"\nArabic behaviour: `{json.dumps(R['arabic'], ensure_ascii=False)}`")
    L.append(f"\nQ2 worst pages: `{json.dumps(Q2['worst10'], ensure_ascii=False)}`")
    L.append(f"\nQ4 extras: `{json.dumps(g('PAGE', 'Q4'), ensure_ascii=False)}`")
    L.append(f"\nBlocks emitted: `{json.dumps(g('PAGE', 'blocks_emitted_by_kind'), ensure_ascii=False)}`")
    L.append(f"\nP1 per role: `{json.dumps({k: (v['n'], v['accuracy']) for k, v in (g('PAGE','P1','per_role') or {}).items()}, ensure_ascii=False)}`")
    L.append(f"\nP1 confusion (top 15): `{json.dumps(dict(list((g('PAGE','P1','confusion') or {}).items())[:15]), ensure_ascii=False)}`")
    L.append(f"\nP7 cell kinds: `{json.dumps(g('TAB', 'P7.cell_kinds'), ensure_ascii=False)}`")
    L.append(f"\nQ5 cost: `{json.dumps(sc.get('Q5'), ensure_ascii=False)}`")
    open(f"{OUT}/scorecard100.md", "w").write("\n".join(L) + "\n")


def _g(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d


if __name__ == "__main__":
    if sys.argv[1:2] == ["--md"]:
        write_md(json.load(open(f"{OUT}/scorecard100.json")))
    else:
        main()
