"""C2b judgments by an agent (Claude): which candidate groups (c2_cross_script_candidates.json) are one institution
still split in platform v2 across Arabic / English / French forms."""
import json
from common48c import OUT, save, progress
J = [
 ("Umm Al-Qura University = جامعة أم القرى", "split", ["I2KCFD1REB", "IXZNJ9PW6W"]),
 ("Cairo University in the same skeleton group: already one entity (5 forms); not a split", "merged-ok", ["IR2J7FA5Z1"]),
 ("Tanta University = جامعة طنطا", "split", ["IR73Q1WKT5", "IWKZTFYQG7"]),
 ("University of Mosul = جامعة الموصل", "split", ["I4W5J7PPKV", "I8XR4X37ZR"]),
 ("«صنعاء» = «جامعة صنعاء» (Sana'a University); «جامعة سيئون» is another university", "split", ["I47WYFRF1Q", "IVFZ9TP13M"]),
 ("Ain Shams University = جامعة عين شمس", "split", ["INB4MJCJT2", "IP6WTDFYN8"]),
 ("«١ ـمعة الإسلامية العاية» (an OCR-damaged «الجامعة الإسلامية العالمية - ماليزيا») vs the ambiguous «الجامعة الإسلامية»: different", "different", []),
 ("Constantine vs Constantine 2: rightly separate (numbered universities)", "different", []),
 ("Helwan University = جامعة حلوان", "split", ["IP4TFH3NK6", "ITG46N2C08"]),
 ("«الزقازيق» (from «آداب الزقازيق») = جامعة الزقازيق", "split", ["IVZHH97YCC", "IZ4MMZ8SFK"]),
 ("World Islamic Sciences University (Jordan) vs International Islamic University: different", "different", []),
 ("Radio administration vs University of Adrar: skeleton coincidence", "different", []),
 ("University of Al-Qadisiyah = جامعة القادسية", "split", ["I0N7SE896X", "I79T33M2NS"]),
]
S = dict(judged_by="agent (Claude)", org_institutions_600=208, already_holding_both_scripts=7,
         candidate_groups=len(J), confirmed_splits=sum(1 for j in J if j[1] == "split"),
         items=[dict(what=w, verdict=v, inst_ids=i) for w, v, i in J],
         note="a consonant-skeleton match only finds splits whose distinctive word is transliterated; «Université Mouloud Mammeri» vs «جامعة تيزي وزو» (renamed/aliased) is not found this way")
save("c2_cross_script_judged.json", S)
progress(f"- judged cross-script candidates: {S['confirmed_splits']} confirmed splits of {len(J)} groups")
print(S["confirmed_splits"])
