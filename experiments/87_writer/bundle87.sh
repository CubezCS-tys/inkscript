#!/bin/bash
# Experiment 87: the upload for the GPU host (local, light).  out/gpu/up/up87.tgz unpacks in /work to:
#   out/programs/  the letter programs (AlQalam strokes, every font's)
#   out/data/      pool.jsonl, held.jsonl, plants_*.jsonl, judged_shown.jsonl, exclude.json, crops/{pool,held,judge}
#   fonts/         the font files (HarfBuzz shapes with them): exp 78's OFL faces and traced faces
# Held-out crops go only as TEST inputs; nothing on the host is trained.
set -e
cd "$(dirname "$0")"
F=../78_synthetic_lines/out/fonts
B=out/gpu/up
mkdir -p $B out/gpu/stage/fonts/traced
python3 - <<'PY'
import json, glob, shutil, os
for p in glob.glob('out/programs/font_*.json'):
    d = json.load(open(p))
    dst = 'out/gpu/stage/fonts/' + d['font']
    if not os.path.exists(dst):
        shutil.copy('../78_synthetic_lines/out/fonts/' + d['font'], dst)
PY
tar czf $B/up87.tgz --exclude=out/programs/alqalam.json --exclude=out/programs/texts.txt out/programs \
    out/data/pool.jsonl out/data/held.jsonl out/data/plants_pool.jsonl out/data/plants_held.jsonl \
    out/data/judged_shown.jsonl out/data/synth.jsonl out/data/exclude.json out/data/crops -C out/gpu/stage fonts
ls -la $B
