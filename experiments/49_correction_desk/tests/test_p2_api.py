"""P2's routes: cookie sign-in, the read routes (articles, persons, works, top-cited, search), ink crops, building a
release from the screens and its before/after. Throwaway schema and folders as the P1 tests."""
from __future__ import annotations

import hashlib
import os
import time

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIR, add_actor

CORR, ADMIN = "person:p2-corrector", "person:p2-admin"
TOK = {CORR: "tok-p2-corrector", ADMIN: "tok-p2-admin"}
H = {a: {"X-Desk-Token": t} for a, t in TOK.items()}
STEM = "1967-000-008-012"            # Ibn Rashiq as poet: 40 citations, «الديوان» among them


@pytest.fixture(scope="module")
def client(pg, test_dir):
    # its own folders: test_release.py counts the release copies in the session's folder
    old = {k: os.environ.get(k) for k in ("DESK_CROPS", "DESK_RELEASES")}
    os.environ["DESK_CROPS"] = str(TEST_DIR / "crops")
    os.environ["DESK_RELEASES"] = str(TEST_DIR / "p2_releases")
    add_actor(pg, CORR, "corrector", ["ar", "en", "fr"])
    add_actor(pg, ADMIN, "admin", ["ar", "en", "fr"])
    for a, t in TOK.items():
        pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                   (hashlib.sha256(t.encode()).hexdigest(), a))
    pg.commit()
    from desk.api import app
    yield TestClient(app)
    for k, v in old.items():
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


def test_cookie_sign_in_and_csrf_header(client):
    c = TestClient(client.app, cookies={"desk_token": TOK[CORR]})
    assert c.get("/desk/api/me").json()["actor_id"] == CORR
    body = dict(text="cookie note")
    r = c.post(f"/desk/api/subjects/article:{STEM}/notes", json=body)
    assert r.status_code == 403 and "X-Desk-Client" in r.json()["detail"]
    r = c.post(f"/desk/api/subjects/article:{STEM}/notes", json=body, headers={"X-Desk-Client": "web"})
    assert r.status_code == 200 and r.json()["author"] == CORR
    assert TestClient(client.app).get("/desk/api/me").status_code == 401


def test_article_search_folds_arabic(client):
    # «إبن» / «رشيق» with a hamza and a final ya form the reading does not use: folding finds it
    r = client.get("/desk/api/articles", params=dict(q="إبن رشيق القيروانى"), headers=H[CORR]).json()
    assert STEM in [a["stem"] for a in r["articles"]]
    r = client.get("/desk/api/search", params=dict(q="العتيبى"), headers=H[CORR]).json()
    assert "AB5Y33ZFR1" in [p["id"] for p in r["persons"]]
    assert r["works"] == [] or all("id" in w for w in r["works"])


def test_article_page_is_whole(client):
    a = client.get(f"/desk/api/articles/{STEM}", headers=H[CORR]).json()
    assert a["subject"] == f"article:{STEM}"
    assert a["title"]["printed"] and a["title"]["catalogue"]
    assert a["authors"] and a["authors"][0]["person"].startswith("person:A")
    assert len(a["blocks"]) > 100 and a["blocks"][0]["role"] == "title"
    assert any(b.get("parts") for b in a["blocks"])
    assert len(a["notes"]) > 30 and any(n["calls"] for n in a["notes"])
    assert len(a["citations"]) >= 40 and any(c["card"] for c in a["citations"])
    assert any(c["target"] for c in a["citations"] if c["kind"] != "full")
    assert a["citations"][0]["anchor"].startswith(f"{STEM}|p")
    assert {"flags", "judge_findings", "corrections", "desk", "decisions"} <= set(a)
    assert client.get("/desk/api/articles/..%2Fetc", headers=H[CORR]).status_code in (404, 422)


