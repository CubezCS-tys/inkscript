import json
from collections import Counter
from db import OUT
cards = json.load(open(f"{OUT}/cards_dump.json"))
def bucket(n): return "1" if n == 1 else "2" if n == 2 else "3-5" if n <= 5 else "6+"
res = {}
for scope, runs in (("all654", None), ("600", {"v33_300_final", "v33_300b_fix3"})):
    cs = []
    for cd in cards:
        ms = [m for m in cd["members"] if runs is None or m["run"] in runs]
        if not ms: continue
        cs.append((cd, ms))
    res[scope] = dict(
        n_cards=len(cs),
        by_members=Counter(bucket(len(ms)) for cd, ms in cs),
        by_mentions_incl_backrefs=Counter(bucket(cd["n_mentions"]) for cd, ms in cs) if runs is None else None,
        by_citing_articles=Counter(bucket(len({m["stem"] for m in ms})) for cd, ms in cs),
        cited_by_gt1_article=sum(1 for cd, ms in cs if len({m["stem"] for m in ms}) > 1),
    )
print(json.dumps(res, ensure_ascii=False, indent=1))
top = sorted(cards, key=lambda cd: (-cd["n_pubs"], -cd["n_mentions"]))[:40]
for cd in top:
    print(cd["cited_work_pk"], cd["n_pubs"], cd["n_members"], cd["n_mentions"], cd["pub_type"], cd["title"], "|", cd["first_author_key"])
json.dump(res, open(f"{OUT}/distribution.json", "w"), ensure_ascii=False, indent=1)
