"""One-off (2026-10-20): recompute records.parallel_titles in marc.db with build45.parallel_titles (the first build
joined 246 $a and $b without trimming the ISBD ' :' of $a, giving 'Title: : Subtitle'). Idempotent."""
import sqlite3
import sys
from itertools import groupby
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from build45 import DB, parallel_titles  # noqa: E402

db = sqlite3.connect(DB)
rows = db.execute("SELECT rec, fseq, code, value FROM fields WHERE tag = '246' ORDER BY rec, fseq, sseq")
upd = []
for rec, g in groupby(rows, key=lambda r: r[0]):
    by_f = [[(c, v) for _, _, c, v in gf] for _, gf in groupby(g, key=lambda r: r[1])]
    upd.append((" | ".join(parallel_titles([("246", sf) for sf in by_f])), rec))
db.executemany("UPDATE records SET parallel_titles = ? WHERE rec = ? AND parallel_titles IS NOT ?", [(a, b, a) for a, b in upd])
db.execute("INSERT OR REPLACE INTO meta VALUES ('fix_parallel45', ?)", (f"{len(upd)} records recomputed",))
db.commit()
print(len(upd), "records with 246")
