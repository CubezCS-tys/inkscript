"""How well a line finder finds the lines of the test pages, against Azure's lines (silver geometry).

    nice out/env/bin/python segeval.py TAG [SEGMODEL]     (no SEGMODEL: kraken's default blla model)
Pages: out/seg/test/*.xml (experiment 19's scanned pages, 150 dpi; seg_data.py). Predictions are cached in
out/segeval/TAG/<page>.json. Matching: a found baseline belongs to the Azure line whose polygon holds most of its
points (at least half). Per Azure line:
  found   exactly one baseline, and that baseline belongs to no other line
  split   two or more baselines
  merged  its baseline also runs through another Azure line (a fifth of its points or more there)
  missed  no baseline
Baselines on no Azure line are "extra" (often real ink Azure left out: ornaments, page furniture, stamps).
Baseline accuracy, on found lines: the mean vertical distance between the found baseline and the one seg_data.py
put on the ink, over their common width, as a share of the line's height; and the share of the line's width covered.
-> out/segeval/TAG.json
"""
import json, os, re, sys
from pathlib import Path
import numpy as np
from shapely.geometry import Point, Polygon
sys.path.insert(0, str(Path(__file__).resolve().parent))
from seg_look import read_xml

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out")


def interp(bl, x):
    xs = [p[0] for p in bl]; ys = [p[1] for p in bl]
    o = np.argsort(xs)
    return np.interp(x, np.array(xs)[o], np.array(ys)[o])


def sample(bl, n=20):
    pts = []
    for (x0, y0), (x1, y1) in zip(bl, bl[1:]):
        for t in np.linspace(0, 1, n, endpoint=False):
            pts.append((x0 + t * (x1 - x0), y0 + t * (y1 - y0)))
    pts.append(tuple(bl[-1]))
    return pts


def score_page(silver, pred):
    polys = [Polygon(l["boundary"]).buffer(2) for l in silver]
    owner = []; touches = []
    for p in pred:
        pts = [Point(q) for q in sample(p["baseline"])]
        frac = [sum(pg.contains(q) for q in pts) / len(pts) for pg in polys]
        k = int(np.argmax(frac)) if frac else -1
        owner.append(k if frac and frac[k] >= 0.5 else None)
        touches.append({i for i, f in enumerate(frac) if f >= 0.2})
    res = dict(silver=len(silver), pred=len(pred), found=0, split=0, merged=0, missed=0, extra=sum(o is None for o in owner),
               dist=[], cover=[])
    for i, s in enumerate(silver):
        mine = [j for j, o in enumerate(owner) if o == i]
        merged_in = any(i in touches[j] and len(touches[j]) >= 2 for j in range(len(pred)))
        if not mine and not merged_in:
            res["missed"] += 1
        elif merged_in:
            res["merged"] += 1
        elif len(mine) >= 2:
            res["split"] += 1
        else:
            res["found"] += 1
            pb = pred[mine[0]]["baseline"]; sb = s["baseline"]
            lo = max(min(q[0] for q in pb), min(q[0] for q in sb)); hi = min(max(q[0] for q in pb), max(q[0] for q in sb))
            ys = [q[1] for q in s["boundary"]]; h = max(ys) - min(ys)
            if hi > lo and h > 0:
                xs = np.linspace(lo, hi, 20)
                res["dist"].append(float(np.mean(np.abs(interp(pb, xs) - interp(sb, xs))) / h))
                res["cover"].append(float((hi - lo) / max(max(q[0] for q in sb) - min(q[0] for q in sb), 1)))
    return res


if __name__ == "__main__":
    tag = sys.argv[1]; model = sys.argv[2] if len(sys.argv) > 2 else None
    import torch
    torch.set_num_threads(4)
    from PIL import Image
    from kraken.tasks.segmentation import SegmentationTaskModel
    from kraken.configs import SegmentationInferenceConfig
    net = None
    d = OUT / "segeval" / tag; d.mkdir(parents=True, exist_ok=True)
    tot = {}; per = {}
    for xml in sorted((OUT / "seg" / "test").glob("*.xml"))[: int(os.environ.get("LIMIT", 10**6))]:
        img, silver = read_xml(xml)
        pj = d / f"{xml.stem}.json"
        if not pj.exists():
            if net is None:
                net = (SegmentationTaskModel.load_model(model), SegmentationInferenceConfig())
            seg = net[0].predict(Image.open(img), net[1])
            json.dump(dict(lines=[dict(baseline=[list(map(int, p)) for p in l.baseline], boundary=[list(map(int, p)) for p in l.boundary])
                                  for l in seg.lines]), open(pj, "w"))
        pred = json.load(open(pj))["lines"]
        r = score_page(silver, pred); per[xml.stem] = {k: v for k, v in r.items() if k not in ("dist", "cover")}
        for k, v in r.items():
            tot[k] = tot.get(k, [] if isinstance(v, list) else 0) + v
        print(xml.stem, {k: v for k, v in r.items() if not isinstance(v, list)}, flush=True)
    s = tot["silver"]
    summ = {k: tot[k] for k in ("silver", "pred", "found", "split", "merged", "missed", "extra")}
    summ.update({f"{k}_share": tot[k] / s for k in ("found", "split", "merged", "missed")},
                baseline_dist_median=float(np.median(tot["dist"])), baseline_dist_mean=float(np.mean(tot["dist"])),
                cover_median=float(np.median(tot["cover"])), within_quarter_height=float(np.mean(np.array(tot["dist"]) < 0.25)))
    json.dump(dict(summary=summ, pages=per), open(OUT / "segeval" / f"{tag}.json", "w"), indent=1)
    print(json.dumps(summ, indent=1))
