"""Experiment 87: the GPU runs (each writes a jsonl as it goes and resumes from it).

    python run87.py ceiling [--libs all] [--iters 200]
        stage 1's ceiling: every pool line written with its TRUE text in every letter library, all settings fitted
        on the line itself -> out/run/ceiling.jsonl; then the control: each line fitted with ANOTHER line's text of
        about the same length (same era), in its page's best library -> out/run/ceiling_ctl.jsonl
    python run87.py style SET          SET = pool | held
        a page's style: its style lines (readers agree / clean Azure) fitted together, one shared style per page and
        library, every library tried; the best library by mean IoU is the page's -> out/run/style_<SET>.jsonl
    python run87.py check SET          the checker: every test reading written in its page's style (style frozen;
        only the line's position, baseline and warp fitted) -> out/run/check_<SET>.jsonl
        SET pool / held: the planted variants (plants_<SET>.jsonl, test lines only);  judged: exp 81's judged lines,
        every candidate reading the judge saw

Style lines of a page: the first 3 of its lines in the data file (all of them when it has fewer than 4); the planted
tests use the others.  Never a held-out page in pool runs; held-out pages are only tested (no global parameter is
fitted on them: each page's own style is fitted from its own agreed text, as the checker would in use).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import zlib
from collections import defaultdict
from pathlib import Path

import cv2
import numpy as np
import torch

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import fit87 as F  # noqa: E402

OUT = HERE / "out"
D = Path(os.environ.get("DATA87", OUT / "data"))
RUN = Path(os.environ.get("RUN87", OUT / "run"))
STYLE_RUN = Path(os.environ.get("STYLE87", RUN))      # round 2 reads round 1's page styles
RUN.mkdir(parents=True, exist_ok=True)
LIMIT = int(os.environ.get("LIMIT87", 0))          # smoke tests only
MODERN = ["amiri_Amiri-Regular", "amiri_Amiri-Bold", "scheherazadenew_ScheherazadeNew-Regular",
          "scheherazadenew_ScheherazadeNew-Bold", "notonaskharabic_NotoNaskhArabic_wght", "lateef_Lateef-Regular",
          "markazitext_MarkaziText_wght", "harmattan_Harmattan-Regular", "mirza_Mirza-Regular",
          "notosansarabic_NotoSansArabic_wdth_wght", "ibmplexsansarabic_IBMPlexSansArabic-Regular",
          "vazirmatn_Vazirmatn_wght", "tajawal_Tajawal-Regular"]
TRACED = ["Mand0300y1957", "Mand0737y1937", "Mand0739y1938", "Mand0749y1951", "Mand0763y1936", "Mand0775y1949",
          "Mand0775y1958", "Mand0873y1940", "Mand0917y1927", "Mand0924y1928", "Mand0924y1936"]
LIBS = ["alqalam"] + [f"font:{m}" for m in MODERN + TRACED]
EXCL = json.loads((HERE.parent / "78_synthetic_lines/out/fonts/traced/exclude.json").read_text()) \
    if (HERE.parent / "78_synthetic_lines/out/fonts/traced/exclude.json").exists() else \
    json.loads((D / "exclude.json").read_text())
OK_SYN = __import__("re").compile(r"^[\u0621-\u064A\s\.،]+$")
ISO_NON_LEFT = set("اأإآدذرزوؤةءى") - {"ى"}


def lib_ok(lib: str, text: str) -> bool:
    """A traced face writes a text only when none of its bad letters is in it (exclude.json, as exp 82)."""
    if not lib.startswith("font:Mand"):
        return True
    e = EXCL.get(lib[5:], {})
    if e == "DROP":
        return False
    if set(text) & set(e.get("chars", "")):
        return False
    iso = set(e.get("iso", ""))
    if iso:
        for w in text.split():
            L = [c for c in w if "ء" <= c <= "ي"]
            for i, c in enumerate(L):
                pj = i > 0 and L[i - 1] not in ISO_NON_LEFT
                nj = i + 1 < len(L) and c not in ISO_NON_LEFT
                if c in iso and not pj and not nj:
                    return False
    return True


def crop(key: str, where: str):
    p = {"pool": D / "crops/pool", "held": D / "crops/held", "judge": D / "crops/judge", "synth": D / "crops/synth"}[where] / f"{key}.png"
    g = cv2.imread(str(p), 0)
    return g


def done_keys(path: Path):
    if not path.exists():
        return set()
    return {json.loads(l)["id"] for l in open(path, encoding="utf-8")}


def run_batches(jobs, out: Path, mode: str, iters: int, batch: int, dev, maps_for=None, style_of=None):
    """jobs: list of dict(id, key, where, text, lib, group, style?); fitted in width-sorted batches."""
    have = done_keys(out)
    jobs = [j for j in jobs if j["id"] not in have]
    if LIMIT:
        jobs = jobs[:LIMIT]
    print(out.name, "jobs", len(jobs), "(done before:", len(have), ")", flush=True)
    if mode == "style":                             # whole page-and-library groups, groups of similar width together
        G = defaultdict(list)
        for j in jobs:
            G[j["group_key"]].append(j)
        groups = sorted(G.values(), key=lambda g: max(x["W"] for x in g))
    else:
        jobs.sort(key=lambda j: j["W"])
    mp = out.with_suffix(".maps")
    mp.mkdir(exist_ok=True)
    t0 = time.time()
    n = 0
    f = open(out, "a", encoding="utf-8")
    batches = []
    if mode == "style":
        cur = []
        for g in groups:
            if cur and len(cur) + len(g) > batch:
                batches.append(cur)
                cur = []
            cur = cur + g
        if cur:
            batches.append(cur)
    else:
        batches = [jobs[i:i + batch] for i in range(0, len(jobs), batch)]
    def process(B):
        items = [dict(grey=crop(j["key"], j["where"]), text=j["text"], lib=j["lib"], group=j.get("group", k))
                 for k, j in enumerate(B)]
        bt = F.Batch(items, dev)
        if mode == "frozen":
            P = F.Params(bt, style_init=[j["style"] for j in B])
            F.init_items(bt, P, fix_size=True)
            F.fit(bt, P, mode="frozen", iters=iters)
        else:
            P = F.Params(bt)
            F.init_items(bt, P)
            F.fit(bt, P, mode="free", iters=iters)
        sc = F.scores(bt, P, need_maps=True)
        for k, (j, s) in enumerate(zip(B, sc)):
            loc = local_feats(s, bt.T[k, :, :bt.Wd[k]].cpu().numpy(), float(P.style["size"][bt.group[k]].detach()))
            row = dict(id=j["id"], key=j["key"], lib=j["lib"], text=j["text"],
                       **{a: (round(b, 4) if isinstance(b, float) else b) for a, b in s.items()
                          if a in ("iou", "recall", "precision", "chamfer", "n_missing") or a.startswith(("word_", "glyph_"))},
                       **loc, params=F.params_of(P, bt, k), **{a: j[a] for a in j.get("keep", [])})
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            if maps_for and maps_for(j):
                np.savez_compressed(mp / f"{j['id'].replace('/', '_').replace('|', '__')}.npz",
                                    written=(255 * s["written"]).astype(np.uint8),
                                    target=bt.T[k, :, :bt.Wd[k]].cpu().numpy().astype(np.uint8))
        f.flush()

    def safe(B):
        try:
            process(B)
        except torch.cuda.OutOfMemoryError:
            torch.cuda.empty_cache()
            if len(B) == 1 or (mode == "style" and len({j["group_key"] for j in B}) == 1):
                raise
            if mode == "style":                   # split between groups
                keys = list(dict.fromkeys(j["group_key"] for j in B))
                h = set(keys[:len(keys) // 2])
                safe([j for j in B if j["group_key"] in h])
                safe([j for j in B if j["group_key"] not in h])
            else:
                safe(B[:len(B) // 2])
                safe(B[len(B) // 2:])
            print("  (out of memory: batch split)", flush=True)

    def guarded(B):
        try:
            safe(B)
        except torch.cuda.OutOfMemoryError:
            raise
        except Exception as e:                    # noqa: BLE001  one bad line must not stop the run: retry singly
            if len(B) == 1:
                print("  skipped", B[0]["id"], type(e).__name__, str(e)[:120], flush=True)
                return
            for j in B:
                guarded([j])

    for B in batches:
        guarded(B)
        n += len(B)
        el = time.time() - t0
        print(f"{out.name} {n}/{len(jobs)} {el / 60:.1f} min ({el / max(1, n):.2f} s/job)", flush=True)
    f.close()


def local_feats(s: dict, T: np.ndarray, size: float) -> dict:
    """Where the writing and the ink disagree: per column, the real ink with no writing near it (missing) and the
    writing with no ink near it (invented); the worst window of 0.6 em and of 1.5 em, each as a share of the ink (or
    writing) in it, and in units of the line's stroke area."""
    t = T > 0.5
    w = s["written"] > 0.5
    miss = (t & (s["dist_to_writing"] > 1.5)).sum(0).astype(np.float32)
    inv = (w & (s["dist_to_ink"] > 1.5)).sum(0).astype(np.float32)
    tc = t.sum(0).astype(np.float32)
    wc = w.sum(0).astype(np.float32)
    out = {}
    for nm, em in (("s", 0.6), ("l", 1.5)):
        k = max(3, int(round(em * size)))
        ker = np.ones(k, np.float32)
        cm = np.convolve(miss, ker, "same")
        ci = np.convolve(inv, ker, "same")
        ct = np.convolve(tc, ker, "same")
        cw = np.convolve(wc, ker, "same")
        out[f"miss_{nm}"] = round(float((cm / np.maximum(ct, 0.25 * k * 2)).max()), 4)
        out[f"inv_{nm}"] = round(float((ci / np.maximum(cw, 0.25 * k * 2)).max()), 4)
        out[f"missa_{nm}"] = round(float(cm.max()) / max(1.0, size * size * 0.05), 4)
        out[f"inva_{nm}"] = round(float(ci.max()) / max(1.0, size * size * 0.05), 4)
    out["miss_all"] = round(float(miss.sum() / max(1.0, tc.sum())), 4)
    out["inv_all"] = round(float(inv.sum() / max(1.0, wc.sum())), 4)
    return out


