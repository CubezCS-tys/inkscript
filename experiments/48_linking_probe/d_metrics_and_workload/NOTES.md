# Probe D: the metrics as a dry run, the coverage effect, and one workload picture (experiment 48)

Data: `platform_v2.db` (read-only, shown versions of the 600: runs `v33_300_final` + `v33_300b_fix3`), `marc.db`
(read-only, immutable) and the outputs of probes A, B and C. No external calls and no paid calls. **Probe D judged
nothing new.** It reuses the verdicts of probes A, B and C, all of them made by agents (Claude), not people. Outputs
are in `out/d_metrics_and_workload/`.

**What these numbers mean.** The 600 articles are spread over about 100 years (1928–2025) and 381 journals. The
metrics below show that the machinery runs end to end, and where it breaks. They measure no person, journal or
work. Do not quote them as metrics.

| step | script | output |
|---|---|---|
| shared loading (mentions, cards, accepted links, B's census, A's journals) | `common_d.py` | — |
| D1 metrics | `d1_metrics.py` (340 s, 66 MB: cold `marc.db` pages on a swapping server; every query is indexed) | `d1_metrics.json`, `d1_networks.json` |
| D2 growth curves (30 random subsets per size, seed 4840+s) | `d2_growth.py` (2 s) | `d2_growth.json` |
| D3 workload table | `d3_workload.py` | `d3_workload.json` |
| D4 page data and scan crops | `d4_page_data.py` | `page_data.json`, `crops/*.jpg` (9 crops, max 900 px wide) |
| headline numbers and examples | `d5_results.py` | `results.json`, `examples.json` |

**What counts as "accepted".** A link counts as accepted if it is either of these:

- one of link47's 181 accepted links in the database;
- one of probe A's 207 v3 accepts (`decisions.jsonl`), which are not in the database.

Their union is 239 cards. Probe A judged its own accepts at 90% [70–97] on a fresh draw. It judged link47's links
at 83% [66–93], and link47-only links were right in only 3 of 8. Cards that B's census found wrong, serial or mixed
(13 cross-article cards) are dropped from every cross-article figure; those figures are labelled "clean".

## D1. The metrics, end to end

**Denominator.** 9,679 citation mentions in the 600, without the Quran and hadith. Probe A's 9,775 also counted
v2_55. 8,693 of the mentions sit on a card, and 339 articles cite anything at all.

