"""HISTORICAL SKETCH — superseded by `solve` in src/inkscript/geometry/penpath.py.

Cuts chosen by the document's own letters, in rounds. Start from the pen-path cuts; build the atlas; for
each piece try every way of placing its cuts on the candidate points of its pen path and keep the one whose
letters look most like their atlas pictures; rebuild the atlas from the letters that agree; repeat.

    python rounds.py <azure.json> <scan.pdf> <pages> <out_dir> [rounds]
"""
import sys, os
from collections import defaultdict
import numpy as np, cv2
from penpath import collect, picture
from atlas import C, BASE, RISE, label, sheet
from inkscript.geometry.letters import form, _base, joins, ASC, DESC_ANY, DESC_END, DOTS_ABOVE, DOTS_BELOW, width_class

GOOD = 0.5                                                            # a letter this close to its reference agrees with it


def prepare(g):
    """Candidate cut points on the strip, the connector stretches (kashida), and a cache of letter pictures."""
    G = g["G"]; S = G["W"]; stroke = G["stroke"]; s = g["ink_s"]
    mass = np.bincount(s[s >= 0], minlength=S).astype(float); sm = np.convolve(mass, np.ones(3) / 3, mode="same")
    mins = [i for i in range(3, S - 3) if sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] and sm[i] <= 1.6 * stroke]
    cand = sorted(set(joins(G)) | set(mins)); kept = []
    for c in cand:                                                    # at least three apart; of two close ones keep the thinner
        if kept and c - kept[-1] < 3:
            if sm[c] < sm[kept[-1]]: kept[-1] = c
        else: kept.append(c)
    if len(kept) > 14: kept = sorted(sorted(kept, key=lambda c: sm[c])[:14])
    conn = np.zeros(S, bool); x = 0; thin = G["thin"]
    while x < S:
        if thin[x]:
            j = x
            while j < S and thin[j]: j += 1
            if j - x >= 4 * stroke: conn[x + stroke:j - stroke] = True  # a long flat connector is nobody's shape
            x = j
        else: x += 1
    g["cand"] = [c for c in kept if 0 < c < S]; g["conn"] = conn; g["cache"] = {}
    g["sc"] = RISE / g["line"]["rise"]; g["base"] = g["line"]["baseline"] - g["off"][1]


def letter_img(g, a, b):
    if (a, b) in g["cache"]: return g["cache"][(a, b)]
    s = g["ink_s"]; ok = (s >= a) & (s < b); m = ok & ~g["conn"][np.clip(s, 0, None)]
    if m.sum() < 4: m = ok
    for (ds, above), lab_id in zip(g["G"]["dots"], g["F"]["dot_labels"]):
        if a <= ds < b: m = m | (g["F"]["lab"] == lab_id)
    ys, xs = np.where(m); im = None
    if len(xs) >= 4:
        sc = g["sc"]; cx = (xs.min() + xs.max()) / 2; M = np.float32([[sc, 0, C / 2 - sc * cx], [0, sc, BASE - sc * g["base"]]])
        im = cv2.warpAffine(m.astype(np.float32), M, (C, C), flags=cv2.INTER_AREA)
        # softened: two thin strokes a pixel apart are the same shape. Compared as hard masks they do not overlap at
        # all, and a fine typeface's atlas came out empty (every reference the median of strokes that never coincide).
        im = cv2.GaussianBlur(im, (0, 0), 2.0)
    g["cache"][(a, b)] = im; return im


def score(im, ref):
    if im is None: return 0.0
    return max(float(np.minimum(sh, ref).sum() / max(1e-6, np.maximum(sh, ref).sum())) for sh in (np.roll(im, dx, 1) for dx in (-4, -2, 0, 2, 4)))


def facts(g, k, a, b):
    """The hard facts, as in `letters.align`: a letter's dots, tall stroke and bowl must be inside its own interval."""
    G = g["G"]; c = _base(g["units"][k]); last = k == g["n"] - 1
    want_asc = c in ASC or c.startswith("ل"); asc_ok = G["asc"][a:b].sum() >= 2 if want_asc else G["tall"][a:b].sum() < 2
    want_desc = c in DESC_ANY or (last and c in DESC_END); desc_ok = G["desc"][a:b].sum() >= 2 if want_desc else G["deep"][a:b].sum() < 2
    da = sum(1 for x, ab in G["dots"] if a <= x < b and ab); db = sum(1 for x, ab in G["dots"] if a <= x < b and not ab)
    wa = DOTS_ABOVE.get(c, 0); wb = DOTS_BELOW.get(c, 0)
    if c == "ي" and last: wb = db if db in (0, 2) else 2
    near = lambda got, want: got == want or (want >= 2 and 1 <= got <= want)
    unit = G["W"] / sum(width_class(u) for u in g["units"]); w = -0.8 * abs(np.log(max(b - a, 1) / (width_class(g["units"][k]) * unit))) ** 2
    return w + (1.5 if asc_ok else -6.0) + (1.0 if desc_ok else -2.0) + (2.0 if near(da, wa) else -5.0) + (2.0 if near(db, wb) else -5.0)


ATLAS = 8.0                                                           # weight of the atlas likeness beside the facts


def key(g, k): return (_base(g["units"][k]), form(k, g["n"]))


def intervals(g, cuts):
    b = [0] + list(cuts) + [g["G"]["W"]]; n = g["n"]; return [(b[n - 1 - k], b[n - k]) for k in range(n)]


