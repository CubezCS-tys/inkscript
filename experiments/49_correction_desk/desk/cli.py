"""Command line for the Desk (P1).

    .venv/bin/python -m desk.cli init                          # create schema `desk` in inkdesk (idempotent)
    .venv/bin/python -m desk.cli actor add person:amina --name "Amina" --role corrector --skills ar,fr
    .venv/bin/python -m desk.cli token person:amina            # a new token (printed once; only its sha256 is kept)
    .venv/bin/python -m desk.cli detect [--db PATH]            # run the three detectors -> tasks
    .venv/bin/python -m desk.cli release [--reading PATH]      # build a release (same as python -m desk.release)
    .venv/bin/python -m desk.cli demo                          # P1 demo data: agent:p1-demo's decisions + a release
    .venv/bin/python -m desk.cli serve                         # the API on 127.0.0.1:8005
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import secrets
import socket
import sys
from pathlib import Path

from . import db

DEMO_NOTE = "DEMO (P1): an agent's example decision, made so P2's screens have something to show; not a person's. "
TOKENS_FILE = Path("/home/appuser/data/desk/demo_tokens.txt")


def add_actor(pg, actor_id, name, role, skills, kind=None, is_demo=False):
    kind = kind or actor_id.split(":")[0]
    pg.execute("""INSERT INTO actors (actor_id, kind, name, role, skills, is_demo) VALUES (%s,%s,%s,%s,%s,%s)
                  ON CONFLICT (actor_id) DO UPDATE SET name = excluded.name, role = excluded.role,
                  skills = excluded.skills""", (actor_id, kind, name, role, skills, is_demo))


def new_token(pg, actor_id) -> str:
    tok = secrets.token_urlsafe(24)
    pg.execute("INSERT INTO tokens (token_sha, actor_id) VALUES (%s, %s)", (hashlib.sha256(tok.encode()).hexdigest(),
                                                                          actor_id))
    return tok


def port_free(host="127.0.0.1", port=8005) -> bool:
    with socket.socket() as s:
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind((host, port))
            return True
        except OSError:
            return False


def demo(pg) -> dict:
    """agent:p1-demo makes test (a)'s decisions (and one more) in the real Desk, then a release is built and the
    detectors run on it. Every row is marked is_demo and every note starts with DEMO."""
    from . import detectors, examples, release
    if pg.execute("SELECT 1 FROM decisions WHERE actor_id = 'agent:p1-demo' LIMIT 1").fetchone():
        raise SystemExit("demo decisions are already loaded")
    add_actor(pg, "agent:p1-demo", "P1 demo agent (example decisions, not a person's)", "corrector",
              ["ar", "en", "fr"], kind="agent", is_demo=True)
    add_actor(pg, "agent:p1-demo-admin", "P1 demo admin (for trying admin routes)", "admin", ["ar", "en", "fr"],
              kind="agent", is_demo=True)
    toks = {a: new_token(pg, a) for a in ("agent:p1-demo", "agent:p1-demo-admin")}
    pg.commit()
    first = detectors.run(pg, is_demo=True)            # tasks on the machine's reading
    pg.commit()
    made = examples.make_test_a(pg, "agent:p1-demo", is_demo=True, note_prefix=DEMO_NOTE)
    made |= examples.make_more(pg, "agent:p1-demo", is_demo=True, note_prefix=DEMO_NOTE)
    pg.commit()
    rel = release.build_release(pg, note="P1 demo release: test (a)'s decisions by agent:p1-demo", is_demo=True)
    second = detectors.run(pg, rel["path"], release_id=rel["release_id"], is_demo=True)
    pg.commit()
    TOKENS_FILE.parent.mkdir(parents=True, exist_ok=True)
    TOKENS_FILE.write_text("".join(f"{a}\t{t}\n" for a, t in toks.items()))
    os.chmod(TOKENS_FILE, 0o600)
    return dict(decisions={k: str(v["decision_id"]) for k, v in made.items()}, release=rel["release_id"],
                release_path=rel["path"], applied=rel["n_applied"], detectors_on_reading=first,
                detectors_on_release=second, tokens_file=str(TOKENS_FILE))


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("init")
    a = sub.add_parser("actor")
    a.add_argument("action", choices=["add"])
    a.add_argument("actor_id")
    a.add_argument("--name", required=True)
    a.add_argument("--role", choices=["corrector", "admin"], default="corrector")
    a.add_argument("--skills", default="ar")
    t = sub.add_parser("token")
    t.add_argument("actor_id")
    d = sub.add_parser("detect")
    d.add_argument("--db")
    r = sub.add_parser("release")
    r.add_argument("--reading")
    r.add_argument("--keep", type=int, default=2)
    r.add_argument("--note")
    sub.add_parser("demo")
    s = sub.add_parser("serve")
    s.add_argument("--port", type=int, default=8005)
    x = ap.parse_args(argv)
    if x.cmd == "init":
        db.init_schema()
        print(f"schema {db.pg_schema()} ready")
        return
    if x.cmd == "serve":
        if not port_free(port=x.port):
            raise SystemExit(f"127.0.0.1:{x.port} is taken")
        import uvicorn
        uvicorn.run("desk.api:app", host="127.0.0.1", port=x.port, workers=1, log_level="info")
        return
    with db.connect() as pg:
        if x.cmd == "actor":
            add_actor(pg, x.actor_id, x.name, x.role, [s for s in x.skills.split(",") if s])
            print(new_token(pg, x.actor_id))
        elif x.cmd == "token":
            print(new_token(pg, x.actor_id))
        elif x.cmd == "detect":
            from . import detectors
            print(json.dumps(detectors.run(pg, x.db), indent=1))
        elif x.cmd == "release":
            from . import release
            rr = release.build_release(pg, x.reading, keep=x.keep, note=x.note)
            print(json.dumps({k: rr[k] for k in ("release_id", "path", "n_decisions", "n_applied", "n_orphaned",
                                                 "n_conflict", "fingerprint", "checks", "timings")}, default=str,
                             ensure_ascii=False, indent=1))
        elif x.cmd == "demo":
            print(json.dumps(demo(pg), ensure_ascii=False, indent=1, default=str))
        pg.commit()


if __name__ == "__main__":
    sys.exit(main())
