#!/bin/bash
# Experiment 74, steps 4-6 for journal J (from experiment 70's sequence): judge pages, screenshots, the judge on Batch
# (Argon, judge v2), the frozen two keys, the summary, the page retries (at most 15, Standard), then final74.sh.
# CAP = the absolute exp 43 log total the judge and retries may not cross (exported as JUDGE43_CAP: exp 70's issue 2).
# Usage: judge74.sh J CAP
set -e
J=$1; CAP=$2
[ -n "$CAP" ] || { echo "usage: judge74.sh J CAP"; exit 1; }
export JUDGE43_CAP=$CAP
export JUDGE43_PW=/home/appuser/inkscript/experiments/52_journal_gate1/out/pwvenv/bin/python
export META43_CATALOGUE_FIRST=1
H=/home/appuser/inkscript/experiments/74_gate2_full
X=/home/appuser/inkscript/experiments/43_rehearsal
PY="nice -n 10 /home/appuser/inkscript/.venv/bin/python"
cd $X
echo "== pages $J $(date +%H:%M)"; $PY $H/judge_pages74.py $J
echo "== shots $(date +%H:%M)"; $PY judge43.py shots --run j$J --pagelist out/j$J/pages_judge.txt > out/j$J/judge_shots.log 2>&1
echo "== judge batch $(date +%H:%M)"; $PY judge43.py batch --run j$J --pagelist out/j$J/pages_judge.txt --model gemini-4-argon --prompt v2 --cap $CAP > out/j$J/judge_batch.log 2>&1; tail -n 3 out/j$J/judge_batch.log
echo "== decide $(date +%H:%M)"; $PY judge43.py decide --run j$J --model gemini-4-argon --prompt v2 --out out/j${J}_final | tail -n 1
$PY $H/judge_summary74.py $J | head -n 30
echo "== retries $(date +%H:%M)"; $PY $H/retries74.py $J > out/j$J/retries.log 2>&1; grep -c "check:" out/j$J/retries.log || true
echo "== final $(date +%H:%M)"; bash $H/final74.sh $J
bash $H/views74.sh $J
echo "== done $(date +%H:%M)"
