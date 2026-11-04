# Experiment 67: the librarian's cited-work decisions, applied as Desk decisions

**Question** (owner, 2026-11-02). Experiment 62's librarian made 2,605 standing decisions about the cited works of
the 780 articles and verified them without the owner (two blind rounds, adjudication, hard checks). Apply them the
proper way, as experiment 64 did for institutions: recorded, reversible Desk decisions that the release is built
from, never silent edits to the platform database. Apply under exp 62's APPLY rule, with five new rules for the
whole index:
- **apply:** edition of, same work, split, card is one work, not a work, related, part of, and the 696 links that
  pass rule K1c (title, author, year and venue fit);
- **hold** (they stay proposals): the other 217 links, different works, no link, every unsure;
- **D40** «صحيح مسلم بشرح النووي» counts as Sahih Muslim, al-Nawawi's commentary recorded as its edition;
- **D41** the DSM's editions are one work, each edition kept;
- **D42** a chapter cited under its own author is its own work, part of the collective book;
- **D43** a thesis and the article drawn from it are two works, related ("derived from");
- **D44** the same text in two journals: link the citation to the one Mandumah holds, marked "same text".

**Answer.** Done. The Desk had only the basic work operations (split, same, not the same, move, type, confirm), so it
gained a publication key and six operations, with constraint checks, release code and tests. Then 1,581 decisions of
`agent:librarian` were imported through the Desk's own `ops.decide`. Release **`R20261102T174226`** applied 2,741
decisions (the 1,581, exp 64's 1,146 and the 15 older ones): 0 orphaned, every constraint holding, 0 foreign-key
violations, and 1 conflict (below). The live API reads it already.

## Before and after (the 780 articles, 13,695 references, Quran and hadith out)

| | machine (`R20261102T155701`) | exp 62's "after" (its own replay) | **this release** |
|---|---|---|---|
| cited works | 9,137 | 8,850 | **8,850** |
| cited by 2+ articles / 3+ | 209 / 58 | 289 / 79 | **288 / 79** |
| gate 1: the journal's works cited by 2+ vs random sets of 126 | 84 vs 10.85 (7.7×) | 118 vs 16.65 (7.1×) | **118 vs 16.7 (7.1×)** |
| references landing on a work Mandumah holds: all / J0130 / random 600 | 6.24% / 15.82% / 2.43% | 7.34% / 18.06% / 3.07% | **6.64% / 16.84% / 2.57%** |

Numbers: `out/numbers67.json` (`measure67.py`, finalize62's definitions on the release). The index pages give the
same through the live API: the overview says 8,850 cited works, 288 cited by 2+ articles, 6.6% (909 references → 825
Mandumah publications); `/most-cited` has 8,850 works, 288 cited by 2+; `/journals/J0130` 118 shared works and 16.84%
held; gate 1's "cited works shared by 2+ articles" row is 118 vs 16.7 (154 in the random 600). Most cited: لسان
العرب 24 articles, المقدّمة 13, وفيات الأعيان 10, كتاب سيبويه 8, then 7 each for معجم الأدباء, الكامل, معجم البلدان,
القاموس المحيط, كشف الظنون and the DSM.

**Why it differs from exp 62's "after":**
- **Held share 6.6%, not 7.3%.** Exp 62 counted all 913 of its links. The 217 outside K1c are held as proposals: their
  cards carry 243 references, 109 of them now on no link (the other 134 keep a machine link). D44's 9 same-text
  links add 9 references. Exp 62 also took back the machine's links on 3 cards whose relation named another record;
  here a relation rejects only a link to its own record, so those 3 keep theirs.
- **288 cited by 2+, not 289.** D42: the two chapters exp 62 had joined as one book are cited by one article each.
- **8,850 works, the same total, from four changes that cancel:** D40 joins «صحيح مسلم بشرح النووي» into Sahih Muslim
  (−1); exp 62's edition_of between that card and al-Nawawi's «شرح صحيح مسلم» is not applied (+1); D42 keeps the two
  chapters apart (+1); the conflict below keeps «المقدمة»'s stray preface on the card (−1).
- Cited works 8,850 counts the cards references land on. The book D42 made has no citation of its own, so it is not
  among them; the Explorer's works tab (9,215 rows) lists every card, merged and not-a-work ones with their status.

## What the Desk needed (and got)

The work operations of P1 were there (`split_work`, `same_work`, `not_same_work`, `move_member`, `set_work_type`,
`confirm_work`). Missing were editions, not-a-work, a work no citation names by itself, links to Mandumah and
relations. Added (in `experiments/49_correction_desk`):
- **Key:** `pub:W…`, a Mandumah publication (`publications.pub_id`), beside `work:C…`. A collective book no card
  stands for gets `keys.defined_work_id(<natural key>)`; a card per citation `keys.split_card_id(<decision>, <i>)`.
  Both are functions of the decision, so every build mints the same ids.
- **Operations**, validated in `ops._prepare_work_extra` and applied by `release.Builder.op_*`:
  - **phase 3**, with split_work / same_work in the order made:
    - `edition_of` (two cards, one work; the second card's citations keep an edition of their own; a label is
      possible, D40);
    - `not_a_work` with `drop` (the citations name no work and count for none), `retitle` (one work, given the title
      its citation prints) or `one_per_citation`;
    - `define_work` (a work cited only through its parts, D42);
  - **phase 10**, last:
    - `link_publication` (`as: work`, or `same_text` for D44; it becomes the card's accepted best link, the one the
      index counts). A catalogue record the decision carries is added as a catalogued-only publication W<c999>, with
      its record, contributors and journal, as link47 adds its own targets. 150 publications were added this way;
    - `relate_works` (part of, derived from, same text … between two works, kept apart);
    - `relate_publication` (reviewed in, studied in, derived … with a publication that is not the work; an accepted
      link to that publication is rejected).

  Ownership is the Desk's usual rule: a second answer on the same question by someone else is refused with "leave a
  note"; a card has one link answer.
- **What a decision records** now follows standing splits, moves and drops (`ops.pending_moves`). A same_work on a
  card that a standing split has cut records only the group left on it. Without this, the dry run had 8 conflicts
  that were the import's own order, not disagreements.
- **Editions follow their citations** (`Builder.carry_edition`, also for same_work and split_work). A citation that
  moves to another card takes the edition it names along. Before, a split left a moved citation pointing at the old
  card's edition row. In the release, every edition of an active work is named by its own citations (0 empty rows,
  0 stale counts, 0 citations on another card's edition).
- **Constraint checks:**
  - a link's card has that link as its best;
  - a relation's two works are apart and related;
  - an edition's second card names editions of its own, none shared with the first;
  - a dropped card's citations are on no card;
  - a retitled card keeps its title while it is the card.

  Temporary triggers on `citation_links` and `work_relations` say which card a decision touched; everything is checked
  again on the final state. This release ran 16,212 checks.
- **counts()** adds cited works cited, references held, links and relations by people, editions and publications.
  The fingerprint covers editions, contributors, publications, catalogue records and journals.
- **Screens (3 small edits):**
  - a work's page lists the relations where it is the object, so a book shows its chapters (`pages.work`);
  - the index's definition of "held" names the librarian's links (`index_pages.DEFS`);
  - the librarian page's banner reads the API's note on what was applied (`librarian_works.py`,
    `web/pages/librarian/works.tsx`).
- **Schema:** no new table. The six review rules are under the idempotent-upgrades mark (`desk.cli init`, run on
  `desk`).
- **Tests:** `experiments/49_correction_desk/tests/test_cited_works.py` (2), on a small reading built with platform
  v2's schema. It covers validation and ownership; a split then a join of its group; editions kept apart with a
  label; the three not-a-work actions; a book and its chapters; a thesis and its article; a new catalogued-only
  publication; a same-text link; a review relation that rejects the machine's link; a relation between two joined
  cards as a conflict; the index counts; a rebuild with the same fingerprint; and a revert.

  The Desk suite passes, 92 tests (`.venv/bin/pytest -q tests`, 6 min). The repo's `tests/test_docs.py` passes
  except for one failure that is not this experiment's: `65_fix_leaks` (running now) has no README yet.

## What was imported (`plan67.py` → `import67.py`), by kind

| Desk operation | n | from |
|---|---|---|
| `split_work` | 25 | exp 62's split_card |
| `move_member` | 4 | the split-off citations exp 62 joined to another card |
| `not_a_work` | 257 | 76 drop, 177 retitle (126 with the title found in the print between the year and the journal's name, 51 without one: the card keeps its title), 4 one per citation. The other 8 of exp 62's 265: 7 second answers on a card that has two (finalize62's precedence: drop, then one per citation, then retitle) and 1 "see split" |
| `confirm_work` | 63 | card_ok |
| `same_work` | 217 | exp 62's 218 − D42's pair; 1 of them is D41's (the DSM) |
| `edition_of` | 86 | exp 62's 86 − D40_NOT (al-Nawawi's «شرح صحيح مسلم») + D40 (the different_work that became an edition of Sahih Muslim); 4 are D41 (the DSM) |
| `define_work` | 1 | D42: «الثقافة العربية: أسئلة التطور والمستقبل» (مركز دراسات الوحدة العربية 2003) |
| `set_work_type` (chapter) | 3 | D42: its two chapters and Aguessy's contribution |
| `relate_works` | 5 | D42 part of ×3 (the two chapters; Aguessy's part_of); D43 derived from ×2 (CQCRSFF7DR ← C5QZVDD45J, CASKNNJDC5 ← CHYN8JAW1K) |
| `link_publication` | 705 | the 696 K1c links (73 of them add their record as a catalogued-only publication) and D44's 9 same-text links (1 adds its record) |
| `relate_publication` | 215 | 225 relations − 8 now D44 links − 1 on a dropped card − 1 made moot (CGWJPWHSMH: the edition_of joins it with the thesis whose K1c link names the record itself; `out/plan67_summary.json`). 77 add their record as a catalogued-only publication. By kind: reviewed in 130, related 39, studied in 18, has derived 20 (D43: the record is drawn from the cited thesis), derived from 7, has part 2 (`out/relations67.json`) |
| **held** (not imported) | | 217 links outside K1c, 700 different works (the other 3 are D40's edition and D43's two relations), 84 no link, 21 unsure (the 22nd, CK75AY2BG4, is D44's link) |

Each decision's `evidence.provenance` holds:
- exp 62's decision id, qkey, kind, level, basis, confidence, reason, time, and whether its proposing rule stood;
- the blind rounds that sampled it, by item, with the agreement and the adjudication;
- the rule applied (`exp62-apply`, `K1c`, `D40`–`D44`) and the evidence ids.

`reason_code` is `librarian:<rule>`; confidence maps high → sure, medium → likely, low → unsure (the owner's rules:
sure). `evidence.source_id` (`E62:<decision id>[:…]`) makes the import idempotent. A key `work:@<source id>#<g>` in
the plan names group g of a split imported earlier, resolved at import to the card the Desk minted.

**The owner's rules, case by case:**
- **D40:** C4EZV38PP2 «صحيح مسلم» + CMGAH5Y38J «صحيح مسلم بشرح النووي». The edition reads «بشرح النووي (شرح النووي
  على صحيح مسلم)», دار الفكر 1981. Sahih Muslim: 5 articles, 12 references, four editions. CPA8ZNRRSW (al-Nawawi's
  «شرح صحيح مسلم», 19 references in one article) stays his work.
- **D41:** the DSM's 4 edition_of decisions and 1 same_work. One work cited by 7 articles, its editions kept: DSM-IV-TR
  2000, DSM-5 2013 and others.
- **D42:** C2BE7XGM7E (عبدالله عبد الدايم) and C7TGVAC7QF (جيهان سليم) are chapters `is_part_of` the book
  C40MEJY8K2; C8SDEY1PYJ (Aguessy) is part of the UNESCO volume C8HQYPRQ6H. The chapter titles are not printed, so the
  two cards keep the book's title.
- **D43:** 2 pairs of cards, and 18 catalogue relations from a cited thesis to the article (or conference paper)
  Mandumah holds.
- **D44:** C03T2DDVD1, CABQ4TJABZ, CCD0SB76WE, CCRANKFQF8, CHQ6T3P6JB, CJEWVA6WMA (another venue), CBMRKZVD45 (a 1976
  article reprinted in 1988), CQH4EVBD8J (a 1998 article cited from a 2015 copy) and CK75AY2BG4 (the escalated case).

## The one conflict (for the lead / the owner)

Exp 62's split of «المقدمة» (CF622F7PED) moves out a stray citation, «الأستاذ حسان عبد المنان في مقدمة رسائل
للرفاعي» (an editor's preface, not Ibn Khaldun's book). The P1 demo's `same_work` (decision
`aa1c93f3-f85f-44d7-a48b-55cf94212b61`, agent:p1-demo, is_demo) pinned every citation of both cards it joined on one
card, that preface included. The earlier decision holds, so the split was not applied: «المقدّمة» shows 13 articles,
not 12. The release left a note on both and a task for agent:librarian. To apply it, the demo decision's owner or an
admin reverts it (`POST /desk/api/decisions/aa1c93f3-…/revert`) and a release is built. The join the demo made is
also in the librarian's decisions, so nothing is lost.

## Reversibility

- **One decision:** its owner (`agent:librarian`) or an admin reverts it (`ops.revert` or
  `POST /desk/api/decisions/{id}/revert`), or supersedes it. The next release puts the machine's reading back for it.
- **The whole pass:** revert the 1,581 decisions whose `evidence->>'source_id'` starts with `E62:` and build a
  release.
- **Releases on disk:** all six copies were kept (`--keep 6`): R20261022T233109, R20261023T005909, R20261102T155701
  (exp 64), R20261102T173613 and R20261102T174053 (two builds of this pass before the editions fix, same decisions;
  their deletion can be proposed, 1 GB each) and R20261102T174226.
- **Backups (taken first):**
  - `~/data/desk/backups/desk_schema_before_exp67_20261102T113059.dump` (`pg_dump -Fc -n desk`; restore with
    `pg_restore -d inkdesk --clean -n desk <file>`) and `.sql`;
  - the code files before the change: `~/data/desk/backups/code_before_exp67/`.

## For the lead

- **Restart the API** to get the new code. The running API (`desk.cli serve`, started 10:56) already reads the new
  release, but the new operations, the reverse relations on a work's page, the "held" wording and the librarian
  banner's note need the restart:
  ```
  cd experiments/49_correction_desk && .venv/bin/python -m desk.cli serve
  ```
- **Rebuild the web** (`/home/appuser/data/desk/web-live` via `sync-build.sh`) for one change: the librarian
  page's banner now shows the API's note. It type-checks (`tsc --noEmit`).
- **Can be dropped or deleted** (not done here): the test schema `test_e67dry` (the dry run); two 1 GB dry-run
  release copies in this session's scratchpad; the two intermediate releases above.

## Files

- `plan67.py`: exp 62 + the owner's rules → `out/plan67.jsonl`, `out/plan67_summary.json`, `out/relations67.json`.
- `import67.py`: → the Desk; idempotent; writes `out/import67_<schema>.jsonl` and `_refused.jsonl`.
- `dryrun67.py`: a throwaway schema copied from `desk`, the import, a release into a scratch folder.
- `measure67.py`: → `out/numbers67.json`.
- `out/release67.json`: the release row.
- `out/shots/`: the live pages after the release.
- `progress.md`.

Run it again:
```
python3 experiments/67_apply_works/plan67.py
cd experiments/49_correction_desk
.venv/bin/python ../67_apply_works/dryrun67.py --out <scratch dir>          # optional: test_e67dry
.venv/bin/python ../67_apply_works/import67.py --schema desk                # skips what is already imported
.venv/bin/python -m desk.release --keep 6 --note "…"
.venv/bin/python ../67_apply_works/measure67.py /home/appuser/data/desk/releases/R20261102T155701.db /home/appuser/data/desk/releases/<new>.db
```

## What it changed

- **The Desk:** the `pub:` key, six cited-work operations, their release application and checks, pending moves in
  what a decision records, and editions that follow their citations (`desk/keys.py`, `ops.py`, `reading.py`,
  `release.py`, `db.py`, `schema.sql`). Three screen edits (`pages.py`, `index_pages.py`, `librarian_works.py` +
  `web/pages/librarian/works.tsx`). Tests: `experiments/49_correction_desk/tests/test_cited_works.py`, and one line
  of `test_librarian_works.py`. Its README has a section "Cited-work decisions".
- **The Desk database:** 1,581 decisions of `agent:librarian`; releases R20261102T173613, R20261102T174053 and
  **R20261102T174226** (the one the Desk reads). The platform database (`platform_v2.db`), marc.db and exp 62's files
  were only read.
- **Docs:** `docs/decisions.md` D40–D44, `docs/STATUS.md`, experiment 62's README ("What it changed"),
  `experiments/README.md`.

No paid call was made.
