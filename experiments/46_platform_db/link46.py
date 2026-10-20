"""Experiment 46: first citation linking. Each parsed work (a <ref>'s element-citation or a note's parsed citation)
is matched to
  (a) an article in platform.db            (title against the article's printed/catalogue titles, + author, year)
  (b) a record of the catalogue (marc.db)  (FTS5 on folded title words, then title similarity + author surname +
                                            year; the catalogue authors' authority ids go into the evidence)
and each back reference («المرجع السابق», «المصدر نفسه», ibid., op. cit.) is resolved
  (c) to the earlier work of the same article: by the author (or title words) written before the marker, else the
      work cited just before it (following earlier back references).
Links go to `citation_links` (from_kind work|backref, target_kind article|catalogue|work) with a score, the method and
the evidence; source rows are never changed. `best` = the kept link per (from, target_kind).

    .venv/bin/python experiments/46_platform_db/link46.py            # articles loaded or reloaded since their last linking
    .venv/bin/python experiments/46_platform_db/link46.py --all      # every article
    .venv/bin/python experiments/46_platform_db/link46.py --report   # counts only
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common46 import DB, connect, fold, key, latin_key, marc, ratio, tokset  # noqa: E402

STOP = set("في من على عن الى إلى و او أو ثم مع بين حول نحو دراسة دراسه تحليلية تحليليه مقارنة مقارنه the of and in on "
           "for a an to with by at from al el".split())


def tkey(s: str | None) -> str:
    s = re.sub(r"\(\s*[0-9٠-٩]+\s*\)", " ", s or "")
    return key(s) if re.search("[؀-ۿ]", s) else latin_key(s)


def work_title(w) -> tuple[str | None, str]:
    """(title to match, which field). Journal article/chapter → its own title; a book/thesis → the source."""
    if w["article_title"]:
        return w["article_title"], "article_title"
    if w["pub_type"] in ("book", "thesis", "other", "web") and w["source_title"]:
        return w["source_title"], "source_title"
    if w["chapter_title"]:
        return w["chapter_title"], "chapter_title"
    return w["source_title"], "source_title"


def fts_q(words: list[str]) -> str:
    return " AND ".join('"' + w.replace('"', "") + '"' for w in words)


def surnames(w_auth) -> list[str]:
    try:
        names = json.loads(w_auth or "[]")
    except Exception:
        return []
    out = []
    for sn, gn in names:
        k = key(sn or gn or "")
        k = re.sub(r"^(ال)", "", k.split()[-1]) if k else ""
        if len(k) >= 3:
            out.append(k)
    return out


def author_hit(sns: list[str], names_folded: list[str]) -> bool:
    """A cited surname is one of the words of a catalogue name (not a substring: «حسن» is not «محسن»)."""
    if not sns:
        return False
    words = set()
    for n in names_folded:
        for w in key(n).split():
            words.add(w)
            words.add(re.sub(r"^ال", "", w))
    return any(s in words for s in sns[:2])


def year_hit(y: int | None, cy: int | None) -> bool:
    if not y or not cy:
        return False
    if y < 1500:
        return abs(y * 0.970229 + 621.5643 - cy) <= 1.5
    return abs(y - cy) <= 0


def link_catalogue(mcon, w, own_rec):
    title, field = work_title(w)
    tk = tkey(title)
    words = [x for x in tk.split() if len(x) >= 3 and x not in STOP]
    if len(words) < 2:
        return None
    words = sorted(set(words), key=lambda x: (-len(x), x))
    cands = []
    for n in (6, 4, 3):
        q = fts_q(words[:n])
        try:
            cands = [r[0] for r in mcon.execute("SELECT rowid FROM fts WHERE fts MATCH ? LIMIT 40", (q,))]
        except Exception:
            cands = []
        if cands:
            break
    if not cands:
        return None
    sns = surnames(w["authors"])
    best = None
    for rec in cands:
        if rec == own_rec:
            continue
        r = mcon.execute("SELECT rec, c999, title, subtitle, title_en, year_int, journal, type FROM records WHERE "
                         "rec = ?", (rec,)).fetchone()
        ctitles = [r["title"], " ".join(x for x in (r["title"], r["subtitle"]) if x), r["title_en"]]
        tr = max(ratio(tk, tkey(c)) for c in ctitles if c) if any(ctitles) else 0
        ts = max(tokset(tk, tkey(c)) for c in ctitles if c) if any(ctitles) else 0
        if tr < 0.85:
            continue
        full = ratio(tk, tkey(ctitles[1])) if r["subtitle"] else tr
        au = mcon.execute("SELECT name, latin, authority_id FROM authors WHERE rec = ? ORDER BY seq", (rec,)).fetchall()
        ah = author_hit(sns, [a["name"] or "" for a in au] + [a["latin"] or "" for a in au])
        yh = year_hit(w["year_int"], r["year_int"])
        sc = 0.6 * tr + 0.25 * ah + 0.15 * yh
        # what the record is: the work itself, a review of it (عروض كتب), or a part / edition of it (a long subtitle
        # such as «من بداية ترجمة … دراسة وتحقيق» the citation does not have)
        rel = "work"
        if "عروض" in (r["type"] or "") or "review" in (r["type"] or "").lower():
            rel = "review"
        elif r["subtitle"] and len(r["subtitle"].split()) >= 4 and full < 0.6:
            rel = "part"
        elif w["pub_type"] == "book" and "مقالات" in (r["type"] or "") and not (ah and yh):
            rel = "about"           # a cited book matched to a journal article: a study of the book, not the book
        # confident: the title agrees and so does the author or the year (both, if the title is only close)
        ok = rel == "work" and ((tr >= 0.9 and ah) or (tr >= 0.9 and yh and len(words) >= 3) or
                                (tr >= 0.8 and ah and yh))
        cand = (ok, rel == "work", sc, r, tr, ts, ah, yh, au, rel)
        if best is None or cand[:3] > best[:3]:
            best = cand
    if not best or best[4] < 0.85:
        return None
    ok, _, sc, r, tr, ts, ah, yh, au, rel = best
    method = "catalogue-fts" if ok else {"review": "catalogue-review-of", "part": "catalogue-part-of",
                                                       "about": "catalogue-about"}.get(
        rel, "catalogue-title-only")
    return dict(target_kind="catalogue", target_id=str(r["rec"]), score=round(sc, 3), best=int(ok), method=method,
                evidence=json.dumps(dict(field=field, title=title, catalogue_title=r["title"], c999=r["c999"],
                                         catalogue_type=r["type"], relation=rel,
                                         title_ratio=round(tr, 3), words=round(ts, 3), author=ah, year=yh,
                                         catalogue_year=r["year_int"], journal=r["journal"],
                                         authority_ids=[a["authority_id"] for a in au if a["authority_id"]],
                                         catalogue_authors=[a["name"] for a in au]), ensure_ascii=False))


def link_articles(arts, w):
    title, field = work_title(w)
    tk = tkey(title)
    if len(tk.split()) < 2:
        return None
    sns = surnames(w["authors"])
    best = None
    for a in arts:
        if a["stem"] == w["stem"]:
            continue
        if tokset(tk, a["_tk"][0]) < 0.4 and all(tokset(tk, t) < 0.4 for t in a["_tk"][1:]):
            continue
        tr = max(ratio(tk, t) for t in a["_tk"] if t)
        ah = author_hit(sns, a["_authors"])
        yh = year_hit(w["year_int"], a["pub_year"])
        sc = 0.6 * tr + 0.25 * ah + 0.15 * yh
        if tr >= 0.85:
            ok = (tr >= 0.9 and (ah or yh)) or (tr >= 0.85 and ah and yh)
            if best is None or (ok, sc) > (best[5], best[0]):
                best = (sc, a, tr, ah, yh, ok)
    if not best:
        return None
    sc, a, tr, ah, yh, ok = best
    return dict(target_kind="article", target_id=a["stem"], score=round(sc, 3), best=int(ok),
                method="article-title" if ok else "article-title-only",
                evidence=json.dumps(dict(field=field, title=title, article_title=a["title"], title_ratio=round(tr, 3),
                                         author=ah, year=yh), ensure_ascii=False))


OPCIT = re.compile(r"(?i)op\.?\s?cit|loc\.?\s?cit|مرجع\s+سابق|المرجع\s+السابق|المصدر\s+السابق|مصدر\s+سابق|م\.\s?س")


def link_backrefs(con, stem):
    """Walk the article's notes in order. «op. cit.»-type markers name an author: resolve by the author (and the title
    words when the author has several works); if the named author has no earlier parsed work, leave it unresolved.
    «ibid./نفسه/ذاته»-type markers point at the work cited just before (following earlier back references); a short
    note with no parsed work in between (a citation we failed to parse) breaks that chain."""
    works = con.execute("SELECT * FROM works WHERE stem = ? ORDER BY ord", (stem,)).fetchall()
    brs = {b["note_id"]: b for b in con.execute("SELECT * FROM back_references WHERE stem = ?", (stem,))}
    notes = con.execute("SELECT * FROM notes WHERE stem = ? ORDER BY ord", (stem,)).fetchall()
    by_note = {}
    for w in works:
        by_note.setdefault(w["container_id"], []).append(w)
    seen = [w for w in works if w["origin"] == "reference"]   # the reference list counts as cited before the notes
    out = []
    last = None
    for n in notes:
        own = by_note.get(n["note_id"], [])
        x = brs.get(n["note_id"])
        if x is None:
            if own:
                seen += own
                last = own[-1]["work_id"]
            elif len((n["text"] or "").split()) <= 12:
                last = None          # a short note we could not parse: probably a citation; ibid. after it is unknown
            continue
        whole = re.sub(r"^\W*[0-9٠-٩]+\W*", "", x["printed"] or "")
        rest = OPCIT.sub(" ", re.sub(r"(?i)ibid\.?|المرجع\s+نفسه|المصدر\s+نفسه|ذاته|نفسه", " ", whole))
        hint = key(rest)
        hint = re.sub(r"\b(ص|ج|جـ|مج|ط|p|pp|vol|no|voir|voy|see|cf|انظر|ينظر|يراجع|راجع|السابق|et|al|in)\b", " ", hint)
        hint_words = [h for h in hint.split() if len(h) >= 3 and h not in STOP and not h.isdigit()]
        hset = set(hint_words) | {re.sub(r"^ال", "", h) for h in hint_words}
        opcit = bool(OPCIT.search(whole))
        tgt, method, sc = None, None, 0
        earlier = [w for w in reversed(seen) if w["origin"] == "note"] + \
            [w for w in reversed(seen) if w["origin"] != "note"]
        if hint_words:
            by_author = [w for w in earlier if set(surnames(w["authors"])[:1]) & hset]
            if by_author:
                sn = set(surnames(by_author[0]["authors"])[:1])
                left = [h for h in hint_words if h not in sn and re.sub(r"^ال", "", h) not in sn]
                titled = []
                for w in by_author:
                    t, _ = work_title(w)
                    tw = {y for y in tkey(t).split() if len(y) >= 3 and y not in STOP}
                    k = len(tw & set(left))
                    if k >= min(2, len(tw)) and k:
                        titled.append((k, w))
                if titled:
                    tgt, method, sc = max(titled, key=lambda z: z[0])[1]["work_id"], "backref-author-title", 0.95
                elif len(left) < 3:
                    tgt, method, sc = by_author[0]["work_id"], "backref-author", 0.9
            if not tgt and len(hint_words) <= 12:    # title words of a long note match by chance (hand check)
                for w in earlier:
                    t, _ = work_title(w)
                    tw = [y for y in tkey(t).split() if len(y) >= 3 and y not in STOP]
                    if len(tw) >= 1 and len(set(tw) & set(hint_words)) >= min(2, len(tw)):
                        tgt, method, sc = w["work_id"], "backref-title", 0.8
                        break
        if not tgt and (opcit and hint_words or len(hint_words) >= 2):
            last = None              # it names a work we did not parse: leave it, and the ibid. after it
            continue
        if not tgt and last:
            tgt, method, sc = last, "backref-previous", 0.7
        if tgt:
            out.append(dict(from_kind="backref", from_id=x["backref_id"], target_kind="work", target_id=tgt,
                            score=sc, method=method, best=1,
                            evidence=json.dumps(dict(marker=x["marker"], hint=" ".join(hint_words)[:120]),
                                                ensure_ascii=False)))
            last = tgt
        else:
            last = None
        seen += own
    return out


TYPED = (("from_work_id", "TEXT"), ("from_backref_id", "TEXT"), ("target_stem", "TEXT"), ("target_rec", "INTEGER"),
         ("target_work_id", "TEXT"))


def typed(r) -> tuple:
    """from_id / target_id split by kind into the typed (key) columns."""
    fk, tk, tid = r["from_kind"], r["target_kind"], r["target_id"]
    return (r["from_id"] if fk == "work" else None, r["from_id"] if fk == "backref" else None,
            tid if tk == "article" else None, int(tid) if tk == "catalogue" else None,
            tid if tk == "work" else None)


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--stem", action="append")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args(argv)
    con = connect(Path(a.db))
    con.execute("CREATE TABLE IF NOT EXISTS link_runs (stem TEXT PRIMARY KEY, linked TEXT)")
    have = {r[1] for r in con.execute("PRAGMA table_info(citation_links)")}
    for c, t in TYPED:  # typed copies of from_id / target_id (declared as keys in schema46.sql; added to older dbs)
        if c not in have:
            con.execute(f"ALTER TABLE citation_links ADD COLUMN {c} {t}")
    if not a.report:
        if a.stem:
            stems = a.stem
        elif a.all:
            stems = [r[0] for r in con.execute("SELECT stem FROM articles ORDER BY stem")]
        else:
            stems = [r[0] for r in con.execute("SELECT a.stem FROM articles a LEFT JOIN link_runs l USING (stem) "
                                               "WHERE l.linked IS NULL OR l.linked < a.loaded ORDER BY a.stem")]
        mcon = marc()
        arts = [dict(r) for r in con.execute(
            "SELECT a.stem, a.title, a.title_printed, a.title_en, a.pub_year, cr.title AS ct, cr.title_en AS cte "
            "FROM articles a LEFT JOIN catalogue_records cr ON cr.stem = a.stem AND cr.is_primary = 1")]
        for x in arts:
            x["_tk"] = [tkey(t) for t in (x["title"], x["title_printed"], x["ct"], x["title_en"], x["cte"]) if t]
            x["_authors"] = [r[0] for r in con.execute(
                "SELECT printed_name FROM article_authors WHERE stem = ? UNION SELECT name FROM catalogue_authors "
                "WHERE stem = ?", (x["stem"], x["stem"]))]
        own = {r[0]: r[1] for r in con.execute("SELECT stem, rec FROM articles")}
        t0 = time.time()
        for i, stem in enumerate(stems):
            con.execute("DELETE FROM citation_links WHERE from_id LIKE ? || '|%' AND source = 'link46'", (stem,))
            rows = []
            for w in con.execute("SELECT * FROM works WHERE stem = ?", (stem,)).fetchall():
                for f in (link_articles(arts, w), link_catalogue(mcon, w, own.get(stem))):
                    if f:
                        rows.append(dict(from_kind="work", from_id=w["work_id"], **f))
            rows += link_backrefs(con, stem)
            ts = time.strftime("%Y-%m-%d %H:%M:%S")
            con.executemany("INSERT OR REPLACE INTO citation_links (from_kind, from_id, target_kind, target_id, score, "
                            "method, best, evidence, linked, source, from_work_id, from_backref_id, target_stem, "
                            "target_rec, target_work_id) VALUES (?,?,?,?,?,?,?,?,?, 'link46',?,?,?,?,?)",
                            [(r["from_kind"], r["from_id"], r["target_kind"], r["target_id"], r["score"], r["method"],
                              r["best"], r["evidence"], ts) + typed(r) for r in rows])
            con.execute("INSERT OR REPLACE INTO link_runs VALUES (?, ?)", (stem, ts))
            if (i + 1) % 20 == 0:
                con.commit()
                print(f"  {i + 1}/{len(stems)} articles ({time.time() - t0:.0f} s)", flush=True)
        con.commit()
    rep = {}
    rep["works"] = con.execute("SELECT count(*) FROM works").fetchone()[0]
    for tk in ("article", "catalogue"):
        rep[f"works linked to {tk}"] = con.execute(
            "SELECT count(DISTINCT from_id) FROM citation_links WHERE from_kind = 'work' AND target_kind = ?",
            (tk,)).fetchone()[0]
    rep["works linked (any)"] = con.execute(
        "SELECT count(DISTINCT from_id) FROM citation_links WHERE from_kind = 'work'").fetchone()[0]
    rep["back references"] = con.execute("SELECT count(*) FROM back_references").fetchone()[0]
    rep["back references resolved"] = dict(con.execute(
        "SELECT method, count(*) FROM citation_links WHERE from_kind = 'backref' GROUP BY method").fetchall())
    rep["catalogue links by work type"] = dict(con.execute(
        "SELECT w.pub_type, count(*) FROM citation_links l JOIN works w ON w.work_id = l.from_id WHERE "
        "l.target_kind = 'catalogue' GROUP BY 1").fetchall())
    rep["works by type"] = dict(con.execute("SELECT pub_type, count(*) FROM works GROUP BY 1").fetchall())
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
