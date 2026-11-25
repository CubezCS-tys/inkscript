"""Experiment 96, goal 2 candidate (b): a small learned "next line" model (pointer style) trained on Argon's reading
order over the training pool (train split only; never the validation documents, held-out or locked journals, or the
test set), local CPU.

    python next96.py data [N]   -> out/next96_data.pt   N training pages (seed 96), Azure boxes + Argon types + ranks
    python next96.py train      -> out/next96.pt        an MLP scoring (line, candidate next line) pairs
order_learned(boxes, labels, rtl, H, W) -> indices in reading order.

Everything happens in the right-to-left frame (a Latin page is mirrored).  For each line i the candidates are the 8
lines nearest in the column rule's order (order96.order_cols) and the 8 nearest by distance between box centres; the
model scores each candidate from the pair's geometry (offsets of the four edges and centres in line heights, widths,
overlaps, page position), both lines' types (16 fine classes + none) and the column rule's own opinion (rank
difference, "is the rule's next line").  Trained with a softmax over each line's candidates against Argon's next line.
Decoding: start at the rule's first line; go to the best-scoring unvisited candidate; when none is left, jump to the
rule's first unvisited line.
"""
from __future__ import annotations

import json
import random
import sys
from collections import defaultdict

import numpy as np

from common96 import FINE, O94, OUT, azure_lines, guard_training, inventory_azure, page_is_rtl
from order96 import order_cols

K = 8
TYPES = FINE + ["none"]


def mirror(B, rtl):
    B = np.array(B, dtype=float)
    if rtl:
        return B
    xm = B[:, 2].max() + B[:, 0].min()
    return np.stack([xm - B[:, 2], B[:, 1], xm - B[:, 0], B[:, 3]], 1)


def page_feats(boxes, labels, rtl, W, H):
    """(pairs [(i, j)], X features, rule order)."""
    n = len(boxes)
    rule = order_cols(boxes, labels, rtl, H=H, W=W)
    rk = np.empty(n, int)
    rk[rule] = np.arange(n)
    B = mirror(boxes, rtl)
    mh = float(np.median(np.maximum(1e-6, B[:, 3] - B[:, 1])))
    gw = max(1e-6, B[:, 2].max() - B[:, 0].min())
    gh = max(1e-6, B[:, 3].max() - B[:, 1].min())
    xc, yc = (B[:, 0] + B[:, 2]) / 2, (B[:, 1] + B[:, 3]) / 2
    T = np.array([TYPES.index(l) if l in TYPES else TYPES.index("none") for l in labels])
    pairs = []
    for i in range(n):
        near = set(rule[max(0, rk[i] - K): rk[i] + K + 1])
        d = np.hypot((xc - xc[i]) / gw, (yc - yc[i]) / gh)
        near |= set(np.argsort(d)[:K + 1].tolist())
        near.discard(i)
        pairs += [(i, j) for j in sorted(near)]
    if not pairs:
        return [], np.zeros((0, 1), np.float32), rule
    I, J = np.array(pairs).T
    hov = np.minimum(B[I, 2], B[J, 2]) - np.maximum(B[I, 0], B[J, 0])
    vov = np.minimum(B[I, 3], B[J, 3]) - np.maximum(B[I, 1], B[J, 1])
    wi, wj = B[I, 2] - B[I, 0], B[J, 2] - B[J, 0]
    hi, hj = B[I, 3] - B[I, 1], B[J, 3] - B[J, 1]
    dr = rk[J] - rk[I]
    geo = np.stack([(B[J, 0] - B[I, 0]) / mh, (B[J, 2] - B[I, 2]) / mh, (B[J, 1] - B[I, 3]) / mh, (B[J, 1] - B[I, 1]) / mh,
                    (xc[J] - xc[I]) / mh, (yc[J] - yc[I]) / mh, (xc[J] - xc[I]) / gw, (yc[J] - yc[I]) / gh,
                    wi / gw, wj / gw, hi / mh, hj / mh, hov / np.maximum(1e-6, np.minimum(wi, wj)),
                    vov / np.maximum(1e-6, np.minimum(hi, hj)), (xc[I] - B[:, 0].min()) / gw, (yc[I] - B[:, 1].min()) / gh,
                    (xc[J] - B[:, 0].min()) / gw, (yc[J] - B[:, 1].min()) / gh,
                    np.clip(dr, -K, K) / K, (dr == 1).astype(float), (dr < 0).astype(float),
                    np.full(len(I), np.log(n) / 5)], 1)
    geo = np.clip(geo, -30, 30)
    oh = np.zeros((len(I), 2 * len(TYPES)))
    oh[np.arange(len(I)), T[I]] = 1
    oh[np.arange(len(I)), len(TYPES) + T[J]] = 1
    return pairs, np.concatenate([geo, oh], 1).astype(np.float32), rule


