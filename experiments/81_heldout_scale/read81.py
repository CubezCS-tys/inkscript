"""Experiment 81, step 2: every reader on every held-out line (local CPU, niced, <= 4 threads).

    nice -n 19 ionice -c3 out/venv/bin/python read81.py image [--limit N]        -> out/read/image.jsonl
    nice -n 19 ionice -c3 out/venv/bin/python read81.py signal NAME CKPT         -> out/read/signal_NAME.jsonl
    nice -n 19 ionice -c3 out/venv/bin/python read81.py check                    (reproduce exp 77/79 outputs on their test lines)

Image readers (weights read only; model code imported unchanged from experiments 77 / 78 by file path):
  v1  = experiment 77 out/weights/v1 (real Azure lines);   v2 = experiment 77 out/weights/v2 (Gemini-judged labels);
  s2r = experiment 78 out/weights/syn_then_real (synthetic v1 then real: the best of 78 on the owner's pages).
Per line: the greedy reading of each; for fusion as experiment 79's score79.py defines it, v1's N best (CTC prefix
beam 10, N <= 8, score79.beam imported) with each candidate's CTC log-likelihood under v1 (s77) and s2r (s78);
v1's per-frame confidence (cmin77 / cmean77).  The signal reader (train79b.SignalReader) adds its greedy reading
(gsig) and its log-likelihood of each of v1's candidates (ssig).  Line order and keys = out/lines81.jsonl.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
import time
from pathlib import Path

import numpy as np
import torch

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
RD = OUT / "read"
sys.path.insert(0, str(E / "79_signal_reader"))


def module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(spec)
    sys.modules[name] = m
    spec.loader.exec_module(m)
    return m


def image_reader(mod, ck_path):
    ck = torch.load(ck_path, map_location="cpu", weights_only=False)
    mm = ck["meta"]
    cs = mod.Charset(mm["chars"])
    try:
        model = mod.Reader(len(cs), arch=mm.get("arch", "lstm"), hid=mm.get("hid", 384), cw=mm.get("cw", 1.0),
                           feat=mm.get("feat", 384))
    except TypeError:
        model = mod.Reader(len(cs), arch=mm.get("arch", "lstm"))
    model.load_state_dict(ck["model"])
    return cs, model.eval()


@torch.no_grad()
def image_logprobs(mod, model, st, keys_idx):
    w = mod.widths_of(st, keys_idx)
    ds = mod.LineSet(st, [(i, []) for i in keys_idx], False)
    out = {}
    order = sorted(range(len(keys_idx)), key=lambda j: w[j])
    B, j = 30000, 0
    while j < len(order):
        mx, batch = 0, []
        while j < len(order) and (not batch or max(mx, w[order[j]]) * (len(batch) + 1) <= B):
            mx = max(mx, w[order[j]])
            batch.append(ds[order[j]])
            j += 1
        x, widths, _, idx = mod.collate(batch)
        lo = model(x, widths // 4).float().log_softmax(-1)
        for k, i in enumerate(idx):
            out[st.keys[i]] = lo[k, :int(widths[k] // 4)].numpy().astype(np.float32)
    return out


def run_image(limit: int = 0):
    import score79 as S
    torch.set_num_threads(4)
    m77 = module("train77", E / "77_scratch_reader/train77.py")
    m78 = module("train78", E / "78_synthetic_lines/train78.py")
    R = {"v1": (m77, *image_reader(m77, E / "77_scratch_reader/out/weights/v1/best.pt")),
         "v2": (m77, *image_reader(m77, E / "77_scratch_reader/out/weights/v2/best.pt")),
         "s2r": (m78, *image_reader(m78, E / "78_synthetic_lines/out/weights/syn_then_real/best.pt"))}
    st = m77.Store(str(OUT / "crops48"), "test81")
    RD.mkdir(exist_ok=True)
    fo = RD / "image.jsonl"
    done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
    todo = [i for i, k in enumerate(st.keys) if k not in done]
    if limit:
        todo = todo[:limit]
    print(f"{len(st.keys)} crops, {len(todo)} to read", flush=True)
    t0 = time.time()
    with open(fo, "a", encoding="utf-8") as f:
        for c in range(0, len(todo), 500):
            chunk = todo[c:c + 500]
            lp = {n: image_logprobs(m, model, st, chunk) for n, (m, cs, model) in R.items()}
            cs77, cs78 = R["v1"][1], R["s2r"][1]
            for i in chunk:
                k = st.keys[i]
                L = lp["v1"][k]
                cands = ["".join(cs77.chars[t - 1] for t in ids) for ids, _ in S.beam(L)[:8]]
                g77 = cs77.decode(L.argmax(-1).tolist())
                if g77 not in cands:
                    cands.insert(0, g77)
                rec = dict(key=k, cands=[m77.from_visual(v) for v in cands],
                           s77=[S.ctc_score(L, cs77, v) for v in cands],
                           s78=[S.ctc_score(lp["s2r"][k], cs78, v) for v in cands],
                           cmin77=float(np.exp(L.max(-1)).min()) if len(L) else 0.0,
                           cmean77=float(np.exp(L.max(-1)).mean()) if len(L) else 0.0, T77=int(L.shape[0]))
                for n, (m, cs, _) in R.items():
                    rec[n] = m.from_visual(cs.decode(lp[n][k].argmax(-1).tolist()))
                f.write(json.dumps(rec, ensure_ascii=False) + "\n")
            f.flush()
            print(f"{c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)


def load_signals(keys=None):
    sig = {}
    for f in sorted((OUT / "sig").glob("*.npz")):
        z = np.load(f)
        for k in z.files:
            if keys is None or k in keys:
                sig[k] = z[k]
    return sig


@torch.no_grad()
def run_signal(name: str, ckpt: str):
    import score79 as S
    import train79b as T79
    torch.set_num_threads(4)
    ck = torch.load(ckpt, map_location="cpu")
    cs = T79.Charset(ck["chars"])
    img = {d["key"]: d for d in map(json.loads, open(RD / "image.jsonl", encoding="utf-8"))}
    sig = load_signals(set(img))
    keys = sorted(k for k in img if k in sig and len(sig[k]) >= 4)
    n_in = sig[keys[0]].shape[1] - 1
    model = T79.SignalReader(n_in, len(cs)).eval()
    model.load_state_dict({k: v for k, v in ck["model"].items() if not k.startswith("head2.")})
    fo = RD / f"signal_{name}.jsonl"
    done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
    keys = [k for k in keys if k not in done]
    keys.sort(key=lambda k: len(sig[k]))
    print(f"{len(keys)} signals to read with {name}", flush=True)
    t0 = time.time()
    with open(fo, "a", encoding="utf-8") as f:
        j = 0
        while j < len(keys):
            b = []
            while j < len(keys) and (not b or len(sig[keys[j]]) * (len(b) + 1) <= 40000):
                b.append(keys[j])
                j += 1
            X = [torch.from_numpy(T79.prep(sig[k], False)) for k in b]
            L = torch.tensor([len(x) for x in X])
            P = torch.zeros(len(X), int(L.max()), X[0].shape[1])
            for i, x in enumerate(X):
                P[i, :len(x)] = x
            lo = model(P).float().log_softmax(-1)
            ol = model.out_len(L)
            for i, k in enumerate(b):
                lp = lo[i, :int(ol[i])].numpy()
                r = img[k]
                f.write(json.dumps(dict(key=k, gsig=T79.from_visual(cs.decode(lp.argmax(-1).tolist())),
                                        ssig=[S.ctc_score(lp, cs, T79.to_visual(c)) for c in r["cands"]],
                                        Tsig=int(lp.shape[0])), ensure_ascii=False) + "\n")
            if j % 2000 < len(b):
                print(f"{j}/{len(keys)} {time.time() - t0:.0f}s", flush=True)
    print("done", name, flush=True)


def run_one(name: str, ckpt: str, threads: int = 2):
    """One more image reader (greedy only), e.g. exp 77's v2b, added after the first pass."""
    torch.set_num_threads(threads)
    m77 = module("train77", E / "77_scratch_reader/train77.py")
    cs, model = image_reader(m77, ckpt)
    st = m77.Store(str(OUT / "crops48"), "test81")
    fo = RD / f"image_{name}.jsonl"
    done = {json.loads(l)["key"] for l in open(fo, encoding="utf-8")} if fo.exists() else set()
    todo = [i for i, k in enumerate(st.keys) if k not in done]
    t0 = time.time()
    with open(fo, "a", encoding="utf-8") as f:
        for c in range(0, len(todo), 500):
            chunk = todo[c:c + 500]
            with torch.no_grad():
                lp = image_logprobs(m77, model, st, chunk)
            for i in chunk:
                k = st.keys[i]
                f.write(json.dumps({"key": k, name: m77.from_visual(cs.decode(lp[k].argmax(-1).tolist()))},
                                   ensure_ascii=False) + "\n")
            f.flush()
            print(f"{c + len(chunk)}/{len(todo)} {time.time() - t0:.0f}s", flush=True)
    print("ONE_DONE", name, flush=True)


