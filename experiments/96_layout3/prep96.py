"""Experiment 96 on the GPU host: render pages and write the layout dataset (experiment 94's prep94.py rendering,
1536 px long side, grey, pypdfium2 5.12.1).

    python prep96.py train  TRAIN96 EXTRA96 PDF_DIR D WORKERS -> D/lay/images/{train,val}/<key>.jpg + labels (16 fine
                                                                  classes; pool pages); D/extra/<key>.jpg (extra pages,
                                                                  labelled later by `pseudo`)
    python prep96.py pseudo EXTRA96 PRED_JSON D                 -> D/lay/{images,labels}/train/<key>.* for the extra pages:
                                                                  catalogue author/affiliation lines as labelled, every
                                                                  other line the stage-2 model's type (box covering
                                                                  >= 40% of the line, largest overlap x confidence;
                                                                  none -> other)
    python prep96.py reps   TRAIN96 EXTRA96 D                   -> D/lay/{images,labels}/train/<key>_r<k>.*  hard-linked
                                                                  repeats (rep per row) + D/lay.yaml
    python prep96.py test   PAGES_JSONL PDF_DIR D WORKERS       -> D/test/<key>.jpg
Pages with >= 300 lines are left out of training (experiment 94's cap94.sh lesson).
"""
from __future__ import annotations

import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

import cv2

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from prep94 import FINE, boxes_of, render, save, yolo_rows  # noqa: E402

G = {}
CAP = 300


def work(r):
    D = G["D"]
    try:
        img = render(os.path.join(G["pdf"], os.path.basename(r["pdf"])), r["page"])
    except Exception as e:  # noqa: BLE001
        return r["key"], f"render {e}"
    if r.get("extra"):
        save(img, D / "extra" / f"{r['key']}.jpg")
        return r["key"], "extra"
    if r["split"] == "train" and len(r["lines"]) >= CAP:
        return r["key"], "capped"
    sp = r["split"]
    B = boxes_of(r, img)
    save(img, D / "lay/images" / sp / f"{r['key']}.jpg")
    (D / "lay/labels" / sp / f"{r['key']}.txt").write_text(
        yolo_rows([(b, FINE.index(x["fine"] or "other")) for b, x in B], img.shape[1], img.shape[0]))
    return r["key"], "ok"


def work_test(r):
    img = render(os.path.join(G["pdf"], os.path.basename(r["pdf"])), r["page"])
    save(img, G["D"] / "test" / f"{r['key']}.jpg")
    return r["key"], "ok"


def init(d, pdf):
    G["D"], G["pdf"] = Path(d), pdf
    cv2.setNumThreads(1)


def rows_of(*files):
    return [json.loads(l) for f in files for l in open(f, encoding="utf-8")]


def train(t96, e96, pdf, d, nw):
    d = Path(d).resolve()
    for sp in ("train", "val"):
        for sub in ("lay/images", "lay/labels"):
            (d / sub / sp).mkdir(parents=True, exist_ok=True)
    (d / "extra").mkdir(parents=True, exist_ok=True)
    from collections import Counter
    c = Counter()
    with Pool(int(nw), initializer=init, initargs=(str(d), pdf)) as P:
        for n, (k, m) in enumerate(P.imap_unordered(work, rows_of(t96, e96), chunksize=8), 1):
            c[m if not m.startswith("render") else "bad"] += 1
            if n % 2000 == 0:
                print(n, dict(c), flush=True)
    print("PREP96_DONE train", dict(c), flush=True)


def pseudo(e96, pred_json, d):
    d = Path(d).resolve()
    P = json.load(open(pred_json))
    from collections import Counter
    c = Counter()
    for r in rows_of(e96):
        k = r["key"]
        if k not in P:
            continue
        img = cv2.imread(str(d / "extra" / f"{k}.jpg"), cv2.IMREAD_GRAYSCALE)
        h, w = img.shape
        pr = P[k]
        items = []
        for b, x in boxes_of(r, img):
            lab = x["fine"]
            if lab is None:
                a = max(1e-9, (b[2] - b[0]) * (b[3] - b[1]))
                cand = []
                for pb, pc, ps in zip(pr["boxes"], pr["cls"], pr["conf"]):
                    q = [pb[0] * w, pb[1] * h, pb[2] * w, pb[3] * h]
                    it = max(0, min(q[2], b[2]) - max(q[0], b[0])) * max(0, min(q[3], b[3]) - max(q[1], b[1])) / a
                    if it >= 0.4:
                        cand.append((it * ps, FINE[pc]))
                lab = max(cand)[1] if cand else "other"
                c["pseudo_" + lab] += 1
            else:
                c["catalogue_" + lab] += 1
            items.append((b, FINE.index(lab)))
        if len(items) >= CAP:
            continue
        os.replace(d / "extra" / f"{k}.jpg", d / "lay/images/train" / f"{k}.jpg")
        (d / "lay/labels/train" / f"{k}.txt").write_text(yolo_rows(items, w, h))
        c["pages"] += 1
    print("PSEUDO96_DONE", dict(c), flush=True)


def reps(t96, e96, d):
    d = (Path(d) / "lay").resolve()
    n = 0
    for r in rows_of(t96, e96):
        k = r["key"]
        im, lb = d / "images/train" / f"{k}.jpg", d / "labels/train" / f"{k}.txt"
        if not r.get("rep") or r["split"] != "train" or not im.exists() or not lb.exists():
            continue
        for j in range(1, r["rep"] + 1):
            for src, ext, sub in ((im, "jpg", "images"), (lb, "txt", "labels")):
                dst = d / sub / "train" / f"{k}_r{j}.{ext}"
                if not dst.exists():
                    os.link(src, dst)
            n += 1
    for f in d.glob("labels/*.cache"):
        f.unlink()
    (d.parent / "lay.yaml").write_text(f"path: {d}\ntrain: images/train\nval: images/val\nnames:\n" +
                                       "".join(f"  {i}: {c}\n" for i, c in enumerate(FINE)))
    print("REPS96_DONE", n, flush=True)


def test(pages, pdf, d, nw):
    d = Path(d).resolve()
    (d / "test").mkdir(parents=True, exist_ok=True)
    with Pool(int(nw), initializer=init, initargs=(str(d), pdf)) as P:
        n = sum(1 for _ in P.imap_unordered(work_test, rows_of(pages), chunksize=4))
    print("PREP96_DONE test", n, flush=True)


if __name__ == "__main__":
    {"train": train, "pseudo": pseudo, "reps": reps, "test": test}[sys.argv[1]](*sys.argv[2:])
