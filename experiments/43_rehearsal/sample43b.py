"""Experiment 43: the second 300-article sample (owner approved 2026-10-20), unseen by every earlier run. No model
calls; S3 reads only (the fetch).

Unseen: no article of experiments 35, 40, 41 (the 55), the first 300 (sample43.json and its proposal) or any batch test
(every stem in a file name under out/). Journals 98xx (dissertations) are left out. At most 3 per journal.
Pools:
  local      experiment 41's inventory (PDF + Azure JSON on this machine; features43.json), not used before
  reserve    the first sample's reserve left over (JSON fetched, measured in out/fetch/measure43.json)
  draw       a new catalogue draw from ~/data/marc/marc.db, **kept only if in experiments/44_bucket_map/out/ids_main.txt**
             (the bucket's documents with PDF + Azure JSON): article records with one PDF, 1-30 printed pages, a year;
             per decade, plus French, English and Literary Text (poems: verse) strata; seed 4344
Layouts as fetched43 (page_feats; formula rule for equations, then by eye: EYE below); French / English = the
catalogue's language (or experiment 41's inventory for local) with a Latin share > 0.3.

    .venv/bin/python sample43b.py draw      -> out/sample2/draw.json, out/sample2/json_ids.txt
    .venv/bin/python sample43b.py draw_verse -> 120 more (literature before 1990, for verse), out/sample2/json_ids2.txt
    .venv/bin/python sample43b.py fetch [json_ids2.txt] -> out/sample2/fetch/<id>/<id>.json (JSON only, resumable)
    .venv/bin/python sample43b.py measure   -> out/sample2/measure.json
    .venv/bin/python sample43b.py sheet     -> out/sample2/sheets/equations.jpg (formula-rule pages, to look at)
    .venv/bin/python sample43b.py select    -> sample43b.json (proposal), out/sample2/pdf_ids.txt
    .venv/bin/python sample43b.py fetchpdf  -> the chosen articles' PDFs
    .venv/bin/python sample43b.py check     -> checks, swaps of unusable articles; final sample43b.json, out/sample2/strata.md
"""
from __future__ import annotations

import json
import os
import random
import re
import sqlite3
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import sample43 as S  # noqa: E402
import fetched43 as F  # noqa: E402

OUT = HERE / "out" / "sample2"
FETCH = OUT / "fetch"
MARC = Path.home() / "data/marc/marc.db"
IDS_MAIN = HERE.parent / "44_bucket_map/out/ids_main.txt"
SEED = 4344
DECS = ["pre-1960", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]
DRAW_PER_DECADE = {"pre-1960": 45, "1960s": 40, "1970s": 35, "1980s": 30, "1990s": 35, "2000s": 25, "2010s": 15,
                   "2020s": 15}
DRAW_LANG = dict(fre=45, eng=40)
DRAW_LITERARY = 45
LAYOUTS = F.LAYOUTS
QUOTA = dict(verse=25, equations=15, french=23, english=30, shared=20, two_columns=60, tables=55)
N = 300
DEC_MAX = 40                     # a layout pick may not push a decade past this
# Equations by eye (out/sample2/sheets/equations*.jpg: each formula-rule article's best page), as fetched43.EYE
# 2026-10-20: 26 of the 62 formula-rule candidates show formulas or worked arithmetic; the rest are statistics tables,
# "p < 0.05", code, charts, a list of exchange rates, notation keys.
EYE_EQ: set[str] = {
    "0163-003-003-007", "0236-016-003-003", "0396-022-005-010", "0430-012-002-008", "0470-021-037-015",
    "0484-060-338-005", "0527-006-001-004", "0527-013-001-011", "0527-054-001-051", "0527-055-002-016",
    "0527-055-002-059", "0528-043-006-006", "0630-000-015-017", "0700-000-034-001", "0700-000-093-002",
    "0782-010-023-018", "0946-034-046-002", "1127-015-004-105", "1147-000-030-003", "1148-000-065-003",
    "1188-000-144-004", "1786-000-015-005", "2259-006-004-071", "2461-003-001-005", "2532-028-004-036",
    "2532-029-004-035"}
# Verse by eye (out/sample2/sheets/verse_*.jpg): the rule's page is not verse
EYE_VERSE_NO = {"0368-000-065-003", "0770-000-082-022", "0701-001-004-015", "0917-004-007,008-003", "1010-035-007,008,009-005"}


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


jdump = F.jdump


