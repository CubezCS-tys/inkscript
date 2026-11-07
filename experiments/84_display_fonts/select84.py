"""Experiment 84, part A: choose the LOCKED final test journals (no network; the catalogue read only; no page opened).

    nice -n 19 ionice -c3 python3 experiments/84_display_fonts/select84.py

Writes LOCKED_TEST.json (in git: codes, names, year spans, the rule) and out/data/locked84_exclusions.json (what was
excluded and why; private).

Rule.
- Eligible document: catalogue (marc.db, read-only) language 'ara', the article-like types of experiments 80/83,
  1900-2025, 2-40 printed pages, both <id>.pdf and <id>.json in the main bucket (experiment 44's listing), so a test
  can later be cut from S3 exactly as experiment 83 cut its lines.
- Eligible journal: at least MIN_DOCS eligible documents, and its code in NONE of:
  split76 held-out (= experiment 81's test; includes lab documents 1-3's journals 2399, 0018, 0877);
  experiment 77's training/dev/old80 manifests and select77.json; experiment 83's plan83 (its 7,763 documents) and
  candidates already cut; experiment 80's plan/manifest/ids; experiment 76's inventory; every document stem found on
  this machine (a scan of every file NAME under /home/appuser, AI-Search not walked, out/data/ondisk84_stems.txt;
  plus every stem MENTIONED in a text/json file of the repo outside experiment 44's bucket listing,
  out/data/mentioned84_stems.txt; plus experiments 80/83's ondisk lists).  A journal is out if ANY of its documents
  is in any of these.
- Choice (seed 84): strata by the journal's median eligible year: pre-1980 (every eligible one, with MIN_DOCS_OLD),
  1980-1999 (9), 2000+ (11); the pre-1980 slots found nothing and are not refilled.  Measured 2026-11-05: NO journal with a document before 1960 is left (all 363 journals
  with pre-1980 documents in the main bucket are excluded but two, 0871 (1970) and 1204 (1978-79): experiments 77, 80
  and 83 took every old journal into training), so the locked test cannot hold pre-1950 print at journal level.
  Inside a stratum journals are taken round-robin over their field of study (catalogue 773$4, first field), largest
  journals first within a field, so subjects spread; in 2000+ two slots go first to fields where display-face
  headers and titles are likely (arts, design, architecture, media), the only hint the catalogue gives.
"""
from __future__ import annotations

import datetime
import glob
import json
import random
import re
import sqlite3
from collections import Counter, defaultdict
from pathlib import Path
from statistics import median

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
DATA = HERE / "out/data"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = EXP / "44_bucket_map/out/ids_main.txt"
LISTING = EXP / "44_bucket_map/out/listing"
TYPES = ("بحوث ومقالات", "نصوص أدبية", "بحوث المؤتمرات", "عروض كتب", "افتتاحيات", "عروض رسائل")
MIN_DOCS = 8
MIN_DOCS_OLD = 5
QUOTA = {"pre-1980": 4, "1980-1999": 9, "2000+": 11}
DISPLAY_FIELDS = re.compile("فنون|الفن|تصميم|العمارة|عمارة|الإعلام|الاعلام|السينما|المسرح|الموسيقى|الآثار|الاثار|التراث")
SEED = 84
STEM = re.compile(r"^(\d{4}-\d{3}-\d{3}-\d{3})/\1\.(pdf|json)$")


def npages(pages, pf, pl):
    if pf and pl and pl >= pf:
        return pl - pf + 1
    m = re.search(r"\d+", pages or "")
    return int(m.group()) if m else None


def jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def excluded_codes():
    why = defaultdict(set)

    def add(codes, reason):
        for c in codes:
            if c:
                why[c[:4]].add(reason)
    add(json.loads((EXP / "76_finetune_pilot/out/split76.json").read_text())["test"], "split76 held-out / exp 81 test")
    add(["2399", "0018", "0877"], "lab documents 1-3")
    add([d["stem"] for d in jsonl(EXP / "76_finetune_pilot/out/inventory76.jsonl")], "exp 76 inventory")
    for f in glob.glob(str(EXP / "77_scratch_reader/out/shards/manifest-*.jsonl")):
        codes = set()
        for l in open(f, encoding="utf-8"):
            d = json.loads(l)
            codes.add(str(d.get("jcode") or d.get("stem") or d.get("key", ""))[:4])
        add(codes, "exp 77 manifests (train/dev/old80)")
    s77 = json.loads((EXP / "77_scratch_reader/out/select77.json").read_text())
    add(re.findall(r"\b(\d{4})-\d{3}-[\d,]+-\d{3}\b", json.dumps(s77)), "exp 77 select77.json")
    add([d["jcode"] for d in jsonl(EXP / "83_reader_scale/out/data/plan83.jsonl")], "exp 83 plan83 (training pool)")
    for f in ("plan80.jsonl", "manifest80.jsonl"):
        add([d.get("jcode") or d["id"] for d in jsonl(EXP / "80_old_print_pull/data" / f)], "exp 80 pull")
    for f, r in ((EXP / "80_old_print_pull/data/ids80.txt", "exp 80 pull"),
                 (EXP / "80_old_print_pull/data/ondisk80.txt", "on disk (exp 80 list)"),
                 (EXP / "83_reader_scale/out/data/ondisk83.txt", "on disk (exp 83 list)"),
                 (DATA / "ondisk84_stems.txt", "on disk (file names, 2026-11-05 scan)"),
                 (DATA / "mentioned84_stems.txt", "mentioned in a repo file")):
        add(f.read_text().split(), r)
    return why


