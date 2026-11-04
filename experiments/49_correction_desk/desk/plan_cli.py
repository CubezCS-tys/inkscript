"""The plan (/plan, 2026-11-02): one file, desk/plan/plan.json, that says what is running, what is live, what is done,
what waits on the owner, what we promised and what comes next. This module is the ONLY writer of that file: the lead
and the agents use it from the shell, and the Desk's "Add item" (admins only, desk/plan.py) calls the same functions.

    .venv/bin/python -m desk.plan_cli start  exp66 "Cited works applied" --lane reconciliation --desc "…" \
        --readme experiments/66_x/README.md --link Librarian=/librarian
    .venv/bin/python -m desk.plan_cli beat   exp66 --note "batch 3 of 9"          # "last seen" on the running bar
    .venv/bin/python -m desk.plan_cli finish exp66 --outcome "1,200 decisions applied" [--status live] [--cost '$0']
    .venv/bin/python -m desk.plan_cli plan   gate2-pilot "Gate 2: one-journal pilot" --lane extraction \
        [--start 2026-11-03T09:00 --end 2026-11-03T18:00] [--after rebuild65] [--cost "about $40"]
    .venv/bin/python -m desk.plan_cli set    gate2-pilot --status parked --outcome "waiting for credits"
    .venv/bin/python -m desk.plan_cli needs-you add go-d30 "Go for the D30 guard?" --question "…" --urgency soon
    .venv/bin/python -m desk.plan_cli needs-you resolve go-d30 --outcome "owner: yes"
    .venv/bin/python -m desk.plan_cli promise add send-audit "Send the owner the re-audit" --due +6h [--item reaudit]
    .venv/bin/python -m desk.plan_cli promise keep send-audit [--outcome "sent"]   |  promise drop send-audit
    .venv/bin/python -m desk.plan_cli add-marker eval "Re-audit: 99.9% in a field" [--at now] [--href /audit]
    .venv/bin/python -m desk.plan_cli list [--status running]   |   show <id>   |   check

Times: "now", "+2h" / "-30m" / "+1d", or ISO ("2026-11-02T14:00", read as the server's local time when it has no
offset; "…Z" or "…+00:00" for UTC). Stored as ISO with the server's offset. Every write takes a lock
(plan.json.lock, fcntl), re-reads the file, writes a temp file and renames it over (atomic), and appends who / when /
what to the file's `log`. Beats are separate small files (desk/plan/beats/<id>.json) so a heartbeat never rewrites
the plan. Env: PLAN_DIR (default desk/plan), PLAN_BY (who is writing; default $USER).
"""
from __future__ import annotations

import argparse
import contextlib
import fcntl
import json
import os
import re
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path

HERE = Path(__file__).resolve().parent

LANES = [
    dict(key="needs_you", label="Needs you", sub="waiting on the owner"),
    dict(key="extraction", label="Extraction (islands)", sub="reading each article"),
    dict(key="reconciliation", label="Reconciliation (bridges)", sub="joining people, places, works"),
    dict(key="platform", label="Platform & Desk", sub="where it is kept and shown"),
    dict(key="evals", label="Evaluations & vendors", sub="tests, trials, audits"),
    dict(key="docs", label="Docs & shareholders", sub="writing it down"),
]
LANE_KEYS = [l["key"] for l in LANES]
STATUSES = ["planned", "running", "done", "live", "parked", "dropped", "blocked-on-owner"]
PROMISE_STATUSES = ["open", "kept", "dropped"]
MARKER_KINDS = ["release", "deploy", "eval", "alert", "milestone"]
ID_RE = re.compile(r"^[a-z0-9][a-z0-9._-]{0,47}$")
TITLE_MAX_WORDS, TITLE_MAX_CHARS = 6, 40


class PlanError(Exception):
    pass


# ------------------------------------------------------------------ files

def plan_dir() -> Path:
    return Path(os.environ.get("PLAN_DIR", str(HERE / "plan")))


def plan_path() -> Path:
    return plan_dir() / "plan.json"


def beats_dir() -> Path:
    return plan_dir() / "beats"


def empty_plan() -> dict:
    return dict(meta=dict(title="The plan", updated_at=None), lanes=LANES, items=[], promises=[], markers=[], log=[])


