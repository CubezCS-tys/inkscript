"""The index pages (2026-10-23): h-index on known cases, and every headline number checked against an independent
SQL query (platform v2's own views) on the machine's reading, opened read-only. Then the routes, with a token, in a
throwaway schema as the P2 tests."""
from __future__ import annotations

import hashlib
import sqlite3

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor
from desk import db
from desk import index_pages as X

PATH = db.reading_path()
J = "J0130"
PERSON = "A8STQEWEAV"           # الغالي أحرشاو: 8 articles in the journal, much self-cited


def test_h_index_known_cases():
    assert X.h_index([]) == 0
    assert X.h_index([0, 0]) == 0
    assert X.h_index([1]) == 1
    assert X.h_index([10, 8, 5, 4, 3]) == 4          # Hirsch's own kind of example
    assert X.h_index([25, 8, 5, 3, 3]) == 3
    assert X.h_index([2, 2, 1, 1, 1]) == 2
    assert X.h_index([100]) == 1
    assert X.h_index([3, 3, 3]) == 3
    assert X.h_index([4, 4, 4]) == 3


@pytest.fixture(scope="module")
def sq():
    c = sqlite3.connect(f"file:{PATH}?mode=ro", uri=True)
    yield c
    c.close()


def test_overview_numbers_match_sql(sq):
    o = {m["key"]: m for m in X.overview(PATH)["numbers"]}
    assert o["articles"]["value"] == sq.execute("SELECT count(*) FROM documents").fetchone()[0]
    assert o["pages"]["value"] == sq.execute("SELECT count(*) FROM pages").fetchone()[0]
    refs = sq.execute("SELECT count(*) FROM v_mention_work").fetchone()[0]
    assert o["references"]["value"] == refs
    held = sq.execute("""SELECT count(*) FROM v_mention_work mw JOIN citation_links l ON l.cited_work_pk = mw.cited_work_pk
                         AND l.status = 'accepted' AND l.best = 1 AND l.target_kind = 'publication'""").fetchone()[0]
    assert o["held"]["value"] == round(100 * held / refs, 1)
    assert o["authors"]["value"] == sq.execute("""SELECT count(DISTINCT a.person_id) FROM authorships a
        JOIN documents d ON d.pub_id = a.pub_id WHERE a.person_id IS NOT NULL""").fetchone()[0]
    assert o["journals"]["value"] == sq.execute("""SELECT count(DISTINCT p.journal_id) FROM documents d
        JOIN publications p ON p.pub_id = d.pub_id""").fetchone()[0]
    assert o["cited_works"]["value"] == sq.execute("SELECT count(*) FROM v_times_cited").fetchone()[0]
    assert o["article_links"]["value"] == sq.execute("""SELECT count(*) FROM v_mention_work mw JOIN citation_links l
        ON l.cited_work_pk = mw.cited_work_pk AND l.status = 'accepted' AND l.best = 1
        JOIN documents d ON d.pub_id = l.target_pub_id""").fetchone()[0]
    assert o["institutions"]["value"] == sq.execute("""SELECT count(DISTINCT l.inst_id) FROM affiliation_links l
        JOIN affiliation_mentions am ON am.aff_pk = l.aff_pk JOIN byline_mentions b ON b.mention_pk = am.mention_pk
        JOIN versions v ON v.version_id = b.version_id AND v.is_current = 1 WHERE l.level = 'org'""").fetchone()[0]


def test_journal_record_matches_sql(sq):
    j = X.journal(PATH, J)
    c = j["counts"]
    tcs = [r[0] for r in sq.execute("""SELECT t.n_citing_pubs FROM v_pub_times_cited t
                                      JOIN publications p ON p.pub_id = t.pub_id WHERE p.journal_id = ?""", (J,))]
    assert c["times_cited"] == sum(tcs) and c["cited_pubs"] == len(tcs)
    assert c["h_index"] == X.h_index(tcs)
    pairs = {(r[0], r[1]): (r[2], r[3]) for r in sq.execute(
        "SELECT citing_journal, cited_journal, n_citing_pubs, n_mentions FROM v_journal_citation_pairs")}
    assert (c["inside_citing"], c["inside_refs"]) == pairs.get((J, J), (0, 0))
    assert c["outside_refs"] == sum(v[1] for (a, b), v in pairs.items() if b == J and a != J)
    assert c["read"] == sq.execute("""SELECT count(*) FROM documents d JOIN publications p ON p.pub_id = d.pub_id
                                     WHERE p.journal_id = ?""", (J,)).fetchone()[0]
    refs = sq.execute("""SELECT count(*) FROM v_mention_work mw JOIN publications p ON p.pub_id = mw.citing_pub_id
                         WHERE p.journal_id = ?""", (J,)).fetchone()[0]
    assert c["references"] == refs
    assert sum(a["references"] for a in j["articles"]) == refs
    assert sum(r["times_cited"] for r in j["received"]) == c["times_cited"]


