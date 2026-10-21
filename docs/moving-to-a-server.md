# Moving development to the server

*Rewritten 2026-10-21. This covers moving **all** development to the owner's Ubuntu server, so that the server
agent sees everything the laptop has: experiments 40–47, the older experiments that today's code still reads, and
the databases. The owner does every server step. The agent on the laptop prepares and tests; it never connects to
the server.*

**The server:** ssh alias `prod`, user `appuser`, home `/home/appuser`, 950 GB free, rsync 3.2.7. The repo is cloned
from `git@github.com:CubezCS-tys/inkscript.git`.

## What git holds, and what it does not

Git holds the code, the docs, the tests and one bundled document. It does not hold `experiments/*/out/`, `~/data`,
`~/.cache/inkscript`, `.venv/`, `.env` or keys. Those travel with `ops/pack_v2.sh` (rsync), except the keys, which
the owner types on the server.

## What travels

Sizes are from the dry run of `ops/pack_v2.sh` on 2026-10-21. Hard-linked files are counted once (experiments 41
and 43 share 7,324 scan pictures as hard links, and `du` counts them in both). The script sends the folders in the
order below, most needed first, so the server agent can start before the older experiments arrive.

| # | What | To send | Rebuildable? |
|---|---|---|---|
| 1 | `~/.cache/inkscript`: `catalogue/catalogue.sqlite` (1.1 GB), `schemas/` (JATS 1.4, ALTO 4.4), `fonts/`, `epubcheck/`, `view/` | 1.3 GB | yes: `python -m inkscript.enrich.catalogue build` streams the bucket's `metadata/metadata_final.xml.gz` (7–18 min); the schemas are fetched on first use |
| 2 | `~/data/platform` (`platform.db` + its `-wal`, experiment 46) | 240 MB | yes: `load46.py --run <run>` for each run, then `link46.py` (seconds) |
| 3 | `~/data/platform_v2` (`platform_v2.db`, `ink.html`, logs, old builds; experiment 47) | 2.4 GB | yes: `build47.sh` order, 2 min 50 s (needs marc.db and platform.db). About 1.6 GB is old builds proposed for deletion (handoff section 8) |
| 4 | `experiments/43_rehearsal/out` + `experiments/41_azure_structure/out`, in one rsync so the hard links survive | 21.8 GB | **no**: Gemini answers ($73.62 of them), judge findings, patches, the proof pack. The masters and views rebuild from the answers, but only the answers are paid for |
| 5 | `experiments/{47,44,40,42}/*/out` | 1.2 GB | 44: a $0.015 S3 listing; 40: Gemini answers ($13.34), not rebuildable |
| 6 | the agent's notes `~/.claude/projects/-home-yassine-inkscript/memory/` → `~/.claude/projects/-home-appuser-inkscript/memory/` | 32 KB | no; [handoff.md](handoff.md) carries their content too |
| 7 | `~/data/marc`: `marc.db` (9.5 GB, experiment 45) and its small logs | 10.2 GB | yes: `experiments/45_marc_db/build45.py`, 22 min, from the uncompressed `metadata_final.xml` (gunzip the bucket's `.gz`). Rebuilding it on the server is faster than three hours of upload, if the owner prefers |
| 8 | the older experiments' `out/`, newest first: 39 (8.5 GB), 28 (7.1 GB), 33 (5.6 GB), 16 (2.2 GB), 37, 19, 29, 34, 35 and the rest down to 14 | 31.1 GB | mostly. Today's code reads 19 (`out/docs`), 28 (`out/azure`), 33 (`out/docs`), 34 (`out/extra`), 38 and 39 (`out/more`): these hold the scans and Azure JSON behind experiments 41/43's first samples |
| | **Total** | **67.7 GB** (GB = 10⁹ bytes) | |

**Never sent:** `.env`, `~/.aws`, `~/.ssh`, `metadata_final.xml` and its `.gz` (7.2 GB / 1.2 GB, in the bucket),
`~/data/marc/slice/` (a test slice), the experiment venvs (`39/out/venv`, `40/out/venv`, `33/out/env`,
`16/out/torchenv`: 4.6 GB, built for this laptop; rebuild them, handoff section 7) and
`39/out/gpu/result.tgz` (1.1 GB, unpacked beside it).

**Untracked files outside `out/`** are not copied. On 2026-10-21 that was only
the raw research notes of experiment 47 (`research_notes_raw.md`, proposed for deletion); check `git status --short` before packing.

**Symlinks.** `rsync -a` copies them as symlinks, and `-L` is never used, so nothing is duplicated. There are 3,389
relative links, which work as they are, and 225 absolute ones, which point at `/home/yassine/...`:
- the 13 run folders in `experiments/41_azure_structure/out/views` (the :8899 page);
- `29_catalogue/out/merged/*` (205);
- `41_azure_structure/out/native_in/*`.
The absolute links work after step 4. About 2,750 links are already broken on the laptop and are copied as they are:
`*/masters/*.pdf` in experiment 43 run folders, which have a `../` too many, and `28_scale/out/azure` → `../fresh`.
They break nothing that runs today.

## Keys: typed by the owner on the server, never through git or chat

- `GEMINI_API_KEY=...` in `~/inkscript/.env` (`chmod 600 .env`).
- The AWS read key for `s3://mandumah-source-docs`: `.venv/bin/aws configure`, which writes `~/.aws/`.
- Optional, only for GPU work: the Vast key (`vastai set api-key`) and a new ssh key (handoff section 6).

## Hard-coded `/home/yassine` paths

**In code (experiments 40–47): none that matter.** Their scripts find files from their own location
(`Path(__file__)`) and `Path.home()` (`~/data/marc`, `~/data/platform`, `~/data/platform_v2`,
`~/.cache/inkscript`). The `/home/yassine/...` in 40/41's docstrings are usage lines, and in 46/47 they are
comments. Older scripts that do hard-code it (`experiments/30_*`, `33_kraken/*.py`, `36_vlm_bakeoff`,
`39_ink_geometry/gpu/*.sh`) are not read by today's code.

**In data, which is what breaks:**
- the 225 absolute symlinks above;
- `experiments/43_rehearsal/sample43.json` and `sample43b.json` (tracked: 600 `pdf` / `azure` paths each);
- `platform.db`: `articles.jats_path` / `alto_path` / `pdf_path` (654 each), `judge_findings.file` (1,248),
  `patches.file` (235), `runs.masters_dir` (7);
- `platform_v2.db`: `storage_roots.base` (3) and `catalogue_exports.file` (1);
- about 250 small JSON / HTML / shell files in older `out/` folders (38's `pages.json`, 34's `pool.json`, 39's
  `plan.json`, 43's `build*.sh`, `~/data/platform_v2/build47.sh`).

`batch_state.json` holds no paths (Gemini job names and keys only). Datasette's `metadata46.json` and
`metadata47.json` hold none either; the paths are in its start commands, which are written with `$HOME` below.

**Fix A, with sudo (simplest; nothing is rewritten):**
```
sudo ln -s /home/appuser /home/yassine
```
Every stored path then resolves on the server.

**Fix B, without sudo:** after the copy, `python3 ops/relocate_home.py` (a dry run that counts what it would change),
then `python3 ops/relocate_home.py --apply`.
- It rewrites the prefix in the symlinks, the text files and the database columns above. A second run finds 0.
- Tested on a scratch copy on 2026-10-21: 218 symlinks, 2 text files and 3,456 database values changed;
  `integrity_check` ok; the second run found 0.
- Git will then show `sample43*.json` as modified. That is expected; don't commit them.
- It leaves other tracked files alone, including the READMEs and the GPU shell scripts of experiments 33, 36 and 39,
  which hard-code `/home/yassine/inkscript`. With fix B, fix those scripts when GPU work resumes. With fix A they
  already work.

## The owner's steps

1. **On the laptop: push today's commits.** The server clones from GitHub, and the last commits are only on the
   laptop. Run `git push`. You should see `main -> main`.
   - **On the server:** if there is no clone yet, `cd ~ && git clone git@github.com:CubezCS-tys/inkscript.git`.
     If there is one, `cd ~/inkscript && git pull`.
   - Then `git log --oneline -1` should show the same commit as the laptop.
2. **On the server: install, then test.**
   ```
   cd ~/inkscript && bash ops/setup_nosudo.sh
   .venv/bin/pip install datasette==0.65.5
   .venv/bin/pytest -q
   ```
   - The setup ends with the venv made and pytest installed.
   - The full test suite takes about 3 minutes and should end `passed`, with no `failed`.
   - The pin check should print `5.12.1 152.0.7947.0`:
     `.venv/bin/python -c "from pypdfium2.version import PYPDFIUM_INFO, PDFIUM_INFO; print(PYPDFIUM_INFO, PDFIUM_INFO)"`
3. **On the server: the keys.** You type these; they never go through chat or git.
   - Put `GEMINI_API_KEY=...` in `~/inkscript/.env`, then run `chmod 600 ~/inkscript/.env`.
   - Run `.venv/bin/aws configure` with the read-only key. Region: the bucket's.
   - Check with `.venv/bin/aws s3 ls s3://mandumah-source-docs/metadata/`. You should see `metadata_final.xml.gz`.
4. **On the server: the path fix.** Use one of the two.
   - **With sudo:** `sudo ln -s /home/appuser /home/yassine`. Then `ls /home/yassine/inkscript` lists the repo.
   - **Without sudo:** run step 4b after step 5 ends: `python3 ops/relocate_home.py`, then the same command with
     `--apply`. It ends `changed: … symlinks, … text files, … database values`. Run it again: it should say `0`
     everywhere.
5. **On the laptop: the copy.**
   - First the dry run:
     ```
     cd ~/inkscript && ops/pack_v2.sh --dry-run prod:/home/appuser
     ```
     It lists 35 folders, each with `to send: … in … files`. It ends with
     `still to send at the start of this run: 67.7GB` (a little more if outputs have grown).
   - Then the real copy:
     ```
     ops/pack_v2.sh prod:/home/appuser
     ```
     - Each folder prints a line, then a running progress line.
     - At about 1 MB/s upload this is likely an overnight job or longer: about 19 hours before compression. Nothing
       was measured over the network, so this is only an estimate.
     - It is safe to stop with Ctrl-C, and safe if the network drops. Run the same command again and it carries
       on where it stopped.
     - It ends with `done`. Run it once more: every line should say `already there, skipped`.
     - To send the most needed part first, add `--only 'cache|platform|43_|47_|memory'`.
   - Keep the laptop awake for the copy. Don't run a database build on the laptop while it copies.
6. **On the server: start the four browse pages.**
   ```
   cd ~/inkscript/experiments/41_azure_structure/out/views && (setsid nohup python3 -m http.server 8899 --bind 127.0.0.1 >/dev/null 2>&1 &)
   cd ~/inkscript && (setsid nohup .venv/bin/datasette serve --immutable $HOME/data/marc/marc.db -h 127.0.0.1 -p 8001 >> $HOME/data/marc/datasette.log 2>&1 &)
   cd ~/inkscript && (setsid nohup .venv/bin/datasette serve $HOME/data/platform/platform.db -h 127.0.0.1 -p 8002 --metadata experiments/46_platform_db/metadata46.json --static diagram:$HOME/data/platform/public/ --setting sql_time_limit_ms 10000 --setting max_returned_rows 2000 >> $HOME/data/platform/datasette.log 2>&1 &)
   cd ~/inkscript && (setsid nohup .venv/bin/datasette serve $HOME/data/platform_v2/platform_v2.db -h 127.0.0.1 -p 8003 --metadata experiments/47_platform_v2/metadata47.json --plugins-dir experiments/47_platform_v2/plugins --static diagram:$HOME/data/platform_v2/ --static pages:$HOME/inkscript/experiments/43_rehearsal/out/pages --setting sql_time_limit_ms 15000 --setting max_returned_rows 2000 >> $HOME/data/platform_v2/datasette.log 2>&1 &)
   sleep 15; for u in 8899/v33_300b_fix3/index.html 8899/proof/proof.html 8001/marc 8002/platform 8003/platform_v2; do curl -s -o /dev/null -w "%{http_code} $u\n" http://127.0.0.1:$u; done
   ```
   - You should see five lines of `200`.
   - The laptop runs the same four with `/home/yassine` paths; :8002 there listens on `0.0.0.0`. On the server
     every page listens on `127.0.0.1` only.
   - To look at the pages from the laptop, open a tunnel to other local ports, because the laptop's own pages hold
     8899 and the rest:
     ```
     ssh -N -L 9899:127.0.0.1:8899 -L 9001:127.0.0.1:8001 -L 9002:127.0.0.1:8002 -L 9003:127.0.0.1:8003 prod
     ```
     Then open http://127.0.0.1:9899/v33_300b_fix3/index.html. The pages look the same as on the laptop.
   - After a server reboot, run this step again.
7. **On the server: start Claude Code inside tmux.** Run `tmux new -s inkscript`, then `cd ~/inkscript && claude`.
   Later, `tmux attach -t inkscript` gets back to it. Give the agent the checklist below as its first task.

### The server agent's first hour

1. **Read, in this order:**
   1. `CLAUDE.md`.
   2. [handoff.md](handoff.md) section 00, then section 1 (how the owner works).
   3. [STATUS.md](STATUS.md), the top section.
   4. `~/.claude/projects/-home-appuser-inkscript/memory/MEMORY.md`, if it was copied.
   5. `experiments/43_rehearsal/out/overnight_plan.md`.
   6. The section headings of `experiments/43_rehearsal/README.md`, then "The exam" and "Fix round 3".
   7. `experiments/43_rehearsal/out/proof/proof.md`.
   8. `experiments/47_platform_v2/README.md`, its `DESIGN.md` and `VERIFY.md`.
2. **Check the move.** Don't fix anything yet, just report.
   - `git status --short`: clean, apart from `sample43*.json` if fix B was used.
   - `.venv/bin/pytest -q tests/test_docs.py` passes.
   - The pypdfium2 pin prints `5.12.1 152.0.7947.0`.
   - `ls ~/data/marc/marc.db ~/data/platform_v2/platform_v2.db ~/.cache/inkscript/catalogue/catalogue.sqlite`.
   - `python3 ops/relocate_home.py` says 0 to change (or `/home/yassine` is the symlink).
   - The five URLs of step 6 return 200.
   - `readlink experiments/41_azure_structure/out/views/v33_300b_fix3` points at a folder that exists.
3. **Money.** Sum `experiments/43_rehearsal/out/gemini_spend.jsonl`: it should be $73.62 or more. About $4 of
   credit is left, so **no paid call until the owner tops up and sets a cap**.
4. **Look before relaying.** Open the fix 3 views and the proof page, and look at two pages beside their scans
   before you say anything about quality.
5. **Then wait for the owner.** The open choices are in handoff section 00, "Waiting for the owner". Don't start the
   ~3,000-article step on your own.

## Older notes that still hold

**No root needed.** `ops/setup_nosudo.sh` needs no system package:
- The wheels (pymupdf, opencv-python-headless, pypdfium2) carry their own libraries. Apart from that they need only
  `libz`.
- `aws` is pip-installed into the venv.
- If Python ≥ 3.10 or `ensurepip` is missing, the script prints the `uv` route.
- LibreOffice and a system Arabic font are optional.
- `ops/setup_server.sh` is the apt version, for when sudo is available.

**Sizing for the PDF sets** (experiment 9): a worker peaks at 1–2.3 GB and uses one core, and a page takes about
7.6 s. Use at most 3–4 workers, and start `experiments/09_pen_path/watchdog.sh` first. Use `tmux` or `setsid nohup`
so runs survive the ssh session.

**`ops/pack_data.sh`** packs the 2026-09 inputs from `~/Desktop/OCR_gem_json`, which no longer exists on the
laptop. Today's inputs are inside the experiments' `out/` folders and on S3 (`inkscript fetch --id-file ids.txt
--out DIR`), so `pack_v2.sh` replaces it.