def read_plan(path: Path | None = None) -> dict:
    p = path or plan_path()
    if not p.exists():
        return empty_plan()
    return json.loads(p.read_text(encoding="utf-8"))


def write_atomic(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(prefix=".plan.", suffix=".tmp", dir=str(path.parent))
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=1)
            f.write("\n")
            f.flush()
            os.fsync(f.fileno())
        os.chmod(tmp, 0o664)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise


@contextlib.contextmanager
def locked_plan(by: str, action: str, target: str | None = None):
    """Lock, read, yield the plan for changes, validate, append to the log, write atomically."""
    p = plan_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(str(p) + ".lock", "a+") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)
        try:
            data = read_plan(p)
            yield data
            at = iso(now())
            data.setdefault("meta", {})["updated_at"] = at
            data.setdefault("log", []).append(dict(at=at, by=by, action=action, id=target))
            problems = validate(data)
            if problems:
                raise PlanError("the plan would not be valid: " + "; ".join(problems[:5]))
            write_atomic(p, data)
        finally:
            fcntl.flock(lk, fcntl.LOCK_UN)


# ------------------------------------------------------------------ time

def local_tz():
    return datetime.now().astimezone().tzinfo


def now() -> datetime:
    return datetime.now().astimezone()


def iso(d: datetime) -> str:
    return d.astimezone(local_tz()).isoformat(timespec="minutes")


def parse_time(s: str | None) -> str | None:
    """'now', '+2h', '-30m', '+1d', or ISO (no offset = server local) -> ISO with offset; None stays None."""
    if s is None or s == "":
        return None
    s = s.strip()
    if s == "now":
        return iso(now())
    m = re.fullmatch(r"([+-])(\d+(?:\.\d+)?)([mhd])", s)
    if m:
        n = float(m.group(2)) * (-1 if m.group(1) == "-" else 1)
        delta = dict(m=timedelta(minutes=n), h=timedelta(hours=n), d=timedelta(days=n))[m.group(3)]
        return iso(now() + delta)
    try:
        d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    except ValueError as e:
        raise PlanError(f"cannot read the time {s!r} (use now, +2h, -30m, +1d or 2026-11-02T14:00)") from e
    if d.tzinfo is None:
        d = d.replace(tzinfo=local_tz())
    return iso(d)


def to_epoch(s: str | None) -> float | None:
    if not s:
        return None
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=local_tz())
    return d.timestamp()


# ------------------------------------------------------------------ validation

def _check_title(t, where):
    if not isinstance(t, str) or not t.strip():
        return [f"{where}: no title"]
    out = []
    if len(t.split()) > TITLE_MAX_WORDS:
        out.append(f"{where}: title has more than {TITLE_MAX_WORDS} words ({t!r})")
    if len(t) > TITLE_MAX_CHARS:
        out.append(f"{where}: title longer than {TITLE_MAX_CHARS} characters ({t!r})")
    return out


