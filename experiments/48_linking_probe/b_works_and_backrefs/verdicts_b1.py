"""Agent's (Claude's) verdicts on the B1 samples, judged by reading each card's printed citations
(over_sample.txt, under_sample.txt). Writes b1_judged.json with Wilson intervals."""
import json, math
from collections import Counter
from db import OUT
def wilson(k, n, z=1.96):
    if n == 0: return None
    p = k / n; d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d; h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]
OVER = {  # index in over_sample.json -> (verdict, why)
 0: ("right", "al-Firuzabadi; one member names him Taj al-Din (misprint by the citing author)"),
 1: ("right", "al-Isfahani; several editions (Bulaq, Dar al-Kutub, Sadir 2008) = one work"),
 2: ("serial", "a law-report series; 13 different rulings (different years and pages) of one article"),
 3: ("wrong", "magazine al-Tariq: contributions by Khalil Hawi, Adonis, Walid Saif all on one card, credited to Hawi"),
 4: ("right", "Muqaddimat Ibn Khaldun (but split from card #19 «المقدّمة»)"),
 5: ("right", "Sibawayh; bare «الكتاب» members are in articles about Sibawayh and grammar"),
 6: ("serial", "the newspaper al-Liwa: 8 different issues"),
 7: ("wrong", "in-article: Ilin-Tomich 2012, 2011, 2017, Grajetzki 2001, 2013, Mohamed 2022: >= 6 works"),
 8: ("right", "Wafayat al-A'yan, several editions"),
 9: ("right", "Sahih al-Bukhari, different hadiths (locators)"),
 10: ("right", "same book, misprints"),
 11: ("serial", "law-report collection, different rulings and volumes"),
 12: ("serial", "journal PSBA by year, items unnamed"),
 13: ("right", "one catalogue in parts (Teil I 1902, Teil II and IV 1908): volumes of one work"),
 14: ("right", "Ibn Jinni al-Khasa'is"),
 15: ("right", "Ibn al-Nadim al-Fihrist; bare members in an article about the sources of Nahj al-Balagha"),
 16: ("wrong", "«الديوان» of six different poets (Ibn Rashiq, al-Akhtal, Ibn al-Farid, al-Ya'qubi, Mihyar, al-'Askari)"),
 17: ("right", "Yaqut, Mu'jam al-Buldan"),
 18: ("right", "Lisan al-'Arab"),
 19: ("wrong", "Ibn Khaldun's Muqaddima plus «مقدمة رسائل للرفاعي» by Hassan Abd al-Mannan (an editor's preface)"),
 20: ("serial", "journal Ancient Egypt 1916, items unnamed"),
 21: ("right", "al-Ghazali, Ihya'"),
 22: ("right", "Ibn 'Idhari; two editions (Miranda 1963, al-Kattani 1985) = one work"),
 23: ("right", "al-Mu'jam al-Wasit"),
 24: ("wrong", "in-article: Pomeau «Beaumarchais» 1962 merged with Didier «Beaumarchais ou la passion du drame» 1994"),
 25: ("right", "Sunan Abi Dawud"),
 26: ("right", "al-Bustani, Muhit al-Muhit (1998 and 2009 printings)"),
 27: ("wrong", "magazine al-Adab, different issues 1962-1973, credited to al-Kharrat and Atiyya"),
 28: ("wrong", "Prisoners' Club web report (Raya Network) merged with al-Batsh's 2007 book"),
 29: ("right", "Sharh Ibn 'Aqil"),
 30: ("right", "al-Baghdadi, Khizanat al-Adab"),
 31: ("right", "one book (author not parsed in any member)"),
 32: ("right", "Quirke 1986"),
 33: ("right", "Zahran"), 34: ("right", "Tammam Hassan"), 35: ("right", "al-Tadili"),
 36: ("right", "in-article repeat"), 37: ("right", "misprinted title"), 38: ("right", "in-article"),
 39: ("right", "in-article"), 40: ("right", "in-article"), 41: ("right", "in-article"), 42: ("right", "in-article"),
 43: ("right", "in-article"), 44: ("right", "in-article"), 45: ("right", "in-article"),
 46: ("right", "a split citation (conference line + full line) of one paper"),
 47: ("right", "al-Zawzani «العشر» vs «السبع», same publisher and year: the citing author's slip, one book"),
 48: ("right", "in-article"), 49: ("right", "in-article"), 50: ("right", "in-article"),
}
UNDER = {  # index in under_sample.json -> (same work? yes/no/unsure, why)
 0: ("yes", "al-Marzubani al-Muwashshah, short title"), 1: ("no", "Rabelais vs Voltaire Oeuvres completes"),
 2: ("yes", "Obeidat et al. al-Bahth al-'Ilmi: 1988 vs 2012 (14th ed.) with full subtitle"),
 3: ("no", "Jad al-Rabb vs Dessler (translated by Abd al-Muta'al): shared token «سيد» is a given-name word"),
 4: ("yes", "Yaqut «البلدان» = Mu'jam al-Buldan"), 5: ("yes", "al-Dhahabi Mizan al-I'tidal"),
 6: ("no", "two Snyder books"), 7: ("no", "two NRC reports"), 8: ("yes", "al-Mawardi al-Ahkam al-Sultaniyya, short title"),
 9: ("yes", "«الميزان» = Mizan al-I'tidal (al-Dhahabi)"), 10: ("yes", "Ibn Kathir al-Bidaya"),
 11: ("yes", "Irshad al-Arib = Mu'jam al-Udaba' (alternate title)"), 12: ("yes", "Harrison «Arcot» in EI, same article"),
 13: ("no", "two works by Bouqentar"), 14: ("yes", "Subh al-A'sha"),
 15: ("no", "card a is itself an over-merge (Tarazi, al-Maghribi, Mujahid); b is Ibn Durayd"),
 16: ("no", "Pictet (IV) vs de Preux (III): different volumes, different authors"), 17: ("yes", "Ibn Rashiq al-'Umda"),
 18: ("unsure", "Majmu' al-Fatawa vs «فتاوى ابن تيمية» (could be al-Fatawa al-Kubra)"), 19: ("yes", "al-Mu'jib"),
 20: ("yes", "al-Bukhari al-Jami' al-Sahih vs «الصحيح»"), 21: ("no", "different authors and books"),
 22: ("yes", "Madarij al-Salikin"), 23: ("yes", "al-Nasa'i al-Du'afa'"), 24: ("yes", "Nazm al-Juman (1962 and 1980 editions)"),
 25: ("yes", "Browne"), 26: ("yes", "Nafh al-Tib"), 27: ("yes", "al-Wasata"), 28: ("yes", "al-Idah fi 'Ilal al-Nahw"),
 29: ("yes", "Awdah al-Masalik"), 30: ("yes", "al-Tabari: Tarikh al-Rusul = Tarikh al-Umam (alternate title)"),
 31: ("yes", "Fatawa Ibn Taymiyya, same title"), 32: ("yes", "Sartre L'etre et le neant"), 33: ("no", "two theses by different al-Ghamdis"),
 34: ("no", "Cuq vs Defay"), 35: ("yes", "«الكتاب» = «كتاب سيبويه»"), 36: ("yes", "al-Anis al-Mutrib"),
 37: ("yes", "Borges Le livre, same article, two printings of one citation"), 38: ("yes", "Bates 1914 and its 1970 reprint"),
 39: ("yes", "Ibn 'Atiyya al-Muharrar al-Wajiz"), 40: ("yes", "Ibn Mujahid al-Sab'a"),
 41: ("yes", "Guilford 1956 vs 6th ed. 1978 with Fruchter: one work, two editions"),
 42: ("unsure", "card a is mixed (al-Jasir + Ghabban); b «غبان، نقوش» likely Ghabban's article"),
 43: ("no", "two Ringle/Sarstedt works"), 44: ("yes", "al-Tabarani al-Mu'jam al-Awsat"),
 45: ("yes", "al-Bukhari al-Jami' al-Sahih (al-Mukhtasar)"), 46: ("no", "different books on education"),
 47: ("yes", "Kashf al-Zunun"), 48: ("no", "al-'Aqqad complete works vs Mudhakkirat Iblis"), 49: ("yes", "Harrison «Arcot»"),
}
over = json.load(open(f"{OUT}/over_sample.json")); under = json.load(open(f"{OUT}/under_sample.json"))
res = {"judged_by": "Claude (agent), reading the printed citations; not a person", "over": {}, "under": {}}
for s in ("6+", "3-5", "2"):
    ix = [i for i, x in enumerate(over) if x["stratum"] == s]
    t = Counter(OVER[i][0] for i in ix); n = len(ix)
    res["over"][s] = dict(n=n, stratum_size=over[ix[0]]["stratum_size"], tally=dict(t),
                          wrong_rate=round(t["wrong"] / n, 3), wrong_wilson=wilson(t["wrong"], n),
                          wrong_or_serial_wilson=wilson(t["wrong"] + t["serial"], n))
# population estimate of wrong multi-member cards (stratified)
est = sum(res["over"][s]["stratum_size"] * res["over"][s]["tally"].get("wrong", 0) / res["over"][s]["n"] for s in res["over"])
res["over"]["estimated_wrong_cards_of_910_multi"] = round(est)
t = Counter(v[0] for v in UNDER.values())
res["under"]["tally"] = dict(t); res["under"]["yes_wilson"] = wilson(t["yes"], 50)
by_rule = {}
for i, p in enumerate(under):
    by_rule.setdefault(p["rule"], Counter())[UNDER[i][0]] += 1
res["under"]["by_rule"] = {k: dict(v) for k, v in by_rule.items()}
res["under"]["n_candidates"] = len(json.load(open(f"{OUT}/under_candidates.json")))
for i, x in enumerate(over): x["verdict"], x["why"] = OVER[i]
for i, x in enumerate(under): x["verdict"], x["why"] = UNDER[i]
json.dump(dict(summary=res, over=over, under=under), open(f"{OUT}/b1_judged.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
