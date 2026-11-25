"""Experiment 102, step 2: the nested training sets S (20,000) < M (200,000) < L (1,000,000) and the DEV set (2,000),
drawn by a fixed seed (102) from pool102 (pool102.py), stratified by period and journal, display-face titles in.

    nice -n 19 ../81_heldout_scale/out/venv/bin/python build102.py    -> out/sets/{S,M,L_local,dev}.jsonl + sets102_summary.json

Rules (written before any model output):
- Lines with fewer than 3 non-space characters are left out (the exam's R1 lines are 3+ characters).
- DEV = 500 lines from each period, drawn from whole DEV DOCUMENTS that no training set touches: all 40 of experiment
  77's dev documents (no reader has trained on them) plus, per period where those hold fewer than 600 lines or 8
  documents, documents drawn at random from the pool (seed 102) until both hold.  DEV holds no catalogue title line.
- Training periods: S and M take 40% 2000+, 20% each 1980-99 / 1950-79 / pre-1950 (the pool is 55% modern; old print
  is where readers differ most).  L takes every remaining local line (about 0.63 M) and is completed to 1,000,000 on
  the host from experiment 83's new documents (rule in L_n83_rule.json; not drawn here: those lines are not on disk).
- Inside a period the order is journal round-robin (journals in random order), inside a journal document
  round-robin, inside a document random: each next line comes from the journal that has given fewest so far.
  S, M and L are prefixes of the same order, so S is inside M and M inside L.
- Every title line of the pool (experiment 91's catalogue-matched page-1 titles, 824 of them display size) goes into
  S first (and so into M and L); they count against their period's quota.
- The builder REFUSES to write anything if one key of any set fails guard102.assert_trainable, if a label source is
  not allowed (guard102.assert_sources), or if a DEV document appears in a training set.
"""
from __future__ import annotations

import gzip
import hashlib
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import guard102 as G  # noqa: E402

POOL = HERE / "out/pool/pool102.jsonl.gz"
OUT = HERE / "out/sets"
SEED = 102
ERAS = ["2000+", "1980-1999", "1950-1979", "pre-1950"]
SHARE = {"2000+": 0.4, "1980-1999": 0.2, "1950-1979": 0.2, "pre-1950": 0.2}
SIZES = {"S": 20_000, "M": 200_000, "L": 1_000_000}
DEV_PER_ERA, DEV_MIN_LINES, DEV_MIN_DOCS = 500, 600, 8
FIELDS = ("key", "stem", "page", "i", "jcode", "year", "era", "src", "label", "label_source", "title", "display", "kind")


def nonspace(s: str) -> int:
    return sum(1 for ch in s if not ch.isspace())


def h(s: str) -> int:
    return int(hashlib.md5(f"{SEED}:{s}".encode()).hexdigest()[:12], 16)


def rr_order(rows: list[dict], rng: random.Random) -> list[dict]:
    """journal round-robin, document round-robin inside a journal, random inside a document."""
    by_j = defaultdict(lambda: defaultdict(list))
    for r in rows:
        by_j[r["jcode"]][r["stem"]].append(r)
    jorder = []
    for j in sorted(by_j):
        docs = sorted(by_j[j])
        rng.shuffle(docs)
        for d in docs:
            rng.shuffle(by_j[j][d])
        seq, k = [], 0                                   # interleave the journal's documents
        while True:
            took = False
            for d in docs:
                if k < len(by_j[j][d]):
                    seq.append(by_j[j][d][k])
                    took = True
            if not took:
                break
            k += 1
        jorder.append((j, seq))
    rng.shuffle(jorder)
    out, k = [], 0                                       # interleave journals
    while True:
        took = False
        for _, seq in jorder:
            if k < len(seq):
                out.append(seq[k])
                took = True
        if not took:
            return out
        k += 1


