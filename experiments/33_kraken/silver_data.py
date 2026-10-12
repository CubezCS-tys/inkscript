"""Training lines from real scans, with Azure's reading as their (silver) text: the scan-domain round.

    nice out/env/bin/python silver_data.py [--workers 3]
Documents: the scanned ones among this experiment's fetches (out/docs: printed 2005 or later; out/docs_old: before
2000, and before 1970 from old70_ids.txt), never a journal of experiment 19's draw (whose judged words are the
real-scan test), nor of the born-digital test split, nor a journal or document held out by experiment 34's yardstick
(this last rule came after round B: round B's silver set still held 32 of those journals; its copy is out/silver_B).
Pre-1970 documents give up to 12 pages and 400 lines. Each line is tagged old70 / vowelled / small (print under 85%
of the page's usual line height: footnotes, captions). Per document up to 6 scanned pages and 150 lines; a line is kept when every Azure word on it has
confidence >= 0.9 (Azure is wrong on about 1.5% of scan words, mostly at low confidence: experiment 19), it has 3+
characters and the page is upright. 10% of documents (by journal) go to dev.
Writes out/silver/img/<doc>_p<page>_l<k>.png with .gt.txt beside it, out/silver/silver.jsonl, out/lists/silver_{train,dev}.txt
"""
import json, random, sys, zlib
from multiprocessing import Pool
from pathlib import Path
import pymupdf
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import born_digital
from textnorm import faithful, vowelled

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
DPI = 300


OLD70 = {l.strip() for l in open(OUT / "old70_ids.txt") if l.strip()} if (OUT / "old70_ids.txt").exists() else set()


def one(args):
    doc_id, d, split = args
    old = doc_id in OLD70                                             # printed before 1970: rare, so more of each
    try:
        pdf = pymupdf.open(str(d / f"{doc_id}.pdf")); az = json.load(open(d / f"{doc_id}.json")); az = az.get("analyzeResult", az)
        pages = [p for p in az["pages"] if abs(p.get("angle") or 0) < 2 and p["pageNumber"] <= len(pdf)
                 and not born_digital(pdf[p["pageNumber"] - 1])]
        r = random.Random(doc_id); r.shuffle(pages); recs = []
        for pg in pages[:(12 if old else 6)]:
            s = DPI if pg.get("unit", "inch") == "inch" else 1.0
            words = pg.get("words", []); im = None
            for k, ln in enumerate(pg.get("lines", [])):
                a = min(sp["offset"] for sp in ln["spans"]); b = max(sp["offset"] + sp["length"] for sp in ln["spans"])
                mem = [w for w in words if a <= w["span"]["offset"] < b]
                text = faithful(" ".join(w["content"] for w in mem))
                if len(text) < 3 or not mem or min(w.get("confidence", 0) for w in mem) < 0.9:
                    continue
                bx = []
                for w in mem:
                    p = w["polygon"]; xs = [v * s for v in p[0::2]]; ys = [v * s for v in p[1::2]]
                    bx.append((min(xs), min(ys), max(xs), max(ys)))
                hs = sorted(q[3] - q[1] for q in bx); h = hs[len(hs) // 2]
                if im is None:
                    pix = pdf[pg["pageNumber"] - 1].get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
                    im = Image.frombytes("L", (pix.width, pix.height), pix.samples)
                box = (max(0, int(min(q[0] for q in bx) - 0.25 * h)), max(0, int(min(q[1] for q in bx) - 0.15 * h)),
                       min(im.width, int(max(q[2] for q in bx) + 0.25 * h) + 1), min(im.height, int(max(q[3] for q in bx) + 0.15 * h) + 1))
                if box[2] - box[0] < 8 or box[3] - box[1] < 8:
                    continue
                lid = f"{doc_id}_p{pg['pageNumber']}_l{k}"; path = OUT / "silver" / "img" / f"{lid}.png"
                im.crop(box).save(path, optimize=True); path.with_suffix(".gt.txt").write_text(text + "\n", encoding="utf-8")
                recs.append(dict(id=lid, doc=doc_id, split=split, page=pg["pageNumber"], text=text, img=str(path), h=h, old70=old,
                                 vowelled=vowelled(text)))
            ph = sorted(q["h"] for q in recs if q["page"] == pg["pageNumber"]) or [0]
            for q in recs:                                               # small print: under 85% of the page's usual line height
                if q["page"] == pg["pageNumber"]:
                    q["small"] = q["h"] < 0.85 * ph[len(ph) // 2]
        r.shuffle(recs)
        return doc_id, recs[:(400 if old else 150)]
    except Exception as e:
        return doc_id, []


if __name__ == "__main__":
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    (OUT / "silver" / "img").mkdir(parents=True, exist_ok=True)
    bad_j = {l.strip()[:4] for l in open(E19 / "ids.txt") if l.strip()}
    held = [l.split() for l in open("/home/yassine/inkscript/experiments/34_yardstick/out/heldout.txt") if l.strip()]
    bad_j |= {b for a, b in held if a == "journal"}                   # experiment 34's yardstick: never trained on
    bad_d = {b for a, b in held if a == "doc"}
    bad_j |= {json.loads(l)["journal"] for l in open(OUT / "data.jsonl") if '"split": "test"' in l}
    status = {p.stem: json.load(open(p)) for p in (OUT / "status").glob("*.json")}
    docs = [(p.name, p) for p in sorted((OUT / "docs").iterdir()) if status.get(p.name, {}).get("status") == "no born-digital pages"]
    docs += [(p.name, p) for p in sorted((OUT / "docs_old").iterdir()) if (p / f"{p.name}.json").exists()]
    docs = [(i, p) for i, p in docs if i[:4] not in bad_j and i not in bad_d and (p / f"{i}.pdf").exists()]
    js = sorted({i[:4] for i, _ in docs}); random.Random(33).shuffle(js); dev = set(js[: max(1, len(js) // 10)])
    todo = [(i, p, "dev" if i[:4] in dev else "train") for i, p in docs]
    allr = []
    with Pool(w) as pool:
        for i, recs in pool.imap_unordered(one, todo):
            allr += recs; print(i, len(recs), flush=True)
    meta = json.load(open(OUT / "meta.json")) if (OUT / "meta.json").exists() else {}
    with open(OUT / "silver" / "silver.jsonl", "w") as f:
        for r in allr:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    for sp in ("train", "dev"):
        (OUT / "lists" / f"silver_{sp}.txt").write_text("\n".join(r["img"] for r in allr if r["split"] == sp) + "\n")
        print(sp, sum(r["split"] == sp for r in allr), "lines from", len({r["doc"] for r in allr if r["split"] == sp}), "documents")
