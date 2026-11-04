"""Experiment 74 (from experiment 72's inst72.py), institutions of one journal (LIB74_J): its affiliations, rules
first, the questions the rules leave, and exp 72's candidate finder.

    python inst74.py packets     experiment 56's packet builder on the release -> OUT/inst/packets56.jsonl;
                                 the journal's -> OUT/inst/aff<J>.jsonl
    python inst74.py build       rules (R1 printed form, R6 no body printed) and the questions left to the models
                                 -> OUT/inst/rule_decisions.jsonl, OUT/questions/inst.jsonl, OUT/inst/build_summary.json

The authority ("the seen list") is experiment 56's (authority56.AUTH) + experiment 64's four new bodies + every
reviewed addition so far (exp 72's authority72.json and each earlier journal's authority74.json, common74.reviewed_
bodies), with the Desk's own row for every body it has defined (define_institution decisions).

Changed against exp 72 (its lesson 5): "are these two rows one body" is asked only for two unit rows that carry the
two statements of one printed line (affiliation_mentions.twin_of_aff_pk: a statement and its twin in the other
script name different machine rows at the same level), not for every Arabic x Latin pair under a parent (exp 72:
68 questions, 51 "different", 1 wrong merge).
"""
from __future__ import annotations

import json
import os
import re
import sys
import unicodedata
from collections import Counter, defaultdict

from common74 import DESK, E56, E64, E71, JOURNAL, OUT, RELEASE, TAG, add_paths, jl, js, reviewed_bodies, ro, wjl, wjs

add_paths(E56, E56.parent / "46_platform_db", DESK, E64)
INST = OUT / "inst"
QDIR = OUT / "questions"

FORMER = re.compile(r"سابق|الأسبق|الاسبق|السابق|متقاعد|\bformer|\bformerly|\bex-|\bpreviously|\bretired", re.I)
DEGREE = re.compile(r"دكتوراه|دكتوراة|ماجستير|ماجيستير|بكالوريوس|ليسانس|دبلوم|حاصل|حاصلة|خريج|طالب|طالبة|"
                    r"ph\.?\s?d|\bmaster|\bbachelor|graduate|student|candidate", re.I)
ORG_HEAD = re.compile(r"(جامع|وزار|مركز|معهد|مجلس|جمعي|هيئ|اكاديمي|أكاديمي|مؤسس|منظم|اتحاد|مجمع|مستشف|شرك|بنك|"
                      r"صندوق|نقاب|رابط|دائر|مديري|مكتب|برنامج|مدرسة|مدرسه|ثانوية|ثانويه|مشروع|"
                      r"univ|minist|cent|instit|council|academ|societ|associat|foundation|organi|hospital|compan|"
                      r"agency|office|program|school|ecole|école|lab)", re.I)


# ------------------------------------------------------------------ the authority and the Desk's rows for it
def desk_defined() -> dict:
    """authority id -> the inst id the Desk's define_institution decision names (all actors)."""
    from desk import db
    with db.connect("desk") as pg:
        rows = pg.execute("SELECT payload->>'authority' a, subject_keys[1] k FROM decisions WHERE op = "
                          "'define_institution' AND status = 'accepted'").fetchall()
    return {r["a"]: r["k"].split(":", 1)[1] for r in rows}


def load_authority():
    """AUTH with experiment 64's new bodies and this experiment's reviewed additions (forms included)."""
    import authority56 as A56
    from plan64 import NEW_BODIES
    for L, b in NEW_BODIES.items():
        if L not in A56.AUTH:
            forms = [x for x in (b.get("name_ar"), b.get("name_en")) if x]
            A56.AUTH[L] = dict(id=L, type=b["type"], country=b["country"], name_ar=b["name_ar"], name_en=b["name_en"],
                               forms=forms, parent=None, note=b["why"], ambiguous=False, same_as=None, new64=True)
    for e in reviewed_bodies().values():
        if e["id"] not in A56.AUTH:
            A56.AUTH[e["id"]] = dict(id=e["id"], type=e["type"], country=e.get("country"), name_ar=e.get("name_ar"),
                                     name_en=e.get("name_en"), forms=list(e.get("forms") or []),
                                     parent=e.get("parent"), note=e.get("why"), ambiguous=False, same_as=None,
                                     new72=True)
    return A56.AUTH


