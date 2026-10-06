"""The two feeler directions put together (experiment 16, the `combo_*` methods). Notes: notes/combo.md.

A letter's cost on a stretch of the path is a sum of separate terms, and each direction improved different ones:

- warp (warp_lib.py): the SHAPE term — every remembered example, the stick's walk compared by DTW (band 2), the
  mean of the 3 nearest examples, and a neighbourhood gate (a letter competes only if its 3 nearest are among the
  16 nearest of its position form);
- taps (taps_lib.py): the TAPS term — dot-ink by size and shape against the document's own single dot, bridged
  loose parts (hamzas) felt again, a likelihood learned per letter-form — and, over the whole chain, a letter
  trigram prior learned from the train pages' readings.

`Scorer` computes, for every candidate stretch of a piece, the shape+length+letter cost and the taps cost of
every letter-form SEPARATELY (vectorised as in warp_lib). `tops` then mixes them with a tap weight and keeps the
K best letters per stretch, prefilled into the memo of `taps_lib.chain`, whose beam search adds the prior. Because
the parts are kept apart, the tap weight and the prior's weight can be chosen together on a held-out train page
from one scoring pass (`pick`).
"""
import numpy as np

import feel as FE
import warp_lib as WL
import taps_lib as T

P = FE.P


class Memory(WL.Memory):
    """warp_lib's memory (every example, grouped by position form) plus taps_lib's learned taps per letter-form."""

    def __init__(self, unit, bridged=True, **kw):
        super().__init__(**kw); self.unit = unit; self.taps = T.Taps(True, bridged)

    def add(self, key, f, q, a, b, rise):
        super().add(key, f, q, a, b, rise); self.taps.add(key, *T.tapped(q, a, b, self.unit))

    def freeze(self):
        super().freeze(); self.taps.freeze()
        for fm in self.forms.values():                 # per form: (K, cells) tables of the taps' cost, above and below
            t = [self.taps.nll.get(k, self.taps.g) for k in fm["keys"]]
            fm["TA"] = np.stack([x[0] for x in t]); fm["TB"] = np.stack([x[1] for x in t])


def learn_memory(train, unit, cap=1000, bridged=True):
    mem = Memory(unit, bridged, cap=cap)
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
    for r in train:
        if r["q"] is not None: r["q"].pop("_walk", None)
    return mem


class Scorer(WL.Feeler):
    """warp_lib.Feeler's shape cost, with the taps cost returned beside it instead of the dot count.
    taps: "new" (taps_lib's learned taps) or "count" (feel.py's count against the usual count, DOT_W)."""

    def __init__(self, mem, taps="new", **kw):
        super().__init__(mem, **kw); self.taps_mode = taps

    def parts(self, form, q, f, rise, spans):
        """(keys, base (I, K), taps (I, K)) for the stretches `spans` and every letter-form of `form`."""
        fm = self.m.forms.get(form)
        if fm is None or not spans: return None
        S = [WL.seqs(f, q["_walk"], *self.m.widen(a, b, rise, len(f)), self.m.L, self.m.LW) for a, b in spans]
        Tq = np.stack([s[0] for s in S]) * self.m.gT; Wq = np.stack([s[1] for s in S]) * self.m.gW
        d = WL.dtw(fm["T"], Tq, self.band, self.short) + WL.dtw(fm["W"], Wq, self.wband, self.short)
        I = len(spans); rows = np.arange(I)[:, None]
        if self.gate:                                   # warp_lib's neighbourhood gate, unchanged
            idx = WL.shortlist(d, fm["owner"], len(fm["keys"]), self.gate, 0); g = np.full_like(d, np.inf)
            g[rows, idx] = d[rows, idx]
            ok = np.isfinite(WL.per_key(g, fm["owner"], len(fm["keys"]), self.knn)).any(1)
            d = np.where(ok[:, None], g, d)
        d = np.sqrt(d) / np.sqrt(self.m.L)
        dk = WL.per_key(d, fm["owner"], len(fm["keys"]), self.knn)
        ln = np.array([b - a for a, b in spans], float)
        lenp = np.log(np.maximum(ln, 1)[:, None] / rise / fm["mu"][None]) ** 2
        base = dk * np.maximum(0.5, ln / rise)[:, None] + self.lw * lenp + self.lc
        if self.taps_mode == "count":
            tp = np.array([FE.taps(q, a, b) for a, b in spans], float)
            tap = self.dw * np.abs(tp[:, None, :] - fm["want"][None]).sum(-1)
        else:
            o = [T.tapped(q, a, b, self.m.unit) for a, b in spans]
            ba = np.array([T.tbin(x[0], True, self.m.taps.bridged) for x in o])
            bb = np.array([T.tbin(x[1], True, self.m.taps.bridged) for x in o])
            tap = fm["TA"][:, ba].T + fm["TB"][:, bb].T
        return fm["keys"], base, tap

    def score_piece(self, q, f, rise):
        """Every stretch the chain search will ask about, per form: {form: (spans, keys, base, taps)}."""
        W = q["G"]["W"]; pos = [0] + list(q["cand"]) + [W]; m = len(pos)
        sp = dict(fin=[(0, pos[i]) for i in range(1, m - 1) if pos[i] >= 3],
                  med=[(pos[j], pos[i]) for i in range(2, m - 1) for j in range(1, i) if pos[i] - pos[j] >= 3],
                  init=[(pos[j], W) for j in range(1, m - 1) if W - pos[j] >= 3], iso=[(0, W)])
        out = {}
        for form, s in sp.items():
            r = self.parts(form, q, f, rise, s)
            if r is not None: out[form] = (s, *r)
        return out


