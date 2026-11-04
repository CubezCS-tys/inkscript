"""What the Desk's pages read (P2): articles, persons, cited works, the top-cited list, search, and a summary of a
release for the before/after view.

Everything is read from the newest release copy on disk, else platform_v2.db, always opened read-only
(`db.open_reading`). Nothing here writes to the machine's reading. Per-state caches (times cited, the search index)
are keyed by the state file's path and mtime, so a new release is picked up at once.

Arabic folding for search is platform v2's own (`common46.fold` through `common47`): no diacritics or tatweel,
alef/hamza forms unified, ى→ي, ة→ه, ASCII digits, lower case."""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
import threading
import time
from collections import Counter, defaultdict
from pathlib import Path

from . import db
from .reading import CURRENT_MENTION, Reading

E47 = Path(__file__).resolve().parents[2] / "47_platform_v2"
if str(E47) not in sys.path:
    sys.path.insert(0, str(E47))
from common47 import fold  # noqa: E402  (read-only use of platform v2's folding)

ARABIC = re.compile(r"[؀-ۿ]")
RELEASE_ID = re.compile(r"R\d{8}T\d{6}(-\d+)?")
STEM = re.compile(r"[0-9A-Za-z][0-9A-Za-z,\-]{2,60}")
# the article beside its scans (experiment 41's mirror pages, served on :8899 and proxied by the web as /views/)
VIEWS = Path(os.environ.get("DESK_VIEWS", Path(__file__).resolve().parents[2] / "41_azure_structure" / "out" / "views"))


def mirror_of(run: str | None, stem: str) -> str | None:
    if run and re.fullmatch(r"[0-9A-Za-z_\-]{1,80}", run) and (VIEWS / run / "mirror" / f"{stem}.html").is_file():
        return f"/views/{run}/mirror/{stem}.html"
    return None
_lock = threading.Lock()
_cache: dict = {}


def state_of(pg) -> tuple[Path, str | None]:
    """(path, release_id or None for the machine reading)."""
    p = db.state_path(pg)
    rid = p.stem if RELEASE_ID.fullmatch(p.stem) and p.parent.resolve() == db.releases_dir().resolve() else None
    if rid is None:
        r = pg.execute("SELECT release_id FROM releases WHERE path = %s", (str(p),)).fetchone()
        rid = r["release_id"] if r else None
    return p, rid


def open_ro(path: Path) -> sqlite3.Connection:
    con = db.open_reading(path)
    con.create_function("fold", 1, fold, deterministic=True)
    return con


def _cached(path: Path, name: str, build):
    k = (str(path), os.path.getmtime(path), name)
    with _lock:
        if k in _cache:
            return _cache[k]
    v = build()
    with _lock:
        for old in [x for x in _cache if x[0] == str(path) and x[2] == name and x != k]:
            del _cache[old]
        if len([x for x in _cache if x[2] == name]) > 3:        # at most a few states in memory
            for old in sorted((x for x in _cache if x[2] == name), key=lambda x: x[1])[:-3]:
                del _cache[old]
        _cache[k] = v
    return v


def times_cited(path: Path) -> dict:
    """cited_work_pk -> (citing articles, mentions incl. back references), from v_times_cited."""
    def build():
        con = open_ro(path)
        try:
            return {r[0]: (r[1], r[2]) for r in con.execute(
                "SELECT cited_work_pk, n_citing_pubs, n_mentions FROM v_times_cited")}
        finally:
            con.close()
    return _cached(path, "tc", build)


def _rows(con, sql, args=()):
    return [dict(r) for r in con.execute(sql, args).fetchall()]


def _cols(con, table: str) -> set:
    """The columns a table has in this state (a release built before the v3.5b fields lacks them)."""
    return {r[1] for r in con.execute(f"PRAGMA table_info([{table}])")}


def _has_table(con, table: str) -> bool:
    return bool(con.execute("SELECT 1 FROM sqlite_master WHERE name = ?", (table,)).fetchone())


def _opt(con, table: str, alias: str, cols) -> str:
    """', a.x, a.y' for those of cols the table has, NULL AS x for the rest (so one query reads every state)."""
    have = _cols(con, table)
    return "".join(f", {alias}.{c}" if c in have else f", NULL AS {c}" for c in cols)


ABOUT = ("conference", "thesis", "reviewed_book", "original")
V35_MENTION = ("edition", "year_calendar", "year2", "year2_calendar", "work_pages", "cited_pages_source", "died",
               "access_date", "ms_library", "ms_shelfmark", "ms_folio", "thesis_degree", "conf_name", "conf_loc")


def _script(text: str | None) -> str:
    t = text or ""
    a = len(ARABIC.findall(t))
    return "ar" if a and a >= 0.3 * len(re.findall(r"\w", t)) else "lat"


# ------------------------------------------------------------------ the top-cited list
def top_works(path: Path, limit: int = 30) -> list[dict]:
    tc = times_cited(path)
    con = open_ro(path)
    try:
        cards = {r["cited_work_pk"]: r for r in con.execute(
            "SELECT cited_work_pk, cited_work_id, title, pub_type, year_printed FROM cited_works WHERE status = 'active'")}
        ranked = sorted(((pk, v) for pk, v in tc.items() if pk in cards),
                        key=lambda x: (-x[1][0], -x[1][1], cards[x[0]]["cited_work_id"]))[:limit]
        out = []
        for i, (pk, (npub, nm)) in enumerate(ranked, 1):
            c = cards[pk]
            au = [r[0] for r in con.execute("SELECT printed FROM cited_work_authors WHERE cited_work_pk = ? ORDER BY seq "
                                            "LIMIT 3", (pk,))]
            out.append(dict(rank=i, work=f"work:{c['cited_work_id']}", id=c["cited_work_id"], title=c["title"],
                            authors=au, pub_type=c["pub_type"], year=c["year_printed"], n_citing_pubs=npub,
                            n_mentions=nm))
        return out
    finally:
        con.close()


