"""Experiment 95, idea 2 (and 3a): learned per-journal letter programs.

For a training-pool journal, the letter programs of its base library are LEARNED from the journal's own consensus
lines: every point of every program a line uses gets an offset (dx, dy in em, and a log width), shared by every
occurrence of that letter form in every line.  Dots, hamza and madda are strokes of their own and learn like the
rest (AlQalam: one set per letter form and dot kind; fonts: the glyph's mark strokes or mark glyphs).

Variants (idea 3a):
  edges   each centre-line edge has its own points: the two ends of edges that meet at a junction may drift apart
          ("two pens");
  onepen  the edge ends that meet at a junction (within 0.035 em, same glyph) are ONE point (snapped to their mean),
          so the letter stays one connected pen trace while it learns.

Training (GPU): minibatches of 48 learn lines; each line's style (size, slant, widths, nib, marks) and position are its
own; phase A fits the line with the programs frozen (100 steps, 30 when warm), phase B moves programs and lines
together (40 steps, fine blur), the program offsets keep one Adam across the whole run; offsets are clamped
(|dx|, |dy| <= 0.08 em, |dlog r| <= 0.7) and kept smooth along each stroke; two epochs.
Test: test DOCUMENTS' lines, exp 87's ceiling fit (true text, all style settings free, 160 steps), base against
learned, same initialisation.

    python learn95.py screen J            the base library of journal J (48 learn lines, 60 steps, every candidate)
    python learn95.py train J VARIANT     -> out/learn/<J>_<VARIANT>.json (the learned programs) + train log
    python learn95.py eval J              -> out/learn/eval_<J>.jsonl (base and every learned variant on test lines)
    python learn95.py all                 every journal: screen, train both variants, eval (resumable)
    python learn95.py smoke               a tiny end-to-end run (8 lines, few steps)

A learned library is written as "L:<J>:<VARIANT>"; install() teaches 87's writer.shape() to write it (the base
library's shaping, then every stroke replaced by its learned points).
"""
from __future__ import annotations

import json
import math
import os
import random
import sys
import time
from collections import defaultdict
from pathlib import Path

import numpy as np

from common95 import D95, OUT, assert_pool, jl, text_for, use_programs

LEARN = Path(os.environ.get("OUT95", OUT)) / "learn"
JOURNALS = ["0013", "0924", "0523", "0739"]          # 0690 tried: only 97 consensus learn lines; 0739 has 427
CANDS = {"modern": ["alqalam", "font:amiri_Amiri-Regular", "font:amiri_Amiri-Bold", "font:notonaskharabic_NotoNaskhArabic_wght",
                    "font:notosansarabic_NotoSansArabic_wdth_wght", "font:mirza_Mirza-Regular",
                    "font:scheherazadenew_ScheherazadeNew-Regular"],
         "old": ["alqalam", "font:amiri_Amiri-Regular", "font:amiri_Amiri-Bold", "font:scheherazadenew_ScheherazadeNew-Regular",
                 "font:scheherazadenew_ScheherazadeNew-Bold", "font:Mand0924y1928", "font:Mand0924y1936", "font:Mand0739y1938",
                 "font:Mand0917y1927", "font:Mand0763y1936"]}
ERA = {"0013": "modern", "0523": "modern", "0924": "old", "0739": "old", "0690": "old"}
TIE = 0.035
CLAMP = (0.08, 0.08, 0.7)
SMOKE = os.environ.get("SMOKE95") == "1"
# round 2 (2026-11-10): round 1's priors held the offsets at ~0.0005 em (nothing learned); REG95 scales both priors,
# R95 tags the output files, EPOCHS95 / BSZ95 the schedule (batch 32: round 1 ran out of GPU memory at 48)
REG = float(os.environ.get("REG95", 1.0))
RTAG = os.environ.get("R95", "")
EPOCHS = int(os.environ.get("EPOCHS95", 2))
BSZ = int(os.environ.get("BSZ95", 48))


# ------------------------------------------------------------------------------------------------ programs + keys
def keyed_strokes(inst, lib):
    """Per glyph instance: [(key, pts [N,3], is_mark, glyph_group)] in the order writer87.segments walks them."""
    import writer87 as W
    out = []
    for g in inst:
        L = []
        if lib == "alqalam":
            code = g.get("code")
            nb = len(W._strokes_of(code)[0]) if code is not None else 0
            for si, (pts, mk) in enumerate(g["strokes"]):
                if si < nb:
                    L.append((f"c{code}.{si}", pts, mk, f"c{code}"))
                else:
                    L.append((f"d{code}.{g['ch']}.{si}", pts, mk, f"d{code}.{g['ch']}"))
        else:
            for si, (pts, mk) in enumerate(g["strokes"]):
                L.append((f"g{g.get('gid')}.{si}", pts, mk, f"g{g.get('gid')}"))
        out.append(L)
    return out


