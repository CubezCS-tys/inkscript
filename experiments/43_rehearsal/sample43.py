"""Experiment 43: the proposed fresh sample for the dress rehearsal (~300 articles none of experiments 35/40/41 used),
stratified across journals, decades and layouts. No model calls; only reads local files.

Pool: experiment 41's inventory (out/inventory.json there: every document on this machine with its PDF and Azure's
JSON, 931), minus every document named in experiment 35's sample and editions, experiment 40's sample and experiment
41's 55. Whole documents of 1-30 pages (chunks of <= 10 pages, as in experiment 41).

Layout flags from Azure's JSON (heuristics, written down in features43.json for each document):
  tables      >= 4 rows of three or more short cells side by side (Azure's read model gives no tables)
  equations   experiment 39's page kinds count maths pages
  two_columns pages where >= 40% of lines sit side by side in two columns with a narrow gutter
  verse       pages with >= 6 pairs of half-lines mirrored about the page's centre whose second halves rhyme (one
              last letter ends >= 60% of them)
  french / english  experiment 41's inventory (Latin share and function words)
  shared      the catalogue's printed page range meets another article of the same issue on one page (one ends where
              the other starts): the first or last page holds part of another article
Selection: quotas for each layout first (random order, seed 43), then decades evened out; at most 3 documents per
journal (journal code = the stem's first four digits).

    .venv/bin/python sample43.py [--n 300] [--seed 43]   -> out/features43.json, sample43.json, prints the strata
"""
from __future__ import annotations

import argparse
import json
import random
import sqlite3
import sys
import re
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parent
OUT = HERE / "out"
STEM = re.compile(r"\d{4}-\d{3}-\d{3}-\d{3}")
QUOTA = dict(verse=25, tables=40, equations=20, two_columns=60, french=20, english=25, shared=30)
PER_JOURNAL = 3
MAX_PAGES = 30


def jl(f):
    return json.loads(Path(f).read_text(encoding="utf-8"))


def excluded() -> dict:
    ex = {}
    for name, files in (("35", [E / "35_edition/out/sample.json"]), ("40", [E / "40_gemini4_vlm/out/sample.json"]),
                        ("41", [E / "41_azure_structure/out/sample.json"])):
        for f in files:
            for s in STEM.findall(f.read_text(encoding="utf-8")):
                ex.setdefault(s, name)
    ed = E / "35_edition/out/editions"
    if ed.exists():
        for d in ed.iterdir():
            for s in STEM.findall(d.name):
                ex.setdefault(s, "35")
    return ex


def lines_of(pg: dict) -> list[tuple]:
    W, H = pg.get("width") or 1, pg.get("height") or 1
    out = []
    for ln in pg.get("lines", []):
        t = (ln.get("content") or "").strip()
        if t and ln.get("polygon"):
            xs, ys = ln["polygon"][0::2], ln["polygon"][1::2]
            out.append((min(xs) / W, min(ys) / H, max(xs) / W, max(ys) / H, t))
    return out


AR_LETTER = re.compile(r"[\u0621-\u063A\u0641-\u064A]")
FOLD = str.maketrans({"ى": "ي", "ة": "ه", "أ": "ا", "إ": "ا", "آ": "ا"})


def last_letter(t: str) -> str:
    ls = AR_LETTER.findall(t)
    return ls[-1].translate(FOLD) if ls else ""


