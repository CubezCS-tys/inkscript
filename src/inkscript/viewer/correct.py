"""`inkscript view --gold GOLD_DIR`: the correction mode (experiment 34). The owner corrects the drafted gold pages
line by line in the browser instead of typing them: the line's crop of the scan, under it the draft text in an
editable field, the second reading and the low-confidence words marked; tables as an editable grid, equations as
LaTeX source, articles as regions clicked together.

    inkscript view --gold GOLD_DIR [--port 8766] [--host 127.0.0.1] [--open]

GOLD_DIR holds <page_id>.json (inkscript-gold/1, see inkscript.gold.format) beside <page_id>.jpg. The server
file is the truth: the app always loads from it and saves the whole page back after every accepted line.

    GET  /                       the app (app/correct.html, correct.js, correct.css; no external library or font)
    GET  /api/pages              one row per page (status, kinds, lines done, flagged lines, seconds)
    GET  /api/page/<page_id>     the page JSON
    POST /api/page/<page_id>     the page JSON back: checked (400 + problems), `rev` must be the one loaded (409 if
                                 another tab saved since), saved atomically, an event line in GOLD_DIR/.log.jsonl.
                                 Lines may come without `words` (Azure's words never change in the editor; they
                                 are taken from the file on disk, which keeps the request small)
    GET  /img/<page_id>.jpg      the page image
    GET  /api/progress           pages and lines done, hours spent, and an estimate of the hours left

The previous version goes to GOLD_DIR/.history/<page_id>/ at most every HISTORY_EVERY seconds (a save after
every line would otherwise keep ~60 KB per line: 0.5 GB over the set).
"""
from __future__ import annotations

import json
import statistics
import sys
import threading
import time
import urllib.parse
from http import HTTPStatus
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from ..gold import format as gf

APP = Path(__file__).with_name("app")
APP_FILES = {"correct.html": "text/html; charset=utf-8", "correct.js": "text/javascript; charset=utf-8",
             "correct.css": "text/css; charset=utf-8"}
JSON = "application/json; charset=utf-8"
HISTORY_EVERY = 300.0
MAX_BODY = 20 * 1024 * 1024
# before the owner has timed 30 lines: seconds per clean line, per flagged line, per page, per table cell, equation
PRIORS = dict(clean=2.0, flagged=8.5, page=35.0, cell=5.0, equation=60.0)   # experiment 34 estimate.py (expected case, dry run)
TABLE_STATUS = ("todo", "ok", "edited")


def _flagged(ln: dict) -> bool:
    return bool(ln.get("disagree") or ln.get("flags"))


def _cells(t: dict) -> int:
    h = (t.get("html") or t.get("draft_html") or "").lower()
    n = h.count("<td") + h.count("<th")
    return n or 4


