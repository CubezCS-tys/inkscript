#!/bin/bash
# Experiment 84: build the upload bundle for the GPU host (local, light).  out/bundle/up84.tgz unpacks in /work to:
#   fonts/ (the display faces render84 uses + their licences), text/display84.jsonl.gz, r78/ (experiment 78's plain
#   fonts, a 1-in-15 slice of text78 for neighbour lines, its paper patches), v3/best.pt (experiment 83's v3),
#   labels_v3.jsonl (v3's held-aside lines dropped: v3's exact training set), test/ (experiment 77's test crops).
# The presigned URL lists (presign84.py) are copied next to it at upload time; they expire.
set -e
cd "$(dirname "$0")"
B=out/bundle; mkdir -p $B
U=out/up84
mkdir -p $U/fonts/deb $U/text $U/test
python3 - <<'EOF'
import re, shutil, os
src = open("render84.py", encoding="utf-8").read()
names = re.findall(r'"([^"]+\.ttf)": \(', src)
disp = [n for n in names if os.path.exists(f"out/fonts/{n}")]
for n in disp:
    d = f"out/up84/fonts/{n}"
    os.makedirs(os.path.dirname(d), exist_ok=True)
    shutil.copy(f"out/fonts/{n}", d)
shutil.copy("out/fonts/LICENCES84.json", "out/up84/fonts/")
print(len(disp), "display faces bundled")
EOF
cp ../78_synthetic_lines/out/fonts/*.ttf $U/r78/fonts/                   # experiment 78's faces (body lines with «» / (( )))
mkdir -p $U/r78/fonts/traced
cp ../78_synthetic_lines/out/fonts/traced/*.ttf ../78_synthetic_lines/out/fonts/traced/exclude.json $U/r78/fonts/traced/
cp out/text/display84.jsonl.gz $U/text/
cp ../77_scratch_reader/out/test/* $U/test/
tar czf $B/up84.tgz -C $U fonts text r78 v3 labels_v3.jsonl test
ls -la $B
