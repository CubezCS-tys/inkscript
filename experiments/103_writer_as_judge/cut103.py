"""Experiment 103: lossless crops for the writer and larger crops for the blind readers.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python cut103.py png   SET.jsonl OUTDIR [WORKERS]
    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python cut103.py blind DISPUTES.jsonl OUTDIR

png:   the reader's crop geometry exactly (cut102 / common77.cut_line, 250 dpi, 96 px, test=True) but stored as PNG,
       not JPEG q90: experiments 87/95 fitted their writer on PNG crops and the binarisation was never checked on
       JPEG.  The reader keeps reading cut102's JPEG crops (what it was trained on).
blind: the same line, 144 px high, PNG, one file per dispute (experiment 97's readers got page-image crops).
Every key passes experiment 102's guard.  Resumable per page.
"""
from __future__ import annotations

import gzip
import io
import json
import os
import sys
import tarfile
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
sys.path.insert(0, str(E / "102_qwen_line_reader"))
POOL = E / "102_qwen_line_reader/out/pool/pool102.jsonl.gz"


def _pages(keys):
    import guard102
    guard102.assert_trainable(list(keys))
    by = defaultdict(list)
    for d in map(json.loads, gzip.open(POOL, "rt", encoding="utf-8")):
        if d["key"] in keys:
            by[(d["pdf"], d["azure"], d["page"])].append(d)
    return by


def _cut(pages, H):
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages, cut_line, nonempty_lines, render_page
    cv2.setNumThreads(1)
    cache = {}
    for (pdf, az, page), rows in pages:
        if az not in cache:
            cache.clear()
            cache[az] = azure_pages(Path(az))
        pg = cache[az][page - 1]
        doc = pdfium.PdfDocument(pdf)
        img = render_page(doc, page - 1)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        by_i = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for r in rows:
            ln = by_i.get(r["i"])
            if not ln or not ln["poly"]:
                continue
            crop, _ = cut_line(img, ln["poly"], sx, sy, H=H, test=True)
            if crop is not None:
                yield r["key"], cv2.imencode(".png", crop)[1].tobytes()


def _work(args):
    wid, pages, outdir = args
    tp = Path(outdir) / f"png-{wid}.tar"
    done = set()
    if tp.exists():
        with tarfile.open(tp) as tf:
            done = {m.name[:-4] for m in tf.getmembers()}
    n = 0
    with tarfile.open(tp, "a") as tf:
        todo = [(k, v) for k, v in pages if any(r["key"] not in done for r in v)]
        for key, data in _cut(todo, 96):
            if key in done:
                continue
            ti = tarfile.TarInfo(key + ".png")
            ti.size = len(data)
            tf.addfile(ti, io.BytesIO(data))
            n += 1
    return wid, n


def png(set_path, outdir, workers=4):
    from multiprocessing import Pool
    keys = {json.loads(l)["key"] for l in open(set_path, encoding="utf-8")}
    by = _pages(keys)
    os.makedirs(outdir, exist_ok=True)
    docs = sorted({k[0] for k in by})
    per = [[] for _ in range(workers)]
    for k, v in sorted(by.items()):
        per[docs.index(k[0]) % workers].append((k, v))
    with Pool(workers) as p:
        for wid, n in p.imap_unordered(_work, [(i, per[i], outdir) for i in range(workers)]):
            print("worker", wid, n, "crops", flush=True)


def blind(disputes, outdir):
    D = [json.loads(l) for l in open(disputes, encoding="utf-8")]
    keys = {d["id"] for d in D}
    os.makedirs(outdir, exist_ok=True)
    n = 0
    for key, data in _cut(sorted(_pages(keys).items()), 144):
        Path(outdir, key + ".png").write_bytes(data)
        n += 1
    print(n, "blind crops of", len(keys))


if __name__ == "__main__":
    if sys.argv[1] == "png":
        png(sys.argv[2], sys.argv[3], int(sys.argv[4]) if len(sys.argv) > 4 else 4)
    elif sys.argv[1] == "blind":
        blind(sys.argv[2], sys.argv[3])
