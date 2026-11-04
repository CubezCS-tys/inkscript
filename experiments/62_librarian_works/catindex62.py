"""Experiment 62, step 1b: the librarian's catalogue drawer — Mandumah's records that could be a cited work, found by
one sequential pass over marc.db (read-only, ~1 min) instead of probe A's per-card FTS queries (on this server the
random reads of the 10 GB file ran at ~10 s a card: 25 hours for 9,137 cards).

1. The cards' title words (norm62.tokens) are indexed; every record (245 $a $b, 242 English title) whose words cover
   >= 60% (and >= 2) of some card's title words is kept, with its authors (100/700, folded) — out/catalogue/cat62.db.
2. Each card is scored against its kept records: title (fuzzy word dice / cover, one misprinted letter forgiven),
   authors (a shared distinctive word, either script), year (either calendar, +-1), journal (for an article), type
   (a thesis only to «رسائل جامعية»), and the citing article's own record left out.
3. A proposal per card, with probe A's thresholds (decide.py) restated: accept / candidate / relation (a cited book
   matched to an article or review about it) / none. Written to out/catalogue/cat62.jsonl.

    nice python3 experiments/62_librarian_works/catindex62.py
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
from norm62 import AR, fuzzy_overlap, name_words, title_sim, tokens, years_of  # noqa: E402

MARC = "file:/home/appuser/data/marc/marc.db?mode=ro&immutable=1"
CAT_TYPE = {"journal": "بحوث ومقالات", "thesis": "رسائل جامعية", "confproc": "بحوث المؤتمرات"}


def card_title(c: dict) -> tuple[str, str | None]:
    """(the title to match, the container: a journal's name for an article)."""
    reps = [m for m in c["members"] if m["kind"] == "full"] or c["members"]
    p = (reps[0]["parsed"] if reps else None) or {}
    t = p.get("article_title") or p.get("chapter_title") or p.get("source_title") or c["title"]
    src = p.get("source_title") if p.get("article_title") else None
    return t or "", src


def card_authors(c: dict) -> set:
    w = set()
    for a in c["authors"]:
        w |= name_words(a["printed"]) | name_words(a.get("latin"))
    for m in c["members"]:
        for x in ((m["parsed"] or {}).get("authors") or []):
            if isinstance(x, list):
                w |= name_words(" ".join(y for y in x if y))
    return w


def card_years(c: dict) -> set:
    out = set()
    for m in c["members"]:
        p = m["parsed"] or {}
        out |= years_of(str(p.get("year") or ""))
    return out


def main():
    t0 = time.time()
    cards = [json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")]
    arts = json.loads((OUT / "articles62.json").read_text(encoding="utf-8"))
    ctoks = []
    for c in cards:
        t, src = card_title(c)
        ctoks.append(tokens(t))
    df = Counter(w for ts in ctoks for w in set(ts))
    idx = defaultdict(list)
    for i, ts in enumerate(ctoks):
        if len(ts) >= 2:
            for w in set(ts):
                if df[w] <= 400:
                    idx[w].append(i)
    need = [max(2, int(0.6 * len(set(ts)) + 0.999)) for ts in ctoks]
    m = sqlite3.connect(MARC, uri=True)
    OUT.joinpath("catalogue").mkdir(exist_ok=True)
    dbp = OUT / "catalogue" / "cat62.db"
    if dbp.exists():
        dbp.unlink()
    k = sqlite3.connect(dbp)
    k.execute("""CREATE TABLE recs (rec INTEGER PRIMARY KEY, c999 TEXT, title TEXT, subtitle TEXT, title_en TEXT,
                 year_int INTEGER, year_hijri TEXT, type TEXT, journal TEXT, journal_code TEXT, volume TEXT, issue TEXT,
                 page_first INTEGER, thesis TEXT, publisher TEXT, toks TEXT)""")
    k.execute("CREATE TABLE auth (rec INTEGER, seq INTEGER, name TEXT, latin TEXT, role TEXT)")
    cand = defaultdict(set)            # card index -> recs
    kept = 0
    for r in m.execute("""SELECT rec, c999, title, subtitle, title_en, subtitle_en, year_int, year_hijri, type, journal,
                                 journal_code, volume, issue, page_first, thesis, publisher FROM records"""):
        rt = tokens(f"{r[2] or ''} {r[3] or ''}")
        rt2 = tokens(f"{r[4] or ''} {r[5] or ''}") if r[4] else []
        hit = Counter()
        for ts in (rt, rt2):
            for w in set(ts):
                for i in idx.get(w, ()):
                    hit[i] += 1
        got = [i for i, n in hit.items() if n >= need[i]]
        if not got:
            continue
        kept += 1
        for i in got:
            cand[i].add(r[0])
        k.execute("INSERT INTO recs VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                  (r[0], r[1], r[2], r[3], r[4], r[6], r[7], r[8], r[9], r[10], r[11], r[12], r[13], r[14], r[15],
                   " ".join(rt + ["|"] + rt2)))
    k.commit()
    keep = {x for s in cand.values() for x in s}
    for r in m.execute("SELECT rec, seq, name, latin, role FROM authors"):
        if r[0] in keep:
            k.execute("INSERT INTO auth VALUES (?,?,?,?,?)", r)
    k.execute("CREATE INDEX auth_rec ON auth(rec)")
    k.commit()
    t1 = time.time()
    # ---------------------------------------------------------------- scoring
    R = {r[0]: r for r in k.execute("SELECT * FROM recs")}
    A = defaultdict(list)
    for rec, seq, name, latin, role in k.execute("SELECT * FROM auth ORDER BY rec, seq"):
        A[rec].append((name, latin, role))
    stem_c999 = {s: a["c999"] for s, a in arts.items()}
    out = []
    for i, c in enumerate(cards):
        t, src = card_title(c)
        ts = ctoks[i]
        au = card_authors(c)
        ys = card_years(c)
        own = {stem_c999.get(s) for s in c["stems"]}
        scored = []
        for rec in cand.get(i, ()):
            r = R[rec]
            if r[1] in own:
                continue
            rt, _, rt2 = r[15].partition("|")
            s1 = title_sim(ts, rt.split())
            s2 = title_sim(ts, rt2.split()) if rt2.strip() else s1
            s = s1 if s1["dice"] >= s2["dice"] else s2
            names = set()
            for name, latin, role in A.get(rec, []):
                if role and re.search(r"مشرف|supervis", role or "", re.I):
                    continue
                names |= name_words(name) | name_words(latin)
            if not au or not names:
                arel = None
            elif au & names or any(fuzzy_overlap([a], list(names)) for a in au):
                arel = 1.0
            else:
                arel = 0.0
            ry = set()
            if r[5]:
                ry |= years_of(str(r[5]))
            yrel = None
            if ys and ry:
                yrel = 1.0 if any(ca == cb and abs(a - b) <= 1 for ca, a in ys for cb, b in ry) else 0.0
            jrel = None
            if src and r[8]:
                jt, jr = tokens(src), tokens(r[8])
                jt = [x for x in jt if x not in ("مجله", "journal", "revue")]
                jr = [x for x in jr if x not in ("مجله", "journal", "revue")]
                if jt and jr:
                    jrel = title_sim(jt, jr)["dice"]
            scored.append(dict(rec=rec, c999=r[1], title=r[2], subtitle=r[3], title_en=r[4], year=r[5], type=r[7],
                               journal=r[8], journal_code=r[9], authors=[x[0] for x in A.get(rec, [])][:4],
                               s_title=s["dice"], s_cover=s["cover"], s_author=arel, s_year=yrel, s_journal=jrel))
        scored.sort(key=lambda x: (-x["s_title"], -(x["s_author"] or 0.5), -(x["s_year"] or 0.5), x["rec"]))
        best = None
        for x in scored[:5]:
            d, why = decide(c, ts, x)
            rank = {"accept": 3, "relation": 2, "candidate": 1, "none": 0}[d]
            if best is None or rank > best[0]:
                best = (rank, d, why, x)
        out.append(dict(cited_work_id=c["cited_work_id"], title=t, source=src, n_cands=len(scored),
                        decision=best[1] if best else "none", why=best[2] if best else "no candidate",
                        best=best[3] if best and best[1] != "none" else None, top=scored[:3]))
    with open(OUT / "catalogue" / "cat62.jsonl", "w", encoding="utf-8") as f:
        for x in out:
            f.write(json.dumps(x, ensure_ascii=False) + "\n")
    print(dict(kept_records=kept, scan_s=round(t1 - t0), total_s=round(time.time() - t0),
               decisions=dict(Counter(x["decision"] for x in out))))


def decide(c: dict, ts: list, x: dict) -> tuple[str, str]:
    """probe A's decide.py, restated on these scores."""
    T, a, Y, J = x["s_title"], x["s_author"], x["s_year"], x["s_journal"]
    rtype = x["type"] or ""
    pt = c["pub_type"]
    if len(ts) < 3:
        return "none", "title < 3 content words"
    if "عروض كتب" in rtype or "افتتاحيات" in rtype or "نصوص أدبية" in rtype:
        return ("relation" if T >= 0.85 and a != 0 else "none"), f"record type {rtype}"
    if pt == "thesis" and "رسائل" not in rtype:
        return ("candidate" if T >= 0.85 and a == 1 else "none"), "cited thesis, record not a thesis"
    if pt in ("book", "chapter") and "رسائل" not in rtype and T >= 0.85 and a == 1:
        return "relation", "cited book matched to an article: a study or a part of it"
    contradict = (Y is not None and Y == 0 and a != 1) or a == 0
    if J is not None and J < 0.3 and T >= 0.85 and a == 1:
        return "candidate", "same title+author, another journal"
    if T >= 0.85 and a == 1 and not contradict:
        return "accept", "a: title+author"
    if T >= 0.85 and a is None and Y == 1 and (J or 0) >= 0.6:
        return "accept", "b: title+year+journal"
    if T >= 0.70 and a == 1 and Y == 1 and (J or 0) >= 0.8:
        return "accept", "c: close title+author+year+journal"
    if T >= 0.75 and (a == 1 or (a is None and Y != 0)):
        return "candidate", "title close, author agrees or unknown"
    return "none", ""


if __name__ == "__main__":
    sys.exit(main())