def test_person_work_top(client):
    p = client.get("/desk/api/persons/AB5Y33ZFR1", headers=H[CORR]).json()
    assert p["subject"] == "person:AB5Y33ZFR1" and p["works"] and "desk" in p
    w = client.get("/desk/api/works/CK4KYP6BAX", headers=H[CORR]).json()
    assert w["subject"] == "work:CK4KYP6BAX" and len(w["members"]) >= 2 and w["citing"]
    assert all(m["key"].startswith("mention:") for m in w["members"])
    t = client.get("/desk/api/top/works", params=dict(limit=10), headers=H[CORR]).json()
    assert len(t["works"]) == 10 and t["works"][0]["rank"] == 1
    assert t["works"][0]["n_citing_pubs"] >= t["works"][-1]["n_citing_pubs"]


def test_crop(client):
    a = client.get(f"/desk/api/articles/{STEM}", headers=H[CORR]).json()
    c = a["citations"][0]
    page = int(c["anchor"].split("|")[1][1:])
    r = client.get("/desk/api/evidence/crop", params=dict(stem=STEM, page=page, anchor=c["anchor"]), headers=H[CORR])
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
    assert any((TEST_DIR / "crops").rglob("*.jpg"))
    b = next(b for b in a["blocks"] if b["parts"])
    r = client.get("/desk/api/evidence/crop", params=dict(stem=STEM, page=b["parts"][0]["page"], block=b["block_id"]),
                   headers=H[CORR])
    assert r.status_code == 200
    r = client.get("/desk/api/evidence/crop", params=dict(stem="0005-012-004-007", page=1, lines="p1b2l1,p1b2l2"),
                   headers=H[CORR])
    assert r.status_code == 200
    assert client.get("/desk/api/evidence/crop", params=dict(stem=STEM, page=1, lines="p1b1l1")).status_code == 401
    for bad in (dict(stem="../../etc", page=1, lines="p1b1l1"), dict(stem=STEM, page=999, lines="p999b1l1"),
                dict(stem=STEM, page=1, lines="p2b1l1"), dict(stem=STEM, page=1, anchor="0005-012-004-007|p1|w1-5")):
        assert client.get("/desk/api/evidence/crop", params=bad, headers=H[CORR]).status_code in (404, 422), bad


def test_build_release_from_the_screens_and_its_diff(client):
    assert client.post("/desk/api/releases", json={}, headers=H[CORR]).status_code == 403
    # a decision that moves the top-cited list: «المقدّمة» + «مقدمة ابن خلدون»
    r = client.post("/desk/api/decisions", headers=H[CORR],
                    json=dict(op="same_work", subject_keys=["work:CF622F7PED", "work:CVSFVRG2E8"], note="P2 test"))
    assert r.status_code == 200, r.text
    r = client.post("/desk/api/releases", json=dict(note="P2 test", run_detectors=False), headers=H[ADMIN])
    assert r.status_code == 202, r.text
    assert client.post("/desk/api/releases", json={}, headers=H[ADMIN]).status_code == 409
    t0 = time.time()
    while client.get("/desk/api/build", headers=H[CORR]).json()["running"]:
        assert time.time() - t0 < 300
        time.sleep(1)
    st = client.get("/desk/api/build", headers=H[CORR]).json()
    assert st["error"] is None and st["release_id"], st
    d = client.get(f"/desk/api/releases/{st['release_id']}/diff", headers=H[CORR]).json()
    assert d["before"] == "reading" and d["after"] == st["release_id"]
    muq = next(w for w in d["top"] if w["id"] == "CF622F7PED")
    assert muq["n_after"] > muq["n_before"] and muq["rank_after"] < muq["rank_before"]
    assert any(c["kind"] == "merged" and c["card"] == "CF622F7PED" for c in d["cards"])
    # the pages now read the release
    w = client.get("/desk/api/works/CVSFVRG2E8", headers=H[CORR]).json()
    assert w["id"] == "CF622F7PED" and w["resolved_from"] == "CVSFVRG2E8"
    assert w["desk"]["standing"] and w["desk"]["standing"][0]["actor_id"] == CORR
