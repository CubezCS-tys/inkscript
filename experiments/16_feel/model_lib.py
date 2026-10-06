"""Shared pieces for the trained feelers (methods/model_*.py): the feeling as a sequence, and a small CTC reader.

The feeling a stick on the back gives (feel.py), laid out as one sequence per piece in READING order (the right
end of the pen path first), resampled at a fixed rate per rise so that four typefaces at four scan sizes feel
alike. Per path position s the channels are:

  0-5   feel.feeling: pen height, ink above, ink below, heading (dy, dx), ink mass        (per rise / unit)
  6-8   the stick's walk up the branches at s: highest point, lowest point, branch length  (per rise)
  9-10  taps: a dot above / below placed at s (smeared over a stroke)
  11-16 the cutter's geometric facts at s: ascender, tall, descender, deep, thin, connector (0/1)
  17    a candidate cut place at s (0/1)

No pixel of the picture goes in; everything is what the pen path, its branches and its taps give.
The model reads the sequence with CTC (letters = base + form, as feel.py names them) and, from a second head
trained on the cutter's cuts, says where between two letters the boundary is most likely.
"""
import sys, pickle, time
from pathlib import Path
import numpy as np

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(HERE.parents[0] / "10_atlas_reader"))
import feel as FE                                                     # noqa: E402

C = 18
MAXCH = np.array([0, 1, 1, 0, 0, 0, 1, 0, 1, 1, 1, 1, 1, 1, 1, 0, 0, 1], bool)  # max-pooled channels (the rest averaged)
MINCH = np.array([0] * 7 + [1] + [0] * 10, bool)                                 # the branch's lowest point: min-pooled
FEATS = HERE / "out" / "model_feats"