def desk_seen() -> set:
    """Every subject key of a standing Desk decision (any actor; not reverts or retirements) and of an open librarian
    task (a question an earlier pass held for a person): the seen list for statements (aff:…) and rows (inst:…).
    A statement or row settled or already waiting for a person is not asked again."""
    from desk import db
    with db.connect("desk") as pg:
        rows = pg.execute("SELECT op, subject_keys FROM decisions WHERE status IN ('proposed', 'accepted') AND op IN "
                          "('link_affiliation', 'not_an_institution', 'same_institution', 'set_inst_parent')").fetchall()
        held = pg.execute("SELECT subject_keys, source FROM tasks WHERE state IN ('open', 'claimed') AND kind = "
                          "'librarian_question' AND source->>'detector' LIKE 'librarian%%'").fetchall()
    out = set()
    for t in held:                          # a question an earlier pass held for a person is not asked again
        ks = t["subject_keys"] or []
        if len(ks) == 1 and ks[0].startswith("aff:"):
            out.add(ks[0])
        elif len(ks) == 1 and ks[0].startswith("inst:"):
            out.add("parent|" + ks[0])
        elif len(ks) == 2 and all(k.startswith("inst:") for k in ks):
            out.add("same|" + "|".join(sorted(ks)))
    for r in rows:
        if r["op"] in ("link_affiliation", "not_an_institution"):
            out.add(r["subject_keys"][0])
        elif r["op"] == "set_inst_parent":
            out.add("parent|" + r["subject_keys"][0])
        else:
            out.add("same|" + "|".join(sorted(r["subject_keys"])))
    return out


# ------------------------------------------------------------------ 1. packets
def packets():
    import build56
    INST.mkdir(parents=True, exist_ok=True)
    m = INST / "marc_inst56.db"
    if not m.exists():
        os.symlink(E56 / "out" / "marc_inst56.db", m)
    build56.OUT = INST
    build56.main(["--db", str(RELEASE)])
    P = jl(INST / "packets56.jsonl")
    con = ro()
    twin = {r[0]: r[1] for r in con.execute("SELECT aff_pk, twin_of_aff_pk FROM affiliation_mentions")}
    mine = []
    for p in P:
        if p["stem"].startswith(JOURNAL + "-"):
            p["twin_of"] = twin.get(p["aff_pk"])
            mine.append(p)
    wjl(INST / f"aff{JOURNAL}.jsonl", mine)
    print(dict(all=len(P), journal=JOURNAL, mine=len(mine), twins=sum(1 for p in mine if p["twin_of"])))


# ------------------------------------------------------------------ 2. the candidate finder
AR_MAP = str.maketrans({"أ": "ا", "إ": "ا", "آ": "ا", "ٱ": "ا", "ة": "ه", "ى": "ي", "ئ": "ي", "ؤ": "و", "ـ": ""})


def fold(s: str) -> str:
    s = unicodedata.normalize("NFKD", s or "")
    s = "".join(c for c in s if not unicodedata.combining(c)).lower().translate(AR_MAP)
    s = re.sub(r"[^\w\s]", " ", s)
    s = re.sub(r"\b(ال|بال|وال|لل)(?=\w{3})", "", s)
    return " ".join(s.split())


def grams(s: str) -> set:
    s = f" {fold(s)} "
    return {s[i:i + 3] for i in range(len(s) - 2)}


STOP = {"جامعه", "university", "of", "the", "de", "la", "le", "des", "du", "d", "universite", "و", "كليه", "college",
        "faculty", "في", "ب", "and", "قسم", "department", "استاذ", "مدرس", "مساعد", "professor", "lecturer", "مصر",
        "المملكه", "العربيه", "جمهوريه", "دوله", "assistant", "associate", "عضو", "هيئه", "تدريس", "member",
        "باحث", "باحثه", "researcher", "institute", "معهد", "مركز", "center", "centre", "وزاره", "ministry", "تربيه",
        "education", "علوم", "sciences", "science", "عام", "عامه", "national", "قومي", "عالي", "عليا", "دراسات",
        "studies", "research", "بحوث", "high", "higher", "مدير", "director", "رئيس", "head", "خبير", "expert"}