# ------------------------------------------------------------------ search (Arabic folding)
def _index(path: Path) -> dict:
    def build():
        con = open_ro(path)
        tc = times_cited(path)
        try:
            arts = {}
            for r in con.execute("""SELECT d.stem, d.pub_id, p.title_shown, p.year_shown, v.version_id
                                    FROM documents d JOIN versions v ON v.stem = d.stem AND v.is_current = 1
                                    LEFT JOIN publications p ON p.pub_id = d.pub_id"""):
                arts[r["stem"]] = dict(stem=r["stem"], pub_id=r["pub_id"], title=r["title_shown"], year=r["year_shown"],
                                       hay=[r["title_shown"] or "", r["stem"], r["pub_id"] or ""], authors=[])
            by_pub = defaultdict(list)
            for s, a in arts.items():
                if a["pub_id"]:
                    by_pub[a["pub_id"]].append(s)
            for r in con.execute("SELECT pub_id, value FROM metadata_assertions WHERE field IN ('title', 'subtitle', "
                                 "'title_translated')"):
                for s in by_pub.get(r[0], []):
                    arts[s]["hay"].append(r[1] or "")
            for r in con.execute("""SELECT a.pub_id, a.position, coalesce(p.preferred_name_ar, p.preferred_name_lat) nm,
                                           p.preferred_name_lat lat FROM authorships a
                                    LEFT JOIN persons p ON p.person_id = a.person_id ORDER BY a.pub_id, a.position"""):
                for s in by_pub.get(r[0], []):
                    if r[2] and r[2] not in arts[s]["authors"]:
                        arts[s]["authors"].append(r[2])
                    arts[s]["hay"] += [r[2] or "", r[3] or ""]
            for r in con.execute("""SELECT v.stem, b.printed FROM byline_mentions b
                                    JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1"""):
                if r[0] in arts:
                    arts[r[0]]["hay"].append(r[1] or "")
            persons = {}
            nw = Counter(r[0] for r in con.execute("SELECT person_id FROM authorships WHERE person_id IS NOT NULL"))
            for r in con.execute("SELECT person_id, status, preferred_name_ar, preferred_name_lat FROM persons "
                                 "WHERE status <> 'merged'"):
                persons[r[0]] = dict(id=r[0], status=r[1], name=r[2] or r[3], name_lat=r[3],
                                     n_works=nw.get(r[0], 0), hay=[r[2] or "", r[3] or "", r[0]])
            for r in con.execute("SELECT person_id, full_form FROM person_names"):
                if r[0] in persons:
                    persons[r[0]]["hay"].append(r[1] or "")
            works = {}
            for r in con.execute("SELECT cited_work_pk, cited_work_id, title, pub_type FROM cited_works "
                                 "WHERE status = 'active'"):
                n = tc.get(r[0], (0, 0))
                works[r[0]] = dict(id=r[1], title=r[2], pub_type=r[3], n_citing_pubs=n[0], n_mentions=n[1],
                                   authors=[], hay=[r[2] or "", r[1]])
            for r in con.execute("SELECT cited_work_pk, printed FROM cited_work_authors ORDER BY seq"):
                if r[0] in works:
                    works[r[0]]["authors"].append(r[1] or "")
                    works[r[0]]["hay"].append(r[1] or "")
            for d in (arts, persons, works):
                for x in d.values():
                    x["folded"] = fold(" | ".join(h for h in x.pop("hay") if h))
            return dict(articles=list(arts.values()), persons=list(persons.values()), works=list(works.values()))
        finally:
            con.close()
    return _cached(path, "index", build)


def _match(items, q: str, key, limit: int):
    words = fold(q).split()
    if not words:
        return []
    hits = [x for x in items if all(w in x["folded"] for w in words)]
    hits.sort(key=key)
    return [{k: v for k, v in x.items() if k != "folded"} for x in hits[:limit]]


def search_articles(path: Path, q: str | None, limit: int = 50) -> list[dict]:
    ix = _index(path)["articles"]
    if not (q or "").strip():
        return [{k: v for k, v in x.items() if k != "folded"} for x in sorted(ix, key=lambda a: a["stem"])[:limit]]
    return _match(ix, q, lambda a: (a["stem"]), limit)


def search(path: Path, q: str, limit: int = 20) -> dict:
    ix = _index(path)
    return dict(q=q, folded=fold(q),
                articles=_match(ix["articles"], q, lambda a: a["stem"], limit),
                persons=_match(ix["persons"], q, lambda p: (-p["n_works"], p["name"] or ""), limit),
                works=_match(ix["works"], q, lambda w: (-w["n_citing_pubs"], -w["n_mentions"], w["id"]), limit))


# ------------------------------------------------------------------ an article, whole
def _anchors(con, pks) -> dict:
    pks = [p for p in set(pks) if p]
    out = {}
    for i in range(0, len(pks), 900):
        chunk = pks[i:i + 900]
        for r in con.execute(f"SELECT anchor_pk, anchor_key, page, method FROM ink_anchors WHERE anchor_pk IN "
                             f"({','.join('?' * len(chunk))})", chunk):
            out[r[0]] = dict(key=r[1], page=r[2], method=r[3])
    return out


