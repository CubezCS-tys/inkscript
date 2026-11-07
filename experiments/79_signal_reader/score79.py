"""Experiment 79, rung 2 (rented GPU): three readers over the same lines, and the image reader's N best re-scored.

    python score79.py --x77 /work/x77 --x78 /work/x78 --sig /work/out/p4/model.pt --sigdata /work/data3 --out /work/out/fuse

Readers (weights read only, copied from experiments 77 and 78):
  img77 = experiment 77's v1 (CNN + BiLSTM, CTC; its train77.py imported unchanged for the model and data code);
  img78 = experiment 78's syn_then_real (its train78.py, likewise) - the image + image CONTROL;
  sig   = this experiment's signal reader (train79b.SignalReader).
Lines: experiment 77's dev split (held-in articles, Azure / v2 labels) and its test split (the held-out pages).
For each line: experiment 77's N best readings by CTC prefix beam search (beam 10, N <= 8), and the CTC
log-likelihood of every candidate under each reader (a character a reader cannot write -> None).  Greedy readings
and img77's per-frame confidence are kept for the warning's controls.  Writes <out>/{dev,test}.jsonl.
"""
from __future__ import annotations

import argparse
import json
import math
import sys
from collections import defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F


def load_image_reader(path: str, module, ck_path: str, dev):
    sys.path.insert(0, path)
    m = __import__(module)
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    mm = ck["meta"]
    cs = m.Charset(mm["chars"])
    try:
        model = m.Reader(len(cs), arch=mm.get("arch", "lstm"), hid=mm.get("hid", 384), cw=mm.get("cw", 1.0), feat=mm.get("feat", 384))
    except TypeError:
        model = m.Reader(len(cs), arch=mm.get("arch", "lstm"))
    model.load_state_dict(ck["model"])
    return m, cs, model.to(dev).to(memory_format=torch.channels_last).eval()


