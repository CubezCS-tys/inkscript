import sys
sys.path.insert(0,'/home/appuser/inkscript/experiments/45_marc_db')
from build45 import fold
from q import marc
m=marc()
for q in sys.argv[1:]:
    print("==", q)
    for (rid,) in m.execute("select rowid from fts where fts match ? order by rank limit 8", (fold(q).replace(" and "," AND ").replace(" or "," OR ").replace(" not "," NOT "),)):
        r=m.execute("select c999,title,subtitle,year_int,journal,type from records where rec=?",(rid,)).fetchone()
        au=[a[0] for a in m.execute("select name from authors where rec=? order by seq",(rid,))][:3]
        print("  ", r, au)
