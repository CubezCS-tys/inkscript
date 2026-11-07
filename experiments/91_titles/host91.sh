#!/bin/bash
# Experiment 91 on the GPU host (experiment 89's host89.sh, with the title stages).  `all` chains every stage with no
# idle gap (STAGE markers in out/stages.log):
#   cut      experiment 83's training lines re-cut from presigned URLs, as 89, by cut91.py (= cut83.py + the title
#            hook: page 1 of each of these documents is matched with its catalogue title too, no extra download);
#            then a PROVISIONAL label pass on those title lines -> out/prov/ + out/look91_prov.tgz (to look at while
#            the next stage runs)
#   titles   title91.py cut: the NEW documents of urls_t91.jsonl, JSON first, the PDF only on a confident match;
#            then v7-28M (init/l28.pt) reads every title crop, and title91.py labels applies the label rule (the
#            reader as third vote) -> d/train-t91-*.tar, d/tdev91-000.tar, out/labels91_titles.jsonl,
#            out/overrides91.jsonl, out/titles91_stats.json, out/look91.tgz
#   render   experiment 84's 300k synthetic lines + 4k dev (render84.py unchanged), as 89
#   (wait)   training waits for /work/go91 (uploaded after the lead's look at 100 title crops; at most 60 min)
#   t91      fine-tune v7-28M on 89's mix + the title lines at ~6% of every epoch: 2 epochs, one-cycle 2e-4, warm-up
#            10%, polarity 6% / 4% (real lines), (( )) lines dropped; labels = v6r's + overrides91 (v6r's win); then reads
#   reads TAG CKPT   test (owner's 20 pages + lab), dev, vsyn84, t81 (exp 81's 22,783 held-out crops), titles89
#            (exp 89's held-out title crops), tdev91
# Every training run passes --forbid forbidden91.json.  Layout as 89: /work/d (shards, never mirrored), /work/out
# (mirrored), /work/run_* (mirrored).  Follow with bracket patterns only:  gs91.py follow '[h]ost91.sh'
set -e
cd /work
mkdir -p d out out/pred
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
CW=$(( C - 1 > 40 ? 40 : C - 1 ))
T=$(( C > 8 ? 8 : C ))
export OMP_NUM_THREADS=1
echo "$(date -u +%FT%TZ) cpus(quota) $C loader $W cpu-workers $CW torch $T" >> out/host91.log
stage() { echo "$(date -u +%FT%TZ) $*" >> out/stages.log; }
DR='\(\(|\)\)'

reads() {   # TAG CKPT
  local tag=$1 ck=$2
  python train91.py infer --ckpt $ck --data test --split test --pred out/pred/test_$tag.jsonl --workers 4 --threads $T >> out/reads_$tag.log 2>&1
  python train91.py infer --ckpt $ck --data d --split dev --pred out/pred/dev_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  python train91.py infer --ckpt $ck --data d --split vsyn84 --pred out/pred/vsyn_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  python train91.py infer --ckpt $ck --data t81 --split test81 --pred out/pred/t81_$tag.jsonl --workers 8 --threads $T >> out/reads_$tag.log 2>&1
  python train91.py infer --ckpt $ck --data titles --split titles89 --pred out/pred/titles_$tag.jsonl --workers 2 --threads $T >> out/reads_$tag.log 2>&1
  python train91.py infer --ckpt $ck --data d --split tdev91 --pred out/pred/tdev91_$tag.jsonl --workers 2 --threads $T >> out/reads_$tag.log 2>&1
  stage "READS_DONE $tag"
}

title_labels() {   # RESULTS_DIR
  python train91.py infer --ckpt init/l28.pt --data d --split ttl91 --pred out/pred/ttl91_l28.jsonl --workers 8 --threads $T >> out/titles.log 2>&1
  rm -f d/train-t91-*.tar d/tdev91-*.tar
  python title91.py labels d out/pred/ttl91_l28.jsonl $1 >> out/titles.log 2>&1
}

do_titles() {
  echo "$(date -u +%FT%TZ) titles ($CW workers)" >> out/titles.log
  python title91.py cut urls_t91.jsonl d $CW >> out/titles.log 2>&1
  stage TITLE_CUT_DONE
  title_labels out
  cat d/docs-ttl91-*.jsonl > out/docs91_host.jsonl
  cat d/manifest-ttl91-*.jsonl > out/manifest91_host.jsonl
  tar czf out/look91.tgz -C d look91
  rm -f urls_t91.jsonl
  stage TITLE_LABELS_DONE
}

