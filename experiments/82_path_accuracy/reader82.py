"""Experiment 82 (downstream check): a frozen copy of experiment 79's train79b.py (2026-11-05) with two more input
kinds: "learned" = the learned rebuilder's paths (lclean + ldmg, learn82.py feats) against "recon" = the rule rebuilder's
(rclean + rdmg, the skeleton), on the same lines, and test sets per kind and damage level (incl. the new "fill").

Experiment 79's original doc follows.

Experiment 79, rung 1: the signal reader (runs on the rented GPU).  (train79b.py = this + --train-split, --charset,
--init, --data-train for round 2: pretraining on Calliar, then fine-tuning; the runs of round 1 used train79.py.)

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
import os
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


# bf16 autocast made the BiLSTM 13x slower on the RTX 5090 (1.16 vs 14.7 steps/s, prof79.py, 2026-11-04): fp32 + TF32
AMP = False
# torch saw 256 CPUs in a container limited to ~61 (cgroup cpu.max): the main process's small CPU ops oversubscribed
# and training ran at 2 steps/s; a few intra-op threads are enough (the data workers do the CPU work)
torch.set_num_threads(4)
torch.backends.cuda.matmul.allow_tf32 = True
torch.backends.cudnn.allow_tf32 = True
NO_THICK = False      # --no-thick: thickness and blob (inputs 10, 11) zeroed: the comparison for the owner's filled heads


def prep(Fe: np.ndarray, train: bool, rng: random.Random | None = None) -> np.ndarray:
    """Input numbers a point: drop absolute x; clip; light augmentation in training."""
    X = Fe[:, 1:].astype(np.float32).copy()
    if NO_THICK and X.shape[1] >= 12:
        X[:, 10:12] = 0
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

    def forward(self, x, both: bool = False):
        h = self.inp(x).transpose(1, 2)
        h = self.conv(h).transpose(1, 2)
        h, _ = self.rnn(h)
        if both:
            return self.head(h), (self.head2(h) if hasattr(self, "head2") else None)
        return self.head(h)


# The rasm: the dotless body of each letter (about 16 shapes); the dots tell the letters of one body apart.  An
# auxiliary CTC head reads the body sequence (the movement's own business) beside the letter head.
RASM = {**{c: "ا" for c in "اأإآٱ"}, **{c: "ٮ" for c in "بتثنيىئ"}, **{c: "ح" for c in "جحخ"}, **{c: "د" for c in "دذ"},
        **{c: "ر" for c in "رز"}, **{c: "س" for c in "سش"}, **{c: "ص" for c in "صض"}, **{c: "ط" for c in "طظ"},
        **{c: "ع" for c in "عغ"}, **{c: "ڡ" for c in "فق"}, **{c: "ه" for c in "هة"}, **{c: "و" for c in "وؤ"}}


def rasm_of(s: str) -> str:
    return "".join(RASM.get(c, c) for c in s)


def partial_init(model, path, P):
    """Load a checkpoint into a model whose input layer may be wider (new features): matching tensors are copied;
    the old input weights go into the first columns, the new features' columns start at zero."""
    old = torch.load(path, map_location="cpu")["model"]
    own = model.state_dict()
    n = 0
    for k, v in old.items():
        if k not in own:
            continue
        if own[k].shape == v.shape:
            own[k] = v
            n += 1
        elif k == "inp.weight" and own[k].shape[0] == v.shape[0] and own[k].shape[1] > v.shape[1]:
            w = torch.zeros_like(own[k])
            w[:, :v.shape[1]] = v
            own[k] = w
            n += 1
    model.load_state_dict(own)
    P(f"initialised {n} tensors from {path}")


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
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=AMP):
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


LOOP = "وفقمهةصضطظعغ"


