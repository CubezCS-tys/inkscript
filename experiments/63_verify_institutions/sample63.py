"""Experiment 63, step 1: a random stratified sample of experiment 56's standing decisions, and BLIND views of them.

Reads (read-only) experiment 56's out/decisions56.jsonl, out/packets56.jsonl, out/institutions56.jsonl.
Writes:
    out/sample63_key.json     sample id -> exp 56 decision id, kind, confidence (NOT read before judging)
    out/blind63.txt           the question and the evidence only, per sample id (no exp 56 decision, reason, ids)
    out/blind63.jsonl         the same, structured

The blind view never shows exp 56's decision, its reason, its authority ids, or the qkey (which names a parent).
What it shows is what the librarian had: the printed statement and its parts, the article, journal, year, author,
the same author's other statements, the machine's rows (the linker's output, not exp 56's) and the catalogue hits.

    python3 sample63.py
"""
from __future__ import annotations

import json
import random
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
E56 = HERE.parent / "56_librarian_institutions" / "out"
OUT = HERE / "out"
SEED = 63

# per (kind, confidence[, basis group]): how many to draw (None = all)
PLAN = {
    ("affiliation_institution", "high", "rule"): 50,
    ("affiliation_institution", "high", "nonrule"): 15,
    ("affiliation_institution", "medium", "*"): None,
    ("set_country", "high", "catalogue"): 10,
    ("set_country", "high", "world"): 10,
    ("set_country", "medium", "*"): None,
    ("not_an_institution", "high", "*"): 12,
    ("not_an_institution", "medium", "*"): None,
    ("not_same_institution", "*", "*"): None,
    ("same_institution", "high", "*"): 10,
    ("same_institution", "medium", "*"): None,
    ("set_parent", "high", "*"): 10,
    ("set_parent", "medium", "*"): None,
    ("set_type", "high", "*"): 8,
    ("unit_kept_apart", "*", "*"): None,
    ("unsure", "*", "*"): None,
}


def standing():
    latest = {}
    for line in open(E56 / "decisions56.jsonl", encoding="utf-8"):
        d = json.loads(line)
        latest[d["qkey"]] = d
    return [d for d in latest.values() if d["kind"] != "retired"]


def stratum(d):
    k, c, b = d["kind"], d["confidence"], d["basis"]
    for (pk, pc, pb) in PLAN:
        if pk != k or (pc != "*" and pc != c):
            continue
        if pb == "*" or pb == b or (pb == "nonrule" and b != "rule"):
            return (pk, pc, pb)
    raise KeyError((k, c, b))


def cat_summary(cat: dict) -> list[str]:
    out = []
    for name, h in (cat or {}).items():
        th = "; ".join(f"{t['univ']} {dict(t['countries'])}" for t in h.get("thesis", [])[:3])
        co = "; ".join(f"{c['heading']} ×{c['n']}" for c in h.get("corp", [])[:4])
        out.append(f"«{name}»: theses[{th}] corp[{co}]")
    return out


def machine_summary(m: dict) -> list[str]:
    return [f"{lvl}: {r['names']} kind={r['kind']} country={r['country']} id={r['inst_id']} parent={r['parent_id']}"
            for lvl, r in (m or {}).items()]


def aff_view(p: dict) -> dict:
    a = p["author"]
    return dict(printed=p["printed"], parts={k: v for k, v in p["parts"].items() if v},
                journal=f"{p['journal_id']} {p['journal']}", year=p["year"], stem=p["stem"],
                author=a.get("name"), email=a.get("email"),
                same_article=[x["printed"] for x in p["same_article"]],
                other_articles=[f"{x['stem']}: {x['printed']}" for x in p["other_articles"][:5]],
                machine=machine_summary(p["machine"]), catalogue=cat_summary(p["catalogue"]))