def build(pool: list[dict]) -> dict:
    rng = random.Random(SEED)
    pool = [r for r in pool if nonspace(r["label"]) >= 3 and r["era"] in ERAS]
    # ---- DEV documents
    docs_era = defaultdict(lambda: defaultdict(int))
    for r in pool:
        docs_era[r["era"]][r["stem"]] += 1
    dev_docs = {r["stem"] for r in pool if r["part"] == "dev"}
    for e in ERAS:
        have = sum(n for s, n in docs_era[e].items() if s in dev_docs)
        nd = sum(1 for s in docs_era[e] if s in dev_docs)
        cand = sorted((s for s in docs_era[e] if s not in dev_docs), key=h)
        for s in cand:
            if have >= DEV_MIN_LINES and nd >= DEV_MIN_DOCS:
                break
            dev_docs.add(s)
            have += docs_era[e][s]
            nd += 1
    dev_pool = [r for r in pool if r["stem"] in dev_docs and not r["title"]]
    dev = []
    for e in ERAS:
        L = sorted((r for r in dev_pool if r["era"] == e), key=lambda r: h(r["key"]))
        dev += L[:DEV_PER_ERA]
    train = [r for r in pool if r["stem"] not in dev_docs]
    # ---- training order per period, titles first
    order = {}
    for e in ERAS:
        rows = [r for r in train if r["era"] == e]
        t = [r for r in rows if r["title"]]
        t.sort(key=lambda r: h(r["key"]))
        order[e] = t + rr_order([r for r in rows if not r["title"]], rng)
    sets = {}
    for name in ("S", "M"):
        sel = []
        for e in ERAS:
            n = round(SIZES[name] * SHARE[e])
            if n > len(order[e]):
                raise SystemExit(f"{name}: period {e} needs {n} lines, pool has {len(order[e])}")
            sel += order[e][:n]
        sets[name] = sel
    sets["L_local"] = [r for e in ERAS for r in order[e]]
    # ---- the guard: refuse on any locked / held-out key, any disallowed source, any DEV document in training
    for name, rows in list(sets.items()) + [("dev", dev)]:
        G.assert_trainable(r["key"] for r in rows)
        G.assert_sources(r["label_source"] for r in rows)
    tr_docs = {r["stem"] for r in sets["L_local"]}
    clash = tr_docs & {r["stem"] for r in dev}
    if clash:
        raise AssertionError(f"DEV documents in training: {sorted(clash)[:5]}")
    keysS, keysM = {r["key"] for r in sets["S"]}, {r["key"] for r in sets["M"]}
    assert keysS <= keysM <= {r["key"] for r in sets["L_local"]}, "sets not nested"
    sets["dev"] = dev
    sets["_dev_docs"] = sorted(dev_docs)
    return sets


def summary(rows: list[dict]) -> dict:
    return dict(lines=len(rows), documents=len({r["stem"] for r in rows}), journals=len({r["jcode"] for r in rows}),
                by_era=dict(Counter(r["era"] for r in rows)), by_kind=dict(Counter(r["kind"] for r in rows)),
                by_label_source=dict(Counter(r["label_source"] for r in rows)),
                titles=sum(r["title"] for r in rows), display_titles=sum(r["display"] for r in rows),
                top_journal_share=round(max(Counter(r["jcode"] for r in rows).values()) / max(1, len(rows)), 4),
                letters=sum(nonspace(r["label"]) for r in rows))


def main():
    pool = [json.loads(l) for l in gzip.open(POOL, "rt", encoding="utf-8")]
    sets = build(pool)
    OUT.mkdir(parents=True, exist_ok=True)
    summ = {}
    for name in ("S", "M", "L_local", "dev"):
        rows = sets[name]
        with open(OUT / f"{name}.jsonl.tmp", "w", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps({k: r[k] for k in FIELDS}, ensure_ascii=False) + "\n")
        (OUT / f"{name}.jsonl.tmp").rename(OUT / f"{name}.jsonl")
        summ[name] = summary(rows)
    (OUT / "dev_documents.json").write_text(json.dumps(sets["_dev_docs"], indent=0))
    need = SIZES["L"] - len(sets["L_local"])
    rule = dict(
        note="L = L_local (every local line not in DEV) + this many lines of experiment 83's new documents, drawn ON THE "
             "HOST after cut83's deterministic re-cut (exp 89/91 recipe), only if the lead approves the S3 egress "
             "(about 27.5 GB of PDF + JSON for all 7,763 documents; fewer if only the needed documents are fetched).",
        n83_lines_needed=need,
        labels="consensus: a new line is trained on when its key is not in held_v3 (v1 = Azure, exp 83); a held line takes "
               "v6r's label (judged or rule85) or is dropped; (( )) labels dropped; experiment 91 title overrides applied",
        order="the same period shares as S/M for the n83 part (40/20/20/20), journal round-robin, seed 102",
        guard="guard102.assert_trainable on every n83 key before training (train102.py also re-checks every key)")
    (OUT / "L_n83_rule.json").write_text(json.dumps(rule, indent=1))
    summ["L_n83_needed"] = need
    (OUT / "sets102_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps(summ, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
