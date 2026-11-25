#!/bin/bash
# Experiment 94 on the GPU host: leave pages with 300 or more lines out of training (41 of 37,096).  The YOLO
# assigner's memory grows with the largest page of a batch; batch 8 at 1280 already used 32 GB on a 367-line batch,
# and the largest page has 911 lines.  The moved files go to /work/capped/.
cd /work/d
mkdir -p ../capped
for ds in lay line; do
  for sp in train val syn; do
    [ -d $ds/labels/$sp ] || continue
    for f in $ds/labels/$sp/*.txt; do
      n=$(wc -l < "$f")
      if [ "$n" -ge 299 ]; then
        b=$(basename "$f" .txt); mkdir -p ../capped/$ds/$sp
        mv "$f" ../capped/$ds/$sp/; mv $ds/images/$sp/$b.jpg ../capped/$ds/$sp/ 2>/dev/null
      fi
    done
  done
  rm -f $ds/labels/*.cache
done
find ../capped -name "*.txt" | wc -l
