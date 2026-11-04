# Experiment 68: take the extraction fixes live (experiment 65's leak fixes + experiment 66's D30 guard)

**Question** (owner-approved, 2026-11-02: steps 1–3 of experiment 61's leak plan, and the D30 guard). Integrate the
guard, rebuild the four current runs with both, load them into the platform, replay every Desk decision on the new
reading, and make it the live state — carefully, reversibly, with ids stable and nothing double-counted.

**Status: LIVE since 2026-11-02 17:16 (release R20261102T231619, switched by the lead after deciding the 3 orphans are harmless re-anchor tasks). Written at 17:10 as "ready, not live":** Everything up to the live switch is done and verified on copies. The
dry-run release replays every decision except **3 orphans** (and the known demo conflict on «المقدمة»). The lead
asked to stop before going live on orphaned decisions, so `platform_v2.db`, the Desk schema and the releases are
untouched. The 3 orphans are explained below. They look benign. One script, `golive68.sh`, makes it live.

## Answer

| step | result |
|---|---|
| 1. guard integrated | `d30guard.patch` applied (rules43 hook + `fixes_refused_d30`; masters.py `content-type = kind`). parse47 loads a refused fix as its own layer `model-suggestion` (applied_to_text 0): an inline span, or, for the 7 + 2 + 2 + 3 on lines no block holds (running heads), the back note's "D30 guard" why. Tests: experiment 43 (84), 47 (`test_ids47`), the Desk (93, with the new `experiments/49_correction_desk/tests/test_twins.py`) |
| 2. rebuild | `build68.sh` → `43_rehearsal/out/<run>_fix61_d30/` (4 new folders; nothing overwritten), all 781 masters DTD / XSD valid, peak 0.80 GB |
| text vs experiment 65 | `compare68.py`: every ALTO word and JATS block identical **except the guard's refusals**: 409 changed spots (alto 409 chunks, blocks 398), **0 unexplained** |
| refusals | **409** (simulate66: 408, all 408 found + 1 the simulation missed: 0732-019-222,224-040 «والفسوء»/«والضوء»): j0130 20, v2 36, exam 154, first 199. **Every one is a flag** (back note `suspected-misprints` with the guard's why; 395 also inline as `named-content[@content-type="model-suggestion"]`, 14 on running-head lines have the note only); **none is applied** (0 in reader-fixes). In the platform: 408 rows `text_corrections.layer = 'model-suggestion'` (the 409th is in v2's 55th master, not a shown version) |
| 3. backups | `~/data/platform_v2/backups/platform_v2.before_exp68_20261102T150931.db` (quick_check ok), `link_cache47.before_exp68_20261102T150931.json`; `~/data/desk/backups/desk_schema_before_exp68_20261102T150931.dump` + `.sql` |
| 4. load + link | into a **copy** (`~/data/platform_v2/golive68_work6.db`, `load68.sh`: load47 ×4 + link47 with its own cache `out/linkwork6/`), 0 orphans, integrity ok. Id stability below |
| 5. release | dry runs in throwaway schemas (`dryrun68.py`, `test_e68*`): **2,738 applied, 3 orphaned, 1 conflict (the demo «المقدمة»)**, every constraint holds, 0 foreign-key violations; 34 decisions found their moved line; fingerprint `7734ba04…` |
| 6. live | **not done** (stopped on the 3 orphans as asked). `golive68.sh` does it; then restart the API (below) |
| 7. audit | run on the candidate release: generic-only lines **1,457 → 808**, accounted **99.665% → 99.814%** (exp 65's candidate: 805 / 99.815%; +3 from the guard, below). The /audit page pointer is ready (`desk/audit.py`), not switched |

## The 3 orphans (why it stopped)

All three are English lines that experiment 65 no longer reads as lines of their own: its fix M2 joined each
English affiliation to its Arabic twin, and on these two articles the English lines were printed run together, so
the English twin is now one combined line.
- `link_affiliation aff:0130-019-074-002|b0|Arab|a3` («Ministry of Education») → Ministry of Education (Kuwait).
  The line is now inside the English twin «Psychological Researcher, Ministry of Education Faculty of Basic
  Education …», which takes the Arabic line's decided bodies (Kuwait's ministry among them).
- `link_affiliation aff:0130-027-105-001|b0|Arab|a3` («Faculty of Educational Sciences، Department of Educational
  Management، AIU») → AIU. The line is now inside the combined twin of the Arabic line, which names AIU and
  Alexandria.
- `set_inst_parent inst:IRV1KRDSVW → AIU`. That row was the English «Faculty of Educational Sciences»; no line
  produces it now.

Nothing counted is lost with them: AIU, Kuwait's ministry and their articles stay linked through the Arabic lines.
The release would give each one a re-anchor task for `agent:librarian`, as the Desk design says. The lead decides
whether that is acceptable or whether the librarian should first re-answer them on the new keys.

## What had to be fixed for the replay (found by the dry runs)

The first load replayed with **62 orphans** and showed re-minted ids. Four causes, each fixed and re-measured
(loads 1 → 6, all on copies):

1. **Institution ids vanished** (99 machine rows, 10 named by Desk decisions). inst46 names each cluster by one of
   its printed names, and the twin rows changed which name wins: «وزارة التربية» became
   «وزارة التربية بإقليم كردستان العراق»'s key. Reloading an article also gives its affiliations new `aff_pk`s, so
   link47's own continuity rule never fired. `biblio47.refresh_institutions` now carries a vanished id into
   `merged_ids`, pointing at the row that now holds most of its printed affiliations. The affiliations are found by
   place, by text, or by clear word overlap (0.5 or more, no tie). The target must be the same body by name:
   - one name's words contain the other's in the same script;
   - names only in different scripts pass.

   The second condition was added after a dry run carried AIU into Alexandria University: the machine now reads only
   Alexandria from «… جامعة أكاديميون العالمية … جامعة الإسكندرية». Result: 93 vanished ids resolve, 14 do not, and
   2 of those are Desk-named.
2. **Affiliation keys moved** (45 of the 649 decided keys):
   - 34 English lines now hang on the twin's mention. `Reading.aff_moved_twin` finds them by the decision's recorded
     printed text, exactly or by clear word overlap.
   - Bylines were renumbered when the Latin names folded into their Arabic twins (1956-017-002-013: `b2` → `b0`).
     `Reading.aff_by_text` finds those by text within the article, keeping byline order.
   - 20 bylines had an empty name in the rebuilt v2 masters. A parse46 bug read only a `string-name` directly under
     `contrib`; it now also reads the printed-on-the-page form and the `name` inside `name-alternatives`.
3. **A Desk-defined body the machine no longer reads**: «مستشفى الزهراء الجامعي» (S116) and AIU.
   `define_institution` now re-makes a registered machine id as the decision saw it (`evidence.was`: kind and
   country), as it already did for new bodies.
4. **A split with one vanished member** (Ministry of Education Kuwait / Yemen / Tunisia) was orphaned whole. Now the
   split stands on the members still printed. It is an orphan only if none is left.

Plus the twin rows themselves (what experiment 65 warned about). An English twin row that no decision names takes
its Arabic line's decided bodies (`Builder.inherit_twins`: 103 rows), so the machine's stray English rows do not
show. Every count skips twin rows (`twin_of_aff_pk IS NOT NULL`):
- the release's `counts()`;
- `index_pages` (overview, institutions, gate 1);
- the Explorer;
- `measure52` (gate 1);
- `measure64`.

## Ids (`ids68.py`, `out/ids_compare6.json`; before = live `platform_v2.db`)

| | before | still the same row | through merged_ids | not resolvable | new ids |
|---|---|---|---|---|---|
| persons A… | 1,948 | 1,947 | – | **1** (AXVWVFESMK, a provisional person keyed on a citation mention whose word span moved) | 0 |
| institutions I… | 701 | 594 | **93** | **14** (none named by a Desk decision except AIU and the hospital, re-made by their define decisions, and IRV1KRDSVW, orphan 3 above) | 75 (inst46 cluster keys; Shaqra and the Simber group now have new ids, the old ids redirect) |
| cited works C… | 9,157 | 9,128 | 3 | **1** (CASB9YEXQR «حاشية عبادة على الشذور»: its only reference's word span moved) + 22 that were already merged without a target before (one, CRTJTVTZSQ, is named by a Desk decision and resolves inside the release as before) | 58 (the references M7 now parses) |
| publications W… | 2,018 | 2,018 | – | 0 | 0 |

Every id a Desk decision names resolves in the dry-run release except IRV1KRDSVW (orphan 3).

## Before / after (live R20261102T174226 vs the candidate release; `out/numbers68_dry.json`)

| | live | candidate | why |
|---|---|---|---|
| institutions (org, current) | 242 | **242** | same; Shaqra and the Simber group under new ids (redirected) |
| … with a country | 225 (93%) | **225 (93%)** | |
| in 2+ articles | 70 | **70** | |
| printed affiliations (counted rows) | 659 | **624** (+136 twin rows not counted) | 35 English lines that were rows of their own are now twins of their Arabic line; 1 combined (orphan 1/2); 1 new English-only line |
| affiliations at a current body | 591 | **556** | the same 35 (all were linked) |
| affiliations with a country | 572 | 537 | the same 35 |
| educated-at links (all rows) | 4 | 5 | one twin row inherits its line's "educated at" (measure64 counts links on every row) |
| gate 1 institutions in 2+ articles | 25 of 67 vs 6.3 | **25 of 67 vs 6.3** | |
| cited works | 8,850 | **8,903** | +53: references with no card 1,276 → 1,219 (M7 hyphen breaks now parse their titles: 57 new cards, 27 articles) |
| cited by 2+ / 3+ | 288 / 79 | **291 / 79** | 3 of the new cards are shared |
| gate 1 shared works | 118 vs 16.7 | **121 vs 16.7** | the same new cards |
| held (all / journal / random 600) | 6.64% / 16.84% / 2.57% | **6.63% / 16.84% / 2.56%** | 909 → 908: one reference (0201-000-044-001 p20) where the guard kept Azure's «الريوي» instead of Gemini's «الربوي» (both misreadings of التربوي) and the linker no longer matches it; references 13,695 → 13,696 (one split in 2483-000-003-017) |

## Audit (experiment 61's code; `out/audit/audit.json`, `out/before_after.md`)

| | exp 61 (live /audit page) | exp 65 candidate | **this candidate** |
|---|---|---|---|
| lines only in generic text | 1,458 (1,457 same-code) | 805 | **808** |
| accounted lines | 99.665% | 99.815% | **99.814%** |
| mapping / not asked / gemini missed | 953 / 556 / 52 | 292 / 437 / 46 | **296 / 437 / 46** (`before_after.json`) |

The +3 against experiment 65 are lines where the guard kept the print and Gemini's metadata holds the corrected
word, so the line no longer matches its field: 2384-001-001-003 «مناع القصان» (an author name),
0763-004-002-001 «ترجها للغة العربية» (a role, experiment 66's printed misprint), and 0018-004-003-005 «خريج
المعلمين العليا». The audit took 110 s on 3 workers, peak 0.19 GB.

## Looked at (the three check articles, `out/look/sheet_0*.jpg`)

- **1010-001-011-014**: fixes 364 → 349 and 15 flags, as experiment 66 found. On the scan the print shows «الصي»,
  «يرد», «ذون», «انها», «فا»: printed misprints, now kept as printed with Gemini's word beside them.
- **1080-002-010-015** (the tan scan): 14 refusals. «وقيما», «بقول», «زابعة», «حبادية» are dotted as printed, so
  they are right to keep. «حال» (8:36) is right. «جيهة», «بحطم» are faded and hard to call.
- **0005-055-003-004** (faded print): 6 refusals. «عمى», «العاوم», «تعم», «تقيل» are faded lam and nun. Azure's
  misreadings stay in the text, flagged. This is the guard's known cost from experiment 66, and a corrector can
  accept the suggestion.

## Make it live (for the lead)

```
cd /home/appuser/inkscript
bash experiments/68_go_live/golive68.sh       # backups, reading copy, link cache, release --keep 7, audit, /audit pointer
cd experiments/49_correction_desk && .venv/bin/python -m desk.cli serve      # restart the API (stop the old one first)
```
Expect the dry run's numbers: 2,738 applied, 3 orphaned, 1 conflict, and fingerprint `7734ba04…` if no decision
changed meanwhile. **The API must restart** because the running process has not loaded the new code:
- the twin-row filters in `index_pages` / `explore` (without them the Explorer and the gate-1 share count the 136
  twin rows);
- the `model-suggestion` layer on the page view (`pipeline.py`);
- the audit pointer (`audit.py`).

No web file changed, so there is no web rebuild.

## Reverting

- **Before going live:** nothing to revert. The live DB, the Desk schema and the releases were not written. The
  copies `golive68_work*.db` and `test_e68*` schemas are scratch.
- **After `golive68.sh`:**
  1. Copy the backup back: `~/data/platform_v2/backups/platform_v2.before_golive68_<T>.db` → `platform_v2.db`
     (backup API), and the link cache likewise.
  2. Set the new release's `copy_deleted_at` (the Desk then reads R20261102T174226 again), or build a release on
     the restored reading.
  3. `rm ~/data/desk/audit_current` (the page falls back to experiment 61's audit).
- **Code:** the files before this experiment are in `out/code_before/`. The guard alone: revert the two hunks of
  `d30guard.patch` (`git apply -R`) and rebuild.

## Files

- `build68.sh`: the four rebuilds, refusing existing folders.
- `compare68.py`: text proof, refusals, flags.
- `load68.sh [DB]`: load ×4 + link47 into a DB, default a copy.
- `ids68.py`: id snapshot and compare.
- `affkeys68.py`: Desk affiliation keys against a DB.
- `dryrun68.py`: release in a test schema.
- `numbers68.py`: experiments 64 / 67 measures and gate 1.
- `golive68.sh`: the live switch, for the lead.
- `progress.md`.

`out/` (gitignored) holds the compare, ids, dry runs, numbers, audit, logs, contact sheets and `code_before/`.

Code changed:
- 43 / 41: the patch.
- `47_platform_v2`:
  - `parse47.py`: model-suggestion layer;
  - `load47.py`: `_fix61_d30` runs;
  - `biblio47.py`: institution id continuity;
  - `schema47.sql`: comment.
- `46_platform_db/parse46.py`: the empty printed name.
- `49_correction_desk`:
  - `release.py`: moved keys, twin inheritance, define re-make, split tolerance, twin-free counts;
  - `reading.py`: `aff_moved_twin`, `aff_by_text`;
  - `index_pages.py`, `explore.py`: twin filters;
  - `pipeline.py`: model-suggestion shown with the flags;
  - `audit.py`: audit pointer;
  - `experiments/49_correction_desk/tests/test_twins.py`.
- `52_journal_gate1/measure52.py`, `64_apply_institutions/measure64.py`: twin filters.
- `61_nothing_lost/audit61.py`: `_fix61_d30`.
- `65_fix_leaks/before_after65.py`: `--outdir`.

No paid call.

**Can be deleted (proposed, not done):**
- `~/data/platform_v2/golive68_work.db`, `_work2.db` (partial), `_work3.db`, `_work4.db` and `_work5.db`: the five
  superseded load attempts, about 1 GB each;
- `out/linkwork*` except `linkwork6`;
- the throwaway schemas `test_e68base`, `test_e68w1`, `test_e68w3`, `test_e68w4`, `test_e68w5` and `test_e68w6`;
- the dry-run releases in this session's scratchpad.

Keep `golive68_work6.db` and `out/linkwork6` until the switch.
