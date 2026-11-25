#!/usr/bin/env python3
"""Experiment 101: the comparison table and the derived "what the fine-tune bought" table, from the arms' scorecards
(out/scores/<arm>/scorecard101.json, all made by score101.py; OCRia-1 = experiment 100's outputs rescored, identical to
its scorecard100.json).  Standard library only.  Writes out/scores/compare101.md and .json.

    nice -n 19 python3 compare101.py

Azure and t91 reading columns are the witnesses counted through the same scorer on the same 584 lines; the Azure +
Gemini pipeline column (structure) is experiment 97's baseline v1 as experiment 100's README quotes it.
"""
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
SC = f"{HERE}/out/scores"
ARMS = [("Qwen3.5-4B plain", "4B"), ("4B, read leniently", "4B_lenient"), ("Qwen3.5-9B plain", "9B"),
        ("9B, read leniently", "9B_lenient"), ("OCRia-1", "ocria1_rescored")]
# baseline v1 (Azure + Gemini), experiment 97 scorecard via experiment 100's README
PIPE = {"P1": 0.957, "noblock": 0.001, "P2": 0.996, "P3one": 0.991, "P3two": 1.0, "found": 1.0, "shape": 1.0,
        "hdr": 0.93, "cells_exact": 0.901, "cells_folded": 0.985, "P9": 0.992, "missing": 0.0}


def g(d, *ks):
    for k in ks:
        d = d.get(k) if isinstance(d, dict) else None
    return d


def measures(s):
    R, Q2, Q5, st = s["R1"], s["Q2"], s.get("Q5") or {}, s["structure"]
    A = R["arabic"]
    m = {}
    m["R1 letters wrong, exact"] = (R["model"]["exact"]["letter_error"], "low")
    m["R1 words wrong, exact"] = (R["model"]["exact"]["word_error"], "low")
    m["R1 letters wrong, folded no punct."] = (R["model"]["folded_no_punct"]["letter_error"], "low")
    m["R1 words wrong, folded no punct."] = (R["model"]["folded_no_punct"]["word_error"], "low")
    m["R1 letters wrong, found lines only"] = (R["model_found_lines_only"]["folded_no_punct"]["letter_error"], "low")
    m["R1 lines not found (of 584)"] = (R["omitted"]["n"], "low")
    m["Arabic-Indic digits kept as printed"] = (A["of_them_output_arabic_indic"] / max(1, A["arabic_indic_digits_in_truth"]), "high")
    m["lines switched wholly to Western digits"] = (A.get("lines_output_switched_to_western", 0), "low")
    m["hamza / alif / ya substitutions"] = (A["hamza_alif_ya_substitutions_total"], "low")
    m["ى printed -> ي written"] = ((A.get("hamza_alif_ya_substitutions") or {}).get("ى printed -> ي", 0), "low")
    m["tashkeel marks written / printed (108)"] = (A["tashkeel_in_output"], "info")
    m["number pairs reversed"] = (A.get("number_pairs_reversed", 0), "low")
    m["number pairs kept (of found)"] = (f"{A.get('number_pairs_kept', 0)} of {A.get('number_pairs_in_truth', 0)}", "info")
    m["printed text missing"] = (Q2["missing_share_of_printed"], "low")
    m["output matching nothing on the page"] = (Q2["invented_share_of_output"], "low")
    m["same, pages without loops"] = (Q2.get("invented_share_pages_without_loops"), "low")
    m["pages looping / cut by the limit"] = (f"{Q2['pages_with_loops']} / {Q2['pages_cut_short']}", "info")
    m["P7 tables found"] = (g(st, "TAB", "P7.found", "share"), "high")
    m["P7 shape"] = (g(st, "TAB", "P7.shape", "share"), "high")
    m["P7 header rows"] = (g(st, "TAB", "P7.header_rows", "share"), "high")
    m["P7 cells exact"] = (g(st, "TAB", "P7.cells", "exact"), "high")
    m["P7 cells folded"] = (g(st, "TAB", "P7.cells", "folded"), "high")
    m["P7 cells misplaced"] = (g(st, "TAB", "P7.cells", "misplaced"), "low")
    m["P7 cells different text"] = (g(st, "TAB", "P7.cells", "different_text"), "low")
    m["P1 label per line, all roles"] = (g(st, "PAGE", "P1", "accuracy"), "high")
    m["P1, roles Markdown can name"] = (g(st, "PAGE", "P1_restricted", "accuracy"), "high")
    m["key text lines in no block"] = (g(st, "PAGE", "lines_in_no_block", "share"), "low")
    m["P2 grouping F1"] = (g(st, "PAGE", "P2", "f1"), "high")
    m["P3 order, one column"] = (g(st, "PAGE", "P3", "one", "share"), "high")
    m["P3 order, two columns"] = (g(st, "PAGE", "P3", "two", "share"), "high")
    m["headings found"] = (g(st, "PAGE", "Q4", "headings_found"), "high")
    m["headings invented"] = (g(st, "PAGE", "Q4", "headings_invented"), "low")
    m["running heads tagged as furniture"] = (g(st, "PAGE", "Q4", "running_head_as_furniture"), "high")
    m["page numbers tagged as furniture"] = (g(st, "PAGE", "Q4", "page_number_as_furniture"), "high")
    m["P9 reference boundaries"] = (g(st, "REFS", "P9.boundaries", "share"), "high")
    m["output tokens per page, median"] = (g(Q5, "output_tokens", "median"), "info")
    m["output tokens per page, p90"] = (g(Q5, "output_tokens", "p90"), "info")
    m["pages per minute (16 in flight)"] = (Q5.get("pages_per_minute"), "high")
    m["$ per 1,000 pages"] = (Q5.get("usd_per_1000_pages"), "low")
    return m


