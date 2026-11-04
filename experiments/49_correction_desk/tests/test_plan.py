"""The plan page (/plan, 2026-11-02): desk/plan/plan.json is valid (lanes, statuses, times, a source on every item,
titles of at most six words and 40 characters), every Desk link in it resolves and every write-up it names exists;
desk/plan_cli.py round-trips every command (as a module and as a script), its writes are atomic and locked (parallel
writers lose nothing), a heartbeat shows as "last seen" and its absence marks a running item stalled; the API serves
the file with live releases, and only an admin can add an item, which lands in the log with the admin's id."""
from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from conftest import add_actor
from test_project import page_exists

HERE = Path(__file__).resolve().parent
DESK = HERE.parent
REPO = DESK.parents[1]
PLAN = DESK / "desk" / "plan" / "plan.json"
PY = sys.executable

from desk import plan_cli  # noqa: E402


@pytest.fixture(scope="module")
def data():
    return json.loads(PLAN.read_text(encoding="utf-8"))


def test_the_file_is_valid(data):
    assert plan_cli.validate(data) == []
    assert [l["key"] for l in data["lanes"]][0] == "needs_you"
    keys = {l["key"] for l in data["lanes"]}
    assert {"extraction", "reconciliation", "platform", "evals", "docs", "needs_you"} <= keys
    for it in data["items"]:
        assert len(it["title"].split()) <= 6 and len(it["title"]) <= 40, it["id"]
        assert it["source"], it["id"]
    st = {it["status"] for it in data["items"]}
    assert {"running", "done", "planned", "blocked-on-owner"} <= st


def test_experiments_43_to_65_are_covered(data):
    """Every experiment from 44 to 65 that has a folder is on the plan (43 through its runs: the exam, v3.5b…)."""
    exps = {it.get("exp") for it in data["items"]}
    for d in sorted((REPO / "experiments").glob("[4-6][0-9]_*")):
        n = int(d.name[:2])
        if 44 <= n <= 65 and n != 46:   # 46 was superseded by 47 the same day
            assert str(n) in exps, d.name
    assert "43" in exps


def test_every_desk_link_resolves(data):
    bad = []
    for it in data["items"]:
        bad += [(it["id"], ln["href"]) for ln in it.get("links") or [] if not page_exists(ln["href"])]
    bad += [(m["id"], m["href"]) for m in data["markers"] if m.get("href") and not page_exists(m["href"])]
    assert not bad, bad
    assert "href: '/plan'" in (DESK / "web" / "components" / "Layout.tsx").read_text(encoding="utf-8")
    assert (DESK / "web" / "pages" / "plan.tsx").exists()


def test_every_write_up_and_watched_folder_exists(data):
    for it in data["items"]:
        for k in ("readme", "watch"):
            if it.get(k):
                assert (REPO / it[k]).exists(), (it["id"], it[k])
        for k in ("after", "waits_on"):
            if it.get(k):
                assert any(x["id"] == it[k] for x in data["items"]), (it["id"], k, it[k])


def _cli(tmp, *args, script=False):
    env = dict(os.environ, PLAN_DIR=str(tmp), PLAN_BY="agent:test")
    cmd = [PY, str(DESK / "desk" / "plan_cli.py")] if script else [PY, "-m", "desk.plan_cli"]
    r = subprocess.run(cmd + list(args), cwd=DESK, env=env, capture_output=True, text=True)
    return r


def test_cli_round_trip(tmp_path):
    ok = lambda r: (r.returncode == 0) or pytest.fail(r.stderr)  # noqa: E731
    ok(_cli(tmp_path, "plan", "x1", "A planned piece", "--lane", "extraction", "--desc", "one line", "--link", "Audit=/audit",
            "--start", "2026-11-03T09:00", "--end", "+2d"))
    ok(_cli(tmp_path, "start", "x1", "--watch", "experiments/49_correction_desk", script=True))
    ok(_cli(tmp_path, "beat", "x1", "--note", "half way"))
    ok(_cli(tmp_path, "finish", "x1", "--outcome", "it worked", "--cost", "$0"))
    ok(_cli(tmp_path, "set", "x1", "--clear", "planned_start", "--clear", "planned_end"))
    ok(_cli(tmp_path, "needs-you", "add", "n1", "Say yes or no", "--question", "Shall we?", "--urgency", "soon"))
    ok(_cli(tmp_path, "needs-you", "resolve", "n1", "--outcome", "yes"))
    ok(_cli(tmp_path, "promise", "add", "p1", "Send the result", "--due", "+6h", "--item", "x1"))
    ok(_cli(tmp_path, "promise", "keep", "p1", "--outcome", "sent"))
    ok(_cli(tmp_path, "add-marker", "eval", "Result: 99%", "--href", "/audit", "--item", "x1"))
    assert ok(_cli(tmp_path, "check"))
    d = json.loads((tmp_path / "plan.json").read_text())
    x1 = next(i for i in d["items"] if i["id"] == "x1")
    assert x1["status"] == "done" and x1["outcome"] == "it worked" and x1["start"] and x1["end"]
    assert "planned_start" not in x1 and x1["links"] == [{"label": "Audit", "href": "/audit"}]
    n1 = next(i for i in d["items"] if i["id"] == "n1")
    assert n1["lane"] == "needs_you" and n1["status"] == "done" and n1["outcome"] == "yes"
    assert d["promises"][0]["status"] == "kept" and d["markers"][0]["kind"] == "eval"
    assert [e["action"] for e in d["log"]][:3] == ["plan", "start", "finish:done"] and all(e["by"] == "agent:test" for e in d["log"])
    assert json.loads((tmp_path / "beats" / "x1.json").read_text())["note"] == "half way"
    # refusals: a title over six words, an unknown id, a bad time
    assert _cli(tmp_path, "start", "x2", "one two three four five six seven", "--lane", "docs").returncode == 2
    assert _cli(tmp_path, "finish", "nope").returncode == 2
    assert _cli(tmp_path, "plan", "x3", "Bad time", "--lane", "docs", "--start", "tomorrowish").returncode == 2
    assert not list(tmp_path.glob(".plan.*.tmp")), "no temp files left behind"


