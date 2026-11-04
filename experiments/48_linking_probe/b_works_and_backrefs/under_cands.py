"""B1 under-merging: candidate pairs of DIFFERENT cards that may be one work.
R1 same author word + similar title once author words, «ابن/بن», edition and volume markers are stripped;
R2 one side has no author: the stripped titles are equal (>= 2 words or >= 8 letters).
Read-only; writes under_candidates.json."""
import json, re, sys
from collections import defaultdict, Counter
sys.path.insert(0, "/home/appuser/inkscript/experiments/47_platform_v2")
import link47
from common47 import ratio, tokset
from db import OUT
cards = json.load(open(f"{OUT}/cards_dump.json"))
MARK = re.compile(r"\b(ط|طبعه|الطبعه|طبعة|ج|جزء|الجزء|مج|مجلد|المجلد|مجلدات|اجزاء|vol|volume|tome|t|ed|edition|"
                  r"تحقيق|تح|شرح|قسم|القسم|part|teil|band|bd|[0-9]+|اول|ثاني|ثالث|الاول|الثاني|الثالث)\b")
info = []
for cd in cards:
    au = set()
    for m in cd["members"]:
        p = json.loads(m["parsed"]) if m["parsed"] else None
        au |= link47.author_tokens(p)
    tk = cd["title_key"] or ""
    words = [w for w in MARK.sub(" ", tk).split() if w not in ("بن", "ابن") and w not in au
             and re.sub("^ل", "", w) not in au]
    st = " ".join(words)
    info.append(dict(i=len(info), id=cd["cited_work_id"], title=cd["title"], tk=tk, st=st, au=au,
                     n=cd["n_members"], pubs=cd["n_pubs"], type=cd["pub_type"]))
by_au, by_st = defaultdict(list), defaultdict(list)
for x in info:
    for w in x["au"]:
        by_au[w].append(x["i"])
    if x["st"]:
        by_st[x["st"]].append(x["i"])
pairs = {}
for w, ix in by_au.items():
    if len(ix) > 400: continue
    for a in ix:
        for b in ix:
            if b <= a: continue
            A, B = info[a], info[b]
            s1, s2 = A["st"], B["st"]
            if not s1 or not s2: continue
            why = None
            if s1 == s2: why = "R1 stripped-equal"
            elif min(len(s1), len(s2)) >= 4 and (f" {s1} " in f" {s2} " or f" {s2} " in f" {s1} "): why = "R1 contained"
            elif tokset(s1, s2) >= 0.6 and ratio(s1, s2) >= 0.6 and min(len(s1.split()), len(s2.split())) >= 2:
                why = "R1 similar"
            if why: pairs[(a, b)] = why
for st, ix in by_st.items():
    if len(st.split()) < 2 and len(st) < 8: continue
    for a in ix:
        for b in ix:
            if b <= a or (a, b) in pairs: continue
            if (not info[a]["au"]) != (not info[b]["au"]) or (not info[a]["au"] and not info[b]["au"]):
                pairs[(a, b)] = "R2 stripped-equal, an author missing"
out = []
for (a, b), why in sorted(pairs.items()):
    A, B = info[a], info[b]
    out.append(dict(rule=why, a=dict(id=A["id"], title=A["title"], au=sorted(A["au"]), n=A["n"], pubs=A["pubs"]),
                    b=dict(id=B["id"], title=B["title"], au=sorted(B["au"]), n=B["n"], pubs=B["pubs"])))
json.dump(out, open(f"{OUT}/under_candidates.json", "w"), ensure_ascii=False, indent=1)
print(len(out), Counter(o["rule"] for o in out))
