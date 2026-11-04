# Experiment 66 — progress log

- 2026-11-02: read exp 60, D30, rules43 (fixes pass through; exp 41 Store applies them), letters43/lettersfix43,
  release DB (versions.is_current: j0130_final 126, v2_55 54, v33_300_final_lettersfix 300, v33_300b_fix3_lettersfix 300).
- collect66.py: 24,528 Gemini fixes in the saved answers of the current versions (10,136 / 8,782 / 4,621 / 989);
  24,339 of them are in the current masters (DB text_corrections). Patches carry no fixes (judge / retry).
  Only 2,981 (12%) touch words Azure read with confidence >= 0.95.
- exp 60's cases: firsf (Azure conf 0.20!), subsequeently (0.84), يزيد (0.36), للتواقع (0.97, from not a word):
  Azure confidence alone does not catch them; the word test (real -> non-word) does for the Latin ones.
- sample66.py: 270 fixes in 7 strata (tune 173 / test 97, split by article); sheets out/sheets/. Labelling by eye
  into out/labels.tsv (G good / B bad / M misprint overwritten / U unclear).
- Labelled 270 by eye (G 212 / B 20 / M 21 / U 17). Bad and overwritten misprints sit at Azure ≥ 0.95 (33 of 41) and
  in Arabic letter edits; within ≥ 0.95, confidence, page quality and Gemini's `why` do not separate further.
  Gemini writing a printed misprint as printed (known → non-word) is right 35 of 43: kept.
- Rule chosen (V3): Azure sure, Arabic letter edit (not ال↔ل, not added text), Gemini's word a known word.
  At 0.95: 595 refusals; the fresh 40 (validate) gave 61% precision, the 0.95–0.97 band mostly good → 0.97:
  408 refusals, precision 69% [50, 83] on the fresh 40, weighted recall 16% [8, 35], good refused 0.5%.
- hook66.py: the hook in memory on real answers; Store accepts every model-suggestion flag (0 rejected).
  Faded-print cost seen on 0005-055-003-004 and 1080-002-010-015.
- Patch built on copies (scratch), rules43 + guard + jats tests pass on the patched copy (44). Not applied.
- README, experiments/README line, d30guard.patch written.
