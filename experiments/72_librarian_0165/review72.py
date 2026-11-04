"""Experiment 72: the authority review — bodies the models named that the authority does not hold.

Experiment 71's rule never applies a "new:" body without an authority review. Here the review is done by hand (by
the experiment's agent, reading every printed statement) and recorded: each body the models named outside the
authority is accepted (a new authority entry L-72-…, with names, type, country, parent and the printed forms that
point at it), mapped to an existing entry (the model did not see it among the candidates), or refused.

    python review72.py gather    -> out/inst/review_candidates.json (every outside id, its questions and statements)
    python review72.py write     REVIEW below -> out/inst/authority72.json (bodies + answer_map: question -> ids)
"""
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

from common72 import OUT, jl, js, wjs
from inst72 import fold

FLASH, OPUS = "gemini-3.8-flash", "claude-opus-5-5"


def outside(q, a):
    auth = {c["id"] for c in q["evidence"].get("authority_candidates") or []}
    return [i for i in (a.get("ids") or []) if i not in auth]


def gather():
    Q = {q["id"]: q for q in jl(OUT / "questions" / "inst.jsonl")}
    A = {m: {} for m in (FLASH, OPUS)}
    for m in A:
        for a in jl(OUT / "answers" / f"{m}.jsonl"):
            if a.get("answer"):
                A[m][a["id"]] = a["answer"]
    groups = defaultdict(lambda: dict(names=set(), questions=[], countries=set(), models=set()))
    for qid, q in Q.items():
        if q["kind"] not in ("inst:affiliation", "inst:set_parent"):
            continue
        for m in (OPUS, FLASH):
            a = A[m].get(qid)
            if not a or a.get("answer") not in ("resolved", "parent"):
                continue
            for i in outside(q, a):
                nm = i[4:] if i.startswith("new:") else i
                k = fold(re.sub(r"[٠-٩]", lambda x: str("٠١٢٣٤٥٦٧٨٩".index(x.group())), nm))
                g = groups[k]
                g["names"].add(nm)
                g["models"].add(m)
                if a.get("country"):
                    g["countries"].add(a["country"])
                if qid not in [x["q"] for x in g["questions"]]:
                    g["questions"].append(dict(q=qid, printed=q["evidence"].get("printed") or
                                               [x.get("printed") for x in q["evidence"].get("affiliations", [])][:2],
                                               opus=A[OPUS].get(qid, {}).get("ids"), opus_conf=A[OPUS].get(qid, {}).get(
                                                   "confidence"), flash=A[FLASH].get(qid, {}).get("ids")))
    out = [dict(key=k, names=sorted(g["names"]), countries=sorted(g["countries"]), models=sorted(g["models"]),
                questions=g["questions"]) for k, g in sorted(groups.items())]
    wjs(OUT / "inst" / "review_candidates.json", out)
    for x in out:
        print(f"{x['key']} | {x['names']} {x['countries']} {x['models']} n={len(x['questions'])}")
        for y in x["questions"][:3]:
            print("      ", y["q"], str(y["printed"])[:110], "| O:", y["opus"], y["opus_conf"])


