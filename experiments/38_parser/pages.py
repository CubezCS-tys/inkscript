"""Experiment 38: the pages the parser is run on -> out/pages.json.

    /home/yassine/inkscript/.venv/bin/python pages.py

About 30 of the hardest yardstick pages, chosen by hand from their kinds (experiment 34's tags and dots.mocr's
block categories), every one of them with an experiment-35 edition of its document so the comparison is like for
like, plus every gold page whose status is "done" when this runs (text accuracy against truth). Inference only:
nothing is tuned on these pages.
"""
from __future__ import annotations

import json
from pathlib import Path

from common import GOLD, OUT, OLD_EDITIONS

HARD = {
    # tables
    "0073-000-239-002_p024": "magazine page with a ruled table",
    "0200-000-140-006_p022": "table with Latin headers and a caption, section heading",
    "0460-005-002-007_p024": "two tables on one page, 1980s print",
    "0495-109-002-003_p011": "two charts with captions, a bilingual table, Latin headings (2025)",
    "0827-000-051-002_p014": "ruled table with caption and Latin (reviewed in experiment 37)",
    "0881-018-206-009_p003": "magazine page: picture, table, 28 text blocks, headings",
    "0924-012-005-007_p002": "three tables, pre-1960 print",
    "1911-002-002-004_p019": "four pictures, a table, Latin",
    # equations
    "0474-008-013-001_p036": "displayed equation and list items, 1980s",
    "0478-007-002-005_p006": "equation and a ruled table on a magazine page (experiment 37: table lost)",
    "0562-028-109-009_p030": "two formulas and a table",
    "0682-000-092-014_p027": "equation, footnotes, Latin",
    "2025-067-002-007_p061": "equation, table, caption, list, footnote",
    "2382-005-003-001_p005": "six numbered equations, a diagram with its caption",
    # magazines, decorative pages, pictures
    "0299-000-004-010_p002": "magazine page with a picture and Quran, 1970s",
    "0465-011-001,002-009_p001": "decorative first page, 21 blocks",
    "0732-019-222,224-040_p001": "decorative magazine first page, five headings",
    "0735-005-009,010-002_p001": "decorative first page with a picture and Latin, 1960s",
    "1865-000-143-005_p017": "magazine page with a picture and Latin (2020s)",
    "7894-000-000-002_p003": "decorative magazine page, Latin, five headings",
    "0781-010-055-015_p006": "magazine page with 23 text blocks and Latin",
    "0737-001-020-003_p009": "pre-1960 magazine columns",
    # footnotes
    "0877-007-027-003_p004": "19 footnote blocks, 1960s",
    "0266-006-002-001_p042": "footnotes and verse (reviewed in experiment 37)",
    # Latin mixed in
    "0694-000-023-013_p027": "26 reference list items mixing Arabic and Latin (reviewed in experiment 37)",
    "0870-017-001-003_p007": "Latin footnotes, 1970s",
    "0513-001-001-011_p003": "Latin in a pre-1960 print",
    # vowelled text, Quran
    "0747-001-003-001_p006": "fully vowelled pre-1960 page, footnotes",
    "0690-037-002-014_p001": "Quran, two pictures, headings, 1960s",
    "0596-033-004-021_p002": "Quran, a picture, four headings",
    "1000-000-020-028_p019": "vowelled Quran with footnotes",
    # old print
    "0691-043-001,004-038_p008": "1960s table",
    "0692-000-009-023_p003": "pre-1960 Quran page with footnotes",
}


def main():
    rows = []
    for f in sorted(GOLD.glob("*.json")):
        g = json.loads(f.read_text(encoding="utf-8"))
        pid = g["page_id"]
        why = HARD.get(pid)
        done = g.get("status") == "done"
        if not why and not done:
            continue
        old = OLD_EDITIONS / g["stem"] / f"{g['stem']}.layout.pdf"
        rows.append(dict(page_id=pid, stem=g["stem"], page=g["page"], kinds=g["kinds"], primary=g["primary"],
                         decade=g["decade"], split=g["split"], gold_done=done, hard=bool(why),
                         why=why or "gold page (status done): text accuracy against truth",
                         old_edition=str(old) if old.exists() else None))
    missing = sorted(set(HARD) - {r["page_id"] for r in rows})
    assert not missing, missing
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "pages.json").write_text(json.dumps(dict(
        about="Experiment 38's pages: the hardest yardstick pages by kind (each with an experiment-35 edition of "
              "its document) and every gold page done at the time of the run. Inference only, never tuned on.",
        pages=rows), ensure_ascii=False, indent=1), encoding="utf-8")
    print(len(rows), "pages:", sum(r["hard"] for r in rows), "hard,", sum(r["gold_done"] for r in rows), "gold done,",
          sum(not r["old_edition"] for r in rows), "without an old edition")


if __name__ == "__main__":
    main()
