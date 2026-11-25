#!/bin/bash
# Experiment 103: stage the upload for the GPU host under out/up/ (symlinks only; nothing copied, nothing deleted).
#   out/up/code/      -> one tgz at gs103.py start: our scripts, experiment 102's (unchanged), 87/95's writer code
#                        (unchanged), 95's letter programs, 87's staged fonts, exp 78's exclude list, the guard codes
#   out/up/weights_M  -> /work/weights/M/ckpt-3125   experiment 102's adapter (ours; it never goes anywhere else)
#   out/up/sets       -> /work/sets                  R, dev103, devmix, heldout (+ out/b/ files later, see README)
#   out/up/crops_*    -> /work/crops/<name>          JPEG tars for the reader, PNG tars for the writer
set -e
cd "$(dirname "$0")"
E=..
U=out/up
mkdir -p $U/code/prompts $U/code/e87 $U/code/e95 $U/code/data87 $U/weights_M $U/sets
ln -sfn "$PWD"/$E/102_qwen_line_reader/prompts/system102.txt $U/code/prompts/system102.txt
for f in host103.sh eval103.py judge103.py fix103.py bidi103.py; do ln -sfn "$PWD/$f" $U/code/$f; done
for f in host102.sh train102.py eval102.py data102.py cut102.py forbidden102.json; do
  ln -sfn "$PWD"/$E/102_qwen_line_reader/$f $U/code/$f; done
for f in writer87.py fit87.py run87.py; do ln -sfn "$PWD"/$E/87_writer/$f $U/code/e87/$f; done
for f in common95.py contrast95.py; do ln -sfn "$PWD"/$E/95_writer3/$f $U/code/e95/$f; done
ln -sfn "$PWD"/$E/78_synthetic_lines/out/fonts/traced/exclude.json $U/code/data87/exclude.json
ln -sfn "$PWD"/$E/95_writer3/out/data/guards.json $U/code/judge_guards.json
ln -sfn "$PWD"/$E/95_writer3/out/programs $U/code/programs
ln -sfn "$PWD"/$E/87_writer/out/gpu/stage/fonts $U/code/fonts
for f in "$PWD"/$E/102_qwen_line_reader/out/weights/M/ckpt-3125/*; do ln -sfn "$f" $U/weights_M/; done
for f in R dev103 devmix heldout; do ln -sfn "$PWD/out/sets/$f.jsonl" $U/sets/$f.jsonl; done
for d in crops_R crops_devmix crops_heldout crops_heldout_png; do
  mkdir -p $U/$d; for f in "$PWD"/out/$d/*; do ln -sfn "$f" $U/$d/; done; done
mkdir -p $U/crops_dev; for f in "$PWD"/$E/102_qwen_line_reader/out/crops_dev/*; do ln -sfn "$f" $U/crops_dev/; done
du -shL $U/* | sort -k2
du -shL $U
