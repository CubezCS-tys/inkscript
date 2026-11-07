"""Experiment 78: experiment 77's train77.py (copied 2026-11-04 16:30 CST, the version of its v1 run), unchanged except
two additions and one guard, so the arms compare (the guard: OneCycleLR is not stepped past its last step, which
ended the synthetic run with an error in its final batch; experiment 77 has the same edge case):
  --init CKPT    start from a checkpoint (synthetic-then-real): its charset is kept, characters new in the real
                 labels (>= min_char) are appended and their head rows start from zero; everything else is loaded.
  --realdev DIR  also score experiment 77's real dev lines after every epoch (logged as "realdev"; never used to
                 pick best.pt, which stays on the --data dev split).
Experiment 77's header follows.

Experiment 77: our own Arabic line reader, trained from scratch (no pretrained weight anywhere).

A line image (grey, height 48, flipped left-right so the network reads in Arabic logical order) -> CNN -> 2-layer
BiLSTM -> CTC over Unicode code points.  The target is the line in "visual right-to-left" order (common77.to_visual:
left-to-right runs reversed); decoding maps back with from_visual.  Runs on the rented GPU (torch, numpy, cv2 only).

    python train77.py train  --data D --out O [--labels L.jsonl] [--epochs N] [--minutes M]
    python train77.py infer  --ckpt O/best.pt --data D --split NAME --pred P.jsonl

D holds tar shards (<key>.jpg, <key>.txt) and manifest-*.jsonl.  --labels overrides/drops training labels
(key -> label, or label null = drop) for v2.
"""
from __future__ import annotations

import argparse
import glob
import json
import math
import os
import random
import re
import tarfile
import time
import unicodedata
from collections import Counter

import cv2
import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F

torch.multiprocessing.set_sharing_strategy("file_system")

H = 48

# --------------------------------------------------------------------------------------------- RTL (= common77)
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


# --------------------------------------------------------------------------------------------- data

class Store:
    """All crops of a split in one uint8 buffer (shared by DataLoader workers without copies)."""

    def __init__(self, data_dir: str, split: str):
        keys, offs, blobs, labels = [], [0], [], {}
        for f in sorted(glob.glob(os.path.join(data_dir, f"{split}-*.tar"))):
            with tarfile.open(f) as t:
                for m in t:
                    b = t.extractfile(m).read()
                    k, ext = m.name.rsplit(".", 1)
                    if ext == "jpg":
                        keys.append(k)
                        blobs.append(np.frombuffer(b, np.uint8))
                        offs.append(offs[-1] + len(b))
                    else:
                        labels[k] = b.decode("utf-8")
        self.keys = keys
        self.offs = np.array(offs, dtype=np.int64)
        self.buf = np.concatenate(blobs) if blobs else np.zeros(0, np.uint8)
        self.labels = [labels.get(k, "") for k in keys]
        self.index = {k: i for i, k in enumerate(keys)}
        self.widths = None

    def image(self, i: int) -> np.ndarray:
        return cv2.imdecode(self.buf[self.offs[i]:self.offs[i + 1]], cv2.IMREAD_GRAYSCALE)


class Charset:
    def __init__(self, chars: list[str]):
        self.chars = chars                       # index 0 = CTC blank
        self.idx = {c: i + 1 for i, c in enumerate(chars)}

    def encode(self, s: str):
        return [self.idx[c] for c in s]

    def decode(self, ids) -> str:
        out, prev = [], 0
        for i in ids:
            if i != prev and i != 0:
                out.append(self.chars[i - 1])
            prev = i
        return "".join(out)

    def __len__(self):
        return len(self.chars) + 1


def augment(img: np.ndarray, rng: random.Random) -> np.ndarray:
    h, w = img.shape
    # width jitter 0.85-1.15, small shear-free vertical shift, contrast/brightness, blur or noise sometimes
    sw = rng.uniform(0.85, 1.15)
    img = cv2.resize(img, (max(8, int(w * sw)), h), interpolation=cv2.INTER_LINEAR)
    if rng.random() < 0.5:
        dy = rng.randint(-3, 3)
        M = np.float32([[1, 0, 0], [0, 1, dy]])
        img = cv2.warpAffine(img, M, (img.shape[1], h), borderValue=255)
    if rng.random() < 0.3:
        img = cv2.GaussianBlur(img, (3, 3), rng.uniform(0.3, 1.0))
    f = img.astype(np.float32)
    if rng.random() < 0.7:
        lo, hi = rng.uniform(0, 60), rng.uniform(190, 255)
        f = lo + f * (hi - lo) / 255.0
    if rng.random() < 0.3:
        f += np.random.default_rng(rng.randint(0, 1 << 30)).normal(0, rng.uniform(2, 12), f.shape)
    return np.clip(f, 0, 255).astype(np.uint8)


