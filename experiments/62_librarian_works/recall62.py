"""Experiment 62, step 5c: how much does the blocking miss? A recall audit.

150 cards drawn at random (seed 6263). For each, a deliberately loose search of the whole catalogue of cards: any
other card sharing a rare title word (in <= 60 cards), one letter forgiven, or sharing an author surname with any
title word in common, ranked by letter similarity, the top 6 that the blocking did NOT already pair. The librarian
reads them (audit62.json, its calls) and counts the true duplicates the blocking missed.

    python3 recall62.py view     -> out/recall62_view.txt
    python3 recall62.py score    -> out/recall62.json (needs recall62_calls.json: {"<a>|<b>": "same"|"edition"|...})
"""
from __future__ import annotations

import json
import random
import sys
from collections import Counter, defaultdict
from difflib import SequenceMatcher
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import near, tokens  # noqa: E402

SEED = 6263
N = 150


def view():
    from cands62 import features
    from tools62 import cards, view_card
    C = cards()
    F = {cid: features(c) for cid, c in C.items()}
    pairs = {(json.loads(l)["a"], json.loads(l)["b"]) for l in open(OUT / "pairs62.jsonl", encoding="utf-8")}
    df = Counter(w for f in F.values() for w in set(f["toks"]))
    idx = defaultdict(set)
    for cid, f in F.items():
        for w in set(f["toks"]):
            if df[w] <= 60:
                idx[w].add(cid)
    sur = defaultdict(set)
    for cid, f in F.items():
        for w in f["sur"]:
            sur[w].add(cid)
    ids = sorted(cid for cid, f in F.items() if f["toks"])
    rnd = random.Random(SEED)
    sample = rnd.sample(ids, N)
    lines, audit = [], []
    for i, cid in enumerate(sample):
        f = F[cid]
        cand = set()
        for w in set(f["toks"]):
            cand |= idx.get(w, set())
        for w in f["sur"]:
            for x in sur.get(w, ()):
                if set(F[x]["toks"]) & set(f["toks"]):
                    cand.add(x)
        cand.discard(cid)
        t = " ".join(f["toks"])
        scored = sorted(((SequenceMatcher(None, t, " ".join(F[x]["toks"])).ratio(), x) for x in cand
                         if tuple(sorted((cid, x))) not in pairs), reverse=True)[:6]
        lines.append(f"=== R{i} {cid}")
        lines.append(view_card(cid, n_members=1, width=110))
        for s, x in scored:
            lines.append(f"   ? {x} r{s:.2f} «{C[x]['title'][:90]}» au={'; '.join(a['printed'] for a in C[x]['authors'][:2])[:50]}")
            audit.append(dict(r=i, card=cid, other=x, ratio=round(s, 3)))
    (OUT / "recall62_view.txt").write_text("\n".join(lines), encoding="utf-8")
    (OUT / "recall62_audit.json").write_text(json.dumps(dict(seed=SEED, n=N, sample=sample, candidates=audit),
                                                        ensure_ascii=False, indent=0), encoding="utf-8")
    print(len(sample), len(audit))


def score():
    A = json.loads((OUT / "recall62_audit.json").read_text(encoding="utf-8"))
    calls = json.loads((HERE / "recall62_calls.json").read_text(encoding="utf-8"))
    pairs = [json.loads(l) for l in open(OUT / "pairs62.jsonl", encoding="utf-8")]
    from finalize62 import standing
    D = standing()
    found_same = {tuple(sorted(d["subject_keys"])) for d in D if d["level"] == "pair" and d["kind"] in ("same_work", "edition_of")}
    sample = set(A["sample"])
    found_for_sample = {p for p in found_same if p[0] in sample or p[1] in sample}
    missed = [k for k, v in calls.items() if v in ("same", "edition")]
    missed_cards = {k.split("|")[0] for k in missed}
    n_found = len(found_for_sample)
    R = dict(sample=len(sample), candidates_read=len(A["candidates"]), missed_duplicates=len(missed),
             missed=missed, found_by_blocking_for_sample=n_found,
             recall_estimate=round(n_found / max(1, n_found + len(missed)), 3),
             note="recall = duplicates the blocking found for the sampled cards / (those + the ones the loose audit "
                  "found that it missed); duplicates neither search reaches (translated titles, wholly different "
                  "titles of one work) are outside both, so this is an upper bound")
    (OUT / "recall62.json").write_text(json.dumps(R, ensure_ascii=False, indent=1), encoding="utf-8")
    print(R)


if __name__ == "__main__":
    {"view": view, "score": score}[sys.argv[1]]()
