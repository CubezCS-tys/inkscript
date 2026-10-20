"""Experiment 46: load a run's masters (and its flags, patches, judge findings) into the platform database
/home/yassine/data/platform/platform.db, with the catalogue's view of each article from marc.db (experiment 45).

    .venv/bin/python experiments/46_platform_db/load46.py --run v33_300            # add / refresh a run
    .venv/bin/python experiments/46_platform_db/load46.py --run v33_300 --stem 1058-005-993-021 --force
    .venv/bin/python experiments/46_platform_db/load46.py --run v2_55 --current if-new   # do not displace another run

Idempotent and incremental: an article whose master files (JATS, D33 sidecar, patches sidecar) have not changed since
the run was last loaded is skipped; a changed or new one is re-read and its rows replaced. Flags, patches and judge
findings of the run are re-read every time (they are small) and replaced for that run only. Sources are never edited:
the masters are read, marc.db is opened read-only.

Which run fills an article's content (blocks, notes, works…) when several runs hold it: `--current always` (default:
the run loaded last wins, e.g. a judged copy loaded after its run) or `if-new` (only articles not yet in the database).
Every (article, run) loaded is in `article_runs`; flags/patches/findings are kept for every run.
"""
from __future__ import annotations

import argparse
import glob
import json
import re
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from common46 import DB, OUT43, connect, fold, key, latin_key, marc, ratio, to_int, tokset, year_of  # noqa: E402
from parse46 import parse_article  # noqa: E402

CONTENT = ("blocks", "notes", "note_calls", "figures", "works", "back_references", "fixes", "misprints",
           "metadata_changes", "keywords", "article_dates", "abstracts", "article_authors", "affiliations",
           "catalogue_records", "catalogue_authors", "subjects", "catalogue_disagreements")


def now():
    return time.strftime("%Y-%m-%d %H:%M:%S")


def init(con):
    con.executescript((HERE / "schema46.sql").read_text(encoding="utf-8"))
    con.execute("CREATE VIRTUAL TABLE IF NOT EXISTS blocks_fts USING fts5(text_folded, content='blocks', "
                "content_rowid='id', tokenize='unicode61 remove_diacritics 2')")
    con.execute("INSERT OR REPLACE INTO meta VALUES ('schema', 'experiment 46 v1')")


def insert(con, table, rows):
    rows = list(rows)
    if not rows:
        return
    cols = list(rows[0])
    con.executemany(f"INSERT OR REPLACE INTO {table} ({','.join(cols)}) VALUES ({','.join('?' * len(cols))})",
                    [tuple(r.get(c) for c in cols) for r in rows])


# ------------------------------------------------------------------ catalogue (marc.db, read only)
TITLE_PREFIX = re.compile(r"^\s*(أ\.?\s*د\.?|ا\.?\s*د\.?|د\s*/|د\s*\.|د\s|الدكتورة?|الأستاذة?|الاستاذة?|أ\s*/|أ\s*\.|"
                          r"prof\.?|dr\.?|professor)\s*", re.I)


def clean_person(name: str) -> str:
    s = name or ""
    for _ in range(3):
        s = TITLE_PREFIX.sub("", s)
    return s.strip(" .،,/")


def nospace(s: str) -> str:
    return key(s).replace(" ", "")


def name_score(printed: str, cat: str, latin: str | None = None) -> float:
    """Printed 'given surname' against the catalogue's 'surname، given' (and the Latin form)."""
    p = nospace(clean_person(printed))
    parts = re.split(r"[،,]", cat or "", maxsplit=1)
    forms = [nospace(cat)]
    if len(parts) == 2:
        forms.append(nospace(parts[1] + " " + parts[0]))
    best = max((ratio(p, f) for f in forms if f), default=0.0)
    if latin:
        lp = latin_key(clean_person(printed)).replace(" ", "")
        lparts = re.split(r",", latin, maxsplit=1)
        lforms = [latin_key(latin).replace(" ", "")]
        if len(lparts) == 2:
            lforms.append(latin_key(lparts[1] + " " + lparts[0]).replace(" ", ""))
        best = max([best] + [ratio(lp, f) for f in lforms if f])
    return best