class LineSet(torch.utils.data.Dataset):
    def __init__(self, store: Store, items: list[tuple[int, list[int]]], train: bool):
        self.s, self.items, self.train = store, items, train

    def __len__(self):
        return len(self.items)

    def __getitem__(self, j):
        i, tgt = self.items[j]
        img = self.s.image(i)
        if self.train:
            img = augment(img, random.Random(j * 7919 + int(time.time() * 1000) % 100000))
        img = img[:, ::-1]                       # flip: the network reads from the line's right end
        return np.ascontiguousarray(img), tgt, i


def collate(batch):
    W = max(b[0].shape[1] for b in batch)
    W = int(math.ceil(W / 8) * 8)
    x = np.full((len(batch), 1, H, W), 255, np.uint8)
    for k, (img, _, _) in enumerate(batch):
        x[k, 0, :, :img.shape[1]] = img
    x = torch.from_numpy(x).float().div_(255.0).sub_(0.5).div_(0.5).neg_()   # ink -> positive
    widths = torch.tensor([b[0].shape[1] for b in batch])
    tl = torch.tensor([len(b[1]) for b in batch], dtype=torch.long)
    tg = torch.tensor([c for b in batch for c in b[1]], dtype=torch.long)      # one tensor: one fd per batch
    return x, widths, (tg, tl), [b[2] for b in batch]


class BucketSampler(torch.utils.data.Sampler):
    """Batches of similar width; at most `budget` padded pixels-columns per batch."""

    def __init__(self, widths: list[int], budget: int, shuffle: bool, seed: int = 0):
        self.w, self.budget, self.shuffle, self.seed, self.epoch = widths, budget, shuffle, seed, 0

    def batches(self):
        rng = random.Random(self.seed + self.epoch)
        order = sorted(range(len(self.w)), key=lambda i: (self.w[i] + (rng.random() * 40 if self.shuffle else 0)))
        out, cur, mx = [], [], 0
        for i in order:
            m = max(mx, self.w[i])
            if cur and m * (len(cur) + 1) > self.budget:
                out.append(cur)
                cur, m = [], self.w[i]
            cur.append(i)
            mx = m
        if cur:
            out.append(cur)
        if self.shuffle:
            rng.shuffle(out)
        return out

    def __iter__(self):
        b = self.batches()
        self.epoch += 1
        return iter(b)

    def __len__(self):
        return len(self.batches())


# --------------------------------------------------------------------------------------------- model

def cbr(i, o, k=3, s=1, p=1):
    return nn.Sequential(nn.Conv2d(i, o, k, s, p, bias=False), nn.BatchNorm2d(o), nn.ReLU(inplace=True))


class Res(nn.Module):
    def __init__(self, c):
        super().__init__()
        self.a, self.b = cbr(c, c), nn.Sequential(nn.Conv2d(c, c, 3, 1, 1, bias=False), nn.BatchNorm2d(c))

    def forward(self, x):
        return F.relu(x + self.b(self.a(x)))


