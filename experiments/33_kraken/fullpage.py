"""Kraken on whole pages with its own line finder (blla, the default segmentation model shipped with kraken 7.1.1).

    nice out/env/bin/python fullpage.py MODEL TAG [--workers 2] [--threads 4] [--scan] [--segmodel SEG.safetensors]
Born-digital: the first drawn page of every test document, rendered at 300 dpi, clean and as a scan-like copy
(degrade.py without skew, so the gold boxes stay where they are). --scan: the scanned pages of the real-scan sample
(one page per scanned document, the page with the most judged words).
Writes out/pages/<TAG>.jsonl: {doc, page, variant, lines: [{bbox px, baseline, text, conf}], seg_s, rec_s}.
The segmentation of a page is cached (out/pages/seg/...json) and reused by every recognition model.
"""
import json, os, sys, time, zlib
from multiprocessing import Pool
from pathlib import Path

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
DPI = 300
_net = None


SEGM = None                                                            # --segmodel: a fine-tuned line finder (task API)
_seg = None


def _init(model, threads, segm=None):
    global _net, SEGM, _seg
    SEGM = segm
    if segm:
        from kraken.tasks.segmentation import SegmentationTaskModel
        from kraken.configs import SegmentationInferenceConfig
        _seg = (SegmentationTaskModel.load_model(segm), SegmentationInferenceConfig())
    import torch
    torch.set_num_threads(threads)
    if str(model).endswith(".mlmodel"):
        from kraken.lib import models
        _net = models.load_any(model, device="cpu")
    else:                                                              # kraken 7 weights: the task API (as krk.py)
        from kraken.tasks.recognition import RecognitionTaskModel
        from kraken.configs import RecognitionInferenceConfig
        _net = (RecognitionTaskModel.load_model(model), RecognitionInferenceConfig(num_line_workers=0))


def page_image(pdf, pno, variant):
    import pymupdf
    from PIL import Image
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from degrade import degrade
    doc = pymupdf.open(str(pdf)); pix = doc[pno - 1].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
    if variant == "deg":
        im = degrade(im, zlib.crc32(f"{pdf.name}:{pno}".encode()), skew=False)
    return im


def one(job):
    from kraken import blla, rpred
    from kraken.containers import Segmentation
    doc_id, pdf, pno, variant = job
    im = page_image(Path(pdf), pno, variant)
    sp = OUT / "pages" / "seg" / f"{doc_id}_p{pno}_{variant}{'_' + Path(SEGM).stem if SEGM else ''}.json"
    t = time.time()
    if sp.exists():
        import dataclasses
        from kraken.containers import BaselineLine
        d = json.load(open(sp))
        seg = Segmentation(type="baselines", imagename="page", text_direction="horizontal-rl", script_detection=False,
                           lines=[BaselineLine(id=l["id"], baseline=[tuple(p) for p in l["baseline"]], boundary=[tuple(p) for p in l["boundary"]])
                                  for l in d["lines"]])
        seg_s = d["seg_s"]
    else:
        seg = _seg[0].predict(im, _seg[1]) if _seg else blla.segment(im, text_direction="horizontal-rl")
        seg_s = time.time() - t
        json.dump(dict(seg_s=seg_s, lines=[dict(id=l.id, baseline=[list(map(int, p)) for p in l.baseline],
                                                 boundary=[list(map(int, p)) for p in l.boundary]) for l in seg.lines]), open(sp, "w"))
    t = time.time(); lines = []
    for rec in (_net[0].predict(im, seg, _net[1]) if isinstance(_net, tuple) else rpred.rpred(_net, im, seg)):
        xs = [p[0] for p in rec.boundary]; ys = [p[1] for p in rec.boundary]
        lines.append(dict(bbox=[min(xs), min(ys), max(xs), max(ys)], baseline=[list(map(int, p)) for p in rec.baseline],
                          text=rec.prediction, conf=(sum(rec.confidences) / len(rec.confidences)) if rec.confidences else None))
    return dict(doc=doc_id, page=pno, variant=variant, lines=lines, seg_s=round(seg_s, 1), rec_s=round(time.time() - t, 1))


def jobs(scan: bool):
    if scan:
        seen = {}
        for l in open(OUT / "scan" / "scan.jsonl"):
            r = json.loads(l); seen.setdefault(r["doc"], {}).setdefault(r["page"], 0); seen[r["doc"]][r["page"]] += 1
        return [(d, str(E19 / "docs" / d / f"{d}.pdf"), max(p, key=p.get), "scan") for d, p in sorted(seen.items())]
    sp = json.load(open(OUT / "splits.json")); out = []
    for d, info in sorted(sp["docs"].items()):
        if info.get("status") == "ok" and info.get("split") == "test" and info.get("drawn"):
            pdf = next(p for p in [E19 / "docs" / d / f"{d}.pdf", OUT / "docs" / d / f"{d}.pdf"] if p.exists())
            for v in ("clean", "deg"):
                out.append((d, str(pdf), info["drawn"][0], v))
    return out


if __name__ == "__main__":
    model, tag = sys.argv[1:3]
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 2
    th = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 4
    segm = sys.argv[sys.argv.index("--segmodel") + 1] if "--segmodel" in sys.argv else None
    (OUT / "pages" / "seg").mkdir(parents=True, exist_ok=True)
    out = OUT / "pages" / f"{tag}.jsonl"
    done = set()
    if out.exists():
        done = {(r["doc"], r["page"], r["variant"]) for r in map(json.loads, open(out))}
    todo = [j for j in jobs("--scan" in sys.argv) if (j[0], j[2], j[3]) not in done]
    print(len(todo), "pages", flush=True)
    t0 = time.time()
    with Pool(w, initializer=_init, initargs=(model, th, segm)) as pool, open(out, "a") as f:
        for k, r in enumerate(pool.imap_unordered(one, todo)):
            f.write(json.dumps(r, ensure_ascii=False) + "\n"); f.flush()
            print(k, r["doc"], r["variant"], len(r["lines"]), r["seg_s"], r["rec_s"], f"{time.time() - t0:.0f}s", flush=True)