def catalogue(mcon, stem: str, art: dict) -> tuple[list, list, list, list, list]:
    recs = mcon.execute("SELECT r.*, p.seq AS pseq FROM pdf_ids p JOIN records r ON r.rec = p.rec WHERE p.stem = ? "
                        "ORDER BY p.seq, r.rec", (stem,)).fetchall()
    if not recs:
        return [], [], [], [], []
    tk = key(art.get("title"))
    prim = max(recs, key=lambda r: ratio(tk, key(r["title"])) if tk else 0)
    crow, cauth, kw, subj, abst = [], [], [], [], []
    for r in recs:
        crow.append(dict(stem=stem, rec=r["rec"], c999=r["c999"], record_id=r["record_id"],
                         is_primary=int(r["rec"] == prim["rec"]), title=r["title"], subtitle=r["subtitle"],
                         title_en=r["title_en"], language=r["language"], year=r["year_int"],
                         year_hijri=r["year_hijri"], pages=r["pages"], page_first=r["page_first"],
                         page_last=r["page_last"], journal=r["journal"], journal_en=r["journal_en"],
                         journal_code=r["journal_code"], issn=r["issn"], volume=r["volume"], issue=r["issue"],
                         issue_printed=r["issue_printed"], article_seq=r["article_seq"], doi=r["doi"],
                         type=r["type"], publisher=r["publisher"], country=r["country"],
                         fields_of_study=r["fields_of_study"], n_authors=r["n_authors"], source="catalogue"))
    p = prim["rec"]
    for a in mcon.execute("SELECT * FROM authors WHERE rec = ? ORDER BY seq", (p,)):
        cauth.append(dict(stem=stem, rec=p, seq=a["seq"], name=a["name"], latin=a["latin"], role=a["role"],
                          authority_id=a["authority_id"], is_org=a["is_org"], source="catalogue"))
    off = 1000
    for k in mcon.execute("SELECT * FROM keywords WHERE rec = ? ORDER BY seq", (p,)):
        for lang in ("ar", "en"):
            if k[lang]:
                kw.append(dict(stem=stem, seq=off, lang=lang, term=k[lang], term_printed=None, term_key=key(k[lang]),
                               source="catalogue", run=None))
                off += 1
    for s in mcon.execute("SELECT * FROM subjects WHERE rec = ? ORDER BY seq", (p,)):
        subj.append(dict(stem=stem, seq=s["seq"], scheme=s["source"], term=s["term"], term_key=key(s["term"]),
                         source="catalogue"))
    for i, a in enumerate(mcon.execute("SELECT * FROM abstracts WHERE rec = ? ORDER BY seq", (p,))):
        t = a["text"]
        lang = "ar" if re.search("[؀-ۿ]", t or "") else "en"
        abst.append(dict(stem=stem, lang=lang, seq=100 + i, text=t, block_id=None, source="catalogue", run=None))
    return crow, cauth, kw, subj, abst


