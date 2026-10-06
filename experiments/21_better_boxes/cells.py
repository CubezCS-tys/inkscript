"""Offline study of cells: the stored plans of the sample pages, today's cell rule and the new one, matched to
experiment 18's sample words.

    ../../.venv/bin/python cells.py check            # today's rule on the stored plans reproduces 18's cutter boxes?
    ../../.venv/bin/python cells.py draw WORDID ...  # piece pictures: ink by letter, trunk, cuts, cells old/new
"""
import sys, json, pickle
from pathlib import Path
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; REPO = HERE.parents[1]; E18 = REPO / "experiments/18_boxes"
sys.path.insert(0, str(REPO / "src")); sys.path.insert(0, str(HERE)); sys.path.insert(0, str(E18))
from inkscript.geometry import penpath as P

_PL = {}


def plans(doc, variant="orig"):
    if (doc, variant) not in _PL:
        _PL[(doc, variant)] = pickle.load(open(HERE / f"out/plans/{variant}_{doc}.pkl", "rb"))
        for p in _PL[(doc, variant)]: p["cache"] = {}
    return _PL[(doc, variant)]


def cells_orig(p):
    """Today's rule (penpath.letter_blobs): each letter's stretch of the trunk, in page x; reading order."""
    x_off = p["off"][0]; S = p["G"]["W"]; trunk = p["trunk"]
    ys, xs = np.where(p["ink_s"] >= 0); X = lambda s: int(xs.min()) if s <= 0 else int(xs.max()) + 1 if s >= S else int(trunk[s][1])
    bounds = [0] + list(p["cuts"]) + [S]; bx = [X(s) for s in bounds]
    if any(b - a < 2 for a, b in zip(bx, bx[1:])):
        bx = [int(round(bx[0] + (bx[-1] - bx[0]) * s / S)) for s in bounds]
        if any(b - a < 2 for a, b in zip(bx, bx[1:])): return None
    cell = dict(zip(bounds, bx))
    return [(cell[a] + x_off, cell[b] + x_off) for a, b in P.intervals(p)]


def piece_x(p):
    ys, xs = np.where(p["ink_s"] >= 0); return xs.min() + p["off"][0], xs.max() + 1 + p["off"][0]


def match(w, doc, variant="orig"):
    """The stored plans of the word's joined pieces, in reading order of pieces: {piece index: plan}."""
    x0, y0, x1, y1 = w["box"]; out = {}
    pcs = {}
    for i, k in enumerate(w["piece_of"]): pcs.setdefault(k, []).append(i)
    cand = [p for p in plans(doc, variant) if p["page"] == w["page"]]
    for k, idx in pcs.items():
        if len(idx) < 2: continue
        units = [w["text"][i] for i in idx]
        best = None
        for p in cand:
            if [P._base(u) for u in p["units"]] != [P._base(u) for u in units]: continue
            ys, xs = np.where(p["ink_s"] >= 0); px0, px1 = piece_x(p); py = ys.mean() + p["off"][1]
            if not (y0 - 5 <= py <= y1 + 5): continue
            ov = min(px1, x1) - max(px0, x0)
            if ov > 0.8 * (px1 - px0):
                # the piece's letters sit at w's letter positions idx: compare with the cutter's cells there
                c = [w["cutter"][i] for i in idx]; d = abs(min(a for a, _ in c) - px0) + abs(max(b for _, b in c) - px1)
                if best is None or d < best[0]: best = (d, p)
        if best is not None: out[k] = (idx, best[1])
    return out


def retile(cells):
    """Reading-order cells -> what the PDF highlights: each glyph's advance runs up to the next glyph on its right
    (type3: adv = max(own width, next origin - origin)), visual order left to right."""
    order = sorted(range(len(cells)), key=lambda i: cells[i][0]); out = list(cells)
    for j, i in enumerate(order):
        a, b = cells[i]
        if j + 1 < len(order): b = max(b, cells[order[j + 1]][0])
        out[i] = (a, b)
    return out