def raw(rec):
    """Per path position (0 = left end) the channels above, as a (W, C) array; None if the piece has no path."""
    q, rise = rec["q"], rec["rise"]
    if q is None: return None
    f = FE.feeling(q, rise); W = q["G"]["W"]; G = q["G"]
    pts, s_of, base, _ = q["_walk"]
    h = (base - pts[:, 0]) / rise
    hi = np.full(W, -np.inf); lo = np.full(W, np.inf); cnt = np.bincount(s_of, minlength=W).astype(float)
    np.maximum.at(hi, s_of, h); np.minimum.at(lo, s_of, h)
    hi = np.where(np.isfinite(hi), hi, f[:, 0]); lo = np.where(np.isfinite(lo), lo, f[:, 0])
    st = max(1, int(G["stroke"])); da = np.zeros(W); db = np.zeros(W)
    for s, above in G["dots"]:
        a, b = max(0, int(s) - st // 2), min(W, int(s) + st // 2 + 1)
        (da if above else db)[a:b] += 1
    facts = [np.asarray(G[k], float)[:W] for k in ("asc", "tall", "desc", "deep", "thin")] + [np.asarray(q["conn"], float)[:W]]
    cand = np.zeros(W); cand[[c for c in q["cand"] if 0 <= c < W]] = 1
    x = np.column_stack([f, hi, lo, cnt / rise, da, db] + facts + [cand]).astype(np.float32)
    x.flags.writeable = True
    return x


def resample(x, rise, rate, rev=True):
    """(W, C) per path position -> (T, C) frames at `rate` frames per rise, in reading order if rev.
    Returns frames and the bin edges in path positions (left-end coordinates, increasing)."""
    W = len(x); T = max(2, int(round(W / rise * rate)))
    edges = np.linspace(0, W, T + 1); lo = np.floor(edges[:-1]).astype(int); hi = np.maximum(lo + 1, np.ceil(edges[1:]).astype(int))
    lo = np.minimum(lo, W - 1); hi = np.minimum(hi, W)
    # pooled per bin: mean (by cumulative sums), max and min by a reduceat over the bin starts (bins may overlap
    # by one position, so take each bin explicitly when they do)
    cs = np.vstack([np.zeros((1, x.shape[1]), np.float32), np.cumsum(x, 0)])
    mean = (cs[hi] - cs[lo]) / (hi - lo)[:, None]
    mx = np.stack([x[a:b].max(0) for a, b in zip(lo, hi)]); mn = np.stack([x[a:b].min(0) for a, b in zip(lo, hi)])
    out = np.where(MAXCH, mx, np.where(MINCH, mn, mean)).astype(np.float32)
    if rev: out = out[::-1].copy()
    return out, edges


def labels_of(rec):
    return [(FE.P._base(u), f) for u, f in zip(rec["units"], rec["forms"])]


def boundary_target(rec, edges, rev=True):
    """Per frame: 1 where a cutter's cut falls inside the frame (smeared to neighbours at 0.5)."""
    T = len(edges) - 1; y = np.zeros(T, np.float32)
    if not rec.get("cuts"): return None
    for c in rec["cuts"]:
        k = int(np.clip(np.searchsorted(edges, c, side="right") - 1, 0, T - 1))
        y[k] = 1.0
        for j in (k - 1, k + 1):
            if 0 <= j < T: y[j] = max(y[j], 0.5)
    return y[::-1].copy() if rev else y


def doc_train_raw(doc):
    """Every train record of one document as (raw features, rise, labels, cuts, W), cached on disk."""
    FEATS.mkdir(parents=True, exist_ok=True); p = FEATS / f"{doc}_train.pkl"
    if p.exists(): return pickle.load(open(p, "rb"))
    from bench import load
    recs = load(doc)["train"]; out = []
    for r in recs:
        x = raw(r)
        if x is None: continue
        out.append(dict(x=x, rise=r["rise"], units=r["units"], forms=r["forms"], cuts=r.get("cuts"), W=r["q"]["G"]["W"], doc=doc))
    del recs
    pickle.dump(out, open(p, "wb")); return out


def from_records(recs):
    out = []
    for r in recs:
        x = raw(r)
        if x is None: continue
        out.append(dict(x=x, rise=r["rise"], units=r["units"], forms=r["forms"], cuts=r.get("cuts"), W=r["q"]["G"]["W"], doc=r["doc"]))
    return out


# ------------------------------------------------------------------ the model
import torch                                                          # noqa: E402
import torch.nn as nn                                                 # noqa: E402
import torch.nn.functional as Fn                                      # noqa: E402

torch.set_num_threads(4)

FORMS = ("init", "med", "fin", "iso")


class Reader(nn.Module):
    """Frames -> per-frame letter scores (CTC, index 0 = blank) and a boundary score."""

    def __init__(self, nlab, c=C, h=128, conv=96, layers=2, drop=0.2):
        super().__init__()
        self.norm = nn.LayerNorm(c)
        self.conv = nn.Sequential(nn.Conv1d(c, conv, 5, padding=2), nn.GELU(), nn.Dropout(drop),
                                  nn.Conv1d(conv, conv, 5, padding=2), nn.GELU())
        self.rnn = nn.LSTM(conv, h, num_layers=layers, bidirectional=True, batch_first=True, dropout=drop)
        self.drop = nn.Dropout(drop)
        self.out = nn.Linear(2 * h, nlab + 1); self.cut = nn.Linear(2 * h, 1)

    def forward(self, x, lens):
        z = self.conv(self.norm(x).transpose(1, 2)).transpose(1, 2)
        z = nn.utils.rnn.pack_padded_sequence(z, lens.cpu(), batch_first=True, enforce_sorted=False)
        z, _ = self.rnn(z); z, _ = nn.utils.rnn.pad_packed_sequence(z, batch_first=True)
        z = self.drop(z)
        return self.out(z), self.cut(z).squeeze(-1)


def collate(items):
    lens = torch.tensor([len(i[0]) for i in items]); T = int(lens.max()); B = len(items)
    x = torch.zeros(B, T, C); yb = torch.zeros(B, T); mb = torch.zeros(B, T)
    tg = []; tl = []
    for b, (f, lab, bt) in enumerate(items):
        x[b, :len(f)] = torch.from_numpy(f); tg += lab; tl.append(len(lab))
        if bt is not None: yb[b, :len(bt)] = torch.from_numpy(bt); mb[b, :len(bt)] = 1
    return x, lens, torch.tensor(tg), torch.tensor(tl), yb, mb


def augment(x, rng):
    """A little of another hand: heights scaled and shifted, heading jittered, noise."""
    x = x.copy()
    s = rng.uniform(0.9, 1.1); x[:, [0, 1, 2, 6, 7]] *= s
    x[:, [0, 6, 7]] += rng.normal(0, 0.05)
    x[:, 3:6] += rng.normal(0, 0.05, (len(x), 3)).astype(np.float32)
    return x


def train(items, vocab, rate=20, epochs=40, seed=0, bs=32, lr=2e-3, cut_w=0.5, model=None, log=None,
          stretch=0.15, aug=True, **kw):
    """items: dicts from doc_train_raw/from_records. Returns the trained Reader."""
    torch.manual_seed(seed); rng = np.random.default_rng(seed)
    idx = {k: i + 1 for i, k in enumerate(vocab)}
    data = [d for d in items if all(k in idx for k in labels_of(d))]
    m = model or Reader(len(vocab), **kw)
    opt = torch.optim.AdamW(m.parameters(), lr=lr, weight_decay=1e-2)
    steps = epochs * ((len(data) + bs - 1) // bs)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=lr, total_steps=steps, pct_start=0.15)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True); t0 = time.time()
    for ep in range(epochs):
        m.train(); order = rng.permutation(len(data)); tot = n = 0
        for i in range(0, len(order), bs):
            batch = []
            for j in order[i:i + bs]:
                d = data[j]; r = rate * (rng.uniform(1 - stretch, 1 + stretch) if aug else 1.0)
                f, edges = resample(d["x"], d["rise"], r)
                lab = [idx[k] for k in labels_of(d)]
                if len(f) < 2 * len(lab):                              # CTC needs room (and a blank between repeats)
                    f, edges = resample(d["x"], d["rise"], r * (2 * len(lab) + 1) / len(f))
                bt = boundary_target(d, edges)
                if aug: f = augment(f, rng)
                batch.append((f, lab, bt))
            x, lens, tg, tl, yb, mb = collate(batch)
            lo, cu = m(x, lens)
            lp = Fn.log_softmax(lo, -1).transpose(0, 1)
            loss = ctc(lp, tg, lens, tl)
            if mb.sum() > 0:
                bce = Fn.binary_cross_entropy_with_logits(cu, yb, reduction="none", pos_weight=torch.tensor(4.0))
                loss = loss + cut_w * (bce * mb).sum() / mb.sum()
            opt.zero_grad(); loss.backward(); nn.utils.clip_grad_norm_(m.parameters(), 1.0); opt.step(); sched.step()
            tot += float(loss) * len(batch); n += len(batch)
        if log: log(f"epoch {ep + 1}/{epochs} loss {tot / n:.3f} ({time.time() - t0:.0f}s)")
    m.eval(); m.vocab = list(vocab); m.rate = rate
    return m


def vocab_of(items):
    from collections import Counter
    c = Counter(k for d in items for k in labels_of(d))
    return sorted(c)


def valid_forms(forms):
    """init med* fin, or iso, possibly several such runs touching (iso/fin may be followed by init/iso)."""
    prev = None
    for f in forms:
        if prev in (None, "fin", "iso"):
            if f not in ("init", "iso"): return False
        else:
            if f not in ("med", "fin"): return False
        prev = f
    return prev in ("fin", "iso")


def decode(m, x, rise, cand, W, beam=8, rate=None, cut_mode="frame"):
    """Read one piece. Returns letters [(base, form)] in reading order and cuts (path positions, increasing).

    Letters: a prefix beam search over the CTC output that only keeps chains the script's grammar allows
    (init, med*, fin; or iso). Cuts: the frames of each letter from the best alignment; between two letters,
    the frame with the highest boundary score, mapped back to the path and snapped to the nearest candidate."""
    rate = rate or m.rate
    f, edges = resample(x, rise, rate)
    with torch.no_grad():
        lo, cu = m(torch.from_numpy(f)[None], torch.tensor([len(f)]))
    lp = Fn.log_softmax(lo[0], -1).numpy(); cb = cu[0].numpy()
    voc = m.vocab
    seq = beam_search(lp, voc, beam)
    if not seq:
        seq = [int(np.argmax(lp[:, 1:].max(0))) + 1]
    peaks = align(lp, seq)
    T = len(f); cuts = []
    cmid = np.array([(edges[k] + edges[k + 1]) / 2 for k in range(T)])[::-1]      # path position of each frame (reading order)
    for a, b in zip(peaks[:-1], peaks[1:]):
        if cut_mode == "cand" and cand and b > a:
            # the candidate cut places lying between the two letters' emissions; the one whose frame the boundary
            # head likes best
            lo_s, hi_s = cmid[b], cmid[a]
            inside = [c for c in cand if lo_s <= c <= hi_s]
            if inside:
                fr = lambda c: T - 1 - int(np.clip(np.searchsorted(edges, c, side="right") - 1, 0, T - 1))
                cuts.append(int(max(inside, key=lambda c: cb[fr(c)]))); continue
        k = a + 1 + int(np.argmax(cb[a + 1:b + 1])) if b > a else a        # frame in reading order
        s = cmid[k]
        if cand:
            c = min(cand, key=lambda c: abs(c - s))
            if abs(c - s) <= rise * 0.25: s = c
        cuts.append(int(round(s)))
    return [voc[i - 1] for i in seq], sorted(cuts)


def beam_search(lp, voc, beam):
    """CTC prefix beam search with the script's grammar as a constraint on the forms."""
    from collections import defaultdict
    T, V = lp.shape; NEG = -1e30
    def lse(a, b):
        if a < b: a, b = b, a
        return a if b <= NEG else a + np.log1p(np.exp(b - a))
    form = [None] + [k[1] for k in voc]
    def can_follow(prev_last, nf):
        if prev_last in (None, "fin", "iso"): return nf in ("init", "iso")
        return nf in ("med", "fin")
    beams = {(): (0.0, NEG)}                                       # prefix -> (p_blank, p_nonblank)
    top = np.argsort(-lp, 1)[:, :12]
    for t in range(T):
        nb = defaultdict(lambda: [NEG, NEG])
        for pre, (pb, pn) in beams.items():
            tot = lse(pb, pn); last = pre[-1] if pre else None
            e = nb[pre]; e[0] = lse(e[0], tot + lp[t, 0])
            if last is not None:
                e[1] = lse(e[1], pn + lp[t, last])
            lf = form[last] if last else None
            for v in top[t]:
                if v == 0: continue
                if not can_follow(lf, form[v]): continue
                npre = pre + (int(v),); e2 = nb[npre]
                if v == last: e2[1] = lse(e2[1], pb + lp[t, v])
                else: e2[1] = lse(e2[1], tot + lp[t, v])
        beams = dict(sorted(((k, tuple(v)) for k, v in nb.items()), key=lambda kv: -lse(*kv[1]))[:beam])
    ok = [(k, lse(*v)) for k, v in beams.items() if k and form[k[-1]] in ("fin", "iso")]
    if not ok: ok = [(k, lse(*v)) for k, v in beams.items() if k]
    return list(max(ok, key=lambda t: t[1])[0]) if ok else []


def align(lp, seq):
    """Viterbi CTC alignment of seq; returns for each label the frame where it is most confidently emitted."""
    T = len(lp); ext = [0]
    for s in seq: ext += [s, 0]
    S = len(ext); NEG = -1e30
    dp = np.full((T, S), NEG); bp = np.zeros((T, S), int)
    dp[0, 0] = lp[0, 0]
    if S > 1: dp[0, 1] = lp[0, ext[1]]
    for t in range(1, T):
        for s in range(S):
            c = [(dp[t - 1, s], s)]
            if s >= 1: c.append((dp[t - 1, s - 1], s - 1))
            if s >= 2 and ext[s] != 0 and ext[s] != ext[s - 2]: c.append((dp[t - 1, s - 2], s - 2))
            v, b = max(c); dp[t, s] = v + lp[t, ext[s]]; bp[t, s] = b
    s = S - 1 if S == 1 or dp[-1, S - 1] >= dp[-1, S - 2] else S - 2
    path = [s]
    for t in range(T - 1, 0, -1):
        s = bp[t, s]; path.append(s)
    path = path[::-1]
    peaks = []
    for k in range(len(seq)):
        fr = [t for t in range(T) if path[t] == 2 * k + 1]
        peaks.append(max(fr, key=lambda t: lp[t, seq[k]]) if fr else (peaks[-1] + 1 if peaks else 0))
    return peaks
