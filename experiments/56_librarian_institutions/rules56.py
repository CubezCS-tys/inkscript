"""Experiment 56, step 3: the calls the librarian made again and again, written as deterministic rules, and how many of
the librarian's own verdicts each rule reproduces (fires / agrees / disagrees).

Each rule reads one packet (and the authority) and returns a proposal or None. A rule "reproduces" a verdict when it
fires and its proposal equals the librarian's (same status, same first institution). Rules are measured one by one
on all 659 affiliations; none of them changes anything.

    python3 rules56.py        -> out/rules56.json and a table on stdout
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))
import judge56 as J  # noqa: E402

AUTH = J.AUTH

# R4: a faculty printed with only its city, where the city has one public university with that faculty
CITY_UNI = {"فاس": "L-ma-usmba", "fes": "L-ma-usmba", "ظهر المهراز": "L-ma-usmba", "dhar el mehraz": "L-ma-usmba",
            "الرباط": "L-ma-um5", "rabat": "L-ma-um5", "تطوان": "L-ma-uae", "tetouan": "L-ma-uae",
            "اكادير": "L-ma-uiz", "agadir": "L-ma-uiz", "الجديده": "L-ma-ucd", "الدار البيضاء": "L-ma-uh2",
            "casablanca": "L-ma-uh2", "مراكش": "L-ma-uca", "تونس": "L-tn-tunis"}
POSITION = re.compile(r"^\s*(أ\.?د\.?|د\.)?\s*(باحث|باحثة|باحثه|ناقد|كاتب|كاتبة|شاعر|قاص|قاصة|أكاديمي|اكاديمي|خبير|مدير مالي|"
                      r"أستاذ|استاذ|مدرس|Professor|Associate Professor|Assistant Professor|Lecturer|Researcher)"
                      r"[^،,\-]*$", re.I)
DEGREE = re.compile(r"(دكتوراه|ماجستير|Ph\.?D|Docteur|لنيل درجة|تحضّر للدكتوراه|تحضر للدكتوراه)", re.I)
BARE = re.compile(r"^\s*(ب|في |و)?(ال)?(كلية|جامعة|معهد|جهاز|جماعة|مجمع|الجماعة)\.?\s*$")
GEN_NAMES = [g for g in J.GENERIC]


def r1_form(p, v_rule):
    """R1 printed form: the statement contains an authority form (longest wins) → that institution."""
    ms = J.matches(p["printed"])
    return dict(status="resolved", org=J.top_of(ms[0][0])) if ms else None


def r2_unit_first(p, v_rule):
    """R2 the university over its unit: the machine linked a centre/institute/faculty printed in the same statement as
    a university → the university (the machine reads the department part first)."""
    m = p["machine"].get("org")
    ms = J.matches(p["printed"])
    unis = [J.top_of(a) for a, _ in ms if AUTH[J.top_of(a)]["type"] in ("university", "ministry")]
    if m and unis and not any(J.top_of(x) == unis[0] and J.canon(x) == unis[0] for x, _ in J.matches(" ".join(m["names"][:2]))):
        return dict(status="resolved", org=unis[0])
    return None


def r3_generic_country(p, v_rule):
    """R3 a generic body (وزارة التربية, Ministry of Education, مجلس الدولة) is resolved only by a country printed
    in the statement or the same author's statement; no country → unsure."""
    t = J.fk(p["printed"])
    for gid, form, rx in J.GFORMS:
        if rx.search(t) and not J.matches(p["printed"]):
            cc = J.printed_country(p)
            if cc:
                return dict(status="resolved", org=f"L-{cc.lower()}-{gid[2:]}")
            return dict(status="unsure", org=None)
    return None


def r4_city_faculty(p, v_rule):
    """R4 a faculty printed with only its city → that city's university (a table of 15 cities)."""
    if J.matches(p["printed"]) or not J.faculty_of(p):
        return None
    t = J.fk(p["printed"])
    for c, u in CITY_UNI.items():
        if re.search(r"(?:^|\s)(?:ب)?" + re.escape(J.fk(c)) + r"(?:\s|$)", t):
            return dict(status="resolved", org=u)
    return None


