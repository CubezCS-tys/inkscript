"""Experiment 75: re-order an existing run's regions with a plain right-to-left column rule (code only, no inference).

    ../../.venv/bin/python rtl_order.py --dataset doc3 --page PAGE --run RUN

Rule: a region is "in columns" when another region in the other half of the page overlaps it vertically; column
regions are read right column first (top to bottom), then the left column; every other region (full-width text,
footnotes, page furniture) follows in top-to-bottom order after the column block above it.  Stored as a DERIVED run
(engine of the source run + "_rtl"), labelled as such; the source run is untouched.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from labocr import runs as R  # noqa: E402

ROOT = HERE / "out" / "data"


def rtl_order(blocks, width):
    boxed = [b for b in blocks if b.box is not None]
    mid = width / 2

    def side(b):
        return "R" if (b.box[0] + b.box[2]) / 2 > mid else "L"

    def overl(a, b):
        return min(a.box[3], b.box[3]) - max(a.box[1], b.box[1]) > 0

    col = {b.block_id for b in boxed if b.box[2] - b.box[0] < 0.6 * width
           and any(o is not b and side(o) != side(b) and o.box[2] - o.box[0] < 0.6 * width and overl(o, b) for o in boxed)}
    cols = [b for b in boxed if b.block_id in col]
    top = min((b.box[1] for b in cols), default=0)
    bottom = max((b.box[3] for b in cols), default=0)
    above = sorted([b for b in boxed if b.block_id not in col and b.box[3] <= top], key=lambda b: b.box[1])
    colseq = sorted([b for b in cols if side(b) == "R"], key=lambda b: b.box[1]) + \
        sorted([b for b in cols if side(b) == "L"], key=lambda b: b.box[1])
    rest = sorted([b for b in boxed if b.block_id not in col and b.box[3] > top], key=lambda b: b.box[1])
    seq = above + colseq + rest
    return seq + [b for b in blocks if b.box is None]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True)
    ap.add_argument("--page", required=True)
    ap.add_argument("--run", required=True)
    a = ap.parse_args()
    p = R.load_predictions(ROOT, a.run)[a.page]
    seq = rtl_order(p.result.blocks, p.width)
    for i, b in enumerate(seq):
        b.order, b.order_source = i, "right-to-left column rule (rtl_order.py) over the source run's regions"
    p.result.page_text = "\n".join(b.raw_text for b in seq if b.raw_text)
    p.result.settings_used = dict(p.result.settings_used, derived_from=a.run, reorder="rtl_order.py column rule")
    p.engine, p.variant = p.engine, p.variant + "_rtl"
    p.result.blocks = seq
    rid = R.import_run(ROOT, a.dataset, p.engine, p.variant, [p], imported=False,
                       note=f"DERIVED: {a.run} re-ordered by a right-to-left column rule (code only, no new inference)",
                       settings={"derived_from": a.run, "rule": "rtl_order.py"})
    print(rid, [b.block_id for b in seq])


if __name__ == "__main__":
    main()
