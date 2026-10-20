"""Experiment 46: affiliations → institutions (organisation > faculty > department), Arabic and English, by folding.

Each affiliation's printed parts (orgname, dept, the raw text when nothing is tagged) are split at - ، , / | and each
piece is classed by its head word (جامعة/University → organisation, كلية/College/Faculty → faculty, قسم/Department →
department, a known country → country). The key of a piece is its folded form without spaces, the article ال and
"the/of"; keys within one level that are near-identical (ratio ≥ 0.92 on keys of ≥ 8 letters) are one institution.
Rebuilt from the `affiliations` rows on every load (cheap, deterministic); writes org_key/faculty_key/dept_key back.
"""
from __future__ import annotations

import re
from collections import Counter, defaultdict

from common46 import fold, key, latin_key, ratio

ORG = re.compile(r"(جامع|university|univ\b|وزار|ministry|مركز|center|centre|معهد|institut|اكاديمي|academy|هيئ|"
                 r"مدرس|school|مستشفي|hospital|شرك|company|بنك|bank|مجلس|council|مكتب|library|منظم|organi[sz]ation|"
                 r"مجمع|المجمع|ديوان|دار\s|جمعي|society|association|نقاب|اتحاد|union|مؤسس|foundation|corporation|"
                 r"المحكم|محكم|court|القضاء|الامانه|امانه|secretariat|بلدي|municipal|مديري|directorate|الادار|ادار)",
                 re.I)
FAC = re.compile(r"^(كلي|college|faculty|school of|عماد|deanship)", re.I)
DEP = re.compile(r"^(قسم|شعب|department|dept|division|وحد|unit|برنامج|program)", re.I)
COUNTRIES = {
    "SA": ["السعوديه", "المملكه العربيه السعوديه", "saudi arabia", "ksa", "kingdom of saudi arabia"],
    "EG": ["مصر", "جمهوريه مصر العربيه", "egypt", "arab republic of egypt"],
    "JO": ["الاردن", "المملكه الاردنيه الهاشميه", "jordan"],
    "IQ": ["العراق", "iraq"], "SY": ["سوريا", "سوريه", "syria"], "LB": ["لبنان", "lebanon"],
    "PS": ["فلسطين", "palestine"], "KW": ["الكويت", "دوله الكويت", "kuwait"],
    "AE": ["الامارات", "الامارات العربيه المتحده", "دوله الامارات العربيه المتحده", "uae", "united arab emirates"],
    "QA": ["قطر", "دوله قطر", "qatar"], "BH": ["البحرين", "مملكه البحرين", "bahrain"],
    "OM": ["عمان", "سلطنه عمان", "oman", "sultanate of oman"], "YE": ["اليمن", "الجمهوريه اليمنيه", "yemen"],
    "SD": ["السودان", "sudan"], "LY": ["ليبيا", "libya"], "TN": ["تونس", "الجمهوريه التونسيه", "tunisia"],
    "DZ": ["الجزائر", "algeria"], "MA": ["المغرب", "المملكه المغربيه", "morocco"], "MR": ["موريتانيا", "mauritania"],
    "US": ["usa", "united states", "الولايات المتحده الامريكيه"], "GB": ["uk", "united kingdom", "england"],
    "FR": ["france", "فرنسا"], "MY": ["malaysia", "ماليزيا"], "TR": ["turkey", "تركيا"],
}
COUNTRY_OF = {key(n): c for c, ns in COUNTRIES.items() for n in ns}
STOP_LAT = {"the", "of", "and", "for", "in", "at"}


def script(s: str) -> str:
    return "ar" if re.search("[؀-ۿ]", s or "") else "lat"


def norm_key(s: str) -> str:
    """Folded, no punctuation, no ال on each word, no stop words, no spaces."""
    if script(s) == "ar":
        ws = [re.sub(r"^(وال|بال|لل|ال)", "", w) if len(w) > 4 else w for w in key(s).split()]
    else:
        ws = [w for w in latin_key(s).split() if w not in STOP_LAT]
    return "".join(ws)


def pieces(text: str) -> list[str]:
    parts = re.split(r"\s+[-–—]\s*|\s*[-–—]\s+|[،,/|;؛]|\s-(?=\S)|(?<=\S)-\s", text or "")
    return [p.strip(" .:()[]") for p in parts if p and p.strip(" .:()[]")]


def classify(p: str) -> str:
    f = fold(p)
    k = key(p)
    if k in COUNTRY_OF:
        return "country"
    w = re.sub(r"^(ب|في|و)", "", f)
    w = re.sub(r"^(مدرس|استاذ|محاضر|باحث|استاذه|lecturer|professor|researcher|assistant|associate)\S*\s+", "", w)
    if DEP.search(w):
        return "department"
    if FAC.search(w):
        return "faculty"
    if ORG.search(f):
        return "organisation"
    return "other"


