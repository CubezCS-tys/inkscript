"""Experiment 82, steps 1-2: the shape metric of every rebuilder on the same lines at every damage level.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python shape82.py --faces modern --n 200 --workers 2
    ... --faces traced --levels clean,heavy,spread,fill
    ... --methods learned --cl out/learned/<run>/cl   (the learned centre lines, one npz per line and level)

Writes out/shape_<faces>/rows.jsonl (one row per line x level x method, written as it goes, resumable),
summary.json, and overlays out/shape_<faces>/ov/<line>_<level>.png (first 12 lines: all methods stacked).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from multiprocessing import Pool
from pathlib import Path

os.environ.setdefault("OMP_NUM_THREADS", "1")
import cv2  # noqa: E402
import numpy as np  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import lines82 as L  # noqa: E402
import metric82 as MM  # noqa: E402
import path82 as P  # noqa: E402
from sig79 import binarise  # noqa: E402

OUT = HERE / "out"
ARGS = None


def job(a):
    i, spec, levels, methods, od, cl_dir, n_ov = a
    grey, owner, ink = L.render(spec)
    truth = MM.truth82(ink, owner, spec["text"])
    rows, tiles = [], {}
    for lv in levels:
        g = L.damaged(grey, lv, spec["seed"] + 7919 * L.LEVELS.index(lv))
        tiles[lv] = []
        for m in methods:
            try:
                cl = None
                if m.startswith("learned"):
                    f = Path(cl_dir) / f"{i:04d}_{lv}.npz"
                    if not f.exists():
                        continue
                    cl = np.load(f)["cl"]
                rec = P.rebuild(g, "learned" if m.startswith("learned") else m, ink=ink if lv == "clean" else None, cl=cl)
                sc = MM.shape_score(rec, truth, owner, spec["text"], ink)
            except Exception as e:  # noqa: BLE001
                print(i, lv, m, "error", type(e).__name__, str(e)[:120], flush=True)
                continue
            rows.append(dict(i=i, level=lv, method=m, font=Path(spec["font"]).stem, text=spec["text"], **sc))
            if i < n_ov:
                tiles[lv].append(MM.overlay(g, rec, truth, owner, spec["text"], ink, sc, scale=2,
                                            label=f"{m}  ({lv})  {Path(spec['font']).stem}"))
    if i < n_ov:
        (od / "ov").mkdir(exist_ok=True)
        for lv, T in tiles.items():
            if T:
                Wm = max(t.shape[1] for t in T)
                cv2.imwrite(str(od / "ov" / f"{i:03d}_{lv}{'_' + methods[0] if len(methods) == 1 else ''}.png"),
                            np.vstack([np.pad(t, ((0, 6), (0, Wm - t.shape[1]), (0, 0)), constant_values=255) for t in T]))
    return rows


def summary(rows):
    out = {}
    for lv in sorted({r["level"] for r in rows}, key=lambda x: L.LEVELS.index(x) if x in L.LEVELS else 9):
        for m in sorted({r["method"] for r in rows}):
            R = [r for r in rows if r["level"] == lv and r["method"] == m]
            if R:
                out[f"{lv}/{m}"] = MM.summarise(R)
    # by loop letter (all levels but clean)
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--faces", default="modern")
    ap.add_argument("--n", type=int, default=200)
    ap.add_argument("--levels", default="clean,mild,heavy,spread")
    ap.add_argument("--methods", default=",".join(P.METHODS))
    ap.add_argument("--workers", type=int, default=2)
    ap.add_argument("--cl", default="")
    ap.add_argument("--tag", default="")
    ap.add_argument("--ov", type=int, default=12)
    ap.add_argument("--lines", default="", help="take the line specs from this lines.json instead of picking them")
    ap.add_argument("--outdir", default=str(OUT))
    a = ap.parse_args()
    od = Path(a.outdir) / f"shape_{a.faces}{a.tag}"
    od.mkdir(parents=True, exist_ok=True)
    specs = json.loads(Path(a.lines).read_text(encoding="utf-8")) if a.lines else L.pick_lines(a.n, a.faces)
    (od / "lines.json").write_text(json.dumps(specs, ensure_ascii=False, indent=0))
    levels, methods = a.levels.split(","), a.methods.split(",")
    rf = od / "rows.jsonl"
    done = set()
    rows = []
    if rf.exists():
        for l in rf.open(encoding="utf-8"):
            r = json.loads(l)
            rows.append(r)
            done.add(r["i"])
    jobs = [(i, s, levels, methods, od, a.cl, a.ov) for i, s in enumerate(specs) if i not in done]
    with open(rf, "a", encoding="utf-8") as fo, Pool(a.workers, maxtasksperchild=20) as pool:
        for k, R in enumerate(pool.imap_unordered(job, jobs, chunksize=1)):
            for r in R:
                fo.write(json.dumps(r, ensure_ascii=False) + "\n")
            fo.flush()
            rows.extend(R)
            if k % 20 == 0:
                print(k, "/", len(jobs), flush=True)
    s = summary(rows)
    (od / "summary.json").write_text(json.dumps(s, ensure_ascii=False, indent=1))
    for k, v in s.items():
        print(k, v)


if __name__ == "__main__":
    main()
