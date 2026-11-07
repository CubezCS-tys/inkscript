"""Experiment 79: the pen signals of experiment 77's held-out TEST lines (the same pages, the same Azure line boxes,
the same labels), for the signal reader's first look at real print.  Local, CPU, light (2 cores, niced).

    nice -n 19 ionice -c3 python realtest79.py

Pages and line boxes: experiment 77's out/test/pages.json (read only): the owner's 20 yardstick pages and lab docs
1-3.  Each line is cut by experiment 77's cut at height 96 (twice its 48: the same box), its signal reconstructed by
sig79.line_signal.  Writes out/realtest/signals.npz (features per line) and out/realtest/lines.jsonl (key, set,
label = clean_label(Azure), truth = the owner's line where the yardstick maps it, else None).  Only features leave
this machine (to the rented GPU for inference); no image does.
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np

from sig79 import E, OUT, features, line_signal

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import azure_pages, clean_label, cut_line, nonempty_lines, render_page  # noqa: E402
from test77 import find_sources  # noqa: E402

cv2.setNumThreads(1)


def main(H: int = 96, centre: str = "skeleton", flags: bool = False, name: str = "realtest"):
    import pypdfium2 as pdfium
    od = OUT / name
    od.mkdir(parents=True, exist_ok=True)
    pages = json.loads((E / "77_scratch_reader/out/test/pages.json").read_text(encoding="utf-8"))
    feats, rows = {}, []
    for P in pages:
        az, pdf = find_sources(P["stem"])
        pg = azure_pages(az)[P["page"] - 1]
        doc = pdfium.PdfDocument(str(pdf))
        img = render_page(doc, P["page"] - 1)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        lines = {ln["i"]: ln for ln in nonempty_lines(pg)}
        gpos = {int(k): v for k, v in (P.get("gold_pos") or {}).items()}
        for r in P["lines"]:
            if not r["cut"]:
                continue
            ln = lines[r["i"]]
            crop, info = cut_line(img, ln["poly"], sx, sy, H=H, test=True)
            if crop is None:
                continue
            try:
                F = features(line_signal(crop, start_rule="top", centre=centre, flags=flags))
            except Exception as e:  # noqa: BLE001
                print(r["key"], "failed", e, flush=True)
                F = np.zeros((0, 17 if flags else 13), np.float32)
            feats[r["key"]] = F.astype(np.float16)
            truth = P["truth"][gpos[r["i"]]] if (P["set"] == "yardstick" and r["i"] in gpos and P.get("truth")) else None
            rows.append(dict(key=r["key"], set=P["set"] if P["set"] == "yardstick" else P["lab"], page_id=P["page_id"],
                             i=r["i"], label=clean_label(r["azure"]), truth=clean_label(truth) if truth else None,
                             points=int(len(F)), W=int(crop.shape[1])))
        print(P["page_id"], len(rows), flush=True)
    np.savez_compressed(od / "signals.npz", **feats)
    with open(od / "lines.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(f"{len(rows)} lines, mean points {np.mean([r['points'] for r in rows]):.0f}")


if __name__ == "__main__":
    # python realtest79.py [centre] [flags] [name]   e.g.  hybrid 1 realtest_hf
    a = sys.argv[1:]
    main(centre=a[0] if a else "skeleton", flags=bool(int(a[1])) if len(a) > 1 else False, name=a[2] if len(a) > 2 else "realtest")
