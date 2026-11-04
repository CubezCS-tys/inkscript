"""Experiment 68: does every Desk decision keyed on a printed affiliation (aff:<stem>|b<n>|<script>|a<n>) still find
its row, with the same printed text, in a platform DB (current versions)? Read-only on PostgreSQL and the DB.
    affkeys68.py DB [DB ...]   -> per DB: found same text / found other text / missing; examples; twin rows hit"""
import json
import sqlite3
import sys

import psycopg

SQL = """SELECT am.aff_pk, am.printed, am.twin_of_aff_pk, am.lang FROM affiliation_mentions am
         JOIN byline_mentions bm ON bm.mention_pk = am.mention_pk
         JOIN versions v ON v.version_id = bm.version_id AND v.is_current = 1
         WHERE v.stem = ? AND bm.byline_pos = ? AND bm.script = ? AND am.seq = ?"""


def main():
    pg = psycopg.connect("dbname=inkdesk")
    rows = pg.execute("SELECT decision_id, op, subject_keys, evidence->>'printed' FROM desk.decisions "
                      "WHERE status = 'accepted' AND EXISTS (SELECT 1 FROM unnest(subject_keys) k WHERE k LIKE 'aff:%')"
                      ).fetchall()
    out = {}
    for db in sys.argv[1:]:
        con = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
        cols = {r[1] for r in con.execute("PRAGMA table_info(affiliation_mentions)")}
        sql = SQL if "twin_of_aff_pk" in cols else SQL.replace("am.twin_of_aff_pk, am.lang", "NULL, NULL")
        st = dict(decisions=len(rows), same=0, other_text=0, missing=0, on_twin_row=0, examples=[])
        for did, op, keys, printed in rows:
            for k in keys:
                if not k.startswith("aff:"):
                    continue
                stem, b, scr, a = k[4:].split("|")
                r = con.execute(sql, (stem, int(b[1:]), scr, int(a[1:]))).fetchall()
                if not r:
                    st["missing"] += 1
                    st["examples"].append(dict(k=k, op=op, printed=printed, got=None))
                elif printed is not None and r[0][1] != printed:
                    st["other_text"] += 1
                    st["examples"].append(dict(k=k, op=op, printed=printed, got=r[0][1]))
                else:
                    st["same"] += 1
                if r and r[0][2] is not None:
                    st["on_twin_row"] += 1
        out[db] = st
        print(db, {k: v for k, v in st.items() if k != "examples"})
        for e in st["examples"][:15]:
            print("   ", json.dumps(e, ensure_ascii=False))
    json.dump(out, open("/home/appuser/inkscript/experiments/68_go_live/out/affkeys68.json", "a"), ensure_ascii=False,
              indent=1)


main()
