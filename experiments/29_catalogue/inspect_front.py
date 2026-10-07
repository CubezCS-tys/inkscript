"""Print, for some documents, the catalogue's title and names beside the words they were aligned to on the page.

    PYTHONPATH=src .venv/bin/python experiments/29_catalogue/inspect_front.py STEM [STEM ...]
"""
import json
import sys
from pathlib import Path

from lxml import etree

OUT = Path(__file__).resolve().parent / "out"
SET28 = Path("/home/yassine/inkscript/experiments/28_scale/out")
rows = {r["stem"]: r for r in json.loads((OUT / "after.json").read_text())}
for stem in sys.argv[1:]:
    r = rows[stem]
    alto = etree.parse(str(OUT / "after" / f"{stem}.alto.xml"))
    words = {s.get("ID"): s.get("CONTENT") for s in alto.iter("{*}String")}
    print("==", stem, r.get("catalogue_check"))
    print("  catalogue title:", r["title"], "|", r["subtitle"])
    print("  its ink        :", " ".join(words.get(i, "?") for i in r["title_word_ids"]), r["title_word_ids"][:1])
    for n, ids in zip(r["authors"], r["author_word_ids"]):
        print("  name:", n, "| ink:", " ".join(words.get(i, "?") for i in ids), ids[:1])
    print("  prefixes:", r["prefixes"], " page front:", r.get("page_front"))
