# Experiment 73: the Desk as a shareholder sees it (audit, 2026-11-02 night)

**Question.** The owner shows the Desk (http://127.0.0.1:8004) to Mandumah's shareholders on 3 November. Which screens
tell the story, what on them is stale, broken, cluttered or jargon, and what must change before tomorrow?

**Method.** Read-only. A corrector test actor `agent:showcase-audit`, signed in by `POST /api/session`; Playwright with
the bundled Chromium walked 39 views at **1440×900** (plus 7 at 1920×1080 and 3 extra article views) on the live release
**R20261103T023001** (gate 2's pilot loaded: 1,143 articles). Each view: a full-page shot and a first-screen shot
(`*_fold.png`), load time, horizontal overflow, nav height, console errors. Every shot was looked at.
Shots: `experiments/73_desk_showcase/out/audit_shots/` (`<nn>_<page>_d.png`, `_d_fold.png`; `_w1920` for the wide
check). Phone width was dropped on the owner's word (desktop only); the few `_m.png` files are left over, ignore them.

**Answer in one paragraph.** The Desk already holds four excellent show screens: *How a page is read* (`/pipeline`),
*an article beside its scan* and the *classic page* (`/articles/<stem>?view=beside|classic`), *a cited work with the ink
of every citation* (`/works/<id>`) and the *one-article audit flow* (`/audit?tab=article`). But a first-time visitor
lands on a corrector's task queue, the menu is 15 items wrapping onto two rows with six bare icons, and **tonight's
headline (gate 2: two journals cite each other, 17 shared authors vs 0, 157 shared cited works vs 26) appears on no
page at all**. Many pages still describe the world before gate 2's pilot ("one journal read whole", "0165 = random
sample", "the 780 articles", "proposals only", "$152 or $456", "being read"), and the same quantity carries different
numbers on different pages and in the deck. The fixes for tomorrow are mostly text and one new page, not new features.

---

## 1. The top 10 problems

| # | Problem | Where (shot) |
|---|---|---|
| 1 | **Gate 2's result is nowhere.** No page shows 0130 ↔ 0165 (15 + 16 references), 17 shared authors vs 0.0, 157 shared cited works vs 26.3, 313 coupled pairs vs 118, the $23.29 cost or "the nine can follow". `/gate2/` is the *pre-run selection* page and says "nothing has been run". | `28_gate2_d_fold.png`, `04_index_home_d.png`, `07_journal_J0165_d.png` |
| 2 | **The landing page is the corrector queue** ("Open tasks 141 · Orphaned 4 · Last release 20261103 02…", "Byline twin (byline without authority)"). The logo also links there. | `01_overview_d.png` |
| 3 | **0165 is labelled "random sample"** and "1 read whole (gate 1)" is still the claim, on the Index home (Journals card, ranked list, intro text) and the Journals list banner; 0165's journal page has no "read whole" badge or note. | `04_index_home_d.png`, `05_journals_d.png`, `07_journal_J0165_d.png` |
| 4 | **Stale state text after tonight:** `/project` journey "Gate 2's pilot journal is being read" and "≈ $152 (five) or $456 (ten)" (the pilot measured ≈ $313 for the ten); `/plan` "the ten about $456"; `/librarian` "Proposals only: nothing here has been applied" (applied 2 Nov, exp 64) and "first pass" on 780 articles; `/institutions` "the same university in Arabic and English is still two records" (joined by exp 64); `/audit` "Every line printed on the 780 articles… orange is what the prompt must ask for before gate 2" while it now audits 925. | `02_project_d.png`, `03_plan_d.png`, `17_librarian_d_fold.png`, `08_institutions_d_fold.png`, `19_audit_corpus_d.png` |
| 5 | **The same number differs across pages and the deck** (table in §3): articles 1,143 / 925 / 780 / **700**; gate-1 institutions 25 vs 6.3 (live) / 26 vs 3.8 (deck); shared cited works 121 / 118 / 84; held references 16.8% / 18.06% / 16.9% / 15.8%; audit 99.84% / 99.81%; institutions 318 / 242 / 234 / 919; authors 1,182 / 2,866. | many |
| 6 | **`/articles` says "700 articles"**: the page asks the API for `limit=700` and shows the length of the list. The index holds 1,143. | `12_articles_d_fold.png` |
| 7 | **Word-route articles break the article views.** 218 of 0165's 363 articles have no scan: "Beside the scan" is two empty grey panes with "Page 1 of …", "Classic page" says "No classic page was made", author crops say "no page image on this server", yet the "View beside the scan" button is still offered. Nothing says the article came from the publisher's Word file. | `13j_word_beside_d.png`, `32_word_classic_d.png`, `31_art_citedby_cross_d.png` |
| 8 | **The cross-journal citation is invisible where it happens.** An 0165 article cited by an 0130 article (`0165-006-024-003`) lists the citing title and year only: no journal, no "from another journal" mark. 0165's journal page buries "cited by 0130: 15" in a tab. | `31_art_citedby_cross_d.png`, `07_journal_J0165_d.png` |
| 9 | **Menu: 15 items + search wrap to two rows at 1440 and at 1920** (nav 85 px on most pages); at 1440 six items are bare icons (Plan, Audit, Guide, Librarian, Notes, Releases) a visitor cannot read; "Top cited" (`/works`) and "Most cited" (`/most-cited`) are two pages for one thing; Journals, Institutions, Most cited and Librarian-works are not in the menu at all. Brand reads "inkscript Desk". | every page; `02_project_w1920_fold.png` |
| 10 | **Internal ids and engineering words on show pages:** release ids `R20261103T023001` in every subtitle; article header "Ids 999$c 834226 · Reading j0165_final", "authority 208589 mandumah-authority 208589", institution ids `IS6EJCS2AS`, work ids `CBDD9P2BCR` beside every title on Top cited; `cost_high`, `fixes_many`, "1634 output tokens", "azure-misread" on Quality; "agent:librarian", "rule K1c", "D40–D44", "experiment 67" on Librarian; code paths, "M1 code, free", "P1 prompt, before gate 2", JATS element tables on Audit; experiment numbers on gate1/gate2/deck. Country codes (EG, SA, MA) instead of names; "not recorded" is the biggest bar in 0165's Countries. | `13a_art_text_d_fold.png`, `11_works_d_fold.png`, `13h_art_quality_d.png`, `18_librarian_works_d_fold.png`, `19_audit_corpus_d.png`, `07_journal_J0165_d.png` |

Also worth knowing before the meeting:
- **`/releases` showed "500 Internal Server Error"** on the first open (the live release's before/after took over 30 s
  and the Next proxy hung up: `web.log` "socket hang up"); a second call answered in 0.4 s. Keep it off the path.
- **Opening `/work` claims a task** for the viewer ("yours for 14:55"): a live demo there changes state.
- `/mindmap/` has overlapping labels (Operations/Request pipeline; The vision/The Desk/The pipeline;
  search.mandumah.com over "Mandumah's product line") and shows internal terms (qdrant). Not for shareholders.
- Loads are fine: every page 3–8 s to network-idle on this machine, articles 4.5–8 s; no console errors except
  the release diff above. No horizontal overflow at 1440 or 1920.

## 2. Page by page

Value = what a shareholder learns. 10 s = is it clear in ten seconds. Keep = on the shareholder path or not.

| Page | Value | 10 s? | Findings | Keep |
|---|---|---|---|---|
| `/` Overview (`01`) | none for them: corrector queue | no | Landing page of the whole Desk; "Orphaned", "Byline twin", truncated release id with a warning icon. | hide |
| `/project` (`02`) | the journey strip is excellent (gate 1 ✓ → gate 2 → gate 3 → archive); the mind map is the owner's own board | strip yes | Stale: "being read", "$152 (five) or $456 (ten)". "Waiting on you 10", "Risks 13", "Plan: 14 need you" are internal. | strip only |
| `/plan` (`03`) | internal timeline | no | "Needs you" lists the owner's to-dos (read shareholder docs, decide gate 3); struck-through labels overlap; release-row labels collide with markers; "$456 (estimate, exp 54)". | hide |
| `/index-home` (`04`) | the index's front page: 10 counters, the gate-1 table, top works / institutions / journals | mostly | Intro "one journal read whole (gate 1) and about 600 drawn at random"; Journals card "1 read whole"; 0165 "random sample" in Journals ranked list; gate-1 card says gate 2 "measures the bridges between journals" (now measured) and has no gate-2 card; "2,079.25" references in random 126 (a mean shown with decimals); "Links between articles read 42 … Few yet: the 600 were drawn at random" (check 42: 0130 inside 37 + 0165 inside 21 + 11 across); "Articles read … Scanned articles" though 218 are Word files. | yes, fixed |
| `/journals` (`05`) | 411 journals, the two read whole on top | yes | Banner "One journal … is read whole"; 0165 has no badge (0130 has "gate 1"); 409 random-sample journals with 2–7 articles make a very long list. | yes, fixed |
| `/journals/J0130` (`06`) | a WoS journal record | yes | Note "Gate 1 (experiment 52) …"; "Cited inside / outside 37 / 17" unexplained; "Authors 17 with 2+" vs 16 on the Index home. | yes |
| `/journals/J0165` (`07`) | the second journal, read whole by both routes | yes | No note that it is gate 2's pilot (scan 145 + Word 218); "cited by 0130: 15" hidden in a tab; 55-row author list makes a 3,600 px page; "not recorded" tops Countries. | yes, fixed |
| `/institutions` (`08`) | 318 institutions with countries | yes | Stale banner (Arabic/English twins); kind "university" and codes "EG" in English. | yes |
| `/institutions/IP4TFH3NK6` (`09`) | Helwan University profile | yes | Id in breadcrumb; fine otherwise. | optional |
| `/most-cited` (`10`) | most-cited works, Mandumah publications cited | yes | Good; "In Mandumah" column empty for the top 16 (classics); not in the menu. | yes |
| `/works` "Top cited" (`11`) | same list as `/most-cited` | yes | Duplicate with an id after every title. | hide (merge) |
| `/articles` (`12`) | the article list | no | "700 articles"; first column is the stem; sorted by stem, so 1931–1990 random articles come first. | hide |
| article: text (`13a`) | the rebuilt text | partly | Header: title printed three times, Ids "999$c … Reading j0165_final", authority numbers, institution ids; 8.1 s load. The author crop beside the byline is a strong touch. | via beside |
| article: beside the scan (`13b`) | **the proof that every fact points at the ink** | yes | Works well; the scan starts 760 px down (header + authors first); footer text mentions "ALTO". | **yes, hero** |
| article: scan only (`13c`) | boxes on the scan | yes | Fine. | optional |
| article: classic page (`13d`) | **the rebuilt edition beside the scan**, beautiful | yes | Explanation line is long and technical ("Gemini's reading order", "line-by-line version"). | **yes** |
| article: all fields (`13e`) | 128 fields, 38 with ink | partly | Good for "how deep"; chips "page / catalogue / corrected / derived". | optional |
| article: references (`13f`) | each reference with its ink crop and the linked card | yes | Strong; chips "unresolved: no title", ids beside titles. | yes |
| article: cited by (`13g`, `31`) | who cites this article | yes | No journal shown for the citing article: the 0130 → 0165 bridge is invisible. | yes, fixed |
| article: quality (`13h`) | flags and corrections | no | `cost_high`, "output tokens", `fixes_many`, "azure-misread". | hide |
| Word-route article (`13i`, `13j`, `32`) | — | no | Empty scan panes, "No classic page was made", "no page image on this server". | fix or avoid |
| `/persons/AJHPHG09X3` (`14`) | a WoS author record: 9 publications, h-index 1, times cited with/without self | yes | Person id in breadcrumb. Good. | yes |
| `/explore` (`15`) | every field, sortable, CSV | partly | Tab counts (Authors 2,866, Institutions 919, Journals 928, Cited works 14,410, References 20,301) differ from the Index home (1,182 / 318 / 411 / 14,040 / 20,070) with no word on why (all mentioned vs signed/read). | optional |
| `/how-we-collect` (`16`) | the field guide | no | "Agreed 0 · Not reviewed 335" reads as "nobody checked anything"; 76,000 px long. | hide |
| `/librarian` (`17`) | before/after of institutions | partly | "Proposals only … nothing applied" is false since 2 Nov; "first pass"; 780 articles; "Sample checked 0/30". | fix or hide |
| `/librarian/works` (`18`) | before/after of cited works, blind check 92% | partly | "agent:librarian", "APPLY rule", "rule K1c", "D40–D44"; "the 780 articles"; no word on the production librarian (exp 71: 99.1% precise, 17% to a person, ≈ $3 per 1,000) or 0165 (exp 72 running). | yes, simplified |
| `/audit` corpus (`19`) | 99.84% of lines accounted for | headline yes | Below the headline: developer content (code paths, "M1/P1", JATS element counts, answer keys). Header says 780 but audits 925; Word route not included. | headline only |
| `/audit?tab=article` (`20`) | **one article's lines flowing into fields** (Sankey) | yes | Column titles "Azure lines / Gemini's role / JATS field / Platform record"; node names `table_cells`, `citation_mentions`. | **yes** |
| `/pipeline` (`21`) | **how a page is read**, seven animated stages on a real page | yes | Excellent opener for "how". Stage names "Azure OCR / Gemini / Judge / Fields & ids". | **yes** |
| `/work` (`22`) | the corrector's task: ink crops, one question | yes | Opening it claims a task. Good to *show* the human-in-the-loop once, as a screenshot. | screenshot |
| `/notes` (`23`) | none | — | Empty. | hide |
| `/releases` (`24`) | none for them | no | 500 error on first open; ids, "agent:p1-demo-admin". | hide |
| `/search` (`25`) | search across articles, people, works | yes | Fine; works ids beside titles. | optional |
| `/works/CBDD9P2BCR` (`30`) | **one cited work: 7 editions folded into one card, 18 printed citations with their ink, 14 citing articles** | yes | The best picture of reconciliation; id in breadcrumb. | **yes** |
| `/pitch/` (`26`) | the 23 Oct deck | yes | Stale (see §3): "October 2026", 780 articles, gate-1 ratios before the librarian, $100.15 spend, gate 2 "$152 / $456" as the ask, slide 11's tour (`/journals/J0130`, "32 citations"), demo screenshots of 23 Oct. | update |
| `/gate1/` (`27`) | gate 1's story with the self-citation arcs | yes | Pre-librarian numbers (84 vs 11, 16.9%, 39), "prompt v3.5b", "experiment 48/52", stems as labels; no link back to the Desk. | update or skip |
| `/gate2/` (`28`) | the selection heat map | yes | "Prices are estimates; nothing has been run." Needs the pilot's answer on top. | update |
| `/mindmap/` (`29`) | Mandumah product map | no | Overlapping labels; internal. | hide |

## 3. Numbers that disagree (pick one source)

| Quantity | Live index (`/index/overview`, release R20261103T023001) | Elsewhere |
|---|---|---|
| Articles in the platform | **1,143** (1,089 final + 54 structured) | `/articles` 700 (API limit); `/audit` "780" in text, 925 audited; `/librarian*` "780"; deck "780 (726 fully rebuilt)" |
| Journals read whole | **2** (0130, 0165) | Index home, Journals banner, overview card: "1" |
| Gate 1, institutions in 2+ articles | **25 vs 6.3** (with the librarian) | deck slide 6: 26 vs 3.8; `/project` source text: 26 vs 3.6 |
| Gate 1, cited works shared by 2+ | **121 vs 16.7** | `/librarian/works` 118 vs 16.65; deck and `/gate1/` 84 vs 11 |
| Gate 1, references to a held work | **16.8%** | `/librarian/works` 18.06%; `/gate1/` 16.9%; deck 15.8% |
| Gate 1, citations inside the journal | **37** (22 → 35) | `/gate1/` 39; deck 32 |
| Nothing lost | `/audit`: **99.84%** of 525,459 lines (925 articles) | overview / handoff: 99.81% of 435,270 (780); exp 70: 0165 99.981% |
| Institutions | **318** (current posts, 1,143 articles) | `/librarian` 234; overview.md 242 (780); Explorer 919 (all rows) |
| Authors | **1,182** signed | Explorer 2,866 (all persons incl. cited) |
| Gate 2 cost for ten | pilot rate: **≈ $313** (exp 70, line 315) | `/project`, `/plan`, `/gate2/`, deck: $456 (worst $633) or $152 |
| Model spend | log: $127.08 at 19:43 2 Nov (+ pilot to $23.29 total) | deck: $100.15 |

**Rule for tomorrow:** every shareholder-facing number comes from the live index API (`/desk/api/index/overview`,
`/index/gate1`) or from one new small file of gate-2 numbers (from `experiments/70_gate2_pilot/out/measure70.json`),
and every page/slide that quotes a gate-1 or gate-2 figure uses the "with the librarian" values.

## 4. The shareholder path (7 screens, about 12 minutes)

| # | Story beat | Screen | What they see | Say |
|---|---|---|---|---|
| 1 | The problem and the asset | `/pitch/` slides 2–3 (or a new Story page, step 1) | <1% of Scopus is Arab; ARCI is a 400-journal selection. Mandumah: 1,013,912 documents with full OCR, 308,593 more, 1,558,415 catalogue records. | "We hold the evidence the region is judged without." |
| 2 | How a page is read | `/pipeline` (play from stage 1) | One real scanned page through scan → words → structure → rules → check → fields → index. | "The machine never types the text; it says what each printed line is." |
| 3 | Every fact points at the ink | `/articles/0165-008-029-001?tab=text&view=beside`, then `view=classic` | The scan and the rebuilt article side by side; hover a block, it lights up on the page; the classic edition. | "Click any fact, you land on the printed lines." |
| 4 | Quality, measured | `/audit?tab=article&stem=0165-008-029-001` with the corpus headline (99.84% of 525,459 lines) above it; the deck's proof (0 wrong words of 1,532 on 60 unseen pages) | Every line flowing into a field; nothing lost. | "Measured beside the scan, not reported by the machine." |
| 5 | The index forms | `/journals/J0165` → a new **Gate 2 card/page** (two journals: 15 + 16 cross-citations, 17 shared authors vs 0, 157 shared works vs 26, 313 coupled pairs vs 118) → one person `/persons/AJHPHG09X3` | A journal record like Web of Science; then the bridges between two journals; then an author record with h-index. | "Read two education journals whole and they cite each other; random sets show nothing." |
| 6 | Reconciliation | `/works/CBDD9P2BCR` (7 editions, 18 printed citations, one card), then `/librarian/works` before/after (9,137 → 8,850 cards; 209 → 289 cited by 2+) and the production librarian numbers | The same book cited seven ways becomes one work; the AI librarian, checked blind, applied only where ≥ 98%. | "A wrong bridge corrupts every count, so bridges are judged by precision: 99.1%, about $3 per 1,000 decisions." |
| 7 | What it costs, what's next | `/project` journey strip + updated deck slides 9 and 12 | Gate 1 $24.24 ✓ · gate 2 pilot $23.29 ✓ (≈ $313 for the ten) · gate 3 ≈ $43k before 1 Dec / ≈ $86k after · the archive. | "The nine journals next; decide gate 3 before the price doubles." |

Optional on request: `/most-cited`, `/institutions`, `/explore` (CSV export), `/work` (as a screenshot: the human in
the loop).

**Hide from the path (workbench):** `/` Overview, `/work`, `/notes`, `/releases`, `/plan`, `/how-we-collect`,
`/articles` list, article *Quality* and *History* tabs, `/works` "Top cited" (duplicate), the audit's lower sections,
`/mindmap/`, `/inventory/`, `/mockup/`, the project mind map's "Waiting on you / Risks".

## 5. Changes, prioritised

Effort: S < 1 h, M 1–3 h, L > 3 h. Files are under `experiments/49_correction_desk/`. Nothing here was changed.

### Must for tomorrow

| # | Page | Problem | Fix | Files | Effort |
|---|---|---|---|---|---|
| M1 | new `/story` (and make it the landing page in show mode) | No guided route; the landing page is a task queue | A **Story** page: 7 large steps (the path in §4), each a sentence, 1–3 big numbers and a "Open the screen →" link (or a thumbnail), with ← → keys / a step-through bar. Numbers read from `/index/overview` + a gate-2 file. The logo goes to `/story` for non-correctors or when show mode is on. | `web/pages/story.tsx` (new), `web/components/Layout.tsx` (logo href), `web/lib/strings.ts` | M |
| M2 | Gate 2 everywhere it is missing | Tonight's headline is on no page | (a) A **gate-2 card** on `/index-home` under the gate-1 card: 0130 ↔ 0165 references 15 / 16; shared authors 17 vs 0.0; shared cited works 157 vs 26.3; coupled pairs 313 vs 118; shared institutions 17 vs 16.1 (honest: chance); cost $23.29; 9 right / 1 minor / 0 serious on 10 pages. Source: `experiments/70_gate2_pilot/out/measure70.json` served by a small `/index/gate2` route (or a static JSON). (b) Replace the top of `/gate2/` with the pilot's answer ("Done: 363 articles, $23.29; the two journals cite each other …"), keep the heat map below and drop "nothing has been run". | `desk/index_api.py` (+ route), `desk/index_pages.py`, `web/pages/index-home.tsx`, `web/public/gate2/index.html` | M |
| M3 | `/index-home`, `/journals`, `/journals/J0165` | 0165 called "random sample"; "1 read whole" | Use `WHOLE_JOURNALS` (already in `index_pages.py` line 31) for the label: "read whole: gate 1" / "read whole: gate 2 pilot (scan 145 + Word 218)". Fix the overview card sub (`index_pages.py` line 308), the intro sentence (`index-home.tsx` line 54), the ranked-list sub (line 125), the Journals banner (`journals/index.tsx` line 17), and add an `is_whole`/gate note on the journal page (`journals/[id].tsx` lines 29, 44). | as listed | S |
| M4 | stale texts | "being read", "$152/$456", "proposals only", "still two records", "the 780 articles", "before gate 2" | `desk/project/project.json` `stage.label`/`detail` → "Gate 2's pilot is done: two journals cite each other; the nine others next" and the gate-2 cost → "pilot $23.29; ten ≈ $313" (via `desk.plan_cli`/project tooling as the repo requires); `web/pages/librarian.tsx` line 215 banner → "Applied on 2 Nov (exp 64)"; `web/pages/institutions/index.tsx` line 17 banner → drop the twins sentence; `web/pages/audit.tsx` lines 33/39 → "Every printed line of the articles read (925 scanned) …", "All articles", drop "orange is what the prompt must ask for before gate 2"; `/librarian/works` "780" wording. | as listed | S |
| M5 | `/articles` | "700 articles" | Show the total from the index (or "showing 700 of 1,143"), sort by journal then year; or simply hide the list from the path. | `web/pages/articles/index.tsx` line 15, `desk/api.py` line 433 | S |
| M6 | top menu | 15 items, wraps at 1440 and 1920, bare icons, duplicates | Regroup into **Story · Index ▾ (Journals, Institutions, Most cited, Search, Explorer) · Quality ▾ (How a page is read, Nothing lost) · Librarian ▾ (Institutions, Cited works) · Project ▾ (Journey, Plan)** and a right-hand **Workbench ▾** (Overview, Work, Notes, Releases, Guide, Articles) for correctors; one row, labels always visible. Rename brand "inkscript Desk" → "Mandumah Citation Index". Drop `/works` from the menu (keep the route) in favour of `/most-cited`. | `web/components/Layout.tsx`, `web/lib/strings.ts` | M |
| M7 | show mode | ids and engineering words on show pages | A **Presentation mode** toggle (`?show=1` → localStorage, with a small chip "Presentation" to turn it off) that hides: release ids in subtitles ("read from R…"), the article header's Ids block and authority/institution ids, ids beside titles (`/works`, search, references), the Quality/History/Notes tabs, the audit page below the headline cards, the Workbench menu. Implement as a `useShow()` hook + a `data-show` class on `<body>` with `.show-hide{display:none}` on those elements. | `web/lib/me.tsx` or new `web/lib/show.ts`, `Layout.tsx`, `pages/articles/[stem].tsx` (header ~lines 204–278), `components/IndexBits.tsx`, `pages/audit.tsx`, `pages/works/index.tsx` | M |
| M8 | Word-route articles | empty scan panes, "No classic page was made" | When the article has no page images: hide "View beside the scan" / Beside / Scan / Classic, and show a chip "Built from the publisher's Word file (no scan)" in the header. At minimum: never open a Word-route article in the demo (the path uses `0165-008-029-001`, a scan). | `pages/articles/[stem].tsx`, `components/BesideScan.tsx`; flag from `desk/pages.py` (`run` startswith `w`) | S |
| M9 | article *Cited by* | the cross-journal citation is invisible | Show the citing article's journal, and a teal chip "another journal" when it differs. Add `journal_id`/`journal` to each `cited_by` row. | `desk/pages.py` (~line 514), `pages/articles/[stem].tsx` lines 109–114 | S |
| M10 | `/pitch/` | the deck of 23 Oct | Update: date "November 2026"; slide 5 add gate 2's 9 right / 1 minor / 0 serious; slide 6 gate-1 numbers with the librarian (16 vs 0.25, 25 vs 6.3, 121 vs 16.7, 16.8%, 37 citations) **plus a gate-2 row or a new slide "Two journals cite each other"** (15 + 16; 17 vs 0; 157 vs 26; 313 vs 118); slide 7 cost: pilot $0.0078 a page, Word route $0.0055 an article measured (no longer "untested"), spend from the log; slide 9: gate 2 "pilot done $23.29, the ten ≈ $313"; slide 11: the new path (§4) with today's numbers (1,143 articles, two journals); slide 12 ask: "approve the nine (≈ $290)". Retake demo shots `pitch/shots/demo1–6.png` from this audit's shots. | `web/public/pitch/index.html`, `web/public/pitch/shots/` | M |
| M11 | `/project` | internal board shown to visitors | In show mode, show only the journey strip (with the updated gate-2 stage) and hide the map's "Waiting on you / Risks" and the Plan pill. | `pages/project.tsx`, `components/ProjectMap.tsx` | S |

### Nice (if time allows tonight)

| # | Page | Fix | Files | Effort |
|---|---|---|---|---|
| N1 | `/journals/J0165` and J0130 | A "Bridges with other journals" panel at the top: cites 0130 ×16, cited by 0130 ×15, a two-node diagram (teal arcs, counts as labels, no overlap). Collapse the author list to the top 10 with "show all". Countries: names, "not recorded" last and grey. | `pages/journals/[id].tsx`, `components/IndexBits.tsx` | M |
| N2 | `/gate1/` | Refresh numbers to the librarian values, drop "prompt v3.5b / experiment 48", titles instead of stems in the arcs, a "back to the index" link. | `web/public/gate1/index.html` | S |
| N3 | `/librarian/works` + `/librarian` | Plain header ("The AI librarian checks every bridge; applied only where measured at 98%+"), the production numbers (99.1% precise, 17% to a person, ≈ $3 per 1,000 decisions), hide K1c / D-rules / agent ids in show mode. | `pages/librarian/works.tsx`, `pages/librarian.tsx` | S |
| N4 | `/audit` | Corpus tab in show mode: the four cards + "What fell through" bars only; rename Sankey columns "The printed lines → What each line is → The article file → The index". | `pages/audit.tsx`, `components/audit/*` | S |
| N5 | article header | Title once (printed form), catalogue/translated only when different; hide Ids. | `pages/articles/[stem].tsx` | S |
| N6 | `/index-home` | Show means as whole numbers ("about 2,079"), explain Explorer vs index counts in one line, recheck "Links between articles read 42". | `index-home.tsx`, `desk/index_pages.py` | S |
| N7 | `/releases` | Precompute the live release's diff, or raise the proxy timeout, so the first open does not 500. | `desk/release.py` / `next.config.js` | S |

### Later

- One source of truth for headline numbers: a `/desk/api/headline` endpoint (live index + gate files + spend log),
  read by the Story page, the Index home, `/project`, the deck and the gate pages (the deck fetching it at load).
- A real role for visitors (read-only "guest" actor) so show mode is a role, not a toggle.
- Word-route articles: a reading view without the scan (the publisher's page layout is not available; the text and
  structure are), and audit coverage for them.
- Explorer: define each tab's population in its tab label ("Authors (all persons mentioned)").
- The pipeline page: a short "the Word route" variant for the 218 Word-only articles.
- `/mindmap/`: fix collisions with a label-avoiding layout, or retire it.

## Files

- Shots: `experiments/73_desk_showcase/out/audit_shots/` (`*_d.png` full page, `*_d_fold.png` first screen,
  `*_w1920*.png` wide check).
- Walk script and per-page timings were kept in the agent's scratchpad (not part of the repo).
- Progress log: [progress.md](progress.md).