def match_authors(authors: list[dict], cauth: list[dict]) -> None:
    """Greedy best pairs printed↔catalogue; then a printed name in the other script (the same person printed twice,
    Arabic and Latin) joins the catalogue author it matches (Latin form) or, failing that, its Arabic twin by order.
    Sets person_key (the catalogue authority id when the names agree)."""
    people = [c for c in cauth if not c["is_org"]]
    pairs = sorted(((name_score(a["printed_name"], c["name"], c["latin"]), i, j)
                    for i, a in enumerate(authors) for j, c in enumerate(people)), reverse=True)
    used_a, used_c = set(), set()

    def take(i, c, s, how):
        authors[i].update(catalogue_seq=c["seq"], catalogue_name=c["name"], authority_id=c["authority_id"],
                          name_score=round(s, 3), match=how)

    for s, i, j in pairs:
        if i in used_a or j in used_c or s < 0.6:
            continue
        used_a.add(i)
        used_c.add(j)
        take(i, people[j], s, "name" if s >= 0.75 else "weak")
    # second pass: the other-script twin
    lat = [i for i, a in enumerate(authors) if not re.search("[\u0600-\u06ff]", a["printed_name"] or "")]
    ara = [i for i, a in enumerate(authors) if i not in lat]
    for s, i, j in pairs:
        if i in used_a or s < 0.75:
            continue
        used_a.add(i)
        take(i, people[j], s, "name-variant")
    if lat and ara and len(lat) == len(ara):
        for i, k in zip(lat, ara):
            if i not in used_a and k in used_a and authors[k].get("match") in ("name", "weak"):
                c = next(c for c in people if c["seq"] == authors[k]["catalogue_seq"])
                used_a.add(i)
                take(i, c, 0.0, "script-twin")
    for a in authors:
        a.setdefault("catalogue_seq", None)
        a.setdefault("catalogue_name", None)
        a.setdefault("authority_id", None)
        a.setdefault("name_score", None)
        a.setdefault("match", "none" if people else "no-catalogue")
        if a["authority_id"] and a["match"] in ("name", "name-variant", "script-twin"):
            a["person_key"] = "auth:" + a["authority_id"]
        else:
            a["person_key"] = "name:" + nospace(clean_person(a["printed_name"]))


def title_key(s: str | None) -> str:
    s = (s or "").replace("ﷺ", " صلى الله عليه وسلم ")
    s = re.sub(r"\(\s*[0-9٠-٩]+\s*\)\s*$", "", s.strip())
    return key(s)


LANG = {"ara": "ar", "eng": "en", "fre": "fr", "fra": "fr", "ger": "de"}


