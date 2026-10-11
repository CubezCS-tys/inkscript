"""The pool of scanned documents the gold pages are drawn from (experiment 34).

    python pool.py            -> out/pool.json: every candidate document with its catalogue facts

Sources, all scanned (born-digital pages need no reading; experiment 19's rule):
  * experiment 28's 205 scanned documents (Azure JSON + scan in experiments/28_scale/out/azure/<stem>/), drawn at
    random from the archive (127 from experiment 19, 78 fresh), none used to tune a rule;
  * extra documents fetched for this experiment to fill strata the random set is thin in (pre-1970 prints,
    cultural magazines laid out like newspapers, science journals with equations): out/extra/<stem>/, chosen by
    extra.py from the catalogue (see README).
Facts from the MARC catalogue index (experiment 29): year, journal, discipline, kind of record.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
MAIN = Path("/home/yassine/inkscript")
OUT = MAIN / "experiments/34_yardstick/out"
SOURCES = [MAIN / "experiments/28_scale/out/azure", OUT / "extra"]


def decade(year: str) -> str:
    y = "".join(c for c in str(year) if c.isdigit())[:4]
    if len(y) < 4:
        return "unknown"
    y = int(y)
    if y < 1960:
        return "pre-1960"
    return f"{y // 10 * 10}s"


def main() -> int:
    from inkscript.enrich.catalogue import open_catalogue
    cat = open_catalogue()
    pool = {}
    for src in SOURCES:
        if not src.exists():
            continue
        for d in sorted(src.iterdir()):
            j, pdf = d / f"{d.name}.json", d / f"{d.name}.pdf"
            if not (j.exists() and pdf.exists()):
                continue
            r = cat.get(d.name) if cat else None
            r = r or {}
            jm = r.get("journal", {})
            pool[d.name] = dict(stem=d.name, azure=str(j), scan=str(pdf), source="exp28" if src.name == "azure" else "extra",
                                year=r.get("year", ""), decade=decade(r.get("year", "")),
                                journal=jm.get("title", ""), field=(jm.get("fields_en") or jm.get("fields") or [""])[0],
                                type=r.get("type_en") or r.get("type", ""), title=r.get("title", ""))
    (OUT / "pool.json").write_text(json.dumps(pool, ensure_ascii=False, indent=1), encoding="utf-8")
    from collections import Counter
    print(len(pool), "documents")
    print(sorted(Counter(p["decade"] for p in pool.values()).items()))
    print(Counter(p["source"] for p in pool.values()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