class Reader(nn.Module):
    """CNN (48 x W -> 1 x W/4, 384 channels; channels-last) + sequence model + linear CTC head.
    arch "tf": 4 pre-norm transformer encoder layers (d 384, 6 heads, FF 1536) after a depthwise positional conv;
    arch "lstm" (the default, the classic CRNN): 2-layer BiLSTM (384 each way).
    Measured on a healthy RTX 5090, 140 lines of width 704 per step: lstm 2,560 lines/s (8.3 M parameters),
    tf 2,930 lines/s (9.4 M).  (A first, power-capped 5090 ran both at ~450-520 lines/s: it was destroyed.)"""

    def __init__(self, n_classes: int, hid: int = 384, arch: str = "lstm", layers: int = 4):
        super().__init__()
        self.arch = arch
        self.cnn = nn.Sequential(
            cbr(1, 32), nn.MaxPool2d(2, 2),                     # 24 x W/2
            cbr(32, 64), nn.MaxPool2d(2, 2),                    # 12 x W/4
            cbr(64, 128), Res(128), nn.MaxPool2d((2, 1)),       # 6 x W/4
            cbr(128, 256), Res(256), nn.MaxPool2d((2, 1)),      # 3 x W/4
            cbr(256, 384, k=(3, 1), p=0),                       # 1 x W/4
            nn.Dropout(0.1))
        if arch == "lstm":
            self.rnn = nn.LSTM(384, hid, num_layers=2, bidirectional=True, batch_first=True, dropout=0.2)
            self.head = nn.Linear(2 * hid, n_classes)
        else:
            self.pos = nn.Conv1d(384, 384, 7, padding=3, groups=384)
            el = nn.TransformerEncoderLayer(384, 6, 1536, dropout=0.1, activation="gelu", batch_first=True, norm_first=True)
            self.enc = nn.TransformerEncoder(el, layers, enable_nested_tensor=False)
            self.norm = nn.LayerNorm(384)
            self.head = nn.Linear(384, n_classes)

    def forward(self, x, frames=None):
        f = self.cnn(x.contiguous(memory_format=torch.channels_last)).squeeze(2).transpose(1, 2)   # B, T, C
        if self.arch == "lstm":
            f, _ = self.rnn(f)
            return self.head(f)
        f = f + self.pos(f.transpose(1, 2)).transpose(1, 2)
        mask = None
        if frames is not None:
            mask = torch.arange(f.shape[1], device=f.device)[None, :] >= frames.to(f.device)[:, None]
        f = self.enc(f, src_key_padding_mask=mask)
        return self.head(self.norm(f))                        # B, T, K


# --------------------------------------------------------------------------------------------- train

def cer(a: str, b: str) -> int:
    # Levenshtein (small strings)
    if a == b:
        return 0
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def build_items(store: Store, cs: Charset, overrides: dict | None, stats: Counter):
    items = []
    for i, k in enumerate(store.keys):
        lab = store.labels[i]
        if overrides is not None and k in overrides:
            lab = overrides[k]
            stats["override"] += 1
            if lab is None:
                stats["dropped_by_labels"] += 1
                continue
        lab = unicodedata.normalize("NFC", lab)
        v = to_visual(lab)
        if any(c not in cs.idx for c in v):
            stats["rare_char"] += 1
            continue
        items.append((i, cs.encode(v)))
    return items, None


def widths_of(store: Store, idx: list[int]) -> list[int]:
    out = []
    for i in idx:
        b = store.buf[store.offs[i]:store.offs[i + 1]].tobytes()
        # JPEG SOF0/SOF2 marker: height (2 bytes), width (2 bytes)
        j, w = 2, None
        while j < len(b) - 9:
            if b[j] != 0xFF:
                j += 1
                continue
            m = b[j + 1]
            if m in (0xC0, 0xC1, 0xC2):
                w = (b[j + 7] << 8) | b[j + 8]
                break
            ln = (b[j + 2] << 8) | b[j + 3]
            j += 2 + ln
        out.append(w or store.image(i).shape[1])
    return out


def greedy(logits: torch.Tensor, lens: torch.Tensor, cs: Charset):
    p = logits.float().softmax(-1)
    conf, ids = p.max(-1)
    out = []
    for k in range(ids.shape[0]):
        n = int(lens[k])
        s = cs.decode(ids[k, :n].tolist())
        c = conf[k, :n]
        out.append((from_visual(s), float(c.min()) if n else 0.0, float(c.mean()) if n else 0.0))
    return out


