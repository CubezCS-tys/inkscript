"""Experiment 90: the verdict picture -> out/look/verdict90.png

    ../81_heldout_scale/out/venv/bin/python fig90.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
BLUE, ORANGE, GREY, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#b5b4ae", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ERAS = [("all", "All"), ("pre-1950", "Before 1950"), ("1950-1979", "1950–79"), ("1980-1999", "1980–99"), ("2000+", "2000+")]
READ = [("azure", "Azure", ORANGE), ("final", "Ours: final reader (v7-28M)", BLUE), ("v3", "Ours: v3 (reference)", GREY)]


def bars(ax, R, title, key="letters"):
    import numpy as np
    x = np.arange(len(ERAS))
    w = 0.26
    for j, (k, lab, col) in enumerate(READ):
        v, lo, hi = [], [], []
        for e, _ in ERAS:
            X = R["all"] if e == "all" else R["by_era"].get(e, {})
            d = X.get(k)
            v.append(d[key] if d else 0)
            ci = d.get(key + "_ci", [d[key], d[key]]) if d else [0, 0]
            lo.append(v[-1] - ci[0])
            hi.append(ci[1] - v[-1])
        ax.bar(x + (j - 1) * w, v, w * 0.92, color=col, label=lab, yerr=[lo, hi], ecolor=MUTED, capsize=2, lw=0)
        for xi, vi in zip(x + (j - 1) * w, v):
            ax.text(xi, vi / 2, f"{vi:.2f}" if key == "letters" else f"{vi:.0f}", ha="center", va="center",
                    fontsize=7.5, color="white", rotation=90)
    ax.set_xticks(x, [l for _, l in ERAS])
    ax.set_title(title, loc="left", fontsize=11, color=INK)
    ax.grid(axis="y", color=GRID)
    ax.set_axisbelow(True)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)


def main():
    R = json.loads((OUT / "est90.json").read_text())
    V = R["verdict"]
    fig, axs = plt.subplots(2, 2, figsize=(16, 10.5), facecolor=SURF)
    bars(axs[0, 0], R["strict"]["masthead_out"], "Letters wrong %, every letter counted (mastheads out)")
    bars(axs[0, 1], R["folded"]["masthead_out"], "Letters wrong %, spellings folded (hamza, ى/ي, ة/ه, marks ignored)".replace("ى/ي, ة/ه", "alef/ya, ta"))
    bars(axs[1, 0], R["strict"]["masthead_out"], "Lines with any error %, every letter counted", key="line")
    axs[0, 0].legend(frameon=False, fontsize=9, loc="upper right")
    ax = axs[1, 1]
    T = V["C2"]["types"]
    names = list(T)
    ys = range(len(names))
    ax.barh(ys, [T[n]["ratio"] for n in names], color=[BLUE if T[n]["ratio"] <= 2 else ORANGE for n in names], height=0.6)
    ax.axvline(1, color=MUTED, lw=1, ls=":")
    ax.axvline(2, color=ORANGE, lw=1.5, ls="--")
    lab = {"title": "display titles", "dark": "light text on dark", "latin": "with Latin letters", "digits": "with digits",
           "rotated": "tilted > 3°"}
    ax.set_yticks(list(ys), [f"{lab.get(n, n)}  (ours {T[n]['final']:.2f}% / Azure {T[n]['azure']:.2f}%)" for n in names])
    for y, n in zip(ys, names):
        ax.text(T[n]["ratio"] + 0.03, y, f"{T[n]['ratio']:.2f}×", va="center", fontsize=9)
    ax.set_title("Line types: our letter errors ÷ Azure's (limit 2×)", loc="left", fontsize=11)
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    c1, c2 = V["C1"], V["C2"]
    o = c1["overall"]
    fp = R["folded"]["masthead_out"]["paired_vs_azure"]["final"]
    txt = (f"LOCKED final test (20 journals never trained on + 280 old documents): "
           f"C1 ours ≥ Azure overall and in every era: {'PASS' if c1['pass_'] else 'FAIL'}   ·   "
           f"C2 no line type > 2× Azure: {'PASS' if c2['pass_'] else 'FAIL'}\n"
           f"Overall letters wrong: ours {o['final_letters']:.2f}% vs Azure {o['azure_letters']:.2f}%; "
           f"lines wrong: ours {o['final_line']:.1f}% vs Azure {o['azure_line']:.1f}%.  Ours minus Azure, letters: "
           + ", ".join(f"{e} {d['letters_diff']:+.2f} ({d['letters_ci'][0]:+.2f} to {d['letters_ci'][1]:+.2f})"
                       for e, d in c1['by_era'].items())
           + f"\nSpellings folded: level overall ({fp['all']['letters_diff']:+.3f}), but 2000+ ours worse "
           f"({fp['2000+']['letters_diff']:+.2f}, CI {fp['2000+']['letters_ci'][0]:+.2f} to {fp['2000+']['letters_ci'][1]:+.2f}); "
           f"titles folded {R['folded']['line_types']['title']['final']['letters'] / R['folded']['line_types']['title']['azure']['letters']:.2f}× Azure. "
           "Error bars per reader are wide because judge errors on agreed lines hit every reader alike; the paired differences are what decide.")
    import textwrap
    txt = "\n".join(w for line in txt.split("\n") for w in textwrap.wrap(line, 175))
    fig.suptitle(txt, x=0.01, ha="left", fontsize=10.5, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.90))
    (OUT / "look").mkdir(exist_ok=True)
    fig.savefig(OUT / "look/verdict90.png", dpi=110, facecolor=SURF)
    print("saved", OUT / "look/verdict90.png")


if __name__ == "__main__":
    main()
