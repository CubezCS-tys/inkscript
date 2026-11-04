"""C1f judgments, by an agent (Claude), of every self-citation platform v2 finds in the 600 (all rows, no sample)."""
import json
from common48c import OUT, save, wilson, progress
rows = json.load(open(OUT / "c1_selfcite.json"))
J = {7: ("provenance", "a first-page note 'a thesis submitted for the PhD in business administration': where the paper comes from, not a citation"),
     20: ("provenance", "first-page note naming the author's thesis MAURUSIA: the article's source"),
     24: ("provenance", "first-page note with the article's own title (part of a book)"),
     25: ("provenance", "the article is an excerpt of Sydney Smith's 'Mostly Murder'; the note names the source of the text"),
     33: ("wrong", "the cited work 'أصداء نيابوليس' is by Tawfiq Daghfous; the byline author Yahya al-Ghoul is not its author")}
items = []
for i, r in enumerate(rows):
    v, why = J.get(i, ("right", "the byline author cites his/her own work (name, field and title agree)"))
    c = r.get("citation") or {}
    items.append(dict(i=i, stem=r["stem"], byline=r["byline"], cited_title=r["title"], page=c.get("page"),
                      note=c.get("container_id"), citation=(c.get("printed") or "")[:300], verdict=v, why=why))
missed = json.load(open(OUT / "c1_selfcite_missed.json"))
k = {v: sum(1 for x in items if x["verdict"] == v) for v in ("right", "provenance", "wrong")}
S = dict(judged_by="agent (Claude)", rows=len(items), articles=len({x["stem"] for x in items}),
         article_person_pairs=len({(r["stem"], r["person_id"]) for r in rows}), verdicts=k,
         right_share=round(k["right"] / len(items), 3), right_wilson95=wilson(k["right"], len(items)),
         missed_by_view_name_equal=len(missed), missed_examples=missed)
save("c1_selfcite_judged.json", dict(summary=S, items=items))
progress(f"- judged all {len(items)} self-citation rows: {k}; missed {len(missed)}")
print(json.dumps({k_: v for k_, v in S.items() if k_ != 'missed_examples'}, indent=1))