def page_feats(pg: dict) -> dict:
    ls = lines_of(pg)
    rows = {}
    for i, a in enumerate(ls):                       # lines on one baseline (rows), by centre y
        cy, h = (a[1] + a[3]) / 2, max(a[3] - a[1], 1e-3)
        for key in rows:
            if abs(key[0] - cy) < 0.5 * key[1]:
                rows[key].append(a)
                break
        else:
            rows[(cy, h)] = [a]
    col = verse = grid = 0
    ends = []
    for r in rows.values():
        if len(r) >= 3 and all(x[2] - x[0] < 0.25 for x in r):
            grid += 1                                # three or more short cells side by side: a table row
        if len(r) != 2:
            continue
        rr, l = sorted(r, key=lambda x: -x[0])
        if not (rr[0] > 0.45 and l[2] < 0.55):
            continue
        gap, wr, wl = rr[0] - l[2], rr[2] - rr[0], l[2] - l[0]
        if gap < 0.05 and wr > 0.33 and wl > 0.33:
            col += 1
        elif gap >= 0.04 and 0.15 < wr < 0.45 and 0.15 < wl < 0.45 and abs((1 - rr[2]) - l[0]) < 0.12:
            ends.append(last_letter(l[4]))           # two half-lines, mirrored about the page's centre
    if len(ends) >= 6:                               # the second halves rhyme: one letter ends most of them
        top = Counter(e for e in ends if e).most_common(1)
        verse = top[0][1] if top and top[0][1] >= 0.6 * len(ends) else 0
    n = max(1, len(ls))
    return dict(lines=len(ls), two_col=2 * col / n >= 0.4 and col >= 8, verse=verse >= 6,
                grid=grid >= 4)


