"""Draw candidate documents: one per journal, Arabic, by the catalogue's year.

    PYTHONPATH=../../src /home/yassine/inkscript/.venv/bin/python sample_docs.py [N=400]  -> out/cand_ids.txt
        printed 2005 or later (mostly born-digital: the line truth comes from their PDF text)
    ... sample_docs.py 160 --before 2000 -> out/old_ids.txt
        printed before 2000 (scans: Azure-read training lines for the scan-domain run), also skipping the journals
        already drawn above, so neither test set shares a journal with them
Journals already in experiment 19's draw are skipped (those documents are used as they are).
"""
import random, re, sys
from pathlib import Path
from inkscript.enrich.catalogue import open_catalogue
OUT = Path("/home/yassine/inkscript/experiments/33_kraken/out"); E19 = Path("/home/yassine/inkscript/experiments/19_azure_map/out")
n = int(sys.argv[1]) if len(sys.argv) > 1 else 400
ids = [m.group(1) for l in open(E19 / "listing.txt") if (m := re.match(r"\s*PRE (\d{4}-[\d,-]+)/$", l))]
used = {i[:4] for i in (l.strip() for l in open(E19 / "ids.txt")) if i}
before = int(sys.argv[sys.argv.index("--before") + 1]) if "--before" in sys.argv else None
if before:
    used |= {i[:4] for i in (l.strip() for l in open(OUT / "cand_ids.txt")) if i}
    if (OUT / "old_ids.txt").exists() and before < 2000:
        used |= {i[:4] for i in (l.strip() for l in open(OUT / "old_ids.txt")) if i}
    # never a journal held out by experiment 34's yardstick
    held = [l.split() for l in open("/home/yassine/inkscript/experiments/34_yardstick/out/heldout.txt") if l.strip()]
    used |= {b for a, b in held if a == "journal"}
random.Random(33 if not before else 34).shuffle(ids)
cat = open_catalogue(); pick = {}; seen = 0
for i in ids:
    j = i[:4]
    if j in used or j in pick: continue
    r = cat.get(i); seen += 1
    if not r: continue
    y = re.search(r"\d{4}", r.get("year") or "")
    if "ara" not in (r.get("lang") or []) or not y: continue
    if (before and int(y.group()) >= before) or (not before and int(y.group()) < 2005): continue
    pick[j] = i
    if len(pick) >= n: break
(OUT / (f"old{before % 100}_ids.txt" if before and before < 2000 else "old_ids.txt" if before else "cand_ids.txt")).write_text("\n".join(pick.values()) + "\n")
print(len(pick), "candidates from", seen, "looked up")