def fmt(x, name):
    if x is None:
        return "–"
    if isinstance(x, str):
        return x
    if isinstance(x, float) and x <= 1.0 and not name.startswith(("$", "output tokens", "pages per")):
        return f"{100 * x:.1f}%"
    if isinstance(x, float):
        return f"{x:.2f}" if name.startswith("$") else f"{x:.0f}"
    return str(x)


def witness(s):
    R = s["R1"]
    out = {}
    for w in ("azure", "t91"):
        W, A = R[f"witness_{w}"], R[f"arabic_witness_{w}"]
        out[w] = {"R1 letters wrong, exact": W["exact"]["letter_error"], "R1 words wrong, exact": W["exact"]["word_error"],
                  "R1 letters wrong, folded no punct.": W["folded_no_punct"]["letter_error"],
                  "R1 words wrong, folded no punct.": W["folded_no_punct"]["word_error"],
                  "Arabic-Indic digits kept as printed": A["of_them_output_arabic_indic"] / max(1, A["arabic_indic_digits_in_truth"]),
                  "lines switched wholly to Western digits": A.get("lines_output_switched_to_western", 0),
                  "hamza / alif / ya substitutions": A["hamza_alif_ya_substitutions_total"],
                  "ى printed -> ي written": (A.get("hamza_alif_ya_substitutions") or {}).get("ى printed -> ي", 0),
                  "tashkeel marks written / printed (108)": A["tashkeel_in_output"],
                  "number pairs reversed": A.get("number_pairs_reversed", 0),
                  "number pairs kept (of found)": f"{A.get('number_pairs_kept', 0)} of {A.get('number_pairs_in_truth', 0)}"}
    return out


PIPE_ROW = {"printed text missing": PIPE["missing"], "P7 tables found": PIPE["found"], "P7 shape": PIPE["shape"],
            "P7 header rows": PIPE["hdr"], "P7 cells exact": PIPE["cells_exact"], "P7 cells folded": PIPE["cells_folded"],
            "P1 label per line, all roles": PIPE["P1"], "key text lines in no block": PIPE["noblock"],
            "P2 grouping F1": PIPE["P2"], "P3 order, one column": PIPE["P3one"], "P3 order, two columns": PIPE["P3two"],
            "P9 reference boundaries": PIPE["P9"]}


def main():
    arms = [(lab, json.load(open(f"{SC}/{d}/scorecard101.json"))) for lab, d in ARMS
            if os.path.exists(f"{SC}/{d}/scorecard101.json")]
    M = {lab: measures(s) for lab, s in arms}
    W = witness(dict(arms)["OCRia-1"])
    names = list(next(iter(M.values())).keys())
    labs = [lab for lab, _ in arms]
    L = ["# Experiment 101 — comparison\n", "| Measure | " + " | ".join(labs) + " | Azure (same lines) | t91 (same lines) | Azure + Gemini v1 |",
         "|" + "---|" * (len(labs) + 4)]
    for n in names:
        L.append(f"| {n} | " + " | ".join(fmt(M[l][n][0], n) for l in labs) + f" | {fmt(W['azure'].get(n), n)} | "
                 f"{fmt(W['t91'].get(n), n)} | {fmt(PIPE_ROW.get(n), n)} |")
    # derived: what the fine-tune bought (4B plain -> OCRia-1)
    base = "Qwen3.5-4B plain"
    D = []
    if base in M and "OCRia-1" in M:
        L += ["\n## What the fine-tune bought: plain Qwen3.5-4B -> OCRia-1 (same base, our prompt vs theirs)\n",
              "Plain 4B column: scored to the output contract; where reading its answers leniently (pipe tables as tables; "
              "diagnostic) changes the number, that value is given after the slash (diagnostic).\n",
              "| Measure | plain 4B | OCRia-1 | change | better with the fine-tune? |", "|---|---|---|---|---|"]
        alt = M.get("4B, read leniently", {})
        for n in names:
            a, b = M[base][n][0], M["OCRia-1"][n][0]
            a2 = alt.get(n, (a,))[0]
            sense = M[base][n][1]
            if isinstance(a, (int, float)) and isinstance(b, (int, float)) and a is not None and b is not None:
                pct = isinstance(a, float) and a <= 1 and isinstance(b, float) and b <= 1 and not n.startswith(("$", "output tokens", "pages per"))
                ch = f"{100 * (b - a):+.1f} points" if pct else f"{b - a:+.2f}" if n.startswith("$") else f"{b - a:+.0f}"
                verdict = "–" if sense == "info" or a == b else ("yes" if (b < a) == (sense == "low") else "no")
            else:
                ch, verdict = "–", "–"
            D.append(dict(measure=n, base=a, ocria1=b, change=ch, fine_tune_better=verdict))
            a_txt = fmt(a, n) + (f" / {fmt(a2, n)}" if a2 != a and fmt(a2, n) != fmt(a, n) else "")
            L.append(f"| {n} | {a_txt} | {fmt(b, n)} | {ch} | {verdict} |")
    json.dump(dict(arms={l: {n: v[0] for n, v in M[l].items()} for l in labs}, witnesses=W, pipeline=PIPE_ROW,
                   fine_tune_bought=D), open(f"{SC}/compare101.json", "w"), ensure_ascii=False, indent=1)
    open(f"{SC}/compare101.md", "w").write("\n".join(L) + "\n")
    print("\n".join(L))


if __name__ == "__main__":
    main()
