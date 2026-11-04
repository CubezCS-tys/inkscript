# The value story: why Mandumah is rebuilding its archive

For the owner's shareholder presentation (English, live, on the owner's screen). Written 2026-10-23. Every number
carries its date and its source in this repo; numbers about other companies carry a public URL (list at the end of
[README.md](README.md)). **Proposals are labelled as proposals.** Estimates are labelled as estimates.

## The story on one page

**The problem.** Arabic scholarship is close to invisible in the indexes the world uses to judge research. Of
29,553 journals in Scopus, about 280 come from Arab countries (under 1%; Al-Fanar Media, May 2025). Clarivate's
Arabic Citation Index (ARCI, on Web of Science since August 2020, with the Egyptian Knowledge Bank) is a real step,
but it is a *selection*: "more than 400" curated journals, coverage from 2015, 138,283 records for 2015–2020 as of
May 2022 (El-Ouahi, arXiv 2101.12177). Yet universities, promotion committees, ranking bodies and ministries in
the region need what Web of Science gives English-language science: times cited, h-indexes, institution and journal
profiles. For most Arabic research those numbers do not exist, or rest on a thin slice.

Mandumah's own AI product has a related problem. ai.mandumah.com answers from OCR chunks that mix bylines,
affiliations, running heads, page numbers, interleaved footnotes and reference lists into the text it quotes as
evidence (the AI-Search team's own list of weak spots, 2026-10-21).

**The asset.** Mandumah already holds what no index has at this depth: **1,013,912 documents** with the scan and a
full OCR reading in its S3 archive, **308,593 more** as PDFs (98% with the publisher's Word file), and a catalogue
of **1,558,415 MARC records** with an author authority file (experiments 44 and 45, 2026-10-19/20). Others index
metadata and reference lists of selected journals; Mandumah has the full text of every article in the journals it
carries, back decades.

**What we built.** A pipeline that rebuilds each article from its scan: every word as printed (never retyped), its
structure (headings, paragraphs, footnotes, tables, references), its people, institutions and journal, each fact
tied to the exact ink on the page. The articles go into one database of people, works, institutions, journals and
citations. A correction Desk lets about 300 correctors fix what the machine got wrong; every decision is kept and
re-applied on every rebuild. One data set feeds two products: **a better RAG** (clean chunks that know a heading
from a footnote) and **an Arabic citation index** (who cites whom, times cited, h-index).

**The proof (measured, not promised).**
- On 60 random pages of 300 articles the pipeline had never seen: **0 wrong words of 1,532**, 43 pages fully right,
  **0 serious errors** (2026-10-20/21).
- Gate 1, one whole education journal (مجلة الطفولة العربية, 126 articles, 2026-10-22): authors who publish again
  **16 vs 0.25** in a random set of the same size, institutions repeating **26 vs 3.8**, cited works shared **84 vs
  11**, **32 citations inside the journal** linked in the platform (39 with the catalogue matcher, 38 of 39 read right), **15.8%** of references landing on a work Mandumah
  already holds (random: 2.4%; the catalogue matcher finds 16.9% vs 2.9%). The index works journal by journal, as Web of Science did in 1961.
- Cost: **$0.106 an article** on the 300-article exam, **$0.192** on gate 1's long articles (about **$0.01 a
  page**); the Word route is free in code and an estimated **$0.010–0.028** an article with a text-only model step.

**The road and the ask.** Gate 2: five education journals (1,344 articles, about $152) or ten (3,460 articles,
about $456). Gate 3: the whole Education slice, 162,816 articles, **about $43k at today's model prices, about $86k
after 1 December 2026**, when the price doubles. Then the other subjects. The decision for shareholders: back the
Education Citation Index through gates 2 and 3, the correction team's pilot, and the move to proper storage and
servers, and choose which business model to test first.

## The 2-minute spoken version

> Thank you. I want to answer one question: why are we doing this?
>
> When a university in Riyadh, Cairo or Rabat wants to know how often its professors are cited, it looks in Web of
> Science or Scopus. Arabic research is almost not there. Fewer than one in a hundred Scopus journals come from Arab
> countries. Clarivate built an Arabic index in 2020: it is a selection of about four hundred journals, from 2015
> on. Promotion committees, ministries and ranking bodies are deciding with a fraction of the evidence.
>
> We hold the evidence. Over a million documents, scanned and read, plus one and a half million catalogue records
> with an author file. Nobody else has the full text of this many Arabic articles.
>
> What we built in the last weeks takes each scanned article and rebuilds it: every word exactly as printed, the
> headings, the footnotes, the references, the authors and their universities. Every fact points back to the ink on
> the page, so anyone can check it. A desk for about three hundred correctors fixes what the machine misses.
>
> Does it work? On sixty random pages it had never seen, it got every one of fifteen hundred words right, with no
> serious errors. And when we read one whole education journal, the connections a citation index needs appeared:
> authors writing again, universities repeating, articles citing each other, and one reference in six landing on
> something we already hold. It cost twenty-four dollars, about nineteen cents an article.
>
> The same clean data makes our AI assistant better, and builds an Arabic citation index deeper than anything on
> the market. We start with Education, journal by journal. Next step: ten journals for about four hundred and
> fifty dollars. The whole Education slice: about forty-three thousand dollars at today's price, double that
> after the first of December.
>
> Let me show you what it looks like.

## Appendix: hard questions, honest answers

1. **"Clarivate already has an Arabic Citation Index. Why would anyone pay for ours?"**
   ARCI is real and indexes cited references (El-Ouahi). But it is a curated selection of 400+ journals with
   coverage from 2015. We would cover every article of every journal Mandumah carries, back decades, with the full
   text, the footnotes (where much Arabic citing happens) and a link from every count to the printed page.
   *What we have not verified:* whether ARCI captures footnote citations, and its current journal count (the public
   pages we could read say "more than 400").

2. **"How do you know it is accurate? An AI read it."**
   The model never types the text: it only says which printed line is a heading, a footnote or a reference. The
   words are the OCR's, checked against the scan. An independent check on 60 random unseen pages found 0 wrong
   words of 1,532 and 0 serious errors; 43 of 60 pages were fully right, the rest had small slips (2026-10-20/21,
   experiment 43 proof pack + fix round 3). Weak spots, honestly: references with empty fields (57 of 80 fully
   right; filled fields 313 of 314 right), small structure slips, italics and sub/superscript, some tables.

3. **"What does the whole archive cost?"**
   Measured: $0.106 an article on the 300-article exam (11.3 pages an article), $0.192 on gate 1 (19.4 pages),
   about $0.01 a page either way. The repo's projection is about $106k per million documents at the exam's mix
   (about £96k incl. VAT) at today's price, **double after 1 December 2026** (estimates). The Word route, where the
   publisher's file exists, is free in code plus an estimated $0.01–0.03 an article (its paid test, under $1, has
   not run yet). Storage, servers and correctors' time are not in these figures and have not been priced.