def disagreements(art: dict, crow: list, cauth: list, authors: list, kws: list, absts: list, run: str) -> list:
    prim = next((c for c in crow if c["is_primary"]), None)
    if not prim:
        return []
    out = []

    def add(field, mv, cv, kind, sev, note=""):
        out.append(dict(stem=art["stem"], rec=prim["rec"], c999=prim["c999"], field=field,
                        masters_value=None if mv is None else str(mv), catalogue_value=None if cv is None else str(cv),
                        kind=kind, severity=sev, note=note, run=run))

    # title
    mt = art.get("title")
    if mt:
        cands = [prim["title"], " ".join(x for x in (prim["title"], prim["subtitle"]) if x), prim["title_en"]]
        mk = title_key(mt)
        best = max(cands, key=lambda c: ratio(mk, title_key(c)) if c else -1)
        bk = title_key(best)
        r = ratio(mk, bk)
        a_, b_ = mk.replace(" ", ""), bk.replace(" ", "")
        if a_ != b_:
            ts = tokset(mk, bk)
            if r >= 0.9:
                add("title", mt, best, "spelling", "low", f"ratio {r:.2f}")
            elif ts >= 0.9 or (min(len(a_), len(b_)) >= 6 and (a_ in b_ or b_ in a_)):
                add("title", mt, best, "partial", "low", f"one contains the other (words {ts:.2f}, ratio {r:.2f})")
            else:
                add("title", mt, best, "different", "medium" if r >= 0.6 else "high", f"ratio {r:.2f}, words {ts:.2f}")
    # English title
    if art.get("title_en") and prim["title_en"]:
        a, b = latin_key(art["title_en"]), latin_key(prim["title_en"])
        if a.replace(" ", "") != b.replace(" ", ""):
            r = ratio(a, b)
            add("title_en", art["title_en"], prim["title_en"], "spelling" if r >= 0.9 else "different",
                "low" if r >= 0.9 else "medium", f"ratio {r:.2f}")
    elif art.get("title_en") and not prim["title_en"]:
        add("title_en", art["title_en"], None, "missing-in-catalogue", "low")
    # authors
    cpeople = [c for c in cauth if not c["is_org"]]
    n_printed = len({a["catalogue_seq"] if a["catalogue_seq"] is not None else f"u{a['seq']}" for a in authors})
    if authors and n_printed != len(cpeople):
        add("authors", n_printed, len(cpeople), "count", "medium",
            "; ".join(a["printed_name"] for a in authors) + "  vs  " + "; ".join(c["name"] for c in cpeople))
    for a in authors:
        if cpeople and a["match"] in ("none", "weak"):
            add(f"author {a['seq'] + 1}", a["printed_name"], a.get("catalogue_name"),
                "name" if a["match"] == "weak" else "not-in-catalogue", "medium",
                f"name score {a['name_score']}" if a["name_score"] else "no catalogue author matches")
    # year
    my, cy = art.get("pub_year"), prim["year"]
    if my and cy and my != cy:
        hij = [int(x) for x in re.findall(r"\d{4}", fold(prim["year_hijri"] or ""))]
        greg = my * 0.970229 + 621.5643 if my < 1500 else None
        if my in hij or (greg and abs(greg - cy) <= 1.5):
            pass      # the print gives the hijri year; the catalogue the gregorian one
        else:
            add("year", my, cy, "differs", "medium")
    elif not my and cy:
        pass
    # pages
    mf, ml = to_int(art.get("fpage")), to_int(art.get("lpage"))
    cf, cl = prim["page_first"], prim["page_last"]
    n = art.get("scan_pages")

    def fits(f, l):
        return bool(f and l and n and l - f + 1 == n)

    for fld, mv_, cv_ in (("fpage", mf, cf), ("lpage", ml, cl)):
        if mv_ and cv_ and mv_ != cv_:
            mfit = fits(mf, ml)
            cfit = fits(cf if fld == "fpage" else mf, cl if fld == "lpage" else ml)
            kind = "catalogue-fits-scan" if cfit and not mfit else "masters-fits-scan" if mfit and not cfit else "differs"
            add(fld, art[fld], cv_, kind, "info" if kind == "catalogue-fits-scan" else "medium",
                f"scan has {n} pages: masters {mf}-{ml}, catalogue {cf}-{cl}")
    # volume / issue
    mv, cv = to_int(art.get("volume")), to_int(prim["volume"])
    if mv and cv and mv != cv:
        add("volume", art["volume"], prim["volume"], "differs", "low")
    mi = to_int(art.get("issue"))
    if mi:
        ci = [to_int(prim["issue"])] + [to_int(x) for x in re.findall(r"\d+", fold(prim["issue_printed"] or ""))]
        if any(ci) and mi not in ci:
            add("issue", art["issue"], f"{prim['issue']} ({prim['issue_printed'] or ''})", "differs", "low")
    # DOI
    md, cd = (art.get("doi") or "").lower().strip(), (prim["doi"] or "").lower().strip()
    if md and cd and md.replace("https://doi.org/", "") != cd.replace("https://doi.org/", ""):
        add("doi", art["doi"], prim["doi"], "differs", "medium")
    elif md and not cd:
        add("doi", art["doi"], None, "missing-in-catalogue", "low")
    # language
    ml_ = (art.get("language") or "")[:2]
    cls = {LANG.get(x.strip(), x.strip()) for x in (prim["language"] or "").split(",") if x.strip()}
    if ml_ and cls and ml_ not in cls:
        add("language", ml_, prim["language"], "differs", "medium")
    # abstracts and keywords the print has but the catalogue lacks
    for lang in ("ar", "en"):
        if art.get(f"abstract_{lang}") and not any(a["lang"] == lang for a in absts if a["source"] == "catalogue"):
            add(f"abstract_{lang}", (art[f"abstract_{lang}"] or "")[:120] + "…", None, "missing-in-catalogue", "low")
    if any(k["source"] == "masters" for k in kws) and not any(k["source"] == "catalogue" for k in kws):
        add("keywords", "؛ ".join(k["term"] for k in kws if k["source"] == "masters")[:200], None,
            "missing-in-catalogue", "low")
    return out