def article(path: Path, stem: str) -> dict | None:
    if not STEM.fullmatch(stem or ""):
        return None
    con = open_ro(path)
    try:
        doc = con.execute("""SELECT d.*, v.version_id, v.run, v.complete, v.pages_covered, v.pages_expected,
                                    v.current_reason FROM documents d
                             JOIN versions v ON v.stem = d.stem AND v.is_current = 1 WHERE d.stem = ?""",
                          (stem,)).fetchone()
        if not doc:
            return None
        vid, pub_id = doc["version_id"], doc["pub_id"]
        pub = con.execute("SELECT * FROM publications WHERE pub_id = ?", (pub_id,)).fetchone() if pub_id else None
        cat = con.execute("SELECT c999, type, title, subtitle, title_en, language_raw, year_raw, year_int, pages_raw, "
                          "page_first, page_last, journal_code, journal_raw, volume_raw, issue_raw, doi FROM "
                          "catalogue_records WHERE c999 = ?", (pub["c999"],)).fetchone() if pub and pub["c999"] else None
        journal = None
        if pub and pub["journal_id"]:
            j = con.execute("SELECT * FROM journals WHERE journal_id = ?", (pub["journal_id"],)).fetchone()
            t = con.execute("SELECT title FROM journal_titles WHERE journal_id = ? ORDER BY is_chosen DESC, n DESC "
                            "LIMIT 1", (pub["journal_id"],)).fetchone()
            journal = dict(id=pub["journal_id"], title=t[0] if t else None, **({k: j[k] for k in j.keys()} if j else {}))
        issue = None
        if pub and pub["issue_id"]:
            i = con.execute("SELECT * FROM issues WHERE issue_id = ?", (pub["issue_id"],)).fetchone()
            issue = dict(i) if i else None

        anchor_pks = []
        # metadata: every value given for a field (printed in this version, corrected, catalogue, others)
        meta = defaultdict(list)
        if pub_id:
            for r in _rows(con, """SELECT assert_pk, field, value, lang, script, form, source, version_id, block_id,
                                          anchor_pk, confidence, rule, reason, is_chosen, chosen_rule, actor_id
                                   FROM metadata_assertions WHERE pub_id = ? AND (version_id IS NULL OR version_id = ?)
                                   ORDER BY field, is_chosen DESC, form""", (pub_id, vid)):
                anchor_pks.append(r["anchor_pk"])
                meta[r["field"]].append(r)

        def form(field, f):
            for r in meta.get(field, []):
                if r["form"] == f:
                    return r["value"]
            return None

        title = dict(printed=form("title", "printed"), corrected=form("title", "corrected") or form("title", "person"),
                     catalogue=form("title", "catalogue"), shown=pub["title_shown"] if pub else None,
                     translated=form("title_translated", "printed") or form("title_translated", "catalogue"))

        # authors: authorships with their person, bylines, affiliations and institutions
        authors = []
        if pub_id:
            for a in _rows(con, """SELECT a.authorship_pk, a.position, a.role_code, rc.name_en role_name, a.person_id,
                                          a.c999, a.catalogue_seq, a.method, a.score, a.asserted_by,
                                          p.preferred_name_ar, p.preferred_name_lat, p.status person_status,
                                          cc.name cat_name, cc.latin cat_latin, cc.authority_id
                                   FROM authorships a LEFT JOIN persons p ON p.person_id = a.person_id
                                   LEFT JOIN role_codes rc ON rc.code = a.role_code
                                   LEFT JOIN catalogue_contributors cc ON cc.c999 = a.c999 AND cc.seq = a.catalogue_seq
                                   WHERE a.pub_id = ? ORDER BY a.position, a.role_code""", (pub_id,)):
                bl = []
                for b in _rows(con, """SELECT b.mention_pk, b.printed, b.titles, b.name_text, b.script, b.email,
                                              b.block_id, b.byline_pos, b.anchor_pk, i.anchor_key""" + _opt(
                                       con, "byline_mentions", "b", ("is_corresponding", "ids", "contrib_type",
                                                                     "role_phrase", "twin_of_pk")) + """
                                       FROM authorship_mentions am JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                                       JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                                       LEFT JOIN ink_anchors i ON i.anchor_pk = b.anchor_pk
                                       WHERE am.authorship_pk = ? ORDER BY b.byline_pos""", (a["authorship_pk"],)):
                    key = b["anchor_key"] or f"{stem}|{b['block_id'] or ''}|{b['byline_pos']}|{b['script'] or ''}"
                    affs = []
                    for f in _rows(con, "SELECT f.aff_pk, f.seq, f.printed, f.position_title, f.org_text, "
                                        "f.faculty_text, f.dept_text, f.city, f.country_code, f.kind, f.anchor_pk" +
                                        _opt(con, "affiliation_mentions", "f", ("assembled", "faculty_printed")) +
                                        " FROM affiliation_mentions f WHERE f.mention_pk = ? ORDER BY f.seq",
                                        (b["mention_pk"],)):
                        f["institutions"] = _rows(con, """
                            SELECT l.inst_id, l.level, l.method, l.score, i.kind, i.country_code,
                                   (SELECT name FROM institution_names n WHERE n.inst_id = l.inst_id
                                    ORDER BY (n.type = 'label') DESC, n.n_seen DESC LIMIT 1) name
                            FROM affiliation_links l JOIN institutions i ON i.inst_id = l.inst_id
                            WHERE l.aff_pk = ?""", (f["aff_pk"],))
                        anchor_pks.append(f["anchor_pk"])
                        affs.append(f)
                    anchor_pks.append(b["anchor_pk"])
                    b["ids"] = json.loads(b["ids"]) if b["ids"] else None
                    b["twin"] = bool(b.pop("twin_of_pk"))         # the same person printed again in another script
                    bl.append(dict(b, key=f"byline:{key}", affiliations=affs))
                a["name"] = a["preferred_name_ar"] or a["preferred_name_lat"] or a["cat_name"]
                a["corresponding"] = any(b["is_corresponding"] for b in bl)
                a["ids"] = _rows(con, "SELECT scheme, value, assigned_by, source FROM external_ids WHERE entity_kind = "
                                      "'A' AND entity_id = ? ORDER BY scheme, value", (a["person_id"],)) \
                    if a["person_id"] else []
                a["person"] = f"person:{a['person_id']}" if a["person_id"] else None
                a["bylines"] = bl
                authors.append(a)

        pages = _rows(con, "SELECT page, width_px, height_px, image_w, image_h, printed_folio FROM pages WHERE stem = ? "
                           "ORDER BY page", (stem,))
        sections = _rows(con, "SELECT section_id, parent_id, level, ord, heading_block_id, heading FROM sections "
                              "WHERE version_id = ? ORDER BY ord", (vid,))
        blocks = _rows(con, "SELECT block_id, ord, page, last_page, role, section_id, note_id, figure_id, lang, text, "
                            "role_source, text_source, n_fixes, n_misprints, n_flags, wc_min, anchor_pk FROM blocks "
                            "WHERE version_id = ? ORDER BY ord", (vid,))
        parts = defaultdict(list)
        for p in _rows(con, "SELECT block_id, part, page, x, y, w, h FROM block_parts WHERE version_id = ? "
                            "ORDER BY block_id, part", (vid,)):
            parts[p.pop("block_id")].append(p)
        verses = defaultdict(list)
        for v in _rows(con, "SELECT verse_id, group_block_id, seq, part, text, call_ids, poet_hint FROM verse_lines "
                            "WHERE version_id = ? ORDER BY group_block_id, seq", (vid,)):
            verses[v.pop("group_block_id")].append(v)
        for b in blocks:
            b["parts"] = parts.get(b["block_id"], [])
            b["script"] = _script(b["text"])
            if b["block_id"] in verses:
                b["verses"] = verses[b["block_id"]]
            anchor_pks.append(b["anchor_pk"])

        calls = _rows(con, "SELECT call_seq, call_text, block_id, char_offset, status, anchor_pk FROM note_calls "
                           "WHERE version_id = ? ORDER BY call_seq", (vid,))
        targets = defaultdict(list)
        for r in con.execute("SELECT call_seq, note_id FROM note_call_targets WHERE version_id = ?", (vid,)):
            targets[r[0]].append(r[1])
        calls_of_note = defaultdict(list)
        for c in calls:
            c["targets"] = targets.get(c["call_seq"], [])
            for t in c["targets"]:
                calls_of_note[t].append(c["call_seq"])
        notes = _rows(con, "SELECT n.note_id, n.kind, n.label, n.label_int, n.ord, n.page, n.first_block_id, n.text, "
                           "n.anchor_pk" + _opt(con, "notes", "n", ("written_by",)) +
                           " FROM notes n WHERE n.version_id = ? ORDER BY n.ord", (vid,))
        for n in notes:
            n["calls"] = calls_of_note.get(n["note_id"], [])
            n["script"] = _script(n["text"])
            anchor_pks.append(n["anchor_pk"])

        figures = _rows(con, "SELECT f.figure_id, f.kind, f.page, f.x, f.y, f.w, f.h, f.caption_block_id, "
                             "f.anchor_block_id, f.label, f.caption, f.alt_ar, f.alt_en, f.text_in_figure, f.tex, "
                             "f.specific_use" + _opt(con, "figures", "f", ("fig_type",)) +
                             " FROM figures f WHERE f.version_id = ? ORDER BY f.page, f.y", (vid,))
        fnotes = defaultdict(list)
        if _has_table(con, "figure_notes"):
            for r in _rows(con, "SELECT figure_id, seq, kind, block_id, note_id, text, anchor_pk FROM figure_notes "
                                "WHERE version_id = ? ORDER BY figure_id, seq", (vid,)):
                anchor_pks.append(r["anchor_pk"])
                fnotes[r.pop("figure_id")].append(r)
        page_marks = _rows(con, "SELECT page, kind, problem, line_id, text, anchor_pk FROM page_marks WHERE "
                                "version_id = ? ORDER BY page, kind, mark_id", (vid,)) \
            if _has_table(con, "page_marks") else []
        anchor_pks += [r["anchor_pk"] for r in page_marks]
        cells = defaultdict(list)
        for c in _rows(con, "SELECT figure_id, row, col, rowspan, colspan, is_header, text FROM table_cells "
                            "WHERE version_id = ? ORDER BY figure_id, row, col", (vid,)):
            cells[c.pop("figure_id")].append(c)
        for f in figures:
            f["cells"] = cells.get(f["figure_id"], [])
            f["notes"] = fnotes.get(f["figure_id"], [])

        # citations: each with its card (times cited), the card's best real link, and a back reference's target
        tc = times_cited(path)
        cits = _rows(con, """SELECT m.mention_pk, m.mention_id, m.container_kind, m.container_id, m.reading_ord, m.kind,
                                    m.marker, m.printed, m.parsed, m.cited_volume, m.cited_pages, m.page, m.block_id,
                                    m.full_mention_pk, m.resolve_method, m.resolve_score, m.resolved_by,
                                    m.unresolved_why, m.anchor_pk,
                                    w.cited_work_pk, w.cited_work_id, w.title card_title, w.pub_type, w.status card_status
                                    """ + _opt(con, "citation_mentions", "m", V35_MENTION) + _opt(
                                        con, "cited_work_members", "cm", ("edition_pk",)) + """
                             FROM citation_mentions m
                             LEFT JOIN cited_work_members cm ON cm.full_mention_pk = coalesce(m.full_mention_pk, m.mention_pk)
                             LEFT JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk
                             WHERE m.version_id = ? ORDER BY m.reading_ord, m.seq_in_container""", (vid,))
        by_pk = {c["mention_pk"]: c for c in cits}
        card_pks = {c["cited_work_pk"] for c in cits if c["cited_work_pk"]}
        links = {}
        if card_pks:
            ks = list(card_pks)
            for i in range(0, len(ks), 900):
                ch = ks[i:i + 900]
                for r in _rows(con, f"""SELECT l.cited_work_pk, l.target_kind, l.target_pub_id, l.target_scheme,
                                               l.target_value, l.status, l.score, l.method, p.title_shown,
                                               p.year_shown, (SELECT stem FROM documents d WHERE d.pub_id = l.target_pub_id
                                               LIMIT 1) target_stem
                                        FROM citation_links l LEFT JOIN publications p ON p.pub_id = l.target_pub_id
                                        WHERE l.best = 1 AND l.status IN ('accepted', 'candidate')
                                          AND l.cited_work_pk IN ({','.join('?' * len(ch))})""", ch):
                    links[r.pop("cited_work_pk")] = r
        people = defaultdict(list)
        if _has_table(con, "citation_mention_people"):
            for r in _rows(con, "SELECT p.mention_pk, p.role, p.seq, p.printed, p.died FROM citation_mention_people p "
                                "JOIN citation_mentions m ON m.mention_pk = p.mention_pk WHERE m.version_id = ? "
                                "ORDER BY p.mention_pk, p.role, p.seq", (vid,)):
                people[r.pop("mention_pk")].append(r)
        citations = []
        for c in cits:
            anchor_pks.append(c["anchor_pk"])
            n = tc.get(c["cited_work_pk"], (0, 0))
            t = by_pk.get(c["full_mention_pk"]) if c["full_mention_pk"] and c["full_mention_pk"] != c["mention_pk"] \
                else None
            citations.append(dict(
                key=f"mention:{c['mention_id']}", mention_id=c["mention_id"], kind=c["kind"], marker=c["marker"],
                printed=c["printed"], page=c["page"], container_kind=c["container_kind"],
                container_id=c["container_id"], reading_ord=c["reading_ord"], cited_pages=c["cited_pages"],
                cited_volume=c["cited_volume"], script=_script(c["printed"]), anchor_pk=c["anchor_pk"],
                card=dict(work=f"work:{c['cited_work_id']}", id=c["cited_work_id"], title=c["card_title"],
                          pub_type=c["pub_type"], status=c["card_status"], n_citing_pubs=n[0], n_mentions=n[1])
                if c["cited_work_id"] else None,
                link=links.get(c["cited_work_pk"]),
                target=dict(key=f"mention:{t['mention_id']}", printed=t["printed"], page=t["page"]) if t else None,
                resolve=dict(method=c["resolve_method"], score=c["resolve_score"], by=c["resolved_by"],
                             unresolved_why=c["unresolved_why"]) if c["kind"] not in ("full", "quran", "hadith") else None,
                # v3.5b parts of the cited work, as printed (NULL when the reader gave none)
                parts={k: c[k] for k in V35_MENTION if c.get(k)} or None,
                year=(json.loads(c["parsed"]).get("year") if c["parsed"] else None),
                editors=[x["printed"] for x in people.get(c["mention_pk"], []) if x["role"] == "editor"],
                translators=[x["printed"] for x in people.get(c["mention_pk"], []) if x["role"] == "translator"],
                authors_died=[dict(name=x["printed"], died=x["died"]) for x in people.get(c["mention_pk"], [])
                              if x["role"] == "author" and x["died"]],
                edition_pk=c.get("edition_pk")))

        flags = _rows(con, "SELECT flag_id, kind, severity, page, block_id, reason, anchor_pk FROM flags "
                           "WHERE version_id = ? ORDER BY page, flag_id", (vid,))
        findings = _rows(con, """SELECT f.finding_pk, c.page, f.type, f.subtype, f.confidence, f.evidence, f.action,
                                        f.route, f.targets_raw, c.model, c.verdict, f.anchor_pk
                                 FROM judge_findings f JOIN judge_calls c ON c.call_id = f.call_id
                                 WHERE c.stem = ? ORDER BY c.page, f.k""", (stem,))
        corrections = _rows(con, "SELECT xml_id, layer, block_id, azure_reading, printed, proposed, applied_to_text, why, "
                                 "asserted_by, status, anchor_pk FROM text_corrections WHERE version_id = ? "
                                 "ORDER BY block_id, char_start", (vid,))
        for x in flags + findings + corrections:
            anchor_pks.append(x["anchor_pk"])
        anchors = _anchors(con, anchor_pks)

        def put(x):
            a = anchors.get(x.pop("anchor_pk", None))
            x["anchor"] = a["key"] if a else None
            return x
        for coll in (blocks, notes, citations, flags, findings, corrections, calls, page_marks):
            for x in coll:
                put(x)
        for fl in fnotes.values():
            for x in fl:
                put(x)
        for a in authors:
            for b in a["bylines"]:
                put(b)
                for f in b["affiliations"]:
                    put(f)
        for fl in meta.values():
            for r in fl:
                put(r)
        # incoming: other articles whose references were linked to this publication (Web of Science's "Times Cited";
        # the outgoing list is `references`, kept also as `citations` for older screens)
        # (experiment 73: each citing article carries its journal, so a citation from another journal shows)
        cited_by = _rows(con, """SELECT mw.stem, mw.citing_pub_id pub_id, p.title_shown title, p.year_shown year,
                                         count(*) n_mentions, p.journal_id,
                                         (SELECT t.title FROM journal_titles t WHERE t.journal_id = p.journal_id
                                          ORDER BY t.is_chosen DESC, (t.form = 'catalogue') DESC, t.n DESC
                                          LIMIT 1) journal
                                  FROM citation_links l JOIN v_mention_work mw ON mw.cited_work_pk = l.cited_work_pk
                                  LEFT JOIN publications p ON p.pub_id = mw.citing_pub_id
                                  WHERE l.target_pub_id = ? AND l.status = 'accepted' AND l.best = 1
                                    AND mw.citing_pub_id IS NOT ?
                                  GROUP BY 1, 2, 3, 4 ORDER BY 4, 1""", (pub_id, pub_id)) if pub_id else []
        # v3.5b: the document type (the page's and the catalogue's, and the one shown) and what the article is about
        def chosen(field):
            rs = meta.get(field) or []
            r = next((x for x in rs if x["is_chosen"]), rs[0] if rs else None)
            return r["value"] if r else None
        doc_type = dict(page=form("doc_type", "reader"), catalogue=form("doc_type", "catalogue"),
                        shown=pub["doc_type"] if pub and "doc_type" in pub.keys() else None,
                        shown_from=pub["doc_type_source"] if pub and "doc_type_source" in pub.keys() else None,
                        disagreement=_rows(con, "SELECT our_value, catalogue_value, severity, evidence, status FROM "
                                                "catalogue_reports WHERE pub_id = ? AND kind = 'document-type'",
                                           (pub_id,)) if pub_id else [])
        about = {}
        for f_ in sorted(meta):
            head = f_.split(".", 1)[0]
            if head in ABOUT and "." in f_:
                about.setdefault(head, {})[f_.split(".", 1)[1]] = chosen(f_)
            elif f_ == "series_part":
                about["series_part"] = {"part": chosen(f_)}
        return dict(
            subject=f"article:{stem}", stem=stem, pub_id=pub_id, read_from=str(path), cited_by=cited_by,
            doc_type=doc_type, about=about, page_marks=page_marks,
            references=citations,
            document=dict(level=doc["level"], part_kind=doc["part_kind"], scan_pages=doc["scan_pages"]),
            version=dict(version_id=vid, run=doc["run"], complete=doc["complete"], pages_covered=doc["pages_covered"],
                         pages_expected=doc["pages_expected"], current_reason=doc["current_reason"],
                         mirror=mirror_of(doc["run"], stem)),
            publication=dict(pub) if pub else None, catalogue=dict(cat) if cat else None, journal=journal, issue=issue,
            title=title, metadata=dict(meta), authors=authors, pages=pages, sections=sections, blocks=blocks,
            notes=notes, calls=calls, figures=figures, citations=citations, flags=flags, judge_findings=findings,
            corrections=corrections,
            counts=dict(blocks=len(blocks), notes=len(notes), citations=len(citations), references=len(citations),
                        cited_by=len(cited_by), figures=len(figures),
                        flags=len(flags), judge_findings=len(findings), corrections=len(corrections)))
    finally:
        con.close()