- **Times cited, per cited work (cards).** This works.
  - 5,478 cards. 5,365 of them are cited by one article.
  - 113 are cited by 2 or more articles (100 after B's census). The most cited are Lisan al-'Arab (14 articles)
    and Wafayat al-A'yan (9).
  - The top 30 are almost all classical books.
  - Before the census, the over-merged «الديوان» ranked #3. Wrong groupings go straight to the top of the list.
- **Times cited, per held article.** The machinery works, but there is almost nothing to count.
  - 238 Mandumah records are reached by accepted links, from 96 citing articles.
  - **Only one of them is cited by two articles. Every other one is cited once.**
  - Only 1 of the 9,679 citations lands on an article that is itself among the 600: Badawi's 1953 «هل يمكن قيام
    أخلاق وجودية ؟», cited in a 1958 article. Crop: `crops/d_inside_corpus.jpg`.
- **Per journal.**
  - 195 journals that Mandumah holds receive 402 citations from 114 articles. Two routes reach them:
    - the journal of a held article, through an accepted link;
    - probe A's A3 journal-name match. A3's journal grouping is reusable as it stands: map each citation's source
      string to its entity.
  - 39 journals are cited by 2 or more articles. The top one is «مجلة الآداب»: 5 articles, 10 citations.
  - The generic «مجلة كلية التربية» (code 0081) is in the top 15, and it is A's known false match.
- **h-index of byline persons.**
  - 695 byline persons (author or coauthor); 632 have an authority id.
  - Their works are their catalogue records across all of `marc.db`: 16,369 records, median 6 per person.
  - Through accepted catalogue links, 15 persons have h ≥ 1 and **none has h ≥ 2**. 9 of the 15 reach 1 only by
    citing themselves, so without self-citation it is 6.
  - Through cited-work cards whose author is linked to the person (this route counts books that are not held), 48
    have h ≥ 1, 14 without self-citation, and none has h ≥ 2.
- **Why the h-index is near zero.**
  - Each person's 16k catalogue records can only be cited by the 600 articles, and the 600 make about 240
    article→record citation pairs in total. That is about 0.015 citations per record.
  - An h of 2 needs two records each cited twice, which is roughly a 1-in-10⁴ event here.
  - Mostly, the 600 do not cite each other's authors: they span a century and every field.
- **Self-citation.**
  - Probe C judged the rows: 35 right, 4 provenance notes, 1 wrong. 2 more self-citations are missed by the view.
  - 30 of the 695 persons cite themselves (4.3%), in 27 articles. Askari cites himself 3 times; 3 persons twice.
  - **40 of the 59 citations that byline persons receive through cards are self-citations.** In a small corpus,
    self-citation dominates what a person "receives". A person page must show it separately from day one.
- **Co-authorship.**
  - Inside the 600: 695 nodes, 320 edges, 549 components. 474 persons are isolated; the largest component has 12.
    No pair writes twice.
  - Using authority ids across the whole catalogue instead, the same persons have 4,468 co-author links, and 464
    of the 695 have at least one. This network works at full scale today, without parsing anything. The catch is
    that it inherits C's mixed authorities, about 10% of ids.
- **Articles joined by shared cited works.**
  - Probe B called this "co-citation". In bibliometrics it is bibliographic coupling.
  - Clean: 100 shared works, 81 articles, 298 edges, 8 components. **The largest component has 66 articles**; the
    second has 3.
  - Raw: 98 articles, largest component 76. The 10 extra articles come from bad cards.
  - True co-citation, meaning two works cited together: 144 work pairs are co-cited by 2 or more articles, and 16
    by 3 or more. The top pair is Wafayat al-A'yan + Lisan al-'Arab, in 5 articles.
- **"Trending".**
  - Citing articles per decade run at about 70 from the 1950s to the 2020s.
  - The median citation age is 14 years. 6.9% of citations are to works at most 2 years old, and 19% to works at
    most 5 years old.
  - Only 1 held record is cited in two different years.
- **What "trending" would need.** Citations to the same work, counted per citing year, over several consecutive
  years, from a corpus that is complete for those years. With about 7 citing articles per year here, there is no
  signal. It would need all of a field's articles for, say, 2020–2025 parsed. It should be measured on cards (books
  included), not only on held records, and normalised by the number of articles parsed per year.
- **Journal impact.**
  - Only 21 of the 230 held-article citations with both years known fall inside a 2-year window.
  - **The JIF denominator is ready in the catalogue**: records by `journal_code`, `year_int` and type
    «بحوث ومقالات». For example, «مجلة الآداب» has 51 citable items in 2017 and 53 in 2018 (`d1_metrics.json`).
  - **The numerator** is the citations in year Y from *every* indexed article to items of Y-1 and Y-2. That needs
    complete citing years, not a sample.
  - **The share attributable to a journal** is held-article links (exact) plus serial citations that name only the
    journal and an issue (B's "serial" type). The second kind counts for the journal and never for a work.
  - **Eigenfactor** needs a journal × journal matrix over a 5-year window without journal self-citations. The 600
    come from 381 citing journals, so the matrix is almost empty.

## D2. The coverage effect

**Shares of the 9,679 mentions at 600.** These are measured, and each category takes precedence over the ones
below it.

| fate | share |
|---|---|
| inside the parsed corpus (one of the 600) | **0.01%** (1 citation) |
| held by Mandumah's catalogue | **3.2%** (union; A's strict figure 2.7–2.9%) |
| a review, study or part of it is held (a relation) | 2.5% |
| its journal is held (not already counted) | 1.4% |
| outside, by DOI (Crossref/OpenAlex, measured) | 4.7% (≈ 8% with full lookup, per A) |
| nowhere | 88% (≈ 85% with full DOI lookup) |

