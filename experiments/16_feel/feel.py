"""Read a word by FEELING it: recognition from the pen path alone, never the picture.

The owner's picture (2026-10-05): someone writes a word on your back with a stick; without looking you track
it, and know the word and where each letter starts and ends. Here every connected piece of ink is unrolled
along its pen path (`penpath.unroll`, as the letter cutter does) and turned into what a stick on the back would
give: as the pen travels from the first letter to the last, how high it is, how far the ink reaches above and
below it (an ascender, a loop, a tail), which way it is heading. The dots come afterwards, as taps at a place
along the path — the word first, then the dots, the way many people (the owner's father among them) write.

The feeler never sees the image. It learns from pages 1-4 of a document — every letter the cutter cut there,
with Azure's text as the label, kept as individual remembered feelings — and reads page 5 blind: the chain of
remembered letters that best matches the feeling of the whole piece, under the script's grammar (initial,
medials, final; or one isolated letter). The reading and the cuts come out of the same pass.

Same split and same pieces as experiment 10 (which read the PICTURE blind: 41% of pieces).

    python feel.py <azure.json> <scan.pdf> <train pages 1,2,3,4> <test pages 5> <out_dir> [--dev]

--dev: learn on the train pages minus the last, test on the last of them (for choosing the two constants).
Writes <out_dir>/feel.json (every test piece: ink, path, feeling, reading, cuts) and prints the scores.
"""
import sys, json, base64
from collections import defaultdict, Counter
from pathlib import Path
import numpy as np, cv2

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "10_atlas_reader"))
from reader import pieces_of, blind, edit                            # same pieces, same blind geometry as experiment 10
from inkscript.geometry import penpath as P

L = 8                                  # samples per letter's stretch of the feeling
CH_W = np.array([1.0, 1.4, 1.4, 0.6, 0.6, 1.0])   # height of the pen, ink above, ink below, heading (dy, dx), ink at that point
LETTER_COST = 0.2                      # what each extra letter must earn: without it a feeling is chopped into teeth
DOT_W = 1.5                            # a missing or extra tap
LEN_W = 1.0                            # an unusual length for that letter-form


def feeling(q, rise):
    """Per position along the pen path (0 = left end): what the stick tells you there."""
    W = q["G"]["W"]; base = q["base"]; ink_s = q["ink_s"]; trunk = np.array(q["trunk"], float)
    pts, s_of = walk(q); q["_walk"] = (pts, s_of, base, rise)
    my, mx = np.where(ink_s >= 0); ms = ink_s[my, mx]
    top = np.full(W, np.inf); bot = np.full(W, -np.inf)
    np.minimum.at(top, ms, my); np.maximum.at(bot, ms, my)
    ty = trunk[:, 0]
    top = np.where(np.isfinite(top), top, ty); bot = np.where(np.isfinite(bot), bot, ty)
    k = 2; nxt = trunk[np.minimum(np.arange(W) + k, W - 1)]; prv = trunk[np.maximum(np.arange(W) - k, 0)]
    d = prv - nxt; n = np.maximum(1e-6, np.hypot(d[:, 0], d[:, 1]))            # heading as the pen travels right to left
    mass = np.bincount(ms, minlength=W) / (rise * max(1.0, q["G"]["stroke"]) / 4)   # how much ink hangs here: a loop, a bowl
    f = np.stack([(base - ty) / rise, (ty - top) / rise, (bot - ty) / rise, d[:, 0] / n, d[:, 1] / n, mass], 1)
    return f.astype(float)


POOL = np.array([np.mean, np.max, np.max, np.mean, np.mean, np.mean])
LW = 16                                # samples of the stick's own walk per letter
WALK_W = 1.0                           # the walk beside the pooled outline of the stretch


