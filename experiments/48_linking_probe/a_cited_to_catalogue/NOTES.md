# Probe A: cited works → Mandumah's catalogue, OpenAlex/Crossref, cited journals (experiment 48)

Everything was judged by an agent (Claude, probe A), reading each printed citation beside the record. No person
checked it. The data is `platform_v2.db` as of 2026-10-21 14:18: 5,478 active cited works, 9,775 citation
mentions (Quran excluded), 8,693 of them on a card. Outputs are in `out/a_cited_to_catalogue/`, and the headline
numbers are in `results.json`.

## Files

| step | code | output |
|---|---|---|
| dump of cards, members, link47 outcome | `extract.py` | `works.jsonl` |
| type of each work | `classify.py` | `classified.jsonl` |
| catalogue candidates and scores | `match.py` (uses `common_tokens.py` → `name_token_freq.json`) | `matches.jsonl` (top 3 per work) |
| link decision (rules v3) | `decide.py` | `decisions.jsonl` (`decisions_v2.jsonl` is the earlier rule) |
| judging draws | `sample_a1.py`, `sample_a1b.py`, `sample_a1c.py`, `recall_ar.py`, `manual.py` | `a1*_sample.txt/json`, `recall_ar.txt`; verdicts in `judged_a1*.json` |
| OpenAlex / Crossref | `ext.py` (polite, cached, logged), `a2.py`, `a2_sample.py` | `external.jsonl`, `external_calls.jsonl`, `http_cache/`, `a2_sample.txt` |
| journals | `cat_journals.py`, `a3.py local / decide / crossref` | `catalogue_journals.json`, `a3_entities.json`, `a3_sample.txt`; verdicts in `judged_a3.json` |
| headline numbers and examples | `results.py`, `make_examples.py` | `results.json`, `examples.json` |

## A1. Cited works held by the catalogue

**Types.** The classifier is a set of regex rules over the parsed fields and the printed text. It was not judged
separately; spot checks found errors at the edges, such as «جريدة الدستور» or a «مدخل لتحقيق» title.

| type | works | mentions |
|---|---|---|
| book | 2,483 (45%) | 4,178 |
| journal article | 1,418 (26%) | 1,833 |
| turath | 282 | 952 |
| other | 292 | 374 |
| chapter | 225 | 340 |
| thesis | 225 | 303 |
| website | 179 | 226 |
| conference paper | 165 | 201 |
| report | 134 | 174 |
| legal | 44 | 61 |
| news | 31 | 51 |

Of the cited works, 57% are in Latin script.

**Method.** This is more than link47 does. For each work:

- Search the title words with OR, ranked by bm25 over the rarest ten words, using the vocabulary's document
  frequencies. Also search with the author's rare name word AND the title words.
- Take up to 60 candidates and score each one on:
  - title: Dice or sequence ratio over title, title + subtitle, English title and parallel titles;
  - author: a shared uncommon name word; supervisors are excluded; a Latin-script name against an Arabic heading
    goes through `translit_pairs`;
  - year: within ±1, with hijri years converted;
  - journal name;
  - volume, issue and first page;
  - record type.

The cost is 381 s and 63 MB for all 5,478 works.

**Decision rules (`decide.py`, v3).** The rules were written after the first judged sample and then checked on
fresh draws:

- A title of fewer than 3 content words is no work. These are citations of a journal issue or a bare journal name.
- A cited thesis may link only to a thesis record or to the thesis's printed summary.
- A book review is a relation, never the work.
- A record whose two sides name different journals is sent to a person (v3).

Results:

- 207 accepted links: 166 articles, 22 theses, 7 conference papers, 12 others.
- 132 relations: a review, study or part of a cited book.
- 56 candidates.
- The rest have no link.

**Precision.** Unsure verdicts count as wrong here.

- Score alone is not enough. On sample 1 (seed 4801, 60 works), the top candidate was right in:
  - 9/9 at a score of 0.85 or more;
  - 7/9 at 0.75–0.85;
  - 4/9 at 0.65–0.75;
  - 1/9 at 0.55–0.65;
  - 0/9 below 0.55.
- Rules v2, fresh draw of 30 accepted links: 26 right, 4 unsure, 0 wrong. That is 86.7% [70.3–94.7].
  - All 4 unsure were "same title, same author, other journal or form".
  - That pattern is now a candidate (v3).
- Rules v3, fresh draw of 20 accepted links: 18 right, 1 unsure (a book versus the thesis it came from), 1 wrong.
  That is 90% [69.9–97.2].
  - The wrong one led to a tighter rule d.
- All judged accepted links under the final rules: 44 right and 1 unsure out of 45. That is 97.8% [88.4–99.6].
  This number is not independent, because the two v3 changes were made after reading these.