def validate(data: dict) -> list[str]:
    """Every problem with the plan, as plain sentences (empty = valid)."""
    out: list[str] = []
    for k in ("items", "promises", "markers", "lanes"):
        if not isinstance(data.get(k), list):
            out.append(f"'{k}' must be a list")
    if out:
        return out
    lane_keys = {l.get("key") for l in data["lanes"]}
    seen: set[str] = set()
    for i, it in enumerate(data["items"]):
        w = f"item {it.get('id', i)}"
        if not ID_RE.match(str(it.get("id", ""))):
            out.append(f"{w}: bad id")
        if it.get("id") in seen:
            out.append(f"{w}: id used twice")
        seen.add(it.get("id"))
        out += _check_title(it.get("title"), w)
        if it.get("lane") not in lane_keys:
            out.append(f"{w}: unknown lane {it.get('lane')!r}")
        if it.get("status") not in STATUSES:
            out.append(f"{w}: unknown status {it.get('status')!r}")
        for k in ("planned_start", "planned_end", "start", "end"):
            if it.get(k):
                try:
                    to_epoch(it[k])
                except ValueError:
                    out.append(f"{w}: {k} is not a time")
        st = it.get("status")
        if st in ("running", "live", "blocked-on-owner") and not it.get("start"):
            out.append(f"{w}: {st} needs a start")
        if st == "done" and not (it.get("start") and it.get("end")):
            out.append(f"{w}: done needs a start and an end")
        if it.get("start") and it.get("end") and to_epoch(it["end"]) < to_epoch(it["start"]):
            out.append(f"{w}: ends before it starts")
        if it.get("planned_start") and it.get("planned_end") and to_epoch(it["planned_end"]) < to_epoch(it["planned_start"]):
            out.append(f"{w}: planned end before planned start")
        if it.get("lane") == "needs_you" and st not in ("blocked-on-owner", "done", "dropped"):
            out.append(f"{w}: a needs-you item is blocked-on-owner, done or dropped")
        for ln in it.get("links") or []:
            if not (isinstance(ln, dict) and ln.get("label") and isinstance(ln.get("href"), str)):
                out.append(f"{w}: a link needs a label and an href")
        if not it.get("source"):
            out.append(f"{w}: no source")
    for i, pr in enumerate(data["promises"]):
        w = f"promise {pr.get('id', i)}"
        if not ID_RE.match(str(pr.get("id", ""))):
            out.append(f"{w}: bad id")
        if pr.get("id") in seen:
            out.append(f"{w}: id used twice")
        seen.add(pr.get("id"))
        if not pr.get("title"):
            out.append(f"{w}: no title")
        if pr.get("status") not in PROMISE_STATUSES:
            out.append(f"{w}: unknown status {pr.get('status')!r}")
        for k in ("made_at", "due", "closed_at"):
            if pr.get(k):
                try:
                    to_epoch(pr[k])
                except ValueError:
                    out.append(f"{w}: {k} is not a time")
        if not pr.get("source"):
            out.append(f"{w}: no source")
    for i, mk in enumerate(data["markers"]):
        w = f"marker {mk.get('id', i)}"
        if mk.get("kind") not in MARKER_KINDS:
            out.append(f"{w}: unknown kind {mk.get('kind')!r}")
        if not mk.get("at"):
            out.append(f"{w}: no time")
        if not mk.get("label"):
            out.append(f"{w}: no label")
    return out


# ------------------------------------------------------------------ operations (the CLI and the Desk call these)

def _find(data, item_id, kind="items"):
    for it in data[kind]:
        if it.get("id") == item_id:
            return it
    return None


def _links(pairs) -> list[dict]:
    out = []
    for p in pairs or []:
        if isinstance(p, dict):
            out.append(dict(label=p["label"], href=p["href"]))
            continue
        if "=" not in p:
            raise PlanError(f"a link is Label=/desk/path, not {p!r}")
        label, href = p.split("=", 1)
        out.append(dict(label=label.strip(), href=href.strip()))
    return out


def _fields(it: dict, **kw):
    for k, v in kw.items():
        if v is None:
            continue
        if k in ("start", "end", "planned_start", "planned_end"):
            v = parse_time(v)
        if k == "links":
            v = _links(v)
            it["links"] = (it.get("links") or []) + [l for l in v if l not in (it.get("links") or [])]
            continue
        if k == "source":
            it["source"] = (it.get("source") or []) + [s for s in v if s not in (it.get("source") or [])]
            continue
        it[k] = v


def _default_source(by: str) -> list[str]:
    return [f"added by {by} on {iso(now())}"]


def start(item_id, title=None, lane=None, by="agent", desc=None, readme=None, links=None, at=None, source=None,
          planned_end=None, cost=None, exp=None, watch=None) -> dict:
    """An item starts (new or planned): status running, start = at (default now)."""
    with locked_plan(by, "start", item_id) as data:
        it = _find(data, item_id)
        if it is None:
            if not (title and lane):
                raise PlanError(f"{item_id} is new: give a title and --lane")
            it = dict(id=item_id, title=title, lane=lane, status="running", added_by=by, added_at=iso(now()))
            data["items"].append(it)
        _fields(it, title=title, lane=lane, desc=desc, readme=readme, links=links, cost=cost, exp=exp, watch=watch,
                planned_end=planned_end, source=source or (None if it.get("source") else _default_source(by)))
        it["status"] = "running"
        it["start"] = parse_time(at or "now")
        it.pop("end", None)
        it["by"] = by
        return it