def _add_marker(args):
    tmp, i = args
    os.environ["PLAN_DIR"] = tmp
    plan_cli.add_marker("eval", f"parallel {i}", by=f"agent:w{i}")


def test_parallel_writers_lose_nothing(tmp_path):
    with ProcessPoolExecutor(6) as ex:
        list(ex.map(_add_marker, [(str(tmp_path), i) for i in range(24)]))
    d = json.loads((tmp_path / "plan.json").read_text())
    assert sorted(m["label"] for m in d["markers"]) == sorted(f"parallel {i}" for i in range(24))
    assert len({m["id"] for m in d["markers"]}) == 24 and len(d["log"]) == 24


@pytest.fixture()
def client(schema, pg, tmp_path, monkeypatch):
    for aid, role in (("person:plan-admin", "admin"), ("person:plan-reader", "corrector")):
        add_actor(pg, aid, role=role)
        pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s) ON CONFLICT DO NOTHING",
                   (hashlib.sha256(f"tok-{aid}".encode()).hexdigest(), aid))
    pg.commit()
    monkeypatch.setenv("PLAN_DIR", str(tmp_path / "plan"))
    rel = tmp_path / "releases"
    (rel / "summaries").mkdir(parents=True)
    (rel / "R20261102T155701.db").write_bytes(b"")
    (rel / "summaries" / "R20261023T005909.json").write_text("{}")
    monkeypatch.setenv("DESK_RELEASES", str(rel))
    monkeypatch.setenv("DESK_WEB_LIVE", str(tmp_path / "no-web-live"))
    plan_cli.start("run1", "A running piece", "platform", by="agent:test", at="-3h")
    plan_cli.start("run2", "Another running piece", "platform", by="agent:test", at="-3h")
    plan_cli.beat("run2", by="agent:test", note="alive")
    plan_cli.promise_add("late", "An overdue promise", "-1h", by="agent:test")
    from desk.api import app   # first: desk.plan imports from desk.api
    from desk import plan as plan_api
    plan_api._cache.clear()
    return TestClient(app)


def test_api_serves_the_plan_with_live_signals(client):
    assert client.get("/desk/api/plan").status_code == 401
    r = client.get("/desk/api/plan", headers={"X-Desk-Token": "tok-person:plan-reader"})
    assert r.status_code == 200, r.text
    b = r.json()
    assert abs(b["now"] - time.time()) < 60 and b["problems"] == []
    assert [x["id"] for x in b["live"]["releases"]] == ["R20261023T005909", "R20261102T155701"]
    assert b["live"]["releases"][-1]["live"] and b["live"]["releases"][-1]["at"] == 1793635021.0
    assert b["live"]["stale"] == ["run1"] and b["live"]["activity"]["run2"]["source"] == "beat"
    assert b["live"]["overdue"] == ["late"]
    assert b["counts"]["running"] == 2 and b["counts"]["stale"] == 1 and b["counts"]["overdue"] == 1


def test_only_admins_add_items_and_the_log_says_who(client):
    body = dict(kind="work", title="Try the new thing", lane="evals", status="planned", desc="one line",
                link_label="Open", link_href="/audit")
    h = {"X-Desk-Token": "tok-person:plan-reader"}
    assert client.post("/desk/api/plan/items", json=body, headers=h).status_code == 403
    h = {"X-Desk-Token": "tok-person:plan-admin"}
    r = client.post("/desk/api/plan/items", json=body, headers=h)
    assert r.status_code == 201, r.text
    assert r.json()["id"] == "try-the-new-thing"
    assert client.post("/desk/api/plan/items", json=dict(body, id="try-the-new-thing"), headers=h).status_code == 409
    assert client.post("/desk/api/plan/items", json=dict(kind="needs_you", title="A question for you", urgency="soon"), headers=h).status_code == 201
    assert client.post("/desk/api/plan/items", json=dict(kind="promise", title="We will send it", due="+1d"), headers=h).status_code == 201
    too_long = client.post("/desk/api/plan/items", json=dict(body, title="one two three four five six seven"), headers=h)
    assert too_long.status_code == 422
    d = plan_cli.read_plan()
    assert [e["by"] for e in d["log"][-3:]] == ["person:plan-admin"] * 3
    it = next(i for i in d["items"] if i["id"] == "try-the-new-thing")
    assert it["added_by"] == "person:plan-admin" and it["source"] == ["added in the Desk by person:plan-admin"]