class _Memo(dict):
    """A memo every stretch is in: a form no train letter had offers no letters (instead of asking a memory)."""
    def __contains__(self, k): return True
    def __missing__(self, k): return []


def tops(parts, tap_w, K=4):
    """The memo taps_lib.chain reads: {(form, a, b): [(cost, key)] the K cheapest, finite only}."""
    memo = _Memo()
    for form, (spans, keys, base, tap) in parts.items():
        c = base + tap_w * tap; kk = min(K, c.shape[1])
        idx = np.argpartition(c, kk - 1, axis=1)[:, :kk] if kk < c.shape[1] else np.broadcast_to(np.arange(c.shape[1]), c.shape)
        for i, (a, b) in enumerate(spans):
            lst = sorted((float(c[i, j]), keys[j]) for j in idx[i] if np.isfinite(c[i, j]))
            memo[(form, a, b)] = lst
    return memo


def read_parts(q, parts, tap_w, lm=None, lam=0.0):
    """The chain (letters in reading order, cuts) for one piece's scored parts."""
    memo = tops(parts, tap_w)
    if not memo.get(("iso", 0, q["G"]["W"])):
        memo[("iso", 0, q["G"]["W"])] = [(1e9, (None, "iso"))]   # never chosen if anything else exists
    ks, cuts, _, _ = T.chain(q, None, None, None, lm, lam, memo=memo)
    return [k[0] for k in ks if k[0] is not None], cuts


def pick(train, make_scorer, lm_of, tap_grid, lam_grid, log=print):
    """Choose the tap weight and the prior's weight together on the TRAIN pages alone, as taps_lib.pick_lam does:
    remember all train pages but the last, read the last blind with every pair, keep the pair that reads most
    pieces as Azure does (ties to the smaller lam, then the tap weight nearest 0.5, taps_prior's)."""
    pages = sorted({r["page"] for r in train}); held = pages[-1]
    tr = [r for r in train if r["page"] != held]; ho = [r for r in train if r["page"] == held and r["q"] is not None]
    sc = make_scorer(tr); lm = lm_of(tr); rows = []
    for r in ho:
        q = r["q"]; f = FE.feeling(q, r["rise"])
        rows.append((q, sc.score_piece(q, f, r["rise"]), [P._base(u) for u in r["units"]])); q.pop("_walk", None)
    acc = {}
    for tw in tap_grid:
        for lam in lam_grid:
            acc[(tw, lam)] = np.mean([read_parts(q, p, tw, lm, lam)[0] == t for q, p, t in rows])
    best = max(acc, key=lambda k: (round(acc[k], 4), -k[1], -abs(k[0] - 0.5)))
    log(f"  held-out train page {held} ({len(rows)} pieces): best tap_w {best[0]}, lam {best[1]} ({100 * acc[best]:.1f}%); "
        + "; ".join(f"{tw}/{lam}: {100 * a:.1f}" for (tw, lam), a in acc.items()), flush=True)
    return best, acc
