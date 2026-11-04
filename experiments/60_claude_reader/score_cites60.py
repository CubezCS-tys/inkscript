"""Experiment 60, test 1: the proof pack's sampled citations (69 of 80 sent), fields right / loose / missing / wrong.
Argon = the proof's verdicts (fix round 3 changed none). Claude = Argon's where Claude's parsed work equals Argon's
(cites60.py), else the hand verdicts below; a work Claude did not parse at all (no element-citation for it in the
master: most are footnote works, where Claude often gives no "cites") has every field missing.
    -> out/t1/cite_scores.json"""
import json
from collections import Counter
from common60 import OUT, jdump
rows = json.loads((OUT / "t1/cites_claude.json").read_text())
NOT_PARSED = {41, 44}       # matched another work of the same article / note: this work itself is not parsed
HAND = {   # i: (field verdicts that change from Argon's, why)
 1: ({"title": "missing"}, "article title not given"),
 2: ({"volume": "missing", "pages": "missing"}, "volume ٥ and page ٣١٤ not given"),
 5: ({"year": "missing", "place": "missing", "authors": "loose"}, "year 2001 and place not given; name not split"),
 6: ({"title": "missing", "authors": "missing", "volume": "missing", "issue": "missing"}, "only source, year, pages"),
 7: ({"volume": "missing"}, "ج١٢ of the second work not given"),
 12: ({"source": "missing", "volume": "missing", "pages": "missing"}, "only authors and year"),
 14: ({"pages": "missing"}, "page 255 not given"),
 17: ({"authors": "loose"}, "name not split into surname / given"),
 19: ({"authors": "loose"}, "name not split into surname / given"),
 20: ({"source": "missing", "place": "missing"}, "only authors and year"),
 21: ({"title": "missing"}, "article title not given"),
 22: ({"link": "missing"}, "URL not given"),
 24: ({"publisher": "missing"}, "chapter title + book title right (better typed than Argon's); publisher not given"),
 30: ({}, "year 81 (Argon «دجنبر 81»): loose either way"),
 35: ({"source": "missing", "issue": "missing"}, "source and issue not given"),
 38: ({"other": "wrong"}, "the date reads «٢١ نوفمبر» (Azure); the print has عدد ٣١"),
 42: ({"authors": "loose"}, "name not split into surname / given"),
 51: ({"title": "missing", "authors": "missing"}, "only the year"),
 53: ({"publisher": "missing"}, "publisher not given"),
 57: ({}, "publisher «L'Harmattan» without «Ed.» (right)"),
 58: ({"authors": "loose"}, "name not split into surname / given"),
 59: ({"year": "missing"}, "date not given"),
 61: ({"publisher": "missing"}, "publisher not given"),
 63: ({}, "a trailing full stop"),
 65: ({"source": "missing", "place": "missing", "publisher": "missing", "authors": "missing"}, "thesis: only the year"),
}
out, pf_a, pf_c = [], Counter(), Counter()
for r in rows:
    a = dict(r["argon_verdicts"])
    if r["same"]:
        c, why = dict(a), "same parse as Argon's"
    elif r["mine"] is None or r["i"] in NOT_PARSED:
        c, why = {k: "missing" for k in a}, "work not parsed (no element-citation)"
    else:
        upd, why = HAND[r["i"]]
        c = dict(a, **upd)
    pf_a.update(f"{k}:{v}" for k, v in a.items())
    pf_c.update(f"{k}:{v}" for k, v in c.items())
    out.append(dict(i=r["i"], stem=r["stem"], where=r["where"], argon=a, claude=c, argon_all=r["argon_all_right"],
                    claude_all=all(v == "right" for v in c.values()), why=why))
fa = Counter(v.split(":")[1] for v in pf_a.elements())
fc = Counter(v.split(":")[1] for v in pf_c.elements())
tot = dict(n=len(out), argon_fully_right=sum(o["argon_all"] for o in out), claude_fully_right=sum(o["claude_all"] for o in out),
           claude_not_parsed=sum(o["why"].startswith("work not parsed") for o in out),
           argon_fields=dict(fa), claude_fields=dict(fc),
           argon_per_field=dict(sorted(pf_a.items())), claude_per_field=dict(sorted(pf_c.items())),
           by_place={w: dict(n=sum(o["where"].startswith(w) for o in out),
                             argon=sum(o["argon_all"] for o in out if o["where"].startswith(w)),
                             claude=sum(o["claude_all"] for o in out if o["where"].startswith(w))) for w in ("ref", "fn")})
jdump(OUT / "t1/cite_scores.json", dict(totals=tot, citations=out))
print(json.dumps({k: v for k, v in tot.items() if "per_field" not in k}, ensure_ascii=False, indent=1))
