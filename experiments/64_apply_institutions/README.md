# Experiment 64: the librarian's institution decisions, applied as Desk decisions

**Question** (owner, 2026-11-02). Experiment 56's librarian made 908 standing decisions about institutions; experiment
63 checked all of them (4 errors, one fault in the data model). Apply them the proper way: as recorded, reversible
Desk decisions that the release is built from, never as silent edits to the platform database. Apply them with
exp 63's fixes, a country per linked body, and three new rules for the whole index:
- D37: a degree-granting university is "educated at", not an affiliation;
- D38: a former post is linked and marked `former`;
- D39: an unnamed body may be filled from the journal's publisher when the wording points to it, marked `inferred`.

**Answer.** Done. The Desk had no institution operations at all, so it gained them: keys, ten operations, release
code with constraint checks, and tests. Then 1,146 decisions of `agent:librarian` were imported through the Desk's
own `ops.decide`. Release **`R20261102T155701`** applied 1,161 decisions (the 1,146 and the 15 older ones), with
0 conflicts, 0 orphans, every constraint holding and 0 foreign-key violations. The live Desk reads it already.

## Before and after (the 780 articles, 659 printed affiliations)

| | machine (`R20261023T005909`) | exp 56's "after" (its own count) | **this release** |
|---|---|---|---|
| institutions (organisation level, current post) | 271 | 234 | **242** |
| … with a country | 114 (42%) | 223 (95%) | **225 (93%)**; 96% leaving out the 7 rows below |
| institutions in 2+ articles | 54 | 69 | **70** |
| affiliations at a current body | 560 | 580 | **591** |
| affiliations with a country (through a body) | 338 | 586 (one field per affiliation) | **572** (per body) |
| gate 1, institutions in 2+ articles: J0130 vs random sets of 126 | 26 vs 3.8 | 25 vs 6.3 | **25 vs 6.3** on the index page (exp 52's measure); 25 vs 6.55 with exp 56's own count |
| former posts / degrees ("educated at") / links marked inferred | – | – | 4 / 4 / 21 |

Numbers: `out/numbers64.json` (`measure64.py`). The index pages show the same numbers through the live API: the
overview says 242 institutions; `/institutions` lists 242; `/index/gate1` gives 25 of 67 vs 48 of 182 (6.3 for
same-size sets). J0130 has 67 institutions, 25 of them in 2+ articles. Cairo University: 14 articles, one fewer than
in the authority, because one statement is now a former post.

**Why 242 and not 234:**
- **+7** machine rows that the 10 `unsure` statements keep. These are «مصلحة الضرائب», «وزارة التجارة», «الجامعة
  الإسلامية» and four more. The design says an unsure answer leaves the machine's reading standing. Exp 56 counted
  these statements as unlinked. None of the 7 rows has a country, so the share drops from 96% to 93%.
- **+4** new bodies: the Integrative Psychology Society (O495), CAPMAS and Ansar al-Sunna (filled by D39), and the
  Palm Strategic Initiative Centre. That centre is the post printed beside a degree (D37); its country is not printed
  and was not guessed.
- **−3** bodies that no statement names as a current post any more: Arab News (O351: a reprint source), the
  University of Malaya (now educated at) and the Lebanese Council of Ministers (now a former post).

The 591 affiliations come from 580 + 9 (O495 and the 8 D39 fills) − 1 (O351) − 5 (statements whose only body is now
educated at or former) + 8 (the unsure statements that keep a machine row). Exp 56's 586 "with a country" counted its
single country field, including statements that name no body. Here a statement has a country only through a body it
names.

## What the Desk needed (and got)

Nothing for institutions existed: `keys.OPS` held works, persons and back references only. Added (in
`experiments/49_correction_desk`):
- **Keys.** `aff:<stem>|b<byline>|<script>|a<n>`, one printed affiliation (exp 56's key), beside the existing
  `inst:I…`. A new body's id is `authority_inst_id(<authority id>)` and a split's new row is
  `split_inst_id(<decision>, <group>)`. Both are deterministic, so every build mints the same ids.
- **Operations.** These are validated in `ops._prepare_institution` and applied by `release.Builder.op_*` in build
  phases 5–9:
  - phase 5: `define_institution`;
  - phase 6: `same_institution`, `not_an_institution_row`;
  - phase 7: `set_inst_country`, `set_inst_parent`, `set_inst_type`;
  - phase 8: `link_affiliation` (each body with a role `current` | `former` | `educated_at`, and optionally
    `inferred`), `not_an_institution`, `unit_kept_apart`;
  - phase 9: `not_same_institution`. Splits come last: by then the affiliations sit on their own bodies, so the split
    only moves the faculty links the machine lumped.

  Ownership is the Desk's usual rule. A second answer on the same statement by someone else is refused with "leave a
  note", and the owner must supersede their own.
- **Constraint checks.** Each decision registers what must stay true, and the release re-checks it after every
  decision that touches it. Change-log triggers on `affiliation_links`, `institutions` and `merged_ids` say what a
  decision touched. Everything is checked again on the final state. The checks:
  - the statement's current / former / educated-at bodies are exactly the decided ones, each in its decided country;
  - merged rows resolve to one row;
  - a row that names no body has no links;
  - a parent is the decided one, and a cycle is a conflict;
  - a split's groups share no institution.

  Run here: 5,890 checks.
- **The release** writes former and degree links to `affiliation_links` with level `former` / `educated_at`. Every
  counter that reads `level = 'org'` (the index pages, gate 1's `measure52`, the Explorer) leaves them out with no new
  code. `counts()` reports institutions linked, merged, former and educated at, and the fingerprint covers the
  institution tables.
- **Index and Explorer, 3 small edits.**
  - The index counts every body a statement names; it counted the first, so Sana'a was missing from «جامعتى القاهرة
    وصنعاء».
  - A body is named by its label first.
  - An institution's page and the Explorer's output columns leave out former and educated-at links.
- **The type list.** `keys.INST_TYPES` now includes hospital, union and regional_education_authority. The 22
  `set_type` decisions are still to be re-decided.
- **Schema.** No new table. The ten review rules (one key) are under the idempotent-upgrades mark (`desk.cli init`).
- **Tests.** `experiments/49_correction_desk/tests/test_institutions.py` (2), on a small reading built with platform v2's own schema. It covers:
  - refusals, ownership and the validation of each operation;
  - merges and a merged id used later, a lumped faculty split under two universities, a ministry split, a row that
    names no body;
  - a centre the machine took for the university kept as its unit, a former post, two bodies in two countries;
  - the index counts, a parent cycle as a conflict, a rebuild with the same fingerprint, and a revert that brings the
    machine's link back.

  The Desk suite passes, 76 tests (`.venv/bin/pytest -q tests`, 5 min).

## What was imported (`plan64.py` → `import64.py`), by kind

| Desk operation | n | from |
|---|---|---|
| `define_institution` | 237 | the authority's 234 bodies, minus Arab News, plus 4 new. 194 use a machine row (the one carrying the body's name, else the most linked); 44 are minted. Of the minted, 18 had no machine row, 4 are new, and 22 had only rows that were a unit or a split row |
| `same_institution` | 30 | exp 56's 30 merges (S182 without the row «جامعتى القاهرة وصنعاء») |
| `not_an_institution_row` | 6 | exp 56 («بالكلية», «بالجهاز», «للجماعة» …) |
| `set_inst_country` | 175 | 132 exp 56 decisions: O610 (Arab News) is dropped, and so is D56-ed1d2f8bb3b0, which gave the row «جامعتى القاهرة وصنعاء» YE as part of S182's merge. 42 come from the authority for rows still without its country (3 of them new bodies). 1 is D39 (S201: the bibliographic centre that publishes J1510, EG, inferred) |
| `set_inst_parent` | 40 | exp 56's 48 set_parent. The 8 on the two lumped «org:?» faculty rows are carried by their splits, which give each group's row its university |
| `link_affiliation` | 588 | 579 of exp 56's 580 (O351 dropped) + O495 + 8 D39 fills |
| `not_an_institution` | 56 | 64 − 8 (now D39 links) − O495 + O351 |
| `unit_kept_apart` | 5 | exp 56 |
| `not_same_institution` | 9 | exp 56's 9 splits |
| not imported | 34 | the 10 `unsure` (the machine's reading stands), the 22 `set_type` (types stay proposals), O610 and D56-ed1d2f8bb3b0 (above) |

Each decision's `evidence.provenance` holds:
- exp 56's decision id, qkey, kind, basis, confidence, reason and time;
- exp 63's item (S### blind / O### open) and its verdict;
- the fix or rule applied (`exp63-error`, `D37`, `D38`, `D39`, `authority56`, `exp64-new-body`).

`reason_code` is `librarian:<rule>`, and the confidence maps high → sure, medium → likely, low → unsure (D39 fills:
likely). `evidence.source_id` makes the import idempotent. The actor `agent:librarian` is an agent with role
corrector; the design has no dedicated role, and all correctors are equal.

**The fixes and rules, case by case.**
- **Errors (exp 63):**
  - O351 «عن صحيفة عرب نيوز»: not an institution;
  - O495 «جماعة علم النفس التكاملى»: linked to the new body;
  - S107 «كلية التربية - جامعتى القاهرة وصنعاء»: Cairo (EG) and Sana'a (YE), each with its country;
  - S182: the row is not merged.
- **D37 (educated at):**
  - O014: Malaya, plus the Palm centre as current;
  - O402: Umm Al-Qura;
  - S214: Cadi Ayyad;
  - O007: Mohammed V, the «كلية الآداب - الرباط» doctorate, beside CRMEF Settat as current.
- **D38 (former):**
  - S160 Zagazig;
  - O448 Cairo (KISR current);
  - O459 SQU;
  - O337 the Lebanese Council of Ministers.
- **D39 (filled from the journal's publisher, inferred, likely):**
  - S069 «قسم التاريخ» → KAU (J0389);
  - S165 «قسم اللغة العربية» → Baghdad (J0739);
  - S212 «قسم التصميم الصناعي» → Helwan (J0241);
  - S199 «بالكلية» → Imam University (J0290);
  - S137 «رئيسة شعبة بحوث» → CAPMAS (J0700);
  - S088 «فرع الإسكندرية» and O479 «الرئيس العام للجماعة» → Ansar al-Sunna (J0596);
  - O499 «العضو المراسل من تونس» → the Cairo academy (J0692).

  Exp 56's own 13 context links where the body is not printed by name are now marked inferred: 7 from the journal
  («عضو المجمع» ×2, «بالجامعة», the Faculty of Law → Cairo, the College of Economics → KAU, College of Education
  Gaza → Al-Aqsa ×2) and 6 from the article («بالمعهد» ×6).

**Examples (before → after, in the release):**
- «كلية التربية - جامعتى القاهرة وصنعاء»: the row «جامعتى القاهرة وصنعاء» (no country) → جامعة القاهرة (EG) +
  جامعة صنعاء (YE).
- «مستشار أول بمعهد الكويت للأبحاث العلمية وأستاذ بكلية الهندسة، جامعة القاهرة سابقا»: KISR only → KISR (KW,
  current) + Cairo (EG, former).
- «A Ph.D. … from the University of Malaya and director of Palm Strategic Initiative Centre»: Malaya → Malaya (MY,
  educated at) + the Palm centre (current, no country).
- «الاستاذ المساعد بقسم القرآن الكريم وعلومه بالكلية» in J0290: the row «بالكلية» → Imam University (SA, inferred),
  with the department kept.
- «عن صحيفة عرب نيوز» → nothing.

## For the owner (not applied; flagged)

- **O170, the AGU line.** The line is «أستاذ تربية الموهوبين المشارك قسم تربية الموهوبين- كلية الدراسات العليا
  (سابقا) جامعة الخليج العربي». Exp 63 listed it among the former posts. Here «(سابقا)» follows the college's name: it
  says the college was renamed, not that the post ended. So the link stays current (D38 is about the post). If you
  read it as a former post, `agent:librarian` (or an admin) supersedes that one decision.
- **S116, the Al-Zahraa University Hospital.** It is left as exp 56 has it, country open. The article's abstract
  places it in Cairo, but nothing points to the journal's publisher, so D39 does not apply.
- **Other degree lines** do not name a degree-granting university as the only body, so D37 changed nothing there.
  For example, «… الجامعة الإسلامية العالمية ماليزيا، دكتوراه التفسير من الجامعة الوطنية الماليزية» keeps IIUM as
  current and leaves the degree unlinked. Doctoral students («طالب دكتوراه») are current affiliations.

## Rough edges

- 19 of 588 faculty / department links sit under a body other than the statement's (10 have no parent, 8 another
  body, 1 a row that names no body). Exp 56 kept faculties as text per institution and gave them no ids of their
  own. The «كلية التربية» of the Cairo + Sana'a line is one of them.
- The Explorer's institutions tab now has 753 rows: 701 machine rows, 44 minted, 8 split rows. It includes 34 merged
  and 6 not-an-institution rows; their `status` says which.
- 7 linked rows hold no country: they are the rows of the unsure statements.

## Reversibility

- **One decision:** its owner (`agent:librarian`) or an admin reverts it (`POST /desk/api/decisions/{id}/revert`, or
  `ops.revert`), or supersedes it with a corrected one. The next release puts the machine's reading back for it.
  `experiments/49_correction_desk/tests/test_institutions.py` does this.
- **The whole pass:** revert the 1,146 decisions of `agent:librarian` (one superseding revert each; the
  originals stay, append-only) and build a release.
- **Point the Desk back at once:** the previous release copy `R20261023T005909.db` is still on disk. The release was
  built with `--keep 3`, so nothing was pruned; `R20261022T233109.db` is also kept. The Desk reads the newest built
  release, so pointing it back means setting the new release's `copy_deleted_at` or moving its file. Prefer the revert.
- **Backups (taken first):** `~/data/desk/backups/desk_schema_before_exp64_20261102T094457.dump` (`pg_dump -Fc -n desk`;
  restore with `pg_restore -d inkdesk --clean -n desk <file>`) and `.sql`. The code files before the change are in
  `~/data/desk/backups/code_before_exp64/`.

## For the lead

Nothing needs a restart. The live API (`desk.cli serve`, started 09:55:42) already runs this code: the last edit was
at 09:54:54. It reads the new release: the overview, `/institutions`, `/journals/J0130` and gate 1 show the numbers
above, and the Explorer and the field guide answer from `R20261102T155701`. No web file changed, so there is no
rebuild. If the API is ever restarted from older code, run
`cd experiments/49_correction_desk && .venv/bin/python -m desk.cli serve`. A throwaway test schema `test_e64dry` (the
dry run) and a 1 GB scratch copy of the dry-run release in this session's scratchpad can be dropped or deleted.

## Files

`plan64.py` (exp 56 + 63 → `out/plan64.jsonl`, `out/plan64_summary.json`), `import64.py` (→ the Desk, idempotent;
`out/import64_desk.jsonl`), `measure64.py` (→ `out/numbers64.json`), `progress.md`. Run it again:
```
python3 experiments/64_apply_institutions/plan64.py
cd experiments/49_correction_desk
.venv/bin/python ../64_apply_institutions/import64.py            # skips what is already imported
.venv/bin/python -m desk.cli release --keep 3 --note "…"
.venv/bin/python ../64_apply_institutions/measure64.py /home/appuser/data/desk/releases/R20261023T005909.db /home/appuser/data/desk/releases/<new>.db
```

## What it changed

- The Desk: institution keys and operations, their release application and checks
  (`desk/keys.py`, `ops.py`, `reading.py`, `release.py`, `db.py`, `schema.sql`), the index (`index_pages.py`), the
  Explorer (`explore.py`), `experiments/49_correction_desk/tests/test_institutions.py`. Its README has a section "Institution decisions".
- The Desk database: actor `agent:librarian`, 1,146 decisions, release `R20261102T155701`. The platform database
  (`platform_v2.db`) was only read.
- `docs/decisions.md` D37–D39; `docs/STATUS.md`; experiment 56's README ("What it changed"); the project page's
  timeline. No paid call was made.
