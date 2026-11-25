"""Experiment 103, job B: the writer of experiments 87 and 95 as a JUDGE, unchanged, on our own crops (GPU host).

    python judge103.py styles   (out/b/style_pages.jsonl)     -> out/judge/style103.jsonl (+ _screen)
    python judge103.py check    (out/b/writer_jobs.jsonl)     -> out/judge/check103.jsonl    the absolute fit, per reading
    python judge103.py contrast (out/b/contrast_groups.jsonl) -> out/judge/contrast_j.jsonl  experiment 95's contrast
    python judge103.py smoke                                   -> 32 style lines, 20 steps: imports, programs, fonts, GPU

What is reused, imported and NOT edited (copied to the host beside this file, as experiments 87/95 shipped them):
  87_writer/{writer87.py, fit87.py, run87.py}: Batch / Params / init_items / fit / scores, run87.run_batches (the
      style and frozen modes, its batching and out-of-memory splitting), run87.local_feats, run87.lib_ok, run87.LIBS;
  95_writer3/{common95.py, contrast95.py}: contrast95.run (anchors, gap geometry, gap fits) with rule95's pick done
      locally by score103 (chamfer on the gap's columns, min over anchors, delta 0, a tie goes to the READER here,
      the place experiment 95 gave v1);
  the letter programs (95's out/programs, which hold 87's plus the glyphs 95's texts needed) and exp 78's fonts.
Settings exactly as 87 round 2 / 95: style = screen every library on the page's first style line (60 steps), the
best 2 fitted on the 3 style lines (160 steps); check = frozen style, 100 steps, WARP87=0.6; contrast = 95's
A_IT95 100 / G_IT95 60.

Our adapters (no change to the writer):
  - crops: our 96-px stored crops (experiment 77's geometry, 250 dpi) read from PNG tars (cut103.py), through
    run87.crop / contrast95.crop_of replaced at import (the functions that read their own folders);
  - text: the writer shapes a line as ONE right-to-left HarfBuzz buffer with no bidi step (B0), so a digit run would
    be written mirrored (2015 -> 5102).  writer_text() gives it the line in the order it is SEEN, right to left
    (fix103.visual_clusters reversed), with every bracket mirrored back (HarfBuzz mirrors them again in RTL).  For a
    line of Arabic words only, writer_text(t) == t.  Lines with a Latin letter are not in the B sets (pool103);
  - pages: page styles come from out/b/style_pages.jsonl (3 lines where the reader and Azure agree).
"""
from __future__ import annotations

import io
import json
import os
import sys
import tarfile
import time
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
W = Path(os.environ.get("WORK103", HERE))                 # /work on the host
B = Path(os.environ.get("B103", W / "out/b"))
J = Path(os.environ.get("J103", W / "out/judge"))
CROPS = Path(os.environ.get("CROPS103", W / "crops/b_png"))
for p in (W, W / "e87", W / "e95", HERE.parent / "87_writer", HERE.parent / "95_writer3"):
    sys.path.insert(0, str(p))

_BRACKETS = dict(zip("()[]{}<>«»‹›", ")(][}{><»«›‹"))


def writer_text(t: str) -> str:
    """The line as SEEN, right to left, for a writer that shapes one RTL buffer without bidi."""
    from fix103 import visual_clusters
    S = visual_clusters(t)[::-1]
    return "".join(_BRACKETS.get(c[0], c[0]) + c[1:] for c in S)


def wt(x: dict) -> str:
    """The writer text of a job / style line: precomputed here (pool103 'wtext'), so the host needs no fribidi."""
    return x.get("wtext") or writer_text(x["text"])


class PngStore:
    """key -> grey uint8 crop, from cut103's tars (one index per tar)."""

    def __init__(self, root: Path):
        self.where = {}
        for t in sorted(root.glob("*.tar")):
            with tarfile.open(t) as tf:
                for m in tf.getmembers():
                    if m.name.endswith(".png"):
                        self.where[m.name[:-4]] = (t, m.name)
        self._open = {}

    def gray(self, key):
        import cv2
        import numpy as np
        t, name = self.where[key]
        if t not in self._open:
            self._open = {t: tarfile.open(t)}
        b = self._open[t].extractfile(name).read()
        return cv2.imdecode(np.frombuffer(b, np.uint8), cv2.IMREAD_GRAYSCALE)


