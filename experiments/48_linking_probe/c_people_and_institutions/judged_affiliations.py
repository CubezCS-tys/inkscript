"""C2 judgments (seed 4824), by an agent (Claude): is the organisation-level institution platform v2 links an
affiliation to the right organisation? right / partial (right body, but its parent or name is lost) / wrong (a generic or
merged entity, or the university lost) / unsure. Read: the printed affiliation, its pieces, and every linked institution
with its kind, parent and names (c2_digest.txt)."""
import json
from common48c import OUT, save, wilson, progress
J = {2: ("wrong", "«آداب الزقازيق» -> an organisation named «الزقازيق» (not جامعة الزقازيق) with a department «آداب»: a split twin of the university, and the faculty read as a department"),
     4: ("wrong", "«مدرس بالمعهد» ('teacher at the institute') -> an institution «المعهد»: a generic word made an entity"),
     6: ("wrong", "«الجامعة الإسلامية» alone (Madinah? Gaza? Islamabad? Omdurman?) -> one institution: ambiguous names merged"),
     7: ("wrong", "UT Austin lost: linked only to «Graduate School of Business and The Center for Middle Eastern Studies», no parent"),
     10: ("wrong", "«قسم التاريخ» with no university -> one orphan 'history department' shared by every such affiliation"),
     19: ("partial", "the centre is right but the parent body «وكالة كليات البنات» is lost"),
     27: ("wrong", "«Faculty of Arts, Fès» -> an orphan 'Faculty of Arts' (no university), shared by all such"),
     35: ("wrong", "«Faculté de Lettres, Université de Minia» -> no organisation link; an orphan faculty"),
     39: ("partial", "Islamic University of Lebanon kept separate but named «University of Lebanon» (risk of a merge with the Lebanese University)"),
     42: ("wrong", "«ENS-CONSTANTINE» -> an organisation «ENS» (every École normale supérieure would merge into it)"),
     45: ("unsure", "«Higher institute of information Technology»: no city or country; which institute?")}
s = json.load(open(OUT / "c2_aff_sample.json"))
items = []
for i, a in enumerate(s):
    v, why = J.get(i, ("right", "the organisation named in the affiliation, with its faculty/department under it where printed"))
    items.append(dict(i=i, stem=a["stem"], printed=a["printed"], verdict=v, why=why,
                      links=[(l["level"], l["inst_id"], l["kind"], (l["names"] or [None])[0]) for l in a["links"]]))
k = {v: sum(1 for x in items if x["verdict"] == v) for v in ("right", "partial", "wrong", "unsure")}
S = dict(judged_by="agent (Claude)", seed=4824, n=len(items), verdicts=k, right_wilson95=wilson(k["right"], len(items)),
         right_or_partial_wilson95=wilson(k["right"] + k["partial"], len(items)), wrong_wilson95=wilson(k["wrong"], len(items)),
         notes=["faculty/department texts: «قسم الرياضيات / كلية التربية» and «College of Business and Economics» are stored as both faculty and dept text; 2 of 50 department names garbled («حوث رسم التنمية», «Weaving»)",
                "orphan faculties/departments are keyed «org:?/…»: all «كلية الآداب» of unknown universities become one institution"])
save("c2_aff_judged.json", dict(summary=S, items=items))
progress(f"- judged 50 affiliation links (seed 4824): {k}")
print(json.dumps(S, indent=1, ensure_ascii=False))
