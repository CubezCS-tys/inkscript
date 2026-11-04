# Shared contract for the three showcase agents (2026-11-03, set by the lead)

1. Show mode: `web/lib/showmode.ts` — `useShowMode(): boolean` (on with `?show=1`, remembered; off with `?show=0`).
   Every page decides what to hide in show mode (ids, release strings, workbench parts). Agent A adds the toggle.
2. Headline numbers come from ONE place: `GET /desk/api/headlines` (agent B builds it in `desk/headlines.py`,
   registered at the end of `desk/api.py`). Shape (all numbers computed live from the current release + experiment
   outputs; every value has a short `def` string):
   { release, articles, pages, words, references, journals_read_whole: [{id, title, articles, country}],
     institutions, institutions_with_country_pct, cited_works, cited_by_2plus, held_pct,
     audit_pct, words_wrong: {wrong: 0, of: 1532, pages: 60},
     gate1: {journal: "J0130", authors_2plus: [16, 0.25], institutions_2plus: [25, 6.3], shared_works: [121, 16.7]},
     gate2: {pair: ["J0130","J0165"], cites_a_to_b: 15, cites_b_to_a: 16, shared_authors: [17, 0.0],
             shared_works: [157, 26.3], coupled_pairs: [313, 118], cost_usd: 23.29, ten_journals_usd: 313},
     librarian: {precision_pct: 99.1, usd_per_1000: 3, institutions: [271, 242], cited_works: [9137, 8903]},
     costs: {per_scan_page_usd: 0.0078, per_word_article_usd: 0.0055, price_doubles: "2026-12-01"} }
   Agent A's Story page and agent C's deck read these; if a key is missing, show "—" (never invent).
3. File ownership (re-read a shared file right before editing; minimal edits):
   - A: `web/components/Layout.tsx` (menu), `web/pages/story.tsx` (new), `web/pages/index.tsx` (landing in show mode), `web/pages/project.tsx` (show mode).
   - B: `desk/headlines.py` (new), `desk/index_pages.py`, `web/pages/index-home.tsx`, `web/pages/journals/*`, `web/pages/institutions/*`,
     `web/pages/articles/*` (+ components it uses), `web/pages/librarian*.tsx`, `web/pages/audit.tsx`, `web/pages/most-cited.tsx`, `web/pages/works/*`, `web/pages/persons/*`.
   - C: `web/public/pitch/` (deck), `web/public/gate2/` (static page), `desk/project/project.json` (stage/money text), `desk/plan/` via plan_cli only.
4. Dev servers: A ports 8124/8125 NEXT_DIST_DIR=.next-a; B 8134/8135 .next-b; C 8144/8145 .next-c. Never `next build` / `next dev` with the default distDir; never restart :8004/:8005 (the lead deploys).
