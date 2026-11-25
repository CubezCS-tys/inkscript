#!/bin/bash
# Experiment 94 on the GPU host.  `bash host94.sh all` chains every stage with no idle gap (STAGE markers in
# out/stages.log).  Inputs in /work: pdfs94.tar (training + test PDFs), train94.jsonl, pages92.jsonl, init/r1.pt
# (experiment 39's round-1 weights), prep94.py, yolo94.py.
#   setup    doclayout-yolo 0.0.4 (AGPL-3.0, as experiment 39), opencv headless 4.10.0.84, pypdfium2 5.12.1
#   prep     render + both YOLO datasets (prep94.py train), the 457 test pages (prep94.py test)
#   lay      layout model, 16 fine classes, imgsz 1280, HL hours; predict the test pages
#   line     line finder, 4 direction classes + synthetic pages, imgsz 1536, HN hours; predict the test pages
# Follow with a bracket pattern only:  gs94.py follow '[h]ost94.sh'
set -e
cd /work
mkdir -p d out
HL=${HL:-3.0}; HN=${HN:-3.0}
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true)
for g in /sys/fs/cgroup/cpu /sys/fs/cgroup/cpu,cpuacct; do
  if [ -z "$C" ] && [ -f $g/cpu.cfs_quota_us ]; then
    q=$(cat $g/cpu.cfs_quota_us); p=$(cat $g/cpu.cfs_period_us)
    [ "$q" -gt 0 ] && C=$(( q / p ))
  fi
done
[ -z "$C" ] && C=$(nproc)
[ "$C" -gt "$(nproc)" ] && C=$(nproc)
W=$(( C - 2 > 16 ? 16 : C - 2 ))
CW=$(( C - 1 > 32 ? 32 : C - 1 ))
export OMP_NUM_THREADS=1
export PYTORCH_ALLOC_CONF=expandable_segments:True
echo "$(date -u +%FT%TZ) cpus(quota) $C loader $W cpu-workers $CW" >> out/host94.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }

setup() {
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libxcb1 libgl1 libglib2.0-0 >/dev/null) 2>&1 | tail -1
  pip install -q "doclayout-yolo==0.0.4" "pypdfium2==5.12.1" huggingface_hub 2>&1 | tail -2
  pip uninstall -y -q opencv-python opencv-python-headless 2>/dev/null || true
  pip install -q --force-reinstall --no-deps opencv-python-headless==4.10.0.84 2>&1 | tail -1
  python -c "import torch, cv2, doclayout_yolo, pypdfium2; from pypdfium2.version import PYPDFIUM_INFO; print('torch', torch.__version__, torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'pdfium', PYPDFIUM_INFO)" >> out/host94.log 2>&1
  nproc >> out/host94.log; free -g | head -2 >> out/host94.log; df -h /work | tail -1 >> out/host94.log
  stage SETUP_DONE
}

prep() {
  mkdir -p pdf && tar xf pdfs94.tar -C pdf
  python prep94.py train train94.jsonl pdf d $CW > out/prep94_train.log 2>&1
  python prep94.py test pages92.jsonl pdf d $CW > out/prep94_test.log 2>&1
  stage PREP_DONE
}

lay() {
  python yolo94.py train lay d/lay.yaml 1280 $HL 8 $W > out/train_lay.log 2>&1
  python yolo94.py predict lay /work/run_lay/r/weights/best.pt d/test 1280 out/pred94_lay.json > out/pred_lay.log 2>&1
  stage LAY_DONE
}

line() {
  python yolo94.py train line d/line.yaml 1536 $HN 6 $W > out/train_line.log 2>&1
  python yolo94.py predict line /work/run_line/r/weights/best.pt d/test 1536 out/pred94_line.json > out/pred_line.log 2>&1
  stage LINE_DONE
}

case "$1" in
  all) grep -q SETUP_DONE out/stages.log 2>/dev/null || setup; prep; lay; line; stage ALL_DONE ;;
  *) "$1" ;;
esac