# ------------------------------------------------------------------ the review (by hand, 2026-11-02, agent:exp72)
# (id, type, country, name_ar, name_en, forms the rule may match, machine rows (the first is the body's row), why)
# Each was read against every statement that names it (review_candidates.json). A form is added only when it names
# this one body wherever it is printed (a generic «أكاديمية الفنون» or «وزارة التنمية الاجتماعية» only with its country).
U, O_, C, M, S, A = "university", "other", "centre", "ministry", "society", "academy"
REVIEW = [
    ("L-72-eg-scu", O_, "EG", "المجلس الأعلى للجامعات", "Supreme Council of Universities (Egypt)",
     ["المجلس الأعلى للجامعات", "المجلس الأعلى للجامعات المصرية"], ["ICDD3H7888", "IV1W0TQ3VE"],
     "Egypt's council of the universities; its sector committees («لجنة قطاع دراسات الطفولة») are printed beside it"),
    ("L-72-int-accd", O_, "EG", "المجلس العربي للطفولة والتنمية", "Arab Council for Childhood and Development",
     ["المجلس العربي للطفولة والتنمية"], ["IACVFC5J84"],
     "an Arab regional body seated in Cairo; the publisher of this journal J0165 (catalogue 260$b)"),
    ("L-72-eg-arts-academy", A, "EG", "أكاديمية الفنون", "Academy of Arts (Egypt)",
     ["أكاديمية الفنون مصر", "أكاديمية الفنون بمصر", "أكاديمية الفنون المصرية"], ["ITFYKE2VPY"],
     "Egypt's state Academy of Arts (Giza); printed with مصر each time. The bare name is not a form (other countries "
     "have academies of arts)"),
    ("L-72-eg-6october", U, "EG", "جامعة 6 أكتوبر", "October 6 University", ["جامعة 6 أكتوبر", "جامعة ٦ أكتوبر"],
     ["I2BDQ4FHMB", "IWNR2771A2"], "a private Egyptian university (6th of October City); «217» in one row is a page "
                                   "number glued to the name"),
    ("L-72-eg-ncee", C, "EG", "المركز القومي للامتحانات والتقويم التربوي",
     "National Center for Examinations and Educational Evaluation (Egypt)",
     ["المركز القومي للامتحانات والتقويم التربوي"], ["IH7T7N7PSF"], "an Egyptian national centre; printed with مصر once"),
    ("L-72-eg-misrelkheir", O_, "EG", "مؤسسة مصر الخير", "Misr El Kheir Foundation", ["مؤسسة مصر الخير"], [],
     "an Egyptian foundation (its name says Egypt); no machine row of its own"),
    ("L-72-om-mosd", M, "OM", "وزارة التنمية الاجتماعية (سلطنة عمان)", "Ministry of Social Development (Oman)",
     ["وزارة التنمية الاجتماعية في سلطنة عمان", "وزارة التنمية الاجتماعية بسلطنة عمان"], ["I3WGPHHGZ8"],
     "a generic ministry name resolved by the printed country (سلطنة عمان), as exp 56's R3"),
    ("L-72-jo-mosd", M, "JO", "وزارة التنمية الاجتماعية (الأردن)", "Ministry of Social Development (Jordan)",
     ["وزارة التنمية الاجتماعية الأردن"], ["I8PZ5ZYBMK"], "the generic name with the printed country الأردن (R3)"),
    ("L-72-eg-moc", M, "EG", "وزارة الثقافة (مصر)", "Ministry of Culture (Egypt)", ["وزارة الثقافة مصر"],
     ["INSRXEKDPY"], "the generic name with the printed country مصر (R3)"),
    ("L-72-ma-irfcjs", "institute", "MA", "المعهد الملكي لتكوين أطر الشبيبة والرياضة",
     "Royal Institute for the Training of Youth and Sports Cadres (Rabat)",
     ["المعهد الملكي لتكوين أطر الشبيبة والرياضة"], ["I3VR2DZ2K8"], "printed with الرباط، المغرب"),
    ("L-72-ly-ala", A, "LY", "مجمع اللغة العربية الليبي", "Libyan Arabic Language Academy",
     ["مجمع اللغة العربية الليبي", "مجمع اللغة العربية ليبيا"], ["IZ77HN5YKW"],
     "printed «مجمع اللغة العربية، ليبيا»; the bare «مجمع اللغة العربية» is not a form (Cairo, Damascus, Amman …)"),
    ("L-72-eg-auc", U, "EG", "الجامعة الأمريكية بالقاهرة", "American University in Cairo",
     ["الجامعة الأمريكية بالقاهرة", "الجامعة الأمريكية في القاهرة", "American University in Cairo"], ["IH8384EX2W"],
     "well known; the name says Cairo"),
    ("L-72-eg-arish", U, "EG", "جامعة العريش", "Arish University", ["جامعة العريش"], ["IHN65ENTHB"],
     "an Egyptian public university (North Sinai); printed with مصر"),
    ("L-72-ps-qou", U, "PS", "جامعة القدس المفتوحة", "Al-Quds Open University", ["جامعة القدس المفتوحة"],
     ["IS6EJCS2AS"], "not Al-Quds University (L-ps-quds): the longer name must win (exp 63's H18 trap); branches such "
                     "as «فرع طولكرم» are its own"),
    ("L-72-dz-mostaganem", U, "DZ", "جامعة عبد الحميد بن باديس مستغانم", "Abdelhamid Ibn Badis University of Mostaganem",
     ["جامعة عبد الحميد بن باديس", "جامعة مستغانم"], ["IY1C3NF47D", "IFCNZ1AGYM"],
     "Mostaganem's university; «جامعة مستغانم» is its short name"),
    ("L-72-ly-benghazi", U, "LY", "جامعة بنغازي", "University of Benghazi (formerly Garyounis University)",
     ["جامعة بنغازي", "جامعة قاريونس"], ["IZA2P6F0H1", "I9V5E74T0W"],
     "Garyounis University was renamed the University of Benghazi in 2011: one body, both names printed in 0165"),
    ("L-72-jo-aabu", U, "JO", "جامعة آل البيت", "Al al-Bayt University", ["جامعة آل البيت"], ["I1JNCWKXPC"],
     "Jordan (Mafraq), well known"),
    ("L-72-jo-autism", S, "JO", "الجمعية الأردنية للتوحد", "Jordanian Autism Society (as printed)",
     ["الجمعية الأردنية للتوحد"], ["IASP6ZHEXR"], "the name says Jordan; the author is its director"),
    ("L-72-eg-epa", S, "EG", "الجمعية المصرية للطب النفسي", "Egyptian Psychiatric Association",
     ["الجمعية المصرية للطب النفسي"], ["I83C8EVT6D"], "the name says Egypt"),
    ("L-72-eg-addiction-fund", O_, "EG", "صندوق مكافحة وعلاج الإدمان والتعاطي",
     "Fund for Drug Control and Treatment of Addiction (Egypt)", ["صندوق مكافحة وعلاج الإدمان والتعاطي"],
     ["I008D9FC5A"], "Egypt's national fund (Ministry of Social Solidarity)"),
    ("L-72-ma-uem", S, "MA", "اتحاد كتاب المغرب", "Union of Moroccan Writers", ["اتحاد كتاب المغرب"], ["IATF5A5GVQ"],
     "the name says Morocco"),
    ("L-72-fr-paris7", U, "FR", "جامعة باريس 7 ديدرو", "Université Paris Diderot (Paris 7)",
     ["جامعة باريس 7 ديدرو", "جامعة باريس السابعة"], ["I46AEXSK19"], "printed as the university of a doctorate (D37)"),
    # accepted, used by no applied decision in this pass (their questions are held for a person): kept for the rules
    ("L-72-jo-jerash", U, "JO", "جامعة جرش", "Jerash University", ["جامعة جرش"], ["IEY81QF4AA"], "Jordan"),
    ("L-72-dz-tiaret", U, "DZ", "جامعة ابن خلدون تيارت", "Ibn Khaldoun University of Tiaret",
     ["جامعة ابن خلدون تيارت", "جامعة تيارت"], ["I7ZZ84Z4VQ"], "Algeria; not Ibn Khaldoun's name elsewhere"),
    ("L-72-eg-sadat", U, "EG", "جامعة مدينة السادات", "University of Sadat City", ["جامعة مدينة السادات"],
     ["I3WJ1R57C0"], "Egypt"),
    ("L-72-eg-nrc", C, "EG", "المركز القومي للبحوث", "National Research Centre (Egypt)", ["المركز القومي للبحوث"],
     ["I4XJ98GCN1"], "Egypt's NRC (Dokki); the bare name is Egypt's in this literature"),
    ("L-72-eg-scc", O_, "EG", "المجلس الأعلى للثقافة", "Supreme Council of Culture (Egypt)", ["المجلس الأعلى للثقافة"],
     ["I8AB1HNJDQ"], "printed with مصر"),
    ("L-72-eg-moss", M, "EG", "وزارة التضامن الاجتماعي (مصر)", "Ministry of Social Solidarity (Egypt)",
     ["وزارة التضامن الاجتماعي"], ["INYWZ9YFNR"], "only Egypt's ministry has this name"),
    ("L-72-int-unodc", O_, None, "مكتب الأمم المتحدة المعني بالمخدرات والجريمة",
     "United Nations Office on Drugs and Crime (UNODC)", ["مكتب الأمم المتحدة المعني بالمخدرات والجريمة"],
     ["IENTMPJE56"], "an international body; its seat (Vienna) is not where the author works: country left open"),
]
REFUSED = {
    "مشروع نداء لجوده تاهيل تعليم لذوي اعاقات متعدده": "a project, not a body",
    "وزاره تربيه تعليم تعليم فني": "not printed: «الإدارة المركزية للتربية الخاصة …» names a department only "
                                   "(a person may infer the ministry)",
}


