"""Experiment 41: the sample (out/sample.json), chosen by hand from out/inventory.json with the reason for each.

Whole articles (every page) wherever the article is short enough; the exp 40 sample pages that sit in very long
documents (30-63 pages) are covered by a WINDOW: the sample page with two pages either side, run with the
article's page 1 attached as context only (the chunk path of a long article, as in exp 40 E).

    /home/yassine/inkscript/.venv/bin/python choose_sample.py
"""
from __future__ import annotations

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"

# stem -> why   (whole articles)
WHOLE = {
    # experiment 40's sample documents (its truth pages, referee pages and whole documents)
    "0005-055-003-004": "exp 40: owner gold p8 (numbered list); referee page",
    "0018-010-003-002": "exp 40: owner gold p3, pre-1960 print; referee page",
    "0197-002-001-003": "exp 40: owner gold p3, 1960s; exp 40 whole document",
    "0355-000-002-006": "exp 40: owner gold p17, two columns; 24 pages, the long-article chunk path",
    "0058-023-003-005": "exp 40: owner gold p3 (headings, list); 24 pages, chunked",
    "0767-010-002-007": "exp 40: born-digital front page p1 (title, authors, abstract, Latin)",
    "0493-000-029-001": "exp 40: born-digital three-column magazine p2, p3",
    "0924-012-005-007": "exp 40: pre-1960 accounts tables, two columns; referee page",
    "0732-019-222,224-040": "exp 40: decorative free verse in four columns; referee page",
    "0747-001-003-001": "exp 40: pre-1960 vowelled verse with footnotes; whole document; referee page",
    "0877-007-027-003": "exp 40: 1960s two columns with footnotes; referee page",
    "0513-001-001-011": "exp 40: pre-1960 old print with Latin; referee page",
    "0692-000-009-023": "exp 40: pre-1960 Quran, two columns; referee page",
    "0690-037-002-014": "exp 40: 1960s one-page front page (title, author, Quran); referee page",
    "2382-005-003-001": "exp 40: 2020s equations and regression tables; whole document; referee page",
    # every other document with owner gold pages (status done), all short
    "0260-000-008-013": "owner gold p5; 1970s; referee page",
    "0322-000-015-014": "owner gold p4; 2000s; referee page",
    "0331-000-054-001": "owner gold p4; 1980s; referee page",
    "0367-000-092-026": "owner gold p11; 1990s",
    "0382-016-063-013": "owner gold p3; 1990s; ruled tables",
    "0407-009-001-028": "owner gold p3; 1970s",
    "0408-002-010-007": "owner gold p3; 1960s",
    "0422-004-006-018": "owner gold p2; 2000s",
    "0447-000-006-007": "owner gold p2; 1970s",
    "0498-000-388-003": "owner gold p6; 2000s; ruled tables",
    "0513-006-003-007": "owner gold p3; pre-1960",
    "0549-021-248-007": "owner gold p5; 1980s; ruled tables",
    "0629-021-011-009": "owner gold p5; 1980s; ruled tables",
    "0656-016-001-011": "owner gold p3; 1960s",
    # born-digital documents (the PDF's own text is the truth on two pages)
    "0418-000-136-002": "born-digital truth p2, p4; 2020s",
    "0920-011-020-009": "born-digital truth p2, p3; 2010s",
    "1148-041-116-018": "born-digital truth p4, p7; 2010s; much English",
    "7956-000-000-016": "born-digital truth p1; 2020s; half English",
    "2571-006-011-016": "born-digital truth p1, p9; 2020s",
    # more referee-labelled documents
    "0781-010-055-015": "referee page p6; 2000s",
    "0881-018-206-009": "referee page p3; 1990s",
    "1147-000-007-006": "referee page p4; 2000s; English",
    # stratified fill (catalogue master): features
    "1140-000-021-003": "French article, 2010s",
    "1769-014-002-002": "equations and tables with English, 2010s",
    "1010-014-001-012": "1960s two columns with footnotes and ruled tables",
    "1106-025-001-001": "2020s tables (29 ruled-grid pages in the pool), English",
    "1054-023-010-019": "pre-1960 two columns with footnotes (al-Azhar)",
    "0049-001-999-012": "1980s footnotes and English",
}

# stem -> (sample page, why)   (windows of long documents: page +-2, page 1 as context)
WINDOW = {
    "0266-006-002-001": (42, "exp 40: 1990s heavy footnotes (48 pages); referee page"),
    "0474-008-013-001": (36, "exp 40: 1980s equations in a numbered list (61 pages); referee page"),
    "0682-000-092-014": (27, "exp 40: 2010s equations, footnotes, Latin (63 pages); referee page"),
    "0200-000-140-006": (22, "exp 40: 2020s table with Latin (32 pages); referee page"),
    "0478-007-002-005": (6, "exp 40: equations on a three-column magazine page (30 pages); referee page"),
    "1000-000-020-028": (19, "exp 40: vowelled Quran, verse, footnotes (30 pages); referee page"),
    "0694-000-023-013": (27, "exp 40: Latin reference list (29 pages); referee page"),
    "0198-012-003-001": (15, "exp 40: born-digital table page p15 (26 pages)"),
    "2502-000-041-029": (21, "exp 40: born-digital table with Latin p21 (48 pages)"),
    "0870-017-001-003": (7, "exp 40: 1970s mixed Arabic / Latin with footnotes (22 pages); referee page"),
    "0737-001-020-003": (9, "exp 40: pre-1960 three-column magazine (21 pages); referee page"),
    "0041-002-005-008": (12, "owner gold p12 (37 pages); referee page"),
}


def main():
    inv = {r["stem"]: r for r in json.loads((OUT / "inventory.json").read_text(encoding="utf-8"))}
    arts = []
    for stem, why in WHOLE.items():
        r = inv[stem]
        arts.append(dict(stem=stem, kind="whole", first=1, last=r["pages"], why=why))
    for stem, (p, why) in WINDOW.items():
        r = inv[stem]
        a, b = max(1, p - 2), min(r["pages"], p + 2)
        arts.append(dict(stem=stem, kind="window", first=a, last=b, why=why))
    for a in arts:
        r = inv[a["stem"]]
        rng = range(a["first"], a["last"] + 1)
        a.update(pages_total=r["pages"], n=len(rng), pdf=r["pdf"], azure=r["azure"], decade=r["decade"],
                 year=r["year"], journal=r["journal"], jats=r["jats"],
                 gold=[p for p in r["gold_done"] if p in rng], bd=[p for p in r["bd_pages"] if p in rng],
                 referee=[p for p in r["referee_pages"] if p in rng], exp40=r["exp40_kind"])
    from collections import Counter
    S = dict(made="2026-10-15", articles=arts,
             counts=dict(units=len(arts), whole=sum(a["kind"] == "whole" for a in arts),
                         windows=sum(a["kind"] == "window" for a in arts), pages=sum(a["n"] for a in arts),
                         gold_pages=sum(len(a["gold"]) for a in arts), bd_pages=sum(len(a["bd"]) for a in arts),
                         referee_pages=sum(len(a["referee"]) for a in arts),
                         with_jats=sum(1 for a in arts if a["jats"]),
                         journals=len({a["stem"][:4] for a in arts}),
                         decades=dict(Counter(a["decade"] for a in arts))))
    (OUT / "sample.json").write_text(json.dumps(S, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(S["counts"], ensure_ascii=False))


if __name__ == "__main__":
    main()
