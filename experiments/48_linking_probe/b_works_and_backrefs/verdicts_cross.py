"""Agent's (Claude's) census of ALL 113 cards cited by more than one article (cross_cards.txt), by reading them.
Everything not listed is judged right."""
import json, math
from db import OUT
NOT_RIGHT = {
 "CK4KYP6BAX": ("wrong", "«الديوان»: six poets' diwans joined through two author-less members"),
 "C8BJW04HWY": ("wrong", "«اللسان»: Lisan al-'Arab (grammar article 0692) vs Ibn Hajar's Lisan al-Mizan (1453)"),
 "CG0KN9WZK5": ("wrong", "«بيانات غير منشورة» (unpublished data) of two different bodies"),
 "CJQ8QN5CSK": ("wrong", "«التهذيب»: Ibn Hajar's Tahdhib vs al-Azhari's Tahdhib al-Lugha"),
 "CT9GTP7QSE": ("wrong", "«المغني»: Ibn Hisham's Mughni al-Labib (grammar, 0135) vs Ibn Qudama's al-Mughni (law, 0328)"),
 "CWESQW9WNN": ("wrong", "«جريدة اللواء»: a 1993 article and 1908 issues - two newspapers of one name"),
 "CF622F7PED": ("mixed", "Ibn Khaldun's Muqaddima in 6 articles + one foreign member (0596: an editor's preface)"),
 "CMVFT5DR25": ("serial", "magazine al-Adab, different issues"),
 "C0G5VDBE37": ("serial", "Le Figaro, 1955 and 2015 items"),
 "C4G2CR89M3": ("serial", "Majallat al-Mashriq, different items"),
 "CAJ3T1HJDD": ("serial", "al-Tariq, different issues"),
 "CBV6J2NVRV": ("serial", "al-Risala, issues unnamed"),
 "CTCV208DY0": ("serial", "law-report collection, different rulings"),
}
def wilson(k, n, z=1.96):
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]
cards = [c for c in json.load(open(f"{OUT}/cards_dump.json")) if c["n_pubs"] > 1]
out = []
for c in cards:
    v, why = NOT_RIGHT.get(c["cited_work_id"], ("right", ""))
    out.append(dict(cited_work_id=c["cited_work_id"], title=c["title"], n_pubs=c["n_pubs"], verdict=v, why=why))
from collections import Counter
t = Counter(o["verdict"] for o in out); n = len(out)
summ = dict(judged_by="Claude (agent), census of all cross-article cards", n=n, tally=dict(t),
            right_wilson=wilson(t["right"], n), wrong_wilson=wilson(t["wrong"], n),
            true_cross_article_works=t["right"] + t["mixed"])
json.dump(dict(summary=summ, cards=out), open(f"{OUT}/cross_article_judged.json", "w"), ensure_ascii=False, indent=1)
print(summ)
