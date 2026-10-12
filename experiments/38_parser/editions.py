"""Experiment 38, step 5: every edition of each page's master with experiment 35's own code (`inkscript edition`,
build_one), so the comparison with the old editions is like for like -> out/pages/<pid>/edition/<pid>/...

    /home/yassine/inkscript/.venv/bin/python editions.py [PID ...] [--force] [--raw] [--workers 3]

Then the pictures the judge, the spot-check and the report use (out/pages/<pid>/shots/):
  scan.jpg            the scan
  new_layout.jpg      the new layout-faithful PDF's page
  old_layout.jpg      the old edition's page (experiment 35's <stem>.layout.pdf, the same page)
  three.jpg           scan | old | new, side by side, labelled
  new_onecol-<k>.jpg  the new one-column PDF's pages
"""
from __future__ import annotations

import json
import sys
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

from common import OLD_EDITIONS, OUT, pages

H_SHOT = 1400


def render(pdf: Path, page: int, height: int = H_SHOT):
    import numpy as np
    import pypdfium2 as pdfium
    d = pdfium.PdfDocument(str(pdf))
    if page - 1 >= len(d):
        return None
    pg = d[page - 1]
    s = height / pg.get_height()
    im = pg.render(scale=s).to_numpy()
    d.close()
    return np.ascontiguousarray(im[..., :3])          # pdfium renders BGR(A)


def label(img, text):
    import cv2
    out = cv2.copyMakeBorder(img, 44, 0, 0, 0, cv2.BORDER_CONSTANT, value=(255, 255, 255))
    cv2.putText(out, text, (12, 32), cv2.FONT_HERSHEY_SIMPLEX, 1.0, (40, 40, 40), 2, cv2.LINE_AA)
    return out


def shots(pid: str, meta: dict, raw: bool = False):
    import cv2
    import numpy as np
    pdir = OUT / "pages" / pid
    sd = pdir / ("shots_raw" if raw else "shots")
    sd.mkdir(exist_ok=True)
    ed = pdir / ("edition_raw" if raw else "edition") / pid
    scan = render(pdir / ("master_raw" if raw else "master") / f"{pid}.pdf", 1)
    new = render(ed / f"{pid}.layout.pdf", 1) if (ed / f"{pid}.layout.pdf").exists() else None
    old_pdf = OLD_EDITIONS / meta["stem"] / f"{meta['stem']}.layout.pdf"
    old = render(old_pdf, meta["page"]) if old_pdf.exists() else None
    for name, im in (("scan", scan), ("new_layout", new), ("old_layout", old)):
        if im is not None:
            cv2.imwrite(str(sd / f"{name}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 82])
    parts = [label(im, t) for im, t in
             ((scan, "scan"), (old, "old (experiment 35)"), (new, "new (experiment 38)")) if im is not None]
    if parts:
        h = max(p.shape[0] for p in parts)
        parts = [cv2.copyMakeBorder(p, 0, h - p.shape[0], 0, 12, cv2.BORDER_CONSTANT, value=(255, 255, 255))
                 for p in parts]
        cv2.imwrite(str(sd / "three.jpg"), np.hstack(parts), [cv2.IMWRITE_JPEG_QUALITY, 80])
    oc = ed / f"{pid}.onecol.pdf"
    if oc.exists():
        import pypdfium2 as pdfium
        n = len(pdfium.PdfDocument(str(oc)))
        for k in range(1, min(n, 4) + 1):
            im = render(oc, k)
            cv2.imwrite(str(sd / f"new_onecol-{k}.jpg"), im, [cv2.IMWRITE_JPEG_QUALITY, 82])


def one(args):
    pid, meta, raw = args
    from inkscript.edition.build import build_one
    pdir = OUT / "pages" / pid
    md = pdir / ("master_raw" if raw else "master")
    out = pdir / ("edition_raw" if raw else "edition")
    r = build_one(str(md / f"{pid}.jats.xml"), str(out))
    (out / "build.json").write_text(json.dumps(r, ensure_ascii=False, indent=1, default=str), encoding="utf-8")
    shots(pid, meta, raw)
    return pid, r.get("errors"), r.get("seconds")


def main(argv):
    raw = "--raw" in argv
    force = "--force" in argv
    workers = int(argv[argv.index("--workers") + 1]) if "--workers" in argv else 3
    want = [a for a in argv if not a.startswith("--") and not a.isdigit()]
    todo = []
    for meta in pages():
        pid = meta["page_id"]
        if want and pid not in want:
            continue
        pdir = OUT / "pages" / pid
        if not (pdir / ("master_raw" if raw else "master") / "master_stats.json").exists():
            continue
        if (pdir / ("edition_raw" if raw else "edition") / "build.json").exists() and not force:
            continue
        todo.append((pid, meta, raw))
    with ProcessPoolExecutor(workers) as ex:
        for pid, err, sec in ex.map(one, todo):
            print(pid, sec, "s", ("ERRORS " + json.dumps(err)[:300]) if err else "ok", flush=True)


if __name__ == "__main__":
    main(sys.argv[1:])
