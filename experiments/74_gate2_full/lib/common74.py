"""Experiment 74: the production librarian for one journal of gate 2 (experiment 72's code, journal-parameterised).

Environment (required):
  LIB74_J        the journal code, 4 digits (0011, 0523, ...)
  LIB74_RELEASE  the Desk release the pass is planned on (the live one after the journal's load)
  LIB74_GUARD    (ask74 only) dollars: a job is refused when this journal's log + open jobs' worst + its worst > guard
Optional: LIB74_OUT (default experiments/74_gate2_full/out/<J>/lib; tests point it at a scratch folder),
          LIB74_FREEZE=1 (inst74 build: keep the questions as asked, re-run only the rules).

Nothing here writes outside OUT, except import74 / golive74.sh (the Desk, through desk.ops) and dryrun74 (a test_ schema).

How to run a journal (from experiments/74_gate2_full/lib; DV = ../../49_correction_desk/.venv/bin/python (psycopg),
RV = ../../../.venv/bin/python (google-genai, anthropic); every step `nice`):
   export LIB74_J=0011 LIB74_RELEASE=/home/appuser/data/desk/releases/R....db LIB74_GUARD=<$ left for this journal>
   1  $DV inst74.py packets              exp 56's packet builder on the release -> OUT/inst/aff<J>.jsonl
   2  $DV inst74.py build                rules R1 / R6, questions -> OUT/questions/inst.jsonl
   3  $DV works74.py cards               every active card; this journal's -> OUT/works<J>/
   4  $DV works74.py catalogue           exp 62's drawer over marc.db (~12 min, ~0.75 GB)
   5  $DV works74.py cands               blocking; packets touching this journal not settled by the seen list
   6  $DV works74.py questions           rules K1c (tightened venue), P6, D44 same text, C1; questions
   7  $DV persons74.py                   same-name pairs -> OUT/persons/pairs.txt (read by hand; nothing applied
                                         unless listed in OUT/persons_apply.json)
   8  $RV ask74.py batch --model gemini-3.8-flash      then  $RV ask74.py collect --model gemini-3.8-flash --wait
   9  $DV decide74.py tier1              -> OUT/ids_opus.txt
  10  $RV ask74.py batch --model claude-opus-5-5 --ids OUT/ids_opus.txt;  collect --wait
  11  $DV review74.py gather             -> OUT/inst/review_candidates.json; write OUT/inst/review74_input.json by hand
  12  $DV review74.py write              -> OUT/inst/authority74.json
  13  LIB74_FREEZE=1 $DV inst74.py build (the reviewed forms re-run R1 on the rule-settled statements)
  14  $DV decide74.py final; $DV decide74.py alarm
  15  $RV ask74.py batch --model claude-sonnet-5-5 --ids OUT/ids_alarm_sonnet.txt; collect --wait
  16  $DV verify74.py alarm; $DV plan74.py (draft plan for the sample); $DV verify74.py checks; $DV verify74.py sample
      -> OUT/handcheck_sheet.txt; verdicts by hand into OUT/handcheck74.jsonl ({"source_id", "op", "reason_code",
      "verdict": right|minor|wrong, "note"}); $DV verify74.py score  (a kind under 98% -> OUT/hold_kinds.json += kind)
  17  $DV plan74.py                      -> OUT/plan74.jsonl, OUT/tasks74.jsonl
  18  cd ../../49_correction_desk && .venv/bin/python ../74_gate2_full/lib/dryrun74.py --out <scratch> (schema test_e74<J>)
  19  ../74_gate2_full/lib/golive74.sh   (backup, import --tasks, release --keep 14, numbers)
"""
from __future__ import annotations

import json
import os
import re
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
E = HERE.parents[1]
E74 = HERE.parent
DESK = E / "49_correction_desk"
E56, E62, E63, E64, E67, E71, E72 = (E / "56_librarian_institutions", E / "62_librarian_works",
                                     E / "63_verify_institutions", E / "64_apply_institutions", E / "67_apply_works",
                                     E / "71_librarian_models", E / "72_librarian_0165")
MARC = Path("/home/appuser/data/marc/marc.db")
JOURNAL = os.environ.get("LIB74_J", "")
if not re.fullmatch(r"\d{4}", JOURNAL):
    raise SystemExit("set LIB74_J to the journal code (4 digits)")
JID = "J" + JOURNAL
if not os.environ.get("LIB74_RELEASE"):
    raise SystemExit("set LIB74_RELEASE to the release the pass is planned on")
RELEASE = Path(os.environ["LIB74_RELEASE"])
OUT = Path(os.environ.get("LIB74_OUT") or (E74 / "out" / JOURNAL / "lib"))
TAG = f"74-{JOURNAL}"                     # question ids I74-<J>-..., W74-<J>-...
SRC = f"E74:{JOURNAL}:"                   # Desk source_id prefix
PROMPT = "74.1"


def ro(path: Path | str = RELEASE) -> sqlite3.Connection:
    c = sqlite3.connect(f"file:{path}?mode=ro", uri=True)
    c.row_factory = sqlite3.Row
    return c


def jl(p):
    p = Path(p)
    return [json.loads(l) for l in open(p, encoding="utf-8") if l.strip()] if p.exists() else []


def wjl(p, rows):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, default=list) + "\n")


def js(p):
    return json.load(open(p, encoding="utf-8"))


def wjs(p, obj):
    Path(p).parent.mkdir(parents=True, exist_ok=True)
    Path(p).write_text(json.dumps(obj, ensure_ascii=False, indent=1, default=list), encoding="utf-8")


def add_paths(*dirs):
    for d in dirs:
        if str(d) not in sys.path:
            sys.path.insert(0, str(d))


def reviewed_files() -> list[Path]:
    """Every earlier reviewed authority file: exp 72's, then each journal's of this experiment (this one's last)."""
    fs = [E72 / "out" / "inst" / "authority72.json"]
    fs += sorted(p for p in (E74 / "out").glob("[0-9][0-9][0-9][0-9]/lib/inst/authority74.json")
                 if p.resolve() != (OUT / "inst" / "authority74.json").resolve())
    p = OUT / "inst" / "authority74.json"
    if p.exists():
        fs.append(p)
    return [f for f in fs if f.exists()]


def reviewed_bodies() -> dict:
    """id -> body of every accepted reviewed body (exp 72 + this experiment's journals)."""
    out = {}
    for f in reviewed_files():
        for b in js(f).get("bodies") or []:
            if b.get("accepted"):
                out[b["id"]] = b
    return out
