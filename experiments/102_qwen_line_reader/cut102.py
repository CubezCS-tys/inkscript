"""Experiment 102: cutting line crops, and turning a crop into the image the model sees.

The crop (stored): experiment 77's geometry exactly (common77.cut_line: Azure's polygon turned upright, padding 0.22 x
the line height above and below and 0.35 x at each end), from a 250-dpi grey pypdfium2 5.12.1 render, but scaled to
STORE_H = 96 px instead of 48 (Qwen's vision patches are 16 px and every 2 x 2 patches become one token: at 48 px a
line would be a token and a half high).  cut_line(test=True): no line is dropped for angle or width (the training
lines already passed build77's filters at 48 px).  Grey JPEG quality 90.

The model image (model_image): the stored crop resized to height H (96 or 64, chosen on DEV before training, see the
README), then padded with white ON THE LEFT (the end of an Arabic line) to a width that is a multiple of 32 and at
least MIN_PIXELS / H, so the processor's smart_resize (factor 32, min_pixels 65,536 = the checkpoint's
preprocessor "shortest_edge") leaves it exactly as given, in Transformers and in vLLM alike.  Lines wider than
MAX_W are scaled down to MAX_W (none in the pool at H = 96).  RGB (the grey copied to 3 channels).

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python cut102.py sets OUTDIR WORKERS SET.jsonl [SET2.jsonl ...]
    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python cut102.py exam OUTDIR       (experiment 97's 600 lines)
Output: OUTDIR/<tag>-<worker>-<NNN>.tar (<key>.jpg) + OUTDIR/index-<tag>-<worker>.jsonl {key, shard, W, H, ...};
resumable (pages already in an index are skipped).
"""
from __future__ import annotations

import io
import json
import math
import os
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))

STORE_H = 96
MIN_PIXELS = 65_536          # Qwen3.5-4B preprocessor_config.json size.shortest_edge (read 2026-11-24, card/)
MAX_W = 8_192
FACTOR = 32                  # patch 16 x spatial merge 2
SHARD = 5000


def model_image(gray, H: int = 96):
    """numpy uint8 grey crop (any height) -> PIL RGB image of height H, width a multiple of 32, >= MIN_PIXELS."""
    import numpy as np
    from PIL import Image
    im = Image.fromarray(gray) if not isinstance(gray, Image.Image) else gray.convert("L")
    w, h = im.size
    W = max(1, int(round(w * H / h)))
    if W > MAX_W:
        W = MAX_W
    im = im.resize((W, H), Image.BICUBIC)
    Wp = max(math.ceil(W / FACTOR) * FACTOR, math.ceil(MIN_PIXELS / H / FACTOR) * FACTOR)
    canvas = Image.new("L", (Wp, H), 255)
    canvas.paste(im, (Wp - W, 0))                  # text kept at the right; white added at the left
    return canvas.convert("RGB")


