# Probe C: people and institutions (experiment 48, 2026-10-21)

The question: can we tell who wrote each article, who is cited, and where each author works, well enough to count
citations and compute an h-index? Precision comes first: a wrong merge does more harm than a missing link.

Data: the 600 sample articles in `platform_v2.db` (runs `v33_300_final` and `v33_300b_fix3`, `is_current = 1`),
`marc.db` (2.2M author headings), and experiment 47's heading-key index
(`~/data/platform_v2/marc_heading_keys47_*.sqlite`). All of it was opened read-only. **An agent (Claude) did every
judgment below by reading the evidence:** the JATS byline and affiliations, the article's own catalogue record, and the
authority's other records grouped by journal. Outputs are in `out/c_people_and_institutions/`. `progress.md` there
lists every step.

## Method (scripts in this folder)

| script | what it does |
|---|---|
| `c1_bylines.py` | every byline authorship of the 600: how it reached an authority id, and how many authority ids carry the printed name (exact folded key; "loose" = every «surname، given…» heading, with and without «ال») |
| `c1_splits.py`, `c1_hard_examples.py` | spellings per authority id (catalogue-wide, one GROUP BY); headings shared by 2+ ids; hard names |
| `c1_authority_profiles.py`, `dump_authority.py`, `judged_authorities.py` | a profile of each of our 675 authority ids (years, journals, fields, countries, theses); a seeded sample (seed 4821, 25 flagged + 15 unflagged) judged as "one person or several" |
| `c1_person_sample.py`, `judged_persons.py` | seed 4822: 50 byline→person links, judged |
| `c1_cited.py`, `judged_cited.py` | cited authors: links, holders in the catalogue; seed 4823: 40 links made, plus 20 unlinked names with a unique holder |
| `c1_selfcite.py`, `c1_selfcite_missed.py`, `judged_selfcite.py` | every self-citation that `v_author_self_citations` reports, judged, plus a search for ones it misses |
| `c2_institutions.py`, `judged_affiliations.py` | affiliations → institutions, levels, a saturation curve; seed 4824: 50 links judged |
| `c2_cross_script.py`, `judged_cross_script.py` | institutions still split across Arabic/English/French (consonant-skeleton candidates, judged) |
| `c2_catalogue_universe.py` | a large-scale saturation curve from the catalogue's 169,600 thesis universities (502 $c) |
| `c2_openalex.py`, `openalex48c.py`, `judged_openalex.py` | OpenAlex coverage of 50 Arab universities (API key read at run time, never stored) |
| `make_results.py`, `make_examples.py` | `results.json`, `examples.json` |

Cost: about 90 s of wall time for all scripts together, with a peak of 72 MB RSS. marc.db was read only through the
`name_folded` / `authority_id` indexes and one SQL GROUP BY. There were no paid calls. OpenAlex got 62 calls: 6 refused (429) before the key, then 56 OK.
All are logged in `external_calls.jsonl`.

## C1. Author identity

**Bylines.** The 600 articles hold 702 byline authorships (715 printed names; 13 are bilingual twins that were
joined). Every article has a catalogue record.
- 638 (91%) carry an authority id. All of them come from the article's own catalogue record, by these methods: exact
  491, token-subset 117, weak name confirmed by the given name 22, transliteration 7, script-twin 1.
- 1 came from a name search alone.
- 63 have no link: 61 provisional and 2 rejected weak matches.
- 47 articles have no byline person at all.

**The links that are made are right.** In the seed 4822 sample, 50 of 50 were right (Wilson 95% interval 0.93–1.00).
I also read all 22 "weak + given name" links and all 8 transliteration / script-twin links: all were right. The 2
rejected weak matches («أبى الحسن الندوى», «سير كِنت كلارك») were both right too, so rejecting them was safe, just
cautious. The risk is not the link. The risk is the entity behind it: in 4 of the 50 cases (Wilson 0.03–0.19), the
authority id also holds another person's records.

**What is missed.** In 11 articles the provisional bylines and the "catalogue-only" contributors are the same people.
Each such author is then counted twice, once from the byline and once from the catalogue, so this is a precision
problem as well as a recall problem. Examples:
- transliteration: «Khalid Talal Alotaibi» = «العتيبي، خالد طلال» (7 printed authors became 12 authorships);
- «Abbas A. Al-Mejren» = «المجرن، عباس علي»;
- short name vs full heading: «طه حسين» = «سلامة، طه حسين علي، ت. 1973 م»;
- a role printed as the byline: «المفتى العام» = «القلقيلي، عادل عبدالله»;
- initials: «ع. م» = «محمد، عرفه».

