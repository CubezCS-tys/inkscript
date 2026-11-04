"""C1c. Authority errors: a profile of every authority id our 600 reach (and of 2,000 random catalogue authority ids,
seed 4821) from its catalogue records — years, journals, fields of study, publication countries, roles, thesis
universities — and a flag when the records look like two people. Then a seeded sample (seed 4821) of flagged and
unflagged ids is written out with the evidence, to be judged by reading. Read-only."""
from __future__ import annotations

import json
import random
import re
from collections import Counter

from common48c import OUT, mcon, progress, save


def profile(m, aid):
    rows = m.execute("""SELECT r.rec, r.c999, r.year_int, r.journal, r.fields_of_study, r.country, r.type, r.thesis,
                               r.title, a.name, a.latin, a.role FROM authors a JOIN records r ON r.rec = a.rec
                        WHERE a.authority_id = ? ORDER BY r.year_int""", (aid,)).fetchall()
    ys = [r["year_int"] for r in rows if r["year_int"] and 1850 < r["year_int"] < 2030]
    fos = Counter()
    for r in rows:
        for f in (r["fields_of_study"] or "").split(" | "):
            if f.strip():
                fos[f.strip()] += 1
    th = []
    for r in rows:
        if r["thesis"] and not re.search(r"مشرف|super|advis", r["role"] or "", re.I):
            try:
                t = json.loads(r["thesis"])
                th.append(t.get("c") or t.get("university") or str(t)[:60])
            except Exception:
                th.append(r["thesis"][:60])
    P = dict(authority_id=aid, n=len(rows), heading=rows[0]["name"] if rows else None,
             latin=rows[0]["latin"] if rows else None,
             year_min=min(ys) if ys else None, year_max=max(ys) if ys else None,
             span=(max(ys) - min(ys)) if ys else None, journals=len({r["journal"] for r in rows if r["journal"]}),
             fields=dict(fos.most_common(6)), countries=dict(Counter(r["country"] for r in rows if r["country"])),
             roles=dict(Counter(r["role"] for r in rows)), theses=th[:5],
             sample=[dict(year=r["year_int"], journal=r["journal"], title=(r["title"] or "")[:90], role=r["role"],
                          c999=r["c999"]) for r in rows][:: max(1, len(rows) // 12)][:14])
    # flags: what would make a cataloguer's "one person" look like two
    fl = []
    if P["span"] is not None and P["span"] >= 45:
        fl.append(f"span {P['span']} years")
    big = [f for f, n in fos.items() if n >= 2]
    if len(big) >= 4:
        fl.append(f"{len(big)} fields with 2+ records")
    if len([c for c, n in P["countries"].items() if n >= 2]) >= 3:
        fl.append("3+ publication countries")
    if len(th) >= 2 and len(set(th)) >= 2:
        fl.append("2+ theses at different universities")
    P["flags"] = fl
    return P


def main():
    m = mcon()
    by = json.load(open(OUT / "c1_bylines.json"))
    ours = sorted({r["authority_id"] for r in by if r["authority_id"] and not r["is_org"]})
    prof = [profile(m, a) for a in ours]
    save("c1_authority_profiles_ours.json", prof)
    progress(f"- c1_authority_profiles.py: {len(prof)} profiles of our authorities")
    # 2,000 random catalogue authority ids (seed 4821): pick random rec numbers, take their first person authority
    rnd = random.Random(4821)
    nrec = m.execute("SELECT max(rec) FROM records").fetchone()[0]
    cat = set()
    while len(cat) < 2000:
        rec = rnd.randint(1, nrec)
        for (aid,) in m.execute("SELECT authority_id FROM authors WHERE rec = ? AND authority_id IS NOT NULL AND "
                                "authority_id <> '' AND NOT coalesce(is_org,0) ORDER BY seq LIMIT 1", (rec,)):
            cat.add(aid)
    cprof = [profile(m, a) for a in sorted(cat)]
    save("c1_authority_profiles_random2000.json", cprof)

    def rate(ps):
        return dict(n=len(ps), flagged=sum(1 for p in ps if p["flags"]),
                    flags=dict(Counter(re.sub(r"\d+", "N", f) for p in ps for f in p["flags"])),
                    n_records_median=sorted(p["n"] for p in ps)[len(ps) // 2])
    S = dict(ours=rate(prof), random_catalogue_by_record=rate(cprof))
    # judge sample: 25 flagged + 15 unflagged of ours (seed 4821)
    rnd = random.Random(4821)
    fl = [p for p in prof if p["flags"]]
    un = [p for p in prof if not p["flags"] and p["n"] >= 3]
    samp = rnd.sample(fl, min(25, len(fl))) + rnd.sample(un, 15)
    save("c1_authority_judge_sample.json", samp)
    save("c1_authority_profiles_summary.json", S)
    progress(f"- c1_authority_profiles.py: summary {S}")
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
