"""Experiment 86: the owner's picture (out/look/bench86.png).   ../81_heldout_scale/out/venv/bin/python fig86.py
Top: KITAB-Bench's printed subsets, official CER (log scale): our readers beside the published Gemini-2.0-Flash,
Azure, GPT-4o (KITAB paper, Table 9) and Nuqta-4B (its model card, images as given).  Bottom: real crops, as our reader
sees them, with what it got wrong."""
import json
import tarfile
from pathlib import Path

import cv2
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

HERE = Path(__file__).resolve().parent
O = HERE / "out"
S = json.loads((O / "scores86.json").read_text())
PUB = json.loads((HERE / "published86.json").read_text())
SUBS = [("patsocr", "PATS (8 fonts, lines)"), ("isippt", "ISI-PPT (slides, lines)"),
        ("synthesizear", "SynthesizeAr (rendered, vowelled)"), ("arabicocr", "ArabicOCR (paragraphs)*")]
ROWS = [("Gemini-2.0-Flash", "gemini", "#eb6834", "s"), ("Azure OCR", "azure", "#4a3aa7", "D"),
        ("GPT-4o", "gpt4o", "#8a8a85", "v"), ("Nuqta-4B", "nuqta", "#1baf7a", "^"),
        ("ours v5", "v5", "#9bbbe6", "o"), ("ours v7-28M (final)", "v7", "#2a78d6", "o")]
fig = plt.figure(figsize=(13, 9.6))
ax = fig.add_axes([0.25, 0.47, 0.72, 0.46])
for i, (k, lab) in enumerate(SUBS):
    y = len(SUBS) - 1 - i
    ax.axhline(y, color="#e6e6e2", lw=1, zorder=0)
    for j, (name, key, col, mk) in enumerate(ROWS):
        if key in ("v3", "v5", "v7"):
            v = S[key][k]["official"]["cer"] * 100
        else:
            v = PUB[key].get(k)
            if v is None:
                continue
            v = v * 100
        v = max(v, 0.05)
        dy = (j - 2.5) * 0.09
        ax.scatter(v, y + dy, s=70 if key == "v7" else 48, color=col, marker=mk, zorder=3,
                   edgecolor="white", linewidth=0.8)
        if key == "v7":
            ax.text(v * 1.12, y + dy + 0.02, f"{v:.2f}%", va="center", fontsize=9, color="#0b0b0b")
ax.set_xscale("log")
ax.set_xlim(0.04, 100)
ax.set_xticks([0.1, 0.3, 1, 3, 10, 30, 100], ["0.1%", "0.3%", "1%", "3%", "10%", "30%", "100%"])
ax.set_yticks(range(len(SUBS)), [lab for _, lab in SUBS][::-1], fontsize=10.5)
ax.set_ylim(-0.6, len(SUBS) - 0.4)
for s in ("top", "right", "left"):
    ax.spines[s].set_visible(False)
ax.tick_params(axis="y", length=0)
ax.grid(axis="x", color="#eeeeea", lw=0.8)
ax.set_xlabel("characters wrong, KITAB-Bench's own scorer (vowel marks dropped, hamza / alif maqsura / ta marbuta folded); lower is better", fontsize=10)
hs = [plt.Line2D([], [], marker=mk, color=col, ls="", markersize=8) for _, _, col, mk in ROWS]
ax.legend(hs, [r[0] for r in ROWS], ncol=6, loc="lower center", bbox_to_anchor=(0.45, 1.01), frameon=False, fontsize=10)
fig.text(0.02, 0.975, "Experiment 86: our line reader on a public Arabic OCR benchmark (KITAB-Bench, printed subsets)",
         fontsize=14, weight="bold")
fig.text(0.25, 0.385, "* paragraph images: we cut the lines with our own simple splitter (the benchmark gives no line boxes). "
         "Published 0.00 is drawn at 0.05%.\n  Nuqta: its own numbers; its card says 114 PATS texts were in its "
         "training. Ours: trained only on Mandumah journal lines, never on any benchmark.", fontsize=8.8, color="#52514e")

# bottom: real crops
EX = [("patsocr", None, "PATS line printed white on black\n(inverted before reading): read exactly"),
      ("isippt", None, "ISI-PPT slide line: read exactly"),
      ("synthesizear", None, "SynthesizeAr, display face: 1 letter wrong\nof 51 (v5: 4); most vowel marks left out"),
      ("ourslines", None, "KITAB line set: v7 reads it right, but the\nreference is a garbled PDF text layer (20 \"errors\")")]
pred = {}
for sub in ("patsocr", "isippt", "synthesizear", "ourslines"):
    for l in open(O / f"pred/v7_{sub}.jsonl", encoding="utf-8"):
        d = json.loads(l)
        pred[d["key"]] = d["pred"]
chosen = json.loads((O / "look/fig86_examples.json").read_text())
y0 = 0.32
for (sub, _, cap), key in zip(EX, chosen):
    t = tarfile.open(O / f"shards/{sub}-000.tar")
    g = cv2.imdecode(np.frombuffer(t.extractfile(key + ".jpg").read(), np.uint8), 0)
    g = g[:, :1100]
    h = 0.062
    a = fig.add_axes([0.30, y0 - h, 0.67 * g.shape[1] / 1100, h])
    a.imshow(g, cmap="gray", vmin=0, vmax=255, aspect="auto")
    a.axis("off")
    fig.text(0.29, y0 - h / 2, cap, ha="right", va="center", fontsize=9)
    y0 -= h + 0.018
fig.savefig(O / "look/bench86_v7.png", dpi=110, facecolor="#fcfcfb")
print("ok")
