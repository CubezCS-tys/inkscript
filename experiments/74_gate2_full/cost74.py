"""Experiment 74: spend per journal and part, from experiment 43's log rows written after this experiment began (row
4,174 on; the log was $127.387 / 4,173 rows) and the librarian logs out/<J>/lib/spend.jsonl. A row belongs to the
journal whose stem its tag names; parts: read (run43, incl. resends / rechunks), judge, retry (judge page retries),
word (the Word route's model step), librarian.   python3 cost74.py [--json]"""
import json, re, sys
from collections import defaultdict
from pathlib import Path
HERE = Path(__file__).resolve().parent
LOG = HERE.parent / "43_rehearsal" / "out" / "gemini_spend.jsonl"
START = 4173
out = defaultdict(lambda: defaultdict(float))
for i, l in enumerate(open(LOG)):
    if i < START or not l.strip():
        continue
    r = json.loads(l)
    t = r.get("tag") or ""
    m = re.search(r"(\d{4})-\d{3}-\d{3}-\d{3}", t)
    j = m.group(1) if m else "?"
    part = ("retry" if "retry" in t else "judge" if t.startswith("judge") else "word" if re.match(r"w\d{4}", t)
            else "read")
    out[j][part] += r.get("usd") or 0
for f in sorted(HERE.glob("out/*/lib/spend.jsonl")):
    j = f.parts[-3]
    out[j]["librarian"] += sum(json.loads(l).get("usd") or 0 for l in open(f) if l.strip())
res = {j: {k: round(v, 3) for k, v in sorted(d.items())} | {"total": round(sum(d.values()), 3)} for j, d in sorted(out.items())}
res["ALL"] = round(sum(v["total"] for v in res.values()), 3)
print(json.dumps(res, indent=1) if "--json" in sys.argv else "\n".join(f"{j}: {v}" for j, v in res.items()))