def big_line_below(pg: dict, y_min: float, need_above: int) -> bool:
    """A line at least 1.7x the page's median line height starting below y_min with need_above text lines above."""
    ls = lines_of(pg)
    if len(ls) < 8:
        return False
    hs = sorted(x[3] - x[1] for x in ls)
    med = hs[len(hs) // 2]
    for x in ls:
        if x[1] > y_min and x[3] - x[1] >= 2.0 * med and len(x[4]) >= 6 and len(x[4].split()) <= 12:
            above = sum(1 for z in ls if 0.08 < z[1] and z[3] < x[1] and len(z[4]) > 25)
            if above >= need_above:
                return True
    return False


_cat = []


def catalogue():
    if not _cat:
        sys.path.insert(0, str(E.parent / "src"))
        from inkscript.enrich.catalogue import open_catalogue
        c = open_catalogue()
        _cat.append(c)
        _cat.append(sqlite3.connect(f"file:{c.path}?mode=ro", uri=True))
    return _cat


def page_span(rec) -> tuple[int, int] | None:
    m = re.match(r"^\s*(\d+)\s*-\s*(\d+)", str((rec or {}).get("pages") or ""))
    return (int(m.group(1)), int(m.group(2))) if m else None


def shared_by_catalogue(stem: str) -> bool | None:
    """The catalogue's printed page range of this article meets another article of the same issue on one page
    (one ends on the page where the other starts). None when the catalogue has no range."""
    c, db = catalogue()
    me = page_span(c.get(stem))
    if not me:
        return None
    issue = stem.rsplit("-", 1)[0]
    for (o,) in db.execute("select stem from pdf where stem > ? and stem < ? and stem != ?",
                           (issue + "-", issue + "-~", stem)):
        sp = page_span(c.get(o))
        if sp and (sp[1] == me[0] or sp[0] == me[1]):
            return True
    return False


def doc_feats(r: dict) -> dict:
    a = jl(r["azure"])
    a = a.get("analyzeResult", a)
    pages = a.get("pages", [])
    pf = [page_feats(p) for p in pages]
    n = len(pages)
    shared = shared_by_catalogue(r["stem"])
    lat = r.get("latin_share") or 0
    return dict(stem=r["stem"], pages=n, tables=sum(f["grid"] for f in pf) >= 1,
                equations=(r.get("math_pages") or 0) > 0,
                two_columns=sum(f["two_col"] for f in pf) >= max(1, n // 3),
                verse=sum(f["verse"] for f in pf) >= 1, french=bool(r.get("french")) and lat > 0.3,
                english=bool(r.get("english")) and lat > 0.3,
                shared=shared, decade=r.get("decade"), year=r.get("year"), journal=r.get("journal"),
                journal_code=r["stem"][:4], lines=r.get("lines"), azure=r["azure"], pdf=r["pdf"],
                footnote_paras=r.get("footnote_paras") or 0)


FETCH = OUT / "fetch"
DRAW = 60000


def catalogue_draw(seed: int, skip: set) -> list[dict]:
    """DRAW random catalogue stems (cached in out/catalogue_draw.json): articles of 1-30 printed pages with a year,
    not used before and not on this machine; with decade, language, journal code, printed pages."""
    f = OUT / "catalogue_draw.json"
    if f.exists():
        rows = jl(f)
    else:
        c, db = catalogue()
        allst = [r[0] for r in db.execute("select stem from pdf")]
        stems = random.Random(seed).sample(allst, DRAW)
        del allst
        rows = []
        for st in stems:
            rec = c.get(st) or {}
            sp = page_span(rec)
            y = str(rec.get("year") or "")[:4]
            if not sp or not y.isdigit() or not 1 <= sp[1] - sp[0] + 1 <= MAX_PAGES:
                continue
            if (rec.get("type_en") or "") not in ("Article", ""):
                continue
            lang = rec.get("lang")
            lang = (lang[0] if isinstance(lang, list) and lang else str(lang or "")).strip("[]' ")
            rows.append(dict(stem=st, year=y, decade=decade(y), lang=lang, journal=(rec.get("journal") or {}).get(
                "title") if isinstance(rec.get("journal"), dict) else None, journal_code=st[:4],
                printed=f"{sp[0]}-{sp[1]}", pages=sp[1] - sp[0] + 1))
        f.write_text(json.dumps(rows, ensure_ascii=False, indent=0), encoding="utf-8")
    out = []
    for r in rows:
        if r["stem"] in skip:
            continue
        out.append(dict(r, source="catalogue", french=r["lang"] == "fre", english=r["lang"] == "eng",
                        pdf=str(FETCH / r["stem"] / f"{r['stem']}.pdf"),
                        azure=str(FETCH / r["stem"] / f"{r['stem']}.json")))
    return out


def decade(y):
    try:
        y = int(str(y)[:4])
    except Exception:
        return None
    return "pre-1960" if y < 1960 else f"{y // 10 * 10}s"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=300)
    ap.add_argument("--seed", type=int, default=43)
    args = ap.parse_args()
    inv = jl(E / "41_azure_structure/out/inventory.json")
    ex = excluded()
    pool = [r for r in inv if r["stem"] not in ex and 1 <= (r.get("pages") or 0) <= MAX_PAGES]
    ff = OUT / "features43.json"
    feats = {x["stem"]: x for x in jl(ff)} if ff.exists() else {}
    for r in pool:
        if r["stem"] not in feats:
            try:
                feats[r["stem"]] = doc_feats(r)
            except Exception as e:                      # an unreadable JSON: left out, noted
                feats[r["stem"]] = dict(stem=r["stem"], error=f"{type(e).__name__}: {e}")
    OUT.mkdir(parents=True, exist_ok=True)
    ff.write_text(json.dumps(list(feats.values()), ensure_ascii=False, indent=0), encoding="utf-8")
    cand = [feats[r["stem"]] for r in pool if "error" not in feats[r["stem"]]]
    rnd = random.Random(args.seed)
    rnd.shuffle(cand)
    chosen, why, per_j = [], {}, Counter()

    def take(x, reason):
        if x["stem"] in why or per_j[x["journal_code"]] >= PER_JOURNAL or len(chosen) >= args.n:
            return False
        chosen.append(x)
        why[x["stem"]] = reason
        per_j[x["journal_code"]] += 1
        return True
    for k, q in sorted(QUOTA.items(), key=lambda kv: sum(1 for x in cand if x[kv[0]])):      # rarest first
        have = sum(1 for x in chosen if x[k])
        for x in cand:
            if have >= q:
                break
            if x[k] and take(x, f"layout: {k}"):
                have += 1
    decs = ["pre-1960", "1960s", "1970s", "1980s", "1990s", "2000s", "2010s", "2020s"]
    target = (args.n * 9 // 10) // len(decs)          # each decade the same (33 of 300); the rest: layouts, languages
    for d in decs:                                    # stage 1: local documents up to the decade's target
        for x in cand:
            if sum(1 for y in chosen if y["decade"] == d) >= target:
                break
            if x["decade"] == d:
                take(x, f"decade: {d}")
    local_n = len(chosen)
    # stage 2: the catalogue (whole corpus; Azure JSON + PDF fetched from S3 before the run)
    draw = catalogue_draw(args.seed, set(ex) | {r["stem"] for r in inv})
    rnd.shuffle(draw)
    for lang, q in (("fre", QUOTA["french"]), ("eng", QUOTA["english"])):
        have = sum(1 for x in chosen if x[{"fre": "french", "eng": "english"}[lang]])
        for x in draw:
            if have >= q:
                break
            if x["lang"] == lang and take(x, f"catalogue, language: {lang}"):
                have += 1
    for d in decs:
        for x in draw:
            if sum(1 for y in chosen if y["decade"] == d) >= target:
                break
            if x["decade"] == d:
                take(x, f"catalogue, decade: {d}")
    for x in draw:                                     # the spare places: decades with the fewest
        if len(chosen) >= args.n:
            break
        cnt = Counter(y["decade"] for y in chosen)
        if x["decade"] == min(decs, key=lambda d: cnt[d]):
            take(x, f"catalogue, decade: {x['decade']}")
    reserve = [x for x in draw if x["stem"] not in why][:args.n // 3]
    strata = dict(articles=len(chosen), local=local_n, catalogue=len(chosen) - local_n, pages=sum(x["pages"] for x in chosen),
                  chunks=sum(-(-x["pages"] // 10) for x in chosen),
                  journals=len({x["journal_code"] for x in chosen}),
                  decades=dict(sorted(Counter(x["decade"] or "unknown" for x in chosen).items())),
                  layouts={k: sum(1 for x in chosen if x.get(k)) for k in QUOTA},
                  layouts_note="layout flags are known for the local documents only; the catalogue documents' are "
                               "measured after the fetch (features43 on their Azure JSON) and swapped from the reserve",
                  pool=dict(inventory=len(inv), excluded=sum(1 for r in inv if r["stem"] in ex),
                            too_long=sum(1 for r in inv if r["stem"] not in ex and (r.get("pages") or 0) > MAX_PAGES),
                            candidates=len(cand), layouts_in_pool={k: sum(1 for x in cand if x[k]) for k in QUOTA},
                            decades_in_pool=dict(sorted(Counter(x["decade"] or "unknown" for x in cand).items()))),
                  pages_hist=dict(sorted(Counter(min(30, -(-x["pages"] // 5) * 5) for x in chosen).items())))
    arts = [dict(stem=x["stem"], kind="whole", first=1, last=x["pages"], pages_total=x["pages"], n=x["pages"],
                 pdf=x["pdf"], azure=x["azure"], decade=x["decade"], year=x["year"], journal=x["journal"],
                 why=why[x["stem"]], flags=[k for k in QUOTA if x.get(k)], source=x.get("source", "local"),
                 printed_pages=x.get("printed")) for x in chosen]
    for a_ in arts:
        if a_["source"] != "local":
            a_["flags"] = [f for f in a_["flags"] if f in ("french", "english")] + ["layout: measure after fetch"]
    FETCH.mkdir(parents=True, exist_ok=True)
    (FETCH / "ids.txt").write_text("\n".join(a_["stem"] for a_ in arts if a_["source"] != "local") + "\n")
    (FETCH / "reserve_ids.txt").write_text("\n".join(x["stem"] for x in reserve) + "\n")
    (HERE / "sample43.json").write_text(json.dumps(dict(
        made="experiment 43 sample43.py (seed %d); proposal, not run" % args.seed, counts=strata, articles=arts,
        reserve=[x["stem"] for x in reserve]),
        ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(strata, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
