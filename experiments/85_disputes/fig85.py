"""Experiment 85: the owner's picture (out/look/disputes85.png).   experiments/81_heldout_scale/out/venv/bin/python fig85.py
Left: on the judged held disputes, who reads the print right, per kind of dispute.  Right: letters wrong on experiment
81's held-out lines (judge truth, every letter counted) by era: Azure, v3, v6r (judged + hamza rule), ctl (same
training, no disputes)."""
import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
O = HERE / "out"
g = json.loads((O / "judge/est85.json").read_text())["cells"]["group"]
NAMES = {"one_letter": "one other letter", "multi": "several characters", "space": "word space",
         "marks": "vowel marks", "hamza_other": "hamza (other cases)", "ya": "final ya vs alif maqsura", "ta": "ta marbuta vs ha",
         "conv_mixed": "mixed spellings", "AUDIT rule85": "hamza rule (audit)"}
order = ["AUDIT rule85", "ya", "ta", "space", "one_letter", "hamza_other", "marks", "multi", "conv_mixed"]
fig, (a, b) = plt.subplots(1, 2, figsize=(13, 5.2), gridspec_kw=dict(width_ratios=[1.25, 1]))
for i, k in enumerate(order):
    c = g[k]
    n = c["n"]
    v = [100 * c.get("az", 0) / n, 100 * c.get("v1", 0) / n, 100 * c.get("none", 0) / n]
    left = 0
    for x, col in zip(v, ["#7a9cc6", "#e0a458", "#c9c9c9"]):
        a.barh(i, x, left=left, color=col, height=0.7)
        if x > 7:
            a.text(left + x / 2, i, f"{x:.0f}", ha="center", va="center", fontsize=9)
        left += x
a.set_yticks(range(len(order)), [f"{NAMES[k]}  ({g[k]['n']})" for k in order])
a.invert_yaxis()
a.set_xlim(0, 100)
a.set_xlabel("% of judged lines")
a.set_title("Who reads the print right, where Azure and our reader disagree", fontsize=11)
a.legend(["Azure right", "our reader (v1) right", "neither"], loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=3, fontsize=9, frameon=False)
r = json.loads((O / "est85_heldout.json").read_text())["two_phase"]
eras = ["pre-1950", "1950-1999", "2000+", "all"]
R = [("Azure", None), ("v3 (before)", "v3h"), ("trained more, no disputes", "ctlh"), ("v6r: + settled disputes", "v6rh")]
az = json.loads((O / "est85_heldout.json").read_text())["by_era"]
cols = ["#7a9cc6", "#9aa5b1", "#c9c9c9", "#e0a458"]
for j, (lab, k) in enumerate(R):
    ys = [(az[e]["azure"]["letters"] if e != "all" else json.loads((O / "est85_heldout.json").read_text())["all"]["azure"]["letters"])
          if k is None else r[k][e]["letters"] for e in eras]
    b.bar([i + (j - 1.5) * 0.2 for i in range(4)], ys, width=0.2, color=cols[j], label=lab)
b.set_xticks(range(4), eras)
b.set_ylabel("letters wrong, %")
b.set_title("Held-out journals (exp 81, judge truth, every letter counted)", fontsize=11)
b.set_ylim(0, 1.35)
b.legend(fontsize=8, frameon=False, ncol=2, loc="upper left")
for s in ("top", "right"):
    a.spines[s].set_visible(False)
    b.spines[s].set_visible(False)
fig.tight_layout()
fig.savefig(O / "look/disputes85.png", dpi=130)
print(O / "look/disputes85.png")
