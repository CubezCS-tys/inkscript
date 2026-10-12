"""Draw a born-digital page's truth lines in bd.py's reading order (red numbers) and Azure's order (blue), to check.

    PYTHONPATH=<worktree>/src .venv/bin/python bd_look.py DOC PAGE [DOC PAGE ...]    -> out/look/<doc>_p<page>.jpg
"""
import json, sys
import cv2, numpy as np, pymupdf
sys.path.insert(0, __file__.rsplit("/", 1)[0])
import bd

args = sys.argv[1:]
sp = json.load(open(bd.E33 / "out" / "splits.json"))["docs"]
(bd.OUT / "look").mkdir(parents=True, exist_ok=True)
for d, p in zip(args[0::2], args[1::2]):
    p = int(p)
    pdoc = pymupdf.open(str(bd.doc_dir(d) / f"{d}.pdf"))
    adoc, ainfo = bd.azure_doc(d)
    r = bd.page_record(d, tuple(sp[d]["variant"]), pdoc, p, adoc, ainfo)
    pix = pdoc[p - 1].get_pixmap(dpi=150)
    im = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width * pix.n].reshape(pix.height, pix.width, pix.n)[:, :, :3].copy()
    k = 0.5
    for i, l in enumerate(r["lines"]):
        b = [int(v * k) for v in l["box"]]
        cv2.rectangle(im, (b[0], b[1]), (b[2], b[3]), (220, 0, 0), 1)
        cv2.putText(im, str(i), (b[2] + 2, b[3]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (220, 0, 0), 1)
    for i, l in enumerate(r["azure"]):
        b = [int(v * k) for v in l["box"]]
        cv2.putText(im, str(i), (max(0, b[0] - 22), b[3]), cv2.FONT_HERSHEY_SIMPLEX, 0.45, (0, 0, 220), 1)
    cv2.imwrite(str(bd.OUT / "look" / f"{d}_p{p:03d}.jpg"), im[:, :, ::-1])
    print(d, p, r["ncols"], round(r["azure_concord"], 3))
