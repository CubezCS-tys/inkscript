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
