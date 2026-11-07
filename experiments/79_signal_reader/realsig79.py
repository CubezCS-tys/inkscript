"""Experiment 79, rung 2 (rented host's CPUs): real lines -> pen signals, in train79b's shard format.

    python realsig79.py --jobs /work/real/jobs_train.jsonl --pdfs /work/real --split train --out /work/data3 --workers 120

Each page is rendered at 250 dpi (pypdfium2, grey) as experiment 77 renders; each line is cut exactly as experiment 77
cuts it (Azure's polygon, padded 0.22 / 0.35, made upright) but at height 96 (twice 48: the same box), and the pen
signal is reconstructed (sig79.line_signal, skeleton centre line, thickness).  Lines experiment 77 drops for training
(rotated > 8 degrees, wider than 2400 px at height 48, tiny) are dropped here too.
Writes <out>/<split>-<w>.npz (key "rreal" + offsets) and .jsonl (key, label, stem).
"""
from __future__ import annotations

import argparse
import json
import math
import os
import time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
cv2.setNumThreads(1)
DPI, PAD_V, PAD_H, MAX_W48 = 250, 0.22, 0.35, 2400


def render_page(pdf, i: int) -> np.ndarray:
    bm = pdf[i].render(scale=DPI / 72, grayscale=True)
    a = bm.to_numpy()
    return np.ascontiguousarray(a[..., 0] if a.ndim == 3 else a)


def cut_line(img, poly, sx, sy, H=96):
    """common77.cut_line (experiment 77), duplicated: same geometry, height H."""
    p = np.array(poly[:8], dtype=np.float64).reshape(4, 2) * [sx, sy]
    top, bot = p[1] - p[0], p[2] - p[3]
    ang = math.atan2(top[1] + bot[1], top[0] + bot[0])
    w = (np.linalg.norm(top) + np.linalg.norm(bot)) / 2
    h = (np.linalg.norm(p[3] - p[0]) + np.linalg.norm(p[2] - p[1])) / 2
    c = p.mean(axis=0)
    if h < 6 or w < 4 or abs(ang) > math.radians(8):
        return None
    ph, pw = h * (1 + 2 * PAD_V), w + 2 * PAD_H * h
    s = H / ph
    W = int(round(pw * s))
    if W * 48 / H > MAX_W48 or W < 16:
        return None
    ca, sa = math.cos(ang), math.sin(ang)
    M = np.array([[ca / s, -sa / s, 0], [sa / s, ca / s, 0]], dtype=np.float64)
    M[:, 2] = c - M[:, :2] @ np.array([W / 2, H / 2])
    return cv2.warpAffine(img, M, (W, H), flags=cv2.WARP_INVERSE_MAP | cv2.INTER_LINEAR,
                          borderMode=cv2.BORDER_CONSTANT, borderValue=255)


def work(args):
    wid, jobs, pdfs, split, out, centre, flags = args
    import pypdfium2 as pdfium
    from sig79 import features, line_signal
    feats, meta = [], []
    t0 = time.time()
    for job in jobs:
        try:
            pdf = pdfium.PdfDocument(str(Path(pdfs) / job["pdf"]))
        except Exception as e:  # noqa: BLE001
            print(wid, job["stem"], "pdf error", e, flush=True)
            continue
        for pg in job["pages"]:
            if pg["page"] - 1 >= len(pdf):
                continue
            img = render_page(pdf, pg["page"] - 1)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            for ln in pg["lines"]:
                crop = cut_line(img, ln["poly"], sx, sy)
                if crop is None:
                    continue
                try:
                    F = features(line_signal(crop, start_rule="top", centre=centre, flags=flags))
                except Exception:  # noqa: BLE001
                    continue
                if len(F) < 4:
                    continue
                feats.append(F.astype(np.float16))
                meta.append(dict(key=ln["key"], label=ln["label"], text=ln["label"], stem=job["stem"], font="real",
                                 level="real", px=0))
        pdf.close()
        print(f"w{wid} {split} {len(meta)} lines {time.time() - t0:.0f}s", flush=True)
    A = np.concatenate(feats) if feats else np.zeros((0, 17 if flags else 13), np.float16)
    np.savez(Path(out) / f"{split}-{wid:03d}.npz", rreal=A, rreal_off=np.cumsum([0] + [len(x) for x in feats]).astype(np.int64))
    with open(Path(out) / f"{split}-{wid:03d}.jsonl", "w", encoding="utf-8") as f:
        for m in meta:
            f.write(json.dumps(m, ensure_ascii=False) + "\n")
    return len(meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs", required=True)
    ap.add_argument("--pdfs", required=True)
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--workers", type=int, default=100)
    ap.add_argument("--centre", default="skeleton", choices=["skeleton", "mcr", "hybrid"])
    ap.add_argument("--flags", action="store_true")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    jobs = [json.loads(l) for l in open(a.jobs, encoding="utf-8")]
    W = min(a.workers, len(jobs))
    with Pool(W, maxtasksperchild=1) as pool:
        r = pool.map(work, [(w, jobs[w::W], a.pdfs, a.split, a.out, a.centre, a.flags) for w in range(W)], chunksize=1)
    print("done", a.split, sum(r), flush=True)


if __name__ == "__main__":
    main()
