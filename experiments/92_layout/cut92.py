"""Experiment 92, step 5 (c): line crops for the reader, from Azure's line polygons and from OUR line boxes
(experiment 39's model, rounds 1 and 2), on the same render of every test page.

    nice -n 19 ionice -c3 ../81_heldout_scale/out/venv/bin/python cut92.py
        -> out/crops48/{az92,r192,r292}-<page>.tar  (Store format: <key>.jpg + <key>.txt, empty label)
           out/own92.jsonl  {key, page, src, j, box (page units), label, conf, cut}

Exactly experiment 77/81's cut: 250-dpi pypdfium2 5.12.1 render, common77.cut_line(test=True) at 48 px.  Azure:
the line polygon.  Ours: the de-duplicated boxes of score92.own_lines (conf >= 0.25), as 4-point polygons (the model
gives upright boxes).  Keys: Azure <stem>_pNNN_lNNN (Azure's non-empty line number), ours <stem>_pNNN_<r1|r2>yNNN.
"""
from __future__ import annotations

import io
import json
import sys
import tarfile

from common92 import E, OUT, assert_not_locked, azure_lines, render_gray

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import cut_line, encode  # noqa: E402
from score92 import own_lines  # noqa: E402


def add(tar, key, crop):
    for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", b"")):
        ti = tarfile.TarInfo(name)
        ti.size = len(data)
        tar.addfile(ti, io.BytesIO(data))


def main():
    import cv2
    cv2.setNumThreads(1)
    pages = [json.loads(l) for l in open(OUT / "pages92.jsonl", encoding="utf-8")]
    assert_not_locked([p["key"] for p in pages])
    Y = {m: json.load(open(OUT / f"yolo92_{m}.json")) for m in ("r1", "r2")}
    D = OUT / "crops48"
    D.mkdir(parents=True, exist_ok=True)
    meta = OUT / "own92.jsonl"
    done = {json.loads(l)["page"] for l in open(meta, encoding="utf-8")} if meta.exists() else set()
    with open(meta, "a", encoding="utf-8") as fm:
        for n, p in enumerate(pages, 1):
            k = p["key"]
            if k in done:
                continue
            img = render_gray(p["pdf"], p["page"])
            lines, W, H = azure_lines(p["azure"], p["page"])
            sx, sy = img.shape[1] / W, img.shape[0] / H
            with tarfile.open(D / f"az92-{k}.tar", "w") as t:
                for ln in lines:
                    if ln["poly"]:
                        crop, _ = cut_line(img, ln["poly"], sx, sy, test=True)
                        if crop is not None:
                            add(t, f"{k}_l{ln['i']:03d}", crop)
            rows = []
            for m in Y:
                with tarfile.open(D / f"{m}92-{k}.tar", "w") as t:
                    for j, (b, lab, c) in enumerate(own_lines(Y[m][k], W, H)):
                        poly = [b[0], b[1], b[2], b[1], b[2], b[3], b[0], b[3]]
                        crop, _ = cut_line(img, poly, sx, sy, test=True)
                        key = f"{k}_{m}y{j:03d}"
                        if crop is not None:
                            add(t, key, crop)
                        rows.append(dict(key=key, page=k, src=m, j=j, box=[round(v, 5) for v in b], label=lab,
                                         conf=c, cut=crop is not None))
            for r in rows:
                fm.write(json.dumps(r, ensure_ascii=False) + "\n")
            fm.flush()
            if n % 20 == 0:
                print(n, "pages", flush=True)
    print("CUT92_DONE", flush=True)


if __name__ == "__main__":
    main()
