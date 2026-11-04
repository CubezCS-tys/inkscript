# The Desk: correction backend design (experiment 49, draft 1, 2026-10-21)

**What this is.** The backend that lets about 300 people who understand publishing correct anything the machines
got wrong, without ever editing the data directly. This draft covers:
- the page (a line's role, reading order, a misread word, a table cell);
- metadata (title, names, year, affiliation);
- identity (the same person, the same work, the same institution, which earlier citation «المرجع السابق»
  points to).

The screens follow the look of AI-Search's admin dashboard (`/admin-vdb`): Next.js + Tailwind, a top bar, white
cards on a light grey ground, an indigo accent, sortable tables and status pills. This document designs the
engine under them and sketches the screens. Nothing is built yet.

It builds on what exists:
- D34: a person's correction is a patch keyed to Azure's lines, with person > judge > retry precedence, and it is
  re-applied on every rebuild.
- Correction tool v1 (`experiments/43_rehearsal`, single user, export and import by command).
- Platform v2's ledger: `patches`, `patch_applications`, `reviews`, `actors`, `id_registry`, `merged_ids`,
  `metadata_assertions` (`experiments/47_platform_v2/DESIGN.md`).

The test cases are the real ones experiment 48 found ([../48_linking_probe/README.md](../48_linking_probe/README.md)).

## 1. The picture

The light table again:
- **The scan** is the bottom layer and never changes.
- **The machine's reading** is a clear sheet on top: Azure's words, Gemini's structure, the linker's guesses.
  It is rebuilt whenever the pipeline improves.
- **The people's decisions** are a second clear sheet on top of that. The Desk writes only to this sheet.

Every rebuild lays the decisions back on top. Nothing underneath is ever overwritten, and every decision can be
traced, reviewed and undone.

```
  scans + Azure ──► pipeline (Gemini, rules, linker) ──► machine reading (rebuilt often)
                                                              │
  correctors ──► Desk API ──► decisions (append-only) ────────┤ re-applied on every build
                     ▲                                        ▼
                     └──── tasks ◄── detectors ◄──── release = reading + decisions ──► search, metrics, exports
```

## 2. Three ideas the whole design rests on

1. **A decision, not an edit.** A correction is a small permanent record:
   - what it targets (by stable key) and what it says;
   - who made it, when and why;
   - the evidence they saw.

   It never changes after it is written. A later decision can supersede it, but both stay.
2. **Stable keys, never row numbers.** Decisions point at things that survive a rebuild:
   - Azure line anchors (`stem|p3|w120-131`) and mention ids;
   - authority ids, `W`+999$c for publications;
   - the registry's `A…` / `C…` / `I…` ids;
   - the journal code.

   If a rebuild makes a key vanish, the decision becomes *orphaned* and a person re-anchors it. It is never
   silently dropped.
3. **"No" is a decision too.** "These two are *not* the same person" is stored and respected, so the linker can
   never re-merge what a person split. Today every error a person fixes could come back on the next linker run.
   Negative decisions stop that.

## 3. The records (PostgreSQL)

The Desk keeps its own small database: the people's sheet. It reads the machine's sheet (platform v2, SQLite
today, PostgreSQL later) and never writes to it. A build combines the two into a release.

**`subjects`**: anything that can be corrected, by stable key.

`subject_key` (`person:A3K…`, `work:C7H8…`, `mention:0201-000-044-001|p20|r1`, `line:0201…|p11|l42`,
`pubfield:W1268685|title`, `authority:213172`, `inst:I…`, `journal:J0201`), `kind`, `label` (for screens),
`first_seen_release`, `last_seen_release`, `status` (live | orphaned).

**`decisions`** (append-only):

| Column | Meaning |
|---|---|
| `decision_id` | uuid |
| `domain` | page, metadata or identity |
| `op` | see the catalogue in section 4 |
| `subject_keys[]` | what it is about; one key, or two for "same as" |
| `payload` | jsonb: the new value, the target, the part split off |
| `reason_code`, `note` | why |
| `evidence` | jsonb: a snapshot of what the person saw, crop refs included |
| `actor_id`, `role_at_time`, `created_at` | who and when |
| `task_id` | the task it answers, if any |
| `confidence` | sure, likely or unsure |
| `status` | proposed, accepted, rejected or superseded |
| `supersedes` | the decision it replaces |
| `review_policy_at_time` | the review rule in force when it was made |

**`tasks`**: a question waiting for a person.

`task_id`, `kind` (from section 5), `subject_keys[]`, `candidates` (jsonb), `machine_guess`, `priority` (impact ×
uncertainty, section 6), `source` (which detector or probe, which release), `skills` (language, field, script),
`state` (open | claimed | answered | escalated | closed | stale), `claimed_by`, `lease_until`, `answered_by`
(decision_id), `created_release`.

**`notes`**: a corrector's comment on someone else's decision or on a subject (section 7).

`note_id`, `subject_key`, `decision_id`, `author_id`, `text`, `created_at`, `resolved_at`. The decision's owner
sees it in their inbox. (A `reviews` table for second looks stays available if a review rule is ever switched on.)

**`gold`**: tasks with a known answer, mixed into queues so each person's accuracy is known.
`task_id`, `answer`, `set_by`.

**`actors`**: people, agents, models and rules, as in platform v2 (`person:<login>`, `agent:link47`,
`model:gemini-4-argon`, `rule:d33-pages`). For people it adds `role` (corrector | admin), `skills`
(languages ar, en, fr; fields such as law, education, turath) and `active`. All correctors are equal (owner,
2026-10-21); `admin` only sets up accounts, review rules and detectors, and its decisions carry no extra weight.

**`releases`**: one row per build. Which machine reading, which decisions applied, which orphaned, the counts and
the checks.

**`applications`**: what a build did with each decision: applied, skipped (superseded), orphaned or conflicted.
This is platform v2's `patch_applications`, generalised.

The existing `patches` stay as they are: page decisions of `source` person, judge, gemini-retry and rule.
The Desk writes its page decisions in the same shape, so `patches43` applies them with no new code path.

## 4. What a person can decide (the operations)

Every operation has an inverse or a superseding form, so nothing needs deleting.

**Page** (keys: Azure line anchors; the patches43 ops, unchanged):
- `set_role` (heading, footnote, caption, noise …);
- `set_order`;
- `split_block` / `merge_blocks`;
- `mark_noise` / `unmark_noise`;
- `mark_other_article`;
- `fix_word` (Azure misread: changes the text) / `flag_misprint` (D30: the print stays, the correction travels
  beside it);
- `set_cell`, `set_picture_box`;
- `link_note_call`.

**Metadata** (D33: the printed form is always kept):
- `set_field` (title, translated title, subtitle, year, pages, volume, issue, language), with `printed` kept and
  `reason` (misprint | misread | cut by design | catalogue wrong);
- `set_contributor_role` (author → translator, reviewer, supervisor, rapporteur);
- `set_affiliation`.

**Identity**:

| Subject | Positive | Negative or undo |
|---|---|---|
| person | `same_person(A, B)`, `link_byline(mention → A)`, `set_name_forms` | `not_same_person(A, B)`, `unlink_byline`, `split_authority(authority → two people, which records go where)` |
| cited work | `same_work(C1, C2)`, `move_member(mention → C)`, `set_work_type` (book, turath, serial, law, diwan …), `link_to_record(C → W…)`, `link_external(C → DOI / OpenAlex W…)`, `relation(C reviewed_in W…)`, `edition_of(C1 → C2)` | `not_same_work(C1, C2)`, `split_work(C → several, which mentions go where)`, `not_a_work` (the citation names only a series) |
| back reference | `resolve(«المرجع السابق» → earlier citation)` | `unresolvable` (no earlier full citation in the article) |
| institution | `same_institution`, `set_parent` (faculty → university), `link_ror` | `not_same_institution`, `not_an_institution` («المعهد» alone) |
| journal | `same_journal`, `link_catalogue_journal` | `generic_name` («مجلة كلية التربية» without its university) |

Each of experiment 48's error kinds is one of these:
- «الديوان» → `split_work`;
- «المقدّمة» + «مقدمة ابن خلدون» → `same_work`;
- Muhammad Kamil Husayn ×2 → `split_authority`;
- Khalid Talal Alotaibi's Latin twin → `same_person`;
- «المعهد» → `not_an_institution`.

## 5. Where tasks come from

Tasks are generated, not chosen by hand. Each release runs **detectors**; each detector's output is a task kind
with its own screen. The first ten come straight from probe D's table:

| Task kind | Detector | Per article (exp. 48) | Screen shows |
|---|---|---|---|
| work card joined without an author | link47 card has members with and without authors | 0.10 | every member citation with its ink crop, grouped by author |
| possible same work | B's under-merge rules (contained title, stripped equal) | 0.26 | the two cards side by side, with sample citations and crops |
| catalogue-link candidate | A's candidates, scores 0.65–0.85 | 0.15 | the citation as printed and the catalogue record(s) |
| byline without authority / catalogue twin | C's provisional bylines | 0.16 | the byline crop, the article's catalogue record and the candidate authority people |
| is this authority one person? | C's authority detector (records over decades, journals, countries) | per authority, most-cited first | the authority's records grouped by journal and decade, with co-authors and institutions |
| back reference unresolved or weak | link47 resolution < 0.75 | 0.32 | the note's crop and the article's earlier citations as a short list |
| affiliation wrong or partial | C's institution rules | 0.14 | the affiliation crop and candidate institutions (with ROR) |
| journal name generic or unsure | A's journal entities | 0.06 | the cited journal strings and candidate journals |
| page flags (existing) | flags43 + judge | per flagged page | correction tool v1's view: scan beside layout |
| orphaned decision | build: a key vanished | rare | the old evidence beside the new reading; re-anchor or retire |

A detector writes a task only when its subject has no standing decision. That is the second reason "no" is
stored: once decided, a task never comes back.

## 6. The queue: right work, right person, right order

- **Priority = impact × uncertainty.**
  - Impact is how many counts the answer moves: the citations a work card holds, the works an authority holds,
    the articles a journal string touches.
  - Uncertainty is 1 − the machine's confidence.

  So the most-cited works and the most-published people come first. Experiment 48 showed that bad groupings rise
  to the top of every ranking, so this is also where errors do the most harm.
- **Skills.** Tasks carry script and language (Arabic, English, French: the team's three) and, where known, the field, from the
  catalogue's subjects. People see only tasks they can do.
- **Claiming.** A person takes the next task; it is theirs for 15 minutes (a lease), then it returns to the
  queue. No two people get the same task.
- **Can't decide.** "Unsure" is an answer. The subject stays as the machine has it, marked *unsure* (never
  guessed), and the task can be offered to someone else later.
- **Batches.** The same kind of task in a row: the screen stays the same, so hands learn it. Each kind gets
  keyboard shortcuts.

## 7. Ownership and trust (owner, 2026-10-21)

- **Each corrector owns their corrections.** A decision is accepted as soon as its corrector makes it (one key).
  There are no blind second checks, no tie-breaks and no majorities: the owner chose this over the
  agreement-based model of draft 1.
- **Nobody overwrites someone else's decision.** Every decision shows its owner ("split by Sara, 21 Oct"). Another
  corrector who thinks it is wrong leaves a **note** on it. The owner of the decision sees the note in their
  inbox and can revise it; they settle it between themselves.
- **Admins can fix anything.** This covers someone leaving, or a clear mistake. An admin's correction is logged
  like any other.
- **A quiet accuracy gauge.** About 5% of tasks have a known answer (gold). Each person's accuracy per task kind
  is visible to admins and to the person, as information only: it gates nothing. It can be switched off.
- **A review rule per kind stays as a setting** (default `single` everywhere), in case a kind ever needs a second
  look. Today none does.
- **Precedence:** accepted person decisions beat the judge, which beats the model and then the rules (as today).
  Two people's decisions on one subject cannot conflict, because the second person can only leave a note.

## 8. Releases: decisions reach the data

A **release** is a build of platform data (later PostgreSQL) = the machine reading + all accepted decisions:
1. Build the machine reading as now (load47 / link47).
2. Apply decisions in order: page, then metadata, then identity, then back references.
   - Identity decisions are applied as constraints on the linker: must-link and cannot-link pairs, pinned
     members and pinned record links. They are not edits after the fact, so the linker builds around them.
   - `merged_ids` records every retired id.
3. Write `applications`. Count orphans and conflicts.
4. Run the checks: integrity, the counts against the previous release, and gold answers reproduced.
5. Only then do metrics, search exports and the RAG chunks read the new release.

Metrics are only ever computed on releases, never on a half-applied state.

## 9. The API (FastAPI, like AI-Search's admin API)

All routes are under `/desk/api`, JSON, and every write needs a logged-in person.

```
GET  /me                                  who am I, role, skills, my stats
GET  /queue/next?kind=&lang=              claim the next task (lease)
POST /tasks/{id}/answer                   {op, payload, reason_code, note, confidence} → decision
POST /tasks/{id}/skip | /unsure          give it back / leave it as the machine has it, marked unsure
GET  /subjects/{key}                      a person / work / institution / journal / article page: current state + history
GET  /subjects/{key}/history              every decision and review on it
POST /decisions                           a decision made outside a task (from an entity page)
POST /subjects/{key}/notes                leave a note on a subject or someone's decision; GET /me/notes = notes on mine
POST /decisions/{id}/revert               a superseding decision that restores the previous state
GET  /search?q=                           people, works, journals, articles (Arabic folding as in platform v2)
GET  /stats/overview | /stats/team | /stats/kinds   the Overview and Team screens
GET  /releases, /releases/{id}            what each build applied, orphaned, changed
GET  /evidence/crop?anchor=               ink crop for an anchor (from the page images, cached)
```

## 10. The screens (admin-vdb look)

These use the same parts: `AdminNav` top bar, `Card`, `Tile`, `StatusPill`, sortable tables with sticky
headers, Lucide icons, an indigo accent, and Arabic set right-to-left in its own blocks. The interface is in
Arabic, English and French (owner, 2026-10-21); each person picks theirs, and the whole layout mirrors for Arabic.

1. **Overview**: tiles for open tasks, decisions today, team accuracy on gold, agreement, orphans and the last
   release. Below them, the queue by kind with a sparkline per kind, and a status line for the build.
2. **Work**: one task at a time. The question at the top in one sentence, the evidence in the middle (ink crops,
   records side by side), the answers as large buttons with keyboard shortcuts (`1` same, `2` different,
   `3` unsure, `s` skip), and a note field. "Next" loads the next task without a page change.
3. **Entity pages**: Person, Work, Institution, Journal and Article, each with a *Current* tab (what the release
   says) and a *History* tab (every decision, who, why). Any corrector can propose a fix there outside a
   queue; it follows the same review rule as a queued one.
4. **Notes**: my inbox of notes others left on my decisions, and the notes I left, open and resolved.
5. **Team** (admins; each person sees their own row): per person, decisions, gold accuracy per kind, agreement, median seconds per task,
   and active days. It is used to coach people, not to rank them.
6. **Releases**: each build, with what was applied, orphaned and changed in the top counts. "Times cited" moves
   are shown, so a merge that moves a ranking is visible.
7. **Activity**: a log of every decision, filterable by person, kind and subject.

## 11. Where it runs, and access

- **Prototype:** on this server, on 127.0.0.1 only, like the browse pages.
  - A user-level PostgreSQL 16, no sudo needed (installed from a relocatable build into `~/pg`, port 5433).
  - The API on a port the AI-Search session confirms is free.
  - The Next.js app built outside the live checkout.
  - Memory: PostgreSQL with `shared_buffers` at 256 MB, so the whole Desk stays under 1 GB. This box is
    production.
- **For 300 people working remotely** (owner, 2026-10-21): it must be reachable over the internet, safely, so a
  **separate small server** is recommended, not this production box. It holds no Qdrant, so its load can't touch
  the live search, and it gets HTTPS (TLS) on its own domain.
  - **Its own accounts** (Mandumah staff logins are not assumed): an admin invites each person by email; they set
    a password and a second factor (an authenticator app). Passwords are hashed, sessions expire, and there is
    no anonymous write. Rate limits and login alerts apply.
  - Scans and crops are served only to logged-in people; nothing is cached on public CDNs.
  - Decisions are backed up nightly (the database is small: decisions, not documents).
- **Private data:** the Desk shows scans, text and names, so it is never on a public link. It needs a login even
  inside the organisation.

## 12. Build order

| Step | What | Done when |
|---|---|---|
| P0 | this design, the owner's answers to the questions below | the owner says it feels right |
| P1 | backend prototype on the 600: PostgreSQL schema, API, 3 detectors (work joined without author, possible same work, byline twin), release step with re-application | a rebuild from scratch reproduces every decision; a "not same" survives a linker run; orphans are detected |
| P2 | screens: Overview, Work (3 task kinds), Article, Person and Work pages, History, Releases (before/after) | the owner can do 20 tasks and see them change the top-cited list and the pages (owner: go for P2 after P1, 2026-10-21) |
| P3 | pilot with 5–10 correctors, 1–2 weeks | real minutes per decision, agreement and gold accuracy per kind; probe D's 16,800 h re-estimated from them |
| P4 | the remaining task kinds, Notes inbox, Team; the separate server with HTTPS and accounts; move platform data to PostgreSQL | ready for 300 remote correctors |

## 13. The owner's answers (2026-10-21)

1. **Catalogue feedback:** "go with your recommendation". The Desk never writes to Mandumah's catalogue. Errors
   found in it go into platform v2's `catalogue_reports`, exported as a list for Mandumah's cataloguers, each
   item with its evidence. Examples: an authority id holding two people, a reviewed book's author listed as the
   review's author, wrong page ranges.
2. **Hierarchy:** none. All correctors are equal. Then, the same day: each corrector owns their corrections, with
   no disagreement settling; others leave notes and they talk it through (section 7). Admins can fix anything.
3. **Languages:** Arabic, English and French, for task routing (section 6) and the interface (section 10).
4. **Where they work:** remotely, so a separate server with HTTPS (section 11).
5. **Logins:** not known. The Desk has its own accounts and does not assume Mandumah staff logins exist; it can
   switch to a single sign-on later if one turns up.

Still open: which fields each person covers (the skills tags beyond language), and the domain and server for
the remote Desk.
