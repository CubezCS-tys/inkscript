"""Experiment 58: run Indra OCR (local, CPU) on a list of pages; one JSON per page.

    nice -n 19 out/venv/bin/python run58.py --units out/units_<set>.json --variant <name> [--dpi 200] [--mode ocr]
        [--workers 8] [--math] [--scale 1.0]

A unit is {"id": "<stem>_pNNN", "image": path} (a 300 dpi page image) or {"id", "pdf": path, "page": n (1-based)}.
Each worker is one process with one ONNX thread (Indra's own parallel layout).  Output:
out/indra/<variant>/<id>.json = Indra's page (lines, blocks, markdown, timings) + our wall time and the scale applied
to an image (boxes are put back into the 300 dpi frame).  Resumable: existing outputs are skipped.  Nothing leaves
the machine: models are read from out/models.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import asdict
from multiprocessing import Pool
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
MODELS = OUT / "models"
os.environ.setdefault("OMP_NUM_THREADS", "1")
os.environ["HF_HUB_OFFLINE"] = "1"

_conv = None
_cfg = {}


def _init(cfg):
    global _conv, _cfg
    import cv2
    import indra_ocr
    cv2.setNumThreads(1)
    _cfg = cfg
    _conv = indra_ocr.load(path=str(MODELS), threads=1, dpi=cfg["dpi"], mode=cfg["mode"], furniture=True,
                           math=cfg["math"])


def _page_dict(page, scale=1.0):
    def sb(b):
        return [round(v / scale, 1) for v in b]
    lines = [asdict(ln) for ln in page.lines]
    for ln in lines:
        ln["box"] = sb(ln["box"])
    blocks = [dict(b, bbox=sb(b["bbox"])) for b in page.blocks]
    return dict(source=page.source, rotation=page.rotation, skew=page.skew, note=page.note, lines=lines,
                blocks=blocks, markdown=page.markdown, timings=page.timings)


def _run(u):
    import cv2
    import numpy as np
    dst = Path(_cfg["dst"]) / f"{u['id']}.json"
    t0 = time.perf_counter()
    try:
        if "image" in u:
            g = cv2.imread(u["image"], cv2.IMREAD_GRAYSCALE)
            s = _cfg["scale"]
            if s != 1.0:
                g = cv2.resize(g, (int(g.shape[1] * s), int(g.shape[0] * s)),
                               interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_CUBIC)
            if _cfg.get("prep") == "otsu":
                g = cv2.threshold(cv2.GaussianBlur(g, (3, 3), 0), 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)[1]
            elif _cfg.get("prep") == "clahe":
                g = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8)).apply(g)
            elif _cfg.get("prep") == "sharpen":
                g = cv2.addWeighted(g, 1.6, cv2.GaussianBlur(g, (0, 0), 2), -0.6, 0)
            page = _conv.ocr(np.ascontiguousarray(g))
            d = _page_dict(page, s)
        else:
            import pypdfium2 as pdfium
            doc = pdfium.PdfDocument(u["pdf"])
            page = _conv.pdf_page(u["pdf"], doc, u["page"] - 1)
            d = _page_dict(page, _cfg["dpi"] / 300.0)   # back to the 300 dpi frame of Azure's boxes
            doc.close()
        d["wall_ms"] = round(1000 * (time.perf_counter() - t0), 1)
        d["id"] = u["id"]
        dst.write_text(json.dumps(d, ensure_ascii=False), encoding="utf-8")
        return u["id"], d["wall_ms"], None
    except Exception as e:  # noqa: BLE001
        return u["id"], None, repr(e)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--units", required=True)
    ap.add_argument("--variant", required=True)
    ap.add_argument("--dpi", type=float, default=200.0)
    ap.add_argument("--mode", default="ocr")
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--math", action="store_true")
    ap.add_argument("--scale", type=float, default=1.0, help="resize page images by this factor first")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--prep", default="", help="image preprocessing before Indra: otsu | clahe | sharpen")
    a = ap.parse_args()
    if a.workers > 8:
        sys.exit("at most 8 workers on this shared machine")
    dst = OUT / "indra" / a.variant
    dst.mkdir(parents=True, exist_ok=True)
    units = json.loads(Path(a.units).read_text())
    units = [u for u in units if not (dst / f"{u['id']}.json").exists()]
    if a.limit:
        units = units[:a.limit]
    cfg = dict(dpi=a.dpi, mode=a.mode, math=a.math, scale=a.scale, dst=str(dst), prep=a.prep)
    print(f"{len(units)} pages to run, variant {a.variant}, {a.workers} workers", flush=True)
    t0 = time.perf_counter()
    done = errs = 0
    log = open(dst / "_run.log", "a")
    with Pool(a.workers, initializer=_init, initargs=(cfg,)) as pool:
        for uid, ms, err in pool.imap_unordered(_run, units, chunksize=1):
            done += 1
            if err:
                errs += 1
                print(f"ERR {uid} {err}", file=log, flush=True)
            if done % 200 == 0:
                el = time.perf_counter() - t0
                print(f"{done}/{len(units)} {el:.0f}s {done / el:.2f} pages/s errors {errs}", flush=True)
    el = time.perf_counter() - t0
    summ = dict(variant=a.variant, pages=done, errors=errs, seconds=round(el, 1),
                pages_per_s=round(done / el, 2) if el else None, workers=a.workers, dpi=a.dpi, mode=a.mode,
                scale=a.scale, math=a.math, prep=a.prep, at=time.strftime("%Y-%m-%d %H:%M:%S"))
    print(json.dumps(summ), file=log, flush=True)
    print(json.dumps(summ))


if __name__ == "__main__":
    main()