def log(msg: str):
    OUT.mkdir(parents=True, exist_ok=True)
    with open(OUT / "log.txt", "a", encoding="utf-8") as f:
        f.write(msg + "\n")
    print(msg, flush=True)


def excluded() -> dict:
    ex = dict(S.excluded())
    for a in jl(HERE / "sample43.json")["articles"]:              # (its reserve list stays a pool: never run)
        ex.setdefault(a["stem"], "43 first 300")
    prop = HERE / "out/fetch/sample43_proposal.json"
    for a in jl(prop)["articles"]:
        ex.setdefault(a["stem"], "43 first 300 (proposal)")
    skip = {HERE / "out/fetch", OUT}
    for root, dirs, files in os.walk(HERE / "out"):
        if Path(root) in skip:
            dirs[:] = []
            continue
        for x in files + dirs:
            for s in S.STEM.findall(x):
                ex.setdefault(s, "43 runs / batch tests (file name under out/)")
    return ex


def marc_rows(stems=None):
    """stem -> (year, page_first, page_last, type_en, language, journal, journal_code) for stems with one record."""
    db = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    q = ("select p.stem, r.year_int, r.page_first, r.page_last, r.type_en, r.language, r.journal, r.n_pdfs "
         "from pdf_ids p join records r on r.rec = p.rec")
    seen, out = Counter(), {}
    if stems is not None:
        it = (row for st in stems for row in db.execute(q + " where p.stem = ?", (st,)))
    else:
        it = db.execute(q)
    for st, y, a, b, t, lang, j, npdf in it:
        seen[st] += 1
        out[st] = (y, a, b, t or "", lang or "", j, npdf)
    for st, k in seen.items():
        if k > 1:
            out.pop(st, None)
    return out


def marc_year(stem: str):
    r = marc_rows([stem]).get(stem)
    return str(r[0]) if r and r[0] else None


# ------------------------------------------------------------------------------------------------ draw

def cmd_draw():
    ex = excluded()
    inv = {r["stem"] for r in jl(HERE.parent / "41_azure_structure/out/inventory.json")}
    first = jl(HERE / "sample43.json")
    reserve = set(first["reserve"])
    log(f"draw: {len(ex)} stems excluded ({dict(Counter(ex.values()))})")
    main = set(Path(IDS_MAIN).read_text().split())
    log(f"draw: ids_main {len(main)}")
    rows = marc_rows()
    log(f"draw: marc stems with one record {len(rows)}")
    by = {}
    for st, (y, a, b, t, lang, j, npdf) in rows.items():
        if st not in main or st in ex or st in inv or st in reserve or st.startswith("98"):
            continue
        if not (y and a is not None and b is not None and 1 <= b - a + 1 <= S.MAX_PAGES and npdf == 1):
            continue
        kind = "literary" if t == "Literary Text" else ("article" if t in ("Article", "") else None)
        if kind is None:
            continue
        by[st] = dict(stem=st, year=str(y), decade=S.decade(y), lang=lang.split(",")[0], type=t, journal=j,
                      printed=f"{a}-{b}", pages=b - a + 1, kind=kind)
    del rows, main
    log(f"draw: candidates in the bucket, unseen, 1-30 pages, a year: {len(by)}; "
        f"{dict(sorted(Counter(x['decade'] for x in by.values()).items()))}")
    rnd = random.Random(SEED)
    keys = sorted(by)
    rnd.shuffle(keys)
    picked, per_j, why = [], Counter(), {}

    def take(st, reason):
        if st in why or per_j[st[:4]] >= 2:          # <= 2 per journal in the draw, so the sample can still mix
            return False
        why[st] = reason
        per_j[st[:4]] += 1
        picked.append(dict(by[st], drawn_for=reason))
        return True
    for lang, q in DRAW_LANG.items():
        n = 0
        for st in keys:
            if n >= q:
                break
            if by[st]["lang"] == lang and by[st]["kind"] == "article" and take(st, f"language {lang}"):
                n += 1
    n = 0
    for st in keys:
        if n >= DRAW_LITERARY:
            break
        if by[st]["kind"] == "literary" and take(st, "literary text (verse)"):
            n += 1
    for d, q in DRAW_PER_DECADE.items():
        n = 0
        for st in keys:
            if n >= q:
                break
            if by[st]["decade"] == d and by[st]["kind"] == "article" and by[st]["lang"] == "ara" and take(st, f"decade {d}"):
                n += 1
    jdump(OUT / "draw.json", dict(made=f"sample43b.py draw (seed {SEED})", candidates=len(by), drawn=picked))
    (OUT / "json_ids.txt").write_text("\n".join(x["stem"] for x in picked) + "\n")
    log(f"draw: {len(picked)} drawn; {dict(Counter(x['drawn_for'] for x in picked))}")


