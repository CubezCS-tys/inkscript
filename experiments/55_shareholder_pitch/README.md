# Experiment 55: the shareholder pitch

**Question** (owner, 2026-10-23). The shareholders asked "where's the value, why are we doing this". Within a week
the owner presents live, in English, on their own screen. What is the honest value story, and a short deck (8–12
slides) that opens and closes the live demo of the Desk?

**Answer.** [story.md](story.md): the story on one page, a 2-minute spoken version, and 8 hard questions with honest
answers. The deck: 12 slides at `experiments/49_correction_desk/web/public/pitch/index.html`, served by the Desk at
`/pitch` (added to both static-page rewrites in `web/next.config.js`).

The story in brief: Arabic research is nearly invisible in the indexes used to judge research; Mandumah holds the
full text and catalogue no one else has at this depth; we rebuild each article from its scan, traceable to the ink;
measured accuracy (0 wrong words of 1,532 on unseen pages), one journal read whole forms a citation network (gate 1),
about $0.01 a page; two products on one data set; business models as proposals; gates 2 and 3 as the road and the
ask, with the 1 December price rise as the deadline.

## Method ($0)

1. Read the repo's own numbers: docs/overview.md, server-agent-briefing.md, STATUS.md (2026-10-22), vision.md;
   experiments 43 (exam, proof pack, fix round 3), 44, 45, 48, 49, 50 (Mandumah's products and the AI-Search weak
   spots), 52, 53, 54; the spend log `experiments/43_rehearsal/out/gemini_spend.jsonl` (sum $100.15, 2026-10-18
   15:41 → 2026-10-22 15:55).
2. Web search (standard mode, public terms only, no Mandumah data in any query) for the competitors; pages fetched
   where the site allowed it (Clarivate's own pages and Al-Fanar returned 403; those figures come from search
   summaries and are marked so).
3. Wrote the deck as one self-contained HTML file: system fonts, no network loads, arrow keys / space / PageUp-Down,
   Home / End, **N** speaker notes (with sources), **F** full screen, **P** print (one 16:9 slide a page; checked: 12
   pages at 1280×720). Arabic names in `lang="ar"` spans, right-to-left. Screenshot slots on slide 11 read
   `pitch/shots/demo1.png` … `demo6.png` and fill themselves when the files exist.
4. Opened it with Playwright (chromium-1243) and looked at every slide: `out/shots/slide01.png` … `slide12.png`, the
   notes panel (`notes_slide03.png`, `notes_slide12.png`), the print PDF (`deck_print.pdf`, two pages rendered as
   `print_p6.png`, `print_p8.png`).

## Numbers used, with their source

| Number | Source | Date |
|---|---|---|
| 1,013,912 documents with scan + OCR; 308,593 legacy PDFs | experiments/44_bucket_map | 2026-10-19 |
| 98% of legacy with the publisher's Word file | docs/overview.md | 2026-10-22 |
| 1,558,415 catalogue records, author authority file | experiments/45_marc_db | 2026-10-20 |
| 0 wrong words of 1,532; 43/60 pages fully right; 0/60 serious; metadata 25/30; citations 57/80, filled fields 313/314 | docs/STATUS.md, server-agent-briefing.md (proof pack + fix round 3) | 2026-10-20/21 |
| Gate 1: 126 articles, 2,439 pp; 16 vs 0.25, 26 vs 3.6, 84 vs 11.3, 16.9% vs 2.9%, 39 internal citations (38 right), 9/1/0 on 10 pages, $24.24, $0.192 an article, $0.0099 a page | experiments/52_journal_gate1 | 2026-10-22 |
| Exam: $31.94, $0.106 an article, 3,404 pages; ≈ $106k per million documents now (≈ £96k), double after 1 Dec | experiments/43_rehearsal "The exam" | 2026-10-20 |
| Word route: 139/139 valid by code, $0.010–0.028 an article (estimate, untested) | experiments/53_word_route | 2026-10-22 |
| Gate 2: ten journals 3,460 articles ≈ $456 (worst $633); five 1,344 ≈ $152 (worst $216) | experiments/54_gate2_selection (draft) | 2026-10-22 |
| Gate 3: 162,816 articles, ≈ $43k now, ≈ $86k after 1 Dec | docs/overview.md, ideas.md, handoff.md (derivation not written beside it) | 2026-10-22 |
| ~16,800 h correction at 1M documents (~56 h per corrector of 300) | experiments/48_linking_probe | 2026-10-21 |
| Spend $100.15 since the 18 Oct top-up | gemini_spend.jsonl | last entry 2026-10-22 15:55 |
| AI-Search chunk weak spots | experiments/50_mindmap, `out/mandumah_products.json` | 2026-10-21 |