def walk(q):
    """The stick's journey, as it would be felt on the back: from the first letter along the centre line to the
    last, going up every branch it meets (an alef's stem, a loop, a tail) and back down again before moving on.
    Returns the points [(y, x)] and, for each, the trunk position it belongs to."""
    sk = P.thin(q["F"]["main"]); trunk = [tuple(t) for t in q["trunk"]]; on_trunk = set(trunk)
    pix = set(zip(*np.where(sk))); seen = set(trunk); pts, s_of = [], []
    nb = lambda y, x: [(y + dy, x + dx) for dy in (-1, 0, 1) for dx in (-1, 0, 1) if (dy or dx) and (y + dy, x + dx) in pix]
    for i in range(len(trunk) - 1, -1, -1):                       # right end (the first letter) to the left end
        t = trunk[i]; pts.append(t); s_of.append(i)
        stack = [(t, iter(nb(*t)))]
        while stack:                                              # a branch: out along it, and back the same way
            node, it = stack[-1]; nxt = next((n for n in it if n not in seen), None)
            if nxt is None:
                stack.pop()
                if stack: pts.append(stack[-1][0]); s_of.append(i)
                continue
            seen.add(nxt); pts.append(nxt); s_of.append(i); stack.append((nxt, iter(nb(*nxt))))
    return np.array(pts, float), np.array(s_of)


def stretch(f, a, b, w=None):
    """A letter's stretch of the feeling, resampled to L samples, plus its length."""
    # pooled per bin, not point-sampled: a tall stroke hangs from ONE position of the path, and sampling
    # between positions stepped over every ascender (lam read as ha)
    edges = np.linspace(a, b, L + 1); seg = np.zeros((L, f.shape[1]))
    for i in range(L):
        lo = int(np.floor(edges[i])); hi = max(lo + 1, int(np.ceil(edges[i + 1])))
        part = f[lo:min(hi, len(f))] if lo < len(f) else f[-1:]
        seg[i] = [pool(part[:, c]) for c, pool in enumerate(POOL)]
    out = (seg * CH_W).ravel()
    if w is None:
        return out
    pts, s_of, base, rise = w; sel = pts[(s_of >= a) & (s_of < b)]
    if len(sel) < 2: sel = np.repeat(pts[np.argmin(np.abs(s_of - (a + b) / 2))][None], 2, 0)
    t = np.linspace(0, len(sel) - 1, LW); yy = np.interp(t, np.arange(len(sel)), sel[:, 0]); xx = np.interp(t, np.arange(len(sel)), sel[:, 1])
    dy, dx = np.diff(yy, append=yy[-1]), np.diff(xx, append=xx[-1]); n = np.maximum(1e-6, np.hypot(dy, dx))
    trip = np.stack([(base - yy) / rise, dy / n, dx / n], 1)
    return np.concatenate([out * 0.5, WALK_W * trip.ravel() * np.sqrt(L / LW)])


def taps(q, a, b):
    """Dots tapped inside [a, b): (above, below)."""
    ab = [above for s, above in q["G"]["dots"] if a <= s < b]
    return sum(ab), len(ab) - sum(ab)


class Memory:
    def __init__(self):
        self.ex = defaultdict(list); self.len = defaultdict(list); self.dots = defaultdict(list)

    def add(self, key, f, q, a, b, rise):
        self.ex[key].append(stretch(f, a, b, q.get("_walk"))); self.len[key].append((b - a) / rise); self.dots[key].append(taps(q, a, b))

    def freeze(self):
        rng = np.random.default_rng(1)
        self.X = {}
        for k, v in self.ex.items():
            v = np.stack(v); self.X[k] = v[rng.choice(len(v), min(40, len(v)), replace=False)]
        self.mu = {k: float(np.median(v)) for k, v in self.len.items()}
        self.want = {k: Counter(v).most_common(1)[0][0] for k, v in self.dots.items()}   # the document is the witness
        self.keys = list(self.X)

    def cost(self, key, f, q, a, b, rise):
        v = stretch(f, a, b, q.get("_walk")); d = float(np.sqrt(((self.X[key] - v) ** 2).sum(1)).min()) / np.sqrt(L)
        da, db = taps(q, a, b); wa, wb = self.want[key]
        # the mismatch is paid along the whole stretch, so a chain of many letters and one letter over the same
        # piece are judged on the same path; each letter then pays its way, its taps and its usual length
        return (d * max(0.5, (b - a) / rise) + DOT_W * (abs(da - wa) + abs(db - wb))
                + LEN_W * np.log(max(b - a, 1) / rise / self.mu[key]) ** 2 + LETTER_COST)


