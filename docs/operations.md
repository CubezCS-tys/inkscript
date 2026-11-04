# Operations: running things on this machine

> **2026-10-22: development runs on the owner's server now.** The sections below were written on the laptop and
> are kept as they were; where they differ from the server, this note wins.
> - **Paths.** The repo is `/home/appuser/inkscript`; `/home/yassine` is a symlink to `/home/appuser`, so stored
>   laptop paths resolve. Data: `~/data/marc`, `~/data/platform`, `~/data/platform_v2`, `~/data/desk`; the run
>   folders are under `experiments/*/out/`. The `~/Desktop/OCR_gem_json` sets in the table below are not on the
>   server. The full list is the stores table of [architecture.md](architecture.md).
> - **Services** (all on 127.0.0.1): 8001 / 8002 / 8003 Datasette (marc, platform v1, platform v2), 8004 the Desk's
>   web app, 8005 the Desk's API, 8899 the views, 5432 PostgreSQL 16 (Ubuntu's, under systemd; database `inkdesk`).
>   How to start, stop and check each: [runbooks.md](runbooks.md#services).
> - **Sharing the box with AI-Search.** The server is production for ai.mandumah.com. Agreed with the AI-Search
>   session on 2026-10-21: our ports are our own (8001–8005, 8899), every server binds 127.0.0.1, nothing heavy on
>   Qdrant, **at most 2 heavy workers during the day**, and processes are killed by port, never by name (AI-Search
>   runs its own `next-server`s).
> - **Memory.** The server has 62 GB (about 34 GB available on 2026-10-22), not the laptop's 15 GB. The rules still
>   hold: one heavy job at a time, `free -g` first, a guard on every long job. Gate 1's guard,
>   `experiments/52_journal_gate1/watchdog52.sh`, kills a matching process over 3 GB and stops them all under 10 GB
>   available.
> - **Running sets today** means experiment 43's pipeline (run43 → masters → judge → patches → platform), not the
>   PDF sets below: [runbooks.md](runbooks.md#running-a-journal-end-to-end).

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
flag if the copied text changed at all.

**Read that last flag carefully.** It compares each page's whole extracted
string, so it also fires when only the *line breaks* move — and cutting a word
differently can move one. On the 2026-09-22 rerun it fired on 73 of 227
documents, and every document sampled had an identical words-intact count
before and after: the changes were words that used to be split across a pdfium
line and now are not. Before treating it as a regression, measure words intact
against Azure's own words in both builds.

## Memory and time

| | Time | Peak memory |
|---|---|---|
| 5-page reference document | ~28 s | 0.85 GB |
| 81-page document | ~10 min (7.6 s a page) | 1.6 GB |
| 227 journals (4,440 pages), 3–4 workers | ~5 h | ~1–2.3 GB a worker |

The laptop has 15 GB and the owner's browser uses several (the server: 62 GB, shared with AI-Search; see the
note at the top). **Rules:** at most
3–4 workers; `nice`; check `free -g` first; measure a long document's peak
with `/usr/bin/time -v` before any multi-worker run; always start the
watchdog (it stops the run when less than 2.5 GB is available). A script that
opens many PDFs with pypdfium2 must close each one (`summary.py` once took
the machine's memory by leaving 227 open).

## Another machine

*(2026-10-22: the move to the server is done; `ops/pack_v2.sh` replaced `ops/pack_data.sh`.)*
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