def article_keys(art: dict) -> tuple[list[str], list[str]]:
    """(the keys an article's decisions can sit on: its work cards and persons, its mention and byline key prefix)."""
    keys = {c["card"]["work"] for c in art["citations"] if c["card"]}
    keys |= {a["person"] for a in art["authors"] if a["person"]}
    keys.add(art["subject"])
    return sorted(keys), [f"mention:{art['stem']}|", f"byline:{art['stem']}|"]


# ------------------------------------------------------------------ a person
def person(path: Path, pid: str) -> dict | None:
    con = open_ro(path)
    try:
        R = Reading(con)
        rid, how = R.resolve_person(pid)
        if not rid:
            return None
        info = R.person_info(rid)
        info["resolved_from"] = None if how == "live" else pid
        info["subject"] = f"person:{rid}"
        info["authorities"] = _rows(con, "SELECT authority_id, heading, n_records, relation FROM person_authorities "
                                         "WHERE person_id = ? ORDER BY authority_id", (rid,))
        works = []
        for a in _rows(con, """SELECT a.authorship_pk, a.pub_id, a.position, a.role_code, rc.name_en role_name,
                                      a.method, a.score, a.asserted_by, p.title_shown, p.year_shown,
                                      (SELECT stem FROM documents d WHERE d.pub_id = a.pub_id LIMIT 1) stem,
                                      (SELECT title FROM journal_titles jt WHERE jt.journal_id = p.journal_id
                                       ORDER BY is_chosen DESC, n DESC LIMIT 1) journal
                               FROM authorships a LEFT JOIN publications p ON p.pub_id = a.pub_id
                               LEFT JOIN role_codes rc ON rc.code = a.role_code
                               WHERE a.person_id = ? ORDER BY p.year_shown, a.pub_id""", (rid,)):
            a["ref"] = R.authorship_ref(a["authorship_pk"])
            a["bylines"] = []
            for b in _rows(con, """SELECT b.printed, b.script, b.block_id, b.byline_pos, i.anchor_key, v.stem
                                   FROM authorship_mentions am JOIN byline_mentions b ON b.mention_pk = am.mention_pk
                                   JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1
                                   LEFT JOIN ink_anchors i ON i.anchor_pk = b.anchor_pk
                                   WHERE am.authorship_pk = ? ORDER BY b.byline_pos""", (a["authorship_pk"],)):
                k = b["anchor_key"] or f"{b['stem']}|{b['block_id'] or ''}|{b['byline_pos']}|{b['script'] or ''}"
                a["bylines"].append(dict(printed=b["printed"], script=b["script"], anchor=b["anchor_key"],
                                         key=f"byline:{k}"))
            a["affiliations"] = _rows(con, """
                SELECT DISTINCT f.printed, l.inst_id, (SELECT name FROM institution_names n WHERE n.inst_id = l.inst_id
                       ORDER BY (n.type = 'label') DESC, n.n_seen DESC LIMIT 1) inst_name
                FROM authorship_mentions am JOIN affiliation_mentions f ON f.mention_pk = am.mention_pk
                LEFT JOIN affiliation_links l ON l.aff_pk = f.aff_pk WHERE am.authorship_pk = ?""", (a["authorship_pk"],))
            works.append(a)
        info["works"] = works
        info.pop("authorships", None)
        info["coauthors"] = _rows(con, """
            SELECT b.person_id, coalesce(p.preferred_name_ar, p.preferred_name_lat) name, count(DISTINCT b.pub_id) n
            FROM authorships a JOIN authorships b ON b.pub_id = a.pub_id AND b.person_id <> a.person_id
            JOIN persons p ON p.person_id = b.person_id
            WHERE a.person_id = ? GROUP BY 1, 2 ORDER BY 3 DESC, 2 LIMIT 50""", (rid,))
        inst = Counter()
        names = {}
        for a in works:
            for f in a["affiliations"]:
                if f["inst_id"]:
                    inst[f["inst_id"]] += 1
                    names[f["inst_id"]] = f["inst_name"]
        info["institutions"] = [dict(inst_id=i, name=names[i], n=n) for i, n in inst.most_common()]
        tc = times_cited(path)
        cited = []
        for r in _rows(con, """SELECT DISTINCT w.cited_work_pk, w.cited_work_id, w.title, w.pub_type
                               FROM cited_work_authors ca JOIN cited_works w ON w.cited_work_pk = ca.cited_work_pk
                               WHERE ca.person_id = ? AND w.status = 'active'""", (rid,)):
            n = tc.get(r["cited_work_pk"], (0, 0))
            cited.append(dict(work=f"work:{r['cited_work_id']}", id=r["cited_work_id"], title=r["title"],
                              pub_type=r["pub_type"], n_citing_pubs=n[0], n_mentions=n[1]))
        cited.sort(key=lambda x: (-x["n_citing_pubs"], -x["n_mentions"]))
        info["cited_works"] = cited
        info["citations_received"] = dict(works=len(cited), citing_pubs=sum(c["n_citing_pubs"] for c in cited),
                                          mentions=sum(c["n_mentions"] for c in cited))
        info["merged_from"] = [r[0] for r in con.execute(
            "SELECT old_id FROM merged_ids WHERE new_id = ? AND relation = 'merged-into'", (rid,))]
        return info
    finally:
        con.close()