# ------------------------------------------------------------------------------------------------ the runs
def synth(a, dev):
    """Rung 0: font-rendered lines fitted with that font's own programs, and with AlQalam's."""
    P = [json.loads(l) for l in open(D / "synth.jsonl", encoding="utf-8")]
    jobs = []
    for r in P:
        for lib in (r["lib"], "alqalam"):
            jobs.append(dict(id=f"{r['key']}|{lib}", key=r["key"], where="synth", text=r["text"], lib=lib, W=r["W"],
                             era="synthetic", keep=["era"]))
    run_batches(jobs, RUN / "ceiling_synth.jsonl", "free", a.iters, a.batch, dev,
                maps_for=lambda j: zlib.crc32(j["key"].encode()) % 5 == 0)


def ceiling(a, dev):
    P = [json.loads(l) for l in open(D / "pool.jsonl", encoding="utf-8")]
    libs = LIBS if a.libs == "all" else a.libs.split(",")
    if os.environ.get("LOOK87"):                  # a first look: about one line in seven, every era
        P = [r for r in P if zlib.crc32(r["key"].encode()) % 7 == 0]
    jobs = []
    for r in P:
        for lib in libs:
            if lib_ok(lib, r["text"]):
                jobs.append(dict(id=f"{r['key']}|{lib}", key=r["key"], where="pool", text=r["text"], lib=lib, W=r["W"],
                                 era=r["era"], keep=["era"]))
    if a.screen:                                   # every library briefly, then the best 3 of each line in full
        run_batches(jobs, RUN / "ceiling_screen.jsonl", "free", a.screen, a.batch, dev)
        sc = defaultdict(list)
        for x in map(json.loads, open(RUN / "ceiling_screen.jsonl", encoding="utf-8")):
            sc[x["key"]].append((x["iou"], x["lib"]))
        top = {k: {l for _, l in sorted(v, reverse=True)[:3]} | {"alqalam"} for k, v in sc.items()}
        jobs = [j for j in jobs if j["lib"] in top.get(j["key"], set())]
    run_batches(jobs, RUN / "ceiling.jsonl", "free", a.iters, a.batch, dev,
                maps_for=lambda j: zlib.crc32(j["key"].encode()) % 10 == 0 or j["lib"] == "alqalam")
    # control: another line's text, same era, nearest length (never the same page), the page's best library
    rows = [json.loads(l) for l in open(RUN / "ceiling.jsonl", encoding="utf-8")]
    by = defaultdict(list)
    for x in rows:
        by[(x["key"].rsplit("_l", 1)[0], x["lib"])].append(x["iou"])
    best = {}
    for (pg, lib), v in by.items():
        if pg not in best or np.mean(v) > best[pg][1]:
            best[pg] = (lib, float(np.mean(v)))
    jobs = []
    for r in P:
        pg = f"{r['stem']}_p{r['page']:03d}"
        others = [o for o in P if o["era"] == r["era"] and o["stem"] != r["stem"]]
        o = min(others, key=lambda o: (abs(len(o["text"]) - len(r["text"])), o["key"]))
        if pg not in best:
            continue
        lib = best[pg][0]
        if not lib_ok(lib, o["text"]):
            continue
        jobs.append(dict(id=f"{r['key']}|ctl", key=r["key"], where="pool", text=o["text"], lib=lib, W=r["W"],
                         era=r["era"], keep=["era"]))
    run_batches(jobs, RUN / "ceiling_ctl.jsonl", "free", a.iters, a.batch, dev)
    # the true text with the page's library (to compare with the control on equal terms)