def read(q, f, mem, rise):
    """The cheapest chain of remembered letters along the path; returns [(letter, form)], cuts (path positions)."""
    W = q["G"]["W"]; pos = [0] + list(q["cand"]) + [W]; m = len(pos); memo = {}
    def c(key, a, b):
        if (key, a, b) not in memo: memo[(key, a, b)] = mem.cost(key, f, q, a, b, rise)
        return memo[(key, a, b)]
    def best(form, a, b):
        ks = [k for k in mem.keys if k[1] == form]
        return min(((c(k, a, b), k) for k in ks), default=(np.inf, None), key=lambda t: t[0])
    INF = np.inf
    iso = best("iso", 0, W); out = (iso[0], [iso[1]], [])
    state = {}                                                       # state[i]: best (cost, labels from the left, cuts) covering [0, pos[i])
    for i in range(1, m - 1):
        if pos[i] >= 3: v, k = best("fin", 0, pos[i]); state[i] = (v, [k], [pos[i]])
    for i in range(2, m - 1):
        for j in range(1, i):
            if j not in state or pos[i] - pos[j] < 3: continue
            v, k = best("med", pos[j], pos[i]); t = state[j][0] + v
            if t < state.get(i, (INF,))[0]: state[i] = (t, state[j][1] + [k], state[j][2] + [pos[i]])
    for j, (v0, seq, cuts) in state.items():
        if W - pos[j] < 3: continue
        v, k = best("init", pos[j], W)
        if v0 + v < out[0]: out = (v0 + v, seq + [k], cuts)
    seq = [k for k in out[1] if k is not None][::-1]                 # reading order
    return seq, sorted(out[2])


def png_b64(mask):
    im = (255 - mask.astype(np.uint8) * 255); ok, buf = cv2.imencode(".png", im); return base64.b64encode(buf).decode()


def learn(azure, scan, train):
    mem = Memory(); plans = []; isos = []
    for pn, pc, (units, forms), lg in pieces_of(azure, scan, train):
        if not lg or lg["rise"] < 10: continue
        if len(units) >= 2:
            p = P.plan(units, pc["blobs"], lg, forms)
            if p: p["_rise"] = lg["rise"]; plans.append(p)
        else:
            q = blind(pc, lg)
            if q: isos.append((q, (P._base(units[0]), "iso"), lg["rise"]))
    P.solve(plans)                                                   # the cutter's own cuts, with the document's atlas, as in the build
    for p in plans:
        f = feeling(p, p["_rise"])
        for k, (a, b) in enumerate(P.intervals(p)):
            if b - a >= 2: mem.add(P.key(p, k), f, p, a, b, p["_rise"])
    for q, key, rise in isos:
        mem.add(key, feeling(q, rise), q, 0, q["G"]["W"], rise)
    mem.freeze()
    print(f"remembered: {sum(len(v) for v in mem.ex.values())} letters felt, {len(mem.keys)} letter-forms, from pages {train}")
    return mem


