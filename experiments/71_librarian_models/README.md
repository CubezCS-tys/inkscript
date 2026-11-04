# 71: which model should be the production librarian?

## Question

Experiments 56 (institutions) and 62 (cited works) had Claude, working as an agent and making no API calls, act as
the librarian. Experiment 63 and the blind rounds of 62 then verified its decisions.

For production the librarian has to be an API model. The questions are:
- Which model, or which combination?
- At what precision, per kind of decision, against the 98% apply bar?
- At what cost per 1,000 decisions, and how many decisions go to a human?
- What does a cross-check between model families add?

Owner-approved, cap $10 (Gemini ≤ $6, Anthropic ≤ $4).

## Answer

**No single model clears 98% on the questions rules cannot settle if it answers everything.** On those 243
judgement items the best is Opus 5.5 at 95.2%; Flash 3.8 and Argon are at 93.2%.

**Two things do clear it:**
1. **Claude's own confidence.** Claude's "high" is calibrated:
   - over all 522 items: Sonnet 5.5 99.4% on 68% of them, Opus 5.5 99.0% on 80%;
   - on the judgement items: 98.4% and 98.8%.

   Gemini's "high" is not calibrated: Flash and Argon say high on about 99% of their answers, and the precision is
   the same as without the filter.
2. **The kind of answer.** For eight kinds every model is at or near 100%: a catalogue record that IS the cited
   work, different works, a card that is fine, a card split, a country, two rows that are one body, a parent, and
   not-an-institution.

**Recommended production librarian (tiered):**
1. Rules first (experiments 62/63).
2. **Flash 3.8 (thinking low) on every model question.** Its answer is applied only for the eight strong kinds.
3. **Everything else goes to Opus 5.5 (effort medium).** Its answer is applied when it says high.
4. **The rest goes to the Desk.**

Measured on the gold:

| scope | precision (Wilson 95% lower bound) | lenient | to a human | cost |
|---|---|---|---|---|
| judgement items | 98.9% (96.0%) | 99.4% | 26% | $3.37 per 1,000 questions |
| all items | 99.1% (97.7%) | 99.8% | 17% | $2.97 per 1,000 |

**Cross-check:** where Flash and Sonnet give the same answer and Sonnet says high, precision is 99.7% (Wilson lower
bound 98.4%) on two thirds of all items, for $2.59 per 1,000. This is the cheapest check across two model families,
and the one to use where an independent second opinion matters.

**Caveat, read first:** the gold was made by Claude. Exp 62's librarian and its blind judge are this same model
(Opus 5.5), and so is exp 63's blind judge. So Claude, and Opus above all, may agree with the gold through shared
habits rather than shared truth (see "Is the gold wrong?").

## Gold (`gold71.py` → `out/gold71.jsonl`)

Only verified answers are used:

- **Cited works (exp 62): all 316 decisions of the two blind rounds.**
  - Where the blind judge agreed, the gold is the librarian's answer (both labels when the round counted
    same_work ≈ edition_of as agreement: 3 items).
  - Where they disagreed, the gold is the adjudicated verdict.
  - Where the adjudication said "both defensible", both answers are accepted.
- **Institutions (exp 63): the 206 blind-sampled decisions where the blind re-decision agreed with exp 56.** Left out:
  - set_type (blind agreement 25%: the type list cannot hold the answer);
  - the 14 "exp 56 conservative" cases (both answers defensible; the blind one is only free text);
  - the 2 minor errors.
- **The strata are the experiments' own, which oversample the hard kinds:**
  - every medium and low institution stratum is taken whole;
  - unsure, edition_of, split and no_link are drawn far above their share.
- **Weighted precisions** reweight each stratum to its population (scale62 / sample63 counts).

| domain | decision kind (librarian's) | items |
|---|---|---|
| works | pair: same_work / edition_of / different_work / unsure | 65 / 15 / 25 / 4 |
| works | card: card_ok / split_card / not_a_work (with the action: drop 8, retitle 26, one per citation 1) | 10 / 10 / 35 |
| works | catalogue: links_to_publication / relation / no_link | 130 / 12 / 10 |
| institutions | affiliation → institution / not an institution / unit kept apart / unsure | 102 / 14 / 2 / 8 |
| institutions | same institution / split a row / set country / set parent | 13 / 8 / 36 / 23 |
| | **total** (rule-proposed 279, judgement 243) | **522** |

## Packets (the tools run first; same packet for every model)

**Works.** Exp 62's blind packets (`blind62.py`, built from `tools62.py`), unchanged:
- the card or cards, with every printed citation, its note, and the article text before the note call;
- the catalogue record (title, subtitle, authors, year, type, journal).

**Institutions.** Exp 63's blind views of exp 56's packets:
- the printed statement and its parts;
- the article, journal and year, and the author;
- the same author's other statements;
- the machine rows and the catalogue hits.

Added to these:
- the journal's publisher and country from the release (as exp 63's judge had it);
- for affiliation, merge and parent questions, **8 authority candidates**. These come from a trigram retriever over
  the authority's names (and its printed forms used twice or more). Each card shows only id, Arabic/English name,
  type, country and parent. Printed forms, articles and counts are never shown, because they were written from the
  decisions under test.
