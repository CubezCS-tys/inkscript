"""Experiment 71, step 1: the gold set and the evidence packets (code only, no call).

Gold = librarian decisions whose answer was VERIFIED:
  * cited works (exp 62): the 316 decisions of the two blind rounds. Gold = the librarian's answer where the blind
    judge agreed; the adjudicated verdict where they disagreed; both answers where the adjudication said "both
    defensible".
  * institutions (exp 63): the 230 decisions re-decided blind. Kept: the 208 where blind and exp 56 agreed, plus the 2
    minor errors with the corrected answer where it is clean. Left out: the 14 "exp 56 conservative" (both answers
    defensible, the blind one only free text), the 6 set_type "both acceptable" and set_type itself (blind agreement
    25%: the type list cannot hold the answer, exp 63).
Packets = what the librarian's tools put in front of it (exp 62's blind packets as built by blind62.py from
tools62.py; exp 63's blind views of exp 56's packets, plus the authority candidates a retriever finds and the
journal's publisher from the release). Never the decision, its reason, its rule or its confidence.

    python3 gold71.py      -> out/gold71.jsonl (id, domain, kind, accept, ...)  out/packets71.jsonl (id, question, evidence)
"""
from __future__ import annotations

import json
import re
import unicodedata
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E = HERE.parent
W = E / "62_librarian_works" / "out"
V = E / "63_verify_institutions" / "out"
I = E / "56_librarian_institutions" / "out"


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def js(p):
    return json.load(open(p, encoding="utf-8"))


# ------------------------------------------------------------------------------------------- cited works (exp 62)

NOTWORK_OPT = {"not_a_work:drop": "not_a_work_drop", "not_a_work:retitle": "not_a_work_retitle",
               "not_a_work:one_per_citation": "not_a_work_one_per_citation"}


def works():
    gold, packets = [], []
    for rnd, (pk, key, sc, adj) in enumerate([("blind62_packets.jsonl", "blind62_key.json", "blind62_scored.json",
                                               "blind62_adjudication.json"),
                                              ("blind62b_packets.jsonl", "blind62b_key.json", "blind62b_scored.json",
                                               "blind62b_adjudication.json")], 1):
        P = {p["bid"]: p for p in jl(W / pk)}
        K = js(W / key)["key"]
        S = {r["bid"]: r for r in js(W / sc)["rows"]}
        A = {c["bid"]: c for c in js(W / adj)["cases"]}
        for bid, p in P.items():
            k, s = K[bid], S[bid]
            notwork_q = "not_a_work_drop" in p["options"]

            def opt(lbl):          # the scored label -> this packet's option
                if notwork_q:
                    return NOTWORK_OPT.get(lbl, lbl)
                return "not_a_work" if lbl.startswith("not_a_work") else lbl
            if s["agree"] and not s["exact"]:      # blind62 counts same_work ~ edition_of as agreement
                accept, how = sorted({opt(s["mine"]), opt(s["blind"])}), "blind agreed (same/edition)"
            elif s["agree"]:
                accept, how = [opt(s["mine"])], "blind agreed"
            else:
                a = A[bid]
                if a["right"] == "both":
                    accept, how = sorted({opt(a["verdict"]), opt(a["mine"]), opt(a["blind"])}), "adjudicated: both"
                else:
                    accept, how = [opt(a["verdict"])], f"adjudicated: {a['right']} right"
            kind = f"{k['level']}:{k['kind']}"
            gk = accept[0] if len(accept) == 1 else "/".join(accept)
            iid = f"W{rnd}-{bid}"
            gold.append(dict(id=iid, domain="works", round=rnd, kind=kind, gold_kind=gk, accept=accept, how=how,
                             librarian_conf=k["confidence"], decision_id=k["decision_id"],
                             groups=s.get("blind_groups") if accept == ["split_card"] else None))
            ev = {x: v for x, v in p.items() if x not in ("bid", "question", "options")}
            packets.append(dict(id=iid, domain="works", question=p["question"], options=p["options"], evidence=ev))
    return gold, packets


