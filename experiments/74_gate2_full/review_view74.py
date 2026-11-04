"""Experiment 74: the authority-review sheet for journal J: every body the models named outside the authority, with
the machine row(s) of that name on the release, a printed statement and Opus' answer. Read by hand to write
out/J/lib/inst/review74_input.json.   python3 review_view74.py J RELEASE"""
import json, sqlite3, sys
J, R = sys.argv[1], sys.argv[2]
c = sqlite3.connect(f"file:{R}?mode=ro", uri=True)
for x in json.load(open(f"out/{J}/lib/inst/review_candidates.json")):
    nm = x["names"][0]
    if len(nm) == 10 and nm.startswith("I") and nm.isupper():
        r = c.execute("select kind,country_code,parent_id from institutions where inst_id=?", (nm,)).fetchone()
        lab = [y[0] for y in c.execute("select name from institution_names where inst_id=? order by n_seen desc limit 2", (nm,))]
        rows = [(nm,) + tuple(r or ())]
    else:
        lab = ""
        rows = c.execute("select n.inst_id,i.kind,i.country_code,i.parent_id from institution_names n join institutions i "
                         "using(inst_id) where n.name=? and i.status='active'", (nm,)).fetchall()[:2]
    q = x["questions"][0]
    print(nm[:60], str(lab)[:60], x["countries"], "n=", len(x["questions"]), "| rows", rows, "| e.g.",
          str(q["printed"])[:100], "| O:", q["opus"], q["opus_conf"])
