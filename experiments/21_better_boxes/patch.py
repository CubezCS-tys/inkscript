"""The proposed change to src/inkscript/geometry/penpath.py, as patched copies applied to the imported module in
this process only (src/ is not edited; the same change as a diff: penpath.patch).

1. `unroll`: the pen path ENDS where the last letter meets the baseline, not at the top of a final alef. The left end
   was the leftmost point of the centre line; a final alef's stem usually leans so that its top is leftmost, and the
   path then ran down the stem: the alef's stretch was the top of its stem, the cut fell part-way down it, and the
   alef's selection box (its stretch in page x) was a sliver from the stem's left edge to its centre line.
   Now, when the path from its left end first climbs down a tall, nearly vertical stroke to the row the rest of the
   path runs along, the path ends at the foot of that stroke (`stem_foot`); the stem hangs from that one point, like
   any other tall stroke.
"""
import numpy as np, cv2
from inkscript.geometry import penpath as P

ORIG = dict(unroll=P.unroll, letter_blobs=P.letter_blobs)
FLAGS = dict(end=True)


def unroll(F: dict, line: dict, y_off: int, start: str = "baseline"):
    """penpath.unroll with the path's left end on the baseline band (see module doc)."""
    main = F["main"]; sk = P.thin(main); ys, xs = np.where(sk)
    if len(xs) < 6:
        return None
    dyb = ys - (line["baseline"] - y_off); near = (dyb >= -0.35 * line["rise"]) & (dyb <= 0.15 * line["rise"])
    if not near.any(): near = np.abs(dyb) <= 0.35 * line["rise"]
    if start == "upper":
        up = dyb <= -0.2 * line["rise"]
        if not up.any(): return None
        near = up
    i = np.where(near)[0][np.argmax(xs[near])] if near.any() else int(np.argmax(xs))
    right = (int(ys[i]), int(xs[i])); left = (int(ys[np.argmin(xs)]), int(xs.min()))
    prev, _ = P._bfs(sk, [right])
    if left not in prev:
        return None
    trunk = []; n = left
    while n is not None: trunk.append(n); n = prev[n]
    if FLAGS["end"]:
        j = stem_foot(trunk, line["rise"])
        if j: trunk = trunk[j:]
    S = len(trunk); pos = {p: k for k, p in enumerate(trunk)}
    _, root = P._bfs(sk, trunk)
    s_of = np.full(sk.shape, -1, int)
    for p, r in root.items(): s_of[p] = pos[r]
    _, lab = cv2.distanceTransformWithLabels((1 - sk).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    table = np.full(int(lab.max()) + 1, -1, int); table[lab[ys, xs]] = s_of[ys, xs]
    ink_s = table[lab]; ink_s[~main] = -1
    H = main.shape[0]; top = np.full(S, H); bot = np.full(S, -1); my, mx = np.where(ink_s >= 0); ms = ink_s[my, mx]
    np.minimum.at(top, ms, my); np.maximum.at(bot, ms, my)
    has = bot >= 0; b0, b1, stroke = F["b0"], F["b1"], F["stroke"]
    base = line["baseline"] - y_off; rise = line["rise"]; drop = max(line["drop"], stroke); up = base - top; down = bot - base
    G = dict(W=S, stroke=stroke, has=has, asc=has & (up >= 0.6 * rise), tall=has & (up >= 0.8 * rise),
             desc=has & (down >= 0.5 * drop) & (down > stroke), deep=has & (down >= 0.75 * drop) & (down > 2 * stroke),
             thin=has & (top >= b0 - 1) & (bot <= b1 + 1), dots=[])
    sy, sx = ys, xs; s_at_pix = s_of[ys, xs]
    G["marks"] = []
    for (cx, above), k in zip(F["dots"], F["dot_labels"]):
        yy, xx = np.where(F["lab"] == k); s_at = int(s_at_pix[int(np.argmin((sx - cx) ** 2 + 0.25 * (sy - yy.mean()) ** 2))]); G["marks"].append((s_at, above, k))
        w, h = xx.max() - xx.min() + 1, yy.max() - yy.min() + 1
        if not (w >= 3 * h and w > 1.5 * stroke): G["dots"].append((s_at, above))
    return G, ink_s, trunk


def stem_foot(trunk, rise):
    """Index of the foot of a tall stroke that the path climbs down at its left end (a final alef), or 0.
    The path from its left end runs DOWN by at least 0.6 x the line's rise, mostly vertically, to the row along
    which the rest of the path runs (its median row, within a fifth of the rise)."""
    t = np.array(trunk); y, x = t[:, 0], t[:, 1]; j = 0
    flat = lambda j: (lambda e: x[e] - x[j] >= 2 and y[e] - y[j] <= 1)(min(j + 3, len(t) - 1))
    while j + 1 < len(t) and y[j + 1] >= y[j] and not flat(j): j += 1          # down the stroke, until the path turns flat
    drop = y[j] - y[0]; base = np.median(y[j:])
    if drop >= 0.6 * rise and abs(int(x[j]) - int(x[0])) <= 0.5 * drop and y[j] >= base - 0.2 * rise and j < len(t) - 6:
        return j
    return 0


def apply():
    P.unroll = unroll


def restore():
    P.unroll = ORIG["unroll"]; P.letter_blobs = ORIG["letter_blobs"]
