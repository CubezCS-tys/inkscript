# Experiment 56: the librarian — an AI curator's first pass over institutions

**Question** (owner, approved 2026-10-23). The linker's rules join printed affiliations into institutions by
spelling, and they break in known ways: Arabic and English names of one university stay two rows; 48 faculties
printed without a university share one key «org:?» (one «كلية الآداب» row covers 6 unrelated articles); 27 of 560
links point at an institute inside the printed university; «Islamic University of Lebanon» became «University of
Lebanon»; «جامعة ،دمشق» became «الجامعة»; 406 of 701 rows have no country. Can an AI "librarian", sitting beside the
rules, settle what they cannot — like a person walking a card catalogue — as a clean, repeatable unit (an evidence
packet in, a structured decision out) that the Claude API can later run at scale? This pilot: one pass, done by Claude
(the agent itself; no paid API call), over all institutions of the 780 articles.

**Answer.** Yes, and most of it turns out to be rule-able once the authority exists. On release `R20261023T005909`:
908 standing decisions (659 per printed affiliation + 249 per institution), **662 reproducible by a deterministic
rule, 246 needing judgement**; 813 high, 85 medium, 10 low confidence; **10 left "unsure"** rather than guessed.
Nothing is applied: they are proposals until the owner has checked the sample on the Desk's `/librarian` page.

## Before and after (the 780 articles, 659 printed affiliations)

| | machine today | with the librarian |
|---|---|---|
| institutions (organisation level, linked) | 271 (of 701 rows; 414 are faculties/departments) | **234** |
| institutions in 2+ articles | 54 | **69** |
| affiliations linked to an institution | 560 | **580** (64 name no body; 10 unsure; 5 faculties kept apart) |
| share of institutions with a country | 42% (406 of 701 rows have none) | **95%** (223 of 234) |
| affiliations with a country | 338 | **586** |
| gate 1, institutions in 2+ articles: journal 0130 vs random sets of 126 | **26 vs 3.8** (6.8×; reproduced exactly with experiment 52's definition and seed) | **25 vs 6.3** (4.0×; random range 3–11) |
| lumped «org:?» faculty/department rows | 48 rows, 48 affiliations | 34 placed under their university, 4 kept apart as their own units, 8 not an institution, 2 unsure |
| bilingual twins joined | — | 16 (Alexandria University = جامعة الإسكندرية, Ain Shams, Helwan, Umm Al-Qura, Al-Quds, Mosul, Basrah, Lebanese University…) |

**Gate 1 gets less flattering, and more true.** The journal loses one recurring institution and random sets gain 2.5:
the machine's false bridges are gone (one «وزارة التربية» row held Kuwait ×7, Yemen and Tunisia; one «وزارة التربية
والتعليم» row Kuwait, Bahrain and Oman; one CRMEF row every Moroccan city), and true ones it missed are made (the same
university in two scripts; «جامعة فاس» = Sidi Mohamed Ben Abdellah; «معهد الطفل» inside جامعة القدس). The contrast
is still 4×.

## Method

1. **Evidence packets** (`build56.py`, 11 s, 59 MB): one per printed affiliation, with the statement and its
   parts, the article, journal and year, the author (byline, person id), the same author's other statements in the
   same article and in other articles, the machine's org / faculty / department rows (names, country, inst46 key),
   where the statement sits on the scan (Azure lines on the byline's page that carry its words, 589 of 659 found;
   for the ink crop), and catalogue hits. The catalogue authority (`marc_authority56.py`, 42 s, read-only):
   MARC 502 $c (the university that granted 169,600 theses) with its country $g, and 2,410 corporate 110 headings
   «البلد. الهيئة. الوحدة». It confirmed the country of 115 of the authority's entries.
2. **Judging** (`authority56.py`, `judge56.py`, `overrides56.json`, `decisions56.py`): the librarian's authority —
   280 entries (one per real body: name in Arabic and English, type, country, parent, printed forms; generic bodies
   like «وزارة التربية» resolved per printed country; shared names like «جامعة الزيتونة» chosen only by a printed
   country) — and the judging unit `judge(packet) -> verdict`: the rule proposal (longest printed form wins, a unit
   points to its university), replaced by the librarian's call where one was needed (95 overrides, each with its
   reason). All 659 packets were read in 11 batches of 60, each committed to `out/decisions56.jsonl` as it was
   judged (append-only; a changed answer is a new decision that supersedes the old; the working log of the pass is
   kept as `out/decisions56_draft_log.jsonl`). `finalize56.py` then asks the institution-level questions over the
   machine's rows (same / not same, country, parent, type, not an institution) and writes the authority
   (`out/authority56.json`) and the numbers (`out/numbers56.json`).
