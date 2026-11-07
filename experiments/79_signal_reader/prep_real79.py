"""Experiment 79, rung 2: the real lines to reconstruct on the rented host (read only from experiments 76/77).

    nice -n 19 ionice -c3 python prep_real79.py [N_ARTICLES=400]   -> out/up_real/{jobs_train.jsonl, jobs_dev.jsonl, <stem>.pdf symlinks}

Training articles: N at random (seed 79) from experiment 77's training selection (select77.json "train": no held-out
journal); every selected page of each.  Dev: experiment 77's dev pages (40 articles of training journals, never
trained on), used only to set the fusion weight and the warning thresholds.
Per line: the key (experiment 77's), Azure's polygon in page units, the page size, and the label = clean_label(Azure)
with experiment 77's v2 overrides (labels_v2.jsonl: Gemini-judged replacements; null = dropped).  Only polygons and
labels and the PDFs leave this machine (the PDFs are what experiment 77 itself uploaded).
"""
from __future__ import annotations

import json
import os
import random
import sys
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "77_scratch_reader"))
from common77 import azure_pages, clean_label, nonempty_lines  # noqa: E402


def main(n_art: int = 400):
    od = HERE / "out/up_real"
    od.mkdir(parents=True, exist_ok=True)
    sel = json.loads((E / "77_scratch_reader/out/select77.json").read_text())
    meta = {}
    for l in open(E / "77_scratch_reader/out/pages77.jsonl", encoding="utf-8"):
        r = json.loads(l)
        meta[(r["stem"], r["page"])] = r
    over = {}
    for l in open(E / "77_scratch_reader/out/labels_v2.jsonl", encoding="utf-8"):
        d = json.loads(l)
        over[d["key"]] = d["label"]
    for split, n in (("dev", None), ("train", n_art)):
        by = defaultdict(list)
        for p in sel[split]:
            by[p["stem"]].append(p["page"])
        arts = sorted(by)
        random.Random(79).shuffle(arts)
        if n:
            arts = arts[:n]
        nl = drop = 0
        with open(od / f"jobs_{split}.jsonl", "w", encoding="utf-8") as fo:
            for a in arts:
                m = meta[(a, by[a][0])]
                pgs = azure_pages(m["azure"])
                job = dict(stem=a, pdf=f"{a}.pdf", pages=[])
                for page in sorted(by[a]):
                    if page - 1 >= len(pgs):
                        continue
                    pg = pgs[page - 1]
                    L = []
                    for ln in nonempty_lines(pg):
                        key = f"{a}_p{page:03d}_l{ln['i']:03d}"
                        lab = over.get(key, clean_label(ln["text"]))
                        if not lab or not ln["poly"]:
                            drop += 1
                            continue
                        L.append(dict(key=key, poly=ln["poly"], label=lab))
                    nl += len(L)
                    job["pages"].append(dict(page=page, width=pg["width"], height=pg["height"], lines=L))
                fo.write(json.dumps(job, ensure_ascii=False) + "\n")
                link = od / f"{a}.pdf"
                if not link.exists():
                    os.symlink(m["pdf"], link)
        mb = sum(os.path.getsize(od / f"{a}.pdf") for a in arts) / 1e6
        print(split, len(arts), "articles", nl, "lines", drop, "dropped", f"{mb:.0f} MB of PDF")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 400)
