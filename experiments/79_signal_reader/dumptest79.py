"""Experiment 79r: the held-out test line crops (experiment 77's test pages, cut at 96 px exactly as realtest79 cuts
them) saved as PNG, so the rented host can rebuild their pen paths with experiment 82's learned centre line.

    nice -n 19 ionice -c3 python dumptest79.py    -> out/up_r/testcrops.npz (key -> PNG bytes) + testcrops.jsonl

Only line crops of the test pages leave this machine (to the rented host, as before); no letters go with them to
the path rebuilder (the labels in the jsonl are used only by the scorer).
"""
from __future__ import annotations

import json
import sys

import cv2
import numpy as np

from sig79 import E, OUT

sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import azure_pages, clean_label, cut_line, nonempty_lines, render_page  # noqa: E402
from test77 import find_sources  # noqa: E402

cv2.setNumThreads(1)


def main(H: int = 96):
    import pypdfium2 as pdfium
    od = OUT / "up_r"
    od.mkdir(parents=True, exist_ok=True)
    pages = json.loads((E / "77_scratch_reader/out/test/pages.json").read_text(encoding="utf-8"))
    crops, rows = {}, []
    for P in pages:
        az, pdf = find_sources(P["stem"])
        pg = azure_pages(az)[P["page"] - 1]
        doc = pdfium.PdfDocument(str(pdf))
        img = render_page(doc, P["page"] - 1)
        doc.close()
        sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
        lines = {ln["i"]: ln for ln in nonempty_lines(pg)}
        for r in P["lines"]:
            if not r["cut"]:
                continue
            crop, _ = cut_line(img, lines[r["i"]]["poly"], sx, sy, H=H, test=True)
            if crop is None:
                continue
            ok, b = cv2.imencode(".png", crop)
            crops[r["key"]] = np.frombuffer(b.tobytes(), np.uint8)
            rows.append(dict(key=r["key"], label=clean_label(r["azure"])))
    np.savez(od / "testcrops.npz", **crops)
    with open(od / "testcrops.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(rows), "test crops")


if __name__ == "__main__":
    main()