There is a second kind of catalogue-only contributor. In a book review, the catalogue lists the reviewed book's author
as مؤلف: Edward Said appears as an author of a 1981 review of *L'Orientalisme*. Without the role code and the record
type (عروض كتب), the review becomes one of Said's works.

**Ambiguity (one name, many people).**
- Exact folded printed name, across the whole catalogue: 448 of 702 names have one holder, 74 have 2+, and 180 have
  none (the print differs from the heading).
- Loose «given … surname» search: 290 have one candidate, 268 have 2+, and 104 have more than 5.
- Catalogue-wide: 26,993 heading keys are held by 2+ ids. Five keys are held by more than 20 ids, e.g. «محمد إبراهيم»
  29 and «أحمد حسين» 28.
- Hard names, as (exact holders, loose holders): «محمد أحمد» (15, 728), «أحمد علي» (18, 357), «Ahmed, M.» / «M. Ahmed»
  (0, 844 Latin «m…ahmed» keys), «Ali, A.» (0, 1,675).
- Only the article's own catalogue record makes such names safe: «أحمد على» (0628-005-004-008) is right only because
  the cataloguer chose 277734.

**Splits (one person, many spellings).** Inside the catalogue an authority id is almost perfectly controlled:
- 718,038 ids carry one raw Arabic form, 752 carry 2, and 334 carry 2 folded forms.
- Latin: 19,712 ids carry 2 Latin forms.
- Of our 675 ids, 177 add one Latin heading. Only 3 vary in Arabic: hamza, a life note, one spelling.

The real splits are between the print and the catalogue:
- token-subset: 117 cases of a short printed name against a full nasab;
- weak given name: 22;
- transliteration: 7;
- 180 printed names that match no heading exactly.

Then there are duplicate authority ids. 75 of our linked headings are also held by other ids, which are homonyms or
duplicates. A clear duplicate: the historian «عبدالعزيز محمد الشناوي» is 128922, and a review of his book sits under
128921.

**Authority errors (one id, two people).** Seed 4821, 40 ids judged: 32 one person, **6 two people**, 2 unsure.
That is a 15% error rate (Wilson 0.07–0.29). My crude flags (span ≥ 45 years, 4+ fields, 3+ countries) did not help:
4 of 25 flagged ids were mixed, and so were 2 of 15 unflagged ones. The pattern is the same every time: a new author is
filed under an older, better-known authority with the same heading. Examples:
- 213172 holds both Egyptians named Muhammad Kamil Husayn: the Fatimid scholar and the surgeon-novelist who died in
  1977. Our byline in 0763-004-002-001 is the scholar, so his person page would show him dying in 1977.
- 418428: the poet Muhammad Omran, plus a 2003 Aleppo leishmaniasis thesis and 2018 audit-law articles.
- 241590: Sheikh al-Azhar Abd al-Majid Salim (d. 1954), plus a co-authored paper at the 1987 Fiqh Academy.
- 86707: an Islamic poet, plus an Algerian demographer (2015–24).

My estimate is that about 69 of our 675 ids (10%; 15% of those with 3+ records) hold another person's records. The
stray records are usually few, but they go straight into that person's paper count and h-index.

**Cited authors (what h-index needs).** The 600 articles cite 6,398 cited-work authors (4,803 works); 284 of them (4.4%)
are linked to a person:
- surname in a linked record: 192;
- name key with one authority holder: 57;
- name equals a byline of the citing article: 35.

In the seed 4823 sample, 39 of 40 links were right (Wilson 0.87–1.00). The wrong one was al-Shinnawi (above). Can the
rest be linked at all?
- 62% of the cited authors are Latin-script; 3,890 of those have no holder in the catalogue (foreign authors).
- 952 names have exactly one holder. Linking those by name alone was right in 18 of 20 judged, with 0 wrong and 2 unsure
  (Wilson for right: 0.70–0.97).
- 167 names have 2+ holders.
- 1,389 Arabic names have no holder.

For citation counts, the safe route is the one already working best: citation → catalogue record → that record's
authority id. A name-only link should be the exception.

