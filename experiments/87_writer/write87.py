"""Experiment 87: the writer as a service call (the Desk's Try page, via experiment 89's serve_reader.py POST /write).

    fit_write(grey, text) -> dict(written=PNG data URL, overlay=PNG data URL, lib, iou, chamfer, ms)

The line crop the reader saw (48 px high) and its reading: three letter libraries are screened together
(AlQalam's pen strokes, a traced 1930s face when it can write the text, Amiri Bold), each fitted for a few steps; the
best is fitted a little longer.  CPU, the caller's threads.  Nothing is stored.
"""
from __future__ import annotations

import base64
import os
import sys
import time
from pathlib import Path

os.environ.setdefault("H87", "48")                 # the reader's crop height: no resampling, 4x less work than 96
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "79_signal_reader/data/pylib"))     # uharfbuzz
import cv2  # noqa: E402
import numpy as np  # noqa: E402
import torch  # noqa: E402

import fit87 as F  # noqa: E402
from run87 import lib_ok  # noqa: E402

LIBS = ["alqalam", "font:Mand0737y1937", "font:Mand0917y1927", "font:amiri_Amiri-Bold"]
SCREEN, REFINE = int(os.environ.get("WRITE87_SCREEN", 6)), int(os.environ.get("WRITE87_REFINE", 14))
DEV = os.environ.get("WRITE87_DEV", "cpu")
FULL = os.environ.get("WRITE87_FULL") == "1"        # the GPU demo: every library screened, the best 3 fitted in full


def strokes_of(bt, P, k: int) -> list:
    """The rendered capsules of line k, back as pen strokes in reading order: [{letter, pts: [[x, y, half-width]]}]
    in the 96-px crop's pixels (after every fitted setting).  A stroke ends where the next segment does not start
    where the last one ended."""
    with torch.no_grad():
        A, B, ra, rb = F.place_batch(bt, P)
    a0, a1 = int(bt.seg_off[k]), int(bt.seg_off[k + 1])
    A, B, ra, rb = (t[a0:a1].cpu().numpy() for t in (A, B, ra, rb))
    sg = bt.segs[k]
    ch = sg.char.cpu().numpy()
    gl = sg.glyph.cpu().numpy()
    f = 96.0 / F.H
    out, cur = [], None
    for i in range(len(A)):
        new = cur is None or gl[i] != gl[i - 1] or np.abs(A[i] - B[i - 1]).max() > 1e-3
        if new:
            cur = dict(letter=int(ch[i]), glyph=int(gl[i]), pts=[[*(A[i] * f), ra[i] * f]])
            out.append(cur)
        cur["pts"].append([*(B[i] * f), rb[i] * f])
    for o in out:
        o["pts"] = [[round(float(x), 1) for x in p] for p in o["pts"]]
    out.sort(key=lambda o: (o["letter"], o["glyph"]))            # reading order; a glyph's strokes in pen order
    for o in out:
        del o["glyph"]
    return out


def _png(a: np.ndarray, up: int = 2) -> str:
    if up > 1:
        a = cv2.resize(a, None, fx=up, fy=up, interpolation=cv2.INTER_NEAREST)
    ok, b = cv2.imencode(".png", a)
    return "data:image/png;base64," + base64.b64encode(b.tobytes()).decode("ascii")


def fit_write(grey: np.ndarray, text: str) -> dict:
    t0 = time.perf_counter()
    text = " ".join(text.split())
    if FULL:
        return _fit_full(grey, text, t0)
    libs = [l for l in LIBS if lib_ok(l, text)]
    traced = [l for l in libs if l.startswith("font:Mand")]
    libs = [l for l in libs if not l.startswith("font:Mand")] + traced[:1]           # at most one traced face
    items = [dict(grey=grey.copy(), text=text, lib=l) for l in libs]
    bt = F.Batch(items, "cpu")
    P = F.Params(bt)
    F.init_items(bt, P)
    F.fit(bt, P, iters=SCREEN)
    sc = F.scores(bt, P)
    k = int(np.argmax([s["iou"] for s in sc]))
    bt1 = F.Batch([dict(grey=grey.copy(), text=text, lib=libs[k])], "cpu")
    P1 = F.Params(bt1)
    with torch.no_grad():                                     # start from the screening's fit
        for n in F.STYLE_KEYS:
            P1.style[n][0] = P.style[n][k]
        for n in F.LINE_KEYS:
            P1.linep[n][0] = P.linep[n][k]
        P1.theta.copy_(P.theta[k:k + 1, :P1.theta.shape[1]])
    F.fit(bt1, P1, iters=REFINE, fine_only=True)
    s = F.scores(bt1, P1, need_maps=True)[0]
    g = bt1.items[0]["grey"]
    w = (255 * (1 - s["written"])).astype(np.uint8)
    ov = F.overlay(g, s["written"], bt1.T[0, :, :bt1.Wd[0]].numpy())
    return dict(written=_png(w), overlay=_png(ov), crop=_png(g), lib=libs[k].replace("font:", ""), strokes=strokes_of(bt1, P1, 0),
                iou=round(s["iou"], 3), chamfer=round(s["chamfer"] * 96 / F.H, 2),
                screened={l: round(x["iou"], 3) for l, x in zip(libs, sc)},
                ms=round((time.perf_counter() - t0) * 1000))


def _fit_full(grey, text, t0):
    from run87 import LIBS as ALL
    libs = [l for l in ALL if lib_ok(l, text)]
    bt = F.Batch([dict(grey=grey.copy(), text=text, lib=l) for l in libs], DEV)
    P = F.Params(bt)
    F.init_items(bt, P)
    F.fit(bt, P, iters=60)
    sc = F.scores(bt, P)
    top = [libs[i] for i in np.argsort([-s["iou"] for s in sc])[:3]]
    bt1 = F.Batch([dict(grey=grey.copy(), text=text, lib=l) for l in top], DEV)
    P1 = F.Params(bt1)
    F.init_items(bt1, P1)
    F.fit(bt1, P1, iters=160)
    s1 = F.scores(bt1, P1, need_maps=True)
    k = int(np.argmax([s["iou"] for s in s1]))
    s = s1[k]
    g = bt1.items[k]["grey"]
    w = (255 * (1 - s["written"])).astype(np.uint8)
    ov = F.overlay(g, s["written"], bt1.T[k, :, :bt1.Wd[k]].cpu().numpy())
    return dict(written=_png(w, 1), overlay=_png(ov, 1), crop=_png(g, 1), lib=top[k].replace("font:", ""), strokes=strokes_of(bt1, P1, k),
                iou=round(s["iou"], 3), chamfer=round(s["chamfer"] * 96 / F.H, 2),
                screened={l: round(x["iou"], 3) for l, x in zip(libs, sc)}, ms=round((time.perf_counter() - t0) * 1000))


if __name__ == "__main__":                                  # a timing check on two held-out judge crops
    torch.set_num_threads(2)
    import json
    for key in sys.argv[1:]:
        g = cv2.imread(str(HERE / f"out/data/crops/judge/{key}.png"), 0)
        g = cv2.resize(g, (int(round(g.shape[1] * 48 / g.shape[0])), 48), interpolation=cv2.INTER_AREA)
        t = [json.loads(l) for l in open(HERE / "out/data/judged_shown.jsonl", encoding="utf-8") if key in l][0]["shown"][0]
        r = fit_write(g, t)
        print(key, r["lib"], r["iou"], r["chamfer"], r["ms"], "ms", r["screened"])
        for n in ("crop", "written", "overlay"):
            open(HERE / f"out/look/write_{key}_{n}.png", "wb").write(base64.b64decode(r[n].split(",")[1]))