def word_boxes(w, rule, variant="orig"):
    """The word's letter boxes with its joined pieces' cells from `rule` (plans of `variant`); other letters keep
    the PDF's box. None if a joined piece of the word has no stored plan (uncut piece: PDF box kept)."""
    base = [tuple(c) for c in w["cutter"]]; raw = list(base); m = match(w, w["doc"], variant)
    for k, (idx, p) in m.items():
        c = rule(p)
        if c is None: continue
        for i, cc in zip(idx, c): raw[i] = cc
    return retile(raw), m


def check():
    S = json.load(open(E18 / "out/sample.json")); n = good = nomatch = 0; worst = []
    for s, ws in S.items():
        for w in ws:
            if not (HERE / f"out/plans/orig_{w['doc']}.pkl").exists(): continue
            b, m = word_boxes(w, cells_orig)
            joined = [i for i in range(len(w["text"])) if w["joined"][i]]
            if any(w["piece_of"][i] not in m for i in joined) and joined: nomatch += 1
            d = max(abs(x - y) for c, cc in zip(b, w["cutter"]) for x, y in zip(c, cc))
            n += 1; good += d <= 1.5
            if d > 1.5: worst.append((round(d, 1), R18.wid(w), w["text"]))
    print(f"words {n}, reproduced within 1.5 px: {good}, a joined piece without stored plan: {nomatch}")
    for x in sorted(worst, reverse=True)[:15]: print(" ", x)


def draw(p, rules, scale=4):
    """The piece: each letter's ink in its own colour, the trunk, cut points; under it one bar per rule."""
    ink = p["ink_s"]; H, W = ink.shape; img = np.full((H, W, 3), 255, np.uint8)
    cols = [(200, 60, 60), (60, 160, 60), (60, 60, 220), (200, 140, 0), (160, 0, 160), (0, 150, 170), (120, 120, 120)]
    for k, (a, b) in enumerate(P.intervals(p)):
        img[P._mask(p, a, b, owner=k) > 0] = cols[k % len(cols)]
    for (y, x) in p["trunk"]: img[y, x] = (0, 0, 0)
    for c in p["cuts"]: y, x = p["trunk"][c]; cv2.circle(img, (x, y), 1, (0, 0, 255), -1)
    img = cv2.resize(img, (W * scale, H * scale), interpolation=cv2.INTER_NEAREST)
    bars = []
    for rule in rules:
        bar = np.full((14, W * scale, 3), 255, np.uint8); c = rule(p) or []
        for k, (a, b) in enumerate(c):
            a -= p["off"][0]; b -= p["off"][0]
            cv2.rectangle(bar, (int(a * scale), 2), (int(b * scale) - 1, 11), cols[k % len(cols)], -1)
        bars.append(bar)
    return np.vstack([img] + bars)


import run18 as R18

if __name__ == "__main__":
    if sys.argv[1] == "check": check()


def find_word(wid):
    S = json.load(open(E18 / "out/sample.json"))
    for s, ws in S.items():
        for w in ws:
            if R18.wid(w) == wid: return s, w


def draw_words(wids, rules, name="draw", variant="orig"):
    tiles = []
    for wid in wids:
        s, w = find_word(wid); m = match(w, w["doc"], variant)
        for k, (idx, p) in m.items():
            t = draw(p, rules); t = cv2.copyMakeBorder(t, 0, 18, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
            cv2.putText(t, f"{wid} {''.join(p['units'])[::-1]}"[:40], (2, t.shape[0] - 4), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
            tiles.append(t)
    Wd = max(t.shape[1] for t in tiles)
    cv2.imwrite(str(HERE / f"out/{name}.png"), np.vstack([cv2.copyMakeBorder(t, 4, 4, 0, Wd - t.shape[1], cv2.BORDER_CONSTANT, value=(235, 235, 235)) for t in tiles]))


if __name__ == "__main__" and sys.argv[1] == "draw":
    v = sys.argv[2]; draw_words(sys.argv[3:], [cells_orig], f"draw_{v}", v)
