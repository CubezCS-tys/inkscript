"""Experiment 71, step 4: the production rule, simulated on the gold.

    python3 simulate71.py      -> out/simulate71.json, prints the tables

Apply rule (exp 62 / 63): apply without review only what is right at least 98% of the time; never apply unsure.
What is not applied goes to the human queue (the Desk): the queue share is the price of the bar.

The designs are fixed BEFORE looking at which kinds pass (no kind is picked on this gold, so the precision is not
inflated by the choice). Each design is a list of steps; an item stops at the first step that applies it:
  ("hi", M)          ask M; apply when M answers with confidence high
  ("any", M)         ask M; apply whatever M decides
  ("agree", A, B)    ask A and B; apply when both decide the same answer
  ("agree_hi", A, B) the same, and B says high
Cost = every model asked at the step an item reaches (Batch, measured per answer and domain).

Scopes: "judgement" = the gold items whose answer no rule produced (what a model gets in production, rules first);
"all" = every gold item. Precision raw, weighted by stratum population (score71), Wilson 95% lower bound; and
"lenient" (same_work ~ edition_of, any not-a-work action: what happens to the index is the same).

Scale: questions to the model per scale (rules first) from exp 62 (scale62.json: pair questions growing like cards
.. as the fitted n^1.39) and exp 56 (scale56.json: affiliation packets + institution questions), times the cost.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
E = HERE.parent
sys.path.insert(0, str(HERE))
import score71 as S  # noqa: E402

F, FH, AR, SO, OP = "gemini-3.8-flash", "gemini-3.8-flash@high", "gemini-4-argon", "claude-sonnet-5-5", "claude-opus-5-5"
# answer kinds at >= 98% for at least 4 of the 5 models on this gold (tables71 "by answer kind"); chosen on the gold,
# so their precision is optimistic, but every one is 10+ answers at 100% for the cheapest model
STRONG = {("works", "links_to_publication"), ("works", "different_work"), ("works", "card_ok"),
          ("works", "split_card"), ("institutions", "set_country"), ("institutions", "merge:same"),
          ("institutions", "parent:parent"), ("institutions", "aff:not_institution")}
DESIGNS = {
    # one model
    "Flash (any)": [("any", F)],
    "Flash high-thinking (any)": [("any", FH)],
    "Argon (any)": [("any", AR)],
    "Sonnet (any)": [("any", SO)],
    "Opus (any)": [("any", OP)],
    "Sonnet, high only": [("hi", SO)],
    "Opus, high only": [("hi", OP)],
    # cascades on Claude's confidence
    "Sonnet high -> Opus high": [("hi", SO), ("hi", OP)],
    # cross-checks across families
    "Flash + Sonnet agree": [("agree", F, SO)],
    "Flash + Sonnet agree (Sonnet high)": [("agree_hi", F, SO)],
    "Flash + Sonnet agree -> Opus high": [("agree", F, SO), ("hi", OP)],
    "Flash + Sonnet agree (Sonnet high) -> Opus high": [("agree_hi", F, SO), ("hi", OP)],
    "Argon + Sonnet agree -> Opus high": [("agree", AR, SO), ("hi", OP)],
    "Sonnet high -> Flash + Opus agree": [("hi", SO), ("agree", F, OP)],
    "Sonnet + Opus agree": [("agree", SO, OP)],
    # kind-gated: the cheap model settles the strong kinds, the rest climbs
    "Flash strong kinds -> Opus high": [("kinds", F), ("hi", OP)],
    "Flash strong kinds -> Flash + Sonnet agree (Sonnet high) -> Opus high": [("kinds", F), ("agree_hi", F, SO),
                                                                             ("hi", OP)],
    "Flash strong kinds -> Sonnet high -> Opus high": [("kinds", F), ("hi", SO), ("hi", OP)],
}


def costs():
    """Measured Batch USD per answer, by model and domain."""
    G = {g["id"]: g for g in S.jl(OUT / "gold71.jsonl")}
    C = {}
    for m in S.MODELS:
        acc = {}
        for r in S.answers(m).values():
            if r["mode"] == "batch":
                acc.setdefault(G[r["id"]]["domain"], []).append(r["usd"])
        if acc:
            C[m] = {d: sum(v) / len(v) for d, v in acc.items()}
    return C


def lab_of(r):
    """score71's label without its domain prefix (works labels are bare; institution labels 'aff:...', 'merge:...')."""
    return r.get("lab", "")


