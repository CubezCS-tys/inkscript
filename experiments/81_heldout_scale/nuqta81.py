"""Experiment 81: Nuqta-Arabic-OCR-4B on the held-out LINE crops (runs on the rented GPU host, /work).

    bash setup_nuqta81.sh                       (env + pinned weights, as experiment 75's workers/setup_gpu.sh)
    /opt/nuqta/bin/python nuqta81.py --crops /work/crops --list /work/nuqta_lines.txt --out /work/out/nuqta81.jsonl

Model, prompt and settings are experiment 75's nuqta_worker.py, imported unchanged: the card-default prompt
"as_written", greedy decoding, bf16, enable_thinking=False, the card's prepare() (a line crop is far below 2.4 MP, so
it is passed as is) and the speed fix (patch embedding as F.linear, identical text on exp 75's lab documents).
Input = the same 96-px line crops (300-dpi renders) the Gemini judge sees.  Lines are batched (left padding) for
speed; max_new_tokens 256 (a line).  Every reading is appended at once (a lost host loses nothing fetched).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, os.environ.get("X75", "/work/x75/workers"))
from nuqta_worker import PROMPTS, conv3d_as_linear, prepare  # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--crops", default="/work/crops")
    ap.add_argument("--list", default="/work/nuqta_lines.txt")
    ap.add_argument("--out", default="/work/out/nuqta81.jsonl")
    ap.add_argument("--model", default="/work/models/Nuqta-Arabic-OCR-4B")
    ap.add_argument("--batch", type=int, default=16)
    ap.add_argument("--max_new", type=int, default=256)
    a = ap.parse_args()
    import torch
    from PIL import Image
    from transformers import AutoModelForImageTextToText, AutoProcessor
    proc = AutoProcessor.from_pretrained(a.model)
    proc.tokenizer.padding_side = "left"
    model = AutoModelForImageTextToText.from_pretrained(a.model, dtype=torch.bfloat16, device_map="cuda").eval()
    patched = conv3d_as_linear(model)
    keys = [l.strip() for l in open(a.list) if l.strip()]
    Path(a.out).parent.mkdir(parents=True, exist_ok=True)
    done = {json.loads(l)["key"] for l in open(a.out)} if os.path.exists(a.out) else set()
    keys = [k for k in keys if k not in done and os.path.exists(f"{a.crops}/{k}.png")]
    print(f"{len(keys)} lines; patched convs {patched}", flush=True)
    eos = model.generation_config.eos_token_id
    eos = set(eos if isinstance(eos, list) else [eos])
    t0 = time.time()
    with open(a.out, "a", encoding="utf-8") as fo:
        for j in range(0, len(keys), a.batch):
            b = keys[j:j + a.batch]
            ims = [prepare(Image.open(f"{a.crops}/{k}.png").convert("RGB")) for k in b]
            msgs = [[{"role": "user", "content": [{"type": "image", "image": im},
                                                   {"type": "text", "text": PROMPTS["as_written"]}]}] for im in ims]
            inp = proc.apply_chat_template(msgs, add_generation_prompt=True, tokenize=True, return_dict=True,
                                           return_tensors="pt", padding=True, enable_thinking=False).to(model.device)
            with torch.inference_mode():
                out = model.generate(**inp, max_new_tokens=a.max_new, do_sample=False)
            gen = out[:, inp["input_ids"].shape[1]:]
            for k, g in zip(b, gen):
                ids = [int(x) for x in g if int(x) != (proc.tokenizer.pad_token_id or -1)]
                text = proc.decode(ids, skip_special_tokens=True)
                fo.write(json.dumps(dict(key=k, nuqta=text, n_tok=len(ids), stopped=bool(set(ids) & eos)),
                                    ensure_ascii=False) + "\n")
            fo.flush()
            if (j // a.batch) % 20 == 0:
                print(f"{j + len(b)}/{len(keys)} {time.time() - t0:.0f}s", flush=True)
    print("NUQTA_DONE", time.time() - t0, flush=True)


if __name__ == "__main__":
    main()
