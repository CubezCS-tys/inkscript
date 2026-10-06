"""Stretch-tolerant matching for the feeler (experiment 16, direction "warp").

feel.py compares a letter's stretch with a remembered one by resampling both evenly to a fixed length and
taking the Euclidean distance: a letter written a little longer at its start and shorter at its end lands its
features in the wrong bins and fails to match. Here the same feeling is compared by dynamic time warping (DTW)
inside a Sakoe-Chiba band: each sample of the candidate may pair with a sample up to `band` places earlier or
later in the remembered example, so local uneven stretching is free while the overall order is kept.

The comparison is made on the same two sequences feel.py builds, kept as sequences instead of flattened:
  - the trunk feeling pooled per bin (height of the pen, ink above, ink below, heading, ink mass), L bins;
  - the stick's walk (height, heading), LW samples.
Each is warped on its own (the walk spends time in branches, so its clock differs from the trunk's).

DTW form: symmetric with a doubled diagonal step (Sakoe & Chiba's "symmetric2"), divided by 2, so that with
band = 0 it is exactly feel.py's squared Euclidean distance (a check that the plumbing matches the baseline).

Also here, because they turned out to matter more than the warping: remembering every example (Memory cap) and
the neighbourhood gate (Feeler gate: a letter competes only if its knn examples are among the `gate` nearest).
See notes/warp.md.

Everything is vectorised over the remembered examples of one letter-form class (iso/init/med/fin) and over all
candidate stretches of a piece at once; memory per call is bounded by chunking.
"""
import numpy as np
from collections import defaultdict, Counter
import feel as FE

P = FE.P


def seqs(f, walkinfo, a, b, L=8, LW=16):
    """A stretch [a, b) of the feeling as two sequences: trunk (L, 6) and walk (LW, 3), weighted like feel.py."""
    edges = np.linspace(a, b, L + 1); seg = np.zeros((L, f.shape[1]))
    for i in range(L):
        lo = int(np.floor(edges[i])); hi = max(lo + 1, int(np.ceil(edges[i + 1])))
        part = f[lo:min(hi, len(f))] if lo < len(f) else f[-1:]
        seg[i] = [pool(part[:, c]) for c, pool in enumerate(FE.POOL)]
    trunk = seg * FE.CH_W * 0.5
    pts, s_of, base, rise = walkinfo; sel = pts[(s_of >= a) & (s_of < b)]
    if len(sel) < 2: sel = np.repeat(pts[np.argmin(np.abs(s_of - (a + b) / 2))][None], 2, 0)
    t = np.linspace(0, len(sel) - 1, LW); yy = np.interp(t, np.arange(len(sel)), sel[:, 0]); xx = np.interp(t, np.arange(len(sel)), sel[:, 1])
    dy, dx = np.diff(yy, append=yy[-1]), np.diff(xx, append=xx[-1]); n = np.maximum(1e-6, np.hypot(dy, dx))
    walk = np.stack([(base - yy) / rise, dy / n, dx / n], 1) * FE.WALK_W * np.sqrt(L / LW)
    return trunk, walk


def walk_var(walkinfo, a, b, per_rise=12, nmax=40, L=8, LW=16):
    """The stick's walk over [a, b) at its own length: `per_rise` samples per rise of path travelled (a loop or an
    ascender adds samples instead of squeezing the rest), between 3 and `nmax`. Returns (nmax, 3) zero-padded, n."""
    pts, s_of, base, rise = walkinfo; sel = pts[(s_of >= a) & (s_of < b)]
    if len(sel) < 2: sel = np.repeat(pts[np.argmin(np.abs(s_of - (a + b) / 2))][None], 2, 0)
    n = int(np.clip(round(len(sel) * per_rise / rise), 3, nmax))
    t = np.linspace(0, len(sel) - 1, n); yy = np.interp(t, np.arange(len(sel)), sel[:, 0]); xx = np.interp(t, np.arange(len(sel)), sel[:, 1])
    dy, dx = np.diff(yy, append=yy[-1]), np.diff(xx, append=xx[-1]); nn = np.maximum(1e-6, np.hypot(dy, dx))
    out = np.zeros((nmax, 3)); out[:n] = np.stack([(base - yy) / rise, dy / nn, dx / nn], 1) * FE.WALK_W * np.sqrt(L / LW)
    return out, n


