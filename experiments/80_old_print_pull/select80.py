"""Experiment 80: choose old-print documents (published before 2000) to pull from the corpus bucket.

No network. Reads the catalogue (marc.db, read-only), experiment 44's bucket listing (object sizes) and
experiment 76's held-out split; writes data/candidates80.jsonl (every eligible document) and data/ids80.txt +
data/plan80.jsonl (the chosen ones, in fetch order).

    nice -n 19 .venv/bin/python experiments/80_old_print_pull/select80.py [--ondisk FILE]

Eligible: catalogue year_int < 2000, language 'ara', type in TYPES, in the main bucket with both <id>.pdf and
<id>.json, 2-40 printed pages, journal not in split76 "test", document not already on this machine (--ondisk: a
file of ids found on disk; experiment 76's inventory is always excluded too).
Choice: a quota per decade (heavier before 1970); inside a decade, round-robin over journals in random order
(one document per journal per round, at most MAX_PER_JOURNAL_DECADE per journal), so as many journals as possible appear.
"""
from __future__ import annotations

import argparse
import json
import random
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
DATA = HERE / "data"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = EXP / "44_bucket_map/out/ids_main.txt"
LISTING = EXP / "44_bucket_map/out/listing"
SPLIT = EXP / "76_finetune_pilot/out/split76.json"
INVENTORY = EXP / "76_finetune_pilot/out/inventory76.jsonl"
TYPES = ("بحوث ومقالات", "نصوص أدبية", "بحوث المؤتمرات", "عروض كتب", "افتتاحيات", "عروض رسائل")
QUOTA = {1900: 20, 1910: 20, 1920: 70, 1930: 80, 1940: 85, 1950: 85, 1960: 80, 1970: 65, 1980: 60, 1990: 55}
MAX_PER_JOURNAL_DECADE = 40   # only binds where a decade has few journals (1920s-1940s)
SEED = 80
STEM = re.compile(r"^(\d{4}-\d{3}-\d{3}-\d{3})/\1\.(pdf|json)$")


def npages(pages, pf, pl):
    if pf and pl and pl >= pf:
        return pl - pf + 1
    m = re.search(r"\d+", pages or "")
    return int(m.group()) if m else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--ondisk")
    a = ap.parse_args()
    DATA.mkdir(parents=True, exist_ok=True)
    held = set(json.loads(SPLIT.read_text())["test"])
    have = {json.loads(l)["stem"] for l in INVENTORY.read_text().splitlines() if l.strip()}
    if a.ondisk:
        have |= set(Path(a.ondisk).read_text().split())
    main_ids = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    q = f"""select p.stem, r.rec, r.year_int, r.journal_code, r.journal, r.type, r.pages, r.page_first, r.page_last,
                   r.volume, r.issue, r.title
            from records r join pdf_ids p on p.rec = r.rec
            where r.year_int < 2000 and r.year_int > 1800 and r.language = 'ara'
              and r.type in ({','.join('?' * len(TYPES))})"""
    cand = {}
    for stem, rec, y, jc, j, t, pg, pf, pl, vol, iss, title in c.execute(q, TYPES):
        if stem in cand or stem not in main_ids or stem in have or jc in held or not jc:
            continue
        n = npages(pg, pf, pl)
        if not n or not 2 <= n <= 40:
            continue
        cand[stem] = dict(id=stem, rec=rec, year=y, decade=y // 10 * 10, jcode=jc, journal=j, type=t,
                          printed_pages=n, volume=vol, issue=iss, title=title)
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
    with (DATA / "candidates80.jsonl").open("w", encoding="utf-8") as fh:
        for s in sorted(cand):
            fh.write(json.dumps(cand[s], ensure_ascii=False) + "\n")

    rng = random.Random(SEED)
    by = defaultdict(lambda: defaultdict(list))
    for d in cand.values():
        by[d["decade"]][d["jcode"]].append(d)
    plan = []
    for dec in sorted(by):
        quota = QUOTA.get(dec, 0)
        js = sorted(by[dec])
        rng.shuffle(js)
        for j in js:
            rng.shuffle(by[dec][j])
        got = 0
        for rnd in range(MAX_PER_JOURNAL_DECADE):
            for j in js:
                if got >= quota:
                    break
                if rnd < len(by[dec][j]):
                    plan.append(by[dec][j][rnd]); got += 1
        print(dec, "journals", len(js), "docs", sum(map(len, by[dec].values())), "chosen", got)
    # fetch order: interleave decades so a stop leaves a balanced set
    per = defaultdict(list)
    for d in plan:
        per[d["decade"]].append(d)
    order = []
    while any(per.values()):
        for dec in sorted(per):
            if per[dec]:
                order.append(per[dec].pop(0))
    (DATA / "ids80.txt").write_text("\n".join(d["id"] for d in order) + "\n")
    with (DATA / "plan80.jsonl").open("w", encoding="utf-8") as fh:
        for d in order:
            fh.write(json.dumps(d, ensure_ascii=False) + "\n")
    gb = sum(d["pdf_bytes"] + d["json_bytes"] for d in order) / 1e9
    print(len(order), "chosen,", sum(d["printed_pages"] for d in order), "printed pages,", f"{gb:.2f} GB,",
          len({d["jcode"] for d in order}), "journals")


if __name__ == "__main__":
    main()
