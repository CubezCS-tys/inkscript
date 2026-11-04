"""Experiment 62, step 1a: the librarian's card catalogue as the machine leaves it (read-only on the release).

One record per active cited-work card of the 780 shown articles, with everything a person would look at:
- the card (id, title, title key, type, language, year, authors with death dates, editions, editors/translators);
- its members: each full citation (or the short form standing alone) with the printed span, the parsed parts,
  the article (stem, journal, year), where it sits (note / reference list, page, the note's text) and its ink
  anchor (for the crop);
- how often it is cited (articles, mentions incl. back references) and the machine's links to Mandumah
  (citation_links) and relations (work_relations).

Output: out/cards62.jsonl, out/articles62.json (stem -> journal, year, title, pub_id, c999).

    python3 experiments/62_librarian_works/build62.py [--db RELEASE]
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
RELEASES = Path.home() / "data/desk/releases"


def newest_release() -> Path:
    """The release this pass was made on (pinned: R20261023T005909, override with LIBRARIAN62_RELEASE)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from norm62 import release
    return release()


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default=None)
    a = ap.parse_args(argv)
    db = Path(a.db) if a.db else newest_release()
    con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    OUT.mkdir(exist_ok=True)

    jname = {}
    for r in con.execute("SELECT journal_id, title FROM journal_titles ORDER BY is_chosen DESC, n DESC"):
        jname.setdefault(r[0], r[1])
    arts = {}
    for r in con.execute("""SELECT v.version_id, v.stem, v.run, d.pub_id, p.c999, p.journal_id, p.year_shown, p.title_shown
                            FROM versions v JOIN documents d ON d.stem = v.stem LEFT JOIN publications p ON p.pub_id = d.pub_id
                            WHERE v.is_current = 1"""):
        arts[r["stem"]] = dict(version_id=r["version_id"], run=r["run"], pub_id=r["pub_id"], c999=r["c999"],
                               journal_id=r["journal_id"], journal=jname.get(r["journal_id"]), year=r["year_shown"],
                               title=r["title_shown"])
    vid2stem = {v["version_id"]: s for s, v in arts.items()}
    notes = {}
    for r in con.execute("SELECT version_id, note_id, text, label FROM notes"):
        if r[0] in vid2stem:
            notes[(r[0], r[1])] = (r[2] or "")[:600]

    cards = {}
    for r in con.execute("SELECT * FROM cited_works WHERE status = 'active'"):
        cards[r["cited_work_pk"]] = dict(r) | dict(authors=[], members=[], editions=[], contributors=[], links=[],
                                                  relations=[])
    for r in con.execute("SELECT * FROM cited_work_authors ORDER BY cited_work_pk, seq"):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["authors"].append(dict(printed=r["printed"], name_key=r["name_key"],
                                                             latin=r["latin"], died=r["died"], died_hijri=r["died_hijri"],
                                                             person_id=r["person_id"]))
    for r in con.execute("SELECT * FROM cited_work_editions"):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["editions"].append(dict(edition_pk=r["edition_pk"], key=r["edition_key"],
                                                              printed=r["edition_printed"], year=r["year_printed"],
                                                              publisher=r["publisher"], place=r["place"], n=r["n_members"]))
    for r in con.execute("SELECT * FROM cited_work_contributors"):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["contributors"].append(dict(role=r["role"], printed=r["printed"], n=r["n_mentions"]))
    for r in con.execute("""SELECT l.cited_work_pk, l.status, l.best, l.score, l.method, l.target_pub_id, p.c999,
                                   p.title_shown, p.journal_id, p.year_shown FROM citation_links l
                            LEFT JOIN publications p ON p.pub_id = l.target_pub_id"""):
        if r["cited_work_pk"] in cards:
            cards[r["cited_work_pk"]]["links"].append(dict(status=r["status"], best=r["best"], score=r["score"],
                                                           method=r["method"], pub_id=r["target_pub_id"], c999=r["c999"],
                                                           title=r["title_shown"], journal_id=r["journal_id"],
                                                           year=r["year_shown"]))
    for r in con.execute("""SELECT w.subject_cited_work_pk, w.relation, w.object_pub_id, p.title_shown, w.method
                            FROM work_relations w LEFT JOIN publications p ON p.pub_id = w.object_pub_id"""):
        if r[0] in cards:
            cards[r[0]]["relations"].append(dict(relation=r[1], pub_id=r[2], title=r[3], method=r[4]))
    # times cited: every mention (back references through their full citation), by article
    tc_art, tc_ment, tc_back = defaultdict(set), Counter(), Counter()
    for r in con.execute("SELECT version_id, stem, kind, cited_work_pk FROM v_mention_work WHERE cited_work_pk IS NOT NULL"):
        tc_art[r[3]].add(r[1])
        tc_ment[r[3]] += 1
        tc_back[r[3]] += r[2] != "full"
    for r in con.execute("""SELECT m.cited_work_pk, m.method AS mmethod, m.edition_pk, c.*, a.anchor_key
                            FROM cited_work_members m JOIN citation_mentions c ON c.mention_pk = m.full_mention_pk
                            LEFT JOIN ink_anchors a ON a.anchor_pk = c.anchor_pk ORDER BY c.mention_id"""):
        if r["cited_work_pk"] not in cards or r["version_id"] not in vid2stem:
            continue
        stem = vid2stem[r["version_id"]]
        cards[r["cited_work_pk"]]["members"].append(dict(
            mention_pk=r["mention_pk"], mention_id=r["mention_id"], stem=stem, kind=r["kind"], method=r["mmethod"],
            container=r["container_kind"], container_id=r["container_id"], page=r["page"], printed=r["printed"],
            printed_fixed=r["printed_fixed"], parsed=json.loads(r["parsed"]) if r["parsed"] else None,
            cited_volume=r["cited_volume"], cited_pages=r["cited_pages"], edition=r["edition"], died=r["died"],
            year2=r["year2"], thesis_degree=r["thesis_degree"], anchor=r["anchor_key"], edition_pk=r["edition_pk"],
            note=notes.get((r["version_id"], r["container_id"])) if r["container_kind"] == "note" else None))
    n = 0
    with open(OUT / "cards62.jsonl", "w", encoding="utf-8") as f:
        for pk, c in sorted(cards.items(), key=lambda kv: kv[1]["cited_work_id"]):
            c["n_articles"] = len(tc_art.get(pk, ()))
            c["stems"] = sorted(tc_art.get(pk, ()))
            c["n_mentions"] = tc_ment.get(pk, 0)
            c["n_backrefs"] = tc_back.get(pk, 0)
            c["short_only"] = bool(c["members"]) and all(m["kind"] != "full" for m in c["members"])
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
            n += 1
    (OUT / "articles62.json").write_text(json.dumps(arts, ensure_ascii=False, indent=0), encoding="utf-8")
    print(dict(cards=n, members=sum(len(c["members"]) for c in cards.values()),
               short_only=sum(1 for c in cards.values() if c["members"] and all(m["kind"] != "full" for m in c["members"])),
               shared_2plus=sum(1 for pk in cards if len(tc_art.get(pk, ())) >= 2), db=str(db)))


if __name__ == "__main__":
    sys.exit(main())
