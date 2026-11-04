"""Experiment 68: are the public ids stable across the reload? Read-only.

    ids68.py snap DB OUT.json          every public id of a platform DB (persons A…, institutions I…, cited works C…,
                                       publications W…), its status, and merged_ids
    ids68.py compare BEFORE.json DB    each id present before: still a row (live / its status) or reached through
                                       merged_ids to a live row; ids new after (minted); the ids the Desk's decisions
                                       name, the same way
"""
from __future__ import annotations

import json
import re
import sqlite3
import sys
from collections import Counter

TABLES = {"person": ("persons", "person_id"), "institution": ("institutions", "inst_id"),
          "cited_work": ("cited_works", "cited_work_id"), "publication": ("publications", "pub_id")}


def ro(db):
    return sqlite3.connect(f"file:{db}?mode=ro", uri=True)


def snap(db):
    c = ro(db)
    out = {}
    for k, (t, col) in TABLES.items():
        cols = {r[1] for r in c.execute(f"PRAGMA table_info({t})")}
        st = "status" if "status" in cols else "NULL"
        out[k] = {r[0]: r[1] for r in c.execute(f"SELECT {col}, {st} FROM {t}")}
    out["merged"] = {r[0]: r[1] for r in c.execute("SELECT old_id, new_id FROM merged_ids")}
    out["registry"] = {r[0]: r[1] for r in c.execute("SELECT public_id, natural_key FROM id_registry")}
    return out


def resolve(S, kind, i):
    seen = set()
    while i not in seen:
        seen.add(i)
        st = S[kind].get(i, "__gone__")
        if st != "__gone__" and st != "merged":
            return i
        if i in S["merged"]:
            i = S["merged"][i]
            continue
        return None
    return None


def desk_ids():
    import psycopg
    pg = psycopg.connect("dbname=inkdesk")
    ids = Counter()
    for keys, payload in pg.execute("SELECT subject_keys, payload::text FROM desk.decisions WHERE status = 'accepted'"):
        txt = " ".join(keys) + " " + payload
        for m in re.finditer(r"\b(person:A|inst:I|work:C|pub:W)([0-9A-Z]+)\b", txt):
            ids[{"person:A": "person", "inst:I": "institution", "work:C": "cited_work",
                 "pub:W": "publication"}[m[1]], m[1].split(":")[1] + m[2]] += 1
    return ids


def compare(before_json, db):
    B = json.load(open(before_json, encoding="utf-8"))
    A = snap(db)
    rep = {}
    for k in TABLES:
        old, new = B[k], A[k]
        st = Counter()
        lost = []
        for i, s in old.items():
            if s == "merged":
                st["was merged"] += 1
                if resolve(A, k, i) is None:
                    lost.append(i)
                continue
            r = resolve(A, k, i)
            if r == i:
                st["same row"] += 1
            elif r:
                st["through merged_ids"] += 1
            else:
                st["LOST"] += 1
                lost.append(i)
        minted = [i for i in new if i not in old]
        rep[k] = dict(before=len(old), after=len(new), **st, lost=lost[:50], n_lost=len(lost), minted=len(minted),
                      minted_examples=[(i, A["registry"].get(i)) for i in minted[:15]])
    D = desk_ids()
    dk = Counter()
    bad = []
    for (k, i), n in D.items():
        if k == "publication":       # catalogued-only publications the Desk adds itself (exp 67) are not in the reading
            if i in A[k] or resolve(A, k, i):
                dk[k + " ok"] += 1
            elif i in B[k]:
                bad.append((k, i))
            else:
                dk[k + " added by the Desk"] += 1
            continue
        if resolve(A, k, i):
            dk[k + " ok"] += 1
        elif i in B[k] or resolve(B, k, i):
            bad.append((k, i))
            dk[k + " LOST"] += 1
        else:
            dk[k + " minted by the Desk"] += 1
    rep["desk_ids"] = dict(dk)
    rep["desk_ids_lost"] = bad[:50]
    return rep


if __name__ == "__main__":
    if sys.argv[1] == "snap":
        json.dump(snap(sys.argv[2]), open(sys.argv[3], "w", encoding="utf-8"), ensure_ascii=False)
        print("snap", {k: len(v) for k, v in json.load(open(sys.argv[3])).items()})
    else:
        r = compare(sys.argv[2], sys.argv[3])
        print(json.dumps(r, ensure_ascii=False, indent=1))