do_cut() {
  for s in r77dev:dev-r77 r77train:train-r77 o80:train-o80 new:train-n83; do
    u=${s%%:*}; p=${s##*:}
    echo "$(date -u +%FT%TZ) cut $u -> $p ($CW workers)" >> out/cut.log
    python cut91.py urls_$u.jsonl d $CW $p >> out/cut.log 2>&1
  done
  cat d/docs-train-*.jsonl d/docs-dev-*.jsonl > out/docs89.jsonl 2>/dev/null || true
  python - <<'EOF' >> out/cut.log
import glob, json
from collections import Counter
c = Counter()
for f in glob.glob("d/manifest-*.jsonl"):
    p = f.split("manifest-")[1].rsplit("-", 1)[0]
    c[p] += sum(1 for _ in open(f))
print("LINES", dict(c))
EOF
  rm -f urls_new.jsonl urls_r77train.jsonl urls_r77dev.jsonl urls_o80.jsonl
  stage CUT_DONE
  mkdir -p out/prov
  title_labels out/prov
  cat d/manifest-ttl91-*.jsonl > out/prov/manifest91_prov.jsonl
  tar czf out/look91_prov.tgz -C d look91
  stage PROV_LABELS_DONE
}

do_render() {
  python render84.py shards --n 300000 --workers $CW --out d --split train-syn84 --root /work --root78 /work/r78 > out/render.log 2>&1
  python render84.py shards --n 4000 --workers 8 --out d --split vsyn84 --root /work --root78 /work/r78 --seed 8484 >> out/render.log 2>&1
  stage RENDER_DONE
}

do_labels() {
  [ -f labels/labels_v6r.jsonl ] || gunzip -k labels/labels_v6r.jsonl.gz
  python - <<'EOF' >> out/host91.log
import json
v6r = {}
for l in open("labels/labels_v6r.jsonl", encoding="utf-8"):
    v6r[json.loads(l)["key"]] = l
n = 0
with open("labels/labels91.jsonl", "w", encoding="utf-8") as f:
    for l in v6r.values():
        f.write(l if l.endswith("\n") else l + "\n")
    for l in open("out/overrides91.jsonl", encoding="utf-8"):
        d = json.loads(l)
        if d["key"] not in v6r or d["label"] is None:     # v6r's judged labels win; a title-dev line's copy is dropped
            f.write(json.dumps(d, ensure_ascii=False) + "\n")
            n += 1
print("labels91:", len(v6r), "v6r +", n, "title overrides")
EOF
}

do_t91() {
  do_labels
  python train91.py train --data d --out run_t91 --labels labels/labels91.jsonl --init init/l28.pt --epochs ${T91_EPOCHS:-2} \
      --workers $W --threads $T --lr 2e-4 --warm 0.1 --invert 0.06 --band 0.04 --dev2 vsyn84,tdev91 --drop_re "$DR" \
      --title_share 0.06 --forbid forbidden91.json > out/train_t91.log 2>&1
  stage TRAIN_DONE t91
  reads t91 run_t91/last.pt
}

case "$1" in
titles) do_titles ;;
cut) do_cut ;;
render) do_render ;;
t91) do_t91 ;;
reads) reads $2 $3 ;;
all)
  stage START all
  ls d/manifest-train-n83-*.jsonl >/dev/null 2>&1 || do_cut
  [ -f out/titles91_stats.json ] || do_titles
  ls d/train-syn84-*.tar >/dev/null 2>&1 || do_render
  n=0; while [ ! -f go91 ] && [ $n -lt 120 ]; do
    [ $n -eq 0 ] && stage "WAITING for go91"; sleep 30; n=$((n + 1)); done
  [ -f go91 ] || { stage "NO go91: stopped before training"; exit 1; }
  do_t91
  python train91.py infer --ckpt init/l28.pt --data d --split tdev91 --pred out/pred/tdev91_l28.jsonl --workers 2 --threads $T >> out/reads_l28.log 2>&1
  stage ALL_DONE ;;
*) echo "usage: host91.sh titles|cut|render|t91|reads TAG CKPT|all"; exit 1 ;;
esac
