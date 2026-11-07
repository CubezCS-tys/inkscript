"""Experiment 88, task 2: the LOCKED old-print DOCUMENTS (no network; the catalogue read only; no page opened).

    nice -n 19 ionice -c3 python3 select88.py scan      # file names under /home/appuser + stems named in repo files
    nice -n 19 ionice -c3 python3 select88.py select    # -> LOCKED_OLD_DOCS.json (+ out/data/locked88_*.json)

Why documents, not journals: experiment 84 found no pre-1980 journal left untouched (all but 2 of 363 are used, and
those 2 are too thin).  The owner chose option (a), 2026-11-05: lock old documents that were never downloaded or used,
from journals that may appear in training.  It tests new pages of known journals, as Mandumah's archive will be read.

Rule.
- Eligible document (as experiment 84): catalogue (marc.db, read only) language 'ara', the article-like types of
  experiments 80/83/84, published 1900-1979, 2-40 printed pages, both <id>.pdf and <id>.json in the main bucket
  (experiment 44's listing), so the test can later be cut from S3 exactly as experiment 83 cut its lines.
- Out, whole journals (kept separate from this set): split76's 27 held-out codes (= experiment 81's test, with lab
  documents 1-3's journals 2399, 0018, 0877) and LOCKED_TEST.json's 20 journals (experiment 84).
- Out, documents: every document in
  experiment 76's inventory; experiment 77's training/dev/old80/test manifests and select77.json; experiment 80's
  plan, manifest, ids and on-disk list; experiment 83's plan83 and on-disk list; experiment 84's on-disk and
  mentioned lists; experiment 85's judge sample;
  every stem in a file NAME anywhere under /home/appuser (fresh scan, AI-Search not walked);
  every stem named INSIDE a repo file (see Verification), except catalogue enumerations, i.e. files that list the
  catalogue or a candidate pool rather than documents used (checked by hand).
  (`scan` also starts a full regex scan of repo contents, out/data/mentioned88_files.json; on 2026-11-05 it was
  stopped after 1h40 for time, and the fixed-string verification below took its place.)
- Choice (seed 88): 280 documents; decade quotas 1920s 40, 1930s 50, 1940s 50, 1950s 50, 1960s 45, 1970s 45, and
  a decade's unfilled quota moves on to the next.  Inside a decade journals are taken round-robin in random order,
  at most one document per issue (stem's first 12 characters), at most 15 documents per journal before 1950 (only
  about 16 old journals are left) and 3 from 1950 on; issues none of whose documents is used come first.
- Verification (verify88.sh): every chosen stem is searched as a fixed string in every repo file (text and binary,
  images and model weights aside); a stem found outside a catalogue enumeration is excluded and the choice redone,
  until no chosen stem is named anywhere.
"""
from __future__ import annotations

import datetime
import gzip
import json
import os
import random
import re
import sqlite3
import sys
import tarfile
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
EXP = HERE.parent
REPO = EXP.parent
DATA = HERE / "out/data"
MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
IDS_MAIN = EXP / "44_bucket_map/out/ids_main.txt"
LISTING = EXP / "44_bucket_map/out/listing"
TYPES = ("بحوث ومقالات", "نصوص أدبية", "بحوث المؤتمرات", "عروض كتب", "افتتاحيات", "عروض رسائل")
STEM = re.compile(r"^(\d{4}-\d{3}-\d{3}-\d{3})/\1\.(pdf|json)$")
RX = re.compile(rb"(?<!\d)(\d{4}-\d{3}-\d{3}-\d{3})(?!\d)")
RXS = re.compile(r"(?<!\d)(\d{4}-\d{3}-\d{3}-\d{3})(?!\d)")
TEXT_EXT = {".json", ".jsonl", ".txt", ".tsv", ".csv", ".log", ".md", ".py", ".sh", ".xml", ".html", ".htm", ".js",
            ".ts", ".tsx", ".yaml", ".yml", ".toml", ".sql", ".state", ".db", ".sqlite", ".sqlite3", ".out", ".err",
            ".ndjson", ".lst", ".ids", ".gz", ".tar", ""}