def plan(item_id, title=None, lane=None, by="agent", desc=None, start_at=None, end_at=None, after=None, readme=None,
         links=None, cost=None, source=None, exp=None) -> dict:
    """A planned item (dates optional: without them it is listed under 'Next', in order, not drawn)."""
    with locked_plan(by, "plan", item_id) as data:
        it = _find(data, item_id)
        if it is None:
            if not (title and lane):
                raise PlanError(f"{item_id} is new: give a title and --lane")
            it = dict(id=item_id, title=title, lane=lane, status="planned", added_by=by, added_at=iso(now()))
            data["items"].append(it)
        _fields(it, title=title, lane=lane, desc=desc, planned_start=start_at, planned_end=end_at, after=after,
                readme=readme, links=links, cost=cost, exp=exp,
                source=source or (None if it.get("source") else _default_source(by)))
        return it


def finish(item_id, outcome=None, status="done", by="agent", at=None, cost=None, links=None, source=None) -> dict:
    if status not in ("done", "live", "dropped", "parked"):
        raise PlanError("finish --status is done, live, dropped or parked")
    with locked_plan(by, f"finish:{status}", item_id) as data:
        it = _find(data, item_id)
        if it is None:
            raise PlanError(f"no item {item_id}")
        it["status"] = status
        t = parse_time(at or "now")
        if not it.get("start"):
            it["start"] = t
        if status in ("done", "dropped", "parked"):
            it["end"] = t
        else:
            it.pop("end", None)
        _fields(it, outcome=outcome, cost=cost, links=links, source=source)
        it["finished_by"] = by
        return it


CLEARABLE = ("planned_start", "planned_end", "after", "waits_on", "cost", "outcome", "readme", "links", "watch",
             "approx", "urgency", "recommended", "unblocks", "priority", "end")


def set_fields(item_id, by="agent", clear=(), **kw) -> dict:
    with locked_plan(by, "set", item_id) as data:
        it = _find(data, item_id)
        if it is None:
            raise PlanError(f"no item {item_id}")
        for k in clear or ():
            if k not in CLEARABLE:
                raise PlanError(f"--clear takes one of {', '.join(CLEARABLE)}")
            it.pop(k, None)
        _fields(it, **kw)
        return it


def needs_you_add(item_id, title, by="agent", question=None, urgency=None, recommended=None, unblocks=None,
                  links=None, at=None, source=None, due=None) -> dict:
    with locked_plan(by, "needs-you add", item_id) as data:
        if _find(data, item_id):
            raise PlanError(f"{item_id} exists already")
        it = dict(id=item_id, title=title, lane="needs_you", status="blocked-on-owner", start=parse_time(at or "now"),
                  added_by=by, added_at=iso(now()))
        _fields(it, desc=question, urgency=urgency, recommended=recommended, unblocks=unblocks, links=links,
                planned_end=due, source=source or _default_source(by))
        data["items"].append(it)
        return it


def needs_you_resolve(item_id, outcome, by="agent", at=None, dropped=False, source=None) -> dict:
    with locked_plan(by, "needs-you resolve", item_id) as data:
        it = _find(data, item_id)
        if it is None or it.get("lane") != "needs_you":
            raise PlanError(f"no needs-you item {item_id}")
        it["status"] = "dropped" if dropped else "done"
        it["end"] = parse_time(at or "now")
        it["outcome"] = outcome
        it["resolved_by"] = by
        _fields(it, source=source)
        return it


def promise_add(pid, title, due=None, by="agent", detail=None, item=None, source=None, at=None) -> dict:
    with locked_plan(by, "promise add", pid) as data:
        if _find(data, pid, "promises") or _find(data, pid):
            raise PlanError(f"{pid} exists already")
        pr = dict(id=pid, title=title, detail=detail, made_at=parse_time(at or "now"), due=parse_time(due),
                  status="open", by=by, item=item, source=source or _default_source(by))
        data["promises"].append({k: v for k, v in pr.items() if v is not None})
        return pr


def promise_close(pid, status="kept", by="agent", outcome=None, at=None) -> dict:
    with locked_plan(by, f"promise {status}", pid) as data:
        pr = _find(data, pid, "promises")
        if pr is None:
            raise PlanError(f"no promise {pid}")
        pr["status"] = status
        pr["closed_at"] = parse_time(at or "now")
        pr["closed_by"] = by
        if outcome:
            pr["outcome"] = outcome
        return pr


