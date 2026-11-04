"""The Explorer (desk/explore.py, /explore): every field, sortable, filterable, groupable, exportable; and nothing but
the listed columns and operators ever reaches SQL. Reads the state read-only (here the machine's reading, since the
throwaway schema has no release)."""
from __future__ import annotations

import csv
import hashlib
import io
import json

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

ACTOR, TOK = "person:explore-tester", "tok-explore-tester"
H = {"X-Desk-Token": TOK}
B = "/desk/api/explore"


@pytest.fixture(scope="module")
def client(pg):
    add_actor(pg, ACTOR, "corrector")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOK.encode()).hexdigest(), ACTOR))
    pg.commit()
    from desk.api import app
    return TestClient(app)


def get(client, path, **params):
    if "f" in params and not isinstance(params["f"], str):
        params["f"] = json.dumps(params["f"], ensure_ascii=False)
    return client.get(B + path, params=params, headers=H)


def test_meta_lists_every_entity_with_where_each_field_lives(client):
    assert client.get(B).status_code == 401                         # a token is needed
    r = get(client, "", warm="true").json()
    ents = r["entities"]
    assert list(ents) == ["articles", "references", "persons", "institutions", "journals", "works"]
    assert len(ents["articles"]["columns"]) >= 120 and len(ents["references"]["columns"]) >= 60
    assert sum(len(e["columns"]) for e in ents.values()) >= 300
    for e in ents.values():
        assert e["n"] and e["n"] > 0
        assert all(c["src"] and c["label"] for c in e["columns"])
        assert e["key"] in {c["name"] for c in e["columns"]}


def test_rows_sort_page_and_filters(client):
    r = get(client, "/works", cols="cited_work_id,title,times_cited", sort="times_cited", desc="true", limit=20).json()
    tc = [row[2] for row in r["rows"]]
    assert len(tc) == 20 and tc == sorted(tc, reverse=True) and r["total"] == r["n_all"] > 1000
    p2 = get(client, "/works", cols="cited_work_id,times_cited", sort="times_cited", desc="true", limit=20,
             offset=20).json()
    assert p2["rows"][0][1] <= tc[-1] and not {x[0] for x in p2["rows"]} & {x[0] for x in r["rows"]}
    # a year range and a numeric filter
    r = get(client, "/articles", cols="stem,year,n_full", f=[{"c": "year", "op": "between", "v": [2000, 2010]},
                                                            {"c": "n_full", "op": "gte", "v": 5}], limit=500).json()
    assert r["total"] > 0 and all(2000 <= y <= 2010 and n >= 5 for _, y, n in r["rows"])
    # empty / not empty partition the table
    a = get(client, "/references", f=[{"c": "cited_work_id", "op": "empty"}], limit=1).json()["total"]
    b = get(client, "/references", f=[{"c": "cited_work_id", "op": "not_empty"}], limit=1).json()["total"]
    assert a + b == get(client, "/references", limit=1).json()["n_all"]


def test_arabic_contains_and_quick_search_fold(client):
    # «إبن منظور» with a hamza the printed references mostly do not use: folding finds «ابن منظور»
    r = get(client, "/references", cols="mention_id,printed", q="إبن منظور", limit=500).json()
    assert r["total"] >= 5 and r["total"] == get(client, "/references", q="ابن منظور", limit=1).json()["total"]
    r2 = get(client, "/references", cols="mention_id,printed",
             f=[{"c": "printed", "op": "contains", "v": "لسان العربى"}], limit=500).json()
    assert r2["total"] >= 5 and all("لسان العرب" in row[1] for row in r2["rows"])


def test_group_by_with_counts_and_a_sum(client):
    r = get(client, "/articles/groups", by="journal", measure="n_full").json()
    assert r["groups"] and r["groups"][0]["n"] >= r["groups"][-1]["n"]
    assert sum(g["n"] for g in r["groups"]) == r["total"] or r["n_groups"] > len(r["groups"])
    assert all(g["sum"] is not None for g in r["groups"])


def test_csv_is_the_current_view(client):
    f = [{"c": "pub_type", "op": "eq", "v": "thesis"}]
    total = get(client, "/works", f=f, limit=1).json()["total"]
    r = client.get(B + "/works/csv", params=dict(cols="cited_work_id,title,times_cited", f=json.dumps(f),
                                                 sort="times_cited", desc="true"), headers=H)
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/csv")
    text = r.content.decode("utf-8-sig")
    rows = list(csv.reader(io.StringIO(text)))
    assert rows[0] == ["Cited work", "Title", "Times cited (articles)"] and len(rows) == total + 1


@pytest.mark.parametrize("path,params", [
    ("/articles", dict(cols="stem,no_such_column")),                                   # an unknown column
    ("/articles", dict(cols="stem,title; DROP TABLE x_articles")),
    ("/articles", dict(sort="year DESC; DELETE FROM x_articles")),
    ("/articles", dict(f=[{"c": "1=1) OR (1", "op": "eq", "v": 1}])),
    ("/articles", dict(f=[{"c": "title", "op": "LIKE", "v": "%"}])),                    # an unknown operator
    ("/articles", dict(f=[{"c": "title", "op": "gt", "v": 3}])),                        # range on a text column
    ("/articles", dict(f=[{"c": "year", "op": "gt", "v": "abc"}])),                     # not a number
    ("/articles", dict(f="not json")),
    ("/articles/groups", dict(by="no_such_column")),
    ("/articles/groups", dict(by="journal", measure="title")),                          # sum of a text column
    ("/no_such_entity", dict()),
    ("/articles/csv", dict(cols="stem,no_such_column")),
])
def test_unknown_names_are_refused(client, path, params):
    r = get(client, path, **params)
    assert r.status_code == 422, (path, params, r.status_code, r.text[:200])


def test_values_are_bound_never_spliced(client):
    n = get(client, "/articles", limit=1).json()["n_all"]
    r = get(client, "/articles", f=[{"c": "title", "op": "eq", "v": "x' OR '1'='1"}], limit=5).json()
    assert r["total"] == 0
    r = get(client, "/articles", q="') OR 1=1 --", limit=5).json()
    assert r["total"] == 0
    assert get(client, "/articles", limit=1).json()["n_all"] == n        # the table is still whole
