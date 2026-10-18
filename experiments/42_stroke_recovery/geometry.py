"""A fixed rasterisation and a text-blind adapter around experiment 16's walk."""
from __future__ import annotations

import importlib.util
from pathlib import Path
import sys

import cv2
import numpy as np

from inkscript.geometry.letters import analyse
from inkscript.geometry import penpath as P

HERE = Path(__file__).resolve().parent
WIDTH, HEIGHT, PAD, STROKE = 384, 128, 8, 3


def normalise(strokes, width=WIDTH, height=HEIGHT):
    arrays = [np.asarray(s, dtype=float)[:, :2] for s in strokes if len(s)]
    if not arrays or not all(np.isfinite(a).all() and a.shape[1] == 2 for a in arrays):
        raise ValueError("Drawing needs finite x,y points")
    xy = np.concatenate(arrays)
    low, high = xy.min(0), xy.max(0)
    scale = min((width - 2 * PAD) / max(high[0] - low[0], 1),
                (height - 2 * PAD) / max(high[1] - low[1], 1))
    offset = (np.array([width, height]) - (high - low) * scale) / 2
    return [((a - low) * scale + offset).round(3).tolist() for a in arrays]


def render(strokes, width=WIDTH, height=HEIGHT, thickness=STROKE):
    image = np.full((height, width), 255, np.uint8)
    for stroke in strokes:
        if not len(stroke):
            continue
        pts = np.rint(np.asarray(stroke)[:, :2]).astype(np.int32)
        cv2.polylines(image, [pts], False, 0, thickness, cv2.LINE_AA)
        for p in (pts[0], pts[-1]):
            cv2.circle(image, tuple(p), thickness // 2, 0, -1, cv2.LINE_AA)
    return image


def _feeler():
    parent = HERE.parent / "16_feel"
    sys.path.insert(0, str(parent)) if str(parent) not in sys.path else None
    spec = importlib.util.spec_from_file_location("stroke42_feel", parent / "feel.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


_FEEL = None


def recover(image):
    """Apply the old trunk/branch walk to components, ordered right to left.

    A word may have several disconnected bodies. No annotated stroke or letter
    boundaries enter this adapter. Components the old unroll cannot traverse
    are retained as explicit failures, not silently replaced by a better walk.
    """
    global _FEEL
    if _FEEL is None:
        _FEEL = _feeler()
    mask = image < 128
    n, labels, stats, centres = cv2.connectedComponentsWithStats(mask.astype(np.uint8), 8)
    baseline = int(mask.sum(1).argmax())
    ys = np.where(mask)[0]
    line = dict(baseline=baseline, rise=max(10, baseline - int(ys.min())) if len(ys) else 10,
                drop=max(3, int(ys.max()) - baseline) if len(ys) else 3)
    order = sorted(range(1, n), key=lambda k: (-centres[k, 0], centres[k, 1]))
    strokes, failures, dots = [], [], 0
    for k in order:
        x, y, w, h, area = map(int, stats[k])
        crop = labels[y:y + h, x:x + w] == k
        skeleton = P.thin(crop)
        if skeleton.sum() < 6:
            # A point-like component remains a tap; its thickness is not motion.
            yy, xx = np.where(crop)
            strokes.append([[float(xx.mean() + x), float(yy.mean() + y)]])
            dots += 1
            continue
        F = analyse(crop, line, y)
        unrolled = P.unroll(F, line, y) if F else None
        if unrolled is None:
            failures.append(dict(box=[x, y, w, h], ink_pixels=area, reason="legacy_unroll_failed"))
            continue
        _, _, trunk = unrolled
        points, _ = _FEEL.walk(dict(F=F, trunk=trunk))
        if not len(points):
            failures.append(dict(box=[x, y, w, h], ink_pixels=area, reason="empty_walk"))
            continue
        xy = points[:, ::-1] + [x, y]
        strokes.append(xy.round(3).tolist())
    drawn = render(strokes, image.shape[1], image.shape[0]) < 128
    tolerance = cv2.dilate(drawn.astype(np.uint8), np.ones((3, 3), np.uint8)).astype(bool)
    ink = max(1, int(mask.sum()))
    return dict(strokes=strokes, failures=failures, components=n - 1, taps=dots,
                ink_coverage=float((mask & tolerance).sum() / ink),
                ink_iou=float((mask & drawn).sum() / max(1, (mask | drawn).sum())),
                provenance="inferred: experiment-16 trunk/branch walk, applied per raster component; "
                           "right-to-left component order; uniform playback has no historical timing")


def sequence(strokes, frames=128):
    """Arc-length sampling with pen-up boundaries, no annotation labels or timing guesses."""
    arrays = [np.asarray(s, np.float32)[:, :2] for s in strokes if len(s)]
    if not arrays:
        return np.zeros((frames, 6), np.float32)
    lengths = np.array([max(1., np.linalg.norm(np.diff(a, axis=0), axis=1).sum()) for a in arrays])
    # Keep every stroke boundary, even if the drawing needs more than frames.
    counts = np.maximum(1, np.floor(lengths / lengths.sum() * (frames - len(arrays))).astype(int) + 1)
    while counts.sum() < frames:
        counts[int(np.argmax(lengths / counts))] += 1
    while counts.sum() > frames and (counts > 1).any():
        k = int(np.argmax(np.where(counts > 1, counts / lengths, -1)))
        counts[k] -= 1
    rows = []
    for points, count in zip(arrays, counts):
        arc = np.r_[0, np.cumsum(np.linalg.norm(np.diff(points, axis=0), axis=1))]
        wanted = np.linspace(0, arc[-1], count)
        xy = np.column_stack([np.interp(wanted, arc, points[:, j]) for j in (0, 1)])
        xy = (xy - [WIDTH / 2, HEIGHT / 2]) / HEIGHT
        delta = np.vstack([np.zeros((1, 2)), np.diff(xy, axis=0)])
        start, end = np.zeros(count), np.zeros(count)
        start[0], end[-1] = 1, 1
        rows.append(np.column_stack([xy, delta, start, end]))
    return np.concatenate(rows).astype(np.float32)