# (1b) a city printed with a faculty: experiment 56's R4 table (rules56.CITY_UNI: the city's public university), and
# faculties whose name points to the bodies that keep such faculties (candidates only: the model still decides)
CITY_UNI = {"فاس": ["L-ma-usmba"], "fes": ["L-ma-usmba"], "ظهر المهراز": ["L-ma-usmba"], "الرباط": ["L-ma-um5"],
            "rabat": ["L-ma-um5"], "تطوان": ["L-ma-uae"], "tetouan": ["L-ma-uae"], "اكادير": ["L-ma-uiz"],
            "agadir": ["L-ma-uiz"], "الجديده": ["L-ma-ucd"], "الدار البيضاء": ["L-ma-uh2"], "casablanca": ["L-ma-uh2"],
            "mohammedia": ["L-ma-uh2"], "المحمديه": ["L-ma-uh2"], "عين الشق": ["L-ma-uh2"],
            "مراكش": ["L-ma-uca", "L-ma-qaraouiyine"], "تونس": ["L-tn-tunis"]}
FACULTY_HINT = [(re.compile(r"لغه عربيه|اصول دين|شريعه|دعوه|دراسات اسلاميه|قران"),
                 ["L-eg-azhar", "L-ma-qaraouiyine", "L-sa-imamu", "L-sa-uqu", "L-sa-iu"]),
                (re.compile(r"دار علوم"), ["L-eg-cairo", "L-eg-minia", "L-eg-fayoum"])]


def name_tokens(s: str) -> set:
    return {w for w in fold(s).split() if len(w) > 2 and w not in STOP and not w.isdigit()}


class Finder:
    """Authority candidates for one question. Shown to the model: id, names, type, country, parent's name (never
    printed forms, articles or counts). `old` = experiment 71's retriever (trigrams over names and repeated printed
    forms, top 8); `new` adds (1) a faculty or unit with a printed city / country -> that place's universities,
    (2) the journal's publisher, (3) entries sharing a distinctive name word, and (4) the machine's own rows."""

    def __init__(self, AUTH, authority_json=None):
        self.A = AUTH
        pf = {}
        if authority_json:
            for e in authority_json["institutions"]:
                pf[e["id"]] = [f["form"] for f in e.get("printed_forms") or [] if f.get("n", 0) >= 2]
        self.G, self.T = {}, {}
        for i, e in AUTH.items():
            forms = [e.get("name_ar") or "", e.get("name_en") or ""] + pf.get(i, []) + list(e.get("forms") or [])
            self.G[i] = [grams(f) for f in forms if f]
            self.T[i] = set().union(*[name_tokens(f) for f in forms if f]) if forms else set()
        self.tok_idx = defaultdict(set)
        for i, ts in self.T.items():
            for w in ts:
                self.tok_idx[w].add(i)

    def card(self, i):
        e = self.A[i]
        par = self.A.get(e.get("parent") or "")
        return dict(id=i, name_ar=e.get("name_ar"), name_en=e.get("name_en"), type=e.get("type"),
                    country=e.get("country"), parent=(par or {}).get("name_ar") if par else None)

    def trigram(self, texts, k=8, types=None):
        q = [grams(t) for t in texts if t]
        sc = []
        for i, gs in self.G.items():
            if types and self.A[i].get("type") not in types:
                continue
            best = max((len(a & b) / max(1, min(len(a), len(b))) * (len(a & b) / max(1, len(a | b))) ** 0.5
                        for a in q for b in gs), default=0)
            sc.append((best, i))
        sc.sort(reverse=True)
        return [i for s, i in sc[:k] if s > 0.05]

    def old(self, texts, k=8, types=None):
        return self.trigram(texts, k, types)

    def new(self, texts, country=None, city=None, publishers=(), k=8, types=None, unit_only=False):
        out = list(self.trigram(texts, k, types))
        # (1) a place printed: that place's universities (a city word in the name or a form first)
        if country or city:
            unis = [i for i, e in self.A.items() if e.get("type") == "university" and not e.get("same_as")
                    and (not country or e.get("country") == country)]
            if city:
                cw = name_tokens(city) or {fold(city)}
                hit = [i for i in unis if cw & self.T[i]]
                out += hit[:6]
            if country and (unit_only or not city):
                rank = self.trigram(texts, 40, {"university"})
                out += [i for i in rank if i in unis][:6]
        if city:
            fc = fold(city)
            for c, us in CITY_UNI.items():
                if fold(c) in fc or fc in fold(c):
                    out += us
        ft = " ".join(fold(t) for t in texts if t)
        for rx, us in FACULTY_HINT:
            if rx.search(ft):
                out += us
        # (2) the journal's publisher, as an authority entry
        for name in publishers:
            if name:
                out += self.trigram([name], 2)
        # (3) a distinctive name word shared with an entry
        toks = set().union(*[name_tokens(t) for t in texts if t]) if texts else set()
        cnt = Counter(i for w in toks for i in self.tok_idx.get(w, ()) if len(self.tok_idx[w]) <= 12)
        out += [i for i, _ in cnt.most_common(6)]
        seen, res = set(), []
        for i in out:
            if i not in seen and i in self.A:
                seen.add(i)
                res.append(i)
        return res[:18]


