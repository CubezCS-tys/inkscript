#!/bin/bash
# Experiment 74: the librarian's model steps for journal J (when run_lib74's guard refused them): Flash (Batch),
# tier 1, Opus (Batch), gather. Usage: lib_models74.sh J RELEASE GUARD
export LIB74_J=$1 LIB74_RELEASE=$2 LIB74_GUARD=$3
cd /home/appuser/inkscript/experiments/74_gate2_full/lib
DV="nice -n 10 ../../49_correction_desk/.venv/bin/python"; RV="nice -n 10 ../../../.venv/bin/python"; O=../out/$1/lib
echo "== flash $(date +%H:%M)"; $RV ask74.py batch --model gemini-3.8-flash; $RV ask74.py collect --model gemini-3.8-flash --wait | tail -n 1
echo "== tier1 $(date +%H:%M)"; $DV decide74.py tier1 | head -4
echo "== opus $(date +%H:%M)"; $RV ask74.py batch --model claude-opus-5-5 --ids $O/ids_opus.txt; $RV ask74.py collect --model claude-opus-5-5 --wait | tail -n 1
echo "== gather $(date +%H:%M)"; $DV review74.py gather > $O/logs/gather.log 2>&1; echo "== done $(date +%H:%M)"
