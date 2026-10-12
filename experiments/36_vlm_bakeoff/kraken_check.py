"""The Kraken checker on CPU (inference only): experiment 33's round-A Kraken (ftA.safetensors, no held-out journal
seen) reading the lines found by 33's fine-tuned line finder (segcpu.safetensors = train/segcpu/best_0.6511), page
by page, the way 33's fullpage.py does (find lines, then read each line).

    nice /home/yassine/inkscript/experiments/33_kraken/out/env/bin/python kraken_check.py JOBS.tsv [--workers 3] [--threads 4]
JOBS.tsv: page_id <TAB> image path. Writes out/kraken/<page_id>.json (skips pages already written):
    {"page_id", "reader": "kraken-ftA+segcpu", "image": {"width", "height"},
     "lines": [{"text", "box": [x0,y0,x1,y1], "baseline": [[x,y],...], "poly": [[x,y],...], "conf", "conf_min"}],
     "seg_s", "rec_s"}
in the page image's pixels, lines in the line finder's order (kraken's reading order), `inkscript score`'s pred format
plus extra fields. conf / conf_min: mean / lowest character confidence of the line.
"""
import json, sys, time
from multiprocessing import Pool
from pathlib import Path

E33 = Path("/home/yassine/inkscript/experiments/33_kraken/out")
REC = E33 / "models" / "ftA.safetensors"
SEGM = E33 / "models" / "segcpu.safetensors"
OUT = Path("/home/yassine/inkscript/experiments/36_vlm_bakeoff/out/kraken")
_rec = _seg = None


def _init(threads):
    global _rec, _seg
    import torch
    torch.set_num_threads(threads)
    from kraken.tasks.segmentation import SegmentationTaskModel
    from kraken.tasks.recognition import RecognitionTaskModel
    from kraken.configs import SegmentationInferenceConfig, RecognitionInferenceConfig
    # right-to-left reading order (the config's default is horizontal-lr, which 33's fullpage.py --segmodel kept: it
    # does not change a line's text, only the order of the lines)
    _seg = (SegmentationTaskModel.load_model(str(SEGM)), SegmentationInferenceConfig(text_direction="horizontal-rl", num_threads=threads))
    _rec = (RecognitionTaskModel.load_model(str(REC)), RecognitionInferenceConfig(num_line_workers=0, num_threads=threads))


def one(job):
    from PIL import Image
    pid, path = job
    try:
        im = Image.open(path).convert("L")
        t = time.time()
        seg = _seg[0].predict(im, _seg[1])
        seg_s = time.time() - t
        t = time.time(); lines = []
        for rec in (_rec[0].predict(im, seg, _rec[1]) if seg.lines else []):
            xs = [p[0] for p in rec.boundary]; ys = [p[1] for p in rec.boundary]
            c = list(rec.confidences or [])
            lines.append(dict(text=rec.prediction, box=[min(xs), min(ys), max(xs), max(ys)],
                              baseline=[list(map(int, p)) for p in rec.baseline], poly=[list(map(int, p)) for p in rec.boundary],
                              conf=round(sum(c) / len(c), 4) if c else None, conf_min=round(min(c), 4) if c else None))
        r = dict(page_id=pid, reader="kraken-ftA+segcpu", image=dict(width=im.width, height=im.height), lines=lines,
                 seg_s=round(seg_s, 1), rec_s=round(time.time() - t, 1))
        tmp = OUT / f"{pid}.json.tmp"
        tmp.write_text(json.dumps(r, ensure_ascii=False), encoding="utf-8"); tmp.replace(OUT / f"{pid}.json")
        return pid, len(lines), r["seg_s"], r["rec_s"], None
    except Exception as e:
        return pid, 0, 0, 0, repr(e)[:300]


if __name__ == "__main__":
    jobs = [tuple(l.rstrip("\n").split("\t")) for l in open(sys.argv[1]) if l.strip()]
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    th = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 4
    OUT.mkdir(parents=True, exist_ok=True)
    todo = [j for j in jobs if not (OUT / f"{j[0]}.json").exists()]
    print(len(todo), "pages to read of", len(jobs), flush=True)
    t0 = time.time()
    with Pool(w, initializer=_init, initargs=(th,)) as pool:
        for k, (pid, n, s1, s2, err) in enumerate(pool.imap_unordered(one, todo)):
            print(k, pid, n, s1, s2, err or "", f"{time.time() - t0:.0f}s", flush=True)
    print("done", f"{time.time() - t0:.0f}s", flush=True)
