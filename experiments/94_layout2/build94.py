"""Experiment 94, step 1: the training pool and the fine-typed test reference.

    python build94.py train   -> out/train94.jsonl  one row per usable training page:
                                 {key, stem, page, jcode, set, pdf, W, H, split (train|val),
                                  lines: [{poly, fine (None = Argon left it out), orient, rank, block}]}
    python build94.py ref     -> out/ref94.jsonl    experiment 92's ref92.jsonl + each line's fine type
                                 out/byline94_sample.json  60 test byline lines with their split, for the hand check

Training pool: experiment 76's inventory, answered articles (first copy of each stem) whose Argon raw files exist, of
journals NOT in split76's held-out list, not locked (both guards), no document of experiment 92's test set.  A page is
usable as in experiment 92: Argon gave blocks, >= 5 non-empty Azure lines, Argon placed >= 80% of them.  Validation:
3% of documents (seed 94).
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter

from common94 import (E92, OUT, RAWS, argon_doc, assert_not_locked, azure_lines, fine_of, fixpath, heldout_codes,
                      is_locked_any, orient_of)

INV = OUT.parent.parent / "76_finetune_pilot/out/inventory76.jsonl"


def test_docs() -> set[str]:
    return {json.loads(l)["stem"] for l in open(E92 / "pages92.jsonl", encoding="utf-8")}


def train():
    held, tdocs = heldout_codes(), test_docs()
    done, rows, skipped = set(), [], Counter()
    for l in open(INV, encoding="utf-8"):
        a = json.loads(l)
        if not a["answered"] or a["stem"] in done or a["set"] not in RAWS:
            continue
        done.add(a["stem"])
        if a["jcode"] in held:
            skipped["heldout"] += 1
            continue
        if is_locked_any(a["stem"]):
            skipped["locked"] += 1
            continue
        if a["stem"] in tdocs:
            skipped["test92"] += 1
            continue
        az, pdf = fixpath(a["azure"]), fixpath(a["pdf"])
        if not (az.exists() and pdf.exists()):
            skipped["missing"] += 1
            continue
        AP, authors = argon_doc(RAWS[a["set"]], a["stem"])
        for p, blocks in sorted(AP.items()):
            try:
                lines, W, H = azure_lines(str(az), p)
            except IndexError:
                continue
            n = len(lines)
            info, rank = {}, 0
            for bi, b in enumerate(blocks):
                for i in b["ids"]:
                    if i not in info:
                        info[i] = (b["type"], bi, rank)
                        rank += 1
            if n < 5 or len(set(info) & {x["i"] for x in lines}) < 0.8 * n:
                continue
            out = []
            for x in lines:
                if not x["poly"]:
                    continue
                t, bi, rk = info.get(x["i"], (None, None, None))
                out.append(dict(i=x["i"], poly=[round(v, 4) for v in x["poly"]],
                                fine=fine_of(t, x["text"], authors) if t else None,
                                orient=orient_of(x["poly"]), rank=rk, block=bi))
            rows.append(dict(key=f"{a['stem']}_p{p:03d}", stem=a["stem"], page=p, jcode=a["jcode"], set=a["set"],
                             pdf=str(pdf), W=W, H=H, lines=out))
        if len(done) % 100 == 0:
            print(len(done), len(rows), flush=True)
    keys = [r["key"] for r in rows]
    assert_not_locked(keys)
    assert not {r["jcode"] for r in rows} & held
    assert not {r["stem"] for r in rows} & tdocs
    docs = sorted({r["stem"] for r in rows})
    rnd = random.Random(94)
    rnd.shuffle(docs)
    val = set(docs[: max(1, int(0.03 * len(docs)))])
    with open(OUT / "train94.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            r["split"] = "val" if r["stem"] in val else "train"
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    c = Counter(x["fine"] for r in rows for x in r["lines"])
    o = Counter(x["orient"] for r in rows for x in r["lines"])
    st = dict(pages=len(rows), docs=len(docs), val_docs=len(val), val_pages=sum(r["split"] == "val" for r in rows),
              journals=Counter(r["jcode"] for r in rows), fine=c, orient=o, skipped=skipped)
    json.dump(st, open(OUT / "train94_stats.json", "w"), indent=1, default=str)
    print(json.dumps(st, default=str))


def ref():
    pages = {json.loads(l)["key"]: json.loads(l) for l in open(E92 / "pages92.jsonl", encoding="utf-8")}
    assert_not_locked(list(pages))
    authors_of, sample = {}, []
    with open(OUT / "ref94.jsonl", "w", encoding="utf-8") as f:
        for l in open(E92 / "ref92.jsonl", encoding="utf-8"):
            r = json.loads(l)
            pg = pages[r["key"]]
            if pg["stem"] not in authors_of:
                authors_of[pg["stem"]] = argon_doc(RAWS[pg["set"]], pg["stem"])[1]
            for x in r["lines"]:
                x["fine"] = fine_of(x["type"], x["text"], authors_of[pg["stem"]]) if x["type"] else None
                x["orient"] = orient_of(x["poly"]) if x["poly"] else None
                if x["type"] == "byline":
                    sample.append(dict(key=r["key"], i=x["i"], text=x["text"], fine=x["fine"]))
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    print(len(sample), "byline lines;", Counter(s["fine"] for s in sample))
    json.dump(sample, open(OUT / "byline94_all.json", "w"), ensure_ascii=False, indent=0)


if __name__ == "__main__":
    {"train": train, "ref": ref}[sys.argv[1]]()
