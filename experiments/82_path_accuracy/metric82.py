"""Experiment 82: the path-SHAPE metric.  Exp 79's rung 0 scored only the ORDER of letters met; this scores whether
the rebuilt pen path has the right SHAPE, letter by letter, against a true path built from the clean glyphs.

Truth (truth82, synth79.truth_path with one change): each letter's clean glyph ink is thinned on its own and walked by
exp 79's rule, letters in reading order, marks after their piece; a piece's FIRST letter starts at the top of a tall
stroke, as the rebuilders' walk does (start_rule 'top'), so an initial alef or lam is not scored as reversed.  It knows which letter every truth point belongs to.

A rebuilt path (from the damaged ink, letters unknown) is cut into letters by the CLEAN letter map: every rebuilt
point goes to the letter of the nearest clean ink pixel (points further than one body height from any clean ink are
"stray").  Per letter that has a body (main strokes only; dots and marks are exp 79's dot-ownership score):

  frechet   discrete Frechet distance between the rebuilt points of the letter (in time order, retraces left out)
            and the truth points of the letter (likewise), the better of the truth's two orientations (so it scores
            shape and the order of its parts, and direction is scored on its own); in pixels at the 96 px line;
            missed = the letter has no rebuilt point;
  mean_d    symmetric mean nearest-point distance (chamfer);  max_d = Hausdorff;
  dir_ok    share of rebuilt points whose direction of travel agrees (within 45 deg) with the nearest truth point's;
            dir_rev = share pointing the opposite way.
Per counter of a loop letter (a closed hole of >= 4 px in the clean glyph; only counters the TRUTH path itself goes
round are scored):
  loop      the rebuilt path, near the counter, winds round its centre (|swept angle| >= 1.6 pi, pen-down points,
            retraces left out).
Per junction of the clean centre line (a node with 3+ branches after spur pruning; its branches' directions where
they leave a disk of radius 1.5 x the stroke width):
  junc_ok   the rebuilt path leaves the same disk along the same branches: the same number of directions, each truth
            branch matched by a rebuilt one within 35 deg (and no extra).
Distances are reported in pixels and in stroke widths of the clean line (stroke ~ 4-6 px at 96 px).
"""
from __future__ import annotations

import math

import cv2
import numpy as np

from sig79 import line_metrics, resample, skeleton_graph, thin
from synth79 import letters_of

LOOP_LETTERS = set("وفقمهةصضطظعغؤ")
STEP = 2.0


