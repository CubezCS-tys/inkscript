"""Experiment 78: pictures of the results.

    python sheet78.py confusions READER [N]   -> out/look/confusions_<READER>.png: the N most common confusions of a
                                                 reader on the owner's 20 yardstick pages (eval78's confusions file),
                                                 each with up to 2 line crops, the truth and the reader's line
    python sheet78.py chart                   -> out/look/results78.png: letters and words wrong, per reader and set
Needs Pillow with raqm (the syn78 venv); reads experiment 77's test crops (read only).
"""
from __future__ import annotations

import io
import json
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
T77 = HERE.parent / "77_scratch_reader/out/test"
AR = str(OUT / "fonts/notonaskharabic_NotoNaskhArabic[wght].ttf")
LAT = "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"


def crops(keys):
    want, got = set(keys), {}
    for f in sorted(T77.glob("test-*.tar")):
        with tarfile.open(f) as t:
            for m in t:
                k = m.name.rsplit(".", 1)[0]
                if k in want and m.name.endswith(".jpg"):
                    got[k] = Image.open(io.BytesIO(t.extractfile(m).read())).convert("L")
    return got


def text(d, xy, s, size, rtl=True, fill=0):
    f = ImageFont.truetype(AR if rtl else LAT, size, layout_engine=ImageFont.Layout.RAQM)
    d.text(xy, s, font=f, fill=fill, anchor="ra" if rtl else "la", direction="rtl" if rtl else "ltr",
           language="ar" if rtl else "en")


def confusions(reader: str, n: int = 10):
    cj = json.loads((OUT / "confusions78.json").read_text(encoding="utf-8"))[reader][:n]
    # several examples per pair: search the predictions again
    preds = {d["key"]: d["pred"] for d in map(json.loads, open(OUT / f"pred/test_{reader}.jsonl", encoding="utf-8"))}
    pages = json.loads((T77 / "pages.json").read_text(encoding="utf-8"))
    from rapidfuzz.distance import Levenshtein
    import unicodedata
    ex = defaultdict(list)
    for rec in pages:
        if rec["set"] != "yardstick":
            continue
        keys = {r["i"]: r["key"] for r in rec["lines"]}
        for i, pos in rec["gold_pos"].items():
            k = keys[int(i)]
            T = unicodedata.normalize("NFC", rec["truth"][pos])
            h = preds.get(k, "")
            for op in Levenshtein.editops(T, h):
                a = T[op.src_pos] if op.tag in ("replace", "delete") else "∅"
                b = h[op.dest_pos] if op.tag in ("replace", "insert") else "∅"
                pk = f"{a}>{b}"
                if len(ex[pk]) < 2 and k not in [x[0] for x in ex[pk]]:
                    ex[pk].append((k, T, h))
    im_rows = []
    allk = [k for c in cj for k, _, _ in ex.get(c["pair"], [])] or [c["example"]["key"] for c in cj]
    C = crops(allk)
    W = 1500
    for c in cj:
        a, b = c["pair"].split(">")
        rows = ex.get(c["pair"]) or [(c["example"]["key"], c["example"]["truth"], c["example"]["reader"])]
        h = 40 + 150 * len(rows)
        im = Image.new("L", (W, h), 255)
        d = ImageDraw.Draw(im)
        text(d, (10, 8), f"{c['count']}x   printed «{a}»  ->  read «{b}»   ({'missing' if b == '∅' else 'extra' if a == '∅' else 'swapped'})", 22, rtl=False)
        y = 40
        for k, tr, pr in rows:
            cr = C.get(k)
            if cr is not None:
                cr = cr.resize((int(cr.width * 1.5), int(cr.height * 1.5)))
                cr = cr.crop((max(0, cr.width - (W - 20)), 0, cr.width, cr.height))
                im.paste(cr, (W - 10 - cr.width, y))
            text(d, (W - 10, y + 76), "truth: " + tr[:120], 22, fill=0)
            text(d, (W - 10, y + 108), "read:  " + pr[:120], 22, fill=90)
            y += 150
        d.line((0, h - 1, W, h - 1), fill=0, width=2)
        im_rows.append(im)
    out = Image.new("L", (W, sum(x.height for x in im_rows)), 255)
    y = 0
    for x in im_rows:
        out.paste(x, (0, y))
        y += x.height
    out.save(OUT / f"look/confusions_{reader}.png")
    print(OUT / f"look/confusions_{reader}.png")


def chart():
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    r = json.loads((OUT / "results78.json").read_text(encoding="utf-8"))["sets"]
    order = ("real_only", "syn_only", "syn_then_real", "syn2_only", "syn2_then_real", "real10", "syn_then_real10",
             "azure", "argon")
    readers = [x for x in order if x in r.get("yardstick", {})]
    sets = [("yardstick", "owner's 20 pages"), ("lab_docs12", "lab docs 1-2"), ("doc3_vs_argon", "doc 3 (vs Argon)")]
    fig, axs = plt.subplots(1, 2, figsize=(16, 5.2))
    cols = {"real_only": "#4C72B0", "syn_only": "#DD8452", "syn_then_real": "#55A868", "syn2_only": "#F2B07E",
            "syn2_then_real": "#8FD19E", "real10": "#9DB4DA", "syn_then_real10": "#2E7D3E", "azure": "#999999",
            "argon": "#BBBBBB"}
    names = {"real_only": "real only (exp 77)", "syn_only": "synthetic only", "syn_then_real": "synthetic, then real",
             "syn2_only": "synthetic v2 only", "syn2_then_real": "synthetic v2, then real",
             "real10": "10% of the real lines", "syn_then_real10": "synthetic, then 10% real",
             "azure": "Azure", "argon": "Argon (doc 3's reference)"}
    for ax, (m, lab) in zip(axs, (("letters", "letters wrong (%)"), ("words", "words wrong, order-free (%)"))):
        w = 0.8 / len(readers)
        for j, rd in enumerate(readers):
            vals = [0 if (rd == "argon" and s == "doc3_vs_argon") else (r.get(s, {}).get(rd, {}).get(m) or 0)
                    for s, _ in sets]
            bars = ax.bar(np.arange(len(sets)) + j * w, vals, w, label=names[rd], color=cols[rd])
            for b_, v in zip(bars, vals):
                ax.text(b_.get_x() + b_.get_width() / 2, v, f"{v:.1f}", ha="center", va="bottom", fontsize=6.5)
        ax.set_xticks(np.arange(len(sets)) + w * (len(readers) - 1) / 2)
        ax.set_xticklabels([n for _, n in sets])
        ax.set_title(lab)
        ax.spines[["top", "right"]].set_visible(False)
    axs[0].legend(frameon=False, fontsize=9)
    fig.suptitle("Experiment 78: the same line reader trained on real, synthetic, and synthetic-then-real lines (held-out pages)")
    fig.tight_layout()
    fig.savefig(OUT / "look/results78.png", dpi=110)
    print(OUT / "look/results78.png")


if __name__ == "__main__":
    if sys.argv[1] == "confusions":
        confusions(sys.argv[2], int(sys.argv[3]) if len(sys.argv) > 3 else 10)
    else:
        chart()
