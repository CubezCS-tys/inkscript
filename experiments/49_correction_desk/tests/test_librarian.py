"""The librarian page's API (desk/librarian.py, experiment 56): decisions are read from the librarian's append-only
files (newest per question, retired ones left out), filtered and shown with their evidence; the owner's verdicts are
stored append-only in PostgreSQL. A small fixture folder stands in for experiment 56's out/; the real files, when
present, are checked for shape."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

ACTOR, TOK = "person:librarian-tester", "tok-librarian-tester"
H = {"X-Desk-Token": TOK}
B = "/desk/api/librarian"
REAL = Path(__file__).resolve().parents[2] / "56_librarian_institutions" / "out"


def _dec(i, kind, conf, level="affiliation", qkey=None, **extra):
    d = dict(decision_id=f"D56-{i:012x}", qkey=qkey or f"q{i}", level=level, kind=kind, question="?",
             subject_keys=[f"aff:0130-018-070-00{i % 9}|b0|Arab|a1"], decision=dict(status="resolved"),
             reason=f"reason {i}", evidence_ids=[f"aff:0130-018-070-00{i % 9}|b0|Arab|a1"], confidence=conf,
             basis="rule", trivial=True, printed=f"جامعة {i}")
    d.update(extra)
    return d


@pytest.fixture(scope="module")
def libdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("librarian")
    rows = [_dec(1, "affiliation_institution", "high"),
            _dec(2, "affiliation_institution", "medium", printed="كلية الآداب - فاس"),
            _dec(3, "unsure", "low"),
            _dec(4, "same_institution", "high", level="institution", qkey="same|L-eg-alexandria",
                 decision=dict(institution="L-eg-alexandria", bilingual_twin=True)),
            # a later answer on question q1 supersedes decision 1; question q5 is withdrawn
            _dec(5, "affiliation_institution", "high", qkey="q1", supersedes="D56-000000000001"),
            _dec(6, "set_country", "high", level="institution", qkey="country|I1"),
            dict(decision_id="D56-00000000000a", qkey="country|I1", level="institution", kind="retired",
                 decision=dict(retired="D56-000000000006"), subject_keys=[], evidence_ids=[])]
    (d / "decisions56.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "sample56.json").write_text(json.dumps(dict(seed=56, strata=[["merge", 1]], items=[
        dict(stratum="merge", decision_id="D56-000000000004", kind="same_institution", evidence=[])])), encoding="utf-8")
    (d / "numbers56.json").write_text(json.dumps(dict(before=dict(institutions_linked=271), after=dict(institutions=234))))
    (d / "packets56.jsonl").write_text(json.dumps(dict(key="aff:0130-018-070-004|b0|Arab|a1", printed="جامعة 4",
                                                       stem="0130-018-070-004"), ensure_ascii=False))
    old = os.environ.get("LIBRARIAN_DIR")
    os.environ["LIBRARIAN_DIR"] = str(d)
    yield d
    if old is None:
        os.environ.pop("LIBRARIAN_DIR", None)
    else:
        os.environ["LIBRARIAN_DIR"] = old


@pytest.fixture(scope="module")
def client(pg, libdir):
    add_actor(pg, ACTOR, "corrector")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOK.encode()).hexdigest(), ACTOR))
    pg.commit()
    from desk.api import app
    return TestClient(app)


def test_needs_a_token(client):
    assert client.get(B).status_code == 401
    assert client.get(B + "/decisions").status_code == 401
    assert client.post(B + "/verdicts", json=dict(decision_id="D56-000000000004", verdict="yes")).status_code == 401


def test_overview_counts_standing_decisions_only(client):
    d = client.get(B, headers=H).json()
    # 1 is superseded by 5, 6 is retired: 2, 3, 4, 5 stand
    assert d["counts"]["total"] == 4
    assert d["counts"]["by_kind"] == {"affiliation_institution": 2, "unsure": 1, "same_institution": 1}
    assert d["numbers"]["after"]["institutions"] == 234 and d["applied"] is False
    assert [x["decision_id"] for x in d["sample"]["items"]] == ["D56-000000000004"]
    assert d["sample"]["items"][0]["verdict"] is None


def test_list_filters(client):
    g = lambda **q: client.get(B + "/decisions", headers=H, params=q).json()  # noqa: E731
    assert g()["total"] == 4
    assert g(kind="unsure")["total"] == 1
    assert g(confidence="medium")["rows"][0]["decision_id"] == "D56-000000000002"
    assert g(level="institution")["total"] == 1
    assert g(q="فاس")["total"] == 1
    assert g(limit=1, offset=1)["rows"][0]["decision_id"] == "D56-000000000002"   # file order of the questions
    assert client.get(B + "/decisions", headers=H, params=dict(kind="drop table")).status_code == 422
    assert client.get(B + "/decisions", headers=H, params=dict(confidence="sure")).status_code == 422


def test_one_decision_with_its_evidence(client):
    r = client.get(B + "/decisions/D56-000000000004", headers=H).json()
    assert r["kind"] == "same_institution" and r["standing"] is True
    assert [p["key"] for p in r["packets"]] == ["aff:0130-018-070-004|b0|Arab|a1"]
    assert client.get(B + "/decisions/D56-000000000001", headers=H).json()["standing"] is False
    assert client.get(B + "/decisions/nope", headers=H).status_code == 422
    assert client.get(B + "/decisions/D56-00000000ffff", headers=H).status_code == 404


def test_verdicts_are_stored_latest_shown_and_append_only(client, pg):
    p = lambda **b: client.post(B + "/verdicts", headers=H, json=b)  # noqa: E731
    assert p(decision_id="D56-000000000004", verdict="maybe").status_code == 422
    assert p(decision_id="D56-00000000ffff", verdict="yes").status_code == 404
    assert p(decision_id="x' OR 1=1", verdict="yes").status_code == 422
    r1 = p(decision_id="D56-000000000004", verdict="no", comment="the Arabic row is another faculty")
    assert r1.status_code == 200 and r1.json()["in_sample"] is True
    r2 = p(decision_id="D56-000000000004", verdict="yes", comment="  ")
    assert r2.json()["comment"] is None
    assert p(decision_id="D56-000000000003", verdict="unsure").json()["in_sample"] is False
    d = client.get(B, headers=H).json()
    item = d["sample"]["items"][0]
    assert item["verdict"]["verdict"] == "yes" and item["verdict"]["n_verdicts"] == 2
    assert d["sample"]["verdicts"] == {"yes": 1}
    hist = client.get(B + "/verdicts", headers=H, params=dict(decision_id="D56-000000000004")).json()
    assert [h["verdict"] for h in hist] == ["no", "yes"]
    rows = client.get(B + "/decisions", headers=H, params=dict(kind="unsure")).json()["rows"]
    assert rows[0]["verdict"]["verdict"] == "unsure"
    for sql in ("UPDATE librarian_verdicts SET verdict = 'no'", "DELETE FROM librarian_verdicts",
                "TRUNCATE librarian_verdicts"):
        with pytest.raises(psycopg.errors.RestrictViolation):
            pg.execute(sql)
        pg.rollback()


@pytest.mark.skipif(not (REAL / "decisions56.jsonl").exists(), reason="experiment 56's out/ is not on this machine")
def test_the_real_files_are_well_formed():
    rows = [json.loads(l) for l in (REAL / "decisions56.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = {r["decision_id"] for r in rows}
    assert len(ids) == len(rows), "decision ids are unique"
    for r in rows:
        assert {"decision_id", "qkey", "level", "kind", "decision", "evidence_ids"} <= set(r), r["decision_id"]
        if r["kind"] != "retired":
            assert r["confidence"] in ("high", "medium", "low") and r["basis"] in (
                "rule", "catalogue", "world", "context", "judgement"), r["decision_id"]
        if r.get("supersedes"):
            assert r["supersedes"] in ids
    s = json.loads((REAL / "sample56.json").read_text(encoding="utf-8"))
    assert s["n"] == len(s["items"]) == 30
    assert all(x["decision_id"] in ids for x in s["items"])
