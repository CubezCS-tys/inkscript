"""Line-finder training pages: scanned Mandumah pages with Azure's lines as PAGE XML baselines and boundaries.

    nice out/env/bin/python seg_data.py [--workers 3]          -> out/seg/{train,dev}/<doc>_p<page>.{jpg,xml}
                                                               -> out/seg/test/...  (experiment 19's pages, for scoring)
Azure's line polygon is the boundary (cut in two where Azure ran one line across two columns: a word gap wider
than twice the line height). Its baseline is not given, so it is found in the ink: inside the polygon, the
row with the most ink between 35% and 95% of the line's height (Arabic letters sit on, and join along, one line), then
tilted with the polygon's own slope. Baselines run left to right, as kraken's own line finder writes them.
Pages: up to 4 upright scanned pages per document of the silver set (silver_data.py) - never a journal or document
held out by experiment 34 (34_yardstick/out/heldout.txt) nor of experiment 19's draw; 10% of journals to dev.
Test: the page of each of experiment 19's scanned documents that fullpage.py --scan reads (most judged words).
Pages are stored at 150 dpi (an A4 page is then about 1750 px high; kraken's line finder scales a page to 1800 px
"""
import json, random, sys
from multiprocessing import Pool
from pathlib import Path
import numpy as np
import pymupdf
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import born_digital

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
Y34 = Path("/home/yassine/inkscript/experiments/34_yardstick/out/heldout.txt")
DPI = 150


def baseline(g: np.ndarray, poly: list) -> list:
    """Baseline (two points, left to right) for one Azure line polygon (px) on the page image g."""
    xs = poly[0::2]; ys = poly[1::2]
    x0, x1, y0, y1 = int(min(xs)), int(max(xs)) + 1, int(min(ys)), int(max(ys)) + 1
    crop = g[max(0, y0):y1, max(0, x0):x1]
    # slope of the polygon's top and bottom edges (points: tl, tr, br, bl as Azure writes them)
    dx = (xs[1] - xs[0]) or 1e-6; slope = ((ys[1] - ys[0]) / dx + (ys[2] - ys[3]) / ((xs[2] - xs[3]) or 1e-6)) / 2
    slope = max(-0.3, min(0.3, slope))
    h = crop.shape[0]
    if h < 4 or crop.shape[1] < 4:
        f = 0.72
    else:
        # de-tilt the profile: shift each column by the slope before summing rows
        thr = crop.mean() - 0.5 * crop.std()
        ink = (crop < thr).astype(np.float32)
        cols = np.arange(ink.shape[1]); shift = np.round((cols - ink.shape[1] / 2) * slope).astype(int)
        prof = np.zeros(h + 2 * abs(shift).max() + 2)
        off = abs(shift).max() + 1
        for c in range(0, ink.shape[1], 2):
            prof[off - shift[c]: off - shift[c] + h] += ink[:, c]
        prof = prof[off: off + h]
        lo, hi = int(0.35 * h), max(int(0.95 * h), int(0.35 * h) + 1)
        f = (lo + int(np.argmax(prof[lo:hi]))) / h if prof[lo:hi].max() > 0 else 0.72
    xm = (min(xs) + max(xs)) / 2; ym = y0 + f * h
    ya = ym + (min(xs) - xm) * slope; yb = ym + (max(xs) - xm) * slope
    return [(int(min(xs)), int(round(ya))), (int(max(xs)), int(round(yb)))]


