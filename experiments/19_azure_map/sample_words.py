"""Draw the words to judge, stratified by place and kind, from every scanned document drawn (out/docs.json).

Per document and stratum (strata.py) up to K words at random (body 5, others 3); born-digital pages are skipped;
words with no letter or digit (a lone bracket or dash) are left out of both the population and the sample.
Each sampled word carries the weight N/n of its (document, stratum) cell, so the archive's word error rate is the
weighted mean (each document counts with all its words). The encoding check runs on EVERY word (no judge needed).

    .venv/bin/python sample_words.py      -> out/sample.json, out/population.json, out/crops/*.png
"""
import json, random, re, sys
from pathlib import Path
from collections import Counter, defaultdict
import numpy as np, cv2
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; REPO = HERE.parents[1]
sys.path.insert(0, str(HERE)); sys.path.insert(0, str(REPO / "experiments/17_judge"))
import strata as S
import judge as J17                                  # crop(): the word's line, the paper behind the word tinted (exp. 17, v3)

K = {"body": 5}; KDEF = 3
REAL = re.compile(r"[\w؀-ۿ]")


def upright(gray, box, angle):
    """For a sideways page: rotate the page so the text runs level, and the box with it."""
    H, W = gray.shape; x0, y0, x1, y1 = box
    if angle > 45:      # Azure's angle is clockwise: text turned clockwise, so rotate the image counter-clockwise
        return np.ascontiguousarray(np.rot90(gray, 1)), [y0, W - x1, y1, W - x0]
    if angle < -45:
        return np.ascontiguousarray(np.rot90(gray, -1)), [H - y1, x0, H - y0, x1]
    return gray, box


def crop_word(pdf, w):
    gray = J17.page_image(pdf, w["page"]); g, b = upright(gray, w["box"], w["angle"])
    return J17.crop(g, b)


if __name__ == "__main__":
    docs = json.load(open(OUT / "docs.json")); (OUT / "crops").mkdir(exist_ok=True)
    sample = []; pop = {}
    for d in docs.values():
        if d["kind"] in ("born-digital", "error"): continue
        i = d["id"]; js = OUT / "docs" / i / f"{i}.json"; pdf = OUT / "docs" / i / f"{i}.pdf"
        import pymupdf
        doc = pymupdf.open(str(pdf))
        from inkscript.pdf.native import born_digital
        skip = {n + 1 for n, pg in enumerate(doc) if born_digital(pg)}
        ws = [w for w in S.words_of(js, skip) if REAL.search(w["text"])]
        cells = defaultdict(list)
        for w in ws: cells[w["stratum"]].append(w)
        pop[i] = dict(N={k: len(v) for k, v in cells.items()}, slips={k: sum(x["slip"] for x in v) for k, v in cells.items()},
                      words=len(ws), skipped_pages=sorted(skip))
        rng = random.Random(f"19:{i}")
        for st, v in sorted(cells.items()):
            pick = rng.sample(v, min(len(v), K.get(st, KDEF)))
            for w in pick:
                w = dict(w, doc=i, id=f"{i}:{w['page']}:{w['i']}", N=len(v), n=len(pick))
                sample.append(w)
        print(i, d["kind"], len(ws), dict(Counter(w["stratum"] for w in ws)), flush=True)
    sample.sort(key=lambda w: (w["doc"], w["page"]))
    for w in sample:
        p = OUT / "crops" / (w["id"].replace(":", "_") + ".png")
        if not p.exists(): cv2.imwrite(str(p), crop_word(OUT / "docs" / w["doc"] / f"{w['doc']}.pdf", w))
    json.dump(sample, open(OUT / "sample.json", "w"), ensure_ascii=False, indent=0)
    json.dump(pop, open(OUT / "population.json", "w"), ensure_ascii=False, indent=1)
    print(len(sample), "words sampled from", len(pop), "documents;", dict(Counter(w["stratum"] for w in sample)))