**Self-citation.** `v_author_self_citations` reports 40 rows in 32 articles. Read one by one:
- 35 are true self-citations, e.g. Askari, Cummings and Toth citing their own forthcoming paper;
- 4 are provenance notes on page 1, not citations: "this paper is from my PhD", "excerpt of *Mostly Murder*";
- 1 is wrong: Yahya al-Ghoul given as an author of a work by Tawfiq Daghfous.

That is 87.5% right (Wilson 0.74–0.95). A name search finds 2 more that the view misses (Sieny, al-Maghrawi). Rule to
add: a page-1 note that names the article's own source is not a citation.

## C2. Institutions

**What the affiliations become.** The 600 hold 418 affiliation mentions in 311 articles:
- 374 name an institution; all 374 are linked, plus 1 of the 12 position-only ones;
- 32 are place only, 12 position only;
- those 418 reach 471 institutions: 134 universities, 138 faculties, 125 departments, 26 centres, 40 organisations,
  and a few societies and ministries;
- at the organisation level there are 208 institutions, about 347 per 1,000 articles.

**Precision.** Seed 4824, 50 affiliations judged at the organisation level: right 39, partial 2, **wrong 8**, unsure 1.
Right is 78% (Wilson 0.65–0.87); wrong is 16% (Wilson 0.08–0.29). The wrong ones are of three kinds:
- **Generic words made entities:** «المعهد» from «مدرس بالمعهد», «ENS» from «ENS-CONSTANTINE», and the bare
  «الجامعة الإسلامية», which would merge Madinah, Gaza, Islamabad and Omdurman.
- **Orphan faculties and departments keyed `org:?/…`:** every «كلية الآداب» or «قسم التاريخ» with no university becomes
  one institution. That applies to 36 keys, and it hits even when the university is printed («Faculté de Lettres,
  Université de Minia»).
- **The university lost:** UT Austin is kept only as its "Graduate School of Business and Center for Middle Eastern
  Studies", with no parent.

**University, faculty and department.** The tree works when the affiliation is complete: «قسم الرياضيات / كلية
التربية / جامعة الموصل» gives three levels, each with its parent. The weak points:
- The department text often repeats the faculty («College of Business and Economics» is stored as both).
- 28 faculties or departments have no parent.
- 2 of the 50 department names are garbled («حوث رسم التنمية», «Weaving»).
- Numbered universities are handled («جامعة قسنطينة 2»), but not when the number is glued on («سطيف2»).

**Arabic, English and French forms.** Of the 208 organisation-level institutions, 7 already hold names in both scripts
(Cairo, Baghdad, Salahaddin, …). A consonant-skeleton search found 12 candidate groups; 8 are confirmed splits of one
university into two entities: Helwan, Mosul, Ain Shams, Tanta, Zagazig, al-Qadisiyah, Sana'a, Umm al-Qura. Renamed or
aliased forms («Université Mouloud Mammeri» = Tizi Ouzou) are not found this way.

**Saturation.** As articles are added in random order (20 orders), the count of distinct organisation-level
institutions goes 22 → 116 → 208 at 50 → 300 → 600 articles. The curve is almost straight: 174 of the 208 are seen only
once.

The catalogue gives a curve at real scale. Its 169,600 theses name 443 distinct universities, and the curve flattens:
86 at 600 theses, 196 at 10,000, 376 at 100,000. Its corporate headings give 1,795 distinct «country. body» pairs.

Projection for 1M articles, at organisation level:
- about 1,900 if the affiliations follow the thesis curve's growth exponent (0.3) beyond 600 articles;
- about 20,000 with exponent 0.6, for the long tail of ministries, schools, hospitals and foreign bodies;
- faculties and departments roughly 5–10× that.

**OpenAlex coverage of Arab universities (source "openalex").** The first attempt (6 calls) got HTTP 429: the free
budget shared by this server's IP was used up. The rerun used the owner's API key, read at run time and never written
to code, cache, log or notes (checked with a grep for the key). It made 56 requests, all 200, at 2 per second.

The 50 universities (seed 4824) were searched under up to two name forms each. Two of our "names" are not one
institution («جامعتى القاهرة وصنعاء», the mis-read «University Center»). Of the other 48, judged (`c2_openalex_judged.json`):

