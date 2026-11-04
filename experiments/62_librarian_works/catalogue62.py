"""Experiment 62, step 0: the machine's cards against Mandumah's catalogue, by experiment 48 probe A's own code
(classify / match / decide, imported unchanged through experiment 52's catalogue52, the matcher that gave gate 1's
16.9%), pointed at the release (read-only) and marc.db (read-only), over ALL 780 shown articles, not one journal.

This is the "before" catalogue view and the source of the catalogue candidates the librarian judges.

    nice python3 experiments/62_librarian_works/catalogue62.py extract|classify|match|decide|results [--db RELEASE]
        -> out/catalogue/{works,classified,matches,decisions}.jsonl, results.json
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "52_journal_gate1"))
import catalogue52 as C52  # noqa: E402

RELEASES = Path.home() / "data/desk/releases"


def newest_release() -> Path:
    """The release this pass was made on (pinned: R20261023T005909, override with LIBRARIAN62_RELEASE)."""
    sys.path.insert(0, str(Path(__file__).resolve().parent))
    from norm62 import release
    return release()


def all_current(con, run=None):
    return {r[0]: r[1] for r in con.execute("SELECT version_id, stem FROM versions WHERE is_current = 1")}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["extract", "classify", "match", "decide", "results"])
    ap.add_argument("--db", default=str(newest_release()))
    a = ap.parse_args()
    a.run = None
    C52.OUT = HERE / "out" / "catalogue"
    C52.versions = all_current
    C52.setup(a.db)
    {"extract": C52.cmd_extract, "classify": C52.cmd_classify, "match": C52.cmd_match, "decide": C52.cmd_decide,
     "results": C52.cmd_results}[a.cmd](a)


if __name__ == "__main__":
    sys.exit(main())