def data(N=6000):
    import torch
    rows = [json.loads(l) for l in open(O94 / "train94.jsonl", encoding="utf-8")]
    rows = [r for r in rows if r["split"] == "train"]
    random.Random(96).shuffle(rows)
    rows = sorted(rows[:int(N)], key=lambda r: r["key"])
    guard_training([r["key"] for r in rows])
    az = inventory_azure()
    Xs, grp, tgt, gid = [], [], [], 0
    for n, r in enumerate(rows, 1):
        L = [x for x in r["lines"] if x["rank"] is not None]
        if len(L) < 3 or len(L) > 300:
            continue
        A, W, H = azure_lines(az[r["stem"]], r["page"])
        A = {x["i"]: x for x in A}
        L = [x for x in L if A.get(x["i"], {}).get("box")]
        if len(L) < 3:
            continue
        rtl = page_is_rtl([A[x["i"]]["text"] for x in L])
        pairs, X, _ = page_feats([A[x["i"]]["box"] for x in L], [x["fine"] or "none" for x in L], rtl, W, H)
        ref = sorted(range(len(L)), key=lambda k: L[k]["rank"])
        nxt = {a: b for a, b in zip(ref, ref[1:])}
        by = defaultdict(list)
        for q, (i, j) in enumerate(pairs):
            by[i].append(q)
        keep = []
        for i, qs in by.items():
            if i not in nxt or not any(pairs[q][1] == nxt[i] for q in qs):
                continue
            for q in qs:
                keep.append(q)
                grp.append(gid)
                tgt.append(int(pairs[q][1] == nxt[i]))
            gid += 1
        Xs.append(X[keep])
        if n % 500 == 0:
            print(n, gid, flush=True)
    X = np.concatenate(Xs)
    torch.save(dict(X=torch.from_numpy(X), g=torch.tensor(grp), y=torch.tensor(tgt, dtype=torch.float32)),
               OUT / "next96_data.pt")
    print("rows", X.shape, "groups", gid)


def net(d):
    import torch.nn as nn
    return nn.Sequential(nn.Linear(d, 128), nn.ReLU(), nn.Linear(128, 64), nn.ReLU(), nn.Linear(64, 1))


