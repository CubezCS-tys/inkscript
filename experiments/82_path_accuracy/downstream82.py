"""Experiment 82, downstream: the signal reader trained and tested on skeleton paths (rd_rule) against the one trained
and tested on learned paths (rd_learned), the same 3,000 held-out lines.

    python downstream82.py out/host/out [--test out/host/d82]    -> out/downstream.json, out/chart_downstream.png
CER (punctuation removed, as exp 79) per damage level and per face kind (modern OFL faces / traced old faces).
Routing: with the test crops (gen82 test shards), a measurable ink feature decides per line which path to read:
  heaviness = the share of the line's ink pixels lying deeper than 0.75 x the line's stroke width inside the ink (the
  filled-head / spread-ink signature that exp 79's hybrid used); the threshold is chosen on half the lines and scored
  on the other half.
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from reader82 import lev, no_punct  # noqa: E402

LEVELS = ["clean", "mild", "heavy", "spread", "fill"]


def load(d, name, kind):
    rows = {}
    for f in sorted(Path(d, name).glob(f"pred_syn_{kind}_*.jsonl")):
        if "_src_" in f.name:
            continue
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            a, b = no_punct(r["pred"]), no_punct(r["label"])
            rows[(r["text"], r["font"], r["level"])] = dict(e=lev(a, b), n=max(1, len(b)), level=r["level"],
                                                            src=r.get("src", "?"), font=r["font"])
    return rows


def cer(rows):
    return round(100 * sum(r["e"] for r in rows) / max(1, sum(r["n"] for r in rows)), 2) if rows else None


def heaviness(test_dir):
    """(text, font, level) -> heaviness of the damaged crop."""
    import cv2

    from sig79 import binarise, line_metrics
    out = {}
    for f in sorted(Path(test_dir).glob("test-*.npz")):
        z = np.load(f, allow_pickle=True)
        meta = [json.loads(l) for l in open(str(f)[:-4] + ".jsonl", encoding="utf-8")]
        for g, m in zip(z["grey"], meta):
            grey = cv2.imdecode(np.frombuffer(g, np.uint8), cv2.IMREAD_GRAYSCALE)
            ink = binarise(grey)
            M = line_metrics(ink)
            dt = cv2.distanceTransform(ink.astype(np.uint8), cv2.DIST_L2, 3)
            out[(m["text"], m["font"], m["level"])] = float((dt[ink] >= 0.75 * M["stroke"] * 1.5).mean()) if ink.any() else 0.0
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("hostout")
    ap.add_argument("--test", default="")
    a = ap.parse_args()
    R = load(a.hostout, "rd_rule", "rdmg")
    Lr = load(a.hostout, "rd_learned", "ldmg")
    keys = sorted(set(R) & set(Lr))
    res = dict(lines=len(keys))
    for src in ("all", "font", "traced"):
        for lv in LEVELS + ["all"]:
            k = [x for x in keys if (src == "all" or R[x]["src"] == src) and (lv == "all" or R[x]["level"] == lv)]
            if k:
                res[f"{src}/{lv}"] = dict(lines=len(k), skeleton=cer([R[x] for x in k]), learned=cer([Lr[x] for x in k]))
    if a.test:
        H = heaviness(a.test)
        k2 = [x for x in keys if x in H]
        rng = np.random.default_rng(82)
        perm = rng.permutation(len(k2))
        dev, tst = [k2[i] for i in perm[::2]], [k2[i] for i in perm[1::2]]
        best = None
        for thr in [-1] + list(np.quantile([H[x] for x in dev], np.linspace(0, 1, 41))) + [2]:
            c = cer([Lr[x] if H[x] > thr else R[x] for x in dev])
            if best is None or c < best[0]:
                best = (c, thr)
        thr = best[1]
        res["routing"] = dict(feature="share of ink deeper than 1.125 x stroke width", threshold=round(float(thr), 4),
                              share_routed_learned=round(float(np.mean([H[x] > thr for x in tst])), 3),
                              test_lines=len(tst), skeleton=cer([R[x] for x in tst]), learned=cer([Lr[x] for x in tst]),
                              routed=cer([Lr[x] if H[x] > thr else R[x] for x in tst]),
                              oracle=cer([min(R[x], Lr[x], key=lambda r: r["e"] / r["n"]) for x in tst]))
        by = defaultdict(list)
        for x in tst:
            by[R[x]["level"]].append(H[x] > thr)
        res["routing"]["routed_learned_by_level"] = {lv: round(float(np.mean(v)), 2) for lv, v in by.items()}
    (HERE / "out/downstream.json").write_text(json.dumps(res, indent=1))
    print(json.dumps(res, indent=1))
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, axs = plt.subplots(1, 2, figsize=(12, 4.4), sharey=True)
    for ax, (src, title) in zip(axs, (("font", "modern faces"), ("traced", "faces traced from our 1927-1958 scans"))):
        xs = [lv for lv in LEVELS if f"{src}/{lv}" in res]
        for j, (m, col, nm) in enumerate((("skeleton", "#2a78d6", "reader on skeleton paths"),
                                           ("learned", "#e87ba4", "reader on learned paths"))):
            v = [res[f"{src}/{lv}"][m] for lv in xs]
            b = ax.bar(np.arange(len(xs)) - 0.2 + 0.4 * j, v, 0.36, color=col, label=nm)
            ax.bar_label(b, fmt="%.1f", fontsize=8, padding=2)
        ax.set_xticks(range(len(xs)), xs)
        ax.set_title(title, fontsize=11)
        ax.grid(axis="y", color="#e6e6e6", lw=0.8)
        ax.set_axisbelow(True)
        for s in ("top", "right"):
            ax.spines[s].set_visible(False)
    axs[0].set_ylabel("% characters wrong (lower is better)")
    axs[0].legend(frameon=False, fontsize=9)
    fig.suptitle(f"Signal reader on held-out synthetic lines ({len(keys)} lines): skeleton paths vs learned paths", fontsize=12)
    fig.tight_layout()
    fig.savefig(HERE / "out/chart_downstream.png", dpi=110)


if __name__ == "__main__":
    main()
