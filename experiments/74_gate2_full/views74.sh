#!/bin/bash
# Experiment 74: publish a journal's scan-route views for /views/<run>/ (the Desk's "Classic page"): an index page in
# out/J/jJ/views and out/J/jJ_final/views (make_index74.py) and experiment 41's views symlinks
# (41_azure_structure/out/views/jJ, jJ_final -> those folders), as exp 52 / 70 did. Free. Usage: views74.sh J
J=$1
H=/home/appuser/inkscript/experiments/74_gate2_full
V=/home/appuser/inkscript/experiments/41_azure_structure/out/views
for r in j$J j${J}_final; do
  [ -d $H/out/$J/$r/views/mirror ] || { echo "no views for $r"; continue; }
  python3 $H/make_index74.py $H/out/$J/$r
  ln -sfn $H/out/$J/$r/views $V/$r
  echo "$r: $(ls $H/out/$J/$r/views/mirror | wc -l) mirror pages -> $V/$r"
done
