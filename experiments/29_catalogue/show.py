"""Before / after front matter of some documents as text (for checking beside out/look/<stem>.jpg).

    python experiments/29_catalogue/show.py STEM [STEM ...]
"""
import json
import sys
from pathlib import Path

OUT = Path(__file__).resolve().parent / "out"
rows = {m: {r["stem"]: r for r in json.loads((OUT / f"{m}.json").read_text())} for m in ("before", "after")}
KEYS = ("title", "subtitle", "authors", "prefixes", "affs", "journal", "year", "volume", "issue", "fpage", "lpage", "title_source")
for s in sys.argv[1:]:
    print("=====", s, rows["after"][s].get("catalogue_check", {}).get("verdict"))
    for m in ("before", "after"):
        r = rows[m][s]
        print(f"  {m:6}", {k: r[k] for k in KEYS if r.get(k)})
