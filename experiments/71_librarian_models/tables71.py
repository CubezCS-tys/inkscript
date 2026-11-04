"""Experiment 71: the README's tables from out/scores71.json and out/simulate71.json (prints Markdown)."""
from __future__ import annotations

import json
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
SC = json.load(open(OUT / "scores71.json"))
SI = json.load(open(OUT / "simulate71.json"))
G = [json.loads(l) for l in open(OUT / "gold71.jsonl")]
MAIN = ["gemini-3.8-flash", "gemini-3.8-flash@high", "gemini-4-argon", "claude-sonnet-5-5", "claude-opus-5-5"]
NAME = {"gemini-3.8-flash": "Flash 3.8 (think low)", "gemini-3.8-flash@high": "Flash 3.8 (think high)",
        "gemini-4-argon": "Argon (think low)", "claude-sonnet-5-5": "Sonnet 5.5", "claude-opus-5-5": "Opus 5.5"}
pct = lambda x: "–" if x is None else f"{100 * x:.1f}%"  # noqa: E731


def gold_table():
    c = Counter((g["domain"], g["kind"]) for g in G)
    print("| domain | decision kind (librarian's) | items |\n|---|---|---|")
    for (d, k), n in sorted(c.items()):
        print(f"| {d} | {k} | {n} |")
    print(f"| | **total** | **{len(G)}** |\n")


def headline():
    print("| model | decided / 522 | precision | weighted | lenient | coverage | says high | precision at high | "
          "Batch $ / 1,000 | in / out tokens |\n|---|---|---|---|---|---|---|---|---|---|")
    for m in MAIN:
        s = SC["models"][m]
        c = s["cost"]
        print(f"| {NAME[m]} | {s['decided']} | {pct(s['precision'])} | {pct(s['w_precision'])} | "
              f"{pct(s['lenient_precision'])} | {pct(s['coverage'])} | {s['high']['n']} | {pct(s['high']['precision'])} | "
              f"${c['usd_per_1000']:.2f} | {c['tokens_in_mean']} / {c['tokens_out_mean']} |")
    print()


def kinds(key="by_answer"):
    allk = sorted({k for m in MAIN for k in SC["models"][m][key]} - {"w:unsure", "i:unsure"})
    print("| answer kind | " + " | ".join(NAME[m] for m in MAIN) + " |\n|---|" + "---|" * len(MAIN))
    for k in allk:
        cells = []
        for m in MAIN:
            t = SC["models"][m][key].get(k)
            if not t or not t["decided"]:
                cells.append("")
                continue
            mark = " **✓**" if t["decided"] >= 10 and t["precision"] >= 0.98 else ""
            cells.append(f"{t['correct']}/{t['decided']} {pct(t['precision'])}{mark}")
        print(f"| {k} | " + " | ".join(cells) + " |")
    print()


def by_basis():
    print("| model | works rule | works judgement | institutions rule | institutions judgement |\n|---|---|---|---|---|")
    for m in MAIN:
        b = SC["models"][m]["by_basis"]
        cell = lambda k: f"{b[k]['correct']}/{b[k]['decided']} {pct(b[k]['precision'])}"  # noqa: E731
        print(f"| {NAME[m]} | {cell('works:rule')} | {cell('works:judgement')} | {cell('institutions:rule')} | "
              f"{cell('institutions:judgement')} |")
    print()


def cross():
    print("| pair | both decided | agree | precision when they agree | disagree: A right / B right | A's errors the "
          "pair flags |\n|---|---|---|---|---|---|")
    for k, v in SC["cross"].items():
        a, b = k.split(" | ")
        if a not in MAIN or b not in MAIN:
            continue
        print(f"| {NAME[a]} + {NAME[b]} | {v['both_decided']} | {v['agree']} | {pct(v['agree_precision'])} | "
              f"{v['a_right']} / {v['b_right']} | {v['errors_of_a_caught']} of {v['errors_of_a']} |")
    print()


def designs(scope):
    D = SI["designs"]
    print("| design | applied | precision (Wilson lo) | lenient | weighted | to human | $ / 1,000 |\n"
          "|---|---|---|---|---|---|---|")
    for d, v in D[f"{scope}|both"].items():
        print(f"| {d} | {v['applied']}/{v['n']} | {pct(v['precision'])} ({pct(v['wilson_lo'])}) | {pct(v['lenient'])} | "
              f"{pct(v['w_precision'])} | {pct(v['human_share'])} | ${v['usd_per_1000']:.2f} |")
    print()


def per_domain(scope, ds):
    D = SI["designs"]
    print("| design | works: applied, precision | institutions: applied, precision |\n|---|---|---|")
    for d in ds:
        w, i = D[f"{scope}|works"][d], D[f"{scope}|institutions"][d]
        print(f"| {d} | {w['applied']}/{w['n']}, {pct(w['precision'])} (lenient {pct(w['lenient'])}) | "
              f"{i['applied']}/{i['n']}, {pct(i['precision'])} |")
    print()


def scale(ds):
    print("| scale | questions to the model (works; institutions) | " + " | ".join(ds) + " |\n|---|---|" + "---|" * len(ds))
    for name, r in SI["scale"].items():
        q = f"{r['works_questions'][0]:,}–{r['works_questions'][1]:,}; {r['institution_questions']:,}"
        cells = []
        for d in ds:
            u, h = r["designs"][d]["usd"], r["designs"][d]["to_human"]
            cells.append(f"${u[0]:,.0f}–{u[1]:,.0f}; {h[0]:,}–{h[1]:,} to a human")
        print(f"| {name} | {q} | " + " | ".join(cells) + " |")
    print()


if __name__ == "__main__":
    print("## gold\n"); gold_table()
    print("## headline\n"); headline()
    print("## by answer kind\n"); kinds()
    print("## by answer kind, high confidence only\n"); kinds("by_answer_high")
    print("## by basis\n"); by_basis()
    print("## cross\n"); cross()
    print("## designs judgement\n"); designs("judgement")
    print("## designs all\n"); designs("all")
    pick = ["Flash (any)", "Opus, high only", "Sonnet high -> Opus high", "Flash + Sonnet agree (Sonnet high)",
            "Flash + Sonnet agree -> Opus high", "Flash + Sonnet agree (Sonnet high) -> Opus high"]
    print("## per domain judgement\n"); per_domain("judgement", pick)
    print("## per domain judgement, kind-gated\n"); per_domain("judgement", [d for d in SI["designs"]["all|both"] if d.startswith("Flash strong")])
    print("## scale\n"); scale(["Flash (any)", "Opus, high only", "Flash strong kinds -> Opus high",
                                "Flash strong kinds -> Flash + Sonnet agree (Sonnet high) -> Opus high"])
