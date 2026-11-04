"""The article beside its scan and the "All fields" tab (2026-10-23): /articles/{stem}/scan, /evidence/page and
/articles/{stem}/fields. Throwaway schema and crop folder, as test_p2_api."""
from __future__ import annotations

import hashlib
import os

import pytest
from fastapi.testclient import TestClient

from conftest import TEST_DIR, add_actor

WHO, TOKEN = "person:scan-reader", "tok-scan-reader"
H = {"X-Desk-Token": TOKEN}
STEM = "0130-018-072-003"            # gate 1's journal: 25 pages, 16 tables, a running head on every page


@pytest.fixture(scope="module")
def client(pg, test_dir):
    old = os.environ.get("DESK_CROPS")
    os.environ["DESK_CROPS"] = str(TEST_DIR / "crops_scan")
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


def test_scan_layout_has_every_page_and_the_blocks_boxes(client):
    r = client.get(f"/desk/api/articles/{STEM}/scan", headers=H)
    assert r.status_code == 200
    L = r.json()
    art = client.get(f"/desk/api/articles/{STEM}", headers=H).json()
    assert [p["page"] for p in L["pages"]] == [p["page"] for p in art["pages"]]
    boxed = {b["id"] for p in L["pages"] for b in p["blocks"]}
    # every block of the reading has its box on some page
    assert {b["block_id"] for b in art["blocks"]} <= boxed
    p1 = L["pages"][0]
    assert p1["w"] > 1000 and p1["h"] > 1000 and p1["folio"]
    for b in p1["blocks"]:                       # boxes sit inside the page frame
        assert 0 <= b["x"] <= p1["w"] and 0 <= b["y"] <= p1["h"]
    assert any(r["role"] == "pageHeader" for p in L["pages"] for r in p["regions"])
    assert client.get(f"/desk/api/articles/{STEM}/scan").status_code == 401
    assert client.get("/desk/api/articles/no-such-stem-1/scan", headers=H).status_code == 404


def test_page_image_is_downscaled_cached_and_checked(client):
    L = client.get(f"/desk/api/articles/{STEM}/scan", headers=H).json()
    if not L["pages"][0]["image"]:
        pytest.skip("the page images are not on this machine")
    r = client.get("/desk/api/evidence/page", params=dict(stem=STEM, page=2, w=640), headers=H)
    assert r.status_code == 200 and r.headers["content-type"] == "image/jpeg" and r.content[:2] == b"\xff\xd8"
    from PIL import Image
    import io
    assert Image.open(io.BytesIO(r.content)).width == 640
    assert any((TEST_DIR / "crops_scan" / "pages").rglob("*.jpg"))
    r2 = client.get("/desk/api/evidence/page", params=dict(stem=STEM, page=2, w=700), headers=H)
    assert r2.content == r.content                       # snapped to the same allowed width, from the cache
    assert client.get("/desk/api/evidence/page", params=dict(stem=STEM, page=999), headers=H).status_code == 404
    assert client.get("/desk/api/evidence/page", params=dict(stem="../etc", page=1), headers=H).status_code == 422


def test_all_fields_lists_every_kind_of_field_with_its_source(client):
    r = client.get(f"/desk/api/articles/{STEM}/fields", headers=H)
    assert r.status_code == 200
    d = r.json()
    F = d["fields"]
    assert d["counts"]["fields"] == len(F) > 100
    assert {f["source"] for f in F} == {"page", "catalogue", "corrected", "derived"}
    assert [g["id"] for g in d["groups"]][:2] == ["identity", "title"]
    keys = {f["key"] for f in F}
    for k in ("title", "journal_title", "year", "fpage", "lpage", "doi", "doc_type", "author.name", "byline",
              "aff.printed", "abstract", "page.folio", "region.pageHeader", "n.refs", "issn"):
        assert k in keys, k
    title = [f for f in F if f["key"] == "title" and f["chosen"]]
    assert title and title[0]["source"] == "page" and title[0]["anchor"].startswith(f"{STEM}|p1|")
    # D33: the last page is the rule's correction, the page's own reading stays beside it
    lp = {f["source"]: f for f in F if f["key"] == "lpage"}
    assert lp["corrected"]["chosen"] and lp["corrected"]["value"] == "75" and lp["page"]["value"] == "59"
    # rows come in group order, and every ink pointer is cuttable by /evidence/crop
    order = [g["id"] for g in d["groups"]]
    assert [order.index(f["group"]) for f in F] == sorted(order.index(f["group"]) for f in F)
    an = next(f for f in F if f["key"] == "byline")
    page = an["anchor"].split("|")[1][1:]
    c = client.get("/desk/api/evidence/crop", params=dict(stem=STEM, page=page, anchor=an["anchor"]), headers=H)
    assert c.status_code == 200 and c.content[:2] == b"\xff\xd8"
    assert client.get("/desk/api/articles/no-such-stem-1/fields", headers=H).status_code == 404
