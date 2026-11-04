"""Experiment 63, step 4: hard checks, by code, over ALL of experiment 56's standing decisions (908).

Independent of exp 56's own matcher where it matters: the printed country is read with this file's own gazetteer
(country names and one-country cities, wider than judge56's), not with judge56.printed_country. The authority
(type, country, parent, forms) is read from experiment 56's authority56.py (a pure data module) and out/authority56.json.

Checks (each yields findings; a finding is a case to look at, not yet an error):
  H1  affiliation country != the country printed in the statement itself
  H2  one authority entry whose affiliations print two or more different countries
  H3  an authority entry whose country differs from a country printed by one of its affiliations
  H4  a same_institution merge whose member rows' affiliations print different countries
  H5  a bilingual twin (same_institution, bilingual_twin) whose printed cities differ
  H6  a set_parent whose parent is in another country than the unit (unit's printed country or the parent's)
  H7  a shared name: one folded form used by authority entries in different countries, and the decisions that chose one
      of them — is a country printed that agrees?
  H8  type contradictions: the authority type against the name's head word (جامعة/University, وزارة/Ministry, كلية,
      مركز/Centre, معهد/Institute, مجمع/Academy); set_type decisions against the authority type
  H9  a statement that prints two or more top-level bodies of the authority, decided with fewer
  H10 a not_an_institution / unit_kept_apart / unsure decision whose statement prints an authority form
  H11 set_country decisions against the authority country of the same institution, and against printed countries
  H12 the authority's parent chain (missing parent, self-parent, cycles) and units whose parent is not a top body
  H13 split groups (not_same_institution) against the affiliation decisions of the same affiliations
  H14 the authority country against the catalogue (MARC 502 $g) country attached to it
  H15 same_institution: an affiliation of a merged row whose own decision points elsewhere

    python3 hardchecks63.py          -> out/hardchecks63.json (all findings) and a summary on stdout
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E56 = HERE.parent / "56_librarian_institutions"
OUT = HERE / "out"
sys.path.insert(0, str(E56))
sys.path.insert(0, str(HERE.parent / "46_platform_db"))
from authority56 import AUTH  # noqa: E402  (pure data)

# ----------------------------------------------------------------------------------------------- normalising
DIAC = re.compile(r"[ً-ْـٰ]")


def norm(s: str | None) -> str:
    s = DIAC.sub("", s or "")
    s = s.replace("أ", "ا").replace("إ", "ا").replace("آ", "ا").replace("ة", "ه").replace("ى", "ي")
    s = re.sub(r"[\(\)\[\]،,;:\-–/|.«»\"']", " ", s)
    return " " + re.sub(r"\s+", " ", s).strip().lower() + " "


def has(text_n: str, form: str) -> bool:
    f = norm(form).strip()
    if not f:
        return False
    return re.search(r"(?:^|\s)(?:و|ب|ل|ف|بال|وال|لل|وب)?" + re.escape(f) + r"(?=\s|$)", text_n) is not None


# my own gazetteer: country words and cities that name one country only (Amman/Oman «عمان», Tripoli, Al-Quds and
# Jerusalem are left out on purpose: they are ambiguous or are also university names)
GAZ = {
    "EG": "مصر|جمهورية مصر العربية|egypt|egypte|القاهره|cairo|الاسكندريه|alexandria|الجيزه|المنصوره|الزقازيق|اسيوط|المنيا|الفيوم|طنطا|سوهاج|دمنهور|بنها|حلوان",
    "SA": "السعوديه|المملكه العربيه السعوديه|saudi arabia|ksa|الرياض|riyadh|جده|jeddah|مكه المكرمه|المدينه المنوره|الظهران|ابها|حائل|بيشه|الدمام",
    "JO": "الاردن|المملكه الاردنيه الهاشميه|jordan|اربد|الزرقاء",
    "IQ": "العراق|جمهوريه العراق|الجمهوريه العراقيه|iraq|بغداد|baghdad|البصره|basrah|الموصل|mosul|اربيل|erbil|كوردستان|الكوفه|النجف|تكريت|ديالي|القادسيه|كربلاء",
    "SY": "سوريا|سوريه|الجمهوريه العربيه السوريه|syria|syrie|دمشق|damascus|حلب|aleppo|حمص|اللاذقيه",
    "LB": "لبنان|الجمهوريه اللبنانيه|lebanon|liban|بيروت|beirut|صيدا|البقاع",
    "PS": "فلسطين|دوله فلسطين|palestine|غزه|gaza|رام الله|نابلس|الخليل|بيت لحم",
    "KW": "الكويت|دوله الكويت|kuwait",
    "AE": "الامارات|الامارات العربيه المتحده|united arab emirates|uae|الشارقه|sharjah|دبي|dubai|ابوظبي|abu dhabi|العين",
    "QA": "قطر|دوله قطر|qatar|الدوحه|doha",
    "BH": "البحرين|مملكه البحرين|bahrain|kingdom of bahrain|المنامه",
    "OM": "سلطنه عمان|oman|sultanate of oman|مسقط|muscat",
    "YE": "اليمن|الجمهوريه اليمنيه|yemen|republic of yemen|صنعاء|sanaa|عدن|حضرموت|سيئون",
    "SD": "السودان|جمهوريه السودان|sudan|الخرطوم|khartoum|سنار",
    "LY": "ليبيا|libya|libye|بنغازي|مصراته|زليتن|ترهونه|الخمس|سرت|سبها",
    "TN": "تونس|الجمهوريه التونسيه|tunisia|tunisie|صفاقس|سوسه|جندوبه|القيروان",
    "DZ": "الجزائر|algeria|algerie|قسنطينه|constantine|باتنه|batna|batna2|ميله|mila|تبسه|tebessa|الاغواط|laghouat|سعيده|saida|معسكر|mascara|البليده|blida|تيبازه|سطيف|setif|ورقله|الجلفه|djelfa|تيارت|عنابه|annaba|المسيله|وهران|oran|تلمسان|بجايه|بسكره|aflou|افلو",
    "MA": "المغرب|المملكه المغربيه|morocco|maroc|الرباط|rabat|فاس|fes|fès|fès sais|مراكش|marrakech|وجده|oujda|سطات|اكادير|agadir|تطوان|tetouan|tétouan|طنجه|خريبكه|القنيطره|مكناس|الجديده|الدار البيضاء|casablanca|المحمديه|mohammedia|الناظور",
    "MY": "ماليزيا|malaysia", "IN": "الهند|india|ديوبند|deoband|بنارس", "FR": "فرنسا|france",
    "US": "الولايات المتحده|usa|united states|texas", "CO": "colombia|كولومبيا", "GT": "guatemala",
    "TR": "تركيا|turkey|turquie", "PK": "باكستان|pakistan", "GB": "بريطانيا|united kingdom|london",
}
GAZ_RE = [(cc, re.compile(r"(?:^|\s)(?:ب|ل|بال|في )?(?:" + "|".join(re.escape(norm(w).strip()) for w in ws.split("|"))
                          + r")(?=\s|$)")) for cc, ws in GAZ.items()]


def countries_in(text: str) -> set:
    t = norm(text)
    return {cc for cc, rx in GAZ_RE if rx.search(t)}


CITY_WORDS = {w for ws in GAZ.values() for w in (norm(x).strip() for x in ws.split("|"))}

# ----------------------------------------------------------------------------------------------- loading


def load():
    latest = {}
    for line in open(E56 / "out" / "decisions56.jsonl", encoding="utf-8"):
        d = json.loads(line)
        latest[d["qkey"]] = d
    S = [d for d in latest.values() if d["kind"] != "retired"]
    P = {}
    for line in open(E56 / "out" / "packets56.jsonl", encoding="utf-8"):
        p = json.loads(line)
        P[p["key"]] = p
    I = {}
    for line in open(E56 / "out" / "institutions56.jsonl", encoding="utf-8"):
        r = json.loads(line)
        I[r["inst_id"]] = r
    A = {a["id"]: a for a in json.loads((E56 / "out" / "authority56.json").read_text(encoding="utf-8"))["institutions"]}
    return S, P, I, A


def auth(aid):
    return AUTH.get(aid) or {}


def top(aid):
    seen = set()
    while aid and auth(aid).get("parent") and aid not in seen:
        seen.add(aid)
        aid = auth(aid)["parent"]
    return aid


HEAD = [("university", r"^(?:ال)?جامع[هة]|university|université|universidad|^الجامعه"), ("ministry", r"^وزار[هة]|ministry"),
        ("faculty", r"^كلي[هة]|^faculty|^college|^faculté"), ("centre", r"^مركز|center|centre"),
        ("institute", r"^(?:ال)?معهد|institute|institut"), ("academy", r"^مجمع|^اكاديمي|academy|académie")]


def head_type(name: str) -> str | None:
    n = norm(name).strip()
    for t, rx in HEAD:
        if re.search(rx, n):
            return t
    return None


# ----------------------------------------------------------------------------------------------- checks


def main():
    S, P, I, A = load()
    F = defaultdict(list)
    aff = {d["subject_keys"][0]: d for d in S if d["level"] == "affiliation"}
    by_inst = defaultdict(list)  # authority id -> affiliation keys
    for k, d in aff.items():
        for x in d["decision"]["institutions"]:
            by_inst[x["id"]].append(k)
            if auth(x["id"]).get("parent"):
                by_inst[top(x["id"])].append(k)

    # H1 affiliation country vs the statement's own printed country
    for k, d in aff.items():
        x = d["decision"]
        if x["status"] != "resolved":
            continue
        pcs = countries_in(P[k]["printed"])
        if pcs and x["country"] and x["country"] not in pcs:
            F["H1"].append(dict(aff=k, decided=x["country"], printed=sorted(pcs), text=P[k]["printed"],
                                inst=[i["id"] for i in x["institutions"]], conf=d["confidence"]))
        if pcs and not x["country"]:
            F["H1_country_missing"].append(dict(aff=k, printed=sorted(pcs), text=P[k]["printed"]))

    # H1b a statement with bodies in two countries carries one country; H16 decided country vs the authority's
    for k, d in aff.items():
        x = d["decision"]
        ccs = {auth(i["id"]).get("country") or auth(top(i["id"])).get("country") for i in x["institutions"]} - {None}
        if len(ccs) > 1:
            F["H1b"].append(dict(aff=k, decided=x["country"], bodies_in=sorted(ccs), text=P[k]["printed"]))
        elif len(ccs) == 1 and x["country"] and x["country"] not in ccs:
            F["H16"].append(dict(aff=k, decided=x["country"], authority=sorted(ccs), text=P[k]["printed"]))

    # H2 / H3 per authority entry: printed countries of its affiliations (statements with one body only)
    for aid, ks in by_inst.items():
        pcs = Counter()
        for k in set(ks):
            if len(aff[k]["decision"]["institutions"]) != 1:
                continue
            for cc in countries_in(P[k]["printed"]):
                pcs[cc] += 1
        if len(pcs) > 1:
            F["H2"].append(dict(inst=aid, name=auth(aid).get("name_en"), printed_countries=dict(pcs),
                                n=len(set(ks))))
        ac = auth(aid).get("country") or A.get(aid, {}).get("country")
        if pcs and ac and ac not in pcs:
            F["H3"].append(dict(inst=aid, name=auth(aid).get("name_en"), authority=ac, printed=dict(pcs)))

    # H4 / H5 / H15 same_institution
    for d in S:
        if d["kind"] != "same_institution":
            continue
        x = d["decision"]
        rows = list(x["machine_rows"])
        row_cc, row_city = {}, {}
        for r in rows:
            cs, cities = set(), set()
            for k in I[r]["affiliations"]:
                if k in P:
                    cs |= countries_in(P[k]["printed"])
                    c = (P[k]["parts"].get("city") or "")
                    if c:
                        cities.add(norm(c).strip())
                    a = aff.get(k)
                    if a and a["decision"]["status"] == "resolved":
                        tops = {top(i["id"]) for i in a["decision"]["institutions"]} | \
                               {i["id"] for i in a["decision"]["institutions"]}
                        if x["institution"] not in tops:
                            F["H15"].append(dict(decision=d["decision_id"], merged_into=x["institution"], row=r,
                                                 aff=k, aff_decided=sorted(tops), text=P[k]["printed"]))
            row_cc[r], row_city[r] = cs, cities
        allc = set().union(*row_cc.values()) if row_cc else set()
        if len(allc) > 1:
            F["H4"].append(dict(decision=d["decision_id"], institution=x["institution"],
                                rows={r: sorted(c) for r, c in row_cc.items()}))
        if x.get("bilingual_twin"):
            cities = [c for c in row_city.values() if c]
            if len(cities) > 1 and not set.intersection(*cities):
                F["H5"].append(dict(decision=d["decision_id"], institution=x["institution"],
                                    cities={r: sorted(c) for r, c in row_city.items()}))

    # H6 set_parent: parent's country vs the unit's
    for d in S:
        if d["kind"] != "set_parent":
            continue
        x = d["decision"]
        pc = auth(x["parent"]).get("country")
        ucs = set()
        for k in x.get("affiliations", []):
            if k in P:
                ucs |= countries_in(P[k]["printed"])
        mc = I.get(x["machine_row"], {}).get("country")
        if pc and ((ucs and pc not in ucs) or (mc and mc != pc)):
            F["H6"].append(dict(decision=d["decision_id"], row=x["machine_row"], parent=x["parent"], parent_cc=pc,
                                printed=sorted(ucs), machine_cc=mc,
                                text=[P[k]["printed"] for k in x.get("affiliations", []) if k in P]))
        if not auth(x["parent"]):
            F["H12"].append(dict(decision=d["decision_id"], problem="parent not in authority", parent=x["parent"]))

    # H7 shared names
    forms = defaultdict(set)
    for aid, a in AUTH.items():
        for f in a["forms"] + [a["name_ar"], a["name_en"]]:
            if f:
                forms[norm(f).strip()].add(aid)
    shared = {f: ids for f, ids in forms.items() if len({auth(i).get("country") for i in ids}) > 1 and len(ids) > 1}
    for f, ids in shared.items():
        users = []
        for k, d in aff.items():
            chosen = {i["id"] for i in d["decision"]["institutions"]} & ids
            if chosen and has(norm(P[k]["printed"]), f):
                cc = auth(next(iter(chosen))).get("country")
                pcs = countries_in(P[k]["printed"] + " " + " ".join(x["printed"] for x in P[k]["same_article"]))
                ok = cc in pcs
                users.append(dict(aff=k, chosen=sorted(chosen), country=cc, printed=sorted(pcs), supported=ok,
                                  journal=P[k]["journal_id"], text=P[k]["printed"]))
        F["H7"].append(dict(form=f, entries={i: auth(i).get("country") for i in ids}, uses=users))

    # H8 type contradictions
    for aid, a in AUTH.items():
        if a.get("generic"):
            continue
        ht = head_type(a["name_ar"]) or head_type(a["name_en"] or "")
        t = a["type"]
        if ht and ht != t and not (ht == "institute" and t in ("school", "centre", "university")) and \
                not (ht == "centre" and t in ("institute",)) and not (ht == "faculty" and t in ("school",)) and \
                not (ht == "university" and t == "other" and "الدول" in a["name_ar"]):
            F["H8"].append(dict(inst=aid, type=t, name_ar=a["name_ar"], name_en=a["name_en"], head=ht,
                                parent=a.get("parent")))
    for d in S:
        if d["kind"] == "set_type":
            x = d["decision"]
            if auth(x["institution"]).get("type") and auth(x["institution"])["type"] != x["type"]:
                F["H8_set_type"].append(dict(decision=d["decision_id"], inst=x["institution"], set=x["type"],
                                             authority=auth(x["institution"])["type"]))

    # H9 two or more top-level bodies printed, fewer decided
    tops_forms = [(aid, f) for aid, a in AUTH.items() for f in a["forms"]]
    for k, d in aff.items():
        t = norm(P[k]["printed"])
        found = {}
        for aid, f in tops_forms:
            if has(t, f):
                found.setdefault(top(aid), set()).add(norm(f).strip())
        # drop a body whose every matched form sits inside a longer matched form of another body
        keep = {}
        for b, fs in found.items():
            others = {g for b2, gs in found.items() if b2 != b for g in gs}
            if any(not any(f != g and f in g for g in others) for f in fs):
                keep[b] = fs
        # bodies sharing one form (Zaytuna LY/TN, generic ministries): count one
        groups = {frozenset(fs) for fs in keep.values()}
        decided = {top(i["id"]) for i in d["decision"]["institutions"]}
        if len(groups) >= 2 and len(decided) < len(groups):
            F["H9"].append(dict(aff=k, text=P[k]["printed"], printed_bodies=sorted(keep), decided=sorted(decided),
                                status=d["decision"]["status"]))

    # H10 a body printed but not linked
    for k, d in aff.items():
        if d["decision"]["status"] in ("not_institution", "unit_only", "unsure"):
            t = norm(P[k]["printed"])
            hits = sorted({aid for aid, f in tops_forms if has(t, f) and len(norm(f).strip()) > 6})
            if hits:
                F["H10"].append(dict(aff=k, status=d["decision"]["status"], text=P[k]["printed"], forms_of=hits))

    # H11 set_country
    for d in S:
        if d["kind"] != "set_country":
            continue
        x = d["decision"]
        ac = auth(x.get("institution")).get("country") if x.get("institution") else None
        if ac and ac != x["country"]:
            F["H11"].append(dict(decision=d["decision_id"], set=x["country"], authority=ac, inst=x.get("institution")))
        pcs = set()
        for k in I.get(x["machine_row"], {}).get("affiliations", []):
            if k in P:
                pcs |= countries_in(P[k]["printed"])
        if pcs and x["country"] not in pcs:
            F["H11_printed"].append(dict(decision=d["decision_id"], set=x["country"], printed=sorted(pcs),
                                         row=x["machine_row"], names=I[x["machine_row"]]["names"]))

    # H12 parent chains
    for aid, a in AUTH.items():
        p = a.get("parent")
        if not p:
            continue
        if p == aid:
            F["H12"].append(dict(inst=aid, problem="self parent"))
        elif p not in AUTH:
            F["H12"].append(dict(inst=aid, problem="parent missing", parent=p))
        else:
            seen, q = {aid}, p
            while q and q in AUTH:
                if q in seen:
                    F["H12"].append(dict(inst=aid, problem="cycle"))
                    break
                seen.add(q)
                q = AUTH[q].get("parent")
            if a.get("country") and AUTH[p].get("country") and a["country"] != AUTH[p]["country"]:
                F["H12"].append(dict(inst=aid, problem="unit and parent in different countries", unit_cc=a["country"],
                                     parent=p, parent_cc=AUTH[p]["country"]))

    # H13 split groups vs affiliation decisions
    for d in S:
        if d["kind"] != "not_same_institution":
            continue
        for gid, ks in d["decision"]["groups"].items():
            for k in ks:
                a = aff.get(k)
                if not a:
                    continue
                ids = {i["id"] for i in a["decision"]["institutions"]} | {top(i["id"]) for i in
                                                                       a["decision"]["institutions"]}
                if gid.startswith("<"):
                    if a["decision"]["status"] == "resolved":
                        F["H13"].append(dict(decision=d["decision_id"], group=gid, aff=k, aff_decided=sorted(ids)))
                elif gid not in ids:
                    F["H13"].append(dict(decision=d["decision_id"], group=gid, aff=k, aff_decided=sorted(ids),
                                         status=a["decision"]["status"]))

    # H14 authority country vs catalogue country
    for aid, a in A.items():
        cat = a.get("catalogue") or {}
        if cat.get("country") and a.get("country") and cat["country"] != a["country"]:
            F["H14"].append(dict(inst=aid, name=a["name_en"], authority=a["country"], catalogue=cat))

    # H17 links whose statement prints none of the chosen entry's forms (or its units' forms): judgement links
    unit_forms = defaultdict(list)
    for aid, a in AUTH.items():
        if a.get("parent"):
            unit_forms[top(aid)] += a["forms"] + [a["name_ar"], a["name_en"] or ""]
    for k, d in aff.items():
        for i in d["decision"]["institutions"]:
            a = auth(i["id"])
            fs = a.get("forms", []) + [a.get("name_ar") or "", a.get("name_en") or ""] + unit_forms.get(i["id"], [])
            t = norm(P[k]["printed"])
            if not any(has(t, f) for f in fs if f):
                F["H17"].append(dict(aff=k, inst=i["id"], basis=d["basis"], conf=d["confidence"],
                                     text=P[k]["printed"]))
            if a.get("ambiguous"):
                pcs = countries_in(P[k]["printed"] + " " + " ".join(x["printed"] for x in P[k]["same_article"]))
                F["H7_ambiguous"].append(dict(aff=k, inst=i["id"], country=a.get("country"), printed=sorted(pcs),
                                              supported=a.get("country") in pcs, text=P[k]["printed"]))

    # H18 a longer university name printed around the matched form (the «Islamic University of Lebanon» trap)
    ADJ = r"(?:الاسلاميه|الامريكيه|الاهليه|الخاصه|الدوليه|العالميه|المفتوحه|التقنيه|التكنولوجيه|للعلوم|للبنات|الوطنيه)"
    for k, d in aff.items():
        t = norm(P[k]["printed"])
        for i in d["decision"]["institutions"]:
            for f in auth(i["id"]).get("forms", []):
                nf = norm(f).strip()
                if nf.startswith("جامعه ") or nf.startswith("الجامعه "):
                    m = re.search(re.escape(nf) + r"\s+" + ADJ, t)
                    if m and not any(has(t, g) and len(norm(g).strip()) > len(nf) for g in auth(i["id"])["forms"]):
                        F["H18"].append(dict(aff=k, inst=i["id"], form=f, text=P[k]["printed"]))

    OUT.mkdir(exist_ok=True)
    (OUT / "hardchecks63.json").write_text(json.dumps(F, ensure_ascii=False, indent=1), encoding="utf-8")
    print("standing decisions:", len(S))
    for h in sorted(F):
        extra = ""
        if h == "H7":
            n_uses = sum(len(x["uses"]) for x in F[h])
            n_unsup = sum(1 for x in F[h] for u in x["uses"] if not u["supported"])
            extra = f"  (uses {n_uses}, without a supporting printed country {n_unsup})"
        print(f"{h:16s} {len(F[h]):4d}{extra}")


if __name__ == "__main__":
    main()
