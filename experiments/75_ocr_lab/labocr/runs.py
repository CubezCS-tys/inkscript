"""Runs: SQLite state (runs, per-page state machine, attempts), resumable, raw + normalised artifacts, timings, errors.

Page states: pending -> running -> succeeded | failed (| cancelled).  Attempts are kept separately.  On restart a
stale `running` page (a crashed core) is reconciled to pending with its attempt closed as `stale`.  Artifacts are
written atomically and the page is marked succeeded only after they are on disk.  Resume skips a page only when its
prediction file exists and parses.  The retry budget is bounded (max_attempts, same configuration every time).

Run identity = sha256 of everything that affects outputs: dataset manifest hash, the render ids, engine, variant,
settings (prompts, decoding, image budgets, precision), model revision, worker argv.  Framework versions are
recorded at start (health) and a resume that sees different versions refuses to continue.
"""
from __future__ import annotations

import base64
import hashlib
import json
import sqlite3
import subprocess
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable, Optional

from . import SCHEMA_VERSION
from .adapters.normalise import NORMALISER_VERSION, normalise
from .adapters.transport import SubprocessAdapter, WorkerError
from .ingest import atomic_write, read_manifest, render_by_id, safe_child, manifest_hash
from .schemas import EngineConfig, ErrorRecord, PagePrediction, PageRequest, PredictionResult

DDL = """
CREATE TABLE IF NOT EXISTS runs (
  run_id TEXT PRIMARY KEY, created_at TEXT, dataset TEXT, engine TEXT, variant TEXT, config_json TEXT,
  identity_json TEXT, manifest_hash TEXT, code_commit TEXT, code_dirty INTEGER, worker_argv_json TEXT,
  health_json TEXT, capabilities_json TEXT, is_fixture INTEGER DEFAULT 0, imported INTEGER DEFAULT 0,
  status TEXT, load_s REAL, wall_s REAL DEFAULT 0, note TEXT);
CREATE TABLE IF NOT EXISTS pages (
  run_id TEXT, page_id TEXT, state TEXT, attempts INTEGER DEFAULT 0, artifact TEXT, raw_artifact TEXT,
  error_kind TEXT, error_message TEXT, updated_at TEXT, PRIMARY KEY (run_id, page_id));
CREATE TABLE IF NOT EXISTS attempts (
  attempt_id TEXT PRIMARY KEY, run_id TEXT, page_id TEXT, n INTEGER, started_at TEXT, finished_at TEXT,
  status TEXT, error_kind TEXT, error_message TEXT, timing_json TEXT);
"""


def now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def connect(root: Path) -> sqlite3.Connection:
    root.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(root / "lab.sqlite"), timeout=30)
    con.row_factory = sqlite3.Row
    con.executescript(DDL)
    return con


def git_state(repo: Path) -> tuple[str, bool]:
    try:
        c = subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], capture_output=True, text=True,
                           timeout=10).stdout.strip()
        d = subprocess.run(["git", "-C", str(repo), "status", "--porcelain", "--", "experiments/75_ocr_lab"],
                           capture_output=True, text=True, timeout=20).stdout.strip()
        return c, bool(d)
    except Exception:  # noqa: BLE001
        return "unknown", True


def run_identity(root: Path, dataset: str, cfg: EngineConfig, argv: list[str], pages: list[str]) -> tuple[str, dict]:
    entries = {e.page_id: e for e in read_manifest(root, dataset)}
    ident = dict(schema=SCHEMA_VERSION, dataset=dataset, manifest_hash=manifest_hash(root, dataset),
                 renders=[entries[p].render_id for p in pages], pages=pages, engine=cfg.engine, variant=cfg.variant,
                 settings=cfg.settings, model_revision=cfg.model_revision,
                 worker=[a for a in argv if not a.startswith("-o")])
    h = hashlib.sha256(json.dumps(ident, sort_keys=True, ensure_ascii=False).encode()).hexdigest()
    return f"run_{cfg.engine}_{cfg.variant}_{h[:10]}", ident


def create_run(root: Path, dataset: str, cfg: EngineConfig, argv: list[str], pages: Optional[list[str]] = None,
               repo: Optional[Path] = None, note: str = "", is_fixture: bool = False) -> str:
    entries = read_manifest(root, dataset)
    pages = pages or [e.page_id for e in entries]
    known = {e.page_id for e in entries}
    missing = [p for p in pages if p not in known]
    if missing:
        raise KeyError(f"pages not in dataset {dataset}: {missing}")
    run_id, ident = run_identity(root, dataset, cfg, argv, pages)
    con = connect(root)
    if con.execute("SELECT 1 FROM runs WHERE run_id=?", (run_id,)).fetchone():
        return run_id                       # same identity: resume it
    commit, dirty = git_state(repo or Path(__file__).resolve().parents[3])
    con.execute("INSERT INTO runs (run_id, created_at, dataset, engine, variant, config_json, identity_json, "
                "manifest_hash, code_commit, code_dirty, worker_argv_json, is_fixture, status, note) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, now(), dataset, cfg.engine, cfg.variant, cfg.model_dump_json(), json.dumps(ident),
                 ident["manifest_hash"], commit, int(dirty), json.dumps(argv), int(is_fixture), "created", note))
    for p in pages:
        con.execute("INSERT INTO pages (run_id, page_id, state, updated_at) VALUES (?,?,?,?)",
                    (run_id, p, "pending", now()))
    con.commit()
    return run_id


