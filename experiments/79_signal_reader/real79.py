"""Experiment 79, step 1: reconstruct pen signals from ~20 REAL line crops of the training pool (never the held-out
journals of experiment 76's split, never exp 77's dev articles).

    nice -n 19 ionice -c3 python real79.py [N=20] [H=96]

Lines are cut by experiment 77's own cut (common77.cut_line: Azure's polygon, the same padding), at height H
(96 = twice experiment 77's 48, the same box: thinning needs a few pixels of stroke).  Writes
out/real/<key>.png (path over ink + the signal strip), out/real/sheet.png, out/real/lines.jsonl (key, label, counts).
"""
from __future__ import annotations

import json
import random
import sys

import cv2
import numpy as np

from sig79 import E, OUT, draw, features, line_signal, signal_strip

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import azure_pages, clean_label, cut_line, nonempty_lines, render_page, test_codes  # noqa: E402

cv2.setNumThreads(1)


def pick(n: int, seed: int = 79):
    sel = json.loads((E / "77_scratch_reader/out/select77.json").read_text())
    meta = {}
    for l in open(E / "77_scratch_reader/out/pages77.jsonl", encoding="utf-8"):
        r = json.loads(l)
        meta[(r["stem"], r["page"])] = r
    held = test_codes()
    rng = random.Random(seed)
    tr = [p for p in sel["train"] if (p["stem"], p["page"]) in meta and meta[(p["stem"], p["page"])]["jcode"] not in held]
    old = [p for p in tr if str(meta[(p["stem"], p["page"])]["year"])[:4] < "2000"]
    new = [p for p in tr if str(meta[(p["stem"], p["page"])]["year"])[:4] >= "2000"]
    rng.shuffle(old)
    rng.shuffle(new)
    seen_j = set()
    out = []
    parts = []
    for pool, k in ((old, n // 2), (new, n - n // 2)):
        out = []
        got = 0
        for p in pool:
            m = meta[(p["stem"], p["page"])]
            if m["jcode"] in seen_j:
                continue
            seen_j.add(m["jcode"])
            out.append(m)
            got += 1
            if got >= k:
                break
        parts.append(out)
    return [m for pair in zip(*parts) for m in pair]


def main(n: int = 20, H: int = 96):
    import pypdfium2 as pdfium
    od = OUT / "real"
    od.mkdir(parents=True, exist_ok=True)
    rng = random.Random(791)
    rows, tiles = [], []
    for m in pick(3 * n):
        if len(rows) >= n:
            break
        pdf = pdfium.PdfDocument(m["azure"].replace(".json", ".pdf")) if False else pdfium.PdfDocument(m["pdf"])
        pg = azure_pages(m["azure"])[m["page"] - 1]
        img = render_page(pdf, m["page"] - 1)
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        lines = [ln for ln in nonempty_lines(pg) if 18 <= len(clean_label(ln["text"])) <= 45
                 and sum("ء" <= c <= "ي" for c in ln["text"]) >= 0.7 * len(ln["text"].replace(" ", ""))]
        if not lines:
            pdf.close()
            continue
        ln = rng.choice(lines)
        crop, info = cut_line(img, ln["poly"], sx, sy, H=H)
        pdf.close()
        if crop is None:
            continue
        key = f"{m['stem']}_p{m['page']:03d}_l{ln['i']:03d}"
        sig = line_signal(crop, start_rule="top")
        F = features(sig)
        pic = draw(crop, sig, scale=2, label=f"{key}  {m['year']}  pieces {sig['n_pieces']}  marks {sig['n_marks']}  points {len(F)}")
        pic = np.vstack([pic, signal_strip(F, pic.shape[1])])
        cv2.imwrite(str(od / f"{key}.png"), pic)
        cv2.imwrite(str(od / f"{key}_crop.png"), crop)
        lab = clean_label(ln["text"])
        rows.append(dict(key=key, year=m["year"], jcode=m["jcode"], label=lab, W=int(crop.shape[1]),
                         pieces=sig["n_pieces"], marks=sig["n_marks"], points=int(len(F)),
                         chars=len(lab.replace(" ", "")), metrics=sig["M"]))
        tiles.append(pic)
        print(key, m["year"], sig["n_pieces"], sig["n_marks"], len(F), flush=True)
    with open(od / "lines.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    Wm = max(t.shape[1] for t in tiles)
    sheet = np.vstack([np.pad(t, ((0, 6), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in tiles])
    cv2.imwrite(str(od / "sheet.png"), sheet)


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 20, int(sys.argv[2]) if len(sys.argv) > 2 else 96)