def main():
    why = excluded_codes()
    print(len(why), "journal codes excluded")
    main_ids = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    q = f"""select p.stem, r.year_int, r.journal_code, r.journal, r.journal_en, r.country, r.fields_of_study, r.pages,
                   r.page_first, r.page_last
            from records r join pdf_ids p on p.rec = r.rec
            where r.year_int >= 1900 and r.year_int <= 2025 and r.language = 'ara'
              and r.type in ({','.join('?' * len(TYPES))})"""
    docs = {}
    bad_prefix = 0
    for stem, y, jc, j, je, ctry, fos, pg, pf, pl in c.execute(q, TYPES):
        if not jc or stem in docs or stem not in main_ids:
            continue
        bad_prefix += stem[:4] != jc
        n = npages(pg, pf, pl)
        if not n or not 2 <= n <= 40:
            continue
        docs[stem] = dict(y=y, jc=jc, j=j, je=je, ctry=ctry, fos=(fos or "").split(" | ")[0].strip())
    print(len(docs), "eligible documents in the main bucket; stems whose prefix is not the journal code:", bad_prefix)
    sizes = defaultdict(set)
    for f in sorted(LISTING.glob("mandumah-source-docs__*.tsv")):
        for line in f.open(encoding="utf-8"):
            m = STEM.match(line.split("\t", 1)[0])
            if m and m.group(1) in docs:
                sizes[m.group(1)].add(m.group(2))
    J = defaultdict(list)
    for s, d in docs.items():
        if sizes.get(s) == {"pdf", "json"}:
            J[d["jc"]].append((s, d))
    pool = {}
    for jc, L in J.items():
        if jc in why or jc[:4] in why:
            continue
        ys = sorted(d["y"] for _, d in L)
        my = median(ys)
        era = "pre-1980" if my < 1980 else "1980-1999" if my < 2000 else "2000+"
        if len(L) < (MIN_DOCS_OLD if era == "pre-1980" else MIN_DOCS):
            continue
        fos = Counter(d["fos"] for _, d in L).most_common(1)[0][0] or "(none)"
        pool[jc] = dict(code=jc, name=L[0][1]["j"], name_en=L[0][1]["je"], country=L[0][1]["ctry"], field=fos,
                        era=era, years=[ys[0], ys[-1]], median_year=my, eligible_docs=len(L))
    print(len(pool), "eligible journals;", Counter(p["era"] for p in pool.values()))
    rng = random.Random(SEED)
    chosen = []
    for era, k in QUOTA.items():
        P = [p for p in pool.values() if p["era"] == era]
        byf = defaultdict(list)
        for p in P:
            byf[p["field"]].append(p)
        for f in byf:
            rng.shuffle(byf[f])
            byf[f].sort(key=lambda p: -min(p["eligible_docs"], 60))
        fields = sorted(byf)
        rng.shuffle(fields)
        got = []
        if era == "2000+":
            disp = [f for f in fields if DISPLAY_FIELDS.search(f)]
            for f in disp[:2]:
                got.append(byf[f].pop(0))
        while len(got) < k and any(byf.values()):
            for f in fields:
                if len(got) >= k:
                    break
                if byf[f]:
                    got.append(byf[f].pop(0))
        chosen += got
        print(era, len(P), "available ->", len(got))
    lock = dict(
        experiment="84_display_fonts", date=datetime.date.today().isoformat(),
        note="locked: no training, no tuning, no peeking; opened once for the final claim with the owner's OK",
        rule=__doc__.split("Rule.")[1].strip(),
        guard="experiments/84_display_fonts/locked.py: locked_codes(), assert_not_locked(stems)",
        pages_opened=0,
        journals=[{k: p[k] for k in ("code", "name", "name_en", "country", "field", "era", "years", "eligible_docs")}
                  for p in sorted(chosen, key=lambda p: (p["era"], p["code"]))])
    (HERE / "LOCKED_TEST.json").write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "locked84_exclusions.json").write_text(json.dumps(
        dict(excluded={k: sorted(v) for k, v in sorted(why.items())}, pool_size=len(pool),
             pool_by_era=Counter(p["era"] for p in pool.values())), ensure_ascii=False, indent=0))
    for p in lock["journals"]:
        print(p)


if __name__ == "__main__":
    main()