def run_design(steps, ids, G, R, CO):
    applied, spent = {}, 0.0
    reached = [0] * len(steps)
    for i in ids:
        dom = G[i]["domain"]
        asked = set()
        for k, st in enumerate(steps):
            reached[k] += 1
            kind, *ms = st
            for m in ms:
                if m not in asked:
                    asked.add(m)
                    spent += CO.get(m, {}).get(dom, 0)
            r = [R[m].get(i) or {} for m in ms]
            if kind == "kinds":
                ok = r[0].get("dec") and (dom, lab_of(r[0])) in STRONG
            elif kind == "any":
                ok = r[0].get("dec")
            elif kind == "hi":
                ok = r[0].get("dec") and r[0].get("conf") == "high"
            else:
                ok = r[0].get("dec") and r[1].get("dec") and S.same_answer(i, ms[0], ms[1]) and \
                    (kind == "agree" or r[1].get("conf") == "high")
            if ok:
                applied[i] = (r[-1]["ok"], r[-1]["lenient"], k)
                break
    n, a = len(ids), list(applied)
    c = sum(1 for i in a if applied[i][0])
    cl = sum(1 for i in a if applied[i][1])
    w = sum(G[i]["w"] for i in a)
    wc = sum(G[i]["w"] for i in a if applied[i][0])
    return dict(n=n, applied=len(a), correct=c, precision=round(c / len(a), 4) if a else None,
                wilson_lo=round(S.wilson_lo(c, len(a)), 4), lenient=round(cl / len(a), 4) if a else None,
                w_precision=round(wc / w, 4) if w else None, applied_share=round(len(a) / n, 3),
                human_share=round(1 - len(a) / n, 3), usd_per_1000=round(1000 * spent / n, 3),
                reached=[round(x / n, 3) for x in reached],
                errors=sorted(i for i in a if not applied[i][0]))


def scale(CO, plan):
    s62 = json.load(open(E / "62_librarian_works" / "out" / "scale62.json"))["estimates"]
    s56 = json.load(open(E / "56_librarian_institutions" / "out" / "scale56.json"))["estimates"]
    e = s56["edu_162816_rules_first"]
    per_art = (e["packets_to_model"] + e["institution_questions_to_model"]) / 162816
    out = {}
    for name, key, docs in (("gate2 (3,460)", "gate2_3460", 3460), ("education (162,816)", "edu_162816", 162816),
                            ("1M documents", "docs_1M", 1000000)):
        w = s62[key]
        lo = sum(w["lower_bound_pairs_per_card"]["questions_to_model"].values())
        hi = sum(w["rules_first"]["questions_to_model"].values())
        if name.startswith("1M"):
            inst = s56["docs_1M_rules_first"]["packets_to_model"] + s56["docs_1M_rules_first"]["institution_questions_to_model"]
        else:
            inst = round(per_art * docs)
        row = dict(documents=docs, works_questions=[lo, hi], institution_questions=inst, designs={})
        for d, (cw, ci, hw, hi_) in plan.items():
            row["designs"][d] = dict(usd=[round((lo * cw + inst * ci) / 1000, 2), round((hi * cw + inst * ci) / 1000, 2)],
                                     to_human=[round(lo * hw + inst * hi_), round(hi * hw + inst * hi_)])
        out[name] = row
    return out


def main():
    G = S.load_gold()
    R = json.load(open(OUT / "scores71.json"))["rows"]
    CO = costs()
    res = dict(cost_per_answer=CO, designs={})
    for scope in ("judgement", "all"):
        for dom in ("works", "institutions", "both"):
            ids = [i for i, g in G.items() if (scope == "all" or not g["rule"]) and (dom == "both" or g["domain"] == dom)]
            res["designs"][f"{scope}|{dom}"] = {d: run_design(st, ids, G, R, CO) for d, st in DESIGNS.items()}
    # scale on the judgement scope: per-domain cost per 1000 and human share
    plan = {}
    for d in DESIGNS:
        jw, ji = res["designs"]["judgement|works"][d], res["designs"]["judgement|institutions"][d]
        plan[d] = (jw["usd_per_1000"], ji["usd_per_1000"], jw["human_share"], ji["human_share"])
    res["scale"] = scale(CO, plan)
    (OUT / "simulate71.json").write_text(json.dumps(res, indent=1), encoding="utf-8")
    for key, D in res["designs"].items():
        print(f"\n--- {key}")
        for d, v in D.items():
            print(f"  {d:50s} applied {v['applied']:3d}/{v['n']:3d} ({v['applied_share']:.2f})  P {v['precision']}  "
                  f"lo {v['wilson_lo']}  lenient {v['lenient']}  wP {v['w_precision']}  ${v['usd_per_1000']}/1000  "
                  f"reach {v['reached']}  err {v['errors'][:6]}")
    print(json.dumps(res["scale"], indent=1)[:4000])


if __name__ == "__main__":
    main()
