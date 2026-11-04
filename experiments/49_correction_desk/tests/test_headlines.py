"""The headline numbers (experiment 73, 2026-11-03): the shape the Story page, the deck and the Index home read
(CONTRACT.md), every value defined, and every value equal to its source (the index numbers of the same state,
experiment 70's measure70.json, the proof pack, experiment 71's simulate71.json). Then the route, with a token."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor
from desk import db
from desk import headlines as H
from desk import index_pages as X

PATH = db.reading_path()
KEYS = {"release", "articles", "pages", "words", "references", "journals_read_whole", "institutions",
        "institutions_with_country_pct", "cited_works", "cited_by_2plus", "held_pct", "audit_pct", "words_wrong",
        "gate1", "gate2", "librarian", "costs"}


@pytest.fixture(scope="module")
def h():
    return H.headlines(PATH, None)


def test_shape_and_defs(h):
    assert KEYS <= set(h)
    for k in KEYS - {"release"}:
        assert H.DEFS.get(k), f"no definition for {k}"
    assert h["defs"] is H.DEFS


def test_index_numbers_agree_with_the_overview(h):
    o = {m["key"]: m["value"] for m in X.overview(PATH)["numbers"]}
    for k in ("articles", "pages", "words", "references", "institutions", "cited_works"):
        assert h[k] == o[k]
    assert h["held_pct"] == o["held"]
    assert 0 <= h["institutions_with_country_pct"] <= 100


def test_journals_read_whole(h):
    ids = [j["id"] for j in h["journals_read_whole"]]
    assert ids == sorted(X.WHOLE_JOURNALS)
    for j in h["journals_read_whole"]:
        assert j["scan"] + j["word"] == j["articles"]
        assert j["gate"] in ("gate 1", "gate 2 pilot")
        assert j["country"] is None or len(j["country"]) > 2       # a name, not a code


def test_gate2_live_with_experiment_70s_code(h):
    g = h["gate2"]
    assert g["pair"] == ["J0130", "J0165"]
    for k in ("shared_authors", "shared_works", "shared_institutions", "coupled_pairs"):
        assert len(g[k]) == 2 and g[k][0] is not None and g[k][1] is not None
    assert g["shared_authors"][0] > g["shared_authors"][1] and g["shared_works"][0] > 3 * g["shared_works"][1]
    assert g["measured_on"] == PATH.stem
    assert g["cost_usd"] == pytest.approx(23.29) and g["ten_journals_usd"] == 313


def test_gate2_reproduces_experiment_70_on_its_release():
    """measure70.json was measured on R20261103T023001: the live code gives the same numbers there."""
    m = json.loads((H.GATE2_DIR / "out" / "measure70.json").read_text())
    rel = Path(m["db"])
    if not rel.is_file():
        pytest.skip("experiment 70's release is not on this machine")
    L = H._gate2_live(rel)
    assert (L["J_to_K"], L["K_to_J"]) == (m["J_to_K"]["to_journal"], m["K_to_J"]["to_journal"])
    for k in ("authors", "institutions", "cited_works", "coupling_edges"):
        assert L["shared"][k] == m["shared_J_K"][k]
        assert L["baseline"][k] == m["baseline"][f"J_vs_randomK.{k}"]["mean"]


def test_proof_librarian_costs(h):
    assert h["words_wrong"]["wrong"] == 0 and h["words_wrong"]["of"] == 1532 and h["words_wrong"]["pages"] == 60
    lib = h["librarian"]
    assert lib["precision_pct"] == 99.1 and lib["usd_per_1000"] == 3
    assert lib["institutions"] == [271, 242] and lib["cited_works"][0] == 9137
    assert h["costs"] == dict(per_scan_page_usd=0.0078, per_word_article_usd=0.0055, price_doubles="2026-12-01")
    assert h["audit_pct"] is None or 99 < h["audit_pct"] <= 100


def test_cached_per_state(h):
    assert H.headlines(PATH, None) is h


TOK = "tok-headlines-reader"


@pytest.fixture(scope="module")
def client(pg, test_dir):
    add_actor(pg, "person:headlines-reader", "corrector")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOK.encode()).hexdigest(), "person:headlines-reader"))
    pg.commit()
    from desk.api import app
    return TestClient(app)


def test_headlines_route(client):
    assert client.get("/desk/api/headlines").status_code == 401
    r = client.get("/desk/api/headlines", headers={"X-Desk-Token": TOK})
    assert r.status_code == 200
    d = r.json()
    assert KEYS <= set(d) and d["defs"]["gate2"]
    assert d["gate2"]["shared_authors"][0] >= 1
