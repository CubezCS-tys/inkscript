"""C1d judgments (seed 4822), by an agent (Claude): is the byline person the catalogue authority platform v2 linked it
to? Read: the JATS byline (contrib group, affiliations), the article's own catalogue record and contributors, and the
authority's other works by journal. 'entity_mixed' notes links that are right for this article but whose authority id
also carries another person's records (a catalogue authority error, see c1_authority_judged.json)."""
import json
from common48c import OUT, save, wilson, progress
MIXED = {16: "authority 86707 also holds an Algerian demographer's 2015-24 papers",
         24: "authority 96677: business-admin 1976-82 + unrelated 2008/2012 items",
         38: "authority 187517: banking articles + an engineering cluster (trickle flow on wire screens)",
         42: "authority 275253: 1988-91 Yemen/Cairo educationist + 2014-24 Fayoum multimedia papers (maybe another person)"}
NOTES = {23: "byline OCR «نال» for «منال»; link still right", 46: "byline badly read («مد الدغام»); link right via token subset",
         2: "role is reviewer (عارض); the record's author is Edward Said, the reviewed book's author"}
s = json.load(open(OUT / "c1_person_sample.json"))
items = [dict(i=i, stem=x["stem"], printed=x["printed"], method=x["method"], heading=x["cat_name"],
              authority=x["authority_id"], verdict="right", entity_mixed=MIXED.get(i), note=NOTES.get(i))
         for i, x in enumerate(s)]
S = dict(judged_by="agent (Claude)", seed=4822, n=len(items), right=sum(1 for x in items if x["verdict"] == "right"),
         wrong=0, unsure=0, right_wilson95=wilson(50, 50), entity_mixed=len(MIXED),
         entity_mixed_wilson95=wilson(len(MIXED), 50),
         by_method={m: sum(1 for x in items if x["method"] == m) for m in sorted({x["method"] for x in items})})
save("c1_person_judged.json", dict(summary=S, items=items))
progress(f"- judged 50 byline->person links (seed 4822): {S}")
print(json.dumps(S, indent=1))
