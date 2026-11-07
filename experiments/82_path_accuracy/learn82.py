"""Experiment 82, step 3: train the learned path rebuilder, and use it.

    python learn82.py train --data /work/d82 --name u1 --steps 20000            (GPU)
    python learn82.py shape --model /work/out/u1/model.pt --lines out/shape_modern/lines.json --out out/learned/u1/modern
              -> the predicted centre line of every shape-test line at every level (cl/<i>_<level>.npz), for shape82.py
    python learn82.py feats --model ... --data /work/d82 --split reader --workers 16 --out /work/r82
              -> reader signals: rule-rebuilt (rclean, rdmg) and learned-rebuilt (lclean, ldmg), exp 79's format

Training: random 96 x 320 windows of the gen82 samples; loss = centre line (BCE against a 1-px truth line blurred to a
ridge, the line weighted 10x) + direction (MSE of cos 2a / sin 2a on the line) + counters (BCE, weighted 4x).
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import sys
import time
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402
import torch.nn.functional as F  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from net82 import UNet, decode, predict, prep  # noqa: E402

cv2.setNumThreads(1)
CROP = 320


def unpack(z_bits, shape):
    h, w = int(shape[0]), int(shape[1])
    return np.unpackbits(z_bits)[:h * w].reshape(h, w).astype(bool)


def targets(cl: np.ndarray, ctr: np.ndarray):
    """1-px truth line -> (ridge heat, cos2a, sin2a, direction mask, counter)."""
    d = cv2.distanceTransform((~cl).astype(np.uint8), cv2.DIST_L2, 3)
    heat = np.exp(-(d ** 2) / 2.0).astype(np.float32)
    b = cv2.GaussianBlur(cl.astype(np.float32), (0, 0), 1.5)
    gx = cv2.Sobel(b, cv2.CV_32F, 1, 0, ksize=3)
    gy = cv2.Sobel(b, cv2.CV_32F, 0, 1, ksize=3)
    jxx = cv2.GaussianBlur(gx * gx, (0, 0), 1.5)
    jyy = cv2.GaussianBlur(gy * gy, (0, 0), 1.5)
    jxy = cv2.GaussianBlur(gx * gy, (0, 0), 1.5)
    th = 0.5 * np.arctan2(2 * jxy, jxx - jyy)                          # gradient axis; the line runs across it
    c2, s2 = -np.cos(2 * th), -np.sin(2 * th)
    mask = (d <= 1.5) & ((jxx + jyy) > 1e-6)
    return heat, c2.astype(np.float32), s2.astype(np.float32), mask, ctr.astype(np.float32)


class Pairs(torch.utils.data.Dataset):
    def __init__(self, files, val=False):
        self.items = []
        for f in files:
            z = np.load(f, allow_pickle=True)
            ig = z["ign"] if "ign" in z.files else [None] * len(z["grey"])
            for g, c, t, s, i in zip(z["grey"], z["cl"], z["ctr"], z["shape"], ig):
                self.items.append((g, c, t, s, i))
        self.val = val

    def __len__(self):
        return len(self.items)

    def __getitem__(self, j):
        g, c, t, s, i = self.items[j]
        grey = cv2.imdecode(np.frombuffer(g, np.uint8), cv2.IMREAD_GRAYSCALE)
        cl, ctr = unpack(c, s), unpack(t, s)
        ign = unpack(i, s) if i is not None else np.zeros_like(cl)
        rng = random.Random(j if self.val else None)
        H, W = grey.shape
        if W > CROP:
            x0 = rng.randrange(W - CROP + 1)
            grey, cl, ctr, ign = grey[:, x0:x0 + CROP], cl[:, x0:x0 + CROP], ctr[:, x0:x0 + CROP], ign[:, x0:x0 + CROP]
        else:
            p = CROP - W
            grey = np.pad(grey, ((0, 0), (0, p)), constant_values=int(np.median(grey)))
            cl, ctr, ign = np.pad(cl, ((0, 0), (0, p))), np.pad(ctr, ((0, 0), (0, p))), np.pad(ign, ((0, 0), (0, p)))
        if not self.val:                                               # light photometric jitter
            gf = grey.astype(np.float32)
            gf = (gf - 128) * rng.uniform(0.7, 1.2) + 128 + rng.uniform(-25, 25)
            grey = np.clip(gf, 0, 255).astype(np.uint8)
        heat, c2, s2, m, ct = targets(cl, ctr)
        x = (255.0 - grey.astype(np.float32)) / 255.0
        keep = (~ign).astype(np.float32)
        return (torch.from_numpy(x)[None], torch.from_numpy(np.stack([heat, c2, s2, ct])),
                torch.from_numpy(np.stack([m.astype(np.float32) * keep, keep])))


def loss_fn(y, T, M):
    heat, ct = T[:, 0:1], T[:, 3:4]
    m, keep = M[:, 0:1], M[:, 1:2]
    w = (1 + 9 * heat) * keep
    l_cl = (F.binary_cross_entropy_with_logits(y[:, 0:1], heat, reduction="none") * w).mean()
    l_dir = (((torch.tanh(y[:, 1:3]) - T[:, 1:3]) ** 2) * m).sum() / (m.sum() * 2 + 1)
    l_ct = (F.binary_cross_entropy_with_logits(y[:, 3:4], ct, reduction="none") * (1 + 3 * ct) * keep).mean()
    return l_cl + 0.5 * l_dir + 0.5 * l_ct, (l_cl.item(), l_dir.item(), l_ct.item())


@torch.no_grad()
def val_f1(model, dl, dev, tol=2):
    model.eval()
    tp = fp = fn = 0
    for X, T, _ in dl:
        y = torch.sigmoid(model(X.to(dev))[:, 0]).float().cpu().numpy()
        for k in range(len(y)):
            tl = (T[k, 0].numpy() > 0.99)
            pl = decode(np.stack([y[k], 0 * y[k], 0 * y[k], 0 * y[k]]))
            dt_t = cv2.distanceTransform((~tl).astype(np.uint8), cv2.DIST_L2, 3)
            dt_p = cv2.distanceTransform((~pl).astype(np.uint8), cv2.DIST_L2, 3)
            tp += int((pl & (dt_t <= tol)).sum())
            fp += int((pl & (dt_t > tol)).sum())
            fn += int((tl & (dt_p > tol)).sum())
    model.train()
    p, r = tp / max(1, tp + fp), tp / max(1, tp + fn)
    return dict(precision=round(p, 4), recall=round(r, 4), f1=round(2 * p * r / max(1e-9, p + r), 4))


def train(a):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    torch.manual_seed(82)
    torch.backends.cudnn.benchmark = True
    od = Path(a.out) / a.name
    od.mkdir(parents=True, exist_ok=True)
    log = open(od / "train.log", "a")

    def P(*s):
        msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in s)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    files = sorted(glob.glob(f"{a.data}/unet-*.npz"))
    vf, tf = files[:1], files[1:] or files
    ds, dv = Pairs(tf), Pairs(vf, val=True)
    dv.items = dv.items[:a.val]
    P(f"train {len(ds)} val {len(dv)} device {dev}")
    dl = torch.utils.data.DataLoader(ds, batch_size=a.batch, shuffle=True, num_workers=a.workers, drop_last=True,
                                     persistent_workers=True, pin_memory=dev.type == "cuda")
    dlv = torch.utils.data.DataLoader(dv, batch_size=a.batch, num_workers=2)
    model = UNet().to(dev)
    P(f"parameters {sum(p.numel() for p in model.parameters()) / 1e6:.2f} M")
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=1e-4)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=a.steps, pct_start=0.05)
    step, t0, acc = 0, time.time(), np.zeros(4)
    while step < a.steps:
        for X, T, M in dl:
            X, T, M = X.to(dev, non_blocking=True), T.to(dev, non_blocking=True), M.to(dev, non_blocking=True)
            with torch.autocast(dev.type, dtype=torch.bfloat16, enabled=dev.type == "cuda"):
                y = model(X)
            loss, parts = loss_fn(y.float(), T, M)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            acc += np.array([loss.item(), *parts])
            if step % 200 == 0:
                P(f"step {step}/{a.steps} loss {acc[0] / 200:.4f} (cl {acc[1] / 200:.4f} dir {acc[2] / 200:.4f} "
                  f"ctr {acc[3] / 200:.4f}) {time.time() - t0:.0f}s")
                acc[:] = 0
            if step % a.eval_every == 0 or step == a.steps:
                P(f"val {step}", val_f1(model, dlv, dev))
                torch.save(dict(model=model.state_dict(), step=step), od / "model.pt")
            if step >= a.steps:
                break
    P("done", round((time.time() - t0) / 60, 1), "min")


def load_model(path, dev):
    model = UNet().to(dev)
    model.load_state_dict(torch.load(path, map_location=dev)["model"])
    model.eval()
    return model


def shape(a):
    """Predicted centre lines of the shape-test lines (same damage seeds as shape82.py)."""
    import lines82 as L
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(a.model, dev)
    specs = json.loads(Path(a.lines).read_text(encoding="utf-8"))
    od = Path(a.out) / "cl"
    od.mkdir(parents=True, exist_ok=True)
    for i, spec in enumerate(specs[:a.n or None]):
        grey, owner, ink = L.render(spec)
        for lv in a.levels.split(","):
            g = L.damaged(grey, lv, spec["seed"] + 7919 * L.LEVELS.index(lv))
            y = predict(model, g, dev)
            np.savez_compressed(od / f"{i:04d}_{lv}.npz", cl=decode(y, a.thr), ctr=(y[3] > 0.5))
        if i % 50 == 0:
            print(i, flush=True)


def _feat_job(args):
    grey_png, clean_png, cl_d, cl_c = args
    import path82 as PP
    from sig79 import features
    g = cv2.imdecode(np.frombuffer(grey_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    c = cv2.imdecode(np.frombuffer(clean_png, np.uint8), cv2.IMREAD_GRAYSCALE)
    out = {}
    for k, (img, m, cl) in {"rclean": (c, "skeleton", None), "rdmg": (g, "skeleton", None),
                            "lclean": (c, "learned", cl_c), "ldmg": (g, "learned", cl_d)}.items():
        try:
            ink = (c < 128) if k == "rclean" else None              # exp 79's rclean: the rendered ink itself
            out[k] = features(PP.rebuild(img, m, ink=ink, cl=cl)).astype(np.float16)
        except Exception:  # noqa: BLE001
            out[k] = np.zeros((0, 13), np.float16)
    return out


def feats(a):
    """Reader signals for one split: rule (skeleton) and learned rebuilds of the clean and the damaged crop."""
    from multiprocessing import Pool
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = load_model(a.model, dev)
    Path(a.out).mkdir(parents=True, exist_ok=True)
    pool = Pool(a.workers, maxtasksperchild=200)
    for f in sorted(glob.glob(f"{a.data}/{a.split}-*.npz")):
        name = Path(f).stem
        if (Path(a.out) / f"{name}.npz").exists():
            continue
        z = np.load(f, allow_pickle=True)
        meta = [json.loads(l) for l in open(f[:-4] + ".jsonl", encoding="utf-8")]
        t0 = time.time()
        cls = []
        for gp, cp in zip(z["grey"], z["clean"]):
            pair = []
            for p in (gp, cp):
                g = cv2.imdecode(np.frombuffer(p, np.uint8), cv2.IMREAD_GRAYSCALE)
                pair.append(decode(predict(model, g, dev), a.thr))
            cls.append(pair)
        t1 = time.time()
        res = pool.map(_feat_job, [(gp, cp, d, c) for gp, cp, (d, c) in zip(z["grey"], z["clean"], cls)], chunksize=8)
        arrs = {}
        for k in ("rclean", "rdmg", "lclean", "ldmg"):
            L_ = [r[k] for r in res]
            arrs[k] = np.concatenate(L_) if L_ else np.zeros((0, 13), np.float16)
            arrs[k + "_off"] = np.cumsum([0] + [len(x) for x in L_]).astype(np.int64)
        np.savez(Path(a.out) / f"{name}.npz", **arrs)
        with open(Path(a.out) / f"{name}.jsonl", "w", encoding="utf-8") as fo:
            for m in meta:
                fo.write(json.dumps(m, ensure_ascii=False) + "\n")
        print(name, len(meta), f"predict {t1 - t0:.0f}s rebuild {time.time() - t1:.0f}s", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("mode", choices=["train", "shape", "feats"])
    ap.add_argument("--data", default="/work/d82")
    ap.add_argument("--out", default="/work/out")
    ap.add_argument("--name", default="u1")
    ap.add_argument("--steps", type=int, default=20000)
    ap.add_argument("--batch", type=int, default=32)
    ap.add_argument("--lr", type=float, default=2e-3)
    ap.add_argument("--workers", type=int, default=12)
    ap.add_argument("--val", type=int, default=512)
    ap.add_argument("--eval-every", type=int, default=2000)
    ap.add_argument("--model", default="")
    ap.add_argument("--lines", default="")
    ap.add_argument("--levels", default="clean,mild,heavy,spread,fill")
    ap.add_argument("--n", type=int, default=0)
    ap.add_argument("--thr", type=float, default=0.5)
    ap.add_argument("--split", default="reader")
    a = ap.parse_args()
    if a.mode == "train":
        torch.set_num_threads(4)
        train(a)
    elif a.mode == "shape":
        shape(a)
    else:
        feats(a)


if __name__ == "__main__":
    main()