**By kind.**

- Books: 4,178 mentions, 23 held. Unlinkable unless an ISBN or library catalogue is added.
- Turath: 952 mentions, 1 held.
- Journal articles: 1,833 mentions. Of these, 232 are held, 374 have a DOI and 130 have a held journal.
- Theses: 32 of 303 are held.

**Growth, measured on random subsets** (30 seeds each; the per-size table is in `d2_growth.json`):

| articles | citing | shared works | coupled articles | share of citing articles coupled | largest component | held share (sd) | inside corpus |
|---|---|---|---|---|---|---|---|
| 50 | 28 | 3.2 | 3.0 | 11% | 2.8 | 3.55% (1.7) | 0 |
| 100 | 57 | 8.1 | 7.9 | 14% | 6.1 | 3.34% (1.0) | 0.07 |
| 200 | 113 | 23.3 | 19.2 | 17% | 16.1 | 3.24% (0.5) | 0.17 |
| 300 | 170 | 39.8 | 32.1 | 19% | 27.2 | 3.28% (0.4) | 0.40 |
| 600 | 339 | 100 | 81 | 24% | 66 | 3.22% | 1 |

The fitted exponents over 100–600 articles:

- shared works grow as N^1.40;
- coupled articles as N^1.30;
- the largest component as N^1.33;
- edges as N^1.94;
- distinct works and held records as N^0.99 (linear).

**What this says.**

