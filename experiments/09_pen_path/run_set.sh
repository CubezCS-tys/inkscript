#!/bin/bash
# Build a set with pen-path letters, resumably, with a few polite workers, then summarise.
#   run_set.sh <azure_dir> <frontpage_dir> <scan_dir or -> <out_dir> <workers>
cd "$(dirname "$(readlink -f "$0")")/../.."; INK=.venv/bin/inkscript; A=$1; FP=$2; SC=$3; J=$4; W=${5:-2}
mkdir -p $J; ls $A | sort > $J/stems.txt; rm -f $J/stems_w*; split -n l/$W -d $J/stems.txt $J/stems_w
scan=(); [ "$SC" != "-" ] && scan=(--scan-dir "$SC")
for f in $J/stems_w*; do w=${f##*_w}
  ( while read d; do [ -z "$d" ] && continue
      nice -n 10 $INK native --azure-dir $A --frontpage-dir $FP "${scan[@]}" --out $J/w$w --vector --verify --resume --only "$d" 2>&1 | grep -v -i "warning\|MuPDF error" | grep " pages "
    done < $f ) >> $J/w$w.log 2>&1 &
done
wait
.venv/bin/python experiments/09_pen_path/summary.py $J/w* 2>&1 | grep -v -i "warning\|MuPDF" > $J/summary.txt
echo "SET DONE $(date)" >> $J/summary.txt
