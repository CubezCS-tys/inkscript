"""Experiment 79r (rented host): real lines -> pen signals through experiment 82's LEARNED centre line.

    python reallearn79.py --jobs /work/real/jobs_train.jsonl --pdfs /work/real --split train --out /work/data7
    python reallearn79.py --crops /work/r/testcrops.npz --split test --out /work/data7       (-> real.npz)

The same lines as p4r: each page rendered at 250 dpi, each line cut as experiment 77 cuts it (realsig79.cut_line,
96 px).  Experiment 82's U-Net (out/learned/u1/model.pt, frozen copies of its net82.py / path82.py / sig79.py in
--x82) predicts the centre-line probability from the grey crop alone; it is thresholded (0.5) and thinned
(net82.decode) and handed to path82.rebuild(grey, "learned", cl=...), i.e. experiment 79's own graph and right-to-left
walk.  No letters are ever given to the rebuilder.  Features: the frozen sig79.features (13 per point, as p4r's).
Work in chunks: CPU pool renders and cuts -> GPU predicts -> CPU pool decodes and rebuilds -> shard written.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

os.environ.setdefault("OMP_NUM_THREADS", "1")
cv2.setNumThreads(1)
X82 = os.environ.get("X82", "/work/x82")
sys.path.insert(0, X82)


def cut_article(args):
    job, pdfs = args
    import pypdfium2 as pdfium
    from realsig79 import cut_line, render_page
    out = []
    try:
        pdf = pdfium.PdfDocument(str(Path(pdfs) / job["pdf"]))
    except Exception:  # noqa: BLE001
        return out
    for pg in job["pages"]:
        if pg["page"] - 1 >= len(pdf):
            continue
        img = render_page(pdf, pg["page"] - 1)
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        for ln in pg["lines"]:
            crop = cut_line(img, ln["poly"], sx, sy)
            if crop is None:
                continue
            ok, b = cv2.imencode(".png", crop)
            out.append((ln["key"], ln["label"], job["stem"], b.tobytes()))
    pdf.close()
    return out


def rebuild_job(args):
    key, png, prob = args
    import path82 as PP
    from net82 import decode
    from sig79 import features
    g = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
    y = np.zeros((4,) + g.shape, np.float32)
    y[0] = prob.astype(np.float32) / 255.0
    try:
        F = features(PP.rebuild(g, "learned", cl=decode(y, 0.5)))
    except Exception:  # noqa: BLE001
        return key, None
    return key, F.astype(np.float16)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--jobs")
    ap.add_argument("--pdfs", default="/work/real")
    ap.add_argument("--crops")
    ap.add_argument("--split", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--model", default=f"{X82}/u1.pt")
    ap.add_argument("--workers", type=int, default=56)
    ap.add_argument("--chunk", type=int, default=40, help="articles per chunk")
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--limit", type=int, default=0, help="test crops only: the first N (smoke test)")
    a = ap.parse_args()
    import torch
    from learn82 import load_model
    from net82 import predict
    torch.set_num_threads(4)
    dev = torch.device(a.device)
    model = load_model(a.model, dev)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    pool = Pool(a.workers, maxtasksperchild=500)
    t0 = time.time()

    def run(items, name):
        """items: [(key, label, stem, png)] -> shard <name>.npz/.jsonl (or real.npz for the test)."""
        probs = []
        with torch.no_grad():
            for key, _, _, png in items:
                g = cv2.imdecode(np.frombuffer(png, np.uint8), cv2.IMREAD_GRAYSCALE)
                probs.append((predict(model, g, dev)[0] * 255).astype(np.uint8))
        t1 = time.time()
        res = pool.map(rebuild_job, [(k, png, p) for (k, _, _, png), p in zip(items, probs)], chunksize=8)
        good = [(it, F) for it, (_, F) in zip(items, res) if F is not None and len(F) >= 4]
        if a.split == "test":
            np.savez(Path(a.out) / "real.npz", **{it[0]: F for it, F in good})
        else:
            np.savez(Path(a.out) / f"{name}.npz", rreal=np.concatenate([F for _, F in good]) if good else np.zeros((0, 13), np.float16),
                     rreal_off=np.cumsum([0] + [len(F) for _, F in good]).astype(np.int64))
            with open(Path(a.out) / f"{name}.jsonl", "w", encoding="utf-8") as f:
                for it, _ in good:
                    f.write(json.dumps(dict(key=it[0], label=it[1], text=it[1], stem=it[2], font="real", level="real",
                                            px=0), ensure_ascii=False) + "\n")
        print(f"{name}: {len(good)} of {len(items)} lines; predict {t1 - tc:.0f}s rebuild {time.time() - t1:.0f}s; "
              f"total {time.time() - t0:.0f}s", flush=True)

    if a.crops:
        z = np.load(a.crops)
        meta = [json.loads(l) for l in open(a.crops[:-4] + ".jsonl", encoding="utf-8")]
        if a.limit:
            meta = meta[:a.limit]
        tc = time.time()
        run([(m["key"], m["label"], "", z[m["key"]].tobytes()) for m in meta], "test")
    else:
        jobs = [json.loads(l) for l in open(a.jobs, encoding="utf-8")]
        for c in range(0, len(jobs), a.chunk):
            tc = time.time()
            parts = pool.map(cut_article, [(j, a.pdfs) for j in jobs[c:c + a.chunk]], chunksize=1)
            run([x for p in parts for x in p], f"{a.split}-{c // a.chunk:03d}")
    pool.close()
    print("done", a.split, flush=True)


if __name__ == "__main__":
    main()
