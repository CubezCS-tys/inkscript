"""Experiment 83, step 1: choose the new documents for the reader's scale-up (no network; the catalogue read only).

    nice -n 19 ionice -c3 .venv/bin/python experiments/83_reader_scale/select83.py

Reads the catalogue (marc.db, read-only, as experiment 80's select80.py), experiment 44's bucket listing (object
sizes) and experiment 76's held-out split.  Writes out/data/candidates83.jsonl (every eligible document) and
out/data/plan83.jsonl (the chosen ones, in fetch order).

Eligible: language 'ara', type in TYPES (as experiment 80), 1900-2025, in the main bucket with both <id>.pdf and
<id>.json, 2-40 printed pages, journal NOT among the 27 held-out codes of split76.json "test", document not on this
machine (out/data/ondisk83.txt: every <id>.pdf|json name under /home/appuser, AI-Search not walked; plus experiment
76's inventory and experiment 80's pull).
Choice: 3,600 pre-2000 documents with a quota per decade (heavier before 1970), and 4,400 documents from 2000 on
with a quota per 5-year span; inside each bucket journals are taken round-robin in random order (one document per
journal per round, at most CAP documents per journal per bucket), so as many journals as possible appear.
The host cuts at most MAX_PAGES pages of each document.
"""
from __future__ import annotations

import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
DATA = HERE / "out/data"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = EXP / "44_bucket_map/out/ids_main.txt"
LISTING = EXP / "44_bucket_map/out/listing"
SPLIT = EXP / "76_finetune_pilot/out/split76.json"
INVENTORY = EXP / "76_finetune_pilot/out/inventory76.jsonl"
PULL80 = EXP / "80_old_print_pull/data"
TYPES = ("بحوث ومقالات", "نصوص أدبية", "بحوث المؤتمرات", "عروض كتب", "افتتاحيات", "عروض رسائل")
# pre-2000: 3,600 documents (about 45% of the documents; old print is 6% of what is on disk)
QUOTA_OLD = {1900: 40, 1910: 60, 1920: 250, 1930: 350, 1940: 400, 1950: 450, 1960: 500, 1970: 500, 1980: 520,
             1990: 530}
# 2000 on: 4,400 documents, by 5-year span
QUOTA_MOD = {2000: 700, 2005: 800, 2010: 950, 2015: 1000, 2020: 950}
CAP = {"old": 60, "mod": 8}        # documents per journal per bucket
# Pages cut per document (chosen at random per document on the host, cut83.py): modern pages carry ~60 Azure lines
# and old ones ~42 (experiment 77's pages77.jsonl), so whole modern documents would give ~5M lines; 6 pages each keeps
# the documents and journals many and the lines near 3.5M, with old print ~55% of the new lines.
MAX_PAGES = {"pre2000": 20, "modern": 6}
SEED = 83
STEM = re.compile(r"^(\d{4}-\d{3}-\d{3}-\d{3})/\1\.(pdf|json)$")


def npages(pages, pf, pl):
    if pf and pl and pl >= pf:
        return pl - pf + 1
    m = re.search(r"\d+", pages or "")
    return int(m.group()) if m else None