DRAW_VERSE = 120


def cmd_draw_verse():
    """A second draw for verse (the first gave 16 by the rule, target 25; Literary Text gave 3 of 45): Arabic
    articles in literature (773 $4 holds الادب / الأدب) before 1990, same filters; appended to draw.json, ids to
    json_ids2.txt."""
    ex = excluded()
    inv = {r["stem"] for r in jl(HERE.parent / "41_azure_structure/out/inventory.json")}
    reserve = set(jl(HERE / "sample43.json")["reserve"])
    d = jl(OUT / "draw.json")
    have = {x["stem"] for x in d["drawn"]}
    per_j = Counter(st[:4] for st in have)
    main = set(Path(IDS_MAIN).read_text().split())
    db = sqlite3.connect(f"file:{MARC}?mode=ro", uri=True)
    rows = db.execute("select p.stem, r.year_int, r.page_first, r.page_last, r.type_en, r.language, r.journal "
                      "from pdf_ids p join records r on r.rec = p.rec where r.year_int < 1990 and r.n_pdfs = 1 and "
                      "(r.fields_of_study like '%الادب%' or r.fields_of_study like '%الأدب%') and r.language = 'ara' "
                      "and r.type_en in ('Article', '') order by p.stem").fetchall()
    cand = [r for r in rows if r[0] in main and r[0] not in ex and r[0] not in inv and r[0] not in reserve
            and r[0] not in have and not r[0].startswith("98") and r[2] is not None and r[3] is not None
            and 1 <= r[3] - r[2] + 1 <= S.MAX_PAGES]
    del main
    random.Random(SEED + 1).shuffle(cand)
    new = []
    for st, y, a, b, t, lang, j in cand:
        if len(new) >= DRAW_VERSE:
            break
        if per_j[st[:4]] >= (2 if not d.get("verse_draws") else 3):    # a second verse draw: 3 per journal
            continue
        per_j[st[:4]] += 1
        new.append(dict(stem=st, year=str(y), decade=S.decade(y), lang=lang, type=t or "", journal=j,
                        printed=f"{a}-{b}", pages=b - a + 1, kind="article", drawn_for="literature before 1990 (verse)"))
    d["drawn"] += new
    d.setdefault("verse_draws", []).append(dict(candidates=len(cand), drawn=len(new), seed=SEED + 1))
    jdump(OUT / "draw.json", d)
    (OUT / "json_ids2.txt").write_text("\n".join(x["stem"] for x in new) + "\n")
    log(f"draw verse: {len(cand)} candidates, {len(new)} drawn; {dict(Counter(x['decade'] for x in new))}")


# ------------------------------------------------------------------------------------------------ fetch

def fetch_ids(ids: list[str], exts) -> dict:
    def one(st):
        return st, F.fetch_one(st, folder_of(st), exts)
    res = {}
    with ThreadPoolExecutor(4) as ex:
        for i, (st, got) in enumerate(ex.map(one, ids), 1):
            res[st] = got
            if i % 25 == 0 or i == len(ids):
                log(f"fetch {'+'.join(exts)}: {i}/{len(ids)}, missing so far {sum(1 for g in res.values() if len(g) < len(exts))}")
    return res


def folder_of(st: str) -> Path:
    r = HERE / "out/fetch/reserve" / st
    return r if r.exists() else FETCH / st


def cmd_fetch():
    f = OUT / (sys.argv[2] if len(sys.argv) > 2 else "json_ids.txt")
    ids = [l.strip() for l in f.read_text().splitlines() if l.strip()]
    res = fetch_ids(ids, ("json",))
    jdump(OUT / f"fetch_{f.stem}.json", res)
    log(f"fetch json: {sum(1 for g in res.values() if 'json' in g)} of {len(ids)}")


# ------------------------------------------------------------------------------------------------ measure

