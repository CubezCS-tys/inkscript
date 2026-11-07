#!/bin/bash
# Experiment 87 on the GPU host.  `all` chains every stage with no idle gap (STAGE markers in out/stages.log):
#   look      a first look: 96 pool lines x 4 libraries (out/run_look/) - speed and pictures, fetched while
#             the next stages run
#   ceiling   stage 1's ceiling on every pool line, every library, then the wrong-text control (run87.py ceiling)
#   pool      the checker designed on POOL pages (style pool, check pool: planted variants)
#   held      the held-out tests: style held, check held (planted), check judged (exp 81's judged lines)
# Follow with bracket patterns only:  gs87.py follow '[h]ost87.sh'
set -e
cd /work
mkdir -p out out/run
[ -f up87.tgz ] && [ ! -d out/data ] && tar xzf up87.tgz
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
export OMP_NUM_THREADS=$T THREADS=$T FONTS87=/work/fonts
echo "$(date -u +%FT%TZ) cpus(quota) $C torch $T" >> out/host87.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
B=${B87:-32}
look() {
  stage look start
  RUN87=out/run_look LOOK87=1 python run87.py ceiling --libs alqalam,font:amiri_Amiri-Regular,font:notonaskharabic_NotoNaskhArabic_wght,font:Mand0737y1937 --iters 200 --batch $B
  stage look done
  stage synth start; python run87.py synth --iters 200 --batch $B; stage synth done
}
ceiling() { stage ceiling start; python run87.py ceiling --screen 60 --iters 160 --batch $B; stage ceiling done; }
pool()    { stage pool start; python run87.py style pool --screen 60 --iters 160 --batch $B; python run87.py check pool --iters 100 --batch $B; stage pool done; }
held()    { stage held start; python run87.py style held --screen 60 --iters 160 --batch $B; python run87.py check held --iters 100 --batch $B
            python run87.py check judged --iters 100 --batch $B; stage held done; }
case "$1" in
  all) look; ceiling; pool; held; stage ALL_DONE ;;
  rest) stage synth start; python run87.py synth --iters 160 --batch $B; stage synth done; ceiling; pool; held; stage ALL_DONE ;;
  *) "$@" ;;
esac
