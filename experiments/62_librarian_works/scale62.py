"""Experiment 62, step 7: what the cited-works librarian would cost at scale (no API call: sizes measured on disk,
tokens estimated from characters with a stated ratio, prices as in experiment 56).

Measured on the 780 articles: packets by kind, decisions, how many the proposing rule settled (trivial) and how many
needed judgement, characters of evidence in and decision out; how cards, distinct works (after the librarian) and
candidate pairs grow with articles (random subsets of the 780).

Estimated: tokens per packet, per 1,000 articles, for gate 2 (3,460 articles), the education slice (162,816) and
1M documents, two ways:
- `rules_first`: code settles what it settled here (the trivial share), the model reads the rest;
- `rules_first_authority`: as above, and a citation whose card already joins a known work by rule is not asked
  again (catalogue and split questions are asked once per distinct work, not once per card);
- `lower_bound_pairs_per_card`: as above with pair questions growing like cards (the rate of the 780), the bound if
  blocking keeps candidate pairs per card flat at scale. The other two let pairs grow as fitted (n^1.39): an upper
  bound.

    python3 scale62.py   -> out/scale62.json
"""
from __future__ import annotations

import json
import math
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

HERE = Path(__file__).resolve().parent
OUT = HERE / "out"
sys.path.insert(0, str(HERE))

CHARS_PER_TOKEN = 2.5        # assumption (as exp 56): Arabic-heavy JSON; not measured
CHARS_PER_TOKEN_RANGE = (2.0, 3.5)
INSTRUCTIONS_TOKENS = 5000   # assumption: librarian instructions + the decision schema, cached across calls
TOOL_TOKENS = 1500           # assumption: per judged packet, tool look-ups (body text, a catalogue search) read back
OUTPUT_OVERHEAD = 1.5        # assumption: thinking/format tokens beyond the decision JSON itself
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20), "claude-haiku-4-5": (1.0, 5.0, 0.10)}
TARGETS = {"gate2_3460": 3460, "edu_162816": 162816, "docs_1M": 1_000_000}


def fit(curve):
    xs = [math.log(n) for n, _ in curve]
    ys = [math.log(max(v, 1e-9)) for _, v in curve]
    m = len(xs)
    b = (m * sum(x * y for x, y in zip(xs, ys)) - sum(xs) * sum(ys)) / (m * sum(x * x for x in xs) - sum(xs) ** 2)
    a = math.exp(sum(ys) / m - b * sum(xs) / m)
    return a, b


