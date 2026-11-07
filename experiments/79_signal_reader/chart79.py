"""Experiment 79: one picture of rung 2 for the owner (fusion and warning, signal vs the image + image control).

    python chart79.py out/fuse/<run> [more runs] -> out/fuse/rung2_chart.png

Left: line CER on the held-out truths: image reader alone, fused with the signal reader (each run), fused with a
second image reader.  Right: the warning's PR-AUC (how well it ranks the image reader's wrong lines first):
the signal's likelihood of the image line (each run), the image reader's own confidence, and 77-vs-78 disagreement.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import cv2
import numpy as np

W, H = 1400, 620
GREY, BLUE, ORANGE, GREEN = (150, 150, 150), (200, 120, 40), (40, 140, 230), (90, 170, 60)


def bars(img, x0, y0, w, h, rows, title, unit, vmax):
    cv2.putText(img, title, (x0, y0 - 18), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (30, 30, 30), 2, cv2.LINE_AA)
    bh = int(h / len(rows) * 0.62)
    for i, (label, v, col) in enumerate(rows):
        y = y0 + int(i * h / len(rows))
        cv2.putText(img, label, (x0, y + bh - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (40, 40, 40), 1, cv2.LINE_AA)
        bx = x0 + 250
        L = int((w - 330) * v / vmax)
        cv2.rectangle(img, (bx, y), (bx + max(2, L), y + bh), col, -1)
        cv2.putText(img, f"{v:.3f}{unit}", (bx + L + 8, y + bh - 6), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (30, 30, 30), 1, cv2.LINE_AA)


def main(runs):
    S = {Path(r).name: json.loads((Path(r) / "summary.json").read_text()) for r in runs}
    first = next(iter(S.values()))
    img = np.full((H, W, 3), 255, np.uint8)
    cer = [("image reader 77 alone", first["all"]["image77"], GREY)]
    for n, s in S.items():
        cer.append((f"77 + signal ({n})", s["all"]["fused_signal"], BLUE))
    cer.append(("77 + image reader 78", first["all"]["fused_image78"], ORANGE))
    bars(img, 30, 90, 680, 470, cer, "Line error rate (lower is better)", "%", max(v for _, v, _ in cer) * 1.15)
    warn = [("77's own confidence", first["warning"]["scores"]["ctl_conf"]["pr_auc"], GREY)]
    for n, s in S.items():
        warn.append((f"signal ({n})", s["warning"]["scores"]["sig_ll"]["pr_auc"], BLUE))
    warn.append(("77 vs 78 disagreement", first["warning"]["scores"]["ctl_dis"]["pr_auc"], ORANGE))
    bars(img, 720, 90, 680, 470, warn, "Warning: finds the wrong lines (higher is better)", "", 1.0)
    cv2.putText(img, f"Exp 79 rung 2 - {first['lines']} held-out lines with the owner's truth; "
                     f"{first['warning']['image_errors']} lines the image reader got wrong",
                (30, 600), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (60, 60, 60), 1, cv2.LINE_AA)
    out = Path(runs[0]).parent / "rung2_chart.png"
    cv2.imwrite(str(out), img)
    print(out)


if __name__ == "__main__":
    main(sys.argv[1:])
