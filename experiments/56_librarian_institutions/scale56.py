"""Experiment 56, step 6: what the librarian pass would cost at scale (no API call: sizes measured on disk, tokens
estimated from characters with a stated ratio).

Measured here: packets, decisions, trivial vs judgement, characters of evidence in and decision out per packet; how
distinct institutions grow with articles (random subsets of the 780, the librarian's authority). Estimated: tokens per
packet and per 1,000 articles, then for 162,816 education articles and for 1M documents.

    python3 scale56.py   -> out/scale56.json
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
import judge56 as J  # noqa: E402
from decisions56 import latest, packet_text  # noqa: E402

CHARS_PER_TOKEN = 2.5        # assumption: Arabic-heavy JSON; not measured (count_tokens is an API call, not used)
CHARS_PER_TOKEN_RANGE = (2.0, 3.5)
INSTRUCTIONS_TOKENS = 4000   # assumption: the fixed librarian instructions + output schema, cached across calls
CANDIDATES = 8               # assumption: authority entries retrieved per packet (by name tokens / country) at scale
# Claude API list prices (USD per 1M tokens, the claude-api skill's table cached 2026-09-25); batch = 50% off;
# cache reads ~0.1x input (Opus 5.5: $0.20)
PRICES = {"claude-opus-5-5": (4.0, 20.0, 0.20), "claude-sonnet-5-5": (2.0, 10.0, 0.20), "claude-haiku-4-5": (1.0, 5.0, 0.10)}
OUTPUT_OVERHEAD = 1.5        # assumption: thinking/format tokens beyond the decision JSON itself


def main():
    P = J.load_packets()
    ov = J.load_overrides()
    V = {p["key"]: J.judge(p, ov) for p in P}
    L = [d for d in latest().values() if d["kind"] != "retired"]
    aff = [d for d in L if d["level"] == "affiliation"]
    inst = [d for d in L if d["level"] == "institution"]
    ev = [len(packet_text(p)) for p in P]
    dec = [d["size"]["decision_chars"] for d in aff if d.get("size")]
    idec = [d["size"]["decision_chars"] for d in inst if d.get("size")]
    auth_entry = [len(json.dumps({k: a[k] for k in ("id", "type", "country", "name_ar", "name_en", "forms", "parent")},
                                 ensure_ascii=False)) for a in J.AUTH.values()]
    mean = lambda x: sum(x) / max(1, len(x))  # noqa: E731
    stems = sorted({p["stem"] for p in P})
    n_articles = 780
    # growth of distinct institutions with articles (librarian authority), random subsets of the 780
    orgs_of = defaultdict(set)
    for p in P:
        v = V[p["key"]]
        if v["status"] == "resolved":
            orgs_of[p["stem"]].update(v["orgs"])
    all_stems = [f"x{i}" for i in range(n_articles - len(stems))] + stems   # articles without affiliations count too
    rnd = random.Random(56)
    curve = []
    for n in (100, 200, 300, 400, 500, 600, 700, 780):
        vals = []
        for _ in range(20):
            s = rnd.sample(all_stems, n)
            vals.append(len(set().union(*[orgs_of.get(x, set()) for x in s])))
        curve.append((n, round(mean(vals), 1)))
    # fit distinct = a * n^b on the curve (Heaps' law)
    xs = [math.log(n) for n, _ in curve]
    ys = [math.log(v) for _, v in curve]
    b = (len(xs) * sum(x * y for x, y in zip(xs, ys)) - sum(xs) * sum(ys)) / (len(xs) * sum(x * x for x in xs) - sum(xs) ** 2)
    a = math.exp(mean(ys) - b * mean(xs))

    per_article_affs = len(P) / n_articles
    trivial_aff = sum(1 for d in aff if d["trivial"])
    nontrivial_aff = len(aff) - trivial_aff
    trivial_inst = sum(1 for d in inst if d["trivial"])
    tok = lambda c: c / CHARS_PER_TOKEN  # noqa: E731
    pkt_in_tokens = tok(mean(ev)) + tok(mean(auth_entry)) * CANDIDATES
    pkt_out_tokens = tok(mean(dec)) * OUTPUT_OVERHEAD
    inst_q_per_inst = len(inst) / max(1, len({o for v in V.values() for o in v["orgs"]}))

    def estimate(n_docs: int, model_share_aff: float) -> dict:
        affs = n_docs * per_article_affs
        distinct = a * n_docs ** b
        model_affs = affs * model_share_aff
        inst_qs = distinct * inst_q_per_inst * (1 - trivial_inst / max(1, len(inst)))
        tin = model_affs * pkt_in_tokens + inst_qs * (pkt_in_tokens * 2)      # an institution question reads ~2 packets
        tout = model_affs * pkt_out_tokens + inst_qs * tok(mean(idec)) * OUTPUT_OVERHEAD
        calls = model_affs + inst_qs
        cached = calls * INSTRUCTIONS_TOKENS
        cost = {m: round((tin / 1e6 * pi + tout / 1e6 * po + cached / 1e6 * pc) * 0.5, 0)        # batch: 50% off
                for m, (pi, po, pc) in PRICES.items()}
        return dict(documents=n_docs, affiliations=round(affs), distinct_institutions_est=round(distinct),
                    packets_to_model=round(model_affs), institution_questions_to_model=round(inst_qs),
                    input_tokens=round(tin), output_tokens=round(tout), cached_instruction_tokens=round(cached),
                    usd_batch_list_price=cost)
    rep = dict(
        measured=dict(
            articles=n_articles, packets=len(P), articles_with_affiliations=len(stems),
            affiliations_per_article=round(per_article_affs, 3),
            decisions=len(L), affiliation_decisions=len(aff), institution_decisions=len(inst),
            by_kind=dict(Counter(d["kind"] for d in L)),
            trivial=dict(affiliation=trivial_aff, affiliation_judgement=nontrivial_aff, institution=trivial_inst,
                         institution_judgement=len(inst) - trivial_inst),
            evidence_chars_per_packet=dict(mean=round(mean(ev)), median=sorted(ev)[len(ev) // 2], max=max(ev)),
            decision_chars_per_affiliation=round(mean(dec)), decision_chars_per_institution_question=round(mean(idec)),
            authority_entries=len(J.AUTH), authority_entry_chars=round(mean(auth_entry)),
            distinct_institutions_curve=curve, heaps_fit=dict(a=round(a, 3), b=round(b, 3))),
        assumptions=dict(chars_per_token=CHARS_PER_TOKEN, range=CHARS_PER_TOKEN_RANGE,
                         instructions_tokens_cached=INSTRUCTIONS_TOKENS, candidates_per_packet=CANDIDATES,
                         output_overhead=OUTPUT_OVERHEAD, prices=PRICES, prices_note="list prices from the claude-api "
                         "skill's table cached 2026-09-25; Batch API 50% off; check the console before spending",
                         affiliations_per_article="as in the 780 (0.84); education journals print more bylines and "
                         "affiliations (gate 1: 1.66 per article), so the 162,816 estimate also shows that case"),
        per_packet_tokens=dict(input=round(pkt_in_tokens), output=round(pkt_out_tokens)),
        per_1000_articles=dict(packets=round(1000 * per_article_affs),
                               tokens_all_to_model=round(1000 * per_article_affs * (pkt_in_tokens + pkt_out_tokens)),
                               tokens_judgement_only=round(1000 * per_article_affs * nontrivial_aff / len(aff) *
                                                           (pkt_in_tokens + pkt_out_tokens))),
        estimates=dict(
            edu_162816_all_to_model=estimate(162816, 1.0),
            edu_162816_rules_first=estimate(162816, nontrivial_aff / len(aff)),
            docs_1M_rules_first=estimate(1_000_000, nontrivial_aff / len(aff))),
        grows_with=dict(documents=["affiliation packets (0.84 per article here; 1.66 in gate 1's education journal)",
                                   "per-affiliation decisions and their tokens: linear"],
                        distinct_institutions=["authority entries", "same / split / country / parent / type questions",
                                               f"sub-linear in documents: distinct ≈ {a:.2f}·n^{b:.2f} on the 780"]))
    # the education-journal case: gate 1 prints ~2 affiliations per article
    j = sum(1 for p in P if p["journal_id"] == "J0130") / 126
    rep["measured"]["affiliations_per_article_gate1"] = round(j, 2)
    saved = per_article_affs
    per_article_affs = j
    rep["estimates"]["edu_162816_rules_first_gate1_density"] = estimate(162816, nontrivial_aff / len(aff))
    per_article_affs = saved
    (OUT / "scale56.json").write_text(json.dumps(rep, ensure_ascii=False, indent=1), encoding="utf-8")
    print(json.dumps(rep, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
