"""Experiment 68: an affiliation printed again in the other script (experiment 65's twin rows).

Before experiment 65 an English line under an Arabic name was the name's own row ('stem|b0|Arab|a2'); since then it
hangs on the twin's mention (twin_of_aff_pk -> the Arabic line). A decision made on the old key still applies (found
again by its recorded printed text); a twin row no decision names takes its main line's decided bodies; counts skip
twin rows."""
from __future__ import annotations

import json
import sqlite3
import uuid

import pytest
from psycopg.types.json import Jsonb

from conftest import add_actor
from desk import db, release
from desk.reading import Reading

LIB = "agent:librarian-twins"
CAIRO, ALEX, STRAY = "IC0000CAIR", "IA0000ALEX", "IS0000STRY"
EN1 = "Faculty of Arts, Cairo University, Egypt"
EN2 = "Faculty of Arts, University of Alexandria"


@pytest.fixture(scope="module")
def reading(test_dir):
    p = test_dir / "twins_reading.db"
    src = sqlite3.connect(f"file:{db.reading_path()}?mode=ro", uri=True)
    con = sqlite3.connect(p)
    for (sql,) in src.execute("""SELECT sql FROM sqlite_master WHERE sql IS NOT NULL AND name NOT LIKE 'search_fts%'
                                 ORDER BY CASE type WHEN 'table' THEN 0 WHEN 'index' THEN 1 ELSE 2 END, rowid"""):
        con.execute(sql)
    src.close()
    cols = {r[1] for r in con.execute("PRAGMA table_info(affiliation_mentions)")}
    for c, t in (("lang", "TEXT"), ("twin_of_aff_pk", "INTEGER")):        # a reading from before experiment 65
        if c not in cols:
            con.execute(f"ALTER TABLE affiliation_mentions ADD COLUMN {c} {t}")
    x = con.execute
    for i, stem in enumerate(["T-001-001", "T-002-002"], 1):
        x("INSERT INTO publications (pub_id, status, journal_id) VALUES (?, 'shown', 'J1')", (f"W{i}",))
        x("INSERT INTO documents (stem, level, pub_id) VALUES (?, 'final', ?)", (stem, f"W{i}"))
        x("INSERT INTO versions (version_id, version_key, stem, run, content_in_db, is_current) VALUES (?,?,?,?,1,1)",
          (i, f"{stem}|r", stem, "r"))
    for iid, name in ((CAIRO, "جامعة القاهرة"), (ALEX, "جامعة الإسكندرية"), (STRAY, "Faculty of Arts")):
        x("INSERT INTO institutions (inst_id, kind, country_code, status, source) VALUES (?, 'university', NULL, "
          "'active', 'masters')", (iid,))
        x("INSERT INTO institution_names (inst_id, name, script, type, n_seen, source) VALUES (?, ?, 'Arab', "
          "'printed', 1, 'masters')", (iid, name))
    # article 1: the Arabic line + its English twin (on the twin's mention); article 2 the same, Alexandria
    for v, (ar, en, body) in enumerate([("كلية الآداب جامعة القاهرة", EN1, CAIRO),
                                        ("كلية الآداب جامعة الإسكندرية", EN2, ALEX)], 1):
        m, t = 10 * v, 10 * v + 1
        x("INSERT INTO byline_mentions (mention_pk, version_id, byline_pos, script, printed) VALUES (?, ?, 0, 'Arab', "
          "'م')", (m, v))
        x("INSERT INTO byline_mentions (mention_pk, version_id, byline_pos, script, printed, twin_of_pk) VALUES "
          "(?, ?, 0, 'Latn', 'M', ?)", (t, v, m))
        x("INSERT INTO affiliation_mentions (aff_pk, mention_pk, seq, printed) VALUES (?, ?, 1, ?)", (100 * v, m, ar))
        x("INSERT INTO affiliation_mentions (aff_pk, mention_pk, seq, printed, lang, twin_of_aff_pk) VALUES "
          "(?, ?, 1, ?, 'en', ?)", (100 * v + 1, t, en, 100 * v))
        x("INSERT INTO affiliation_links (aff_pk, inst_id, level, method, asserted_by) VALUES (?, ?, 'org', 'inst46', "
          "'link47')", (100 * v, body))
        x("INSERT INTO affiliation_links (aff_pk, inst_id, level, method, asserted_by) VALUES (?, ?, 'org', 'inst46', "
          "'link47')", (100 * v + 1, STRAY))          # the machine linked the English line to a stray row
    con.commit()
    con.close()
    return p


def raw_decision(pg, op, keys, payload, evidence):
    """A decision as an earlier reading accepted it (its key may be gone from this one)."""
    pg.execute("""INSERT INTO decisions (decision_id, domain, op, subject_keys, payload, evidence, actor_id, status,
                  review_policy_at_time, confidence) VALUES (%s, 'identity', %s, %s, %s, %s, %s, 'accepted', 'none',
                  'sure')""", (str(uuid.uuid4()), op, keys, Jsonb(payload), Jsonb(evidence), LIB))


def test_old_key_and_twin_inheritance(pg, reading, test_dir):
    add_actor(pg, LIB)
    link = lambda iid: dict(institutions=[dict(inst=f"inst:{iid}", role="current", country=None)])  # noqa: E731
    # article 1: the English line decided under its pre-experiment-65 key (the Arabic name's a2), the Arabic too
    raw_decision(pg, "link_affiliation", ["aff:T-001-001|b0|Arab|a2", f"inst:{CAIRO}"], link(CAIRO), dict(printed=EN1))
    raw_decision(pg, "link_affiliation", ["aff:T-001-001|b0|Arab|a1", f"inst:{CAIRO}"], link(CAIRO),
                 dict(printed="كلية الآداب جامعة القاهرة"))
    # article 2: only the Arabic line decided
    raw_decision(pg, "link_affiliation", ["aff:T-002-002|b0|Arab|a1", f"inst:{ALEX}"], link(ALEX),
                 dict(printed="كلية الآداب جامعة الإسكندرية"))
    # an old key whose printed text matches nothing stays an orphan (never a guess)
    raw_decision(pg, "not_an_institution", ["aff:T-002-002|b0|Arab|a2"], {}, dict(printed="something else"))
    pg.commit()
    rel = release.build_release(pg, reading, test_dir / "twins_releases", keep=5)
    assert rel["n_orphaned"] == 1 and rel["n_conflict"] == 0
    assert rel["checks"]["decisions_hold"]
    S = Reading(sqlite3.connect(f"file:{rel['path']}?mode=ro", uri=True))
    links = lambda pk: {(r["inst_id"], r["level"], r["asserted_by"]) for r in S.aff_links(pk)}  # noqa: E731
    assert links(101) == {(CAIRO, "org", "person")}          # the old key found its twin row by its printed text
    assert links(201) == {(ALEX, "org", "person")}           # inherited from its Arabic line; the stray link gone
    assert json.loads(S.q1("SELECT evidence FROM affiliation_links WHERE aff_pk = 201")[0])["twin_of_aff_pk"] == 200
    c = rel["counts_after"]
    assert c["affiliations_linked_org"] == 2 and c["institutions_linked_org"] == 2      # twins not counted