class Table:
    """Every program point a set of texts uses: base points and the parameter row each point reads."""

    def __init__(self, lib: str, texts, variant: str):
        import writer87 as W
        self.lib, self.variant = lib, variant
        self.keys = {}                                    # key -> (first point, n)
        base, glyph_of = [], []
        groups = defaultdict(list)
        for t in texts:
            inst, _ = W.shape(text_for(lib, t), lib)
            for L in keyed_strokes(inst, lib):
                for key, pts, mk, gg in L:
                    if key in self.keys or len(pts) == 0:
                        continue
                    p = np.asarray(pts, np.float32)
                    self.keys[key] = (len(base), len(p))
                    groups[gg].append(key)
                    base.extend(p.tolist())
        self.base = np.asarray(base, np.float32).reshape(-1, 3)
        self.pid = np.arange(len(self.base))
        if variant == "onepen":                          # junction ends: one point per cluster, snapped
            for gg, ks in groups.items():
                ends = []
                for k in ks:
                    a, n = self.keys[k]
                    ends += [a, a + n - 1] if n > 1 else [a]
                ends = sorted(set(ends))
                P = self.base[ends, :2]
                lab = list(range(len(ends)))
                for i in range(len(ends)):
                    for j in range(i):
                        if np.hypot(*(P[i] - P[j])) < TIE:
                            ri, rj = lab[i], lab[j]
                            lab = [rj if x == ri else x for x in lab]
                for r in set(lab):
                    mem = [ends[i] for i in range(len(ends)) if lab[i] == r]
                    if len(mem) > 1:
                        m = self.base[mem, :2].mean(0)
                        self.base[mem, :2] = m
                        self.pid[mem] = mem[0]
        # neighbours along strokes (smoothness), point level
        prv, nxt = np.arange(len(self.base)), np.arange(len(self.base))
        for k, (a, n) in self.keys.items():
            for j in range(1, n - 1):
                prv[a + j], nxt[a + j] = a + j - 1, a + j + 1
        self.prv, self.nxt = prv, nxt
        self.n = len(self.base)

    def learned(self, OFF):
        """key -> learned points [N,3] (numpy)."""
        o = OFF[self.pid]
        P = self.base.copy()
        P[:, :2] += o[:, :2]
        P[:, 2] *= np.exp(o[:, 2])
        return {k: P[a:a + n].round(5).tolist() for k, (a, n) in self.keys.items()}


def seg_index(bt, tab: Table):
    """For F.Batch bt: per segment the start / end point rows of tab, the instance offsets and the dup flag."""
    ia, ib, ox, oy, dup = [], [], [], [], []
    for it in bt.items:
        for g, L in zip(it["inst"], keyed_strokes(it["inst"], tab.lib)):
            for key, pts, mk, gg in L:
                if len(pts) == 0:
                    continue
                a, n = tab.keys[key]
                if n == 1:
                    ia.append(a); ib.append(a); ox.append(g["x"]); oy.append(g["y"]); dup.append(1)
                    continue
                for j in range(n - 1):
                    ia.append(a + j); ib.append(a + j + 1); ox.append(g["x"]); oy.append(g["y"]); dup.append(0)
    import torch
    dev = bt.dev
    S = dict(ia=torch.as_tensor(ia, device=dev), ib=torch.as_tensor(ib, device=dev),
             o=torch.as_tensor(np.stack([ox, oy], 1), dtype=torch.float32, device=dev),
             dup=torch.as_tensor(dup, dtype=torch.float32, device=dev))
    if len(ia) != len(bt.a):
        print("  segment count mismatch", len(ia), len(bt.a), flush=True)
        return None
    return S


def apply_off(bt, tab_t, S, OFF):
    """Set bt.a, bt.b, bt.ra, bt.rb from the base points and the offsets (differentiable in OFF)."""
    import torch
    base, pid = tab_t
    o = OFF[pid]
    P = torch.cat([base[:, :2] + o[:, :2], (base[:, 2] * torch.exp(o[:, 2]))[:, None]], 1)
    A, B = P[S["ia"]], P[S["ib"]]
    bt.a = A[:, :2] + S["o"]
    # every segment at least 1e-4 em long: a junction snapped onto itself would give atan2(0, 0), whose gradient is NaN
    bt.b = B[:, :2] + S["o"] + torch.stack([(S["dup"] + 1.0) * 1e-4, torch.zeros_like(S["dup"])], 1)
    bt.ra, bt.rb = A[:, 2], B[:, 2]


