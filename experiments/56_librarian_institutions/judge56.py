"""Experiment 56, step 2: the librarian's judging unit — one evidence packet in, one structured verdict out.

    verdict = judge(packet)            # pure: the packet (build56) + the authority (authority56) + overrides56

A verdict says, for one printed affiliation:
- `orgs`: the top-level institution(s) it names (authority ids, in printed order; usually one);
- `unit`: the faculty / department / institute printed inside it, with its parent;
- `country` and where the country came from (`printed` | `catalogue` | `world` | none);
- `status`: `resolved` | `unit_only` (a faculty printed without its university: kept apart, never lumped) |
  `not_institution` (a place or a position only) | `unsure`;
- `confidence` (high / medium / low), `basis` (rule | catalogue | world | context | judgement), the reason;
- `trivial`: True when a deterministic rule produced it and the librarian only confirmed it.

How the rule part works (`propose`): the folded statement is scanned for every printed form of the authority; a
form inside a longer matched form is dropped («جامعة الجزائر» inside «جامعة الجزائر 3»); a unit entry (an institute
with a parent, «معهد الطفل») points to its university; a faculty is read from the reader's faculty part or a كلية /
College / Faculty piece. The librarian's own calls are in overrides56.json, keyed by the affiliation key; an override
replaces the proposal and is marked as judgement.

    python3 judge56.py view BATCH            print batch BATCH (60 packets) with the proposals, to be judged
    python3 judge56.py commit BATCH          append batch BATCH's verdicts as decisions to out/decisions56.jsonl
    python3 judge56.py unmatched             packets the rule leaves without an institution
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE.parents[0] / "46_platform_db"))
sys.path.insert(0, str(HERE))
from common46 import key, latin_key  # noqa: E402
from authority56 import AUTH, GENERIC, generic_entry  # noqa: E402

BATCH = 60
TOP_TYPES = {"university", "ministry", "other", "academy", "institute", "centre", "school"}
FAC_RE = re.compile(r"((?:ب|و|في )?(?:كلية|كليه)\s+[^،,\-–/|]+?)(?=\s*(?:[،,\-–/|]|جامعة|بجامعة|$))")
FAC_LAT = re.compile(r"((?:College|Faculty|Collage|School|Faculté)\s+(?:of|de|des|d')\s+[^,،\-–/|]+)", re.I)
COUNTRY_AR = {"مصر": "EG", "السعودية": "SA", "الأردن": "JO", "العراق": "IQ", "سوريا": "SY", "لبنان": "LB",
              "فلسطين": "PS", "الكويت": "KW", "الإمارات": "AE", "قطر": "QA", "البحرين": "BH", "عمان": "OM",
              "اليمن": "YE", "السودان": "SD", "ليبيا": "LY", "تونس": "TN", "الجزائر": "DZ", "المغرب": "MA"}


def fk(s: str | None) -> str:
    """The folded matching form of a text, Arabic or Latin, with و/ب/ل prefixes kept (forms allow them)."""
    s = s or ""
    k = latin_key(s) if not re.search("[؀-ۿ]", s) else key(s)
    # Arabic and Latin may sit in one statement: fold both
    return " ".join(latin_key(w) if not re.search("[؀-ۿ]", w) else w for w in k.split())


def _form_re(form: str) -> re.Pattern:
    f = fk(form)
    return re.compile(r"(?:(?<=\s)|^)(?:و|ب|ل|ف|بال|وال|لل|وب|في )?" + re.escape(f) + r"(?=\s|$)")


# a printed form that belongs to two bodies (جامعة الزيتونة: Tunisia's and Libya's) is chosen by the printed country
_by_form = {}
for _aid, _a in AUTH.items():
    for _f in _a["forms"]:
        _by_form.setdefault(fk(_f), []).append(_aid)
SHARED = {f: a for f, a in _by_form.items() if len(set(a)) > 1}
FORMS = sorted(((aid, f, _form_re(f)) for aid, a in AUTH.items() for f in a["forms"]),
               key=lambda x: -len(fk(x[1])))
GFORMS = sorted((("G:" + g[0], f, _form_re(f)) for g in GENERIC for f in g[4]), key=lambda x: -len(fk(x[1])))

# country words as printed (folded), longest first; a city only where it names one country
PLACES = {
    "EG": ["جمهورية مصر العربية", "مصر", "Egypt", "القاهرة", "Cairo", "الإسكندرية", "الجيزة"],
    "SA": ["المملكة العربية السعودية", "السعودية", "Saudi Arabia", "KSA", "الرياض", "Riyadh", "جدة", "Jeddah",
           "مكة المكرمة", "المدينة المنورة", "الظهران", "خميس مشيط"],
    "JO": ["المملكة الأردنية الهاشمية", "الأردن", "Jordan"],
    "IQ": ["جمهورية العراق", "الجمهورية العراقية", "العراق", "Iraq", "بغداد", "Baghdad", "البصرة", "كوردستان العراق",
           "Kurdistan Region", "اربيل", "Erbil"],
    "SY": ["الجمهورية العربية السورية", "سورية", "سوريا", "Syria", "SYRIE", "دمشق", "حلب"],
    "LB": ["الجمهورية اللبنانية", "لبنان", "Lebanon", "بيروت", "Beirut"],
    "PS": ["دولة فلسطين", "فلسطين", "Palestine", "GAZA", "غزة"],
    "KW": ["دولة الكويت", "الكويت", "Kuwait", "State of Kuwait"],
    "AE": ["دولة الإمارات العربية المتحدة", "الإمارات العربية المتحدة", "الإمارات", "United Arab Emirates", "UAE"],
    "QA": ["دولة قطر", "قطر", "Qatar"],
    "BH": ["مملكة البحرين", "البحرين", "Bahrain", "Kingdom of Bahrain", "Kingdome of Bahrain"],
    "OM": ["سلطنة عمان", "Oman", "Sultanate of Oman", "مسقط", "Muscat"],
    "YE": ["الجمهورية اليمنية", "اليمن", "Yemen", "Republic of Yemen", "صنعاء", "حضرموت"],
    "SD": ["جمهورية السودان", "السودان", "Sudan", "الخرطوم"],
    "LY": ["ليبيا", "Libya", "La Libye", "Libye"],
    "TN": ["الجمهورية التونسية", "تونس", "Tunisia", "Tunisie"],
    "DZ": ["الجمهورية الجزائرية الديمقراطية الشعبية", "الجزائر", "Algeria", "Algérie"],
    "MA": ["المملكة المغربية", "المغرب", "Morocco", "Maroc", "الرباط", "Rabat", "فاس", "Fès", "Fes", "مراكش", "وجدة",
           "سطات", "أكادير", "تطوان", "طنجة", "خريبكة", "العرائش", "القنيطرة", "مكناس", "تزنيت", "Casablanca", "الدار البيضاء"],
    "MY": ["ماليزيا", "Malaysia"], "PK": ["باكستان", "Pakistan", "لاهور", "Lahore"], "IN": ["الهند", "India"],
    "TR": ["تركيا", "Turquie", "Turkey"], "CA": ["كندا", "Canada"], "FR": ["فرنسا", "France"],
}
PLACE_RE = sorted(((cc, _form_re(f)) for cc, fs in PLACES.items() for f in fs), key=lambda x: -len(x[1].pattern))


def printed_country(p: dict, include_same=True) -> str | None:
    """A country printed in the statement (its country part, a country word, a one-country city), else in the same
    author's other statements in the article."""
    if p["parts"].get("country_code"):
        return p["parts"]["country_code"]
    texts = [p["printed"]] + ([x["printed"] for x in p["same_article"]] if include_same else [])
    for t in texts:
        ft = fk(t)
        for cc, rx in PLACE_RE:
            if rx.search(ft):
                return cc
    return None


