#!/bin/bash
# Runs on the GPU host in /work, after setup.sh: one model served at a time, smoke test on 2 dev pages, then all
# 258 pages. If a smoke test fails it waits up to 15 min for /work/GO_<tag> (go on) or /work/SKIP_<tag>; default skip.
# Progress: /work/logs/orch.log; markers /work/state/<tag>.{smoke_ok,smoke_fail,done,skipped,serve_fail}.
cd /work; mkdir -p logs state; export HF_HOME=/work/hf
L=logs/orch.log; log() { echo "$(date -Is) $*" >> $L; }
VLLM=/opt/vllm/bin/vllm; VPY=/opt/vllm/bin/python
waitfor() { until [ -f "$1" ]; do [ -f "${1%.ok}.fail" ] && return 1; sleep 10; done; }

serve() {   # serve TAG PORT args...   (starts in its own process group; waits for /v1/models)
  local tag=$1 port=$2; shift 2
  log "serve $tag: $*"
  setsid nohup $VLLM serve "$@" --port $port > logs/serve_$tag.log 2>&1 < /dev/null &
  SPID=$!; local t=0
  until curl -sf localhost:$port/v1/models > /dev/null; do
    sleep 10; t=$((t+10))
    if ! kill -0 $SPID 2>/dev/null || [ $t -gt 1800 ]; then log "serve $tag FAILED after $t s"; touch state/$tag.serve_fail; stop; return 1; fi
  done
  log "serve $tag up after $t s"
}
stop() {
  [ -n "$SPID" ] && kill -- -$SPID 2>/dev/null; sleep 5; kill -9 -- -$SPID 2>/dev/null; SPID=
  for i in $(seq 30); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)" -lt 1500 ] && break; sleep 3; done
}
gate() {    # gate TAG  (after a smoke test returned non-zero)
  log "smoke $1 FAILED: waiting for GO_$1 / SKIP_$1"; touch state/$1.smoke_fail
  for i in $(seq 90); do [ -f GO_$1 ] && { log "GO $1"; return 0; }; [ -f SKIP_$1 ] && break; sleep 10; done
  log "skip $1"; touch state/$1.skipped; return 1
}
client() {  # client TAG [args]  -> smoke then full
  local tag=$1; shift
  if $VPY gpu/vlm_client.py $tag --smoke "$@" >> logs/client_$tag.log 2>&1; then touch state/$tag.smoke_ok; log "smoke $tag ok"
  else gate $tag || return 1; fi
  $VPY gpu/vlm_client.py $tag "$@" >> logs/client_$tag.log 2>&1
  $VPY gpu/vlm_client.py $tag "$@" >> logs/client_$tag.log 2>&1      # second pass retries timeouts/errors once
  touch state/$tag.done; log "done $tag: $(tail -1 logs/client_$tag.log)"
}

waitfor setup/vllm.ok || { log "vllm install failed"; exit 1; }
waitfor setup/pages.ok
log "start; $(cat setup/vllm.ok)"

# 1. dots.mocr
waitfor setup/dl_dots.mocr.ok && serve dots_mocr 8000 rednote-hilab/dots.mocr --revision e539fbb52280393adc081b289ec597430a0f9031 \
  --code-revision e539fbb52280393adc081b289ec597430a0f9031 --tokenizer-revision e539fbb52280393adc081b289ec597430a0f9031 \
  --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --chat-template-content-format string \
  --served-model-name model --trust-remote-code --max-model-len 40960 && { client dots_mocr; stop; }

# 1b. dots.ocr
waitfor setup/dl_dots.ocr.ok && serve dots_ocr 8000 rednote-hilab/dots.ocr --revision c0111ce6bc07803dbc267932ffef0ae3a51dc951 \
  --code-revision c0111ce6bc07803dbc267932ffef0ae3a51dc951 --tokenizer-revision c0111ce6bc07803dbc267932ffef0ae3a51dc951 \
  --tensor-parallel-size 1 --gpu-memory-utilization 0.9 --chat-template-content-format string \
  --served-model-name model --trust-remote-code --max-model-len 40960 && { client dots_ocr; stop; }