# ------------------------------------------------------------------------------------------- institutions (exp 56/63)

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


class Authority:
    """The librarian's authority file as a retriever sees it. Shown to the model: id, names, type, country, parent's
    name. Never shown: printed forms, articles, counts (they were written from the decisions under test)."""

    def __init__(self):
        a = js(I / "authority56.json")
        self.E = {e["id"]: e for e in a["institutions"]}
        self.G = {}
        for e in a["institutions"]:
            forms = [e.get("name_ar") or "", e.get("name_en") or ""] + [f["form"] for f in e.get("printed_forms") or []
                                                                      if f.get("n", 0) >= 2]
            self.G[e["id"]] = [grams(f) for f in forms if f]

    def card(self, i):
        e = self.E[i]
        par = self.E.get(e.get("parent") or "")
        return dict(id=i, name_ar=e.get("name_ar"), name_en=e.get("name_en"), type=e.get("type"),
                    country=e.get("country"), parent=(par or {}).get("name_ar") if par else None)

    def search(self, texts, k=8, types=None):
        q = [grams(t) for t in texts if t]
        sc = []
        for i, gs in self.G.items():
            if types and self.E[i].get("type") not in types:
                continue
            best = max((len(a & b) / max(1, min(len(a), len(b))) * (len(a & b) / max(1, len(a | b))) ** 0.5
                        for a in q for b in gs), default=0)
            sc.append((best, i))
        sc.sort(reverse=True)
        return [i for s, i in sc[:k] if s > 0.05]


Q_AFF = ("Which institution(s) does this printed affiliation name? status: resolved = it names one or more bodies "
         "(give their ids from the candidates, or new:<name> for a body not among them, and the country) | unit_only = "
         "a faculty / department printed without its university and nothing on the page says which | not_institution "
         "= no body is named (a position, a degree, a place, a court, a reprint source) | unsure.")
Q_SAME = ("These machine rows were proposed as spellings of one body. Are they one body (same) or not (different)? "
          "If same, give the authority id if one of the candidates is that body, else new:<name>.")
Q_SPLIT = ("This one machine row holds several affiliations. Do they all name one body (one_body), or do they name "
           "different bodies (several_bodies)?")
Q_COUNTRY = "In which country is this institution (machine row)? Answer an ISO 3166 alpha-2 code, or unsure."
Q_ROW = ("Is this machine row an institution at all (a body: university, ministry, centre, society...), or "
         "not_institution (a position, a place, a court, a generic word)?")
Q_PARENT = ("Is this machine row a unit (faculty, institute, centre, hospital) of a larger body? If so give the "
            "parent's id from the candidates (or new:<name>); answer none if it is a top-level body.")