def main(azure, scan, train, test, out_dir, mem=None, quiet=False):
    mem = mem or learn(azure, scan, train)

    n = ok = ch = err = 0; by = Counter(); ok_by = Counter(); conf = []; cut_err = []; rows = []
    for pn, pc, (units, forms), lg in pieces_of(azure, scan, test):
        if not lg or lg["rise"] < 10: continue
        truth = [P._base(u) for u in units]; rise = lg["rise"]
        q = blind(pc, lg); n += 1; nb = min(len(truth), 5); by[nb] += 1
        if q is None:
            ch += len(truth); err += len(truth); continue
        f = feeling(q, rise); seq, cuts = read(q, f, mem, rise); got = [k[0] for k in seq]
        e = edit(got, truth); ch += len(truth); err += e
        ref = None
        if len(units) >= 2:
            p = P.plan(units, pc["blobs"], lg, forms)
            if p and p["G"]["W"] == q["G"]["W"]: ref = sorted(p["cuts"])
        if e == 0:
            ok += 1; ok_by[nb] += 1
            if ref and len(ref) == len(cuts): cut_err += [abs(a - b) / q["G"]["stroke"] for a, b in zip(cuts, ref)]
        else:
            conf.append(("".join(truth), "".join(got)))
        m = q["F"]["main"].copy()
        if q.get("real") is not None: m = q["real"]
        dots = np.zeros_like(m)
        for _, _, lab_id in q["G"]["marks"]: dots |= q["F"]["lab"] == lab_id
        rows.append(dict(page=pn, truth="".join(units), got="".join(got), right=e == 0, n=len(truth),
                         w=int(m.shape[1]), h=int(m.shape[0]), ink=png_b64(m | dots),
                         W=int(q["G"]["W"]), cuts=[int(c) for c in cuts], ref=ref and [int(c) for c in ref],
                         letters=[k[0] for k in seq], forms=[k[1] for k in seq], base=float(q["base"]), rise=float(rise),
                         seg=seg_map(q, cuts, len(seq)), **walk_out(q)))
    lr = 100 * (1 - err / max(1, ch))
    if quiet:
        return dict(right=ok, n=n, letters=round(lr, 1), by={k: f"{ok_by[k]}/{by[k]}" for k in sorted(by)})
    print(f"felt blind on pages {test}: {n} pieces; read as Azure reads them: {ok} ({100 * ok / max(1, n):.1f}%); letters right {lr:.1f}%")
    print("by piece length (letters: agree/total):", {k: f"{ok_by[k]}/{by[k]}" for k in sorted(by)})
    if cut_err:
        ce = np.array(cut_err)
        print(f"cuts on correctly read joined pieces vs the cutter's: median {np.median(ce):.2f} strokes apart, within one stroke {100 * (ce <= 1).mean():.0f}% ({len(ce)} cuts)")
    print("confusions (Azure -> felt):", conf[:30])
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    summary = dict(train=train, test=test, pieces=n, right=ok, letters_right=round(lr, 1),
                   by_len={str(k): [ok_by[k], by[k]] for k in sorted(by)},
                   cut_median_strokes=float(np.median(cut_err)) if cut_err else None,
                   cut_within_stroke=float((np.array(cut_err) <= 1).mean()) if cut_err else None, cuts=len(cut_err),
                   remembered=sum(len(v) for v in mem.ex.values()), forms=len(mem.keys))
    json.dump(dict(summary=summary, pieces=rows), open(Path(out_dir) / "feel.json", "w"), ensure_ascii=False)
    return summary


def walk_out(q):
    """The stick's walk for the page to animate (at most ~500 points), and the dots as taps with where they are."""
    pts, s_of = q["_walk"][:2]; k = max(1, len(pts) // 500)
    taps_ = []
    for ds, above, lab_id in q["G"]["marks"]:
        yy, xx = np.where(q["F"]["lab"] == lab_id); taps_.append([int(ds), bool(above), round(float(yy.mean()), 1), round(float(xx.mean()), 1)])
    taps_.sort(key=lambda t: -t[0])                                   # tapped in reading order, after the word
    return dict(walk=pts[::k].astype(int).tolist(), walk_s=s_of[::k].astype(int).tolist(), marks=taps_)


def seg_map(q, cuts, n):
    """Which letter (reading order) each ink pixel was felt as: the ink's place along the path, between the cuts."""
    s = q["ink_s"].astype(int); b = [0] + list(cuts) + [q["G"]["W"]]; lab = np.full(s.shape, -1, np.int16)
    for k in range(len(b) - 1):
        lab[(s >= b[k]) & (s < b[k + 1])] = n - 1 - k
    for ds, above, lab_id in q["G"]["marks"]:
        k = next((i for i in range(len(b) - 1) if b[i] <= ds < b[i + 1]), 0); lab[q["F"]["lab"] == lab_id] = n - 1 - k
    ok, buf = cv2.imencode(".png", (lab + 1).astype(np.uint8)); return base64.b64encode(buf).decode()


if __name__ == "__main__":
    a = sys.argv[1:]; dev = "--dev" in a; a = [x for x in a if x != "--dev"]
    tr = [int(x) for x in a[2].split(",")]; te = [int(x) for x in a[3].split(",")]
    if dev:
        te, tr = [tr[-1]], tr[:-1]; mem = learn(a[0], a[1], tr)
        for lc in (0.2, 0.5, 1.0, 2.0):
            for lw in (1.0, 3.0):
                for dw in (1.5, 3.0):
                    LETTER_COST, LEN_W, DOT_W = lc, lw, dw
                    print(f"letter {lc} length {lw} dots {dw}:", main(a[0], a[1], tr, te, a[4], mem, quiet=True), flush=True)
    else:
        main(a[0], a[1], tr, te, a[4])
