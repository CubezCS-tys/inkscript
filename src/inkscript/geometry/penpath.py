"""Letters along the pen path.

A connected piece of ink is thinned to its centre line. The trunk is the path from where the first letter
meets the baseline to the piece's left end; everything else — an arm, an ascender, the far side of a loop, a
tail sweeping back — belongs to the trunk point it hangs from. The piece is thereby unrolled into a strip
indexed by distance along the pen path, and a cut between two letters is a POINT on that path, not a column
of the page: a kaf keeps the arm it throws over its neighbour.

Where the cuts go is decided by two witnesses. The hard facts: a letter's dots, tall stroke and bowl must lie
in its own stretch of the path (`facts`). And the document's own alphabet: the mean picture of every
letter-form, built from the cut letters themselves (`build_atlas`); cuts are re-chosen to make each letter
look like its picture, the pictures rebuilt, and so on until little changes (`solve`). A piece is cut only if
every fact holds and every letter resembles its picture (`accepted`); otherwise it stays one glyph.

A letter's glyph has the ink that hangs from its stretch of the path, and a selection cell that is its stretch
of the baseline — as in a typeset font, where a kaf's arm overhangs the next letter's box. The letters' inks
add up to exactly the piece's ink, so the page looks the same wherever the cuts fall. Experiment 09.
"""
from __future__ import annotations
from collections import defaultdict, deque
import numpy as np, cv2

from .letters import (piece_mask, analyse, joins, form, _base, width_class,
                      ASC, DESC_ANY, DESC_END, DOTS_ABOVE, DOTS_BELOW)

NB = [(-1, -1), (-1, 0), (-1, 1), (0, -1), (0, 1), (1, -1), (1, 0), (1, 1)]
C, BASE, RISE = 72, 46, 26                                # atlas canvas, its baseline row, pixels per line rise
ATLAS = 8.0                                               # weight of likeness to the atlas beside the facts
AGREE = 0.3                                               # every letter of an accepted piece is at least this like its picture
ROUNDS = 4
RELIABLE = 0.85                                           # a fact counts for a letter-form when this share of its occurrences show it


def thin(img: np.ndarray) -> np.ndarray:
    """Zhang–Suen thinning."""
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


def _bfs(sk, sources):
    prev = {s: None for s in sources}; root = {s: s for s in sources}; q = deque(sources); H, W = sk.shape
    while q:
        y, x = q.popleft()
        for dy, dx in NB:
            n = (y + dy, x + dx)
            if 0 <= n[0] < H and 0 <= n[1] < W and sk[n] and n not in prev:
                prev[n] = (y, x); root[n] = root[(y, x)]; q.append(n)
    return prev, root


def unroll(F: dict, line: dict, y_off: int):
    """The strip: per-ink-pixel trunk position (0 = the left end of the pen path) and the strip's features."""
    main = F["main"]; sk = thin(main); ys, xs = np.where(sk)
    if len(xs) < 6:
        return None
    # The path starts where the first letter's body meets the baseline, not at the rightmost ink: a kaf that
    # throws its arm out to the right made the arm's tip the start, and cuts were placed along the arm.
    near = np.abs(ys - (line["baseline"] - y_off)) <= 0.35 * line["rise"]
    i = np.where(near)[0][np.argmax(xs[near])] if near.any() else int(np.argmax(xs))
    right = (int(ys[i]), int(xs[i])); left = (int(ys[np.argmin(xs)]), int(xs.min()))
    prev, _ = _bfs(sk, [right])
    if left not in prev:
        return None
    trunk = []; n = left
    while n is not None: trunk.append(n); n = prev[n]                 # left end first
    S = len(trunk); pos = {p: k for k, p in enumerate(trunk)}
    _, root = _bfs(sk, trunk)
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
    sy, sx = np.array([p[0] for p in trunk]), np.array([p[1] for p in trunk])
    # Every loose bit of ink goes to a letter (`marks`), but only dot-shaped ones are evidence (`dots`): the
    # fragments of an underline under `لمعجم` were counted as three dots below and vetoed a correct cut.
    G["marks"] = []
    for (cx, above), k in zip(F["dots"], F["dot_labels"]):
        yy, xx = np.where(F["lab"] == k); s_at = int(np.argmin((sx - cx) ** 2 + 0.25 * (sy - yy.mean()) ** 2)); G["marks"].append((s_at, above, k))
        w, h = xx.max() - xx.min() + 1, yy.max() - yy.min() + 1
        if not (w >= 3 * h and w > 1.5 * stroke): G["dots"].append((s_at, above))
    return G, ink_s, trunk


