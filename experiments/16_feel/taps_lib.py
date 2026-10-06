"""Taps and word knowledge for the feeler (experiment 16, the `taps_*` methods).

Two things a back-reader has that `feel.py` does not use:

1. THE TAPS, felt properly. `feel.py` counts dot-shaped marks above/below a letter's stretch and compares the
   count with the letter-form's usual count. But this kind of print merges two dots into one blob and three into a
   bigger one, so a count of 1 is said by ب, ت, ن, ي alike. Here each tap is felt by its SIZE: a mark's ink area
   in units of the document's own single dot (the median dot-shaped mark on the train pages — most dots are single
   dots). A letter's stretch is felt as "how much dot-ink was tapped above, how much below", and what each
   letter-form's taps feel like is LEARNED from the train pages (a smoothed histogram of that mass per side, per
   letter-form, shrunk towards all letters' histogram): the document is the witness, no table of dot counts.

2. WORD KNOWLEDGE. From the train pages' readings (Azure's), a letter n-gram over pieces (Witten-Bell
   interpolated, order 3) and a piece lexicon with counts, mixed as P(piece) = mu * count/N + (1 - mu) * P_ngram,
   mu the Witten-Bell chance that the next piece is one already seen (N / (N + types)). The prior enters the chain
   search as a cost lam * (-log P - H * (letters + 1)): H is the n-gram's own per-letter entropy on the train
   pages, so on average the prior says WHICH letters, not HOW MANY (the feeler's letter cost and length cost
   already speak to that). lam, the exchange rate between a nat of prior and a unit of felt mismatch, is chosen
   on a held-out TRAIN page (see `pick_lam`), never on dev.

The chain search (`chain`) is the same grammar as `feel.read` (final, medials, initial; or one isolated letter)
but a beam over the top letters of every stretch, so the prior can choose among near-ties of the feeling.
"""
import math
from collections import Counter, defaultdict
import numpy as np
import cv2

import feel as FE
from inkscript.geometry.penpath import _base

BINS = np.array([0.3, 0.75, 1.3, 1.8, 2.5, 3.5])        # dot-ink mass, in single dots: none / small / one / one+ / two / three / more
NB = len(BINS) + 1


# ---------------------------------------------------------------- the taps

def dot_marks(q):
    """The piece's dot-shaped marks as (place on the path, above?, ink area in pixels, width/height). Same shape
    rule as `penpath` uses for G["dots"] (a long flat mark is an underline fragment, not a dot)."""
    if "_tapm" in q: return q["_tapm"]
    out = []; st = q["G"]["stroke"]
    for s, above, k in q["G"]["marks"]:
        yy, xx = np.where(q["F"]["lab"] == k)
        if not len(yy): continue
        w, h = xx.max() - xx.min() + 1, yy.max() - yy.min() + 1
        if w >= 3 * h and w > 1.5 * st: continue
        out.append((int(s), bool(above), float(len(yy)), float(w) / float(h), "d"))
    if q.get("real") is not None:                     # a piece the cutter had to BRIDGE: its loose parts (a hamza above
        n, cc = cv2.connectedComponents(q["real"].astype(np.uint8))   # an alef, under it) were joined to the body;
        if n > 2:                                     # felt again here as loose taps, by their place on the path
            sizes = np.bincount(cc.ravel())[1:]; big = 1 + int(np.argmax(sizes))
            for c in range(1, n):
                if c == big: continue
                yy, xx = np.where(cc == c); ss = q["ink_s"][yy, xx]; ss = ss[ss >= 0]
                if not len(ss): continue
                w, h = xx.max() - xx.min() + 1, yy.max() - yy.min() + 1
                out.append((int(np.median(ss)), bool(yy.mean() < q["base"]), float(len(yy)), float(w) / float(h), "b"))
    q["_tapm"] = out
    return out


def doc_unit(train):
    """The document's single dot: the median ink area of dot-shaped marks on the train pages."""
    a = [m[2] for r in train if r["q"] is not None for m in dot_marks(r["q"]) if m[4] == "d"]
    return float(np.median(a)) if a else 1.0


WIDE = 1.4                                             # a mark this much wider than tall: two dots side by side, merged


def tapped(q, a, b, unit):
    """What was tapped inside [a, b): per side (above, below), (dot-ink in single dots, marks, widest mark's w/h)."""
    o = [[0.0, 0, 0.0, 0], [0.0, 0, 0.0, 0]]
    for s, above, area, wh, kind in dot_marks(q):
        if a <= s < b:
            t = o[0 if above else 1]
            if kind == "b": t[3] += 1
            else: t[0] += area / unit; t[1] += 1; t[2] = max(t[2], wh)
    return tuple(map(tuple, o))


