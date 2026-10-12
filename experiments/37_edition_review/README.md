# 37 — The editions by eye: scan vs layout-faithful vs one-column

**Question.** Looked at the way a reader would, how close are experiment 35's derived editions to the original
pages? What is wrong, how often, and what should be fixed first?

**Method.**
- `shots.py` renders every page of all 205 documents: the scan on the left and the layout-faithful PDF on the
  right (`out/shots/<id>/pNN.jpg`, 3,254 pages), plus each page of the one-column PDF (`onecol-NN.jpg`, 1,969 pages).
  It takes 4 min on 4 workers and 1.3 GB.
- Reviewer agents each look at up to 6 page pairs and 2 one-column pages per document. They report every
  difference with where it is and how bad it is, and score each document 1–5.
- Each document's findings are saved to `out/reviews/<id>.json` as soon as that document is done. A run skips the
  documents that already have a file.
- A final agent checks the findings against crops and writes `out/report.html` with a ranked fix list.

**Status (2026-10-12): paused.** The first run hit the owner's Claude usage limit. Nine reviewers lost their
finished work, because they held their findings until the end. Only one batch survived: 20 documents and 64
issues, in `out/reviews/`. The rest (185 documents) runs in a session the owner sets aside, saving each document
as it goes.
