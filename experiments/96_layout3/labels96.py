"""Experiment 96, goal 1, step 2: the training labels for the layout round (local, before the GPU host).

    python labels96.py   -> out/train96.jsonl   experiment 94's training pool rows (same lines, fine types) with the
                                                catalogue changes the eye check kept, + a repeat count per page
                            out/extra96.jsonl   EXTRA pages (experiments 77/80 documents, no Argon): Azure lines
                                                (poly), catalogue labels for the matched lines; the other lines get
                                                the stage-2 model's type on the host (prep96.py pseudo)
                            out/labels96_stats.json

Pool changes kept (eye check, out/spot96_hand.json): a catalogue author line that Argon typed title / heading /
caption / other becomes author.  Rejected: body -> author (a sentence or citation naming the author), affiliation ->
author (a name and a post on one line: the metadata split stays), any change to affiliation (6 of 8 looked at wrong).
Up-weighting: a training page holding an author or affiliation line is repeated REP times (hard-linked copies on the
host), so these lines are seen REP + 1 times per epoch; the validation split is not repeated.
"""
from __future__ import annotations

import json
from collections import Counter

from common96 import O94, OUT, azure_lines, guard_training

REP = 4
OK_FROM = {"title", "heading", "caption", "other", None}


def main():
    cat = {}
    for l in open(OUT / "authors96.jsonl", encoding="utf-8"):
        r = json.loads(l)
        cat[r["key"]] = {int(i): v for i, v in r["labels"].items()}
    st = Counter()
    keys = []
    with open(OUT / "train96.jsonl", "w", encoding="utf-8") as f:
        for l in open(O94 / "train94.jsonl", encoding="utf-8"):
            r = json.loads(l)
            c = cat.get(r["key"], {})
            for x in r["lines"]:
                v = c.get(x["i"])
                if v == "author" and x["fine"] in OK_FROM and x["fine"] != "author":
                    st[f"changed {x['fine']}->author"] += 1
                    x["fine"] = "author"
            has = any(x["fine"] in ("author", "affiliation") for x in r["lines"])
            r["rep"] = REP if (has and r["split"] == "train") else 0
            st["pages"] += 1
            st["pages_repeated"] += r["rep"] > 0
            keys.append(r["key"])
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    n = 0
    with open(OUT / "extra96.jsonl", "w", encoding="utf-8") as f:
        for l in open(OUT / "authors96_extra.jsonl", encoding="utf-8"):
            r = json.loads(l)
            L, W, H = azure_lines(r["azure"], r["page"])
            lab = {int(i): v for i, v in r["labels"].items()}
            row = dict(key=r["key"], stem=r["stem"], page=r["page"], jcode=r["jcode"], pdf=r["pdf"], W=W, H=H,
                       split="train", rep=REP, extra=True,
                       lines=[dict(i=x["i"], poly=[round(v, 4) for v in x["poly"]], fine=lab.get(x["i"]))
                              for x in L if x["poly"]])
            st["extra_pages"] += 1
            st["extra_author"] += sum(v == "author" for v in lab.values())
            st["extra_affiliation"] += sum(v == "affiliation" for v in lab.values())
            keys.append(r["key"])
            n += 1
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
    guard_training(keys)
    json.dump(st, open(OUT / "labels96_stats.json", "w"), indent=1)
    print(dict(st))


if __name__ == "__main__":
    main()
