"""Experiment 82, step 3: training pairs for the learned path rebuilder (and lines for the downstream reader).

    python gen82.py --set unet --n 80000 --workers 16 --out /work/d82      (on the rented host's CPUs)
    python gen82.py --set reader --n 60000 ...  /  --set test --n 3000 ...

Every sample is a 96-px line crop with its damage, and the truth the network learns:
  grey   - the damaged crop (PNG bytes)
  clean  - the clean crop (PNG bytes; reader sets only: exp 79's rclean is rebuilt from it)
  cl     - the TRUE centre line, 1 px (packed bits):
             fonts:  the thinned clean ink (the skeleton of the clean glyphs: loops open, strokes whole)
             ADAB:   the real pen trajectory itself
  ctr    - the counters of the CLEAN ink (paper enclosed by a loop), packed bits: what a filled head hides
  ign    - where the loss looks away: round a loop letter whose own glyph has no counter (the traced old faces draw
           most heads filled, so their skeleton has no loop to learn from)
Sources (unet set; weights in SRC):
  (a) font    - exp 78's OFL faces (Mirza held out), exp 78's text (exp 79's test-hash lines and the shape test lines
                never used), rendered by synth79 with known letters
  (b) adab    - ADAB's real pen trajectories (CC BY 4.0; set_1/set_2 here, set_3 held out for testing) drawn as PRINT-like
                ink: a broad nib 3.5-8 px wide at a random angle, then the same damage
  (c) traced  - exp 78's typefaces traced from our old scans (exclude.json respected, lines82.allowed)
Damage: clean / mild / heavy / spread / fill (lines82) with weights 1 / 2 / 2 / 2 / 2.
Shards: <out>/<set>-<w>.npz (object arrays) + .jsonl (text, label, font, level, src).
"""
from __future__ import annotations

import argparse
import glob
import gzip
import json
import os
import random
import re
import sys
import time
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

LEVELS = ["clean", "mild", "heavy", "spread", "fill"]
LEVEL_W = [1, 2, 2, 2, 2]
SRC = {"font": 6, "adab": 2, "traced": 2}
H = 96


def counters_of(ink: np.ndarray) -> np.ndarray:
    n, lab, st, _ = cv2.connectedComponentsWithStats((~ink.astype(bool)).astype(np.uint8), connectivity=4)
    out = np.zeros(ink.shape, bool)
    Hh, W = ink.shape
    for k in range(1, n):
        x, y, w, h, a = st[k]
        if a >= 4 and x > 0 and y > 0 and x + w < W and y + h < Hh:
            out[lab == k] = True
    return out


def png(a: np.ndarray) -> bytes:
    return cv2.imencode(".png", a)[1].tobytes()


# ------------------------------------------------------------------------------------------------ ADAB as print

TRACE = re.compile(r"<trace[^>]*>([^<]*)</trace>")
LABEL = re.compile(r'<alternate value="([^"]*)"')


def adab_files(root: str, sets=("set_1", "set_2")):
    out = []
    for s in sets:
        for f in sorted(glob.glob(f"{root}/{s}/inkml/*.inkml")):
            u = Path(f).parent.parent / "upx" / (Path(f).stem + ".upx")
            out.append((f, str(u)))
    return out


def adab_strokes(path: str):
    out = []
    for t in TRACE.findall(Path(path).read_text(encoding="ascii", errors="ignore")):
        pts = [p.split() for p in t.strip().split(",") if p.strip()]
        a = np.array([[float(p[1]), float(p[0])] for p in pts if len(p) >= 2])       # (y, x)
        if len(a):
            out.append(a)
    return out


def adab_render(strokes, rng: random.Random):
    """Real pen strokes -> (grey crop, true centre line, clean ink): a broad-nib print-like rendering at 96 px."""
    from sig79 import resample, smooth
    allp = np.vstack(strokes)
    h = max(1.0, np.ptp(allp[:, 0]))
    s = rng.uniform(40, 64) / h
    S = [(p - allp.min(0)) * s for p in strokes]
    wid = max(np.ptp(np.vstack(S)[:, 1]), 1)
    W = int(wid + rng.uniform(0.4, 0.9) * H)
    oy = rng.uniform(0.12, 0.88 - (np.ptp(np.vstack(S)[:, 0]) / H)) * H if np.ptp(np.vstack(S)[:, 0]) < 0.76 * H else 6
    ox = rng.uniform(0.15, 0.35) * H
    S = [p + np.array([oy, ox]) for p in S]
    w0 = rng.uniform(3.5, 8.0)
    nib = rng.uniform(np.radians(25), np.radians(65))
    k = 4                                                              # draw at 4x, area-downsample
    big = np.zeros((H * k, W * k), np.uint8)
    cl = np.zeros((H, W), np.uint8)
    for p in S:
        q = smooth(resample(p, 0.7), 2) if len(p) > 1 else p
        if len(q) == 1:
            cv2.circle(big, (int(q[0][1] * k), int(q[0][0] * k)), int(w0 * k / 2), 255, -1, cv2.LINE_AA)
            cl[int(np.clip(q[0][0], 0, H - 1)), int(np.clip(q[0][1], 0, W - 1))] = 1
            continue
        d = np.gradient(q, axis=0)
        ang = np.arctan2(d[:, 0], d[:, 1])
        for i in range(len(q)):
            r = w0 * (0.5 + 0.5 * abs(np.sin(ang[i] - nib))) / 2
            cv2.circle(big, (int(q[i][1] * k), int(q[i][0] * k)), max(1, int(r * k)), 255, -1, cv2.LINE_AA)
        qi = np.round(q).astype(np.int32)
        cv2.polylines(cl, [qi[:, ::-1].reshape(-1, 1, 2)], False, 1, 1)
    ink = cv2.resize(big, (W, H), interpolation=cv2.INTER_AREA) >= 128
    grey = np.where(ink, 25, 245).astype(np.uint8)
    grey = cv2.GaussianBlur(grey, (3, 3), 0.6)
    return grey, cl.astype(bool) & (cv2.dilate(ink.astype(np.uint8), np.ones((3, 3), np.uint8)) > 0), ink