def dtw_var(X, nx, V, nv, rband, LW=16, chunk=3_000_000):
    """Squared DTW (symmetric2) between sequences of their own lengths: X (B, N, C) of lengths nx (B,), V (B, N, C)
    of lengths nv (B,). Cells further than `rband` apart in relative position (n/nx vs m/nv) are forbidden.
    Normalised by the path's nominal length (nx + nv), scaled to LW steps: equal-length sequences on the diagonal
    give the same number as the evenly stretched comparison would. Returns (B,)."""
    B, N, C = X.shape; out = np.empty(B)
    step = max(1, chunk // (N * N))
    rn = np.arange(1, N + 1)
    for s0 in range(0, B, step):
        x, v, a, b = X[s0:s0 + step], V[s0:s0 + step], nx[s0:s0 + step], nv[s0:s0 + step]; Bb = len(x)
        c = ((x[:, :, None, :] - v[:, None, :, :]) ** 2).sum(-1)                             # (Bb, N, N)
        rel = np.abs(rn[None, :, None] / a[:, None, None] - rn[None, None, :] / b[:, None, None])
        c = np.where(rel <= rband + 1e-9, c, np.inf)
        D = np.full((Bb, N + 1, N + 1), np.inf); D[:, 0, 0] = 0
        for d in range(2, 2 * N + 1):                                                         # anti-diagonals n + m = d
            n = np.arange(max(1, d - N), min(N, d - 1) + 1); m = d - n; cc = c[:, n - 1, m - 1]
            D[:, n, m] = np.minimum(np.minimum(D[:, n - 1, m - 1] + 2 * cc, D[:, n - 1, m] + cc), D[:, n, m - 1] + cc)
        out[s0:s0 + step] = D[np.arange(Bb), a, b] / (a + b) * LW
    return out


def euclid(X, V):
    """Squared Euclidean distances between every example X[e] (E, N, C) and every query V[i] (I, N, C): (I, E)."""
    Xf = X.reshape(len(X), -1); Vf = V.reshape(len(V), -1)
    return np.maximum(0, (Vf ** 2).sum(1)[:, None] + (Xf ** 2).sum(1)[None] - 2 * Vf @ Xf.T)


def dtw_pairs(X, V, band):
    """Squared DTW distance (symmetric2 / 2, Sakoe-Chiba band) between X[i, k] (I, K, N, C) and V[i] (I, N, C):
    (I, K). With band 0 it equals the squared Euclidean distance; it is never larger than it."""
    I, K, N, C = X.shape
    c = ((X[:, :, :, None, :] - V[:, None, None, :, :]) ** 2).sum(-1)          # (I, K, N, N)
    D = np.full((I, K, N + 1, N + 1), np.inf); D[:, :, 0, 0] = 0
    for n in range(1, N + 1):
        for m in range(max(1, n - band), min(N, n + band) + 1):
            cc = c[:, :, n - 1, m - 1]
            D[:, :, n, m] = np.minimum(np.minimum(D[:, :, n - 1, m - 1] + 2 * cc, D[:, :, n - 1, m] + cc), D[:, :, n, m - 1] + cc)
    return D[:, :, N, N] / 2


def dtw(X, V, band, short=64, chunk=4_000_000):
    """Squared distances (I, E) of every query V[i] to every example X[e]: Euclidean for all, then DTW for the
    `short` examples nearest by Euclid (DTW is never above Euclid, so the rest keep an upper bound)."""
    d = euclid(X, V)
    if band == 0: return d
    E, N, C = X.shape; K = min(short, E)
    idx = np.argpartition(d, K - 1, axis=1)[:, :K] if K < E else np.broadcast_to(np.arange(E), (len(V), E))
    step = max(1, chunk // (K * N * N * C))
    for s in range(0, len(V), step):
        ii = idx[s:s + step]
        d[np.arange(s, s + len(ii))[:, None], ii] = dtw_pairs(X[ii], V[s:s + step], band)
    return d


class Memory:
    """Remembered letters (individual examples, up to `cap` per letter-form), grouped by form for vectorised DTW."""

    def __init__(self, L=8, LW=16, cap=40, standardise=False, per_rise=0, nmax=40, margin=0.0):
        self.margin = margin; self.L, self.LW, self.cap, self.std, self.pr, self.nmax = L, LW, cap, standardise, per_rise, nmax
        self.wv = defaultdict(list)
        self.tr = defaultdict(list); self.wk = defaultdict(list); self.len = defaultdict(list); self.dots = defaultdict(list)

    def add(self, key, f, q, a, b, rise):
        t, w = seqs(f, q["_walk"], *self.widen(a, b, rise, len(f)), self.L, self.LW)
        if self.pr: self.wv[key].append(walk_var(q["_walk"], a, b, self.pr, self.nmax, self.L, self.LW))
        self.tr[key].append(t); self.wk[key].append(w); self.len[key].append((b - a) / rise); self.dots[key].append(FE.taps(q, a, b))

    def widen(self, a, b, rise, W):
        """The stretch felt with a little of its neighbours on each side (`margin` rises): where it comes from and
        where it goes, so a cut placed a little early or late changes less of what is felt."""
        m = int(round(self.margin * rise)); return max(0, a - m), min(W, b + m)

    def freeze(self):
        rng = np.random.default_rng(1); self.forms = {}
        pick = {k: rng.choice(len(v), min(self.cap, len(v)), replace=False) for k, v in self.tr.items()}   # same draw as feel.py
        self.mu = {k: float(np.median(v)) for k, v in self.len.items()}
        lg = {k: np.log(np.maximum(np.array(v), 1e-3)) for k, v in self.len.items()}
        self.lsd = {k: float(max(0.15, np.std(v))) if len(v) >= 3 else 0.3 for k, v in lg.items()}   # spread of the log length
        self.want = {k: Counter(v).most_common(1)[0][0] for k, v in self.dots.items()}
        by = defaultdict(list)
        for k in self.tr: by[k[1]].append(k)
        self.gT = np.ones(6); self.gW = np.ones(3)
        if self.std:                                   # every channel the same spread, the overall scale kept
            allT = np.concatenate([np.stack(v).reshape(-1, 6) for v in self.tr.values()])
            allW = np.concatenate([np.stack(v).reshape(-1, 3) for v in self.wk.values()])
            sT = allT.std(0) + 1e-6; sW = allW.std(0) + 1e-6
            self.gT = np.sqrt((sT ** 2).mean()) / sT; self.gW = np.sqrt((sW ** 2).mean()) / sW
        for form, keys in by.items():
            T, Wk, owner, WV = [], [], [], []
            for ki, k in enumerate(keys):
                sel = pick[k]
                T += [self.tr[k][i] for i in sel]; Wk += [self.wk[k][i] for i in sel]; owner += [ki] * len(sel)
                if self.pr: WV += [self.wv[k][i] for i in sel]
            self.forms[form] = dict(keys=keys, T=np.stack(T) * self.gT, W=np.stack(Wk) * self.gW, owner=np.array(owner),
                                    mu=np.array([self.mu[k] for k in keys]), lsd=np.array([self.lsd[k] for k in keys]), want=np.array([self.want[k] for k in keys], float))
            if self.pr:
                self.forms[form]["WV"] = np.stack([w for w, _ in WV]); self.forms[form]["nWV"] = np.array([n for _, n in WV])
        self.wv = None


def per_key(d, owner, nkeys, knn):
    """Per letter-form: the mean of its `knn` nearest examples' distances. d: (I, E) -> (I, K)."""
    I = d.shape[0]; out = np.full((I, nkeys), np.inf)
    for k in range(nkeys):
        dk = d[:, owner == k]
        if dk.shape[1] == 0: continue
        kk = min(knn, dk.shape[1])
        out[:, k] = np.sort(dk, 1)[:, :kk].mean(1) if kk > 1 else dk.min(1)
    return out


def shortlist(d, owner, nkeys, short, per_key):
    """Which examples get the (costly) warped comparison, by the even distance d (I, E): the `short` nearest
    overall, or (per_key > 0) the `per_key` nearest of EVERY letter-form, so that no letter is ruled out unseen."""
    I, E = d.shape
    if not per_key:
        K = min(short, E)
        return np.argpartition(d, K - 1, axis=1)[:, :K] if K < E else np.broadcast_to(np.arange(E), (I, E))
    out = []
    for k in range(nkeys):
        cols = np.where(owner == k)[0]
        if len(cols) <= per_key: out.append(np.broadcast_to(cols, (I, len(cols)))); continue
        out.append(cols[np.argpartition(d[:, cols], per_key - 1, axis=1)[:, :per_key]])
    return np.concatenate(out, 1)


class Feeler:
    """The cheapest chain of remembered letters along the path, with DTW costs. Parameters:
    band (DTW warp, in bins), knn (nearest examples averaged), and feel.py's three constants."""

    def __init__(self, mem, band=2, knn=1, letter_cost=FE.LETTER_COST, dot_w=FE.DOT_W, len_w=FE.LEN_W, wband=None, short=64, rband=0.25, vshort=None, mix=False, per_key=0, gate=0, len_gauss=False):
        self.m = mem; self.band = band; self.wband = band * mem.LW // mem.L if wband is None else wband
        self.knn = knn; self.short = short; self.rband = rband; self.vshort = vshort or short; self.mix = mix; self.per_key = per_key; self.gate = gate; self.len_gauss = len_gauss; self.lc, self.dw, self.lw = letter_cost, dot_w, len_w

    def costs(self, form, q, f, rise, spans):
        """For each span (a, b): (cost, key) of the best letter of this form."""
        fm = self.m.forms.get(form)
        if fm is None or not spans: return [(np.inf, None)] * len(spans)
        S = [seqs(f, q["_walk"], *self.m.widen(a, b, rise, len(f)), self.m.L, self.m.LW) for a, b in spans]
        T = np.stack([s[0] for s in S]) * self.m.gT; Wq = np.stack([s[1] for s in S]) * self.m.gW
        if self.m.pr:                                  # the walk at its own length, warped, on the examples nearest by the even comparison
            d = dtw(fm["T"], T, self.band, self.short); dw = euclid(fm["W"], Wq)
            dw_even = dw; idx = shortlist(d + dw, fm["owner"], len(fm["keys"]), self.vshort, self.per_key); K = idx.shape[1]
            V = [walk_var(q["_walk"], a, b, self.m.pr, self.m.nmax, self.m.L, self.m.LW) for a, b in spans]
            Vq = np.stack([v for v, _ in V]); nv = np.array([n for _, n in V]); I = len(spans)
            dv = dtw_var(fm["WV"][idx].reshape(I * K, *fm["WV"].shape[1:]), fm["nWV"][idx].ravel(),
                         np.repeat(Vq, K, 0), np.repeat(nv, K), self.rband, self.m.LW).reshape(I, K)
            dw = np.full_like(dw, np.inf); dw[np.arange(I)[:, None], idx] = dv
            d = d + (0.5 * (dw + dw_even) if self.mix else dw)
        else:
            d = dtw(fm["T"], T, self.band, self.short) + dtw(fm["W"], Wq, self.wband, self.short)          # squared, (I, E)
            if self.gate:                              # only letters with knn examples among the `gate` nearest compete
                idx = shortlist(d, fm["owner"], len(fm["keys"]), self.gate, 0); g = np.full_like(d, np.inf)
                g[np.arange(len(spans))[:, None], idx] = d[np.arange(len(spans))[:, None], idx]
                dk_g = per_key(g, fm["owner"], len(fm["keys"]), self.knn); none = ~np.isfinite(dk_g).any(1)
                d = np.where(none[:, None], d, g)          # no letter has knn examples that near: fall back to all
        d = np.sqrt(d) / np.sqrt(self.m.L)
        dk = per_key(d, fm["owner"], len(fm["keys"]), self.knn)                    # (I, K)
        ln = np.array([b - a for a, b in spans], float)
        tp = np.array([FE.taps(q, a, b) for a, b in spans], float)                  # (I, 2)
        dots = np.abs(tp[:, None, :] - fm["want"][None]).sum(-1)
        lenp = np.log(np.maximum(ln, 1)[:, None] / rise / fm["mu"][None]) ** 2
        if self.len_gauss: lenp = 0.5 * lenp / fm["lsd"][None] ** 2           # each letter's own spread of length
        c = dk * np.maximum(0.5, ln / rise)[:, None] + self.dw * dots + self.lw * lenp + self.lc
        j = c.argmin(1)
        return [(float(c[i, j[i]]), fm["keys"][j[i]]) for i in range(len(spans))]

    def read(self, q, f, rise, pos=None):
        W = q["G"]["W"]; pos = pos if pos is not None else [0] + list(q["cand"]) + [W]; m = len(pos); INF = np.inf
        fin_sp = [(0, pos[i]) for i in range(1, m - 1) if pos[i] >= 3]
        med_sp = [(pos[j], pos[i]) for i in range(2, m - 1) for j in range(1, i) if pos[i] - pos[j] >= 3]
        init_sp = [(pos[j], W) for j in range(1, m - 1) if W - pos[j] >= 3]
        C = {}
        for form, sp in (("fin", fin_sp), ("med", med_sp), ("init", init_sp), ("iso", [(0, W)])):
            for s, v in zip(sp, self.costs(form, q, f, rise, sp)): C[(form, s)] = v
        iso = C[("iso", (0, W))]; out = (iso[0], [iso[1]], [])
        state = {}
        for i in range(1, m - 1):
            if pos[i] >= 3: v, k = C[("fin", (0, pos[i]))]; state[i] = (v, [k], [pos[i]])
        for i in range(2, m - 1):
            for j in range(1, i):
                if j not in state or pos[i] - pos[j] < 3: continue
                v, k = C[("med", (pos[j], pos[i]))]; t = state[j][0] + v
                if t < state.get(i, (INF,))[0]: state[i] = (t, state[j][1] + [k], state[j][2] + [pos[i]])
        for j, (v0, seq, cuts) in state.items():
            if W - pos[j] < 3: continue
            v, k = C[("init", (pos[j], W))]
            if v0 + v < out[0]: out = (v0 + v, seq + [k], cuts)
        seq = [k for k in out[1] if k is not None][::-1]
        return seq, sorted(out[2])


def learn_memory(train, **kw):
    mem = Memory(**kw)
    for r in train:
        q, rise = r["q"], r["rise"]
        if q is None: continue
        f = FE.feeling(q, rise)
        if len(r["units"]) == 1:
            mem.add((P._base(r["units"][0]), "iso"), f, q, 0, q["G"]["W"], rise)
        elif r.get("cuts"):
            n = len(r["units"]); b = [0] + r["cuts"] + [q["G"]["W"]]
            for k in range(n):
                a, bb = b[n - 1 - k], b[n - k]
                if bb - a >= 2: mem.add((P._base(r["units"][k]), r["forms"][k]), f, q, a, bb, rise)
    mem.freeze()
    return mem