def units_forms(text: str):
    """The letters of a piece with each one's form. Usually the piece is one joined run; when two runs touch in
    the ink (`خلا` + `ل` printed as one blob) the word arrives unsplit, and its letters still lie along one pen
    path — each keeps the form its own run gives it. None when the text is not purely Arabic runs."""
    from ..text import pieces, ARABIC_LETTER
    from .letters import letters_of
    runs = pieces(text.strip())
    if not runs or not all(ARABIC_LETTER.search(r) for r in runs):
        return None
    units, forms = [], []
    for r in runs:
        u = letters_of(r); units += u; forms += [form(k, len(u)) for k in range(len(u))]
    if "".join(units) != text.strip():
        return None                                                  # the letters must spell the piece exactly: `ركبهم ـ` lost its space
    return units, forms


def bridge(mask: np.ndarray, reach: float):
    """A run whose ink is broken in the scan (`على` printed as two blobs) has no single pen path. The big blobs are
    joined, nearest points first, by a two-pixel line no longer than `reach` — for the PATH only: the bridge is
    never drawn, and it is an obvious place for a cut. None if the blobs are further apart than that."""
    n, lab, st, _ = cv2.connectedComponentsWithStats(mask.astype(np.uint8), connectivity=8)
    big = [k for k in range(1, n) if st[k, cv2.CC_STAT_AREA] > 0.25 * st[1:, cv2.CC_STAT_AREA].max()]
    if len(big) < 2 or len(big) > 4:
        return None
    out = mask.astype(np.uint8).copy(); big.sort(key=lambda k: st[k, cv2.CC_STAT_LEFT])
    for a, b in zip(big, big[1:]):
        pa = np.argwhere(lab == a); pb = np.argwhere(lab == b)
        pa = pa[pa[:, 1] >= pa[:, 1].max() - 12]; pb = pb[pb[:, 1] <= pb[:, 1].min() + 12]     # facing edges
        d = ((pa[:, None, :] - pb[None, :, :]) ** 2).sum(2); i, j = np.unravel_index(np.argmin(d), d.shape)
        if d[i, j] ** 0.5 > reach:
            return None
        cv2.line(out, (int(pa[i][1]), int(pa[i][0])), (int(pb[j][1]), int(pb[j][0])), 1, 2)
    return out.astype(bool)


def plan(units: list[str], blobs: list[dict], line: dict | None, forms: list[str] | None = None):
    """One piece on its pen path, with its candidate cut points; cuts are chosen later by `solve`."""
    if len(units) < 2 or not line or line["rise"] < 10:
        return None
    mask, off = piece_mask(blobs)
    if mask.shape[1] < 4 * len(units) or mask.shape[1] > 1500:
        return None
    F = analyse(mask, line, off[1]); real = None
    if F is None:
        joined = bridge(mask, 0.5 * line["rise"])
        if joined is None:
            return None
        F = analyse(joined, line, off[1]); real = mask
        if F is None:
            return None
    r = unroll(F, line, off[1])
    if r is None:
        return None
    G, ink_s, trunk = r; S = G["W"]; stroke = G["stroke"]
    mass = np.bincount(ink_s[ink_s >= 0], minlength=S).astype(float); sm = np.convolve(mass, np.ones(3) / 3, mode="same")
    mins = [i for i in range(3, S - 3) if sm[i] <= sm[i - 1] and sm[i] <= sm[i + 1] and sm[i] <= 1.6 * stroke]
    kept = []
    for c in sorted(set(joins(G)) | set(mins)):                       # at least three apart; of two close ones the thinner
        if kept and c - kept[-1] < 3:
            if sm[c] < sm[kept[-1]]: kept[-1] = c
        else: kept.append(c)
    if len(kept) > 14: kept = sorted(sorted(kept, key=lambda c: sm[c])[:14])
    cand = [c for c in kept if 0 < c < S]
    if len(cand) < len(units) - 1:
        return None                                                  # fewer places than cuts: the piece stays whole
    conn = np.zeros(S, bool); x = 0; th = G["thin"]
    while x < S:
        if th[x]:
            j = x
            while j < S and th[j]: j += 1
            if j - x >= 4 * stroke: conn[x + stroke:j - stroke] = True   # a kashida is nobody's shape
            x = j
        else: x += 1
    p = dict(kind="pen", units=units, n=len(units), forms=forms or [form(k, len(units)) for k in range(len(units))], F=F, G=G, ink_s=ink_s, trunk=trunk, off=off, cand=cand, conn=conn,
             real=real, sc=RISE / line["rise"], base=line["baseline"] - off[1], cache={}, cuts=None)
    p["cuts"] = best_cuts(p, {})
    return p if p["cuts"] is not None else None