- Candidates: 1 right, 3 unsure and 6 wrong out of 10. They are rightly left to a person.
- Recall: of 40 unlinked works of catalogue type (20 of them Arabic-script), searched by hand by author and title,
  0 were held by the catalogue [0–8.8%].

**link47.** link47 accepted 181 links. On 149 of them we agree, with the same target. We never disagree on the
target. link47 has 32 links mine does not, and mine has 58 that link47 does not.

- On a sample of 30 of link47's links: 25 right, 4 unsure, 1 wrong (83%, [66.4–92.7]).
  - The wrong one is a classical poem linked to its 1990 reprint.
- In the sample, the link47-only links were 3 right, 4 unsure and 1 wrong. The 3 right ones my rules lose:
  - an OCR-garbled author («لايف عورة» for «نايف عودة»);
  - a misspelled author (شوكت/شوكة);
  - a 2-word title.
- My rules add Latin translations of Arabic articles (matched through the English titles and `translit_pairs`) and
  records whose catalogue author is «هيئة التحرير».

**The answer.** About 3.9% of the cited works (3.5–4.5%) are held by Mandumah's catalogue. Weighted by mentions,
that is 2.9%. Within the catalogue's own types:

- 12% of all journal articles, theses and conference papers;
- about 31–33% of the Arabic-script ones (175 of 568 accepted);
- almost none of the Latin-script ones, apart from translated Arabic articles.

## A2. OpenAlex and Crossref

Every call was logged in `external_calls.jsonl`: 1,314 calls.

- **Crossref: 1,050 calls** (1,040 OK, 10 refused with 429).
- **OpenAlex: 264 calls** (99 OK, 161 refused with 429, 4 with 400).
- No e-mail address was sent and no document text was sent.

**OpenAlex.** After 99 searches, OpenAlex refused with "Insufficient budget": the anonymous daily budget is shared
by everyone on this IP. A later message passed the owner's API key along. The permission system refused my use of
it, so I removed the key-reading code. Two questions are therefore not measured:

- whether OpenAlex knows Arabic-language journals;
- the OpenAlex side of A3.

On the 41 Latin-script articles sent to both sources, each source finds 23 and together they find 28.

**Results at a total score of 0.8 or more:**

| source | looked up | found |
|---|---|---|
| Crossref, Latin-script journal articles | 500 | 280 (56%), all with a DOI |
| OpenAlex title search, Latin-script articles | 99 | 50 (51%) |
| Crossref, Latin-script books | 300 | 47 (16%) |
| Crossref, Arabic-script articles | 20 | 3, plus 1 at 0.79 |
| Crossref, Arabic-script books | 20 | 0 |

The four Arabic articles found are all already in Mandumah. They sit under Kuwait University's DOI prefix 10.34120
and Mandumah's own prefix 10.47337.

**Precision (seed 4802, a sample of 40 with a score of 0.6 or more):**

- All 40: 31 right, 2 unsure, 7 wrong.
- Articles at 0.8 or more: 29 right out of 30 (96.7%, [83.3–99.4]).
- Books: 1 right out of 8. Crossref is not a book index: it returns chapters, reviews and articles about the book.

**DOIs gained.** 280 now. Projected to all 1,068 Latin-script articles: about 600 with Crossref, about 650 with
OpenAlex added.

## A3. Journals as cited sources

- **Collapse.** There are 1,736 journal citations, of which 1,696 name the journal. They hold 1,236 distinct
  strings, which become 1,162 keys and then 1,142 journal entities.
  - The keys come from folding, dropping «مجلة» and its variants, expanding abbreviations and removing locators.
  - Close keys are then merged; 80 entities have more than one form.
  - The collapse is small because most journals are cited once.
  - Of the 80 merges: 74 right, 2 wrong, 4 unsure.
- **Matching against the catalogue's 5,306 journal codes** (9,325 title forms). The forms are Arabic, the English
  title and the romanised title.
  - Accepted: 313 citations, 18.5% of the 1,696 that name a journal.
  - Candidates: 28 citations. A Latin-script name equal to an Arab journal's English title is ambiguous
    ("Journal of Business Research").
  - Family (series) matches: 8 citations.
  - Nothing: 1,341 citations.
- **Judged sample (seed 4803, 40 citations).**
  - Accepted matches: 12 right out of 13 [66.7–98.6]. The wrong one is the generic «مجلة كلية التربية», a name
    dozens of journals share.
  - Rightly unmatched: 24 of 27. Two were missed: JGUAA, an abbreviation, and «…جامعة الزقازيق» against
    «…بالزقازيق». One is unsure.
