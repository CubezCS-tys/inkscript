# Experiment 71: progress

- 2026-11-02: gold built (`gold71.py`): 316 cited-work decisions (exp 62 blind rounds 1+2, agreed or adjudicated) +
  206 institution decisions (exp 63 blind sample, agreed; set_type, the 14 "conservative" and 2 minor errors left
  out) = 522. Packets: exp 62's blind packets as they are; exp 63's blind views + journal publisher + authority
  candidates (retriever top 8 by name trigrams; the gold body injected when missed: 35 of 160).
- Token count (30 packets): Gemini 1,215 input tokens/request, Claude 1,741.
- Pilot, 12 Standard calls each: Flash $0.021, Argon $0.053, Sonnet $0.049; answers 65-215 tokens incl. thinking.
- Batch: Flash all 510 remaining (worst case $3.31), Sonnet first 200 (worst $3.40) submitted.
- Flash batch: 510 answers in 185 s wall, $0.39 (Gemini total $0.47). Precision 94.4% (514 decided of 522), coverage
  98.8%, says "high" on 508; $0.77 per 1,000 decisions. Argon first 250 submitted (worst case $4.25).
- Argon (thinking low, the pipeline's setting): 510 in 2 jobs, $1.11; precision 95.2%, $2.18/1000.
- Flash thinking high (variant `gemini-3.8-flash@high`): 510 in 3 jobs, $1.34; precision 95.9%, $2.63/1000.
- Argon thinking high: pilot of 12 only ($0.33): two answers spent 7-8k thinking tokens (one truncated, no answer),
  ~$10/1000 at Batch; not run on the set (cost and erratic length; Gemini left for safety).
- Sonnet first 200 (+12 pilot): 91.8% precision overall but 99.3% at its "high" (144 of 208): its confidence
  separates; Gemini says "high" on ~99% of answers. $1.56/1000 (system prompt cached in Batch too).
- Claude max output lowered to 1500 (max seen 313). Sonnet remaining 310 submitted.
- Opus: 510 in 5 Batch jobs (chunked under the worst-case guard), $2.10 + pilot $0.12. Total $6.47 (Gemini $3.27,
  Anthropic $3.19). All 522 answered by Flash, Flash-high, Argon, Sonnet, Opus; none unparsed.
- gold71 fix: 3 blind-round items where blind62 counted same_work ~ edition_of as agreement now accept both labels.
- Scored (score71), designs simulated (simulate71: fixed designs + one kind-gated list), tables (tables71), the 10
  consensus-vs-gold items read (1 gold right, 9 both defensible, 0 gold wrong). README written.
