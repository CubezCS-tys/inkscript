"""Line images with their exact text from born-digital Mandumah documents, split by journal.

    nice out/env/bin/python build_data.py [--workers 3]
Reads out/meta.json (meta.py), experiment 19's born-digital documents and out/docs (fetched candidates).
Writes, per document, out/lines/<id>.json (every born-digital page's lines: box, the chosen decoding of the text,
Azure's words on that line, kind) and line images for the pages drawn for its split:
out/img/<split>/<id>_p<page>_l<k>.png (clean, 300 dpi) and ..._d.jpg (scan-like copy, degrade.py).
Then out/data.jsonl (one record per drawn line) and out/splits.json.
"""
import json, random, sys, traceback, zlib
from collections import Counter
from multiprocessing import Pool
from pathlib import Path
import pymupdf
from PIL import Image
sys.path.insert(0, str(Path(__file__).resolve().parent))
from lines import born_digital, page_lines, azure_words, assign_azure
from textnorm import faithful, is_arabic_line, vowelled
from degrade import degrade
from rapidfuzz.distance import Levenshtein

OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
DPI = 300
PAGES = {"train": 8, "dev": 3, "test": 4}                          # pages drawn per document
VARIANTS = [(False, False), (True, False), (False, True), (True, True)]


def doc_paths():
    out = {}
    d19 = json.load(open(E19 / "docs.json"))
    for i, r in d19.items():
        if r.get("kind") == "born-digital":
            out[i] = E19 / "docs" / i
    for p in (OUT / "docs").iterdir():
        if (p / f"{p.name}.pdf").exists() and (p / f"{p.name}.json").exists():
            out[p.name] = p
    return out


def splits(ids):
    js = sorted({i[:4] for i in ids}); random.Random(33).shuffle(js)
    n = len(js); test = set(js[: int(0.2 * n)]); dev = set(js[int(0.2 * n): int(0.3 * n)])
    return {i: ("test" if i[:4] in test else "dev" if i[:4] in dev else "train") for i in ids}


def kind(ln, body):
    t = ln["gold"]
    if not is_arabic_line(t):
        return "latin" if sum(c.isalpha() for c in t) > 0.5 * len(t.replace(" ", "")) else "numbers"
    if sum(c.isdigit() for c in t) >= 0.3 * len(t.replace(" ", "")):
        return "numbers"
    if vowelled(t):
        return "vowelled"
    if ln["size"] >= 1.12 * body or (ln["bold"] and len(t) < 0.6 * ln["maxlen"]):
        return "heading"
    if ln["size"] <= 0.88 * body:
        return "footnote"
    return "body"


def one(args):
    i, d, split = args
    st = OUT / "status" / f"{i}.json"
    if st.exists():
        return i, json.load(open(st))
    i, info = _one(args)
    if info.get("status") != "error":
        json.dump(info, open(st, "w"), default=str)
    return i, info


