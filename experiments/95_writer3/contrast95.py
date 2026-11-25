"""Experiment 95, idea 1: contrastive checking.

Competing readings of one line are written in the page's style and compared ON THE INK OF THE DISPUTED SPAN only, the
rest of the line held fixed:
  1. the candidates' common leading and trailing words are the CONTEXT, the words between them the disputed span;
  2. an ANCHOR fit (exp 87's frozen page style; the line's position, baseline and warp fitted, 100 steps, exp 87's
     round-2 warp floor) writes one candidate and fixes where the context words sit;
  3. every candidate's disputed span is written alone into the gap between the fixed context words (its start and
     its own warp fitted, slope 0.6-2.0 of the style's natural width; style, size and baseline fixed), over the
     context's writing, two starts (fill the anchor's span / natural width), and scored on the gap's columns only;
  4. each of up to three candidates serves once as the anchor; a candidate's score is the mean over anchors.

    python contrast95.py jobs SET       local: out/data/cjobs_<SET>.jsonl  (SET = synth | pool | held | judged)
    python contrast95.py run SET        GPU: out/run/contrast_<SET>.jsonl (one row per group, resumable)

A GROUP is one comparison: a line, its candidates (texts), which candidates anchor, and what it tests.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path
from types import SimpleNamespace

import cv2
import numpy as np

from common95 import D87, D95, E, OUT, assert_pool, assert_unlocked, jl, norm_ws, text_for, use_programs

RUN = Path(os.environ.get("RUN95", OUT / "run"))
STYLE87 = Path(os.environ.get("STYLE87", E / "87_writer/out/run"))

# ------------------------------------------------------------------------------------------------ siblings
SIBG = ["بتثنيئ", "جحخ", "دذ", "رز", "سش", "صض", "طظ", "عغ", "فق", "هة", "اأإآ", "ىيئ", "وؤ"]
SIB = defaultdict(set)
for g in SIBG:
    for c in g:
        SIB[c] |= set(g) - {c}
AR = re.compile("^[ء-ي]+$")
HELD_PCT = 60                                    # held-out planted tests: 60% of the test lines (hash)


def siblings(word: str):
    out = []
    for j, ch in enumerate(word):
        for c in sorted(SIB.get(ch, ())):
            out.append(word[:j] + c + word[j + 1:])
    return out


def sibling_cands(text: str, key: str, n: int = 6):
    """(true text, [up to n texts with one letter of one word changed to a dot / hamza / ى / ة sibling], word index)"""
    rng = random.Random(int(hashlib.md5((key + "|sib").encode()).hexdigest()[:8], 16))
    ws = text.split(" ")
    idx = [i for i, w in enumerate(ws) if AR.match(w) and len(w) >= 3 and siblings(w)]
    if not idx:
        return None
    i = rng.choice(idx)
    S = siblings(ws[i])
    rng.shuffle(S)
    return [" ".join(ws[:i] + [s] + ws[i + 1:]) for s in S[:n]], i


# ------------------------------------------------------------------------------------------------ jobs (local)
def page_styles(which):
    rows = jl(STYLE87 / f"style_{which}.jsonl")
    import fit87 as F
    by = defaultdict(list)
    for x in rows:
        by[(x["page"], x["lib"])].append(x)
    best = {}
    for (p, lib), v in by.items():
        m = float(np.mean([x["iou"] for x in v]))
        if p not in best or m > best[p]["iou"]:
            best[p] = dict(lib=lib, iou=m, style={k: v[0]["params"][k] for k in F.STYLE_KEYS})
    return best


def _group(gid, key, where, lib, style, cands, anchors, test, **kw):
    return dict(gid=gid, key=key, where=where, lib=lib, style=style, cands=cands, anchors=anchors, test=test, **kw)


def jobs(which: str):
    out = []
    if which == "synth":
        for r in jl(D87 / "synth.jsonl"):
            sc = sibling_cands(norm_ws(r["text"]), r["key"])
            if sc:
                S, wi = sc
                out.append(_group(f"{r['key']}|sib", r["key"], "synth", r["lib"], None, [norm_ws(r["text"])] + S, [0, 1],
                                  "sibling", style_text=norm_ws(r["text"]), page=r["key"], era="synthetic", word=wi))
    elif which in ("pool", "held"):
        sys.path.insert(0, str(E / "87_writer"))
        import run87
        run87.D = D87
        styles = page_styles(which)
        pg = run87._pages(which)
        plants = {r["key"]: r for r in jl(D87 / f"plants_{which}.jsonl")}
        for p, L in pg.items():
            if p not in styles:
                continue
            _, T = run87.split_page(L, 2 if which == "held" else 0)
            st = styles[p]
            ok = lambda t: run87.lib_ok(st["lib"], t)       # a traced face never writes its excluded letters
            for x in T:
                if which == "held" and int(hashlib.md5(x["key"].encode()).hexdigest()[:8], 16) % 100 >= HELD_PCT:
                    continue                           # budget: a fixed hash sample of the held-out test lines
                V = {k: norm_ws(v) for k, v in plants[x["key"]]["variants"].items()}
                kinds = ("letter", "word_sub", "word_drop", "word_add") if which == "pool" else ("letter", "word_sub")
                for kind in kinds:
                    if kind in V and V[kind] != V["orig"] and ok(V["orig"]) and ok(V[kind]):
                        out.append(_group(f"{x['key']}|{kind}", x["key"], x["where"], st["lib"], st["style"],
                                          [V["orig"], V[kind]], [0, 1], kind, page=p, era=x["era"]))
                sc = sibling_cands(V["orig"], x["key"])
                if sc and ok(V["orig"]):
                    S, wi = sc
                    S = [t for t in S if ok(t)]
                if sc and ok(V["orig"]) and S:
                    out.append(_group(f"{x['key']}|sib", x["key"], x["where"], st["lib"], st["style"], [V["orig"]] + S,
                                      [0, 1], "sibling", page=p, era=x["era"], word=wi))
        if which == "pool":
            assert_pool([g["key"] for g in out], "pool groups")
    elif which == "judged":
        sys.path.insert(0, str(E / "81_heldout_scale"))
        import est81
        rows, S, C, ans = est81.load()
        styles = page_styles("held")
        held = {r["key"]: r for r in jl(D87 / "held.jsonl") if r["role"] == "judged"}
        for k, s in S.items():
            if k not in held:
                continue
            r = rows[k]
            p = f"{r['stem']}_{r['page']}"
            if p not in styles or not (D87 / "crops/judge" / f"{k}.png").exists():
                continue
            # distinct candidates by the strict form, each written as a reader gave it (v1, s2r, azure first)
            reps = {}
            for src in ["v1", "s2r", "azure"]:
                t = r["readings"].get(src)
                if isinstance(t, str) and est81.form(t) not in reps:
                    reps[est81.form(t)] = (norm_ws(t), src)
            for t in s["shown"]:
                if est81.form(t) not in reps:
                    reps[est81.form(t)] = (norm_ws(t), "shown")
            if len(reps) < 2:
                continue
            cands = [v[0] for v in reps.values()]
            srcs = [v[1] for v in reps.values()]
            if len(cands) > 6:
                cands, srcs = cands[:6], srcs[:6]
            anchors = [i for i, sname in enumerate(srcs) if sname in ("v1", "s2r", "azure")][:3] or [0]
            out.append(_group(f"{k}|judged", k, "judge", styles[p]["lib"], styles[p]["style"], cands, anchors, "judged",
                              srcs=srcs, page=p, era=r["era"], stratum=s["stratum"]))
    assert_unlocked([g["key"] for g in out], which)
    D95.mkdir(parents=True, exist_ok=True)
    with open(D95 / f"cjobs_{which}.jsonl", "w", encoding="utf-8") as f:
        for g in out:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    print(which, len(out), "groups", dict(__import__("collections").Counter(g["test"] for g in out)))


# ------------------------------------------------------------------------------------------------ GPU
def render_px(F, segs, Wmax, dev, tile=16, tau=0.6):
    """Soft ink [n, H, Wmax] of fixed placed capsules (no gradients): segs = [(A, B, ra, rb)] per line, pixels."""
    import torch
    n = [len(s[0]) for s in segs]
    if sum(n) == 0:
        return torch.zeros((len(segs), F.H, Wmax), device=dev)
    A = torch.cat([s[0] for s in segs]).to(dev)
    B = torch.cat([s[1] for s in segs]).to(dev)
    ra = torch.cat([s[2] for s in segs]).to(dev)
    rb = torch.cat([s[3] for s in segs]).to(dev)
    bt = SimpleNamespace(B=len(segs), Wmax=Wmax, seg_off=np.concatenate([[0], np.cumsum(n)]), dev=dev)
    with torch.no_grad():
        idx, val, T = F._tile_index(bt, A, B, ra, rb, tile, tau)
        x0s = (torch.arange(T, device=dev) * tile).float().repeat(bt.B)
        N = idx.shape[0]
        cnt = val.sum(1)
        order = torch.argsort(cnt)
        cs = cnt[order].cpu().numpy()
        first = int(np.searchsorted(cs, 1))
        flat = torch.zeros((N, F.H * tile), device=dev)
        for c0 in range(first, N, 256):
            o = order[c0:c0 + 256]
            sm = max(1, int(cs[min(N, c0 + 256) - 1]))
            best, _ = F._render_tiles(A, B, ra, rb, idx[o, :sm], val[o, :sm], x0s[o], tile, tau)
            flat[o] = best
        return flat.reshape(bt.B, T, F.H, tile).permute(0, 2, 1, 3).reshape(bt.B, F.H, T * tile)[:, :, :Wmax]


def crop_of(key, where):
    d = {"pool": D87 / "crops/pool", "held": D87 / "crops/held", "judge": D87 / "crops/judge",
         "synth": D87 / "crops/synth", "jl": D95 / "crops/jl"}[where]
    return cv2.imread(str(d / f"{key}.png"), 0)


def fit_styles(F, groups, dev, iters=int(os.environ.get("S_IT95", 160))):
    """Synthetic rung: the line is its own page; its style is fitted with the true text (like a page's agreed lines)."""
    need = [g for g in groups if g["style"] is None]
    for i in range(0, len(need), 24):
        B = need[i:i + 24]
        items = [dict(grey=crop_of(g["key"], g["where"]), text=text_for(g["lib"], g["style_text"]), lib=g["lib"], group=k)
                 for k, g in enumerate(B)]
        bt = F.Batch(items, dev)
        P = F.Params(bt)
        F.init_items(bt, P)
        F.fit(bt, P, mode="free", iters=iters)
        for k, g in enumerate(B):
            g["style"] = F.style_of_group(P, k)


def fit_anchors(F, W, items, dev, iters=int(os.environ.get("A_IT95", 100))):
    """items: dict(grey, text, lib, style) -> per item dict(segs (A, B, ra, rb) px, word per segment, line params)."""
    import torch
    its = [dict(grey=it["grey"], text=it["text"], lib=it["lib"], group=k) for k, it in enumerate(items)]
    bt = F.Batch(its, dev)
    P = F.Params(bt, style_init=[it["style"] for it in items])
    F.init_items(bt, P, fix_size=True)
    F.fit(bt, P, mode="frozen", iters=iters)
    sc = F.scores(bt, P)
    with torch.no_grad():
        A, B, ra, rb = F.place_batch(bt, P)
    res = []
    for i in range(bt.B):
        a, b = int(bt.seg_off[i]), int(bt.seg_off[i + 1])
        sg = bt.segs[i]
        g = sg.glyph.cpu().numpy()
        wd = np.asarray(sg.words, int)
        word = wd[np.clip(g, 0, max(0, len(wd) - 1))] if len(wd) else np.full(len(g), -1)
        if not its[i]["text"].strip() or not len(sg.words):
            word = np.full(b - a, -1)
        res.append(dict(segs=(A[a:b].cpu(), B[a:b].cpu(), ra[a:b].cpu(), rb[a:b].cpu()), word=word,
                        base=float(P.linep["base"][i]), tilt=float(P.linep["tilt"][i]), curve=float(P.linep["curve"][i]),
                        iou=sc[i]["iou"], size=float(P.style["size"][i]), W=bt.Wd[i]))
    return res


def common_affix(token_lists):
    n = min(len(t) for t in token_lists)
    p = 0
    while p < n and all(t[p] == token_lists[0][p] for t in token_lists):
        p += 1
    q = 0
    while q < n - p and all(t[len(t) - 1 - q] == token_lists[0][len(token_lists[0]) - 1 - q] for t in token_lists):
        q += 1
    return p, q


def gap_geometry(anc, p, q, n_words):
    """From the anchor's placed capsules: the fixed context's capsules, the gap [xl, xr] between the context words
    (pixels; an open side is the crop's edge), and the anchor's own disputed extent [dl, dr] (None when empty)."""
    import torch
    A, B, ra, rb = anc["segs"]
    w = anc["word"]
    ctx = (w >= 0) & ((w < p) | (w >= n_words - q))
    pre = (w >= 0) & (w < p)
    suf = (w >= 0) & (w >= n_words - q)
    dis = (w >= 0) & ~ctx
    r = torch.maximum(ra, rb).numpy()
    x_lo = torch.minimum(A[:, 0], B[:, 0]).numpy() - r
    x_hi = torch.maximum(A[:, 0], B[:, 0]).numpy() + r
    Wc = anc["W"]
    xr = float(x_lo[pre].min()) if pre.any() else float(Wc)
    xl = float(x_hi[suf].max()) if suf.any() else 0.0
    d = (float(x_lo[dis].min()), float(x_hi[dis].max())) if dis.any() else None
    m = torch.as_tensor(ctx)
    return (A[m], B[m], ra[m], rb[m]), xl, xr, d, bool(pre.any()), bool(suf.any())


def fit_gaps(F, gj, dev, iters=int(os.environ.get("G_IT95", 60))):
    """gj: gap jobs dict(grey, sub, lib, style, base, tilt, curve, ctx, win (c0, c1), span (s0, s1), init) ->
    per job its gap scores."""
    import torch
    import torch.nn.functional as TF
    its = [dict(grey=j["grey"], text=j["sub"] if j["sub"].strip() else "ا", lib=j["lib"], group=k) for k, j in enumerate(gj)]
    bt = F.Batch(its, dev)
    P = F.Params(bt, style_init=[j["style"] for j in gj])
    nonempty = torch.as_tensor([1.0 if j["sub"].strip() else 0.0 for j in gj], device=dev)
    lo, hi = math.log(math.expm1(0.6)), math.log(math.expm1(2.0))
    with torch.no_grad():
        for k, j in enumerate(gj):
            P.linep["base"][k] = j["base"]
            P.linep["tilt"][k] = j["tilt"]
            P.linep["curve"][k] = j["curve"]
            size = float(j["style"]["size"])
            wc = max(0.1, bt.widths[k])
            s0, s1 = j["span"]
            r = 1.0 if j["init"] == "natural" else float(np.clip((s1 - s0) / (size * wc), 0.6, 2.0))
            P.theta[k] = math.log(math.expm1(r))
            P.linep["x0"][k] = s1 - size * r * wc
    CTX = render_px(F, [j["ctx"] for j in gj], bt.Wmax, dev)
    M = torch.zeros((bt.B, 1, bt.Wmax), device=dev)
    for k, j in enumerate(gj):
        M[k, :, int(j["win"][0]):int(math.ceil(j["win"][1]))] = 1
    M = M * bt.colmask
    with torch.no_grad():
        dens = F._blur(bt.T, 4.0)
        Wt = 1.0 / (0.15 + dens / dens.amax((1, 2), keepdim=True).clamp(min=1e-3))
    for kk in F.STYLE_KEYS:
        P.style[kk].requires_grad_(False)
    for kk in ("base", "tilt", "curve"):
        P.linep[kk].requires_grad_(False)
    opt = torch.optim.Adam([dict(params=[P.linep["x0"]], lr=0.6), dict(params=[P.theta], lr=0.03)], betas=(0.8, 0.95))
    sched = [(0.0, 2.0), (0.4, 1.2), (0.75, 0.6)]

    def soft_loss(R, sig):
        Rb, Tb = F._blur(R, sig), F._blur(bt.T, sig)
        inter = (M * Wt * Rb * Tb).sum((1, 2))
        uni = (M * Wt * (Rb + Tb - Rb * Tb)).sum((1, 2)).clamp(min=1.0)
        return 1 - inter / uni

    for it in range(iters):
        sig = [s for f, s in sched if it >= f * iters][-1]
        opt.zero_grad(set_to_none=True)
        R = torch.maximum(F.render_batch(bt, P) * nonempty[:, None, None], CTX)
        loss = soft_loss(R, sig).sum()
        loss.backward()
        opt.step()
        with torch.no_grad():
            P.theta.clamp_(lo, hi)
    with torch.no_grad():
        R = torch.maximum(F.render_batch(bt, P) * nonempty[:, None, None], CTX)
        L = soft_loss(R, 0.0).cpu().numpy()
        L6 = soft_loss(R, 0.6).cpu().numpy()
    Rn = (R > 0.5).cpu().numpy()
    Tn = bt.T.cpu().numpy() > 0.5
    out = []
    for k, j in enumerate(gj):
        w = bt.Wd[k]
        c0, c1 = int(j["win"][0]), int(math.ceil(min(j["win"][1], w)))
        r, t = Rn[k, :, :w], Tn[k, :, :w]
        dr = cv2.distanceTransform((~r).astype(np.uint8), cv2.DIST_L2, 3)
        dt = cv2.distanceTransform((~t).astype(np.uint8), cv2.DIST_L2, 3)
        rw, tw = r[:, c0:c1], t[:, c0:c1]
        drw, dtw = dr[:, c0:c1], dt[:, c0:c1]
        size = float(j["style"]["size"])
        area = max(1.0, 0.05 * size * size)
        out.append(dict(loss=round(float(L[k]), 5), loss6=round(float(L6[k]), 5),
                        iou=round(float((rw & tw).sum() / max(1, (rw | tw).sum())), 5),
                        chamfer=round(0.5 * (float(drw[tw].mean()) if tw.any() else 20.0) + 0.5 * (float(dtw[rw].mean()) if rw.any() else 20.0), 4),
                        miss=round(float((tw & (drw > 1.5)).sum()) / area, 4), inv=round(float((rw & (dtw > 1.5)).sum()) / area, 4),
                        n_missing=int(bt.items[k].get("n_missing", 0)) if j["sub"].strip() else 0,
                        x0=round(float(P.linep["x0"][k]), 2)))
    return out


def run(which: str, batch_a=32, batch_g=64, chunk=48):
    import torch
    W = use_programs()
    import fit87 as F
    if os.environ.get("LEARNED95"):                     # idea 2's second test: learned libraries "L:<J>:<variant>"
        import learn95
        learn95.install(dict(learn95.load_learned(*n.split(":")[1:]) for n in os.environ["LEARNED95"].split(",")))
    dev = F.device()
    print("device", dev, torch.__version__, flush=True)
    RUN.mkdir(parents=True, exist_ok=True)
    out = RUN / f"contrast_{which}.jsonl"
    done = {json.loads(l)["gid"] for l in open(out, encoding="utf-8")} if out.exists() else set()
    G = [g for g in jl(D95 / f"cjobs_{which}.jsonl") if g["gid"] not in done]
    lim = int(os.environ.get("LIMIT95", 0))
    if lim:
        G = G[:lim]
    G.sort(key=lambda g: (g["where"], g["key"]))
    print(which, "groups", len(G), "(done before", len(done), ")", flush=True)
    f = open(out, "a", encoding="utf-8")
    t0 = time.time()
    crops = {}
    for c in range(0, len(G), chunk):
        C = G[c:c + chunk]
        for g in C:
            if g["key"] not in crops:
                crops[g["key"]] = crop_of(g["key"], g["where"])
        if len(crops) > 4000:
            crops = {g["key"]: crops[g["key"]] for g in C}
        fit_styles(F, C, dev)
        # 1. anchors (unique line x text)
        need = {}
        for g in C:
            for a in g["anchors"]:
                need[(g["key"], g["cands"][a])] = g
        keys = sorted(need, key=lambda kt: crops[kt[0]].shape[1])
        anc = {}
        for i in range(0, len(keys), batch_a):
            B = keys[i:i + batch_a]
            items = [dict(grey=crops[k], text=text_for(need[(k, t)]["lib"], t), lib=need[(k, t)]["lib"],
                          style=need[(k, t)]["style"]) for k, t in B]
            try:
                res = fit_anchors(F, W, items, dev)
            except Exception as e:  # noqa: BLE001
                print("anchor batch failed", type(e).__name__, str(e)[:200], flush=True)
                torch.cuda.empty_cache() if dev == "cuda" else None
                res = []
                for it in items:
                    try:
                        res += fit_anchors(F, W, [it], dev)
                    except Exception as e2:  # noqa: BLE001
                        print("  anchor skipped", type(e2).__name__, str(e2)[:120], flush=True)
                        res.append(None)
            for kt, r in zip(B, res):
                anc[kt] = r
        # 2. gap jobs
        gj, ref = [], []
        meta = {}
        for g in C:
            toks = [c_.split(" ") for c_ in g["cands"]]
            p, q = common_affix(toks)
            meta[g["gid"]] = {}
            for a in g["anchors"]:
                A_ = anc.get((g["key"], g["cands"][a]))
                if A_ is None:
                    continue
                ctx, xl, xr, d, has_pre, has_suf = gap_geometry(A_, p, q, len(toks[a]))
                size = float(g["style"]["size"])
                Wc = A_["W"]
                m = 0.3 * size
                win = (max(0.0, xl - m) if has_suf else 0.0, min(float(Wc), xr + m) if has_pre else float(Wc))
                if d is not None:
                    span = d
                elif has_pre and has_suf:
                    span = (xl, xr)
                else:
                    span = (xl, xl + size) if has_suf else (max(0.0, xr - size), xr)
                if win[1] - win[0] < 4:
                    continue
                meta[g["gid"]][a] = dict(anchor_iou=round(A_["iou"], 4), xl=round(xl, 1), xr=round(xr, 1),
                                         span=[round(span[0], 1), round(span[1], 1)], win=[round(win[0], 1), round(win[1], 1)])
                for ci, ct in enumerate(g["cands"]):
                    sub = " ".join(toks[ci][p:len(toks[ci]) - q])
                    for init in ("fill", "natural"):
                        gj.append(dict(grey=crops[g["key"]], sub=text_for(g["lib"], sub), lib=g["lib"], style=g["style"],
                                       base=A_["base"], tilt=A_["tilt"], curve=A_["curve"], ctx=ctx, win=win, span=span,
                                       init=init))
                        ref.append((g["gid"], a, ci, init))
        res = {}
        order = sorted(range(len(gj)), key=lambda i: gj[i]["grey"].shape[1])
        for i in range(0, len(order), batch_g):
            ix = order[i:i + batch_g]
            try:
                rr = fit_gaps(F, [gj[k] for k in ix], dev)
            except Exception as e:  # noqa: BLE001
                print("gap batch failed", type(e).__name__, str(e)[:200], flush=True)
                if dev == "cuda":
                    torch.cuda.empty_cache()
                rr = []
                for k in ix:
                    try:
                        rr += fit_gaps(F, [gj[k]], dev)
                    except Exception as e2:  # noqa: BLE001
                        print("  gap skipped", type(e2).__name__, str(e2)[:120], flush=True)
                        rr.append(None)
            for k, r in zip(ix, rr):
                res[ref[k]] = r
        for g in C:
            sc = {}
            for a in meta[g["gid"]]:
                sc[str(a)] = []
                for ci in range(len(g["cands"])):
                    two = [res.get((g["gid"], a, ci, init)) for init in ("fill", "natural")]
                    two = [x for x in two if x is not None]
                    sc[str(a)].append(min(two, key=lambda x: x["loss6"]) if two else None)
            row = {k: v for k, v in g.items() if k not in ("style",)}
            row.update(p_q=list(common_affix([c_.split(" ") for c_ in g["cands"]])), anchors_meta=meta[g["gid"]], scores=sc,
                       style_size=round(float(g["style"]["size"]), 2))
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
        f.flush()
        el = time.time() - t0
        n = min(len(G), c + chunk)
        print(f"contrast_{which} {n}/{len(G)} {el / 60:.1f} min ({el / max(1, n):.2f} s/group)", flush=True)
    f.close()


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("set")
    a = ap.parse_args()
    {"jobs": jobs, "run": run}[a.cmd](a.set)