- **The retriever missed the gold body in 35 of 160 questions.** These are faculties printed without their
  university, where only world knowledge links them. In those questions the gold body was put among the 8 (sorted by
  id, so nothing marks it). Production will need a better candidate finder (city, e-mail domain, journal publisher).

**Never in a packet:** the decision, its reason, its rule, its confidence, or the question key. I read a dozen
packets of both domains in full before sending.

**Instruction** (`prompt71.py`, version 71.1): one system text with the house rules of exps 56/62 and a fixed JSON
schema: answer, ids, country, groups, confidence (high / medium / low) and a one-line reason. Unsure is allowed and
encouraged.

**Settings:**
- Gemini: `responseSchema`, thinking low (the pipeline's setting), plus a Flash run at thinking high.
- Claude: `output_config.format` (json_schema), adaptive thinking at effort medium, with the system prompt cached.

## Runs (`run71.py`)

| model | mode | answers | spend |
|---|---|---|---|
| gemini-3.8-flash (newest Flash in the API's list, 2026-11-02), thinking low | 12 Standard + 1 Batch job | 522 | $0.41 |
| gemini-3.8-flash, thinking high | 12 Standard + 3 Batch jobs | 522 | $1.42 |
| gemini-4-argon, thinking low | 12 Standard + 2 Batch jobs | 522 | $1.17 |
| gemini-4-argon, thinking high | 12 Standard (pilot only) | 12 | $0.27 |
| claude-sonnet-5-5, effort medium | 12 Standard + 2 Batch | 522 | $0.98 |
| claude-opus-5-5, effort medium | 12 Standard + 5 Batch | 522 | $2.21 |
| **total** | | | **$6.47** (Gemini $3.27 of 6, Anthropic $3.19 of 4) |

**Argon at thinking high was stopped at the pilot.** Two of its 12 answers spent 7–8k thinking tokens and one ran
out of room with no answer. That is about $10 per 1,000 at Batch: not a production candidate.

**How spend was capped:** every answer is a row of `out/spend71.jsonl`. A Batch job was refused unless the logged
spend plus its worst case (every answer at maximum output) stayed under the provider's cap, so the jobs went out in
chunks.

## Results (`score71.py`, `tables71.py`)

**Definitions:**
- **decided** = the model did not answer unsure.
- **precision** = right / decided. For institutions, right means the status AND the authority ids; the country
  agreed every time the ids did.
- **lenient** = right about what happens to the index: same_work ≈ edition_of (both join the cards), and any
  not-a-work action counts.
- **coverage** = decided / items whose gold is not unsure.

### Overall (all 522)

| model | decided | precision | weighted | lenient | coverage | says high | precision at high | Batch $ / 1,000 | tokens in / out |
|---|---|---|---|---|---|---|---|---|---|
| Flash 3.8 (think low) | 514 | 94.9% | 96.7% | 96.9% | 98.8% | 508 | 95.9% | **$0.77** | 1276 / 154 |
| Flash 3.8 (think high) | 511 | 96.3% | 97.0% | 97.7% | 99.0% | 508 | 96.7% | $2.63 | 1276 / 1148 |
| Argon (think low) | 515 | 95.5% | 97.1% | 97.1% | 99.4% | 507 | 96.1% | $2.18 | 1611 / 114 |
| Sonnet 5.5 | 502 | 93.2% | 96.3% | 95.4% | 97.1% | 354 | **99.4%** | $1.82 | 945 / 148 |
| Opus 5.5 | 507 | **97.0%** | **97.9%** | 98.0% | 98.4% | 418 | 99.0% | $4.11 | 945 / 196 |

| | works, rule-proposed | works, judgement | institutions, rule | institutions, judgement |
|---|---|---|---|---|
| Flash (low) | 95.2% | 93.3% | 100% | 93.1% |
| Flash (high) | 97.6% | 91.4% | 100% | 96.1% |
| Argon | 97.1% | 92.5% | 98.6% | 93.8% |
| Sonnet | 96.2% | 90.2% | 100% | 87.1% |
| Opus | 98.1% | 94.2% | 100% | 96.0% |

**Latency:**
- Standard calls, median per answer: Sonnet 2.0 s, Flash 2.7 s, Opus 3.4 s, Flash-high 6.1 s, Argon 7.1 s.
- Batch, whole jobs:
  - Gemini: 2.5–7 minutes per job (148–423 s);
  - Anthropic: 6–7 minutes (365–450 s), and one Sonnet job took 41 minutes.

### Precision per answer kind (what an apply rule sees; ✓ = ≥ 98% on 10+ answers)

| answer | Flash (low) | Flash (high) | Argon | Sonnet | Opus |
|---|---|---|---|---|---|
| links_to_publication | 125/125 ✓ | 125/126 ✓ | 125/125 ✓ | 123/124 ✓ | 125/125 ✓ |
| different_work | 25/25 ✓ | 26/27 | 26/26 ✓ | 26/26 ✓ | 25/25 ✓ |
| same_work | 60/65 92% | 62/65 95% | 65/69 94% | 62/70 89% | 66/69 96% |
| edition_of | 13/15 87% | 13/13 ✓ | 13/14 93% | 8/10 80% | 12/12 ✓ |
| relation | 18/20 90% | 19/22 86% | 19/22 86% | 17/20 85% | 18/20 90% |
| no_link | 4/6 | 3/4 | 4/5 | 4/5 | 4/6 |
| card_ok / split_card | 10/10 ✓ / 10/10 ✓ | 10/10 ✓ / 10/10 ✓ | 10/10 ✓ / 9/9 | 10/10 ✓ / 9/9 | 10/10 ✓ / 9/9 |
| not a work: retitle / drop | 23/24 / 7/10 | 23/24 / 7/10 | 23/24 / 7/10 | 25/26 / 6/6 | 25/26 / 7/8 |
| affiliation resolved | 100/108 93% | 100/102 ✓ | 101/106 95% | 92/98 94% | 100/102 ✓ |
| affiliation not an institution | 12/12 ✓ | 12/13 | 12/12 ✓ | 12/13 | 12/12 ✓ |
| unit only (faculty without university) | 1/2 | 2/3 | 1/2 | 2/7 | 2/3 |
| set country | 35/35 ✓ | 35/35 ✓ | 35/35 ✓ | 34/34 ✓ | 35/35 ✓ |
| rows are one body | 13/13 ✓ | 13/13 ✓ | 13/13 ✓ | 12/13 | 13/13 ✓ |
| set parent | 20/20 ✓ | 21/21 ✓ | 20/21 | 16/17 | 21/21 ✓ |
| a row holds several bodies | 7/7 | 7/7 | 6/6 | 7/7 | 5/5 |

**At confidence high only:**
- Sonnet passes same_work (38/38), not-a-work retitle (17/17), affiliation resolved (70/70) and links (112/112).
- Opus passes affiliation resolved (77/77), relation (12/12) and retitle (17/17).
- Gemini's high changes nothing.

**Kinds no model can be trusted with alone:**
- "unit only";
- no_link versus relation;
- the not-a-work action (drop versus retitle);
- part_of.

### Cross-model agreement (all 522)

| pair | both decided | agree | precision when they agree | disagreements: A right / B right | A's errors flagged by the pair |
|---|---|---|---|---|---|
| Flash (low) + Sonnet | 501 | 462 | 98.5% | 23 / 13 | 19 of 26 |
| Flash (low) + Opus | 506 | 482 | 98.6% | 10 / 16 | 19 of 26 |
| Flash (high) + Sonnet | 499 | 460 | 98.9% | 27 / 12 | 14 of 19 |
| Flash (low) + Argon | 511 | 490 | 97.5% | 10 / 12 | 14 of 26 |
| Sonnet + Opus | 495 | 462 | 98.7% | 9 / 26 | 28 of 34 |

- **Two Gemini models catch each other least.** Flash and Argon agree on 490 and are 97.5% right when they do: they
  share their mistakes.
- **A Claude check on Flash flags about 3 in 4 of Flash's errors**, by disagreeing or by saying unsure. The cost is
  the 8% of items where the two disagree, and those go up a tier or to the Desk.
- **Requiring Sonnet's high on top of the agreement** gives 99.7% (351 items; Wilson lower bound 98.4%).

### The production rule, simulated (`simulate71.py`)

The designs were fixed before looking at which kinds pass. Only the "strong kinds" list was read off this gold: every
kind in it is at or near 100% for at least four of the five models, and at 100% for Flash.

The cost is what each step actually asks (Batch, measured).

**On the 243 judgement items** (what a model gets in production, after the rules):

| design | applied | precision (Wilson lo) | lenient | to a human | $ / 1,000 |
|---|---|---|---|---|---|
| Flash, applies everything | 236 | 93.2% (89.3%) | 94.1% | 3% | $0.78 |
| Opus, applies everything | 229 | 95.2% (91.6%) | 95.6% | 6% | $4.40 |
| Sonnet, high only | 122 | 98.4% (94.2%) | 98.4% | 50% | $1.94 |
| Opus, high only | 166 | 98.8% (95.7%) | 99.4% | 32% | $4.40 |
| Sonnet high → Opus high | 173 | 97.7% (94.2%) | 98.3% | 29% | $4.13 |
| Flash + Sonnet agree | 200 | 97.5% (94.3%) | 98.5% | 18% | $2.72 |
| Flash + Sonnet agree (Sonnet high) | 120 | **99.2%** (95.4%) | 99.2% | 51% | $2.72 |
| Flash + Sonnet agree → Opus high | 208 | 97.6% (94.5%) | 98.6% | 14% | $3.55 |
| **Flash strong kinds → Opus high** | 179 | **98.9%** (96.0%) | **99.4%** | 26% | **$3.37** |
| Flash strong kinds → Sonnet high → Opus high | 183 | 98.4% (95.3%) | 98.9% | 25% | $3.51 |

**Per domain** (judgement items), Flash strong kinds → Opus high:
- works 81/106 applied at 97.5% (lenient 98.8%);
- institutions 98/137 at 100%.

**The works that remain wrong are label boundaries, not false joins:**
- same_work versus edition_of (W1-B031);
- relation versus no_link (W1-B152).

**On all 522 items:**

| design | applied | precision | to a human | $ / 1,000 |
|---|---|---|---|---|
| Flash strong kinds → Opus high | 435 | 99.1% (97.7%) | 17% | $2.97 |
| Flash + Sonnet agree (Sonnet high) | 351 | 99.7% (98.4%) | 33% | $2.59 |
| Opus, high only | 418 | 99.0% (97.6%) | 20% | $4.11 |

**Adding a Sonnet step before Opus is not cheaper.** Sonnet says high on only about half of the judgement questions,
so Opus is asked for the other half anyway.

### At scale

Questions that reach the model after the rules:
- **Works**, from exp 62's `scale62.json`. The low figure has pair questions growing like cards; the high figure
  uses the fitted n^1.39, an upper bound past 10^4 documents.
- **Institutions**, from exp 56's `scale56.json`: affiliation packets plus institution questions, at the 780's
  density. Gate 1's education journal prints twice as many affiliations.

Both are multiplied by the measured Batch cost.

| scale | questions to the model (works; institutions) | Flash alone (93% on judgement) | **Flash strong kinds → Opus high** | to a human, same design |
|---|---|---|---|---|
| gate 2 (3,460 articles) | 3.4k–4.4k; 633 | $3–4 | **$13–16** | 1.0k–1.2k |
| education slice (162,816) | 168k–600k; 30k | $150–460 | **$620–1,950** | 48k–150k |
| 1M documents | 1.05M–6.9M; 163k | $900–5,200 | **$3.8k–21.7k** | 0.29M–1.67M |

- **The cost is small.** Exp 62 estimated Sonnet at $5 and Opus at $9 per 1,000 articles' questions. The measured
  answers are shorter than assumed (Sonnet $1.8, Opus $4.1 per 1,000 decisions).
- **The human queue is the real bill.** 26% of judgement questions do not clear 98%. At the education slice that is
  48k–150k decisions, mostly:
  - same_work versus edition_of: both join, so the join could be applied and the label proposed;
  - relation versus no_link: neither changes the work counts;
  - not-a-work drop versus retitle.

  Exp 62's rule for different_work also applies here: when a decision only labels or only holds things apart,
  applying it changes nothing, so it needs no review. The owner can cut the queue a good deal by deciding which of
  these boundaries need a human at all.

## Is the gold wrong? (the disagreements read)

**Where three or four of Flash-high, Argon, Sonnet and Opus agree against the gold** (10 items,
`out/consensus_vs_gold_ids.json`), I read the packets:
- **1: the gold is right.** W1-B009: two short «فتاوى ابن تيمية» citations; unsure stands.
- **9: both answers are defensible.** These are label boundaries:
  - same_work versus edition_of: W1-B031, B036, B040;
  - split_card versus not_a_work, for a journal-titled card holding several items: B070;
  - relation versus unsure, for the same text in another journal, which D44 now links: B122;
  - relation versus no_link, both called "weak" by the adjudication: B149, B153;
  - drop versus retitle, for an issue-only newspaper citation: B2141;
  - unsure versus not_institution, for «عضو مكتب الخبراء بالمكتب الفني»: I-S084.
- **0: the gold is plainly wrong.**

**Gemini's own errors that Claude does not share** are mostly two habits:
- **It almost never says unsure.** It resolves the gold's unsure affiliations with new bodies, such as «Higher
  institute of information Technology» → a Libyan institute, «مدير دائرة الأرصاد الجوية» → Jordan's met office. Some
  are fair guesses, but a guess is what the house rules forbid.
- **It drops one of two bodies** in a two-body affiliation (I-S012, I-S200).

**Claude's medium answers carry its errors**, which is why the high filter works.

**What this means for the precisions:**
- The ~3% "errors" of the better models are largely conventions, not facts, so the lenient column is the better
  guide for joins.
- The Claude–gold agreement is the one number that may be inflated, because Opus 5.5 made the gold.

## Recommendation for the production librarian

1. **Rules first**, unchanged: K1c links, C1 journal-name cards, P6 thesis versus article, and exp 56's printed-form
   rules with `hardchecks63.py`.
2. **Tier 1, Flash 3.8 (thinking low, Batch), on every question the rules leave.** Apply its answer only for the
   strong kinds:
   - links to a Mandumah record (the record IS the cited work);
   - different works;
   - card ok and card split;
   - set country;
   - rows are one body;
   - set parent;
   - affiliation names no body.
3. **Tier 2, Opus 5.5 (effort medium, Batch), on everything else.** Apply when it says high. Never apply unsure,
   part_of, unit-only, or a "new:" body without authority review.
4. **Tier 3, the Desk**, with both models' answers and reasons shown.
5. **Independent check without owner sampling:** each week, re-ask a random 2% of applied decisions to the other
   family (Sonnet on Flash's, Flash on Opus's) and treat a disagreement rate above about 5% as an alarm. On this gold
   a Flash–Claude disagreement flags about 3 of every 4 errors.
6. **Expected:**

   | scale | precision of what is applied | to a human | cost |
   |---|---|---|---|
   | gate 2 | ~99% (judgement items 98.9%, Wilson lower bound 96%) | about 1,100 | $13–16 |
   | education slice | ~99% | 48k–150k before any policy on the label boundaries | $620–1,950 |
   | 1M documents | ~99% | | $3.8k–21.7k |

**Cheaper variant:** if the owner prefers the cross-family guarantee to Opus, use **Flash + Sonnet agree with Sonnet
high** instead of tier 2. It gives 99.7% on what it applies for $2.59 per 1,000, but sends about a third of
everything to the Desk.

**Not recommended:**
- **Argon:** no better than Flash at 2.8× the price; its confidence carries nothing; at high thinking its answer
  length is erratic.
- **Flash at thinking high:** +1.3 points for 3.4× the cost.
- **Sonnet alone:** worst at "any" (93.2%); it is good only through its confidence.

## Files

Scripts:
- `gold71.py`: the gold and the packets;
- `prompt71.py`: the one instruction and the schema;
- `run71.py`: count / pilot / batch / collect, with the cap guard and spend log;
- `score71.py`: precision, coverage, by kind, cross-model agreement;
- `simulate71.py`: designs and scale;
- `tables71.py`: these tables.

Outputs in `out/` (gitignored):
- `gold71.jsonl`, `packets71.jsonl`;
- `answers/<model>.jsonl`, `spend71.jsonl`, `batch_state71.json`, `batch/`;
- `scores71.json`, `disagree71_<model>.jsonl`, `simulate71.json`, `tables71.md`;
- `consensus_vs_gold_ids.json`.

Notes as the work went: `progress.md`.

Re-run with no calls: `python3 score71.py && python3 simulate71.py && python3 tables71.py`.

## What it changed

Nothing in `src/`, the platform database, the Desk, releases or experiment 70. It answers which model the
production librarian should use and how to tier it; wiring it in is the next step.
