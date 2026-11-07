"""Experiment 82: the shape-metric chart.  One panel per measure, damage level along x, one bar per rebuilder.

    python chart82.py out/shape_modern [out/shape_modern_learned ...] --title "..." --out out/chart_modern.png
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
COL = {"skeleton": "#2a78d6", "mcr": "#eb6834", "hybrid": "#1baf7a", "hybrid_r": "#eda100", "learned": "#e87ba4"}
NAME = {"skeleton": "skeleton (exp 79 today)", "mcr": "MCR runs", "hybrid": "hybrid (whole heavy pieces)",
        "hybrid_r": "hybrid (blob regions)", "learned": "learned network"}
LEVELS = ["clean", "mild", "heavy", "spread", "fill"]
PANELS = [("shape_ok", "letters drawn in the right place\n(within 1.5 stroke widths everywhere)"),
          ("loop_ok", "loops travelled round as a loop"),
          ("dir_ok", "path moving the right way"),
          ("junc_ok", "junctions with the right branches")]


def load(dirs):
    S = {}
    for d in dirs:
        rows = [json.loads(l) for l in open(Path(d) / "rows.jsonl", encoding="utf-8")]
        import metric82 as MM
        for r in rows:
            S.setdefault((r["level"], r["method"]), []).append(r)
        S = {k: v for k, v in S.items()}
    return {k: MM.summarise(v) for k, v in S.items()}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dirs", nargs="+")
    ap.add_argument("--title", default="")
    ap.add_argument("--out", required=True)
    a = ap.parse_args()
    S = load(a.dirs)
    methods = [m for m in COL if any(k[1] == m for k in S)]
    levels = [l for l in LEVELS if any(k[0] == l for k in S)]
    fig, axs = plt.subplots(1, 4, figsize=(17, 4.6), sharey=True)
    w = 0.8 / len(methods)
    for ax, (key, title) in zip(axs, PANELS):
        for j, m in enumerate(methods):
            xs, ys = [], []
            for i, lv in enumerate(levels):
                v = S.get((lv, m), {}).get(key)
                if v is not None:
                    xs.append(i - 0.4 + w * (j + 0.5))
                    ys.append(100 * v)
            ax.bar(xs, ys, w * 0.88, color=COL[m], label=NAME[m])
        ax.set_title(title, fontsize=10.5)
        ax.set_xticks(range(len(levels)), levels)
        ax.set_ylim(0, 100)
        ax.grid(axis="y", color="#e6e6e6", lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axs[0].set_ylabel("% right")
    n = next(iter(S.values()))["lines"]
    fig.suptitle(a.title or f"Pen-path shape against the true path ({n} lines a level, letters known)", fontsize=13)
    axs[-1].legend(loc="upper right", fontsize=8.5, frameon=False)
    fig.tight_layout()
    fig.savefig(a.out, dpi=110)
    with open(Path(a.out).with_suffix(".json"), "w", encoding="utf-8") as f:
        json.dump({f"{k[0]}/{k[1]}": v for k, v in sorted(S.items())}, f, indent=1)
    print(a.out)


if __name__ == "__main__":
    main()