# ------------------------------------------------------------------ a cited-work card
def work(path: Path, cid: str) -> dict | None:
    con = open_ro(path)
    try:
        R = Reading(con)
        rid, how = R.resolve_work(cid)
        if not rid:
            return None
        c = R.card(rid)
        info = R.card_info(rid)
        info["resolved_from"] = None if how == "live" else cid
        info["subject"] = f"work:{rid}"
        info.update({k: c[k] for k in ("year_greg", "year_hijri", "edition_note", "place", "publisher", "lang", "method")})
        info["authors"] = _rows(con, """SELECT ca.seq, ca.printed, ca.person_id,
                                               coalesce(p.preferred_name_ar, p.preferred_name_lat) person_name,
                                               ca.authority_id, ca.match_method""" + _opt(
                                    con, "cited_work_authors", "ca", ("died", "died_hijri", "died_greg")) + """
                                        FROM cited_work_authors ca
                                        LEFT JOIN persons p ON p.person_id = ca.person_id
                                        WHERE ca.cited_work_pk = ? ORDER BY ca.seq""", (c["cited_work_pk"],))
        members = []
        for r in con.execute(CURRENT_MENTION + """ JOIN cited_work_members cm ON cm.full_mention_pk = m.mention_pk
                             WHERE cm.cited_work_pk = ? ORDER BY v.stem, m.reading_ord""", (c["cited_work_pk"],)):
            p = json.loads(r["parsed"]) if r["parsed"] else {}
            pub = con.execute("SELECT title_shown, year_shown FROM publications WHERE pub_id = ?", (r["pub_id"],)).fetchone()
            members.append(dict(key=f"mention:{r['mention_id']}", mention_id=r["mention_id"], stem=r["stem"],
                                page=r["page"], printed=r["printed"], anchor=r["anchor_key"], script=_script(r["printed"]),
                                authors=[" ".join(x for x in (a[1], a[0]) if x) for a in (p.get("authors") or [])],
                                article_title=pub[0] if pub else None, article_year=pub[1] if pub else None))
        info["members"] = members
        info.pop("member_rows", None)
        # v3.5b: the work's editions as its citations give them, and its editors / translators
        info["editions"] = _rows(con, """SELECT e.edition_pk, e.edition_printed, e.year_printed, e.year_calendar, e.year2,
                                                e.publisher, e.place, e.n_members FROM cited_work_editions e
                                         WHERE e.cited_work_pk = ? ORDER BY e.year_printed, e.edition_key""",
                                   (c["cited_work_pk"],)) if _has_table(con, "cited_work_editions") else []
        if info["editions"]:
            ed_of = {r[0]: r[1] for r in con.execute(
                "SELECT m.mention_id, cm.edition_pk FROM cited_work_members cm JOIN citation_mentions m ON "
                "m.mention_pk = cm.full_mention_pk WHERE cm.cited_work_pk = ?", (c["cited_work_pk"],))}
            for m in members:
                m["edition_pk"] = ed_of.get(m["mention_id"])
        info["contributors"] = _rows(con, """SELECT role, seq, printed, edition_pk, n_mentions FROM cited_work_contributors
                                             WHERE cited_work_pk = ? ORDER BY role, seq""", (c["cited_work_pk"],)) \
            if _has_table(con, "cited_work_contributors") else []
        info["citing"] = _rows(con, """SELECT mw.stem, mw.citing_pub_id pub_id, p.title_shown title, p.year_shown year,
                                              count(*) n_mentions, sum(mw.kind = 'full') n_full
                                       FROM v_mention_work mw LEFT JOIN publications p ON p.pub_id = mw.citing_pub_id
                                       WHERE mw.cited_work_pk = ? GROUP BY 1, 2, 3, 4 ORDER BY 4, 1""",
                               (c["cited_work_pk"],))
        info["links"] = _rows(con, """SELECT l.target_kind, l.target_pub_id, l.target_scheme, l.target_value, l.status,
                                             l.best, l.score, l.method, l.asserted_by, p.title_shown title, p.year_shown year,
                                             (SELECT stem FROM documents d WHERE d.pub_id = l.target_pub_id LIMIT 1) stem
                                      FROM citation_links l LEFT JOIN publications p ON p.pub_id = l.target_pub_id
                                      WHERE l.cited_work_pk = ? ORDER BY l.best DESC, l.score DESC""",
                              (c["cited_work_pk"],))
        info["relations"] = _rows(con, """SELECT r.relation, r.inverse, r.object_pub_id, p.title_shown object_title,
                                                 (SELECT stem FROM documents d WHERE d.pub_id = r.object_pub_id LIMIT 1)
                                                 object_stem, w.cited_work_id object_work, w.title object_work_title,
                                                 r.score, r.method, r.asserted_by
                                          FROM work_relations r LEFT JOIN publications p ON p.pub_id = r.object_pub_id
                                          LEFT JOIN cited_works w ON w.cited_work_pk = r.object_cited_work_pk
                                          WHERE r.subject_cited_work_pk = ?
                                          UNION ALL
                                          SELECT r.inverse, r.relation, NULL, NULL, NULL, w.cited_work_id, w.title,
                                                 r.score, r.method, r.asserted_by
                                          FROM work_relations r JOIN cited_works w
                                          ON w.cited_work_pk = r.subject_cited_work_pk
                                          WHERE r.object_cited_work_pk = ?""",
                                  (c["cited_work_pk"], c["cited_work_pk"]))
        # experiment 67: the reverse side too (a collective book shows the chapters it holds, D42)
        info["merged_from"] = [r[0] for r in con.execute(
            "SELECT old_id FROM merged_ids WHERE new_id = ? AND relation = 'merged-into'", (rid,))]
        return info
    finally:
        con.close()