def _catalogue_basis():
    """A catalogue (MARC 502 $c + $g) country for each entry's Arabic name: the cataloguers' decision."""
    import sqlite3
    db = OUT / "marc_inst56.db"
    if not db.exists():
        return {}
    ar = {"الاردن": "JO", "السودان": "SD", "السعودية": "SA", "فلسطين": "PS", "مصر": "EG", "الجزائر": "DZ",
          "العراق": "IQ", "عمان": "OM", "سوريا": "SY", "البحرين": "BH", "تونس": "TN", "ليبيا": "LY", "اليمن": "YE",
          "ماليزيا": "MY", "لبنان": "LB", "الكويت": "KW", "الامارات": "AE", "المغرب": "MA", "بريطانيا": "GB",
          "الولايات المتحدة الأمريكية": "US", "تركيا": "TR", "قطر": "QA", "فرنسا": "FR"}
    c = sqlite3.connect(f"file:{db}?mode=ro", uri=True)
    cnt = {}
    for u, cc, _f, n in c.execute("SELECT univ, country, faculty, n FROM thesis_unis WHERE univ IS NOT NULL"):
        k = fk(u)
        d = cnt.setdefault(k, Counter())
        d[ar.get(cc, cc)] += n
    return cnt


CATALOGUE = _catalogue_basis()
for _a in AUTH.values():
    _hits = Counter()
    for _f in [_a["name_ar"]] + [f for f in _a["forms"] if re.search("[؀-ۿ]", f)]:
        _hits.update(CATALOGUE.get(fk(_f), Counter()))
    if _hits:
        _cc, _n = _hits.most_common(1)[0]
        _a["catalogue"] = dict(country=_cc, n=_n, of=sum(_hits.values()))
        if _a["country"] == _cc:
            _a["country_basis"] = "catalogue"
        elif _a["country"]:
            _a["country_conflict"] = _cc