class Gold:
    """The gold directory: reads (with a per-file summary cache), checked saves, progress and the estimate."""

    def __init__(self, gold_dir: Path):
        self.dir = Path(gold_dir)
        self.lock = threading.Lock()
        self._sum: dict[str, tuple[int, dict]] = {}

    def path(self, pid: str) -> Path:
        if not gf.valid_id(pid) or "/" in pid or "\\" in pid:
            raise KeyError(pid)
        p = self.dir / f"{pid}.json"
        if p.resolve().parent != self.dir.resolve():
            raise KeyError(pid)
        return p

    def image(self, pid: str) -> Path:
        p = self.path(pid).with_suffix(".jpg")
        if not p.exists():
            raise KeyError(pid)
        return p

    def ids(self) -> list[str]:
        return [p.stem for p in gf.pages(self.dir)]

    def summary(self, pid: str) -> dict:
        p = self.path(pid)
        m = p.stat().st_mtime_ns
        hit = self._sum.get(pid)
        if hit and hit[0] == m:
            return hit[1]
        g = gf.load(p)
        lines = g.get("lines", [])
        s = dict(page_id=pid, status=g.get("status", "todo"), primary=g.get("primary", ""),
                 kinds=g.get("kinds", []), decade=g.get("decade", ""), journal=g.get("journal", ""),
                 year=g.get("year", ""), split=g.get("split", ""), lines=len(lines),
                 lines_done=sum(1 for ln in lines if ln.get("status") != "todo"),
                 flagged=sum(1 for ln in lines if _flagged(ln)),
                 tables=len(g.get("tables", [])), equations=len(g.get("equations", [])),
                 seconds=round(float(g.get("seconds", 0.0)), 1), rev=g.get("rev", 0),
                 _lines=[(float(ln.get("seconds", 0.0) or 0.0), _flagged(ln), ln.get("status", "todo"))
                         for ln in lines],
                 _cells_todo=sum(_cells(t) for t in g.get("tables", []) if t.get("status", "todo") == "todo"),
                 _eq_todo=sum(1 for e in g.get("equations", []) if e.get("status", "todo") == "todo"))
        self._sum[pid] = (m, s)
        return s

    def rows(self) -> list[dict]:
        out = []
        for pid in self.ids():
            try:
                s = self.summary(pid)
            except Exception as e:                   # a broken file shows as a row, not a dead start screen
                out.append(dict(page_id=pid, status="error", error=f"{type(e).__name__}: {e}"))
                continue
            out.append({k: v for k, v in s.items() if not k.startswith("_")})
        return out

    def page(self, pid: str) -> bytes:
        p = self.path(pid)
        if not p.exists():
            raise KeyError(pid)
        return p.read_bytes()

    def save(self, pid: str, body: bytes) -> tuple[int, dict]:
        """(http status, answer) for a POSTed page."""
        try:
            g = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as e:
            return 400, dict(error="not JSON", problems=[str(e)])
        if not isinstance(g, dict):
            return 400, dict(error="not a page", problems=["the body is not a JSON object"])
        if g.get("page_id") != pid:
            return 400, dict(error="page_id mismatch", problems=[f"{g.get('page_id')!r} posted to {pid!r}"])
        p = self.path(pid)
        with self.lock:
            if not p.exists():
                return 404, dict(error="no such page")
            cur = gf.load(p)
            rev = int(cur.get("rev", 0) or 0)
            if int(g.get("rev", 0) or 0) != rev:
                return 409, dict(error="stale", rev=rev,
                                 problems=["this page was saved from another tab or window since it was loaded"])
            words = {ln.get("id"): ln.get("words", []) for ln in cur.get("lines", [])}
            for ln in g.get("lines", []) if isinstance(g.get("lines"), list) else []:
                if isinstance(ln, dict) and "words" not in ln:
                    ln["words"] = words.get(ln.get("id"), [])
            problems = gf.check(g) + extra_checks(g)
            if problems:
                return 400, dict(error="invalid page", problems=problems)
            g["rev"] = rev + 1
            gf.save(p, g, history=self._history_due(pid))
            done = sum(1 for ln in g["lines"] if ln.get("status") != "todo")
            ev = dict(when=time.strftime("%Y-%m-%dT%H:%M:%S"), page_id=pid, lines_done=done,
                      seconds=round(float(g.get("seconds", 0.0)), 1), status=g.get("status"), rev=g["rev"])
            with open(self.dir / ".log.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(ev, ensure_ascii=False) + "\n")
        return 200, dict(ok=True, rev=g["rev"], lines_done=done)

    def _history_due(self, pid: str) -> bool:
        h = self.dir / ".history" / pid
        if not h.exists():
            return True
        last = max((f.stat().st_mtime for f in h.glob("*.json")), default=0.0)
        return time.time() - last >= HISTORY_EVERY

    def progress(self) -> dict:
        pr = gf.progress(self.dir)
        pr["hours"] = round(pr["seconds"] / 3600, 2)
        pr["estimate"] = self.estimate()
        return pr

    def estimate(self) -> dict:
        sums = []
        for pid in self.ids():
            try:
                sums.append(self.summary(pid))
            except Exception:
                continue
        timed = [(sec, fl) for s in sums for sec, fl, st in s["_lines"] if sec > 0 and st != "todo"]
        basis = "own" if len(timed) >= 30 else "prior"
        clean, flagged, page = PRIORS["clean"], PRIORS["flagged"], PRIORS["page"]
        if basis == "own":
            c = [t for t, fl in timed if not fl]
            f = [t for t, fl in timed if fl]
            clean = statistics.median(c) if len(c) >= 5 else clean
            flagged = statistics.median(f) if len(f) >= 5 else flagged
            over = [max(0.0, s["seconds"] - sum(t for t, _, _ in s["_lines"])) for s in sums
                    if s["status"] == "done" and s["seconds"] > 0]
            page = statistics.median(over) if over else page
        left = [s for s in sums if s["status"] not in ("done", "skip")]
        lc = sum(1 for s in left for _, fl, st in s["_lines"] if st == "todo" and not fl)
        lf = sum(1 for s in left for _, fl, st in s["_lines"] if st == "todo" and fl)
        cells = sum(s["_cells_todo"] for s in left)
        eqs = sum(s["_eq_todo"] for s in left)
        secs = lc * clean + lf * flagged + len(left) * page + cells * PRIORS["cell"] + eqs * PRIORS["equation"]
        return dict(basis=basis, timed_lines=len(timed), seconds_left=round(secs), hours_left=round(secs / 3600, 1),
                    per_clean_line=round(clean, 1), per_flagged_line=round(flagged, 1), per_page=round(page, 1),
                    per_table_cell=PRIORS["cell"], per_equation=PRIORS["equation"], pages_left=len(left),
                    lines_left_clean=lc, lines_left_flagged=lf, table_cells_left=cells, equations_left=eqs)


def extra_checks(g: dict) -> list[str]:
    """What format.check does not look at but the editor writes: tables, equations, regions, articles."""
    out = []
    for k, st in (("tables", TABLE_STATUS), ("equations", TABLE_STATUS)):
        items = g.get(k, [])
        if not isinstance(items, list):
            out.append(f"{k} is not a list")
            continue
        for t in items:
            if not isinstance(t, dict) or t.get("status", "todo") not in st:
                out.append(f"{k}: {t.get('id') if isinstance(t, dict) else t!r}: bad item or status")
    rids = [r.get("id") for r in g.get("regions", []) if isinstance(r, dict)]
    if len(set(rids)) != len(rids):
        out.append("duplicate region ids")
    for a in g.get("articles", []) or []:
        if not isinstance(a, dict) or any(r not in rids for r in a.get("regions", [])):
            out.append(f"article {a.get('id') if isinstance(a, dict) else a!r} names a region that does not exist")
    if not isinstance(g.get("seconds", 0.0), (int, float)):
        out.append("seconds is not a number")
    return out


def _json(obj) -> bytes:
    return json.dumps(obj, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def make_handler(gold: Gold):
    class H(BaseHTTPRequestHandler):
        server_version = "inkscript-correct"

        def log_message(self, fmt, *args):
            if args and str(args[1]).startswith(("4", "5")):
                sys.stderr.write("correct: " + fmt % args + "\n")

        def send(self, body: bytes, ctype: str, status=HTTPStatus.OK, cache=False):
            self.send_response(status)
            self.send_header("Content-Type", ctype)
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "max-age=86400" if cache else "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if self.command != "HEAD":
                self.wfile.write(body)

        def fail(self, status, msg: str, **kw):
            self.send(_json(dict(error=msg, **kw)), JSON, status)

        def route(self) -> str:
            return urllib.parse.unquote(urllib.parse.urlsplit(self.path).path).lstrip("/")

        def do_HEAD(self):
            self.do_GET()

        def do_GET(self):
            path = self.route()
            try:
                if path in ("", "index.html", "correct.html"):
                    return self.send((APP / "correct.html").read_bytes(), APP_FILES["correct.html"])
                if path in APP_FILES:
                    return self.send((APP / path).read_bytes(), APP_FILES[path])
                if path == "api/pages":
                    return self.send(_json(dict(pages=gold.rows(), gold_dir=str(gold.dir))), JSON)
                if path == "api/progress":
                    return self.send(_json(gold.progress()), JSON)
                if path.startswith("api/page/"):
                    return self.send(gold.page(path[len("api/page/"):]), JSON)
                if path.startswith("img/") and path.endswith(".jpg"):
                    return self.send(gold.image(path[4:-4]).read_bytes(), "image/jpeg", cache=True)
            except KeyError as e:
                return self.fail(HTTPStatus.NOT_FOUND, f"not found: {e}")
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                return self.fail(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
            self.fail(HTTPStatus.NOT_FOUND, "not found")

        def do_POST(self):
            path = self.route()
            try:
                if not path.startswith("api/page/"):
                    return self.fail(HTTPStatus.NOT_FOUND, "not found")
                pid = path[len("api/page/"):]
                gold.path(pid)
                n = int(self.headers.get("Content-Length") or 0)
                if n <= 0 or n > MAX_BODY:
                    return self.fail(HTTPStatus.BAD_REQUEST, "empty or too large body")
                body = self.rfile.read(n)
                status, ans = gold.save(pid, body)
                return self.send(_json(ans), JSON, status)
            except KeyError as e:
                return self.fail(HTTPStatus.NOT_FOUND, f"not found: {e}")
            except (BrokenPipeError, ConnectionResetError):
                return
            except Exception as e:
                return self.fail(HTTPStatus.INTERNAL_SERVER_ERROR, f"{type(e).__name__}: {e}")
    return H


def server(gold_dir, host="127.0.0.1", port=8766) -> ThreadingHTTPServer:
    httpd = ThreadingHTTPServer((host, port), make_handler(Gold(gold_dir)))
    httpd.daemon_threads = True
    return httpd


def main(a) -> int:
    gold_dir = Path(a.gold).expanduser()
    if not gold_dir.is_dir() or not gf.pages(gold_dir):
        print(f"no <page_id>.json gold pages in {gold_dir}")
        return 1
    port = 8766 if a.port is None else a.port
    httpd = server(gold_dir, a.host, port)
    url = f"http://{'localhost' if a.host in ('0.0.0.0', '', '127.0.0.1') else a.host}:{httpd.server_address[1]}/"
    print(f"{len(gf.pages(gold_dir))} gold page(s) in {gold_dir}\nopen {url}   (Ctrl+C to stop; from Windows, if "
          f"localhost does not reach WSL, restart with --host 0.0.0.0 and use this machine's address)", flush=True)
    if a.open:
        import webbrowser
        webbrowser.open(url)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        httpd.server_close()
    return 0
