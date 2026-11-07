"""Experiment 86, step 2: benchmark images -> our reader's input (grey line crops, height 48, padded as exp 77 cuts).

    out/venv/bin/python prep86.py calib            -> out/calib86.json   (from OUR exp 77 dev crops, never a benchmark)
    out/venv/bin/python prep86.py prep [SUBSETS]   -> out/shards/<subset>-000.tar (+ manifest-<subset>.jsonl)

Why a calibration.  Experiment 77 cuts a line from Azure's polygon: polygon height h, padded by PAD_V*h above and
below and PAD_H*h at the ends, scaled to height 48.  A benchmark line image has no Azure polygon, only its own
margins.  So we find the line's ink box (Otsu, coordinates trimmed at the 1st/99th percentile of ink pixels) and
turn it into the polygon Azure would have drawn, using the median ratio between Azure's polygon and the same ink box
measured on experiment 77's own dev crops (our data).  Nothing here is fitted on a benchmark.

Per image: RGBA is laid on white; colour -> grey (BT.601, as cv2); light-on-dark images (border median darker than
the ink) are inverted, so every line is dark ink on a light ground as in training; the image is extended with its own
background grey so the padding never shows a white edge.  Then common77.cut_line(test=True) with the pseudo polygon.

Line sources:
  line images      patsocr, synthesizear, isippt (+ out-of-scope references: historyar, muharaf, khatt,
                   onlinekhatt, adab, evarest)
  page + GT boxes  ourslines (KITAB line-recognition set): each 'line' box (tables skipped) -> ink box inside it
  page, no boxes   hindawi, arabicocr: our own simple splitter (horizontal ink profile), lines read top to bottom and
                   joined; reported separately because the split is ours, not the benchmark's
"""
from __future__ import annotations

import io
import json
import math
import sys
import tarfile
from pathlib import Path

import cv2
import numpy as np

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import H, PAD_H, PAD_V, cut_line, encode  # noqa: E402

D = HERE / "data" / "kitab_img"
OUT = HERE / "out"
LINE_SETS = ["patsocr", "synthesizear", "isippt", "historyar", "muharaf", "khatt", "onlinekhatt", "adab", "evarest"]
PAGE_SETS = ["hindawi", "arabicocr"]
Q = 0.01


def ink_box(g: np.ndarray):
    """(x0, y0, x1, y1) of the ink in a dark-on-light grey image, trimmed at the Q / 1-Q quantiles; None if blank."""
    if g.size == 0 or int(g.max()) - int(g.min()) < 20:
        return None
    thr, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ys, xs = np.nonzero(g <= thr)
    if len(ys) < 5:
        return None
    return (float(np.quantile(xs, Q)), float(np.quantile(ys, Q)), float(np.quantile(xs, 1 - Q)) + 1,
            float(np.quantile(ys, 1 - Q)) + 1)


# ------------------------------------------------------------------------------------------------ calibration

def calib():
    """Azure polygon vs ink box on exp 77's dev crops (H=48): band rows are fixed by PAD_V, ends by PAD_H."""
    sd = E / "77_scratch_reader/out/shards"
    ph = H / (1 + 2 * PAD_V)                      # the polygon's height inside a crop
    top = PAD_V * ph
    r_h, off, mx0, mx1 = [], [], [], []
    for f in sorted(sd.glob("dev-*.tar")):
        with tarfile.open(f) as t:
            for m in t:
                if not m.name.endswith(".jpg"):
                    continue
                g = cv2.imdecode(np.frombuffer(t.extractfile(m).read(), np.uint8), cv2.IMREAD_GRAYSCALE)
                b = ink_box(g)
                if b is None:
                    continue
                x0, y0, x1, y1 = b
                ih = y1 - y0
                if ih < 4:
                    continue
                W = g.shape[1]
                pad = PAD_H * ph
                r_h.append(ph / ih)
                off.append(((top + ph / 2) - (y0 + y1) / 2) / ph)
                mx0.append((x0 - pad) / ph)
                mx1.append(((W - pad) - x1) / ph)
    res = dict(n=len(r_h), r_h=float(np.median(r_h)), off=float(np.median(off)), mx_left=float(np.median(mx0)),
               mx_right=float(np.median(mx1)), q=Q,
               r_h_iqr=[float(np.quantile(r_h, .25)), float(np.quantile(r_h, .75))])
    (OUT / "calib86.json").write_text(json.dumps(res, indent=1))
    print(res)


