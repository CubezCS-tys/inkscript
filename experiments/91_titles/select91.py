"""Experiment 91, step 1 (local, no network; the catalogue read only): the candidate documents for title lines.

    nice -n 19 ionice -c3 python3 select91.py     -> out/data/docs91.jsonl, out/data/select91.json

Sets (each document's page 1 is matched on the host, title91.py):
  plan83  - every document of experiment 83's plan83 (its training documents);
  r77     - experiment 77's train documents (select77.json "train");
  o80     - experiment 80's pull (pages80.jsonl);
  new     - NEW training-pool documents from experiment 83's candidates83.jsonl (eligible by 83's rule: language
            'ara', article-like types, 2-40 pages, pdf+json in the bucket, held-out journals excluded), not in the
            sets above: every pre-1950 one, NEW_QUOTA[era] more, journals round-robin (CAP per journal), seed 91.
NEVER: split76's held-out journals, experiment 84's locked journals, experiment 88's locked documents
(locked_old.assert_not_locked on every id, plus the held-out check).  Experiment 77's dev documents are left out
(they are the trainer's dev).
Each row: id, set, year, era, jcode, journal, title, subtitle (marc.db 245 $a / $b).
"""
from __future__ import annotations

import json
import random
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
sys.path.insert(0, str(E / "88_truth_and_lock"))
from locked_old import assert_not_locked, is_locked_any  # noqa: E402

MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
OUT = HERE / "out/data"
NEW_QUOTA = {"pre-1950": 10 ** 9, "1950-1999": 6000, "2000+": 1000}
CAP = {"pre-1950": 10 ** 9, "1950-1999": 40, "2000+": 6}
BUDGET_GB = 13.0          # S3 egress of the NEW documents: every JSON + the PDF of ~85% (the matched ones)
SEED = 91


def era(y) -> str:
    y = int(str(y)[:4])
    return "2000+" if y >= 2000 else "1950-1999" if y >= 1950 else "pre-1950"


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    held = set(json.loads((E / "76_finetune_pilot/out/split76.json").read_text())["test"])
    e77 = E / "77_scratch_reader/out"
    sets: dict[str, str] = {}
    for l in open(E / "83_reader_scale/out/data/plan83.jsonl", encoding="utf-8"):
        sets.setdefault(json.loads(l)["id"], "plan83")
    s77 = json.loads((e77 / "select77.json").read_text())
    dev77 = {r["stem"] for r in s77["dev"]}
    for r in s77["train"]:
        sets.setdefault(r["stem"], "r77")
    for l in open(e77 / "pages80.jsonl", encoding="utf-8"):
        sets.setdefault(json.loads(l)["stem"], "o80")
    cand = [json.loads(l) for l in open(E / "83_reader_scale/out/data/candidates83.jsonl", encoding="utf-8")]
    pool = [d for d in cand if d["id"] not in sets and d["id"] not in dev77 and d["jcode"] not in held
            and not is_locked_any(d["id"])]
    rng = random.Random(SEED)
    by = defaultdict(lambda: defaultdict(list))
    for d in pool:
        by[era(d["year"])][d["jcode"]].append(d)
    for e, js in sorted(by.items()):
        names = sorted(js)
        rng.shuffle(names)
        for j in names:                     # smallest documents first (S3 egress, the lead's rule of 2026-11-06)
            js[j].sort(key=lambda d: (d["json_bytes"] + d["pdf_bytes"], d["id"]))
        got = 0
        for rnd in range(min(CAP[e], max(len(v) for v in js.values()))):
            for j in names:
                if got >= NEW_QUOTA[e]:
                    break
                if rnd < len(js[j]):
                    sets[js[j][rnd]["id"]] = "new"
                    got += 1
            if got >= NEW_QUOTA[e]:
                break
    size = {d["id"]: d["json_bytes"] + 0.85 * d["pdf_bytes"] for d in pool}
    gb = sum(size[i] for i, v in sets.items() if v == "new") / 1e9
    print(f"new documents: {sum(v == 'new' for v in sets.values())}, estimated egress {gb:.1f} GB")
    assert gb <= BUDGET_GB, "over the egress budget"
    ids = sorted(sets)
    assert_not_locked(ids)
    assert not [i for i in ids if i[:4] in held], "held-out journal"
    assert not [i for i in ids if i in dev77], "exp 77 dev document"
    c = sqlite3.connect(MARC, uri=True)
    rows, miss = [], Counter()
    q = """select r.title, r.subtitle, r.year_int, r.journal_code, r.journal from pdf_ids p join records r on r.rec = p.rec
           where p.stem = ?"""
    for i in ids:
        r = c.execute(q, (i,)).fetchone()
        if not r or not r[0] or not r[2]:
            miss[sets[i]] += 1
            continue
        rows.append(dict(id=i, set=sets[i], year=r[2], era=era(r[2]), jcode=i[:4], journal=r[4] or "", title=r[0],
                         subtitle=r[1] or ""))
    rng.shuffle(rows)                       # fetch order: mixed, so a stop leaves a balanced set
    with open(OUT / "docs91.jsonl", "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    st = dict(docs=len(rows), no_catalogue_title=dict(miss), by_set=Counter(r["set"] for r in rows),
              by_era=Counter(r["era"] for r in rows), by_set_era=Counter(f"{r['set']}|{r['era']}" for r in rows),
              journals=len({r["jcode"] for r in rows}), new_pool=Counter(era(d["year"]) for d in pool))
    (OUT / "select91.json").write_text(json.dumps(st, ensure_ascii=False, indent=1))
    print(json.dumps(st, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
