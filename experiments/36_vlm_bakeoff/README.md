# 36 · VLM bake-off: which open vision-language model reads Mandumah pages

Work in progress (2026-10-12). Question: which open VLM should be the main whole-page reader (text, tables,
equations, reading order), how often each invents or drops text, and how well Kraken (experiment 33) catches it.
Candidates and run recipes: [models.md](models.md).

## Scoring (built before the VLM outputs landed)

```
V=/home/yassine/inkscript/.venv/bin/python
$V convert.py                 # out/raw/<tag>/ -> out/pred/<tag>/ (+ .kl re-cut); azure, kraken, synth_azure too
$V evaluate.py                # -> out/results.json, out/eval_pages.jsonl, out/score/<reader>.json (the CLI's gold report)
$V judge.py estimate          # Gemini judge of tables/equations: cost only; `run --limit 3` = the 3-call test
```

- [convert.py](convert.py): dots (JSON blocks, boxes in the resized image's pixels, salvages output cut at the token
  cap), Qwen `qwenvl html` (data-bbox on 0–1000), PaddleOCR-VL `parsing_res_list`, amad plain text. Block text is
  split on newlines (paragraphs); the `.kl` variant re-cuts each block on the Kraken lines inside it, for the
  line-level measures only. Tables: HTML plus cell lines; display equations: LaTeX only; page header/footer kept as
  furniture.
- [evaluate.py](evaluate.py): three page sets, never pooled: `gold` (done pages, score.py), `bd` (born-digital
  text layer, digits folded), `ys_azure` (all 202 yardstick pages: agreement with Azure, not accuracy). Strata:
  split, decade band, vowelled/Quran, table, equation, multi-column, footnotes, Latin. 95% intervals by document
  bootstrap (1,000 draws).
- Invented and dropped text are counted in words, order-free (the docstring has the rule). It was
  checked on `synth_azure`, a calibration reader: Azure's reading with one line from another page inserted, one line
  dropped and a loop on a fifth of the pages. The rule finds 88–95% of the inserted words. Kraken can misread
  but cannot invent, so its "invented" rate is the rule's false-alarm floor for a reader that weak: 8.6 per
  1,000 words on bd and 17 per 1,000 vs Azure, almost all on tables.
- [judge.py](judge.py): one Gemini call per table/equation (63 on the yardstick pages), all readers' versions
  anonymised in one request; cache, spend log `out/gemini_spend.jsonl`, $3 cap, no retry of a truncated answer.
  A reader that gave nothing is graded 1 locally, not sent.
- [headline.py](headline.py): `out/headline.md`, the tables below, from results.json and judge.jsonl.

## First results (2026-10-12; gold = 6 done pages, rerun evaluate.py + headline.py as gold grows)

Full tables with intervals: `out/headline.md`. Character error rate (faithful) and the main failure counts:

| reader | gold CER | born-digital CER | vs Azure CER | pages given up / runaway (vs Azure) | judge: tables / equations (1–5) | pages/h, $/1k pages |
|---|---|---|---|---|---|---|
| Azure | 0.9% (flattered) | 3.1% | — | — | — | — |
| dots.mocr | 3.0% | 5.5% | 13.7% | 0% / 0% | 3.44 / 2.42 | 2,807, $0.17 |
| dots.ocr | 3.6% | 7.3% | 18.5% | 1% / 1% | 2.68 / 2.06 | 2,648, $0.18 |
| amad-vlm6 (text only) | 1.5% | 3.6% | 18.4% (8.7% healthy) | 0% / 2% | — | 3,051, $0.15 |
| PaddleOCR-VL-1.5 | 5.8% | 25.8% | 50.1% | 0% / 1% | 2.26 / 1.71 | 5,486, $0.09 |
| Qwen3-VL-32B AWQ | 102% | 38% (11.7% healthy) | 44.7% (18.8% healthy) | 23% / 8% | 1.78 / 1.39 | 326, $1.44 |
| Qwen3-VL-8B | 12.1% | 145% (17.6% healthy) | 105% (30.2% healthy) | 6% / 12% | 1.23 / 1.03 | 1,059, $0.44 |
| Kraken (the checker) | 6.0% | 9.5% | 19.0% | — | — | — |

What the numbers show:
- Qwen gives up on 23% of pages: it answers a whole text page as one `<img>`. It loops until the 8,192-token
  cap on 8–12%, and it adds vowel marks the page does not print (marks precision 8–18%).
- Paddle reads two-column Arabic left column first (word order on multi-column pages 36–55%).
- Truth-based invented text is rare for every VLM: 1–3 words per 1,000 outside tables.
- Kraken flags 92–100% of the VLMs' truth-based inventions. Its precision is 4–19% on the good readers, because
  most of its flags fall where Kraken itself misreads.