def add_marker(kind, label, by="agent", at=None, href=None, detail=None, item=None, source=None) -> dict:
    with locked_plan(by, f"marker {kind}", None) as data:
        n = 1 + max([int(m["id"][1:]) for m in data["markers"] if re.fullmatch(r"m\d+", str(m.get("id")))] or [0])
        mk = dict(id=f"m{n}", kind=kind, at=parse_time(at or "now"), label=label, href=href, detail=detail,
                  item=item, by=by, source=source or _default_source(by))
        data["markers"].append({k: v for k, v in mk.items() if v is not None})
        return mk


def beat(item_id, by="agent", note=None) -> dict:
    """A heartbeat: desk/plan/beats/<id>.json (atomic), not the plan file."""
    if not ID_RE.match(item_id):
        raise PlanError("bad id")
    if _find(read_plan(), item_id) is None:
        raise PlanError(f"no item {item_id}")
    b = dict(id=item_id, at=iso(now()), by=by, note=note)
    write_atomic(beats_dir() / f"{item_id}.json", b)
    return b


def read_beats() -> dict:
    out = {}
    d = beats_dir()
    if d.is_dir():
        for f in d.glob("*.json"):
            with contextlib.suppress(ValueError, OSError):
                b = json.loads(f.read_text(encoding="utf-8"))
                out[b.get("id") or f.stem] = b
    return out


# ------------------------------------------------------------------ the command line