PRUNE = {".git", ".venv", "venv", "venv_surya", "site-packages", "hf_cache", "node_modules", "__pycache__", ".next"}
# Catalogue / bucket / candidate-pool enumerations (repo-relative): they name documents nobody has used.
ENUMERATIONS = [
    "experiments/44_bucket_map/out/",                      # the bucket listing and its id lists
    "experiments/83_reader_scale/out/data/candidates83.jsonl",
    "experiments/80_old_print_pull/data/candidates80.jsonl",
    "experiments/88_truth_and_lock/",                      # this experiment's own scan, candidates and the lock
    "experiments/16_feel/out/books/all_ids.txt",            # every catalogue id
    "experiments/19_azure_map/out/listing.txt",             # bucket listing
    "experiments/28_scale/out/catalogue.tsv",               # catalogue export
    "experiments/43_rehearsal/out/catalogue_draw.json",     # random draw of 18,767 catalogue stems (not fetched)
    "experiments/89_final_reader/", "experiments/90_locked_final/",   # copies of this lock (its guard / the test)
]
SEED = 88
TARGET = 280
QUOTA = {1900: 0, 1910: 0, 1920: 40, 1930: 50, 1940: 50, 1950: 50, 1960: 45, 1970: 45}   # unfilled quota moves on
PER_JOURNAL_OLD = 15         # pre-1950: few journals are left, so more documents each (still one per issue)
PER_JOURNAL = 3


def jsonl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def npages(pages, pf, pl):
    if pf and pl and pl >= pf:
        return pl - pf + 1
    m = re.search(r"\d+", pages or "")
    return int(m.group()) if m else None


def eligible() -> dict:
    """Pre-1980 eligible documents (experiment 84's rule, years 1900-1979)."""
    main_ids = set(IDS_MAIN.read_text().split())
    c = sqlite3.connect(MARC, uri=True)
    q = f"""select p.stem, r.year_int, r.journal_code, r.journal, r.journal_en, r.country, r.fields_of_study, r.pages,
                   r.page_first, r.page_last, r.type
            from records r join pdf_ids p on p.rec = r.rec
            where r.year_int >= 1900 and r.year_int <= 1979 and r.language = 'ara'
              and r.type in ({','.join('?' * len(TYPES))})"""
    docs = {}
    for stem, y, jc, j, je, ctry, fos, pg, pf, pl, ty in c.execute(q, TYPES):
        if not jc or stem in docs or stem not in main_ids:
            continue
        n = npages(pg, pf, pl)
        if not n or not 2 <= n <= 40:
            continue
        docs[stem] = dict(stem=stem, year=y, journal_code=jc, journal=j, journal_en=je, country=ctry,
                          field=(fos or "").split(" | ")[0].strip(), type=ty, printed_pages=n)
    sizes = defaultdict(set)
    for f in sorted(LISTING.glob("mandumah-source-docs__*.tsv")):
        for line in f.open(encoding="utf-8"):
            m = STEM.match(line.split("\t", 1)[0])
            if m and m.group(1) in docs:
                sizes[m.group(1)].add(m.group(2))
    return {s: d for s, d in docs.items() if sizes.get(s) == {"pdf", "json"}}


# ---------------------------------------------------------------- scans
def scan_names() -> set[str]:
    """Every stem in a file or directory NAME under /home/appuser (AI-Search not walked)."""
    out = set()
    for root, dirs, files in os.walk("/home/appuser"):
        if root == "/home/appuser":
            dirs[:] = [d for d in dirs if d != "AI-Search"]
        for n in dirs + files:
            if "-" in n:
                out.update(RXS.findall(n))
    return out


def stems_in_file(p: Path) -> set[bytes]:
    found = set()
    name = p.name.lower()
    if name.endswith(".tar"):
        with tarfile.open(p) as t:
            for m in t:
                found.update(RX.findall(m.name.encode()))
        return found
    opener = gzip.open if name.endswith(".gz") and not name.endswith(".tar.gz") else open
    tail = b""
    with opener(p, "rb") as f:
        while True:
            b = f.read(1 << 24)
            if not b:
                break
            chunk = tail + b
            found.update(RX.findall(chunk))
            tail = chunk[-32:]
    return found


