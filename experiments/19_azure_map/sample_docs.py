"""Draw documents at random from the corpus listing (out/listing.txt = `aws s3 ls s3://mandumah-source-docs/`).

    .venv/bin/python sample_docs.py [N] [--seed 19] [--more]   -> out/ids.txt   (run: 160, then 80 --more)
Only document prefixes (NNNN-...-NNN/) count; metadata/, legacy*/ and metrics.txt are not documents.
"""
import re, sys, random
from pathlib import Path
OUT = Path(__file__).resolve().parent / "out"
n = int(sys.argv[1]) if len(sys.argv) > 1 and sys.argv[1].isdigit() else 160
seed = int(sys.argv[sys.argv.index("--seed") + 1]) if "--seed" in sys.argv else 19
ids = [m.group(1) for l in open(OUT / "listing.txt") if (m := re.match(r"\s*PRE (\d{4}-[\d,-]+)/$", l))]
print(len(ids), "documents in the corpus")
if "--more" in sys.argv:                       # a second draw, from the documents not yet drawn, appended to ids.txt
    have = [l.strip() for l in open(OUT / "ids.txt") if l.strip()]; hs = set(have)
    pick = have + random.Random(seed + 1).sample([i for i in ids if i not in hs], n)
else:
    pick = random.Random(seed).sample(ids, n)
(OUT / "ids.txt").write_text("\n".join(pick) + "\n")
print(len(pick), "drawn ->", OUT / "ids.txt")