def _dot_owner(p, ds, above, cuts=None):
    """The letter (reading order) a dot's ink goes to: the one whose stretch holds it, unless that letter takes no
    dot on that side and a neighbour within a stroke does."""
    iv = intervals(p, cuts); tol = p["G"]["stroke"]; wants = lambda k: (DOTS_ABOVE if above else DOTS_BELOW).get(_base(p["units"][k]), 0) > 0 or (not above and _base(p["units"][k]) == "ي")
    own = next((k for k, (a, b) in enumerate(iv) if a <= ds < b), 0)
    if not wants(own):
        for k in (own - 1, own + 1):
            if 0 <= k < len(iv) and wants(k) and iv[k][0] - tol <= ds < iv[k][1] + tol: return k
    return own


def _mask(p, a, b, connectors=True, owner=None):
    s = p["ink_s"]; m = (s >= a) & (s < b)
    if p.get("real") is not None: m = m & p["real"]                   # a bridge is path, not ink
    if not connectors:
        m2 = m & ~p["conn"][np.clip(s, 0, None)]
        if m2.sum() >= 4: m = m2
    for ds, above, lab_id in p["G"]["marks"]:
        if (a <= ds < b) if owner is None else (_dot_owner(p, ds, above) == owner): m = m | (p["F"]["lab"] == lab_id)
    return m


def letter_img(p, a, b):
    """The letter on the atlas canvas: scaled by the line's rise, baseline on a fixed row, softened — two thin
    strokes a pixel apart are the same shape, and as hard masks a fine typeface's letters never coincide."""
    if (a, b) in p["cache"]: return p["cache"][(a, b)]
    ys, xs = np.where(_mask(p, a, b, connectors=False)); im = None
    if len(xs) >= 4:
        sc = p["sc"]; cx = (xs.min() + xs.max()) / 2; M = np.float32([[sc, 0, C / 2 - sc * cx], [0, sc, BASE - sc * p["base"]]])
        m = np.zeros(p["ink_s"].shape, np.float32); m[ys, xs] = 1
        im = cv2.GaussianBlur(cv2.warpAffine(m, M, (C, C), flags=cv2.INTER_AREA), (0, 0), 2.0)
    p["cache"][(a, b)] = im; return im


def likeness(im, ref) -> float:
    if im is None: return 0.0
    return max(float(np.minimum(sh, ref).sum() / max(1e-6, np.maximum(sh, ref).sum())) for sh in (np.roll(im, dx, 1) for dx in (-4, -2, 0, 2, 4)))


def key(p, k): return (_base(p["units"][k]), p["forms"][k])


def intervals(p, cuts=None):
    b = [0] + list(p["cuts"] if cuts is None else cuts) + [p["G"]["W"]]; n = p["n"]; return [(b[n - 1 - k], b[n - k]) for k in range(n)]


def _facts(p, k, a, b):
    G = p["G"]; c = _base(p["units"][k]); last = p["forms"][k] in ("fin", "iso"); tol = G["stroke"]
    # on the strip a tall stroke that hangs from the trunk occupies ONE position, however wide it is on the page
    want_asc = c in ASC or c.startswith("ل"); asc_ok = G["asc"][a:b].sum() >= 1 if want_asc else G["tall"][a:b].sum() < 2
    want_desc = c in DESC_ANY or (last and c in DESC_END); desc_ok = G["desc"][a:b].sum() >= 1 if want_desc else G["deep"][a:b].sum() < 2
    # A dot is placed on the path by the nearest trunk point, which near a cut can be the neighbour's (the dot of
    # a medial jim sits under the letter before it). Within a stroke of the boundary it counts for the letter
    # that wants it and not against the one that does not.
    wa = DOTS_ABOVE.get(c, 0); wb = DOTS_BELOW.get(c, 0)
    cnt = lambda above, want: sum(1 for x, ab in G["dots"] if ab == above and ((a - tol <= x < b + tol) if want else (a + tol <= x < b - tol)))
    da = cnt(True, wa > 0); db = cnt(False, wb > 0 or c == "ي")
    if c == "ي" and last: wb = db if db in (0, 2) else 2
    near = lambda got, want: got == want or (want >= 2 and 1 <= got <= want)
    return asc_ok, desc_ok, near(da, wa), near(db, wb), (want_asc or want_desc or wa > 0 or wb > 0)