def install(tables: dict):
    """Teach writer87.shape() the learned libraries: tables = {"L:J:V": (base lib, {key: pts})}."""
    import writer87 as W
    if not hasattr(W, "_shape87"):
        W._shape87 = W.shape

    def shape(text, lib, **kw):
        if not lib.startswith("L:"):
            return W._shape87(text, lib, **kw)
        blib, learned = tables[lib]
        inst, width = W._shape87(text, blib, **kw)
        for g, L in zip(inst, keyed_strokes(inst, blib)):
            g["strokes"] = [(np.asarray(learned[k], np.float32) if k in learned else pts, mk) for k, pts, mk, _ in L]
        return inst, width
    W.shape = shape


def load_learned(J, V):
    d = json.loads((LEARN / f"{J}_{V}.json").read_text())   # V may carry the round tag (onepen_r2)
    return f"L:{J}:{V}", (d["base"], d["strokes"])


# ------------------------------------------------------------------------------------------------ data
def lines(J, role):
    import cv2
    R = [r for r in jl(D95 / "journals.jsonl") if r["jcode"] == J and r["role"] == role]
    assert_pool([r["key"] for r in R], f"journal {J}")
    for r in R:
        r["grey"] = cv2.imread(str(D95 / "crops/jl" / f"{r['key']}.png"), 0)
    return [r for r in R if r["grey"] is not None]


def lib_ok(lib, text):
    sys.path.insert(0, os.environ.get("E87", str(Path(__file__).resolve().parent.parent / "87_writer")))
    if not lib.startswith("font:Mand"):
        return True
    import json as _j
    p = D95 / "exclude.json"
    EX = _j.loads(p.read_text()) if p.exists() else {}
    e = EX.get(lib[5:], {})
    if e == "DROP":
        return False
    return not (set(text) & set(e.get("chars", "")))


# ------------------------------------------------------------------------------------------------ GPU steps
def free_fit(F, items, dev, iters):
    bt = F.Batch(items, dev)
    P = F.Params(bt)
    F.init_items(bt, P)
    F.fit(bt, P, mode="free", iters=iters)
    return bt, P, F.scores(bt, P)


def screen(J):
    W = use_programs()
    import fit87 as F
    dev = F.device()
    LEARN.mkdir(parents=True, exist_ok=True)
    out = LEARN / f"screen_{J}.json"
    if out.exists():
        return json.loads(out.read_text())
    R = lines(J, "learn")
    rng = random.Random(95)
    R = rng.sample(R, min(48 if not SMOKE else 4, len(R)))
    res = {}
    for lib in CANDS[ERA[J]]:
        ok = [r for r in R if lib_ok(lib, r["text"])]
        if len(ok) < 0.9 * len(R):
            res[lib] = dict(skipped=f"writes {len(ok)}/{len(R)} lines")
            continue
        items = [dict(grey=r["grey"], text=text_for(lib, r["text"]), lib=lib, group=k) for k, r in enumerate(ok)]
        ious = []
        for i in range(0, len(items), 24):
            _, _, sc = free_fit(F, [dict(x, group=k) for k, x in enumerate(items[i:i + 24])], dev, 60 if not SMOKE else 3)
            ious += [s["iou"] for s in sc if s["n_missing"] == 0]
        res[lib] = dict(median_iou=round(float(np.median(ious)), 4) if ious else 0.0, n=len(ious))
        print(J, lib, res[lib], flush=True)
    best = max((l for l in res if "median_iou" in res[l]), key=lambda l: res[l]["median_iou"])
    d = dict(journal=J, best=best, libs=res)
    out.write_text(json.dumps(d, indent=1))
    return d