## Sources (competitors and the market), read 2026-10-23

- Clarivate ARCI launch, August 2020, Egyptian Knowledge Bank, "over 400" journals, bibliographic data and
  citations: https://www.stm-publishing.com/clarivate-launches-the-arabic-citation-index-in-egypt/
- El-Ouahi, "The Arabic Citation Index – Toward a better understanding of Arab scientific literature" (arXiv,
  revised 2023): coverage from 2015, 138,283 records 2015–2020 as of May 2022, records include cited references,
  separate subscription: https://arxiv.org/abs/2101.12177
- Clarivate's ARCI pages (403 to the fetcher; listed for the owner to check the current journal count):
  https://clarivate.com/webofsciencegroup/solutions/Arabic-citation-index ,
  https://clarivate.com/academia-government/blog/the-arabic-citation-index-transforming-local-research-into-global-impact/
- Scopus, ~280 of 29,553 journals from Arab countries (<1%), Al-Fanar Media, May 2025 (from the search summary; the
  page returned 403): https://al-fanarmedia.org/2025/05/arab-scientific-journals-make-up-less-than-1-of-global-indexes/
- Touri, "Scopus database and the Arabic journals in it", MIJEPS, 2023 ("Arabic has nearly no place"):
  https://ojs.mediu.edu.my/index.php/MIJEPS/article/view/4525
- ARCIF 2025 report (October 2025): ~5,500 journals examined, 1,272 qualified, 956,000+ papers, 364,000 authors:
  https://www.qatar-tribune.com/article/199838/front/qatar-tops-arab-world-in-engineering-technology-arcif-scientific-report ;
  objectives https://emarefa.net/arcif/goals/
- e-Marefa (~1,900 periodicals, ~400,000 articles; search summary, date not stated):
  https://edesiderata.crl.edu/resources/e-marefa
- Al Manhal (475+ peer-reviewed eJournals, 19,950+ eBooks, 9,310+ eTheses; search summary):
  https://stm-publishing.com/?p=16049 , https://libguides.princeton.edu/az/al-manhal
- Shamaa (free, Arab education research, 2007 onward): https://shamaa.org/eng/objectives-eng/ ; 376 periodicals
  and 93,937 works from a search summary of Shamaa's pages, not confirmed on a page we could read.

## What could not be verified

- **ARCI's current size.** Public Clarivate pages were not readable (403). The latest independent figure is May 2022.
- **Whether ARCI captures footnote citations.** The repo's briefing says ARCI is "metadata only, none of the
  footnotes". That is **not right as stated**: ARCI records include cited references (El-Ouahi). The deck therefore
  claims depth (every article, decades back, footnotes, proof from the scan), not that ARCI lacks references.
- **ARCIF's method** (whether its citations come from e-Marefa's full text). Its 2025 scale is large; it is named as
  a competitor on rankings.
- **Gate 3's $43k:** the figure is in three docs but its derivation is not written next to it.
- **Storage, servers, correctors' time, prices and buyers:** not priced or researched in this project; the deck
  says so.

## What it changed

Nothing in the pipeline. The Desk serves a new static page once rebuilt/restarted: `next start` does not serve files
added to `public/` after its build, so `/pitch` returned 404 on the running :8004 at 2026-10-23 (left untouched, as
instructed). Opening the HTML file directly works.

## Files

- `story.md`: the narrative, spoken version, hard questions.
- `experiments/49_correction_desk/web/public/pitch/index.html`: the deck (screenshot slots: `pitch/shots/demo1–6.png`).
- `out/shots/` (gitignored): slide screenshots and `deck_print.pdf`.