def scan_repo(cand: set[str]):
    """Per repo file: how many distinct stems it names, and which candidates."""
    per = {}
    nfiles = nbytes = 0
    for root, dirs, files in os.walk(REPO):
        dirs[:] = [d for d in dirs if d not in PRUNE and not d.startswith("venv")]
        for fn in files:
            p = Path(root) / fn
            ext = p.suffix.lower()
            if ext not in TEXT_EXT or p.is_symlink():
                continue
            try:
                st = stems_in_file(p)
            except Exception as e:                      # unreadable / corrupt: record it, never skip silently
                per[str(p.relative_to(REPO))] = dict(n=-1, error=repr(e)[:200], cand=[])
                continue
            nfiles += 1
            nbytes += p.stat().st_size
            if st:
                s = {x.decode() for x in st}
                per[str(p.relative_to(REPO))] = dict(n=len(s), cand=sorted(s & cand))
    return per, nfiles, nbytes


def cmd_scan():
    DATA.mkdir(parents=True, exist_ok=True)
    el = eligible()
    (DATA / "eligible88.json").write_text(json.dumps(el, ensure_ascii=False), encoding="utf-8")
    print(len(el), "eligible pre-1980 documents", flush=True)
    names = scan_names()
    (DATA / "ondisk88_stems.txt").write_text("\n".join(sorted(names)) + "\n")
    print(len(names), "stems in file names under /home/appuser", flush=True)
    per, nf, nb = scan_repo(set(el))
    (DATA / "mentioned88_files.json").write_text(json.dumps(dict(files=nf, bytes=nb, per_file=per), indent=0))
    print(nf, "repo files read,", round(nb / 1e9, 1), "GB;", len(per), "name a stem", flush=True)


# ---------------------------------------------------------------- selection
def used_docs(el: dict) -> tuple[dict, set]:
    """stem -> reasons, for documents used / on disk / named; and the journal codes kept apart."""
    why = defaultdict(set)

    def add(stems, reason):
        for s in stems:
            s = str(s or "")
            for m in RXS.findall(s):
                why[m].add(reason)

    add([d["stem"] for d in jsonl(EXP / "76_finetune_pilot/out/inventory76.jsonl")], "exp 76 inventory")
    for f in sorted((EXP / "77_scratch_reader/out/shards").glob("manifest-*.jsonl")) + \
            [EXP / "77_scratch_reader/out/test/manifest-test.jsonl"]:
        add([d.get("stem") or d.get("key") or d.get("id") for d in jsonl(f)], f"exp 77 {f.name}")
    add(RXS.findall((EXP / "77_scratch_reader/out/select77.json").read_text()), "exp 77 select77.json")
    add([d["id"] for d in jsonl(EXP / "83_reader_scale/out/data/plan83.jsonl")], "exp 83 plan83")
    for f in ("plan80.jsonl", "manifest80.jsonl"):
        add([d.get("id") or d.get("stem") for d in jsonl(EXP / "80_old_print_pull/data" / f)], "exp 80 pull")
    for f, r in ((EXP / "80_old_print_pull/data/ids80.txt", "exp 80 pull"),
                 (EXP / "80_old_print_pull/data/ondisk80.txt", "on disk (exp 80 list)"),
                 (EXP / "83_reader_scale/out/data/ondisk83.txt", "on disk (exp 83 list)"),
                 (EXP / "84_display_fonts/out/data/ondisk84_stems.txt", "on disk (exp 84 list)"),
                 (EXP / "84_display_fonts/out/data/mentioned84_stems.txt", "mentioned (exp 84 list)"),
                 (DATA / "ondisk88_stems.txt", "on disk (file names, 2026-11-05 scan)")):
        add(f.read_text().split(), r)
    s85 = EXP / "85_disputes/out/judge/sample.jsonl"
    if s85.exists():
        add([d["key"] for d in jsonl(s85)], "exp 85 judge sample")
    mf = DATA / "mentioned88_files.json"                 # the full content scan, when it has been run to the end
    if mf.exists():
        for f, v in json.loads(mf.read_text())["per_file"].items():
            if not any(f.startswith(e) for e in ENUMERATIONS):
                add(v["cand"], "named in a repo file")
    gh = DATA / "grep88_hits.json"                        # verify88.sh: chosen stems found inside a repo file
    if gh.exists():
        for s, files in json.loads(gh.read_text()).items():
            if any(not any(f.startswith(e) for e in ENUMERATIONS) for f in files):
                add([s], "named in a repo file (verify88 grep)")
    held = set(json.loads((EXP / "76_finetune_pilot/out/split76.json").read_text())["test"]) | {"2399", "0018", "0877"}
    sys.path.insert(0, str(EXP / "84_display_fonts"))
    from locked import locked_codes                                    # read only
    return why, {c[:4] for c in held} | set(locked_codes())


