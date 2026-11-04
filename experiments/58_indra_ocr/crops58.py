"""Experiment 58: Indra's recognizer alone, on Azure's line boxes (detector and layout out of the comparison).

    nice -n 19 out/venv/bin/python crops58.py   -> out/indra/azcrops/<id>.json (lines in Azure's order)
"""
import json, os, time
from pathlib import Path
os.environ["HF_HUB_OFFLINE"] = "1"
import cv2
import numpy as np
import indra_ocr

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
dst = OUT / "indra/azcrops"; dst.mkdir(parents=True, exist_ok=True)
conv = indra_ocr.load(path=str(OUT / "models"), threads=4)
az = json.loads((OUT / "azure_truth34.json").read_text())
units = json.loads((OUT / "units_truth34.json").read_text())
for u in units:
    g = cv2.imread(u["image"], cv2.IMREAD_GRAYSCALE)
    lines = az[u["id"]]
    boxes = np.array([l["px"] for l in lines], np.float32).reshape(-1, 4)
    t0 = time.perf_counter()
    rec = conv.ocr.recognize(g, boxes)
    conv.ocr._page_rtl = sum("\u0600" <= c <= "\u06ff" for l in lines for c in l["text"]) > \
        sum(c.isascii() and c.isalpha() for l in lines for c in l["text"])
    rec = [(conv.ocr._decode(r[2]) if r[2] else r[0], r[1], r[2]) for r in rec]   # visual -> logical, as Indra's page step
    ms = 1000 * (time.perf_counter() - t0)
    out = [dict(box=l["px"], text=r[0], conf=round(float(r[1]), 4), azure=l["text"]) for l, r in zip(lines, rec)]
    (dst / f"{u['id']}.json").write_text(json.dumps(dict(id=u["id"], lines=out, wall_ms=ms), ensure_ascii=False))
print("done")
