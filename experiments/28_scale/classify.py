"""Keep the scans among the fresh candidates, per decade up to draw.py's targets, in draw order; link them into
out/azure beside experiment 19's scans.  Same rule as experiments/19_azure_map/classify.py: a document is
born-digital when most of its pages pass the pipeline's born_digital().   -> out/fresh_kinds.json, out/ids_fresh.txt
"""
import json, os, sys
from pathlib import Path
import pymupdf
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; sys.path.insert(0, str(HERE.parents[1] / "src"))
from inkscript.pdf.native import born_digital
sys.path.insert(0, str(HERE)); 
WANT = {"pre1960": 12, "196": 12, "197": 12, "198": 10, "199": 10, "200": 10, "201": 8, "202": 8}
kinds, keep, n = {}, [], {}
for l in open(OUT / "candidates.tsv"):
    i, y, j, d = l.rstrip("\n").split("\t"); f = OUT / "fresh" / i / f"{i}.pdf"
    r = dict(id=i, year=y, journal=j, decade=d)
    try:
        doc = pymupdf.open(str(f)); nb = sum(born_digital(p) for p in doc); fonts = set()
        for p in doc: fonts |= {x[3] for x in p.get_fonts()}
        r.update(pages=len(doc), bd_pages=nb, kind="born-digital" if nb > len(doc) / 2 else ("scan" if fonts <= {"Dummy"} else "scan+real-font"))
        doc.close()
        if not (OUT / "fresh" / i / f"{i}.json").exists(): r["kind"] = "no-json"
    except Exception as e:
        r.update(kind="error", err=str(e)[:200])
    kinds[i] = r
    if r["kind"].startswith("scan") and n.get(d, 0) < WANT[d]:
        n[d] = n.get(d, 0) + 1; keep.append(i)
        link = OUT / "azure" / i
        if not link.exists(): os.symlink(f"../fresh/{i}", link)
json.dump(kinds, open(OUT / "fresh_kinds.json", "w"), ensure_ascii=False, indent=1)
(OUT / "ids_fresh.txt").write_text("".join(i + "\n" for i in keep))
from collections import Counter
print(Counter(r["kind"] for r in kinds.values())); print("kept per decade", n, "total", len(keep))
