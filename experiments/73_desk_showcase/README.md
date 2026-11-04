# Experiment 73: the Desk's shareholder showcase (2026-11-02/03)

The audit is [AUDIT.md](AUDIT.md); the agents' shared rules are [CONTRACT.md](CONTRACT.md). Each agent adds its own section.

## Agent C: the deck, the gate 2 page, the project page (2026-11-03)

**Question.** Bring the shareholder deck (`/pitch/`, dated 23 Oct), the `/gate2/` page ("nothing has been run") and
the project page's stage and money up to tonight's state, every number measured or labelled estimate, with its date
and source.

**What changed.**
- **Deck** (`experiments/49_correction_desk/web/public/pitch/index.html`, 12 → 14 slides; keys, notes, print kept):
  title dated 3 Nov; slide 4 platform counts (1,143 articles, two journals whole); slide 5 adds gate 2's 10 pages
  (9 / 1 / 0) and the audit (99.84% of 525,459 lines); slide 6 gate 1 with the librarian (16 vs 0.25, 25 vs 6.3,
  121 vs 16.7, 16.8% vs 2.6%, 37 inside); **new slide 7** "The two education journals cite each other" (15 + 16;
  17 vs 0.0; 157 vs 26.3; 313 vs 118; institutions 17 vs 16.1 shown as chance; $23.29); **new slide 8** what was built
  since we last met (nothing-lost audit + D30 guard, the librarian with blind checks and the 98% rule, 271 → 242 and
  9,137 → 8,903, the production librarian 99.1% / 17% / ≈ $3 per 1,000, tools rejected on numbers); slide 9 cost
  measured ($0.0078 a page, $0.0055 a Word article, spend $127.39 Gemini log + $33.97 Claude API); slide 12 road
  (gate 2 pilot done; the nine ≈ $290; gate 3 ≈ $38k / ≈ $74k re-derived; ≈ $88k per million); slide 13 the 7-screen
  demo path with empty slots `pitch/shots/demo1–7.png`; slide 14 the ask ("approve the nine, ≈ $290").
  The 23 Oct demo shots moved (not deleted) to `pitch/shots/old_2026-10-23/`.
- **Live numbers.** 53 number spots in the deck carry `data-h="<headlines key>"`. [fill_deck_c.py](fill_deck_c.py) pulls
  `GET /desk/api/headlines` (agent B) and rewrites any that changed, printing each change; a missing key keeps the
  written value. Against B's dev API on 3 Nov: 0 changed, 0 missing.
