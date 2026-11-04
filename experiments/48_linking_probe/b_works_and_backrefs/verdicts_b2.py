"""Agent's (Claude's) verdicts on the 61 back references of backref_sample.json (seed 4813), judged by reading the
marker's note, the 5 notes before it in the JATS master and, where needed, every note of the article that names the
author (backref_sample.txt). Resolved: right / wrong / unsure. Unresolved: correct-unresolved (no earlier citation of
the work exists, or it is not a bibliographic work) / miss (the right earlier citation exists)."""
import json, math
from collections import Counter, defaultdict
from db import OUT
V = {
 0: ("right", "al-Messiri full just before"), 1: ("right", "previous short form; the work has no full citation"),
 2: ("right", "the poem «العائد» just before"), 3: ("right", "Asrar al-Balagha"), 4: ("right", "Ibn Rashiq's Diwan (note 12)"),
 5: ("right", "the insurance report"), 6: ("right", "SNAT 2013"), 7: ("right", "Kilito, al-Adab wa-l-Ghuraba"),
 8: ("right", "al-Kalabadhi"), 9: ("right", "al-Qamus al-Muhit"),
 10: ("right", "Said's Orientalism through two «المرجع السابق»"), 11: ("right", "Nafh al-Tib"),
 12: ("right", "Rafi-ud-Din, Ideology of the Future"),
 13: ("right", "the sigle «S.R.C.» (Scarron, Le Roman comique) - but the sigle is not tied to its defining full citation fn-p4-4"),
 14: ("right", "Mu'jam al-Udaba'"), 15: ("right", "Affa & al-Maghrawi"), 16: ("right", "Ideology of the Future"),
 17: ("unsure", "bare «مرجع سابق» with no author after a chain; the note before cites «115/1 - 34/2», a multi-volume work (Ibn al-Anbari?), not al-Zajjaji's one-volume Idah"),
 18: ("right", "Ideology of the Future"), 19: ("right", "Mudhakkirat Mahmud Riyad"),
 20: ("right", "Mujawir (the proof pack's 'missed' case, now linked)"), 21: ("right", "Ryngaert, Introduction a l'analyse du theatre"),
 22: ("right", "Pictet"), 23: ("right", "F. Fahmy"), 24: ("right", "Chaudet"), 25: ("right", "Pictet"),
 26: ("right", "Barrington Moore"), 27: ("right", "Ahmad Shafiq (second marker of the note)"), 28: ("right", "Abd al-Hakim Hasan, thesis r15"),
 29: ("right", "Benoukrim"), 30: ("right", "Cys Part III (title words pick the right part)"), 31: ("right", "Sharh Ibn 'Aqil"),
 32: ("right", "al-Jama'i & al-'Asri"), 33: ("right", "Mudhakkirat Mahmud Riyad"),
 34: ("right", "Pesaran, Shin & Smith 2001 (pages 289-326 match)"),
 35: ("right", "al-Rafi'i: most recent of his three books is «محمد فريد» (note 22), target its full citation"),
 36: ("right", "Ibn al-Athir, al-Kamil"), 37: ("right", "La Rosa «La preuve» in Droit international penal (p. 961)"),
 38: ("right", "same"), 39: ("right", "Roldan et al. 2006"),
 40: ("wrong", "op. cit. inside a full citation (Tejera in Roldan et al. eds, op. cit.) refers to Roldan 2006; linked to «Madrider Mitteilungen 31»"),
 41: ("right", "the web page"), 42: ("right", "Heba Mahmoud's article"),
 43: ("unsure", "Bernal et al.: five works fit; the most recent taken (Anuario 2006) is plausible"),
 44: ("wrong", "«Cabestan et A. Tomes, Sartre, op. cit.»: a book titled Sartre by Cabestan & Tomes; linked to Sartre's own Transcendance de l'ego"),
 45: ("correct-unresolved", "no full Hansen citation anywhere in the article"),
 46: ("miss", "the full citation exists (fn-p2-1 «Sartre, une vie pour la philosophie (entretien)»); not matched"),
 47: ("correct-unresolved", "no earlier full citation of Abd al-Wahhab Khalil"),
 48: ("miss", "al-Rafi'i: the hint swallowed the next citation («- أيضا مذكرات محمد فريد»); the most recent Rafi'i work is findable"),
 49: ("correct-unresolved", "Guillien & Vincent are cited only by op. cit."),
 50: ("miss", "al-Messiri: only one earlier work (fn-p12-4 «العلمانية تحت المجهر», same p. 15 confirmed by note 14)"),
 51: ("miss", "«جاكندوب» = Jakendoff, full in the reference list r33 (Latin script)"),
 52: ("correct-unresolved", "no full Hansen citation"),
 53: ("miss", "chain through «The Wretched of the Earth, op. cit.»; its full citation sits inside an explanatory note (fn-p13-15) not parsed"),
 54: ("miss", "same chain"),
 55: ("miss", "corporate author «الهيئة العامة للمعلومات»: r8 (census 2006) cited at p. 60 in note 11, same page"),
 56: ("miss", "same Wretched-of-the-Earth chain"),
 57: ("correct-unresolved", "Ibid after a court judgment (Akayesu): not a bibliographic work"),
 58: ("miss", "«Id, p.957» was not taken as a back reference and broke the chain; right answer La Rosa «La preuve»"),
 59: ("right", "op. cit. inside the parsed Aguessy citation, counted once"),
 60: ("right", "op. cit. inside the parsed Cesaire citation, counted once"),
}
def wilson(k, n, z=1.96):
    if not n: return None
    p = k / n; d = 1 + z * z / n; c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return [round(c - h, 3), round(c + h, 3)]