def train(J, variant, epochs=None, bsz=None):
    import torch
    import torch.nn.functional as TF
    W = use_programs()
    import fit87 as F
    dev = F.device()
    epochs, bsz = epochs or EPOCHS, bsz or BSZ
    out = LEARN / f"{J}_{variant}{RTAG}.json"
    if out.exists():
        return
    lib = screen(J)["best"]
    R = [r for r in lines(J, "learn") if lib_ok(lib, r["text"])]
    if SMOKE:
        R, epochs, bsz = R[:8], 1, 4
    T = [r for r in lines(J, "test") if lib_ok(lib, r["text"])]
    tab = Table(lib, [r["text"] for r in R + T], variant)
    base_t = torch.as_tensor(tab.base, device=dev)
    pid_t = torch.as_tensor(tab.pid, device=dev)
    prv_t, nxt_t = torch.as_tensor(tab.prv, device=dev), torch.as_tensor(tab.nxt, device=dev)
    OFF = torch.zeros((tab.n, 3), device=dev, requires_grad=True)
    optO = torch.optim.Adam([OFF], lr=1.0, betas=(0.9, 0.99))
    lrs = torch.tensor([0.0012, 0.0012, 0.006], device=dev)       # per column: em, em, log width
    lim = torch.tensor(CLAMP, device=dev)
    cache = {}
    log = open(LEARN / f"{J}_{variant}{RTAG}.log", "a")
    rng = random.Random(95)
    t0 = time.time()
    nA, nB = (100, 40) if not SMOKE else (3, 3)
    for ep in range(epochs):
        order = list(range(len(R)))
        rng.shuffle(order)
        for bi in range(0, len(order), bsz):
            B = [R[i] for i in order[bi:bi + bsz]]
            if dev == "cuda":
                torch.cuda.empty_cache()
            items = [dict(grey=r["grey"], text=text_for(lib, r["text"]), lib=lib, group=k) for k, r in enumerate(B)]
            bt = F.Batch(items, dev)
            S = seg_index(bt, tab)
            if S is None:
                continue
            with torch.no_grad():
                apply_off(bt, (base_t, pid_t), S, OFF.detach())
            P = F.Params(bt)
            warm = all(r["key"] in cache for r in B)
            if warm:
                with torch.no_grad():
                    for k, r in enumerate(B):
                        c = cache[r["key"]]
                        for kk in F.STYLE_KEYS:
                            P.style[kk][k] = c["s"][kk]
                        for kk in F.LINE_KEYS:
                            P.linep[kk][k] = c["l"][kk]
                        n = min(len(c["t"]), P.theta.shape[1])
                        P.theta[k, :n] = torch.as_tensor(c["t"][:n], device=dev)
                F.fit(bt, P, mode="free", iters=max(3, nA // 3), fine_only=True)
            else:
                F.init_items(bt, P)
                F.fit(bt, P, mode="free", iters=nA)
            # phase B: programs and lines together
            for kk in F.STYLE_KEYS:
                P.style[kk].requires_grad_(True)
            optL = torch.optim.Adam([dict(params=list(P.style.values()), lr=0.005),
                                     dict(params=list(P.linep.values()), lr=0.1), dict(params=[P.theta], lr=0.01)])
            used = torch.zeros(tab.n, dtype=torch.bool, device=dev)
            used[pid_t[S["ia"]]] = True
            used[pid_t[S["ib"]]] = True
            with torch.no_grad():
                dens = F._blur(bt.T, 4.0)
                Wt = 1.0 / (0.15 + dens / dens.amax((1, 2), keepdim=True).clamp(min=1e-3))
            for it in range(nB):
                sig = 1.2 if it < nB // 2 else 0.6
                optO.zero_grad(set_to_none=True)
                optL.zero_grad(set_to_none=True)
                apply_off(bt, (base_t, pid_t), S, OFF)
                Rr = F.render_batch(bt, P)
                Rb, Tb = F._blur(Rr, sig), F._blur(bt.T, sig)
                inter = (Wt * Rb * Tb).sum((1, 2))
                union = (Wt * (Rb + Tb - Rb * Tb)).sum((1, 2)).clamp(min=1.0)
                data = (1 - inter / union).sum()
                o = OFF[pid_t]
                sec = o[prv_t] - 2 * o + o[nxt_t]
                um = used[pid_t]
                reg = REG * (1e-3 * ((o[um, :2] / 0.03) ** 2).sum() + 1e-3 * ((o[um, 2] / 0.3) ** 2).sum()
                             + 1e-2 * ((sec[um, :2] / 0.01) ** 2).sum())
                (data + reg).backward()
                with torch.no_grad():
                    for q in [OFF] + list(P.parameters()):
                        if q.grad is not None:
                            torch.nan_to_num_(q.grad, nan=0.0, posinf=0.0, neginf=0.0)
                    keep = OFF.detach().clone()
                    g = OFF.grad
                    # Adam with a per-column learning rate: scale the step after the update
                    optO.step()
                    step = OFF - keep
                    OFF.copy_(keep + step * lrs[None, :])
                    OFF[~used] = keep[~used]
                    OFF.copy_(torch.maximum(torch.minimum(OFF, lim), -lim))
                optL.step()
                P.clamp_()
            sc = F.scores(bt, P)
            for k, r in enumerate(B):
                cache[r["key"]] = dict(s={kk: float(P.style[kk][k]) for kk in F.STYLE_KEYS},
                                       l={kk: float(P.linep[kk][k]) for kk in F.LINE_KEYS},
                                       t=P.theta[k].detach().cpu().numpy().tolist(), iou=sc[k]["iou"])
            msg = dict(ep=ep, batch=bi // bsz, lines=len(B), iou=round(float(np.mean([s["iou"] for s in sc])), 4),
                       off_mean=round(float(OFF.detach()[:, :2].abs().mean()), 5), min=round((time.time() - t0) / 60, 1))
            log.write(json.dumps(msg) + "\n")
            log.flush()
            print(J, variant, msg, flush=True)
    O = OFF.detach().cpu().numpy()
    out.write_text(json.dumps(dict(journal=J, variant=variant, base=lib, n_points=int(tab.n),
                                   n_params=int(len(set(tab.pid.tolist()))), learn_lines=len(R),
                                   train_iou={k: v["iou"] for k, v in cache.items()},
                                   off_abs_mean=float(np.abs(O[:, :2]).mean()), strokes=tab.learned(O))))


def evaluate(J, variants=("edges", "onepen", "edges_r2", "onepen_r2"), iters=160):
    W = use_programs()
    import fit87 as F
    dev = F.device()
    out = LEARN / f"eval_{J}.jsonl"
    done = {(json.loads(l)["key"], json.loads(l)["lib"]) for l in open(out)} if out.exists() else set()
    base = screen(J)["best"]
    libs = [base]
    tabs = {}
    for v in variants:
        if (LEARN / f"{J}_{v}.json").exists():
            name, t = load_learned(J, v)
            tabs[name] = t
            libs.append(name)
    install(tabs)
    T = [r for r in lines(J, "test") if lib_ok(base, r["text"])]
    Lr = [r for r in lines(J, "learn") if lib_ok(base, r["text"])]
    Lr = random.Random(7).sample(Lr, min(96, len(Lr)))
    if SMOKE:
        T, Lr, iters = T[:4], Lr[:2], 3
    f = open(out, "a")
    for role, Rs in (("test", T), ("learn", Lr)):
        for lib in libs:
            todo = [r for r in Rs if (r["key"], lib) not in done]
            for i in range(0, len(todo), 32):
                B = todo[i:i + 32]
                items = [dict(grey=r["grey"], text=text_for(base, r["text"]), lib=lib, group=k) for k, r in enumerate(B)]
                bt, P, sc = free_fit(F, items, dev, iters)
                for r, s in zip(B, sc):
                    f.write(json.dumps(dict(key=r["key"], stem=r["stem"], role=role, lib=lib,
                                            **{k: round(s[k], 4) for k in ("iou", "chamfer", "recall", "precision")},
                                            n_missing=s["n_missing"])) + "\n")
                f.flush()
                print(J, role, lib, i + len(B), "/", len(todo), flush=True)


def main_all():
    if os.environ.get("JOURNALS95"):
        JL = os.environ["JOURNALS95"].split(",")
    else:
        JL = JOURNALS
    for J in JL:
        if not lines(J, "learn"):
            print("no lines for", J, flush=True)
            continue
        screen(J)
        for v in (("onepen", "edges") if J == "0013" else ("onepen",)):   # budget: 3a on 0013 only
            try:
                train(J, v)
            except Exception as e:  # noqa: BLE001
                print("train failed", J, v, type(e).__name__, str(e)[:200], flush=True)
        evaluate(J)


if __name__ == "__main__":
    c = sys.argv[1]
    if c == "screen":
        print(screen(sys.argv[2]))
    elif c == "train":
        train(sys.argv[2], sys.argv[3])
    elif c == "eval":
        evaluate(sys.argv[2])
    elif c == "all":
        main_all()
    elif c == "smoke":
        os.environ["SMOKE95"] = "1"
        SMOKE = True
        LEARN = LEARN.parent / "learn_smoke"
        LEARN.mkdir(parents=True, exist_ok=True)
        J = sys.argv[2] if len(sys.argv) > 2 else "0013"
        screen(J)
        train(J, "onepen")
        train(J, "edges")
        evaluate(J)
