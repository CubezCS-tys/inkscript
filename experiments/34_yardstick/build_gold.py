"""Draft the chosen pages into the gold dir (experiment 34).

    PYTHONPATH=src python build_gold.py      -> out/gold/<page_id>.json + .jpg (an existing page is never touched)

Each page: Azure's lines in reading order with boxes, blocks with the build's kinds and their column, the page as a
300 dpi grey JPEG (gold/draft.py), and the page's facts from selection.json (kinds, decade, journal, split).
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

from inkscript.gold.draft import write_pages

OUT = Path("/home/yassine/inkscript/experiments/34_yardstick/out")


def main() -> int:
    sel = json.loads((OUT / "selection.json").read_text())
    pool = json.loads((OUT / "pool.json").read_text())
    by_doc = defaultdict(list)
    for s in sel:
        by_doc[s["stem"]].append(s)
    n = 0
    for stem, rows in sorted(by_doc.items()):
        p = pool[stem]
        meta = dict(stem=stem, split=rows[0]["split"], decade=rows[0]["decade"], year=rows[0]["year"],
                    journal=rows[0]["journal"], field=rows[0]["field"],
                    pages={r["page"]: dict(kinds=r["kinds"], primary=r["primary"]) for r in rows})
        got = write_pages(p["azure"], p["scan"], [r["page"] for r in rows], OUT / "gold", meta)
        n += len(got)
        print(stem, got, flush=True)
    print(n, "pages drafted")
    return 0


if __name__ == "__main__":
    sys.exit(main())