# ------------------------------------------------------------------------------------------------ one sample

def sample(src: str, rng: random.Random, texts, adab, want_clean: bool):
    import lines82 as L
    import synth79 as SY
    from data79 import clean_label, cut
    from sig79 import thin
    if src == "adab":
        f, u = adab[rng.randrange(len(adab))]
        st = adab_strokes(f)
        if not st:
            return None
        grey, cl, ink = adab_render(st, rng)
        m = LABEL.search(Path(u).read_text(encoding="utf-8", errors="ignore")) if Path(u).exists() else None
        import html
        text = html.unescape(m.group(1)) if m else ""
        font = "adab"
    else:
        fonts = L.MODERN[:-1] if src == "font" else L.TRACED                 # Mirza (last of MODERN) held out
        for _ in range(30):
            text = cut(rng.choice(texts), rng)
            font = rng.choice(fonts)
            if len(text) >= 6 and L.allowed(text, font) and SY.covers(L.FONTS / font, text):
                break
        else:
            return None
        SY.H = H
        grey, owner, ink = SY.render(text, L.FONTS / font, px_per_em=62.0 * rng.uniform(0.85, 1.15))
        cl = thin(ink).astype(bool)
        # a loop letter drawn FILLED in its glyph (the traced old faces print most heads of و ف ق م ه filled): its
        # skeleton has no loop, which would teach the network to collapse loops; the loss ignores it instead
        ign = np.zeros(ink.shape, bool)
        for c in (np.unique(owner) if src == "traced" else []):          # modern faces: an open head (initial ع) is real
            if c >= 0 and c < len(text) and text[c] in L.LOOPS:
                m = owner == c
                if not counters_of(m).any():
                    ign |= cv2.dilate(m.astype(np.uint8), np.ones((5, 5), np.uint8)) > 0
    level = rng.choices(LEVELS, LEVEL_W)[0]
    g = L.damaged(grey, level, rng.randrange(1 << 30))
    d = dict(grey=png(g), cl=np.packbits(cl), ctr=np.packbits(counters_of(ink)), shape=np.array(g.shape))
    if src != "adab":
        d["ign"] = np.packbits(ign)
    if want_clean:
        d["clean"] = png(grey)
    meta = dict(text=text, label=clean_label(text), font=Path(font).stem, level=level, src=src)
    return d, meta


def load_texts(test: bool):
    import lines82 as L
    import synth79 as SY
    from data79 import is_test_text
    out = []                    # the shape test lines come from corpus lines i % 50 == 23 (lines82.texts): never here
    with gzip.open(os.environ.get("TEXT82", str(SY.TEXT)), "rt", encoding="utf-8") as f:
        for i, l in enumerate(f):
            t = json.loads(l)["t"]
            if len(t.split()) < 2:
                continue
            if test == is_test_text(t) and (test or (i % 50) not in (7, 23)):
                out.append(t)
    return out


def work(args):
    wid, set_, n, out, adab_root = args
    rng = random.Random(8200 + 31 * wid + {"unet": 0, "reader": 1, "test": 2}[set_] * 1000)
    texts = load_texts(set_ == "test")
    adab = adab_files(adab_root, ("set_3",) if set_ == "test" else ("set_1", "set_2")) if set_ == "unet" else []
    srcs = SRC if set_ == "unet" else {"font": 8, "traced": 2}
    names, weights = list(srcs), list(srcs.values())
    cols = {k: [] for k in ("grey", "cl", "ctr", "shape", "clean", "ign")}
    meta = []
    t0 = time.time()
    while len(meta) < n:
        src = rng.choices(names, weights)[0]
        try:
            r = sample(src, rng, texts, adab, want_clean=set_ != "unet")
        except Exception as e:  # noqa: BLE001
            print(wid, "error", type(e).__name__, str(e)[:100], flush=True)
            continue
        if r is None:
            continue
        d, m = r
        for k in cols:
            if k in d:
                cols[k].append(d[k])
            elif k == "ign":
                cols[k].append(np.packbits(np.zeros(int(np.prod(d["shape"])), bool)))
        meta.append(m)
        if len(meta) % 1000 == 0:
            print(f"w{wid} {set_} {len(meta)}/{n} {time.time() - t0:.0f}s", flush=True)
    arr = {}
    for k, v in cols.items():
        if v:
            a = np.empty(len(v), object)
            a[:] = v
            arr[k] = a
    np.savez(Path(out) / f"{set_}-{wid:02d}.npz", **arr)
    with open(Path(out) / f"{set_}-{wid:02d}.jsonl", "w", encoding="utf-8") as fo:
        for m in meta:
            fo.write(json.dumps(m, ensure_ascii=False) + "\n")
    return len(meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--set", default="unet", choices=["unet", "reader", "test"])
    ap.add_argument("--n", type=int, default=80000)
    ap.add_argument("--workers", type=int, default=16)
    ap.add_argument("--out", default="/work/d82")
    ap.add_argument("--adab", default=str(HERE.parent / "79_signal_reader/data/adab/ADAB DATABASE"))
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    jobs = [(w, a.set, a.n // a.workers + 1, a.out, a.adab) for w in range(a.workers)]
    with Pool(a.workers, maxtasksperchild=1) as pool:
        r = pool.map(work, jobs, chunksize=1)
    print("done", sum(r), flush=True)


if __name__ == "__main__":
    main()