# ------------------------------------------------------------------------------------------------ images

def load_grey(path: Path) -> np.ndarray:
    a = cv2.imread(str(path), cv2.IMREAD_UNCHANGED)
    if a.ndim == 3 and a.shape[2] == 4:
        al = a[..., 3:4].astype(np.float32) / 255.0
        a = (a[..., :3].astype(np.float32) * al + 255.0 * (1 - al)).astype(np.uint8)
    if a.ndim == 3:
        a = cv2.cvtColor(a, cv2.COLOR_BGR2GRAY)
    return a


def polarity(g: np.ndarray):
    """Invert light-on-dark: the border's median is the ground; if it is darker than the image's Otsu ink class
    mean on the other side, the ink is light."""
    border = np.concatenate([g[0], g[-1], g[:, 0], g[:, -1]])
    bg = float(np.median(border))
    thr, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    inv = bg < thr
    if inv:
        g = 255 - g
        bg = 255 - bg
    return g, inv, bg


def cut_from_box(g: np.ndarray, b, cal: dict, bg: float):
    x0, y0, x1, y1 = b
    h = (y1 - y0) * cal["r_h"]
    cy = (y0 + y1) / 2 + cal["off"] * h
    xa, xb = x0 - cal["mx_left"] * h, x1 + cal["mx_right"] * h
    ya, yb = cy - h / 2, cy + h / 2
    m = int(math.ceil(h * 2 + 10))               # extend with the ground colour so padding has no white edge
    gg = cv2.copyMakeBorder(g, m, m, m, m, cv2.BORDER_CONSTANT, value=int(round(bg)))
    poly = [xa + m, ya + m, xb + m, ya + m, xb + m, yb + m, xa + m, yb + m]
    return cut_line(gg, poly, 1.0, 1.0, test=True)


