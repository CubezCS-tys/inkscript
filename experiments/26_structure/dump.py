"""Print a document's paragraphs (page, role, box, letter height, text) to help write the truth by eye.

    python dump.py AZURE_DIR STEM [PAGES]
"""
import statistics
import sys
from pathlib import Path

from inkscript.enrich.document import load, para_box

AZ = Path(sys.argv[1])
stem = sys.argv[2]
pages = {int(x) for x in sys.argv[3].split(",")} if len(sys.argv) > 3 else None
doc = load(AZ / stem / f"{stem}.json")
W = doc["words"]
for p in doc["paras"]:
    pg = W[p["words"][0]]["page"]
    if pages and pg not in pages:
        continue
    H = doc["pages"][pg]["h"]
    b = para_box(doc, p, pg)
    h = statistics.median(W[k]["box"][3] - W[k]["box"][1] for k in p["words"])
    t = " ".join(W[k]["text"] for k in p["words"])
    print(f"p{pg} #{p['idx']:<4} {str(p.get('kind')):15} y={b[1] / H:.2f}-{b[3] / H:.2f} x={b[0]:.0f}-{b[2]:.0f} "
          f"h={h:.0f} n={len(p['words'])} {W[p['words'][0]]['id']}  {t[:110]}")