# ------------------------------------------------------------------ one article
def load_article(con, mcon, mdir: Path, stem: str, run: str) -> dict:
    R = parse_article(mdir, stem, run)
    art = R["article"]
    crow, cauth, ckw, csubj, cabs = catalogue(mcon, stem, art)
    prim = next((c for c in crow if c["is_primary"]), None)
    if prim:
        art.update(rec=prim["rec"], c999=prim["c999"], record_id=prim["record_id"])
    authors = R["authors"]
    match_authors(authors, cauth)
    for d in CONTENT:
        con.execute(f"DELETE FROM {d} WHERE stem = ?", (stem,))
    con.execute("DELETE FROM work_authors WHERE work_id LIKE ? || '|%'", (stem,))
    con.execute("DELETE FROM citation_links WHERE from_id LIKE ? || '|%'", (stem,))
    art["loaded"] = now()
    insert(con, "articles", [art])
    insert(con, "blocks", R["blocks"])
    insert(con, "notes", R["notes"])
    insert(con, "note_calls", R["note_calls"])
    insert(con, "figures", R["figures"])
    insert(con, "works", R["works"])
    insert(con, "work_authors", R["work_authors"])
    insert(con, "back_references", R["back_references"])
    insert(con, "fixes", R["fixes"])
    insert(con, "misprints", R["misprints"])
    insert(con, "metadata_changes", R["metadata_changes"])
    insert(con, "keywords", R["keywords"] + ckw)
    insert(con, "article_dates", R["dates"])
    insert(con, "abstracts", R["abstracts"] + cabs)
    insert(con, "article_authors", authors)
    insert(con, "affiliations", R["affiliations"])
    insert(con, "catalogue_records", crow)
    insert(con, "catalogue_authors", cauth)
    insert(con, "subjects", csubj)
    insert(con, "catalogue_disagreements",
           disagreements(art, crow, cauth, authors, R["keywords"] + ckw, R["abstracts"] + cabs, run))
    con.execute("UPDATE article_runs SET current = 0 WHERE stem = ?", (stem,))
    con.execute("INSERT OR REPLACE INTO article_runs VALUES (?,?,?,?,?,1)", (stem, run, R["sha"], art["made"], now()))
    jt = R["journal_title"]
    con.execute("INSERT OR IGNORE INTO journals (journal_id) VALUES (?)", (art["journal_id"],))
    if jt:
        con.execute("UPDATE journals SET title_masters = ? WHERE journal_id = ?", (jt, art["journal_id"]))
    if prim:
        con.execute("UPDATE journals SET title_catalogue = ?, title_en_catalogue = ?, issn = ?, publisher = ?, "
                    "country = ? WHERE journal_id = ?", (prim["journal"], prim["journal_en"], prim["issn"],
                                                         prim["publisher"], prim["country"], art["journal_id"]))
    return art


# ------------------------------------------------------------------ run-level quality files
def load_flags(con, run: str, path: Path) -> int:
    con.execute("DELETE FROM flags WHERE run = ?", (run,))
    if not path.exists():
        return 0
    d = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for stem, a in (d.get("articles") or {}).items():
        for f in a.get("flags") or []:
            extra = {k: v for k, v in f.items() if k not in ("id", "stem", "kind", "severity", "page", "lines", "box",
                                                             "reason")}
            rows.append(dict(flag_id=f.get("id"), run=run, stem=f.get("stem") or stem, kind=f.get("kind"),
                             severity=f.get("severity"), page=f.get("page"),
                             lines=json.dumps(f.get("lines"), ensure_ascii=False),
                             box=json.dumps(f.get("box")), reason=f.get("reason"),
                             extra=json.dumps(extra, ensure_ascii=False) if extra else None, made=d.get("made"),
                             source="flags43"))
    insert(con, "flags", rows)
    for stem, a in (d.get("articles") or {}).items():
        con.execute("UPDATE articles SET flags_high = ?, flags_medium = ?, flags_low = ? WHERE stem = ? AND run = ?",
                    (a.get("high"), a.get("medium"), a.get("low"), stem, run))
    return len(rows)


def _j(x):
    return None if x is None else (x if isinstance(x, str) else json.dumps(x, ensure_ascii=False))