3. **Rules learned** (`rules56.py`, `out/rules56.json`): see below.
4. **The owner's sample** (`sample56.py`): 30 decisions, stratified (merges 6, splits 4, parent fixes 5, countries 5,
   affiliation fixes 5, not an institution 2, unsure 3; seed 56), each with its printed statements and ink crops. The
   Desk page `/librarian` (`experiments/49_correction_desk/web/pages/librarian.tsx`, API
   `experiments/49_correction_desk/desk/librarian.py`, table `librarian_verdicts` in `desk/schema.sql` under the
   idempotent-upgrades mark) shows them with Yes / No / Unsure buttons and an optional comment (append-only, latest
   shown), the before/after numbers, every decision with filters (kind, confidence, level, basis, search, "only
   unsure"), the rules and the scale estimate.
5. **Scale** (`scale56.py`, `out/scale56.json`).

**Decisions by kind** (standing, newest per question): affiliation → institution 580 (high 540, medium 40; the
machine agreed on 451, 129 fixed), not an institution 70, unsure 10 (all low), faculty kept apart 5,
set_country 134, set_parent 48, same_institution 30, set_type 22, not_same_institution 9. Basis: printed name (rule)
592, world knowledge 133, judgement 80, catalogue 73, same article / journal (context) 30. World knowledge was used
only for well-known bodies and is named in each reason («University of Riyadh» = King Saud University before 1982;
Dhar El Mehraz is Sidi Mohamed Ben Abdellah's; the Faculty of Usul al-Din in Cairo is Al-Azhar's).

**Hard calls** (examples):
- «جامعة الزيتونة، ترهونة، ليبيا» is Libya's Az-Zaytuna University, not Tunisia's Ez-Zitouna — the authority first had
  one entry; a shared name is now resolved only by a printed country.
- «الهيئة العامة للآثار والمتاحف، بوادي حضرموت» is Yemen's antiquities body; the authority had put that exact name
  under Syria (whose body is «المديرية العامة للآثار والمتاحف»). Found while judging, fixed in the authority.
- «جامعة العلوم التطبيقية - شفا بدران - عمان»: the machine gave Oman; Shafa Badran is in Amman (Jordan).
- «عضو اتحاد الكتاب التونسيين عضو رابطة الأدب الحديث بالقاهرة» was first one body (Tunisian writers); the
  printed-country check (EG ≠ TN) flagged it: two bodies.
- «COLLEGE OF EDUCATION - GAZA» (1998) in Al-Aqsa University's own journal: Al-Aqsa's predecessor (medium, context).
- «مركز العلوم الجيدة الكبرى» read as a literal translation of UC Berkeley's Greater Good Science Center (medium).
- «عضو المجمع» in the Cairo Academy's own journal → that academy (medium); «بالمعهد» × 6 in one article → the
  Higher Institute of Social Work the first author is dean of (medium).
- Left **unsure**: «الجامعة الإسلامية» alone (Madinah? Gaza? Baghdad? Lebanon?), «دائرة الأرصاد الجوية» (Jordanian
  co-authors, not enough), «Higher institute of information Technology», «مصلحة الضرائب», «وزارة التجارة», a
  ministry library, the army and a veterans' association (1957), «مكتب الخبراء بالمكتب الفني».
- Kept apart, not lumped: «كلية الآداب - بغداد» (1974: Baghdad and al-Mustansiriyah both have one), «كلية التربية
  الأساسية» (Kuwait's PAAET and Iraqi universities both), «كلية التجارة بدمنهور» (Alexandria's branch or
  Damanhour University), a 1952 «كلية الحقوق», a Faculty of Arts with archaeology and museums (2000).

## Rules learned (each measured against the librarian's own 659 verdicts)

| rule | fires | reproduces | differs |
|---|---|---|---|
| R1 printed form: the statement contains an authority form (longest wins) → that body | 520 | 517 | 3 (statements naming two bodies: the rule picks one) |
| R2 the university over its unit: a centre/institute/faculty printed with a university → the university (the machine reads the department first) | 46 | 43 | 3 (a former post or a second body printed first) |
| R3 a generic body («وزارة التربية», «مجلس الدولة») is resolved only by a printed country; none → unsure | 9 | 8 | 1 (the journal's country used as context) |
| R4 a faculty printed with only its city → that city's one public university (15-city table: Fès, Rabat, Tétouan, Agadir, El Jadida, Casablanca, Marrakech, Tunis…) | 18 | 17 | 1 (the Faculty of Arabic Language in Marrakech is Al-Qaraouiyine's) |
| R5 an unnamed «بالمعهد» / «بالجامعة» / «عضو المجمع» → the body named elsewhere in the article or the journal | 9 | 8 | 1 («بالكلية» named nothing) |
| R6 no body printed: a place, a position, a degree, a bare head word («بالكلية», «بالجهاز») → not an institution | 57 | 56 | 1 |
| R7 a name shared by two bodies needs a printed place | 1 | 1 | 0 |
| R8 a printed country that differs from the institution's → hold for a person | caught 1 in the pass | | |

The authority itself is the main "rule": 280 entries, 3–6 printed forms each. With it, 662 of 908 decisions are
deterministic; what needs a model is the long tail (new names, damaged OCR, context, world knowledge).

## Scale

Measured here: 659 packets (0.84 per article; gate 1's education journal prints 1.66), a packet ≈ 1,320 characters
of evidence (median 1,240, max 3,150) and its decision ≈ 545 characters; with 8 candidate authority entries
(≈ 210 characters each) that is ≈ **1,200 tokens in, 330 out per packet** at an assumed 2.5 characters a token
(Arabic-heavy JSON; not measured — counting tokens is an API call; range 2–3.5), plus ≈ 4,000 tokens of instructions
cached across calls. Per 1,000 articles: 845 packets, ≈ 1.3M tokens if every packet goes to the model, ≈ 0.19M if only
the judgement cases do (14% of affiliation packets) — plus the institution-level questions.

What grows with what: affiliation packets grow linearly with documents; the authority and the institution-level
questions grow with **distinct institutions**, which grow slower (on the 780: distinct ≈ 1.35·n^0.78, Heaps' law;
an extrapolation, to be re-measured at gate 2).

| | packets to the model | institution questions | tokens in / out | Batch API list price, Opus 5.5 / Sonnet 5.5 / Haiku 4.5 |
|---|---|---|---|---|
| 162,816 education articles, every packet to the model | 137,559 | 9,936 | 189M / 48M | $914 / $486 / $243 |
| 162,816, rules first (0.84 affiliations per article) | 19,830 | 9,936 | 48M / 9M | $198 / $105 / $53 |
| 162,816, rules first, gate 1's density (1.66 per article) | 38,932 | 9,936 | 71M / 15M | $314 / $167 / $84 |
| 1M documents, rules first | 121,795 | 40,842 | 245M / 51M | $1,060 / $563 / $281 |

Prices: list $/1M tokens in / out — Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 4.5 $1 / $5 (the claude-api
reference, cached 2026-09-25), Batch API 50% off, cached instructions at the cache-read price. Formula:
`cost = 0.5 × (tokens_in × p_in + tokens_out × p_out + cached × p_cache) / 1e6`. Check the console before spending;
the output overhead (×1.5 for thinking/format) is an assumption too.

## What it changed

- A Desk page `/librarian` and API `desk/librarian.py` (registered at the end of `desk/api.py`), table
  `librarian_verdicts` (append-only; `desk.cli init` creates it), a "Librarian" item in the top bar. Tests:
  `experiments/49_correction_desk/tests/test_librarian.py` (6: token required; superseded and retired decisions left out;
  filters and refused inputs; one decision with its packets; verdicts stored, latest shown, append-only at the
  database; the real files well formed and the sample's 30 ids present).
- Nothing in the platform, the releases or marc.db was written. No paid call was made.
- **Applied on 2026-11-02** ([../64_apply_institutions/README.md](../64_apply_institutions/README.md)), after
  experiment 63's blind check ([../63_verify_institutions/README.md](../63_verify_institutions/README.md)) and the
  owner's choices: 874 of the 908 standing decisions (all but the 10 `unsure`, the 22 `set_type`, O610, the
  country of the Arab News row, and the YE country of the unmerged «جامعتى القاهرة وصنعاء» row) became 1,146 Desk
  decisions of `agent:librarian`, each carrying its exp 56 id, its exp 63 item and verdict, basis and confidence, plus
  one record per body of the authority (237). Exp 63's four errors were fixed first (O351 not an institution, O495
  linked, S107 / S182 two universities with two countries, the row not merged), and the owner's D37 / D38 / D39
  applied (`docs/decisions.md`). Release `R20261102T155701`: 242 institutions (234 here + 7 machine rows the unsure
  statements keep + 4 new bodies − 3 now only former / educated at), 93% with a country (96% leaving out those 7,
  which have none), 70 in
  2+ articles, gate 1 25 vs 6.3. This README's files are unchanged.

## Rough edges

- The ink crop finds the statement by its words on the byline's page: 589 of 659 found; a few land on a footnote
  that shares words (0680's «كلية الآداب» crop shows a CV note); 70 fall back to the byline crop; some pages have no
  image on this server (grey placeholder).
- Faculties and departments under a university are listed per institution (`units` in `out/authority56.json`), not
  yet given ids of their own.
- The type question compares the authority's types with the machine's kinds through a mapping (institute → centre,
  academy → society, school/other → organisation): 22 differences, all high, worth a glance rather than a rule.
- Token counts are estimates from characters; the Heaps extrapolation rests on 780 articles.
- The page reads the experiment's `out/` files; after a new pass the page shows it at once (cached by mtime).

Screenshots: `experiments/56_librarian_institutions/out/shots/` (01 top, 02 full page, 03 a merge, 04 the lumped
«كلية الآداب» split after a "No", 05 parent, 06 country, 07 affiliation fix, 08 unsure, 09–11 filters and the
decision list, 12 numbers, 13 rules, 14 phone width). Progress notes: `progress.md`.

**Run it again** (all read-only, ~1 min):
```
python3 experiments/56_librarian_institutions/marc_authority56.py    # once
python3 experiments/56_librarian_institutions/build56.py
for b in 0 1 2 3 4 5 6 7 8 9 10; do python3 experiments/56_librarian_institutions/judge56.py commit $b; done
python3 experiments/56_librarian_institutions/finalize56.py && python3 experiments/56_librarian_institutions/sample56.py
python3 experiments/56_librarian_institutions/rules56.py && python3 experiments/56_librarian_institutions/scale56.py
```
