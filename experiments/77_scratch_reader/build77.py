"""Experiment 77, step 1b: choose the pilot pages and cut their lines into tar shards.

    python build77.py select        -> out/select77.json (pages chosen, lines expected)
    python build77.py build [N]     -> out/shards/train-XXXX.tar  (+ out/shards/manifest.jsonl), N workers (<= 4)

Choice: every pre-2000 page (old print is scarce: 3,354 pages, 142k lines), then modern pages at random (seed 77) up
to TARGET lines, no journal over JCAP lines.  A few articles are held back entirely as a held-in dev set (journals
seen in training, articles not).  Each line: Azure's polygon -> upright crop, padded, height 48, grey JPEG q80;
label = clean_label(Azure's text).  Shard member names: <key>.jpg and <key>.txt; the manifest has the metadata.
"""
from __future__ import annotations

import io
import json
import os
import random
import sys
import tarfile
import time
from collections import Counter, defaultdict
from multiprocessing import Pool

from common77 import OUT, azure_pages, clean_label, cut_line, encode, nonempty_lines, render_page

TARGET = 520_000
JCAP = 38_000
DEV_ARTICLES = 40
SHARD = 5000


def era(y):
    try:
        return "pre2000" if int(str(y)[:4]) < 2000 else "modern"
    except ValueError:
        return "modern"


def select():
    P = [json.loads(l) for l in open(OUT / "pages77.jsonl", encoding="utf-8")]
    rng = random.Random(77)
    stems = sorted({p["stem"] for p in P})
    rng.shuffle(stems)
    dev = set(stems[:DEV_ARTICLES])
    old = [p for p in P if era(p["year"]) == "pre2000" and p["stem"] not in dev]
    mod = [p for p in P if era(p["year"]) == "modern" and p["stem"] not in dev]
    rng.shuffle(mod)
    chosen = list(old)
    lines = sum(p["lines"] for p in old)
    per_j = Counter()
    for p in old:
        per_j[p["jcode"]] += p["lines"]
    for p in mod:
        if lines >= TARGET:
            break
        if per_j[p["jcode"]] + p["lines"] > JCAP:
            continue
        chosen.append(p)
        per_j[p["jcode"]] += p["lines"]
        lines += p["lines"]
    devp, per_a = [], Counter()
    for p in P:
        if p["stem"] in dev and per_a[p["stem"]] < 4:
            devp.append(p)
            per_a[p["stem"]] += 1
    res = dict(train=[dict(stem=p["stem"], page=p["page"]) for p in chosen],
               dev=[dict(stem=p["stem"], page=p["page"]) for p in devp],
               summary=dict(train_pages=len(chosen), train_lines_azure=lines,
                            train_articles=len({p["stem"] for p in chosen}),
                            train_journals=len({p["jcode"] for p in chosen}),
                            pre2000_pages=len(old), pre2000_lines=sum(p["lines"] for p in old),
                            dev_articles=len(dev), dev_pages=len(devp), dev_lines=sum(p["lines"] for p in devp),
                            top_journals=per_j.most_common(12)))
    (OUT / "select77.json").write_text(json.dumps(res, ensure_ascii=False, indent=0))
    print(json.dumps(res["summary"], ensure_ascii=False, indent=1))


def work(args):
    wid, split, jobs = args
    import cv2
    import pypdfium2 as pdfium
    cv2.setNumThreads(2)
    meta = {}
    for f in ("pages77.jsonl", "pages80.jsonl"):
        if (OUT / f).exists():
            meta.update({p["stem"]: p for p in (json.loads(l) for l in open(OUT / f, encoding="utf-8"))})
    sd = OUT / "shards"
    shard_no, n_in, tar, mf = 0, 0, None, open(sd / f"manifest-{split}-{wid}.jsonl", "w", encoding="utf-8")
    skipped = Counter()
    done = 0
    t0 = time.time()
    for stem, pages in jobs:
        m = meta[stem]
        try:
            pdf = pdfium.PdfDocument(m["pdf"])
            pgs = azure_pages(m["azure"])
        except Exception as e:  # noqa: BLE001
            skipped["article_error"] += 1
            print(wid, stem, "error", e, flush=True)
            continue
        for page in pages:
            if page - 1 >= len(pdf) or page - 1 >= len(pgs):
                skipped["page_missing"] += 1
                continue
            pg = pgs[page - 1]
            img = render_page(pdf, page - 1)
            sx, sy = img.shape[1] / pg["width"], img.shape[0] / pg["height"]
            for ln in nonempty_lines(pg):
                lab = clean_label(ln["text"])
                if not lab or not ln["poly"]:
                    skipped["empty"] += 1
                    continue
                crop, info = cut_line(img, ln["poly"], sx, sy)
                if crop is None:
                    skipped[info["reason"]] += 1
                    continue
                if tar is None or n_in >= SHARD:
                    if tar:
                        tar.close()
                    tar = tarfile.open(sd / f"{split}-{wid}-{shard_no:03d}.tar", "w")
                    shard_no += 1
                    n_in = 0
                key = f"{stem}_p{page:03d}_l{ln['i']:03d}"
                for name, data in ((key + ".jpg", encode(crop)), (key + ".txt", lab.encode("utf-8"))):
                    ti = tarfile.TarInfo(name)
                    ti.size = len(data)
                    tar.addfile(ti, io.BytesIO(data))
                n_in += 1
                mf.write(json.dumps(dict(key=key, stem=stem, page=page, i=ln["i"], jcode=m["jcode"], year=m["year"],
                                         W=info["W"], label=lab, shard=f"{split}-{wid}-{shard_no - 1:03d}.tar"),
                                    ensure_ascii=False) + "\n")
            done += 1
            if done % 200 == 0:
                print(f"w{wid} {split}: {done} pages, {time.time() - t0:.0f}s, skipped {dict(skipped)}", flush=True)
        pdf.close()
    if tar:
        tar.close()
    mf.close()
    return dict(wid=wid, pages=done, skipped=dict(skipped))


def build(nw: int, splits=("dev", "train")):
    sel = json.loads((OUT / "select77.json").read_text())
    (OUT / "shards").mkdir(exist_ok=True)
    (OUT / "build77.pid").write_text(str(os.getpid()))
    res = []
    for split in splits:
        by = defaultdict(list)
        src = sel[split] if split != "old80" else [json.loads(l) for l in open(OUT / "pages80.jsonl", encoding="utf-8")]
        for p in src:
            by[p["stem"]].append(p["page"])
        arts = sorted(by.items())
        random.Random(1).shuffle(arts)
        jobs = [(w, split, arts[w::nw]) for w in range(nw)]
        with Pool(nw, maxtasksperchild=1) as pool:
            r = pool.map(work, jobs)
        res += r
        print(split, r, flush=True)
    (OUT / "build77_result.json").write_text(json.dumps(res, indent=1))


if __name__ == "__main__":
    if sys.argv[1] == "select":
        select()
    else:
        build(min(2, int(sys.argv[2]) if len(sys.argv) > 2 else 2), tuple(sys.argv[3].split(",")) if len(sys.argv) > 3 else ("dev", "train"))   # shared box: at most 2 workers (lead, 2026-11-04)
