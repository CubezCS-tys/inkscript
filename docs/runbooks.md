# Runbooks

*Written 2026-10-22. Each procedure is taken from an experiment's README, its progress log or the code itself, and
says which. A command marked **(not run here)** was put together from those sources and was not run while writing
this page; read the source before you rely on it. How the parts fit together is
[architecture.md](architecture.md).*

Paths: the repo is `~/inkscript` = `/home/appuser/inkscript`. `/home/yassine` is a symlink to `/home/appuser`, so
paths written on the laptop work too. `PY=~/inkscript/.venv/bin/python` below.

## Before anything heavy

This box is production for AI-Search. Agreed with the AI-Search session on 2026-10-21, and kept by every run since:

- **At most 2 heavy workers during the day**, and one heavy job of ours at a time (a run, a masters build, a load,
  a link pass). Check `free -g` first: on 2026-10-22 the box had 62 GB, about 34 GB available.
- **Nothing heavy on Qdrant** (ports 6333/6334); our code does not touch it.
- **Every server of ours on 127.0.0.1**, on our own ports (8001–8005, 8899). Kill by **port**, never by name.
- **A memory guard for every long job.** Gate 1 used `experiments/52_journal_gate1/watchdog52.sh`: it kills any
  matching Python process over 3 GB, and all of them when available memory falls under 10 GB. Its pattern names
  gate 1 (`--set d`, `j0130`, `gate1`), so a new set needs its own copy with the new names.
  (`experiments/09_pen_path/watchdog.sh` is the laptop's guard for the PDF sets, with a 2.5 GB floor.)
- **No paid call without the owner's cap** ([Money](#money)).
- **Don't edit code another agent's run is importing.** The letter-fix rebuild used a snapshot of the code
  (`experiments/43_rehearsal/out/lettersfix/code/`) for this reason.
- Long jobs: start them detached with `setsid nohup … &` and a log file; wait on a PID (`kill -0 $PID`), not on a
  `pgrep -f` pattern, which can match the waiting shell itself ([operations.md](operations.md)).

## Viewing everything

From the owner's machine, one tunnel carries every page:

```
ssh -N -L 9004:127.0.0.1:8004 prod
```

Then open http://localhost:9004. On Windows / WSL use `localhost`, not `127.0.0.1`.

| Page | Address through the tunnel |
|---|---|
| The Desk (sign in with the token from `~/data/desk/owner_token.txt`, admin) | http://localhost:9004/ |
| Mockup, mind map, inventory, gate 1 | http://localhost:9004/mockup/, `/mindmap/`, `/inventory/`, `/gate1/` |
| Any Layout view (the :8899 server, proxied) | http://localhost:9004/views/j0130_final/index.html, `/views/v33_300b_fix3/index.html`, … |
| Datasette | not proxied: add `-L 9001:127.0.0.1:8001 -L 9002:127.0.0.1:8002 -L 9003:127.0.0.1:8003` to the tunnel |

## Services

### Check what is running

```
ss -ltnp | grep -E ':(8001|8002|8003|8004|8005|8899|5432) '
for u in 8899/v33_300b_fix3/index.html 8001/marc 8002/platform 8003/platform_v2 8004/signin; do
  curl -s -o /dev/null -w "%{http_code} $u\n" http://127.0.0.1:$u; done
```

The first line is from `restart.sh`'s use of `ss`; the loop is step 6 of
[moving-to-a-server.md](moving-to-a-server.md) with `/signin` added for the Desk. Each should say `200`.

### Stop one service, by its port

This is how `experiments/49_correction_desk/web/restart.sh` finds its process. Replace 8003 with the port:

```
pid=$(ss -ltnpH 'sport = :8003' | grep -o 'pid=[0-9]*' | head -1 | cut -d= -f2); echo "$pid"
kill "$pid"
```

Look at the PID's command line (`tr '\0' ' ' < /proc/$pid/cmdline`) before you kill it. **(not run here)** as two
lines; the same `ss` call runs inside `restart.sh` every time it is used.

### Start each service

All from the source docs; each line detaches and logs.

**Views, 8899** (step 6 of [moving-to-a-server.md](moving-to-a-server.md)):
```
cd ~/inkscript/experiments/41_azure_structure/out/views && (setsid nohup python3 -m http.server 8899 --bind 127.0.0.1 >/dev/null 2>&1 &)
```

#### Datasette (8001, 8002, 8003)

Step 6 of [moving-to-a-server.md](moving-to-a-server.md); the running processes on 2026-10-22 had exactly these
arguments:
```
cd ~/inkscript && (setsid nohup .venv/bin/datasette serve --immutable $HOME/data/marc/marc.db -h 127.0.0.1 -p 8001 >> $HOME/data/marc/datasette.log 2>&1 &)
cd ~/inkscript && (setsid nohup .venv/bin/datasette serve $HOME/data/platform/platform.db -h 127.0.0.1 -p 8002 --metadata experiments/46_platform_db/metadata46.json --static diagram:$HOME/data/platform/public/ --setting sql_time_limit_ms 10000 --setting max_returned_rows 2000 >> $HOME/data/platform/datasette.log 2>&1 &)
cd ~/inkscript && (setsid nohup .venv/bin/datasette serve $HOME/data/platform_v2/platform_v2.db -h 127.0.0.1 -p 8003 --metadata experiments/47_platform_v2/metadata47.json --plugins-dir experiments/47_platform_v2/plugins --static diagram:$HOME/data/platform_v2/ --static pages:$HOME/inkscript/experiments/43_rehearsal/out/pages --setting sql_time_limit_ms 15000 --setting max_returned_rows 2000 >> $HOME/data/platform_v2/datasette.log 2>&1 &)
```
:8002 and :8003 are not `--immutable`, so a load shows at once. After `meta47.py` rewrites `metadata47.json`,
restart :8003 to pick up the new canned queries.

**The Desk API, 8005** ([experiment 49](../experiments/49_correction_desk/README.md), "How to run it"):
```
cd ~/inkscript/experiments/49_correction_desk
setsid nohup .venv/bin/python -m desk.cli serve >> /home/appuser/data/desk/api.log 2>&1 &
curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8005/desk/api/docs
```
The API uses experiment 49's own `.venv` (FastAPI, uvicorn, psycopg, Pillow), not the repo's. Stop the old one by
its port first.

**The Desk web app, 8004**:
```
~/inkscript/experiments/49_correction_desk/web/restart.sh
```
It kills only the process listening on 8004, starts `next start -p 8004 -H 127.0.0.1` (log
`~/data/desk/web.log`), waits for `/signin` and prints the listener. It serves the last build: after a code or
`public/` change, rebuild first ([The Desk](#the-desk)).

**PostgreSQL, 5432** is Ubuntu's PostgreSQL 16 under systemd (`systemctl is-active postgresql` → `active`,
enabled at boot). It needs nothing from us.

**After a reboot** start, in this order: 8899, the three Datasettes, the API, the web app; then run the check
above. The Desk API and web app have no start-at-boot either.

## Running a journal end to end

This is gate 1 ([experiment 52](../experiments/52_journal_gate1/README.md), journal 0130), whose exact commands are
in `experiments/52_journal_gate1/progress.md`; it followed the exam's sequence (experiment 43, "The exam: second
300"). The steps below name gate 1's set `d`, run `j0130` and files; a new journal needs its own names everywhere.

**0. Price it and get the cap.** Sum the spend log ([Money](#money)). The owner's cap is *on top of* the log: gate
1's was $32 on a log of $75.902, so the absolute cap was $107.90. Recompute before each paid launch.

**1. Catalogue query and bucket check.** `sample52.py ids` asks `marc.db` (read only) for the journal's records
(`journal_code`, `type = 'بحوث ومقالات'`, years) and keeps the stems that are in the main bucket, by experiment 44's
listing `experiments/44_bucket_map/out/ids_main.txt` (a listing made on 2026-10-19, not a live check):
```
$PY experiments/52_journal_gate1/sample52.py ids                  # -> out/ids_all.txt
```
For a new journal, copy the script and change its SQL. Years that are only in `legacy/` have no scan: they go by
the Word route ([experiment 53](../experiments/53_word_route/README.md)); first check that each Word file is the
right article (its first page = the catalogue's first page).

**2. Fetch** the PDF and Azure JSON of each stem (gate 1: 195 stems, 881 MB, about 30 min):
```
.venv/bin/inkscript fetch --id-file experiments/52_journal_gate1/out/ids_all.txt --out experiments/52_journal_gate1/out/fetch
```
**(not run here)**: the log says only "fetch launched into out/fetch/"; the options are `inkscript fetch`'s.

**3. Build the set file.** Each PDF must open and have Azure's page count (`fetched43.problems`); the others are
listed under `left_out`. `--from YEAR` cuts the years:
```
$PY experiments/52_journal_gate1/sample52.py build --from 2010     # -> out/sample52.json
```

**4. Define the set in experiment 43.** The scripts know sets `a`–`d` by letter. Gate 1 added set `d` (one line or
so each, no change to other runs) in `run43`, `pictures43`, `flags43`, `views43`, `judge43` (its `RUNS`),
`patches43`, `summary43`, `retry43`, `rechunk43` and `lettersfix43`, and symlinked `experiments/43_rehearsal/out/j0130`
and `j0130_final` to the experiment's own `out/`. This is a code change in experiment 43: agree it with whoever else is
working there.

**5. Dry run and price** (no calls):
```
cd ~/inkscript/experiments/43_rehearsal
$PY run43.py --set d --prompt v3.5b --thinking low --dry-run
```
Gate 1's plan (`experiments/52_journal_gate1/out/PLAN.md`) takes the dry run × 1.06 for v3.5b (its `enrich` part
adds output), adds the judge (about 16% of pages flagged plus 50 random pages, at $0.0072 a judged page) and up to 15
page retries at $0.036. When the total is over the cap, cut the years, not the safeguards.

**6. Start the guard**, check memory, then launch the run:
```
free -g
setsid nohup experiments/52_journal_gate1/watchdog52.sh >/dev/null 2>&1 &          # (not run here in this form)
cd ~/inkscript/experiments/43_rehearsal
$PY run43.py --set d --prompt v3.5b --thinking low --run j0130 --cap 103.30 --max-enqueued 2500000
```
- `--cap` is an absolute total of the spend log (gate 1: log + $27.40, keeping room for the judge). run43 cuts any
  round whose worst case could cross it.
- `--max-enqueued 2500000` cuts each Batch job at 2.5M input tokens. Without it, the first launch reached 3.09 GB
  while building job 1 and the watchdog killed it (nothing sent). With it, and run43 dropping each article's Azure
  JSON once its request is built, the peak was 2.0 GB.
- **Resume = the same command.** Answers saved in `out/j0130/raw/` are skipped; `batch_state.json` holds the job of
  each round, so an unfinished job is polled, not sent again.
- Gate 1 wrote the run's log to `out/j0130/run.log`. 126 articles took 10 Batch jobs, about 1 h 40 min.

**7. Rechunk** any chunk that ran out of output (MAX_TOKENS), then ask for the smaller chunks with the same cap:
```
$PY rechunk43.py --run j0130
$PY run43.py --set d --prompt v3.5b --thinking low --run j0130 --cap 103.30 --stems 0130-020-080-001 0130-025-099-004
```
**(not run here)** in exactly this form: the log names the retry run as "--stems, cap 103.30". A chunk that ended
normally but gave broken JSON is not a MAX_TOKENS failure, so `rechunk43` skips it; the exam split one by hand with
`rechunk43.split`.

**8. Build the masters** with today's rules and the letter fix, and validate them:
```
experiments/52_journal_gate1/build52.sh
```
It runs `lettersfix43.py plain --run j0130 --set d --dst out/j0130` and `lettersfix43.py validate`, with
`PYTHONPATH` pointing at the `latex2mathml` copy in `experiments/43_rehearsal/out/lettersfix/pylib` (the repo's
`.venv` had none that morning; it was then installed there with the owner's OK and listed in `pyproject.toml`,
so `PYTHONPATH` is no longer needed). Every master must pass JATS DTD + ALTO XSD; gate 1: 126/126, 376 MB peak.

**9. Flags, views, summary** (from `experiments/43_rehearsal/`; the forms `final52.sh` uses):
```
$PY flags43.py --run j0130
$PY views43.py --masters out/j0130/masters --out out/j0130/views --stems $(ls out/j0130/masters/*.jats.xml | xargs -n1 basename | sed 's/.jats.xml//')
$PY summary43.py --run j0130
```
**(not run here)** for the plain run: the log records only "views 126; flags; summary".

**10. The judge.** Pick the pages (every flagged page plus 50 random unflagged ones), take the screenshots, then one
Batch job under its own cap:
```
$PY ~/inkscript/experiments/52_journal_gate1/judge_pages52.py        # -> out/j0130/pages_judge.txt
export JUDGE43_PW=~/inkscript/experiments/52_journal_gate1/out/pwvenv/bin/python   # Playwright for the screenshots
$PY judge43.py shots --run j0130 --pagelist out/j0130/pages_judge.txt
JUDGE43_CAP=107.30 $PY judge43.py batch --run j0130 --pagelist out/j0130/pages_judge.txt --model gemini-4-argon --prompt v2
$PY judge43.py decide --run j0130 --model gemini-4-argon --prompt v2 --out out/j0130_final
$PY ~/inkscript/experiments/52_journal_gate1/judge_summary52.py      # every finding with its route
```
**(not run here)**: put together from `judge43.py`'s usage lines and gate 1's log (Argon, judge prompt v2,
`JUDGE43_CAP=107.30`, decisions into `out/j0130_final/patches`). `JUDGE43_CAP` is the log total the judge may not
cross; keep about $0.6 under the run's absolute cap for page retries. The two keys (confidence ≥ 0.85 and the code
check) are frozen; don't loosen them for a run.

**11. Page retries** (paid, Argon Standard, about $0.036–0.05 a page): `retries52.py` sends at most 15 retry pages
drawn at random; each becomes a patch only if the code check passes. Send them only while the log stays under the
cap.

**12. Patches and the final run:**
```
experiments/52_journal_gate1/final52.sh
```
It copies the plain masters into `out/j0130_final`, applies the patches (`patches43.py build --run j0130_final
--src out/j0130/rules --out out/j0130_final`), validates, flags (`--patches`), views and summarises. Then the index
pages and the link for :8899:
```
python3 experiments/52_journal_gate1/make_index52.py experiments/52_journal_gate1/out/j0130_final
```
and a symlink `experiments/41_azure_structure/out/views/j0130_final` → the run's `views/` folder (the existing one
points at `experiments/52_journal_gate1/out/j0130_final/views`). Look at ten random pages beside the scan before
reporting quality.

**13. Load into the platform, link, check**: next section. Gate 1 first loaded into a copy (`gate1.db`), measured
there, and was loaded into the main `platform_v2.db` later the same day, after a backup
(`platform_v2.before_journal0130_2026-10-22.db`).

**14. Measure.** Gate 1's measures read a platform database read only, the same code on the journal and on the
random 600:
```
$PY experiments/52_journal_gate1/measure52.py --db DB --runs RUN [RUN ...] --label NAME
$PY experiments/52_journal_gate1/catalogue52.py extract|match|decide|results --db ~/data/platform_v2/gate1.db --run j0130_final
$PY experiments/52_journal_gate1/detect52.py --db DB --runs RUN [RUN ...] --label NAME     # counts Desk tasks; writes none
$PY experiments/52_journal_gate1/fields52.py DIR/masters
$PY experiments/52_journal_gate1/gate1page52.py                                           # the owner's page
```

## Loading a run into the platform

From [experiment 47](../experiments/47_platform_v2/README.md) ("How it is built") and the reload log
`experiments/43_rehearsal/out/lettersfix/reload_progress.md`.

1. **Check.** `free -g`; nothing else writing `platform_v2.db` (only the :8003 Datasette, which reads it). One load
   at a time: load47 peaks at about 150 MB, link47 at about 141 MB and 1–2 minutes.
2. **Back up first**, with SQLite's backup API (the db has a live WAL, so a file copy could miss pages), to a dated
   name beside it:
   ```
   $PY -c "import sqlite3; s=sqlite3.connect('file:$HOME/data/platform_v2/platform_v2.db?mode=ro', uri=True); d=sqlite3.connect('$HOME/data/platform_v2/platform_v2.before_WHAT_$(date +%F).db'); s.backup(d); print(d.execute('PRAGMA integrity_check').fetchone()); d.close()"
   ```
   **(not run here)**: the call is the one `experiments/49_correction_desk/desk/release.py` makes (`backup`, in one
   step: about 3 s for 570 MB); the reload logged "backup (sqlite backup API, integrity ok)".
3. **Load** each run, the plain one before its final:
   ```
   P=experiments/47_platform_v2
   $PY $P/load47.py --run j0130 --kind base
   $PY $P/load47.py --run j0130_final --kind final --note "what this run is, and the date"
   ```
   - `--db` defaults to `~/data/platform_v2/platform_v2.db`; gate 1 passed `--db ~/data/platform_v2/gate1.db`.
   - **Kinds**: sample | base | judged | final | exam. Without `--kind` it comes from the name (`300b` → exam,
     `_final` → final, `_judged` → judged, `v2_` → sample, else base). An exam run can never take the shown
     version from a final one.
   - **The shown version** of a document: a person's choice, then a complete version, then its purpose (final
     first), then the newest stamp. Loading a newer final run makes it shown; the old runs stay as history.
   - Idempotent: an unchanged version is skipped (the sha covers JATS, ALTO, D33 and patch sidecars and the stamp).
   - A `<run>_lettersfix` folder with no `flags.json` or `raw/` reads its source run's (`load47.source_run`).
4. **Link and check:**
   ```
   $PY $P/link47.py              # gate 1 on its copy: --db ~/data/platform_v2/gate1.db --work experiments/52_journal_gate1/out/link_work
   $PY $P/checks47.py            # orphans must be 0; writes experiments/47_platform_v2/out/checks47.json
   ```
   `checks47`'s reconciliation with platform v1 prints "MUST BE EQUAL — not explained" on most rows now, because v1
   was not loaded with the newer runs; read the orphan count, not those rows.
5. **Stable ids.** After a change to the loader or the linker:
   ```
   .venv/bin/pytest -q experiments/47_platform_v2/test_ids47.py      # small form, 8 documents, about 1 min
   $PY experiments/47_platform_v2/test_ids47.py --full               # three build orders, about 8 min, 0.6 GB
   ```
   Also compare the active cited-work ids before and after a reload: on 2026-10-22 the letter-fix reload gave 21
   cross-article cards new ids (cause and fix in the reload log).
6. **Then the Desk:** build a release and run the detectors ([below](#the-desk)), or the Desk keeps reading the
   previous release.
7. **Metadata for Datasette**, after a schema change: `python3 experiments/47_platform_v2/meta47.py`, then restart
   :8003.

`build47.sh` in `~/data/platform_v2/` is the full build from scratch of the first 354 documents (2 min 50 s); it
does not include the exam, gate 1 or the letter-fix runs, which were loaded on top.

## The Desk

From [experiment 49](../experiments/49_correction_desk/README.md). Commands from
`~/inkscript/experiments/49_correction_desk` with its own `.venv`.

**Build a release, then run the detectors.** The detectors read the newest release, so they run after it:
```
.venv/bin/python -m desk.cli release [--reading PATH] [--note "why"]     # -> ~/data/desk/releases/R<time>.db
.venv/bin/python -m desk.cli detect
```
Or an admin presses "Build a release" on the Releases page: one build at a time (a second gets 409); it summarises
the copies and runs the detectors itself. On 2026-10-21 a release took 6.5 s from the command line (peak 60 MB), and
11.3 s from the screens with the summaries and the detectors.
At most 2 release copies stay on disk (`--keep`). After any platform reload, build a release.

**Actors and tokens.**
```
.venv/bin/python -m desk.cli actor add person:amina --name Amina --role corrector --skills ar,fr   # prints a token
.venv/bin/python -m desk.cli token person:amina                                                   # a new token
```
A token is printed once; only its sha256 is stored. Keep tokens in mode-600 files under `~/data/desk/`
(`owner_token.txt`, `demo_tokens.txt`); never paste one into chat, a doc or a commit. The owner's token was shown in
chat once on 2026-10-21: reissue it before the Desk goes beyond this box. Real accounts (invitations, password + TOTP,
HTTPS on a separate server) are P4, not built.

**Tests.**
```
.venv/bin/pytest -q tests/          # 19 tests, about 130 s, in throwaway schemas test_<pid>_* inside inkdesk
```
`experiments/49_correction_desk/tests/p2_walkthrough.py` drives the live Desk with Playwright and makes (then
reverts) real decisions: run it only with the owner's go.

**Rebuild the web app** (after a change under `web/`, including `public/`):
```
cd ~/inkscript/experiments/49_correction_desk/web
NODE_OPTIONS=--max-old-space-size=1536 npx next build >> ~/data/desk/next_build.log 2>&1 && ./restart.sh
```
`next build` took 34 s and 392 MB with that cap. **(not run here)** in this exact form: the README gives the memory
cap and `restart.sh` says "after `npx next build`".

**Add a static page** (as gate 1 did):
1. Put the page at `web/public/<name>/index.html` (one file; inline CSS; no CDN).
2. Add `<name>` to **both** `beforeFiles` rewrites in `web/next.config.js` (the `(mockup|mindmap|inventory|gate1|gate2)`
   lists), so `/<name>` and `/<name>/` serve it.
3. Rebuild and restart as above. A new file is not served until the rebuild (experiment 51 got a 404 before it).
4. Check `curl -s -o /dev/null -w "%{http_code}\n" http://127.0.0.1:8004/<name>/` → 200.

Pages in `public/` hold Mandumah's titles: keep them out of commits.

## Prompt changes

How v3.5 and v3.5b were checked (experiment 43, "Prompt v3.5"; `experiments/43_rehearsal/out/v35_check/PLAN_v35.md`).

1. **Write the new prompt as a change list** on the old one in `prompt43.py`; never edit the old version. Check that
   the old prompt's text hash is unchanged (v3.3: `d6b2156150`, the frozen exam stamp) and that its prompts as sent
   are byte-identical before and after, chunk by chunk.
2. **Prove old answers build the same.** Two code trees (git HEAD and the change) built from saved v3.3 answers:
   every master byte-identical (version stamp stripped). v3.5's proof: 40 articles, 418 files.
3. **Price** without calls: `run43.py --dry-run` and `check35.py price` (from the same chunks' real v3.3 tokens).
4. **With the owner's cap**, ask for the check's 12 articles (gold 2382 and 0747, and ten chosen for the new
   fields and for v3.4's known losses), sets b and a run one after the other under the same cap:
   ```
   $PY run43.py --set b --prompt v3.5 --run v35_check --cap 76.40 --stems 0069-000-026-005 1608-023-001-025 \
       0500-015-002-013 0412-005-001-005 0042-004-009-012 0295-016-002-014 0881-031-355-002 1875-005-020-001 \
       1010-006-011-015 0787-011-001-003
   $PY run43.py --set a --prompt v3.5 --run v35_check --cap 76.40 --stems 2382-005-003-001 0747-001-003-001
   $PY check35.py build
   $PY check35.py score               # score.md, score.json, fields.md
   $PY flags43.py --run v35_check
   ```
5. **The bar** (from the plan): no structural change beyond **v3.3's own run-to-run noise** (v3.3 against its
   replicate: share of lines with the same block type, reading order, pages changed); on v3.4's loss pages
   (1010-006 pp 2 and 4, the advert; 0787 p9, the paragraphs) the old structure exactly; on the gold pages the
   differences within G0's range (0747: 44 / 42 / 35; 2382: 17 / 19 / 29). The new fields are read by a person
   (`fields.md`) on the scan.
6. **What happened.** v3.5 moved the structure beyond the noise on some pages (gold 2382 31 differences against 17),
   so **v3.5b** = v3.5 without v3.4's two content lines was checked the same way in
   `experiments/43_rehearsal/out/v35b_check/` (run log: 10 articles, cap $76.21; `check35.py … --dir
   out/v35b_check`). The owner chose v3.5b for gate 1. The reason is written at v3.5b in `prompt43.py`.

## Money

- **The log.** Every Gemini call of experiments 43 and 52 is a row of
  `experiments/43_rehearsal/out/gemini_spend.jsonl` (`usd` per row). The total:
  ```
  python3 -c "import json; print(round(sum(json.loads(l).get('usd') or 0 for l in open('experiments/43_rehearsal/out/gemini_spend.jsonl') if l.strip()), 3))"
  ```
  On 2026-10-22, evening: **$100.146** (3,070 rows). Experiments 40 and 41 have their own older logs.
- **The credit left.** The owner topped up **£101.28 incl. VAT on 2026-10-18**; the log counts from then. Budget =
  log dollars → pounds (at 1.33 $/£, the rate the docs use) + 20% VAT; Google's balance agreed with this within 1%
  on 2026-10-20. Today: $100.146 / 1.33 × 1.2 ≈ £90.4 used, so **about £11 left**. The console is the truth: ask the
  owner to look before a large run, and compare the log with the balance after each run (a running job is charged
  before it is logged).
- **The cap.** Never a paid call without the owner's cap. Write it as an absolute total of the log (log now + the
  owner's cap) and pass it everywhere: `run43.py --cap`, `JUDGE43_CAP` for the judge, and a check of the log before
  each retry. Recompute it before each launch: other runs share the log.
- **Prices.** Gemini's prices double on 2026-12-01 (Argon Batch $1/$5 → $2/$10 per M tokens in/out).

## Backups and restore

**Where.** All in `~/data/platform_v2/`, made with SQLite's backup API before each reload or fix round:

| File | The db before |
|---|---|
| `platform_v2.db.bak-20261020-fix0`, `…-20261020-fix1`, `…-20261021-fix2` | experiment 47's fix rounds 1, 2 and the follow-up |
| `platform_v2.before_exam_2026-10-21.db` | the exam's 300 were loaded |
| `platform_v2.before_journal0130_2026-10-22.db` | gate 1's journal was loaded |
| `platform_v2.before_lettersfix_2026-10-22.db` | the 600 were reloaded with the letter fix |
| `platform_v2.db.fix1-draft`, `.fix1-draft2`, `.fix2-draft` | intermediate builds, proposed for deletion |

The Desk's decisions are in PostgreSQL, not in these files, and survive any platform restore. Release copies keep
only the last two. No backup of `inkdesk` is set up yet (DESIGN §11 asks for nightly ones on the separate server).

**Roll back the platform** **(not run here)**; the reload log's plan for undoing a bad load was "redo the load on a
draft from the backup, then copy the draft over the live db (backup API) and release again":
1. Stop every writer (no load or link running). The :8003 Datasette only reads.
2. Keep the current db: back it up under a dated name, as in [Loading a run](#loading-a-run-into-the-platform) step 2.
3. Copy the backup over the live db with the backup API, so the WAL is handled:
   ```
   $PY -c "import sqlite3; s=sqlite3.connect('file:$HOME/data/platform_v2/platform_v2.before_WHAT_DATE.db?mode=ro', uri=True); d=sqlite3.connect('$HOME/data/platform_v2/platform_v2.db'); s.backup(d); print(d.execute('PRAGMA integrity_check').fetchone()); d.close()"
   ```
4. `checks47.py` (orphans 0), restart :8003, then build a Desk release and run the detectors, so the screens read
   the restored reading.