4. **"How much human correction does this need?"**
   An estimate from the 600-article linking probe (experiment 48, 2026-10-21): about 16,800 hours at a million
   documents, about 56 hours per corrector across 300. It is an extrapolation; gates 2 and 3 exist to measure it.
   The Desk (built, 19 tests passing) records every decision so nothing is corrected twice.

5. **"Do Arabic articles actually cite each other enough for an index?"**
   In random articles across all subjects, only 2.4% of references land on a work Mandumah holds (platform links; 2.9% with the catalogue matcher); two-thirds of
   citations are books and classical works. Inside one education journal, 15.8% land on held works (16.9% with the catalogue matcher) and 62% of the
   Arabic article/thesis references do. That is why we go journal by journal. *Still thin:* repeat co-authorship
   (one pair) and corresponding authors (none marked). Citations *between* journals are gate 2's question.

6. **"Why now? Why not wait for prices to fall?"**
   The model price for the reader we use doubles on 1 December 2026 (Argon; Flash on 1 January 2027), per the
   project's notes. Gate 3 is about $43k before and about $86k after. Waiting costs money unless prices fall again.

7. **"Is the data safe?"**
   Everything runs on Mandumah's own machines; the catalogue, database and documents never go to a public link or
   to GitHub, and the working pages listen on the local machine only. The model provider sees page images during
   processing.

8. **"Who buys it, and for how much?"**
   We do not know yet; there is no pricing or customer research in this project. The deck lists options, not
   commitments. The first test can be cheap: show a university its own profile from gate 2's ten journals.
