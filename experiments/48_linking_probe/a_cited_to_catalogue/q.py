import sqlite3, sys
P="/home/appuser/data/platform_v2/platform_v2.db"; M="/home/appuser/data/marc/marc.db"
def pv(): return sqlite3.connect(f"file:{P}?mode=ro", uri=True)
def marc(): return sqlite3.connect(f"file:{M}?mode=ro&immutable=1", uri=True)
if __name__=="__main__":
    db = marc() if sys.argv[1]=="m" else pv()
    for s in sys.argv[2:]:
        print("==", s[:100])
        cur=db.execute(s)
        if cur.description: print([d[0] for d in cur.description])
        for r in cur.fetchall(): print(r)
