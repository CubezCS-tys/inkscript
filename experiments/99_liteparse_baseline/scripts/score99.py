#!/usr/bin/env python3
"""Experiment 99 scorer: LiteParse (out/runs/exam_<mode>/) against experiment 97's final keys, with experiment 97's own
comparison functions (score97.compare_page / compare_tab / compare_refs via score97.run_part), exactly as key A is
scored against key B.  R1 reading against the settled readings (out/reading/settle/{A,B,C}) with score97's folds.

    nice -n 19 ionice -c3 /home/appuser/inkscript/.venv/bin/python score99.py

Writes out/scores/liteparse_scorecard.json, liteparse_scorecard.md, misses_<mode>_<PART>.jsonl, r1_lines_<mode>.jsonl.
Reads experiment 97; writes nothing there.
"""
from __future__ import annotations

import collections as C
import json
import os
import re
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import convert99 as V  # noqa: E402
sys.path.insert(0, V.P97)
import score97 as S  # noqa: E402
from common97 import BY_STEM, fold, lev, ws  # noqa: E402

E = V.E
OUT = f"{E}/out/scores"
MODES = ["text", "text_apache", "tess", "nano"]
MODE_NAME = {"text": "text layer (LayoutNet on)", "text_apache": "text layer (Apache-only, no model)",
             "tess": "Tesseract OCR on page image", "nano": "ocria-nano OCR on page image"}
AR = re.compile(r"[؀-ۿ]")


def jl(path, rows):
    with open(path, "w") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=str) + "\n")


_runs = {}


def run(mode, stem):
    k = (mode, stem)
    if k not in _runs:
        _runs[k] = V.load_run(f"exam_{mode}", stem)
    return _runs[k]


def lp_page(mode, stem, page):
    r = run(mode, stem)
    if not r:
        return None
    return (r.get("pages") or {}).get(str(page))


EMPTY = dict(width=1.0, height=1.0, text_items=[], blocks=[])


# ================================================================================================ structure
def preds(mode, part, gold_files):
    out, missing = {}, 0
    for name, g in gold_files.items():
        if not S._is_eval_file(part, g):
            continue
        stem, page = g["stem"], int(g["page"])
        lp = lp_page(mode, stem, page)
        if lp is None:
            missing += 1
            lp = dict(EMPTY, width=V.packet_page(stem, page)["width_px"] / (300 / 72))
        if part == "PAGE":
            out[name] = V.pred_page(stem, page, lp)[0]
        elif part == "TAB":
            out[name] = V.pred_tab(stem, page, lp)
        elif part == "REFS":
            out[name] = V.pred_refs(stem, page, lp)
        elif part == "REFS_para":
            out[name] = V.pred_refs(stem, page, lp, kinds=("list_item", "paragraph"))
    return out, missing


def p1_restricted(acc):
    n = ok = 0
    for (g, p), v in acc["P1_conf"].items():
        if g in V.EXPRESSIBLE:
            n += v
            ok += acc["P1_ok"][(g, p)]
    return dict(lines=n, accuracy=S.rate(ok, n))


def score_structure(mode):
    res = {}
    for part in ("PAGE", "TAB", "REFS", "REFS_para"):
        kp = "REFS" if part == "REFS_para" else part
        gold, src = S.gold_set(kp, "final")
        pf, missing = preds(mode, part, gold["files"])
        acc, diffs, cnt = S.run_part(kp, gold["files"], pf)
        summ = S.summarise(kp, acc)
        summ["_counts"] = dict(cnt, pred_pages_missing=missing)
        summ["_key_state"] = src
        if kp == "PAGE":
            summ["P1_restricted"] = p1_restricted(acc)
            summ["P1_restricted"]["roles"] = sorted(V.EXPRESSIBLE)
            # lines the key calls text that LiteParse put in no block (no word matched, or words outside blocks)
            lost = sum(v for (g, p), v in acc["P1_conf"].items() if p == S.NO_BLOCK)
            summ["lines_in_no_block"] = dict(n=lost, share=S.rate(lost, sum(acc["P1_conf"].values())))
        res[part] = summ
        jl(f"{OUT}/misses_{mode}_{part}.jsonl", diffs)
    return res