def finder_eval():
    """Recall of the old and the new finder on experiment 71's 160 institution questions that name a body."""
    AUTH = load_authority()
    a56 = js(E56 / "out" / "authority56.json")
    F = Finder(AUTH, a56)
    import judge56
    G = {g["id"]: g for g in jl(E71 / "out" / "gold71.jsonl")}
    P = {p["id"]: p for p in jl(E71 / "out" / "packets71.jsonl")}
    rows = []
    for gid, g in G.items():
        if g["domain"] != "institutions" or not g.get("ids"):
            continue
        ev = P[gid]["evidence"]
        if "printed" in ev:
            texts = [ev.get("printed"), (ev.get("parts") or {}).get("org"), (ev.get("parts") or {}).get("faculty")]
            parts = ev.get("parts") or {}
            pkt = dict(printed=ev["printed"], parts=dict(country_code=parts.get("country_code")),
                       same_article=[dict(printed=x) if isinstance(x, str) else x for x in ev.get("same_article") or []])
            cc = judge56.printed_country(pkt)
            city = parts.get("city")
            unit = bool(parts.get("faculty")) and not parts.get("org")
        else:
            texts = [n for r in ev.get("rows") or [] for n in r["names"]] + \
                    [af.get("printed") for af in (ev.get("affiliations") or [])[:6]]
            af = (ev.get("affiliations") or [{}])[0]
            parts = af.get("parts") or {}
            pkt = dict(printed=af.get("printed") or "", parts=dict(country_code=parts.get("country_code")),
                       same_article=[])
            cc = judge56.printed_country(pkt)
            city = parts.get("city")
            unit = True
        pubs = [p[1] for j in (ev.get("journal_publishers") or {}).values() for p in j.get("publishers") or []]
        types = None
        if P[gid]["question"].startswith("Is this machine row a unit"):
            types = {"university", "ministry", "academy", "other", "centre", "institute", "school"}
        old = set(F.old(texts, 8, types))
        new = set(F.new(texts, cc, city, pubs, 8, types, unit_only=unit))
        rows.append(dict(id=gid, kind=g["kind"], gold=g["ids"], old_hit=all(i in old for i in g["ids"]),
                         new_hit=all(i in new for i in g["ids"]), n_old=len(old), n_new=len(new),
                         injected71=g.get("candidates_injected")))
    S = dict(questions=len(rows), old_recall=sum(r["old_hit"] for r in rows), new_recall=sum(r["new_hit"] for r in rows),
             exp71_injected=sum(1 for r in rows if r["injected71"]),
             new_found_of_injected=sum(1 for r in rows if r["injected71"] and r["new_hit"]),
             mean_candidates_old=round(sum(r["n_old"] for r in rows) / len(rows), 1),
             mean_candidates_new=round(sum(r["n_new"] for r in rows) / len(rows), 1),
             still_missed=[r for r in rows if not r["new_hit"]])
    wjs(INST / "finder_eval.json", S)
    print(json.dumps({k: v for k, v in S.items() if k != "still_missed"}, indent=1),
          "still missed:", [(r["id"], r["gold"]) for r in S["still_missed"]])


# ------------------------------------------------------------------ 3. rules and questions
Q_AFF = ("Which institution(s) does this printed affiliation name? status: resolved = it names one or more bodies "
         "(give their ids from the candidates, or new:<name> for a body not among them, and the country) | unit_only = "
         "a faculty / department printed without its university and nothing on the page says which | not_institution "
         "= no body is named (a position, a degree, a place, a court, a reprint source) | unsure.")
