"""`inkscript view --gold` (experiment 34): the correction mode's server. A fixture page drafted into a gold dir,
the server started on a free port; pages listed, a page read, corrected and saved back, history and log kept,
bad ids / path tricks / a wrong page_id / broken JSON / a stale revision refused, progress moving, the app served."""
import json
import shutil
import subprocess
import threading
import urllib.error
import urllib.request
from pathlib import Path

import pytest

from inkscript.gold import format as gf
from inkscript.gold.draft import write_pages
from inkscript.viewer import correct

APP = Path(correct.__file__).with_name("app")


@pytest.fixture(scope="module")
def gold(fixture, tmp_path_factory):
    d = tmp_path_factory.mktemp("gold")
    azure = fixture["azure_dir"] / fixture["stem"] / f"{fixture['stem']}.json"
    ids = write_pages(azure, fixture["scan"], [2], d, dict(stem=fixture["stem"], split="dev", primary="body",
                                                            kinds=["body"]), dpi=100)
    assert ids == [f"{fixture['stem']}_p002"]
    return d


@pytest.fixture(scope="module")
def url(gold):
    httpd = correct.server(gold, "127.0.0.1", 0)
    t = threading.Thread(target=httpd.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{httpd.server_address[1]}/"
    httpd.shutdown()
    httpd.server_close()


def call(url, path, body=None, raw=None):
    data = raw if raw is not None else (json.dumps(body, ensure_ascii=False).encode() if body is not None else None)
    req = urllib.request.Request(url + path, data=data, method="POST" if data is not None else "GET",
                                 headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=20) as r:
            return r.status, r.read(), r.headers
    except urllib.error.HTTPError as e:
        return e.code, e.read(), e.headers


def jcall(url, path, body=None, raw=None):
    st, b, _ = call(url, path, body, raw)
    return st, json.loads(b)


def test_app_files_served(url):
    for path, needle in (("", b"correct.js"), ("correct.js", b"function accept"), ("correct.css", b".txt")):
        st, body, h = call(url, path)
        assert st == 200 and needle in body, path
    assert call(url, "../../etc/passwd")[0] == 404
    assert call(url, "app.js")[0] == 404              # only the correction app and the gold dir are served


def test_pages_and_page(url, fixture):
    st, rows = jcall(url, "api/pages")
    assert st == 200
    (row,) = rows["pages"]
    pid = f"{fixture['stem']}_p002"
    assert row["page_id"] == pid and row["status"] == "todo" and row["lines"] > 10 and row["lines_done"] == 0
    assert set(row) >= {"primary", "kinds", "decade", "journal", "year", "split", "flagged", "seconds"}
    st, g = jcall(url, f"api/page/{pid}")
    assert st == 200 and g["page_id"] == pid and g["lines"][0]["words"]
    st, img, h = call(url, f"img/{pid}.jpg")
    assert st == 200 and img[:2] == b"\xff\xd8" and "max-age" in h["Cache-Control"]


def test_save_roundtrip_history_log_progress(url, gold, fixture):
    pid = f"{fixture['stem']}_p002"
    _, p0 = jcall(url, "api/progress")
    assert p0["lines_done"] == 0 and p0["estimate"]["basis"] == "prior" and p0["estimate"]["seconds_left"] > 0
    _, g = jcall(url, f"api/page/{pid}")
    g["status"] = "doing"
    g["seconds"] = 12.0
    g["lines"][0]["status"] = "ok"
    g["lines"][0]["seconds"] = 3
    g["lines"][1]["text"] = g["lines"][1]["text"] + " زيادة"
    g["lines"][1]["status"] = "edited"
    for ln in g["lines"]:                             # the app sends lines without Azure's words
        ln.pop("words")
    st, ans = jcall(url, f"api/page/{pid}", g)
    assert st == 200 and ans["ok"] and ans["rev"] == 1 and ans["lines_done"] == 2
    _, g2 = jcall(url, f"api/page/{pid}")
    assert g2["rev"] == 1 and g2["lines"][1]["text"].endswith("زيادة") and g2["lines"][1]["status"] == "edited"
    assert g2["lines"][0]["words"], "Azure's words are kept from the file"
    assert list((gold / ".history" / pid).glob("*.json")), "the previous version is kept"
    log = [json.loads(x) for x in (gold / ".log.jsonl").read_text(encoding="utf-8").splitlines()]
    assert log[-1]["page_id"] == pid and log[-1]["lines_done"] == 2 and log[-1]["seconds"] == 12.0
    _, p1 = jcall(url, "api/progress")
    assert p1["lines_done"] == 2 and p1["seconds"] == 12.0
    assert p1["estimate"]["seconds_left"] < p0["estimate"]["seconds_left"]
    _, rows = jcall(url, "api/pages")
    assert rows["pages"][0]["lines_done"] == 2 and rows["pages"][0]["status"] == "doing"

    # a stale revision (another tab saved since) is refused, and nothing is written
    g["rev"] = 0
    g["lines"][2]["status"] = "ok"
    st, ans = jcall(url, f"api/page/{pid}", g)
    assert st == 409 and ans["rev"] == 1
    assert gf.load(gold / f"{pid}.json")["lines"][2]["status"] == "todo"


def test_refusals(url, gold, fixture):
    pid = f"{fixture['stem']}_p002"
    _, g = jcall(url, f"api/page/{pid}")
    before = (gold / f"{pid}.json").read_bytes()
    assert call(url, "api/page/nonsense")[0] == 404
    assert call(url, "api/page/..%2F..%2Fetc%2Fpasswd")[0] == 404
    assert call(url, "img/..%2Fx_p001.jpg")[0] == 404
    assert call(url, "api/page/nonsense", g)[0] == 404
    st, ans = jcall(url, f"api/page/{pid}", raw=b"{not json")
    assert st == 400 and ans["error"] == "not JSON"
    other = dict(g, page_id=f"{fixture['stem']}_p003")
    st, ans = jcall(url, f"api/page/{pid}", other)
    assert st == 400 and "mismatch" in ans["error"]
    bad = json.loads(json.dumps(g))
    bad["lines"][0]["status"] = "great"
    bad["order"] = bad["order"][1:]
    st, ans = jcall(url, f"api/page/{pid}", bad)
    assert st == 400 and any("status" in p for p in ans["problems"]) and any("order" in p for p in ans["problems"])
    assert (gold / f"{pid}.json").read_bytes() == before


def test_estimate_uses_own_times(tmp_path, gold, fixture):
    pid = f"{fixture['stem']}_p002"
    for f in gold.glob("*.jpg"):
        shutil.copy(f, tmp_path)
    g = gf.load(gold / f"{pid}.json")
    for i, ln in enumerate(g["lines"]):
        ln["status"], ln["seconds"] = "ok", 4.0
    g["status"], g["seconds"] = "done", 4.0 * len(g["lines"]) + 30
    gf.save(tmp_path / f"{pid}.json", g, history=False)
    g2 = json.loads(json.dumps(g))
    g2["page_id"] = f"{fixture['stem']}_p009"
    for ln in g2["lines"]:
        ln["status"], ln["seconds"] = "todo", 0
    g2["status"] = "todo"
    gf.save(tmp_path / f"{g2['page_id']}.json", g2, history=False)
    e = correct.Gold(tmp_path).estimate()
    assert len(g["lines"]) >= 30
    assert e["basis"] == "own" and e["per_clean_line"] == 4.0 and e["per_page"] == 30.0
    clean = sum(1 for ln in g2["lines"] if not correct._flagged(ln))
    flagged = len(g2["lines"]) - clean
    per_flagged = 4.0 if sum(1 for ln in g["lines"] if correct._flagged(ln)) >= 5 else correct.PRIORS["flagged"]
    assert e["seconds_left"] == round(30 + 4.0 * clean + per_flagged * flagged)


def test_cli_parser_accepts_gold(monkeypatch, gold):
    from inkscript import cli
    seen = {}
    monkeypatch.setattr(correct, "main", lambda a: seen.update(gold=a.gold, port=a.port, out=a.out_dir) or 0)
    assert cli.main(["view", "--gold", str(gold)]) == 0
    assert seen == dict(gold=str(gold), port=8766, out=None)
    assert cli.main(["view"]) == 2


@pytest.mark.skipif(shutil.which("node") is None, reason="node not installed")
def test_js_parses():
    r = subprocess.run(["node", "--check", str(APP / "correct.js")], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
