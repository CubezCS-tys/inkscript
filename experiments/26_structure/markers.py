"""Survey: how note markers look in Azure's words (glued, bracketed, bare raised digits) on one document's pages.

    python markers.py AZURE_DIR STEM [PAGES]
"""
import re
import sys
from pathlib import Path

from inkscript.enrich.document import load

AZ = Path(sys.argv[1])
stem = sys.argv[2]
pages = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None
doc = load(AZ / stem / f"{stem}.json")
W = doc["words"]
D = re.compile(r"[0-9٠-٩]")
for w in W:
    if pages and w["page"] not in pages:
        continue
    if D.search(w["text"]):
        L = doc["lines"][w["page"]][w["line"]]
        lh = sorted(W[k]["box"][3] - W[k]["box"][1] for k in L)
        med = lh[len(lh) // 2]
        print(w["id"], repr(w["text"]), f"h={w['box'][3] - w['box'][1]:.0f} lineMed={med:.0f} linelen={len(L)}",
              f"ytop={w['box'][1]:.0f} lineTop={min(W[k]['box'][1] for k in L):.0f}", doc["paras"][w["para"]].get("kind"))