- **Re-derived estimates** (3 Nov, from experiment 70's measured rates): the nine = $313 − $23.29 ≈ $290 (≈ $270
  without gate 1's already-read scans); gate 3 = 4.57M pages × $0.0078 + 92,832 × $0.0055 + librarian $0.6–2k
  ≈ $37–38k, ≈ $73–74k after 1 Dec; a million documents = 11.3M pages × $0.0078 ≈ $88k.
- **`/gate2/`**: the pilot's answer first (cards, the bridges with bars, cost / quality table, the nine ≈ $290), then
  the 22 Oct selection below, labelled as pre-pilot estimates.
- **`desk/project/project.json`**: stage "Gate 2's pilot is done: two journals cite each other; the nine others next";
  money (spend $127.39 from the log, pilot and 2 Nov checks rows, credit ≈ £480 estimate, Claude API $33.97 of $250);
  projections and roadmap (gate 2 pilot done, nine ≈ $290, gate 3 and per-million re-derived); a 3 Nov timeline item.
  `experiments/49_correction_desk/tests/test_project.py`: 7 passed.

**Shots.** `out/c_shots/slide01–14.png` (1440×810, each looked at), `slide_notes_example.png`, `gate2_fold.png`,
`gate2_full.png`, `deck_print.pdf` (print to PDF: 14 pages, 1280×720). Made by [shoot_deck_c.py](shoot_deck_c.py)
with `experiments/52_journal_gate1/out/pwvenv/bin/python`.

## Agent A: the Story page, the menu, presentation mode (2026-11-03)

**Question.** Give a first-time visitor one guided route through the Desk (AUDIT.md §4, M1). Also fix the menu, which
took two rows (M6), and hide the workbench and internal ids when presenting (M7, M11).

**What was built** (files under `experiments/49_correction_desk/web/`):
- **`/story`** (`pages/story.tsx`, `components/story/Steps.tsx`, `components/story/Bits.tsx`): seven steps, one
  per screen. Each has a big plain headline, one to three visuals, and an "Open live" button beside the headline.
  The seven steps:
  1. the problem and Mandumah's archive;
  2. how a page is read (seven stages and the measured costs);
  3. the article beside its scan;
  4. 0 wrong words in 1,532, drawn as 1,532 squares, and the nothing-lost share;
  5. the two journals: a two-arc citation diagram, and teal-against-grey bars for shared authors, shared cited
     works and coupled pairs;
  6. one cited work, لسان العرب (`/works/C7H83S6DX4`). It shows four real ink crops of differently printed
     citations, the librarian's before/after bars (institutions, cited works), 99.1% precision and about $3 per
     1,000 decisions;
  7. the journey strip (the project page's own component, from `project.json`), the pilot cost, the cost of the
     ten journals and the nine still to read, and the 1 December price doubling with a day count.

  Every changing number is read at render time from `GET /desk/api/headlines` (or from the live work, journal and
  project records). A missing value shows "—". The only fixed numbers are the outside facts on step 1 (Scopus share
  from Al-Fanar 2025; the archive and catalogue counts from experiments 44/45, as in the deck), each with its source
  on the page.
  Keys: → / space / PageDown go forward, ← / PageUp go back, 1–7 jump to a step, F goes full screen. The
  progress bar is clickable. "Present" switches the browser to full screen and hides the menu. The step stays in
  the URL (`?step=3`), so the browser's back button returns from a live screen to the same step.
- **The hero cited work was changed.** The audit proposed `CBDD9P2BCR` (al-Hiti, ثقافة الأطفال). That card also
  holds three citations of a different book: al-Kaabi 2011, تكنولوجيا الثقافة, all from article 0165-007-028-003
  page 25. This was reported to the lead. The Story uses `C7H83S6DX4` (Ibn Manzur, لسان العرب) instead. Every
  member was checked against its print on 3 Nov: 36 ink crops looked at on a contact sheet, plus 4 members without
  an anchor checked by their printed text. All 40 are right (40 citations in 35 articles on release
  R20261103T055432).
- **Menu** (`components/Layout.tsx`): brand "Mandumah Citation Index". The logo goes to `/story` in presentation
  mode and to `/` otherwise. The top bar reads Story · Index ▾ · Quality ▾ · Librarian ▾ · Project ▾ · Workbench ▾,
  all on one 57 px row at 1440 and 1920 with every label visible; each menu item has a one-line explanation.
  The menus open by click, or by Enter / Space / ↓. ↑/↓/Home/End move inside a menu, Esc closes it and returns
  focus, and Tab closes it. While one menu is open, hovering a neighbour switches to it.
  Workbench (task overview, tasks, notes with their count, releases, articles, the id list of top cited works) is
  hidden in presentation mode. The user menu holds the **Presentation mode** switch. While presentation mode is on,
  a teal "Presentation" chip beside the search turns it off.
- **Presentation mode on my pages**: `/` redirects to `/story` (`pages/index.tsx`). `/project` shows only a plain
  headline and the journey strip (`pages/project.tsx`), using `Journey`, now exported from
  `components/ProjectMap.tsx` (one word changed there).
- Thumbnails of live screens: `web/public/story-shots/{pipeline,beside,classic}.png`. They are stills because the
  Desk sends `X-Frame-Options: DENY`, so it cannot be framed. They were taken from this dev server at 1440 in
  presentation mode. Retake them if those screens change.

**Shots** (`out/a_shots/`, each looked at):
- `story1–7_1440.png` and `story1–7_1920.png`; each step fits one 1440×900 screen within a pixel;
- `story3_present_1440.png` (full screen, no menu);
- `menu_<w>_<work|show>[_<menu>].png` (every dropdown open, the user menu, at both widths);
- `project_show_1440.png`, `project_work_1440.png`.

**Checks.** `npx tsc --noEmit -p .` is clean. The Desk tests pass: 101 passed in 11 min. No console errors on any Story step. In the keyboard walk through the
menus, ↓ focuses the first item, a second ↓ the next one, and Esc returns focus to the button.

## Agent B: the headline numbers, the index pages, the articles, presentation mode (2026-11-03)

**Question.** Give every show page one source of headline numbers, put gate 2 on the Index home, and remove the stale
claims ("1 read whole", "random sample" for 0165, "700 articles", "proposals only", "780", "before gate 2"). Make
Word-route articles and cross-journal citations read right, and hide internal ids in presentation mode.

**`GET /desk/api/headlines`** (`experiments/49_correction_desk/desk/headlines.py`, three lines at the end of
`desk/api.py`). It returns the CONTRACT.md shape plus `authors`, `journals`, `audit{pct,lines,articles,release}`,
`gate2.shared_institutions`, `gate2.pages_checked`, `gate2.random_ranges`, `librarian.to_person_pct`, `defs` (one
plain definition per value) and `sources`. The response is cached per release (path and mtime) and per mtime of the
experiment files. The API warms it in the background at startup.
- **Live on the current release:** the index counts, the journals read whole (with scan/Word split and the country
  name), gate 1 (experiment 52's `measure52`, as `/index/gate1`) and **gate 2**. Gate 2 runs experiment 70's own
  `measure70.base/cross/shared` with the same 20 random sets (seed 7070), so all its numbers move together.
  `measured_on` names the release. A test checks that on R20261103T023001 the live code reproduces measure70.json
  exactly (15/16, 17 vs 0.0, 17 vs 16.1, 157 vs 26.3, 313 vs 117.6).
- **Read from the experiment that measured them:** the audit (the folder `audit_current` points at), the proof pack's
  0 wrong of 1,532 words (experiment 43, on 10 of the 60 proof pages), the production librarian (experiment 71: 99.1%,
  17% to a person, about $3 per 1,000), the librarian's before/after on the first 780 articles (experiments 64, 67, 68:
  271 → 242 institutions, 9,137 → 8,903 works), and experiment 70's costs ($23.29; the ten about $313; $0.0078 a scan
  page, $0.0055 a Word article). The date prices double, 2026-12-01, is the only value typed in.
- Values on the live release R20261103T055432 (3 Nov, after experiment 72's librarian on 0165): 1,143 articles,
  12,991 pages, 299 institutions (80.8% with a country), 13,924 cited works (679 cited by 2+), held 8.3%. Gate 1:
  16 vs 0.25, 25 vs 6.3, 122 vs 16.7. Gate 2: 0130 → 0165 15 references, 0165 → 0130 19; shared authors 17 vs 0.0;
  shared works 199 vs 26.3; coupled pairs 376 vs 118; shared institutions 19 vs 16.1.

**Pages changed** (`experiments/49_correction_desk/web/`):
- `/index-home`: the intro says two journals were read whole. Gate 1 and gate 2 are now two calm cards
  (`components/GateCards.tsx`). Each comparison is two bars on one scale, values in their own column. Gate 2 shows
  the two journals with the references each way, then shared authors, works and coupled pairs, and institutions
  marked "no more than chance", plus the cost, the ten journals and the page check. Gate 1's full table stays in a
  collapsed "All the measures" section outside presentation mode. Means show as whole numbers above 100. Journal and
  institution lists show "read whole · gate 1 / gate 2 pilot" and country names.
- `desk/index_pages.py`: the Journals card says "2 read whole (gate 1 and gate 2's pilot)". The definitions of
  articles and of links between articles cover the Word route and the journals read whole. `journal()` returns
  `is_whole`, `whole_gate` and `counts.word`.
- `/journals`: new banner (two journals read whole), and both journals carry a "read whole" chip.
  `/journals/<id>`: a "read whole" chip and a note for each journal (0165: 145 scans + 218 Word files); a new
  **Bridges with other journals** panel (the other journal read whole: references to it and from it; then the
  journals it cites and that cite it); authors shown as the top 10 with "Show all"; countries as names, with
  "Country not recorded yet" last.
- `/institutions`: banner says the Arabic and English twins are one record (joined on 2 Nov), with the share that
  has a country; country names. `/institutions/<id>`: no id or release in presentation mode.
- `/articles`: the true total ("1,143 articles"; a search shows "n of 1,143 match"). The API limit went from 700 to
  5,000 and the response carries `total`, `journal` and `word_route`. The list has a Journal column (read-whole label)
  and a "Word file" chip, and is sorted with the journals read whole first, then by journal, newest first.
- Article page: Word-route articles (`run` starting with `w`) show a calm chip "Built from the publisher's Word
  file". "View beside the scan" is hidden; "Beside the scan", "Scan only" and "Classic page" are disabled, with the
  line "No scan: … page numbers are estimates". Ink toggles and byline crops are hidden. The **Cited by** tab shows
  each citing article's journal, an "another journal" chip, and a "n from another journal" count
  (`desk/pages.py` adds `journal_id` and `journal` to `cited_by`). In presentation mode the page drops stem, pub id,
  release, the Ids block (999$c, run), authority and person ids, institution ids, extraction-method chips, card ids,
  link status and "unresolved" chips, and the Quality, History and Notes tabs; the title shows once.
- `/librarian` and `/librarian/works`: a green "Applied on 2 November" banner replaces "Proposals only", and a new
  card shows the production librarian from `/headlines`. The tiles use the applied counts (271 → 242,
  8,903 works). "First pass" and "the 780 articles" now read "the first 780 articles read". In presentation mode the
  review sample, rules, at-scale estimates, the questions for the owner and the pre-apply tables are hidden: those
  tables carry exp 56/62's own counts (234, 8,850), which differ from the applied ones, and outside presentation mode
  they are now labelled that way.
- `/audit`: the header and tab give the real count ("All 925 articles", every scanned article of the current
  release; Word-route articles are not in it). "780" and "before gate 2" are gone. The Sankey columns read "The
  printed lines → What each line is → The article file → The index". In presentation mode only the headline cards
  and "What fell through" remain (no filters, fixes, Gemini tables, ids, or an empty false-alarm card).
- `/most-cited`, `/works`, `/works/<id>`, `/persons/<id>`: no ids, release strings or History/Notes tabs in
  presentation mode.

**Shots** (1440 wide, `_n` normal, `_s` presentation mode, `_fold` first screen): `out/b_shots/01–16_*.png`, all
looked at.

**Tests.** `experiments/49_correction_desk/tests/test_headlines.py` (8): shape and definitions; agreement with `/index/overview`; journals read
whole; gate 2 live; gate 2 reproducing experiment 70 on its release; proof, librarian and costs; the cache; the
route with a token. TypeScript `tsc --noEmit` is clean.

**Not done.** `/releases`' slow first open (N7) is in `desk/release.py` and was left alone.