def cmd_select():
    el = json.loads((DATA / "eligible88.json").read_text(encoding="utf-8"))
    why, apart = used_docs(el)
    touched_issue = {s[:12] for s in why}
    pool = {s: d for s, d in el.items()
            if s not in why and d["journal_code"][:4] not in apart and s[:4] not in apart}
    stats = dict(eligible=len(el), used_or_named=sum(s in why for s in el),
                 journal_kept_apart=sum(s not in why and (d["journal_code"][:4] in apart or s[:4] in apart)
                                        for s, d in el.items()),
                 pool=len(pool), pool_in_untouched_issues=sum(s[:12] not in touched_issue for s in pool))
    print(stats, "\npool by decade", sorted(Counter(d["year"] // 10 * 10 for d in pool.values()).items()))
    rng = random.Random(SEED)
    per_j = Counter()
    used_issue = set()
    chosen = []
    carry = 0
    for dec in sorted(QUOTA):
        k = QUOTA[dec] + carry
        cap = PER_JOURNAL_OLD if dec < 1950 else PER_JOURNAL
        D = defaultdict(list)
        for s, d in sorted(pool.items()):
            if d["year"] // 10 * 10 == dec:
                D[d["journal_code"]].append(d)
        for L in D.values():                 # untouched issues first, random inside
            rng.shuffle(L)
            L.sort(key=lambda d: d["stem"][:12] in touched_issue)
        js = sorted(D)
        rng.shuffle(js)
        got = 0
        while got < k:
            moved = False
            for j in js:
                if got >= k or per_j[j] >= cap:
                    continue
                while D[j] and D[j][0]["stem"][:12] in used_issue:
                    D[j].pop(0)
                if D[j]:
                    d = D[j].pop(0)
                    chosen.append(d)
                    used_issue.add(d["stem"][:12])
                    per_j[j] += 1
                    got += 1
                    moved = True
            if not moved:
                break
        carry = k - got
        print(dec, "quota", k, "->", got, "from", len({d["journal_code"] for d in chosen if d["year"] // 10 * 10 == dec}),
              "journals", flush=True)
    chosen.sort(key=lambda d: d["stem"])
    (DATA / "chosen88.txt").write_text("".join(d["stem"] + "\n" for d in chosen))
    from locked import assert_not_locked
    assert_not_locked([d["stem"] for d in chosen])
    lock = dict(
        experiment="88_truth_and_lock", date=datetime.date.today().isoformat(),
        note="locked: no download, no training, no tuning; opened once for the final claim with the owner's OK",
        owner_choice="option (a), 2026-11-05: old documents never downloaded or used, from journals that may appear "
                     "in training (new pages of known journals)",
        rule=__doc__.split("Rule.")[1].strip(),
        guard="experiments/88_truth_and_lock/locked_old.py: locked_docs(), is_locked_doc(stem), "
              "assert_not_locked(stems) (journals of experiment 84 AND these documents)",
        pages_opened=0, documents_downloaded=0,
        counts=dict(documents=len(chosen), journals=len({d["journal_code"] for d in chosen}),
                    by_decade=dict(sorted(Counter(str(d["year"] // 10 * 10) for d in chosen).items())),
                    pre_1950=sum(d["year"] < 1950 for d in chosen)),
        selection_stats=stats,
        documents=[{k: d[k] for k in ("stem", "year", "journal_code", "journal", "journal_en", "country", "field",
                                      "type", "printed_pages")} for d in chosen])
    (HERE / "LOCKED_OLD_DOCS.json").write_text(json.dumps(lock, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    (DATA / "locked88_exclusions.json").write_text(json.dumps(
        dict(stats=stats, excluded={s: sorted(v) for s, v in sorted(why.items()) if s in el}), ensure_ascii=False,
        indent=0))
    print(lock["counts"])


if __name__ == "__main__":
    {"scan": cmd_scan, "select": cmd_select}[sys.argv[1]]()
