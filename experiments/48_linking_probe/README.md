# Experiment 48: linking probe (the "Web of Science" direction, breadth first)

**Question** (owner, 2026-10-21). Extraction (Gemini on Azure lines → JATS + ALTO) is parked "in a good place".
What can we actually do in the other direction (linking cited works, people, institutions and journals, the
metrics on top, and the correction work behind them), measured on the 600 sample articles?

For each direction a probe answered four questions:
1. **Can we?** Does a method work on our data at all?
2. **How well?** Precision on a seeded random sample, which the probe agent judged itself by reading the evidence.
3. **What does it cost?**
4. **What is left for people?** Projected to 1M documents and the owner's team of about 300 correctors who
   understand publishing.

The shared rules every probe followed are in [BRIEF.md](BRIEF.md).

**Answer (2026-10-21, $0 in paid calls; OpenAlex and Crossref used, every request logged).**

Linking works where there is something to link to. What limits it is what Arabic scholarship cites:
- **What is cited:** books and classical works (turath) are about two-thirds of citations.
- **What is held:** only about **3%** of the 9,775 citations land on a work Mandumah holds. Among cited Arabic
  articles, theses and conference papers it is about **a third**.
- **What is found outside:** about 8% can be found by DOI. The world's indexes barely see Arabic: OpenAlex matched
  0 of 40 Arabic citations, found 9 of the 60 most-cited Arabic journals, and holds 1 of 10 of our own sample
  articles.
- **What has no record:** about **86%** have no record anywhere.
- **Coverage is set by what authors cite:** the held share stays flat (3.2–3.6%) from 50 to 600 articles, so
  parsing more articles will not raise it.

So an index built around Mandumah's own records would show "times cited 0" for most of them (about 0.26
citations per record at 1M articles). A Web-of-Science-depth index for this literature has to count **cited works
as their own entities**, books and turath included. The owner holds this as an open question, to re-measure as
more documents are parsed (2026-10-21).

All the verdicts below are an agent's (Claude's) judgements, by reading the evidence. **No person has checked
them.**

| Probe | Direction | Headline |
|---|---|---|
| [A](a_cited_to_catalogue/NOTES.md) | cited works → catalogue; OpenAlex and Crossref; cited journals | ~2.9% of citations held. Accepted catalogue links right 26/30 and 18/20 on fresh draws. Crossref finds 56% of foreign journal articles (29/30 right) and almost no books or Arabic. 1,236 journal strings → 1,142 journals (merges 74/80 right); 64% of Arabic journal names land on a held journal. |
| [B](b_works_and_backrefs/NOTES.md) | same work cited differently; back references | Cross-article cards 100/113 right. The errors come from one rule: a citation with no author joins by title alone, so «الديوان» = six poets' diwans. With authors on every member, 50/51 right. Under-merging: 35 of 50 candidate pairs are one work («المقدّمة» = «مقدمة ابن خلدون»). Back references: 43/47 resolved right (91.5%). 101 works shared by 2+ articles join 82 articles; almost all classical. |
| [C](c_people_and_institutions/NOTES.md) | authors; institutions | 91% of byline authors carry an authority id, all from the article's own record; byline → person 50/50 right. Authority file: 6 of 40 ids hold two people. Latin bylines doubled beside their catalogue twin in 11 articles. Cited authors 4.4% linked (39/40 right). Affiliations 39/50 right. OpenAlex knows 33 of 48 Arab universities (with ROR ids), and misses mostly Algerian ones. Self-citation 35/40 real. |
| [D](d_metrics_and_workload/NOTES.md) | metrics dry run; coverage; combined workload | Every metric runs end to end: times cited, journals, h-index (nobody above 1 at 600), self-citation, co-authorship, bibliographic coupling (largest group 66 articles). Shared works grow about N^1.4 over 50–600 articles. Combined human workload at 1M documents is about 16,800 h (about 56 h per corrector). Card merges, up to about 22,000 h, and a full authority check, 17,000 h or about 2,000 h most-cited first, could dominate. |

**What it changed.**
- Platform v2 now holds all 600 articles. The exam is loaded as `v33_300b_fix3` (kind final, shown for its own
  300 stems) and `v33_300b` (beside). A backup was taken first: `platform_v2.before_exam_2026-10-21.db`. Orphans
  are 0.
- Owner's dashboard of the findings (private): https://claude.ai/artifact/VVc89hqKw144WmxTshG2pb
- Nothing in `src/` or experiment 47 changed. The fixes the probes point to (the author-less title join, rule-fixable
  back references, Latin-byline twins, generic institution names) wait for the owner.
- Next, proposed by the session to the owner: a correction backend (patches for page, metadata and identity, a
  queue, review), designed before more linking is built, because wrong groupings surface at the top of every
  ranking.

**External calls.** Each request is logged in `out/<probe>/external_calls.jsonl`, and every result from these
sources is marked `source: "openalex"` or `"crossref"`. Only citation strings, titles and names were sent;
never document text, and never an email address.
- Probe A made 1,314 calls; its OpenAlex calls were cut short by the anonymous daily budget.
- Probe C made 61.
- The orchestrator made 249 (OpenAlex follow-up, `a_cited_to_catalogue/openalex_followup.py`) and 10 (the
  10-article check, `out/owner_check/`).
- From 2026-10-21 the owner's OpenAlex key is used. It is read at run time from `~/.config/inkscript/openalex.env`
  (outside git), is never written to a file, and is stripped from every log.

**Files.**
- `BRIEF.md`: the shared rules.
- `<probe>/NOTES.md`: method, results, failures, workload, next steps.
- `<probe>/*.py`: the code.
- `out/<probe>/`: `results.json`, `examples.json`, the judged samples, `progress.md` and call logs.
- `out/d_metrics_and_workload/page_data.json` and `crops/`: data and scan crops for the page.
- `watchdog48.sh`: a memory guard. It stops probe scripts over 3 GB, or all of them under 10 GB available.