def split_lines(pg, s):
    """Azure's line polygons (px), a line cut in two where its words leave a gap wider than twice the line's height:
    Azure sometimes runs one line across both columns of a page."""
    words = pg.get("words", []); out = []
    for ln in pg.get("lines", []):
        poly = [v * s for v in ln["polygon"]]
        if len(poly) < 8:
            continue
        a = min(sp["offset"] for sp in ln["spans"]); b = max(sp["offset"] + sp["length"] for sp in ln["spans"])
        ws = [[v * s for v in w["polygon"]] for w in words if a <= w["span"]["offset"] < b]
        if len(ws) < 2:
            out.append(poly); continue
        boxes = sorted((min(w[0::2]), min(w[1::2]), max(w[0::2]), max(w[1::2])) for w in ws)
        h = sorted(q[3] - q[1] for q in boxes)[len(boxes) // 2]
        groups = [[boxes[0]]]
        for q in boxes[1:]:
            if q[0] - max(r[2] for r in groups[-1]) > 2 * h:
                groups.append([])
            groups[-1].append(q)
        if len(groups) == 1:
            out.append(poly); continue
        for gr in groups:
            x0 = min(q[0] for q in gr); y0 = min(q[1] for q in gr); x1 = max(q[2] for q in gr); y1 = max(q[3] for q in gr)
            out.append([x0, y0, x1, y0, x1, y1, x0, y1])
    return out


def page_xml(img_name, w, h, lines):
    out = ['<?xml version="1.0" encoding="UTF-8"?>',
           '<PcGts xmlns="http://schema.primaresearch.org/PAGE/gts/pagecontent/2019-07-15">',
           f'<Page imageFilename="{img_name}" imageWidth="{w}" imageHeight="{h}">',
           f'<TextRegion id="r0"><Coords points="0,0 {w - 1},0 {w - 1},{h - 1} 0,{h - 1}"/>']
    for k, (poly, bl) in enumerate(lines):
        pts = " ".join(f"{int(poly[i])},{int(poly[i + 1])}" for i in range(0, len(poly), 2))
        out.append(f'<TextLine id="l{k}"><Coords points="{pts}"/><Baseline points="{bl[0][0]},{bl[0][1]} {bl[1][0]},{bl[1][1]}"/></TextLine>')
    out += ["</TextRegion>", "</Page>", "</PcGts>"]
    return "\n".join(out)


def one(args):
    doc_id, d, split, pages = args
    try:
        pdf = pymupdf.open(str(d / f"{doc_id}.pdf")); az = json.load(open(d / f"{doc_id}.json")); az = az.get("analyzeResult", az)
        azp = {p["pageNumber"]: p for p in az["pages"]}
        if pages is None:
            cand = [p for p in az["pages"] if abs(p.get("angle") or 0) < 5 and p["pageNumber"] <= len(pdf)
                    and len(p.get("lines", [])) >= 3 and not born_digital(pdf[p["pageNumber"] - 1])]
            random.Random(doc_id + "seg").shuffle(cand); pages = [p["pageNumber"] for p in cand[:4]]
        done = []
        for pn in pages:
            pg = azp[pn]; pix = pdf[pn - 1].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
            im = Image.frombytes("L", (pix.width, pix.height), pix.samples); g = np.asarray(im)
            s = DPI if pg.get("unit", "inch") == "inch" else DPI / 300
            lines = []
            for poly in split_lines(pg, s):
                xs = poly[0::2]; ys = poly[1::2]
                if max(ys) - min(ys) > 1.5 * (max(xs) - min(xs)):
                    continue                                             # vertical or sideways text: not a line to learn
                bl = baseline(g, poly)
                if abs(bl[1][1] - bl[0][1]) > 0.15 * max(bl[1][0] - bl[0][0], 1):
                    continue                                             # steeper than 8 degrees: Azure's polygon is odd
                lines.append((poly, bl))
            name = f"{doc_id}_p{pn}"
            im.save(OUT / "seg" / split / f"{name}.jpg", quality=80)
            (OUT / "seg" / split / f"{name}.xml").write_text(page_xml(f"{name}.jpg", im.width, im.height, lines), encoding="utf-8")
            done.append((name, len(lines)))
        return doc_id, done
    except Exception as e:
        return doc_id, [("ERR " + str(e)[:200], 0)]


if __name__ == "__main__":
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    held = [l.split() for l in open(Y34) if l.strip()]
    hj = {b for a, b in held if a == "journal"}; hd = {b for a, b in held if a == "doc"}
    e19j = {l.strip()[:4] for l in open(E19 / "ids.txt") if l.strip()}
    for sp in ("train", "dev", "test"):
        (OUT / "seg" / sp).mkdir(parents=True, exist_ok=True)
    silver_docs = sorted({json.loads(l)["doc"] for l in open(OUT / "silver" / "silver.jsonl")})
    where = lambda i: OUT / "docs" / i if (OUT / "docs" / i).exists() else OUT / "docs_old" / i
    docs = [i for i in silver_docs if i[:4] not in hj and i not in hd and i[:4] not in e19j]
    js = sorted({i[:4] for i in docs}); random.Random(35).shuffle(js); dev = set(js[: max(1, len(js) // 10)])
    todo = [(i, where(i), "dev" if i[:4] in dev else "train", None) for i in docs]
    # test pages: the ones fullpage.py --scan reads
    seen = {}
    for l in open(OUT / "scan" / "scan.jsonl"):
        r = json.loads(l); seen.setdefault(r["doc"], {}).setdefault(r["page"], 0); seen[r["doc"]][r["page"]] += 1
    todo += [(d, E19 / "docs" / d, "test", [max(p, key=p.get)]) for d, p in sorted(seen.items())]
    n = {}
    with Pool(w) as pool:
        for i, done in pool.imap_unordered(one, todo):
            for name, k in done:
                print(i, name, k, flush=True)
    for sp in ("train", "dev", "test"):
        xs = sorted(str(p) for p in (OUT / "seg" / sp).glob("*.xml"))
        (OUT / "lists" / f"seg_{sp}.txt").write_text("\n".join(xs) + "\n")
        print(sp, len(xs), "pages")
