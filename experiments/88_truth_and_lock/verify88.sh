#!/usr/bin/env bash
# Experiment 88: is any chosen locked stem named inside ANY repo file?  (fixed-string search, text and binary;
# images, PDFs and model weights are not read; their NAMES are covered by select88's scan of file names.)
#   nice -n 19 ionice -c3 bash verify88.sh   -> out/data/grep88_raw.txt, out/data/grep88_hits.json
set -euo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
REPO="$(cd "$HERE/../.." && pwd)"
D="$HERE/out/data"
cd "$REPO"
grep -rFoa -f "$D/chosen88.txt" . \
  --exclude-dir=.git --exclude-dir='venv*' --exclude-dir=.venv --exclude-dir=site-packages --exclude-dir=hf_cache \
  --exclude-dir=node_modules --exclude-dir=__pycache__ \
  --exclude='*.jpg' --exclude='*.jpeg' --exclude='*.png' --exclude='*.pdf' --exclude='*.pt' --exclude='*.so' \
  --exclude='*.wmf' --exclude='*.emf' --exclude='*.npz' --exclude='*.pkl' --exclude='*.tif' --exclude='*.webp' \
  --exclude='*.safetensors' --exclude='*.ckpt' --exclude='*.onnx' --exclude='*.npy' \
  | sort -u > "$D/grep88_raw.txt" || true
python3 - "$D" <<'EOF'
import json, sys
from collections import defaultdict
d = sys.argv[1]
hits = defaultdict(set)
for l in open(f"{d}/grep88_raw.txt", encoding="utf-8", errors="replace"):
    f, s = l.rstrip("\n").rsplit(":", 1)
    hits[s].add(f[2:] if f.startswith("./") else f)
prev = json.load(open(f"{d}/grep88_hits.json")) if __import__("os").path.exists(f"{d}/grep88_hits.json") else {}
for s, fs in prev.items():
    hits[s] |= set(fs)
json.dump({s: sorted(v) for s, v in sorted(hits.items())}, open(f"{d}/grep88_hits.json", "w"), indent=0)
print(len(hits), "stems named in some repo file (cumulative)")
EOF