# ================================================================================================ R1
def r1_truth():
    """Same construction as score97.score_r1: A=B exact; else the third reader C (unreadable / unsure left out,
    order_only reported apart); A~B after folding gives a folded truth only.  Lines where all three witnesses agree
    have no reader: their truth is Azure's text (score97 extrapolates them at the control lines' error rate; the 60
    control lines, read blind, had none wrong)."""
    R = S.READING
    def load(p):
        out = {}
        if os.path.exists(p):
            for x in open(p):
                x = x.strip()
                if x:
                    try:
                        d = json.loads(x)
                        out[d["id"]] = d
                    except (ValueError, KeyError):
                        pass
        return out
    RA, RB, RC = (load(f"{S.SETTLE}/{k}/readings.jsonl") for k in "ABC")
    disp = {d["id"]: d for d in map(json.loads, open(f"{R}/disputes.jsonl"))}
    lines = {}
    for r in map(json.loads, open(f"{R}/lines.jsonl")):
        lines[f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}"] = r
    use = {k: r for k, r in lines.items() if r.get("all_three_agree") is not None}
    truth, order_only, left = {}, set(), set()
    ok = lambda x: x and not x.get("unsure") and isinstance(x.get("printed"), str)
    for i, d in disp.items():
        a, b, c3 = RA.get(i), RB.get(i), RC.get(i)
        if ok(a) and ok(b) and ws(a["printed"]) == ws(b["printed"]):
            truth[i] = dict(exact=ws(a["printed"]), folded=S.r1_fold(ws(a["printed"])), by="A=B")
            continue
        if c3:
            if c3.get("unreadable") or c3.get("unsure"):
                left.add(i)
            elif c3.get("order_only"):
                order_only.add(i)
            elif isinstance(c3.get("printed"), str):
                truth[i] = dict(exact=ws(c3["printed"]), folded=S.r1_fold(ws(c3["printed"])), by="C")
        elif ok(a) and ok(b) and S.r1_fold(ws(a["printed"])) == S.r1_fold(ws(b["printed"])):
            truth[i] = dict(folded=S.r1_fold(ws(a["printed"])), by="A~B folded")
    for k, r in use.items():
        if k not in disp and r["all_three_agree"]:
            t = ws(r["azure"])
            truth[k] = dict(exact=t, folded=S.r1_fold(t), by="all three agree (Azure text)")
    return use, truth, dict(order_only=len(order_only), left_out_by_C=len(left))


def r1_rates(texts, truth, keys):
    """letters / words wrong per comparison mode (score97's three: exact, folded, folded + punctuation ignored)."""
    out = {}
    for mode in ("exact", "folded", "folded_no_punct"):
        tf = (lambda x: x) if mode == "exact" else (S.r1_fold if mode == "folded" else (lambda x: S.no_punct(S.r1_fold(x))))
        tt = (lambda x: x) if mode != "folded_no_punct" else S.no_punct
        le = ll = we = wl = n = nw = 0
        for k in keys:
            t = (truth.get(k) or {}).get("exact" if mode == "exact" else "folded")
            if t is None or k not in texts:
                continue
            a, b, c, d = S._errs(tf(texts[k] or ""), tt(t))
            le += a; ll += b; we += c; wl += d; n += 1; nw += a > 0
        out[mode] = dict(lines=n, lines_wrong=nw, letters_wrong=le, letters=ll, letter_error=S.rate(le, ll),
                         word_error=S.rate(we, wl))
    return out


