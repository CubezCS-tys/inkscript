"""Population detector for over-merging: a card whose members' own printed authors (link47.author_tokens on each
member's parsed citation) contain two non-empty, disjoint sets. Read-only."""
import json, sys
from collections import Counter
sys.path.insert(0, "/home/appuser/inkscript/experiments/47_platform_v2")
import link47
from db import OUT
cards = json.load(open(f"{OUT}/cards_dump.json"))
out = []
for cd in cards:
    if cd["n_members"] < 2: continue
    sets = []
    for m in cd["members"]:
        p = json.loads(m["parsed"]) if m["parsed"] else None
        sets.append((m["stem"], frozenset(link47.author_tokens(p)), m["printed"][:100]))
    ne = [s for s in sets if s[1]]
    # connected components of non-empty author sets by overlap
    comps = []
    for s in ne:
        hit = [c for c in comps if any(s[1] & t[1] for t in c)]
        new = [s] + [x for c in hit for x in c]
        comps = [c for c in comps if c not in hit] + [new]
    if len(comps) >= 2:
        cross = len({s[0] for s in sets}) > 1
        out.append(dict(cited_work_id=cd["cited_work_id"], title=cd["title"], n_members=cd["n_members"],
                        n_pubs=cd["n_pubs"], n_author_groups=len(comps), cross_article=cross,
                        has_authorless=len(ne) < len(sets),
                        groups=[sorted({w for x in c for w in x[1]}) for c in comps]))
json.dump(out, open(f"{OUT}/author_conflict_cards.json", "w"), ensure_ascii=False, indent=1)
print(len(out), Counter((o["cross_article"], o["has_authorless"]) for o in out))
print("members in conflict cards", sum(o["n_members"] for o in out))
for o in sorted(out, key=lambda o: -o["n_members"]):
    print(o["n_members"], o["n_pubs"], o["title"][:60], o["groups"][:6])
