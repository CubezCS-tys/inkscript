"""C1e judgments (seed 4823), by an agent (Claude) reading the citation as printed, the cited work and the authority's
catalogue records. Sample A: 40 cited-author -> person links that platform v2 made. Sample B: 20 unlinked cited authors
whose folded name has exactly one holder in the whole catalogue: would linking them by that name alone be right?"""
import json
from common48c import OUT, save, wilson, progress
A = {6: ("wrong", "historian Abd al-Aziz Muhammad al-Shinnawi (Ottoman history) linked to authority 128921, mostly a "
             "short-story writer in al-Qissa; the historian's own id is 128922 (Egyptian Historical Review). The catalogue "
             "put a review of his book under the other id, and the unique-name rule took it")}
B = {0: ("unsure", "«الأستاذ محسن محمد» cited in a Syrian lawyers' journal; the only holder is an Egyptian journalist"),
     2: ("unsure", "Sayyid Ahmad Uthman the educational psychologist vs a one-record holder with a 1985 teachers' study")}
sa = json.load(open(OUT / "c1_cited_sample_linked.json"))
sb = json.load(open(OUT / "c1_cited_sample_unique_unlinked.json"))
def items(s, J):
    out = []
    for i, e in enumerate(s):
        v, why = J.get(i, ("right", "the cited title is among the authority's catalogue records, or the name and field agree"))
        c = e.get("citation") or {}
        out.append(dict(i=i, verdict=v, why=why, printed=e["printed"], method=e.get("match_method"), stem=c.get("stem"),
                        page=c.get("page"), note=c.get("container_id"), citation=(c.get("printed") or "")[:300],
                        authority=e.get("authority_used"), heading=(e.get("authority_heading") or {}).get("name")))
    return out
def tally(xs):
    k = {v: sum(1 for x in xs if x["verdict"] == v) for v in ("right", "wrong", "unsure")}
    k["n"] = len(xs); k["right_wilson95"] = wilson(k["right"], len(xs)); return k
ia, ib = items(sa, A), items(sb, B)
S = dict(judged_by="agent (Claude)", seed=4823, linked_sample=tally(ia), unique_name_unlinked_sample=tally(ib))
save("c1_cited_judged.json", dict(summary=S, linked=ia, unique_unlinked=ib))
progress(f"- judged cited authors (seed 4823): {S}")
print(json.dumps(S, indent=1))
