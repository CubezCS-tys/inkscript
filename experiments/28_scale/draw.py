"""Draw fresh documents for the set, stratified by decade, one per journal, Arabic only, from the documents in the
bucket that experiment 19 did not draw (out/catalogue.tsv x experiments/19_azure_map/out/listing.txt).
Recent decades are drawn with extra candidates because most of their documents are born-digital; `classify.py`
keeps the scans.     .venv/bin/python draw.py   -> out/candidates.tsv (id, year, journal, decade)
"""
import re, random, collections, json
from pathlib import Path
HERE = Path(__file__).resolve().parent; OUT = HERE / "out"; X19 = HERE.parent / "19_azure_map" / "out"
WANT = {"pre1960": 12, "196": 12, "197": 12, "198": 10, "199": 10, "200": 10, "201": 8, "202": 8}   # scans to keep
OVER = {"pre1960": 1.5, "196": 1.5, "197": 1.5, "198": 1.6, "199": 1.8, "200": 2.5, "201": 3.5, "202": 4.5}
bucket = set(m.group(1) for l in open(X19 / "listing.txt") if (m := re.match(r"\s*PRE (\d{4}-[\d,-]+)/$", l)))
taken = set(l.strip() for l in open(X19 / "ids.txt") if l.strip())
meta19 = json.load(open(X19 / "meta.json"))
seen_j = {v.get("journal") for v in meta19.values()}
pool = collections.defaultdict(list)
for l in open(OUT / "catalogue.tsv"):
    i, y, j, lang, k = l.rstrip("\n").split("\t")
    m = re.search(r"(1[89]\d\d|20[0-2]\d)", y)
    if i not in bucket or i in taken or lang != "ara" or not m: continue
    d = m.group(1)[:3]; d = "pre1960" if d < "196" else d
    pool[d].append((i, m.group(1), j))
rng = random.Random(28); rows = []
for d, n in WANT.items():
    c = pool[d]; rng.shuffle(c); got = []; js = set()
    for i, y, j in c:
        if j in js or j in seen_j: continue          # a journal not yet in the set, once
        js.add(j); got.append((i, y, j, d))
        if len(got) >= round(n * OVER[d]): break
    rows += got; print(d, len(pool[d]), "in the pool,", len(got), "drawn")
(OUT / "candidates.tsv").write_text("".join("\t".join(r) + "\n" for r in rows))
(OUT / "candidate_ids.txt").write_text("".join(r[0] + "\n" for r in rows))
print(len(rows), "candidates")