def train(epochs=6):
    import torch
    torch.manual_seed(96)
    torch.set_num_threads(2)
    D = torch.load(OUT / "next96_data.pt")
    X, g, y = D["X"], D["g"], D["y"]
    ng = int(g.max()) + 1
    mu, sd = X.mean(0), X.std(0) + 1e-6
    sd[22:] = 1.0
    mu[22:] = 0.0
    Xn = (X - mu) / sd
    m = net(X.shape[1])
    opt = torch.optim.Adam(m.parameters(), lr=2e-3)
    # groups are contiguous: batch by group ranges
    starts = torch.cat([torch.tensor([0]), torch.nonzero(g[1:] != g[:-1]).flatten() + 1, torch.tensor([len(g)])])
    order = torch.randperm(ng)
    for ep in range(int(epochs)):
        tot, acc, cnt = 0.0, 0, 0
        perm = torch.randperm(ng)
        for b in range(0, ng, 2048):
            gs = perm[b:b + 2048]
            idx = torch.cat([torch.arange(starts[k], starts[k + 1]) for k in gs.tolist()])
            gi = torch.cat([torch.full((int(starts[k + 1] - starts[k]),), n) for n, k in enumerate(gs.tolist())])
            s = m(Xn[idx]).squeeze(1)
            mx = torch.full((len(gs),), -1e9).scatter_reduce(0, gi, s, "amax")
            e = torch.exp(s - mx[gi])
            den = torch.zeros(len(gs)).index_add(0, gi, e)
            logp = s - mx[gi] - torch.log(den[gi])
            loss = -(logp * y[idx]).sum() / len(gs)
            opt.zero_grad()
            loss.backward()
            opt.step()
            tot += float(loss) * len(gs)
            with torch.no_grad():
                best = torch.full((len(gs),), -1e9).scatter_reduce(0, gi, s, "amax")
                acc += int(((s == best[gi]) & (y[idx] > 0)).sum())
            cnt += len(gs)
        print(f"epoch {ep} loss {tot / cnt:.4f} top1 {acc / cnt:.4f}", flush=True)
    del order
    torch.save(dict(state=m.state_dict(), mu=mu, sd=sd, d=X.shape[1]), OUT / "next96.pt")


_M = {}
DECODE = dict(mode="greedy")


def _chains(n, pairs, s, cand, rule):
    """Greedy path cover: the line pairs taken by descending softmax probability within each line's candidates,
    each line at most one next and one previous, no cycles; chains are then read in the order of the rule's rank of
    their first line."""
    prob = {}
    for i, c in cand.items():
        v = np.array([x for x, _ in c])
        e = np.exp(v - v.max())
        e /= e.sum()
        for (x, j), p in zip(c, e):
            prob[(i, j)] = p
    nxt, prv = {}, {}
    head = list(range(n))           # union-find over chains to refuse cycles

    def f(i):
        while head[i] != i:
            head[i] = head[head[i]]
            i = head[i]
        return i
    for (i, j), p in sorted(prob.items(), key=lambda t: -t[1]):
        if p < 0.3 or i in nxt or j in prv or f(i) == f(j):
            continue
        nxt[i], prv[j] = j, i
        head[f(i)] = f(j)
    rk = {k: r for r, k in enumerate(rule)}
    starts = sorted((i for i in range(n) if i not in prv), key=lambda i: rk[i])
    out = []
    for st in starts:
        i = st
        while i is not None:
            out.append(i)
            i = nxt.get(i)
    return out


def _model():
    if "m" not in _M:
        import torch
        torch.set_num_threads(2)
        c = torch.load(OUT / "next96.pt")
        m = net(c["d"])
        m.load_state_dict(c["state"])
        m.eval()
        _M.update(m=m, mu=c["mu"], sd=c["sd"])
    return _M


def order_learned(boxes, labels, rtl, H, W):
    import torch
    n = len(boxes)
    if n < 3:
        return order_cols(boxes, labels, rtl, H=H, W=W)
    labels = [l if l in TYPES else "none" for l in labels]
    pairs, X, rule = page_feats(boxes, labels, rtl, W, H)
    M = _model()
    with torch.no_grad():
        s = M["m"]((torch.from_numpy(X) - M["mu"]) / M["sd"]).squeeze(1).numpy()
    cand = defaultdict(list)
    for (i, j), v in zip(pairs, s):
        cand[i].append((v, j))
    if DECODE["mode"] == "chains":
        return _chains(n, pairs, s, cand, rule)
    seen, out = set(), []
    cur = rule[0]
    while True:
        out.append(cur)
        seen.add(cur)
        if len(out) == n:
            break
        c = [(v, j) for v, j in cand[cur] if j not in seen]
        cur = max(c)[1] if c else next(k for k in rule if k not in seen)
    return out


if __name__ == "__main__":
    {"data": data, "train": train}[sys.argv[1]](*sys.argv[2:])
