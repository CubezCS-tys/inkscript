"""C1c judgments (seed 4821): does one Mandumah authority id hold the records of more than one person?
Judged by an agent (Claude) reading each id's records grouped by journal (dump_authority.py). 'error' = two or more
people under one id; 'right' = one person; 'unsure'. The first 25 were sampled from the ids our flags marked, the last 15
from the unflagged ids with 3+ records."""
import json
from common48c import OUT, save, wilson, progress
J = [
 ("288187", "right", "poet Hassan Fathalbab; the police-journal / criminal-evidence articles fit him (a police officer and poet)"),
 ("312707", "right", "Abd al-Razzaq Muhyi al-Din, Iraqi Academy; consistent"),
 ("229007", "right", "historian Younan Labib Rizk; supervisions at Ain Shams fit"),
 ("117585", "right", "Mustafa al-Sibai; 1985/2018/2024 items are reprints"),
 ("198485", "right", "Arif Tamer, Ismaili studies; consistent"),
 ("412285", "right", "painter-critic Izz al-Din Naguib; consistent"),
 ("155979", "right", "Moroccan educator/philosopher; consistent"),
 ("86707", "error", "Islamic poet 1965-2010 (al-Wa'y al-Islami, al-Adab al-Islami) + an Algerian demographer/sociologist 2015-2024 (fertility in Algeria, COVID, video-game addiction)"),
 ("332135", "right", "Ali Asaad Watfa, sociology of education; 227 records consistent"),
 ("217816", "unsure", "Lebanese fiction writer in al-Adab 1959-62 and al-Mawqif 1982; a 1972 Moroccan Da'wat al-Haqq article on the Sira and 1993 al-Ijtihad on al-Ghazali may be another Muhammad Haidar"),
 ("276006", "right", "Hani Atiyya, library science + Islamic web; consistent"),
 ("253100", "error", "Sheikh Atiyya Saqr (d. 2006), al-Wa'y al-Islami fatwas; a 2014 supervision at the Islamic University of Madinah (after his death) is another person"),
 ("327690", "right", "Abd al-Razzaq Nawfal, Quranic miracles; consistent"),
 ("104380", "right", "Osama Amin al-Kholy, science & technology policy; consistent"),
 ("418428", "error", "Syrian poet Muhammad Omran (d. 1996) + a 2003 Aleppo medical thesis on cutaneous leishmaniasis + 2018 auditor law articles"),
 ("327305", "right", "Muhammad Safwat Nur al-Din (d. 2002), al-Tawhid; later items are reprints"),
 ("180287", "right", "poet Mukhtar al-Wakil; consistent"),
 ("154284", "right", "al-Sadiq al-Faqih, Sudanese political writer; consistent"),
 ("213172", "error", "two famous Egyptians named Muhammad Kamil Husayn: the Fatimid/Ismaili scholar (Kulliyat al-Adab 1936-54, al-Risala al-Wa'iza) and the surgeon-novelist of Qarya Zalima (d. 1977)"),
 ("144026", "right", "Yusuf al-Ush, Damascus libraries; 1981/1996 items about his subject plausible reprints"),
 ("115027", "right", "Jamil Sidqi al-Zahawi; 1990 item a reprint"),
 ("275130", "right", "Jaber Asfour; consistent"),
 ("315919", "right", "historian Ahmad Abd al-Rahim Mustafa; consistent"),
 ("279911", "right", "Muhammad Kurd Ali (d. 1953); one 2010 Algerian item is odd but may be a reprint"),
 ("238222", "right", "Edward Said; note: some records ABOUT him carry him as author (reviews of his books)"),
 ("107291", "right", "fashion design, consistent"),
 ("162832", "right", "Islamic banking, Sudan; consistent"),
 ("325120", "right", "Emile Nakhleh; consistent"),
 ("205012", "right", "Fuad Jamil; consistent"),
 ("313269", "right", "Egyptian political scientist; consistent"),
 ("122016", "right", "social work / delinquency; consistent"),
 ("293200", "right", "Mosul statistician; consistent"),
 ("303609", "right", "Algerian marketing; consistent"),
 ("212793", "error", "Syrian development economist (Damascus 1999-2012) + teachers' stories in Palestinian Ru'a Tarbawiyya 2010-16 + an Algerian 2014 article on Quranic orthography"),
 ("241590", "error", "Sheikh al-Azhar Abd al-Majid Salim (d. 1954) in Risalat al-Islam 1949-54 + a 1984 Qatar article and a 1987 Fiqh Academy co-authored paper (not reprints)"),
 ("469909", "unsure", "reproductive-health demography (2018-22) and marital-adjustment psychology (2021): could be one or two people"),
 ("263330", "right", "social work; consistent"),
 ("129134", "right", "al-Shinqiti in Hady al-Islam; consistent"),
 ("452643", "right", "hadith studies, Algeria; consistent"),
 ("207565", "right", "Elia Hawi; consistent"),
]
samp = json.load(open(OUT / "c1_authority_judge_sample.json"))
assert [s["authority_id"] for s in samp] == [j[0] for j in J]
out = [dict(authority_id=a, verdict=v, why=w, flagged=bool(s["flags"]), flags=s["flags"], heading=s["heading"], n=s["n"])
       for (a, v, w), s in zip(J, samp)]
def tally(xs):
    c = {k: sum(1 for x in xs if x["verdict"] == k) for k in ("right", "error", "unsure")}
    n = len(xs); c["n"] = n; c["error_rate"] = round(c["error"] / n, 3); c["error_wilson95"] = wilson(c["error"], n)
    return c
prof = json.load(open(OUT / "c1_authority_profiles_ours.json"))
n_fl = sum(1 for p in prof if p["flags"]); n_un3 = sum(1 for p in prof if not p["flags"] and p["n"] >= 3)
n_small = sum(1 for p in prof if not p["flags"] and p["n"] < 3)
tf, tu = tally(out[:25]), tally(out[25:])
est = (n_fl * tf["error_rate"] + n_un3 * tu["error_rate"])
S = dict(judged_by="agent (Claude), reading records grouped by journal", seed=4821, all=tally(out), flagged=tf,
         unflagged_3plus=tu, population=dict(flagged=n_fl, unflagged_3plus=n_un3, under_3_records=n_small),
         estimated_mixed_authorities_of_our_675=round(est), estimated_share=round(est / len(prof), 3))
save("c1_authority_judged.json", dict(summary=S, items=out))
progress(f"- judged 40 authority ids (seed 4821): {S['all']}; est. mixed {S['estimated_mixed_authorities_of_our_675']}/675")
print(json.dumps(S, indent=1, ensure_ascii=False))
