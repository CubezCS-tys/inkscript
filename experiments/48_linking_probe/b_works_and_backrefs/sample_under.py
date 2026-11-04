"""B1 under-merging sample: 50 candidate pairs, seed 4812; prints both cards' members for judging."""
import json, random
from db import OUT
c = json.load(open(f"{OUT}/under_candidates.json"))
cards = {cd["cited_work_id"]: cd for cd in json.load(open(f"{OUT}/cards_dump.json"))}
rng = random.Random(4812)
s = rng.sample(c, 50)
json.dump(s, open(f"{OUT}/under_sample.json", "w"), ensure_ascii=False, indent=1)
for i, p in enumerate(s):
    print(f"\n#{i} {p['rule']}")
    for side in "ab":
        cd = cards[p[side]["id"]]
        print(f"  {side} {cd['cited_work_id']} «{cd['title']}» au={p[side]['au']}")
        for m in cd["members"][:3]:
            print("      ", m["stem"], "::", (m["printed"] or "")[:160])
