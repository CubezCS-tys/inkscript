"""The project page (/project, 2026-10-26): desk/project/project.json is well formed, every item carries a source,
every item the Map tab draws has a short label of at most six words, every Desk link in it resolves to a page that
exists, every repo path it cites exists (an experiment's out/ only when that out/ is present, as in
tests/test_docs.py) with its #section where it names a Markdown heading, and the API serves it with the live
spend."""
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
REPO = DESK.parents[1]
WEB = DESK / "web"
PROJECT = DESK / "desk" / "project" / "project.json"

SECTIONS = ["meta", "headline", "stage", "north_star", "picture", "timeline", "numbers", "decisions", "ideas",
            "waiting_on_owner", "next_steps", "roadmap", "money", "where_things_live", "risks", "glossary",
            "source_notes"]
STATIC = ("gate1", "gate2", "pitch", "inventory", "mindmap", "mockup")   # web/public pages (next.config.js rewrites)


@pytest.fixture(scope="module")
def data():
    return json.loads(PROJECT.read_text(encoding="utf-8"))


def _walk(o, path=""):
    """(path, dict) for every dict in the file."""
    if isinstance(o, dict):
        yield path, o
        for k, v in o.items():
            yield from _walk(v, f"{path}.{k}")
    elif isinstance(o, list):
        for i, v in enumerate(o):
            yield from _walk(v, f"{path}[{i}]")


def _sources(data):
    for p, d in _walk(data):
        for s in d.get("source") or []:
            yield p, s
    for s in data["money"].get("by_day_source", []):
        yield "money.by_day_source", s


def _hrefs(data):
    for p, d in _walk(data):
        for k in ("href", "pick_up"):
            v = d.get(k)
            if isinstance(v, str) and v.startswith("/"):
                yield p, v


def page_exists(href: str) -> bool:
    """Does this Desk link reach a page: a Next page (dynamic [x] segments allowed), a static page in public/, or an
    article view through /views/ (its run folder, when experiment 41's out/ is present)?"""
    path = href.split("#")[0].split("?")[0]
    parts = [p for p in path.split("/") if p]
    if not parts:
        return (WEB / "pages" / "index.tsx").exists()
    if parts[0] in STATIC:
        return (WEB / "public" / parts[0] / "index.html").exists() if len(parts) == 1 else (WEB / "public" / Path(*parts)).exists()
    if parts[0] == "views":
        views = REPO / "experiments" / "41_azure_structure" / "out" / "views"
        return not views.exists() or (views / parts[1]).exists()
    d = WEB / "pages"
    for i, seg in enumerate(parts):
        last = i == len(parts) - 1
        if last:
            if (d / f"{seg}.tsx").exists() or (d / seg / "index.tsx").exists():
                return True
            return any(f.name.startswith("[") for f in d.glob("*.tsx")) if d.exists() else False
        if (d / seg).is_dir():
            d = d / seg
        else:
            dyn = [x for x in d.iterdir() if x.is_dir() and x.name.startswith("[")] if d.exists() else []
            if not dyn:
                return False
            d = dyn[0]
    return False


def test_well_formed(data):
    for s in SECTIONS:
        assert s in data, s
    assert data["stage"]["current"] in {g["id"] for g in data["roadmap"]}
    for key in ("north_star", "picture", "timeline", "numbers", "decisions", "ideas", "waiting_on_owner",
                "next_steps", "roadmap", "where_things_live", "risks", "glossary", "source_notes"):
        assert data[key], key
        for i, item in enumerate(data[key]):
            assert isinstance(item.get("source"), list) and item["source"], f"{key}[{i}] has no source"
    for sec in ("headline", "stage"):
        assert data[sec]["source"], sec
    dates = [t["date"] for t in data["timeline"]]
    assert dates == sorted(dates, reverse=True), "timeline is newest first"
    for t in dates + [d["date"] for d in data["decisions"]] + [x["date"] for x in data["numbers"]]:
        assert re.fullmatch(r"\d{4}-\d\d-\d\d", t), t
    for i in data["ideas"]:
        assert i["status"] in {"done", "in progress", "open", "parked", "dropped"}, i["id"]
    for x in data["numbers"]:
        assert x["kind"] in {"measured", "estimate"}, x["id"]
    for s in data["next_steps"]:
        assert s["when"] in {"this week", "next", "later"}
    for w in data["waiting_on_owner"]:
        assert w["recommended"], w["id"]
    ids = [x["id"] for k in ("north_star", "picture", "numbers", "decisions", "ideas", "waiting_on_owner", "risks",
                             "roadmap") for x in data[k]]
    assert len(ids) == len(set(ids)), "ids are unique"


