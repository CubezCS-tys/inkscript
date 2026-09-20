# Operations: running things on this machine

## Where the data is (outside the repo; nothing here is committed)

*The paths below are the owner's machine. On any other machine: the bundled
document in `tests/fixtures/` needs nothing; for more, `inkscript fetch` needs
the `aws` command-line tool signed in with credentials that can read the
bucket (the owner's AWS profile — ask; they are not in the repo), and the
Gemini commands need `GEMINI_API_KEY` in `.env` (`.env.example`).*

| What | Where |
|---|---|
| Corpus | `s3://mandumah-source-docs/<id>/<id>.{pdf,json}` — Azure's searchable PDF and its JSON; `inkscript fetch --id-file ids.txt --out DIR` pulls them into the `--azure-dir` layout |
| 30-document test set | `~/Desktop/OCR_gem_json/output/bakeoff_full/{azure,input}`, page-1 readings in `…/output/frontpage_set` (needs `--scan-dir`) |
| 47 S3 documents | `~/Desktop/OCR_gem_json/output/s3_sample/` |
| 227 journals, one document each | `~/Desktop/OCR_gem_json/output/s3_night/{azure,frontpage}` (the PDF sits beside each JSON; no `--scan-dir`) |
| 451-document sample | `~/Desktop/OCR_gem_json/output/s3_big/` |
| Keys | `.env` (`GEMINI_API_KEY`); only `frontpage`, `numbers`, `second` call Gemini (~$0.005 a document for page 1) |

`--azure-dir` layout: `DIR/<stem>/<stem>.json` (+ `<stem>.pdf`).

## Building a set

```
experiments/09_pen_path/run_set.sh <azure_dir> <frontpage_dir> <scan_dir or -> <out_dir> <workers> &
experiments/09_pen_path/watchdog.sh &
```

- Resumable: rerun the same command after a crash or shutdown; finished
  documents are skipped (`--resume --only`). A suspended laptop simply resumes.
- Writes `<out>/w0N/` per worker and, at the end, `<out>/summary.txt`
  (`summary.py`: text checks, letter coverage on the pages we wrote, reasons
  pieces were doubted, the fifteen weakest documents).
- A very long document blocks its worker's queue; its tail can be handed to an
  extra worker by truncating `stems_w0N` and starting a helper on the cut-off
  part (bash reads the list lazily).

## Judging a change to the letter cutter

Build the same documents before and after, then
`experiments/09_pen_path/compare_boxes.py OLD_DIR NEW_DIR`: per document, the
share of characters whose box moved, letter coverage before → after, and a
flag if the copied text changed at all (it should not). This is the open task
for the fixes made after the 227-journal run ([roadmap.md](roadmap.md), item 5).

## Memory and time

| | Time | Peak memory |
|---|---|---|
| 5-page reference document | ~28 s | 0.85 GB |
| 81-page document | ~10 min (7.6 s a page) | 1.6 GB |
| 227 journals (4,440 pages), 3–4 workers | ~5 h | ~1–2.3 GB a worker |

The machine has 15 GB and the owner's browser uses several. **Rules:** at most
3–4 workers; `nice`; check `free -g` first; measure a long document's peak
with `/usr/bin/time -v` before any multi-worker run; always start the
watchdog (it stops the run when less than 2.5 GB is available). A script that
opens many PDFs with pypdfium2 must close each one (`summary.py` once took
the machine's memory by leaving 227 open).

## Another machine

`docs/moving-to-a-server.md`: what git does not hold (4.6 GB of inputs, the
keys), how to copy it (`ops/pack_data.sh`), setup with or without root
(`ops/setup_nosudo.sh`, `ops/setup_server.sh`), and how to size the machine.
Point `INKSCRIPT_DATA` at the copied data; `config.DATA_ROOT` reads it.

## Long jobs from an agent session

- Start them detached (`setsid nohup … &`); background tasks of the session
  itself are killed by the harness's memory guard and by session ends.
- `pkill -f PATTERN` kills your own shell when the pattern is in your command
  line: kill by PID, or write the pattern so it does not match itself
  (`grep "[b]in/inkscript"`).
- Never edit `src/` while a set is building (each document is a new process).
- Tests take ~3 minutes; the fixture build is the quick end-to-end check.

## Checking a build

`--verify` prints, per document: words intact in pdfium, lines in order,
in-column inversions, pages that lost their image, and a warning when pdfium
returns under 80% of the lines written (boxes overlapping a neighbouring
line make it join lines). Letter coverage is a separate script
([letters.md](letters.md)).