Q_SAME = ("These machine rows were proposed as spellings of one body. Are they one body (same) or not (different)? "
          "If same, give the authority id if one of the candidates is that body, else new:<name>.")
Q_COUNTRY = "In which country is this institution (machine row)? Answer an ISO 3166 alpha-2 code, or unsure."
Q_PARENT = ("Is this machine row a unit (faculty, institute, centre, hospital) of a larger body? If so give the "
            "parent's id from the candidates (or new:<name>); answer none if it is a top-level body.")


def residue_heads(printed: str, judge56) -> list[str]:
    """Organisation head words left in a statement once the matched authority forms are cut out (a second body the
    authority does not hold)."""
    t = judge56.fk(printed)
    spans = []
    for aid, form, rx in judge56.FORMS:
        for m in rx.finditer(t):
            spans.append(m.span())
    keep = "".join(ch if not any(a <= i < b for a, b in spans) else " " for i, ch in enumerate(t))
    return ORG_HEAD.findall(keep)


def machine_rows(p, con_names, inst):
    out = []
    for lvl, m in (p.get("machine") or {}).items():
        out.append(f"{lvl}: {m.get('names', [])[:3]} kind={m.get('kind')} country={m.get('country')} id={m['inst_id']} "
                   f"parent={m.get('parent_id')}")
    return out


def aff_view(p):
    return dict(key=p["key"], printed=p["printed"], parts={k: v for k, v in p["parts"].items() if v},
                journal=f"{p['journal_id']} {p['journal']}", year=p["year"], stem=p["stem"],
                author=p["author"].get("name") or p["author"].get("printed"), email=p["author"].get("email"),
                same_article=[x["printed"] for x in p["same_article"]][:4],
                other_articles=[f"{x['stem']}: {x['printed']}" for x in p["other_articles"]][:4],
                machine=machine_rows(p, None, None),
                catalogue=[f"«{n}»: theses{[t['univ'] for t in h['thesis']][:2]} corp{[c['heading'] for c in h['corp']][:2]}"
                           for n, h in (p.get("catalogue") or {}).items()][:3])


def publishers_of(con, jid):
    out = {}
    for r in con.execute("""SELECT jp.journal_id, p.publisher_id, p.name, p.name_en, p.country_code, j.country_code jc
                            FROM journal_publishers jp JOIN publishers p USING (publisher_id)
                            JOIN journals j ON j.journal_id = jp.journal_id WHERE jp.journal_id = ?""", (jid,)):
        out.setdefault(r["journal_id"], dict(country=r["jc"], publishers=[]))["publishers"].append(
            [r["publisher_id"], r["name"], r["name_en"], r["country_code"], None])
    return out


_TW = {}


def _twins() -> dict:
    """aff_pk -> twin_of_aff_pk on the release."""
    if not _TW:
        for r in ro().execute("SELECT aff_pk, twin_of_aff_pk FROM affiliation_mentions WHERE twin_of_aff_pk IS NOT NULL"):
            _TW[r[0]] = r[1]
    return _TW