def score_r1(modes):
    use, truth, extra = r1_truth()
    keys = sorted(use)
    res = dict(lines=len(keys), with_truth=sum(1 for k in keys if k in truth),
               truth_by=dict(C.Counter(truth[k]["by"] for k in keys if k in truth)), **extra)
    # the exam's own witnesses through the same direct count, to check this count against score97's estimate
    for w in ("azure", "t91"):
        res[f"witness_{w}"] = r1_rates({k: use[k].get(w) or "" for k in keys}, truth, keys)
    for mode in modes:
        texts, rtl, recs = {}, {}, []
        item_dir = C.Counter()
        for k in keys:
            r = use[k]
            lp = lp_page(mode, r["stem"], r["page"])
            if lp is None:
                texts[k] = rtl[k] = ""
                continue
            m = V.match_page(r["stem"], r["page"], lp)
            texts[k] = V.line_text(m, lp, r["line"], "returned")
            rtl[k] = V.line_text(m, lp, r["line"], "rtl")
            items = m["line_items"].get(r["line"], [])
            t_ = (truth.get(k) or {}).get("folded") or ""
            if len(items) >= 2 and AR.search(t_):
                xs = [lp["text_items"][i]["x"] + lp["text_items"][i]["width"] / 2 for i in items]
                inc = sum(1 for a, b in zip(xs, xs[1:]) if b > a)
                dec = len(xs) - 1 - inc
                item_dir["left_to_right (visual)" if inc > dec else "right_to_left (reading)" if dec > inc else "mixed"] += 1
            recs.append(dict(id=k, kind=r["kind"], truth=(truth.get(k) or {}).get("exact"), azure=r["azure"],
                             t91=r.get("t91"), liteparse=texts[k], liteparse_rtl_reordered=rtl[k],
                             n_items=len(m["line_items"].get(r["line"], []))))
        res[mode] = dict(as_returned=r1_rates(texts, truth, keys), items_reordered_right_to_left=r1_rates(rtl, truth, keys),
                         order=r1_order(texts, truth, keys),
                         arabic_lines_with_2plus_items_direction=dict(item_dir), empty_lines=sum(1 for k in keys if not texts.get(k)))
        jl(f"{OUT}/r1_lines_{mode}.jsonl", recs)
    return res


def r1_order(texts, truth, keys):
    """Q3: for Arabic lines, is the returned text in logical order?  Folded, punctuation ignored.  Counts lines equal
    to the truth as returned, equal only after reversing the word order, equal only after reversing the characters;
    and, since OCR rarely gives an exact line, lines where reversing the word order lowers the word error."""
    c = C.Counter()
    for k in keys:
        t = (truth.get(k) or {}).get("folded")
        x = texts.get(k) or ""
        if t is None or not AR.search(t) or not x:
            continue
        f = lambda s: S.no_punct(S.r1_fold(s))
        T, Xf = f(t), f(x)
        c["arabic_lines"] += 1
        rw = " ".join(reversed(Xf.split()))
        rc = Xf[::-1]
        if Xf == T:
            c["equal_as_returned"] += 1
        elif rw == T:
            c["equal_only_word_order_reversed"] += 1
        elif rc == T:
            c["equal_only_characters_reversed"] += 1
        if sorted(Xf.split()) == sorted(T.split()):
            c["same_words_as_truth"] += 1
            c["same_words_in_wrong_order"] += Xf != T
        we = lev(Xf.split(), T.split())
        wr = lev(rw.split(), T.split())
        if len(Xf.split()) > 1:
            c["multiword_lines"] += 1
            c["word_reversal_lowers_word_error"] += wr < we
            c["word_reversal_raises_word_error"] += wr > we
    n = c["arabic_lines"] or 1
    return dict(c, share_equal_as_returned=round(c["equal_as_returned"] / n, 4),
                share_equal_only_after_word_reversal=round(c["equal_only_word_order_reversed"] / n, 4),
                share_equal_only_after_char_reversal=round(c["equal_only_characters_reversed"] / n, 4),
                share_wrong_order_among_lines_with_right_words=round(c["same_words_in_wrong_order"] / max(1, c["same_words_as_truth"]), 4),
                share_word_reversal_better=round(c["word_reversal_lowers_word_error"] / max(1, c["multiword_lines"]), 4))


# ================================================================================================ cost
def cost(mode):
    f = f"{E}/out/logs/time_exam_{mode}.log"
    d = {}
    if os.path.exists(f):
        t = open(f).read()
        m = re.search(r"Maximum resident set size \(kbytes\): (\d+)", t)
        w = re.search(r"Elapsed \(wall clock\) time \(h:mm:ss or m:ss\): ([\d:.]+)", t)
        cpu = re.search(r"Percent of CPU this job got: (\d+)%", t)
        if m:
            d["peak_rss_mb"] = round(int(m.group(1)) / 1024)
        if w:
            parts = [float(x) for x in w.group(1).split(":")]
            sec = parts[-1] + (parts[-2] * 60 if len(parts) > 1 else 0) + (parts[-3] * 3600 if len(parts) > 2 else 0)
            d["wall_seconds_last_process"] = round(sec, 1)
        if cpu:
            d["cpu_percent"] = int(cpu.group(1))
    secs = n = 0
    for a in V.json.load(open(f"{V.P97}/LOCKED_EVAL.json"))["articles"]:
        r = run(mode, a["stem"])
        if r:
            secs += r["seconds"]
            n += len(r["exam_pages"])
    d.update(pages=n, seconds_in_parse=round(secs, 1), pages_per_second=round(n / secs, 3) if secs else None)
    return d