# 2. PaddleOCR-VL-1.5 full pipeline
R=2a4195faa5e7914c12f2fc601d72c81caf8d2da5
if waitfor setup/paddle.ok && waitfor setup/dl_PaddleOCR-VL-1.5.ok && serve paddle_vl15 8118 PaddlePaddle/PaddleOCR-VL-1.5 \
   --revision $R --code-revision $R --tokenizer-revision $R --trust-remote-code --max-num-batched-tokens 16384 \
   --no-enable-prefix-caching --mm-processor-cache-gb 0 --gpu-memory-utilization 0.5 --served-model-name PaddleOCR-VL-1.5-0.9B; then
  if /opt/paddle/bin/python gpu/paddle_run.py paddle_vl15 --smoke >> logs/client_paddle_vl15.log 2>&1; then touch state/paddle_vl15.smoke_ok; log "smoke paddle ok"; ok=1
  else gate paddle_vl15 && ok=1 || ok=0; fi
  [ $ok = 1 ] && { /opt/paddle/bin/python gpu/paddle_run.py paddle_vl15 >> logs/client_paddle_vl15.log 2>&1; touch state/paddle_vl15.done; log "done paddle"; }
  stop
fi

# 3. Qwen3-VL-32B AWQ (fallback 8B bf16)
R=c2d44b1376c73fa120fdb4e216c2ef61c1945498
if waitfor setup/dl_Qwen3-VL-32B-Instruct-AWQ.ok && serve qwen3vl32b_awq 8000 QuantTrio/Qwen3-VL-32B-Instruct-AWQ --revision $R \
   --code-revision $R --tokenizer-revision $R --served-model-name qwen --max-model-len 16384 --max-num-seqs 6 \
   --gpu-memory-utilization 0.92 --limit-mm-per-prompt.video 0 --mm-processor-cache-gb 0 --kv-cache-dtype fp8 \
   --async-scheduling --trust-remote-code; then
  client qwen3vl32b_awq; Q=$?
  if [ $Q = 0 ] && [ ! -f NO_CARD ]; then   # the card's sampled setting on 10 test pages, as a check
    $VPY -c "import json; P=[p['page_id'] for p in json.load(open('manifest.json'))['pages'] if p['split']=='test']; print('\n'.join(P[::len(P)//10][:10]))" > state/card_ids.txt
    $VPY gpu/vlm_client.py qwen3vl32b_awq_card --ids state/card_ids.txt >> logs/client_qwen3vl32b_awq_card.log 2>&1; log "card check done"
  fi
  stop
fi
if [ ! -f state/qwen3vl32b_awq.done ]; then
  R=0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
  waitfor setup/dl_Qwen3-VL-8B-Instruct.ok && serve qwen3vl8b 8000 Qwen/Qwen3-VL-8B-Instruct --revision $R --code-revision $R \
    --tokenizer-revision $R --served-model-name qwen --max-model-len 16384 --max-num-seqs 16 --gpu-memory-utilization 0.92 \
    --limit-mm-per-prompt.video 0 --mm-processor-cache-gb 0 --async-scheduling --trust-remote-code && { client qwen3vl8b; stop; }
fi

# 4. amad-vlm6 (optional)
R=7daf90cd5e5706173e159c88ca4e6dc2475a485e
if [ ! -f NO_AMAD ]; then
  waitfor setup/dl_amad-vlm6.ok && serve amad_vlm6 8000 amad-iq/amad-vlm6 --revision $R --tokenizer-revision $R \
    --served-model-name amad --max-model-len 20480 --limit-mm-per-prompt.video 0 --gpu-memory-utilization 0.9 && { client amad_vlm6; stop; }
fi
log "ALL DONE"; touch state/ALL_DONE