MAP_ITEMS = ("north_star", "timeline", "waiting_on_owner", "next_steps", "decisions", "ideas", "numbers",
             "where_things_live", "risks", "roadmap")   # the Map tab's labels (components/ProjectMap.tsx)


def test_every_map_item_has_a_short_label(data):
    """The Map tab shows each item by its `short` label, at most six words; the journey line shows each gate's
    `short` (what it proves), `cost_short` and `scope_short`."""
    def words(s):
        return len(s.split())
    bad = []
    items = [(k, i, x) for k in MAP_ITEMS for i, x in enumerate(data[k])]
    items += [("money.spent_by", i, x) for i, x in enumerate(data["money"]["spent_by"])]
    items += [("money.projections", i, x) for i, x in enumerate(data["money"]["projections"])]
    items += [("money.deadline", 0, data["money"]["deadline"]), ("money.not_priced", 0, data["money"]["not_priced"])]
    for k, i, x in items:
        s = x.get("short")
        if not isinstance(s, str) or not s.strip() or words(s) > 6:
            bad.append((k, i, s))
    for g in data["roadmap"]:
        for f in ("cost_short", "scope_short"):
            if not isinstance(g.get(f), str) or not g[f].strip() or words(g[f]) > 6:
                bad.append(("roadmap", g["id"], f, g.get(f)))
    assert not bad, bad
    assert (WEB / "components" / "ProjectMap.tsx").exists() and (WEB / "components" / "ProjectDetails.tsx").exists()


def test_sources_have_a_known_shape(data):
    for p, s in _sources(data):
        assert isinstance(s, str) and s.strip(), p
        if s.startswith("conversation"):
            assert re.match(r"conversation \d{4}-\d\d-\d\d \d\d:\d\d", s), (p, s)


def test_repo_paths_in_sources_exist(data):
    """Every repo-relative path a source names exists (skipping an experiment's out/ when that out/ is absent, as a
    fresh clone has none), and a #section on a Markdown file names a heading or a D-number there."""
    missing = []
    for p, s in _sources(data):
        if s.startswith(("conversation", "memory/", "git ", "/")):
            continue
        path = re.split(r" \(", s, 1)[0].strip()
        path, _, section = path.partition("#")
        f = REPO / path
        m = re.match(r"experiments/[^/]+/out/", path)
        if m and not (REPO / m.group(0)).exists():
            continue
        if not f.exists():
            missing.append((p, s))
            continue
        if section and f.suffix == ".md":
            text = f.read_text(encoding="utf-8")
            sec = section.strip()
            heads = [ln.lstrip("#").strip() for ln in text.splitlines() if ln.startswith("#")]
            ok = (any(h == sec or h.startswith(sec) for h in heads)
                  or (re.fullmatch(r"D\d+", sec) and f"**{sec} ·" in text)
                  or f"**{sec}" in text)
            if not ok:
                missing.append((p, s))
    assert not missing, missing


def test_every_desk_link_resolves(data):
    bad = [(p, h) for p, h in _hrefs(data) if not page_exists(h)]
    assert not bad, bad
    # and the nav item exists
    assert "href: '/project'" in (WEB / "components" / "Layout.tsx").read_text(encoding="utf-8")
    assert (WEB / "pages" / "project.tsx").exists()


def test_page_exists_refuses_unknown_pages():
    assert page_exists("/explore") and page_exists("/journals/J0130") and page_exists("/gate1/")
    assert not page_exists("/no-such-page") and not page_exists("/nosuch/static/x")


def test_api_serves_the_file_with_live_spend(schema, pg, tmp_path, monkeypatch):
    import hashlib
    add_actor(pg, "person:project-tester")
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
               (hashlib.sha256(b"tok-project-tester").hexdigest(), "person:project-tester"))
    pg.commit()
    log = tmp_path / "spend.jsonl"
    log.write_text('{"when": "2026-10-18 15:41:07", "usd": 1.25}\n{"when": "2026-10-22 15:55:27", "usd": 0.5}\n')
    monkeypatch.setenv("GEMINI_SPEND_LOG", str(log))
    from desk.api import app
    c = TestClient(app)
    assert c.get("/desk/api/project").status_code == 401
    r = c.get("/desk/api/project", headers={"X-Desk-Token": "tok-project-tester"})
    assert r.status_code == 200
    body = r.json()
    assert body["stage"]["current"] and body["live"]["spend"] == dict(
        usd=1.75, rows=2, first_entry="2026-10-18 15:41:07", last_entry="2026-10-22 15:55:27", log=str(log))
