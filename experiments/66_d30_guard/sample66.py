"""Experiment 66, phase 1: a stratified sample of Gemini's fixes, and contact sheets of their ink to judge by eye.

    sample66.py pick      out/sample.jsonl (stratum, weight, split: tune / test by article)
    sample66.py sheets    out/sheets/sheet_NN.jpg + .txt (10 fixes a sheet: the line around the word, Azure's
                          words of the fix boxed in red; the listing gives Azure's reading -> Gemini's and why)
Strata are over the edit kinds the guard could refuse (not d30guard43.SAFE) plus one stratum of the SAFE kinds.
"""
from __future__ import annotations

import hashlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

import common66 as C

C.e43_path()
import d30guard43 as G  # noqa: E402

N = {"A_sure_real_to_nonword": 45, "B_unsure_real_to_nonword": 40, "C_sure_real_to_real": 45,
     "D_sure_nonword": 35, "E_unsure_real_to_real": 40, "F_unsure_nonword": 35, "G_safe_kinds": 30}


def real(ks):
    ks = [k for k in ks if k is not None]
    return None if not ks else all(ks)


def stratum(r):
    if r["cls"] in G.SAFE:
        return "G_safe_kinds"
    cs = [x for x in r["confs"] if x is not None]
    if not cs or not r["found"]:
        return None
    sure = min(cs) >= 0.95
    fr, tr = real(r["from_known"]), real(r["to_known"])
    if fr and tr is False:
        return "A_sure_real_to_nonword" if sure else "B_unsure_real_to_nonword"
    if fr and tr:
        return "C_sure_real_to_real" if sure else "E_unsure_real_to_real"
    if fr is False:
        return "D_sure_nonword" if sure else "F_unsure_nonword"
    return None


def split_of(stem):
    return "test" if int(hashlib.sha1(stem.encode()).hexdigest(), 16) % 5 < 2 else "tune"


def pick():
    R = list(C.jlines(C.OUT / "fixes.jsonl"))
    pools = {}
    for i, r in enumerate(R):
        s = stratum(r)
        if s and (s != "G_safe_kinds" or (r["found"] and r["confs"])):
            pools.setdefault(s, []).append(i)
    rng = random.Random(66)
    out = []
    for s, n in N.items():
        ids = pools.get(s, [])
        take = sorted(rng.sample(ids, min(n, len(ids))))
        for i in take:
            out.append(dict(R[i], idx=i, stratum=s, pop=len(ids), weight=len(ids) / len(take), split=split_of(R[i]["stem"])))
    rng.shuffle(out)
    for k, r in enumerate(out, 1):
        r["sid"] = k
    with open(C.OUT / "sample.jsonl", "w", encoding="utf-8") as f:
        for r in out:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print({s: len(v) for s, v in pools.items()}, Counter(r["split"] for r in out), len(out))


def page_image(r):
    if r["run"] == "v2_55":
        return C.REPO / "experiments" / "41_azure_structure" / "out" / "pages" / f"{r['stem']}_p{r['page']:03d}.jpg"
    return C.E43 / "out" / "pages" / f"{r['stem']}_p{r['page']:03d}.jpg"


_ARTS = {}


def frame_scale(r, img):
    """Azure's word boxes are in a 300 dpi frame for inch pages, in Azure's own pixels for pixel pages: the factor
    from that frame to the page image."""
    import run43
    from masters43 import ST
    if not _ARTS:
        for run, (_, which) in C.RUNS.items():
            for a in run43.articles(which):
                _ARTS.setdefault(a["stem"], a)
    pg = ST.azure(_ARTS[r["stem"]])["pages"][r["page"] - 1]
    s = 300.0 if pg.get("unit", "inch") == "inch" else 1.0
    return img.shape[1] / (pg["width"] * s)


def crop_box(r, img):
    f = frame_scale(r, img)
    return [int(v * f) for v in r["box"]]


def sheets(src=None, dst=None):
    import cv2
    import numpy as np
    S = list(C.jlines(src or C.OUT / "sample.jsonl"))
    dst = dst or C.OUT / "sheets"
    dst.mkdir(parents=True, exist_ok=True)
    W = 1500
    for s0 in range(0, len(S), 10):
        rows, txt = [], []
        for r in S[s0:s0 + 10]:
            img = cv2.imread(str(page_image(r)), cv2.IMREAD_COLOR)
            x0, y0, x1, y1 = crop_box(r, img)
            h = max(20, y1 - y0)
            H, Wp = img.shape[:2]
            cx0, cx1 = max(0, x0 - 6 * h), min(Wp, x1 + 6 * h)
            cy0, cy1 = max(0, y0 - int(1.3 * h)), min(H, y1 + int(1.3 * h))
            crop = img[cy0:cy1, cx0:cx1].copy()
            cv2.rectangle(crop, (x0 - cx0 - 3, y0 - cy0 - 3), (x1 - cx0 + 3, y1 - cy0 + 3), (0, 0, 255), 1)
            sc = min(130 / crop.shape[0], 620 / crop.shape[1], 2.5)
            crop = cv2.resize(crop, (int(crop.shape[1] * sc), int(crop.shape[0] * sc)), interpolation=cv2.INTER_CUBIC)
            zm = img[max(0, y0 - h // 3):min(H, y1 + h // 3), max(0, x0 - h // 3):min(Wp, x1 + h // 3)]
            zs = min(230 / zm.shape[0], 720 / zm.shape[1], 7.0)
            zm = cv2.resize(zm, (int(zm.shape[1] * zs), int(zm.shape[0] * zs)), interpolation=cv2.INTER_CUBIC)
            row = np.full((max(crop.shape[0], zm.shape[0]) + 10, W, 3), 255, np.uint8)
            row[5:5 + zm.shape[0], 60:60 + zm.shape[1]] = zm
            row[5:5 + crop.shape[0], W - 5 - crop.shape[1]:W - 5] = crop
            cv2.putText(row, str(r["sid"]), (4, 40), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (200, 0, 0), 2)
            row[-2:, :] = 160
            rows.append(row)
            txt.append(f"#{r['sid']} [{r['stratum']}] {r['stem']} p{r['page']} {r['line']} cls={r['cls']} "
                       f"conf={[round(c, 3) for c in r['confs']]}\n   AZURE «{r['frm']}»  ->  GEMINI «{r['to']}»  "
                       f"why: {r['why']}\n   line: {r['text']}\n   known from/to {r['from_known']}/{r['to_known']} "
                       f"wl {r['from_wl']}/{r['to_wl']}")
        k = s0 // 10 + 1
        cv2.imwrite(str(dst / f"sheet_{k:02d}.jpg"), np.vstack(rows), [cv2.IMWRITE_JPEG_QUALITY, 88])
        (dst / f"sheet_{k:02d}.txt").write_text("\n".join(txt) + "\n", encoding="utf-8")
    print(len(S), "fixes on", -(-len(S) // 10), "sheets ->", dst)


if __name__ == "__main__":
    {"pick": pick, "sheets": sheets}[sys.argv[1]]()
