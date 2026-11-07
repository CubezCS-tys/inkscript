"""Experiment 89: the owner's picture (out/look/final89.png).
    ../81_heldout_scale/out/venv/bin/python fig89.py
Top left: held-out journals (exp 81, judge truth, every letter counted, 0097's running header left out: it is layout's),
letters wrong by era.  Top right: the title test, letters wrong by era.  Bottom: six real title crops, with which readers
read them exactly (truth = the blind judge)."""
import json
import sys
from pathlib import Path

import cv2
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
O = HERE / "out"
sys.path.insert(0, str(HERE))
import score89 as S  # noqa: E402

R = [("Azure", "azure", "#7a9cc6"), ("v3", "v3", "#c9c9c9"), ("v6r", "v6r", "#9aa5b1"), ("v7", "v7", "#e0a458"),
     ("v7-28M", "l28", "#b5651d")]
H = json.loads((O / "heldout/est89_strict_nohdr.json").read_text())
T = json.loads((O / "titles/score89_titles.json").read_text())["strict"]
eras = ["pre-1950", "1950-1999", "2000+", "all"]

fig = plt.figure(figsize=(14, 10.5))
gs = fig.add_gridspec(3, 6, height_ratios=[1.25, 0.55, 0.55], hspace=0.55, wspace=0.25)
a = fig.add_subplot(gs[0, :3])
b = fig.add_subplot(gs[0, 3:])
rs = [r for r in R if r[1] == "azure" or r[1] in H["two_phase"]]
for j, (lab, k, col) in enumerate(rs):
    if k == "azure":
        ys = [H["by_era"][e]["azure"]["letters"] for e in eras[:3]] + [H["all"]["azure"]["letters"]]
    else:
        ys = [H["two_phase"][k][e]["letters"] for e in eras]
    w = 0.8 / len(rs)
    a.bar([i + (j - (len(rs) - 1) / 2) * w for i in range(4)], ys, width=w, color=col, label=lab)
a.set_xticks(range(4), eras)
a.set_ylabel("letters wrong, %")
a.set_title("Held-out journals: 18,067 lines of 26 journals no reader saw\n(judge truth, every letter counted; "
            "0097's running header left out)", fontsize=10)
a.legend(fontsize=8, frameon=False, ncol=5, loc="upper left")
a.set_ylim(0, 1.15)
rt = [r for r in R if r[1] in T["all"]]
te = ["1950-1999", "2000+", "all"]
for j, (lab, k, col) in enumerate(rt):
    ys = [T[e][k]["letters"] for e in te]
    w = 0.8 / len(rt)
    b.bar([i + (j - (len(rt) - 1) / 2) * w for i in range(3)], ys, width=w, color=col, label=lab)
b.set_xticks(range(3), [f"{e}\n({T[e]['azure']['lines']} lines)" for e in te])
b.set_title(f"Article titles (display faces), first pages of the same journals\n({T['all']['azure']['lines']} lines; "
            f"pre-1950 has only {T['pre-1950']['azure']['lines']})", fontsize=10)
b.set_ylabel("letters wrong, %")
for ax in (a, b):
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)

# six crops: three where the 28M reader is exact and Azure is not or both are, three where v7 fails
strict, fold = S.title_forms()
TT = S.title_truths(strict)
rows = {d["key"]: d for d in S.jl(O / "titles/titles89.jsonl")}
bad = {d["key"] for d in json.loads((O / "titles/not_titles.json").read_text())["lines"]}
P = {n: {d["key"]: d["pred"] for d in S.jl(O / f"pred/titles_{n}.jsonl")} for n in ("v7", "l28")}
good, fail = [], []
for k, (t, _, _) in sorted(TT.items()):
    if k in bad or k not in rows or k not in P["l28"]:
        continue
    ok7 = strict(P["l28"][k]) == strict(t)              # the pick: the 28M reader
    oka = strict(rows[k]["azure"]) == strict(t)
    (good if ok7 else fail).append((k, ok7, oka))
pick = [x for x in good if not x[2]][:2] + [x for x in good if x[2] and not x[0].startswith("0097")][:1] + \
       [x for x in fail if x[2] and not x[0].startswith("0097")][:3]
for i, (k, ok7, oka) in enumerate(pick[:6]):
    ax = fig.add_subplot(gs[1 + i // 3, (i % 3) * 2:(i % 3) * 2 + 2])
    im = cv2.imread(str(O / "titles/crops" / f"{k}.png"), cv2.IMREAD_GRAYSCALE)
    ax.imshow(im, cmap="gray", vmin=0, vmax=255)
    ax.set_xticks([])
    ax.set_yticks([])
    v7 = "exact" if strict(P["v7"].get(k, "")) == strict(TT[k][0]) else "wrong"
    ax.set_title(f"{rows[k]['era']}   Azure {'exact' if oka else 'wrong'}   v7 {v7}   v7-28M {'exact' if ok7 else 'wrong'}",
                 fontsize=9, color="#2e7d32" if ok7 else "#b23b3b")
fig.suptitle("Experiment 89: the final line reader", fontsize=13)
(O / "look").mkdir(parents=True, exist_ok=True)
fig.savefig(O / "look/final89.png", dpi=110, bbox_inches="tight")
print("written", O / "look/final89.png", [p[0] for p in pick])