def bucket(y):
    return (y // 10 * 10, "old") if y < 2000 else (min(2020, y // 5 * 5), "mod")


def main():
    DATA.mkdir(parents=True, exist_ok=True)
    held = set(json.loads(SPLIT.read_text())["test"])
    have = {json.loads(l)["stem"] for l in INVENTORY.read_text().splitlines() if l.strip()}
    for f in (DATA / "ondisk83.txt", PULL80 / "ondisk80.txt", PULL80 / "ids80.txt"):
        have |= set(f.read_text().split())
    print(len(have), "documents on this machine (excluded)")
    main_ids = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    q = f"""select p.stem, r.year_int, r.journal_code, r.journal, r.type, r.pages, r.page_first, r.page_last
            from records r join pdf_ids p on p.rec = r.rec
            where r.year_int >= 1900 and r.year_int <= 2025 and r.language = 'ara'
              and r.type in ({','.join('?' * len(TYPES))})"""
    cand = {}
    for stem, y, jc, j, t, pg, pf, pl in c.execute(q, TYPES):
        if stem in cand or stem not in main_ids or stem in have or not jc or jc in held:
            continue
        n = npages(pg, pf, pl)
        if not n or not 2 <= n <= 40:
            continue
        b, era = bucket(y)
        e = "pre2000" if era == "old" else "modern"
        cand[stem] = dict(id=stem, year=y, bucket=b, era=e, jcode=jc, journal=j, type=t, printed_pages=n,
                          max_pages=MAX_PAGES[e])
    print(len(cand), "catalogue candidates")
    sizes = defaultdict(dict)
    for f in sorted(LISTING.glob("mandumah-source-docs__*.tsv")):
        for line in f.open(encoding="utf-8"):
            k, b = line.split("\t", 2)[:2]
            m = STEM.match(k)
            if m and m.group(1) in cand:
                sizes[m.group(1)][m.group(2)] = int(b)
    for s in list(cand):
        z = sizes.get(s, {})
        if "pdf" not in z or "json" not in z:
            del cand[s]
            continue
        cand[s].update(pdf_bytes=z["pdf"], json_bytes=z["json"])
    print(len(cand), "with pdf+json in the listing")
    with (DATA / "candidates83.jsonl").open("w", encoding="utf-8") as fh:
        for s in sorted(cand):
            fh.write(json.dumps(cand[s], ensure_ascii=False) + "\n")

    rng = random.Random(SEED)
    by = defaultdict(lambda: defaultdict(list))
    for d in cand.values():
        by[d["bucket"]][d["jcode"]].append(d)
    plan, report = [], []
    for b in sorted(by):
        old = b < 2000
        quota = (QUOTA_OLD if old else QUOTA_MOD).get(b, 0)
        cap = CAP["old" if old else "mod"]
        js = sorted(by[b])
        rng.shuffle(js)
        for j in js:
            rng.shuffle(by[b][j])
        got, used = 0, Counter()
        for rnd in range(cap):
            for j in js:
                if got >= quota:
                    break
                if rnd < len(by[b][j]):
                    plan.append(by[b][j][rnd])
                    got += 1
                    used[j] += 1
        report.append(dict(bucket=b, journals_available=len(js), docs_available=sum(map(len, by[b].values())),
                           chosen=got, journals_chosen=len(used)))
        print(b, "journals", len(js), "docs", sum(map(len, by[b].values())), "chosen", got, "from", len(used), "journals")
    # fetch order: interleave buckets so a stop at any point leaves a balanced set
    per = defaultdict(list)
    for d in plan:
        per[d["bucket"]].append(d)
    order = []
    while any(per.values()):
        for b in sorted(per):
            if per[b]:
                order.append(per[b].pop(0))
    with (DATA / "plan83.jsonl").open("w", encoding="utf-8") as fh:
        for d in order:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    gb = sum(d["pdf_bytes"] + d["json_bytes"] for d in order) / 1e9
    summ = dict(chosen=len(order), pre2000=sum(d["era"] == "pre2000" for d in order),
                printed_pages=sum(d["printed_pages"] for d in order),
                pages_to_cut=sum(min(d["printed_pages"], d["max_pages"]) for d in order), gb=round(gb, 2),
                journals=len({d["jcode"] for d in order}),
                journals_pre2000=len({d["jcode"] for d in order if d["era"] == "pre2000"}), buckets=report)
    (DATA / "plan83_summary.json").write_text(json.dumps(summ, ensure_ascii=False, indent=1))
    print(json.dumps({k: v for k, v in summ.items() if k != "buckets"}))


if __name__ == "__main__":
    main()
