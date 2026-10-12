"""Experiment 36: the headline tables from out/results.json and out/judge.jsonl -> out/headline.md (and stdout).

    /home/yassine/inkscript/.venv/bin/python headline.py
Rerun after evaluate.py (and judge.py). Intervals: 95% bootstrap over documents.
"""
import json
from collections import defaultdict
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out")
R = json.load(open(OUT / "results.json"))
ORDER = ["azure", "kraken", "dots_mocr", "dots_ocr", "paddle_vl15", "qwen3vl32b_awq", "qwen3vl8b", "amad_vlm6",
         "qwen3vl32b_awq_card", "synth_azure"]


def f(x, pct=False, d=1):
    if x is None:
        return "—"
    return f"{100 * x:.{d}f}" if pct else f"{x:.{d}f}"


def ci(st, k, pct=False, d=1):
    v = st.get(k)
    c = st.get("ci95", {}).get(k)
    if v is None:
        return "—"
    return f(v, pct, d) + (f" [{f(c[0], pct, d)}–{f(c[1], pct, d)}]" if c else "")


def table(sset):
    res = R["results"].get(sset, {})
    rows = []
    hdr = ["reader", "pages", "CER %", "folded CER %", "marks P/R %", "invented /1k w (non-table)",
           "invented /1k w (table pages)", "dropped /1k w", "repeated /1k w", "pages inv/drop/rep/runaway/empty %", "CER % on its healthy pages (n)",
           "Kraken flags its inventions R/P %", "Kraken flags its drops R / run P %", "word order, multi-col %",
           "TEDS idx/box", "eq sim idx/box"]
    for rd in sorted(res, key=lambda r: ORDER.index(r) if r in ORDER else 99):
        a, nt, tb, mc, hl = (res[rd].get(k, {}) for k in ("all", "non_table", "table", "multicolumn", "healthy"))
        rows.append([rd, str(a["pages"]), ci(a, "faithful.cer", True), ci(a, "folded.cer", True),
                     f"{f(a.get('mark_precision'), True, 0)}/{f(a.get('mark_recall'), True, 0)}",
                     ci(nt, "invented_per_1000w"), f(tb.get("invented_per_1000w")) if tb else "—",
                     ci(a, "dropped_per_1000w"), ci(a, "repeated_per_1000w"),
                     "/".join(f(a.get(k), True, 0) for k in ("pages_inventing", "pages_dropping", "pages_repeating",
                                                              "pages_runaway", "pages_empty")),
                     f"{ci(hl, 'faithful.cer', True)} ({hl.get('pages', 0)})",
                     f"{f(a.get('checker_recall'), True, 0)}/{f(a.get('checker_precision'), True, 0)}",
                     f"{f(a.get('checker_drop_recall'), True, 0)}/{f(a.get('checker_drop_run_precision'), True, 0)}",
                     ci(mc, "word_order", True) if mc else "—",
                     f"{f(a.get('teds'), False, 2)}/{f(a.get('teds_box'), False, 2)} (n {a.get('tables_scored', 0)})",
                     f"{f(a.get('eq_sim'), False, 2)}/{f(a.get('eq_sim_box'), False, 2)} (n {a.get('equations_scored', 0)})"])
    return hdr, rows


def md(hdr, rows):
    out = ["| " + " | ".join(hdr) + " |", "|" + "---|" * len(hdr)]
    out += ["| " + " | ".join(r) + " |" for r in rows]
    return "\n".join(out)


def judge():
    f_ = OUT / "judge.jsonl"
    if not f_.exists():
        return ""
    g = defaultdict(lambda: defaultdict(list))
    for l in f_.read_text(encoding="utf-8").splitlines():
        r = json.loads(l)
        for rd, v in (r.get("verdicts") or {}).items():
            rd = r["labels"].get(rd.replace("Candidate", "").strip(), rd)     # one answer said "Candidate A"
            g[(r["kind"], rd)]["grade"].append(v.get("grade", 1))
            g[(r["kind"], rd)]["struct"].append(bool(v.get("structure_ok")))
            g[(r["kind"], rd)]["missing"].append(bool(v.get("missing")))
            g[(r["kind"], rd)]["five"].append(v.get("grade") == 5)
    hdr = ["object", "reader", "n", "mean grade 1-5", "structure right %", "exact (5) %", "gave none %"]
    rows = []
    for (k, rd), v in sorted(g.items()):
        n = len(v["grade"])
        rows.append([k, rd, str(n), f"{sum(v['grade']) / n:.2f}", f"{100 * sum(v['struct']) / n:.0f}",
                     f"{100 * sum(v['five']) / n:.0f}", f"{100 * sum(v['missing']) / n:.0f}"])
    spend = sum(json.loads(l)["usd"] for l in (OUT / "gemini_spend.jsonl").read_text().splitlines() if l.strip())
    return md(hdr, rows) + f"\n\nGemini judge (gemini-3.1-pro-preview), spent ${spend:.2f} in total."


def speed():
    s = R.get("speed", {}).get("models", {})
    hdr = ["model", "pages/h (RTX 5090)", "$ / 1,000 pages", "hit the token cap (pages)", "concurrency"]
    rows = [[k, f(v.get("pages_per_hour"), False, 0), f(v.get("usd_per_1000_pages"), False, 2), str(v.get("hit_cap")),
             str(v.get("concurrency"))] for k, v in s.items()]
    return md(hdr, rows)


if __name__ == "__main__":
    parts = [f"# Experiment 36 headline ({', '.join(f'{k} {v} pages' for k, v in R['sets'].items())})\n"]
    for s in ("gold", "bd", "ys_azure"):
        parts.append(f"## {s}: {R['labels'][s]}\n")
        parts.append(md(*table(s)) + "\n")
    parts.append("## Tables and equations, Gemini judge\n\n" + judge() + "\n")
    parts.append("## Speed and cost\n\n" + speed() + "\n")
    text = "\n".join(parts)
    (OUT / "headline.md").write_text(text, encoding="utf-8")
    print(text)
