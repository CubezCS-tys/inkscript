# Experiment 59 progress notes

- 2026-10-30 18:25: read docs.reducto.ai (llms.txt index; copies of the pages used in out/docs/): r-1 (preview, V3 API,
  `settings.model: "r-1"`), word/cell citations (`settings.return_citations`, r-1 only, +$2/1,000 pages), Extract
  (schema, citations, deep_extract), legacy Parse (extraction_mode ocr, agentic text/table scopes), pricing (per-product
  list prices since 2026-09-01: r-1 $10/1k pages, legacy $15/$30 per 1k (x2 agentic), Extract $20/1k incl. parse,
  Deep Extract $40/1k; batch queue -20%).
- Retention / privacy read BEFORE sending anything:
  * Zero Data Retention (24 h purge) and no-training promise are for **Growth tier and above** only
    (security/policies.md, enterprise-readiness.md: ZDR "—" for Standard; "Enterprise tier data is never used for training").
  * On-demand deletion `DELETE /job/{id}` and `DELETE /upload/{id}` exist; docs say job deletion returns 422
    NOT_APPLICABLE below Growth.
  * Per request we can only set `settings.persist_results: false` (the default: results expire, "job IDs generally
    expire after 12 hours"; uploads "expire after 24 hours").
  * Terms of Use (reducto.ai/terms, effective 17 Apr 2026) govern the Standard tier "even if your usage is free":
    User Content is "non-confidential and non-proprietary" and Reducto gets a licence "to use, analyze, aggregate,
    reproduce ... to provide the Services to you, to develop and improve the Services, to develop new offerings ...
    and for our other business purposes". No opt-out offered on this tier.
- Smoke tests with no Mandumah data (Reducto's public sample PDF and a synthetic one-line page): API v1.12.21; account
  is on **per-product pricing** (usage_breakdown, credits null; tier "Default"). `DELETE /job` and `DELETE /upload`
  both return **500 INTERNAL_ERROR** (tried twice); a parse of the "deleted" upload still succeeded (served from cache).
  So: nothing can be deleted on demand from this account; we rely on the default expiry.
- Decision: proceed within the owner's approval (about 50 pages, already hand-checked articles), persist_results false,
  try DELETE on every upload and job anyway and log the answer; no Mandumah page goes anywhere else.
- units59.py: 49 pages (22 text truth, 12 metadata page-1s, 15 citation pages holding 20 of the 80 sampled citations).
- 18:40 r1 on all 49 pages (66 s, 3 workers); r1_verbatim / legacy_ag / legacy on the 22 text pages.
- Lead's instruction received: no page beyond the 49; minimal re-processing. Nothing else sent.
- Text (22 pages): Azure 2.34, Argon 1.96, Indra 11.55, r1 5.19, r1_verbatim 3.51 (bd 2.24 vs Azure 2.65), legacy 5.49,
  legacy_ag 8.89. Retyping: ى→ي ~35, hamza changes; two-column Arabic read left column first.
- Layout (27 pages): roles 87.2% (Indra 87.0); headings 92%, furniture 95%; footnotes all "List Item"; 2-col 0/8 identical.
- Extract refs std/deep + meta std/deep done (deep refs ~95 s/page). Refs fully right: ours 12, std 13, deep 15 of 20
  (judge59_refs.json). Meta page 1: ours 11, std 6, deep 7 of 12 (judge59_meta.json).
- Boxes: 94% of words boxed, 96.5% inside the same Azure word. Total list $4.61.
- Side page out/side/index.html built and looked at with Playwright (8 sections; mobile no h-scroll). README written.