def tbin(o, shape=True, bridged=False):
    """A side's taps as one cell: the mass bin, and (with shape) none / one round mark / one wide mark / several,
    and (with bridged) whether a loose part bridged into the body sits on that side."""
    m = int(np.searchsorted(BINS, o[0], side="right"))
    if shape: m = m * 4 + (0 if o[1] == 0 else 3 if o[1] >= 2 else 2 if o[2] >= WIDE else 1)
    if bridged: m = m * 2 + (o[3] > 0)
    return m


class Taps:
    """Per letter-form, the learned feel of its taps: P(cell above) * P(cell below), each a histogram over the
    side's cells, shrunk towards all letter-forms' histogram with weight ALPHA pseudo-letters. The cost is the
    negative log of that, relative to the letter-form's most usual cell (its usual taps cost nothing)."""
    ALPHA = 2.0

    def __init__(self, shape=True, bridged=False):
        self.obs = defaultdict(list); self.shape = shape; self.bridged = bridged
        self.nb = NB * (4 if shape else 1) * (2 if bridged else 1)

    def add(self, key, oa, ob): self.obs[key].append((tbin(oa, self.shape, self.bridged), tbin(ob, self.shape, self.bridged)))

    def freeze(self):
        allo = np.array([o for v in self.obs.values() for o in v]) if self.obs else np.zeros((0, 2), int)
        g = [np.bincount(allo[:, s], minlength=self.nb) + 1.0 for s in (0, 1)]; g = [x / x.sum() for x in g]
        self.nll = {}
        for k, v in self.obs.items():
            v = np.array(v); t = []
            for s in (0, 1):
                p = (np.bincount(v[:, s], minlength=self.nb) + self.ALPHA * g[s]) / (len(v) + self.ALPHA)
                t.append(-np.log(p) + np.log(p.max()))
            self.nll[k] = t
        self.g = [-np.log(x) + np.log(x.max()) for x in g]

    def cost(self, key, oa, ob):
        t = self.nll.get(key, self.g)
        return float(t[0][tbin(oa, self.shape, self.bridged)] + t[1][tbin(ob, self.shape, self.bridged)])


class Memory(FE.Memory):
    """`feel.Memory` with the taps felt by size (a learned likelihood) instead of a count against the usual count.
    TAP_W: the weight of a nat of tap evidence against a unit of felt mismatch."""

    def __init__(self, unit, tap_w=1.0, count_too=False, shape=True, bridged=False):
        super().__init__(); self.unit = unit; self.tap_w = tap_w; self.count_too = count_too; self.taps = Taps(shape, bridged)

    def add(self, key, f, q, a, b, rise):
        super().add(key, f, q, a, b, rise); self.taps.add(key, *tapped(q, a, b, self.unit))

    def freeze(self):
        super().freeze(); self.taps.freeze()

    def stretch_v(self, f, q, a, b):
        c = q.setdefault("_sv", {})                                    # the stretch's feeling does not depend on the key
        if (a, b) not in c: c[(a, b)] = FE.stretch(f, a, b, q.get("_walk"))
        return c[(a, b)]

    def cost(self, key, f, q, a, b, rise):
        v = self.stretch_v(f, q, a, b); d = float(np.sqrt(((self.X[key] - v) ** 2).sum(1)).min()) / np.sqrt(FE.L)
        c = d * max(0.5, (b - a) / rise) + FE.LEN_W * np.log(max(b - a, 1) / rise / self.mu[key]) ** 2 + FE.LETTER_COST
        c += self.tap_w * self.taps.cost(key, *tapped(q, a, b, self.unit))
        if self.count_too:
            da, db = FE.taps(q, a, b); wa, wb = self.want[key]; c += FE.DOT_W * (abs(da - wa) + abs(db - wb))
        return c


def learn_memory(train, mem):
    """Fill a memory from train records exactly as feel_v1 does (the cutter's cuts give each letter's stretch)."""
    for r in train:
        q, rise = r["q"], r["rise"]
        if q is None: continue
        f = FE.feeling(q, rise)
        if len(r["units"]) == 1:
            mem.add((_base(r["units"][0]), "iso"), f, q, 0, q["G"]["W"], rise)
        elif r.get("cuts"):
            n = len(r["units"]); b = [0] + r["cuts"] + [q["G"]["W"]]
            for k in range(n):
                a, bb = b[n - 1 - k], b[n - k]
                if bb - a >= 2: mem.add((_base(r["units"][k]), r["forms"][k]), f, q, a, bb, rise)
    mem.freeze()
    for r in train:                                                    # the per-piece caches are not needed any more
        if r["q"] is not None: r["q"].pop("_sv", None); r["q"].pop("_walk", None)
    return mem


