"""Experiment 87, stage 1a: AlQalam's letter programs, read from its own METAFONT source.

AlQalam 0.2 (Hossam A. H. Fahmy, LPPL 1.3+; experiments/79_signal_reader/data/alqalam_lppl) defines every Naskh letter
body as broad-nib pen strokes (`draw path` with `pensquare xscaled px yscaled py rotated 70`) plus a few filled
shapes (the bowls of ر and ح, round dots).  We run the real METAFONT (Ubuntu's texlive-binaries 2023, unpacked into
out/tex without root) on the unchanged sources, with a hook file (out/tex/run/trace87.mf) that prints the pen and
the path of every draw/fill to the log.  This script turns that log into programs:

    out/programs/alqalam.json : {code: {w, h, d, prims: [{t: "stroke", pts, pen} | {t: "fill", poly, pen?} |
                                                        {t: "erase", ...}]}}   in em units (1 em = 25.4 dx)

    python alqalam87.py mf        # run METAFONT (seconds)
    python alqalam87.py parse     # log -> programs json
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
TEX = OUT / "tex"
RUN = TEX / "run"
AQ = HERE.parent / "79_signal_reader/data/alqalam_lppl/alqalam-0.2/fonts"
LICENCE = "AlQalam 0.2, (c) Hossam A. H. Fahmy, LaTeX Project Public License 1.3 or later (alqalam_lppl/LICENSE)"

HOOK = r"""% exp 87: capture AlQalam's pen strokes. Every draw/fill prints its pen and path to the log.
def draw expr p = message "@DRAW"; show currentpen; show p.t_;
 addto_currentpicture doublepath p.t_ withpen currentpen enddef;
def fill expr c = message "@FILL"; show c.t_; addto_currentpicture contour c.t_ enddef;
def filldraw expr c = message "@FILLDRAW"; show currentpen; fill counterclockwise c withpen currentpen enddef;
def unfill expr c = message "@UN"; fill c withweight _ enddef;
def undraw expr p = message "@UN"; draw p withweight _ enddef;
def unfilldraw expr c = message "@UN"; filldraw c withweight _ enddef;
def drawdot expr z = message "@DOT"; show currentpen; show z.t_;
 if unknown currentpen_path: def_pen_path_ fi
 addto_currentpicture contour currentpen_path shifted (z.t_) withpen penspeck enddef;
def beginhook = message "@BEGIN"; show charcode, w, h, d, dx, dy; enddef;
extra_beginchar := extra_beginchar & "beginhook;";
"""


def run_mf():
    RUN.mkdir(parents=True, exist_ok=True)
    (RUN / "trace87.mf").write_text(HOOK)
    env = dict(os.environ, max_print_line="1000000", error_line="250", half_error_line="200", LD_LIBRARY_PATH=str(TEX / "root/usr/lib/x86_64-linux-gnu"),
               MFINPUTS=f".:{TEX / 'root/usr/share/texlive/texmf-dist/metafont/base'}:{AQ}")
    subprocess.run([str(TEX / "root/usr/bin/mf-nowin"), "-ini",
                    r"\input plain; mode=proof; mag=1; batchmode; showstopping:=0; input trace87; input qnskh14"],
                   cwd=RUN, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=300)
    print("log", (RUN / "plain.log").stat().st_size)


_NUM = r"-?\d+(?:\.\d+)?"
_PAIR = re.compile(rf"\(({_NUM}),({_NUM})\)")


def parse_path(txt: str):
    """METAFONT's printed path -> (list of cubic segments [(p0,c1,c2,p3)], cyclic) or a single point."""
    cyc = "cycle" in txt
    toks = re.findall(rf"\(({_NUM}),({_NUM})\)|(controls)|(and)|(cycle)", txt)
    pts = []
    for a, b, c, d, e in toks:
        if a:
            pts.append((float(a), float(b)))
    # printed form: k0 ..controls c1 and c2 ..k1 ..controls ... [..cycle]  => 3n+1 pairs (or 3n with cycle)
    if len(pts) == 1:
        return [], cyc, pts[0]
    segs = []
    i = 0
    while i + 3 < len(pts):
        segs.append((pts[i], pts[i + 1], pts[i + 2], pts[i + 3]))
        i += 3
    if cyc and i + 2 < len(pts):
        segs.append((pts[i], pts[i + 1], pts[i + 2], pts[0]))
    return segs, cyc, None