def facts(p, k, a, b) -> float:
    asc_ok, desc_ok, da_ok, db_ok, _ = _facts(p, k, a, b)
    unit = p["G"]["W"] / sum(width_class(u) for u in p["units"]); w = -0.8 * abs(np.log(max(b - a, 1) / (width_class(p["units"][k]) * unit))) ** 2
    return w + (1.5 if asc_ok else -6.0) + (1.0 if desc_ok else -2.0) + (2.0 if da_ok else -5.0) + (2.0 if db_ok else -5.0)


def best_cuts(p, ref):
    n = p["n"]; pos = [0] + p["cand"] + [p["G"]["W"]]; m = len(pos)
    NEG = -1e9; best = np.full((n + 1, m), NEG); back = np.zeros((n + 1, m), int); best[0][0] = 0
    for i in range(n):                                                # i-th letter from the left = reading-order letter n-1-i
        k = n - 1 - i; r = ref.get(key(p, k))
        for ai in range(m - 1):
            if best[i][ai] == NEG: continue
            for bi in range(ai + 1, m):
                if (i == n - 1) != (bi == m - 1) or pos[bi] - pos[ai] < 3: continue
                v = best[i][ai] + facts(p, k, pos[ai], pos[bi]) + ATLAS * (likeness(letter_img(p, pos[ai], pos[bi]), r) if r is not None else 0.3)
                if v > best[i + 1][bi]: best[i + 1][bi] = v; back[i + 1][bi] = ai
    if best[n][m - 1] == NEG:
        return None
    cuts = []; bi = m - 1
    for i in range(n, 1, -1): bi = back[i][bi]; cuts.append(pos[bi])
    return sorted(cuts)


def build_atlas(plans, ref=None):
    ex = defaultdict(list); every = defaultdict(list)
    for p in plans:
        for k, (a, b) in enumerate(intervals(p)):
            im = letter_img(p, a, b)
            if im is None: continue
            every[key(p, k)].append(im)
            if ref is None or key(p, k) not in ref or likeness(im, ref[key(p, k)]) >= 0.4: ex[key(p, k)].append(im)
    for kk, v in every.items():                                       # a form none of whose examples agree yet keeps all of them
        if len(ex[kk]) < 5: ex[kk] = v
    return {kk: np.mean(np.stack(v), 0) for kk, v in ex.items() if len(v) >= 5}


def solve(plans: list[dict], rounds: int = ROUNDS) -> dict:
    """Choose every plan's cuts with the document's atlas, in rounds; leaves p['scores']. Returns the atlas."""
    ref = build_atlas(plans)
    for _ in range(rounds):
        changed = 0
        for p in plans:
            c = best_cuts(p, ref)
            if c is not None and c != p["cuts"]: p["cuts"] = c; changed += 1
        new = build_atlas(plans, ref)
        ref = {kk: 0.5 * ref[kk] + 0.5 * v if kk in ref else v for kk, v in new.items()}   # damped: a full swap flip-flops
        if not changed: break
    # Which facts this typeface actually shows for each letter-form: a final nun whose bowl hovers at the
    # threshold says nothing either way, and must not veto a cut (the same rule as `letters.learn`).
    seen = defaultdict(list)
    for p in plans:
        for k, (a, b) in enumerate(intervals(p)): seen[key(p, k)].append(_facts(p, k, a, b)[:4])
    reliable = {kk: tuple(len(v) >= 5 and np.mean([f[i] for f in v]) >= RELIABLE for i in range(4)) for kk, v in seen.items()}
    for p in plans:
        p["reliable"] = reliable
        p["scores"] = [likeness(letter_img(p, a, b), ref[key(p, k)]) if key(p, k) in ref else None for k, (a, b) in enumerate(intervals(p))]
    return ref


