"""How a page is read (/pipeline, 2026-10-30): GET /desk/api/pipeline/{stem}?page=N. The shape every stage of the
page reads, the known numbers of the default page (0130-018-072-003 page 1, gate 1's journal), the quick-switch
pages, and that nothing is written: the reading, the ALTO master and Gemini's answer keep their bytes. Throwaway
schema, as test_scan_fields."""
from __future__ import annotations

import hashlib
import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIR, add_actor

WHO, TOKEN = "person:pipeline-reader", "tok-pipeline-reader"
H = {"X-Desk-Token": TOKEN}
STEM = "0130-018-072-003"


def _sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


@pytest.fixture(scope="module")
def client(pg, test_dir):
    old = os.environ.get("DESK_CROPS")
    os.environ["DESK_CROPS"] = str(TEST_DIR / "crops_pipeline")
    add_actor(pg, WHO)
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(TOKEN.encode()).hexdigest(), WHO))
    pg.commit()
    from desk.api import app
    yield TestClient(app)
    if old is None:
        os.environ.pop("DESK_CROPS", None)
    else:
        os.environ["DESK_CROPS"] = old


@pytest.fixture(scope="module")
def p1(client):
    r = client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=1), headers=H)
    if r.status_code == 404 and "masters" in r.text:
        pytest.skip("experiment 43's masters are not on this machine")
    assert r.status_code == 200, r.text
    return r.json()


def test_shape_of_every_stage(p1):
    for k in ("stem", "page", "pages", "frame", "image_url", "answer", "words", "lines", "blocks", "regions", "fixes",
              "misprints", "flags", "judge", "fields", "entities", "index", "suggest", "counts", "role_labels"):
        assert k in p1, k
    assert set(p1["counts"]) == {"scan", "azure", "gemini", "rules", "judge", "platform", "index"}
    W, Hh = p1["frame"]["w"], p1["frame"]["h"]
    for w in p1["words"]:                               # every word sits in the page frame, on a numbered line
        assert 0 <= w["x"] <= W and 0 <= w["y"] <= Hh and w["w"] > 0 and w["l"]
    for f in p1["fields"]:                              # every field carries its ink
        assert f["boxes"], f
        for b in f["boxes"]:
            assert 0 <= b["x"] <= W and 0 <= b["y"] <= Hh
    ids = {e["id"] for e in p1["entities"]}
    for f in p1["fields"]:
        assert set(f["entities"]) <= ids


def test_the_default_page_numbers(p1):
    """The front page of gate 1's article: Azure's 419 words on 46 lines, Gemini's 16 blocks in 6 roles (line ids
    only, prompt v3.5b), 14 blocks in the masters with the running head and the page number kept out, and the
    fields that resolve to one person, two institutions (faculty and university) and the journal."""
    c = p1["counts"]
    assert c["azure"]["words"] == 419 and c["azure"]["lines"] == 46
    assert p1["answer"]["source"] == "gemini" and p1["answer"]["prompt"] == "v3.5b"
    assert c["gemini"]["blocks"] == 16 and c["gemini"]["roles"] == 6 and c["gemini"]["lines"] == 46
    assert [b["role"] for b in p1["answer"]["blocks"]][:3] == ["running", "title", "byline"]
    assert p1["answer"]["blocks"][1]["lines"] == [4, 5, 6]
    assert c["rules"]["blocks"] == 14 and c["rules"]["kept_out"] == 2
    assert {r["role"] for r in p1["regions"]} == {"pageHeader", "pageNumber"}
    kinds = [f["kind"] for f in p1["fields"]]
    # two affiliations since experiment 68 went live (exp 65's M2): the English line «University of Mohamed V -
    # Faculty of Education Sciences - Morocco», experiment 61's leak 1:31, is now a field beside its Arabic twin
    assert kinds.count("title") == 2 and kinds.count("author") == 2 and kinds.count("affiliation") == 2
    assert kinds.count("abstract") == 2 and kinds.count("heading") == 2
    aff = next(f for f in p1["fields"] if f["kind"] == "affiliation")
    assert {p["part"] for p in aff["parts"]} >= {"faculty", "organisation", "country"}
    ents = {e["id"]: e for e in p1["entities"]}
    assert ents["A41QMPZRVG"]["kind"] == "person"
    # the faculty: «كلية علوم التربية» I1NW24RKQM before experiment 68; since its twin rows the page names the English
    # twin's row IP0XR2KXSC «Faculty of Education Sciences» (same parent; the two rows are one faculty: a librarian task)
    assert "IJAPCDK8G1" in ents and {"I1NW24RKQM", "IP0XR2KXSC"} & set(ents) and ents["J0130"]["kind"] == "journal"
    assert ents["J0130"]["n_articles"] >= 126
    assert p1["index"]["pub_id"] == "W825854" and p1["index"]["references"] == 31
    assert p1["suggest"] == {"front": 1, "footnotes": 2, "table": 12, "references": 24} or \
        {k: p1["suggest"][k] for k in ("front", "footnotes", "table", "references")} == \
        {"front": 1, "footnotes": 2, "table": 12, "references": 24}


def test_footnote_table_and_reference_pages(client):
    p2 = client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=2), headers=H).json()
    fn = [f for f in p2["fields"] if f["kind"] == "footnote"]
    assert len(fn) == 1 and fn[0]["call"]                    # the call mark's own word, for the arrow
    assert p2["answer"]["calls"][0]["line"] == 26
    p12 = client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=12), headers=H).json()
    tables = [f for f in p12["fields"] if f["kind"] == "table"]
    assert len(tables) == 2 and all(t["cells"] for t in tables)
    p24 = client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=24), headers=H).json()
    refs = [f for f in p24["fields"] if f["kind"] == "reference"]
    assert len(refs) == 11
    assert all(r["entities"] and r["entities"][0].startswith("C") for r in refs)
    first = refs[0]
    assert {p["part"] for p in first["parts"]} >= {"author", "title"}


def test_nothing_is_written(client):
    from desk import pipeline as PL
    from desk import db
    with db.connect() as pg:
        from desk import pages as P
        state, _ = P.state_of(pg)
    alto = PL.E43 / "j0130_final" / "masters" / f"{STEM}.alto.xml"
    raws = sorted((PL.E43 / "j0130_final" / "raw").glob(f"{STEM}_c*.json"))
    files = [state, alto, *raws]
    files = [f for f in files if f.is_file()]
    before = {f: (_sha(f), f.stat().st_mtime) for f in files}
    for page in (1, 2, 12, 24):
        assert client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=page), headers=H).status_code == 200
    assert {f: (_sha(f), f.stat().st_mtime) for f in files} == before


def test_refusals(client):
    assert client.get(f"/desk/api/pipeline/{STEM}").status_code == 401
    assert client.get("/desk/api/pipeline/no-such-stem-1", headers=H).status_code == 404
    assert client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=999), headers=H).status_code == 404
    assert client.get("/desk/api/pipeline/..%2Fetc", headers=H).status_code in (404, 422)
    assert client.get(f"/desk/api/pipeline/{STEM}", params=dict(page=0), headers=H).status_code == 422


def test_runs_it_was_built_from():
    from desk import pipeline as PL
    assert PL._runs_from("v33_300_final_lettersfix") == ["v33_300_final_lettersfix", "v33_300_final", "v33_300", "v33"]
    assert PL.answer_chunk("../x", STEM, 1) == (None, None)
