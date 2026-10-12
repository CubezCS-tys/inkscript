"""Kraken line recognition on line images (one image = one line), CPU, with a small process pool.

    nice out/env/bin/python krk.py MODEL LIST.txt OUT.jsonl [--workers 2] [--threads 4]
--seg baseline (default; a level baseline at --base 0.7 of the crop's height, the crop as boundary, which is what
models trained on baselines expect) or bbox. LIST.txt: one image path per line. OUT.jsonl: {"img": path, "text": ..., "conf": mean char confidence, "s": seconds}.
Resumes: images already in OUT.jsonl are skipped.
"""
import json, os, sys, time
from multiprocessing import Pool
from pathlib import Path

_net = None
SEG = "baseline"; BASE = 0.7


def _init(model, threads, seg="baseline", base=0.7):
    global _net, SEG, BASE
    SEG, BASE = seg, base
    import torch
    torch.set_num_threads(threads)
    if str(model).endswith(".mlmodel"):                               # the 2022 OpenITI model: the classic rpred path
        from kraken.lib import models
        _net = models.load_any(model, device="cpu")
    else:                                                              # kraken 7 weights (.safetensors): the task API
        from kraken.tasks.recognition import RecognitionTaskModel
        from kraken.configs import RecognitionInferenceConfig
        _net = (RecognitionTaskModel.load_model(model), RecognitionInferenceConfig(num_line_workers=0))


def read_line(path):
    from PIL import Image
    from kraken import rpred
    from kraken.containers import Segmentation, BBoxLine, BaselineLine
    t = time.time()
    try:
        im = Image.open(path).convert("L")
        if SEG == "bbox":
            seg = Segmentation(type="bbox", imagename=str(path), text_direction="horizontal-rl", script_detection=False,
                               lines=[BBoxLine(id="l0", bbox=(0, 0, im.width, im.height), text_direction="horizontal-rl")])
        else:                                                          # a level baseline at BASE of the height, the whole crop as boundary
            W, H = im.width, im.height; y = int(BASE * H)
            seg = Segmentation(type="baselines", imagename=str(path), text_direction="horizontal-rl", script_detection=False,
                               lines=[BaselineLine(id="l0", baseline=[(0, y), (W - 1, y)], boundary=[(0, 0), (W - 1, 0), (W - 1, H - 1), (0, H - 1)])])
        recs = list(_net[0].predict(im, seg, _net[1])) if isinstance(_net, tuple) else list(rpred.rpred(_net, im, seg))
        txt = recs[0].prediction if recs else ""
        conf = sum(recs[0].confidences) / len(recs[0].confidences) if recs and recs[0].confidences else None
        return dict(img=str(path), text=txt, conf=conf, s=round(time.time() - t, 3))
    except Exception as e:
        return dict(img=str(path), text="", conf=None, err=str(e)[:200], s=round(time.time() - t, 3))


if __name__ == "__main__":
    model, lst, out = sys.argv[1:4]
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 2
    th = int(sys.argv[sys.argv.index("--threads") + 1]) if "--threads" in sys.argv else 4
    if "--seg" in sys.argv:
        SEG = sys.argv[sys.argv.index("--seg") + 1]
    if "--base" in sys.argv:
        BASE = float(sys.argv[sys.argv.index("--base") + 1])
    paths = [l.strip() for l in open(lst) if l.strip()]
    done = set()
    if os.path.exists(out):
        done = {json.loads(l)["img"] for l in open(out)}
    todo = [p for p in paths if p not in done]
    print(f"{len(todo)} to read ({len(done)} done)", flush=True)
    t0 = time.time()
    with Pool(w, initializer=_init, initargs=(model, th, SEG, BASE)) as pool, open(out, "a") as f:
        for k, r in enumerate(pool.imap(read_line, todo, chunksize=8)):
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
            if k % 500 == 0:
                f.flush(); print(k, f"{time.time() - t0:.0f}s", flush=True)
    print("done", len(todo), f"{time.time() - t0:.0f}s")
