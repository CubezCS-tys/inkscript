"""The cited-works librarian page's API (desk/librarian_works.py, experiment 62): decisions are read from the
librarian's append-only file (newest per question), filtered; the verification results are served as they are; only
the escalated cases take a verdict, stored append-only in PostgreSQL. A small fixture folder stands in for
experiment 62's out/; the real files, when present, are checked for shape."""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import psycopg
import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

ACTOR, TOK = "person:works-librarian-tester", "tok-works-librarian-tester"
H = {"X-Desk-Token": TOK}
B = "/desk/api/librarian/works"
REAL = Path(__file__).resolve().parents[2] / "62_librarian_works" / "out"


def _dec(i, level, kind, conf, qkey=None, **extra):
    d = dict(decision_id=f"D62-{i:012x}", qkey=qkey or f"q{i}", level=level, kind=kind, question="?",
             packet=f"merge:C{i}", subject_keys=[f"C{i:09d}"], decision=dict(cards=[]), reason=f"reason {i}",
             evidence_ids=[f"C{i:09d}"], confidence=conf, basis="rule", trivial=True, printed=[f"لسان العرب {i}"])
    d.update(extra)
    return d


@pytest.fixture(scope="module")
def libdir(tmp_path_factory):
    d = tmp_path_factory.mktemp("librarian62")
    rows = [_dec(1, "pair", "same_work", "high"),
            _dec(2, "pair", "different_work", "medium", printed=["الصحيح لابن خزيمة"]),
            _dec(3, "card", "not_a_work", "medium", decision=dict(action="drop")),
            _dec(4, "catalogue", "links_to_publication", "high", basis="catalogue"),
            # a later answer on question q1 supersedes decision 1
            _dec(5, "pair", "edition_of", "high", qkey="q1", supersedes="D62-000000000001", basis="world",
                 trivial=False)]
    (d / "decisions62.jsonl").write_text("\n".join(json.dumps(r, ensure_ascii=False) for r in rows), encoding="utf-8")
    (d / "numbers62.json").write_text(json.dumps(dict(before=dict(cited_works=9137), after=dict(cited_works=8850))))
    (d / "precision62.json").write_text(json.dumps(dict(threshold=0.98, by_kind=[dict(kind="pair:edition_of", n=15,
                                                                                     correct=15)])))
    (d / "escalate62.json").write_text(json.dumps(dict(cases=[dict(decision_id="D62-000000000002", title="?")])))
    old = os.environ.get("LIBRARIAN62_DIR")
    os.environ["LIBRARIAN62_DIR"] = str(d)
    yield d
    if old is None:
        os.environ.pop("LIBRARIAN62_DIR", None)
    else:
        os.environ["LIBRARIAN62_DIR"] = old


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
    assert client.post(B + "/verdicts", json=dict(decision_id="D62-000000000002", verdict="yes")).status_code == 401


def test_overview(client):
    d = client.get(B, headers=H).json()
    assert d["counts"]["total"] == 4 and d["counts"]["superseded"] == 1   # 1 is superseded by 5
    assert d["counts"]["by_kind"] == {"pair:edition_of": 1, "pair:different_work": 1, "card:not_a_work": 1,
                                      "catalogue:links_to_publication": 1}
    assert d["numbers"]["after"]["cited_works"] == 8850 and d["applied"] == "partly"
    assert d["precision"]["threshold"] == 0.98
    assert [c["decision_id"] for c in d["escalated"]] == ["D62-000000000002"] and d["escalated"][0]["verdict"] is None
    assert d["blind"] == [] and d["rules"] is None      # files absent: empty, not an error


def test_list_filters(client):
    g = lambda **q: client.get(B + "/decisions", headers=H, params=q).json()  # noqa: E731
    assert g()["total"] == 4
    assert g(level="pair")["total"] == 2
    assert g(kind="not_a_work")["total"] == 1
    assert g(confidence="medium")["rows"][0]["decision_id"] == "D62-000000000002"
    assert g(basis="world")["rows"][0]["decision_id"] == "D62-000000000005"
    assert g(q="خزيمة")["total"] == 1
    assert g(limit=1, offset=1)["rows"][0]["decision_id"] == "D62-000000000002"
    assert client.get(B + "/decisions", headers=H, params=dict(kind="drop table")).status_code == 422
    assert client.get(B + "/decisions", headers=H, params=dict(level="work")).status_code == 422


def test_one_decision_with_what_it_replaced(client):
    r = client.get(B + "/decisions/D62-000000000005", headers=H).json()
    assert r["standing"] is True and [x["decision_id"] for x in r["superseded"]] == ["D62-000000000001"]
    assert client.get(B + "/decisions/D62-000000000001", headers=H).json()["standing"] is False
    assert client.get(B + "/decisions/D56-000000000001", headers=H).status_code == 422
    assert client.get(B + "/decisions/D62-00000000ffff", headers=H).status_code == 404


def test_verdicts_only_on_escalated_cases_and_append_only(client, pg):
    p = lambda **b: client.post(B + "/verdicts", headers=H, json=b)  # noqa: E731
    assert p(decision_id="D62-000000000002", verdict="maybe").status_code == 422
    assert p(decision_id="D62-00000000ffff", verdict="yes").status_code == 404
    assert p(decision_id="x' OR 1=1", verdict="yes").status_code == 422
    assert p(decision_id="D62-000000000004", verdict="yes").status_code == 409     # not escalated
    r1 = p(decision_id="D62-000000000002", verdict="no", comment="they are one work")
    assert r1.status_code == 200 and r1.json()["escalated"] is True
    assert p(decision_id="D62-000000000002", verdict="yes", comment="  ").json()["comment"] is None
    d = client.get(B, headers=H).json()
    assert d["escalated"][0]["verdict"]["verdict"] == "yes" and d["escalated"][0]["verdict"]["n_verdicts"] == 2
    hist = client.get(B + "/verdicts", headers=H, params=dict(decision_id="D62-000000000002")).json()
    assert [h["verdict"] for h in hist] == ["no", "yes"]
    for sql in ("UPDATE librarian_works_verdicts SET verdict = 'no'", "DELETE FROM librarian_works_verdicts",
                "TRUNCATE librarian_works_verdicts"):
        with pytest.raises(psycopg.errors.RestrictViolation):
            pg.execute(sql)
        pg.rollback()


@pytest.mark.skipif(not (REAL / "decisions62.jsonl").exists(), reason="experiment 62's out/ is not on this machine")
def test_the_real_files_are_well_formed():
    rows = [json.loads(l) for l in (REAL / "decisions62.jsonl").read_text(encoding="utf-8").splitlines() if l.strip()]
    ids = {r["decision_id"] for r in rows}
    assert len(ids) == len(rows), "decision ids are unique"
    for r in rows:
        assert {"decision_id", "qkey", "level", "kind", "decision", "evidence_ids", "reason"} <= set(r), r["decision_id"]
        assert r["confidence"] in ("high", "medium", "low") and r["basis"] in (
            "rule", "catalogue", "world", "context", "judgement"), r["decision_id"]
        if r.get("supersedes"):
            assert r["supersedes"] in ids
    latest = {}
    for r in rows:
        latest[r["qkey"]] = r
    for c in json.loads((REAL / "escalate62.json").read_text(encoding="utf-8"))["cases"]:
        assert latest[c["qkey"]]["decision_id"] == c["decision_id"], "escalated cases point at standing decisions"
