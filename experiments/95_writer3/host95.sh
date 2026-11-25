#!/bin/bash
# Experiment 95 on the GPU host.  Stages chain with no idle gap; STAGE markers in /work/out/stages.log.
#   c_synth c_pool c_held c_judged   idea 1, contrastive (contrast95.py run SET) -> out/run/contrast_<SET>.jsonl
#   learn                            idea 2 + 3a (learn95.py all) -> out/learn/
#   onepen                           idea 3b (onepen95.py fit) -> out/onepen/
#   queue FILE                       run the stage names listed in FILE one after another (lines may be added while
#                                    it runs; it stops at a line "END"), so the host never idles between our uploads
# Follow with bracket patterns only:  gs95.py follow '[h]ost95.sh'
set -e
cd /work
mkdir -p out out/run
[ -f up95.tgz ] && [ ! -d data95 ] && tar xzf up95.tgz
C=$(awk '$1 != "max" {print int($1 / $2)}' /sys/fs/cgroup/cpu.max 2>/dev/null || true)
for g in /sys/fs/cgroup/cpu /sys/fs/cgroup/cpu,cpuacct; do
  if [ -z "$C" ] && [ -f $g/cpu.cfs_quota_us ]; then
    q=$(cat $g/cpu.cfs_quota_us); p=$(cat $g/cpu.cfs_period_us)
    [ "$q" -gt 0 ] && C=$(( q / p ))
  fi
done
[ -z "$C" ] && C=$(nproc)
[ "$C" -gt "$(nproc)" ] && C=$(nproc)
T=$(( C > 8 ? 8 : C ))
export OMP_NUM_THREADS=$T THREADS=$T FONTS87=/work/fonts E87=/work/e87 DATA87=/work/data87 DATA95=/work/data95 \
       PROG95=/work/programs RUN95=/work/out/run WARP87=0.6 OUT95=/work/out
echo "$(date -u +%FT%TZ) cpus(quota) $C torch $T" >> out/host95.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
run_stage() {
  case "$1" in
    c_synth|c_pool|c_held|c_judged) stage "$1" start; python contrast95.py run "${1#c_}"; stage "$1" done ;;
    c_smoke) stage c_smoke start; LIMIT95=48 RUN95=/work/out/smoke python contrast95.py run pool; stage c_smoke done ;;
    learn) stage learn start; python learn95.py all; stage learn done ;;
    learn_smoke) stage learn_smoke start; python learn95.py smoke; stage learn_smoke done ;;
    onepen) stage onepen start; python onepen95.py fit; stage onepen done ;;
    *) python "$@" ;;
  esac
}
if [ "$1" = "queue" ]; then
  n=1
  while true; do
    L=$(sed -n "${n}p" "$2" 2>/dev/null || true)
    if [ -z "$L" ]; then sleep 20; continue; fi
    [ "$L" = "END" ] && break
    run_stage $L || stage "$L" FAILED
    n=$((n + 1))
  done
  stage QUEUE_DONE
else
  for s in "$@"; do run_stage $s; done
  stage ALL_DONE
fi
