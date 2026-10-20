"""Experiment 47: citations. For every version (one run's reading of a document) loaded by load47:

1. **Back references resolve to the FIRST FULL citation of the work in the article.** The article's citation
   mentions are walked in reading order. Full citations and short forms of the same work inside the article are one
   in-article work; «المرجع نفسه»/«نفسه»/ibid. take the mention just before them, «المرجع السابق»/op. cit. the earlier
   work named by the author (and title words) written before the marker; either way the pointer goes to that work's
   first full citation, never to another back reference, so chains collapse to one step and every back reference
   counts as one more citation of the work. What cannot be resolved stays NULL with unresolved_why.
2. **Cited works**: the full citations (and short forms with no full one) of the shown versions are grouped across
   articles into one card per work (title key + a shared author word), books included.
3. **Real links only**: each cited work is matched to the catalogue (marc.db, experiment 46's link_catalogue) and to
   the archive's own publications (link_articles); a confirmed match is an accepted citation_link to a publication
   (catalogued-only records become publications W<c999>), a title-only one a candidate; a record that reviews,
   studies or is part of the cited book is a work_relation, not a link. No back reference, no in-article pointer and
   no link from an article to itself is ever a citation_link.
4. The 54 hand checks of experiment 46 are carried into `reviews`, re-attached to the v2 subjects (or marked stale).
5. Metrics: resolution, times cited, true self-citation (shared person id), journal pairs, Quran index.

    .venv/bin/python experiments/47_platform_v2/link47.py            # versions not linked yet, then all cards
    .venv/bin/python experiments/47_platform_v2/link47.py --all      # re-resolve every version
    .venv/bin/python experiments/47_platform_v2/link47.py --report   # metrics only
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import time
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import biblio47  # noqa: E402
from common47 import (DATA, DB, E46, V46, calendar_of, connect, fold, greg_to_hijri, hijri_to_greg, insert, jdump,  # noqa: E402
                      key, marc, name_parts, now, ratio, sha_files, script, tokset, year_of)

sys.path.insert(0, str(E46))
import link46  # noqa: E402

THRESHOLDS = dict(in_article_title_tokset=0.8, in_article_title_ratio=0.85, short_note_words=12,
                  catalogue="link46.link_catalogue (title ratio >= 0.85; confident: title >= 0.9 + author, or + year "
                            "with >= 3 words, or >= 0.8 + author + year)", article="link46.link_articles")
COMMON = set("محمد احمد علي عبد بن ابن ابو ابي ام ال الله حسن حسين محمود مصطفى ابراهيم عمر عثمان يوسف سعيد صالح "
             "خالد عبدالله عبدالرحمن جمال الدين al el ibn abu bin mohamed mohammed muhammad ahmed ali".split())
CACHE = DATA / "link_cache47.json"


# ------------------------------------------------------------------ keys
def title_of(p: dict) -> str | None:
    if not p:
        return None
    if p.get("article_title"):
        return p["article_title"]
    return p.get("source_title") or p.get("chapter_title")


def tnorm(t: str | None) -> str:
    k = link46.tkey(t or "")
    ws = [re.sub(r"^(ال|و?بال|لل)(?=\S{2,})", "", w) for w in k.split()]
    ws = ["بن" if w in ("ابن", "بن") else w for w in ws]
    return " ".join(w for w in ws if w)


def author_tokens(p: dict) -> set:
    out = set()
    for sn, gn in (p or {}).get("authors") or []:
        for w in key(f"{gn or ''} {sn or ''}").split():
            w2 = re.sub(r"^ال", "", w)
            if len(w2) >= 3 and w2 not in COMMON and w not in COMMON:
                out.add(w2)
    return out


def compatible(a: set, b: set) -> bool:
    return not a or not b or bool(a & b)


def same_title(t1: str, t2: str) -> bool:
    if not t1 or not t2:
        return False
    if t1 == t2:
        return True
    a, b = t1.replace(" ", ""), t2.replace(" ", "")
    if min(len(a), len(b)) >= 6 and (a in b or b in a) and tokset(t1, t2) >= THRESHOLDS["in_article_title_tokset"]:
        return True
    return tokset(t1, t2) >= 0.8 and ratio(t1, t2) >= THRESHOLDS["in_article_title_ratio"]


class UF:
    def __init__(self):
        self.p = {}

    def find(self, x):
        self.p.setdefault(x, x)
        while self.p[x] != x:
            self.p[x] = self.p[self.p[x]]
            x = self.p[x]
        return x

    def union(self, a, b):
        ra, rb = self.find(a), self.find(b)
        if ra != rb:
            self.p[max(ra, rb)] = min(ra, rb)


# ------------------------------------------------------------------ 1. resolution inside one version
HINT_STOP = re.compile(r"\b(ص|ج|جـ|مج|ط|p|pp|vol|no|voir|voy|see|cf|انظر|ينظر|يراجع|راجع|السابق|et|al|in|وانظر|"
                       r"المرجع|المصدر|مرجع|مصدر|سابق|نفسه|ذاته)\b")


def hint_words(h: str) -> list:
    k = HINT_STOP.sub(" ", key(h or ""))
    return [w for w in k.split() if len(w) >= 3 and w not in link46.STOP and not w.isdigit()]


def resolve(con, vid: int) -> dict:
    ms = [dict(r) for r in con.execute("SELECT * FROM citation_mentions WHERE version_id = ? ORDER BY reading_ord",
                                       (vid,))]
    for m in ms:
        m["p"] = json.loads(m["parsed"]) if m["parsed"] else None
        m["tk"] = tnorm(title_of(m["p"])) if m["p"] else ""
        m["au"] = author_tokens(m["p"])
    works = [m for m in ms if m["kind"] in ("full", "short") and m["tk"]]
    uf = UF()
    for i, a in enumerate(works):
        uf.find(a["mention_pk"])
        for b in works[:i]:
            if compatible(a["au"], b["au"]) and same_title(a["tk"], b["tk"]):
                uf.union(a["mention_pk"], b["mention_pk"])
            elif "short" in (a["kind"], b["kind"]) and a["au"] & b["au"] and tokset(a["tk"], b["tk"]) >= 0.6 and \
                    min(len(a["tk"].split()), len(b["tk"].split())) >= 2:
                uf.union(a["mention_pk"], b["mention_pk"])       # same author, most title words (a misprinted title)
    clusters = defaultdict(list)
    for m in works:
        clusters[uf.find(m["mention_pk"])].append(m)
    canon = {}
    for root, mm in clusters.items():
        fulls = [m for m in mm if m["kind"] == "full"]
        c = min(fulls or mm, key=lambda m: m["reading_ord"])
        for m in mm:
            canon[m["mention_pk"]] = c["mention_pk"]
    by_pk = {m["mention_pk"]: m for m in ms}
    notes = {r["note_id"]: dict(r) for r in con.execute("SELECT note_id, ord, text FROM notes WHERE version_id = ?", (vid,))}
    note_has = {m["container_id"] for m in ms if m["container_kind"] == "note"}
    upd = []
    stats = Counter()
    target = {}      # mention_pk -> canonical pk it counts for
    prev = None
    refs = [m for m in ms if m["container_kind"] == "ref-list" and m["kind"] in ("full", "short")]
    for m in ms:
        pk = m["mention_pk"]
        u = dict(full_mention_pk=None, resolve_method=None, resolve_score=None, resolved_by=None, unresolved_why=None,
                 resolve_evidence=m["resolve_evidence"])
        k = m["kind"]
        if k == "full":
            u.update(full_mention_pk=pk, resolve_method="self", resolve_score=1.0, resolved_by="link47")
            target[pk] = canon.get(pk, pk)
        elif k == "short":
            c = canon.get(pk)
            if c and c != pk and by_pk[c]["kind"] == "full":
                u.update(full_mention_pk=c, resolve_method="short-form", resolve_score=0.9, resolved_by="link47")
            else:
                u.update(unresolved_why="no-full-citation" if m["tk"] else "no-title")
            target[pk] = canon.get(pk, pk)
        elif k == "quran":
            target[pk] = pk
        elif k in ("ibid", "op_cit", "loc_cit"):
            ev = json.loads(m["resolve_evidence"]) if m["resolve_evidence"] else {}
            hw = hint_words(ev.get("hint") or "") if k != "ibid" else []
            tgt, how, sc, why = None, None, None, None
            if prev is not None and prev["container_kind"] == m["container_kind"] == "note" and \
                    prev["container_id"] == m["container_id"] and prev["kind"] in ("full", "short") and not hw:
                # «Pincus: Economic Aid, op. cit., 362»: the marker is part of the citation just parsed; that citation
                # place is counted once (as the parsed mention, resolved to its work's first full citation)
                u.update(resolve_method="part-of-citation", resolved_by="link47",
                         resolve_evidence=jdump(dict(ev, citation=prev["mention_id"])))
                stats["part-of-citation"] += 1
                target[pk] = target.get(prev["mention_pk"], prev["mention_pk"])
                upd.append((None, u["resolve_method"], None, u["resolved_by"], None, u["resolve_evidence"], pk))
                prev = m
                continue
            earlier = [x for x in ms[:ms.index(m)] if x["kind"] in ("full", "short") and x["tk"]]
            if hw:
                hs = set(hw) | {re.sub(r"^ال", "", h) for h in hw}
                pool = list(reversed(earlier)) + [x for x in refs if x not in earlier]
                by_a = [x for x in pool if x["au"] & hs]
                if by_a:
                    cl = []
                    for x in by_a:
                        c = canon.get(x["mention_pk"], x["mention_pk"])
                        if c not in cl:
                            cl.append(c)
                    left = [h for h in hw if re.sub(r"^ال", "", h) not in set().union(*(x["au"] for x in by_a))]
                    titled = []
                    for c in cl:
                        tw = {w for w in by_pk[c]["tk"].split() if len(w) >= 3}
                        n = len(tw & {re.sub(r"^ال", "", h) for h in left} | tw & set(left))
                        if n:
                            titled.append((n, c))
                    if titled:
                        tgt, how, sc = max(titled)[1], "same-author+title-words", 0.95
                    elif len(cl) == 1:
                        tgt, how, sc = cl[0], "same-author-earliest", 0.9
                    elif len(left) < 3:
                        tgt, how, sc = cl[0], "same-author-latest", 0.6
                        why = f"author has {len(cl)} works cited earlier; the most recent taken"
                    else:
                        why = "ambiguous-author"
                if not tgt and not why and len(hw) <= THRESHOLDS["short_note_words"]:
                    for x in list(reversed(earlier)) + refs:
                        tw = [w for w in x["tk"].split() if len(w) >= 3]
                        if tw and len(set(tw) & {re.sub(r"^ال", "", h) for h in hw} | set(tw) & set(hw)) >= min(2, len(tw)):
                            tgt, how, sc = canon.get(x["mention_pk"], x["mention_pk"]), "title-words", 0.8
                            break
                if not tgt and not why and (k != "ibid" and len(hw) >= 1):
                    why = "no-earlier-full: names a work not parsed earlier in the article"
            if not tgt and not why:
                # ibid (or a bare op. cit.): the mention just before; a short unparsed note in between breaks it
                p = prev
                if p is None:
                    why = "no-earlier-mention"
                else:
                    gap = False
                    if m["container_kind"] == "note" and p["container_kind"] == "note":
                        lo, hi = notes.get(p["container_id"], {}).get("ord"), notes.get(m["container_id"], {}).get("ord")
                        if lo is not None and hi is not None:
                            for nid, n in notes.items():
                                if lo < n["ord"] < hi and nid not in note_has and len((n["text"] or "").split()) <= 12 \
                                        and re.search(r"[0-9٠-٩]", n["text"] or ""):
                                    gap = True
                    if gap:
                        why = "previous-not-parsed: a short note without a parsed citation lies in between"
                    elif p["kind"] in ("ibid", "op_cit", "loc_cit"):
                        if target.get(p["mention_pk"]):
                            tgt, how, sc = target[p["mention_pk"]], "previous-mention (chain collapsed)", 0.85
                        else:
                            why = "chain-broken: the back reference before it is unresolved"
                    else:
                        tgt, how, sc = target.get(p["mention_pk"], p["mention_pk"]), "previous-mention", 0.9
            if tgt:
                u.update(full_mention_pk=tgt, resolve_method=how, resolve_score=sc, resolved_by="link47")
                if why:
                    ev["note"] = why
                    u["resolve_evidence"] = jdump(ev)
                target[pk] = tgt
                stats[f"resolved:{how}"] += 1
            else:
                u["unresolved_why"] = why
                stats[f"unresolved:{(why or '').split(':')[0]}"] += 1
        upd.append((u["full_mention_pk"], u["resolve_method"], u["resolve_score"], u["resolved_by"],
                    u["unresolved_why"], u["resolve_evidence"], pk))
        if k != "see_also":
            prev = m
    con.executemany("UPDATE citation_mentions SET full_mention_pk = ?, resolve_method = ?, resolve_score = ?, "
                    "resolved_by = ?, unresolved_why = ?, resolve_evidence = ? WHERE mention_pk = ?", upd)
    return dict(stats=stats, clusters={c: [m["mention_pk"] for m in mm] for c, mm in
                                       ((canon[mm[0]["mention_pk"]], mm) for mm in clusters.values())},
                mentions={m["mention_pk"]: m for m in works})


# ------------------------------------------------------------------ 2. cited works across articles
def build_cited_works(con, res: dict, load_id: int) -> dict:
    groups = []          # (canonical pk, mention dict, member pks, citing stem)
    for vid, r in res.items():
        for c, pks in r["clusters"].items():
            groups.append((c, r["mentions"][c], pks))
    by_t = defaultdict(list)
    for i, g in enumerate(groups):
        by_t[g[1]["tk"]].append(i)
    uf = UF()
    for t, ix in by_t.items():
        for a in ix:
            uf.find(a)
            for b in ix:
                if b < a and compatible(groups[a][1]["au"], groups[b][1]["au"]):
                    uf.union(a, b)
    cw = defaultdict(list)
    for i in range(len(groups)):
        cw[uf.find(i)].append(i)
    con.execute("DELETE FROM cited_work_members")
    con.execute("DELETE FROM cited_work_authors")
    keep = set()
    out = {}
    for root, ix in cw.items():
        reps = [groups[i] for i in ix]
        rep = max(reps, key=lambda g: (g[1]["kind"] == "full", len(json.dumps(g[1]["p"] or {}))))[1]
        au = Counter(w for g in reps for w in g[1]["au"])
        akey = au.most_common(1)[0][0] if au else ""
        nat = f"cw:{rep['tk']}|{akey}"
        cid = biblio47.public_id(con, "cited_work", nat, load_id)
        p = rep["p"] or {}
        yp = p.get("year")
        y = year_of(yp)
        cal = calendar_of(f"{yp or ''} {rep['printed'] or ''}" if y and re.search(r"%s\s*هـ" % y, fold(rep["printed"] or ""))
                          else yp, y) if y else None
        pt = p.get("pub_type") or ("article" if p.get("article_title") else "book")
        con.execute("""INSERT INTO cited_works (cited_work_id, pub_type, title, title_key, first_author_key, year_printed,
                       year_calendar, year_hijri, year_greg, edition_note, place, publisher, lang, status, method,
                       built_load) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?, 'active', ?, ?)
                       ON CONFLICT(cited_work_id) DO UPDATE SET pub_type = excluded.pub_type, title = excluded.title,
                       title_key = excluded.title_key, first_author_key = excluded.first_author_key,
                       year_printed = excluded.year_printed, year_calendar = excluded.year_calendar,
                       year_hijri = excluded.year_hijri, year_greg = excluded.year_greg, place = excluded.place,
                       publisher = excluded.publisher, lang = excluded.lang, status = 'active',
                       built_load = excluded.built_load""",
                    (cid, pt, title_of(p), rep["tk"], akey or None, yp, cal,
                     y if cal == "hijri" else (greg_to_hijri(y) if y else None),
                     hijri_to_greg(y) if cal == "hijri" else y, (p.get("extra") or {}).get("edition") if isinstance(
                         p.get("extra"), dict) else None, p.get("place"), p.get("publisher"),
                     "ara" if script(title_of(p)) == "Arab" else ("lat" if title_of(p) else None),
                     "title-key + shared author word", load_id))
        cpk = con.execute("SELECT cited_work_pk FROM cited_works WHERE cited_work_id = ?", (cid,)).fetchone()[0]
        keep.add(cpk)
        for c, m, pks in reps:
            for pk in pks:
                mm = next((x for r in res.values() for x in [r["mentions"].get(pk)] if x), None)
                if mm and (mm["kind"] == "full" or pk == c):
                    con.execute("INSERT OR REPLACE INTO cited_work_members VALUES (?,?,?,?,?, 'link47', NULL)",
                                (pk, cpk, "in-article-first" if pk == c else "in-article-repeat",
                                 1.0 if pk == c else 0.9,
                                 jdump(dict(title_key=m["tk"], authors=sorted(m["au"])))))
        for k, (sn, gn) in enumerate(p.get("authors") or []):
            printed = " ".join(x for x in (gn, sn) if x)
            pp = name_parts(printed)
            con.execute("INSERT OR REPLACE INTO cited_work_authors (cited_work_pk, seq, printed, honorific, kunya, ism, "
                        "nasab, nisba, laqab, shuhra, latin, name_key) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                        (cpk, k + 1, printed, pp["titles"], pp["kunya"], pp["ism"], pp["nasab"], pp["nisba"],
                         pp["laqab"], pp["shuhra"], printed if script(printed) == "Latn" else None,
                         key(printed).replace(" ", "")))
        out[cpk] = dict(rep=rep, citing=set())
    con.execute(f"UPDATE cited_works SET status = 'merged' WHERE cited_work_pk NOT IN ({','.join(map(str, keep)) or 0})")
    return out


# ------------------------------------------------------------------ 3. real links
def link_cards(con, mcon, cards: dict, link_run_id: int) -> Counter:
    cache = json.loads(CACHE.read_text(encoding="utf-8")) if CACHE.exists() else {}
    chash = sha_files([HERE / "link47.py", E46 / "link46.py"])
    con.execute("DELETE FROM citation_links WHERE asserted_by = 'link47'")
    con.execute("DELETE FROM work_relations WHERE asserted_by = 'link47'")
    # citing publications of each card (an article never links to itself)
    for r in con.execute("""SELECT m.cited_work_pk, p.pub_id, p.c999 FROM cited_work_members m
                            JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                            JOIN versions v ON v.version_id = c.version_id JOIN documents d ON d.stem = v.stem
                            JOIN publications p ON p.pub_id = d.pub_id"""):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["citing"].add(r["pub_id"])
    arts = []
    for r in con.execute("""SELECT d.stem, p.pub_id, p.year_shown AS pub_year,
                            (SELECT value FROM metadata_assertions a WHERE a.pub_id = p.pub_id AND a.field = 'title'
                             AND a.is_chosen = 1 LIMIT 1) AS title FROM documents d JOIN publications p ON p.pub_id = d.pub_id"""):
        x = dict(r)
        ts = [t[0] for t in con.execute("SELECT DISTINCT value FROM metadata_assertions WHERE pub_id = ? AND field IN "
                                        "('title', 'title_translated')", (r["pub_id"],))]
        x["_tk"] = [link46.tkey(t) for t in ts if t] or [""]
        x["_authors"] = [t[0] for t in con.execute(
            "SELECT b.name_text FROM authorships a JOIN authorship_mentions am USING (authorship_pk) JOIN byline_mentions "
            "b USING (mention_pk) WHERE a.pub_id = ? UNION SELECT c.name FROM authorships a JOIN catalogue_contributors c "
            "ON c.c999 = a.c999 AND c.seq = a.catalogue_seq WHERE a.pub_id = ?", (r["pub_id"], r["pub_id"]))]
        arts.append(x)
    S = Counter()
    REL = {"review": ("is_reviewed_in", "reviews"), "about": ("is_studied_in", "studies"),
           "part": ("is_part_of", "has_part")}
    t0 = time.time()
    for i, (cpk, c) in enumerate(cards.items()):
        rep = c["rep"]
        p = rep["p"] or {}
        w = dict(article_title=p.get("article_title"), pub_type=p.get("pub_type"), source_title=p.get("source_title"),
                 chapter_title=p.get("chapter_title"), authors=json.dumps(p.get("authors") or [], ensure_ascii=False),
                 year_int=year_of(p.get("year")), stem=None)
        ck = hashlib.sha1(json.dumps([chash, w], ensure_ascii=False, sort_keys=True).encode()).hexdigest()
        if ck not in cache:
            f = link46.link_catalogue(mcon, w, None)
            cache[ck] = f
        f = cache[ck]
        if f:
            ev = json.loads(f["evidence"])
            c999 = ev.get("c999")
            rel = ev.get("relation")
            tp = biblio47.ensure_catalogued_pub(con, mcon, c999) if c999 else None
            if tp and tp in c["citing"]:
                S["dropped: catalogue match is a citing article itself"] += 1
            elif tp and rel in REL:
                con.execute("INSERT INTO work_relations (subject_cited_work_pk, relation, inverse, object_pub_id, score, "
                            "method, evidence, asserted_by, link_run_id) VALUES (?,?,?,?,?,?,?, 'link47', ?)",
                            (cpk, REL[rel][0], REL[rel][1], tp, f["score"], f["method"], f["evidence"], link_run_id))
                S[f"relation:{REL[rel][0]}"] += 1
            elif tp:
                ok = bool(f["best"])
                con.execute("""INSERT OR IGNORE INTO citation_links (cited_work_pk, via_mention_pk, target_kind, target_pub_id,
                               status, best, score, method, matched_on, evidence, asserted_by, link_run_id, created)
                               VALUES (?,?, 'publication', ?, ?, ?, ?, ?, 'printed', ?, 'link47', ?, ?)""",
                            (cpk, rep["mention_pk"], tp, "accepted" if ok else "candidate", int(ok), f["score"],
                             "catalogue-fts+validate" if ok else "catalogue-fts (title only)", f["evidence"],
                             link_run_id, now()))
                S["link:catalogue:" + ("accepted" if ok else "candidate")] += 1
        x = [a for a in arts if a["pub_id"] not in c["citing"]]
        fa = link46.link_articles(x, dict(w, stem="")) if len(link46.tkey(title_of(p)).split()) >= 2 else None
        if fa:
            tp = next(a["pub_id"] for a in x if a["stem"] == fa["target_id"])
            ok = bool(fa["best"])
            con.execute("""INSERT OR IGNORE INTO citation_links (cited_work_pk, via_mention_pk, target_kind, target_pub_id,
                           status, best, score, method, matched_on, evidence, asserted_by, link_run_id, created)
                           VALUES (?,?, 'publication', ?, ?, ?, ?, ?, 'printed', ?, 'link47', ?, ?)""",
                        (cpk, rep["mention_pk"], tp, "accepted" if ok else "candidate", int(ok), fa["score"],
                         "article-fts+validate" if ok else "article-title (title only)", fa["evidence"], link_run_id,
                         now()))
            S["link:article:" + ("accepted" if ok else "candidate")] += 1
        if (i + 1) % 500 == 0:
            print(f"  linked {i + 1}/{len(cards)} cards ({time.time() - t0:.0f} s)", flush=True)
            CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    CACHE.write_text(json.dumps(cache, ensure_ascii=False), encoding="utf-8")
    # best: one accepted link per card and target kind
    con.execute("""UPDATE citation_links SET best = 0 WHERE status = 'accepted' AND link_pk NOT IN (SELECT link_pk FROM
                   (SELECT link_pk, row_number() OVER (PARTITION BY cited_work_pk ORDER BY score DESC) rn FROM
                   citation_links WHERE status = 'accepted') WHERE rn = 1)""")
    return S


def cited_authors_to_persons(con) -> int:
    """A cited author is a person when the card's accepted link is a catalogue record whose contributor with an
    authority id carries the cited surname (as a whole word)."""
    n = 0
    for r in con.execute("""SELECT a.cited_work_pk, a.seq, a.printed, p.c999 FROM cited_work_authors a
                            JOIN citation_links l ON l.cited_work_pk = a.cited_work_pk AND l.status = 'accepted'
                            AND l.best = 1 JOIN publications p ON p.pub_id = l.target_pub_id WHERE p.c999 IS NOT NULL""").fetchall():
        sn = [w for w in key(r["printed"]).split() if len(re.sub(r"^ال", "", w)) >= 3 and w not in COMMON]
        for c in con.execute("SELECT name, latin, authority_id FROM catalogue_contributors WHERE c999 = ? AND "
                             "authority_id IS NOT NULL AND is_org = 0", (r["c999"],)).fetchall():
            ws = set(key(c["name"]).split()) | {re.sub(r"^ال", "", w) for w in key(c["name"]).split()} | \
                set(key(c["latin"] or "").split())
            if sn and any(s in ws or re.sub(r"^ال", "", s) in ws for s in sn[-1:]):
                pid = biblio47.public_id(con, "person", f"auth:{c['authority_id']}", None)
                con.execute("UPDATE cited_work_authors SET person_id = ?, authority_id = ?, match_method = "
                            "'surname-in-linked-record', match_score = 0.9 WHERE cited_work_pk = ? AND seq = ?",
                            (pid, c["authority_id"], r["cited_work_pk"], r["seq"]))
                n += 1
                break
    return n


# ------------------------------------------------------------------ 4. experiment 46's hand checks
def carry_checks(con, mcon) -> Counter:
    S = Counter()
    con.execute("DELETE FROM reviews WHERE source_file = 'link_checks'")
    v46 = connect(V46, ro=True)
    for c in v46.execute("SELECT * FROM link_checks").fetchall():
        fk, fid = c["from_kind"], c["from_id"]
        stem = fid.split("|")[0]
        vid = con.execute("SELECT version_id FROM versions WHERE stem = ? AND is_current = 1", (stem,)).fetchone()
        subj, kind, fp, attach = None, None, None, "stale"
        if vid:
            vid = vid[0]
            if fk == "work":
                _, cont, seq = fid.split("|")
                ck, cid = cont.split(":", 1)
                ms = con.execute("SELECT * FROM citation_mentions WHERE version_id = ? AND container_id = ? AND kind IN "
                                 "('full', 'short') ORDER BY seq_in_container", (vid, cid)).fetchall()
                m = ms[int(seq)] if int(seq) < len(ms) else None
                if m:
                    rec = mcon.execute("SELECT c999, title FROM records WHERE rec = ?", (int(c["target_id"]),)).fetchone()
                    c999 = rec["c999"] if rec else None
                    cw = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                     (m["full_mention_pk"] or m["mention_pk"],)).fetchone()
                    kind = "relation" if c["verdict"] == "withheld-ok" else "link"
                    subj = f"{m['mention_id']}->W{c999}"
                    fp = hashlib.sha1(f"{m['printed']}|{rec['title'] if rec else ''}".encode()).hexdigest()[:16]
                    if cw:
                        l = con.execute("SELECT status FROM citation_links WHERE cited_work_pk = ? AND target_pub_id = ?",
                                        (cw[0], f"W{c999}")).fetchone()
                        r = con.execute("SELECT relation FROM work_relations WHERE subject_cited_work_pk = ? AND "
                                        "object_pub_id = ?", (cw[0], f"W{c999}")).fetchone()
                        attach = f"v2 link {l[0]}" if l else (f"v2 relation {r[0]}" if r else "v2 has no such link")
            else:
                note = fid.split("|")[1]
                m = con.execute("SELECT * FROM citation_mentions WHERE version_id = ? AND container_id = ? AND kind IN "
                                "('ibid', 'op_cit', 'loc_cit') ORDER BY seq_in_container LIMIT 1", (vid, note)).fetchone()
                if m:
                    kind, subj = "resolution", m["mention_id"]
                    fp = hashlib.sha1((m["printed"] or "").encode()).hexdigest()[:16]
                    tw = c["target_id"].split("|")   # stem|note:fn-..|k  (the v46 target work)
                    _, cont, seq = tw
                    ck, cid = cont.split(":", 1)
                    ms = con.execute("SELECT mention_pk, full_mention_pk FROM citation_mentions WHERE version_id = ? AND "
                                     "container_id = ? AND kind IN ('full', 'short') ORDER BY seq_in_container",
                                     (vid, cid)).fetchall()
                    old = ms[int(seq)] if int(seq) < len(ms) else None
                    eff = m["full_mention_pk"]
                    if eff is None and m["resolve_method"] == "part-of-citation":
                        cm = con.execute("SELECT mention_pk, full_mention_pk FROM citation_mentions WHERE version_id = ? "
                                         "AND mention_id = ?", (vid, json.loads(m["resolve_evidence"])["citation"])
                                         ).fetchone()
                        eff = (cm["full_mention_pk"] or cm["mention_pk"]) if cm else None
                    if eff is None:
                        attach = f"v2 leaves it unresolved ({m['unresolved_why']})"
                    elif old:
                        oe = old["full_mention_pk"] or old["mention_pk"]
                        a = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                        (eff,)).fetchone()
                        b = con.execute("SELECT cited_work_pk FROM cited_work_members WHERE full_mention_pk = ?",
                                        (oe,)).fetchone()
                        attach = "v2 resolves to the same work" if eff == oe or (a and b and a[0] == b[0]) else \
                            "v2 resolves to a different work"
                    else:
                        attach = "v46 target not found in v2"
        S[attach.split(" (")[0]] += 1
        insert(con, "reviews", [dict(subject_kind=kind or ("link" if fk == "work" else "resolution"),
                                     subject_key=subj or f"v46:{fk}:{fid}->{c['target_kind']}:{c['target_id']}",
                                     subject_fingerprint=fp,
                                     verdict={"near": "partly", "withheld-ok": "right"}.get(c["verdict"], c["verdict"]),
                                     note=f"{c['note']} | v46 {fk} {fid} -> {c['target_kind']} {c['target_id']} | "
                                          f"attached: {attach}",
                                     actor_id="agent:agent-46", checked=c["checked"], is_gold=0,
                                     source_file="link_checks")], "INSERT")
    return S


# ------------------------------------------------------------------ 5. metrics
def metrics(con) -> dict:
    q = lambda s, *a: con.execute(s, a).fetchall()  # noqa: E731
    cur = "JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1"
    M = {}
    M["mentions (shown versions) by kind"] = dict(q(f"SELECT m.kind, count(*) FROM citation_mentions m {cur} GROUP BY 1"))
    M["back references resolved"] = dict(q(f"SELECT m.resolve_method, count(*) FROM citation_mentions m {cur} WHERE "
                                           "m.kind IN ('ibid','op_cit','loc_cit') AND m.full_mention_pk IS NOT NULL "
                                           "GROUP BY 1 ORDER BY 2 DESC"))
    M["back references unresolved"] = dict(q(f"SELECT substr(m.unresolved_why, 1, instr(m.unresolved_why || ':', ':') - 1), "
                                             f"count(*) FROM citation_mentions m {cur} WHERE m.kind IN "
                                             "('ibid','op_cit','loc_cit') AND m.full_mention_pk IS NULL AND "
                                             "coalesce(m.resolve_method, '') <> 'part-of-citation' GROUP BY 1"))
    M["back-reference markers inside a parsed citation (counted once, as that citation)"] = q(
        f"SELECT count(*) FROM citation_mentions m {cur} WHERE m.resolve_method = 'part-of-citation'")[0][0]
    M["short forms resolved to a first full citation"] = q(
        f"SELECT count(*) FROM citation_mentions m {cur} WHERE m.kind = 'short' AND m.full_mention_pk IS NOT NULL")[0][0]
    M["back references pointing at a non-full mention"] = q(
        "SELECT count(*) FROM citation_mentions m JOIN citation_mentions t ON t.mention_pk = m.full_mention_pk "
        "WHERE m.kind IN ('ibid','op_cit','loc_cit') AND t.kind IN ('ibid','op_cit','loc_cit')")[0][0]
    M["cited works (active)"] = q("SELECT count(*) FROM cited_works WHERE status = 'active'")[0][0]
    M["cited works by type"] = dict(q("SELECT pub_type, count(*) FROM cited_works WHERE status = 'active' GROUP BY 1 "
                                      "ORDER BY 2 DESC"))
    M["cited works cited by >1 article"] = q("SELECT count(*) FROM v_times_cited WHERE n_citing_pubs > 1")[0][0]
    M["citation_links"] = dict(q("SELECT method || ' / ' || status, count(*) FROM citation_links GROUP BY 1"))
    M["work_relations"] = dict(q("SELECT relation, count(*) FROM work_relations GROUP BY 1"))
    M["same-article links (must be 0)"] = q(
        """SELECT count(*) FROM citation_links l JOIN cited_work_members w ON w.cited_work_pk = l.cited_work_pk
           JOIN citation_mentions c ON c.mention_pk = w.full_mention_pk JOIN versions v ON v.version_id = c.version_id
           JOIN documents d ON d.stem = v.stem WHERE d.pub_id = l.target_pub_id""")[0][0]
    M["top cited works"] = [dict(r) for r in q(
        """SELECT w.cited_work_id, w.title, w.first_author_key, t.n_citing_pubs, t.n_mentions, t.n_full, t.n_backrefs
           FROM v_times_cited t JOIN cited_works w USING (cited_work_pk) ORDER BY t.n_citing_pubs DESC, t.n_mentions DESC
           LIMIT 12""")]
    M["true self-citations (shared person id)"] = [dict(r) for r in q(
        """SELECT s.citing_pub_id, s.person_id, w.title FROM v_author_self_citations s
           JOIN cited_works w USING (cited_work_pk) LIMIT 20""")]
    M["journal citation pairs"] = [dict(r) for r in q("SELECT * FROM v_journal_citation_pairs ORDER BY n_mentions DESC "
                                                      "LIMIT 10")]
    M["quran index (top)"] = [dict(r) for r in q("SELECT q.*, a.sura_name_ar FROM v_quran_index q JOIN quran_ayat a ON "
                                                 "a.sura = q.sura AND a.aya = q.aya_from ORDER BY n_places DESC LIMIT 10")]
    M["quran places"] = dict(q("SELECT q.method, count(*) FROM quran_citations q JOIN versions v USING (version_id) "
                               "WHERE v.is_current = 1 GROUP BY 1"))
    return M


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--report", action="store_true")
    ap.add_argument("--db", default=str(DB))
    a = ap.parse_args(argv)
    con = connect(Path(a.db))
    t0 = time.time()
    if not a.report:
        mcon = marc()
        cur = con.execute("INSERT INTO load_events (started, tool, tool_hash, export_id, args) VALUES (?, 'link47', ?, "
                          "?, ?)", (now(), sha_files([HERE / "link47.py"]), biblio47.EXPORT, " ".join(sys.argv[1:])))
        load_id = cur.lastrowid
        lr = con.execute("INSERT INTO link_runs (linker, code_hash, thresholds, export_id, started) VALUES "
                         "('link47', ?, ?, ?, ?)", (sha_files([HERE / "link47.py", E46 / "link46.py"]),
                                                    json.dumps(THRESHOLDS, ensure_ascii=False), biblio47.EXPORT, now()))
        lrid = lr.lastrowid
        # resolution: every version not linked yet (or all); cards are rebuilt from every shown version
        done = {r[0] for r in con.execute("SELECT DISTINCT version_id FROM link_run_versions")}
        vids = [r[0] for r in con.execute("SELECT version_id FROM versions ORDER BY version_id")]
        res, stats = {}, Counter()
        for vid in vids:
            shown = con.execute("SELECT is_current FROM versions WHERE version_id = ?", (vid,)).fetchone()[0]
            if a.all or vid not in done or shown:
                r = resolve(con, vid)
                if shown:
                    res[vid] = r
                    stats.update(r["stats"])
                con.execute("INSERT OR IGNORE INTO link_run_versions VALUES (?, ?)", (lrid, vid))
        con.commit()
        print(f"resolved {len(vids)} versions ({time.time() - t0:.0f} s): {dict(stats)}", flush=True)
        cards = build_cited_works(con, res, load_id)
        con.commit()
        print(f"cited works: {len(cards)} ({time.time() - t0:.0f} s)", flush=True)
        S = link_cards(con, mcon, cards, lrid)
        np_ = cited_authors_to_persons(con)
        biblio47.refresh_persons(con, mcon, load_id)
        con.commit()
        C = carry_checks(con, mcon)
        n_links = con.execute("SELECT count(*) FROM citation_links WHERE link_run_id = ?", (lrid,)).fetchone()[0]
        con.execute("UPDATE link_runs SET finished = ?, n_versions = ?, n_links = ? WHERE link_run_id = ?",
                    (now(), len(vids), n_links, lrid))
        con.execute("UPDATE load_events SET finished = ?, n_loaded = ?, rows_by_table = ? WHERE load_id = ?",
                    (now(), len(vids), json.dumps(dict(links=dict(S), cited_authors_as_persons=np_, checks=dict(C)),
                                                  ensure_ascii=False), load_id))
        con.commit()
        print(f"links {dict(S)}; cited authors -> persons {np_}; hand checks carried {dict(C)} "
              f"({time.time() - t0:.0f} s)")
    M = metrics(con)
    (DATA / "metrics47.json").write_text(json.dumps(M, ensure_ascii=False, indent=1, default=list), encoding="utf-8")
    print(json.dumps({k: v for k, v in M.items() if not isinstance(v, list)}, ensure_ascii=False, indent=1))
    print("orphans:", len(con.execute("PRAGMA foreign_key_check").fetchall()))


if __name__ == "__main__":
    main()
