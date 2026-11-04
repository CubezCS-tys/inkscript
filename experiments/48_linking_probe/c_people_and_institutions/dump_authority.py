"""Print an authority id's catalogue records grouped by journal (years, count, two titles, roles) for judging."""
import sys, json
from collections import defaultdict
from common48c import mcon
m = mcon()
def dump(aid):
    rows = m.execute("""SELECT r.year_int y, coalesce(r.journal, r.type, '?') j, r.title t, a.role, r.thesis, a.name, a.latin, r.country
                        FROM authors a JOIN records r ON r.rec=a.rec WHERE a.authority_id=? ORDER BY r.year_int""", (aid,)).fetchall()
    g = defaultdict(list)
    for r in rows: g[r["j"]].append(r)
    print(f"## {aid} {rows[0]['name']} | {rows[0]['latin']} | n={len(rows)}")
    for j, rs in sorted(g.items(), key=lambda x: min((r["y"] or 9999) for r in x[1])):
        ys = [r["y"] for r in rs if r["y"]]
        th = [json.loads(r["thesis"]).get("c") for r in rs if r["thesis"]]
        print(f"  {min(ys) if ys else '?'}-{max(ys) if ys else '?'} n{len(rs)} [{rs[0]['country']}] {j[:45]} :: " +
              " / ".join((r["t"] or "")[:55] for r in rs[:2]) + (f"  roles={sorted({r['role'] for r in rs})}" if any(r['role']!='مؤلف' for r in rs) else "") + (f" thesis={th}" if th else ""))
for a in sys.argv[1:]: dump(a)