def reconcile(con: sqlite3.Connection, run_id: str) -> int:
    """Stale `running` pages (the core died mid-page) -> pending; their open attempts -> stale."""
    n = 0
    for r in con.execute("SELECT page_id FROM pages WHERE run_id=? AND state='running'", (run_id,)).fetchall():
        con.execute("UPDATE attempts SET status='stale', finished_at=?, error_kind='worker_crash', "
                    "error_message='stale lease reconciled at restart' WHERE run_id=? AND page_id=? AND "
                    "finished_at IS NULL", (now(), run_id, r["page_id"]))
        con.execute("UPDATE pages SET state='pending', updated_at=? WHERE run_id=? AND page_id=?",
                    (now(), run_id, r["page_id"]))
        n += 1
    con.commit()
    return n


def _valid_artifact(root: Path, rel: Optional[str]) -> bool:
    if not rel:
        return False
    try:
        PagePrediction.model_validate_json(safe_child(root, rel).read_text(encoding="utf-8"))
        return True
    except Exception:  # noqa: BLE001
        return False


AdapterFactory = Callable[[list[str]], SubprocessAdapter]


def execute_run(root: Path, run_id: str, *, max_attempts: int = 2, embed_image: bool = False,
                adapter_factory: Optional[AdapterFactory] = None, timeouts: Optional[dict] = None,
                log=print) -> dict:
    """Run (or resume) every unfinished page of run_id.  Returns the run summary."""
    con = connect(root)
    run = con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone()
    if not run:
        raise KeyError(run_id)
    if run["imported"]:
        raise ValueError("an imported run has no worker to execute")
    cfg = EngineConfig.model_validate_json(run["config_json"])
    argv = json.loads(run["worker_argv_json"])
    entries = {e.page_id: e for e in read_manifest(root, run["dataset"])}
    reconcile(con, run_id)
    stderr_path = str(root / "runs" / run_id / "worker.stderr.log")
    (root / "runs" / run_id).mkdir(parents=True, exist_ok=True)
    make = adapter_factory or (lambda a: SubprocessAdapter(a, timeouts=timeouts, stderr_path=stderr_path))

    def todo():
        out = []
        for r in con.execute("SELECT * FROM pages WHERE run_id=? ORDER BY page_id", (run_id,)).fetchall():
            if r["state"] == "succeeded" and _valid_artifact(root, r["artifact"]):
                continue
            if r["state"] == "cancelled" or r["attempts"] >= max_attempts:
                continue
            out.append(r["page_id"])
        return out

    pages = todo()
    if not pages:
        return summary(root, run_id)
    t_run = time.monotonic()
    adapter = None

    def start():
        a = make(argv)
        health = a.health()
        caps = a.capabilities()
        if caps.is_fixture != bool(run["is_fixture"]):
            a.close()
            raise RuntimeError("a fixture worker may only serve a run created as a fixture run (and vice versa)")
        prev = run["health_json"]
        if prev and json.loads(prev).get("versions") != health.versions:
            a.close()
            raise RuntimeError(f"framework versions changed since the run started: {json.loads(prev)['versions']} "
                               f"-> {health.versions}; create a new run")
        if not health.ok:
            a.close()
            raise RuntimeError(f"worker health check failed: {health.detail}")
        a.load(cfg)
        con.execute("UPDATE runs SET health_json=?, capabilities_json=?, load_s=?, status='running' WHERE run_id=?",
                    (health.model_dump_json(), caps.model_dump_json(), a.load_seconds, run_id))
        con.commit()
        return a

    try:
        try:
            adapter = start()
        except (WorkerError, RuntimeError) as ex:
            # a worker that cannot start or load: every page gets a failed attempt with the reason (kept as evidence)
            err = ex.error if isinstance(ex, WorkerError) else ErrorRecord(kind="load_error", message=str(ex))
            if err.kind == "other":
                err = ErrorRecord(kind="load_error", message=err.message)
            for pid in pages:
                n = con.execute("SELECT attempts FROM pages WHERE run_id=? AND page_id=?", (run_id, pid)).fetchone()[0] + 1
                con.execute("INSERT INTO attempts (attempt_id, run_id, page_id, n, started_at, finished_at, status, "
                            "error_kind, error_message) VALUES (?,?,?,?,?,?,?,?,?)",
                            (f"{run_id}:{pid}:a{n}", run_id, pid, n, now(), now(), "failed", err.kind, err.message[:4000]))
                con.execute("UPDATE pages SET state='failed', attempts=?, error_kind=?, error_message=?, updated_at=? "
                            "WHERE run_id=? AND page_id=?", (n, err.kind, err.message[:4000], now(), run_id, pid))
            con.commit()
            log(f"worker could not start: {err.kind}: {err.message[:300]}")
            adapter = None
            pages = []
        for pid in pages:
            e = entries[pid]
            rr = render_by_id(root, e.render_id)
            n = con.execute("SELECT attempts FROM pages WHERE run_id=? AND page_id=?", (run_id, pid)).fetchone()[0] + 1
            att = f"{run_id}:{pid}:a{n}"
            con.execute("INSERT INTO attempts (attempt_id, run_id, page_id, n, started_at, status) VALUES (?,?,?,?,?,?)",
                        (att, run_id, pid, n, now(), "running"))
            con.execute("UPDATE pages SET state='running', attempts=?, updated_at=? WHERE run_id=? AND page_id=?",
                        (n, now(), run_id, pid))
            con.commit()
            img = safe_child(root, rr.path)
            req = PageRequest(request_id=f"q{n}_{pid}", page_id=pid, page_number=e.page_number,
                              render_id=rr.render_id, width=rr.width, height=rr.height,
                              image_path=None if embed_image else str(img),
                              image_b64=base64.b64encode(img.read_bytes()).decode() if embed_image else None,
                              image_name=img.name)
            raw_rel = f"runs/{run_id}/raw/{pid}.a{n}.json"
            t0 = time.monotonic()
            try:
                if adapter is None:
                    adapter = start()
                reply = adapter.predict_raw(req)
                wall = time.monotonic() - t0
                atomic_write(safe_child(root, raw_rel), json.dumps(reply, ensure_ascii=False).encode("utf-8"))
                try:
                    res = PredictionResult.model_validate(reply)
                except Exception as ve:  # noqa: BLE001
                    raise WorkerError(ErrorRecord(kind="invalid_output", message=str(ve)[:2000]))
                tn = time.monotonic()
                blocks = normalise(cfg.engine, cfg.variant, reply)
                res.blocks = blocks
                res.timing.normalise_s = time.monotonic() - tn
                res.timing.total_s = wall
                res.empty = res.empty or not any(b.raw_text.strip() for b in blocks)
                pred = PagePrediction(run_id=run_id, attempt_id=att, document_id=e.document_id,
                                      page_number=e.page_number, page_id=pid, render_id=rr.render_id,
                                      width=rr.width, height=rr.height, engine=cfg.engine, variant=cfg.variant,
                                      result=res, raw_artifact=raw_rel)
                rel = f"runs/{run_id}/pred/{pid}.json"
                atomic_write(safe_child(root, rel), pred.model_dump_json(indent=1).encode("utf-8"))
                con.execute("UPDATE attempts SET finished_at=?, status='succeeded', timing_json=? WHERE attempt_id=?",
                            (now(), res.timing.model_dump_json(), att))
                con.execute("UPDATE pages SET state='succeeded', artifact=?, raw_artifact=?, error_kind=NULL, "
                            "error_message=NULL, updated_at=? WHERE run_id=? AND page_id=?",
                            (rel, raw_rel, now(), run_id, pid))
                con.commit()
                log(f"{pid}: ok {wall:.1f}s blocks={len(blocks)} empty={res.empty} truncated={res.truncated}")
            except (WorkerError, RuntimeError) as ex:
                err = ex.error if isinstance(ex, WorkerError) else ErrorRecord(kind="load_error", message=str(ex))
                con.execute("UPDATE attempts SET finished_at=?, status='failed', error_kind=?, error_message=? "
                            "WHERE attempt_id=?", (now(), err.kind, err.message[:4000], att))
                con.execute("UPDATE pages SET state='failed', error_kind=?, error_message=?, updated_at=? "
                            "WHERE run_id=? AND page_id=?", (err.kind, err.message[:4000], now(), run_id, pid))
                con.commit()
                log(f"{pid}: FAILED {err.kind}: {err.message[:200]}")
                if err.kind in ("worker_crash", "timeout", "protocol_error"):
                    if adapter is not None:
                        adapter.terminate()
                    adapter = None          # a fresh worker for the next page
    finally:
        if adapter is not None:
            adapter.close()
        con.execute("UPDATE runs SET wall_s=COALESCE(wall_s,0)+? WHERE run_id=?", (time.monotonic() - t_run, run_id))
        con.commit()
    # bounded retry of failed pages with the same configuration (a new attempt each)
    if todo() and any(con.execute("SELECT 1 FROM pages WHERE run_id=? AND state='failed' AND attempts<?",
                                  (run_id, max_attempts)).fetchall()):
        return execute_run(root, run_id, max_attempts=max_attempts, embed_image=embed_image,
                           adapter_factory=adapter_factory, timeouts=timeouts, log=log)
    s = summary(root, run_id)
    con.execute("UPDATE runs SET status=? WHERE run_id=?", ("finished" if s["failed"] == 0 else "finished_with_failures",
                                                            run_id))
    con.commit()
    return summary(root, run_id)