def accepted(p: dict) -> bool:
    """Every fact holds for every letter, at least one letter is confirmed by a positive fact, and every letter
    is known to the atlas and looks like its picture."""
    positive = False
    for k, (a, b) in enumerate(intervals(p)):
        asc_ok, desc_ok, da_ok, db_ok, pos = _facts(p, k, a, b)
        rel = p.get("reliable", {}).get(key(p, k), (True,) * 4)
        if any(r and not ok for r, ok in zip(rel, (asc_ok, desc_ok, da_ok, db_ok))): return False
        positive = positive or pos
    # One letter-form too rare for the atlas (a medial `ئ`) does not veto a piece whose other letters all agree:
    # its stretch is what the neighbours leave, and its facts held.
    sc = p.get("scores", [None]); unknown = sum(s is None for s in sc)
    return positive and unknown <= 1 and unknown < len(sc) - 1 and all(s >= AGREE for s in sc if s is not None)


def verdict(p: dict) -> str:
    """Why a piece is or is not cut, for the build report."""
    if accepted(p): return "cut"
    for k, (a, b) in enumerate(intervals(p)):
        rel = p.get("reliable", {}).get(key(p, k), (True,) * 4)
        for name, r, ok in zip(("tall stroke", "bowl", "dots above", "dots below"), rel, _facts(p, k, a, b)[:4]):
            if r and not ok: return f"fact: {name}"
    sc = p.get("scores", [])
    if sum(s is None for s in sc) > 1 or all(s is None for s in sc): return "letter-forms too rare for the atlas"
    if any(s is not None and s < AGREE for s in sc): return "unlike the atlas"
    return "nothing positive to confirm it"


def letter_blobs(p: dict, blobs: list[dict]) -> list[list[dict]]:
    """One list of blob dicts per letter, in reading order: the ink hanging from its stretch of the path (dots
    with it), and its `cell` — its stretch of the baseline in page x — which is the glyph's selection box."""
    x_off, y_off = p["off"]; n = p["n"]; S = p["G"]["W"]; trunk = p["trunk"]; out = []
    ys, xs = np.where(p["ink_s"] >= 0); X = lambda s: int(xs.min()) if s <= 0 else int(xs.max()) + 1 if s >= S else int(trunk[s][1])
    for k, (a, b) in enumerate(intervals(p)):
        cx0, cx1 = X(a), X(b)
        if cx1 - cx0 < 2:
            return []                                                # the path doubles back here: no honest cell
        # Outlines run through pixel centres, so two letters traced apart leave a one-pixel seam of missing ink
        # across the stroke where they meet (1.1% of a page's ink). Each letter therefore takes one pixel of its
        # neighbour's ink at the seam — inside the piece's ink only, so the outer outline does not move.
        sub = (cv2.dilate(_mask(p, a, b, owner=k).astype(np.uint8), np.ones((3, 3), np.uint8)) & ((p["ink_s"] >= 0) & (p["real"] if p.get("real") is not None else True))).astype(np.uint8)
        sub |= _mask(p, a, b, owner=k).astype(np.uint8)
        cs, hier = cv2.findContours(sub, cv2.RETR_CCOMP, cv2.CHAIN_APPROX_SIMPLE)
        keep = [(c.reshape(-1, 2) + [x_off, y_off], int(hier[0][i][3] >= 0)) for i, c in enumerate(cs)]
        keep = [(pth, h) for pth, h in ((cv2.approxPolyDP(pth.astype(np.int32), 0.0, True).reshape(-1, 2), h) for pth, h in keep) if len(pth) >= 3]
        if not keep:
            return []
        px = np.concatenate([pth[:, 0] for pth, _ in keep]); py = np.concatenate([pth[:, 1] for pth, _ in keep])
        out.append([dict(x=int(px.min()), y=int(py.min()), w=int(px.max() - px.min()), h=int(py.max() - py.min()), cx=float(px.mean()), cy=float(py.mean()),
                         paths=[pth for pth, _ in keep], holes=[h for _, h in keep], word=blobs[0].get("word"), cell=(cx0 + x_off, cx1 + x_off))])
    return out