def _one(args):
    i, d, split = args
    try:
        doc = pymupdf.open(str(d / f"{i}.pdf")); az = json.load(open(d / f"{i}.json")); az = az.get("analyzeResult", az)
        azp = {p["pageNumber"]: p for p in az["pages"]}
        pages = []
        for pno, page in enumerate(doc):
            if page.rotation or not born_digital(page) or (pno + 1) not in azp:
                continue
            lines, junk = page_lines(page, VARIANTS)
            if junk or not lines:
                continue
            assign_azure(lines, azure_words(azp[pno + 1], page))
            pages.append(dict(page=pno + 1, lines=lines))
        if not pages:
            return i, dict(status="no born-digital pages")
        # the document's decoding: the variant closest to Azure on its Arabic lines
        tot = Counter(); n = 0
        for p in pages:
            for ln in p["lines"]:
                if ln["azure"] and is_arabic_line(ln["text"][VARIANTS[0]]):
                    n += 1
                    for v in VARIANTS:
                        tot[v] += Levenshtein.distance(faithful(ln["text"][v]), faithful(ln["azure"]))
        if n < 10:
            return i, dict(status="too few Arabic lines")
        var = min(VARIANTS, key=lambda v: (tot[v], VARIANTS.index(v)))
        cers = []
        sizes = Counter()
        for p in pages:
            for ln in p["lines"]:
                ln["gold"] = faithful(ln["text"][var]); ln["variants"] = len({faithful(t) for t in ln["text"].values()})
                del ln["text"]
                sizes[round(ln["size"] * 2) / 2] += len(ln["gold"])
                if ln["azure"] and is_arabic_line(ln["gold"]) and len(ln["gold"]) >= 10:
                    cers.append(Levenshtein.distance(ln["gold"], faithful(ln["azure"])) / len(ln["gold"]))
        body = sizes.most_common(1)[0][0]
        for p in pages:
            ml = max(len(l["gold"]) for l in p["lines"])
            for k, ln in enumerate(p["lines"]):
                ln["maxlen"] = ml; ln["kind"] = kind(ln, body); ln["k"] = k
        cers.sort(); med = cers[len(cers) // 2] if cers else 1
        good = sum(c <= 0.1 for c in cers) / max(len(cers), 1)
        info = dict(status="ok" if med <= 0.05 and good >= 0.7 else "junk text layer", variant=var, median_cer_vs_azure=med,
                    share_close=good, n_arabic=len(cers), pages=len(pages), body_size=body, split=split)
        json.dump(dict(info=info, pages=pages), open(OUT / "lines" / f"{i}.json", "w"), ensure_ascii=False, default=str)
        if info["status"] != "ok":
            return i, info
        # draw pages and render their lines
        r = random.Random(i); drawn = sorted(r.sample([p["page"] for p in pages], min(PAGES[split], len(pages))))
        info["drawn"] = drawn; recs = []
        (OUT / "img" / split).mkdir(parents=True, exist_ok=True)
        for p in pages:
            if p["page"] not in drawn:
                continue
            pg = doc[p["page"] - 1]; pix = pg.get_pixmap(dpi=DPI, colorspace=pymupdf.csGRAY)
            im = Image.frombytes("L", (pix.width, pix.height), pix.samples); s = DPI / 72
            for ln in p["lines"]:
                g = ln["gold"]
                if len(g) < 2 or any(0xE000 <= ord(c) <= 0xF8FF or c == "�" for c in g):
                    continue
                x0, y0, x1, y1 = ln["bbox"]; h = (y1 - y0)
                if h < 3 or x1 - x0 < 3:
                    continue
                box = (max(0, int((x0 - 0.25 * h) * s)), max(0, int((y0 - 0.12 * h) * s)),
                       min(im.width, int((x1 + 0.25 * h) * s) + 1), min(im.height, int((y1 + 0.12 * h) * s) + 1))
                crop = im.crop(box); lid = f"{i}_p{p['page']}_l{ln['k']}"
                crop.save(OUT / "img" / split / f"{lid}.png", optimize=True)
                degrade(crop, zlib.crc32(lid.encode())).save(OUT / "img" / split / f"{lid}_d.jpg", quality=90)
                recs.append(dict(id=lid, doc=i, journal=i[:4], split=split, page=p["page"], k=ln["k"], bbox=ln["bbox"],
                                 px=box, gold=g, azure=ln["azure"], azure_conf=ln["azure_conf"], kind=ln["kind"],
                                 size=ln["size"], variants=ln["variants"], nlig=ln["nlig"]))
        info["lines"] = len(recs)
        with open(OUT / "recs" / f"{i}.jsonl", "w") as f:
            for rc in recs:
                f.write(json.dumps(rc, ensure_ascii=False) + "\n")
        return i, info
    except Exception as e:
        return i, dict(status="error", err=traceback.format_exc()[-600:])


if __name__ == "__main__":
    import os
    os.environ.setdefault("PYTHONHASHSEED", "0")
    w = int(sys.argv[sys.argv.index("--workers") + 1]) if "--workers" in sys.argv else 3
    (OUT / "lines").mkdir(exist_ok=True); (OUT / "recs").mkdir(exist_ok=True); (OUT / "status").mkdir(exist_ok=True)
    meta = json.load(open(OUT / "meta.json"))
    paths = doc_paths()
    ids = sorted(i for i in paths if "ara" in (meta.get(i, {}).get("lang") or ["ara"]))
    sp = splits(ids)
    only = sys.argv[sys.argv.index("--only") + 1].split(",") if "--only" in sys.argv else None
    todo = [(i, paths[i], sp[i]) for i in ids if not only or i in only]
    res = {}
    with Pool(w) as pool:
        for i, info in pool.imap_unordered(one, todo):
            res[i] = info; print(i, info.get("status"), info.get("lines", ""), round(info.get("median_cer_vs_azure", -1), 3), flush=True)
    if not only:
        json.dump(dict(splits=sp, docs=res), open(OUT / "splits.json", "w"), ensure_ascii=False, indent=1, default=str)
        with open(OUT / "data.jsonl", "w") as f:
            for i in ids:
                p = OUT / "recs" / f"{i}.jsonl"
                if res.get(i, {}).get("status") == "ok" and p.exists():
                    f.write(p.read_text())
        print(Counter(r.get("status") for r in res.values()))
