"""Tests run against throwaway schemas `test_<pid>_<module>` inside `inkdesk` (appuser may not CREATE DATABASE here),
dropped afterwards, and a throwaway folder under /home/appuser/data/desk/ for release copies, removed afterwards.
platform_v2.db is only ever opened read-only; anything that writes works on a copy."""
from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
TEST_DIR = Path(f"/home/appuser/data/desk/test_{os.getpid()}")
os.environ["DESK_RELEASES"] = str(TEST_DIR / "releases")
os.environ.setdefault("DESK_SCHEMA", f"test_{os.getpid()}")

from desk import db  # noqa: E402


@pytest.fixture(scope="module")
def schema(request):
    name = f"test_{os.getpid()}_{Path(request.module.__file__).stem.replace('test_', '')}"
    old = os.environ.get("DESK_SCHEMA")
    os.environ["DESK_SCHEMA"] = name
    db.init_schema(name, drop=True)
    yield name
    db.drop_schema(name)
    if old is not None:
        os.environ["DESK_SCHEMA"] = old


@pytest.fixture(scope="module")
def pg(schema):
    con = db.connect(schema)
    yield con
    con.rollback()
    con.close()


@pytest.fixture(scope="session")
def test_dir():
    TEST_DIR.mkdir(parents=True, exist_ok=True)
    yield TEST_DIR
    shutil.rmtree(TEST_DIR, ignore_errors=True)


def add_actor(pg, actor_id, role="corrector", skills=("ar", "en", "fr")):
    pg.execute("INSERT INTO actors (actor_id, kind, name, role, skills) VALUES (%s, %s, %s, %s, %s) "
               "ON CONFLICT DO NOTHING", (actor_id, actor_id.split(":")[0], actor_id, role, list(skills)))
    pg.commit()
