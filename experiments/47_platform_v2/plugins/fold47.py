"""Datasette plugin (experiment 47): fold(text) and stem47(text) as SQL functions, the same Arabic search forms the
loader indexes (experiment 45/46 folding; clitics و ف ب ك ل ال stripped), so a query reads MATCH fold(:q)."""
import sys
from pathlib import Path

from datasette import hookimpl

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from common47 import fold, stemmed  # noqa: E402


@hookimpl
def prepare_connection(conn):
    conn.create_function("fold", 1, lambda s: fold(s), deterministic=True)
    conn.create_function("stem47", 1, lambda s: stemmed(s), deterministic=True)