def local_pool(ex: dict) -> list[dict]:
    out = []
    for x in jl(HERE / "out/features43.json"):
        if "error" in x or x["stem"] in ex or x["stem"].startswith("98") or not 1 <= x["pages"] <= S.MAX_PAGES:
            continue
        y = x.get("year") if x.get("year") and str(x["year"])[:4].isdigit() else marc_year(x["stem"])
        a = jl(x["azure"])
        a = a.get("analyzeResult", a)
        ml = [F.math_page(p) for p in a.get("pages", [])]
        out.append(dict(stem=x["stem"], where="local", azure_pages=x["pages"], tables=x["tables"],
                        two_columns=x["two_columns"], verse=x["verse"], equations=max(ml or [0]) >= 2,
                        math_lines=sum(ml), french=x["french"], english=x["english"], shared=bool(x["shared"]),
                        year=str(y)[:4] if y else None, journal=x.get("journal"), journal_code=x["stem"][:4],
                        azure=x["azure"], pdf=x["pdf"]))
    return out


def cmd_measure():
    ex = excluded()
    f = OUT / "measure.json"
    m = jl(f) if f.exists() else {}
    for x in local_pool(ex):
        m.setdefault(x["stem"], x)
    old = jl(HERE / "out/fetch/measure43.json")
    for st in jl(HERE / "sample43.json")["reserve"]:
        if st in old and "error" not in old[st] and st not in ex and not st.startswith("98"):
            d = folder_of(st)
            m.setdefault(st, dict(old[st], where="reserve", azure=str(d / f"{st}.json"), pdf=str(d / f"{st}.pdf")))
    for x in jl(OUT / "draw.json")["drawn"]:
        st = x["stem"]
        if st in m and "error" not in m[st]:
            continue
        az = folder_of(st) / f"{st}.json"
        if not az.exists():
            m[st] = dict(stem=st, where="draw", error="no Azure JSON")
            continue
        try:
            m[st] = dict(F.measure_json(st, az), where="draw", drawn_for=x["drawn_for"], type=x["type"],
                         azure=str(az), pdf=str(folder_of(st) / f"{st}.pdf"))
        except Exception as e:
            m[st] = dict(stem=st, where="draw", error=f"{type(e).__name__}: {e}")
        jdump(f, m)
    jdump(f, m)
    for w in ("local", "reserve", "draw"):
        xs = [x for x in m.values() if x["where"] == w and "error" not in x]
        log(f"measure {w}: {len(xs)} ok, {sum(1 for x in m.values() if x['where'] == w and 'error' in x)} errors; "
            f"{ {k: sum(1 for x in xs if x.get(k)) for k in LAYOUTS} } "
            f"{dict(sorted(Counter(S.decade(x['year']) or 'unknown' for x in xs).items()))}")


# ------------------------------------------------------------------------------------------------ sheet (by eye)

def best_page(x: dict, flag: str) -> tuple[int, int]:
    a = jl(x["azure"])
    a = a.get("analyzeResult", a)
    pages = a.get("pages", [])
    if flag == "equations":
        sc = [F.math_page(p) for p in pages]
    else:
        sc = [int(S.page_feats(p)["verse"]) * len(p.get("lines", [])) for p in pages]
    i = max(range(len(sc)), key=lambda k: sc[k])
    return i, sc[i]


