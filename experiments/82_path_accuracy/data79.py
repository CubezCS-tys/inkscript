"""Experiment 79, rungs 0-1 data (runs on the rented host's CPUs): synthetic lines with three pen signals each.

    python data79.py --n 150000 --test 3000 --workers 30 --out /work/data

Per line (text from experiment 78's corpus, a face from experiment 78's fonts; Mirza held out for the font test):
  truth  = the perfect path (synth79.truth_path: the letters known),
  rclean = the reconstruction (sig79.line_signal) from the clean rendered ink,
  rdmg   = the reconstruction from damaged ink (mild 2/3, heavy 1/3),
and for test lines the rung-0 score of both reconstructions (letter order error, back-steps, dot ownership).
Text is split by a hash of the line: about 2% of the corpus lines are test text and never trained on.
Shards: <out>/<split>-<w>.npz (features float16, concatenated, with offsets per signal kind) + <split>-<w>.jsonl.
"""
from __future__ import annotations

import argparse
import gzip
import hashlib
import json
import os
import random
import re
import sys
import time
import unicodedata
from multiprocessing import Pool
from pathlib import Path

import cv2
import numpy as np

from sig79 import binarise

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
os.environ.setdefault("OMP_NUM_THREADS", "1")
cv2.setNumThreads(1)

ROOT_FONTS = None  # set in main (the host's copy of experiment 78's fonts)
TRAIN_FONTS = {   # face -> weight in the mix (experiment 78's naskh-like and sans faces + the traced ones)
    "amiri_Amiri-Regular.ttf": 10, "amiri_Amiri-Bold.ttf": 4, "scheherazadenew_ScheherazadeNew-Regular.ttf": 7,
    "scheherazadenew_ScheherazadeNew-Bold.ttf": 3, "notonaskharabic_NotoNaskhArabic[wght].ttf": 10,
    "lateef_Lateef-Regular.ttf": 4, "lateef_Lateef-Bold.ttf": 2, "markazitext_MarkaziText[wght].ttf": 5,
    "harmattan_Harmattan-Regular.ttf": 3, "notosansarabic_NotoSansArabic[wdth_wght].ttf": 5,
    "ibmplexsansarabic_IBMPlexSansArabic-Regular.ttf": 4, "vazirmatn_Vazirmatn[wght].ttf": 3,
    "cairo_Cairo[slnt_wght].ttf": 2, "tajawal_Tajawal-Regular.ttf": 2, "almarai_Almarai-Regular.ttf": 2,
    "traced/Mand0737y1937.ttf": 2, "traced/Mand0300y1957.ttf": 2, "traced/Mand0484y1958.ttf": 2,
    "traced/Mand0756y1951.ttf": 2, "traced/Mand0775y1958.ttf": 2, "traced/Mand0924y1928.ttf": 2}
HELD_FONT = "mirza_Mirza-Regular.ttf"
ARABIC = set(chr(c) for c in range(0x0621, 0x064B))

# ---- experiment 77's label rules (common77.clean_label / to_visual), duplicated so this file runs on the host
_PRES = re.compile("[ﭐ-﷿ﹰ-ﻼ]")
_WS = re.compile(r"\s+")