def sample_bezier(segs, step: float) -> np.ndarray:
    out = []
    for p0, c1, c2, p3 in segs:
        P = np.array([p0, c1, c2, p3], float)
        L = np.linalg.norm(np.diff(P, axis=0), axis=1).sum()
        n = max(2, int(np.ceil(L / step)) + 1)
        t = np.linspace(0, 1, n)[:, None]
        B = (1 - t) ** 3 * P[0] + 3 * (1 - t) ** 2 * t * P[1] + 3 * (1 - t) * t ** 2 * P[2] + t ** 3 * P[3]
        out.append(B if not out else B[1:])
    return np.vstack(out) if out else np.zeros((0, 2))


def parse():
    log = (RUN / "plain.log").read_text(errors="replace")
    blocks = log.split("@BEGIN")[1:]
    chars = {}
    for b in blocks:
        nums = re.findall(rf"^>> ({_NUM})\b", b[:600], flags=re.M)[:6]
        code, w, h, d, dx, dy = (float(x) for x in nums)
        em = 25.4 * dx                                    # qnskh14: fs# = 25.4 dx#
        prims = []
        # split into events
        ev = re.split(r"^(@DRAW|@FILLDRAW|@FILL|@UN|@DOT)\s*$", b, flags=re.M)
        pending_pen, mode_un, fd_pen = None, False, None
        for k in range(1, len(ev), 2):
            tag, body = ev[k], ev[k + 1]
            pen = None
            m = re.search(r">> Pen polygon at line \d+:\n(.*?)\n\n", body, flags=re.S)
            if m:
                pen = [(float(a), float(c)) for a, c in _PAIR.findall(m.group(1))]
            pm = re.search(r">> Path at line \d+:\n(.*?)\n\n", body, flags=re.S)
            if not pm:
                pm = re.search(r">> (\(.*?\))\s*$", body, flags=re.M)
            if tag == "@UN":
                mode_un = True
                continue
            if tag == "@FILLDRAW":
                fd_pen = pen
                continue
            if pm is None:
                continue
            segs, cyc, single = parse_path(pm.group(1))
            if single is not None:
                pts = np.array([single])
            else:
                pts = sample_bezier(segs, step=0.015 * em)
            pts = pts / em
            pn = (np.array(pen) / em).tolist() if pen else None
            if tag == "@FILL":
                prim = dict(t="fill", poly=np.round(pts, 5).tolist(), pen=(np.array(fd_pen) / em).tolist() if fd_pen else None)
                fd_pen = None
            elif tag in ("@DRAW", "@DOT"):
                prim = dict(t="stroke", pts=np.round(pts, 5).tolist(), pen=pn)
            else:
                continue
            if mode_un:
                prim["erase"] = True
                mode_un = False
            prims.append(prim)
        chars[int(code)] = dict(w=w / em, h=h / em, d=d / em, prims=prims)   # a later definition replaces an earlier
    (OUT / "programs").mkdir(parents=True, exist_ok=True)
    (OUT / "programs/alqalam.json").write_text(json.dumps(dict(licence=LICENCE, chars=chars)))
    n_st = sum(sum(p["t"] == "stroke" for p in c["prims"]) for c in chars.values())
    n_fi = sum(sum(p["t"] == "fill" for p in c["prims"]) for c in chars.values())
    print(f"{len(chars)} char codes, {n_st} pen strokes, {n_fi} fills")


def _pen_half(pen: np.ndarray, d: np.ndarray) -> np.ndarray:
    """Half the extent of a convex pen polygon across directions d [N,2] (unit)."""
    n = np.stack([-d[:, 1], d[:, 0]], 1)
    proj = n @ pen.T                                       # [N, V]
    return 0.5 * (proj.max(1) - proj.min(1))


