#!/bin/bash
# inkscript fix on every built document of the set, judged by Gemini (Flash, then Pro), applied.
# Hard cap: the spend log is cumulative, so --cap bounds the whole run, reruns included (CAP, default 13 of the $15 budget).
# Resumable: a rerun judges nothing twice (answers cached) and writes nothing twice.
cd "$(dirname "$(readlink -f "$0")")/../.."; O=experiments/28_scale/out; CAP=${CAP:-13}
nice -n 10 .venv/bin/inkscript fix $O/set/w0 $O/set/w1 $O/set/w2 --azure-dir $O/azure --apply --cap $CAP \
   --spend-log $O/spend.jsonl --cache $O/judge_cache.jsonl 2>&1 | grep -v -i "fitz\|MuPDF error"
echo "FIX DONE $(date)"
