"""Experiment 79, rung 1: the signal reader (runs on the rented GPU).

    python train79.py --data /work/data --kind truth --name p2 --epochs 15
    python train79.py --data /work/data --kind recon --name p3 --epochs 15       (recon = rclean + rdmg)

Input: per-point features (sig79.features) without absolute x: 11 numbers a point.  Encoder: linear -> 3 conv1d
(width 5, one halving time) -> 3-layer BiLSTM (320 each way) -> linear CTC head over the characters of the training
labels in experiment 77's right-to-left target order (to_visual: Latin runs and numbers reversed).
Evaluates on every synthetic test signal (truth, rclean, rdmg mild/heavy, the held-out face) and on the real held-out
test lines (real.npz + real.jsonl: experiment 77's test pages; label = Azure, truth = the owner's line where known).
Writes /work/out/<name>/{model.pt, charset.json, results.json, pred_*.jsonl, train.log}.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import random
import re
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

# ---- experiment 77's right-to-left target (common77.to_visual / from_visual), duplicated
_LAT = "A-Za-zÀ-ɏ"
_DIG = "0-9٠-٩۰-۹"
_RUNS = re.compile(rf"[{_LAT}](?:[^؀-ۿ\n]*[{_LAT}{_DIG}])?|%?[{_DIG}]+(?:[.,:/\-٫٬][{_DIG}]+)*%?")
_ARABIC = re.compile("[ؠ-يٱ-ۓۺ-ۿ]")


def to_visual(s: str) -> str:
    if not _ARABIC.search(s):
        return s[::-1]
    return _RUNS.sub(lambda m: m.group()[::-1], s)


def from_visual(v: str) -> str:
    return to_visual(v[::-1])[::-1]


_PUNCT = re.compile(r"[^\w\s]|_", re.UNICODE)
_WS = re.compile(r"\s+")


def no_punct(s: str) -> str:
    s = unicodedata.normalize("NFC", s or "")
    return _WS.sub(" ", _PUNCT.sub(" ", s)).strip()


def lev(a, b) -> int:
    if len(a) < len(b):
        a, b = b, a
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


# ------------------------------------------------------------------------------------------------ data

def load_split(data: str, split: str, kinds: list[str]):
    """-> list of (features float16 [N,12], label, meta)."""
    items = []
    for f in sorted(glob.glob(f"{data}/{split}-*.npz")):
        z = np.load(f)
        meta = [json.loads(l) for l in open(f[:-4] + ".jsonl", encoding="utf-8")]
        for k in kinds:
            A, off = z[k], z[k + "_off"]
            for i, m in enumerate(meta):
                items.append((A[off[i]:off[i + 1]], m["label"], dict(m, kind=k)))
    return items


def prep(Fe: np.ndarray, train: bool, rng: random.Random | None = None) -> np.ndarray:
    """11 input numbers a point: drop absolute x; clip; light augmentation in training."""
    X = Fe[:, 1:].astype(np.float32).copy()
    if train and len(X) > 8:
        s = rng.uniform(0.9, 1.1)
        X[:, 1:3] *= s                                     # dx, dy
        X[:, 0] = X[:, 0] * rng.uniform(0.92, 1.08) + rng.uniform(-0.1, 0.1)   # y
        if rng.random() < 0.5:                             # drop a few points (keeps pen-lift rows)
            keep = (np.random.default_rng(rng.randrange(1 << 30)).random(len(X)) > rng.uniform(0, 0.1)) | (X[:, 6] == 1)
            X = X[keep]
    X[:, 0] = np.clip(X[:, 0], -4, 4)
    X[:, 1:3] = np.clip(X[:, 1:3], -3, 3)
    X[:, 5] = np.clip(X[:, 5], -math.pi, math.pi)
    return X


class Charset:
    def __init__(self, chars):
        self.chars = list(chars)
        self.idx = {c: i + 1 for i, c in enumerate(self.chars)}   # 0 = CTC blank

    def encode(self, s):
        return [self.idx[c] for c in s if c in self.idx]

    def decode(self, ids):
        out, prev = [], 0
        for i in ids:
            if i != prev and i != 0:
                out.append(self.chars[i - 1])
            prev = i
        return "".join(out)

    def __len__(self):
        return len(self.chars) + 1


class Lines(torch.utils.data.Dataset):
    def __init__(self, items, cs, train):
        self.items, self.cs, self.train = items, cs, train
        self.rng = random.Random(1)

    def __len__(self):
        return len(self.items)

    def __getitem__(self, j):
        Fe, lab, _ = self.items[j]
        X = prep(Fe, self.train, self.rng)
        return torch.from_numpy(X), torch.tensor(self.cs.encode(to_visual(lab)), dtype=torch.long), j


def collate(b):
    L = torch.tensor([x.shape[0] for x, _, _ in b])
    X = torch.zeros(len(b), int(L.max()), b[0][0].shape[1])
    for i, (x, _, _) in enumerate(b):
        X[i, :len(x)] = x
    tl = torch.tensor([len(t) for _, t, _ in b])
    T = torch.cat([t for _, t, _ in b]) if len(b) else torch.zeros(0, dtype=torch.long)
    return X, L, T, tl, [j for _, _, j in b]


def buckets(lengths, budget, shuffle, seed=0):
    order = sorted(range(len(lengths)), key=lambda i: lengths[i])
    out, cur, mx = [], [], 0
    for i in order:
        m = max(mx, lengths[i])
        if cur and m * (len(cur) + 1) > budget:
            out.append(cur)
            cur, m = [], lengths[i]
        cur.append(i)
        mx = m
    if cur:
        out.append(cur)
    if shuffle:
        random.Random(seed).shuffle(out)
    return out


# ------------------------------------------------------------------------------------------------ model

class SignalReader(nn.Module):
    def __init__(self, n_in: int, n_classes: int, d: int = 256, hid: int = 320):
        super().__init__()
        self.inp = nn.Linear(n_in, d)
        self.conv = nn.Sequential(
            nn.Conv1d(d, d, 5, padding=2), nn.BatchNorm1d(d), nn.GELU(),
            nn.Conv1d(d, d, 5, padding=2, stride=2), nn.BatchNorm1d(d), nn.GELU(),
            nn.Conv1d(d, d, 5, padding=2), nn.BatchNorm1d(d), nn.GELU(), nn.Dropout(0.1))
        self.rnn = nn.LSTM(d, hid, num_layers=3, bidirectional=True, batch_first=True, dropout=0.2)
        self.head = nn.Linear(2 * hid, n_classes)

    def out_len(self, L):
        return (L + 1) // 2

    def forward(self, x):
        h = self.inp(x).transpose(1, 2)
        h = self.conv(h).transpose(1, 2)
        h, _ = self.rnn(h)
        return self.head(h)


# ------------------------------------------------------------------------------------------------ train / eval

def evaluate(model, items, cs, dev, budget, out_file=None, extra_ref=None):
    model.eval()
    lens = [len(x[0]) for x in items]
    errs = defaultdict(lambda: [0, 0])
    rows = []
    with torch.no_grad():
        for b in buckets(lens, budget, False):
            batch = [Lines(items, cs, False)[j] for j in b]
            X, L, _, _, idx = collate(batch)
            X = X.to(dev)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                lo = model(X)
            ids = lo.float().argmax(-1).cpu().numpy()
            ol = model.out_len(L).numpy()
            for r, j in enumerate(idx):
                pred = from_visual(cs.decode(ids[r][:ol[r]]))
                Fe, lab, meta = items[j]
                rec = dict(meta, pred=pred)
                for name, ref in (("label", lab), ("truth", meta.get("truth"))):
                    if not ref:
                        continue
                    a, bb = no_punct(pred), no_punct(ref)
                    e = lev(a, bb)
                    errs[name][0] += e
                    errs[name][1] += max(1, len(bb))
                    rec[f"cer_{name}"] = round(e / max(1, len(bb)), 4)
                rows.append(rec)
    if out_file:
        with open(out_file, "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")
    model.train()
    return {k: round(100 * e / max(1, n), 2) for k, (e, n) in errs.items()}, rows


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/work/data")
    ap.add_argument("--kind", default="truth", choices=["truth", "recon", "all"])
    ap.add_argument("--name", default="p2")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--budget", type=int, default=120000)   # padded points per batch
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    torch.manual_seed(79)
    dev = torch.device("cuda")
    od = Path("/work/out") / a.name
    od.mkdir(parents=True, exist_ok=True)
    log = open(od / "train.log", "a")

    def P(*s):
        msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in s)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    kinds = {"truth": ["truth"], "recon": ["rclean", "rdmg"], "all": ["truth", "rclean", "rdmg"]}[a.kind]
    tr = load_split(a.data, "train", kinds)
    if a.limit:
        tr = tr[:a.limit]
    cnt = Counter()
    for _, lab, _ in tr:
        cnt.update(to_visual(lab))
    cs = Charset(sorted(c for c, n in cnt.items() if n >= 20))
    (od / "charset.json").write_text(json.dumps(cs.chars, ensure_ascii=False))
    # CTC feasibility
    keep = []
    for it in tr:
        t = cs.encode(to_visual(it[1]))
        reps = sum(1 for x, y in zip(t, t[1:]) if x == y)
        if len(t) and (len(it[0]) + 1) // 2 >= len(t) + reps + 1:
            keep.append(it)
    P(f"train {len(keep)} of {len(tr)} signals ({kinds}); charset {len(cs)}")
    tr = keep
    tests = {}
    te = load_split(a.data, "test", ["truth", "rclean", "rdmg"])
    for k in ("truth", "rclean"):
        tests[f"syn_{k}"] = [x for x in te if x[2]["kind"] == k]
    for lv in ("mild", "heavy"):
        tests[f"syn_rdmg_{lv}"] = [x for x in te if x[2]["kind"] == "rdmg" and x[2]["level"] == lv]
    tf = load_split(a.data, "testfont", ["truth", "rclean"])
    for k in ("truth", "rclean"):
        tests[f"font_{k}"] = [x for x in tf if x[2]["kind"] == k]
    real = []
    if Path(a.data, "real.npz").exists():
        z = np.load(Path(a.data, "real.npz"))
        for l in open(Path(a.data, "real.jsonl"), encoding="utf-8"):
            m = json.loads(l)
            if m["key"] in z.files and len(z[m["key"]]) >= 4:
                real.append((z[m["key"]], m["label"], dict(m, kind="real")))
    tests["real"] = real
    P({k: len(v) for k, v in tests.items()})

    model = SignalReader(11, len(cs)).to(dev)
    P(f"parameters {sum(p.numel() for p in model.parameters()) / 1e6:.2f} M")
    lens = [len(x[0]) for x in tr]
    steps = len(buckets(lens, a.budget, False)) * a.epochs
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.05)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    ds = Lines(tr, cs, True)
    step = 0
    t0 = time.time()
    small = {k: v[:600] for k, v in tests.items() if k in ("syn_truth", "syn_rclean")}
    for ep in range(a.epochs):
        bl = buckets(lens, a.budget, True, seed=ep)
        dl = torch.utils.data.DataLoader(ds, batch_sampler=bl, num_workers=a.workers, collate_fn=collate,
                                         pin_memory=True, persistent_workers=False)
        tot, n = 0.0, 0
        for X, L, T, tl, _ in dl:
            X = X.to(dev, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.bfloat16):
                lo = model(X)
            lp = lo.float().log_softmax(-1).transpose(0, 1)
            loss = ctc(lp, T, model.out_len(L), tl)
            opt.zero_grad(set_to_none=True)
            loss.backward()
            nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            opt.step()
            sched.step()
            step += 1
            tot += loss.item()
            n += 1
            if step % 200 == 0:
                P(f"ep {ep} step {step}/{steps} loss {tot / n:.3f} {time.time() - t0:.0f}s")
        r = {k: evaluate(model, v, cs, dev, a.budget)[0] for k, v in small.items()}
        P(f"epoch {ep} done loss {tot / max(1, n):.3f} quick CER {r}")
        torch.save(dict(model=model.state_dict(), chars=cs.chars), od / "model.pt")
    res = {}
    for k, v in tests.items():
        if v:
            res[k], _ = evaluate(model, v, cs, dev, a.budget, out_file=od / f"pred_{k}.jsonl")
    res["minutes"] = round((time.time() - t0) / 60, 1)
    res["train_signals"] = len(tr)
    (od / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    P("RESULTS", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