def _print(o):
    print(json.dumps(o, ensure_ascii=False, indent=1))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="plan_cli", description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--by", default=os.environ.get("PLAN_BY") or f"agent:{os.environ.get('USER', 'lead')}",
                    help="who is writing (default $PLAN_BY, else agent:$USER)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p, title_pos=True):
        p.add_argument("id")
        if title_pos:
            p.add_argument("title", nargs="?")
        p.add_argument("--lane", choices=LANE_KEYS)
        p.add_argument("--desc", help="one plain line: what it is")
        p.add_argument("--readme", help="repo path of its README")
        p.add_argument("--link", action="append", help="Label=/desk/path (repeatable)")
        p.add_argument("--cost")
        p.add_argument("--exp", help="experiment number")
        p.add_argument("--source", action="append")

    s = sub.add_parser("start", help="an item starts running (new, or a planned one)")
    common(s)
    s.add_argument("--at")
    s.add_argument("--planned-end")
    s.add_argument("--watch", help="repo folder whose newest file counts as activity")
    p = sub.add_parser("plan", help="a planned item (dates optional)")
    common(p)
    p.add_argument("--start")
    p.add_argument("--end")
    p.add_argument("--after", help="the item it follows")
    f = sub.add_parser("finish", help="an item ends")
    f.add_argument("id")
    f.add_argument("--outcome")
    f.add_argument("--status", default="done", choices=["done", "live", "dropped", "parked"])
    f.add_argument("--at")
    f.add_argument("--cost")
    f.add_argument("--link", action="append")
    f.add_argument("--source", action="append")
    e = sub.add_parser("set", help="change fields of an item")
    common(e)
    e.add_argument("--status", choices=STATUSES)
    e.add_argument("--outcome")
    e.add_argument("--start")
    e.add_argument("--end")
    e.add_argument("--planned-start")
    e.add_argument("--planned-end")
    e.add_argument("--after")
    e.add_argument("--waits-on", help="the needs-you item it waits for")
    e.add_argument("--priority", type=int, help="needs-you order: 0 = most urgent")
    e.add_argument("--clear", action="append", default=[], help="remove a field (repeatable): " + ", ".join(CLEARABLE))
    b = sub.add_parser("beat", help="a heartbeat for a running item")
    b.add_argument("id")
    b.add_argument("--note")
    n = sub.add_parser("needs-you", help="something only the owner can do")
    nsub = n.add_subparsers(dest="ncmd", required=True)
    na = nsub.add_parser("add")
    na.add_argument("id")
    na.add_argument("title")
    na.add_argument("--question")
    na.add_argument("--urgency")
    na.add_argument("--recommended")
    na.add_argument("--unblocks")
    na.add_argument("--due")
    na.add_argument("--at")
    na.add_argument("--link", action="append")
    na.add_argument("--source", action="append")
    nr = nsub.add_parser("resolve")
    nr.add_argument("id")
    nr.add_argument("--outcome", required=True)
    nr.add_argument("--dropped", action="store_true")
    nr.add_argument("--at")
    nr.add_argument("--source", action="append")
    pr = sub.add_parser("promise", help="a promise with a due time")
    psub = pr.add_subparsers(dest="pcmd", required=True)
    pa = psub.add_parser("add")
    pa.add_argument("id")
    pa.add_argument("title")
    pa.add_argument("--due", help="when it is due (now, +6h, ISO); leave out when no time was promised")
    pa.add_argument("--detail")
    pa.add_argument("--item")
    pa.add_argument("--source", action="append")
    for verb in ("keep", "drop"):
        pk = psub.add_parser(verb)
        pk.add_argument("id")
        pk.add_argument("--outcome")
    m = sub.add_parser("add-marker", help="a release, deploy, eval, alert or milestone on the time axis")
    m.add_argument("kind", choices=MARKER_KINDS)
    m.add_argument("label")
    m.add_argument("--at")
    m.add_argument("--href")
    m.add_argument("--detail")
    m.add_argument("--item")
    m.add_argument("--source", action="append")
    ls = sub.add_parser("list")
    ls.add_argument("--status", choices=STATUSES)
    ls.add_argument("--lane", choices=LANE_KEYS)
    sh = sub.add_parser("show")
    sh.add_argument("id")
    sub.add_parser("check", help="validate the file")
    x = ap.parse_args(argv)
    by = x.by
    try:
        if x.cmd == "start":
            _print(start(x.id, x.title, x.lane, by, x.desc, x.readme, x.link, x.at, x.source, x.planned_end, x.cost,
                         x.exp, x.watch))
        elif x.cmd == "plan":
            _print(plan(x.id, x.title, x.lane, by, x.desc, x.start, x.end, x.after, x.readme, x.link, x.cost,
                        x.source, x.exp))
        elif x.cmd == "finish":
            _print(finish(x.id, x.outcome, x.status, by, x.at, x.cost, x.link, x.source))
        elif x.cmd == "set":
            _print(set_fields(x.id, by, title=x.title, lane=x.lane, desc=x.desc, readme=x.readme, links=x.link,
                              cost=x.cost, exp=x.exp, source=x.source, status=x.status, outcome=x.outcome,
                              start=x.start, end=x.end, planned_start=x.planned_start, planned_end=x.planned_end,
                              after=x.after, waits_on=x.waits_on, priority=x.priority, clear=x.clear))
        elif x.cmd == "beat":
            _print(beat(x.id, by, x.note))
        elif x.cmd == "needs-you":
            if x.ncmd == "add":
                _print(needs_you_add(x.id, x.title, by, x.question, x.urgency, x.recommended, x.unblocks, x.link,
                                     x.at, x.source, x.due))
            else:
                _print(needs_you_resolve(x.id, x.outcome, by, x.at, x.dropped, x.source))
        elif x.cmd == "promise":
            if x.pcmd == "add":
                _print(promise_add(x.id, x.title, x.due, by, x.detail, x.item, x.source))
            else:
                _print(promise_close(x.id, "kept" if x.pcmd == "keep" else "dropped", by, x.outcome))
        elif x.cmd == "add-marker":
            _print(add_marker(x.kind, x.label, by, x.at, x.href, x.detail, x.item, x.source))
        elif x.cmd == "list":
            d = read_plan()
            for it in d["items"]:
                if (x.status and it["status"] != x.status) or (x.lane and it["lane"] != x.lane):
                    continue
                print(f"{it['id']:<24} {it['status']:<17} {it['lane']:<15} {it['title']}")
            if not x.status and not x.lane:
                for pr_ in d["promises"]:
                    print(f"{pr_['id']:<24} {'promise ' + pr_['status']:<17} {'due ' + (pr_.get('due') or '-'):<15} {pr_['title']}")
        elif x.cmd == "show":
            d = read_plan()
            it = _find(d, x.id) or _find(d, x.id, "promises")
            if it is None:
                raise PlanError(f"no item {x.id}")
            _print(it)
        elif x.cmd == "check":
            probs = validate(read_plan())
            for pr_ in probs:
                print(pr_)
            print("ok" if not probs else f"{len(probs)} problems")
            return 1 if probs else 0
    except PlanError as e:
        print(f"plan_cli: {e}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    if __package__ in (None, ""):          # run as a script: python desk/plan_cli.py …
        sys.path.insert(0, str(HERE.parent))
    raise SystemExit(main())
