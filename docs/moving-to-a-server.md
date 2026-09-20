# Moving development to a server

Git holds the code, the docs, the tests and one bundled document — 7 MB. It
deliberately does **not** hold data, keys or outputs (`.gitignore`: `.env`,
`.venv/`, `output/`, `data/`, `*.zip`, `experiments/*/out/`, caches). So a
clone is enough to develop and run the tests, and not enough to run the sets.

## What has to travel, and how

| What | Size | How | Why not git |
|---|---|---|---|
| The repo | 7 MB | `git clone git@github.com:CubezCS-tys/inkscript.git` | — |
| Inputs: Azure JSON + PDFs, scans, Gemini page-1 readings, id lists (30-doc test set, 47, 227 journals, 451 sample) | ~6 GB | `ops/pack_data.sh user@server:~/inkscript-data` (rsync, resumable) | copyrighted scans; size |
| Keys: `GEMINI_API_KEY` (`.env`), AWS credentials for `s3://mandumah-source-docs` (`~/.aws/`) | — | type them on the server (`aws configure`; edit `.env`) — never commit, never paste into chat | secrets |
| Built PDFs of the 227-journal runs (`experiments/09_pen_path/out/`) | 7.4 GB | optional: `rsync -avh experiments/09_pen_path/out/ user@server:~/inkscript/experiments/09_pen_path/out/` | reproducible (~5 h); needed only as the OLD side of `compare_boxes.py` |
| The agent's private notes (`~/.claude/projects/…/memory/`) | KB | not needed: `CLAUDE.md` and `docs/` are the source of truth | — |

The Azure inputs can also be re-fetched on the server (`inkscript fetch
--id-file ids.txt --out DIR`); the Gemini page-1 readings can be regenerated
(`inkscript frontpage`, about $0.005 a document) — copying them is cheaper.
The other ~160 GB under the laptop's `OCR_gem_json/output` are older
experiments and are not needed.

## On the server

```
git clone git@github.com:CubezCS-tys/inkscript.git && cd inkscript
bash ops/setup_server.sh            # python venv, dependencies, awscli, an Arabic font
export INKSCRIPT_DATA=~/inkscript-data
.venv/bin/pytest -q                 # ~3 min; proves the install
experiments/09_pen_path/run_set.sh $INKSCRIPT_DATA/s3_night/azure $INKSCRIPT_DATA/s3_night/frontpage - experiments/09_pen_path/out/journals227 4 &
experiments/09_pen_path/watchdog.sh &
```

**Sizing.** A worker peaks at 1–2.3 GB and uses one core; a page takes about
7.6 s. 8 GB RAM / 4 cores runs 3 workers (227 journals in ~5 h); 16 GB / 8
cores runs 6–7. Disk: 6 GB inputs + ~17 MB of output per document built
(PDF + vector PDF + shapes) — 40 GB is comfortable for the samples; the full
corpus (~100,000 documents) would need outputs pushed to a bucket as they are
made. Use `tmux` or `setsid nohup` so runs survive the SSH session; runs are
resumable either way ([operations.md](operations.md)).

**Paths.** `docs/operations.md` lists the laptop's paths; on the server the
same folders sit under `$INKSCRIPT_DATA`. `docs/storyboard/rebuild.sh` and
`ops/pack_data.sh` read that variable (default: the laptop's path).
LibreOffice is only needed for `experiments/11_typeface/specimen.py`; Chrome
is not needed at all (verification uses the pinned pdfium).