def load_patches(con, run: str, mdir: Path, pdirs: list[Path]) -> int:
    con.execute("DELETE FROM patches WHERE built_run = ?", (run,))
    status = {}
    for sc in mdir.glob("*.patches.json"):
        try:
            d = json.loads(sc.read_text(encoding="utf-8"))
        except Exception:
            continue
        for kind in ("applied", "skipped", "overridden"):
            for e in d.get(kind) or []:
                pid = e.get("id") if isinstance(e, dict) else e
                status[pid] = (kind, e.get("why") if isinstance(e, dict) else None)
        for e in d.get("log") or []:
            if isinstance(e, dict) and e.get("id"):
                status[e["id"]] = (e.get("status") or e.get("result") or "logged", e.get("why"))
    rows = []
    for pdir in pdirs:
        for f in sorted(pdir.glob("*.json")) if pdir.exists() else []:
            try:
                lst = json.loads(f.read_text(encoding="utf-8"))
            except Exception:
                continue
            if isinstance(lst, dict):
                lst = lst.get("patches") or []
            for p in lst:
                if not isinstance(p, dict) or not p.get("id"):
                    continue
                st, why = status.get(p["id"], (None, None))
                if st is None:
                    st = "proposed" if not p.get("apply") else "not-built"
                rows.append(dict(patch_id=p["id"], run=p.get("run") or run, stem=p.get("article"), page=p.get("page"),
                                 action=p.get("action"), targets=_j(p.get("targets")), payload=_j(p.get("payload")),
                                 source=p.get("source"), confidence=_j(p.get("confidence")),
                                 evidence=_j(p.get("evidence")), reason=p.get("reason"), route=p.get("route"),
                                 apply=int(bool(p.get("apply"))), status=st, status_why=_j(why), built_run=run,
                                 created=p.get("created"), raw=_j(p), file=str(f)))
    insert(con, "patches", rows)
    return len(rows)


def judge_files(run: str) -> list[Path]:
    pats = [OUT43 / run / "judge" / "**" / "*.json", OUT43 / "judge" / run / "**" / "*.json",
            OUT43 / "judge" / "**" / f"findings*{run}*.json", OUT43 / "judge" / "**" / "findings*.json"]
    seen = []
    for p in pats:
        for f in glob.glob(str(p), recursive=True):
            if f not in seen:
                seen.append(f)
    return [Path(f) for f in seen]


def load_judge(con, run: str) -> int:
    con.execute("DELETE FROM judge_findings WHERE run = ?", (run,))
    rows = []
    for f in judge_files(run):
        try:
            d = json.loads(f.read_text(encoding="utf-8"))
        except Exception:
            continue
        lst = d if isinstance(d, list) else (d.get("findings") if isinstance(d, dict) else None)
        if not isinstance(lst, list):
            continue
        frun = d.get("run") if isinstance(d, dict) else None
        for k, x in enumerate(lst):
            if not isinstance(x, dict) or not (x.get("type") or x.get("kind") or x.get("question")):
                continue
            r = x.get("run") or frun or run
            if r != run and not (OUT43 / run / "judge") in f.parents:
                continue
            stem = x.get("stem") or x.get("article") or (d.get("stem") if isinstance(d, dict) else None)
            fid = x.get("id") or f"{stem}|p{x.get('page')}|{f.stem}|{k}"
            rows.append(dict(finding_id=fid, run=run, stem=stem, page=x.get("page"), type=x.get("type") or x.get("kind"),
                             question=_j(x.get("question")), answer=_j(x.get("answer")), targets=_j(x.get("targets")),
                             confidence=_j(x.get("confidence")), evidence=_j(x.get("evidence")),
                             code_check=_j(x.get("code_check") or x.get("check")), action=_j(x.get("action")),
                             route=x.get("route"), patch_id=x.get("patch_id") or x.get("patch"),
                             status=x.get("status"), model=x.get("model") or (d.get("model") if isinstance(d, dict)
                                                                               else None),
                             created=x.get("created"), raw=_j(x), source=x.get("source") or "judge", file=str(f)))
    insert(con, "judge_findings", rows)
    return len(rows)