def train(a):
    torch.manual_seed(77)
    random.seed(77)
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    os.makedirs(a.out, exist_ok=True)
    log = open(os.path.join(a.out, "train_log.jsonl"), "a")
    t0 = time.time()
    tr = Store(a.data, "train")
    dv = Store(a.data, "dev")
    if a.limit:
        dv.keys, dv.labels = dv.keys[:a.limit], dv.labels[:a.limit]
    print(f"loaded {len(tr.keys)} train, {len(dv.keys)} dev lines, {tr.buf.nbytes / 1e9:.2f} GB, {time.time() - t0:.0f}s",
          flush=True)
    overrides = None
    if a.labels:
        overrides = {}
        for l in open(a.labels, encoding="utf-8"):
            d = json.loads(l)
            overrides[d["key"]] = d["label"]
    cnt = Counter()
    for lab in tr.labels:
        cnt.update(to_visual(unicodedata.normalize("NFC", lab)))
    if overrides:
        for lab in overrides.values():
            if lab:
                cnt.update(to_visual(unicodedata.normalize("NFC", lab)))
    chars = sorted(c for c, n in cnt.items() if n >= a.min_char)
    init = None
    if a.init:
        init = torch.load(a.init, map_location="cpu", weights_only=False)
        old = init["meta"]["chars"]
        chars = old + [c for c in chars if c not in set(old)]
        print(f"init from {a.init}: {len(old)} chars kept, {len(chars) - len(old)} new", flush=True)
    cs = Charset(chars)
    stats = Counter()
    items, _ = build_items(tr, cs, overrides, stats)
    tw = widths_of(tr, [i for i, _ in items])
    # CTC feasibility: T = W/4 frames must cover the target plus one blank per repeated pair
    keep = []
    for (i, t), w in zip(items, tw):
        reps = sum(1 for x, y in zip(t, t[1:]) if x == y)
        if (w // 4) >= len(t) + reps + 1 and len(t) > 0:
            keep.append(((i, t), w))
        else:
            stats["too_dense"] += 1
    items, tw = [k for k, _ in keep], [w for _, w in keep]
    if a.limit:
        items, tw = items[:a.limit], tw[:a.limit]
    dstats = Counter()
    ditems, _ = build_items(dv, cs, None, dstats)
    dw = widths_of(dv, [i for i, _ in ditems])
    print(f"charset {len(cs)} classes; train items {len(items)}; {dict(stats)}; dev {len(ditems)}", flush=True)
    model = Reader(len(cs), arch=a.arch).to(dev).to(memory_format=torch.channels_last)
    if init is not None:
        assert init["meta"].get("arch", "lstm") == a.arch
        sd = init["model"]
        n_old = sd["head.weight"].shape[0]
        own = model.state_dict()
        for k, v in sd.items():
            if k.startswith("head."):
                own[k][:n_old] = v
            else:
                own[k] = v
        model.load_state_dict(own)
    rdv = rddl = None
    if a.realdev:
        rdv = Store(a.realdev, "dev")
        rdi, _ = build_items(rdv, cs, None, Counter())
        rddl = torch.utils.data.DataLoader(LineSet(rdv, rdi, False),
                                           batch_sampler=BucketSampler(widths_of(rdv, [i for i, _ in rdi]), a.budget, False),
                                           num_workers=min(4, a.workers), collate_fn=collate)
    npar = sum(p.numel() for p in model.parameters())
    print(f"parameters {npar / 1e6:.2f} M", flush=True)
    samp = BucketSampler(tw, a.budget, True)
    dl = torch.utils.data.DataLoader(LineSet(tr, items, True), batch_sampler=samp, num_workers=a.workers,
                                     collate_fn=collate, pin_memory=dev.type == "cuda", persistent_workers=a.workers > 0)
    ddl = torch.utils.data.DataLoader(LineSet(dv, ditems, False), batch_sampler=BucketSampler(dw, a.budget, False),
                                      num_workers=min(4, a.workers), collate_fn=collate)
    steps_per_epoch = len(samp)
    total = steps_per_epoch * a.epochs
    opt = torch.optim.AdamW(model.parameters(), lr=a.lr, weight_decay=0.01)
    sched = torch.optim.lr_scheduler.OneCycleLR(opt, max_lr=a.lr, total_steps=total, pct_start=0.05,
                                                anneal_strategy="cos", div_factor=20, final_div_factor=200)
    ctc = nn.CTCLoss(blank=0, zero_infinity=True)
    scaler = torch.amp.GradScaler("cuda", enabled=dev.type == "cuda")
    meta = dict(chars=chars, H=H, hid=384, arch=a.arch, params=npar, stats=dict(stats), items=len(items), args=vars(a))
    best = 1e9
    step = 0
    deadline = t0 + a.minutes * 60 if a.minutes else None
    for ep in range(a.epochs):
        model.train()
        te, tl, tn, seen = time.time(), 0.0, 0, 0
        for x, widths, tg, _ in dl:
            x = x.to(dev, non_blocking=True)
            with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                lo = model(x, widths // 4)
            lp = lo.float().log_softmax(-1).transpose(0, 1)       # T, B, K
            il = torch.clamp(widths // 4, max=lp.shape[0])
            loss = ctc(lp, tg[0], il, tg[1])
            opt.zero_grad(set_to_none=True)
            scaler.scale(loss).backward()
            scaler.unscale_(opt)
            nn.utils.clip_grad_norm_(model.parameters(), 5.0)
            scaler.step(opt)
            scaler.update()
            if step < total - 1:                     # exp 78: the bucket sampler can give one batch more than counted
                sched.step()
            step += 1
            tl += float(loss.detach()) * x.shape[0]
            tn += x.shape[0]
            seen += x.shape[0]
            if step % 200 == 0:
                el = time.time() - te
                print(f"ep {ep} step {step}/{total} loss {tl / tn:.4f} {seen / el:.0f} lines/s lr {sched.get_last_lr()[0]:.2e}",
                      flush=True)
                log.write(json.dumps(dict(ep=ep, step=step, loss=tl / tn, lps=seen / el, t=time.time() - t0)) + "\n")
                log.flush()
                tl, tn = 0.0, 0
            if deadline and time.time() > deadline:
                break
        r = evaluate(model, ddl, dv, cs, dev)
        if rddl is not None:
            r["realdev"] = evaluate(model, rddl, rdv, cs, dev)
        r.update(ep=ep, step=step, epoch_s=round(time.time() - te), t=round(time.time() - t0))
        print("DEV", json.dumps(r), flush=True)
        log.write(json.dumps(dict(dev=r)) + "\n")
        log.flush()
        ck = dict(model=model.state_dict(), meta=meta, dev=r)
        torch.save(ck, os.path.join(a.out, "last.pt"))
        if r["cer"] < best:
            best = r["cer"]
            torch.save(ck, os.path.join(a.out, "best.pt"))
        if deadline and time.time() > deadline:
            print("time limit reached", flush=True)
            break
    print("done", flush=True)


@torch.no_grad()
def evaluate(model, ddl, store, cs, dev, limit=None):
    model.eval()
    e = n = le = ln = 0
    for x, widths, tg, idx in ddl:
        with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
            lo = model(x.to(dev), widths // 4)
        for (s, _, _), i in zip(greedy(lo, widths // 4, cs), idx):
            ref = unicodedata.normalize("NFC", store.labels[i])
            e += cer(s, ref)
            n += len(ref)
            le += s != ref
            ln += 1
    model.train()
    return dict(cer=e / max(1, n), line_err=le / max(1, ln), lines=ln)


@torch.no_grad()
def infer(a):
    dev = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    ck = torch.load(a.ckpt, map_location="cpu", weights_only=False)
    cs = Charset(ck["meta"]["chars"])
    model = Reader(len(cs), arch=ck["meta"].get("arch", "lstm")).to(dev).to(memory_format=torch.channels_last)
    model.load_state_dict(ck["model"])
    model.eval()
    st = Store(a.data, a.split)
    items = [(i, []) for i in range(len(st.keys))]
    w = widths_of(st, list(range(len(st.keys))))
    dl = torch.utils.data.DataLoader(LineSet(st, items, False), batch_sampler=BucketSampler(w, a.budget, False),
                                     num_workers=a.workers, collate_fn=collate)
    if dev.type == "cuda":
        torch.cuda.synchronize()
    t0 = time.time()
    n = 0
    with open(a.pred, "w", encoding="utf-8") as f:
        for x, widths, _, idx in dl:
            with torch.autocast(dev.type, dtype=torch.float16, enabled=dev.type == "cuda"):
                lo = model(x.to(dev), widths // 4)
            for (s, cmin, cmean), i in zip(greedy(lo, widths // 4, cs), idx):
                f.write(json.dumps(dict(key=st.keys[i], pred=s, cmin=round(cmin, 4), cmean=round(cmean, 4)),
                                   ensure_ascii=False) + "\n")
                n += 1
    el = time.time() - t0
    info = dict(split=a.split, lines=n, seconds=round(el, 2), lines_per_s=round(n / el, 1), device=str(dev),
                gpu=torch.cuda.get_device_name(0) if dev.type == "cuda" else "cpu",
                params=ck["meta"]["params"])
    print(json.dumps(info), flush=True)
    with open(a.pred + ".info.json", "w") as f:
        json.dump(info, f)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("cmd")
    p.add_argument("--data")
    p.add_argument("--out")
    p.add_argument("--labels")
    p.add_argument("--epochs", type=int, default=10)
    p.add_argument("--minutes", type=float, default=0)
    p.add_argument("--lr", type=float, default=1e-3)
    p.add_argument("--budget", type=int, default=64 * 1200)
    p.add_argument("--workers", type=int, default=8)
    p.add_argument("--min_char", type=int, default=5)
    p.add_argument("--limit", type=int, default=0)
    p.add_argument("--ckpt")
    p.add_argument("--split")
    p.add_argument("--pred")
    p.add_argument("--threads", type=int, default=0)
    p.add_argument("--arch", default="lstm")
    p.add_argument("--init")
    p.add_argument("--realdev")
    a = p.parse_args()
    if a.threads:
        torch.set_num_threads(a.threads)
    {"train": train, "infer": infer}[a.cmd](a)
