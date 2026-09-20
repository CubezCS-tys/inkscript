# Moving development to a server

Git holds the code, the docs, the tests and one bundled document — 7 MB. It
deliberately does **not** hold data, keys or outputs (`.gitignore`: `.env`,
`.venv/`, `output/`, `data/`, `*.zip`, `experiments/*/out/`, caches). So a
clone is enough to develop and run the tests, and not enough to run the sets.

## What has to travel, and how

| What | Size | How | Why not git |
|---|---|---|---|
| The repo | 7 MB | `git clone git@github.com:CubezCS-tys/inkscript.git` | — |
| Inputs: Azure JSON + PDFs, scans, Gemini page-1 readings, id lists (30-doc test set, 47, 227 journals, 451 sample) | 4.6 GB, 4,173 files | `ops/pack_data.sh user@server:~/inkscript-data` (rsync, resumable) | copyrighted scans; size |
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
bash ops/setup_nosudo.sh            # no root needed (ops/setup_server.sh is the apt version, if you have sudo)
export INKSCRIPT_DATA=~/inkscript-data
.venv/bin/pytest -q                 # ~3 min; proves the install
experiments/09_pen_path/run_set.sh $INKSCRIPT_DATA/s3_night/azure $INKSCRIPT_DATA/s3_night/frontpage - experiments/09_pen_path/out/journals227 4 &
experiments/09_pen_path/watchdog.sh &
```

**Sizing.** A worker peaks at 1–2.3 GB and uses one core; a page takes about
7.6 s. 8 GB RAM / 4 cores runs 3 workers (227 journals in ~5 h); 16 GB / 8
cores runs 6–7. Disk: 4.6 GB inputs + ~17 MB of output per document built
(PDF + vector PDF + shapes) — 40 GB is comfortable for the samples; the full
corpus (~100,000 documents) would need outputs pushed to a bucket as they are
made. Use `tmux` or `setsid nohup` so runs survive the SSH session; runs are
resumable either way ([operations.md](operations.md)).

## No root on the server

Nothing here needs a system package, so a plain user account is enough
(`ops/setup_nosudo.sh`):

- `pymupdf`, `opencv-python-headless` and `pypdfium2` ship their own
  libraries in the wheels; the only system library they use is `libz`, which
  every Linux already has (checked with `ldd`, 2026-09-20). No `libGL`, no
  `libglib`.
- `aws` is installed by pip into the venv, and `inkscript fetch` looks for it
  beside its own interpreter before falling back to `PATH`.
- A system Arabic font is optional: `config.arabic_font()` searches, and only
  some experiment scripts label pictures with it — nothing the PDFs need
  depends on it. Set `INKSCRIPT_ARABIC_FONT` to a `.ttf` of your own, or drop
  one in `~/.local/share/fonts/`, if you want those labels.
- LibreOffice is only for `experiments/11_typeface/specimen.py` (typesetting a
  font specimen). Skip it.
- If the server's Python is older than 3.10, or `python3 -m venv` fails
  because `ensurepip` is missing, the script prints the `uv` route: a single
  binary that installs into `~/.local/bin` and brings its own Python.
- `ops/pack_data.sh` needs `rsync` at both ends; without it on the server it
  falls back to one `tar` stream over ssh (which cannot resume).

**Paths.** `docs/operations.md` lists the laptop's paths; on the server the
same folders sit under `$INKSCRIPT_DATA`. `docs/storyboard/rebuild.sh` and
`ops/pack_data.sh` read that variable (default: the laptop's path).
LibreOffice is only needed for `experiments/11_typeface/specimen.py`; Chrome
is not needed at all (verification uses the pinned pdfium).
