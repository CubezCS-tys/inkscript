"""Experiment 96, goal 3 (no new model): GAP FILL for experiment 94's line finder.  Experiment 94 keeps boxes with
conf >= 0.25.  Several of the judged lines it misses are boxed well (IoU >= 0.94 with Azure's line) at lower
confidence.  Gap fill keeps, in addition, every box with conf >= LO that overlaps no kept box (intersection under
30% of either box's area), de-duplicated among themselves (IoU > 0.5).  Only the added boxes are cut (experiment
92/94's cut, unchanged) and read; the 0.25 boxes keep experiment 94's crops and reads.

    python cut96.py dev|test LO   -> out/crops48[dev]/ln94g<LO>-<page>.tar (added boxes only), out/own94[dev]g<LO>.jsonl
                                     (all boxes, experiment 94's rows first); then read96 + e2e96
"""
from __future__ import annotations

import json
import sys
import tarfile

from common96 import E, E92, O94, OUT, area, assert_not_locked, azure_lines, inter, iou

sys.path.insert(0, str(E / "94_layout2"))
from cut94 import add, dev_pages, own_boxes, poly_of  # noqa: E402
from common92 import render_gray  # noqa: E402

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import cut_line  # noqa: E402


def gap_fill(pred, W, H, lo):
    keep = own_boxes(pred, W, H)
    extra = []
    for b, c, s in sorted(own_boxes(pred, W, H, conf=lo), key=lambda t: -t[2]):
        if s >= 0.25:
            continue
        if any(inter(b, k[0]) > 0.3 * min(area(b), area(k[0])) for k in keep + extra):
            continue
        extra.append((b, c, s))
    return keep, extra


def main(which, lo):
    import cv2
    cv2.setNumThreads(1)
    lo = float(lo)
    tag = f"g{lo:g}".replace(".", "")
    if which == "test":
        pages = [json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")]
        pred = json.load(open(O94 / "pred94_line.json"))
        D, base, meta = OUT / "crops48", O94 / "own94.jsonl", OUT / f"own94{tag}.jsonl"
    else:
        pages = dev_pages()
        pred = json.load(open(O94 / "pred94_line_val.json"))
        D, base, meta = OUT / "crops48dev", O94 / "own94dev.jsonl", OUT / f"own94dev{tag}.jsonl"
    assert_not_locked([p["key"] for p in pages])
    D.mkdir(parents=True, exist_ok=True)
    rows0 = {}
    for l in open(base, encoding="utf-8"):
        d = json.loads(l)
        rows0.setdefault(d["page"], []).append(d)
    n_add = 0
    with open(meta, "w", encoding="utf-8") as fm:
        for p in pages:
            k = p["key"]
            if k not in pred or k not in rows0:
                continue
            lines, W, H = azure_lines(p["azure"], p["page"])
            keep, extra = gap_fill(pred[k], W, H, lo)
            assert len(keep) == len(rows0[k])
            for r in rows0[k]:
                fm.write(json.dumps(r) + "\n")
            if not extra:
                continue
            img = render_gray(p["pdf"], p["page"])
            sx, sy = img.shape[1] / W, img.shape[0] / H
            with tarfile.open(D / f"ln94{tag}-{k}.tar", "w") as t:
                for j, (b, c, s) in enumerate(extra, len(keep)):
                    crop, _ = cut_line(img, poly_of(b, c), sx, sy, test=True)
                    key = f"{k}_ln{j:03d}"
                    if crop is not None:
                        add(t, key, crop)
                    fm.write(json.dumps(dict(key=key, page=k, src=f"ln94{tag}", j=j, box=[round(v, 5) for v in b],
                                             cls=c, conf=s, cut=crop is not None, added=True)) + "\n")
                    n_add += 1
    print("CUT96_DONE", which, tag, "added", n_add, flush=True)


if __name__ == "__main__":
    main(*sys.argv[1:])
