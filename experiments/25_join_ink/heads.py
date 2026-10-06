"""Heads along the pen path: a lump of ink (a filled loop: the head of و, ف, ق, م…) that hangs from ONE point of the
path. For each path position s: the box of the ink rooted there; a head is at least `HW` x the line's rise wide and
tall and does not reach a tall stroke's height.  heads.py stats VARIANT -> per letter-form share with a head inside."""
import sys
import numpy as np

HW = 0.3


def head_positions_dt(p, k=1.6):
    """A path position whose rooted ink is much thicker than a stroke: a lump (a filled head)."""
    import cv2
    ink = p["ink_s"]; S = p["G"]["W"]; main = (ink >= 0).astype(np.uint8)
    dt = cv2.distanceTransform(np.pad(main, 1), cv2.DIST_L2, 5)[1:-1, 1:-1]
    ys, xs = np.where(ink >= 0); s = ink[ys, xs]; m = np.zeros(S); np.maximum.at(m, s, dt[ys, xs])
    st = np.median(m[m > 0]) if (m > 0).any() else 1.0
    return [int(i) for i in range(S) if m[i] >= k * st]


def head_positions(p, hw=HW):
    ink = p["ink_s"]; S = p["G"]["W"]; rise = 26.0 / p["sc"]; base = p["base"]
    ys, xs = np.where(ink >= 0); s = ink[ys, xs]
    y0 = np.full(S, 10 ** 6); y1 = np.full(S, -1); x0 = np.full(S, 10 ** 6); x1 = np.full(S, -1)
    np.minimum.at(y0, s, ys); np.maximum.at(y1, s, ys); np.minimum.at(x0, s, xs); np.maximum.at(x1, s, xs)
    h = y1 - y0 + 1; w = x1 - x0 + 1; up = base - y0
    return [int(i) for i in range(S) if y1[i] >= 0 and h[i] >= hw * rise and w[i] >= hw * rise and up[i] < 0.75 * rise]


if __name__ == "__main__" and sys.argv[1] == "stats":
    from common import load, P
    from collections import defaultdict
    tab = defaultdict(lambda: [0, 0])
    for doc in ("0582", "0618", "1036", "0772"):
        for p in load(sys.argv[2], doc):
            hp = (head_positions_dt if len(sys.argv) > 3 else head_positions)(p)
            for k, (a, b) in enumerate(P.intervals(p)):
                kk = (P._base(p["units"][k]), p["forms"][k]); t = tab[kk]; t[1] += 1; t[0] += any(a <= x < b for x in hp)
    rows = sorted(tab.items(), key=lambda kv: -kv[1][1])
    print(" ".join(f"{l}{f[:2]}:{a}/{n}" for (l, f), (a, n) in rows if n >= 8))