def load_overrides() -> dict:
    p = HERE / "overrides56.json"
    return json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}


def load_packets() -> list:
    return [json.loads(l) for l in open(OUT / "packets56.jsonl", encoding="utf-8")]


def matches(text: str) -> list:
    """Authority entries printed in the text, longest form first, a form inside a longer one dropped."""
    t = fk(text)
    spans, out = [], []
    for aid, form, rx in FORMS:
        for m in rx.finditer(t):
            s, e = m.span()
            if any(s >= a and e <= b for a, b, _ in spans):
                continue
            spans.append((s, e, aid))
    for s, e, aid in sorted(spans):
        if aid not in [x[0] for x in out]:
            out.append((aid, s))
    return out


def shared_choice(ms: list, t: str, pc: str | None) -> tuple:
    """Replace a match on a shared form by the body of the printed country; report the ones left open."""
    out, open_ = [], []
    for aid, pos in ms:
        f = next((f for f in SHARED if t[pos:].lstrip("وبلف ").startswith(f) or t[pos:].startswith(f)), None)
        if not f or aid not in SHARED.get(f, []):
            out.append((aid, pos))
            continue
        pick = [a for a in SHARED[f] if AUTH[a]["country"] == pc]
        if pick:
            out.append((pick[0], pos))
        else:
            open_.append(f)
    return out, open_


def faculty_of(p: dict) -> str | None:
    f = (p["parts"].get("faculty") or "").split(" | ")[0].strip()
    if f and re.search(r"كلي|college|faculty|faculté|school", f, re.I):
        return f
    m = FAC_RE.search(p["printed"]) or FAC_LAT.search(p["printed"])
    return m.group(1).strip() if m else None


def canon(aid: str) -> str:
    """Follow the librarian's same-as links (one body printed under two names)."""
    seen = set()
    while AUTH.get(aid, {}).get("same_as") and aid not in seen:
        seen.add(aid)
        aid = AUTH[aid]["same_as"]
    return aid


def top_of(aid: str) -> str:
    a = AUTH[canon(aid)]
    seen = set()
    while a["parent"] and a["type"] != "university" and a["id"] not in seen:
        seen.add(a["id"])
        if a["parent"] not in AUTH:
            break
        a = AUTH[a["parent"]]
    return a["id"]


def propose(p: dict) -> dict:
    """The rule's verdict for one packet (no librarian judgement)."""
    ms = matches(p["printed"])
    gen = []
    t = fk(p["printed"])
    ms, shared_open = shared_choice(ms, t, printed_country(p))
    covered = [(s, s + len(fk(AUTH[a]["name_ar"]))) for a, s in ms]
    for gid, form, rx in GFORMS:
        for m in rx.finditer(t):
            # a generic name inside a specific one («وزارة التربية» of «وزارة التربية دولة الكويت») is not another body
            spec = [x for x in matches(t[m.start():]) if x[1] == 0]
            if gid not in [g for g, _ in gen] and not spec:
                gen.append((gid, m.start()))
    pc = printed_country(p)
    for gid, pos in gen[:2]:
        if pc:
            ms.append((generic_entry(gid[2:], pc)["id"], pos))
    ms.sort(key=lambda x: x[1])
    orgs, units = [], []
    for aid, _ in ms:
        t = top_of(aid)
        if t != canon(aid):
            units.append(aid)
        if t not in orgs:
            orgs.append(t)
    fac = faculty_of(p)
    v = dict(key=p["key"], orgs=orgs, units=units, faculty=fac, basis="rule", confidence="high", trivial=True,
             reason=None)
    own_cc = printed_country(p, include_same=False)
    if shared_open and not orgs:
        v.update(status="unsure", confidence="low", reason=f"«{shared_open[0]}» names two bodies and no country is printed")
    elif orgs:
        v["status"] = "resolved"
        if len(orgs) > 1:
            v["reason"] = "several institutions printed in one statement"
        elif own_cc and AUTH[orgs[0]].get("country") and own_cc != AUTH[orgs[0]]["country"]:
            v["confidence"] = "low"
            v["reason"] = f"printed country {own_cc} differs from the institution's {AUTH[orgs[0]]['country']}: to check"
    elif gen:
        v["status"] = "unsure"
        v["confidence"] = "low"
        v["reason"] = f"a generic name ({gen[0][0][2:]}) with no country printed"
    elif fac:
        v["status"] = "unit_only"
        v["reason"] = "a faculty printed without its university"
    elif p["kind"] in ("place-only", "position-only"):
        v["status"] = "not_institution"
        v["reason"] = f"{p['kind']}: no institution printed"
    else:
        v["status"] = "unsure"
        v["confidence"] = "low"
        v["reason"] = "no authority form printed"
    return v