@torch.no_grad()
def check():
    """Our CPU pipeline must reproduce the GPU outputs of experiments 77 (v1 greedy on its test shards) and 79
    (p3t greedy on its realtest signals)."""
    import train79b as T79
    torch.set_num_threads(4)
    m77 = module("train77", E / "77_scratch_reader/train77.py")
    cs, model = image_reader(m77, E / "77_scratch_reader/out/weights/v1/best.pt")
    st = m77.Store(str(E / "77_scratch_reader/out/test"), "test")
    idx = list(range(0, len(st.keys), 4))
    lp = image_logprobs(m77, model, st, idx)
    ref = {d["key"]: d["pred"] for d in map(json.loads, open(E / "77_scratch_reader/out/pred/test_v1.jsonl", encoding="utf-8"))}
    same = sum(m77.from_visual(cs.decode(v.argmax(-1).tolist())) == ref[k] for k, v in lp.items())
    print(f"v1 CPU vs exp 77 GPU greedy: {same}/{len(lp)} identical", flush=True)
    ck = torch.load(E / "79_signal_reader/out/host/p3t/model.pt", map_location="cpu")
    scs = T79.Charset(ck["chars"])
    z = np.load(E / "79_signal_reader/out/realtest/signals.npz")
    keys = [k for k in z.files if len(z[k]) >= 4][::4]
    sm = T79.SignalReader(z[keys[0]].shape[1] - 1, len(scs)).eval()
    sm.load_state_dict({k: v for k, v in ck["model"].items() if not k.startswith("head2.")})
    ref = {d["key"]: d["gsig"] for d in map(json.loads, open(E / "79_signal_reader/out/fuse/p3t/test.jsonl", encoding="utf-8"))}
    same = n = 0
    for k in keys:
        if k not in ref:
            continue
        x = torch.from_numpy(T79.prep(z[k], False))[None]
        lo = sm(x)[0]
        same += T79.from_visual(scs.decode(lo.argmax(-1).tolist())) == ref[k]
        n += 1
    print(f"p3t CPU vs exp 79 GPU greedy: {same}/{n} identical", flush=True)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("name", nargs="?")
    ap.add_argument("ckpt", nargs="?")
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    if a.cmd == "image":
        run_image(a.limit)
    elif a.cmd == "signal":
        run_signal(a.name, a.ckpt)
    elif a.cmd == "one":
        run_one(a.name, a.ckpt)
    elif a.cmd == "check":
        check()