def r5_unnamed_in_article(p, v_rule):
    """R5 an unnamed «بالمعهد» / «بالجامعة» → the body another author of the same article names in full."""
    if not re.search(r"(^|\s)(ب|في )?(ال)(معهد|جامعة|كلية|مجمع)\.?\s*$", p["printed"].strip()):
        return None
    return dict(status="resolved", org="<from the article>")


def r6_not_institution(p, v_rule):
    """R6 no body printed: a place, a position, a degree or a bare head word («بالكلية», «بالجهاز») → not an institution."""
    if J.matches(p["printed"]) or J.faculty_of(p):
        return None
    s = p["printed"].strip(" .()")
    if re.search(r"كلي|جامع|ـمعة|univ|تجارة|آداب|معهد|مركز|وزار|هيئة|مجلس|الهيئ", s, re.I):
        return None
    if p["kind"] in ("place-only", "position-only") or BARE.match(s) or POSITION.match(s) or \
            (DEGREE.search(s) and not re.search(r"جامع|univ|كلي|معهد|وزار", s, re.I)):
        return dict(status="not_institution", org=None)
    return None


def r7_shared_name(p, v_rule):
    """R7 a name shared by two bodies (جامعة الزيتونة Tunisia / Libya; الجامعة الإسلامية) needs a printed place."""
    t = J.fk(p["printed"])
    if any(f in t for f in J.SHARED) or re.search(r"(^|\s)(بال|ال)جامعه الاسلاميه(\s|$)", t) and \
            not re.search(r"المدينه|غزه|العالميه|لبنان|ماليزيا|الاسمريه", t):
        cc = J.printed_country(p)
        if not cc:
            return dict(status="unsure", org=None)
    return None


def r8_country_conflict(p, v_rule):
    """R8 a printed country that differs from the matched institution's → hold for a person (caught «عمان» = Amman
    read as Oman, and a Cairo league printed after a Tunisian union)."""
    ms = J.matches(p["printed"])
    own = J.printed_country(p, include_same=False)
    if len(ms) == 1 and own and AUTH[J.top_of(ms[0][0])].get("country") not in (None, own):
        return dict(status="check", org=J.top_of(ms[0][0]))
    return None


RULES = [r1_form, r2_unit_first, r3_generic_country, r4_city_faculty, r5_unnamed_in_article, r6_not_institution,
         r7_shared_name, r8_country_conflict]


def main():
    P = J.load_packets()
    ov = J.load_overrides()
    out = []
    print(f"{'rule':28} fires agrees disagrees")
    for rule in RULES:
        c = Counter()
        ex = []
        for p in P:
            v = J.judge(p, ov)
            r = rule(p, J.propose(p))
            if r is None:
                continue
            c["fires"] += 1
            mine = (v["status"], v["orgs"][0] if v["orgs"] else None)
            if r["status"] == "check":
                ok = v["confidence"] == "low" or v["orgs"] != [r["org"]] or len(v["orgs"]) > 1
            elif r["org"] == "<from the article>":
                ok = v["status"] == "resolved" and v.get("basis") == "context"
            else:
                ok = (r["status"], r["org"]) == mine
            c["agrees" if ok else "disagrees"] += 1
            if not ok and len(ex) < 5:
                ex.append(dict(key=p["key"], printed=p["printed"][:120], rule=r, librarian=mine))
        doc = rule.__doc__.split("\n")[0]
        out.append(dict(rule=rule.__name__, what=" ".join(rule.__doc__.split()), fires=c["fires"], agrees=c["agrees"],
                        disagrees=c["disagrees"], disagreements=ex))
        print(f"{rule.__name__:28} {c['fires']:5} {c['agrees']:6} {c['disagrees']:9}   {doc[:70]}")
    (OUT / "rules56.json").write_text(json.dumps(out, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