def netcheck():
    """Every connect() strace saw, per exam run: AF_UNIX (local sockets) apart from network families."""
    out = {}
    for f in sorted(os.listdir(f"{E}/out/logs")):
        if not f.startswith("net_"):
            continue
        fam = C.Counter()
        net = []
        for line in open(f"{E}/out/logs/{f}"):
            m = re.search(r"sa_family=(AF_\w+)", line)
            if m:
                fam[m.group(1)] += 1
                if m.group(1) in ("AF_INET", "AF_INET6"):
                    net.append(line.strip()[:200])
        out[f[4:-4]] = dict(families=dict(fam), network_connects=net[:10], n_network=len(net))
    return out


def main():
    os.makedirs(OUT, exist_ok=True)
    modes = [m for m in (sys.argv[1:] or MODES) if os.path.isdir(f"{E}/out/runs/exam_{m}")]
    sc = dict(made=__import__("time").strftime("%Y-%m-%d %H:%M"), modes=modes, mode_names=MODE_NAME,
              role_mapping=V.KIND_TO_KEY, expressible_roles=sorted(V.EXPRESSIBLE), structure={}, cost={})
    for m in modes:
        sc["structure"][m] = score_structure(m)
        sc["cost"][m] = cost(m)
        print("scored", m, flush=True)
    sc["R1"] = score_r1(modes)
    sc["network"] = netcheck()
    S.jdump(sc, f"{OUT}/liteparse_scorecard.json")
    write_md(sc)
    print("wrote", f"{OUT}/liteparse_scorecard.json")


# ================================================================================================ scorecard text
BASE = {  # Baseline v1 (Azure + Gemini) and key A vs key B, from experiment 97's scorecard.md (2026-11-10)
    "P1": ("95.7%", "99.2%", ">= 97%"), "P1r": ("–", "–", "(diagnostic)"), "nob": ("0.1% (R2 keyed lost)", "0.0%", "<= 0.5%"),
    "P2": ("99.6%", "99.9%", ">= 95%"), "P2nt": ("98.1%", "99.5%", "(diagnostic)"),
    "P3one": ("99.1%", "100.0%", ">= 98%"), "P3two": ("100.0%", "100.0%", ">= 95%"), "P3mixed": ("98.7%", "100.0%", "(apart)"),
    "P3first": ("100.0%", "100.0%", "(apart)"),
    "P7found": ("100.0%", "100.0%", ">= 98%"), "P7shape": ("100.0%", "100.0%", ">= 95%"), "P7hdr": ("93.0%", "100.0%", "(no mark)"),
    "P7a": ("90.1%", "99.7%", ">= 99.5%"), "P7b": ("98.5%", "99.8%", ">= 99.5%"),
    "P9": ("99.2%", "99.3%", ">= 98%"), "P9p": ("99.2%", "99.3%", "(diagnostic)"),
    "R1e": ("Azure 0.8% / 4.3%; t91 1.3% / 5.5%", "–", "<= 0.5% / <= 2%"),
    "R1f": ("Azure 0.6% / 2.3%; t91 0.7% / 2.6%", "–", "<= 0.5% / <= 2%"),
}


def pc(x):
    return "–" if x is None else f"{100 * x:.1f}%"