# ------------------------------------------------------------------ global rebuilds (cheap; deterministic)
def rebuild_people(con):
    con.execute("DELETE FROM people")
    con.execute("DELETE FROM person_names")
    aa = con.execute("SELECT * FROM article_authors").fetchall()
    ca = {(r["stem"], r["seq"]): r for r in con.execute(
        "SELECT ca.* FROM catalogue_authors ca JOIN catalogue_records cr ON cr.stem = ca.stem AND cr.rec = ca.rec "
        "AND cr.is_primary = 1")}
    # name keys known for each authority person
    auth_of_key = {}
    for a in aa:
        if a["person_key"].startswith("auth:"):
            auth_of_key[nospace(clean_person(a["printed_name"]))] = a["person_key"]
            if a["catalogue_name"]:
                parts = re.split(r"[،,]", a["catalogue_name"], maxsplit=1)
                auth_of_key[nospace(" ".join(reversed(parts)))] = a["person_key"]
    for c in ca.values():
        if c["authority_id"] and not c["is_org"]:
            parts = re.split(r"[،,]", c["name"], maxsplit=1)
            auth_of_key.setdefault(nospace(" ".join(reversed(parts))), "auth:" + c["authority_id"])
    names, people = {}, {}
    for a in aa:
        pk = a["person_key"]
        if pk.startswith("name:"):
            pk = auth_of_key.get(pk[5:], pk)
            if pk != a["person_key"]:
                con.execute("UPDATE article_authors SET person_key = ?, match = match || '+variant' WHERE stem = ? "
                            "AND seq = ?", (pk, a["stem"], a["seq"]))
        p = people.setdefault(pk, dict(person_key=pk, authority_id=pk[5:] if pk.startswith("auth:") else None,
                                       stems=set(), printed={}, latin=None, catalogue={}))
        p["stems"].add(a["stem"])
        p["printed"][a["printed_name"]] = p["printed"].get(a["printed_name"], 0) + 1
        if a["catalogue_name"]:
            p["catalogue"][a["catalogue_name"]] = p["catalogue"].get(a["catalogue_name"], 0) + 1
            c = ca.get((a["stem"], a["catalogue_seq"]))
            if c and c["latin"]:
                p["latin"] = c["latin"]
    rows, nrows = [], []
    for pk, p in people.items():
        disp = max(p["printed"], key=p["printed"].get)
        rows.append(dict(person_key=pk, authority_id=p["authority_id"], display_name=clean_person(disp),
                         latin_name=p["latin"], n_articles=len(p["stems"]),
                         source="catalogue+masters" if p["authority_id"] else "masters"))
        for n, k in p["printed"].items():
            nrows.append(dict(person_key=pk, name=n, name_key=nospace(clean_person(n)), form="printed", n=k,
                              source="masters"))
        for n, k in p["catalogue"].items():
            nrows.append(dict(person_key=pk, name=n, name_key=nospace(n), form="catalogue", n=k, source="catalogue"))
        if p["latin"]:
            nrows.append(dict(person_key=pk, name=p["latin"], name_key=latin_key(p["latin"]).replace(" ", ""),
                              form="latin", n=1, source="catalogue"))
    insert(con, "people", rows)
    insert(con, "person_names", nrows)
    return len(rows)