| verdict | count |
|---|---|
| right top hit (same university, right country, with a ROR id) | 33 (69%, Wilson 0.55–0.80) |
| wrong top hit: «الجامعة الإسلامية العالمية» → Selangor Islamic University | 1 |
| unsure: «جامعة الفرات», «جامعة الزيتونة», a UMT without a country (ambiguous across countries) | 3 |
| no hit | 11 |

Arabic names often work (جامعة سوهاج → Sohag University; جامعة 8 ماي 1945 → University of Guelma). Both forms of
Helwan and of Tikrit resolve to the same ROR id, so OpenAlex can merge our cross-script twins. Most misses are
Algerian universities under French or eponym names (Béjaïa, Tébessa, Tlemcen, Batna 2, Blida 2, Emir Abdelkader), plus
spelling variants (ی for ي, ى for ي).

OpenAlex has 1,970 institutions in the 22 Arab countries, 1,045 of them of type education (Egypt 282, Morocco 190,
Saudi Arabia 169, Algeria 165, …). So it is a useful reference list for universities, used with a country filter and
a human check on ambiguous names. It does not cover faculties and departments, and it holds few of the
ministries, centres and schools.

## C3. Work left for people

Uncertain decisions per article, all measured on the 600:

| decision | per article | the screen must show |
|---|---|---|
| a real person on the byline with no authority id (49) | 0.082 | the byline ink crop with its affiliation and e-mail; the record's contributors; candidate ids from a loose search, each with its works grouped by journal, its co-authors and its years |
| a catalogue contributor with no byline (46): missed byline, reviewed book's author, or the twin of a provisional byline | 0.077 | the record (type, role), the byline crop, and the provisional bylines of the same article side by side, so one click pairs them |
| weak match rejected (2) | 0.003 | as row 1 |
| affiliation wrong or partial (~82) | 0.137 | the affiliation ink crop and the proposed tree (university › faculty › department); candidates with their name forms in each script, country and city. Mostly decided once per string, not per article |
| **must decide** | **0.30** | |

There is also one decision per person rather than per article: is this authority one person? A corrector needs the
authority's records grouped by journal and decade, with fields, countries, roles and life dates (the
`dump_authority.py` view). I read such a view in about 1–2 minutes.

Projection to 1M documents and 300 correctors who understand publishing:
- **Article-level:** about 300,000 decisions. At 1.5 minutes each, that is about 7,500 hours, about 25 hours per
  corrector.
- **Person-level authority review:** if every authority with 3+ records is checked once (about 515,000 ids at 2
  minutes), that is about 57 hours per corrector. Taking first the persons who receive citations, and the ids flagged
  by "records after the life date" or "a cluster of journals in another country and field", cuts this a lot.
- **Institutions:** one decision per institution (1,900–20,000 at about 3 minutes): at most about 3 hours per
  corrector.

**Safe to leave unlinked rather than guessed** (it costs recall, not precision):
- every cited author without a linked record: 167 + 770 per 600 articles, about 1.6 per article. With 2+ holders,
  never guess. With one holder, link only when the cited title is among that holder's records.
- the ~12 role and corporate bylines and the initials-only bylines that the catalogue does not resolve;
- the 43 place-only and position-only affiliations;
- every orphan faculty or department (no university printed): keep the printed text, link nothing.

With those left aside, the human queue is the 0.30 per article above, plus the authority reviews ordered by citation
weight.

## What I would do next

1. Pair provisional bylines with catalogue-only contributors of the same record by transliteration, the catalogue's
   Latin forms (`translit_pairs`), initials and role. That removes the double counts in 11 of 600 articles.
2. Use the record type and role (عروض كتب, عارض) so that a reviewed book's author is not counted as the review's
   author.
3. Stop orphan and generic institution keys: no entity for «المعهد», «ENS» or «الجامعة الإسلامية» without a city or
   country. Never key an orphan faculty as one shared `org:?` institution.
4. Merge cross-script university twins through a bilingual list seeded from the catalogue's 443 thesis universities,
   once OpenAlex/ROR can be queried.
5. Build an "authority health" report for Mandumah: records after a life date, journal clusters in another field or
   country. The 6 errors found here are a start (`c1_authority_judged.json`).
6. Resolve organisation-level institutions to OpenAlex/ROR with a country filter. Queue the ambiguous and missing
   ones (about a third) for a person.
