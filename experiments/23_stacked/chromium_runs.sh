#!/bin/bash
# The Chromium 153 sessions behind the report: three stacked words of the fixture (page 3), today's PDF (base) and
# the stacked rule (cell): drag letter by letter, select each letter alone, and drag a whole line.
cd "$(dirname "$0")"; PW=/tmp/claude-1000/-home-yassine-inkscript/ed816869-9be5-4008-b630-480b426fc462/scratchpad/pw/bin/python
for v in base cell; do
  for w in على المحكم معاجم; do
    echo "$v $w drag";   $PW chromium.py $PWD/out/post/0582_$v.pdf 3 $w ${v}_$w 2>&1 | grep -v fitz
    echo "$v $w single"; $PW chromium.py $PWD/out/post/0582_$v.pdf 3 $w ${v}_${w}_single --single 2>&1 | grep -v fitz
  done
  echo "$v line"; $PW chromium.py $PWD/out/post/0582_$v.pdf 3 المحكم ${v}_line --line 2>&1 | grep -v fitz
done
