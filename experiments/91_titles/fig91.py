"""Experiment 91: the owner's picture (out/look/fig91.png).

    ../81_heldout_scale/out/venv/bin/python fig91.py

Top left: article titles, letters wrong (every letter counted), Azure / final reader (v7-28M) / new reader (t91), on
the held-out title test and on the locked titles (second read).  Top right: experiment 81's held-out lines, the new
reader minus the final reader per era with 95% intervals (below 0 = better).  Bottom: held-out title crops where the
new reader is right and the final reader was not, with both readings.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402
from PIL import Image, ImageDraw, ImageFont  # noqa: E402

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
INK, MUTED, GRID = "#1f1f1e", "#6b6a63", "#e4e3dc"
COL = {"azure": "#9a998f", "l28": "#2a78d6", "t91": "#eb6834"}
NAME = {"azure": "Azure", "l28": "final reader (v7-28M)", "t91": "new reader (titles)"}
FONT = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
LAT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def charts() -> Image.Image:
    T = json.loads((OUT / "score91_titles.json").read_text())["strict"]["all"]
    L = json.loads((OUT / "score91_locked.json").read_text())["strict"]["all"]
    H = json.loads((OUT / "heldout/est91_strict.json").read_text())["paired_t91"]["t91_minus_l28"]
    fig, ax = plt.subplots(1, 2, figsize=(14, 4.6), gridspec_kw=dict(width_ratios=[1.25, 1]))
    for a in ax:
        a.spines[["top", "right"]].set_visible(False)
        a.spines[["left", "bottom"]].set_color(GRID)
        a.tick_params(colors=MUTED)
        a.yaxis.grid(True, color=GRID, lw=0.8)
        a.set_axisbelow(True)
    a = ax[0]
    groups = [("held-out titles\n(250 lines)", T), ("locked titles, second read\n(672 lines)", L)]
    w = 0.26
    for g, (lab, D) in enumerate(groups):
        for j, n in enumerate(("azure", "l28", "t91")):
            v = D[n]["letters"]
            ci = D[n].get("letters_ci")
            x = g + (j - 1) * (w + 0.02)
            a.bar(x, v, w, color=COL[n], label=NAME[n] if g == 0 else None)
            if ci:
                a.plot([x, x], ci, color=INK, lw=1)
            a.text(x, 0.25, f"{v:.2f}", ha="center", va="bottom", fontsize=10, color="white", fontweight="bold")
    a.set_xticks(range(len(groups)), [g[0] for g in groups], color=INK)
    a.set_ylabel("letters wrong, %", color=MUTED)
    a.set_title("Article titles (every letter counted)", color=INK, loc="left", fontsize=13)
    a.legend(frameon=False, loc="upper left", fontsize=10)
    a = ax[1]
    eras = ["all", "pre-1950", "1950-1999", "2000+"]
    for k, e in enumerate(eras):
        d = H[e]
        a.plot([k, k], d["letters_ci"], color=COL["t91"], lw=2)
        a.plot(k, d["letters_diff"], "o", color=COL["t91"], ms=8)
        a.text(k + 0.08, d["letters_diff"], f"{d['letters_diff']:+.3f}", va="center", fontsize=10, color=INK)
    a.axhline(0, color=INK, lw=1)
    a.set_xticks(range(len(eras)), ["all", "pre-1950", "1950–99", "2000+"], color=INK)
    a.set_xlim(-0.5, len(eras) - 0.3)
    a.set_ylabel("new − final reader, points of letters", color=MUTED)
    a.set_title("Held-out lines (18,138): below 0 = new reader better", color=INK, loc="left", fontsize=13)
    fig.tight_layout()
    b = io.BytesIO()
    fig.savefig(b, dpi=110, facecolor="white")
    plt.close(fig)
    return Image.open(b).convert("RGB")


def examples(n=5) -> Image.Image:
    sys.path.insert(0, str(E / "89_final_reader"))
    import score89
    from rapidfuzz.distance import Levenshtein
    strict, fold = score89.title_forms()
    S = {x["key"]: x for x in map(json.loads, open(OUT / "judge/sample.jsonl", encoding="utf-8"))}
    T = score89.title_truths(strict)
    for a in map(json.loads, open(OUT / "judge/answers.jsonl", encoding="utf-8")):
        s = S.get(a["key"])
        if s and s["set"] == "heldout" and a["verdict"] != "unreadable":
            t = s["shown"][a["right_idx"][0]] if a["verdict"] == "match" and a["right_idx"] else a["reading"]
            T[a["key"]] = (t, s["shown"], "judge91")
    P = {n: {x["key"]: x["pred"] for x in map(json.loads, open(f, encoding="utf-8"))}
         for n, f in (("l28", E / "89_final_reader/out/pred/titles_l28.jsonl"), ("t91", OUT / "host/pred/titles_t91.jsonl"))}
    cand = []
    for k, (t, _, _) in T.items():
        if k in P["t91"] and k in P["l28"] and strict(P["t91"][k]) == strict(t) and strict(P["l28"][k]) != strict(t) \
                and fold(P["l28"][k]) != fold(t):
            cand.append((Levenshtein.distance(strict(P["l28"][k]), strict(t)), k))
    cand.sort(reverse=True)
    pick, seen = [], set()
    for _, k in cand:
        if k[:4] in seen and len(seen) < n:
            continue
        seen.add(k[:4])
        pick.append(k)
        if len(pick) == n:
            break
    W, Hh = 1540, 150
    im = Image.new("RGB", (W, 40 + Hh * len(pick)), "white")
    d = ImageDraw.Draw(im)
    fa = ImageFont.truetype(FONT, 24, layout_engine=ImageFont.Layout.RAQM)
    fl = ImageFont.truetype(LAT, 15)
    d.text((10, 8), "Held-out titles the new reader now reads right (the print, then each reader's text)", font=fl, fill=INK)
    for j, k in enumerate(pick):
        y = 40 + j * Hh
        c = Image.open(E / "89_final_reader/out/titles/crops" / f"{k}.png").convert("RGB")
        sc = min(1.0, (W - 20) / c.width, 64 / c.height)
        c = c.resize((max(1, int(c.width * sc)), max(1, int(c.height * sc))))
        im.paste(c, (W - c.width - 10, y))
        d.text((W - 10, y + 70), P["t91"][k], font=fa, fill=COL["t91"], anchor="ra", direction="rtl")
        d.text((W - 10, y + 104), P["l28"][k], font=fa, fill=COL["l28"], anchor="ra", direction="rtl")
        d.text((10, y + 76), "new reader", font=fl, fill=COL["t91"])
        d.text((10, y + 110), "final reader", font=fl, fill=COL["l28"])
        d.line([(0, y + Hh - 4), (W, y + Hh - 4)], fill=GRID)
    return im


def main():
    a, b = charts(), examples()
    W = max(a.width, b.width)
    im = Image.new("RGB", (W, a.height + b.height), "white")
    im.paste(a, (0, 0))
    im.paste(b, (0, a.height))
    (OUT / "look").mkdir(parents=True, exist_ok=True)
    im.save(OUT / "look/fig91.png")
    print(OUT / "look/fig91.png", im.size)


if __name__ == "__main__":
    main()