def split_lines(g: np.ndarray):
    """Our simple page splitter: rows with ink (Otsu) form bands; a band is a line when separated by >= 1 blank row;
    bands thinner than 30% of the median band are attached to the nearest band (dots and marks).  Returns boxes
    (x0, y0, x1, y1) from top to bottom (generic settings, not tuned on any benchmark)."""
    thr, _ = cv2.threshold(g, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    ink = g <= thr
    rows = ink.sum(1) > 0
    bands, y = [], 0
    while y < len(rows):
        if rows[y]:
            s = y
            while y < len(rows) and rows[y]:
                y += 1
            bands.append([s, y])
        y += 1
    if not bands:
        return []
    med = float(np.median([b[1] - b[0] for b in bands]))
    merged = []
    for b in bands:
        if b[1] - b[0] < 0.3 * med and merged and (b[0] - merged[-1][1]) < 0.6 * med:
            merged[-1][1] = b[1]
        elif merged and (merged[-1][1] - merged[-1][0]) < 0.3 * med and b[0] - merged[-1][1] < 0.6 * med:
            merged[-1][1] = b[1]
        else:
            merged.append(list(b))
    # bands that hold several touching lines (pages whose lines have no blank row between them): estimate the line
    # pitch from the autocorrelation of the row profile and cut such bands at the profile's minima, one per pitch.
    prof = ink.sum(1).astype(np.float64)
    pc = prof - prof.mean()
    ac = np.correlate(pc, pc, "full")[len(pc) - 1:]
    lo, hi = 6, min(len(ac) - 1, 200)
    pitch = None
    if hi > lo + 2:
        lag = lo + int(np.argmax(ac[lo:hi]))
        if ac[lag] > 0.2 * ac[0]:
            pitch = lag
    if pitch:
        cut = []
        for a, z in merged:
            n = int(round((z - a) / pitch))
            if (z - a) > 1.5 * pitch and n >= 2:
                edges = [a]
                for k in range(1, n):
                    c = a + k * (z - a) / n
                    w0, w1 = int(c - pitch * 0.3), int(c + pitch * 0.3) + 1
                    edges.append(w0 + int(np.argmin(prof[w0:w1])))
                edges.append(z)
                cut += [[edges[k], edges[k + 1]] for k in range(n)]
            else:
                cut.append([a, z])
        merged = cut
        med = float(np.median([z - a for a, z in merged]))
    out = []
    for a, z in merged:
        if z - a < 0.3 * med:
            continue
        sub = g[a:z]
        bb = ink_box(sub)
        if bb is None:
            continue
        out.append((bb[0], bb[1] + a, bb[2], bb[3] + a))
    return out


class Shard:
    def __init__(self, name):
        sd = OUT / "shards"
        sd.mkdir(parents=True, exist_ok=True)
        self.t = tarfile.open(sd / f"{name}-000.tar", "w")
        self.mf = open(sd / f"manifest-{name}.jsonl", "w", encoding="utf-8")

    def add(self, key, crop, gt, **meta):
        for nm, data in ((key + ".jpg", encode(crop, q=95)), (key + ".txt", (gt or "").encode("utf-8"))):
            ti = tarfile.TarInfo(nm)
            ti.size = len(data)
            self.t.addfile(ti, io.BytesIO(data))
        self.mf.write(json.dumps(dict(key=key, gt=gt, W=int(crop.shape[1]), **meta), ensure_ascii=False) + "\n")

    def close(self):
        self.t.close()
        self.mf.close()


def prep(subsets):
    cal = json.loads((OUT / "calib86.json").read_text())
    for name in subsets:
        rows = [json.loads(l) for l in open(D / f"{name}.jsonl", encoding="utf-8")]
        sh = Shard(name)
        stats = dict(items=len(rows), lines=0, blank=0, inverted=0)
        for r in rows:
            g0 = load_grey(D / name / r["file"])
            g, inv, bg = polarity(g0)
            stats["inverted"] += inv
            if name == "ourslines":
                for ln in json.loads(r["gt"]):
                    if ln.get("class") != "line" or not (ln.get("text") or "").strip():
                        continue
                    bb = ln["bbox"]
                    xa, ya = max(0, bb["x1"] - 2), max(0, bb["y1"] - 2)
                    sub = g[ya:bb["y2"] + 2, xa:bb["x2"] + 2]
                    b = ink_box(sub)
                    if b is None:
                        stats["blank"] += 1
                        continue
                    b = (b[0] + xa, b[1] + ya, b[2] + xa, b[3] + ya)
                    crop, _ = cut_from_box(g, b, cal, bg)
                    if crop is None:
                        stats["blank"] += 1
                        continue
                    sh.add(f"{name}_{r['idx']:04d}_{ln['line_index']:03d}", crop, ln["text"], item=r["idx"],
                           line=ln["line_index"], inv=bool(inv))
                    stats["lines"] += 1
            elif name in PAGE_SETS:
                for j, b in enumerate(split_lines(g)):
                    crop, _ = cut_from_box(g, b, cal, bg)
                    if crop is None:
                        continue
                    sh.add(f"{name}_{r['idx']:04d}_{j:03d}", crop, "", item=r["idx"], line=j, inv=bool(inv))
                    stats["lines"] += 1
            else:
                b = ink_box(g)
                if b is None:
                    stats["blank"] += 1
                    continue
                crop, _ = cut_from_box(g, b, cal, bg)
                if crop is None:
                    stats["blank"] += 1
                    continue
                sh.add(f"{name}_{r['idx']:04d}", crop, r["gt"], item=r["idx"], inv=bool(inv))
                stats["lines"] += 1
        sh.close()
        print(name, stats, flush=True)
        (OUT / "shards" / f"stats-{name}.json").write_text(json.dumps(stats))


if __name__ == "__main__":
    cv2.setNumThreads(2)
    if sys.argv[1] == "calib":
        calib()
    else:
        prep(sys.argv[2:] or LINE_SETS + ["ourslines"] + PAGE_SETS)
