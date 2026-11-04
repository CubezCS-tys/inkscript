"""Experiment 71, step 3: score every model's answers against the gold; cross-model agreement; the tiered design.

    python3 score71.py        -> out/scores71.json, out/disagree71_<model>.jsonl, prints the tables

Definitions
  decided   = the model did not answer "unsure" (or gave no parsable answer)
  correct   = the decided answer is one the gold accepts (institutions: the status / answer AND the ids; the country is
              scored separately and in "strict")
  precision = correct / decided; coverage = decided / items whose gold is not "unsure"
  by answer = grouped by what the MODEL said (what an apply rule sees); by gold = grouped by the right answer
  weighted  = each item weighted by its stratum's population / sample size (the gold is stratified, oversampling hard
              kinds; the weighted figure is what the population of decisions would see)
"""
from __future__ import annotations

import json
import math
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E = HERE.parent
MODELS = ["gemini-3.8-flash", "gemini-3.8-flash@high", "gemini-4-argon", "claude-sonnet-5-5", "gemini-4-argon@high",
          "claude-opus-5-5"]   # roughly cheapest first (simulate71 cascades go cheaper -> dearer in this order)
BAR = 0.98


def jl(p):
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()]


def wilson_lo(k, n, z=1.96):
    if n == 0:
        return 0.0
    p = k / n
    d = 1 + z * z / n
    return (p + z * z / (2 * n) - z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / d


# ------------------------------------------------------------------------------------------------ gold + weights

def load_gold():
    G = {g["id"]: g for g in jl(OUT / "gold71.jsonl")}
    # basis (rule vs judgement) and population weights
    d62 = {d["decision_id"]: d for d in jl(E / "62_librarian_works" / "out" / "decisions62.jsonl")}
    sc = json.load(open(E / "62_librarian_works" / "out" / "scale62.json"))["measured"]["levels"]
    popw = {f"{lv}:{k}": n for lv, v in sc.items() for k, n in v["by_kind"].items()}
    key63 = json.load(open(E / "63_verify_institutions" / "out" / "sample63_key.json"))
    n_in = Counter()
    for g in G.values():
        if g["domain"] == "works":
            d = d62.get(g["decision_id"]) or {}
            g["basis"] = d.get("basis") or "?"
            g["rule"] = bool(d.get("trivial")) or g["basis"] == "rule"
            g["stratum"] = g["kind"]
            g["pop"] = popw.get(g["kind"], 1)
        else:
            k = key63[g["id"][2:]]
            g["rule"] = g["basis"] == "rule"
            g["stratum"] = k["stratum"]
            g["pop"] = k["stratum_size"]
        n_in[g["stratum"]] += 1
    for g in G.values():
        g["w"] = g["pop"] / n_in[g["stratum"]]
    return G


# ------------------------------------------------------------------------------------------------ judging one answer

def judge(g, a):
    """-> (decided, correct, label, strict) ; label = the model's answer kind as an apply rule would see it."""
    if not isinstance(a, dict):
        return False, False, "no_answer", False
    ans = str(a.get("answer") or "").strip()
    ids = sorted(str(x) for x in a.get("ids") or [])
    if ans.lower() == "unsure" or not ans:
        return False, False, "unsure", False
    if g["domain"] == "works":
        lab = ans
        ok = ans in g["accept"]
        return True, ok, lab, ok
    k = g["kind"]
    if "country" in g:                             # affiliation level (gold71 gives these ids + country)
        lab = f"aff:{ans}"
        ok = ans == g["gold_kind"]
        if ok and ans == "resolved":
            ok = ids == sorted(g["ids"])
        strict = ok and (ans != "resolved" or not g.get("country") or
                         str(a.get("country") or "").upper() == g["country"])
        return True, ok, lab, strict
    if k == "inst:not_an_institution":             # row level
        return True, ans == "not_institution", f"row:{ans}", ans == "not_institution"
    if k == "inst:same_institution":
        ok = ans == "same" and ids == sorted(g["ids"])
        return True, ok, f"merge:{ans}", ok
    if k == "inst:not_same_institution":
        return True, ans == "several_bodies", f"split:{ans}", ans == "several_bodies"
    if k == "inst:set_country":
        ok = ans.upper() == g["gold_kind"]
        return True, ok, "set_country", ok
    if k == "inst:set_parent":
        ok = ans == "parent" and ids == sorted(g["ids"])
        return True, ok, f"parent:{ans}", ok
    raise ValueError(k)


JOIN = {"same_work", "edition_of"}                 # both join the two cards; only the edition label differs
NOTWORK = {"not_a_work_drop", "not_a_work_retitle", "not_a_work_one_per_citation", "not_a_work"}


def lenient(g, a, dec, ok):
    """Right about what happens to the index: same_work ~ edition_of (both join), and any not-a-work action."""
    if ok or not dec or g["domain"] != "works":
        return ok
    ans = str(a.get("answer"))
    return any(ans in grp and x in grp for grp in (JOIN, NOTWORK) for x in g["accept"])


def gold_is_unsure(g):
    return g["accept"] == ["unsure"]


# ------------------------------------------------------------------------------------------------ scoring

def answers(model):
    f = OUT / "answers" / f"{model}.jsonl"
    A = {}
    if f.exists():
        for r in jl(f):
            A[r["id"]] = r          # last wins
    return A


def table(rows, keyf):
    T = defaultdict(lambda: dict(n=0, decided=0, correct=0, wn=0.0, wd=0.0, wc=0.0))
    for g, dec, ok, lab, conf in rows:
        t = T[keyf(g, lab, conf)]
        t["n"] += 1
        t["wn"] += g["w"]
        if dec:
            t["decided"] += 1
            t["wd"] += g["w"]
            if ok:
                t["correct"] += 1
                t["wc"] += g["w"]
    out = {}
    for k, t in sorted(T.items()):
        out[k] = dict(n=t["n"], decided=t["decided"], correct=t["correct"],
                      precision=round(t["correct"] / t["decided"], 4) if t["decided"] else None,
                      wilson_lo=round(wilson_lo(t["correct"], t["decided"]), 3),
                      coverage=round(t["decided"] / t["n"], 3) if t["n"] else None,
                      w_precision=round(t["wc"] / t["wd"], 4) if t["wd"] else None)
    return out


def score(G, model):
    A = answers(model)
    rows, dis, usd, secs, n_b, toks, extra = [], [], [], [], 0, Counter(), {}
    for iid, g in G.items():
        r = A.get(iid)
        if not r:
            continue
        a = r.get("answer")
        dec, ok, lab, strict = judge(g, a)
        conf = (a or {}).get("confidence") if isinstance(a, dict) else None
        rows.append((g, dec, ok, lab, conf))
        extra[iid] = dict(strict=strict, lenient=lenient(g, a, dec, ok))
        if r["mode"] == "batch":
            usd.append(r["usd"])
            toks["in"] += r["tin"]
            toks["out"] += r["tout"] + r["think"]
            n_b += 1
        elif r.get("secs"):
            secs.append(r["secs"])
        if not ok:
            dis.append(dict(id=iid, kind=g["kind"], gold=g["accept"], gold_ids=g.get("ids"), model=a,
                            decided=dec, how=g["how"]))
    if not rows:
        return None
    (OUT / f"disagree71_{model}.jsonl").write_text(
        "".join(json.dumps(x, ensure_ascii=False) + "\n" for x in dis), encoding="utf-8")
    nonuns = [x for x in rows if not gold_is_unsure(x[0])]
    dec = [x for x in rows if x[1]]
    S = dict(model=model, n=len(rows),
             decided=len(dec), correct=sum(1 for x in dec if x[2]),
             precision=round(sum(1 for x in dec if x[2]) / max(1, len(dec)), 4),
             coverage=round(sum(1 for x in nonuns if x[1]) / max(1, len(nonuns)), 4),
             accuracy=round(sum(1 for x in rows if x[2]) / len(rows), 4),
             w_precision=round(sum(x[0]["w"] for x in dec if x[2]) / max(1e-9, sum(x[0]["w"] for x in dec)), 4),
             strict_precision=round(sum(1 for x in dec if extra[x[0]["id"]]["strict"]) / max(1, len(dec)), 4),
             lenient_precision=round(sum(1 for x in dec if extra[x[0]["id"]]["lenient"]) / max(1, len(dec)), 4),
             high=dict(n=sum(1 for x in dec if x[4] == "high"),
                       correct=sum(1 for x in dec if x[4] == "high" and x[2])),
             unparsed=sum(1 for x in rows if x[3] == "no_answer"),
             by_domain=table(rows, lambda g, l, c: g["domain"]),
             by_gold=table(rows, lambda g, l, c: f"{g['kind']} -> {'/'.join(g['accept']) if g['domain'] == 'works' else g['gold_kind'] if g['kind'] != 'inst:set_country' else 'ISO2'}"),
             by_answer=table(rows, lambda g, l, c: f"{g['domain'][0]}:{l}"),
             by_answer_high=table([x for x in rows if x[4] == "high"], lambda g, l, c: f"{g['domain'][0]}:{l}"),
             by_conf=table(rows, lambda g, l, c: str(c)),
             by_basis=table(rows, lambda g, l, c: f"{g['domain']}:{'rule' if g['rule'] else 'judgement'}"),
             cost=dict(batch_n=n_b, usd_per_decision=round(sum(usd) / n_b, 6) if n_b else None,
                       usd_per_1000=round(1000 * sum(usd) / n_b, 3) if n_b else None,
                       tokens_in_mean=round(toks["in"] / n_b) if n_b else None,
                       tokens_out_mean=round(toks["out"] / n_b) if n_b else None),
             latency=dict(standard_secs_median=sorted(secs)[len(secs) // 2] if secs else None, standard_n=len(secs)))
    S["high"]["precision"] = round(S["high"]["correct"] / max(1, S["high"]["n"]), 4)
    S["rows"] = {x[0]["id"]: dict(dec=x[1], ok=x[2], lab=x[3], conf=x[4], **extra[x[0]["id"]]) for x in rows}
    return S


def batch_wall():
    f = OUT / "batch_state71.json"
    if not f.exists():
        return {}
    st = json.load(open(f))
    return {m: [dict(n=j["n"], wall_secs=j.get("wall_secs")) for j in js] for m, js in st.items()}


def cross(S, G):
    """Agreement between every two models, and the precision when they agree."""
    out = {}
    ms = [m for m in MODELS if S.get(m)]
    for i, a in enumerate(ms):
        for b in ms[i + 1:]:
            Ra, Rb = S[a]["rows"], S[b]["rows"]
            both = [k for k in Ra if k in Rb]
            agree = [k for k in both if Ra[k]["dec"] and Rb[k]["dec"] and same_answer(k, a, b)]
            dis = [k for k in both if Ra[k]["dec"] and Rb[k]["dec"] and k not in set(agree)]
            out[f"{a} | {b}"] = dict(
                both=len(both), both_decided=sum(1 for k in both if Ra[k]["dec"] and Rb[k]["dec"]),
                agree=len(agree), agree_correct=sum(1 for k in agree if Ra[k]["ok"]),
                agree_precision=round(sum(1 for k in agree if Ra[k]["ok"]) / max(1, len(agree)), 4),
                disagree=len(dis), a_right=sum(1 for k in dis if Ra[k]["ok"]), b_right=sum(1 for k in dis if Rb[k]["ok"]),
                errors_of_a_caught=sum(1 for k in both if Ra[k]["dec"] and not Ra[k]["ok"] and
                                       (not Rb[k]["dec"] or k in set(dis))),
                errors_of_a=sum(1 for k in both if Ra[k]["dec"] and not Ra[k]["ok"]))
    return out


_ANS = {}


def same_answer(k, a, b):
    for m in (a, b):
        if m not in _ANS:
            _ANS[m] = answers(m)

    def norm(m):
        x = _ANS[m][k].get("answer") or {}
        return (str(x.get("answer")).upper(), tuple(sorted(x.get("ids") or [])) if x.get("answer") in
                ("resolved", "same", "parent") else ())
    return norm(a) == norm(b)


def main():
    G = load_gold()
    S = {m: score(G, m) for m in MODELS}
    S = {m: s for m, s in S.items() if s}
    for m, s in S.items():
        print(f"\n=== {m}: n={s['n']} decided={s['decided']} precision={s['precision']} (weighted {s['w_precision']}) "
              f"strict={s['strict_precision']} lenient={s['lenient_precision']} coverage={s['coverage']} high-conf precision={s['high']['precision']} ({s['high']['n']}) "
              f"unparsed={s['unparsed']} cost/1000=${s['cost']['usd_per_1000']}")
        for k, t in s["by_answer"].items():
            flag = "PASS" if t["precision"] is not None and t["precision"] >= BAR and t["decided"] >= 10 else ""
            print(f"   {k:34s} decided {t['decided']:4d}  correct {t['correct']:4d}  P {t['precision']}  "
                  f"(wilson lo {t['wilson_lo']}, weighted {t['w_precision']}) {flag}")
    X = cross(S, G)
    for k, v in X.items():
        print(k, v)
    res = dict(models={m: {x: y for x, y in s.items() if x != "rows"} for m, s in S.items()}, cross=X,
               batch_wall=batch_wall(), rows={m: s["rows"] for m, s in S.items()})
    (OUT / "scores71.json").write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")


if __name__ == "__main__":
    main()