@torch.no_grad()
def image_logprobs(m, cs, model, data_dir, split, dev):
    st = m.Store(data_dir, split)
    items = [(i, []) for i in range(len(st.keys))]
    w = m.widths_of(st, list(range(len(st.keys))))
    dl = torch.utils.data.DataLoader(m.LineSet(st, items, False), batch_sampler=m.BucketSampler(w, 60000, False),
                                     num_workers=8, collate_fn=m.collate)
    out = {}
    for x, widths, _, idx in dl:
        lo = model(x.to(dev), widths // 4).float().log_softmax(-1).cpu()
        for k, i in enumerate(idx):
            n = int(widths[k] // 4)
            out[st.keys[i]] = lo[k, :n].numpy().astype(np.float32)
    return out, {k: st.labels[i] for k, i in st.index.items()}


@torch.no_grad()
def signal_logprobs(T79, ck_path, items, dev):
    ck = torch.load(ck_path, map_location="cpu")
    cs = T79.Charset(ck["chars"])
    n_in = items[0][1].shape[1] - 1
    model = T79.SignalReader(n_in, len(cs)).to(dev).eval()
    model.load_state_dict({k: v for k, v in ck["model"].items() if not k.startswith("head2.")})
    out = {}
    for j in range(0, len(items), 64):
        b = items[j:j + 64]
        X = [torch.from_numpy(T79.prep(f, False)) for _, f in b]
        L = torch.tensor([len(x) for x in X])
        P = torch.zeros(len(X), int(L.max()), X[0].shape[1])
        for i, x in enumerate(X):
            P[i, :len(x)] = x
        lo = model(P.to(dev)).float().log_softmax(-1).cpu()
        ol = model.out_len(L)
        for i, (k, _) in enumerate(b):
            out[k] = lo[i, :int(ol[i])].numpy()
    return cs, out


def beam(lp: np.ndarray, beam_w: int = 10, prune: float = -9.0):
    """CTC prefix beam search over log-probs [T, K] (0 = blank) -> [(label ids tuple, log score)] best first."""
    NEG = -1e30
    beams = {(): (0.0, NEG)}                           # prefix -> (log p ending in blank, log p ending in non-blank)
    lse = np.logaddexp
    for t in range(lp.shape[0]):
        row = lp[t]
        cand = np.where(row > prune)[0]
        nb = defaultdict(lambda: [NEG, NEG])
        for pre, (pb, pnb) in beams.items():
            tot = lse(pb, pnb)
            for c in cand:
                p = row[c]
                if c == 0:
                    e = nb[pre]
                    e[0] = lse(e[0], tot + p)
                    continue
                last = pre[-1] if pre else None
                npre = pre + (int(c),)
                e = nb[npre]
                if c == last:
                    e[1] = lse(e[1], pb + p)
                    e2 = nb[pre]
                    e2[1] = lse(e2[1], pnb + p)
                else:
                    e[1] = lse(e[1], tot + p)
        beams = dict(sorted(((k, (v[0], v[1])) for k, v in nb.items()), key=lambda kv: -lse(*kv[1]))[:beam_w])
    return [(k, float(lse(*v))) for k, v in sorted(beams.items(), key=lambda kv: -lse(*kv[1]))]


def ctc_score(lp: np.ndarray, cs, visual: str):
    """CTC log-likelihood of one visual-order string under log-probs [T, K]; None if a character is unknown or the
    string does not fit."""
    ids = []
    for ch in visual:
        if ch not in cs.idx:
            return None
        ids.append(cs.idx[ch])
    T = lp.shape[0]
    reps = sum(1 for a, b in zip(ids, ids[1:]) if a == b)
    if not ids or T < len(ids) + reps:
        return None
    v = F.ctc_loss(torch.from_numpy(lp)[:, None, :], torch.tensor([ids]), torch.tensor([T]), torch.tensor([len(ids)]),
                   reduction="sum", zero_infinity=False).item()
    return None if not math.isfinite(v) else -v


def greedy(lp, cs):
    ids = lp.argmax(-1)
    return cs.decode(ids.tolist())


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--x77", default="/work/x77")
    ap.add_argument("--x78", default="/work/x78")
    ap.add_argument("--sig", required=True)
    ap.add_argument("--sigdata", default="/work/data3")
    ap.add_argument("--out", default="/work/out/fuse")
    ap.add_argument("--nbest", type=int, default=8)
    ap.add_argument("--reuse", default="", help="a previous --out: keep its candidates and image scores, redo the signal")
    a = ap.parse_args()
    dev = torch.device("cuda")
    Path(a.out).mkdir(parents=True, exist_ok=True)
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    import train79b as T79
    if a.reuse:
        sig_items = {}
        for f in sorted(Path(a.sigdata).glob("dev-*.npz")):
            z = np.load(f)
            meta = [json.loads(l) for l in open(str(f)[:-4] + ".jsonl", encoding="utf-8")]
            A, off = z["rreal"], z["rreal_off"]
            for i, m in enumerate(meta):
                sig_items[m["key"]] = A[off[i]:off[i + 1]]
        z = np.load(Path(a.sigdata) / "real.npz")
        for k in z.files:
            sig_items[k] = z[k]
        for split in ("dev", "test"):
            R = [json.loads(l) for l in open(Path(a.reuse) / f"{split}.jsonl", encoding="utf-8")]
            css, lps = signal_logprobs(T79, a.sig, [(r["key"], sig_items[r["key"]]) for r in R], dev)
            with open(Path(a.out) / f"{split}.jsonl", "w", encoding="utf-8") as fo:
                for r in R:
                    L = lps[r["key"]]
                    r["ssig"] = [ctc_score(L, css, T79.to_visual(c)) for c in r["cands"]]
                    r["gsig"] = T79.from_visual(css.decode(L.argmax(-1).tolist()))
                    r["Tsig"] = int(L.shape[0])
                    fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            print("done", split, len(R), flush=True)
        return
    m77, cs77, r77 = load_image_reader(a.x77, "train77", f"{a.x77}/v1.pt", dev)
    for mod in ("train77",):
        sys.modules.pop(mod, None)
    m78, cs78, r78 = load_image_reader(a.x78, "train78", f"{a.x78}/syn_then_real.pt", dev)
    to_vis, from_vis = T79.to_visual, T79.from_visual
    # signals: dev from the reconstructed dev split, test from real.npz
    sig_items = {}
    for f in sorted(Path(a.sigdata).glob("dev-*.npz")):
        z = np.load(f)
        meta = [json.loads(l) for l in open(str(f)[:-4] + ".jsonl", encoding="utf-8")]
        A, off = z["rreal"], z["rreal_off"]
        for i, m in enumerate(meta):
            sig_items[m["key"]] = A[off[i]:off[i + 1]]
    z = np.load(Path(a.sigdata) / "real.npz")
    for k in z.files:
        sig_items[k] = z[k]
    for split, ddir in (("dev", f"{a.x77}/dev"), ("test", f"{a.x77}/test")):
        lp77, labels = image_logprobs(m77, cs77, r77, ddir, split, dev)
        lp78, _ = image_logprobs(m78, cs78, r78, ddir, split, dev)
        keys = [k for k in lp77 if k in sig_items and len(sig_items[k]) >= 4]
        css, lps = signal_logprobs(T79, a.sig, [(k, sig_items[k]) for k in keys], dev)
        n = 0
        with open(Path(a.out) / f"{split}.jsonl", "w", encoding="utf-8") as fo:
            for k in keys:
                L = lp77[k]
                bs = beam(L)[:a.nbest]
                cands = []
                for ids, sc in bs:
                    v = cs77.decode(list(ids)) if False else "".join(cs77.chars[i - 1] for i in ids)
                    cands.append(v)
                g77 = cs77.decode(L.argmax(-1).tolist())
                if g77 not in cands:
                    cands.insert(0, g77)
                rec = dict(key=k, label=labels.get(k), cands=[from_vis(v) for v in cands],
                           s77=[ctc_score(L, cs77, v) for v in cands],
                           s78=[ctc_score(lp78[k], cs78, v) for v in cands] if k in lp78 else None,
                           ssig=[ctc_score(lps[k], css, v) for v in cands],
                           g77=from_vis(g77), g78=from_vis(cs78.decode(lp78[k].argmax(-1).tolist())) if k in lp78 else None,
                           gsig=from_vis(css.decode(lps[k].argmax(-1).tolist())),
                           cmin77=float(np.exp(L.max(-1)).min()), cmean77=float(np.exp(L.max(-1)).mean()),
                           T77=int(L.shape[0]), Tsig=int(lps[k].shape[0]))
                fo.write(json.dumps(rec, ensure_ascii=False) + "\n")
                n += 1
                if n % 1000 == 0:
                    print(split, n, flush=True)
        print("done", split, n, "of", len(lp77), flush=True)


if __name__ == "__main__":
    main()