def _fill_strokes(poly: np.ndarray, pen: np.ndarray | None, S: int = 120):
    """A filled contour (and its outline pen) -> many short strokes along its medial axis, radius = the distance."""
    import cv2
    from skimage.morphology import medial_axis
    allp = poly if pen is None else np.vstack([poly + v for v in pen])
    x0, y0 = allp.min(0) - 0.05
    x1, y1 = allp.max(0) + 0.05
    Wd, Hd = int((x1 - x0) * S) + 2, int((y1 - y0) * S) + 2
    m = np.zeros((Hd, Wd), np.uint8)
    tp = lambda P: np.round(np.stack([(P[:, 0] - x0) * S, (y1 - P[:, 1]) * S], 1) * 8).astype(np.int32)
    cv2.fillPoly(m, [tp(poly)], 1, shift=3)
    if pen is not None:
        for i in range(len(poly)):
            a, b = poly[i], poly[(i + 1) % len(poly)]
            hull = cv2.convexHull(np.vstack([a + pen, b + pen]).astype(np.float32))[:, 0]
            cv2.fillConvexPoly(m, tp(hull), 1, shift=3)
    sk, dist = medial_axis(m > 0, return_distance=True)
    ys, xs = np.nonzero(sk)
    idx = {(y, x): k for k, (y, x) in enumerate(zip(ys, xs))}
    out = []
    for (y, x), k in idx.items():
        for dy, dx in ((0, 1), (1, 0), (1, 1), (1, -1)):
            j = idx.get((y + dy, x + dx))
            if j is not None:
                pa = (x0 + x / S, y1 - y / S, dist[y, x] / S)
                pb = (x0 + xs[j] / S, y1 - ys[j] / S, dist[ys[j], xs[j]] / S)
                out.append([pa, pb])
    # thin the many tiny segments: keep every one (cheap enough at this resolution: ~1-3k per fill), rounded
    return [np.round(np.array(o), 5).tolist() for o in out[::2]] + [np.round(np.array(o), 5).tolist() for o in out[1::2]]


def strokes():
    """programs json -> strokes with their own half-width r0: out/programs/alqalam_strokes.json"""
    d = json.loads((OUT / "programs/alqalam.json").read_text())
    res = {}
    nfill = 0
    for code, c in d["chars"].items():
        S = []
        for p in c["prims"]:
            if p.get("erase"):
                continue
            pen = np.array(p["pen"]) if p.get("pen") else None
            if p["t"] == "stroke":
                P = np.array(p["pts"], float)
                if pen is None:
                    pen = np.array([[0.004, 0], [0, 0.004], [-0.004, 0], [0, -0.004]])
                if len(P) == 1 or np.ptp(P, 0).max() < 1e-4:
                    # a dot of the square pen: a capsule along the pen's longest diagonal
                    dd = pen[:, None, :] - pen[None, :, :]
                    i, j = np.unravel_index(np.argmax((dd ** 2).sum(-1)), dd.shape[:2])
                    u = (pen[i] - pen[j]) / max(1e-9, np.linalg.norm(pen[i] - pen[j]))
                    r = float(_pen_half(pen, u[None])[0])
                    L = 0.5 * np.linalg.norm(pen[i] - pen[j]) - r
                    c0 = P[0]
                    S.append(dict(pts=[[*(c0 + u * L), r], [*(c0 - u * L), r]]))
                    continue
                D = np.gradient(P, axis=0)
                D /= np.maximum(1e-9, np.linalg.norm(D, axis=1, keepdims=True))
                r = _pen_half(pen, D)
                # the square nib's corners reach a little further than a capsule of half-width r: no correction
                S.append(dict(pts=np.round(np.column_stack([P, r]), 5).tolist()))
            else:
                for seg in _fill_strokes(np.array(p["poly"], float), pen):
                    S.append(dict(pts=seg))
                nfill += 1
        res[code] = dict(w=c["w"], h=c["h"], d=c["d"], strokes=S)
    (OUT / "programs/alqalam_strokes.json").write_text(json.dumps(dict(licence=LICENCE, chars=res)))
    print(len(res), "codes;", nfill, "fills turned into medial-axis strokes")


if __name__ == "__main__":
    {"mf": run_mf, "parse": parse, "strokes": strokes}[sys.argv[1]]()
