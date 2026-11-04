"""Index of the Gemini requests experiment 43 stored (out/<run>/batch/round*.jsonl): key -> file, byte offset.
    reqindex60.py v33_300b j0130 ...      -> out/req_index.json (read-only on experiment 43)"""
import json, sys
from pathlib import Path
from common60 import E43, OUT, jdump
idx = json.loads((OUT / "req_index.json").read_text()) if (OUT / "req_index.json").exists() else {}
for run in sys.argv[1:]:
    for f in sorted((E43 / "out" / run / "batch").glob("round*.jsonl")):
        off = 0
        with open(f, "rb") as fh:
            for line in fh:
                k = line[9:line.index(b"\"", 9)].decode() if line.startswith(b"{\"key\": \"") else None
                if k:
                    idx.setdefault(k, []).append([str(f), off])
                off += len(line)
        print(f, len(idx), flush=True)
jdump(OUT / "req_index.json", idx)