# ---------------------------------------------------------------- word knowledge

def pieces_text(train):
    """Each train piece as a tuple of base letters, reading order (Azure's reading)."""
    return [tuple(_base(u) for u in r["units"]) for r in train if r["units"]]


class LM:
    """Letter trigram over pieces (Witten-Bell interpolated) mixed with a piece lexicon (Witten-Bell weight).
    Trained on REVERSED pieces, because the chain search walks the path from the last letter to the first."""
    N = 3

    def __init__(self, pieces, use_lex=True):
        self.use_lex = use_lex; self.lex = Counter(pieces); self.Nw = sum(self.lex.values()); self.Tw = len(self.lex)
        self.mu = self.Nw / (self.Nw + self.Tw) if self.Nw else 0.0
        self.c = defaultdict(Counter)                                  # context (tuple) -> next-letter counts
        self.V = set()
        for w in pieces:
            s = ("<",) * (self.N - 1) + tuple(reversed(w)) + (">",)
            for i in range(self.N - 1, len(s)):
                self.V.add(s[i])
                for n in range(self.N):
                    self.c[s[i - n:i]][s[i]] += 1
        self.V = sorted(self.V); self.cache = {}
        lp = [self.logp_seq(w) for w in pieces]
        self.H = -sum(lp) / max(1, sum(len(w) + 1 for w in pieces))     # nats per letter (incl. the end), on train

    def p(self, ctx, x):
        key = (ctx, x)
        if key in self.cache: return self.cache[key]
        if len(ctx) == 0:
            cnt = self.c[()]; tot = sum(cnt.values()); T = len(cnt)
            pr = (cnt[x] + 1.0) / (tot + len(self.V) + 1)                 # add-one at the bottom: never zero
        else:
            cnt = self.c.get(ctx); lower = self.p(ctx[1:], x)
            if not cnt: pr = lower
            else:
                tot = sum(cnt.values()); T = len(cnt); pr = (cnt[x] + T * lower) / (tot + T)
        self.cache[key] = pr
        return pr

    def logp_seq(self, w):
        """log P_ngram of a piece given in READING order."""
        s = ("<",) * (self.N - 1) + tuple(reversed(w)) + (">",)
        return sum(math.log(self.p(s[i - self.N + 1:i], s[i])) for i in range(self.N - 1, len(s)))

    def step(self, hist, x):
        """-log P(x | the last N-1 letters of hist), hist in path order (reversed reading)."""
        ctx = (("<",) * (self.N - 1) + tuple(hist))[-(self.N - 1):]
        return -math.log(self.p(ctx, x)) - self.H

    def final(self, hist):
        """At the end of a piece: the end symbol, then swap the n-gram's word probability for the lexicon mixture.
        Returns the cost to add to the accumulated step costs."""
        ctx = (("<",) * (self.N - 1) + tuple(hist))[-(self.N - 1):]
        end = -math.log(self.p(ctx, ">")) - self.H
        if not self.use_lex: return end
        w = tuple(reversed(hist)); lp_ng = self.logp_seq(w)
        lp = math.log(self.mu * self.lex.get(w, 0) / max(1, self.Nw) + (1 - self.mu) * math.exp(lp_ng))
        return end + (lp_ng - lp)                                       # = -lp - H*(len+1), given the steps so far

    def known(self, letters): return tuple(letters) in self.lex


# ---------------------------------------------------------------- the chain search

def chain(q, f, mem, rise, lm=None, lam=0.0, K=4, B=24, memo=None):
    """The cheapest chain of remembered letters along the path, plus lam * the word prior.
    At each stretch the K best letters of the form compete; B partial chains are kept per cut place.
    Returns (keys in reading order, cuts, felt cost, prior cost)."""
    W = q["G"]["W"]; pos = [0] + list(q["cand"]) + [W]; m = len(pos); memo = {} if memo is None else memo

    def top(form, a, b):
        if (form, a, b) not in memo:
            ks = [(mem.cost(k, f, q, a, b, rise), k) for k in mem.keys if k[1] == form]
            ks.sort(key=lambda t: t[0]); memo[(form, a, b)] = ks[:K]
        return memo[(form, a, b)]

    use = lm is not None and lam > 0
    sc = lambda h: h[0] + lam * h[1]
    fin = []                                                           # complete chains: (felt, prior, keys path-order, cuts)
    for v, k in top("iso", 0, W):
        pr = (lm.step((), k[0]) + lm.final((k[0],))) if use else 0.0
        fin.append((v, pr, [k], []))
    state = defaultdict(list)                                          # state[i]: chains covering [0, pos[i])
    for i in range(1, m - 1):
        if pos[i] >= 3:
            for v, k in top("fin", 0, pos[i]):
                state[i].append((v, lm.step((), k[0]) if use else 0.0, [k], [pos[i]]))
    for i in range(1, m - 1):
        if state[i]: state[i] = sorted(state[i], key=sc)[:B]
        for j in range(1, i):
            if not state[j] or pos[i] - pos[j] < 3: continue
            for v, k in top("med", pos[j], pos[i]):
                for h in state[j]:
                    pr = h[1] + (lm.step([x[0] for x in h[2]], k[0]) if use else 0.0)
                    state[i].append((h[0] + v, pr, h[2] + [k], h[3] + [pos[i]]))
        if state[i]: state[i] = sorted(state[i], key=sc)[:B]
    for j in range(1, m - 1):
        if not state[j] or W - pos[j] < 3: continue
        for v, k in top("init", pos[j], W):
            for h in state[j]:
                pr = h[1]
                if use:
                    hist = [x[0] for x in h[2]]; pr += lm.step(hist, k[0]) + lm.final(hist + [k[0]])
                fin.append((h[0] + v, pr, h[2] + [k], h[3]))
    best = min(fin, key=sc)
    return [k for k in best[2] if k is not None][::-1], sorted(best[3]), best[0], best[1]


