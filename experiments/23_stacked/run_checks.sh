#!/bin/bash
# Fixture checks (pdfium words intact, lines in order, inversions, coverage) on 21's after-builds and on the
# same documents post-processed with the stacked rule (variant cell).  -> out/checks.jsonl
cd "$(dirname "$0")"; PY=../../.venv/bin/python; TRY=../14_vs_azure/out/tryout_2026-10-05/azure; FIX=../../tests/fixtures/0582-004-009-012/azure
for d in 0582 1036 0618 0772; do
  B=../21_better_boxes/out/build_new/$d; stem=$(basename $(ls $B/*_vector.pdf) _vector.pdf); AZ=$TRY; [ $d = 0582 ] && AZ=$FIX
  [ -f out/post/${d}_img_cell.pdf ] || $PY post.py $B/$stem.pdf out/post/${d}_img_cell.pdf cell >/dev/null 2>&1
  for v in before after; do
    if [ $v = before ]; then P=$B/$stem.pdf; V=$B/${stem}_vector.pdf; else P=out/post/${d}_img_cell.pdf; V=out/post/${d}_cell.pdf; fi
    r=$($PY checks.py $P $B/native_pdf_report.json $AZ $V 2>/dev/null | tail -1)
    echo "{\"doc\": \"$d\", \"variant\": \"$v\", \"checks\": $r}" | tee -a out/checks.jsonl
  done
done