- **Estimate.** 17–24% of journal citations land on a journal Mandumah holds; for Arabic-script journal names it is
  64% (292 of 456 citations).
- **Crossref journals**, for 200 foreign journal entities: at a similarity of 0.95 or more, 79 entities and 212 of
  548 citations are matched, with an ISSN. A spot check found 7 of 7 right at 0.95 or more. This was not a seeded
  judged sample.

## Shares of all 9,775 citations

| what | share | detail |
|---|---|---|
| the cited work is held by Mandumah | **~2.9%** | range 2.6–3.6% |
| a review, study or part of the cited work is held | 2.5% | a relation, not the work |
| the cited work's journal is held | 3.2% | 18.5% of journal citations |
| linkable externally, by DOI from Crossref or OpenAlex | **~8%** | almost all Latin-script journal articles |
| unlinkable | **~86%** | see below |

The unlinkable citations break down as:

- Arabic books: 25%;
- Latin-script books: 18%;
- turath: 10%;
- short forms and unresolved back references, on no card: 11%;
- Arabic articles and theses the catalogue does not hold: about 5%;
- chapters, websites, reports, laws, news and other: about 13%.

Books and turath have no index on either side. They need an ISBN or library catalogue, such as WorldCat or the
national libraries, or a turath authority list.

## What is left for people

These are the decisions per article (337 citing articles):

- **Catalogue candidates:** about 0.26 per article (56 candidates and 32 link47-only links). For each, a person
  sees:
  - the printed citation crop;
  - the catalogue record, with its journal, year, volume and pages;
  - the author authority.

  The commonest case is "same title and author, other journal or form". The person decides whether it is the same
  publication.
- **Journal candidates and generic names:** about 0.1 per article.

At 1,000,000 documents that comes to about 360,000 decisions. At about a minute each, that is about 6,000 hours,
or about 20 hours per corrector for 300 correctors. Generic journal names («مجلة كلية التربية» without its
university) need the university from the citation. That is a parser task first.

## Cost at scale

- The matcher takes 0.07 s per work and stays under 100 MB. 16M cited works (before de-duplication) would take
  about 300 CPU-hours, or about 80 h on 4 workers.
- The public APIs cannot carry millions of lookups. Use the free Crossref and OpenAlex snapshots locally instead
  (disk, $0).
- No paid calls were made.

## Next

1. The OpenAlex Arabic test (20 citations) and OpenAlex sources for journals, once a key may be used.
2. Resolve journal abbreviations (JEA, BIFAO, JGUAA…) from a list, using ISO 4 or the field's own lists.
3. Let the author comparison tolerate one misread letter, as link47's does. That would recover link47's right
   links that my rules lose.
4. Record "second publication of the same text" as its own relation type.
5. Join the parsed university to generic journal names.

## Follow-up: OpenAlex with the owner's key (2026-10-21, run by the orchestrating session)

This follow-up was run with the owner's explicit OK to use the key: `openalex_followup.py`, results in
`out/a_cited_to_catalogue/openalex_followup.jsonl`. It made 249 requests, all HTTP 200, all logged in
`external_calls.jsonl` with the key stripped; a grep of the folder finds no copy of the key. Every row is marked
`source: "openalex"`. The scores below are the match scores of `a2.py`; nobody judged these matches.

- **F1, Arabic citations** (the same seed 4802 draws that went to Crossref):
  - 20 Arabic article citations: OpenAlex returned anything for 5, and matched none at 0.8 or more.
  - 20 Arabic book and thesis citations: it returned anything for 10, and matched none at 0.8 or more. A title
    alone sometimes hits an old catalogue record, for example «العمدة في صناعة الشعر ونقده» at title score 1.0
    with no author or year agreeing.
  - OpenAlex does hold some Arabic journal articles, through DOIs from Egyptian EKB (10.21608), Iraqi and other
    prefixes, and Mandumah's own (10.34118, 10.71219, whose suffixes are Mandumah stems such as
    `0135-031-003-001`). It does not hold the Arabic works these 600 articles cite.
- **F2, OpenAlex sources for cited journals:**
  - The 120 most-cited Latin-script journal entities: 58 found at name similarity 0.9 or more, 4 between 0.75
    and 0.9, 58 not found or low.
  - The 60 most-cited Arabic-script journal entities: 9 found at 0.9 or more, 7 between 0.75 and 0.9, 44 not
    found. Not found: «مجلة اللسان العربي» (17 cites), «مجموعة الأحكام», «مجلة عالم الفكر», «مجلة الأقلام».
  - Generic names such as «مجلة كلية التربية» match a single faculty's journal; that is the same trap as in
    the catalogue.