def jl(p):
    with open(p, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def _setup():
    os.environ.setdefault("WARP87", "0.6")
    os.environ.setdefault("FONTS87", str(W / "fonts"))
    os.environ.setdefault("PROG95", str(W / "programs"))
    os.environ.setdefault("RUN87", str(J))
    os.environ.setdefault("RUN95", str(J))
    os.environ.setdefault("DATA95", str(J))
    J.mkdir(parents=True, exist_ok=True)
    store = PngStore(CROPS)
    import common95
    common95.use_programs()                                 # 95's programs (87's + the glyphs 95 needed)
    import run87
    run87.crop = lambda key, where: store.gray(key)         # our crops, not 87's folders
    run87.RUN = J
    return store, run87


def styles(iters=160, screen=60, batch=32, limit=0):
    store, run87 = _setup()
    import fit87 as F
    from common95 import text_for
    dev = F.device()
    pages = jl(B / "style_pages.jsonl")[: limit or None]
    need = defaultdict(set)                                 # every text a page's lines will be written with
    for j in jl(B / "writer_jobs.jsonl"):
        need[_page(j["key"])].add(wt(j))
    jobs = []
    for p in pages:
        for lib in run87.LIBS:
            texts = [wt(x) for x in p["lines"]]
            if not all(run87.lib_ok(lib, t) for t in list(need[p["page"]]) + texts):
                continue
            g = f"{p['page']}|{lib}"
            for x, t in zip(p["lines"], texts):
                Wd = store.gray(x["key"]).shape[1]
                jobs.append(dict(id=f"{x['key']}|{lib}", key=x["key"], where="b", text=text_for(lib, t), lib=lib, W=Wd,
                                 group=g, group_key=g, page=p["page"], keep=["page"]))
    first = {}
    for j in jobs:
        first.setdefault(j["group_key"], j)
    scr = [dict(j, group=j["id"], group_key=j["id"]) for j in first.values()]
    run87.run_batches(scr, J / "style103_screen.jsonl", "style", screen, batch, dev)
    sc = defaultdict(list)
    for x in jl(J / "style103_screen.jsonl"):
        sc[x["page"]].append((x["iou"], x["lib"]))
    top = {p: {l for _, l in sorted(v, reverse=True)[:2]} for p, v in sc.items()}
    jobs = [j for j in jobs if j["lib"] in top.get(j["page"], set())]
    run87.run_batches(jobs, J / "style103.jsonl", "style", iters, batch, dev)


def _page(key):
    stem, rest = key.split("_p", 1)
    return f"{stem}_{int(rest.split('_')[0])}"


def page_styles():
    import numpy as np
    import fit87 as F
    by = defaultdict(list)
    for x in jl(J / "style103.jsonl"):
        by[(x["page"], x["lib"])].append(x)
    best = {}
    for (p, lib), v in by.items():
        m = float(np.mean([x["iou"] for x in v]))
        if p not in best or m > best[p]["iou"]:
            best[p] = dict(lib=lib, iou=m, style={k: v[0]["params"][k] for k in F.STYLE_KEYS})
    return best


def check(iters=100, batch=32):
    store, run87 = _setup()
    import fit87 as F
    from common95 import text_for
    dev = F.device()
    st = page_styles()
    jobs = []
    for j in jl(B / "writer_jobs.jsonl"):
        p = _page(j["key"])
        if p not in st:
            continue
        lib = st[p]["lib"]
        t = wt(j)
        jobs.append(dict(id=j["id"], key=j["key"], where="b", text=text_for(lib, t), lib=lib,
                         W=store.gray(j["key"]).shape[1], style=st[p]["style"], kind=j["kind"], page=p,
                         keep=["kind", "page"]))
    run87.run_batches(jobs, J / "check103.jsonl", "frozen", iters, batch, dev)


def contrast():
    store, run87 = _setup()
    import contrast95
    contrast95.crop_of = lambda key, where: store.gray(key)
    st = page_styles()
    out = []
    for g in jl(B / "contrast_groups.jsonl"):
        if g["page"] not in st:
            continue
        s = st[g["page"]]
        cands = g.get("wcands") or [writer_text(c) for c in g["cands"]]
        if len(set(cands)) < 2:                             # differ only in what the writer cannot see
            continue
        out.append(dict(g, where="b", lib=s["lib"], style=s["style"], cands=cands, cands_text=g["cands"]))
    with open(J / "cjobs_j.jsonl", "w", encoding="utf-8") as f:
        for g in out:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    contrast95.run("j")


def smoke():
    store, run87 = _setup()
    import fit87 as F
    from common95 import text_for
    dev = F.device()
    pages = jl(B / "style_pages.jsonl")[:11]
    jobs = []
    for p in pages:
        for x in p["lines"][:3]:
            t = wt(x)
            jobs.append(dict(id=f"{x['key']}|smoke", key=x["key"], where="b", text=text_for("font:amiri_Amiri-Regular", t),
                             lib="font:amiri_Amiri-Regular", W=store.gray(x["key"]).shape[1], group=p["page"],
                             group_key=p["page"], page=p["page"], keep=["page"]))
    t0 = time.time()
    run87.run_batches(jobs[:32], J / "smoke103.jsonl", "style", 20, 32, dev)
    print("SMOKE_OK", len(jobs[:32]), "lines", round(time.time() - t0, 1), "s", flush=True)


if __name__ == "__main__":
    {"styles": styles, "check": check, "contrast": contrast, "smoke": smoke}[sys.argv[1]]()