def build():
    AUTH = load_authority()
    import judge56
    F = Finder(AUTH, js(E56 / "out" / "authority56.json"))
    defined = desk_defined()
    con = ro()
    P = jl(INST / f"aff{JOURNAL}.jsonl")
    pubs = publishers_of(con, "J" + JOURNAL)
    pubnames = [x[1] for v in pubs.values() for x in v["publishers"]]
    rules, qs = [], []
    stat = Counter()
    # once the models have been asked, the questions are frozen: a rebuild (with the reviewed authority's forms) only
    # re-runs the rules on the statements the rules settled, so R1 can correct itself (a longer reviewed form wins)
    frozen = {q["id"]: q for q in jl(QDIR / "inst.jsonl")} if os.environ.get("LIB74_FREEZE") == "1" else {}
    seen = desk_seen()
    for n, p in enumerate(P):
        if p["key"] in seen:
            stat["seen: a standing Desk decision on the statement"] += 1
            continue
        if p.get("twin_of"):
            stat["twin line (takes its main line's bodies)"] += 1
            continue
        if f"I{TAG}-A{n:03d}" in frozen:
            qs.append(frozen[f"I{TAG}-A{n:03d}"])
            stat["frozen question"] += 1
            continue
        v = judge56.propose(p)
        printed = p["printed"]
        fm, dg = bool(FORMER.search(printed)), bool(DEGREE.search(printed))
        res = residue_heads(printed, judge56) if v["status"] == "resolved" else []
        rule = None
        if v["status"] == "resolved" and v["confidence"] == "high" and not v.get("reason") and not fm and not dg \
                and not res and len(v["orgs"]) == 1:
            rule = "R1"
        elif v["status"] == "not_institution" and not ORG_HEAD.search(printed) and not fm and not dg:
            rule = "R6"
        if rule:
            cc = None
            if rule == "R1":
                a = AUTH[v["orgs"][0]]
                cc = a.get("country")
            rules.append(dict(id=f"I{TAG}-A{n:03d}", level="affiliation", key=p["key"], printed=printed, rule=rule,
                              status=v["status"], orgs=v["orgs"], units=v["units"], faculty=v["faculty"], country=cc,
                              confidence="high", reason=("R1 printed form: " + ", ".join(AUTH[o]["name_ar"] or o for o in
                                                                                         v["orgs"])) if rule == "R1"
                              else f"R6 no body printed ({p['kind']})", defined={o: defined.get(o) for o in v["orgs"]}))
            stat[f"rule {rule}"] += 1
            continue
        why = ("former" if fm else "") + (" degree" if dg else "") + (f" residue {res[:2]}" if res else "") + \
              f" rule:{v['status']}/{v['confidence']}" + (f" ({v['reason']})" if v.get("reason") else "")
        stat["to the model: " + ("former/degree" if fm or dg else "a second body" if res else v["status"])] += 1
        texts = [printed, p["parts"].get("org"), p["parts"].get("faculty")]
        cc = judge56.printed_country(p)
        unit = bool(p["parts"].get("faculty")) and not v["orgs"]
        cands = F.new(texts, cc, p["parts"].get("city"), pubnames, 8, unit_only=unit)
        for o in v["orgs"]:                 # the rule's own reading is always among the candidates
            if o not in cands:
                cands.append(o)
        ev = aff_view(p)
        ev["aff_key"] = ev.pop("key")
        ev["journal_publishers"] = pubs
        ev["authority_candidates"] = [F.card(i) for i in sorted(set(cands))]
        qs.append(dict(id=f"I{TAG}-A{n:03d}", domain="institutions", kind="inst:affiliation", question=Q_AFF,
                       options=["resolved", "unit_only", "not_institution", "unsure"], evidence=ev,
                       meta=dict(key=p["key"], rule_proposal=dict(status=v["status"], orgs=v["orgs"],
                                                                  confidence=v["confidence"], reason=v.get("reason")),
                                 why=why.strip(), machine_org=(p["machine"].get("org") or {}).get("inst_id"))))
    # ---------------------------------------------------------------- institution-level questions
    touched = set()
    affs_of = defaultdict(list)
    for p in P:
        for lvl, m in (p.get("machine") or {}).items():
            touched.add(m["inst_id"])
            affs_of[m["inst_id"]].append(p)
    allp = {p["key"]: p for p in jl(INST / "packets56.jsonl")}
    for p in allp.values():                 # every row's statements (this journal's first), the twins' other rows included
        if p.get("stem", "").startswith(JOURNAL + "-"):
            continue
        for lvl, m in (p.get("machine") or {}).items():
            affs_of[m["inst_id"]].append(p)
    names = defaultdict(list)
    for r in con.execute("SELECT inst_id, name, n_seen FROM institution_names ORDER BY n_seen DESC"):
        names[r[0]].append(r[1])
    rows = {r["inst_id"]: dict(r) for r in con.execute("SELECT * FROM institutions")}
    nlinks = Counter(r[0] for r in con.execute("SELECT inst_id FROM affiliation_links"))

    def row_view(i):
        r = rows[i]
        return dict(id=i, kind=r["kind"], country=r["country_code"], names=names[i][:4], parent=r["parent_id"],
                    parent_names=names.get(r["parent_id"], [])[:2] if r["parent_id"] else None, n_aff=nlinks[i])

    def affs(i, k=6):
        return [aff_view(p) for p in affs_of.get(i, [])[:k]]
    # (a) twins of one printed line (exp 72's lesson 5): a statement and its twin (the same line in the other script,
    # affiliation_mentions.twin_of_aff_pk) whose machine rows at one unit level differ; one of the rows is this
    # journal's
    by_pk = {p["aff_pk"]: p for p in allp.values()}
    pairs = {}
    for p in allp.values():
        tw = by_pk.get(_twins().get(p["aff_pk"]))
        if not tw:
            continue
        for lvl in ("faculty", "dept", "org"):
            ma, mb = (p.get("machine") or {}).get(lvl), (tw.get("machine") or {}).get(lvl)
            if not ma or not mb or ma["inst_id"] == mb["inst_id"]:
                continue
            a, b = sorted((ma["inst_id"], mb["inst_id"]))
            if a not in touched and b not in touched or f"same|inst:{a}|inst:{b}" in seen:
                continue
            if a in rows and b in rows and rows[a]["status"] == "active" and rows[b]["status"] == "active":
                pairs.setdefault((a, b), dict(level=lvl, lines=[]))["lines"].append((p["printed"], tw["printed"]))
    for n, ((a, b), v) in enumerate(sorted(pairs.items())):
        ev = dict(rows=[row_view(a), row_view(b)], affiliations=affs(a, 3) + affs(b, 3),
                  twin_lines=[dict(line=x, twin=y) for x, y in v["lines"][:3]],
                  note="the two rows carry one printed line and its twin in the other script")
        qs.append(dict(id=f"I{TAG}-T{n:03d}", domain="institutions", kind="inst:same_institution",
                       question=Q_SAME, options=["same", "different", "unsure"], evidence=ev,
                       meta=dict(rows=[a, b], parent=rows[a]["parent_id"], twin=True, level=v["level"])))
    # (b) a unit row with no parent (a faculty printed without its university, lumped by the machine)
    for i in sorted(touched):
        r = rows.get(i)
        if not r or r["kind"] not in ("faculty", "department") or r["parent_id"] or f"parent|inst:{i}" in seen:
            continue
        texts = names[i][:3] + [p["printed"] for p in affs_of[i][:6]]
        cc = None
        for p in affs_of[i]:
            cc = cc or judge56.printed_country(p)
        cands = F.new(texts, cc, None, pubnames, 8, {"university", "ministry", "academy", "other", "centre",
                                                     "institute", "school"}, unit_only=True)
        ev = dict(rows=[row_view(i)], affiliations=affs(i), journal_publishers=pubs,
                  authority_candidates=[F.card(x) for x in sorted(set(cands))])
        qs.append(dict(id=f"I{TAG}-P{i}", domain="institutions", kind="inst:set_parent", question=Q_PARENT,
                       options=["parent", "none", "unsure"], evidence=ev, meta=dict(row=i)))
    if frozen:                              # the institution-level questions as they were asked
        qs = [q for q in qs if q["kind"] == "inst:affiliation"] + [q for q in frozen.values()
                                                                   if q["kind"] != "inst:affiliation"]
        old_rules = {r["id"]: r for r in jl(INST / "rule_decisions.jsonl")}
        changed = [dict(id=r["id"], printed=r["printed"], before=old_rules[r["id"]].get("orgs"), after=r.get("orgs"))
                   for r in rules if r["id"] in old_rules and old_rules[r["id"]].get("orgs") != r.get("orgs")]
        wjs(INST / "rules_changed_by_review.json", changed)
        stat["rule answers changed by the reviewed forms"] = len(changed)
    # (c) countries: asked later (review72), for the bodies the applied links name that have none
    wjl(INST / "rule_decisions.jsonl", rules)
    wjl(QDIR / "inst.jsonl", qs)
    S = dict(affiliations=len(P), stat=dict(stat), rules=dict(Counter(r["rule"] for r in rules)),
             questions=dict(Counter(q["kind"] for q in qs)),
             rule_bodies_not_yet_defined=sorted({o for r in rules for o, k in r["defined"].items() if not k}))
    wjs(INST / "build_summary.json", S)
    print(json.dumps(S, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    dict(packets=packets, build=build)[sys.argv[1]]()