def institutions():
    key = js(V / "sample63_key.json")
    adj = js(V / "adjudication63.json")
    views = {v["sid"]: v for v in jl(V / "blind63.jsonl")}
    journals = js(V / "journals63.json")
    by_id = {d["decision_id"]: d for d in jl(I / "decisions56.jsonl")}
    AU = Authority()
    gold, packets, skipped = [], [], Counter()
    for sid, k in key.items():
        a, v, d = adj[sid], views[sid], by_id[k["decision_id"]]
        kind = k["kind"]
        if kind == "set_type":
            skipped["set_type"] += 1
            continue
        if a["verdict"] not in ("agree",):
            skipped[a["verdict"]] += 1
            continue
        ev = {x: y for x, y in v.items() if x not in ("sid", "question", "level")}
        # the journal's publisher (release catalogue), as exp 63's blind judge had it
        jids = sorted({(af.get("journal") or "").split(" ")[0] for af in ([v] if v["level"] == "affiliation"
                                                                         else v.get("affiliations") or [])})
        ev["journal_publishers"] = {j: journals[j] for j in jids if j in journals}
        texts = [v.get("printed"), (v.get("parts") or {}).get("org"), (v.get("parts") or {}).get("faculty")] \
            if v["level"] == "affiliation" else \
            [n for r in v.get("rows") or [] for n in r["names"]] + \
            [af.get("printed") for af in (v.get("affiliations") or [])[:6]]
        dc = d["decision"]
        g = dict(id=f"I-{sid}", domain="institutions", kind=f"inst:{kind}", librarian_conf=k["confidence"],
                 basis=k["basis"], decision_id=k["decision_id"], how="blind agreed")
        cands, inject = None, False
        if v["level"] == "affiliation":
            st = dc["status"]
            ids = sorted(x["id"] for x in dc.get("institutions") or [])
            g.update(gold_kind=st, accept=[st], ids=ids, country=dc.get("country"))
            cands = AU.search(texts, k=8)
            miss = [i for i in ids if i not in cands]
            if miss:
                inject = True
                cands = (cands[:8 - len(miss)] + miss)
            q, opts = Q_AFF, ["resolved", "unit_only", "not_institution", "unsure"]
        elif kind == "not_an_institution":          # institution level: is the row a body at all?
            g.update(gold_kind="not_institution", accept=["not_institution"])
            q, opts = Q_ROW, ["institution", "not_institution", "unsure"]
        elif kind == "same_institution":
            g.update(gold_kind="same", accept=["same"], ids=[dc["institution"]])
            cands = AU.search(texts, k=8)
            if dc["institution"] not in cands:
                inject, cands = True, cands[:7] + [dc["institution"]]
            q, opts = Q_SAME, ["same", "different", "unsure"]
        elif kind == "not_same_institution":
            g.update(gold_kind="several_bodies", accept=["several_bodies"])
            q, opts = Q_SPLIT, ["one_body", "several_bodies", "unsure"]
        elif kind == "set_country":
            g.update(gold_kind=dc["country"], accept=[dc["country"]])
            q, opts = Q_COUNTRY, ["<ISO2>", "unsure"]
        elif kind == "set_parent":
            g.update(gold_kind="parent", accept=["parent"], ids=[dc["parent"]])
            cands = AU.search(texts, k=8, types={"university", "ministry", "academy", "other", "centre", "institute",
                                                 "school"})
            if dc["parent"] not in cands:
                inject, cands = True, cands[:7] + [dc["parent"]]
            q, opts = Q_PARENT, ["parent", "none", "unsure"]
        else:
            raise ValueError(kind)
        if cands is not None:
            cands = sorted(set(cands))          # order carries no hint
            ev["authority_candidates"] = [AU.card(i) for i in cands]
            g["candidates_injected"] = inject
        gold.append(g)
        packets.append(dict(id=g["id"], domain="institutions", question=q, options=opts, evidence=ev))
    return gold, packets, skipped


def main():
    OUT.mkdir(exist_ok=True)
    gw, pw = works()
    gi, pi, skipped = institutions()
    gold, packets = gw + gi, pw + pi
    with open(OUT / "gold71.jsonl", "w", encoding="utf-8") as f:
        for g in gold:
            f.write(json.dumps(g, ensure_ascii=False) + "\n")
    with open(OUT / "packets71.jsonl", "w", encoding="utf-8") as f:
        for p in packets:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    c = Counter((g["kind"], g["gold_kind"] if g["domain"] == "works" else "") for g in gold)
    for x in sorted(c):
        print(f"  {x[0]:38s} {x[1]:32s} {c[x]}")
    print("works", len(gw), "institutions", len(gi), "skipped", dict(skipped),
          "injected", sum(1 for g in gi if g.get("candidates_injected")),
          "of", sum(1 for g in gi if "candidates_injected" in g))
    sz = [len(json.dumps(p, ensure_ascii=False)) for p in packets]
    print("packet chars: mean", sum(sz) // len(sz), "max", max(sz))


if __name__ == "__main__":
    main()