def rebuild_journals_issues(con):
    con.execute("UPDATE journals SET n_articles = (SELECT count(*) FROM articles a WHERE a.journal_id = "
                "journals.journal_id)")
    con.execute("DELETE FROM issues")
    con.execute("""INSERT INTO issues SELECT a.issue_id, a.journal_id, max(coalesce(a.volume, cr.volume)),
                   max(coalesce(a.issue, cr.issue)), max(cr.issue_printed), max(coalesce(cr.year, a.pub_year)),
                   max(cr.year_hijri), count(*) FROM articles a LEFT JOIN catalogue_records cr ON cr.stem = a.stem
                   AND cr.is_primary = 1 GROUP BY a.issue_id""")


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--run", required=True, help="run folder under experiments/43_rehearsal/out (masters in <run>/masters)")
    ap.add_argument("--masters", help="masters folder, if not out/<run>/masters")
    ap.add_argument("--flags", help="flags43 output, if not out/<run>/flags.json")
    ap.add_argument("--patches", action="append", help="patch folder(s), default out/<run>/patches")
    ap.add_argument("--stem", action="append", help="only these articles")
    ap.add_argument("--force", action="store_true", help="re-read articles even if unchanged")
    ap.add_argument("--current", choices=("always", "if-new"), default="always")
    ap.add_argument("--db", default=str(DB))
    ap.add_argument("--note", default=None)
    a = ap.parse_args(argv)
    run = a.run
    mdir = Path(a.masters) if a.masters else OUT43 / run / "masters"
    if not mdir.exists():
        sys.exit(f"no masters folder {mdir}")
    con = connect(Path(a.db))
    init(con)
    mcon = marc()
    stems = sorted(p.name[:-len(".jats.xml")] for p in mdir.glob("*.jats.xml"))
    if a.stem:
        stems = [s for s in stems if s in set(a.stem)]
    stamp = {}
    sj = next(iter(sorted(mdir.glob("*.stamp.json"))), None)
    if sj:
        stamp = json.loads(sj.read_text(encoding="utf-8"))
    t0 = time.time()
    done = skipped = kept = 0
    for i, stem in enumerate(stems):
        cur = con.execute("SELECT run FROM articles WHERE stem = ?", (stem,)).fetchone()
        if a.current == "if-new" and cur and cur["run"] != run:
            from parse46 import sha_of
            sha = sha_of([mdir / f"{stem}.jats.xml", mdir / f"{stem}.metachanges.json", mdir / f"{stem}.patches.json"])
            con.execute("INSERT OR REPLACE INTO article_runs VALUES (?,?,?,?,?,0)",
                        (stem, run, sha, stamp.get("made"), now()))
            kept += 1
            continue
        if not a.force and cur and cur["run"] == run:
            from parse46 import sha_of
            sha = sha_of([mdir / f"{stem}.jats.xml", mdir / f"{stem}.metachanges.json", mdir / f"{stem}.patches.json"])
            old = con.execute("SELECT sha FROM article_runs WHERE stem = ? AND run = ?", (stem, run)).fetchone()
            if old and old["sha"] == sha:
                skipped += 1
                continue
        load_article(con, mcon, mdir, stem, run)
        done += 1
        if done % 25 == 0:
            con.commit()
            print(f"  {i + 1}/{len(stems)} articles ({time.time() - t0:.0f} s)", flush=True)
    con.commit()
    nf = load_flags(con, run, Path(a.flags) if a.flags else OUT43 / run / "flags.json")
    pdirs = [Path(p) for p in a.patches] if a.patches else [OUT43 / run / "patches"]
    npch = load_patches(con, run, mdir, pdirs)
    nj = load_judge(con, run)
    rebuild_people(con)
    rebuild_journals_issues(con)
    import inst46
    inst46.rebuild(con)
    con.execute("INSERT INTO blocks_fts(blocks_fts) VALUES ('rebuild')")
    n_cur = con.execute("SELECT count(*) FROM articles WHERE run = ?", (run,)).fetchone()[0]
    con.execute("""INSERT INTO runs (run, masters_dir, prompt, prompt_hash, rules_hash, model, first_loaded, last_loaded,
                   n_articles, note) VALUES (?,?,?,?,?,?,?,?,?,?) ON CONFLICT(run) DO UPDATE SET
                   masters_dir = excluded.masters_dir, prompt = excluded.prompt, prompt_hash = excluded.prompt_hash,
                   rules_hash = excluded.rules_hash, model = excluded.model, last_loaded = excluded.last_loaded,
                   n_articles = excluded.n_articles, note = coalesce(excluded.note, runs.note)""",
                (run, str(mdir), stamp.get("prompt"), stamp.get("prompt_hash"), stamp.get("rules_hash"),
                 stamp.get("model"), now(), now(), n_cur, a.note))
    con.commit()
    print(f"run {run}: {len(stems)} masters, {done} loaded, {skipped} unchanged, {kept} kept under another run; "
          f"{nf} flags, {npch} patches, {nj} judge findings ({time.time() - t0:.0f} s)")


if __name__ == "__main__":
    main()