def test_person_record_matches_sql(sq):
    p = X.person_record(PATH, PERSON)
    c = p["counts"]
    # every citing article of the person's cited works (author matched) and of the publications they signed
    citing = {r[0] for r in sq.execute("""SELECT mw.citing_pub_id FROM v_mention_work mw JOIN cited_work_authors ca
        ON ca.cited_work_pk = mw.cited_work_pk WHERE ca.person_id = ?""", (PERSON,))}
    citing |= {r[0] for r in sq.execute("""SELECT mw.citing_pub_id FROM v_mention_work mw JOIN citation_links l
        ON l.cited_work_pk = mw.cited_work_pk AND l.status = 'accepted' AND l.best = 1
        JOIN authorships a ON a.pub_id = l.target_pub_id WHERE a.person_id = ?""", (PERSON,))}
    assert c["citing_articles"] == len(citing)
    own = {r[0] for r in sq.execute("SELECT pub_id FROM authorships WHERE person_id = ?", (PERSON,))}
    assert c["citing_articles_no_self"] == len(citing - own)
    assert c["h_index"] == X.h_index(i["times_cited"] for i in p["items"])
    assert c["times_cited"] >= c["times_cited_no_self"] >= 0
    assert c["articles_read"] == sq.execute("""SELECT count(DISTINCT a.pub_id) FROM authorships a
        JOIN documents d ON d.pub_id = a.pub_id WHERE a.person_id = ?""", (PERSON,)).fetchone()[0]


def test_most_cited_and_institution(sq):
    m = X.most_cited(PATH, "works", 5)
    top = sq.execute("SELECT max(n_citing_pubs) FROM v_times_cited").fetchone()[0]
    assert m["items"][0]["times_cited"] == top
    pubs = X.most_cited(PATH, "pubs", 3)
    assert pubs["total"] == sq.execute("SELECT count(*) FROM v_pub_times_cited").fetchone()[0]
    assert pubs["items"][0]["times_cited"] == sq.execute("SELECT max(n_citing_pubs) FROM v_pub_times_cited").fetchone()[0]
    top_inst = X.institutions(PATH, 1)[0]
    i = X.institution(PATH, top_inst["inst_id"])
    assert i["counts"]["articles"] >= top_inst["articles"]
    assert i["counts"]["h_index"] == X.h_index(a["times_cited"] for a in i["articles"])


TOK = "tok-index-reader"


@pytest.fixture(scope="module")
def client(pg, test_dir):
    add_actor(pg, "person:index-reader", "corrector")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOK.encode()).hexdigest(), "person:index-reader"))
    pg.commit()
    from desk.api import app
    return TestClient(app)


def test_index_routes(client):
    h = {"X-Desk-Token": TOK}
    assert client.get("/desk/api/index/overview").status_code == 401
    o = client.get("/desk/api/index/overview", headers=h).json()
    assert {m["key"] for m in o["numbers"]} >= {"articles", "references", "held", "article_links"}
    assert all(m["define"] for m in o["numbers"])
    j = client.get(f"/desk/api/index/journals/{J}", headers=h).json()
    assert j["is_gate1"] and j["counts"]["read"] > 0
    assert client.get("/desk/api/index/journals/x;drop", headers=h).status_code in (404, 422)
    assert client.get("/desk/api/index/journals/J9999999", headers=h).status_code == 404
    assert client.get(f"/desk/api/index/persons/{PERSON}", headers=h).json()["counts"]["h_index"] >= 1
    assert client.get("/desk/api/index/most-cited?kind=pubs&limit=2", headers=h).status_code == 200
    g = client.get("/desk/api/index/gate1", headers=h).json()
    rows = {r["key"]: r for r in g["rows"]}
    assert rows["authors2"]["journal"]["n"] > rows["authors2"]["random_same_size"]
    assert g["draws"] == 20