QUESTION = {
    "affiliation": "Which institution(s) does this printed affiliation name? (resolved: which body/bodies and "
                   "country | unit_only: a faculty printed without its university | not_institution | unsure)",
    "set_country": "In which country is this institution (machine row)?",
    "set_parent": "Is this machine row a unit of another body? If so, which?",
    "set_type": "What kind of body is this row (university / ministry / academy / institute / centre / school / "
                "society / organisation / faculty …)?",
    "same_institution": "Are these machine rows one body?",
    "not_same_institution": "Is this machine row one body? If not, how do its affiliations split?",
    "not_an_institution": "Is this machine row an institution at all?",
}


def main():
    S = standing()
    P = {json.loads(l)["key"]: json.loads(l) for l in open(E56 / "packets56.jsonl", encoding="utf-8")}
    I = {json.loads(l)["inst_id"]: json.loads(l) for l in open(E56 / "institutions56.jsonl", encoding="utf-8")}
    groups = defaultdict(list)
    for d in S:
        groups[stratum(d)].append(d)
    rng = random.Random(SEED)
    picked = []
    for st, n in PLAN.items():
        g = sorted(groups.get(st, []), key=lambda d: d["decision_id"])
        picked += [(st, d) for d in (g if n is None or n >= len(g) else rng.sample(g, n))]
    rng.shuffle(picked)  # judge in a mixed order, not kind by kind
    key, blind, lines = {}, [], []
    for i, (st, d) in enumerate(picked, 1):
        sid = f"S{i:03d}"
        key[sid] = dict(decision_id=d["decision_id"], kind=d["kind"], confidence=d["confidence"],
                        basis=d["basis"], stratum="|".join(st), stratum_size=len(groups[st]),
                        stratum_drawn=sum(1 for s, _ in picked if s == st))
        if d["level"] == "affiliation":
            p = P[d["subject_keys"][0]]
            v = dict(sid=sid, level="affiliation", question=QUESTION["affiliation"], aff_key=p["key"], **aff_view(p))
        else:
            q = d["kind"]
            rows = [I[s[5:]] for s in d["subject_keys"] if s.startswith("inst:")]
            affs = [e for e in d["evidence_ids"] if e.startswith("aff:")]
            for r in rows:
                for a in r["affiliations"]:
                    if a not in affs:
                        affs.append(a)
            rv = []
            for r in rows:
                par = I.get(r["parent_id"]) if r.get("parent_id") else None
                rv.append(dict(id=r["inst_id"], kind=r["kind"], country=r["country"], names=r["names"],
                               parent=(par["names"] if par else None), n_aff=len(r["affiliations"])))
            v = dict(sid=sid, level="institution", question=QUESTION[q], rows=rv,
                     affiliations=[dict(key=a, **aff_view(P[a])) for a in affs if a in P][:12])
        blind.append(v)
        lines.append(f"=== {sid}  [{v['level']}]  {v['question']}")
        if v["level"] == "affiliation":
            for f in ("printed", "parts", "journal", "year", "stem", "author", "email", "same_article",
                      "other_articles", "machine", "catalogue"):
                if v.get(f):
                    lines.append(f"  {f}: {v[f]}")
        else:
            for r in v["rows"]:
                lines.append(f"  ROW {r['id']} kind={r['kind']} country={r['country']} names={r['names']} "
                             f"parent={r['parent']} n_aff={r['n_aff']}")
            for a in v["affiliations"]:
                lines.append(f"   - {a['printed']}  | {a['journal']} {a['year']} {a['stem']} | parts={a['parts']}")
                if a["same_article"]:
                    lines.append(f"       same article: {a['same_article']}")
                if a["other_articles"]:
                    lines.append(f"       other articles: {a['other_articles'][:3]}")
                for c in a["catalogue"][:2]:
                    lines.append(f"       cat {c[:300]}")
        lines.append("")
    OUT.mkdir(exist_ok=True)
    (OUT / "sample63_key.json").write_text(json.dumps(key, ensure_ascii=False, indent=1), encoding="utf-8")
    with open(OUT / "blind63.jsonl", "w", encoding="utf-8") as f:
        for v in blind:
            f.write(json.dumps(v, ensure_ascii=False) + "\n")
    (OUT / "blind63.txt").write_text("\n".join(lines), encoding="utf-8")
    print(len(picked), Counter("|".join(s) for s, _ in picked))


if __name__ == "__main__":
    main()