# ------------------------------------------------------------------ a release's summary, for before/after
def summary_dir() -> Path:
    return db.releases_dir() / "summaries"


def summarize(path: Path, label: str, top_n: int = 100) -> dict:
    """What the before/after view compares: the top-cited list, which card each full citation sits on, and the
    persons. Small (a few hundred kB); written next to the release copies so it outlives a pruned copy."""
    out = summary_dir() / f"{label}.json"
    if out.exists():
        try:
            s = json.loads(out.read_text(encoding="utf-8"))
            if s.get("mtime") == os.path.getmtime(path) or label.startswith("R"):
                return s
        except (ValueError, OSError):
            pass
    t0 = time.time()
    con = open_ro(path)
    try:
        members = {r[0]: r[1] for r in con.execute(
            """SELECT m.mention_id, w.cited_work_id FROM cited_work_members cm
               JOIN cited_works w ON w.cited_work_pk = cm.cited_work_pk AND w.status = 'active'
               JOIN citation_mentions m ON m.mention_pk = cm.full_mention_pk
               JOIN versions v ON v.version_id = m.version_id AND v.is_current = 1""")}
        tc = times_cited(path)
        cards = {r[1]: [r[2], *tc.get(r[0], (0, 0))] for r in con.execute(
            "SELECT cited_work_pk, cited_work_id, title FROM cited_works WHERE status = 'active'")}
        persons = {r[0]: [r[1], r[2] or r[3]] for r in con.execute(
            "SELECT person_id, status, preferred_name_ar, preferred_name_lat FROM persons")}
        merged = {r[0]: r[1] for r in con.execute(
            "SELECT old_id, new_id FROM merged_ids WHERE relation = 'merged-into' AND kind = 'person'")}
        aship = {str(r[0]): r[1] for r in con.execute(
            "SELECT authorship_pk, person_id FROM authorships WHERE person_id IS NOT NULL")}
    finally:
        con.close()
    s = dict(label=label, path=str(path), mtime=os.path.getmtime(path), made=time.strftime("%Y-%m-%d %H:%M:%S"),
             top=top_works(path, top_n), members=members, cards=cards, persons=persons, person_merged=merged,
             authorships=aship, seconds=round(time.time() - t0, 1))
    summary_dir().mkdir(parents=True, exist_ok=True)
    tmp = out.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(s, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp, out)
    return s


