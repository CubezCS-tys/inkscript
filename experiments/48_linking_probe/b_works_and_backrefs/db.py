import sqlite3, sys
DB = "/home/appuser/data/platform_v2/platform_v2.db"
OUT = "/home/appuser/inkscript/experiments/48_linking_probe/out/b_works_and_backrefs"
def con():
    c = sqlite3.connect(f"file:{DB}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c
if __name__ == "__main__":
    c = con()
    for q in sys.argv[1:]:
        for r in c.execute(q):
            print(tuple(r))