def write_md(sc):
    M = sc["modes"]
    st, R = sc["structure"], sc["R1"]
    def g(m, *ks):
        x = st[m]
        for k in ks:
            x = (x or {}).get(k) if isinstance(x, dict) else None
        return x
    def row(label, key, f):
        b = BASE[key]
        return f"| {label} | " + " | ".join(f(m) for m in M) + f" | {b[0]} | {b[1]} | {b[2]} |"
    def n_(m, *ks):
        v = g(m, *ks)
        return v
    rows = [
        row("P1 label per line, all roles (n lines)", "P1", lambda m: f"{pc(g(m,'PAGE','P1','accuracy'))} (n={g(m,'PAGE','P1','lines')})"),
        row("P1 label per line, roles LiteParse can name", "P1r", lambda m: f"{pc(g(m,'PAGE','P1_restricted','accuracy'))} (n={g(m,'PAGE','P1_restricted','lines')})"),
        row("Key text lines LiteParse put in no block", "nob", lambda m: pc(g(m, 'PAGE', 'lines_in_no_block', 'share'))),
        row("P2 grouping, same-piece F1", "P2", lambda m: pc(g(m, 'PAGE', 'P2', 'f1'))),
        row("P2 grouping F1, tables left out", "P2nt", lambda m: pc(g(m, 'PAGE', 'P2_no_tables', 'f1'))),
        row("P3 order, one column (pairs)", "P3one", lambda m: f"{pc(g(m,'PAGE','P3','one','share'))} (n={g(m,'PAGE','P3','one','pairs')})"),
        row("P3 order, two columns (pairs)", "P3two", lambda m: f"{pc(g(m,'PAGE','P3','two','share'))} (n={g(m,'PAGE','P3','two','pairs')})"),
        row("P3 order, mixed pages", "P3mixed", lambda m: f"{pc(g(m,'PAGE','P3','mixed','share'))} (n={g(m,'PAGE','P3','mixed','pairs')})"),
        row("P3 order, first pages, body pieces", "P3first", lambda m: f"{pc(g(m,'PAGE','P3','first_body','share'))} (n={g(m,'PAGE','P3','first_body','pairs')})"),
        row("P7 tables found (n=43)", "P7found", lambda m: f"{pc(g(m,'TAB','P7.found','share'))} (+{g(m,'TAB','P7.found','pred_extra')} extra)"),
        row("P7 shape, rows x columns (of found)", "P7shape", lambda m: f"{pc(g(m,'TAB','P7.shape','share'))} (n={g(m,'TAB','P7.shape','n')})"),
        row("P7 header rows (of found)", "P7hdr", lambda m: pc(g(m, 'TAB', 'P7.header_rows', 'share'))),
        row("P7 cells (a) exact (n cells compared)", "P7a", lambda m: f"{pc(g(m,'TAB','P7.cells','exact'))} (n={g(m,'TAB','P7.cells','n')})"),
        row("P7 cells (b) folded", "P7b", lambda m: pc(g(m, 'TAB', 'P7.cells', 'folded'))),
        row("P9 reference boundaries, list items (n=517)", "P9", lambda m: f"{pc(g(m,'REFS','P9.boundaries','share'))} ({g(m,'REFS','P9.boundaries','pred_refs')} items)"),
        row("P9 boundaries, list items + paragraphs", "P9p", lambda m: f"{pc(g(m,'REFS_para','P9.boundaries','share'))} ({g(m,'REFS_para','P9.boundaries','pred_refs')} pieces)"),
    ]
    def r1(m, mode, which="as_returned"):
        x = R[m][which][mode]
        return f"{pc(x['letter_error'])} / {pc(x['word_error'])}"
    rows.append(row(f"R1 letters / words wrong, exact, as returned ({R['with_truth']} lines)", "R1e", lambda m: r1(m, "exact")))
    rows.append(row("R1 letters / words wrong, folded, punctuation ignored, as returned", "R1f", lambda m: r1(m, "folded_no_punct")))
    rows.append(row("R1 same, LiteParse's pieces put right to left by us", "R1f", lambda m: r1(m, "folded_no_punct", "items_reordered_right_to_left")))
    head = ("| Measure | " + " | ".join(MODE_NAME[m] for m in M) + " | Baseline v1 (Azure + Gemini) | Key A vs key B | Pass mark |\n"
            "|---|" + "---|" * (len(M) + 3))
    L = [f"# Experiment 99 — LiteParse 2.21.1 on the extraction exam\n\nScored {sc['made']} against experiment 97's final keys "
         "(212 PAGE files, 37 TAB, 38 REFS) with experiment 97's own comparison functions; reading on the exam's "
         f"{R['lines']} three-witness lines ({R['with_truth']} with a settled or all-agree truth).\n", head] + rows
    L.append(f"\nWitnesses through this script's direct count (calibration of the R1 count against score97's estimate): "
             f"Azure {pc(R['witness_azure']['exact']['letter_error'])} / {pc(R['witness_azure']['exact']['word_error'])} exact, "
             f"{pc(R['witness_azure']['folded_no_punct']['letter_error'])} / {pc(R['witness_azure']['folded_no_punct']['word_error'])} folded no punct.; "
             f"t91 {pc(R['witness_t91']['exact']['letter_error'])} / {pc(R['witness_t91']['exact']['word_error'])}, "
             f"{pc(R['witness_t91']['folded_no_punct']['letter_error'])} / {pc(R['witness_t91']['folded_no_punct']['word_error'])}.\n")
    L.append("## Q3 right-to-left order (Arabic lines, folded, punctuation ignored)\n\n| Mode | Arabic lines | equal as returned | "
             "words all right but in the wrong order (of lines with all words right) | equal only after reversing words | "
             "only after reversing characters | lines of 2+ pieces: pieces left to right / right to left / mixed |\n|---|---|---|---|---|---|---|")
    for m in M:
        o = R[m]["order"]
        dct = R[m].get("arabic_lines_with_2plus_items_direction") or {}
        L.append(f"| {MODE_NAME[m]} | {o.get('arabic_lines')} | {pc(o.get('share_equal_as_returned'))} | "
                 f"{o.get('same_words_in_wrong_order', 0)} of {o.get('same_words_as_truth', 0)} "
                 f"({pc(o.get('share_wrong_order_among_lines_with_right_words'))}) | {o.get('equal_only_word_order_reversed', 0)} | "
                 f"{o.get('equal_only_characters_reversed', 0)} | {dct.get('left_to_right (visual)', 0)} / "
                 f"{dct.get('right_to_left (reading)', 0)} / {dct.get('mixed', 0)} |")
    L.append("\n## Q4 cost (this box, nice 19, 4 workers, one process per mode over the 214 exam pages)\n\n"
             "| Mode | pages | seconds in parse | pages / second | peak memory (MB, whole process) | CPU % |\n|---|---|---|---|---|---|")
    for m in M:
        c = sc["cost"][m]
        L.append(f"| {MODE_NAME[m]} | {c.get('pages')} | {c.get('seconds_in_parse')} | {c.get('pages_per_second')} | "
                 f"{c.get('peak_rss_mb')} | {c.get('cpu_percent')} |")
    L.append("\n## P1 per key role (lines; share right)\n")
    roles = sorted({r for m in M for r in g(m, "PAGE", "P1", "per_role") or {}},
                   key=lambda r: -(g(M[0], "PAGE", "P1", "per_role", r, "n") or 0))
    L.append("| Key role | n | " + " | ".join(MODE_NAME[m] for m in M) + " |\n|---|---|" + "---|" * len(M))
    for r in roles:
        L.append(f"| {r}{' (LiteParse has no name for it)' if r not in V.EXPRESSIBLE and r != 'author block (byline + affiliation)' else ''} | "
                 f"{g(M[0],'PAGE','P1','per_role',r,'n')} | " + " | ".join(pc(g(m, 'PAGE', 'P1', 'per_role', r, 'accuracy')) for m in M) + " |")
    L.append("\n## P1 confusion, text layer (key role -> LiteParse role, wrong lines, top 15)\n")
    L.append("| Key -> LiteParse | " + " | ".join(MODE_NAME[m] for m in M) + " |\n|---|" + "---|" * len(M))
    conf = C.Counter()
    for m in M:
        for k, v in (g(m, "PAGE", "P1", "confusion") or {}).items():
            conf[k] += v
    for k, _ in conf.most_common(15):
        L.append(f"| {k} | " + " | ".join(str((g(m, 'PAGE', 'P1', 'confusion') or {}).get(k, 0)) for m in M) + " |")
    L.append("\n## Role mapping (LiteParse block kind -> key role)\n\n| LiteParse | Key role |\n|---|---|")
    for k, v in V.KIND_TO_KEY.items():
        L.append(f"| `{k}` | {v} |")
    L.append("| words in no block, or no LiteParse word on the line | (no-block) |")
    L.append("\nNetwork: connect() calls to AF_INET/AF_INET6 seen by strace per run: " +
             ", ".join(f"{k} {v['n_network']}" for k, v in sc["network"].items()) + ".\n")
    L.append("Files: every miss `misses_<mode>_<PART>.jsonl` (PAGE, TAB, REFS, REFS_para); line readings `r1_lines_<mode>.jsonl`.")
    open(f"{OUT}/liteparse_scorecard.md", "w").write("\n".join(L) + "\n")


if __name__ == "__main__":
    if sys.argv[1:2] == ["--md"]:
        write_md(json.load(open(f"{OUT}/liteparse_scorecard.json")))
    else:
        main()