def cmd_sheet():
    """Each rule-flagged candidate's best page on contact sheets (12 a sheet, pymupdf only), to look at by eye:
    equations (formula rule) and verse (rhyme rule). Candidates without a PDF get it fetched first (PDF only)."""
    import pymupdf
    m = jl(OUT / "measure.json")
    (OUT / "sheets").mkdir(parents=True, exist_ok=True)
    for flag in sys.argv[2:] or ["equations", "verse"]:
        xs = sorted([x for x in m.values() if "error" not in x and x.get(flag)], key=lambda x: x["stem"])
        fetch_ids([x["stem"] for x in xs if not Path(x["pdf"]).exists()], ("pdf",))
        W, H, k = 420, 620, 0
        for k in range(0, len(xs), 12):
            out = pymupdf.open()
            pg = out.new_page(width=4 * W, height=3 * H)
            for j, x in enumerate(xs[k:k + 12]):
                r = pymupdf.Rect((j % 4) * W, (j // 4) * H + 18, (j % 4 + 1) * W - 4, (j // 4 + 1) * H - 2)
                try:
                    i, sc = best_page(x, flag)
                    with pymupdf.open(x["pdf"]) as src:
                        pg.show_pdf_page(r, src, i)
                    pg.insert_text(((j % 4) * W + 4, (j // 4) * H + 13), f"{x['stem']} p{i + 1} ({sc})", fontsize=11,
                                   color=(0.8, 0, 0))
                except Exception as e:
                    log(f"sheet {flag}: {x['stem']} {type(e).__name__}: {e}")
            pg.get_pixmap(dpi=80).save(OUT / "sheets" / f"{flag}_{k // 12 + 1}.jpg", jpg_quality=80)
        log(f"sheet {flag}: {len(xs)} candidates on {-(-len(xs) // 12)} sheets in {OUT / 'sheets'}")


# ------------------------------------------------------------------------------------------------ select

def usable_pool(m: dict, ex: dict) -> list[dict]:
    pool = []
    for x in m.values():
        if "error" in x or x["stem"] in ex or x["stem"].startswith("98") or not x.get("year"):
            continue
        if not 1 <= (x.get("azure_pages") or 0) <= S.MAX_PAGES:
            continue
        pool.append(dict(x, decade=S.decade(x["year"]), equations=x["stem"] in EYE_EQ,
                         verse=bool(x.get("verse")) and x["stem"] not in F.EYE["verse"]["no"] | EYE_VERSE_NO))
    return pool


def art(x: dict, why: str) -> dict:
    n = x["azure_pages"]
    return dict(stem=x["stem"], kind="whole", first=1, last=n, pages_total=n, n=n, pdf=x["pdf"], azure=x["azure"],
                decade=x["decade"], year=x["year"], journal=x.get("journal"), why=why,
                flags=[k for k in LAYOUTS if x.get(k)], source="local" if x["where"] == "local" else "catalogue",
                pool=x["where"], printed_pages=x.get("printed"))


def select(pool: list[dict], n: int = N, chosen=None) -> list[dict]:
    rnd = random.Random(SEED)
    pool = sorted(pool, key=lambda x: x["stem"])
    rnd.shuffle(pool)
    pool.sort(key=lambda x: x["where"] != "local")        # local first (stable): nothing to fetch
    chosen = list(chosen or [])
    have = {a["stem"] for a in chosen}
    per_j = Counter(a["stem"][:4] for a in chosen)
    dec = Counter(a["decade"] for a in chosen)

    def take(x, why, cap=DEC_MAX):
        if x["stem"] in have or per_j[x["stem"][:4]] >= S.PER_JOURNAL or len(chosen) >= n or dec[x["decade"]] >= cap:
            return False
        chosen.append(art(x, why))
        have.add(x["stem"])
        per_j[x["stem"][:4]] += 1
        dec[x["decade"]] += 1
        return True
    for k, q in sorted(QUOTA.items(), key=lambda kv: sum(1 for x in pool if x[kv[0]])):   # rarest first
        got = sum(1 for a in chosen if k in a["flags"])
        # within a layout, the thinnest decade first
        for x in sorted([x for x in pool if x[k]], key=lambda x: dec[x["decade"]]):
            if got >= q:
                break
            if take(x, f"layout: {k}"):
                got += 1
    target = n // len(DECS)                               # 37 each; the spare go to the thinnest
    for d in DECS:
        for x in pool:
            if dec[d] >= target:
                break
            if x["decade"] == d:
                take(x, f"decade: {d}")
    for x in pool:
        if len(chosen) >= n:
            break
        if x["decade"] == min(DECS, key=lambda d: dec[d]):
            take(x, f"decade: {x['decade']}", cap=99)
    return chosen


def cmd_select():
    ex = excluded()
    m = jl(OUT / "measure.json")
    pool = usable_pool(m, ex)
    chosen = select(pool)
    jdump(HERE / "sample43b.json", dict(made=f"sample43b.py select (seed {SEED}); proposal (before PDF checks)",
                                       counts=strata(chosen), articles=chosen))
    (OUT / "pdf_ids.txt").write_text("\n".join(a["stem"] for a in chosen if not Path(a["pdf"]).exists()) + "\n")
    log(f"select: {len(chosen)} chosen; {json.dumps(strata(chosen), ensure_ascii=False)}")


def cmd_fetchpdf():
    ids = [l.strip() for l in (OUT / "pdf_ids.txt").read_text().splitlines() if l.strip()]
    res = fetch_ids(ids, ("pdf",))
    log(f"fetch pdf: {sum(1 for g in res.values() if 'pdf' in g)} of {len(ids)}")


# ------------------------------------------------------------------------------------------------ check

def cmd_check():
    """Every article: PDF opens, its pages = Azure's, 1-30 pages, a year. An unusable one is replaced by a pool article
    of the same decade (and language / thin layout if it had one), whose PDF is fetched and checked in turn."""
    ex = excluded()
    m = jl(OUT / "measure.json")
    pool = {x["stem"]: x for x in usable_pool(m, ex)}
    s = jl(HERE / "sample43b.json")
    arts = s["articles"]
    swaps, bad_ever = [], set()
    while True:
        bad = []
        for a in arts:
            if a.get("checked"):
                continue
            p, info = F.problems(Path(a["azure"]), Path(a["pdf"]), a["year"])
            a.update(info)
            if p:
                bad.append((a, p))
            else:
                a["checked"] = True
        if not bad:
            break
        for a, p in bad:
            bad_ever.add(a["stem"])
            arts.remove(a)
            have = {b["stem"] for b in arts} | bad_ever
            per_j = Counter(b["stem"][:4] for b in arts)
            cands = [x for x in pool.values() if x["stem"] not in have and per_j[x["stem"][:4]] < S.PER_JOURNAL]
            rare_ = [k for k in a["flags"] if k in QUOTA]
            cands.sort(key=lambda x: (x["decade"] != a["decade"], -sum(bool(x.get(k)) for k in rare_),
                                      x["where"] != "local", x["stem"]))
            if not cands:
                swaps.append(dict(out=a["stem"], problems=p, **{"in": None}))
                continue
            x = cands[0]
            if not Path(x["pdf"]).exists():
                F.fetch_one(x["stem"], folder_of(x["stem"]), ("pdf",))
            new = art(x, f"replaces unusable {a['stem']} ({'; '.join(p)})")
            arts.append(new)
            swaps.append(dict(out=a["stem"], problems=p, **{"in": x["stem"]}, in_decade=x["decade"], in_flags=new["flags"]))
            log(f"check: {a['stem']} unusable ({'; '.join(p)}) -> {x['stem']}")
    for a in arts:
        a.pop("checked", None)
    arts.sort(key=lambda a: a["stem"])
    st = strata(arts)
    st["swaps"] = len(swaps)
    jdump(HERE / "sample43b.json", dict(
        made=f"experiment 43 sample43b.py (seed {SEED}): the second 300, unseen; checked (PDF opens, pages = Azure's, "
             "1-30, a year); final", counts=st, articles=arts))
    jdump(OUT / "swaps.json", swaps)
    (OUT / "strata.md").write_text(table(arts), encoding="utf-8")
    log(f"check: {len(arts)} usable, {len(swaps)} swaps; {json.dumps(st, ensure_ascii=False)}")
    print(table(arts))


def strata(arts: list[dict]) -> dict:
    return dict(articles=len(arts), local=sum(a["source"] == "local" for a in arts),
                catalogue=sum(a["source"] != "local" for a in arts),
                by_pool=dict(Counter(a["pool"] for a in arts)), pages=sum(a["n"] for a in arts),
                chunks=sum(-(-a["n"] // 10) for a in arts), journals=len({a["stem"][:4] for a in arts}),
                max_per_journal=max(Counter(a["stem"][:4] for a in arts).values()) if arts else 0,
                decades=dict(sorted(Counter(a["decade"] or "unknown" for a in arts).items())),
                layouts={k: sum(1 for a in arts if k in a["flags"]) for k in LAYOUTS},
                arabic_only=sum(1 for a in arts if not {"french", "english"} & set(a["flags"])),
                pages_hist=dict(sorted(Counter(min(30, -(-a["n"] // 5) * 5) for a in arts).items())))


def table(arts: list[dict]) -> str:
    rows = ["| decade | articles (local + cat.) | pages | verse | tables | equations | two columns | French | English | shared |",
            "|---|---|---|---|---|---|---|---|---|---|"]
    keys = ("verse", "tables", "equations", "two_columns", "french", "english", "shared")
    for d in DECS + [None]:
        xs = arts if d is None else [a for a in arts if a["decade"] == d]
        loc = sum(a["source"] == "local" for a in xs)
        cells = [f"{len(xs)} ({loc} + {len(xs) - loc})", f"{sum(a['n'] for a in xs):,}"] + \
                [str(sum(1 for a in xs if k in a["flags"])) for k in keys]
        name = "**all**" if d is None else d
        if d is None:
            cells = [f"**{c}**" for c in cells]
        rows.append(f"| {name} | " + " | ".join(cells) + " |")
    return "\n".join(rows) + "\n"


if __name__ == "__main__":
    {"draw": cmd_draw, "draw_verse": cmd_draw_verse, "fetch": cmd_fetch, "measure": cmd_measure, "sheet": cmd_sheet, "select": cmd_select,
     "fetchpdf": cmd_fetchpdf, "check": cmd_check}[sys.argv[1]]()
