"""Letters along the pen path. The ink of a connected piece is thinned to its centre line; the trunk is the
path from the rightmost to the leftmost point of that line; every other bit of ink (an arm, an ascender, the
far side of a loop, a tail sweeping back) belongs to the trunk position it hangs from. The piece is thereby
unrolled into a strip indexed by distance along the pen path, and the same alignment as `geometry/letters`
cuts the strip — a cut is a point on the path, not a column on the page.

    python penpath.py <azure.json> <scan.pdf> <page,page,...> <out.png>
"""
import sys, json, random
from collections import deque
from pathlib import Path
import numpy as np, cv2, fitz
from inkscript.geometry import letters as L
from inkscript.geometry.letters import letters_of, line_geometry, piece_mask, analyse, align
from inkscript.text import pieces, MARKS
from inkscript.ocr.azure import load_azure
from inkscript.geometry.trace import page_blobs
from inkscript.geometry.layout import layout_page, split_word

NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]


def thin(img):
    I = img.astype(np.uint8).copy(); changed = True
    while changed:
        changed = False
        for it in (0, 1):
            P = np.pad(I, 1); p2, p3, p4, p5, p6, p7, p8, p9 = P[:-2, 1:-1], P[:-2, 2:], P[1:-1, 2:], P[2:, 2:], P[2:, 1:-1], P[2:, :-2], P[1:-1, :-2], P[:-2, :-2]
            B = p2 + p3 + p4 + p5 + p6 + p7 + p8 + p9; seq = [p2, p3, p4, p5, p6, p7, p8, p9, p2]
            A = sum(((seq[k] == 0) & (seq[k + 1] == 1)).astype(int) for k in range(8))
            c = (p2 * p4 * p6 == 0) & (p4 * p6 * p8 == 0) if it == 0 else (p2 * p4 * p8 == 0) & (p2 * p6 * p8 == 0)
            m = (I == 1) & (B >= 2) & (B <= 6) & (A == 1) & c
            if m.any(): I[m] = 0; changed = True
    return I


def bfs(sk, sources):
    dist = {s: 0 for s in sources}; prev = {s: None for s in sources}; root = {s: s for s in sources}; q = deque(sources)
    H, W = sk.shape
    while q:
        y, x = q.popleft()
        for dy, dx in NB:
            n = (y + dy, x + dx)
            if 0 <= n[0] < H and 0 <= n[1] < W and sk[n] and n not in dist:
                dist[n] = dist[(y, x)] + 1; prev[n] = (y, x); root[n] = root[(y, x)]; q.append(n)
    return dist, prev, root


def unroll(F, line, y_off):
    """Per-ink-pixel trunk position (0 = the left end of the pen path), and the strip's features."""
    main = F["main"]; sk = thin(main)
    ys, xs = np.where(sk)
    if len(xs) < 6: return None
    # The pen path starts where the first letter's body meets the baseline, not at the piece's rightmost ink: in a
    # typeface whose kaf throws its arm out to the right, the arm's tip became the start, the path ran down the arm,
    # and cuts were placed along it. An arm, like an ascender, must hang from the trunk.
    base_row = line["baseline"] - y_off; near = np.abs(ys - base_row) <= 0.35 * line["rise"]
    right_zone = near                                                 # however far an arm reaches beyond it
    i = np.where(right_zone)[0][np.argmax(xs[right_zone])] if right_zone.any() else int(np.argmax(xs))
    right = (int(ys[i]), int(xs[i])); left = (int(ys[np.argmin(xs)]), int(xs.min()))
    _, prev, _ = bfs(sk, [right])
    if left not in prev: return None
    trunk = []; n = left
    while n is not None: trunk.append(n); n = prev[n]                  # left end first
    S = len(trunk); pos = {p: i for i, p in enumerate(trunk)}
    _, _, root = bfs(sk, trunk)                                       # every other centre-line pixel hangs from a trunk pixel
    s_of = np.full(sk.shape, -1, int)
    for p, r in root.items(): s_of[p] = pos[r]
    _, lab = cv2.distanceTransformWithLabels((1 - sk).astype(np.uint8), cv2.DIST_L2, 5, labelType=cv2.DIST_LABEL_PIXEL)
    lab2s = {}
    for y, x in zip(ys, xs): lab2s[int(lab[y, x])] = s_of[y, x]
    ink_s = np.vectorize(lambda v: lab2s.get(int(v), -1))(lab); ink_s[~main] = -1
    H = main.shape[0]; top = np.full(S, H); bot = np.full(S, -1)
    for y, x in zip(*np.where(main)):
        s = ink_s[y, x]
        if s >= 0: top[s] = min(top[s], y); bot[s] = max(bot[s], y)
    has = bot >= 0; b0, b1, stroke = F["b0"], F["b1"], F["stroke"]
    base = line["baseline"] - y_off; rise = line["rise"]; drop = max(line["drop"], stroke); up = base - top; down = bot - base
    G = dict(W=S, stroke=stroke, has=has, asc=has & (up >= 0.6 * rise), tall=has & (up >= 0.8 * rise),
             desc=has & (down >= 0.5 * drop) & (down > stroke), deep=has & (down >= 0.75 * drop) & (down > 2 * stroke),
             thin=has & (top >= b0 - 1) & (bot <= b1 + 1), dots=[])
    sy, sx = np.array([p[0] for p in trunk]), np.array([p[1] for p in trunk])
    for (cx, above), k in zip(F["dots"], F["dot_labels"]):
        cy = np.where(F["lab"] == k)[0].mean(); G["dots"].append((int(np.argmin((sx - cx) ** 2 + 0.25 * (sy - cy) ** 2)), above))
    return G, ink_s, sk, trunk


