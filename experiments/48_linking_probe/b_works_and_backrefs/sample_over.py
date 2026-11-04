"""B1 over-merging sample: seed 4811, stratified by card size (members), weighted toward large cards:
all 21 cards with 6+ members, 15 of 114 with 3-5, 15 of 775 with 2."""
import json, random
from db import OUT
cards = json.load(open(f"{OUT}/cards_dump.json"))
rng = random.Random(4811)
strata = {"6+": [c for c in cards if c["n_members"] >= 6], "3-5": [c for c in cards if 3 <= c["n_members"] <= 5],
          "2": [c for c in cards if c["n_members"] == 2]}
take = {"6+": None, "3-5": 15, "2": 15}
sample = []
for s, cs in strata.items():
    cs = sorted(cs, key=lambda c: c["cited_work_pk"])
    pick = cs if take[s] is None else rng.sample(cs, take[s])
    for c in pick:
        sample.append(dict(stratum=s, stratum_size=len(cs), cited_work_pk=c["cited_work_pk"], cited_work_id=c["cited_work_id"],
                           title=c["title"], first_author_key=c["first_author_key"], n_pubs=c["n_pubs"],
                           members=[dict(stem=m["stem"], mention_id=m["mention_id"], note=m["container_id"],
                                         page=m["page"], method=m["method"], printed=m["printed"],
                                         authors=json.loads(m["evidence"])["authors"]) for m in c["members"]]))
json.dump(sample, open(f"{OUT}/over_sample.json", "w"), ensure_ascii=False, indent=1)
for i, s in enumerate(sample):
    print(f"\n#{i} [{s['stratum']}] {s['cited_work_id']} «{s['title']}» fa={s['first_author_key']} pubs={s['n_pubs']}")
    for m in s["members"]:
        print("   ", m["stem"], m["method"][12:], m["authors"], "::", (m["printed"] or "")[:170].replace("\n", " "))