def _pages(which: str):
    """page -> list of its lines in file order (dict key, text, where, W)."""
    pg = defaultdict(list)
    if which == "pool":
        for l in open(D / "pool.jsonl", encoding="utf-8"):
            r = json.loads(l)
            pg[f"{r['stem']}_{r['page']}"].append(dict(key=r["key"], text=r["text"], where="pool", W=r["W"], era=r["era"]))
    else:
        for l in open(D / "held.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r["role"] == "fit":
                g = crop(r["key"], "held")
                if g is None:
                    continue
                pg[f"{r['stem']}_{r['page']}"].append(dict(key=r["key"], text=r["text"], where="held", W=g.shape[1], era=r["era"]))
    return pg


def split_page(L, n_test: int = 0):
    """(style lines, test lines): the first 3 lines for the style, the next ones (at most n_test, 0 = all) tested."""
    if len(L) < 4:
        return L, []
    return L[:3], (L[3:3 + n_test] if n_test else L[3:])


def needed_texts(which: str):
    """page -> every text the checker will write on it (style lines, planted variants, judged candidates)."""
    need = defaultdict(set)
    pg = _pages(which)
    plants = {json.loads(l)["key"]: json.loads(l) for l in open(D / f"plants_{which}.jsonl", encoding="utf-8")}
    for p, L in pg.items():
        S, T = split_page(L, 2 if which == "held" else 0)
        need[p].update(x["text"] for x in S)
        for x in T:
            need[p].update(plants[x["key"]]["variants"].values())
    if which == "held":
        S = judged_shown()
        for l in open(D / "held.jsonl", encoding="utf-8"):
            r = json.loads(l)
            if r["role"] == "judged" and r["key"] in S:
                need[f"{r['stem']}_{r['page']}"].update(S[r["key"]])
    return need


def judged_shown():
    """key -> the candidate readings the judge saw (exp 81), plus any extra candidates."""
    X = HERE.parent / "81_heldout_scale/out/judge"
    S = {}
    if X.exists():
        for f in ("sample.jsonl", "calib.jsonl"):
            for l in open(X / f, encoding="utf-8"):
                d = json.loads(l)
                S[d["key"]] = list(d["shown"])
    else:
        S = {json.loads(l)["key"]: json.loads(l)["shown"] for l in open(D / "judged_shown.jsonl", encoding="utf-8")}
    if (D / "judged_extra.jsonl").exists():
        for l in open(D / "judged_extra.jsonl", encoding="utf-8"):
            d = json.loads(l)
            S[d["key"]] = list(dict.fromkeys(S.get(d["key"], []) + d["cands"]))
    return S


def style(a, dev):
    pg = _pages(a.set)
    need = needed_texts(a.set)
    libs = LIBS if a.libs == "all" else a.libs.split(",")
    if a.set == "held" and a.libs == "all" and (RUN / "style_pool.jsonl").exists():
        # held-out pages try only the libraries that won a POOL page (plus AlQalam): chosen on pool pages alone
        won = {v["lib"] for v in page_styles("pool").values()}
        libs = [l for l in LIBS if l in won or l == "alqalam"]
        print("held libraries (pool winners):", libs, flush=True)
    jobs = []
    for p, L in pg.items():
        S, _ = split_page(L)
        for lib in libs:
            if not all(lib_ok(lib, t) for t in need[p]):
                continue
            g = f"{p}|{lib}"
            for x in S:
                jobs.append(dict(id=f"{x['key']}|{lib}", key=x["key"], where=x["where"], text=x["text"], lib=lib,
                                 W=x["W"], group=g, group_key=g, page=p, keep=["page"]))
    if a.screen:                                   # each library on the page's first style line, then the best 2 in full
        first = {}
        for j in jobs:
            first.setdefault(j["group_key"], j)
        scr = [dict(j, group=j["id"], group_key=j["id"]) for j in first.values()]
        run_batches(scr, RUN / f"style_{a.set}_screen.jsonl", "style", a.screen, a.batch, dev)
        sc = defaultdict(list)
        for x in map(json.loads, open(RUN / f"style_{a.set}_screen.jsonl", encoding="utf-8")):
            sc[x["page"]].append((x["iou"], x["lib"]))
        top = {p: {l for _, l in sorted(v, reverse=True)[:2]} for p, v in sc.items()}
        jobs = [j for j in jobs if j["lib"] in top.get(j["page"], set())]
    run_batches(jobs, RUN / f"style_{a.set}.jsonl", "style", a.iters, a.batch, dev)


def page_styles(which: str):
    rows = [json.loads(l) for l in open(STYLE_RUN / f"style_{which}.jsonl", encoding="utf-8")]
    by = defaultdict(list)
    for x in rows:
        by[(x["page"], x["lib"])].append(x)
    best = {}
    for (p, lib), v in by.items():
        m = float(np.mean([x["iou"] for x in v]))
        if p not in best or m > best[p]["iou"]:
            st = {k: v[0]["params"][k] for k in F.STYLE_KEYS}
            best[p] = dict(lib=lib, iou=m, style=st)
    return best


def check(a, dev):
    which = a.set
    jobs = []
    if which in ("pool", "held"):
        styles = page_styles(which)
        pg = _pages(which)
        plants = {json.loads(l)["key"]: json.loads(l) for l in open(D / f"plants_{which}.jsonl", encoding="utf-8")}
        for p, L in pg.items():
            if p not in styles:
                continue
            _, T = split_page(L, 2 if which == "held" else 0)
            for x in T:
                for kind, txt in plants[x["key"]]["variants"].items():
                    lib = styles[p]["lib"]
                    jobs.append(dict(id=f"{x['key']}|{kind}", key=x["key"], where=x["where"], text=txt, lib=lib,
                                     W=x["W"], style=styles[p]["style"], kind=kind, page=p, era=x["era"],
                                     keep=["kind", "page", "era"]))
    else:                                            # judged held-out lines, every candidate the judge saw
        styles = page_styles("held")
        H = [json.loads(l) for l in open(D / "held.jsonl", encoding="utf-8")]
        S = judged_shown()
        for r in H:
            if r["role"] != "judged":
                continue
            p = f"{r['stem']}_{r['page']}"
            if p not in styles:
                continue
            g = crop(r["key"], "judge")
            if g is None:
                continue
            cands = S.get(r["key"], [])
            for ci, txt in enumerate(cands):
                lib = styles[p]["lib"]
                jobs.append(dict(id=f"{r['key']}|c{ci}", key=r["key"], where="judge", text=txt, lib=lib, W=g.shape[1],
                                 style=styles[p]["style"], cand=ci, page=p, era=r["era"],
                                 keep=["cand", "page", "era"]))
    run_batches(jobs, RUN / f"check_{which}.jsonl", "frozen", a.iters, a.batch, dev,
                maps_for=lambda j: zlib.crc32(j["key"].encode()) % 25 == 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd")
    ap.add_argument("set", nargs="?", default="pool")
    ap.add_argument("--libs", default="all")
    ap.add_argument("--iters", type=int, default=200)
    ap.add_argument("--batch", type=int, default=24)
    ap.add_argument("--screen", type=int, default=0, help="iterations of the library screening (0: none)")
    a = ap.parse_args()
    dev = F.device()
    print("device", dev, torch.__version__, flush=True)
    {"synth": synth, "ceiling": ceiling, "style": style, "check": check}[a.cmd](a, dev)
