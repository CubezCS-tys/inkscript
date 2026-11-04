"""C2c judgments by an agent (Claude) of c2_openalex.json (source "openalex"): is OpenAlex's top hit for our university
name the same institution, in the right country? right / wrong / unsure / miss (no hit) / n.a. (our name is not one
institution)."""
import json
from common48c import OUT, save, wilson, progress
J = {0: ("n.a.", "two universities in one string («جامعتى القاهرة وصنعاء»)"),
     1: ("miss", "Sétif 2 (Mohamed Lamine Debaghine); our name has Persian ی, no hit"),
     6: ("miss", "Mohamed El Bachir El Ibrahimi University, Bordj Bou Arreridj: Arabic name not found"),
     10: ("unsure", "«University of Management and Technology»: top hit is UMT Lahore (PK); our affiliation gives no country"),
     11: ("miss", "French form «Université d'Ain-Shams» not found (the English and Arabic forms are)"),
     15: ("miss", "«Université de Bejaia» not found"), 16: ("miss", "Emir Abdelkader University (Constantine) not found"),
     18: ("miss", "«Université Abderrahmane Mira de Bejaia» not found"),
     20: ("n.a.", "our institution name is the generic «University Center» (a mis-read «Centre universitaire …»)"),
     27: ("miss", "Imam Ja'far al-Sadiq University (Iraq) not found"), 35: ("miss", "Larbi Tebessi University (Tébessa) not found"),
     37: ("miss", "«University of Tlemcen» (Abou Bekr Belkaïd) not found by this English form"),
     38: ("unsure", "«جامعة الفرات»: top hit Al-Furat Al-Awsat Technical University (IQ), second Al Furat University (SY); needs the country"),
     41: ("wrong", "«الجامعة الإسلامية العالمية» -> Selangor Islamic University (MY); meant IIUM Malaysia (or Islamabad)"),
     43: ("unsure", "«جامعة الزيتونة»: Jordan, Libya and Tunisia all have one; top hit Jordan"),
     44: ("miss", "«Univversité blida 2» (typo) not found"), 48: ("miss", "Batna 2 (Mustafa Ben Boulaïd) not found")}
d = json.load(open(OUT / "c2_openalex.json"))
items = []
for i, x in enumerate(d["items"]):
    v, why = J.get(i, ("right", "top hit is the same university, right country"))
    top = next((s["top"][0] for s in x["searches"] if s["top"]), None)
    items.append(dict(i=i, inst_id=x["inst_id"], names=x["names"], verdict=v, why=why, source="openalex",
                      openalex_id=top and top["id"], ror=top and top["ror"], openalex_name=top and top["name"], cc=top and top["cc"]))
k = {v: sum(1 for x in items if x["verdict"] == v) for v in ("right", "wrong", "unsure", "miss", "n.a.")}
n = len(items) - k["n.a."]
calls = sum(1 for l in open(OUT / "external_calls.jsonl") if '"status": 200' in l)
S = dict(judged_by="agent (Claude)", source="openalex", seed=4824, searched=len(items), testable=n, verdicts=k,
         found_right_share=round(k["right"] / n, 3), found_right_wilson95=wilson(k["right"], n),
         wrong_top_hit_wilson95=wilson(k["wrong"], n),
         openalex_institutions_in_arab_countries=sum(g["count"] for g in d["countries"]),
         openalex_education_institutions_in_arab_countries=sum(g["count"] for g in d["countries_education"]),
         per_country=[(g.get("key_display_name") or g["key"], g["count"]) for g in d["countries"]],
         cross_script_twins_resolved=["Helwan University / جامعة حلوان -> ROR 00h55v928", "Tikrit University / جامعة تكريت -> ROR 01zfzax10"],
         calls_ok=calls, notes=["11 misses: mostly Algerian universities under French or eponym names, plus Arabic spelling variants (ى/ي, ی): a query per name form still misses them",
                                "ambiguous names (الزيتونة, الفرات, الإسلامية العالمية, طرابلس) need a country filter, else the top hit can be the wrong country"])
save("c2_openalex_judged.json", dict(summary=S, items=items))
R = json.load(open(OUT / "results.json"))
R["C2_institutions"]["openalex"] = dict(status="measured 2026-10-21 with the owner's API key (never stored)", **S)
save("results.json", R)
progress(f"- OpenAlex coverage judged: {k}")
print(json.dumps({x: S[x] for x in S if x != "per_country"}, ensure_ascii=False, indent=1))
