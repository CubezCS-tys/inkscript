"""Experiment 102 pictures for the owner (out/pictures/).

    nice -n 19 ../87_writer/out/venv/bin/python pictures102.py curve     -> dev_curve.png (matplotlib)
    nice -n 19 ../81_heldout_scale/out/venv/bin/python pictures102.py strip  -> exam_strip.png (PIL + raqm)

curve: DEV letters wrong (folded, punctuation ignored) against training lines seen, S and M, the untrained model at 0;
       Azure's and t91's EXAM levels drawn as dashed reference lines, labelled as a different set.
strip: 16 exam lines: 8 that M reads right (folded, punctuation ignored) and the untrained model wrong (seed 102 among
       them), and M's 8 worst lines by letters wrong; per line the printed crop, then truth, Azure, t91, untrained
       Qwen, Qwen after M; a reading that differs from the truth is on a pale red band.
"""
from __future__ import annotations

import io
import json
import random
import sys
import tarfile
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out/pictures"
M_CKPT = (HERE / "out/M_choice.txt").read_text().strip() if (HERE / "out/M_choice.txt").exists() else None


def curve():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    sc = HERE / "out/scores"
    base = json.loads((sc / "dev_base_H96.json").read_text())["reading"]["folded_no_punct"]["letter_error"] * 100
    series = {}
    for tag in ("S", "M"):
        pts = [(1000, base)]
        for f in sorted(sc.glob(f"dev_{tag}_*.json"), key=lambda p: int(p.stem.split("_")[-1])):
            step = int(f.stem.split("_")[-1])
            pts.append((step * 64, json.loads(f.read_text())["reading"]["folded_no_punct"]["letter_error"] * 100))
        series[tag] = pts
    fig, ax = plt.subplots(figsize=(9, 5), dpi=130)
    fig.patch.set_facecolor("#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    colors = {"S": "#2a78d6", "M": "#eb6834"}
    names = {"S": "trained on S (20,000 lines)", "M": "trained on M (200,000 lines)"}
    for tag, pts in series.items():
        x, y = zip(*pts)
        ax.plot(x, y, color=colors[tag], lw=2, marker="o", ms=5, label=names[tag])
        if len(pts) > 1:
            ax.annotate(f"{y[-1]:.2f}%", (x[-1], y[-1]), textcoords="offset points", xytext=(6, 6), color="#0b0b0b", fontsize=9)
    for val, lab, dy in ((0.53, "Azure on the EXAM lines (a different set): 0.53%", -0.22),
                         (0.71, "our reader t91 on the EXAM lines (a different set): 0.71%", 0.08)):
        ax.axhline(val, color="#8a8984", lw=1, ls="--")
        ax.text(1100, val + dy, lab, color="#52514e", fontsize=8)
    ax.annotate(f"untrained {base:.2f}%", (1000, base), textcoords="offset points", xytext=(8, 4), color="#0b0b0b", fontsize=9)
    ax.set_xscale("log")
    ax.set_xticks([1000, 3200, 10000, 32000, 100000, 200000])
    ax.set_xticklabels(["untrained", "3,200", "10,000", "32,000", "100,000", "200,000"])
    ax.set_xlabel("training lines seen (log scale)")
    ax.set_ylabel("letters wrong on DEV, %  (folded, punctuation ignored)")
    ax.set_ylim(0, max(base + 0.5, 6.5))
    ax.set_title("Qwen3.5-4B learning to read our lines (DEV truth = Azure-derived labels)", fontsize=11, color="#0b0b0b")
    for s in ("top", "right"):
        ax.spines[s].set_visible(False)
    ax.grid(axis="y", color="#e6e5e0", lw=0.8)
    ax.legend(frameon=False, loc="upper right")
    OUT.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(OUT / "dev_curve.png")
    print(OUT / "dev_curve.png")


def strip():
    import numpy as np
    from PIL import Image, ImageDraw, ImageFont
    sys.path.insert(0, str(E / "97_extraction_evals"))
    sys.path.insert(0, str(E / "99_liteparse_baseline/scripts"))
    import score97 as S
    import score99 as S99
    from common97 import lev
    use, truth, _ = S99.r1_truth()
    rd = lambda p, ad: {d["key"]: d["text"] for d in map(json.loads, open(p, encoding="utf-8")) if d.get("adapter") == ad}
    base = rd(HERE / "out/eval/exam_base.jsonl", "base")
    m = rd(HERE / "out/eval/exam_M.jsonl", M_CKPT)
    np_ = lambda s: S.no_punct(S.r1_fold(s or ""))
    keys = [k for k in sorted(use) if k in truth and truth[k].get("exact")]
    err = lambda k, t: lev(np_(t), S.no_punct(truth[k]["folded"]))
    good = [k for k in keys if err(k, m.get(k)) == 0 and err(k, base.get(k)) > 0]
    random.Random(102).shuffle(good)
    worst = sorted(keys, key=lambda k: -err(k, m.get(k)))[:8]
    picks = [("M right, untrained wrong", k) for k in good[:8]] + [("M's worst", k) for k in worst]
    tf = tarfile.open(HERE / "out/crops_exam/exam-000.tar")
    names = {mm.name[:-4]: mm for mm in tf.getmembers()}
    NASKH = "/usr/share/fonts/truetype/noto/NotoNaskhArabic-Regular.ttf"
    SANS = "/usr/share/fonts/truetype/noto/NotoSans-Regular.ttf"
    fa, fl, fs = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 21), ImageFont.truetype(SANS, 16), ImageFont.truetype(SANS, 14)
    W = 1500
    rows = []
    for why, k in picks:
        crop = Image.open(io.BytesIO(tf.extractfile(names[k]).read())).convert("L")
        if crop.size[0] > W - 40:
            crop = crop.resize((W - 40, int(crop.size[1] * (W - 40) / crop.size[0])))
        texts = [("truth (settled)", truth[k]["exact"]), ("Azure", use[k].get("azure")), ("t91 (ours)", use[k].get("t91")),
                 ("Qwen untrained", base.get(k)), ("Qwen after M", m.get(k))]
        h = 30 + crop.size[1] + 10 + 40 * len(texts) + 20
        im = Image.new("RGB", (W, h), (252, 252, 251))
        d = ImageDraw.Draw(im)
        d.text((20, 6), f"{why}   ·   {k}   ·   M: {err(k, m.get(k))} letters wrong, untrained: {err(k, base.get(k))}",
               font=fs, fill=(82, 81, 78))
        im.paste(crop.convert("RGB"), (W - 20 - crop.size[0], 30))
        y = 30 + crop.size[1] + 10
        for lab, t in texts:
            wrong = lab != "truth (settled)" and err(k, t) > 0
            if wrong:
                d.rectangle([0, y - 2, W, y + 36], fill=(252, 228, 224))
            d.text((20, y + 8), lab, font=fl, fill=(11, 11, 11))
            tw = d.textlength(t or "", font=fa, direction="rtl")
            d.text((W - 20 - tw, y), t or "(nothing)", font=fa, fill=(11, 11, 11), direction="rtl")
            y += 40
        d.line([0, h - 2, W, h - 2], fill=(200, 199, 194), width=2)
        rows.append(im)
    for part in (0, 1):
        sub = rows[part * 8:(part + 1) * 8]
        H = sum(r.size[1] for r in sub)
        sheet = Image.new("RGB", (W, H), (252, 252, 251))
        y = 0
        for r in sub:
            sheet.paste(r, (0, y))
            y += r.size[1]
        OUT.mkdir(parents=True, exist_ok=True)
        p = OUT / f"exam_strip_{'right' if part == 0 else 'worst'}.png"
        sheet.save(p)
        print(p)


if __name__ == "__main__":
    {"curve": curve, "strip": strip}[sys.argv[1]]()