def pick_lam(train, make_mem, lm_of, grid=(0.0, 0.25, 0.5, 1.0, 2.0), log=print):
    """Choose the prior's weight on the TRAIN pages alone: remember all train pages but the last, build the prior
    from the same pages, read the last train page blind with each lam, keep the lam that reads most pieces as
    Azure does (ties to the smaller lam). Returns (lam, {lam: accuracy})."""
    pages = sorted({r["page"] for r in train}); held = pages[-1]
    tr = [r for r in train if r["page"] != held]; ho = [r for r in train if r["page"] == held and r["q"] is not None]
    mem = make_mem(tr); lm = lm_of(tr); acc = {}
    rows = []
    for r in ho:
        q = r["q"]; f = FE.feeling(q, r["rise"]); truth = [_base(u) for u in r["units"]]
        rows.append((q, f, r["rise"], truth, {}))
    for lam in grid:
        ok = 0
        for q, f, rise, truth, memo in rows:
            ks, _, _, _ = chain(q, f, mem, rise, lm, lam, memo=memo); ok += [k[0] for k in ks] == truth
        acc[lam] = ok / max(1, len(rows))
    for q, *_ in rows: q.pop("_sv", None); q.pop("_walk", None)
    lam = max(grid, key=lambda l: (round(acc[l], 4), -l))
    log(f"  prior weight on held-out train page {held} ({len(rows)} pieces): " + ", ".join(f"{l}: {100 * a:.1f}%" for l, a in acc.items()) + f" -> lam {lam}")
    return lam, acc


# ---------------------------------------------------------------- how often the prior overrode the feeling

def overrides(name, docs):
    """Join a taps_prior/taps_lex read log (out/taps/<name>_<doc>.jsonl) with the dev truth (Azure) and say how
    often the prior changed the feeling's reading, whether for the better, and how it does on pieces the train
    pages never had. Analysis only: run after a bench run, never inside read()."""
    import json, sys
    from pathlib import Path
    here = Path(__file__).resolve().parent; sys.path.insert(0, str(here)); import bench
    for doc in docs:
        data = bench.load(doc); recs = [r for r in data["dev"] if r["q"] is not None]
        rows = [json.loads(l) for l in open(here / "out" / "taps" / f"{name}_{doc}.jsonl")]
        assert len(recs) == len(rows)
        lex = {"".join(_base(u) for u in r["units"]) for r in data["train"]}
        t = ["".join(_base(u) for u in r["units"]) for r in recs]
        ch = [(x["feel"] == y, x["prior"] == y) for x, y in zip(rows, t) if x["feel"] != x["prior"]]
        out = [x["prior"] == y for x, y in zip(rows, t) if not x["prior_known"]]
        nov = [(x["feel"] == y, x["prior"] == y) for x, y in zip(rows, t) if y not in lex]
        print(f"{doc}: {len(rows)} pieces; prior changed {len(ch)} ({100 * len(ch) / len(rows):.1f}%): fixed "
              f"{sum(p and not f for f, p in ch)}, broke {sum(f and not p for f, p in ch)}; prior read outside the train "
              f"lexicon {len(out)} ({100 * len(out) / len(rows):.1f}%), {sum(out)} of them right; Azure's piece not in "
              f"the train lexicon {len(nov)}: feeling right {sum(f for f, _ in nov)}, with prior {sum(p for _, p in nov)}")


if __name__ == "__main__":
    import sys
    if sys.argv[1] == "overrides": overrides(sys.argv[2], sys.argv[3:])