def clean_label(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    if _PRES.search(s):
        s = _PRES.sub(lambda m: unicodedata.normalize("NFKC", m.group()) if m.group() != "ﷺ" else m.group(), s)
    s = s.replace("ـ", "")
    return _WS.sub(" ", s).strip()


def is_test_text(t: str) -> bool:
    return int(hashlib.md5(t.encode("utf-8")).hexdigest()[:4], 16) % 50 == 0


def damage(grey: np.ndarray, rng: random.Random, level: str) -> np.ndarray:
    """Print and scan damage on a clean rendered line (a light version of experiment 78's)."""
    g = grey.astype(np.float32)
    ink = g < 128
    if level == "spread":                                             # heavy ink spread: counters close, heads fill
        e = cv2.getStructuringElement(cv2.MORPH_ELLIPSE, (3, 3))
        m = cv2.dilate(ink.astype(np.uint8), e, iterations=rng.choice([1, 2, 2, 3]))
        g = np.where(m > 0, 25, 245).astype(np.float32)
        level = "mild"
    heavy = level == "heavy"
    if rng.random() < (0.5 if heavy else 0.3):                        # ink spread or eroded
        k = np.ones((2, 2), np.uint8)
        m = cv2.dilate(ink.astype(np.uint8), k) if rng.random() < 0.5 else cv2.erode(ink.astype(np.uint8), k)
        g = np.where(m > 0, 25, 245).astype(np.float32)
    if heavy and rng.random() < 0.5:                                  # strong spread (letters touch, loops fill) or wear
        k3 = np.ones((3, 3), np.uint8)
        cur = (g < 128).astype(np.uint8)
        m = cv2.dilate(cur, k3) if rng.random() < 0.5 else cv2.erode(cur, k3)
        if m.sum() > 0.3 * cur.sum():
            g = np.where(m > 0, 25, 245).astype(np.float32)
    if heavy and rng.random() < 0.7:                                  # broken strokes: holes ON the ink
        holes = np.zeros_like(g, np.uint8)
        ys, xs = np.where(g < 128)
        for _ in range(rng.randint(6, 20) if len(xs) else 0):
            j = rng.randrange(len(xs))
            cv2.circle(holes, (int(xs[j]), int(ys[j])), rng.randint(1, 3), 1, -1)
        g = np.where(holes > 0, 245, g)
    fade = rng.uniform(0, 0.5 if heavy else 0.3)                       # faded ink
    g = 245 - (245 - g) * (1 - fade)
    s = rng.uniform(0.45, 0.65) if heavy else rng.uniform(0.65, 1.0)   # low resolution
    if s < 0.97:
        h, w = g.shape
        g = cv2.resize(cv2.resize(g, (max(8, int(w * s)), max(8, int(h * s))), interpolation=cv2.INTER_AREA), (w, h),
                       interpolation=cv2.INTER_LINEAR)
    sig = rng.uniform(0.3, 1.6 if heavy else 0.9)
    g = cv2.GaussianBlur(g, (0, 0), sig)
    g = g + np.random.default_rng(rng.randrange(1 << 30)).normal(0, rng.uniform(4, 18 if heavy else 10), g.shape)
    g = np.clip(g, 0, 255).astype(np.uint8)
    q = rng.randint(30 if heavy else 50, 90)
    ok, b = cv2.imencode(".jpg", g, [cv2.IMWRITE_JPEG_QUALITY, q])
    return cv2.imdecode(b, cv2.IMREAD_GRAYSCALE)


def one(text: str, font: Path, rng: random.Random, scored: bool):
    import synth79 as S
    from sig79 import features, line_signal
    S.H = 96
    px = 62.0 * rng.uniform(0.85, 1.15)
    grey, owner, ink = S.render(text, font, px_per_em=px)
    tp = S.truth_path(ink, owner, text)
    rc = line_signal(grey, start_rule="top", ink=ink)
    level = rng.choice(["mild", "heavy", "spread"])
    gd = damage(grey, rng, level)
    rd = line_signal(gd, start_rule="top")
    out = dict(truth=features(tp), rclean=features(rc), rdmg=features(rd), level=level, px=round(px, 1))
    if scored:
        out["s_clean"] = S.score(rc, owner, text, ink)
        out["s_dmg"] = S.score(rd, owner, text, ink)
        out["loops"] = loops_kept(owner, text, binarise(gd))
    return out


def loops_kept(owner: np.ndarray, text: str, ink_d: np.ndarray):
    """Every closed counter of the clean letters (a hole in the letter's own ink of >= 4 pixels) and whether the
    damaged ink still leaves it open (more than half of its pixels still paper): [(char, kept 0/1), ...]."""
    out = []
    for c in sorted({int(c) for c in np.unique(owner) if c >= 0}):
        m = (owner == c).astype(np.uint8)
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        for j, h in enumerate(hier[0]):
            if h[3] < 0:
                continue                                              # an outer contour, not a hole
            hole = np.zeros_like(m)
            cv2.drawContours(hole, cs, j, 1, -1)
            hole &= (1 - m)
            if hole.sum() < 4:
                continue
            out.append((text[c] if c < len(text) else "?", int((~ink_d[hole > 0]).mean() > 0.5)))
    return out


def cut(t: str, rng: random.Random) -> str:
    w = t.split()
    n = rng.randint(2, 11)
    a = rng.randrange(max(1, len(w) - n + 1))
    s = " ".join(w[a:a + n])
    while len(s) > 70 and " " in s:
        s = s.rsplit(" ", 1)[0]
    return s


def work(args):
    wid, split, n, texts, fonts_dir, out = args
    import synth79 as S
    rng = random.Random(7900 + wid * 13 + {"train": 0, "test": 1, "testfont": 2}[split] * 1000)
    fonts_dir = Path(fonts_dir)
    S.FONTS = fonts_dir
    ex = json.loads((fonts_dir / "traced/exclude.json").read_text(encoding="utf-8"))
    names = list(TRAIN_FONTS) if split != "testfont" else [HELD_FONT]
    weights = [TRAIN_FONTS.get(f, 1) for f in names]
    feats = {k: [] for k in ("truth", "rclean", "rdmg")}
    meta = []
    t0 = time.time()
    tries = 0
    while len(meta) < n and tries < 20 * n:
        tries += 1
        t = cut(rng.choice(texts), rng)
        if len(t) < 6:
            continue
        f = rng.choices(names, weights)[0]
        fp = fonts_dir / f
        if not fp.exists():
            continue
        if f.startswith("traced"):
            e = ex.get(Path(f).stem, {})
            bad = set(e.get("chars", "")) if isinstance(e, dict) else set()
            if set(t) & bad or not set(t.replace(" ", "")) <= ARABIC:
                continue
        if not S.covers(fp, t):
            continue
        try:
            r = one(t, fp, rng, scored=split != "train")
        except Exception as e:  # noqa: BLE001
            print(wid, "error", type(e).__name__, str(e)[:100], flush=True)
            continue
        if min(len(r["truth"]), len(r["rclean"])) < 4:
            continue
        for k in feats:
            feats[k].append(r[k].astype(np.float16))
        m = dict(text=t, label=clean_label(t), font=Path(f).stem, level=r["level"], px=r["px"])
        if "s_clean" in r:
            m["s_clean"], m["s_dmg"], m["loops"] = r["s_clean"], r["s_dmg"], r["loops"]
        meta.append(m)
        if len(meta) % 500 == 0:
            print(f"w{wid} {split} {len(meta)}/{n} {time.time() - t0:.0f}s", flush=True)
    arrs = {}
    for k, L in feats.items():
        arrs[k] = np.concatenate(L) if L else np.zeros((0, 13), np.float16)
        arrs[k + "_off"] = np.cumsum([0] + [len(x) for x in L]).astype(np.int64)
    np.savez(Path(out) / f"{split}-{wid:02d}.npz", **arrs)
    with open(Path(out) / f"{split}-{wid:02d}.jsonl", "w", encoding="utf-8") as fo:
        for m in meta:
            fo.write(json.dumps(m, ensure_ascii=False) + "\n")
    return len(meta)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=150000)
    ap.add_argument("--test", type=int, default=3000)
    ap.add_argument("--workers", type=int, default=30)
    ap.add_argument("--fonts", default="/work/fonts")
    ap.add_argument("--text", default="/work/text78.jsonl.gz")
    ap.add_argument("--out", default="/work/data")
    ap.add_argument("--testfont", type=int, default=1000)
    ap.add_argument("--only-test", action="store_true", help="rung 0 alone: the scored test splits, no training lines")
    a = ap.parse_args()
    Path(a.out).mkdir(parents=True, exist_ok=True)
    train_t, test_t = [], []
    with gzip.open(a.text, "rt", encoding="utf-8") as f:
        for l in f:
            t = json.loads(l)["t"]
            if len(t.split()) < 2:
                continue
            (test_t if is_test_text(t) else train_t).append(t)
    print(f"text lines: train {len(train_t)}, test {len(test_t)}", flush=True)
    W = a.workers
    jobs = [(w, "test", a.test // W + 1, test_t, a.fonts, a.out) for w in range(W)]
    jobs += [(w, "testfont", a.testfont // W + 1, test_t, a.fonts, a.out) for w in range(W)]
    if not a.only_test:
        jobs += [(w, "train", a.n // W + 1, train_t, a.fonts, a.out) for w in range(W)]
    with Pool(W, maxtasksperchild=1) as pool:
        r = pool.map(work, jobs, chunksize=1)
    print("done", sum(r), flush=True)


if __name__ == "__main__":
    main()
