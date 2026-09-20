# 09 — Letters along the pen path

**Question.** The owner's picture: a person can recognise a number traced on
their back by feeling the strokes. Can a joined word's letters be found by
following the ink like a pen, and letting the book teach its own alphabet?

**Method.** `penpath.py` (first sketch), `atlas.py`, `rounds.py`: thin the ink
to its centre line; trunk from right to left; everything else hangs from the
trunk point it attaches to; cuts are points on the path; the document's mean
picture of each letter-form is built from the cuts, the cuts re-chosen to
match it, and so on. Now lives in `src/inkscript/geometry/penpath.py`;
narrative in `docs/letters.md`.

**Results.**
- Reference document: ~half of random pieces cut right by eye → ~50 of 60
  after the rounds; the atlas alone made some worse (big letters swallow small
  ones) until combined with the hard facts.
- In the build: 63% → 95% → 96% of words with a box for every letter, as the
  causes were removed one by one (rejecting good cuts; broken ink; blobs and
  runs not pairing off; a space lost from `ركبهم ـ`).
- At scale (227 journals, 194 scanned, 3,511 pages): 85.8% first run, **96.8%**
  second; text unchanged at 99.99% of words.
- Found by accident: a per-cut picture cache that took 5.7 GB a process.

**Scripts still in use** (the letter tooling — see `docs/letters.md`):
`coverage.py`, `summary.py`, `why_word.py`, `nopath.py`, `diagnose.py`,
`run_set.sh`, `watchdog.sh`. `penpath.py`/`atlas.py`/`rounds.py` are the
historical sketches (`diagnose.py` borrows their drawing helpers).
