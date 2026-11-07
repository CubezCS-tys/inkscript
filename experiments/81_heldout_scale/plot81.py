"""Experiment 81: the reader-by-era chart (estimated letter error with 95% intervals), strict and folded, plus the
2000+ explanation (journal 0097's running header) -> out/look/readers_by_era.png

    out/venv/bin/python plot81.py
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image  # noqa: E402

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
NAMES = [("azure", "Azure"), ("argon", "Azure + Argon fixes"), ("v1", "ours: v1 (exp 77)"),
         ("v2b", "ours: v2b, + old print (exp 77)"), ("s2r", "ours: synthetic then real (exp 78)"),
         ("v3", "ours: v3, 4.8x lines (exp 83)"), ("fsig4", "ours: v1 + signal reader p4r"),
         ("f78", "ours: v1 + exp 78 (two image readers)"), ("nuqta", "Nuqta-Arabic-OCR-4B")]
BLUE, ORANGE, GREY, INK, MUTED, GRID, SURF = "#2a78d6", "#eb6834", "#8a8984", "#0b0b0b", "#52514e", "#e4e3df", "#fcfcfb"
ERAS = [("all", "All held-out lines"), ("2000+", "2000+"), ("1950-1999", "1950–1999"), ("pre-1950", "Before 1950")]


def get(est, era, k):
    if k in est.get("two_phase", {}):
        return est["two_phase"][k][era]
    R = est["all"] if era == "all" else est["by_era"][era]
    return R.get(k)


def main():
    strict = json.loads((OUT / "est81.json").read_text())
    folded = json.loads((OUT / "est81_folded.json").read_text())
    agree = json.loads((OUT / "agree81.json").read_text())
    names = [(k, l) for k, l in NAMES if get(strict, "all", k)]
    fig = plt.figure(figsize=(16, 12.4), facecolor=SURF)
    gs = fig.add_gridspec(3, 4, height_ratios=[1, 1, 0.62], hspace=0.42, wspace=0.08)
    for row, (est, title) in enumerate(((strict, "Every letter counts: hamza, dotted or dotless ya, ta marbuta and vowel marks as printed"),
                                        (folded, "Spelling conventions folded: hamza forms, dotted or dotless ya, ta marbuta, vowel marks ignored"))):
        xmax = max(get(est, e, k)["letters_ci"][1] for e, _ in ERAS for k, _ in names) * 1.12
        for col, (era, et) in enumerate(ERAS):
            ax = fig.add_subplot(gs[row, col])
            ax.set_facecolor(SURF)
            for j, (k, lab) in enumerate(names):
                y = len(names) - 1 - j
                v = get(est, era, k)
                c = BLUE if k in ("azure", "argon") else GREY if k == "nuqta" else ORANGE
                lo, hi = v["letters_ci"]
                ax.plot([lo, hi], [y, y], color=c, lw=2, solid_capstyle="round")
                ax.plot([v["letters"]], [y], "o", ms=7, color=c, mec=SURF, mew=1.5)
                ax.text(hi + 0.012 * xmax, y, f"{v['letters']:.2f}", va="center", fontsize=8, color=INK)
            ax.axvline(get(est, era, "azure")["letters"], color=BLUE, lw=1, ls=(0, (3, 3)), alpha=0.7)
            ax.set_xlim(0, xmax)
            n = agree["all"]["lines"] if era == "all" else agree["by_era"][era]["lines"]
            ax.set_title(f"{et}  ({n:,} lines)", fontsize=10, color=INK, loc="left")
            ax.grid(axis="x", color=GRID, lw=0.8)
            ax.set_axisbelow(True)
            for s in ("top", "right", "left"):
                ax.spines[s].set_visible(False)
            ax.spines["bottom"].set_color(GRID)
            ax.tick_params(colors=MUTED, labelsize=8, length=0)
            ax.set_yticks(range(len(names)))
            ax.set_yticklabels([l for _, l in names][::-1] if col == 0 else [], fontsize=8.5, color=INK)
            if row == 1:
                ax.set_xlabel("letters wrong, %  (punctuation ignored)", fontsize=8.5, color=MUTED)
            if col == 0:
                ax.text(0, 1.2, title, transform=ax.transAxes, fontsize=10.5, color=INK, weight="bold")
    # the 2000+ explanation: journal 0097's running header
    d = json.loads((OUT / "diag81_v1.json").read_text())
    hb = d["buckets"]["header"]
    hk = [k for k in hb if k != "other"][0]
    ax = fig.add_subplot(gs[2, :])
    ax.axis("off")
    key = d["worst20"][0]["key"]
    im = Image.open(OUT / "judge/crops" / f"{key}.png").convert("RGB")
    axi = ax.inset_axes([0.0, 0.42, 0.33, 0.5])
    axi.imshow(im)
    axi.axis("off")
    txt = (f"Why ours loses letters on 2000+ print: one running header. Journal 0097 prints its title in a white display face\n"
           f"on a dark band (left) on every page. It is {hb[hk]['share_of_lines']}% of 2000+ lines but\n"
           f"{hb[hk]['share_of_excess']:.0f}% of our extra letter errors there (v1 garbles it: {hb[hk]['letters_ours']:.0f}% of its letters "
           f"wrong\nvs Azure {hb[hk]['letters_azure']:.0f}%). Without it, on 2000+ lines: v1 {hb['other']['letters_ours']:.2f}% vs Azure "
           f"{hb['other']['letters_azure']:.2f}% letters,\nand v1 has fewer wrong lines ({hb['other']['lines_ours']:.1f}% vs "
           f"{hb['other']['lines_azure']:.1f}%).")
    ax.text(0.35, 0.92, txt, transform=ax.transAxes, fontsize=9.5, color=INK, va="top", wrap=True)
    ax.text(0.0, 0.18, "How it was measured: 26 journals no reader trained on; a line counts as right where every reader agrees "
            "(less the judged share of such lines that is wrong);\ndisputed lines (2,294 judged of 3,870) and 473 agreed lines "
            "were read blind by Gemini Flash, which then picked the matching reading. Bars: 95% page bootstrap.\nThe judge is "
            "harsher on Azure than the owner's own corrected lines are (folded: 43 vs 30 of 200 lines), and the owner's lines were drafted from Azure: "
            "Azure's true error lies between the two.", transform=ax.transAxes, fontsize=8.5, color=MUTED, va="top")
    fig.suptitle("Experiment 81, held-out journals, no human correction: estimated letters wrong per reader (dot) with "
                 "95% interval (bar); dashed line = Azure", fontsize=12, color=INK, x=0.01, ha="left", y=0.985)
    (OUT / "look").mkdir(exist_ok=True)
    fig.savefig(OUT / "look/readers_by_era.png", dpi=110, facecolor=SURF, bbox_inches="tight")
    print(OUT / "look/readers_by_era.png")


if __name__ == "__main__":
    main()