def best_cuts(g, ref):
    """The cuts, among the candidates, whose letters together look most like the atlas."""
    n = g["n"]; pos = [0] + g["cand"] + [g["G"]["W"]]; m = len(pos)
    if m - 2 < n - 1: return None
    NEG = -1e9; best = np.full((n + 1, m), NEG); back = np.zeros((n + 1, m), int); best[0][0] = 0
    for i in range(n):                                                # i-th letter from the left = reading-order letter n-1-i
        r = ref.get(key(g, n - 1 - i))
        for ai in range(m - 1):
            if best[i][ai] == NEG: continue
            for bi in range(ai + 1, m):
                if (i == n - 1) != (bi == m - 1) or pos[bi] - pos[ai] < 3: continue
                v = best[i][ai] + facts(g, n - 1 - i, pos[ai], pos[bi]) + ATLAS * (score(letter_img(g, pos[ai], pos[bi]), r) if r is not None else 0.3)
                if v > best[i + 1][bi]: best[i + 1][bi] = v; back[i + 1][bi] = ai
    if best[n][m - 1] == NEG: return None
    cuts = []; bi = m - 1
    for i in range(n, 1, -1): bi = back[i][bi]; cuts.append(pos[bi])
    return sorted(cuts)


def build_atlas(got, ref=None):
    ex = defaultdict(list); every = defaultdict(list)
    for g in got:
        for k, (a, b) in enumerate(intervals(g, g["cuts"])):
            im = letter_img(g, a, b)
            if im is None: continue
            every[key(g, k)].append(im)
            if ref is None or key(g, k) not in ref or score(im, ref[key(g, k)]) >= 0.4: ex[key(g, k)].append(im)
    for kk, v in every.items():                                       # a form none of whose examples agree yet keeps all of them: it must not drop out
        if len(ex[kk]) < 5: ex[kk] = v
    return {kk: np.mean(np.stack(v), 0) for kk, v in ex.items() if len(v) >= 5}, {kk: len(v) for kk, v in ex.items()}


def judge(got, ref):
    for g in got:
        g["scores"] = [score(letter_img(g, a, b), ref[key(g, k)]) if key(g, k) in ref else None for k, (a, b) in enumerate(intervals(g, g["cuts"]))]
        known = [s for s in g["scores"] if s is not None]; g["worst"] = min(known) if len(known) == g["n"] else None
    w = np.array([g["worst"] for g in got if g["worst"] is not None])
    return f"pieces all of whose letters agree with the atlas (>= {GOOD}): {int((w >= GOOD).sum())} of {len(got)} ({100 * (w >= GOOD).sum() / len(got):.0f}%); median worst-letter score {np.median(w):.2f}"


def atlas_sheet(ref, counts, path):
    tiles = []
    for kk in sorted(ref, key=lambda k: (k[0], ["iso", "init", "med", "fin"].index(k[1]))):
        im = cv2.cvtColor((255 - np.clip(ref[kk] / max(1e-6, ref[kk].max()), 0, 1) * 255).astype(np.uint8), cv2.COLOR_GRAY2BGR); cv2.line(im, (0, BASE), (C, BASE), (200, 220, 255), 1)
        tiles.append(cv2.copyMakeBorder(np.vstack([label(f"{kk[0]} {kk[1]} {counts[kk]}"), im]), 4, 4, 4, 4, cv2.BORDER_CONSTANT, value=(225, 225, 225)))
    sheet([cv2.resize(t, None, fx=2, fy=2, interpolation=cv2.INTER_CUBIC) for t in tiles], path)


def piece_sheet(pieces, path):
    tiles = []
    for g in pieces:
        im = picture(g["F"], g["ink_s"], g["cuts"], g["G"], g["n"], up=4); cv2.putText(im, f"{g['worst'] if g['worst'] is not None else -1:.2f}", (2, 12), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)
        tiles.append(cv2.copyMakeBorder(im, 6, 6, 6, 6, cv2.BORDER_CONSTANT, value=(255, 255, 255)))
    sheet(tiles, path)


def main(azure, scan, pages, out, rounds=4):
    os.makedirs(out, exist_ok=True); got, tried = collect(azure, scan, pages)
    for g in got: prepare(g)
    ref, counts = build_atlas(got); print(f"pieces of 2+ letters {tried}, on a pen path {len(got)}\nstart:   " + judge(got, ref))
    atlas_sheet(ref, counts, f"{out}/atlas_start.png")
    judged = sorted([g for g in got if g["worst"] is not None], key=lambda g: g["worst"]); watch = judged[:60]; piece_sheet(watch, f"{out}/worst60_before.png")
    import random; random.seed(3); mid = random.sample(judged, 60); piece_sheet(mid, f"{out}/random60_before.png")
    for r in range(1, rounds + 1):
        changed = 0
        for g in got:
            c = best_cuts(g, ref)
            if c is not None and c != list(g["cuts"]): g["cuts"] = c; changed += 1
        new, counts = build_atlas(got, ref)
        ref = {kk: 0.5 * ref[kk] + 0.5 * v if kk in ref else v for kk, v in new.items()}   # damped: a full swap made a fine typeface flip between two states
        print(f"round {r}: {changed} pieces re-cut; " + judge(got, ref))
        if changed == 0: break
    atlas_sheet(ref, counts, f"{out}/atlas_end.png"); piece_sheet(watch, f"{out}/worst60_after.png"); piece_sheet(mid, f"{out}/random60_after.png")


if __name__ == "__main__":
    main(sys.argv[1], sys.argv[2], [int(p) for p in sys.argv[3].split(",")], sys.argv[4], int(sys.argv[5]) if len(sys.argv) > 5 else 4)
