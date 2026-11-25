#!/bin/bash
# Experiment 96 on the GPU host.  `bash host96.sh all` chains every stage with no idle gap (STAGE markers in
# out/stages.log).  Inputs in /work: pdfs96.tar, train96.jsonl, extra96.jsonl, pages92.jsonl, init/lay94.pt and
# init/line94.pt (experiment 94's layout model and line finder), prep94.py, prep96.py, yolo96.py.
#   setup   doclayout-yolo 0.0.4 (AGPL-3.0, as experiments 39/94), huggingface_hub, opencv headless 4.10.0.84, pypdfium2 5.12.1
#   prep    render the pool (train + val), the extra pages and the 457 test pages
#   pseudo  stage-2 layout model on the extra pages -> their other lines' labels; repeats (author pages x REP)
#   lay     fine-tune the layout model from experiment 94's, imgsz 1280, batch 8, HL hours
#   pred    new model on test + val pages; experiment 94's layout model and line finder on the val (DEV) pages
# Follow with a bracket pattern only:  gs96.py follow '[h]ost96.sh'
set -e
cd /work
mkdir -p d out
HL=${HL:-1.75}
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
export OUT94=/work/out RUN94=/work
echo "$(date -u +%FT%TZ) cpus(quota) $C loader $W cpu-workers $CW HL $HL" >> out/host96.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }

setup() {
  (apt-get update -qq && DEBIAN_FRONTEND=noninteractive apt-get install -y -qq libxcb1 libgl1 libglib2.0-0 >/dev/null) 2>&1 | tail -1
  pip install -q "doclayout-yolo==0.0.4" "pypdfium2==5.12.1" huggingface_hub 2>&1 | tail -2
  pip uninstall -y -q opencv-python opencv-python-headless 2>/dev/null || true
  pip install -q --force-reinstall --no-deps opencv-python-headless==4.10.0.84 2>&1 | tail -1
  python -c "import torch, cv2, doclayout_yolo, pypdfium2; from pypdfium2.version import PYPDFIUM_INFO; print('torch', torch.__version__, torch.cuda.get_device_name(0), 'cv2', cv2.__version__, 'pdfium', PYPDFIUM_INFO)" >> out/host96.log 2>&1
  nproc >> out/host96.log; free -g | head -2 >> out/host96.log; df -h /work | tail -1 >> out/host96.log
  stage SETUP_DONE
}

prep() {
  mkdir -p pdf && tar xf pdfs96.tar -C pdf
  python prep96.py train train96.jsonl extra96.jsonl pdf d $CW > out/prep96_train.log 2>&1
  python prep96.py test pages92.jsonl pdf d $CW > out/prep96_test.log 2>&1
  stage PREP_DONE
}

pseudo() {
  python yolo96.py predict lay94 init/lay94.pt d/extra 1280 out/pred96_extra_lay94.json > out/pred_extra.log 2>&1
  python prep96.py pseudo extra96.jsonl out/pred96_extra_lay94.json d > out/pseudo96.log 2>&1
  python prep96.py reps train96.jsonl extra96.jsonl d > out/reps96.log 2>&1
  ls d/lay/images/train | wc -l >> out/reps96.log
  stage PSEUDO_DONE
}

lay() {
  INIT94=/work/init/lay94.pt python yolo96.py train lay d/lay.yaml 1280 $HL 8 $W > out/train_lay.log 2>&1
  stage LAY_DONE
}

pred() {
  python yolo96.py predict lay /work/run_lay/r/weights/best.pt d/test 1280 out/pred96_lay.json > out/pred_lay.log 2>&1
  python yolo96.py predict lay /work/run_lay/r/weights/best.pt d/lay/images/val 1280 out/pred96_lay_val.json >> out/pred_lay.log 2>&1
  python yolo96.py predict lay94 init/lay94.pt d/lay/images/val 1280 out/pred94_lay_val.json >> out/pred_lay.log 2>&1
  python yolo96.py predict line94 init/line94.pt d/lay/images/val 1536 out/pred94_line_val_all.json >> out/pred_lay.log 2>&1
  stage PRED_DONE
}

case "$1" in
  all) grep -q SETUP_DONE out/stages.log 2>/dev/null || setup; prep; pseudo; lay; pred; stage ALL_DONE ;;
  *) "$1" ;;
esac
