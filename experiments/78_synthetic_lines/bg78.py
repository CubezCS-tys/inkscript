"""Experiment 78, step 2: real paper for the synthetic lines, cut from TRAINING-POOL scans (never a held-out journal).

    .venv/bin/python bg78.py [PAGES]   -> out/bg/paper-*.jpg   blank paper (no Azure line within a margin), 250 dpi
                                          out/bg/through-*.jpg  printed text cut from another page and mirrored
                                                                left-right, to be laid faintly under a line as
                                                                show-through
                                          out/bg/bg78.json      counts, sources
Pages: experiment 77's pages77.jsonl (held-out journals already left out; checked again), 60% before 2000.
"""
from __future__ import annotations

import json
import math
import random
import sys

import cv2
import numpy as np

from common78 import DPI, OUT, OUT77, azure_pages, nonempty_lines, pages80, render_page, test_codes

SRC80 = "--src80" in sys.argv     # pages of the experiment 80 old-print pull instead of experiment 77 pages

PW, PH = 1400, 150          # a paper patch at 250 dpi (wider than most lines' height x 20)


def main(n_pages: int):
    import pypdfium2 as pdfium
    rng = random.Random(7801)
    held = test_codes()
    P = pages80() if SRC80 else [json.loads(l) for l in open(OUT77 / "pages77.jsonl", encoding="utf-8")]
    old = [p for p in P if str(p.get("year"))[:4].isdigit() and int(str(p["year"])[:4]) < 2000]
    mod = [p for p in P if not (str(p.get("year"))[:4].isdigit() and int(str(p["year"])[:4]) < 2000)]
    pick = (rng.sample(old, min(len(old), n_pages)) if SRC80 else
            rng.sample(old, int(n_pages * 0.6)) + rng.sample(mod, n_pages - int(n_pages * 0.6)))
    D = OUT / ("bg80" if SRC80 else "bg")
    D.mkdir(parents=True, exist_ok=True)
    npaper = nthrough = 0
    src = []
    for k, p in enumerate(pick):
        assert p["jcode"] not in held
        try:
            pdf = pdfium.PdfDocument(p["pdf"])
            pg = azure_pages(p["azure"])[p["page"] - 1]
            img = render_page(pdf, p["page"] - 1)
            pdf.close()
        except Exception:  # noqa: BLE001
            continue
        H, W = img.shape
        sx, sy = W / pg["width"], H / pg["height"]
        mask = np.zeros((H, W), np.uint8)
        polys = []
        for ln in nonempty_lines(pg):
            if not ln["poly"]:
                continue
            q = (np.array(ln["poly"][:8], float).reshape(4, 2) * [sx, sy]).astype(np.int32)
            cv2.fillPoly(mask, [q], 255)
            polys.append(q)
        mask = cv2.dilate(mask, np.ones((61, 61), np.uint8))
        # paper: random windows that touch no line (dilated) and hold little ink
        got = 0
        for _ in range(60):
            if got >= 4:
                break
            pw = rng.randint(500, PW)
            x, y = rng.randint(0, max(0, W - pw)), rng.randint(0, max(0, H - PH))
            if mask[y:y + PH, x:x + pw].any():
                continue
            win = img[y:y + PH, x:x + pw]
            if win.shape != (PH, pw) or (win < 128).mean() > 0.01:
                continue
            cv2.imwrite(str(D / f"paper-{npaper:05d}.jpg"), win, [cv2.IMWRITE_JPEG_QUALITY, 90])
            npaper += 1
            got += 1
        # show-through: a window over printed lines, mirrored left-right (the back of the leaf)
        if polys and rng.random() < 0.7:
            q = polys[rng.randrange(len(polys))]
            x0, y0 = max(0, q[:, 0].min()), max(0, q[:, 1].min() - 40)
            win = img[y0:y0 + PH, x0:x0 + PW]
            if win.shape[0] == PH and win.shape[1] > 300 and (win < 128).mean() > 0.02:
                cv2.imwrite(str(D / f"through-{nthrough:05d}.jpg"), win[:, ::-1], [cv2.IMWRITE_JPEG_QUALITY, 85])
                nthrough += 1
        src.append(dict(stem=p["stem"], page=p["page"], year=p.get("year")))
        if k % 50 == 0:
            print(k, npaper, nthrough, flush=True)
    (D / "bg78.json").write_text(json.dumps(dict(paper=npaper, through=nthrough, pages=len(src), dpi=DPI, src=src)))
    print(npaper, nthrough)


if __name__ == "__main__":
    args = [x for x in sys.argv[1:] if not x.startswith("--")]
    main(int(args[0]) if args else 500)
