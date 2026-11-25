"""Experiment 102: read a set of line crops with Qwen3.5-4B (base, or base + one or more LoRA adapters) through vLLM's
offline engine, on the rented host.  One JSONL out, one row per line and adapter.

    python eval102.py --model DIR --set sets/dev.jsonl --crops crops/dev --out out/eval/dev_base.jsonl [--H 96]
    python eval102.py --model DIR --set sets/dev.jsonl --crops crops/dev --out out/eval/dev_S.jsonl \
        --adapters run_S/ckpt-100 run_S/ckpt-200 ...           (one engine; adapters swapped per request)
    python eval102.py ... --merged                             (fallback: each adapter merged into the base with PEFT,
                                                                saved under /work/merged/, served as a plain model)

Request = exactly train102's prompt: system prompts/system102.txt, user [image, "Read this line."], the chat template
with enable_thinking=False; the image is cut102.model_image(crop, H) (already 32-aligned and >= min_pixels, so vLLM's
processor does not resize it).  Greedy (temperature 0), max_tokens 256 (a finish of "length" is counted as a loop),
no presence / repetition penalty.  Resumable: keys already in --out (for that adapter) are skipped.
Writes per line: key, adapter, text, finish, prompt_tokens, out_tokens; and <out>.summary.json with lines per second.
No telemetry (VLLM_NO_USAGE_STATS, DO_NOT_TRACK set by host102.sh).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
import data102 as D  # noqa: E402
from cut102 import model_image  # noqa: E402


def merge(model_dir: str, adapter: str, dst: str):
    import torch
    from peft import PeftModel
    from transformers import AutoProcessor, Qwen3_5ForConditionalGeneration
    if Path(dst, "DONE").exists():
        return dst
    m = Qwen3_5ForConditionalGeneration.from_pretrained(model_dir, dtype=torch.bfloat16)
    m = PeftModel.from_pretrained(m, adapter).merge_and_unload()
    m.save_pretrained(dst)
    AutoProcessor.from_pretrained(model_dir).save_pretrained(dst)
    Path(dst, "DONE").write_text("ok")
    del m
    torch.cuda.empty_cache()
    return dst


def run_engine(model_dir, rows, store, a, adapters, out_f, done, label=None):
    from vllm import LLM, SamplingParams
    from vllm.lora.request import LoRARequest
    kw = dict(model=model_dir, max_model_len=a.max_len, limit_mm_per_prompt={"image": 1}, gpu_memory_utilization=a.gpu_mem,
              max_num_seqs=a.max_seqs, seed=0)
    if adapters and not a.merged:
        kw.update(enable_lora=True, max_lora_rank=a.max_lora_rank, max_loras=1)
    llm = LLM(**kw)
    tok = llm.get_tokenizer()
    prompt = tok.apply_chat_template(D.messages(D.system_prompt(a.system)), tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False)
    sp = SamplingParams(temperature=0.0, max_tokens=a.max_tokens)
    stats = []
    for ai, ad in enumerate(adapters or [None]):
        name = label or (ad if ad else "base")
        todo = [r for r in rows if (r["key"], name) not in done]
        lr = LoRARequest(f"a{ai}", ai + 1, ad) if (ad and not a.merged) else None
        t0, n = time.time(), 0
        for i in range(0, len(todo), a.chunk):
            part = todo[i:i + a.chunk]
            reqs = [{"prompt": prompt, "multi_modal_data": {"image": model_image(store.gray(r["key"]), a.H)}} for r in part]
            outs = llm.generate(reqs, sp, lora_request=lr, use_tqdm=False)
            for r, o in zip(part, outs):
                c = o.outputs[0]
                out_f.write(json.dumps(dict(key=r["key"], adapter=name, text=c.text.strip(), finish=c.finish_reason,
                                            prompt_tokens=len(o.prompt_token_ids), out_tokens=len(c.token_ids)),
                                       ensure_ascii=False) + "\n")
            out_f.flush()
            n += len(part)
            print(f"{time.strftime('%H:%M:%S')} {name}: {n}/{len(todo)} ({n / max(1e-6, time.time() - t0):.1f} lines/s)",
                  flush=True)
        stats.append(dict(adapter=name, lines=n, seconds=round(time.time() - t0, 1),
                          lines_per_s=round(n / max(1e-6, time.time() - t0), 2)))
    return stats


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--set", required=True)
    ap.add_argument("--crops", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapters", nargs="*", default=[])
    ap.add_argument("--merged", action="store_true")
    ap.add_argument("--system", default=str(D.SYSTEM_FILE))
    ap.add_argument("--H", type=int, default=96)
    ap.add_argument("--max_tokens", type=int, default=256)
    ap.add_argument("--max_len", type=int, default=2048)
    ap.add_argument("--gpu_mem", type=float, default=0.85)
    ap.add_argument("--max_seqs", type=int, default=128)
    ap.add_argument("--max_lora_rank", type=int, default=32)
    ap.add_argument("--chunk", type=int, default=512)
    ap.add_argument("--limit", type=int, default=0)
    a = ap.parse_args()
    rows = D.read_set(a.set, a.limit)
    store = D.LineStore(a.crops)
    rows = [r for r in rows if r["key"] in store]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    done = set()
    if Path(a.out).exists():
        for l in open(a.out, encoding="utf-8"):
            if l.strip():
                d = json.loads(l)
                done.add((d["key"], d["adapter"]))
    print(f"{len(rows)} lines, adapters {a.adapters or ['base']}, H {a.H}, merged {a.merged}", flush=True)
    stats = []
    with open(a.out, "a", encoding="utf-8") as out_f:
        if a.merged and a.adapters:
            for ad in a.adapters:                       # one engine per merged checkpoint
                dst = merge(a.model, ad, f"/work/merged/{Path(ad).parent.name}_{Path(ad).name}")
                stats += run_engine(dst, rows, store, a, [None], out_f, done, label=ad)
        else:
            stats = run_engine(a.model, rows, store, a, a.adapters, out_f, done)
    Path(str(a.out) + ".summary.json").write_text(json.dumps(dict(stats=stats, H=a.H, set=a.set, merged=a.merged), indent=1))
    print(json.dumps(stats), flush=True)


if __name__ == "__main__":
    main()