def write():
    import judge56  # noqa: F401  (loads the authority with experiment 64's bodies)
    from inst72 import desk_defined, load_authority
    AUTH = load_authority()
    defined = desk_defined()
    canon_of = {v: k for k, v in defined.items()}
    bodies = []
    keymap = {}
    for (i, t, cc, ar, en, forms, rows, why) in REVIEW:
        claimed = [r for r in rows if r in canon_of]
        if claimed:
            raise SystemExit(f"{i}: row {claimed} is already the Desk's row for {canon_of[claimed[0]]}")
        bodies.append(dict(id=i, type=t, country=cc, name_ar=ar, name_en=en, forms=forms, rows=rows, why=why,
                           accepted=True, reviewed_by="agent:exp72 (by hand, 2026-11-02)"))
        for x in [ar, en] + forms:
            keymap[fold(re.sub(r"\(.*?\)", "", x))] = i
            keymap[fold(x)] = i
        for r in rows:
            keymap[r] = i
    # an outside id the models gave -> a reviewed body, or an authority entry the model did not see
    from judge56 import matches
    Q = {q["id"]: q for q in jl(OUT / "questions" / "inst.jsonl")}
    amap = {}
    for a in jl(OUT / "answers" / f"{OPUS}.jsonl"):
        q = Q.get(a["id"])
        ans = a.get("answer") or {}
        if not q or ans.get("answer") not in ("resolved", "parent"):
            continue
        out_ids = outside(q, ans)
        if not out_ids:
            continue
        ids, ok, why = [], True, []
        for x in ans["ids"]:
            if x not in out_ids:
                ids.append(x)
                continue
            nm = x[4:] if x.startswith("new:") else x
            b = keymap.get(x) or keymap.get(fold(nm)) or keymap.get(fold(re.sub(r"\(.*?\)", "", nm)))
            if not b and x in canon_of:
                b = canon_of[x]
            if not b and x.startswith("new:"):
                ms = matches(nm)
                if len(ms) == 1 and fold(AUTH[ms[0][0]]["name_ar"] or "") == fold(nm):
                    b = ms[0][0]
            if b:
                ids.append(b)
                why.append(f"{x} -> {b}")
            else:
                ok = False
                why.append(f"{x}: not accepted")
        amap[a["id"]] = dict(ids=ids, ok=ok, why="; ".join(why))
    wjs(OUT / "inst" / "authority72.json", dict(bodies=bodies, refused=REFUSED, answer_map=amap))
    print(len(bodies), "bodies;", sum(1 for v in amap.values() if v["ok"]), "of", len(amap), "answers mapped")
    for k, v in amap.items():
        if not v["ok"]:
            print("  not mapped:", k, v["why"])


if __name__ == "__main__":
    dict(gather=gather, write=write)[sys.argv[1]]()
