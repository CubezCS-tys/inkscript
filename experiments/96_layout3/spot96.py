"""Experiment 96, goal 1: the eye check of the catalogue labels.  100 labelled lines (seed 96): 40 author and 20
affiliation lines of the EXTRA documents (labels that are entirely new), 20 author and 20 affiliation lines of the
pool (where Argon mostly agrees; the lines whose label the catalogue changed are drawn first).

    python spot96.py            -> out/look/spot96_{0..4}.jpg (20 crops each, numbered), out/spot96.json (the sample)
Verdicts are typed by hand into out/spot96_hand.json after looking at the pictures.
"""
from __future__ import annotations

import json
import random
import sys

import cv2
import numpy as np

from common96 import E, O94, OUT, azure_lines, guard_training, inventory_azure

sys.path.insert(0, str(E / "92_layout"))
from common92 import render_gray  # noqa: E402


def main():
    rnd = random.Random(96)
    pool = [json.loads(l) for l in open(OUT / "authors96.jsonl", encoding="utf-8")]
    extra = [json.loads(l) for l in open(OUT / "authors96_extra.jsonl", encoding="utf-8")]
    tr = {}
    for l in open(O94 / "train94.jsonl", encoding="utf-8"):
        r = json.loads(l)
        tr[r["key"]] = r
    az = inventory_azure()

    def items(R, lab, src):
        out = []
        for r in R:
            old = {x["i"]: x["fine"] for x in tr[r["key"]]["lines"]} if src == "pool" else {}
            for i, v in r["labels"].items():
                if v == lab:
                    out.append(dict(key=r["key"], i=int(i), label=v, src=src, changed=old.get(int(i)) != v,
                                    pdf=r.get("pdf") or tr[r["key"]]["pdf"], azure=r.get("azure") or az[r["stem"]],
                                    page=r["page"]))
        rnd.shuffle(out)
        out.sort(key=lambda d: not d["changed"])
        return out
    S = (items(extra, "author", "extra")[:40] + items(extra, "affiliation", "extra")[:20] +
         items(pool, "author", "pool")[:20] + items(pool, "affiliation", "pool")[:20])
    guard_training([s["key"] for s in S])
    (OUT / "look").mkdir(exist_ok=True)
    crops = []
    for n, s in enumerate(S):
        img = render_gray(s["pdf"], s["page"], dpi=150)
        L, W, H = azure_lines(s["azure"], s["page"])
        b = next(x["box"] for x in L if x["i"] == s["i"])
        sx, sy = img.shape[1] / W, img.shape[0] / H
        pad = 0.15 * (b[3] - b[1])
        c = img[max(0, int((b[1] - pad) * sy)):int((b[3] + pad) * sy), max(0, int((b[0] - pad) * sx)):int((b[2] + pad) * sx)]
        h = 44
        c = cv2.resize(c, (max(1, min(900, int(c.shape[1] * h / max(1, c.shape[0])))), h))
        canvas = np.full((h + 6, 1000), 255, np.uint8)
        canvas[3:3 + h, 1000 - c.shape[1]:] = c
        cv2.putText(canvas, f"{n:02d} {'AU' if s['label'] == 'author' else 'AF'} {s['src'][0]}", (2, 32),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, 0, 2)
        crops.append(canvas)
    for g in range(5):
        cv2.imwrite(str(OUT / "look" / f"spot96_{g}.jpg"), np.vstack(crops[20 * g:20 * g + 20]))
    json.dump([{k: v for k, v in s.items() if k not in ("pdf", "azure")} for s in S], open(OUT / "spot96.json", "w"), indent=0)
    print(len(S), sum(s["changed"] for s in S if s["src"] == "pool"))


if __name__ == "__main__":
    main()
