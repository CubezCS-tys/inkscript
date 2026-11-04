# Experiment 61 progress notes

- 2026-11-02: read the pipeline (prompt43 v2 / v3.3 / v3.5b, rules43, enrich43, meta43, jats43, masters41), the
  platform loader (parse47), the release DB `R20261023T005909.db` (780 current versions: j0130_final 126 v3.5b,
  v33_300_final_lettersfix 300 v3.3, v33_300b_fix3_lettersfix 300 v3.3, v2_55 54 v2).
- Confirmed the owner's example by reading the code: 0130-018-072-003's answer holds both authors with role and
  affiliation; `meta43.names_pre` folds the Latin twin into the Arabic contrib and copies its `aff` only when the
  Arabic one has none (so the English affiliation is dropped); `<role>` is written only for translator / reviewer /
  editor / supervisor / rapporteur, so an author's position («طالبة باحثة في علم الاجتماع», "PhD Student in
  Sociology") never reaches JATS. Both survive only as the generic `custom-meta front-matter-block`.
- Method chosen: word level. Azure word -> ALTO String (ink47.match_words, by box) -> TextBlock -> JATS element (id
  or xlink:href) -> field class; byline-type containers (front-matter-block, contrib, body byline p) are split by
  matching their words against the specific values of JATS (and, separately, of the platform rows).
- Audit built and iterated against false alarms (labels beside stored values, titles printed twice, superscript
  marks, ALTO boxes re-laid in mixed-script lines, window page offsets, words drawn on the wrong ALTO page, inline
  formulas). Final: 99.66% of 435,270 lines accounted for; 1,460 fell through.
- Scan check: 83 sampled leaks, 82 looked at, 1 false alarm (1.2%), 17 with a wrong "what it is" label.
- Desk `/audit` built (desk/audit.py, web/pages/audit.tsx, web/components/audit/), screenshots in out/shots/;
  test servers on 8094/8095 stopped. Desk tests 74 passed; audit tests 7 passed.