def nearest_owner(owner: np.ndarray):
    """-> (map of the letter-cluster of the nearest clean ink pixel, distance to it)."""
    src = (owner < 0).astype(np.uint8)                                 # zero pixels = ink
    dist, lab = cv2.distanceTransformWithLabels(src, cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    ys, xs = np.where(src == 0)                                        # labels 1..n in raster order of the zeros
    lut = np.r_[-1, owner[ys, xs]]
    return lut[lab], dist


def frechet(P: np.ndarray, Q: np.ndarray) -> float:
    """Discrete Frechet distance (row-wise DP, vectorised along each row's running max)."""
    n, m = len(P), len(Q)
    D = np.sqrt(((P[:, None, :] - Q[None, :, :]) ** 2).sum(-1))
    ca = np.empty(m)
    ca[0] = D[0, 0]
    for j in range(1, m):
        ca[j] = max(ca[j - 1], D[0, j])
    for i in range(1, n):
        prev = ca.copy()
        ca[0] = max(prev[0], D[i, 0])
        for j in range(1, m):
            ca[j] = max(min(prev[j], prev[j - 1], ca[j - 1]), D[i, j])
    return float(ca[-1])


def _tangents(p: np.ndarray) -> np.ndarray:
    if len(p) < 2:
        return np.zeros_like(p)
    d = np.gradient(p, axis=0)
    return d / (np.linalg.norm(d, axis=1, keepdims=True) + 1e-9)


def _resample_runs(pts: np.ndarray, keep: np.ndarray, step: float = STEP):
    """Points where keep, split where keep is false or the path jumps, each run resampled at `step`."""
    runs, cur = [], []
    for i in range(len(pts)):
        if keep[i] and (not cur or np.linalg.norm(pts[i] - cur[-1]) < 4 * step + 4):
            cur.append(pts[i])
        else:
            if len(cur):
                runs.append(np.array(cur))
            cur = [pts[i]] if keep[i] else []
    if len(cur):
        runs.append(np.array(cur))
    return [resample(r, step) if len(r) > 1 else r for r in runs]


def letter_points(sig: dict, letter_at, use_retrace=False):
    """letter -> list of (points[N,2], tangents[N,2]) runs in time order, from main strokes."""
    out: dict = {}
    for s in sig["strokes"]:
        if s["kind"] != "main" or len(s["pts"]) == 0:
            continue
        pts = s["pts"]
        keep = np.ones(len(pts), bool) if use_retrace else (np.asarray(s["retrace"]) == 0)
        for run in _resample_runs(pts, keep):
            if len(run) == 0:
                continue
            ks = letter_at(run)
            tg = _tangents(run)
            # split the run at letter changes
            start = 0
            for i in range(1, len(run) + 1):
                if i == len(run) or ks[i] != ks[start]:
                    k = ks[start]
                    if k >= 0:
                        out.setdefault(k, []).append((run[start:i], tg[start:i]))
                    start = i
    return out


def winding(sig: dict, cy: float, cx: float, R: float) -> float:
    """The largest angle swept round (cy, cx) by one continuous pen-down stretch of a main stroke, counting only steps
    whose both ends lie within R of the centre (retraced steps count 0, so a loop gone round and then retraced still
    counts once).  A stroke merely passing by sweeps at most about pi; going round a loop sweeps about 2 pi."""
    best = 0.0
    for s in sig["strokes"]:
        if s["kind"] != "main":
            continue
        p = s["pts"]
        rt = np.asarray(s["retrace"])
        if len(p) < 2:
            continue
        d = np.hypot(p[:, 0] - cy, p[:, 1] - cx)
        a = np.arctan2(p[:, 0] - cy, p[:, 1] - cx)
        da = (np.diff(a) + np.pi) % (2 * np.pi) - np.pi
        ok = (d[1:] <= R) & (d[:-1] <= R) & (d[1:] > 0.5) & (d[:-1] > 0.5) & (rt[1:] == 0)
        cum = np.r_[0.0, np.cumsum(np.where(ok, da, 0.0))]
        best = max(best, float(np.max(cum - np.minimum.accumulate(cum))), float(np.max(np.maximum.accumulate(cum) - cum)))
    return best


def counters(owner, text):
    out = []
    for c in sorted({int(c) for c in np.unique(owner) if c >= 0}):
        m = (owner == c).astype(np.uint8)
        cs, hier = cv2.findContours(m, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_NONE)
        if hier is None:
            continue
        for j, h in enumerate(hier[0]):
            if h[3] < 0:
                continue
            hole = np.zeros_like(m)
            cv2.drawContours(hole, cs, j, 1, -1)
            hole &= (1 - m)
            if hole.sum() < 4:
                continue
            ys, xs = np.where(hole > 0)
            out.append(dict(c=c, ch=text[c] if c < len(text) else "?", cy=float(ys.mean()), cx=float(xs.mean()),
                            r=float(np.sqrt(hole.sum() / np.pi)), hole=hole > 0))
    return out


def _dense(polys, step: float = 1.0):
    out = [resample(p, step) for p in polys if len(p) > 1]
    return np.vstack(out) if out else np.zeros((0, 2))


def _exits(polys, cy: float, cx: float, rad: float):
    """Branch directions round (cy, cx): the angles of the polylines' points in the ring between rad and 1.7 x rad,
    in 10-degree bins, neighbouring non-empty bins merged; each branch's direction is its points' circular mean.
    Measured away from the centre, so smoothing that cuts a junction's corner does not move it."""
    P = _dense(polys)
    if not len(P):
        return []
    d = np.hypot(P[:, 0] - cy, P[:, 1] - cx)
    q = P[(d >= rad) & (d <= 1.7 * rad)]
    if len(q) < 2:
        return []
    ang = np.arctan2(q[:, 0] - cy, q[:, 1] - cx)
    nb = 36
    h = np.bincount(((ang + np.pi) / (2 * np.pi) * nb).astype(int) % nb, minlength=nb) >= 2
    if h.all():
        return []
    s0 = int(np.argmin(h))                                             # start the scan at an empty bin
    clusters, cur = [], []
    for i in range(1, nb + 1):
        b = (s0 + i) % nb
        if h[b]:
            cur.append(b)
        elif cur:
            clusters.append(cur)
            cur = []
    if cur:
        clusters.append(cur)
    out = []
    for c in clusters:
        lo = (np.array(c) - nb / 2 + 0.5) * 2 * np.pi / nb
        sel = np.isin(((ang + np.pi) / (2 * np.pi) * nb).astype(int) % nb, c)
        m = np.array([np.sin(ang[sel]).mean(), np.cos(ang[sel]).mean()])
        out.append(m / (np.linalg.norm(m) + 1e-9))
    return out


def junctions(ink: np.ndarray, M: dict, truth: dict | None = None):
    """Junctions of the clean centre line: [(y, x, [branch unit directions], radius)].  Junction nodes closer than the
    disk are one junction (a thinned X gives two nodes); its branches are where the clean centre line crosses the
    disk's rim, so the truth and a rebuilt path are measured the same way."""
    out = []
    n, lab = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    rad = max(4.0, 1.6 * M["stroke"])
    for k in range(1, n):
        mk = lab == k
        if mk.sum() < 0.5 * M["stroke"] * M["rise"]:
            continue
        G = skeleton_graph(mk, spur=1.6 * M["stroke"])
        if G is None:
            continue
        polys = [d["pts"] for _, _, d in G.edges(data=True)]
        if truth is not None:                                          # branches measured on the truth path itself
            polys = [st["pts"] for st in truth["strokes"] if st["kind"] == "main"]
        nodes = [np.array(G.nodes[v]["p"]) for v in G.nodes if G.degree(v) >= 3]
        groups = []
        for c in nodes:
            for g in groups:
                if min(np.linalg.norm(c - q) for q in g) < rad:
                    g.append(c)
                    break
            else:
                groups.append([c])
        for g in groups:
            c = np.mean(g, axis=0)
            dirs = _exits(polys, c[0], c[1], rad)
            if len(dirs) >= 3:
                out.append((float(c[0]), float(c[1]), dirs, rad))
    return out


def path_exits(sig: dict, cy: float, cx: float, rad: float):
    return _exits([s["pts"] for s in sig["strokes"] if s["kind"] == "main"], cy, cx, rad)


def truth82(ink, owner, text):
    """synth79.truth_path, with the first letter of each piece walked by the 'top' start rule, and a letter whose body
    is drawn by a ligature neighbour (its largest part is mark-sized) left out of the letters."""
    from sig79 import add_thickness, smooth, walk
    num, n = letters_of(text)
    M = line_metrics(ink)
    step = max(1.0, 0.12 * M["rise"])
    _, piece_of = cv2.connectedComponents(ink.astype(np.uint8), connectivity=8)
    strokes, pending, cur = [], [], None

    def flush():
        for m in sorted(pending, key=lambda m: -m["pts"][:, 1].mean()):
            strokes.append(m)
        pending.clear()

    for c in sorted({int(c) for c in np.unique(owner) if c >= 0}):
        m = owner == c
        k = num.get(c, -1)
        nl, lab, st, cen = cv2.connectedComponentsWithStats(m.astype(np.uint8), 8)
        if nl < 2:
            continue
        parts = sorted(range(1, nl), key=lambda j: -st[j][4])
        main_j = parts[0]
        small = st[main_j][4] < 1.2 * M["stroke"] ** 2 * 2
        for j in parts:
            comp = lab == j
            G = skeleton_graph(comp, spur=1.6 * M["stroke"])
            vals = piece_of[comp]
            pc = int(np.bincount(vals[vals > 0]).argmax()) if (vals > 0).any() else -1
            first = j == main_j and not small and pc != cur
            segs = walk(G, "top" if first else "baseline", M, 0.0)
            if not segs:
                continue
            P = [resample(sg, step) for sg, _ in segs]
            pts = np.vstack(P)
            rt = np.concatenate([np.full(len(q), t) for q, (_, t) in zip(P, segs)])
            if j == main_j and not small:
                if cur is not None and pc != cur:
                    flush()
                strokes.append(dict(kind="main", pts=smooth(pts), retrace=rt, letter=k, cont=(pc == cur)))
                cur = pc
            else:
                if len(pts) > 1 and pts[0][1] < pts[-1][1]:
                    pts, rt = pts[::-1], rt[::-1]
                pending.append(dict(kind="mark", pts=pts, retrace=np.zeros(len(pts), int), letter=k,
                                    above=bool(cen[j][1] < M["baseline"] - 0.3 * M["rise"])))
    flush()
    return add_thickness(dict(strokes=strokes, M=M, n_letters=n), ink)


def shape_score(rec: dict, truth: dict, owner: np.ndarray, text: str, ink: np.ndarray) -> dict:
    """The shape metric of one rebuilt path against the truth (see the module doc)."""
    num, n = letters_of(text)
    near, dist = nearest_owner(owner)
    Mc = line_metrics(ink)
    sw = Mc["stroke"]
    H, W = owner.shape
    far = Mc["rise"]

    def letter_at(p):
        y = np.clip(np.round(p[:, 0]).astype(int), 0, H - 1)
        x = np.clip(np.round(p[:, 1]).astype(int), 0, W - 1)
        c = near[y, x]
        ok = dist[y, x] <= far
        return np.array([num.get(int(cc), -1) if o and cc >= 0 else -1 for cc, o in zip(c, ok)])

    T = {}
    for s in truth["strokes"]:
        if s["kind"] != "main" or s["letter"] < 0 or len(s["pts"]) == 0:
            continue
        keep = np.asarray(s["retrace"]) == 0
        for run in _resample_runs(s["pts"], keep):
            T.setdefault(s["letter"], []).append((run, _tangents(run)))
    Rp = letter_points(rec, letter_at)
    letters = []
    for k, runs in sorted(T.items()):
        tp = np.vstack([r for r, _ in runs])
        tt = np.vstack([t for _, t in runs])
        ch = None
        for c, kk in num.items():
            if kk == k:
                ch = text[c]
        if k not in Rp:
            letters.append(dict(k=k, ch=ch, missed=1))
            continue
        rp = np.vstack([r for r, _ in Rp[k]])
        rt = np.vstack([t for _, t in Rp[k]])
        D = np.sqrt(((rp[:, None, :] - tp[None, :, :]) ** 2).sum(-1))
        a, b = D.min(1), D.min(0)
        j = D.argmin(1)
        cos = (rt * tt[j]).sum(1)
        fr = min(frechet(rp[:400], tp[:400]), frechet(rp[:400], tp[::-1][:400]))
        letters.append(dict(k=k, ch=ch, missed=0, frechet=round(fr, 2), mean_d=round(float((a.mean() + b.mean()) / 2), 2),
                            max_d=round(float(max(a.max(), b.max())), 2), dir_ok=round(float((cos > 0.707).mean()), 3),
                            dir_rev=round(float((cos < -0.707).mean()), 3)))
    loops = []
    for c in counters(owner, text):
        if c["ch"] not in LOOP_LETTERS:
            continue
        R = 1.6 * c["r"] + sw + 2
        wt = winding(truth, c["cy"], c["cx"], R)
        if abs(wt) < 1.6 * np.pi:
            continue                                                   # the truth path itself does not go round it
        wr = winding(rec, c["cy"], c["cx"], R)
        loops.append(dict(ch=c["ch"], loop=int(abs(wr) >= 1.6 * np.pi), r=round(c["r"], 1)))
    juncs = []
    for (cy, cx, dirs, rad) in junctions(ink, Mc, truth):
        ex = path_exits(rec, cy, cx, rad)
        ok = len(ex) == len(dirs) and all(max(float(np.dot(d, e)) for e in ex) > math.cos(math.radians(35)) for d in dirs)
        juncs.append(int(ok))
    return dict(stroke=round(sw, 2), letters=letters, loops=loops, juncs=juncs)


def summarise(rows: list[dict]) -> dict:
    """Mean metric over rows (each a shape_score dict).  shape_ok: share of letters (missed ones count as wrong) whose
    rebuilt stretch lies within 1.5 stroke widths of the truth everywhere and vice versa (Hausdorff)."""
    L = [(l, r["stroke"]) for r in rows for l in r["letters"]]
    hit = [l for l, _ in L if not l["missed"]]
    lp = [x["loop"] for r in rows for x in r["loops"]]
    jn = [x for r in rows for x in r["juncs"]]
    fr = np.array([l["frechet"] for l in hit]) if hit else np.zeros(1)
    sw = float(np.mean([r["stroke"] for r in rows])) if rows else 1.0
    return dict(lines=len(rows), letters=len(L), missed=round(1 - len(hit) / max(1, len(L)), 4),
                mean_d=round(float(np.mean([l["mean_d"] for l in hit])), 2) if hit else None,
                max_d=round(float(np.mean([l["max_d"] for l in hit])), 2) if hit else None,
                shape_ok=round(float(np.mean([(not l["missed"]) and l["max_d"] <= 1.5 * s for l, s in L])), 3) if L else None,
                frechet=round(float(fr.mean()), 2), stroke=round(sw, 2),
                dir_ok=round(float(np.mean([l["dir_ok"] for l in hit])), 3) if hit else None,
                dir_rev=round(float(np.mean([l["dir_rev"] for l in hit])), 3) if hit else None,
                loops=len(lp), loop_ok=round(float(np.mean(lp)), 3) if lp else None,
                juncs=len(jn), junc_ok=round(float(np.mean(jn)), 3) if jn else None)


def overlay(grey: np.ndarray, rec: dict, truth: dict, owner: np.ndarray, text: str, ink: np.ndarray, sc: dict | None = None,
            scale: int = 3, label: str = "") -> np.ndarray:
    """The ink pale; truth path thick green; rebuilt path red (retraces thin grey); letters whose rebuilt stretch strays
    more than 1.5 stroke widths from the truth (Hausdorff) get their number in red; counters: a blue circle if the rebuilt path goes round, an orange cross
    if not; junctions: a small square, green if the branches match, magenta if not."""
    sc = sc or shape_score(rec, truth, owner, text, ink)
    h, w = grey.shape
    img = cv2.cvtColor(cv2.resize((255 - (255 - grey.astype(np.float32)) * 0.3).astype(np.uint8), (w * scale, h * scale),
                                  interpolation=cv2.INTER_NEAREST), cv2.COLOR_GRAY2BGR)

    def pl(p, col, th):
        p = p * scale
        for i in range(1, len(p)):
            cv2.line(img, (int(p[i - 1][1]), int(p[i - 1][0])), (int(p[i][1]), int(p[i][0])), col, th, cv2.LINE_AA)

    for s in truth["strokes"]:
        if s["kind"] == "main":
            pl(s["pts"], (60, 170, 60), 5)
    for s in rec["strokes"]:
        if s["kind"] != "main":
            for q in s["pts"]:
                cv2.circle(img, (int(q[1] * scale), int(q[0] * scale)), 2, (40, 40, 200), -1)
            continue
        p, rt = s["pts"], np.asarray(s["retrace"])
        for i in range(1, len(p)):
            col, th = ((90, 90, 90), 1) if rt[i] else ((30, 30, 220), 2)
            cv2.line(img, (int(p[i - 1][1] * scale), int(p[i - 1][0] * scale)), (int(p[i][1] * scale), int(p[i][0] * scale)), col, th, cv2.LINE_AA)
    sw = sc["stroke"]
    for l in sc["letters"]:
        ts = [s for s in truth["strokes"] if s["kind"] == "main" and s["letter"] == l["k"] and len(s["pts"])]
        if not ts:
            continue
        p = ts[0]["pts"][len(ts[0]["pts"]) // 2] * scale
        bad = l["missed"] or l["max_d"] > 1.5 * sw
        cv2.putText(img, str(l["k"] + 1), (int(p[1]) - 5, int(h * scale - 6)), cv2.FONT_HERSHEY_SIMPLEX, 0.45,
                    (0, 0, 220) if bad else (0, 120, 0), 1, cv2.LINE_AA)
    cs = [c for c in counters(owner, text) if c["ch"] in LOOP_LETTERS]
    for c in cs:
        R = 1.6 * c["r"] + sw + 2
        if abs(winding(truth, c["cy"], c["cx"], R)) < 1.6 * np.pi:
            continue
        ok = abs(winding(rec, c["cy"], c["cx"], R)) >= 1.6 * np.pi
        ctr = (int(c["cx"] * scale), int(c["cy"] * scale))
        if ok:
            cv2.circle(img, ctr, int(c["r"] * scale) + 4, (200, 120, 0), 2, cv2.LINE_AA)
        else:
            cv2.drawMarker(img, ctr, (0, 140, 255), cv2.MARKER_TILTED_CROSS, 14, 3)
    for (cy, cx, dirs, rad), ok in zip(junctions(ink, line_metrics(ink), truth), sc["juncs"]):
        col = (0, 160, 0) if ok else (200, 0, 200)
        cv2.rectangle(img, (int(cx * scale) - 4, int(cy * scale) - 4), (int(cx * scale) + 4, int(cy * scale) + 4), col, 2)
    if label:
        bar = np.full((24, img.shape[1], 3), 255, np.uint8)
        cv2.putText(bar, label, (4, 17), cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 1, cv2.LINE_AA)
        img = np.vstack([bar, img])
    return img