def strip_role(p: str) -> str:
    """'مدرس المناهج…' / 'الاستاذ بقسم…' → the institution part."""
    f = p
    m = re.search(r"(قسم|كلي|جامع|شعب|department|college|faculty|university)", f, re.I)
    if m and m.start() > 0 and len(f[:m.start()].split()) <= 4:
        return f[m.start():]
    return f


def rebuild(con) -> dict:
    con.execute("DELETE FROM institutions")
    con.execute("DELETE FROM institution_variants")
    affs = con.execute("SELECT * FROM affiliations").fetchall()
    parsed = []   # (rowkey, {level: name}, country)
    for a in affs:
        lv = {}
        country = None
        texts = []
        for col in ("dept", "orgname"):
            for t in (a[col] or "").split(" | "):
                if t:
                    texts.append(t)
        if a["country"]:
            country = COUNTRY_OF.get(key(a["country"])) or a["country"]
        if not texts and a["printed"]:
            texts = [a["printed"]]
        for t in texts:
            for p in pieces(t):
                p = strip_role(p)
                c = classify(p)
                if c == "country":
                    country = country or COUNTRY_OF[key(p)]
                elif c in ("organisation", "faculty", "department") and c not in lv:
                    lv[c] = p
        if "organisation" not in lv and a["orgname"]:
            lv["organisation"] = a["orgname"].split(" | ")[0]
        if not country and a["printed"]:
            for p in pieces(a["printed"]):
                if key(p) in COUNTRY_OF:
                    country = COUNTRY_OF[key(p)]
        parsed.append(((a["stem"], a["author_seq"], a["seq"]), lv, country))

    # cluster organisations by key, then merge near-identical keys (same script)
    variants = defaultdict(Counter)       # key -> printed variants
    countries = defaultdict(Counter)
    for _, lv, c in parsed:
        if "organisation" in lv:
            k = norm_key(lv["organisation"])
            if k:
                variants[k][lv["organisation"]] += 1
                if c:
                    countries[k][c] += 1
    keys = sorted(variants, key=lambda k: -sum(variants[k].values()))
    canon = {}
    for k in keys:
        tgt = None
        for c in [x for x in keys if x in canon and canon[x] == x]:
            if len(k) >= 8 and len(c) >= 8 and script(k) == script(c) and ratio(k, c) >= 0.92:
                tgt = c
                break
        canon[k] = tgt or k
    org_key = {}
    rows = {}
    for k, c in canon.items():
        ik = "org:" + c
        r = rows.setdefault(ik, dict(inst_key=ik, level="organisation", variants=Counter(), parent_key=None,
                                     countries=Counter()))
        r["variants"].update(variants[k])
        r["countries"].update(countries[k])
        org_key[k] = ik

    out = []
    for rk, lv, c in parsed:
        ok = org_key.get(norm_key(lv["organisation"])) if "organisation" in lv else None
        fk = dk = None
        if "faculty" in lv:
            fk = f"fac:{ok or 'org:?'}/{norm_key(lv['faculty'])}"
            r = rows.setdefault(fk, dict(inst_key=fk, level="faculty", variants=Counter(), parent_key=ok,
                                         countries=Counter()))
            r["variants"][lv["faculty"]] += 1
            if c:
                r["countries"][c] += 1
        if "department" in lv:
            dk = f"dep:{fk or ok or 'org:?'}/{norm_key(lv['department'])}"
            r = rows.setdefault(dk, dict(inst_key=dk, level="department", variants=Counter(), parent_key=fk or ok,
                                         countries=Counter()))
            r["variants"][lv["department"]] += 1
            if c:
                r["countries"][c] += 1
        out.append((ok, fk, dk) + rk)
    con.executemany("UPDATE affiliations SET org_key = ?, faculty_key = ?, dept_key = ? WHERE stem = ? AND "
                    "author_seq = ? AND seq = ?", out)
    ins, var = [], []
    for ik, r in rows.items():
        name = r["variants"].most_common(1)[0][0] if r["variants"] else ik
        ins.append((ik, r["level"], name, r["parent_key"],
                    r["countries"].most_common(1)[0][0] if r["countries"] else None, script(name),
                    sum(r["variants"].values()), len(r["variants"]), "masters"))
        var += [(ik, v, n) for v, n in r["variants"].items()]
    con.executemany("INSERT OR REPLACE INTO institutions VALUES (?,?,?,?,?,?,?,?,?)", ins)
    con.executemany("INSERT OR REPLACE INTO institution_variants VALUES (?,?,?)", var)
    return dict(institutions=len(ins), affiliations=len(affs))