S = json.load(open(f"{OUT}/backref_sample.json"))
pop = json.load(open(f"{OUT}/backref_categories.json"))
for i, s in enumerate(S): s["verdict"], s["why_judged"] = V[i]
by = defaultdict(Counter)
for s in S: by[s["category"]][s["verdict"]] += 1
res = dict(judged_by="Claude (agent), reading the notes in the JATS masters; not a person", seed=4813, n=len(S),
           scope="the 600 (runs v33_300_final + v33_300b_fix3): 1096 back references in 129 articles",
           population_by_category=pop, sample_by_category={k: dict(v) for k, v in by.items()})
R = [s for s in S if not s["category"].startswith("unresolved")]
U = [s for s in S if s["category"].startswith("unresolved")]
tr = Counter(s["verdict"] for s in R); tu = Counter(s["verdict"] for s in U)
res["resolved"] = dict(n=len(R), tally=dict(tr), right_wilson=wilson(tr["right"], len(R)),
                       right_of_decided_wilson=wilson(tr["right"], tr["right"] + tr["wrong"]))
# weighted by category size
wsum = wr = ww = 0
for k, cnt in by.items():
    if k.startswith("unresolved"): continue
    n = sum(cnt.values()); P = pop[k]
    wsum += P; wr += P * cnt["right"] / n; ww += P * cnt["wrong"] / n
res["resolved"]["weighted_right"] = round(wr / wsum, 3); res["resolved"]["weighted_wrong"] = round(ww / wsum, 3)
res["resolved"]["estimated_wrong_links_of_1017"] = round(ww)
res["unresolved"] = dict(n=len(U), tally=dict(tu), miss_wilson=wilson(tu["miss"], len(U)), population=79)
res["compare_proof_pack"] = "ibid_score.json (seed 20261023, older linker, population 510): 20 judged: 15 right (14 linked + 1 correctly unresolved), 1 wrong, 4 missed"
json.dump(dict(summary=res, sample=S), open(f"{OUT}/b2_judged.json", "w"), ensure_ascii=False, indent=1)
print(json.dumps(res, ensure_ascii=False, indent=1))
