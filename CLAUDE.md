# inkscript — start here

A scanned Arabic page goes in; a PDF comes out in which the printed ink *is*
the text: each word (and, since 2026-09-20, each letter) is a Type 3 glyph
whose outline is its own traced ink, mapped to its reading. It selects,
copies and searches in Chrome like a born-digital PDF, and the vector
version needs no image. Why this exists, in the owner's words:
[docs/vision.md](docs/vision.md).

## Read in this order

1. [docs/STATUS.md](docs/STATUS.md) — what works today, with the numbers and their dates; what is in flight.
2. [docs/ideas.md](docs/ideas.md) — every idea discussed: done, tried-and-dropped, parked, open — with where to pick each up.
3. [docs/roadmap.md](docs/roadmap.md) — the milestones the owner wants next, in order.
4. [docs/pipeline.md](docs/pipeline.md) → [docs/letters.md](docs/letters.md) → [docs/pdf-writing-rules.md](docs/pdf-writing-rules.md) — how it works; every rule with the measurement behind it.
5. [docs/decisions.md](docs/decisions.md) — why things are the way they are. Read before "fixing" something that looks odd.
6. [docs/operations.md](docs/operations.md) — running sets on this machine: data locations, memory, the watchdog, resuming; [docs/moving-to-a-server.md](docs/moving-to-a-server.md) — what git does not hold and how to take it along.
7. [docs/glossary.md](docs/glossary.md) — piece, run, pen path, atlas, cell, facts…

The full map of the docs is [docs/README.md](docs/README.md); experiments are
indexed in [experiments/README.md](experiments/README.md).

## Commands

```
python3 -m venv .venv && .venv/bin/pip install -e ".[dev]"
.venv/bin/pip install fonttools                               # only for experiments/11_typeface (not in the dev extra)
.venv/bin/pytest -q                                           # ~3 min: builds the bundled 5-page document end to end
.venv/bin/inkscript native --azure-dir F/azure --scan-dir F/input --frontpage-dir F/frontpage \
    --out OUT --vector --verify                               # F = tests/fixtures/0582-004-009-012
.venv/bin/python experiments/09_pen_path/coverage.py OUT/<stem>_vector.pdf    # letter coverage of one PDF
```

`inkscript --help` lists the ten subcommands; [docs/pipeline.md](docs/pipeline.md) has a table of them and a file-by-file map of `src/`. The fixture is a real five-page
document, so nothing here needs data or keys (Gemini is only called by
`frontpage`, `numbers`, `second`; the fixture ships its page-1 reading).

## Rules that have each cost a day when broken

- **Chrome's engine is the judge, measured, never reasoned about.** `--verify`
  reads the PDF back with pdfium. `pypdfium2` is pinned to **5.12.1** (pdfium
  7947, reads right-to-left lines like Chrome); 5.13 bundles a build that does
  not, and misled a whole day of rules.
- **The faithful PDF draws every occurrence with its own ink.** No glyph is
  substituted, simplified or repaired there. Restoration is a separate output
  (see [docs/typeface.md](docs/typeface.md)).
- **Compare any selection method with the free baseline**: Chrome slices an
  uncut glyph into equal parts per character. A method that does not beat
  that is not worth its code (it happened: `docs/decisions.md`, D7).
- **Report what the user experiences, not what the code accepted.** Letter
  coverage = share of words in which every letter has its own box
  (`coverage.py`), not "plans accepted".
- **Do not edit `src/` while a set run is going.** Every document starts a
  fresh process and would import half-finished code.
- **Memory.** Before any multi-worker run, measure peak memory on a long
  document (`/usr/bin/time -v`), use at most 3–4 workers, and start
  `experiments/09_pen_path/watchdog.sh`. A cache in the letter cutter once
  took all 15 GB and froze the owner's machine.
- **Outputs stay in the repo**, under the experiment's `out/` (gitignored) —
  not on the Desktop. Give absolute paths. Propose deletions; don't do them.
- **A wrong glyph in a document's font means a systematic wrong cut in that
  document.** Building the typeface (`experiments/11_typeface`) is the best
  debugger of the letter cutter found so far.

## Working with the owner

Describe choices by what the result looks like, not by data structures. They
think in physical pictures (liquid flowing round letters; feeling strokes
written on your back) and those pictures have twice been the right design.
When they hand-mark a line of a PDF (word → letters selectable: yes/no), chase
every "no": one such map found four bugs that sample sheets had hidden. They
want to stop and think at turning points; don't fill the pause with
experiments.

## Keeping this repo self-documenting

After any change that alters behaviour or a number:

1. the rule and its measurement → `docs/pdf-writing-rules.md` (or `docs/letters.md`);
2. the headline numbers and date → `docs/STATUS.md`;
3. a new idea, or an idea's new status → `docs/ideas.md`;
4. a choice between alternatives → `docs/decisions.md`;
5. a new experiment → its own `README.md` (question, method, result, what it changed) and a line in `experiments/README.md`.

`tests/test_docs.py` fails if a document points at a file that no longer exists.