1. **The held share is flat.** It goes from 3.55% at 50 articles to 3.22% at 600, and its spread narrows. Parsing
   more citing articles does not raise it. It is a property of what is cited and of what Mandumah holds. It moves
   only if:
   - the matcher improves (A's next steps, maybe +1 point);
   - the field mix changes (Arabic social science cites more Arabic journal articles);
   - the catalogue grows.
2. **Inside-the-corpus links grow roughly as N².** That is mentions × the corpus's share of the catalogue: 0.07
   links at 100 articles, 0.4 at 300, 1 at 600.
   - At 3,000 articles, expect about 25 of about 48,000 citations (≈ 0.05%).
   - At 1M scanned articles, the corpus is most of the catalogue (1.56M records), so inside-corpus tends towards
     the held share, about 2–3%.
   - **Full-text metrics on the corpus itself start to mean something only near full coverage.**
3. **The networks grow faster than the corpus.** Extrapolating the fit (a guess within ×2) gives, at 3,000 random
   articles, about 1,000 shared works and about 650 coupled articles (35–45% of the citing articles).
   - Growing by whole journal runs or by field would densify much faster than a random mix.
   - At 1M the fits mean nothing: the curves saturate around the classical core and each field's canon.
4. **Times cited for held records stays thin.** At 0.40 article→record pairs per citing article, 1M articles give
   about 400,000 pairs over about 1.5M catalogue records: about 0.26 citations per record on average. Most records
   will show 0.

All assumptions are written out in `results.json` → `D2_coverage.assumptions`.

## D3. One workload picture

The counts are measured on the 600 and divided by all 600 articles. The minutes are each probe's own reading time,
taken by an agent. Rows are ordered by impact on the metrics. The full table, with what each screen must show and
the count after the proposed rules, is in `d3_workload.json`.

| # | decision (probe) | per article | at 1M | min | hours | h / corrector (300) |
|---|---|---|---|---|---|---|
| 1 | split or confirm a cross-article work joined through an author-less citation (B) | 0.103 | 103k | 1.0 | 1,722 | 5.7 |
| 2 | is this authority one person? (C), per authority, prioritised by citations received | — | 60k (515k for all) | 2.0 | 2,000 (17,167) | 6.7 (57) |
| 3 | catalogue-link candidate (A): 56 candidates + 32 link47-only | 0.147 | 147k | 1.0 | 2,444 | 8.1 |
| 4 | byline person with no authority / catalogue-only twin (C) | 0.162 | 162k | 1.5 | 4,042 | 13.5 |
| 5 | merge two cards that may be one work (B) | 0.257 | 257k (up to 2M) | 0.67 | 2,866 (up to ~22,000) | 9.6 |
| 6 | journal candidate or generic name (A), per string | 0.06 | 18k | 1.0 | 300 | 1.0 |
| 7 | affiliation wrong or partial (C), per string | 0.137 | 41k | 1.5 | 1,025 | 3.4 |
| 8 | back reference unresolved or low-score (B) | 0.315 | 315k | 0.33 | 1,732 | 5.8 |
| 9 | self-citation that is a provenance note (C) | 0.008 | 8k | 0.5 | 69 | 0.2 |
| | 1% audit of automatic links (B) | | | | 580 | 1.9 |
| | **total** (prioritised authority review) | | | | **≈ 16,800** | **≈ 56 h ≈ 11 working days** |

**Double counting removed.**

- B's "about 220 grouping decisions" overlap: its 21 author-conflict cards sit inside the 62 author-less joins.
- A's catalogue decisions act on cards after grouping, so they add to B's rather than overlap them.
- C's cited-author decisions are counted as zero: they are left unlinked by design, and the safe route
  (citation → record → authority) is row 3.
- C's 0.30 per article is split between rows 4 and 7.
- The per-string rows assume that 30% of occurrences are new strings at scale. That figure is an assumption.

**Safe to leave unlinked** (this costs recall, not precision):

- the ~86% of citations with no held record and no DOI: they keep their card, with no guessed catalogue link;
- cited authors with no linked record;
- generic short titles across articles, until an author or a classical-works list joins them;
- unresolved back references, which change mention counts but not citing-article counts;
- Latin-script books against Crossref;
- place-only affiliations and orphan faculties;
- serial-only citations: they count for the journal and never get a work card.

**The rule of thumb.** People are not the bottleneck: about 11 working days for the team. The two rows that can
explode are 5 (merges grow faster than the corpus) and 2 (all 515k authorities). Both shrink with a
classical-works list and with an authority review that starts from the persons who receive citations.

## D4. The data for the page

`out/d_metrics_and_workload/page_data.json` holds:

- `citation_fate` (totals, shares, by kind);
- `cited_work_types`;
- `top30_cited_works` (clean);
- `top_held_articles`;
- `top_held_journals`;
- `cocitation_network`: the bibliographic coupling network. Its 81 nodes carry stem, title, year, journal and
  `in_largest`; its 298 edges carry the names of the shared works;
- `coauthorship_network`: 221 connected nodes and 320 edges;
- `growth_curves`, with means, sds and fits;
- `h_index`, `self_citation`, `trending`, `impact_factor`;
- `workload`;
- `example_cards`: 9 of them, from A, B, C and D, good and bad. Each has a stem, page, note id, mention id, the
  printed text, what it was matched to, a lesson, and a crop under `crops/`. The crops come from
  `43_rehearsal/out/pages` plus the `ink_anchors` boxes (citation) or `block_parts` boxes (byline).

## What I would do next

1. Before any metric is shown, add a work/serial/legal typing and B's rule against author-less joins. The
   top-cited list is where wrong groupings show first.
2. Make the cited-work card, not the held record, the unit of "times cited" (cited-reference search). 86% of
   citations never reach a held record.
3. Choose the next 3,000 by field and by whole journal runs, not at random. Coupling and journal metrics need
   dense citing years.
4. Show self-citations separately on every person page from day one.
5. Build JIF only per field-year once that field-year is completely parsed. The denominator is already in the
   catalogue.
