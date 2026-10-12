#!/bin/bash
# Fourth GPU job: fine-tune kraken's line finder (blla, the default baseline model shipped with kraken 7.1.1) on
# scanned Mandumah pages whose lines come from Azure (seg_data.py: PAGE XML, boundaries = Azure's polygons, baselines
# found in the ink). Output classes are reset to what the data has (lines only, no regions). Early stopping on dev.
mkdir -p /work; cd /work
while pgrep -f "pip install" > /dev/null; do sleep 5; done                 # gpu_run.sh started it during the upload
python -c "import kraken" 2>/dev/null || pip install -q kraken==7.1.1 >> pip.log 2>&1 || { echo PIPFAIL > DONE4; exit 1; }
tar xf seg.tar
ls /work/seg/train/*.xml > seg_train.lst; ls /work/seg/dev/*.xml > seg_dev.lst
BLLA=$(python -c "import kraken, os; print(os.path.join(os.path.dirname(kraken.__file__), 'blla.mlmodel'))")
date +%s > S.start
timeout 75m ketos --workers 12 --threads 4 -d cuda:0 segtrain -f page -i "$BLLA" --resize both --augment \
  -N 60 -q early --min-epochs 10 --lag 8 -F 1 -o segA -t seg_train.lst -e seg_dev.lst > segA.log 2>&1
echo $? > segA.exit; date +%s > S.end
echo ok > DONE4
