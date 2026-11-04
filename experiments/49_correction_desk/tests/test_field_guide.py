"""The field guide (/how-we-collect): every Explorer column of a tab whose guide file exists is documented (so a new
column cannot go undocumented), each entry is well formed, and reviews are stored append-only in PostgreSQL."""
from __future__ import annotations

import hashlib

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

ACTOR, TOK = "person:guide-tester", "tok-guide-tester"
H = {"X-Desk-Token": TOK}
B = "/desk/api/field-guide"
KEYS = {"tab", "key", "label", "group", "meaning", "source", "how", "exact", "examples", "fill", "caveats", "label_check"}


@pytest.fixture(scope="module")
def guide_mod():
    import desk.api  # noqa: F401  (field_guide imports from the api module)
    from desk import field_guide
    return field_guide


def test_every_explorer_column_of_a_written_tab_has_an_entry(guide_mod):
    from desk import explore as X
    written = 0
    for tab, e in X.ENTITIES.items():
        entries = guide_mod.load_tab(tab)
        if entries is None:
            continue
        written += 1
        keys = [r["key"] for r in entries]
        cols = [c["name"] for c in e["cols"]]
        missing = [c for c in cols if c not in keys]
        assert not missing, f"{tab}: Explorer columns with no field-guide entry: {missing}"
        assert not set(keys) - set(cols), f"{tab}: entries for columns the Explorer no longer has: {set(keys) - set(cols)}"
        assert len(keys) == len(set(keys)), f"{tab}: duplicate entries"
    assert guide_mod.load_tab("articles") is not None and written >= 1


def test_entries_are_well_formed(guide_mod):
    from desk import explore as X
    for tab in X.ENTITIES:
        for r in guide_mod.load_tab(tab) or []:
            where = f"{tab}.{r.get('key')}"
            assert KEYS <= set(r), f"{where}: missing {KEYS - set(r)}"
            assert r["tab"] == tab, where
            assert r["source"] in guide_mod.SOURCES, f"{where}: source {r['source']!r}"
            assert r["meaning"].strip() and r["how"] and r["exact"], where
            assert isinstance(r["label_check"].get("ok"), bool) and r["label_check"].get("why"), where
            assert isinstance(r["examples"], list) and isinstance(r["caveats"], list), where


@pytest.fixture(scope="module")
def client(pg):
    add_actor(pg, ACTOR, "corrector")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOK.encode()).hexdigest(), ACTOR))
    pg.commit()
    from desk.api import app
    return TestClient(app)


def test_guide_lists_every_column_with_counts(client):
    assert client.get(B).status_code == 401
    d = client.get(B, headers=H).json()
    from desk import explore as X
    assert [t["tab"] for t in d["tabs"]] == list(X.ENTITIES)
    assert d["n_columns"] == sum(len(e["cols"]) for e in X.ENTITIES.values())
    arts = next(t for t in d["tabs"] if t["tab"] == "articles")
    assert arts["written"] and arts["n_entries"] == arts["n_columns"] == len(X.ARTICLES)
    assert sum(d["counts"].values()) == d["n_columns"]


def test_reviews_are_stored_shown_and_append_only(client, pg):
    fk = "articles.n_institutions"
    r = client.post(B + "/reviews", headers=H, json=dict(field_key=fk, verdict="wrong_label", comment="institutes",
                                                         proposed_label="Top-level institutions linked (n)"))
    assert r.status_code == 200, r.text
    assert r.json()["author"] == ACTOR
    r2 = client.post(B + "/reviews", headers=H, json=dict(field_key=fk, verdict="agree"))
    assert r2.status_code == 200
    d = client.get(B, headers=H).json()
    col = next(c for t in d["tabs"] for c in t["columns"] if c["field_key"] == fk)
    assert col["review"]["verdict"] == "agree" and col["review"]["n_reviews"] == 2      # the latest is shown
    assert d["counts"]["agree"] >= 1
    hist = client.get(B + "/reviews", headers=H, params={"field": fk}).json()
    assert [h["verdict"] for h in hist] == ["wrong_label", "agree"]
    # refused: an unknown column, an unknown verdict, a question with no text
    assert client.post(B + "/reviews", headers=H, json=dict(field_key="articles.nope", verdict="agree")).status_code == 422
    assert client.post(B + "/reviews", headers=H, json=dict(field_key=fk, verdict="maybe")).status_code == 422
    assert client.post(B + "/reviews", headers=H, json=dict(field_key=fk, verdict="question")).status_code == 422
    # a browser write riding on the cookie needs X-Desk-Client, like every other write
    client.cookies.set("desk_token", TOK)
    assert client.post(B + "/reviews", json=dict(field_key=fk, verdict="agree")).status_code == 403
    client.cookies.clear()
    with pytest.raises(psycopg.errors.RestrictViolation):
        pg.execute("UPDATE field_reviews SET verdict = 'agree'")
    pg.rollback()
    with pytest.raises(psycopg.errors.RestrictViolation):
        pg.execute("DELETE FROM field_reviews")
    pg.rollback()


def test_init_is_idempotent_and_adds_the_table_to_an_existing_schema(schema, pg):
    from desk import db
    db.init_schema(schema)              # the schema exists: only the upgrades tail runs again
    db.init_schema(schema)
    n = pg.execute("SELECT count(*) AS n FROM information_schema.tables WHERE table_schema = %s AND "
                   "table_name = 'field_reviews'", (schema,)).fetchone()["n"]
    assert n == 1
