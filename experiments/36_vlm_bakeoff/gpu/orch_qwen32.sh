#!/bin/bash
# Second pass for Qwen, after orchestrate.sh (state/ALL_DONE).
# - Qwen3-VL-8B died after 67 pages: a device-side assert in masked_scatter (image embeddings vs placeholder count)
#   inside vLLM's async-scheduling batch queue. --async-scheduling is a speed flag only; dropped here, and the 8B
#   is resumed on the pages it did not finish (its client skips pages already done).
# - Qwen3-VL-32B AWQ did not start: --kv-cache-dtype fp8 makes vLLM pick FlashInfer, which JIT-compiles with nvcc,
#   absent from the runtime image. models.md's own fallback: bf16 KV and --max-num-seqs 3.
# Then the card's sampled setting on 10 test pages as a check.
cd /work; export HF_HOME=/work/hf; VLLM=/opt/vllm/bin/vllm; VPY=/opt/vllm/bin/python; L=logs/orch.log
log() { echo "$(date -Is) $*" >> $L; }
serve() {   # serve TAG args...
  local tag=$1; shift; log "serve $tag (2nd pass): $*"
  setsid nohup $VLLM serve "$@" --port 8000 > logs/serve_${tag}_2.log 2>&1 < /dev/null &
  SPID=$!; local t=0
  until curl -sf localhost:8000/v1/models > /dev/null; do
    sleep 10; t=$((t+10)); if ! kill -0 $SPID 2>/dev/null || [ $t -gt 1800 ]; then log "serve $tag FAILED again"; kill -- -$SPID 2>/dev/null; return 1; fi
  done; log "serve $tag up after $t s"
}
stop() { kill -- -$SPID 2>/dev/null; sleep 5; kill -9 -- -$SPID 2>/dev/null
  for i in $(seq 30); do [ "$(nvidia-smi --query-gpu=memory.used --format=csv,noheader,nounits | head -1)" -lt 1500 ] && break; sleep 3; done; }
until [ -f state/ALL_DONE ]; do sleep 10; done

R=0c351dd01ed87e9c1b53cbc748cba10e6187ff3b
if serve qwen3vl8b Qwen/Qwen3-VL-8B-Instruct --revision $R --code-revision $R --tokenizer-revision $R --served-model-name qwen \
   --max-model-len 16384 --max-num-seqs 16 --gpu-memory-utilization 0.92 --limit-mm-per-prompt.video 0 \
   --mm-processor-cache-gb 0 --trust-remote-code; then
  $VPY gpu/vlm_client.py qwen3vl8b >> logs/client_qwen3vl8b.log 2>&1
  $VPY gpu/vlm_client.py qwen3vl8b >> logs/client_qwen3vl8b.log 2>&1
  log "done qwen3vl8b (2nd pass): $(tail -1 logs/client_qwen3vl8b.log)"; stop
fi

R=c2d44b1376c73fa120fdb4e216c2ef61c1945498
if serve qwen3vl32b_awq QuantTrio/Qwen3-VL-32B-Instruct-AWQ --revision $R --code-revision $R --tokenizer-revision $R \
   --served-model-name qwen --max-model-len 16384 --max-num-seqs 3 --gpu-memory-utilization 0.92 \
   --limit-mm-per-prompt.video 0 --mm-processor-cache-gb 0 --trust-remote-code; then
  if $VPY gpu/vlm_client.py qwen3vl32b_awq --smoke --conc 3 >> logs/client_qwen3vl32b_awq.log 2>&1; then log "smoke qwen32 ok"
  else log "smoke qwen32 FAILED (continuing; check)"; fi
  $VPY gpu/vlm_client.py qwen3vl32b_awq --conc 3 >> logs/client_qwen3vl32b_awq.log 2>&1
  $VPY gpu/vlm_client.py qwen3vl32b_awq --conc 3 >> logs/client_qwen3vl32b_awq.log 2>&1
  log "done qwen32: $(tail -1 logs/client_qwen3vl32b_awq.log)"
  if [ ! -f NO_CARD ]; then
    $VPY -c "import json; P=[p['page_id'] for p in json.load(open('manifest.json'))['pages'] if p['split']=='test']; print('\n'.join(P[::len(P)//10][:10]))" > state/card_ids.txt
    $VPY gpu/vlm_client.py qwen3vl32b_awq_card --ids state/card_ids.txt --conc 3 >> logs/client_qwen3vl32b_awq_card.log 2>&1
    log "card check done: $(tail -1 logs/client_qwen3vl32b_awq_card.log)"
  fi
  stop
fi
touch state/QWEN32_DONE; log "QWEN32 ALL DONE"
