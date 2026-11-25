"""Experiment 103: experiment 102's reader (vLLM offline, LoRA served directly) WITH its confidence.

    python eval103.py read  --model DIR --set SET.jsonl --crops DIR [DIR..] --out OUT.jsonl --adapters A [B ..]
    python eval103.py force --model DIR --cands CANDS.jsonl --crops DIR --out OUT.jsonl --adapters A

read:  exactly eval102's request (system prompt, image, "Read this line.", thinking off, greedy, max 256 tokens), plus
       logprobs=1: per line the chosen tokens' log-probabilities -> lp_sum, lp_mean, lp_min, n_tok, and the 5 lowest.
force: the reader's log-likelihood of GIVEN texts (e.g. Azure's reading and the reader's own) on the same image: the
       text + <|im_end|> appended to the prompt, prompt_logprobs=0, max_tokens 1; the answer tokens' log-probabilities
       -> lp_sum, lp_mean, lp_min.  {key, cid, text} per row in CANDS.
Imports experiment 102's data102 / cut102 (uploaded beside this file).  Resumable.  No telemetry (host103.sh).
"""
from __future__ import annotations

import argparse
import json
import math
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent / "102_qwen_line_reader"))
import data102 as D  # noqa: E402
from cut102 import model_image  # noqa: E402


def lp_stats(lps):
    lps = [x for x in lps if x is not None and not math.isnan(x)]
    if not lps:
        return dict(lp_sum=None, lp_mean=None, lp_min=None, n_tok=0)
    return dict(lp_sum=round(sum(lps), 4), lp_mean=round(sum(lps) / len(lps), 5), lp_min=round(min(lps), 4),
                n_tok=len(lps), lp_low5=[round(x, 3) for x in sorted(lps)[:5]])


def engine(a, lora: bool):
    from vllm import LLM
    kw = dict(model=a.model, max_model_len=a.max_len, limit_mm_per_prompt={"image": 1}, gpu_memory_utilization=a.gpu_mem,
              max_num_seqs=a.max_seqs, seed=0)
    if lora:
        kw.update(enable_lora=True, max_lora_rank=a.max_lora_rank, max_loras=1)
    llm = LLM(**kw)
    tok = llm.get_tokenizer()
    prompt = tok.apply_chat_template(D.messages(D.system_prompt(a.system)), tokenize=False, add_generation_prompt=True,
                                     enable_thinking=False)
    return llm, tok, prompt


def read(a):
    from vllm import SamplingParams
    from vllm.lora.request import LoRARequest
    rows = D.read_set(a.set, a.limit)
    store = D.LineStore(a.crops)
    rows = [r for r in rows if r["key"] in store]
    done = set()
    if Path(a.out).exists():
        done = {(d["key"], d["adapter"]) for d in map(json.loads, open(a.out, encoding="utf-8"))}
    llm, tok, prompt = engine(a, bool(a.adapters))
    sp = SamplingParams(temperature=0.0, max_tokens=a.max_tokens, logprobs=1)
    stats = []
    with open(a.out, "a", encoding="utf-8") as f:
        for ai, ad in enumerate(a.adapters or [None]):
            name = ad or "base"
            todo = [r for r in rows if (r["key"], name) not in done]
            lr = LoRARequest(f"a{ai}", ai + 1, ad) if ad else None
            t0, n = time.time(), 0
            for i in range(0, len(todo), a.chunk):
                part = todo[i:i + a.chunk]
                reqs = [{"prompt": prompt, "multi_modal_data": {"image": model_image(store.gray(r["key"]), a.H)}} for r in part]
                for r, o in zip(part, llm.generate(reqs, sp, lora_request=lr, use_tqdm=False)):
                    c = o.outputs[0]
                    lps = [lp[t].logprob for t, lp in zip(c.token_ids, c.logprobs or []) if lp and t in lp]
                    f.write(json.dumps(dict(key=r["key"], adapter=name, text=c.text.strip(), finish=c.finish_reason,
                                            prompt_tokens=len(o.prompt_token_ids), out_tokens=len(c.token_ids),
                                            **lp_stats(lps)), ensure_ascii=False) + "\n")
                f.flush()
                n += len(part)
                print(f"{time.strftime('%H:%M:%S')} {name}: {n}/{len(todo)} ({n / max(1e-6, time.time() - t0):.1f} lines/s)", flush=True)
            stats.append(dict(adapter=name, lines=n, lines_per_s=round(n / max(1e-6, time.time() - t0), 2)))
    Path(a.out + ".summary.json").write_text(json.dumps(dict(stats=stats, set=a.set, H=a.H), indent=1))


def force(a):
    from vllm import SamplingParams
    from vllm.lora.request import LoRARequest
    cands = [json.loads(l) for l in open(a.cands, encoding="utf-8")]
    store = D.LineStore(a.crops)
    cands = [c for c in cands if c["key"] in store]
    done = set()
    if Path(a.out).exists():
        done = {(d["key"], d["cid"]) for d in map(json.loads, open(a.out, encoding="utf-8"))}
    cands = [c for c in cands if (c["key"], c["cid"]) not in done]
    llm, tok, prompt = engine(a, bool(a.adapters))
    n_prompt = len(tok(prompt, add_special_tokens=False)["input_ids"])
    sp = SamplingParams(temperature=0.0, max_tokens=1, prompt_logprobs=0)
    lr = LoRARequest("a0", 1, a.adapters[0]) if a.adapters else None
    with open(a.out, "a", encoding="utf-8") as f:
        for i in range(0, len(cands), a.chunk):
            part = cands[i:i + a.chunk]
            reqs = [{"prompt": prompt + c["text"] + "<|im_end|>",
                     "multi_modal_data": {"image": model_image(store.gray(c["key"]), a.H)}} for c in part]
            for c, o in zip(part, llm.generate(reqs, sp, lora_request=lr, use_tqdm=False)):
                ids = o.prompt_token_ids
                # the answer = the tokens after the text prompt; the image placeholder expands inside the prompt, so
                # count the answer from the END: tokenise the answer alone
                n_ans = len(tok(c["text"] + "<|im_end|>", add_special_tokens=False)["input_ids"])
                pl = o.prompt_logprobs or []
                lps = []
                for t, d in zip(ids[-n_ans:], pl[-n_ans:]):
                    if d and t in d:
                        lps.append(d[t].logprob)
                f.write(json.dumps(dict(key=c["key"], cid=c["cid"], n_prompt_text=n_prompt, **lp_stats(lps)),
                                   ensure_ascii=False) + "\n")
            f.flush()
            print(f"{time.strftime('%H:%M:%S')} force {min(len(cands), i + a.chunk)}/{len(cands)}", flush=True)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("cmd", choices=["read", "force"])
    ap.add_argument("--model", required=True)
    ap.add_argument("--set")
    ap.add_argument("--cands")
    ap.add_argument("--crops", nargs="+", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--adapters", nargs="*", default=[])
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
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    {"read": read, "force": force}[a.cmd](a)


if __name__ == "__main__":
    main()
