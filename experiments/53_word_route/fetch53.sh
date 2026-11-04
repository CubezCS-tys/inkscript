#!/bin/bash
# Read-only fetch of legacy/<stem>/<stem>.pdf for the stems in out/stems_legacy.txt (exp 53).
cd "$(dirname "$0")/out"
while read s; do
  [ -s legacy_pdf/$s.pdf ] && continue
  /home/appuser/inkscript/.venv/bin/aws s3 cp "s3://mandumah-source-docs/legacy/$s/$s.pdf" legacy_pdf/$s.pdf --quiet && echo "$s ok" || echo "$s FAIL"
done < stems_legacy.txt
