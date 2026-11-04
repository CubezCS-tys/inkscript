"""Experiment 69, step 3b: contact sheets of the units to judge on the scan.

    sheets69.py TAG_A TAG_B [...]   -> out/sheets/sheet_NN.jpg + .txt  (units where the conditions differ and
                                       experiment 66 did not judge the word; already-labelled units skipped)
Each row: the word at up to 7x (left) and its line in context (right), Azure's word box in red; the .txt lists the
row's number, Azure's text and each condition's text for the unit.
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np

import common69 as C
from units69 import FOLD
from sample66 import page_image, crop_box  # noqa: E402  (experiment 66)


def todo(tags):
    lab = labels()
    out = []
    for u in C.jlines(C.UNITS):
        if u["judged"] and u["judged"]["lab"] in "GBM" or u["uid"] in lab:
            continue
        o = {t: u["outs"][t].translate(FOLD) for t in u["outs"]}
        keys = [t for t in o if t != "saved"]
        if len({o[t] for t in keys}) > 1:
            out.append(u)
    return out


def labels() -> dict:
    f = C.OUT / "labels69.tsv"
    out = {}
    if f.exists():
        for ln in open(f, encoding="utf-8"):
            if ln.strip() and not ln.startswith("#"):
                uid, truth, *why = ln.rstrip("\n").split("\t")
                out[uid] = (truth, why[0] if why else "")
    return out


def main(tags):
    U = todo(tags)
    dst = C.SHEETS
    dst.mkdir(parents=True, exist_ok=True)
    W = 1500
    for s0 in range(0, len(U), 8):
        rows, txt = [], []
        for k, u in enumerate(U[s0:s0 + 8], s0 + 1):
            r = dict(u)
            img = cv2.imread(str(page_image(r)), cv2.IMREAD_COLOR)
            if not u["box"]:
                txt.append(f"#{k} NO BOX {u['uid']}")
                continue
            x0, y0, x1, y1 = crop_box(r, img)
            h = max(20, y1 - y0)
            H, Wp = img.shape[:2]
            cx0, cx1 = max(0, x0 - 6 * h), min(Wp, x1 + 6 * h)
            cy0, cy1 = max(0, y0 - int(1.3 * h)), min(H, y1 + int(1.3 * h))
            crop = img[cy0:cy1, cx0:cx1].copy()
            cv2.rectangle(crop, (x0 - cx0 - 3, y0 - cy0 - 3), (x1 - cx0 + 3, y1 - cy0 + 3), (0, 0, 255), 1)
            sc = min(150 / crop.shape[0], 640 / crop.shape[1], 2.5)
            crop = cv2.resize(crop, (int(crop.shape[1] * sc), int(crop.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
            zm = img[max(0, y0 - h // 3):min(H, y1 + h // 3), max(0, x0 - h // 2):min(Wp, x1 + h // 2)]
            zs = min(240 / zm.shape[0], 740 / zm.shape[1], 7.0)
            zm = cv2.resize(zm, (int(zm.shape[1] * zs), int(zm.shape[0] * zs)), interpolation=cv2.INTER_CUBIC)
            row = np.full((max(crop.shape[0], zm.shape[0]) + 10, W, 3), 255, np.uint8)
            row[5:5 + zm.shape[0], 60:60 + zm.shape[1]] = zm
            row[5:5 + crop.shape[0], W - 5 - crop.shape[1]:W - 5] = crop
            cv2.putText(row, str(k), (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 0, 0), 2)
            row[-2:, :] = 160
            rows.append(row)
            outs = "  ".join(f"{t}«{v}»" for t, v in u["outs"].items() if not t.endswith("+g"))
            g = "  ".join(f"{t}«{v}»" for t, v in u["outs"].items() if t.endswith("+g"))
            txt.append(f"#{k} {u['uid']} [{u['stratum']}{' poor' if u['poor'] else ''}] conf={u['confs']}\n"
                       f"   AZURE «{u['azure']}»  {outs}\n   guard: {g}\n   line: {u['text']}")
        n = s0 // 8 + 1
        if rows:
            cv2.imwrite(str(dst / f"sheet_{n:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 90])
        (dst / f"sheet_{n:02d}.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print(len(U), "units to judge ->", dst)


if __name__ == "__main__":
    main(sys.argv[1:])