def summary(root: Path, run_id: str) -> dict:
    con = connect(root)
    run = dict(con.execute("SELECT * FROM runs WHERE run_id=?", (run_id,)).fetchone())
    pages = [dict(r) for r in con.execute("SELECT * FROM pages WHERE run_id=? ORDER BY page_id", (run_id,))]
    atts = [dict(r) for r in con.execute("SELECT * FROM attempts WHERE run_id=? ORDER BY started_at", (run_id,))]
    return dict(run_id=run_id, engine=run["engine"], variant=run["variant"], status=run["status"],
                is_fixture=bool(run["is_fixture"]), imported=bool(run["imported"]), load_s=run["load_s"],
                wall_s=run["wall_s"], pages=len(pages), succeeded=sum(p["state"] == "succeeded" for p in pages),
                failed=sum(p["state"] == "failed" for p in pages), attempts=len(atts),
                retries=sum(1 for a in atts if a["n"] > 1), page_states=pages, attempt_log=atts)


def import_run(root: Path, dataset: str, engine: str, variant: str, predictions: list[PagePrediction],
               note: str, settings: Optional[dict] = None, imported: bool = True) -> str:
    """Store outputs that already exist on disk (our pipeline, earlier experiments) as an imported run:
    no worker, no inference; labelled `imported` everywhere."""
    cfg = EngineConfig(engine=engine, variant=variant, settings=settings or {})
    run_id, ident = run_identity(root, dataset, cfg, ["imported"], [p.page_id for p in predictions])
    con = connect(root)
    con.execute("DELETE FROM pages WHERE run_id=?", (run_id,))
    con.execute("DELETE FROM runs WHERE run_id=?", (run_id,))
    commit, dirty = git_state(Path(__file__).resolve().parents[3])
    con.execute("INSERT INTO runs (run_id, created_at, dataset, engine, variant, config_json, identity_json, "
                "manifest_hash, code_commit, code_dirty, worker_argv_json, imported, status, note) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (run_id, now(), dataset, engine, variant, cfg.model_dump_json(), json.dumps(ident),
                 ident["manifest_hash"], commit, int(dirty), "[]", int(imported), "imported" if imported else "finished",
                 note))
    for p in predictions:
        p.run_id = run_id
        p.attempt_id = f"{run_id}:{p.page_id}:import"
        rel = f"runs/{run_id}/pred/{p.page_id}.json"
        atomic_write(safe_child(root, rel), p.model_dump_json(indent=1).encode("utf-8"))
        con.execute("INSERT INTO pages (run_id, page_id, state, attempts, artifact, updated_at) VALUES (?,?,?,?,?,?)",
                    (run_id, p.page_id, "succeeded", 0, rel, now()))
    con.commit()
    return run_id


def load_predictions(root: Path, run_id: str) -> dict[str, PagePrediction]:
    con = connect(root)
    out = {}
    for r in con.execute("SELECT page_id, artifact FROM pages WHERE run_id=? AND state='succeeded'", (run_id,)):
        out[r["page_id"]] = PagePrediction.model_validate_json(safe_child(root, r["artifact"]).read_text("utf-8"))
    return out


def renormalise(root: Path, run_id: str) -> int:
    """Rebuild blocks from the stored raw replies (a normaliser change needs no inference)."""
    preds = load_predictions(root, run_id)
    n = 0
    for pid, p in preds.items():
        if not p.raw_artifact:
            continue
        reply = json.loads(safe_child(root, p.raw_artifact).read_text("utf-8"))
        p.result.blocks = normalise(p.engine, p.variant, reply)
        rel = f"runs/{run_id}/pred/{pid}.json"
        atomic_write(safe_child(root, rel), p.model_dump_json(indent=1).encode("utf-8"))
        n += 1
    return n


__all__ = ["connect", "create_run", "execute_run", "summary", "import_run", "load_predictions", "renormalise",
           "reconcile", "NORMALISER_VERSION"]