def load_summary(label: str) -> dict | None:
    p = summary_dir() / f"{label}.json"
    if not p.exists():
        return None
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return None


def diff(a: dict, b: dict, top_n: int = 30) -> dict:
    """Before (a) and after (b): the top-cited list in both, cards split, merged or changed, persons merged."""
    ta = {w["id"]: w for w in a["top"]}
    tb = {w["id"]: w for w in b["top"]}
    top = []
    for w in b["top"][:top_n]:
        o = ta.get(w["id"])
        top.append(dict(id=w["id"], title=w["title"], rank_after=w["rank"], n_after=w["n_citing_pubs"],
                        m_after=w["n_mentions"], rank_before=o["rank"] if o else None,
                        n_before=o["n_citing_pubs"] if o else (a["cards"].get(w["id"]) or [None, None])[1]))
    dropped = [dict(id=w["id"], title=w["title"], rank_before=w["rank"], n_before=w["n_citing_pubs"],
                    rank_after=tb[w["id"]]["rank"] if w["id"] in tb else None,
                    n_after=(b["cards"].get(w["id"]) or [None, None])[1])
               for w in a["top"][:top_n] if w["id"] not in {x["id"] for x in b["top"][:top_n]}]
    # cards: where did each card's full citations go?
    ma, mb = a["members"], b["members"]
    fwd = defaultdict(Counter)
    back = defaultdict(Counter)
    for m, ca in ma.items():
        cb = mb.get(m)
        fwd[ca][cb] += 1
        if cb:
            back[cb][ca] += 1
    for m, cb in mb.items():
        if m not in ma:
            back[cb][None] += 1
    changed = []
    for ca, dest in fwd.items():
        dest = Counter({d: n for d, n in dest.items() if d})
        if not dest:
            continue
        only = next(iter(dest)) if len(dest) == 1 else None
        if len(dest) > 1:
            kind = "split" if any(d not in a["cards"] for d in dest) else "members moved"
        elif only != ca and len([s for s in back[only] if s]) == 1:
            kind = "renamed"
        else:
            continue
        changed.append(dict(kind=kind, card=ca, title=(a["cards"].get(ca) or [None])[0],
                            n_before=(a["cards"].get(ca) or [None, None])[1],
                            to=[dict(card=d, title=(b["cards"].get(d) or [None])[0], members=n,
                                     n_after=(b["cards"].get(d) or [None, None])[1])
                                for d, n in dest.most_common()]))
    for cb, src in back.items():
        real = [s for s in src if s]
        if len(real) > 1:
            changed.append(dict(kind="merged", card=cb, title=(b["cards"].get(cb) or [None])[0],
                                n_after=(b["cards"].get(cb) or [None, None])[1],
                                frm=[dict(card=s, title=(a["cards"].get(s) or [None])[0], members=n,
                                          n_before=(a["cards"].get(s) or [None, None])[1])
                                     for s, n in src.most_common() if s]))
    pa, pb = a["persons"], b["persons"]
    persons = []
    for pid, (st, name) in pb.items():
        before = pa.get(pid)
        if st == "merged" and (not before or before[0] != "merged"):
            to = b["person_merged"].get(pid)
            persons.append(dict(kind="merged", person=pid, name=name, into=to, into_name=(pb.get(to) or [None, None])[1]))
        elif not before:
            persons.append(dict(kind="new", person=pid, name=name))
    moved = []
    for apk, p_b in b["authorships"].items():
        p_a = a["authorships"].get(apk)
        if p_a and p_a != p_b and not any(x["person"] == p_a and x["kind"] == "merged" for x in persons):
            moved.append(dict(authorship=apk, before=p_a, before_name=(pa.get(p_a) or [None, None])[1], after=p_b,
                              after_name=(pb.get(p_b) or [None, None])[1]))
    joined = sum(1 for k in a["authorships"] if k not in b["authorships"])
    tbr = []
    for w in a["top"][:top_n]:
        o = tb.get(w["id"])
        tbr.append(dict(id=w["id"], title=w["title"], rank_before=w["rank"], n_before=w["n_citing_pubs"],
                        m_before=w["n_mentions"], rank_after=o["rank"] if o else None,
                        n_after=o["n_citing_pubs"] if o else (b["cards"].get(w["id"]) or [None, None])[1]))
    return dict(before=a["label"], after=b["label"], top=top, top_before=tbr, left_top=dropped, cards=changed,
                persons=persons, bylines_moved=moved, authorships_joined=joined,
                counts=dict(cards_before=len(a["cards"]), cards_after=len(b["cards"]),
                            persons_before=sum(1 for v in pa.values() if v[0] != "merged"),
                            persons_after=sum(1 for v in pb.values() if v[0] != "merged")))