def main():
    from finalize62 import UF, standing
    D = standing()
    cards = {json.loads(l)["cited_work_id"]: json.loads(l) for l in open(OUT / "cards62.jsonl", encoding="utf-8")}
    P = [json.loads(l) for l in open(OUT / "packets62.jsonl", encoding="utf-8")]
    pairs = [json.loads(l) for l in open(OUT / "pairs62.jsonl", encoding="utf-8")]
    arts = json.loads((OUT / "articles62.json").read_text(encoding="utf-8"))
    n_articles = len(arts)
    mean = lambda x: sum(x) / max(1, len(x))  # noqa: E731

    by_level = defaultdict(list)
    for d in D:
        by_level[d["level"]].append(d)
    lv = {}
    for lvl, ds in by_level.items():
        tr = [d for d in ds if d.get("trivial")]
        ju = [d for d in ds if not d.get("trivial")]
        lv[lvl] = dict(decisions=len(ds), trivial=len(tr), judgement=len(ju),
                       trivial_share=round(len(tr) / len(ds), 3),
                       evidence_chars=dict(mean=round(mean([d["size"]["evidence_chars"] for d in ds])),
                                           judged_mean=round(mean([d["size"]["evidence_chars"] for d in ju]))),
                       decision_chars=round(mean([d["size"]["decision_chars"] for d in ds])),
                       by_kind=dict(Counter(d["kind"] for d in ds)),
                       by_basis=dict(Counter(d["basis"] for d in ds)))

    # growth with articles: cards, distinct works after the librarian, candidate pairs (both cards in the subset)
    uf = UF()
    for d in D:
        if d["level"] == "pair" and d["kind"] in ("same_work", "edition_of"):
            uf.union(*d["subject_keys"])
    drop = {d["subject_keys"][0] for d in D if d["level"] == "card" and d["kind"] == "not_a_work"
            and d["decision"].get("action") == "drop"}
    stems_of = {cid: set(c["stems"]) for cid, c in cards.items()}
    cards_of = defaultdict(set)
    for cid, ss in stems_of.items():
        for s in ss:
            cards_of[s].add(cid)
    all_stems = sorted(arts)
    rnd = random.Random(62)
    cur_cards, cur_works, cur_pairs = [], [], []
    for n in (100, 200, 300, 400, 500, 600, 700, n_articles):
        vc, vw, vp = [], [], []
        for _ in range(12):
            s = set(rnd.sample(all_stems, n))
            cs = set().union(*[cards_of.get(x, set()) for x in s])
            vc.append(len(cs))
            vw.append(len({uf.find(c) for c in cs if c not in drop}))
            vp.append(sum(1 for p in pairs if p["a"] in cs and p["b"] in cs))
        cur_cards.append((n, mean(vc)))
        cur_works.append((n, mean(vw)))
        cur_pairs.append((n, mean(vp)))
    fc, fw, fp = fit(cur_cards), fit(cur_works), fit(cur_pairs)

    tok = lambda c: c / CHARS_PER_TOKEN  # noqa: E731
    per_q = {}
    for lvl, x in lv.items():
        per_q[lvl] = dict(input=round(tok(x["evidence_chars"]["judged_mean"]) + TOOL_TOKENS),
                          output=round(tok(x["decision_chars"]) * OUTPUT_OVERHEAD))
    # questions per level, measured here, and how each grows
    q_here = {lvl: lv[lvl]["decisions"] for lvl in lv}
    judged_share = {lvl: 1 - lv[lvl]["trivial_share"] for lvl in lv}
    # pair questions grow like candidate pairs; card and catalogue questions like cards (per card) or like
    # distinct works (with a work authority)
    def questions(n_docs, authority, pairs_linear=False):
        cards_n = fc[0] * n_docs ** fc[1]
        works_n = fw[0] * n_docs ** fw[1]
        pairs_n = fp[0] * n_docs ** fp[1]
        q = {}
        q["pair"] = q_here["pair"] * (cards_n / cur_cards[-1][1] if pairs_linear else pairs_n / cur_pairs[-1][1])
        base = works_n / cur_works[-1][1] if authority else cards_n / cur_cards[-1][1]
        q["card"] = q_here["card"] * base
        q["catalogue"] = q_here["catalogue"] * base
        return q, cards_n, works_n, pairs_n

    def estimate(n_docs, authority, pairs_linear=False):
        q, cards_n, works_n, pairs_n = questions(n_docs, authority, pairs_linear)
        model_q = {lvl: q[lvl] * judged_share[lvl] for lvl in q}
        tin = sum(model_q[l] * per_q[l]["input"] for l in q)
        tout = sum(model_q[l] * per_q[l]["output"] for l in q)
        calls = sum(model_q.values())
        cached = calls * INSTRUCTIONS_TOKENS
        cost = {m: round((tin / 1e6 * pi + tout / 1e6 * po + cached / 1e6 * pc) * 0.5)
                for m, (pi, po, pc) in PRICES.items()}
        lo_hi = {m: [round(cost[m] * CHARS_PER_TOKEN / CHARS_PER_TOKEN_RANGE[1]),
                     round(cost[m] * CHARS_PER_TOKEN / CHARS_PER_TOKEN_RANGE[0])] for m in cost}
        return dict(documents=n_docs, cards_est=round(cards_n), distinct_works_est=round(works_n),
                    candidate_pairs_est=round(pairs_n), questions=dict((k, round(v)) for k, v in q.items()),
                    questions_to_model=dict((k, round(v)) for k, v in model_q.items()),
                    input_tokens=round(tin), output_tokens=round(tout), cached_instruction_tokens=round(cached),
                    usd_batch_list_price=cost, usd_range_chars_per_token=lo_hi)

    rep = dict(
        measured=dict(articles=n_articles, cards=len(cards), packets=dict(Counter(p["kind"] for p in P)),
                      decisions=len(D), levels=lv, candidate_pairs=len(pairs),
                      growth=dict(cards=cur_cards, distinct_works=cur_works, candidate_pairs=cur_pairs),
                      fits=dict(cards=[round(fc[0], 3), round(fc[1], 3)], distinct_works=[round(fw[0], 3), round(fw[1], 3)],
                                candidate_pairs=[round(fp[0], 4), round(fp[1], 3)]),
                      fits_note="value ≈ a·n^b over random subsets of the 780 (12 draws per size)"),
        assumptions=dict(chars_per_token=CHARS_PER_TOKEN, range=CHARS_PER_TOKEN_RANGE,
                         instructions_tokens_cached=INSTRUCTIONS_TOKENS, tool_tokens_per_judged_packet=TOOL_TOKENS,
                         output_overhead=OUTPUT_OVERHEAD, prices=PRICES,
                         prices_note="list prices as in experiment 56 (claude-api skill table, cached 2026-09-25); "
                                     "Batch API 50% off; check the console before spending",
                         extrapolation_note="the pair-question exponent is fitted on 100-780 articles; past ~10^4 "
                                            "documents candidate pairs are bounded by the blocking (rare words only, "
                                            "clusters cut at 12 cards), so the 1M figure is an upper bound"),
        per_judged_question_tokens=per_q,
        per_1000_articles=dict((k, estimate(1000, True)[k]) for k in ("questions", "questions_to_model", "input_tokens",
                                                                       "output_tokens", "usd_batch_list_price")),
        estimates={name: dict(rules_first=estimate(n, False), rules_first_authority=estimate(n, True),
                              lower_bound_pairs_per_card=estimate(n, True, True))
                   for name, n in TARGETS.items()},
        grows_with=dict(
            documents=["cards (one per full citation or short form standing alone): ~11.7 per article",
                       "not-a-work and split questions, per card, unless a work authority answers them once per work",
                       "catalogue questions, per card, unless asked once per distinct work"],
            distinct_works=["the work authority itself", "catalogue questions with an authority",
                            f"distinct works ≈ {fw[0]:.2f}·n^{fw[1]:.2f} on the 780: almost linear here, because most "
                            "works are cited once; sharing grows only in a field's own journals"],
            candidate_pairs=[f"pair questions ≈ {fp[0]:.4f}·n^{fp[1]:.2f}: faster than linear (every new card meets "
                             "the cards already there), bounded at scale by the blocking"]))
    (OUT / "scale62.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(dict(levels={k: {x: v[x] for x in ("decisions", "trivial", "judgement", "evidence_chars",
                                                        "decision_chars")} for k, v in lv.items()},
                          fits=rep["measured"]["fits"], per_q=per_q, per_1000=rep["per_1000_articles"],
                          est={k: {m: v[m]["usd_batch_list_price"] for m in v} for k, v in rep["estimates"].items()},
                          q={k: v["rules_first_authority"]["questions_to_model"] for k, v in rep["estimates"].items()}),
                     ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
