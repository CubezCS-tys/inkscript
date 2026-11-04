"""Nothing lost (/audit, 2026-11-02): GET /desk/api/audit and /desk/api/audit/articles/{stem} serve experiment 61's
precomputed audit, read-only. The known leak of the default article (0130-018-072-003 p1: the English affiliation
and both posts) is there; refusals. Throwaway schema, as test_pipeline."""
from __future__ import annotations

import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

WHO, TOKEN = "person:audit-reader", "tok-audit-reader"
H = {"X-Desk-Token": TOKEN}
STEM = "0130-018-072-003"


@pytest.fixture(scope="module")
def client(pg):
    add_actor(pg, WHO)
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOKEN.encode()).hexdigest(), WHO))
    pg.commit()
    from desk.api import app
    from desk import audit
    # the test pins experiment 61's own audit (it holds the known leak); the live pointer (/home/appuser/data/desk/
    # audit_current, experiments 68 and 70) reads audits where experiment 65 fixed that leak
    import os
    old = os.environ.get("DESK_AUDIT_DIR")
    os.environ["DESK_AUDIT_DIR"] = str(Path(audit.__file__).resolve().parents[2] / "61_nothing_lost" / "out")
    if not (audit.audit_dir() / "audit.json").exists():
        pytest.skip("experiment 61's audit has not been run on this machine")
    yield TestClient(app)
    if old is None:
        os.environ.pop("DESK_AUDIT_DIR", None)
    else:
        os.environ["DESK_AUDIT_DIR"] = old


def test_summary(client):
    r = client.get("/desk/api/audit", headers=H)
    assert r.status_code == 200, r.text
    d = r.json()
    assert d["n_articles"] >= 700 and d["totals"]["all"]["accounted_lines"] > 99
    assert any(x["field"] == "position" and x["kind"] == "mapping" for x in d["leak_table"])
    assert {f["id"] for f in d["fixes"]} >= {"M1", "M2", "P1"}
    assert any(x["stem"] == STEM for x in d["index"])


def test_the_default_article(client):
    d = client.get(f"/desk/api/audit/articles/{STEM}", headers=H).json()
    lk = {x["id"]: x for x in d["leaks"]}
    assert lk["1:31"]["field"] == "affiliation" and lk["1:31"]["kind"] == "mapping"
    assert {"1:9", "1:30"} <= set(lk)
    assert d["page_size"]["1"] and any(L["id"] == "1:31" and L["box"] for L in d["lines"])
    assert any(f["bucket"] == "b" for f in d["flows"])


def test_refusals(client):
    assert client.get("/desk/api/audit").status_code == 401
    assert client.get("/desk/api/audit/articles/no-such-stem-1", headers=H).status_code == 404
    assert client.get("/desk/api/audit/articles/..%2Fetc", headers=H).status_code in (404, 422)