def loop_confusions(model, items, cs, dev, budget):
    """Per loop letter: occurrences in the labels, how often the reader got it wrong (substituted or deleted, by an
    alignment of the label and the reading), and what it was read as most often."""
    from rapidfuzz.distance import Levenshtein
    _, rows = evaluate(model, items, cs, dev, budget)
    occ, wrong, as_ = Counter(), Counter(), defaultdict(Counter)
    for r in rows:
        a, b = r["label"], r["pred"]
        for ch in a:
            if ch in LOOP:
                occ[ch] += 1
        for op in Levenshtein.editops(a, b):
            if op.tag in ("replace", "delete") and a[op.src_pos] in LOOP:
                wrong[a[op.src_pos]] += 1
                as_[a[op.src_pos]][b[op.dest_pos] if op.tag == "replace" else "∅"] += 1
    return {ch: dict(n=occ[ch], err=round(wrong[ch] / max(1, occ[ch]), 3), top=as_[ch].most_common(3)) for ch in LOOP if occ[ch]}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="/work/data")
    ap.add_argument("--kind", default="truth", choices=["truth", "recon", "all", "real", "learned"])
    ap.add_argument("--extra-train", default="", help="DIR:SPLIT:KIND1,KIND2:N - mix N more training signals in")
    ap.add_argument("--name", default="p2")
    ap.add_argument("--epochs", type=int, default=15)
    ap.add_argument("--lr", type=float, default=1e-3)
    ap.add_argument("--budget", type=int, default=120000)   # padded points per batch
    ap.add_argument("--workers", type=int, default=8)
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--train-split", default="train")
    ap.add_argument("--data-train", default="", help="read the training split from here (default --data)")
    ap.add_argument("--charset", default="", help="a charset.json to use instead of the training labels' own")
    ap.add_argument("--init", default="", help="start from this model.pt (same charset)")
    ap.add_argument("--no-thick", action="store_true")
    ap.add_argument("--rasm", type=float, default=0.0, help="weight of the auxiliary rasm (letter body) CTC head")
    ap.add_argument("--skip-real", action="store_true")
    a = ap.parse_args()
    global NO_THICK
    NO_THICK = a.no_thick
    torch.manual_seed(79)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    od = Path(os.environ.get("OUT82", "/work/out")) / a.name
    od.mkdir(parents=True, exist_ok=True)
    log = open(od / "train.log", "a")

    def P(*s):
        msg = time.strftime("%H:%M:%S ") + " ".join(str(x) for x in s)
        print(msg, flush=True)
        log.write(msg + "\n")
        log.flush()

    kinds = {"truth": ["truth"], "recon": ["rclean", "rdmg"], "all": ["truth", "rclean", "rdmg"], "real": ["rreal"],
             "learned": ["lclean", "ldmg"]}[a.kind]
    tr = load_split(a.data_train or a.data, a.train_split, kinds)
    if a.extra_train:
        d_, sp_, k_, n_ = a.extra_train.split(":")
        ex = load_split(d_, sp_, k_.split(","))
        random.Random(5).shuffle(ex)
        tr += ex[:int(n_)]
    if a.limit:
        tr = tr[:a.limit]
    cnt = Counter()
    for _, lab, _ in tr:
        cnt.update(to_visual(lab))
    cs = Charset(json.loads(Path(a.charset).read_text()) if a.charset else sorted(c for c, n in cnt.items() if n >= 20))
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
    tk = ["lclean", "ldmg"] if a.kind == "learned" else ["rclean", "rdmg"]
    te = load_split(a.data, "test", tk)
    tests[f"syn_{tk[0]}"] = [x for x in te if x[2]["kind"] == tk[0]]
    for lv in ("clean", "mild", "heavy", "spread", "fill"):
        tests[f"syn_{tk[1]}_{lv}"] = [x for x in te if x[2]["kind"] == tk[1] and x[2]["level"] == lv]
    for src in ("font", "traced"):
        tests[f"syn_{tk[1]}_src_{src}"] = [x for x in te if x[2]["kind"] == tk[1] and x[2].get("src") == src]
    real = []
    if Path(a.data, "real.npz").exists() and not a.skip_real:
        z = np.load(Path(a.data, "real.npz"))
        for l in open(Path(a.data, "real.jsonl"), encoding="utf-8"):
            m = json.loads(l)
            if m["key"] in z.files and len(z[m["key"]]) >= 4:
                real.append((z[m["key"]], m["label"], dict(m, kind="real")))
    tests["real"] = real
    dv = load_split(a.data, "dev", ["rreal"]) if glob.glob(f"{a.data}/dev-*.npz") else []
    if dv:
        tests["dev_real"] = dv
    P({k: len(v) for k, v in tests.items()})

    n_in = tr[0][0].shape[1] - 1
    model = SignalReader(n_in, len(cs)).to(dev)
    P(f"inputs per point {n_in}; no_thick {NO_THICK}")
    if a.init:
        partial_init(model, a.init, P)
    cs2 = None
    if a.rasm > 0:
        c2 = Counter()
        for _, lab, _ in tr:
            c2.update(rasm_of(to_visual(lab)))
        cs2 = Charset(sorted(c for c, n in c2.items() if n >= 20))
        model.head2 = nn.Linear(model.head.in_features, len(cs2))
        model.to(dev)
        (od / "charset_rasm.json").write_text(json.dumps(cs2.chars, ensure_ascii=False))
        P(f"rasm head: {len(cs2)} classes, weight {a.rasm}")
    P(f"parameters {sum(p.numel() for p in model.parameters()) / 1e6:.2f} M")
    lens = [len(x[0]) for x in tr]
    steps = len(buckets(lens, a.budget, False)) * a.epochs
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=steps, pct_start=0.05)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    ds = Lines(tr, cs, True)
    step = 0
    t0 = time.time()
    small = {k: v[:600] for k, v in tests.items() if k in (f"syn_{tk[0]}", f"syn_{tk[1]}_heavy")}
    for ep in range(a.epochs):
        bl = buckets(lens, a.budget, True, seed=ep)
        dl = torch.utils.data.DataLoader(ds, batch_sampler=bl, num_workers=a.workers, collate_fn=collate,
                                         pin_memory=True, persistent_workers=False)
        tot, n = 0.0, 0
        for X, L, T, tl, idx in dl:
            X = X.to(dev, non_blocking=True)
            with torch.autocast("cuda", dtype=torch.bfloat16, enabled=AMP):
                lo, la = model(X, both=True)
            lp = lo.float().log_softmax(-1).transpose(0, 1)
            loss = ctc(lp, T, model.out_len(L), tl)
            if cs2 is not None:
                t2 = [torch.tensor(cs2.encode(rasm_of(to_visual(tr[j][1]))), dtype=torch.long) for j in idx]
                loss = loss + a.rasm * ctc(la.float().log_softmax(-1).transpose(0, 1), torch.cat(t2),
                                           model.out_len(L), torch.tensor([len(t) for t in t2]))
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
    res["loop_letters"] = {k: loop_confusions(model, v, cs, dev, a.budget) for k, v in tests.items()
                           if v and k.startswith(("syn_", "font_")) and "_src_" not in k}
    res["minutes"] = round((time.time() - t0) / 60, 1)
    res["train_signals"] = len(tr)
    (od / "results.json").write_text(json.dumps(res, indent=1, ensure_ascii=False))
    P("RESULTS", json.dumps(res, ensure_ascii=False))


if __name__ == "__main__":
    main()
