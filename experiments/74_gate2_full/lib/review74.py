"""Experiment 74 (from review72.py): the authority review of one journal — bodies the models named that the
authority does not hold (exp 72's lesson 3: review the new bodies once per journal).

Experiment 71's rule never applies a "new:" body without an authority review. The review is done by hand (reading
every printed statement in review_candidates.json) and recorded in OUT/inst/review74_input.json (format below): each
body the models named outside the authority is accepted (a new authority entry L-74-…, with names, type, country and
the printed forms that point at it), mapped to an existing entry, or refused.

    python review74.py gather    -> OUT/inst/review_candidates.json (every outside id, its questions and statements)
    python review74.py write     OUT/inst/review74_input.json -> OUT/inst/authority74.json (bodies + answer_map)
""" 
from __future__ import annotations

import json
import re
import sys
from collections import defaultdict

from common74 import JOURNAL, OUT, jl, js, wjs
from inst74 import fold

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


# ------------------------------------------------------------------ the review (by hand), read from a file
# OUT/inst/review74_input.json, written by the agent after reading every statement of review_candidates.json:
#   {"bodies": [{"id": "L-74-<cc>-<name>", "type": "university|other|centre|ministry|society|academy|...",
#                "country": "EG" | null, "name_ar": "...", "name_en": "...", "forms": ["forms a rule may match"],
#                "rows": ["machine rows, the body's own first"], "why": "..."}],
#    "refused": {"<folded name>": "why"},
#    "map": {"<outside id or name as the model gave it>": "<existing authority id>"}}
# A form is added only when it names this one body wherever it is printed (a generic name only with its country).


def review_input():
    p = OUT / "inst" / "review74_input.json"
    if not p.exists():
        raise SystemExit(f"write the hand review first: {p}")
    R = js(p)
    rv = [(b["id"], b["type"], b.get("country"), b.get("name_ar"), b.get("name_en"), list(b.get("forms") or []),
           list(b.get("rows") or []), b.get("why") or "") for b in R.get("bodies") or []]
    return rv, dict(R.get("refused") or {}), dict(R.get("map") or {})


def write():
    import judge56  # noqa: F401  (loads the authority with experiment 64's bodies)
    from inst74 import desk_defined, load_authority
    AUTH = load_authority()
    defined = desk_defined()
    canon_of = {v: k for k, v in defined.items()}
    REVIEW, REFUSED, MAP = review_input()
    bodies = []
    keymap = {}
    for x, L in MAP.items():
        keymap[x] = L
        keymap[fold(x[4:] if x.startswith("new:") else x)] = L
    for (i, t, cc, ar, en, forms, rows, why) in REVIEW:
        claimed = [r for r in rows if r in canon_of]
        if claimed:
            raise SystemExit(f"{i}: row {claimed} is already the Desk's row for {canon_of[claimed[0]]}")
        bodies.append(dict(id=i, type=t, country=cc, name_ar=ar, name_en=en, forms=forms, rows=rows, why=why,
                           accepted=True, reviewed_by=f"agent:exp74 (by hand, journal {JOURNAL})"))
        for x in [y for y in [ar, en] + forms if y]:
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
    wjs(OUT / "inst" / "authority74.json", dict(bodies=bodies, refused=REFUSED, answer_map=amap))
    print(len(bodies), "bodies;", sum(1 for v in amap.values() if v["ok"]), "of", len(amap), "answers mapped")
    for k, v in amap.items():
        if not v["ok"]:
            print("  not mapped:", k, v["why"])


if __name__ == "__main__":
    dict(gather=gather, write=write)[sys.argv[1]]()
