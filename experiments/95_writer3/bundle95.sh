#!/bin/bash
# Experiment 95: the upload for the GPU host (local, light).  out/gpu/up/up95.tgz unpacks in /work to:
#   data87/    87's line data and crops (pool, held, judge, synth) - held-out crops go as TEST inputs only
#   data95/    our jobs, the journals' lines and crops, guards.json (split76 test codes, for the host's asserts)
#   programs/  87's letter programs completed for our texts (prog95.py)
#   fonts/     the font files HarfBuzz shapes with (87's staged copy of exp 78's OFL and traced faces)
set -e
cd "$(dirname "$0")"
B=out/gpu/up
mkdir -p $B
D=../87_writer/out
tar czf $B/up95.tgz \
  --transform "s,^87_writer/out/data,data87," --transform 's,^out/data,data95,' --transform 's,^out/programs,programs,' \
  --transform "s,^87_writer/out/gpu/stage/fonts,fonts," \
  $D/data/crops $D/data/synth.jsonl $D/data/held.jsonl \
  $(ls out/data/*.jsonl out/data/*.json 2>/dev/null) $( [ -n "$JL95" ] && echo out/data/crops ) out/programs \
  $D/gpu/stage/fonts
ls -la $B