COLS = [(40, 40, 220), (220, 120, 30), (40, 160, 40), (170, 40, 170), (30, 170, 200), (120, 120, 120), (20, 90, 160)]


def picture(F, ink_s, cuts, G, n, up=5):
    H, W = F["main"].shape; im = np.full((H, W, 3), 255, np.uint8); bounds = [0] + list(cuts) + [G["W"]]
    for k in range(n):                                                # k-th letter in reading order = k-th interval from the right end
        a, b = bounds[n - 1 - k], bounds[n - k]; im[(ink_s >= a) & (ink_s < b)] = COLS[k % len(COLS)]
    for (s, above), lab_id in zip(G["dots"], F["dot_labels"]):
        k = next((k for k in range(n) if bounds[n - 1 - k] <= s < bounds[n - k]), 0); im[F["lab"] == lab_id] = COLS[k % len(COLS)]
    return cv2.resize(im, None, fx=up, fy=up, interpolation=cv2.INTER_NEAREST)


def collect(azure, scan, pages):
    words, _, dims = load_azure(Path(azure)); j = json.load(open(azure)); ar = j.get("analyzeResult", j); az = {p["pageNumber"]: p for p in ar["pages"]}
    doc = fitz.open(scan); got = []; tried = 0
    for pn in pages:
        pw = [w for w in words if w["page"] == pn]; pix = doc[pn - 1].get_pixmap(dpi=300, colorspace=fitz.csGRAY); gray = np.frombuffer(pix.samples, np.uint8).reshape(pix.h, pix.w)
        _, ink = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV | cv2.THRESH_OTSU); ink = ink > 0
        W_in, H_in = dims[pn]; blobs = page_blobs(gray); lines, _ = layout_page(pw, [w["text"] for w in pw], az[pn].get("lines", []), blobs, gray.shape[1] / W_in, gray.shape[0] / H_in)
        for Ln in lines:
            bl = [b for w in Ln if w["blobs"] for b in w["blobs"]]
            if not bl: continue
            lh = max(1.0, max(b["y"] + b["h"] for b in bl) - min(b["y"] for b in bl)); lg = line_geometry(ink, bl)
            if not lg or lg["rise"] < 10: continue
            for w in Ln:
                if not w["blobs"] or MARKS.search(w["text"]): continue
                for pc in split_word(w, lh):
                    t = pc["text"].strip(); u = letters_of(t)
                    if len(pieces(t)) != 1 or len(u) < 2: continue
                    tried += 1; m, off = piece_mask(pc["blobs"]); F = analyse(m, lg, off[1])
                    if F is None: continue
                    r = unroll(F, lg, off[1])
                    if r is None: continue
                    G, ink_s, sk, trunk = r; cuts = align(u, G)
                    if cuts is None: continue
                    col = L.plan(u, pc["blobs"], lg)
                    got.append(dict(text=t, units=u, n=len(u), F=F, G=G, ink_s=ink_s, cuts=cuts, column=col is not None, line=lg, off=off, page=pn))
    return got, tried


def main(azure, scan, pages, out, want=56, seed=5):
    got, tried = collect(azure, scan, pages)
    print(f"pieces of 2+ letters: {tried}; cut along the pen path: {len(got)}; of those the column method also cut: {sum(g['column'] for g in got)}")
    random.seed(seed); hard = [g for g in got if not g["column"]]; easy = [g for g in got if g["column"]]
    sample = random.sample(hard, min(want // 2, len(hard))) + random.sample(easy, min(want - min(want // 2, len(hard)), len(easy)))
    tiles = []
    for g in sample:
        im = picture(g["F"], g["ink_s"], g["cuts"], g["G"], g["n"])
        tiles.append(cv2.copyMakeBorder(im, 8, 8, 8, 8, cv2.BORDER_CONSTANT, value=(255, 255, 255) if g["column"] else (215, 235, 255)))
    h = max(t.shape[0] for t in tiles); rows = []; row = []; wsum = 0
    for t in tiles:
        t = cv2.copyMakeBorder(t, 0, h - t.shape[0], 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
        if wsum + t.shape[1] > 2400 and row: rows.append(np.hstack(row)); row = []; wsum = 0
        row.append(t); wsum += t.shape[1]
    if row: rows.append(np.hstack(row))
    wmax = max(r.shape[1] for r in rows); cv2.imwrite(out, np.vstack([cv2.copyMakeBorder(r, 0, 0, 0, wmax - r.shape[1], cv2.BORDER_CONSTANT, value=(255, 255, 255)) for r in rows]))
    print([g["text"] for g in sample])


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(p) for p in sys.argv[3].split(",")], sys.argv[4])
