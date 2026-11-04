"""Connections: the Desk's PostgreSQL schema (the people's sheet) and platform v2's SQLite (the machine's reading).

Configuration comes from the environment so tests can point everything elsewhere:

    DESK_PG       libpq connection string            (default 'dbname=inkdesk', peer auth over the local socket)
    DESK_SCHEMA   the schema holding the Desk         (default 'desk'; tests use 'test_<pid>')
    DESK_READING  the machine reading, opened read-only (default platform_v2.db)
    DESK_RELEASES where release copies are written    (default /home/appuser/data/desk/releases)
"""
from __future__ import annotations

import os
import re
import sqlite3
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

HERE = Path(__file__).resolve().parent
SCHEMA_SQL = HERE / "schema.sql"
PLATFORM_V2 = Path("/home/appuser/data/platform_v2/platform_v2.db")


def reading_path() -> Path:
    return Path(os.environ.get("DESK_READING", str(PLATFORM_V2)))


def releases_dir() -> Path:
    return Path(os.environ.get("DESK_RELEASES", "/home/appuser/data/desk/releases"))


def pg_dsn() -> str:
    return os.environ.get("DESK_PG", "dbname=inkdesk")


def pg_schema() -> str:
    s = os.environ.get("DESK_SCHEMA", "desk")
    if not re.fullmatch(r"[a-z_][a-z0-9_]*", s):
        raise ValueError(f"bad schema name {s!r}")
    return s


def connect(schema: str | None = None, autocommit: bool = False) -> psycopg.Connection:
    """A connection whose search_path is the Desk schema (then public, for the extensions)."""
    schema = schema or pg_schema()
    con = psycopg.connect(pg_dsn(), row_factory=dict_row, autocommit=autocommit)
    con.execute(f"SET search_path TO {schema}, public")
    return con


def init_schema(schema: str | None = None, drop: bool = False) -> None:
    """Create the schema and its tables (and the extensions, once per database)."""
    schema = schema or pg_schema()
    with psycopg.connect(pg_dsn(), autocommit=True) as con:
        for ext in ("pg_trgm", "unaccent", "btree_gist"):
            con.execute(f"CREATE EXTENSION IF NOT EXISTS {ext} SCHEMA public")
        if drop:
            con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")
        exists = con.execute("SELECT 1 FROM information_schema.schemata WHERE schema_name = %s", (schema,)).fetchone()
        if exists:                       # an existing schema: only the idempotent tail of schema.sql (new tables)
            con.execute(f"SET search_path TO {schema}, public")
            con.execute(upgrades_sql())
            return
        con.execute(f"CREATE SCHEMA {schema}")
        con.execute(f"SET search_path TO {schema}, public")
        con.execute(SCHEMA_SQL.read_text(encoding="utf-8"))
    with connect(schema) as con:
        seed_rules(con)
        con.commit()


UPGRADES_MARK = "-- ==== idempotent upgrades"


def upgrades_sql() -> str:
    """The part of schema.sql below the upgrades mark: statements safe to run again (IF NOT EXISTS / OR REPLACE)."""
    text = SCHEMA_SQL.read_text(encoding="utf-8")
    i = text.find(UPGRADES_MARK)
    return text[i:] if i >= 0 else ""


def drop_schema(schema: str) -> None:
    if not schema.startswith("test_"):
        raise ValueError("only test schemas are dropped by code")
    with psycopg.connect(pg_dsn(), autocommit=True) as con:
        con.execute(f"DROP SCHEMA IF EXISTS {schema} CASCADE")


# The review rule per kind (DESIGN §7). One key by default (owner, 2026-10-21): every decision is accepted as soon
# as its corrector makes it. The table stays a setting so another rule can be switched on later.
DEFAULT_RULES = [(op, "single", 0, None, "") for op in (
    "split_work", "same_work", "not_same_work", "move_member", "set_work_type", "confirm_work",
    "same_person", "not_same_person", "link_byline", "unlink_byline", "resolve_backref", "unresolvable",
    "define_institution", "same_institution", "not_same_institution", "not_an_institution_row", "set_inst_country",
    "set_inst_parent", "set_inst_type", "link_affiliation", "not_an_institution", "unit_kept_apart",
    "edition_of", "not_a_work", "define_work", "link_publication", "relate_works", "relate_publication",
    "revert", "retire")]


def seed_rules(con) -> None:
    for op, rule, pct, mi, note in DEFAULT_RULES:
        con.execute("INSERT INTO review_rules (op, rule, sample_pct, two_keys_min_impact, note) VALUES (%s,%s,%s,%s,%s)"
                    " ON CONFLICT (op) DO NOTHING", (op, rule, pct, mi, note))


# ------------------------------------------------------------------ the machine's reading (SQLite)
def open_reading(path: Path | str | None = None) -> sqlite3.Connection:
    """platform v2 (or a release copy), read-only. Never written."""
    p = Path(path or reading_path())
    if not p.exists():
        raise FileNotFoundError(p)
    con = sqlite3.connect(f"file:{p}?mode=ro", uri=True)
    con.row_factory = sqlite3.Row
    return con


def latest_release_path(con) -> Path | None:
    """The newest built release whose copy is still on disk: the state screens and validation read."""
    r = con.execute("SELECT path FROM releases WHERE status = 'built' AND copy_deleted_at IS NULL "
                    "ORDER BY finished_at DESC LIMIT 1").fetchone()
    if r and r["path"] and Path(r["path"]).exists():
        return Path(r["path"])
    return None


def state_path(con) -> Path:
    return latest_release_path(con) or reading_path()