def country_of(v: dict, p: dict) -> tuple:
    for o in list(v["orgs"]) + list(v.get("units") or []):
        a = AUTH.get(o)
        if a and a.get("country"):
            return a["country"], a.get("country_basis", "world")
    if p["parts"].get("country_code"):
        return p["parts"]["country_code"], "printed"
    return None, None


def judge(p: dict, overrides: dict | None = None) -> dict:
    """One packet in, one verdict out: the rule's proposal, replaced by the librarian's override where there is one."""
    overrides = load_overrides() if overrides is None else overrides
    v = propose(p)
    o = overrides.get(p["key"])
    if o:
        changed = any(o.get(k) is not None and o.get(k) != v.get(k) for k in ("orgs", "status", "faculty"))
        v.update({k: x for k, x in o.items() if not k.startswith("_")})
        v["trivial"] = not changed and o.get("basis", "rule") == "rule"
        v.setdefault("basis", "judgement")
        if changed and v.get("basis") == "rule":
            v["basis"] = "judgement"
    cc, cb = country_of(v, p)
    if v.get("country"):
        cb = v.get("country_basis") or "judgement"
        cc = v["country"]
    v["country"], v["country_basis"] = cc, cb
    return v


def show(p: dict, v: dict) -> str:
    m = p["machine"].get("org")
    mo = f"{m['names'][0] if m and m['names'] else None} [{m['inst_id']}|{m['country']}]" if m else "-"
    mf = p["machine"].get("faculty")
    mfs = f" fac={mf['key'].split('/')[0][7:] if mf and mf.get('key') else ''}" if mf else ""
    lines = [f"{p['key']}  [{p['journal_id']} {p['year']}] {p['author']['name']}",
             f"  P: {p['printed']}",
             f"  machine: {mo}{mfs}",
             f"  rule:    {v['status']} {v['orgs']} unit={v['units']} fac={v['faculty']} cc={v['country']}({v['country_basis']}) {v['confidence']}"
             + (f" — {v['reason']}" if v.get("reason") else "")]
    if p["same_article"]:
        lines.append("  same: " + " || ".join(x["printed"] for x in p["same_article"])[:400])
    if p["other_articles"]:
        lines.append("  other: " + " || ".join(f"{x['stem']}: {x['printed']}" for x in p["other_articles"][:3])[:400])
    if p["parts"].get("city") or p["parts"].get("country"):
        lines.append(f"  place: {p['parts'].get('city')} / {p['parts'].get('country')}")
    return "\n".join(lines)


def main(argv):
    cmd = argv[0] if argv else "view"
    P = load_packets()
    ov = load_overrides()
    if cmd == "view":
        b = int(argv[1])
        for i, p in enumerate(P[b * BATCH:(b + 1) * BATCH]):
            v = judge(p, ov)
            m = p["machine"].get("org")
            agree = (v["status"] == "resolved" and len(v["orgs"]) == 1 and m and m["names"] and
                     any(v["orgs"][0] == x for x, _ in matches(" ".join(m["names"][:3]))) and not v["units"])
            if agree:
                print(f"= {b * BATCH + i:03d} {p['key']} | {p['printed'][:110]} -> {v['orgs'][0]} fac={v['faculty']} cc={v['country']}")
            else:
                print(f"# {b * BATCH + i:03d} " + show(p, v))
    elif cmd == "unmatched":
        n = 0
        for p in P:
            v = judge(p, ov)
            if v["status"] in ("unsure",) or (v["status"] == "unit_only"):
                n += 1
                print(show(p, v))
        print(n, "packets")
    elif cmd == "stats":
        c = Counter((judge(p, ov)["status"]) for p in P)
        print(c, len(P), "batches", (len(P) + BATCH - 1) // BATCH)
    elif cmd == "commit":
        import decisions56
        b = int(argv[1])
        print(decisions56.commit_batch(b, P[b * BATCH:(b + 1) * BATCH], ov))


if __name__ == "__main__":
    main(sys.argv[1:])