def image_tokens(width: int, height: int) -> int:
    return (width // FACTOR) * (height // FACTOR)


def _put(tar, name, data: bytes):
    ti = tarfile.TarInfo(name)
    ti.size = len(data)
    ti.mtime = 0
    tar.addfile(ti, io.BytesIO(data))


def _work(args):
    wid, pages, outdir, tag = args
    import cv2
    import pypdfium2 as pdfium
    from common77 import azure_pages, clean_label, cut_line, encode, nonempty_lines, render_page
    cv2.setNumThreads(1)
    idx_p = Path(outdir) / f"index-{tag}-{wid}.jsonl"
    done = set()
    if idx_p.exists():
        for l in open(idx_p, encoding="utf-8"):
            d = json.loads(l)
            done.add((d["stem"], d["page"]))
    shard_no = len(list(Path(outdir).glob(f"{tag}-{wid}-*.tar")))
    tar, n_in, tar_name = None, SHARD, None
    idx = open(idx_p, "a", encoding="utf-8")
    cache = {}
    nl = mism = 0
    t0 = time.time()
    for (stem, page, pdf, az), lines in pages:
        if (stem, page) in done:
            continue
        if az not in cache:
            cache.clear()
            cache[az] = azure_pages(Path(az))
        pg = cache[az][page - 1]
        doc = pdfium.PdfDocument(pdf)
        img = render_page(doc, page - 1)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        by_i = {ln["i"]: ln for ln in nonempty_lines(pg)}
        rows, blobs = [], []
        for r in lines:
            ln = by_i.get(r["i"])
            if ln is None or not ln["poly"]:
                rows.append(dict(key=r["key"], stem=stem, page=page, cut=False, why="no line"))
                continue
            same = clean_label(ln["text"]) == r.get("azure_check", clean_label(ln["text"]))
            mism += not same
            crop, info = cut_line(img, ln["poly"], sx, sy, H=STORE_H, test=True)
            if crop is None:
                rows.append(dict(key=r["key"], stem=stem, page=page, cut=False, why=info.get("reason")))
                continue
            blobs.append((r["key"] + ".jpg", encode(crop, q=90)))
            rows.append(dict(key=r["key"], stem=stem, page=page, cut=True, W=int(crop.shape[1]), H=int(crop.shape[0]),
                             ang=info.get("ang"), azure_same=same))
        if blobs:
            if n_in + len(blobs) > SHARD and tar is not None:
                tar.close()
                os.rename(tar_name + ".part", tar_name)
                tar = None
            if tar is None:
                tar_name = str(Path(outdir) / f"{tag}-{wid}-{shard_no:03d}.tar")
                shard_no += 1
                tar, n_in = tarfile.open(tar_name + ".part", "w"), 0
            for name, data in blobs:
                _put(tar, name, data)
            n_in += len(blobs)
            tar.fileobj.flush()
        for r in rows:
            if r.get("cut"):
                r["shard"] = os.path.basename(tar_name)
            idx.write(json.dumps(r) + "\n")
        idx.flush()
        nl += len(rows)
    if tar is not None:
        tar.close()
        os.rename(tar_name + ".part", tar_name)
    idx.close()
    return wid, nl, mism, round(time.time() - t0)


def cmd_sets(outdir: str, workers: int, files: list[str], tag: str = "tr"):
    """Cut every line of the given set manifests (the union; S is inside M) from the local PDFs."""
    import gzip
    from multiprocessing import Pool
    os.makedirs(outdir, exist_ok=True)
    want = {}
    for f in files:
        for l in open(f, encoding="utf-8"):
            r = json.loads(l)
            if r["label_source"].startswith("azure"):
                r["azure_check"] = r["label"]          # the line id must still point at the same Azure line
            want[r["key"]] = r
    sys.path.insert(0, str(HERE))
    import guard102 as G
    G.assert_trainable(want)                       # nothing locked is ever cut for training or DEV
    paths = {}
    for l in gzip.open(HERE / "out/pool/pool102.jsonl.gz", "rt", encoding="utf-8"):
        r = json.loads(l)
        if r["key"] in want:
            paths[r["key"]] = (r["pdf"], r["azure"])
    by_page = defaultdict(list)
    for k, r in want.items():
        pdf, az = paths[k]
        by_page[(r["stem"], int(r["page"]), pdf, az)].append(r)
    pages = sorted(by_page.items(), key=lambda x: (x[0][0], x[0][1]))
    # documents stay together inside one worker (one JSON parse per document)
    per = [[] for _ in range(workers)]
    docs = sorted({p[0][0] for p in pages})
    wof = {d: i % workers for i, d in enumerate(docs)}
    for p in pages:
        per[wof[p[0][0]]].append(p)
    print(f"{len(want)} lines on {len(pages)} pages of {len(docs)} documents, {workers} workers", flush=True)
    with Pool(workers) as pool:
        for wid, nl, mism, sec in pool.imap_unordered(_work, [(i, per[i], outdir, tag) for i in range(workers)]):
            print(f"worker {wid}: {nl} lines, {mism} Azure-text mismatches, {sec} s", flush=True)


def cmd_exam(outdir: str):
    """Experiment 97's 600 R1 lines from the exam's own page images (packet image + Azure's box, the R1 crops' source),
    with the same padding and scale as training (a box is an upright polygon)."""
    import cv2
    import numpy as np
    from common77 import cut_line, encode
    os.makedirs(outdir, exist_ok=True)
    P97 = E / "97_extraction_evals/out"
    img_of = {}
    for pk in (P97 / "packets").glob("*/packet.json"):
        p = json.loads(pk.read_text())
        for pg in p["pages"]:
            img_of[(p["stem"], pg["page"])] = pg["image"]
    rows = []
    tar_name = os.path.join(outdir, "exam-000.tar")
    with tarfile.open(tar_name + ".part", "w") as tar:
        cache = {}
        for l in open(P97 / "reading/lines.jsonl", encoding="utf-8"):
            r = json.loads(l)
            key = f"{r['stem']}_p{r['page']:03d}_l{r['line']:03d}"
            ip = img_of[(r["stem"], r["page"])]
            if ip not in cache:
                cache.clear()
                cache[ip] = cv2.imread(ip, cv2.IMREAD_GRAYSCALE)
            x, y, w, h = r["box"]
            poly = [x, y, x + w, y, x + w, y + h, x, y + h]
            crop, info = cut_line(cache[ip], poly, 1.0, 1.0, H=STORE_H, test=True)
            if crop is None:
                rows.append(dict(key=key, cut=False, why=info.get("reason")))
                continue
            _put(tar, key + ".jpg", encode(crop, q=90))
            rows.append(dict(key=key, stem=r["stem"], page=r["page"], i=r["line"], kind=r["kind"], cut=True,
                             W=int(crop.shape[1]), H=int(crop.shape[0]), shard="exam-000.tar"))
    os.rename(tar_name + ".part", tar_name)
    with open(os.path.join(outdir, "index-exam.jsonl"), "w") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    print(len(rows), "exam lines,", sum(r["cut"] for r in rows), "cut")


def cmd_locked(outdir: str, workers: int = 3):
    """Experiment 90's locked lines (both sets: the 20 journals and the 280 old documents), cut ONLY for the final
    score, from experiment 90's own private copies (out/src) with experiment 90's line ids.  Refuses unless the lead has
    recorded the owner's OK for this read (LOCKED_OK102=1) and unless every key is locked (the inverse guard)."""
    from multiprocessing import Pool
    if os.environ.get("LOCKED_OK102") != "1":
        raise SystemExit("the locked lines are cut only for the final score, with the owner's OK (LOCKED_OK102=1)")
    sys.path.insert(0, str(E / "88_truth_and_lock"))
    import locked_old
    X = E / "90_locked_final/out"
    rows = [json.loads(l) for l in open(X / "readings90.jsonl", encoding="utf-8")]
    bad = [r["key"] for r in rows if not locked_old.is_locked_any(r["key"])]
    if bad:
        raise SystemExit(f"{len(bad)} keys are not locked: this command is for the locked test only, e.g. {bad[:3]}")
    os.makedirs(outdir, exist_ok=True)
    by_page = defaultdict(list)
    for r in rows:
        stem = r["stem"]
        by_page[(stem, int(r["page"]), str(X / "src" / f"{stem}.pdf"), str(X / "src" / f"{stem}.json"))].append(
            dict(key=r["key"], i=int(r["i"])))
    pages = sorted(by_page.items(), key=lambda x: (x[0][0], x[0][1]))
    docs = sorted({p[0][0] for p in pages})
    wof = {d: i % workers for i, d in enumerate(docs)}
    per = [[] for _ in range(workers)]
    for p in pages:
        per[wof[p[0][0]]].append(p)
    with Pool(workers) as pool:
        for res in pool.imap_unordered(_work, [(i, per[i], outdir, "locked") for i in range(workers)]):
            print("worker", res, flush=True)
    with open(HERE / "out/sets/locked.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(dict(key=r["key"], stem=r["stem"], page=r["page"], i=r["i"], era=r["era"], set=r["set"]),
                               ensure_ascii=False) + "\n")


if __name__ == "__main__":
    if sys.argv[1] == "locked":
        cmd_locked(sys.argv[2])
    elif sys.argv[1] == "sets":
        cmd_sets(sys.argv[2], int(sys.argv[3]), sys.argv[4:])
    elif sys.argv[1] == "exam":
        cmd_exam(sys.argv[2])
    else:
        raise SystemExit(__doc__)
