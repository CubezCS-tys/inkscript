#!/bin/bash
# Experiment 74: the librarian's automatic part for journal J on release R (steps 1-10 of common74.py): packets,
# rules and questions, cited-work cards / catalogue drawer / blocking / questions, same-name persons, Flash on every
# question (Batch), tier 1, Opus on the rest (Batch). Stops before the authority review (by hand).
# Usage: run_lib74.sh J RELEASE GUARD
set -e
export LIB74_J=$1 LIB74_RELEASE=$2 LIB74_GUARD=$3
cd /home/appuser/inkscript/experiments/74_gate2_full/lib
DV="nice -n 10 ../../49_correction_desk/.venv/bin/python"
RV="nice -n 10 ../../../.venv/bin/python"
O=../out/$1/lib; mkdir -p $O/logs
step() { echo "== $1 $(date +%H:%M)"; }
step packets;   /usr/bin/time -v $DV inst74.py packets > $O/logs/packets.log 2> $O/logs/packets.time; tail -n 1 $O/logs/packets.log
step build;     $DV inst74.py build > $O/logs/inst_build.log 2>&1; tail -n 12 $O/logs/inst_build.log
step cards;     $DV works74.py cards > $O/logs/cards.log 2>&1; tail -n 1 $O/logs/cards.log
step catalogue; /usr/bin/time -v $DV works74.py catalogue > $O/logs/catalogue.log 2> $O/logs/catalogue.time; tail -n 1 $O/logs/catalogue.log; grep "Maximum res" $O/logs/catalogue.time
step cands;     $DV works74.py cands > $O/logs/cands.log 2>&1; tail -n 8 $O/logs/cands.log
step questions; $DV works74.py questions > $O/logs/questions.log 2>&1; tail -n 12 $O/logs/questions.log
step persons;   $DV persons74.py > $O/logs/persons.log 2>&1; tail -n 2 $O/logs/persons.log
step flash;     $RV ask74.py batch --model gemini-3.8-flash > $O/logs/flash.log 2>&1; tail -n 2 $O/logs/flash.log
                $RV ask74.py collect --model gemini-3.8-flash --wait >> $O/logs/flash.log 2>&1; tail -n 1 $O/logs/flash.log
step tier1;     $DV decide74.py tier1 > $O/logs/tier1.log 2>&1; tail -n 30 $O/logs/tier1.log
if [ -s $O/ids_opus.txt ]; then
step opus;      $RV ask74.py batch --model claude-opus-5-5 --ids $O/ids_opus.txt > $O/logs/opus.log 2>&1; tail -n 2 $O/logs/opus.log
                $RV ask74.py collect --model claude-opus-5-5 --wait >> $O/logs/opus.log 2>&1; tail -n 1 $O/logs/opus.log
fi
step gather;    $DV review74.py gather > $O/logs/gather.log 2>&1; tail -n 3 $O/logs/gather.log
echo "== done $(date +%H:%M)"
